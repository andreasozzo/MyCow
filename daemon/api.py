"""
MyCow API REST locale
Flask su 127.0.0.1:3333 — backend per la Web UI.
MAI bindare su 0.0.0.0.
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml
from flask import Flask, jsonify, request, send_from_directory

logger = logging.getLogger("mycow.api")

ROOT_DIR = Path(__file__).parent.parent
AGENTS_DIR = ROOT_DIR / "agents"
SKILLS_GLOBAL = ROOT_DIR / "skills" / "global"
SKILLS_REGISTRY = ROOT_DIR / "skills" / "registry"
EMERGENCY_STOP_FILE = ROOT_DIR / "EMERGENCY_STOP"
WEB_DIR = ROOT_DIR / "web"
ENV_FILE = ROOT_DIR / ".env"

_start_time = time.monotonic()


# Campi .env che possono essere letti via API (no secrets)
READABLE_SETTINGS = {"MYCOW_PORT", "MYCOW_LOG_LEVEL"}
# Campi .env che possono essere scritti via API — include secrets (write-only, mai letti)
WRITABLE_SETTINGS = {"MYCOW_PORT", "MYCOW_LOG_LEVEL",
                     "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "BRAVE_API_KEY"}
# Secrets: scrivibili ma non restituiti da GET /api/settings
SECRET_SETTINGS = {"TELEGRAM_BOT_TOKEN", "BRAVE_API_KEY"}


def _err(message: str, code: int = 400):
    return jsonify({"error": True, "message": message, "code": code}), code


def _ok(data: dict | list, code: int = 200):
    return jsonify(data), code


def _agent_state(name: str, scheduler=None, heartbeat_mgr=None) -> dict:
    """Costruisce il dict di stato di un agente."""
    agent_dir = AGENTS_DIR / name
    yaml_path = agent_dir / "cron.yaml"
    config = {}
    if yaml_path.exists():
        try:
            config = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        except Exception:
            pass

    # Crons dal scheduler
    crons = []
    if scheduler:
        crons = [j for j in scheduler.list_jobs() if j.get("agent") == name]

    # Heartbeat
    hb_status = None
    if heartbeat_mgr:
        for h in heartbeat_mgr.get_status():
            if h["name"] == name:
                hb_status = h
                break

    # Ultimi log
    from daemon.agent_runner import get_logs
    logs = get_logs(name, limit=1)
    last_run = logs[0] if logs else None

    # Skill attive
    skills = _agent_skills(name)

    return {
        "name": name,
        "enabled": config.get("enabled", True),
        "crons": crons,
        "heartbeat": hb_status,
        "last_run": last_run,
        "skills": skills,
        "permissions": config.get("permissions", {}),
    }


def _agent_skills(name: str) -> list[str]:
    claude_md = AGENTS_DIR / name / "CLAUDE.md"
    if not claude_md.exists():
        return []
    content = claude_md.read_text(encoding="utf-8")
    match = re.search(r"## Skills Attive\b(.*?)(?=\n##|\Z)", content, re.DOTALL | re.IGNORECASE)
    if not match:
        return []
    lines = match.group(1).strip().splitlines()
    skills = []
    for line in lines:
        line = line.strip().lstrip("-").strip()
        if line:
            skills.append(Path(line).stem if "/" in line else line)
    return skills


def create_app(scheduler=None, heartbeat_mgr=None, telegram=None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["JSON_SORT_KEYS"] = False

    # ------------------------------------------------------------------
    # Serve Web UI
    # ------------------------------------------------------------------

    @app.route("/")
    def index():
        if WEB_DIR.exists() and (WEB_DIR / "index.html").exists():
            return send_from_directory(str(WEB_DIR), "index.html")
        return _ok({"message": "MyCow API running. Web UI not yet built."})

    @app.route("/<path:filename>")
    def static_files(filename):
        if WEB_DIR.exists():
            return send_from_directory(str(WEB_DIR), filename)
        return _err("File not found", 404)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @app.route("/health")
    def health():
        import shutil
        claude_ok = shutil.which("claude") is not None
        tg_connected = telegram is not None and bool(os.environ.get("TELEGRAM_BOT_TOKEN"))
        agents = [d.name for d in AGENTS_DIR.iterdir() if d.is_dir()] if AGENTS_DIR.exists() else []
        sched_backend = getattr(scheduler, "scheduler", None)
        scheduler_running = bool(scheduler and sched_backend and getattr(sched_backend, "running", False))
        heartbeat_running = bool(heartbeat_mgr and getattr(heartbeat_mgr, "_running", False))
        return _ok({
            "status": "ok",
            "uptime_seconds": round(time.monotonic() - _start_time),
            "claude_available": claude_ok,
            "telegram_connected": tg_connected,
            "scheduler_running": scheduler_running,
            "heartbeat_running": heartbeat_running,
            "agents_count": len(agents),
            "emergency_stop": EMERGENCY_STOP_FILE.exists(),
        })

    # ------------------------------------------------------------------
    # Agents
    # ------------------------------------------------------------------

    @app.route("/api/agents")
    def agents_list():
        if not AGENTS_DIR.exists():
            return _ok([])
        agents = []
        for d in AGENTS_DIR.iterdir():
            if d.is_dir():
                agents.append(_agent_state(d.name, scheduler, heartbeat_mgr))
        return _ok(agents)

    @app.route("/api/agents/<name>")
    def agent_detail(name):
        if not (AGENTS_DIR / name).exists():
            return _err(f"Agente '{name}' non trovato", 404)
        return _ok(_agent_state(name, scheduler, heartbeat_mgr))

    @app.route("/api/agents/<name>/run", methods=["POST"])
    def agent_run(name):
        agent_dir = AGENTS_DIR / name
        if not agent_dir.exists():
            return _err(f"Agente '{name}' non trovato", 404)
        yaml_path = agent_dir / "cron.yaml"
        config = yaml.safe_load(yaml_path.read_text()) if yaml_path.exists() else {}

        # Prompt custom dal body (chat) o primo cron (run manuale)
        body = request.get_json(silent=True) or {}
        custom_prompt = (body.get("prompt") or "").strip()

        if custom_prompt:
            prompt = custom_prompt
            model = config.get("model")
            trigger = "chat"
        else:
            crons = config.get("crons", [])
            if not crons:
                return _err("Nessun cron configurato per questo agente")
            entry = crons[0]
            prompt = entry.get("prompt", "").strip()
            if not prompt:
                return _err("Nessun prompt nel primo cron")
            model = entry.get("model") or config.get("model")
            trigger = "manual"

        import threading
        from daemon.agent_runner import run_agent
        def _run():
            run_agent(name, prompt, trigger=trigger, cron_config=config, model=model,
                      resume_session=(trigger == "chat"))
        threading.Thread(target=_run, daemon=True).start()
        return _ok({"message": f"Agente '{name}' avviato in background"})

    @app.route("/api/agents/<name>/pause", methods=["POST"])
    def agent_pause(name):
        if scheduler:
            scheduler.pause_agent(name)
        if heartbeat_mgr:
            heartbeat_mgr.pause_agent(name)
        return _ok({"message": f"'{name}' in pausa"})

    @app.route("/api/agents/<name>/resume", methods=["POST"])
    def agent_resume(name):
        if scheduler:
            scheduler.resume_agent(name)
        if heartbeat_mgr:
            heartbeat_mgr.resume_agent(name)
        return _ok({"message": f"'{name}' ripreso"})

    @app.route("/api/agents/create", methods=["POST"])
    def agent_create():
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip().lower()
        if not name or not re.match(r"^[a-z0-9][a-z0-9\-]{0,48}$", name):
            return _err("Nome agente non valido (solo lowercase, numeri, trattini)")
        agent_dir = AGENTS_DIR / name
        if agent_dir.exists():
            return _err(f"Agente '{name}' esiste gia'")

        crons = data.get("crons", [])
        heartbeat = data.get("heartbeat", 0)
        heartbeat_model = data.get("heartbeat_model", "")
        permissions = data.get("permissions", {
            "bash": False, "internet": False,
            "write_outside_dir": False, "telegram_without_approval": False,
        })

        # Crea struttura cartelle
        (agent_dir / "memory").mkdir(parents=True)
        (agent_dir / ".claude").mkdir()

        # cron.yaml
        telegram_chat_id = (data.get("telegram_chat_id") or "").strip()
        cron_config = {
            "name": name,
            "enabled": True,
            "heartbeat": heartbeat,
            "permissions": permissions,
            "crons": crons,
        }
        if telegram_chat_id:
            cron_config["telegram_chat_id"] = telegram_chat_id
        if heartbeat_model:
            cron_config["heartbeat_model"] = heartbeat_model
        (agent_dir / "cron.yaml").write_text(
            yaml.dump(cron_config, allow_unicode=True, default_flow_style=False),
            encoding="utf-8"
        )

        # CLAUDE.md
        claude_lines = [f"# {name}\n"]
        for entry in crons:
            cid = entry.get("id", "default")
            prompt = entry.get("prompt", "")
            claude_lines.append(f"## Task ({cid})\n{prompt}\n")
        if heartbeat:
            hb_prompt = data.get("heartbeat_prompt", "")
            claude_lines.append(f"## Heartbeat Behavior\n{hb_prompt}\n")
        if data.get("skills"):
            claude_lines.append("## Skills Attive")
            for s in data["skills"]:
                claude_lines.append(f"- ../../../skills/global/{s}/skill.md")
        (agent_dir / "CLAUDE.md").write_text("\n".join(claude_lines), encoding="utf-8")

        # memory files
        (agent_dir / "memory" / "core.md").write_text(f"# {name} — Core Memory\n", encoding="utf-8")
        (agent_dir / "memory" / "working.md").write_text("", encoding="utf-8")
        (agent_dir / "memory" / "decisions.md").write_text("", encoding="utf-8")

        # .claude/settings.json
        (agent_dir / ".claude" / "settings.json").write_text(
            json.dumps({"permissions": {"allow": [
                f"Write(agents/{name}/**)",
                f"Read(agents/{name}/**)",
            ]}}, indent=2),
            encoding="utf-8"
        )

        # Registra subito nel scheduler se attivo
        if scheduler:
            scheduler._register_agent(name)

        return _ok({"message": f"Agente '{name}' creato", "name": name}, 201)

    @app.route("/api/agents/<name>/logs")
    def agent_logs(name):
        if not (AGENTS_DIR / name).exists():
            return _err(f"Agente '{name}' non trovato", 404)
        limit = min(int(request.args.get("limit", 100)), 500)
        from daemon.agent_runner import get_logs
        return _ok(get_logs(name, limit=limit))

    @app.route("/api/agents/<name>/schedule")
    def agent_schedule(name):
        if not (AGENTS_DIR / name).exists():
            return _err(f"Agente '{name}' non trovato", 404)
        if not scheduler:
            return _ok({"crons": []})
        jobs = [j for j in scheduler.list_jobs() if j.get("agent") == name]
        return _ok({"crons": jobs})

    @app.route("/api/agents/<name>/heartbeat")
    def agent_heartbeat(name):
        if not (AGENTS_DIR / name).exists():
            return _err(f"Agente '{name}' non trovato", 404)
        if not heartbeat_mgr:
            return _ok({"status": "not_running"})
        for h in heartbeat_mgr.get_status():
            if h["name"] == name:
                return _ok(h)
        return _ok({"name": name, "status": "no_heartbeat_configured"})

    # ------------------------------------------------------------------
    # Skills
    # ------------------------------------------------------------------

    @app.route("/api/skills")
    def skills_list():
        installed = []
        if SKILLS_GLOBAL.exists():
            for d in SKILLS_GLOBAL.iterdir():
                if d.is_dir():
                    manifest = {}
                    mf = d / "manifest.yaml"
                    if mf.exists():
                        manifest = yaml.safe_load(mf.read_text()) or {}
                    installed.append({
                        "name": d.name,
                        "version": manifest.get("version", ""),
                        "description": manifest.get("description", ""),
                        "requires_env": manifest.get("requires_env", []),
                    })
        available = []
        if SKILLS_REGISTRY.exists():
            for d in SKILLS_REGISTRY.iterdir():
                if d.is_dir() and not any(s["name"] == d.name for s in installed):
                    manifest = {}
                    mf = d / "manifest.yaml"
                    if mf.exists():
                        manifest = yaml.safe_load(mf.read_text()) or {}
                    available.append({
                        "name": d.name,
                        "version": manifest.get("version", ""),
                        "description": manifest.get("description", ""),
                        "requires_env": manifest.get("requires_env", []),
                    })
        return _ok({"installed": installed, "available": available})

    @app.route("/api/skills/install", methods=["POST"])
    def skill_install():
        data = request.get_json(silent=True) or {}
        name = data.get("name", "").strip()
        if not name:
            return _err("Campo 'name' obbligatorio")
        src = SKILLS_REGISTRY / name
        dst = SKILLS_GLOBAL / name
        if not src.exists():
            return _err(f"Skill '{name}' non trovata nel registry", 404)
        if dst.exists():
            return _err(f"Skill '{name}' gia' installata")
        import shutil
        shutil.copytree(str(src), str(dst))
        return _ok({"message": f"Skill '{name}' installata"}, 201)

    @app.route("/api/skills/<name>", methods=["DELETE"])
    def skill_uninstall(name):
        dst = SKILLS_GLOBAL / name
        if not dst.exists():
            return _err(f"Skill '{name}' non trovata", 404)
        import shutil
        shutil.rmtree(str(dst))
        return _ok({"message": f"Skill '{name}' disinstallata"})

    @app.route("/api/agents/<agent>/skills/<skill>", methods=["POST"])
    def agent_skill_add(agent, skill):
        claude_md = AGENTS_DIR / agent / "CLAUDE.md"
        if not claude_md.exists():
            return _err(f"Agente '{agent}' non trovato", 404)
        content = claude_md.read_text(encoding="utf-8")
        skill_ref = f"- ../../../skills/global/{skill}/skill.md"
        if skill_ref in content:
            return _ok({"message": "Skill gia' attiva"})
        if "## Skills Attive" not in content:
            content += "\n## Skills Attive\n"
        content = content.rstrip() + f"\n{skill_ref}\n"
        claude_md.write_text(content, encoding="utf-8")
        return _ok({"message": f"Skill '{skill}' aggiunta a '{agent}'"})

    @app.route("/api/agents/<agent>/skills/<skill>", methods=["DELETE"])
    def agent_skill_remove(agent, skill):
        claude_md = AGENTS_DIR / agent / "CLAUDE.md"
        if not claude_md.exists():
            return _err(f"Agente '{agent}' non trovato", 404)
        content = claude_md.read_text(encoding="utf-8")
        skill_ref = f"- ../../../skills/global/{skill}/skill.md"
        content = content.replace(skill_ref + "\n", "").replace(skill_ref, "")
        claude_md.write_text(content, encoding="utf-8")
        return _ok({"message": f"Skill '{skill}' rimossa da '{agent}'"})

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    @app.route("/api/settings")
    def settings_get():
        result = {}
        for key in READABLE_SETTINGS:
            result[key] = os.environ.get(key, "")
        # Per i secrets: solo booleano "configurato"
        for key in SECRET_SETTINGS:
            result[f"{key}__set"] = bool(os.environ.get(key, "").strip())
        # TELEGRAM_CHAT_ID è readable (non è un secret)
        result["TELEGRAM_CHAT_ID"] = os.environ.get("TELEGRAM_CHAT_ID", "")
        result["TELEGRAM_CHAT_ID__set"] = bool(os.environ.get("TELEGRAM_CHAT_ID", "").strip())
        return _ok(result)

    @app.route("/api/settings", methods=["PATCH"])
    def settings_patch():
        data = request.get_json(silent=True) or {}
        forbidden = [k for k in data if k not in WRITABLE_SETTINGS]
        if forbidden:
            return _err(f"Campi non modificabili via API: {forbidden}")
        # Leggi .env attuale
        env_lines = []
        if ENV_FILE.exists():
            env_lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
        for key, value in data.items():
            found = False
            for i, line in enumerate(env_lines):
                if line.startswith(f"{key}="):
                    env_lines[i] = f"{key}={value}"
                    found = True
                    break
            if not found:
                env_lines.append(f"{key}={value}")
        ENV_FILE.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
        # Aggiorna env in memoria
        for key, value in data.items():
            os.environ[key] = str(value)
        return _ok({"message": "Impostazioni aggiornate"})

    # ------------------------------------------------------------------
    # Stop All
    # ------------------------------------------------------------------

    @app.errorhandler(Exception)
    def handle_exception(e):
        logger.exception("Unhandled API exception")
        return jsonify({"error": True, "message": "Internal server error", "code": 500}), 500

    @app.route("/api/stop-all", methods=["POST"])
    def stop_all():
        EMERGENCY_STOP_FILE.touch()
        if scheduler:
            try:
                scheduler.stop()
            except Exception:
                pass
        if heartbeat_mgr:
            try:
                heartbeat_mgr.stop()
            except Exception:
                pass
        return _ok({"message": "EMERGENCY_STOP attivato. Tutti gli agenti fermati."})

    return app
