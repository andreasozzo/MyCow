"""
MyCow Agent Runner
Wraps Claude Code CLI in a non-interactive subprocess.
Every execution is logged as JSON in agents/{name}/logs/.
"""

import json
import logging
import os
import subprocess
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("mycow.agent_runner")

ROOT_DIR = Path(__file__).parent.parent
AGENTS_DIR = ROOT_DIR / "agents"

# Permission level mapping → --allowedTools
PERMISSION_LEVELS = {
    0: "Read",
    1: "Read,Write",
    2: "Read,Write,Bash(git *),Bash(npm test),Bash(python *)",
    3: "Read,Write,Bash(*)",
}


def _resolve_allowed_tools(cron_config: dict) -> str:
    """
    Builds the --allowedTools string from permissions in cron.yaml.
    Uses PERMISSION_LEVELS as base, then adds skill-specific tools.
    """
    permissions = cron_config.get("permissions", {})

    bash_allowed = permissions.get("bash", False)
    internet_allowed = permissions.get("internet", False)

    if bash_allowed:
        level = 2
    else:
        level = 1

    tools = PERMISSION_LEVELS[level]

    # WebSearch/WebFetch only if internet is enabled
    if internet_allowed:
        tools += ",WebSearch,WebFetch"

    return tools


def _hash_prompt(prompt: str) -> str:
    return "sha256:" + hashlib.sha256(prompt.encode()).hexdigest()[:16]


def _save_log(agent_name: str, log_entry: dict) -> None:
    log_dir = AGENTS_DIR / agent_name / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = log_dir / f"{date_str}.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def get_logs(agent_name: str, limit: int = 100) -> list[dict]:
    """Reads the most recent logs for an agent."""
    log_dir = AGENTS_DIR / agent_name / "logs"
    if not log_dir.exists():
        return []

    log_files = sorted(log_dir.glob("*.jsonl"), reverse=True)
    entries = []
    for log_file in log_files:
        try:
            with open(log_file, encoding="utf-8") as f:
                lines = f.readlines()
            for line in reversed(lines):
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
                if len(entries) >= limit:
                    break
        except OSError:
            pass
        if len(entries) >= limit:
            break

    return entries[:limit]


