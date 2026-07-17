import uuid

from app.constants import DEMO_WORKSPACE_ID
from app.db import SessionLocal
from app.models import Escalation
from app.tools.base import ToolContext
from app.tools.create_escalation import CreateEscalationTool
from app.tools.order_lookup import OrderLookupTool


async def test_order_lookup_finds_seeded_order(db_ready: None) -> None:
    async with SessionLocal() as session:
        ctx = ToolContext(session=session, workspace_id=DEMO_WORKSPACE_ID, run_id=uuid.uuid4())
        result = await OrderLookupTool().execute({"order_number": "1042"}, ctx)
    assert result.data["found"] is True
    assert result.data["status"] == "shipped"
    assert "1042" in result.content


async def test_order_lookup_missing_order(db_ready: None) -> None:
    async with SessionLocal() as session:
        ctx = ToolContext(session=session, workspace_id=DEMO_WORKSPACE_ID, run_id=uuid.uuid4())
        result = await OrderLookupTool().execute({"order_number": "does-not-exist"}, ctx)
    assert result.data.get("found") is False


async def test_create_escalation_inserts_row(db_ready: None) -> None:
    async with SessionLocal() as session:
        # run_id is nullable (FK SET NULL) — a standalone escalation is valid.
        ctx = ToolContext(session=session, workspace_id=DEMO_WORKSPACE_ID, run_id=None)
        result = await CreateEscalationTool().execute(
            {"summary": "Customer double-charged", "priority": "high"}, ctx
        )
        assert "created" in result.content.lower()
        found = await session.get(Escalation, uuid.UUID(result.data["escalation_id"]))
        assert found is not None
        assert found.priority == "high"
