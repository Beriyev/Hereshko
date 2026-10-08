"""Read-only chunk tuning on indexed source text; no Groq calls or DB writes.

Run: .venv/Scripts/python.exe -m tests.benchmark_chunking
This measures dense retrieval + the existing MMR, not Weaviate's hybrid/reranker
or final answer quality. Original extraction files are not retained, so adjacent
stored fragments are joined only when an exact suffix/prefix overlap exists.
"""
import os
os.environ["HF_HUB_OFFLINE"] = "1"

import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
import weaviate

from app.core.normalization import Document, SourceType
from app.services.rag.chunker import chunker, get_token_count
from app.services.rag.embeddings import get_embedding_model
from app.services.rag.weaviate_service import WeaviateService


SETTINGS = [(256, 32), (320, 48), (384, 48), (384, 64),
            (448, 64), (448, 96), (512, 96), (612, 128)]
# Questions and supporting phrases chosen before running the parameter sweep.
# Each label is an existing source page, not an LLM-generated answer.
PROBES = [
    ("SPM", 30, "What tangible and intangible elements constitute organizational business value?",
     ["monetary assets", "brand recognition", "strategic alignment"]),
    ("SPM", 31, "Who appoints a program manager and what are their responsibilities?",
     ["senior official", "leadership, conduct, and performance", "program objectives"]),
    ("SPM", 80, "Who signs a program charter and what does the charter authorize?",
     ["signed by a sponsor", "organizational resources"]),
    ("SPM", 102, "What activities are involved in program benefits delivery?",
     ["monitoring the organizational environment", "interdependencies", "opportunities and threats"]),
    ("SPM", 105, "How are benefits checked against the business case at the end of a program?",
     ["compared", "business case", "acceptance criteria"]),
    ("SPM", 182, "Who implements risk management across component projects and whom do they report to?",
     ["program risk manager", "reports to the program manager"]),
    ("SPM", 182, "Does a program contingency reserve replace component contingency reserves?",
     ["not a substitute", "component contingency"]),
    ("SPM", 182, "How does program schedule management track progress and correct schedule variances?",
     ["start and finish", "planned timelines", "corrective action"]),
    ("L9", 11, "Why are verifiable objectives useful in evaluating management?",
     ["measurement", "effectiveness and efficiency"]),
    ("L9", 12, "What three dimensions define a strategy, and who formulates it?",
     ["long-term objectives", "course of action", "allocating", "top level"]),
    ("L9", 21, "How do strategic, tactical, and operational plans differ in time frame and scope?",
     ["upper-level", "lower-level", "daily, weekly, or monthly", "five or more years"]),
    ("L9", 58, "How does Blue Ocean Strategy combine differentiation and low cost?",
     ["differentiation and low cost", "uncontested market space"]),
    ("L9", 79, "How does TOWS link internal capabilities to external conditions?",
     ["internal strengths", "threats and opportunities"]),
    ("L9", 84, "What strengths and opportunity underpin the iPhone SO strategy example?",
     ["brand awareness", "product design", "touchscreen smartphones"]),
    ("L9", 86, "How does the Apple Watch illustrate a WO strategy?",
     ["smaller product portfolio", "wearables", "apple watch in 2015"]),
    ("L9", 87, "How does launching Apple TV+ address weaknesses and threats?",
     ["limited functionality", "streaming service", "apple tv+"]),
]


def normalized(text):
    return " ".join(text.lower().split())


def read_documents():
    groups = defaultdict(list)
    client = weaviate.connect_to_local()
    try:
        for obj in client.collections.get("Chunks").iterator():
            p = obj.properties
            position = (p.get("page_number"), p.get("slide_number"),
                        p.get("timestamp_seconds"), p.get("paragraph_index"))
            groups[(p["document_id"], p["notebook_id"], p["source_name"], p["position_type"], position)].append(p["content"])
    finally:
        client.close()
    documents = []
    unjoined = 0
    for (document_id, notebook_id, title, kind, position), texts in groups.items():
        texts = list(dict.fromkeys(texts))
        # Recover order from overlap, rather than relying on UUID iteration order.
        while len(texts) > 1:
            best = (0, None, None)
            for i, first in enumerate(texts):
                for j, second in enumerate(texts):
                    if i == j:
                        continue
                    for length in range(min(len(first), len(second)), 19, -1):
                        if first[-length:] == second[:length]:
                            if length > best[0]:
                                best = (length, i, j)
                            break
            length, i, j = best
            if not length:
                unjoined += len(texts) - 1
                break
            merged = texts[i] + texts[j][length:]
            texts = [text for k, text in enumerate(texts) if k not in (i, j)] + [merged]
        page, slide, timestamp, paragraph = position
        for text in texts:
            boundary = {"start": 0, "end": len(text), "page_number": page,
                        "slide_number": slide, "timestamp_seconds": timestamp,
                        "paragraph_index": paragraph}
            documents.append(Document(
                document_id=document_id, notebook_id=notebook_id, title=title,
                content=text, source_type=SourceType(kind), source_identifier="benchmark",
                ingested_at=datetime.now(timezone.utc), raw_metadata={"boundaries": [boundary]},
            ))
    print(f"Corpus: {len(documents)} boundary texts; {unjoined} fragment joins unavailable", flush=True)
    for prefix, page, query, phrases in PROBES:
        text = normalized(" ".join(d.content for d in documents
                                   if d.title.startswith(prefix) and d.raw_metadata["boundaries"][0]["page_number"] == page))
        assert all(normalized(phrase) in text for phrase in phrases), (query, phrases)
    return documents


