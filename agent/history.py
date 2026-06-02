from __future__ import annotations
import logging
from config import Config

logger = logging.getLogger(__name__)

_store: dict[int, list[dict]] = {}


def get(chat_id: int) -> list[dict]:
    return _store.setdefault(chat_id, [])


def add(chat_id: int, role: str, content: str) -> None:
    get(chat_id).append({"role": role, "content": content})


def clear(chat_id: int) -> None:
    _store[chat_id] = []


def build_context(chat_id: int) -> str:
    lines = []
    for msg in get(chat_id):
        if msg["role"] == "system":
            lines.append(msg["content"])
        elif msg["role"] == "user":
            lines.append(f"User: {msg['content']}")
        else:
            lines.append(f"Assistant: {msg['content']}")
    return "\n".join(lines)


async def compact_if_needed(chat_id: int, cfg: Config) -> None:
    from agent.executor import run_raw

    history = get(chat_id)
    if len(history) <= cfg.max_history_len:
        return

    import os
    to_summarize = history[: -cfg.history_keep_recent]
    recent = history[-cfg.history_keep_recent :]
    conv_text = "\n".join(
        msg["content"] if msg["role"] == "system"
        else f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
        for msg in to_summarize
    )
    summary = await run_raw(
        f"Summarize this conversation concisely, preserving key context, decisions, and technical details:\n\n{conv_text}",
        cwd=os.path.expanduser("~"),
        cfg=cfg,
    )
    _store[chat_id] = [
        {"role": "system", "content": f"[Summary of previous conversation]: {summary}"}
    ] + recent
    logger.info(f"History compacted for chat_id {chat_id}: {len(to_summarize)} messages → summary")
