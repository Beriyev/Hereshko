import json
import uuid
from typing import Any

from mcp import Client

from app.clients.groq_client import async_groq_client
from app.clients.mcp_client import call_tool, get_tool_specs, result_text
from app.config import settings
from app.core.chunking import Chunk
from app.core.normalization import SourceType


WEB_AGENT_SYSTEM_PROMPT = """You are a research assistant. The user's notebook context is provided below.

Use the web tools ONLY when the provided context is insufficient to answer the question.
- Call web_search to find relevant pages.
- Then call scrape_page on the most promising URLs to read their content.
- Do not call tools if the provided context already answers the question.
- When you have enough information, stop calling tools.

Provided context:
{context}
"""


def _to_chunk(title: str, url: str, content: str, notebook_id: str) -> Chunk:
    return Chunk(
        chunk_id=f"web-{uuid.uuid4().hex}",
        document_id=f"web-{url}",
        notebook_id=notebook_id,
        content=content,
        position_type=SourceType.WEBSITE,
        metadata={"url": url},
        source_name=title,
    )


def _chunks_from_call(name: str, structured: dict[str, Any], notebook_id: str) -> list[Chunk]:
    if name == "web_search":
        return [
            _to_chunk(title=result["title"], url=result["url"], content=result["snippet"], notebook_id=notebook_id)
            for result in structured.get("result", [])
        ]
    if name == "scrape_page":
        return [
            _to_chunk(title=structured["title"], url=structured["url"], content=structured["content"], notebook_id=notebook_id)
        ]
    return []


async def gather_web_sources(query: str, context_chunks: list[Chunk], notebook_id: str) -> list[Chunk]:
    context = "\n\n".join(chunk.content for chunk in context_chunks)
    messages: list[Any] = [
        {"role": "system", "content": WEB_AGENT_SYSTEM_PROMPT.format(context=context)},
        {"role": "user", "content": query},
    ]

    by_url: dict[str, Chunk] = {}

    async with Client(settings.mcp_server_url) as client:
        tool_specs = await get_tool_specs(client=client)

        for _ in range(settings.web_tool_max_iterations):
            completion = await async_groq_client.chat.completions.create(
                messages=messages,
                model=settings.groq_llm_model,
                tools=tool_specs,
                tool_choice="auto",
                max_tokens=1024,
            )

            message = completion.choices[0].message
            messages.append(message.model_dump(exclude_none=True))

            if not message.tool_calls:
                break

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}

                result = await call_tool(client=client, name=tool_name, arguments=arguments)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_text(result=result),
                })

                if result.is_error or result.structured_content is None:
                    continue

                for chunk in _chunks_from_call(name=tool_name, structured=result.structured_content, notebook_id=notebook_id):
                    chunk_url = chunk.metadata["url"]
                    dict_chunk = by_url.get(chunk_url)
                    if dict_chunk is None or len(chunk.content) > len(dict_chunk.content):
                        by_url[chunk_url] = chunk

    return list(by_url.values())
