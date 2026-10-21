from __future__ import annotations

from typing import Any, Callable

from ..models.card import AgentCard, Skill
from ..models.message import Message
from ..models.task import Task
from ..runners.base import TaskExecutionHandler


class LangGraphA2AAdapter:
    """Bridges a LangGraph StateGraph / Runnable into canonical A2A task handlers and Agent Cards."""

    def __init__(
        self,
        graph: Any,
        name: str,
        description: str,
        did: str,
        skills: list[Skill] | None = None,
        input_key: str = "messages",
        output_key: str = "messages",
    ) -> None:
        self.graph = graph
        self.name = name
        self.description = description
        self.did = did
        self.skills = skills or [
            Skill(id="graph_execute", name=name, description=description)
        ]
        self.input_key = input_key
        self.output_key = output_key

    def as_agent_card(self) -> AgentCard:
        return AgentCard(
            name=self.name,
            description=self.description,
            did=self.did,
            skills=self.skills,
            metadata={"framework": "langgraph"},
        )

    def as_task_handler(self) -> TaskExecutionHandler:
        async def handler(
            task: Task,
            emit_status: Callable[[str, dict[str, Any] | None], Any],
            is_cancelled: Callable[[], bool],
        ) -> tuple[str, list[Any]]:
            user_text = task.latest_message.get_text() if task.latest_message else ""
            await emit_status("invoking_langgraph", {"node": "entrypoint"})

            if is_cancelled():
                return "Cancelled before invocation", []

            # Invoke graph
            inputs = {self.input_key: [{"role": "user", "content": user_text}]}
            if hasattr(self.graph, "ainvoke"):
                res = await self.graph.ainvoke(inputs)
            else:
                res = self.graph.invoke(inputs)

            # Extract output
            output_raw = res.get(self.output_key, res)
            if isinstance(output_raw, list) and output_raw:
                last_elem = output_raw[-1]
                output_text = getattr(last_elem, "content", str(last_elem))
            elif isinstance(output_raw, dict):
                output_text = str(output_raw.get("content", output_raw))
            else:
                output_text = str(output_raw)

            await emit_status("langgraph_completed")
            return output_text, []

        return handler
