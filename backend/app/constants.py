"""Shared constants."""

import uuid

# Must match the workspace seeded in migration 0001. Until auth lands (Phase 6),
# every request operates in this single demo workspace.
DEMO_WORKSPACE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
