"""
MyCow Telegram Bridge
Bot bidirezionale: riceve comandi, invia notifiche dagli agenti.
Architettura pull — nessuna porta in ascolto, zero attack surface.
"""

import logging
import os
import threading
from pathlib import Path

logger = logging.getLogger("mycow.telegram")

ROOT_DIR = Path(__file__).parent.parent
AGENTS_DIR = ROOT_DIR / "agents"
EMERGENCY_STOP_FILE = ROOT_DIR / "EMERGENCY_STOP"

MAX_PROMPT_LENGTH = 2000
FORBIDDEN_PATTERNS = [
    "--dangerously",
    "--allowedTools Bash(*)",
    "rm -rf",
    "format c:",
    "del /f /s",
]


def sanitize_input(text: str) -> str:
    if len(text) > MAX_PROMPT_LENGTH:
        raise ValueError(f"Input troppo lungo (max {MAX_PROMPT_LENGTH} char)")
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.lower() in text.lower():
            raise ValueError(f"Pattern non consentito: {pattern}")
    return text.strip()


class TelegramBridge:
    def __init__(self):
        self._token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._allowed_chat_ids = self._load_allowed_chats()
        self._app = None
        self._thread: threading.Thread | None = None
        self._scheduler = None   # iniettato da main.py dopo l'avvio
        self._heartbeat = None   # iniettato da main.py dopo l'avvio

    def _load_allowed_chats(self) -> set[str]:
        raw = os.environ.get("TELEGRAM_CHAT_ID", "")
        return {c.strip() for c in raw.split(",") if c.strip()}

    # ------------------------------------------------------------------
    # Pubblici
    # ------------------------------------------------------------------

    def start(self):
        if not self._token:
            logger.warning("TELEGRAM_BOT_TOKEN non configurato - bridge disabilitato.")
            return
        self._thread = threading.Thread(
            target=self._run_polling, daemon=True, name="telegram-bridge"
        )
        self._thread.start()
        logger.info("Telegram Bridge avviato (polling).")

    def stop(self):
        if self._app:
            try:
                self._app.stop()
            except Exception:
                pass
        logger.info("Telegram Bridge fermato.")

    def send_message(self, text: str, chat_id: str | None = None) -> bool:
        """
        Invia un messaggio Telegram. Chiamabile da agent_runner e heartbeat.
        Non-bloccante: usa asyncio in un thread separato se necessario.
        """
        if not self._token:
            logger.debug("send_message ignorato: token non configurato.")
            return False
        target = chat_id or (next(iter(self._allowed_chat_ids), None))
        if not target:
            logger.warning("send_message: nessun chat_id configurato.")
            return False
        try:
            import asyncio
            import telegram
            async def _send():
                bot = telegram.Bot(token=self._token)
                await bot.send_message(
                    chat_id=target,
                    text=text[:4096],
                    parse_mode="Markdown",
                )
            asyncio.run(_send())
            return True
        except Exception as e:
            logger.error("Errore invio Telegram: %s", e)
            return False

    # ------------------------------------------------------------------
    # Privati — polling loop
    # ------------------------------------------------------------------

    def _run_polling(self):
        try:
            from telegram.ext import Application, CommandHandler, MessageHandler, filters

            app = Application.builder().token(self._token).build()
            self._app = app

            for cmd_name in ["start", "status", "agents", "run", "stop",
                             "pause", "resume", "logs", "schedule",
                             "heartbeat", "skills"]:
                method = getattr(self, f"_cmd_{cmd_name}", None)
                if method:
                    app.add_handler(CommandHandler(cmd_name, method))

            # Messaggi liberi → inoltrati all'agente
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

            logger.info("Bot Telegram in ascolto...")
            app.run_polling(drop_pending_updates=True)
        except Exception as e:
            logger.exception("Errore fatale Telegram polling: %s", e)

    def _is_allowed(self, chat_id: str) -> bool:
        if not self._allowed_chat_ids:
            return False  # nessuna whitelist = rifiuta tutto
        return str(chat_id) in self._allowed_chat_ids

    async def _handle_message(self, update, context):
        """Messaggio libero → inoltrato all'agente configurato per questo chat_id."""
        if not self._is_allowed(str(update.effective_chat.id)):
            return
        text = (update.message.text or "").strip()
        if not text:
            return

        # Trova l'agente associato a questo chat_id
        target_agent = None
        if AGENTS_DIR.exists():
            import yaml
            for d in AGENTS_DIR.iterdir():
                if not d.is_dir():
                    continue
                yaml_path = d / "cron.yaml"
                if not yaml_path.exists():
                    continue
                try:
                    cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
                    agent_chat_id = str(cfg.get("telegram_chat_id", ""))
                    if agent_chat_id == str(update.effective_chat.id):
                        target_agent = d.name
                        break
                except Exception:
                    continue

        if not target_agent:
            # Fallback: usa il primo agente disponibile
            dirs = [d for d in AGENTS_DIR.iterdir() if d.is_dir()] if AGENTS_DIR.exists() else []
            if dirs:
                target_agent = dirs[0].name
            else:
                await update.message.reply_text("Nessun agente configurato. Usa /agents.")
                return

        await update.message.reply_text(f"Inoltro a *{target_agent}*...", parse_mode="Markdown")
        threading.Thread(
            target=self._trigger_agent_with_prompt,
            args=[target_agent, text, update.effective_chat.id],
            daemon=True,
        ).start()

    def _trigger_agent_with_prompt(self, agent_name: str, prompt: str, chat_id):
        try:
            import yaml
            from daemon.agent_runner import run_agent
            yaml_path = AGENTS_DIR / agent_name / "cron.yaml"
            config = yaml.safe_load(yaml_path.read_text()) if yaml_path.exists() else {}
            crons = config.get("crons", [])
            model = (crons[0].get("model") if crons else None) or config.get("model")

            result = run_agent(
                agent_name, prompt, trigger="chat",
                cron_config=config, model=model,
                resume_session=True,
            )
            status = result.get("status", "unknown")
            output = (result.get("output") or "")[:1000]

            if output:
                self.send_message(output, str(chat_id))
            else:
                self.send_message(f"[{agent_name}] {status}", str(chat_id))
        except Exception as e:
            self.send_message(f"Errore: {e}", str(chat_id))

    # ------------------------------------------------------------------
    # Comandi in entrata
    # ------------------------------------------------------------------

    async def _cmd_start(self, update, context):
        if not self._is_allowed(str(update.effective_chat.id)):
            return
        await update.message.reply_text(
            "*MyCow* - The proactive layer for Claude Code\n\n"
            "Comandi disponibili:\n"
            "/status - stato daemon e agenti\n"
            "/agents - lista agenti\n"
            "/run <nome> - esegui agente manualmente\n"
            "/stop [nome] - ferma agente o tutti\n"
            "/pause <nome> - metti in pausa\n"
            "/resume <nome> - riprendi\n"
            "/logs <nome> - ultimi log\n"
            "/schedule <nome> - prossime esecuzioni\n"
            "/heartbeat <nome> - forza heartbeat\n"
            "/skills - skill installate",
            parse_mode="Markdown",
        )

    async def _cmd_status(self, update, context):
        if not self._is_allowed(str(update.effective_chat.id)):
            return
        emergency = EMERGENCY_STOP_FILE.exists()
        agents = [d.name for d in AGENTS_DIR.iterdir() if d.is_dir()] if AGENTS_DIR.exists() else []
        lines = [
            f"*MyCow Status*",
            f"Emergency stop: {'SI' if emergency else 'no'}",
            f"Agenti: {len(agents)}",
        ]
        if self._scheduler:
            jobs = self._scheduler.list_jobs()
            active = [j for j in jobs if j['status'] == 'active']
            lines.append(f"Cron attivi: {len(active)}")
        if self._heartbeat:
            hb = self._heartbeat.get_status()
            active_hb = [h for h in hb if h['status'] == 'active']
            lines.append(f"Heartbeat attivi: {len(active_hb)}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _cmd_agents(self, update, context):
        if not self._is_allowed(str(update.effective_chat.id)):
            return
        if not AGENTS_DIR.exists() or not any(AGENTS_DIR.iterdir()):
            await update.message.reply_text("Nessun agente configurato.")
            return
        lines = ["*Agenti*"]
        for d in AGENTS_DIR.iterdir():
            if d.is_dir():
                lines.append(f"- {d.name}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _cmd_run(self, update, context):
        if not self._is_allowed(str(update.effective_chat.id)):
            return
        if not context.args:
            await update.message.reply_text("Uso: /run <nome-agente>")
            return
        agent_name = context.args[0]
        agent_dir = AGENTS_DIR / agent_name
        if not agent_dir.exists():
            await update.message.reply_text(f"Agente '{agent_name}' non trovato.")
            return
        await update.message.reply_text(f"Avvio '{agent_name}'...")
        threading.Thread(
            target=self._trigger_agent,
            args=[agent_name, update.effective_chat.id],
            daemon=True,
        ).start()

    def _trigger_agent(self, agent_name: str, chat_id):
        try:
            import yaml
            from daemon.agent_runner import run_agent
            yaml_path = AGENTS_DIR / agent_name / "cron.yaml"
            config = yaml.safe_load(yaml_path.read_text()) if yaml_path.exists() else {}
            crons = config.get("crons", [])
            prompt = crons[0].get("prompt", "") if crons else ""
            model = (crons[0].get("model") if crons else None) or config.get("model")
            if not prompt:
                self.send_message(f"[{agent_name}] Nessun prompt configurato.", str(chat_id))
                return
            result = run_agent(agent_name, prompt, trigger="manual", cron_config=config, model=model)
            status = result.get("status", "unknown")
            output = (result.get("output") or "")[:500]
            self.send_message(f"[{agent_name}] {status}\n{output}", str(chat_id))
        except Exception as e:
            self.send_message(f"[{agent_name}] Errore: {e}", str(chat_id))

    async def _cmd_stop(self, update, context):
        if not self._is_allowed(str(update.effective_chat.id)):
            return
        if context.args:
            # Ferma agente specifico
            name = context.args[0]
            if self._scheduler:
                self._scheduler.pause_agent(name)
            if self._heartbeat:
                self._heartbeat.pause_agent(name)
            await update.message.reply_text(f"Agente '{name}' messo in pausa.")
        else:
            # Kill switch globale
            EMERGENCY_STOP_FILE.touch()
            if self._scheduler:
                self._scheduler.stop()
            if self._heartbeat:
                self._heartbeat.stop()
            await update.message.reply_text(
                "EMERGENCY_STOP attivato. Tutti gli agenti fermati.\n"
                "Rimuovi il file EMERGENCY_STOP per riabilitare."
            )

    async def _cmd_pause(self, update, context):
        if not self._is_allowed(str(update.effective_chat.id)):
            return
        if not context.args:
            await update.message.reply_text("Uso: /pause <nome-agente>")
            return
        name = context.args[0]
        if self._scheduler:
            self._scheduler.pause_agent(name)
        if self._heartbeat:
            self._heartbeat.pause_agent(name)
        await update.message.reply_text(f"'{name}' in pausa.")

    async def _cmd_resume(self, update, context):
        if not self._is_allowed(str(update.effective_chat.id)):
            return
        if not context.args:
            await update.message.reply_text("Uso: /resume <nome-agente>")
            return
        name = context.args[0]
        if self._scheduler:
            self._scheduler.resume_agent(name)
        if self._heartbeat:
            self._heartbeat.resume_agent(name)
        await update.message.reply_text(f"'{name}' ripreso.")

    async def _cmd_logs(self, update, context):
        if not self._is_allowed(str(update.effective_chat.id)):
            return
        if not context.args:
            await update.message.reply_text("Uso: /logs <nome-agente>")
            return
        name = context.args[0]
        from daemon.agent_runner import get_logs
        logs = get_logs(name, limit=5)
        if not logs:
            await update.message.reply_text(f"Nessun log per '{name}'.")
            return
        lines = [f"*Ultimi log — {name}*"]
        for entry in logs:
            ts = entry.get("timestamp", "")[:19]
            trigger = entry.get("trigger", "")
            status = entry.get("status", "")
            dur = entry.get("duration_seconds", 0)
            lines.append(f"`{ts}` [{trigger}] {status} ({dur}s)")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _cmd_schedule(self, update, context):
        if not self._is_allowed(str(update.effective_chat.id)):
            return
        if not context.args:
            await update.message.reply_text("Uso: /schedule <nome-agente>")
            return
        name = context.args[0]
        if not self._scheduler:
            await update.message.reply_text("Scheduler non disponibile.")
            return
        jobs = [j for j in self._scheduler.list_jobs() if j["agent"] == name]
        if not jobs:
            await update.message.reply_text(f"Nessun cron per '{name}'.")
            return
        lines = [f"*Schedule — {name}*"]
        for j in jobs:
            lines.append(f"[{j['cron_id']}] prossimo: {(j['next_run'] or 'N/A')[:19]}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _cmd_heartbeat(self, update, context):
        if not self._is_allowed(str(update.effective_chat.id)):
            return
        if not context.args:
            await update.message.reply_text("Uso: /heartbeat <nome-agente>")
            return
        name = context.args[0]
        if not self._heartbeat:
            await update.message.reply_text("HeartbeatManager non disponibile.")
            return
        await update.message.reply_text(f"Forzo heartbeat per '{name}'...")
        import yaml
        yaml_path = AGENTS_DIR / name / "cron.yaml"
        config = yaml.safe_load(yaml_path.read_text()) if yaml_path.exists() else {}
        interval = config.get("heartbeat", 3600)
        threading.Thread(
            target=self._heartbeat._tick,
            args=[name, interval],
            daemon=True,
        ).start()

    async def _cmd_skills(self, update, context):
        if not self._is_allowed(str(update.effective_chat.id)):
            return
        skills_dir = ROOT_DIR / "skills" / "global"
        if not skills_dir.exists():
            await update.message.reply_text("Nessuna skill installata.")
            return
        skills = [d.name for d in skills_dir.iterdir() if d.is_dir()]
        if not skills:
            await update.message.reply_text("Nessuna skill installata.")
            return
        lines = ["*Skill installate*"] + [f"- {s}" for s in skills]
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
