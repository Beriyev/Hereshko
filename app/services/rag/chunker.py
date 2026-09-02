from langchain_text_splitters import RecursiveCharacterTextSplitter
from transformers import AutoTokenizer
from app.core.chunking import Chunk
from app.core.normalization import Document
import uuid

tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3.8-27B")

def get_token_count(text: str): 
    tokens = tokenizer.encode(text,add_special_tokens=False)
    return len(tokens)

def chunker(document: Document, chunk_size: int = 612, chunk_overlap: int = 73) -> list[Chunk]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=get_token_count
    )

    boundaries = document.raw_metadata.get("boundaries",[])
    chunks: list[Chunk] = []
    if not boundaries:
        boundaries = [{"start":0,"end":len(document.content)}]

    for boundary in boundaries:
        document_part = document.content[boundary["start"]:boundary["end"]]
        document_part_chunks = splitter.split_text(document_part)
        for chunk in document_part_chunks:
            chunks.append(
                Chunk(
                    chunk_id=str(uuid.uuid4()),
                    document_id=document.document_id,
                    notebook_id=document.notebook_id,
                    content=chunk,
                    position_type=document.source_type,
                    page_number=boundary.get("page_number"),
                    paragraph_index=boundary.get("paragraph_index"),
                    slide_number=boundary.get("slide_number"),
                    timestamp_seconds=boundary.get("timestamp_seconds")
                )
            )
    return chunks

