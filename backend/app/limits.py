"""Per-IP rate limiting (slowapi) for the expensive endpoints.

The free-tier LLM/embedding quotas are the scarce resource — one enthusiastic
visitor (or bot) hammering /agent could exhaust a day's quota in minutes. Limits
are enforced per client IP, in memory (fine for a single free-tier instance; a
multi-replica deployment would back this with Redis).

Health probes and read endpoints stay unlimited.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# One knob per endpoint class, importable by the routers.
ASK_LIMIT = "20/minute"  # chat + agent answers (LLM tokens)
RESUME_LIMIT = "30/minute"  # approval resumes (cheap-ish, but still LLM turns)
UPLOAD_LIMIT = "20/minute"  # document ingestion (embedding quota)
EVAL_LIMIT = "10/hour"  # eval runs (a graded run = ~150 LLM calls)
DEMO_SEED_LIMIT = "10/hour"  # demo seeding (12 docs of embedding quota)
