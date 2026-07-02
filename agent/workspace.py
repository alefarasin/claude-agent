from __future__ import annotations
import asyncio
import os
import logging
from config import Config

logger = logging.getLogger(__name__)


async def setup(cfg: Config) -> bool:
    if not os.path.exists(cfg.workspace_dir):
        os.makedirs(os.path.dirname(cfg.workspace_dir), exist_ok=True)
        repo_url = (
            f"https://{cfg.github_username}:{cfg.github_token}"
            f"@github.com/{cfg.github_username}/{cfg.repo_name}.git"
        )
        proc = await asyncio.create_subprocess_exec(
            "git", "clone", repo_url, cfg.workspace_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error("Errore clone repo: %s", stderr.decode("utf-8", errors="replace"))
            return False
        await _git(["git", "config", "user.email", "claude-agent@bot.local"], cfg.workspace_dir)
        await _git(["git", "config", "user.name", "Claude Agent"], cfg.workspace_dir)
    return True


async def pull(cfg: Config) -> None:
    await _git(["git", "pull"], cfg.workspace_dir)


async def _git(cmd: list[str], cwd: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=cwd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.communicate()
