from app.config import settings
from app.core.chunking import Chunk
from app.schemas.chat import Citation, ChatResponse, ChatRequest
from app.clients.groq_client import groq_client
from app.core.exceptions import ChatError
from groq.types.chat import ChatCompletionMessageParam
from app.core.chat import ChatMessage, ChatRole
import re
from typing import cast
from app.core.notebook import GeneratedOverview

client = groq_client

CITATION_SYSTEM_PROMPT = """You are Hereshko, an assistant that answers questions using ONLY the numbered sources provided below. You must not use any outside knowledge.

Rules:
1. Every factual claim you make must be followed by a citation marker in the exact format [n], where n is the source number it came from.
2. If a claim is supported by multiple sources, cite all of them directly next to each other, like this: [1][3].
3. If the sources do not contain enough information to answer the question, say so plainly instead of guessing or using outside knowledge.
4. Do not invent source numbers. Only cite numbers that actually appear in the sources below.
5. Write in clear, direct prose. Do not restate the sources verbatim — synthesize them into an answer.

Example of correct citation style:
"The engine relies on a turbocharger for increased power [2], though this comes at the cost of higher fuel consumption under load [1][4]."

Sources:
{context}
"""

def generate_answer(chat_request: ChatRequest, retrieved_chunks: list[Chunk], history: list[ChatMessage] | None = None, citation_start: int = 1) -> ChatResponse:
    context_blocks = []
    chunk_map: dict[int,Chunk] = {}
    for i,chunk in enumerate(retrieved_chunks,start=citation_start):
        context_blocks.append(f"[{i}] {chunk.content}")
        chunk_map[i] = chunk
    context = '\n\n'.join(context_blocks)

    messages_list: list[ChatCompletionMessageParam] = []

    messages_list.append(cast(ChatCompletionMessageParam,{'role':'system','content':CITATION_SYSTEM_PROMPT.format(context = context)}))

    for message in history or []:
        role = message.role.value
        content = message.content
        if message.role == ChatRole.ASSISTANT:
            content = re.sub(r'\[(\d+)\]','',content)
        messages_list.append(cast(ChatCompletionMessageParam,{'role' : role, 'content' : content}))

    messages_list.append(cast(ChatCompletionMessageParam,{'role':'user','content':chat_request.query}))

    chat_completion = client.chat.completions.create(
        model = settings.groq_llm_model,
        messages=messages_list,
        max_tokens=800,
    )

    answer_content = chat_completion.choices[0].message.content

    citations = []
    seen: set[str] = set()

    if answer_content is None:
        raise ChatError("LLM returned no response.")

    for n in re.findall(r'\[(\d+)\]',answer_content):
        num = int(n)
        chunk = chunk_map.get(num)
        if chunk is None:
            continue
        if chunk.chunk_id in seen:
            continue
        seen.add(chunk.chunk_id)
        citation = Citation(
            marker=num,
            chunk_id=chunk.chunk_id,
            content=chunk.content,
            source_type=chunk.position_type.value,
            source_name=chunk.source_name,
            page_number=chunk.page_number,
            paragraph_index=chunk.paragraph_index,
            slide_number=chunk.slide_number,
            timestamp_seconds=chunk.timestamp_seconds,
            source_url=chunk.metadata.get("url")
        )
        citations.append(citation)
        

    chat_response = ChatResponse(
        answer=answer_content,
        sources=citations
    )

    return chat_response


def generate_preview_summary(source_previews: list[dict]) -> GeneratedOverview:
    context = "\n\n".join(
        f"Source: {source['title']}\n{source['preview_text']}"
        for source in source_previews
        if source["preview_text"].strip()
    )

    if not context:
        raise ChatError("No source previews are available for summarization.")

    prompt = f"""
Create a concise introductory overview of this notebook.

Use only the source previews below. Explain the broad subject,
the main themes, and how the sources relate to one another.
Do not claim this is a complete or exhaustive summary.

Return ONLY valid JSON in exactly this shape:
{{
  "title": "A short descriptive notebook title",
  "summary": "The introductory overview"
}}

The title should be specific to the sources, concise, and no longer
than 60 characters. Do not use markdown or extra text outside the JSON.

Source previews:
{context}
"""

    completion = client.chat.completions.create(
        model=settings.groq_llm_model,
        messages=[
            {
                "role": "system",
                "content": "You create concise notebook introductions. Return only the requested JSON object.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        max_tokens=500,
        response_format={"type": "json_object"},
    )

    answer = completion.choices[0].message.content

    if not answer:
        raise ChatError("Summary generation returned no content.")

    try:
        overview = GeneratedOverview.model_validate_json(answer)
    except ValueError as error:
        raise ChatError("Summary generation returned invalid overview JSON.") from error

    return overview





