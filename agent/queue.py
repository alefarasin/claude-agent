from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from config import Config

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    CANCELLED = "cancelled"


@dataclass
class AgentTask:
    id: int
    instruction: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None


_counter = 0
task_queues: dict[int, list[AgentTask]] = {}
running_tasks: dict[int, AgentTask | None] = {}
worker_tasks: dict[int, asyncio.Task | None] = {}


def enqueue(chat_id: int, instruction: str) -> AgentTask:
    global _counter
    _counter += 1
    task = AgentTask(id=_counter, instruction=instruction)
    task_queues.setdefault(chat_id, []).append(task)
    return task


def is_busy(chat_id: int) -> bool:
    return bool(running_tasks.get(chat_id))


def ensure_worker(chat_id: int, bot, cfg: Config) -> None:
    w = worker_tasks.get(chat_id)
    if w is None or w.done():
        worker_tasks[chat_id] = asyncio.create_task(
            _worker(chat_id, bot, cfg)
        )


def cancel_all(chat_id: int) -> bool:
    w = worker_tasks.get(chat_id)
    if not w or w.done():
        return False
    task_queues[chat_id] = []
    w.cancel()
    return True


def remove_task(chat_id: int, task_id: int) -> str:
    """Remove a task by ID. Returns 'running', 'removed', or 'not_found'."""
    running = running_tasks.get(chat_id)
    if running and running.id == task_id:
        w = worker_tasks.get(chat_id)
        if w and not w.done():
            task_queues[chat_id] = []
            w.cancel()
            return "running"
    queue = task_queues.get(chat_id, [])
    for i, task in enumerate(queue):
        if task.id == task_id:
            queue.pop(i)
            return "removed"
    return "not_found"


def queue_status(chat_id: int) -> tuple[AgentTask | None, list[AgentTask]]:
    return running_tasks.get(chat_id), task_queues.get(chat_id, [])


async def _heartbeat(chat_id: int, task: AgentTask, bot, interval: int) -> None:
    while True:
        await asyncio.sleep(interval)
        elapsed = int((datetime.now() - task.started_at).total_seconds() / 60)
        try:
            await bot.send_message(chat_id, f"⏳ Task #{task.id} ancora in esecuzione ({elapsed}min)...")
        except Exception:
            pass


async def _worker(chat_id: int, bot, cfg: Config) -> None:
    from agent import executor, history, workspace

    try:
        while True:
            queue = task_queues.get(chat_id, [])
            if not queue:
                break

            task = queue.pop(0)
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            running_tasks[chat_id] = task

            try:
                await bot.send_message(
                    chat_id,
                    f"▶️ Task #{task.id} in esecuzione...\n_{task.instruction[:80]}_",
                    parse_mode="Markdown",
                )

                if not await workspace.setup(cfg):
                    await bot.send_message(chat_id, "❌ Errore workspace. Controlla il GitHub token.")
                    task.status = TaskStatus.DONE
                    continue

                await workspace.pull(cfg)
                await history.compact_if_needed(chat_id, cfg)

                heartbeat = asyncio.create_task(
                    _heartbeat(chat_id, task, bot, cfg.heartbeat_interval)
                )
                try:
                    result = await executor.run(task.instruction, chat_id, cfg)
                finally:
                    heartbeat.cancel()
                    try:
                        await heartbeat
                    except asyncio.CancelledError:
                        pass

                task.status = TaskStatus.DONE
                history.add(chat_id, "user", task.instruction)
                history.add(chat_id, "assistant", result)

                display = result[:3800] + "\n\n... _(output troncato)_" if len(result) > 3800 else result
                await bot.send_message(
                    chat_id,
                    f"✅ *Task #{task.id} completato!*\n\n{display}",
                    parse_mode="Markdown",
                )

            except asyncio.CancelledError:
                task.status = TaskStatus.CANCELLED
                task_queues[chat_id] = []
                asyncio.create_task(
                    bot.send_message(chat_id, f"🚫 Task #{task.id} annullato.")
                )
                raise

            finally:
                running_tasks[chat_id] = None

    finally:
        worker_tasks[chat_id] = None
