"""Shared constants."""

import uuid

# Must match the workspace seeded in migration 0001. Until auth lands (Phase 6),
# every request operates in this single demo workspace.
DEMO_WORKSPACE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

# Isolated workspace holding the fixed eval corpus, so evaluation never depends on
# (or pollutes) whatever the user uploaded to the demo workspace. Seeded in migration 0005.
EVAL_WORKSPACE_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
