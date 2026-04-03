"""
MyCow CronScheduler
Gestisce l'esecuzione pianificata degli agenti via APScheduler.

Formato cron.yaml supportato:
  crons:
    - id: morning
      schedule: "0 8 * * *"
      model: claude-haiku-4-5-20251001
      prompt: "Testo del prompt..."
    - id: evening
      schedule: "0 18 * * *"
      model: claude-sonnet-4-6
      prompt: "Altro prompt..."

Job ID interno: "{agent_name}__{cron_id}"
Supporta hot-reload: modifica cron.yaml senza riavviare il daemon.
"""

import json
import logging
import threading
from datetime import timezone
from pathlib import Path

import yaml
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger("mycow.scheduler")

ROOT_DIR = Path(__file__).parent.parent
AGENTS_DIR = ROOT_DIR / "agents"
EMERGENCY_STOP_FILE = ROOT_DIR / "EMERGENCY_STOP"

HOT_RELOAD_INTERVAL = 30  # secondi
JOB_SEP = "__"  # separatore agent_name e cron_id nel job ID


def _job_id(agent_name: str, cron_id: str) -> str:
    return f"{agent_name}{JOB_SEP}{cron_id}"


def _parse_job_id(job_id: str) -> tuple[str, str]:
    parts = job_id.split(JOB_SEP, 1)
    return (parts[0], parts[1]) if len(parts) == 2 else (job_id, "")


