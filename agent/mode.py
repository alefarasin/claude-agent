from __future__ import annotations

CLAUDE = "claude"
OLLAMA = "ollama"

_store: dict[int, str] = {}


def get(chat_id: int) -> str:
    return _store.get(chat_id, CLAUDE)


def set(chat_id: int, mode: str) -> None:
    if mode not in (CLAUDE, OLLAMA):
        raise ValueError(f"Invalid mode: {mode}")
    _store[chat_id] = mode
