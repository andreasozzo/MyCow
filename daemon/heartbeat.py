"""
MyCow HeartbeatManager
Loop autonomo che fa valutare agli agenti se agire ogni N secondi.
Differenza chiave vs CronScheduler: il cron ESEGUE sempre,
il heartbeat lascia decidere all'agente se agire o no.
"""

import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

logger = logging.getLogger("mycow.heartbeat")

ROOT_DIR = Path(__file__).parent.parent
AGENTS_DIR = ROOT_DIR / "agents"
EMERGENCY_STOP_FILE = ROOT_DIR / "EMERGENCY_STOP"


class HeartbeatManager:
    def __init__(self):
        self._stop_event = threading.Event()
        self._threads: dict[str, threading.Thread] = {}
        self._paused: set[str] = set()
        self._last_tick: dict[str, str] = {}       # agent_name → ISO timestamp
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Pubblici
    # ------------------------------------------------------------------

    def start(self):
        self._stop_event.clear()
        self._reload_agents()
        logger.info("HeartbeatManager avviato. Agenti: %d", len(self._threads))

    def stop(self):
        self._stop_event.set()
        for name, t in list(self._threads.items()):
            t.join(timeout=5)
        self._threads.clear()
        logger.info("HeartbeatManager fermato.")

    def pause_agent(self, name: str):
        with self._lock:
            self._paused.add(name)
        logger.info("[%s] Heartbeat in pausa.", name)

    def resume_agent(self, name: str):
        with self._lock:
            self._paused.discard(name)
        logger.info("[%s] Heartbeat ripreso.", name)

    def get_status(self) -> list[dict]:
        statuses = []
        if not AGENTS_DIR.exists():
            return statuses
        for agent_dir in AGENTS_DIR.iterdir():
            if not agent_dir.is_dir():
                continue
            name = agent_dir.name
            config = self._load_heartbeat_config(name)
            interval = config.get("heartbeat", 0) if config else 0
            if interval <= 0:
                continue
            with self._lock:
                paused = name in self._paused
                last_tick = self._last_tick.get(name)
            thread = self._threads.get(name)
            if paused:
                status = "paused"
            elif thread and thread.is_alive():
                status = "active"
            else:
                status = "stopped"
            next_tick = None
            if last_tick and not paused:
                try:
                    last_dt = datetime.fromisoformat(last_tick)
                    from datetime import timedelta
                    next_dt = last_dt + timedelta(seconds=interval)
                    next_tick = next_dt.isoformat()
                except Exception:
                    pass
            statuses.append({
                "name": name,
                "interval": interval,
                "last_tick": last_tick,
                "next_tick": next_tick,
                "status": status,
            })
        return statuses

    # ------------------------------------------------------------------
    # Privati — caricamento agenti
    # ------------------------------------------------------------------

    def _reload_agents(self):
        if not AGENTS_DIR.exists():
            return
        for agent_dir in AGENTS_DIR.iterdir():
            if not agent_dir.is_dir():
                continue
            name = agent_dir.name
            config = self._load_heartbeat_config(name)
            if not config:
                continue
            interval = config.get("heartbeat", 0)
            if interval <= 0:
                continue
            if name not in self._threads or not self._threads[name].is_alive():
                t = threading.Thread(
                    target=self._heartbeat_loop,
                    args=[name, interval],
                    daemon=True,
                    name=f"hb-{name}",
                )
                self._threads[name] = t
                t.start()
                logger.info("[%s] Heartbeat avviato (intervallo: %ds).", name, interval)

    def _load_heartbeat_config(self, name: str) -> dict | None:
        yaml_path = AGENTS_DIR / name / "cron.yaml"
        if not yaml_path.exists():
            return None
        try:
            with open(yaml_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except Exception as e:
            logger.error("[%s] Errore lettura cron.yaml: %s", name, e)
            return None
        if not config.get("enabled", True):
            return None
        return config

    # ------------------------------------------------------------------
    # Privati — loop heartbeat
    # ------------------------------------------------------------------

    def _heartbeat_loop(self, name: str, interval: int):
        while not self._stop_event.is_set():
            # Attendi l'intervallo (o stop anticipato)
            self._stop_event.wait(timeout=interval)
            if self._stop_event.is_set():
                break

            with self._lock:
                is_paused = name in self._paused

            if is_paused:
                continue

            if EMERGENCY_STOP_FILE.exists():
                logger.warning("[%s] EMERGENCY_STOP attivo - heartbeat skippato.", name)
                continue

            self._tick(name, interval)

    def _tick(self, name: str, interval: int):
        config = self._load_heartbeat_config(name)
        if config is None:
            return

        prompt = self._extract_heartbeat_prompt(name)
        if not prompt:
            logger.warning("[%s] Nessun ## Heartbeat Behavior in CLAUDE.md - skip.", name)
            return

        # Timeout = min(interval * 0.8, 300)
        timeout = int(min(interval * 0.8, 300))

        tick_start = time.monotonic()
        logger.info("[%s] Heartbeat tick.", name)

        try:
            from daemon.agent_runner import run_agent
            result = run_agent(
                agent_name=name,
                prompt=prompt,
                trigger="heartbeat",
                cron_config=config,
                timeout=timeout,
                model=config.get("heartbeat_model") or config.get("model"),
            )
            duration = time.monotonic() - tick_start

            # Warn se impiega più del doppio dell'intervallo
            if duration > interval * 2:
                msg = f"Heartbeat lento: {duration:.0f}s (intervallo {interval}s)"
                logger.warning("[%s] %s", name, msg)
                self._notify_telegram(name, msg, config)

            if result.get("status") != "success":
                self._notify_telegram(name, f"Errore heartbeat: {result.get('error')}", config)

        except Exception as e:
            logger.exception("[%s] Errore inatteso nel heartbeat: %s", name, e)
            self._notify_telegram(name, f"Crash heartbeat: {e}", config)

        with self._lock:
            self._last_tick[name] = datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Privati — lettura prompt
    # ------------------------------------------------------------------

    def _extract_heartbeat_prompt(self, name: str) -> str:
        claude_md = AGENTS_DIR / name / "CLAUDE.md"
        if not claude_md.exists():
            return ""
        try:
            content = claude_md.read_text(encoding="utf-8")
        except OSError:
            return ""

        match = re.search(r"##\s+Heartbeat Behavior\b", content, re.IGNORECASE)
        if match:
            start = match.end()
            next_header = re.search(r"\n##\s+", content[start:])
            end = start + next_header.start() if next_header else len(content)
            prompt = content[start:end].strip()
            if prompt:
                return prompt[:4000]
        return ""

    # ------------------------------------------------------------------
    # Privati — notifiche
    # ------------------------------------------------------------------

    def _notify_telegram(self, name: str, message: str, config: dict):
        try:
            from daemon.telegram_bridge import TelegramBridge
            chat_id = config.get("telegram_chat_id") or os.environ.get("TELEGRAM_CHAT_ID")
            if chat_id:
                TelegramBridge().send_message(f"[{name}] {message}", chat_id=chat_id)
        except ImportError:
            pass
        except Exception as e:
            logger.debug("Notifica Telegram fallita: %s", e)
