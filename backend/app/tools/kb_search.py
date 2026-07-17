"""search_knowledge_base — read-only retrieval tool."""

from app.config import settings
from app.core.answer import citations_payload
from app.core.retrieval.retriever import retrieve
from app.tools.base import ToolContext, ToolResult


class KnowledgeBaseSearchTool:
    name = "search_knowledge_base"
    description = (
        "Search the internal knowledge base and support documents. Use this to "
        "answer the user's factual questions. Returns numbered sources; cite them "
        "inline as [n] in your final answer."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to search for."},
        },
        "required": ["query"],
    }
    side_effect = False

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        query = str(args.get("query", "")).strip()
        if not query:
            return ToolResult(content="No query provided.", data={"citations": []})
        results = await retrieve(
            ctx.session,
            ctx.workspace_id,
            query,
            mode=settings.retrieval_mode,
            k=settings.retrieval_k,
            candidates=settings.retrieval_candidates,
        )
        if not results:
            return ToolResult(content="No relevant sources found.", data={"citations": []})
        lines = []
        for r in results:
            loc = f" · {r.location}" if r.location else ""
            lines.append(f"[{r.index}] ({r.filename}{loc}) {r.text}")
        citations = citations_payload(results)
        return ToolResult(
            content="\n".join(lines),
            data={"citations": citations},
            citations=citations,
        )
