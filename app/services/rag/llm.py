from app.config import settings
from app.core.chunking import Chunk
from app.schemas.chat import Citation, ChatResponse, ChatRequest
from app.clients.groq_client import groq_client
from app.core.exceptions import ChatError
from groq.types.chat import ChatCompletionMessageParam
from app.core.chat import ChatMessage, ChatRole
import re
from typing import cast

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

def generate_answer(chat_request: ChatRequest, retrieved_chunks: list[Chunk], history: list[ChatMessage] | None = None) -> ChatResponse:
    context_blocks = []
    chunk_map: dict[int,Chunk] = {}
    for i,chunk in enumerate(retrieved_chunks,start=1):
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
        messages=messages_list
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
            source_type=str(chunk.position_type),
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





