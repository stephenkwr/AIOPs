"""FastAPI dependencies shared across routers."""

import uuid

from app.constants import DEMO_WORKSPACE_ID


async def get_workspace_id() -> uuid.UUID:
    """Resolve the active workspace.

    v1 always returns the demo workspace. When auth lands this becomes "derive
    the workspace from the authenticated user", and every endpoint that already
    depends on it keeps working unchanged.
    """
    return DEMO_WORKSPACE_ID
