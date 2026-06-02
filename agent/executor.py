from __future__ import annotations
import asyncio
import logging
from config import Config

logger = logging.getLogger(__name__)


async def run_raw(instruction: str, cwd: str, cfg: Config) -> str:
    env = _build_env(cfg)
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            "claude", "--print", "--dangerously-skip-permissions", instruction,
            cwd=cwd, env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        output = stdout.decode("utf-8", errors="replace")
        errors = stderr.decode("utf-8", errors="replace")
        if process.returncode != 0 and errors:
            return f"⚠️ Output:\n{output}\n\nErrori:\n{errors}"
        return output if output else "✅ Completato senza output."
    except asyncio.CancelledError:
        if process:
            process.kill()
            await process.wait()
        raise
    except Exception as e:
        return f"❌ Errore: {str(e)}"


async def run(instruction: str, chat_id: int, cfg: Config) -> str:
    from agent import history

    context = history.build_context(chat_id)
    full_instruction = f"{context}\n\nCurrent instruction: {instruction}" if context else instruction
    return await run_raw(full_instruction, cwd=cfg.workspace_dir, cfg=cfg)


def _build_env(cfg: Config) -> dict:
    import os
    env = os.environ.copy()
    env["CLAUDE_CODE_OAUTH_TOKEN"] = cfg.claude_oauth_token
    env.pop("ANTHROPIC_API_KEY", None)
    return env
