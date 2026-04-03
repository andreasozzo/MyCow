"""
MyCow Skill Manager
Installa, disinstalla e gestisce le skill degli agenti.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
from pathlib import Path

import yaml

logger = logging.getLogger("mycow.skill_manager")

ROOT_DIR = Path(__file__).parent.parent
SKILLS_GLOBAL = ROOT_DIR / "skills" / "global"
SKILLS_REGISTRY = ROOT_DIR / "skills" / "registry"
AGENTS_DIR = ROOT_DIR / "agents"


class SkillManager:

    def install(self, name: str) -> dict:
        """
        Copia la skill da skills/registry/{name} a skills/global/{name}.
        Ritorna {ok, missing_env} dove missing_env è lista di var non configurate.
        """
        src = SKILLS_REGISTRY / name
        dst = SKILLS_GLOBAL / name

        if not src.exists():
            raise FileNotFoundError(f"Skill '{name}' non trovata nel registry")
        if dst.exists():
            raise FileExistsError(f"Skill '{name}' gia' installata")

        shutil.copytree(str(src), str(dst))
        logger.info("Skill '%s' installata.", name)

        missing_env = self._check_env(name)
        return {"ok": True, "name": name, "missing_env": missing_env}

    def uninstall(self, name: str) -> None:
        """Rimuove la skill da skills/global e la de-referenzia da tutti gli agenti."""
        dst = SKILLS_GLOBAL / name
        if not dst.exists():
            raise FileNotFoundError(f"Skill '{name}' non installata")

        shutil.rmtree(str(dst))
        logger.info("Skill '%s' disinstallata.", name)

        # Rimuovi riferimento da tutti gli agenti
        if AGENTS_DIR.exists():
            for agent_dir in AGENTS_DIR.iterdir():
                if agent_dir.is_dir():
                    try:
                        self.remove_from_agent(name, agent_dir.name)
                    except Exception:
                        pass

    def list(self) -> dict:
        """
        Ritorna {installed: [...], available: [...]}.
        available = skill nel registry non ancora installate.
        """
        installed = self._scan_dir(SKILLS_GLOBAL)
        available = [
            s for s in self._scan_dir(SKILLS_REGISTRY)
            if s["name"] not in {i["name"] for i in installed}
        ]
        # Arricchisce installed con env_configured
        for skill in installed:
            skill["env_configured"] = len(self._check_env(skill["name"])) == 0
        return {"installed": installed, "available": available}

    def add_to_agent(self, skill_name: str, agent_name: str) -> None:
        """Aggiunge riferimento skill nel CLAUDE.md dell'agente."""
        if not (SKILLS_GLOBAL / skill_name).exists():
            raise FileNotFoundError(f"Skill '{skill_name}' non installata")

        claude_md = AGENTS_DIR / agent_name / "CLAUDE.md"
        if not claude_md.exists():
            raise FileNotFoundError(f"Agente '{agent_name}' non trovato")

        content = claude_md.read_text(encoding="utf-8")
        ref = f"- ../../../skills/global/{skill_name}/skill.md"

        if ref in content:
            return  # gia' presente

        if "## Skills Attive" not in content:
            content = content.rstrip() + "\n\n## Skills Attive\n"
        content = content.rstrip() + f"\n{ref}\n"
        claude_md.write_text(content, encoding="utf-8")
        logger.info("Skill '%s' aggiunta a '%s'.", skill_name, agent_name)

    def remove_from_agent(self, skill_name: str, agent_name: str) -> None:
        """Rimuove riferimento skill dal CLAUDE.md dell'agente."""
        claude_md = AGENTS_DIR / agent_name / "CLAUDE.md"
        if not claude_md.exists():
            return
        content = claude_md.read_text(encoding="utf-8")
        ref = f"- ../../../skills/global/{skill_name}/skill.md"
        new_content = content.replace(ref + "\n", "").replace(ref, "")
        if new_content != content:
            claude_md.write_text(new_content, encoding="utf-8")
            logger.info("Skill '%s' rimossa da '%s'.", skill_name, agent_name)

    # ------------------------------------------------------------------
    # Privati
    # ------------------------------------------------------------------

    def _scan_dir(self, base: Path) -> list[dict]:
        if not base.exists():
            return []
        skills = []
        for d in base.iterdir():
            if not d.is_dir():
                continue
            manifest = {}
            mf = d / "manifest.yaml"
            if mf.exists():
                try:
                    manifest = yaml.safe_load(mf.read_text(encoding="utf-8")) or {}
                except Exception:
                    pass
            skills.append({
                "name": d.name,
                "version": manifest.get("version", ""),
                "description": manifest.get("description", ""),
                "requires_env": manifest.get("requires_env", []),
                "mcp_server": manifest.get("mcp_server"),
            })
        return skills

    def _check_env(self, skill_name: str) -> list[str]:
        """Ritorna lista di env vars richieste dalla skill ma non configurate."""
        mf = SKILLS_GLOBAL / skill_name / "manifest.yaml"
        if not mf.exists():
            mf = SKILLS_REGISTRY / skill_name / "manifest.yaml"
        if not mf.exists():
            return []
        try:
            manifest = yaml.safe_load(mf.read_text(encoding="utf-8")) or {}
        except Exception:
            return []
        return [v for v in manifest.get("requires_env", []) if not os.environ.get(v)]
