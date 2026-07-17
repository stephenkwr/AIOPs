"""lookup_order — read-only mock-ERP lookup."""

from sqlalchemy import select

from app.models import Order
from app.tools.base import ToolContext, ToolResult


class OrderLookupTool:
    name = "lookup_order"
    description = (
        "Look up a customer order by order number or customer email. Returns the "
        "order status, items, and total. Read-only."
    )
    parameters = {
        "type": "object",
        "properties": {
            "order_number": {"type": "string", "description": "The order number, e.g. 1042."},
            "customer_email": {"type": "string", "description": "The customer's email."},
        },
    }
    side_effect = False

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        order_number = args.get("order_number")
        customer_email = args.get("customer_email")

        stmt = select(Order).where(Order.workspace_id == ctx.workspace_id)
        if order_number:
            stmt = stmt.where(Order.order_number == str(order_number))
        elif customer_email:
            stmt = stmt.where(Order.customer_email == str(customer_email))
        else:
            return ToolResult(content="Provide an order_number or customer_email.", data={})

        order = await ctx.session.scalar(stmt)
        if order is None:
            return ToolResult(content="No matching order was found.", data={"found": False})

        data = {
            "found": True,
            "order_number": order.order_number,
            "status": order.status,
            "customer_email": order.customer_email,
            "total_usd": float(order.total_usd),
            "items": order.items,
        }
        content = (
            f"Order {order.order_number}: status={order.status}, "
            f"total=${float(order.total_usd):.2f}, items={order.items}, "
            f"customer={order.customer_email}"
        )
        return ToolResult(content=content, data=data)
