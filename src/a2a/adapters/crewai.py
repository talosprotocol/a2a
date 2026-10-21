from __future__ import annotations

import asyncio
from typing import Any, Callable

from ..models.card import AgentCard, Skill
from ..models.task import Task
from ..runners.base import TaskExecutionHandler


class CrewAIA2AAdapter:
    """Bridges a CrewAI Agent or Crew into canonical A2A task handlers and Agent Cards."""

    def __init__(
        self,
        crew_or_agent: Any,
        name: str,
        description: str,
        did: str,
        skills: list[Skill] | None = None,
    ) -> None:
        self.target = crew_or_agent
        self.name = name
        self.description = description
        self.did = did
        self.skills = skills or self._extract_skills()

    def _extract_skills(self) -> list[Skill]:
        skills: list[Skill] = []
        tools = getattr(self.target, "tools", None) or []
        for t in tools:
            tool_name = getattr(t, "name", str(t))
            tool_desc = getattr(t, "description", "")
            skills.append(Skill(id=f"tool:{tool_name}", name=tool_name, description=tool_desc))
        if not skills:
            skills.append(Skill(id="execute_crew", name=self.name, description=self.description))
        return skills

    def as_agent_card(self) -> AgentCard:
        role = getattr(self.target, "role", "")
        goal = getattr(self.target, "goal", "")
        desc = self.description or f"{role} - {goal}".strip(" -")
        return AgentCard(
            name=self.name,
            description=desc,
            did=self.did,
            skills=self.skills,
            metadata={"framework": "crewai", "role": role},
        )

    def as_task_handler(self) -> TaskExecutionHandler:
        async def handler(
            task: Task,
            emit_status: Callable[[str, dict[str, Any] | None], Any],
            is_cancelled: Callable[[], bool],
        ) -> tuple[str, list[Any]]:
            user_text = task.latest_message.get_text() if task.latest_message else ""
            await emit_status("starting_crew_execution", {"agent": self.name})

            if is_cancelled():
                return "Cancelled before execution", []

            # CrewAI kickoff / execute is often sync
            if hasattr(self.target, "kickoff_async"):
                res = await self.target.kickoff_async(inputs={"prompt": user_text})
            elif hasattr(self.target, "kickoff"):
                res = await asyncio.to_thread(self.target.kickoff, inputs={"prompt": user_text})
            elif hasattr(self.target, "execute_task"):
                res = await asyncio.to_thread(self.target.execute_task, user_text)
            else:
                res = str(self.target)

            output_text = getattr(res, "raw", str(res))
            await emit_status("crew_execution_finished")
            return output_text, []

        return handler
