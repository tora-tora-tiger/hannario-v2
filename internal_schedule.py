from letta_client import Letta, MessageCreate, TextContent

from letta_agent import RETURN_MESSAGE_TYPES, extract_assistant_text
from schedule_db import ScheduledTask


def build_internal_task_prompt(task: ScheduledTask) -> str:
    return "\n".join(
        [
            "Internal scheduled task",
            "This is private. Do not assume a Discord message will be sent.",
            "Think about the task note and respond with a short internal reflection.",
            f"task_id: {task.id}",
            f"kind: {task.kind}",
            f"channel_id: {task.channel_id}",
            f"message: {task.message}",
            f"note: {task.note or ''}",
            f"due_at: {task.due_at}",
        ]
    )


def consult_letta_for_internal_task(client: Letta, agent_id: str, task: ScheduledTask) -> str:
    response = client.agents.messages.create(
        agent_id=agent_id,
        messages=[
            MessageCreate(
                role="user",
                content=[TextContent(text=build_internal_task_prompt(task))],
            )
        ],
        include_return_message_types=RETURN_MESSAGE_TYPES,
    )
    text = extract_assistant_text(response)
    if text is None:
        raise RuntimeError(f"Could not extract Letta internal task reply from {type(response)!r}")
    return text
