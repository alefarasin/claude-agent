from __future__ import annotations
import asyncio
import logging
from pathlib import Path
from config import Config

logger = logging.getLogger(__name__)


def _context_path(cfg: Config) -> Path:
    return Path(cfg.workspace_dir).parent / "context.md"


def read_context(cfg: Config) -> str:
    p = _context_path(cfg)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def reset_context(cfg: Config) -> None:
    p = _context_path(cfg)
    if p.exists():
        p.unlink()
    logger.info("Context reset")


async def compact_context(cfg: Config) -> None:
    context = read_context(cfg)
    if not context:
        return
    summary = await run_raw(
        "Summarise this conversation concisely, preserving key decisions, "
        "code changes, and important technical context. Be brief but complete.\n\n"
        + context,
        cwd=str(Path(cfg.workspace_dir).parent),
        cfg=cfg,
    )
    _context_path(cfg).write_text(
        f"## Conversation summary (compacted)\n\n{summary}\n", encoding="utf-8"
    )
    logger.info("Context compacted")


async def run(instruction: str, cfg: Config) -> str:
    context = read_context(cfg)
    full_instruction = (
        f"Conversation history:\n{context}\n\nCurrent instruction: {instruction}"
        if context else instruction
    )
    result = await run_raw(full_instruction, cwd=cfg.workspace_dir, cfg=cfg)
    p = _context_path(cfg)
    with p.open("a", encoding="utf-8") as f:
        f.write(f"\n### User\n{instruction}\n\n### Claude\n{result}\n")
    return result


async def run_raw(instruction: str, cwd: str, cfg: Config) -> str:
    env = _build_env(cfg)
    process = None
    logger.info(">>> CLAUDE INPUT\n%s", instruction)
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
            result = f"⚠️ Output:\n{output}\n\nErrori:\n{errors}"
        else:
            result = output if output else "✅ Completato senza output."
        logger.info("<<< CLAUDE OUTPUT (rc=%d)\n%s", process.returncode, result)
        return result
    except asyncio.CancelledError:
        if process:
            process.kill()
            await process.wait()
        raise
    except Exception as e:
        logger.error("<<< CLAUDE ERROR: %s", e)
        return f"❌ Errore: {str(e)}"


def _build_env(cfg: Config) -> dict:
    import os
    env = os.environ.copy()
    env["CLAUDE_CODE_OAUTH_TOKEN"] = cfg.claude_oauth_token
    env.pop("ANTHROPIC_API_KEY", None)
    return env
