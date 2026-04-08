"""
MyCow Daemon - Entrypoint
Starts and coordinates: API REST, CronScheduler, HeartbeatManager, TelegramBridge.
"""

import argparse
import logging
import os
import socket
import sys
import time
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

# Ensures the project root is in sys.path when main.py is run
# directly (e.g. python daemon/main.py)
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Load .env from project root
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(dotenv_path=_env_path, override=True)
except ImportError:
    print("[WARNING] python-dotenv not installed. Run: pip install -r requirements.txt")

# --- Logging ----------------------------------------------------------

LOG_BUFFER: deque = deque(maxlen=1000)

class MemoryLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            LOG_BUFFER.append({
                "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "level": record.levelname,
                "logger": record.name,
                "message": self.format(record),
            })
        except Exception:
            pass

def setup_logging(level: str = "INFO") -> logging.Logger:
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    mem_handler = MemoryLogHandler()
    mem_handler.setLevel(log_level)
    logging.getLogger().addHandler(mem_handler)
    return logging.getLogger("mycow")

logger = setup_logging(os.environ.get("MYCOW_LOG_LEVEL", "INFO"))

# --- Constants ---------------------------------------------------------

ROOT_DIR = Path(__file__).parent.parent
EMERGENCY_STOP_FILE = ROOT_DIR / "EMERGENCY_STOP"
PORT = int(os.environ.get("MYCOW_PORT", 3333))

# --- Child module imports (graceful) -----------------------------------

_api = None
_scheduler = None
_heartbeat = None
_telegram = None

def _load_modules():
    global _api, _scheduler, _heartbeat, _telegram

    try:
        from daemon import api as _api_module
        _api = _api_module
        logger.debug("Module api loaded.")
    except ImportError:
        logger.warning("Module api.py not yet implemented - Web UI unavailable.")

    try:
        from daemon import scheduler as _sched_module
        _scheduler = _sched_module
        logger.debug("Module scheduler loaded.")
    except ImportError:
        logger.warning("Module scheduler.py not yet implemented - Cron disabled.")

    try:
        from daemon import heartbeat as _hb_module
        _heartbeat = _hb_module
        logger.debug("Module heartbeat loaded.")
    except ImportError:
        logger.warning("Module heartbeat.py not yet implemented - Heartbeat disabled.")

    try:
        from daemon import telegram_bridge as _tg_module
        _telegram = _tg_module
        logger.debug("Module telegram_bridge loaded.")
    except ImportError:
        logger.warning("Module telegram_bridge.py not yet implemented - Telegram disabled.")

# --- Port utilities ---------------------------------------------------

def _find_free_port(start: int = 3333, max_attempts: int = 10) -> int:
    for port in range(start, start + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError(f"No free port found between {start} and {start + max_attempts}")


def _update_env_port(port: int) -> None:
    """Persists the port to the .env file."""
    env_path = ROOT_DIR / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    key = "MYCOW_PORT"
    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={port}"
            found = True
            break
    if not found:
        lines.append(f"{key}={port}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --- CLI Commands -------------------------------------------------------

def cmd_start(args):
    logger.info("Starting MyCow daemon...")

    if EMERGENCY_STOP_FILE.exists():
        logger.error(
            "EMERGENCY_STOP file found in root. Remove it to start: %s",
            EMERGENCY_STOP_FILE,
        )
        sys.exit(1)

    _load_modules()

    # Port auto-detection
    requested_port = PORT
    port = _find_free_port(requested_port)
    if port != requested_port:
        logger.warning("Port %d in use, switching to %d", requested_port, port)
        _update_env_port(port)
        os.environ["MYCOW_PORT"] = str(port)
    else:
        port = requested_port

    started = []
    sched_instance = None
    hb_instance = None
    tg_instance = None

    if _scheduler:
        try:
            sched_instance = _scheduler.CronScheduler()
            sched_instance.start()
            started.append("CronScheduler")
        except Exception as e:
            logger.error("Error starting CronScheduler: %s", e)

    if _heartbeat:
        try:
            hb_instance = _heartbeat.HeartbeatManager()
            hb_instance.start()
            started.append("HeartbeatManager")
        except Exception as e:
            logger.error("Error starting HeartbeatManager: %s", e)

    if _telegram:
        try:
            tg_instance = _telegram.TelegramBridge()
            tg_instance._scheduler = sched_instance
            tg_instance._heartbeat = hb_instance
            tg_instance.start()
            started.append("TelegramBridge")
        except Exception as e:
            logger.error("Error starting TelegramBridge: %s", e)

    if _api:
        logger.info("Web UI available at http://127.0.0.1:%d", port)
        started.append("API")
        try:
            flask_app = _api.create_app(
                scheduler=sched_instance,
                heartbeat_mgr=hb_instance,
                telegram=tg_instance,
                log_buffer=LOG_BUFFER,
            )
            flask_app.run(host="127.0.0.1", port=port, use_reloader=False)
        except Exception as e:
            logger.error("Error starting API: %s", e)
    else:
        if started:
            logger.info("Components started: %s", ", ".join(started))
            logger.info("Daemon running. Press Ctrl+C to stop.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Manual interrupt. Stopping daemon.")
        else:
            logger.warning(
                "No modules available. "
                "Implement modules in daemon/ and restart."
            )


def cmd_stop(args):
    logger.info("Creating EMERGENCY_STOP file to halt all agents...")
    EMERGENCY_STOP_FILE.touch()
    logger.info("EMERGENCY_STOP created. The daemon will not start new agents.")
    logger.info("To remove the block: delete the file %s", EMERGENCY_STOP_FILE)


def cmd_status(args):
    _load_modules()

    print("\n=== MyCow Status ===")
    print(f"Root:            {ROOT_DIR}")
    print(f"Port:            {PORT}")
    print(f"Emergency stop:  {'YES - daemon blocked' if EMERGENCY_STOP_FILE.exists() else 'no'}")
    print()

    agents_dir = ROOT_DIR / "agents"
    agents = [d for d in agents_dir.iterdir() if d.is_dir()] if agents_dir.exists() else []
    print(f"Agents defined:  {len(agents)}")
    for agent in agents:
        print(f"  - {agent.name}")

    print()
    print("Modules:")
    modules = {
        "api.py":             _api,
        "scheduler.py":       _scheduler,
        "heartbeat.py":       _heartbeat,
        "telegram_bridge.py": _telegram,
    }
    for name, mod in modules.items():
        status = "[ok] available" if mod else "[--] not implemented"
        print(f"  {name:<22} {status}")
    print()

# --- Entrypoint --------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="mycow",
        description="MyCow - The proactive layer for Claude Code",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    subparsers.required = True

    p_start = subparsers.add_parser("start", help="Start the MyCow daemon")
    p_start.set_defaults(func=cmd_start)

    p_stop = subparsers.add_parser("stop", help="Stop all agents (creates EMERGENCY_STOP)")
    p_stop.set_defaults(func=cmd_stop)

    p_status = subparsers.add_parser("status", help="Show daemon and agent status")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
