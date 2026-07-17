"""Tool registry: the fixed set of tools the agent may use."""

from app.core.llm.base import ToolSpec
from app.tools.base import Tool
from app.tools.create_escalation import CreateEscalationTool
from app.tools.kb_search import KnowledgeBaseSearchTool
from app.tools.order_lookup import OrderLookupTool

TOOLS: list[Tool] = [
    KnowledgeBaseSearchTool(),
    OrderLookupTool(),
    CreateEscalationTool(),
]

REGISTRY: dict[str, Tool] = {t.name: t for t in TOOLS}


def tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(name=t.name, description=t.description, parameters=t.parameters) for t in TOOLS
    ]
