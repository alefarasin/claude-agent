from __future__ import annotations
import os
import subprocess
import logging
from config import Config

logger = logging.getLogger(__name__)


def setup(cfg: Config) -> bool:
    if not os.path.exists(cfg.workspace_dir):
        os.makedirs(os.path.dirname(cfg.workspace_dir), exist_ok=True)
        repo_url = f"https://{cfg.github_username}:{cfg.github_token}@github.com/{cfg.github_username}/{cfg.repo_name}.git"
        result = subprocess.run(
            ["git", "clone", repo_url, cfg.workspace_dir],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            logger.error(f"Errore clone repo: {result.stderr}")
            return False
        subprocess.run(["git", "config", "user.email", "claude-agent@bot.local"], cwd=cfg.workspace_dir)
        subprocess.run(["git", "config", "user.name", "Claude Agent"], cwd=cfg.workspace_dir)
    return True


def pull(cfg: Config) -> None:
    subprocess.run(["git", "pull"], cwd=cfg.workspace_dir, capture_output=True)
