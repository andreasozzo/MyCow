"""
MyCow Skill Manager
Installs, uninstalls, and manages agent skills.
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
        Copies the skill from skills/registry/{name} to skills/global/{name}.
        Returns {ok, missing_env} where missing_env is a list of unconfigured vars.
        """
        src = SKILLS_REGISTRY / name
        dst = SKILLS_GLOBAL / name

        if not src.exists():
            raise FileNotFoundError(f"Skill '{name}' not found in registry")
        if dst.exists():
            raise FileExistsError(f"Skill '{name}' already installed")

        shutil.copytree(str(src), str(dst))
        logger.info("Skill '%s' installed.", name)

        missing_env = self._check_env(name)
        return {"ok": True, "name": name, "missing_env": missing_env}

    def uninstall(self, name: str) -> None:
        """Removes the skill from skills/global and de-references it from all agents."""
        dst = SKILLS_GLOBAL / name
        if not dst.exists():
            raise FileNotFoundError(f"Skill '{name}' not installed")

        shutil.rmtree(str(dst))
        logger.info("Skill '%s' uninstalled.", name)

        # Remove references from all agents
        if AGENTS_DIR.exists():
            for agent_dir in AGENTS_DIR.iterdir():
                if agent_dir.is_dir():
                    try:
                        self.remove_from_agent(name, agent_dir.name)
                    except Exception:
                        pass

    def list(self) -> dict:
        """
        Returns {installed: [...], available: [...]}.
        available = skills in registry not yet installed.
        """
        installed = self._scan_dir(SKILLS_GLOBAL)
        available = [
            s for s in self._scan_dir(SKILLS_REGISTRY)
            if s["name"] not in {i["name"] for i in installed}
        ]
        # Enrich installed with env_configured
        for skill in installed:
            skill["env_configured"] = len(self._check_env(skill["name"])) == 0
        return {"installed": installed, "available": available}

    def add_to_agent(self, skill_name: str, agent_name: str) -> None:
        """Adds skill reference to the agent's CLAUDE.md."""
        if not (SKILLS_GLOBAL / skill_name).exists():
            raise FileNotFoundError(f"Skill '{skill_name}' not installed")

        claude_md = AGENTS_DIR / agent_name / "CLAUDE.md"
        if not claude_md.exists():
            raise FileNotFoundError(f"Agent '{agent_name}' not found")

        content = claude_md.read_text(encoding="utf-8")
        ref = f"- ../../../skills/global/{skill_name}/skill.md"

        if ref in content:
            return  # already present

        if "## Active Skills" not in content:
            content = content.rstrip() + "\n\n## Active Skills\n"
        content = content.rstrip() + f"\n{ref}\n"
        claude_md.write_text(content, encoding="utf-8")
        logger.info("Skill '%s' added to '%s'.", skill_name, agent_name)

    def remove_from_agent(self, skill_name: str, agent_name: str) -> None:
        """Removes skill reference from the agent's CLAUDE.md."""
        claude_md = AGENTS_DIR / agent_name / "CLAUDE.md"
        if not claude_md.exists():
            return
        content = claude_md.read_text(encoding="utf-8")
        ref = f"- ../../../skills/global/{skill_name}/skill.md"
        new_content = content.replace(ref + "\n", "").replace(ref, "")
        if new_content != content:
            claude_md.write_text(new_content, encoding="utf-8")
            logger.info("Skill '%s' removed from '%s'.", skill_name, agent_name)

    # ------------------------------------------------------------------
    # Private
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
        """Returns list of env vars required by the skill but not configured."""
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
