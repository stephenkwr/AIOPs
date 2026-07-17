"""Tool interface for the agent loop.

`side_effect=True` marks a tool that changes state — the loop gates it behind
human approval. Read-only tools execute automatically. Tools take typed args
(validated by the loop against `parameters`) and never receive raw SQL/shell.
"""

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class ToolContext:
    session: AsyncSession
    workspace_id: uuid.UUID
    run_id: uuid.UUID | None  # None when a tool runs outside a run (e.g. tests)


@dataclass
class ToolResult:
    content: str  # text returned to the model
    data: dict = field(default_factory=dict)  # structured payload for the trace/UI
    citations: list[dict] = field(default_factory=list)


class Tool(Protocol):
    name: str
    description: str
    parameters: dict  # JSON Schema
    side_effect: bool

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult: ...
