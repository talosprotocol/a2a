from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActivityStepInput:
    task_id: str
    context_id: str
    step_name: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActivityStepOutput:
    output_text: str
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    status_message: str = "Step completed"


@dataclass
class WorkflowTaskInput:
    task_id: str
    context_id: str
    message: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
