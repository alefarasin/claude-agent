import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    allowed_chat_id: int
    claude_oauth_token: str
    github_token: str
    github_username: str
    repo_name: str
    workspace_dir: str
    max_history_len: int = 20
    history_keep_recent: int = 6
    heartbeat_interval: int = 60  # seconds
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5-coder:14b"
    ollama_fallback: bool = False

    @classmethod
    def from_env(cls) -> "Config":
        missing = []
        for var in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "CLAUDE_CODE_OAUTH_TOKEN", "GITHUB_TOKEN", "GITHUB_USERNAME"):
            if not os.getenv(var):
                missing.append(var)
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        repo_name = os.getenv("REPO_NAME", "claude-work")
        return cls(
            telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
            allowed_chat_id=int(os.environ["TELEGRAM_CHAT_ID"]),
            claude_oauth_token=os.environ["CLAUDE_CODE_OAUTH_TOKEN"],
            github_token=os.environ["GITHUB_TOKEN"],
            github_username=os.environ["GITHUB_USERNAME"],
            repo_name=repo_name,
            workspace_dir=os.path.expanduser(f"~/workspace/{repo_name}"),
            ollama_url=os.getenv("OLLAMA_URL", "http://ollama:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5-coder:14b"),
            ollama_fallback=os.getenv("OLLAMA_FALLBACK", "false").lower() == "true",
        )
