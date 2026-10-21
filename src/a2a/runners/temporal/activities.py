from __future__ import annotations

import logging
from typing import Any

from .contracts import ActivityStepInput, ActivityStepOutput

LOGGER = logging.getLogger(__name__)

try:
    from temporalio import activity
except ImportError:
    # Graceful fallback decorator if temporalio optional dependency is absent
    def activity_defn(fn=None, **kwargs):
        if fn is not None:
            return fn
        return lambda f: f

    class _ActivityModule:
        defn = staticmethod(activity_defn)

    activity = _ActivityModule()  # type: ignore


@activity.defn
async def execute_a2a_step(step_input: ActivityStepInput) -> ActivityStepOutput:
    """Default discrete execution activity for agent computation, LLM reasoning, or tool dispatch."""
    LOGGER.info(
        "Executing temporal activity step '%s' for task %s",
        step_input.step_name,
        step_input.task_id,
    )
    # Activities are overridden by workers or customized per agent pipeline
    return ActivityStepOutput(
        output_text=f"Completed {step_input.step_name}",
        artifacts=[],
        status_message=f"Activity {step_input.step_name} executed",
    )