class CronScheduler:
    def __init__(self):
        self._scheduler = BackgroundScheduler(timezone="UTC")
        self._reload_thread: threading.Thread | None = None
        self._stop_reload = threading.Event()
        self._yaml_mtimes: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Pubblici
    # ------------------------------------------------------------------

    def start(self):
        self._register_all_agents()
        self._scheduler.start()
        logger.info("CronScheduler avviato. Job attivi: %d", len(self._scheduler.get_jobs()))
        self._start_hot_reload()

    def stop(self):
        self._stop_reload.set()
        if self._reload_thread and self._reload_thread.is_alive():
            self._reload_thread.join(timeout=5)
        self._scheduler.shutdown(wait=False)
        logger.info("CronScheduler fermato.")

    def pause_agent(self, agent_name: str):
        """Mette in pausa tutti i cron di un agente."""
        paused = 0
        for job in self._scheduler.get_jobs():
            name, _ = _parse_job_id(job.id)
            if name == agent_name:
                try:
                    self._scheduler.pause_job(job.id)
                    paused += 1
                except Exception as e:
                    logger.warning("[%s] pause fallito per job %s: %s", agent_name, job.id, e)
        logger.info("[%s] %d cron in pausa.", agent_name, paused)

    def resume_agent(self, agent_name: str):
        """Riprende tutti i cron di un agente."""
        resumed = 0
        for job in self._scheduler.get_jobs():
            name, _ = _parse_job_id(job.id)
            if name == agent_name:
                try:
                    self._scheduler.resume_job(job.id)
                    resumed += 1
                except Exception as e:
                    logger.warning("[%s] resume fallito per job %s: %s", agent_name, job.id, e)
        logger.info("[%s] %d cron ripresi.", agent_name, resumed)

    def list_jobs(self) -> list[dict]:
        """Restituisce tutti i job con stato e prossima esecuzione."""
        jobs = []
        registered_agents = set()

        for job in self._scheduler.get_jobs():
            agent_name, cron_id = _parse_job_id(job.id)
            registered_agents.add(agent_name)
            nrt = getattr(job, "next_run_time", None)
            jobs.append({
                "agent": agent_name,
                "cron_id": cron_id,
                "job_id": job.id,
                "schedule": str(job.trigger),
                "next_run": nrt.isoformat() if nrt else None,
                "last_run": self._get_last_run(agent_name, cron_id),
                "status": "paused" if nrt is None else "active",
            })

        # Agenti senza job (disabilitati o senza crons)
        if AGENTS_DIR.exists():
            for agent_dir in AGENTS_DIR.iterdir():
                if agent_dir.is_dir() and agent_dir.name not in registered_agents:
                    jobs.append({
                        "agent": agent_dir.name,
                        "cron_id": None,
                        "job_id": None,
                        "schedule": None,
                        "next_run": None,
                        "last_run": None,
                        "status": "disabled",
                    })
        return jobs

    # ------------------------------------------------------------------
    # Privati — registrazione job
    # ------------------------------------------------------------------

    def _register_all_agents(self):
        if not AGENTS_DIR.exists():
            return
        for agent_dir in AGENTS_DIR.iterdir():
            if agent_dir.is_dir():
                self._register_agent(agent_dir.name)

    def _register_agent(self, agent_name: str):
        config = self._load_config(agent_name)
        if config is None:
            return

        crons = config.get("crons", [])
        if not crons:
            logger.debug("[%s] Nessun cron configurato.", agent_name)
            return

        # Rimuovi tutti i job esistenti dell'agente (hot-reload)
        self._unregister_agent(agent_name)

        for entry in crons:
            cron_id = entry.get("id") or entry.get("name", "default")
            schedule = entry.get("schedule")
            if not schedule:
                logger.warning("[%s][%s] Campo 'schedule' mancante - skip.", agent_name, cron_id)
                continue
            try:
                trigger = CronTrigger.from_crontab(schedule, timezone="UTC")
            except Exception as e:
                logger.error("[%s][%s] Cron expression non valida '%s': %s", agent_name, cron_id, schedule, e)
                continue

            jid = _job_id(agent_name, cron_id)
            self._scheduler.add_job(
                func=self._run_cron_entry,
                trigger=trigger,
                id=jid,
                name=jid,
                args=[agent_name, entry, config],
                max_instances=1,
                coalesce=True,
                misfire_grace_time=300,
            )
            logger.info("[%s][%s] Cron registrato: %s model=%s",
                        agent_name, cron_id, schedule, entry.get("model", "default"))

    def _unregister_agent(self, agent_name: str):
        for job in self._scheduler.get_jobs():
            name, _ = _parse_job_id(job.id)
            if name == agent_name:
                self._scheduler.remove_job(job.id)
                logger.debug("[%s] Job rimosso: %s", agent_name, job.id)

    # ------------------------------------------------------------------
    # Privati — esecuzione job
    # ------------------------------------------------------------------

    def _run_cron_entry(self, agent_name: str, entry: dict, config: dict):
        cron_id = entry.get("id") or entry.get("name", "default")

        if EMERGENCY_STOP_FILE.exists():
            logger.warning("[%s][%s] EMERGENCY_STOP attivo - skip.", agent_name, cron_id)
            return

        prompt = entry.get("prompt", "").strip()
        if not prompt:
            logger.warning("[%s][%s] Campo 'prompt' mancante nel cron - skip.", agent_name, cron_id)
            return

        model = entry.get("model") or config.get("model")
        logger.info("[%s][%s] Avvio. model=%s", agent_name, cron_id, model or "default")

        try:
            from daemon.agent_runner import run_agent
            result = run_agent(
                agent_name=agent_name,
                prompt=prompt,
                trigger=f"cron:{cron_id}",
                cron_config=config,
                model=model,
            )
            if result.get("status") != "success":
                self._notify_error(agent_name, cron_id, result.get("error", "Errore sconosciuto"), config)
        except Exception as e:
            logger.exception("[%s][%s] Errore inatteso: %s", agent_name, cron_id, e)
            self._notify_error(agent_name, cron_id, str(e), config)

    # ------------------------------------------------------------------
    # Privati — lettura config
    # ------------------------------------------------------------------

    def _load_config(self, agent_name: str) -> dict | None:
        yaml_path = AGENTS_DIR / agent_name / "cron.yaml"
        if not yaml_path.exists():
            return None
        try:
            with open(yaml_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except Exception as e:
            logger.error("[%s] Errore lettura cron.yaml: %s", agent_name, e)
            return None
        if not config.get("enabled", True):
            return None
        return config

    # ------------------------------------------------------------------
    # Privati — hot-reload
    # ------------------------------------------------------------------

    def _start_hot_reload(self):
        self._stop_reload.clear()
        self._reload_thread = threading.Thread(
            target=self._hot_reload_loop, daemon=True, name="cron-hot-reload"
        )
        self._reload_thread.start()

    def _hot_reload_loop(self):
        self._yaml_mtimes = self._snapshot_mtimes()
        while not self._stop_reload.wait(HOT_RELOAD_INTERVAL):
            current = self._snapshot_mtimes()

            for name, mtime in current.items():
                if self._yaml_mtimes.get(name) != mtime:
                    logger.info("[%s] cron.yaml modificato - aggiorno job.", name)
                    self._register_agent(name)

            for name in self._yaml_mtimes:
                if name not in current:
                    self._unregister_agent(name)

            self._yaml_mtimes = current

    def _snapshot_mtimes(self) -> dict[str, float]:
        mtimes = {}
        if not AGENTS_DIR.exists():
            return mtimes
        for agent_dir in AGENTS_DIR.iterdir():
            yaml_path = agent_dir / "cron.yaml"
            if yaml_path.exists():
                mtimes[agent_dir.name] = yaml_path.stat().st_mtime
        return mtimes

    # ------------------------------------------------------------------
    # Privati — utility
    # ------------------------------------------------------------------

    def _get_last_run(self, agent_name: str, cron_id: str) -> str | None:
        log_dir = AGENTS_DIR / agent_name / "logs"
        if not log_dir.exists():
            return None
        trigger_key = f"cron:{cron_id}"
        log_files = sorted(log_dir.glob("*.jsonl"), reverse=True)
        for log_file in log_files:
            try:
                lines = log_file.read_text(encoding="utf-8").strip().splitlines()
                for line in reversed(lines):
                    try:
                        entry = json.loads(line)
                        if entry.get("trigger") == trigger_key:
                            return entry.get("timestamp")
                    except Exception:
                        pass
            except Exception:
                pass
        return None

    def _notify_error(self, agent_name: str, cron_id: str, error: str, config: dict):
        try:
            import os
            from daemon.telegram_bridge import TelegramBridge
            chat_id = config.get("telegram_chat_id") or os.environ.get("TELEGRAM_CHAT_ID")
            if chat_id:
                TelegramBridge().send_message(
                    f"[{agent_name}][{cron_id}] Errore: {error}", chat_id=chat_id
                )
        except ImportError:
            pass
        except Exception as e:
            logger.debug("Notifica Telegram fallita: %s", e)
