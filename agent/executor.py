from __future__ import annotations
import asyncio
import json
import logging
import urllib.request
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
        if process.returncode != 0:
            if cfg.ollama_fallback:
                logger.warning("Claude exited with rc=%d, falling back to Ollama", process.returncode)
                result = await _run_ollama(instruction, cfg)
                return f"⚠️ _Claude non disponibile — risposta da {cfg.ollama_model}:_\n\n{result}"
            if errors:
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
    from agent import history, mode

    context = history.build_context(chat_id)
    full_instruction = f"{context}\n\nCurrent instruction: {instruction}" if context else instruction

    if mode.get(chat_id) == mode.OLLAMA:
        return await _run_ollama(full_instruction, cfg)
    return await run_raw(full_instruction, cwd=cfg.workspace_dir, cfg=cfg)


async def _run_ollama(instruction: str, cfg: Config) -> str:
    payload = json.dumps({
        "model": cfg.ollama_model,
        "messages": [{"role": "user", "content": instruction}],
        "stream": False,
    }).encode()

    def _call() -> str:
        req = urllib.request.Request(
            f"{cfg.ollama_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read())
            return data["message"]["content"]

    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, _call)
    except Exception as e:
        logger.error("Ollama request failed: %s", e)
        return f"❌ Errore Ollama: {e}"


def _build_env(cfg: Config) -> dict:
    import os
    env = os.environ.copy()
    env["CLAUDE_CODE_OAUTH_TOKEN"] = cfg.claude_oauth_token
    env.pop("ANTHROPIC_API_KEY", None)
    return env
