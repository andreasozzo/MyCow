"""
MyCow Daemon - Entrypoint
Avvia e coordina: API REST, CronScheduler, HeartbeatManager, TelegramBridge.
"""

import argparse
import logging
import os
import socket
import sys
import time
from pathlib import Path

# Assicura che la root del progetto sia in sys.path quando main.py viene
# eseguito direttamente (es. python daemon/main.py)
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Carica .env dalla root del progetto
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(dotenv_path=_env_path)
except ImportError:
    print("[WARNING] python-dotenv non installato. Esegui: pip install -r requirements.txt")

# --- Logging -----------------------------------------------------------

def setup_logging(level: str = "INFO") -> logging.Logger:
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger("mycow")

logger = setup_logging(os.environ.get("MYCOW_LOG_LEVEL", "INFO"))

# --- Costanti ----------------------------------------------------------

ROOT_DIR = Path(__file__).parent.parent
EMERGENCY_STOP_FILE = ROOT_DIR / "EMERGENCY_STOP"
PORT = int(os.environ.get("MYCOW_PORT", 3333))

# --- Import moduli figli (graceful) ------------------------------------

_api = None
_scheduler = None
_heartbeat = None
_telegram = None

def _load_modules():
    global _api, _scheduler, _heartbeat, _telegram

    try:
        from daemon import api as _api_module
        _api = _api_module
        logger.debug("Modulo api caricato.")
    except ImportError:
        logger.warning("Modulo api.py non ancora implementato - Web UI non disponibile.")

    try:
        from daemon import scheduler as _sched_module
        _scheduler = _sched_module
        logger.debug("Modulo scheduler caricato.")
    except ImportError:
        logger.warning("Modulo scheduler.py non ancora implementato - Cron disabilitato.")

    try:
        from daemon import heartbeat as _hb_module
        _heartbeat = _hb_module
        logger.debug("Modulo heartbeat caricato.")
    except ImportError:
        logger.warning("Modulo heartbeat.py non ancora implementato - Heartbeat disabilitato.")

    try:
        from daemon import telegram_bridge as _tg_module
        _telegram = _tg_module
        logger.debug("Modulo telegram_bridge caricato.")
    except ImportError:
        logger.warning("Modulo telegram_bridge.py non ancora implementato - Telegram disabilitato.")

# --- Port utilities ----------------------------------------------------

def _find_free_port(start: int = 3333, max_attempts: int = 10) -> int:
    for port in range(start, start + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError(f"Nessuna porta libera trovata tra {start} e {start + max_attempts}")


def _update_env_port(port: int) -> None:
    """Persiste la porta nel file .env."""
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


# --- Comandi CLI -------------------------------------------------------

def cmd_start(args):
    logger.info("Avvio MyCow daemon...")

    if EMERGENCY_STOP_FILE.exists():
        logger.error(
            "File EMERGENCY_STOP presente nella root. Rimuovilo per avviare: %s",
            EMERGENCY_STOP_FILE,
        )
        sys.exit(1)

    _load_modules()

    # Port auto-detection
    requested_port = PORT
    port = _find_free_port(requested_port)
    if port != requested_port:
        logger.warning("Porta %d occupata, uso %d", requested_port, port)
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
            logger.error("Errore avvio CronScheduler: %s", e)

    if _heartbeat:
        try:
            hb_instance = _heartbeat.HeartbeatManager()
            hb_instance.start()
            started.append("HeartbeatManager")
        except Exception as e:
            logger.error("Errore avvio HeartbeatManager: %s", e)

    if _telegram:
        try:
            tg_instance = _telegram.TelegramBridge()
            tg_instance._scheduler = sched_instance
            tg_instance._heartbeat = hb_instance
            tg_instance.start()
            started.append("TelegramBridge")
        except Exception as e:
            logger.error("Errore avvio TelegramBridge: %s", e)

    if _api:
        logger.info("Web UI disponibile su http://127.0.0.1:%d", port)
        started.append("API")
        try:
            flask_app = _api.create_app(
                scheduler=sched_instance,
                heartbeat_mgr=hb_instance,
                telegram=tg_instance,
            )
            flask_app.run(host="127.0.0.1", port=port, use_reloader=False)
        except Exception as e:
            logger.error("Errore avvio API: %s", e)
    else:
        if started:
            logger.info("Componenti avviati: %s", ", ".join(started))
            logger.info("Daemon in esecuzione. Ctrl+C per fermare.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Interruzione manuale. Arresto daemon.")
        else:
            logger.warning(
                "Nessun modulo disponibile. "
                "Implementa i moduli in daemon/ e riavvia."
            )


def cmd_stop(args):
    logger.info("Creazione file EMERGENCY_STOP per fermare tutti gli agenti...")
    EMERGENCY_STOP_FILE.touch()
    logger.info("EMERGENCY_STOP creato. Il daemon non avviera' nuovi agenti.")
    logger.info("Per rimuovere il blocco: elimina il file %s", EMERGENCY_STOP_FILE)


def cmd_status(args):
    _load_modules()

    print("\n=== MyCow Status ===")
    print(f"Root:            {ROOT_DIR}")
    print(f"Porta:           {PORT}")
    print(f"Emergency stop:  {'SI - daemon bloccato' if EMERGENCY_STOP_FILE.exists() else 'no'}")
    print()

    agents_dir = ROOT_DIR / "agents"
    agents = [d for d in agents_dir.iterdir() if d.is_dir()] if agents_dir.exists() else []
    print(f"Agenti definiti: {len(agents)}")
    for agent in agents:
        print(f"  - {agent.name}")

    print()
    print("Moduli:")
    modules = {
        "api.py":             _api,
        "scheduler.py":       _scheduler,
        "heartbeat.py":       _heartbeat,
        "telegram_bridge.py": _telegram,
    }
    for name, mod in modules.items():
        status = "[ok] disponibile" if mod else "[--] non implementato"
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

    p_start = subparsers.add_parser("start", help="Avvia il daemon MyCow")
    p_start.set_defaults(func=cmd_start)

    p_stop = subparsers.add_parser("stop", help="Ferma tutti gli agenti (crea EMERGENCY_STOP)")
    p_stop.set_defaults(func=cmd_stop)

    p_status = subparsers.add_parser("status", help="Mostra stato del daemon e degli agenti")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