def run():
    sys.stdout.reconfigure(encoding="utf-8")
    started = time.perf_counter()
    documents = read_documents()
    variants = {}
    unique = {}
    for size, overlap in SETTINGS:
        chunks = [chunk for document in documents for chunk in chunker(document, size, overlap)]
        variants[(size, overlap)] = chunks
        for chunk in chunks:
            unique.setdefault(chunk.content, len(unique))
        print(f"Split {size}/{overlap}: {len(chunks)} chunks", flush=True)
    model = get_embedding_model()
    print(f"Embedding {len(unique)} unique passages on {model.device}; max_seq_length={model.max_seq_length}", flush=True)
    texts = list(unique)
    lengths = [len(model.tokenizer.encode(text, truncation=False, verbose=False)) for text in texts]
    vectors = []
    for start in range(0, len(texts), 128):
        vectors.append(model.encode(texts[start:start + 128], batch_size=8, normalize_embeddings=True,
                                    convert_to_numpy=True, show_progress_bar=False))
        print(f"Embedded {min(start + 128, len(texts))}/{len(texts)}", flush=True)
    vectors = np.concatenate(vectors)
    queries = model.encode(["Represent this sentence for searching relevant passages: " + p[2] for p in PROBES],
                           batch_size=8, normalize_embeddings=True, convert_to_numpy=True)
    service = object.__new__(WeaviateService)
    print("size overlap chunks truncated% overflow_tokens% page_hit@6 evidence@6 evidence@8 SPM_evidence@6 mean_context_tokens@6", flush=True)
    for (size, overlap), chunks in variants.items():
        indices = [unique[c.content] for c in chunks]
        matrix = vectors[indices]
        chunk_lengths = [lengths[i] for i in indices]
        hits, evidence6, evidence8, spm_evidence, context = [], [], [], [], []
        for probe, query_vector in zip(PROBES, queries):
            prefix, page, _, phrases = probe
            notebook_id = next(c.notebook_id for c in chunks if c.source_name.startswith(prefix) and c.page_number == page)
            allowed = np.array([i for i, c in enumerate(chunks) if c.notebook_id == notebook_id])
            ranked = allowed[np.argsort(-(matrix[allowed] @ query_vector))]
            for k, output in [(6, evidence6), (8, evidence8)]:
                # Match L2's 12 candidates / 6 chunks and L1's 15 / 8.
                candidates = ranked[:12 if k == 6 else 15]
                selected = service._select_with_mmr(
                    [chunks[i] for i in candidates], [matrix[i].tolist() for i in candidates],
                    query_vector.tolist(), limit=k, lambda_val=0.75)
                if k == 6:
                    hits.append(any(c.source_name.startswith(prefix) and c.page_number == page for c in selected))
                    context.append(sum(get_token_count(c.content) for c in selected))
                # Require supporting phrases from the labeled page, not incidental matches.
                relevant = [normalized(c.content) for c in selected
                            if c.source_name.startswith(prefix) and c.page_number == page]
                score = sum(any(normalized(phrase) in text for text in relevant) for phrase in phrases) / len(phrases)
                output.append(score)
                if k == 6 and prefix == "SPM":
                    spm_evidence.append(score)
        truncated = np.mean([length > model.max_seq_length for length in chunk_lengths]) * 100
        overflow = sum(max(0, length - model.max_seq_length) for length in chunk_lengths) / sum(chunk_lengths) * 100
        print(f"{size} {overlap} {len(chunks)} {truncated:.2f} {overflow:.2f} "
              f"{np.mean(hits)*100:.2f} {np.mean(evidence6)*100:.2f} {np.mean(evidence8)*100:.2f} "
              f"{np.mean(spm_evidence)*100:.2f} {np.mean(context):.0f}", flush=True)
    print(f"Elapsed: {time.perf_counter()-started:.1f}s", flush=True)


if __name__ == "__main__":
    run()