def run_agent(
    agent_name: str,
    prompt: str,
    trigger: str = "manual",
    cron_config: dict | None = None,
    timeout: int = 300,
    model: str | None = None,
    resume_session: str | None = None,
) -> dict:
    """
    Runs an agent via Claude Code CLI.

    Args:
        agent_name:  Agent folder name in agents/
        prompt:      Prompt to pass to Claude Code
        trigger:     "cron" | "heartbeat" | "manual"
        cron_config: Content of the agent's cron.yaml (for permissions)
        timeout:     Subprocess timeout in seconds (default 300)

    Returns:
        dict with status, output, duration_seconds, error
    """
    agent_dir = AGENTS_DIR / agent_name
    if not agent_dir.exists():
        logger.error("Agent folder not found: %s", agent_dir)
        return {"status": "error", "error": f"Agent dir not found: {agent_dir}"}

    emergency_stop = ROOT_DIR / "EMERGENCY_STOP"
    if emergency_stop.exists():
        logger.warning("[%s] EMERGENCY_STOP active — execution blocked", agent_name)
        return {"status": "blocked", "error": "EMERGENCY_STOP active. Remove the file to re-enable."}

    cron_config = cron_config or {}
    allowed_tools = _resolve_allowed_tools(cron_config)

    cmd = [
        "claude",
        "-p", prompt,
        "--allowedTools", allowed_tools,
        "--output-format", "json",
        "--max-turns", "10",
        "--permission-mode", "acceptEdits",
    ]
    if model:
        cmd += ["--model", model]
    if resume_session:
        cmd += ["--continue"]
    cmd += [
        "--append-system-prompt",
        "To create or modify files ALWAYS use the Write tool, never Bash. "
        "To read files use Read, never Bash. "
        "Use Bash only for operations you cannot do with Read/Write. "
        "DO NOT look for tokens, credentials, or .env files — they are not in your environment and you cannot access them. "
        "DO NOT attempt to send Telegram messages directly: the daemon sends them for you automatically. "
        "To communicate something via Telegram simply write the text as output — the daemon delivers it.",
    ]

    logger.info("[%s] Starting — trigger=%s tools=%s", agent_name, trigger, allowed_tools)
    start_time = time.monotonic()
    timestamp = datetime.now(timezone.utc).isoformat()

    result = {
        "timestamp": timestamp,
        "agent": agent_name,
        "trigger": trigger,
        "prompt_hash": _hash_prompt(prompt),
        "prompt": prompt if trigger == "chat" else None,
        "allowed_tools": allowed_tools,
        "duration_seconds": 0,
        "status": "unknown",
        "output": None,
        "telegram_sent": False,
        "error": None,
    }

    # Remove secrets from subprocess environment — the agent must not have them
    clean_env = {k: v for k, v in os.environ.items()
                 if k not in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")}

    def _run_cmd(c):
        return subprocess.run(
            c,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=str(agent_dir),
            env=clean_env,
        )

    try:
        proc = _run_cmd(cmd)

        duration = round(time.monotonic() - start_time, 2)
        result["duration_seconds"] = duration

        if proc.returncode != 0:
            stderr = proc.stderr.strip()
            stdout = proc.stdout.strip()[:500]
            error_msg = stderr or stdout or f"Exit code {proc.returncode}"
            logger.error("[%s] Claude Code error (rc=%d) stderr=%r stdout=%r",
                         agent_name, proc.returncode, stderr[:200] if stderr else "", stdout[:200] if stdout else "")
            result["status"] = "error"
            result["error"] = error_msg
            _save_log(agent_name, result)
            _notify_telegram(agent_name, f"Execution error: {error_msg}", cron_config)
            return result

        # Parse Claude Code JSON output
        output_text, session_id, parsed_ok = _parse_claude_output(proc.stdout, agent_name)

        # Retry CLI if output is malformed and stdout was not empty
        if not parsed_ok and proc.stdout.strip():
            logger.warning("[%s] Malformed output, retrying CLI...", agent_name)
            try:
                proc = _run_cmd(cmd)
                output_text, session_id, parsed_ok = _parse_claude_output(proc.stdout, agent_name)
            except Exception as retry_err:
                logger.warning("[%s] Retry failed: %s", agent_name, retry_err)

        result["status"] = "success"
        result["output"] = output_text
        if session_id:
            result["session_id"] = session_id
        logger.info("[%s] Completato in %.1fs", agent_name, duration)

        # Auto-notify Telegram only for cron/heartbeat — chat and manual handle their own responses
        if (cron_config.get("permissions", {}).get("telegram_without_approval")
                and output_text
                and trigger not in ("chat", "manual")):
            _notify_telegram(agent_name, output_text, cron_config)
            result["telegram_sent"] = True

    except subprocess.TimeoutExpired:
        duration = round(time.monotonic() - start_time, 2)
        result["duration_seconds"] = duration
        result["status"] = "timeout"
        result["error"] = f"Timeout after {timeout}s"
        logger.warning("[%s] Timeout after %ds", agent_name, timeout)
        _notify_telegram(agent_name, f"Timeout after {timeout}s", cron_config)

    except FileNotFoundError:
        result["status"] = "error"
        result["error"] = "Claude Code CLI not found. Install: npm install -g @anthropic-ai/claude-code"
        logger.error("[%s] claude CLI not found in PATH", agent_name)

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        logger.exception("[%s] Unexpected error: %s", agent_name, e)

    _save_log(agent_name, result)
    return result


def _parse_claude_output(raw_stdout: str, agent_name: str) -> tuple[str | None, str | None, bool]:
    """
    Parses the JSON output from Claude Code (--output-format json).
    Returns (response_text, session_id, parsed_ok).
    parsed_ok=False means the output was not valid JSON (fallback to raw text).
    """
    if not raw_stdout.strip():
        return None, None, False

    # Claude Code with --output-format json emits a list of messages.
    # The last one with role="assistant" contains the final response.
    # Alternatively it emits a single dict {type:"result", subtype:"success", result:"..."}
    for attempt in range(2):
        try:
            data = json.loads(raw_stdout)
            if isinstance(data, list):
                session_id = None
                text = None
                for msg in reversed(data):
                    if not isinstance(msg, dict):
                        continue
                    if not session_id:
                        session_id = msg.get("session_id")
                    if not text and msg.get("role") == "assistant":
                        content = msg.get("content", "")
                        if isinstance(content, list):
                            text = " ".join(
                                block.get("text", "")
                                for block in content
                                if isinstance(block, dict) and block.get("type") == "text"
                            )
                        else:
                            text = str(content)
                return text, session_id, True
            elif isinstance(data, dict):
                session_id = data.get("session_id")
                if data.get("type") == "result":
                    subtype = data.get("subtype", "")
                    if subtype not in ("success",):
                        logger.warning("[%s] Claude Code terminato con subtype=%s", agent_name, subtype)
                        return None, session_id, True
                    result_text = data.get("result")
                    return (str(result_text) if result_text else None), session_id, True
                return data.get("result") or data.get("content") or None, session_id, True
        except json.JSONDecodeError:
            if attempt == 0:
                for line in reversed(raw_stdout.strip().splitlines()):
                    try:
                        data = json.loads(line)
                        raw_stdout = line
                        break
                    except json.JSONDecodeError:
                        continue
            else:
                logger.warning("[%s] Claude Code output not parseable — returning raw text", agent_name)
                return raw_stdout[:2000], None, False

    return raw_stdout[:2000], None, False


def _notify_telegram(agent_name: str, message: str, cron_config: dict) -> None:
    """Sends a Telegram notification via the daemon (the agent does not have the token)."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = cron_config.get("telegram_chat_id") or os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        import asyncio
        import telegram
        async def _send():
            bot = telegram.Bot(token=token)
            await bot.send_message(
                chat_id=chat_id,
                text=f"[{agent_name}]\n{message}"[:4096],
                parse_mode="Markdown",
            )
        asyncio.run(_send())
    except Exception as e:
        logger.debug("Telegram notification failed: %s", e)
