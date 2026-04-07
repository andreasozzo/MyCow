"""
MyCow CronScheduler
Manages scheduled agent execution via APScheduler.

Supported cron.yaml format:
  crons:
    - id: morning
      schedule: "0 8 * * *"
      model: claude-haiku-4-5-20251001
      prompt: "Prompt text..."
    - id: evening
      schedule: "0 18 * * *"
      model: claude-sonnet-4-6
      prompt: "Another prompt..."

Internal job ID: "{agent_name}__{cron_id}"
Supports hot-reload: modify cron.yaml without restarting the daemon.
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

HOT_RELOAD_INTERVAL = 30  # seconds
JOB_SEP = "__"  # separator between agent_name and cron_id in job ID


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
    # Public
    # ------------------------------------------------------------------

    def start(self):
        self._register_all_agents()
        self._scheduler.start()
        logger.info("CronScheduler started. Active jobs: %d", len(self._scheduler.get_jobs()))
        self._start_hot_reload()

    def stop(self):
        self._stop_reload.set()
        if self._reload_thread and self._reload_thread.is_alive():
            self._reload_thread.join(timeout=5)
        self._scheduler.shutdown(wait=False)
        logger.info("CronScheduler stopped.")

    def pause_agent(self, agent_name: str):
        """Pauses all crons for an agent."""
        paused = 0
        for job in self._scheduler.get_jobs():
            name, _ = _parse_job_id(job.id)
            if name == agent_name:
                try:
                    self._scheduler.pause_job(job.id)
                    paused += 1
                except Exception as e:
                    logger.warning("[%s] pause failed for job %s: %s", agent_name, job.id, e)
        logger.info("[%s] %d cron(s) paused.", agent_name, paused)

    def resume_agent(self, agent_name: str):
        """Resumes all crons for an agent."""
        resumed = 0
        for job in self._scheduler.get_jobs():
            name, _ = _parse_job_id(job.id)
            if name == agent_name:
                try:
                    self._scheduler.resume_job(job.id)
                    resumed += 1
                except Exception as e:
                    logger.warning("[%s] resume failed for job %s: %s", agent_name, job.id, e)
        logger.info("[%s] %d cron(s) resumed.", agent_name, resumed)

    def list_jobs(self) -> list[dict]:
        """Returns all jobs with their status and next run time."""
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

        # Agents without jobs (disabled or without crons)
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
    # Private — job registration
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
            logger.debug("[%s] No cron configured.", agent_name)
            return

        # Remove all existing jobs for the agent (hot-reload)
        self._unregister_agent(agent_name)

        for entry in crons:
            cron_id = entry.get("id") or entry.get("name", "default")
            schedule = entry.get("schedule")
            if not schedule:
                logger.warning("[%s][%s] Missing 'schedule' field - skipping.", agent_name, cron_id)
                continue
            try:
                trigger = CronTrigger.from_crontab(schedule, timezone="UTC")
            except Exception as e:
                logger.error("[%s][%s] Invalid cron expression '%s': %s", agent_name, cron_id, schedule, e)
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
                        agent_name, cron_id, schedule, entry.get("model", "default"))  # noqa

    def _unregister_agent(self, agent_name: str):
        for job in self._scheduler.get_jobs():
            name, _ = _parse_job_id(job.id)
            if name == agent_name:
                self._scheduler.remove_job(job.id)
                logger.debug("[%s] Job removed: %s", agent_name, job.id)

    # ------------------------------------------------------------------
    # Private — job execution
    # ------------------------------------------------------------------

    def _run_cron_entry(self, agent_name: str, entry: dict, config: dict):
        cron_id = entry.get("id") or entry.get("name", "default")

        if EMERGENCY_STOP_FILE.exists():
            logger.warning("[%s][%s] EMERGENCY_STOP active - skipping.", agent_name, cron_id)
            return

        prompt = entry.get("prompt", "").strip()
        if not prompt:
            logger.warning("[%s][%s] Missing 'prompt' field in cron - skipping.", agent_name, cron_id)
            return

        model = entry.get("model") or config.get("model")
        logger.info("[%s][%s] Starting. model=%s", agent_name, cron_id, model or "default")

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
                self._notify_error(agent_name, cron_id, result.get("error", "Unknown error"), config)
        except Exception as e:
            logger.exception("[%s][%s] Unexpected error: %s", agent_name, cron_id, e)
            self._notify_error(agent_name, cron_id, str(e), config)

    # ------------------------------------------------------------------
    # Private — config loading
    # ------------------------------------------------------------------

    def _load_config(self, agent_name: str) -> dict | None:
        yaml_path = AGENTS_DIR / agent_name / "cron.yaml"
        if not yaml_path.exists():
            return None
        try:
            with open(yaml_path, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except Exception as e:
            logger.error("[%s] Error reading cron.yaml: %s", agent_name, e)
            return None
        if not config.get("enabled", True):
            return None
        return config

    # ------------------------------------------------------------------
    # Private — hot-reload
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
                    logger.info("[%s] cron.yaml changed - updating jobs.", name)
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
    # Private — utilities
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
                    f"[{agent_name}][{cron_id}] Error: {error}", chat_id=chat_id
                )
        except ImportError:
            pass
        except Exception as e:
            logger.debug("Telegram notification failed: %s", e)
