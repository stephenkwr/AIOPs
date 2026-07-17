"""create_escalation — side-effecting tool, gated behind human approval."""

from sqlalchemy import select

from app.models import Escalation, Order
from app.tools.base import ToolContext, ToolResult

_PRIORITIES = ("low", "medium", "high")


class CreateEscalationTool:
    name = "create_escalation"
    description = (
        "Create an escalation ticket for a human support agent. This performs an "
        "action that changes state and requires human approval before it runs. Use "
        "it when the issue needs a human or you cannot resolve it from the sources."
    )
    parameters = {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "What the human needs to handle."},
            "priority": {"type": "string", "enum": list(_PRIORITIES)},
            "order_number": {"type": "string", "description": "Related order, if any."},
        },
        "required": ["summary"],
    }
    side_effect = True

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        summary = str(args.get("summary", "")).strip() or "Escalation"
        priority = str(args.get("priority", "medium"))
        if priority not in _PRIORITIES:
            priority = "medium"

        order_id = None
        order_number = args.get("order_number")
        if order_number:
            order = await ctx.session.scalar(
                select(Order).where(
                    Order.workspace_id == ctx.workspace_id,
                    Order.order_number == str(order_number),
                )
            )
            order_id = order.id if order else None

        escalation = Escalation(
            workspace_id=ctx.workspace_id,
            run_id=ctx.run_id,
            order_id=order_id,
            priority=priority,
            summary=summary,
            status="open",
        )
        ctx.session.add(escalation)
        await ctx.session.commit()
        await ctx.session.refresh(escalation)

        return ToolResult(
            content=(
                f"Escalation ticket created (priority={priority}). A human agent will follow up."
            ),
            data={
                "escalation_id": str(escalation.id),
                "priority": priority,
                "summary": summary,
            },
        )
