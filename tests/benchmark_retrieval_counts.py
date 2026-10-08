"""Read-only candidate/context sweep at 384/48; no Groq or index writes.

Run: .venv/Scripts/python.exe -m tests.benchmark_retrieval_counts
Uses the real embedder and MMR with notebook filters. Dense candidates only:
this does not model Weaviate hybrid search, its reranker, or generated answers.
"""
import sys
import time

import numpy as np

from tests.benchmark_chunking import PROBES, normalized, read_documents
from app.services.rag.chunker import chunker, get_token_count
from app.services.rag.embeddings import get_embedding_model
from app.services.rag.weaviate_service import WeaviateService


COUNTS = [(12, 6), (16, 6), (24, 6), (32, 6),
          (15, 8), (20, 8), (24, 8), (32, 8), (40, 8),
          (20, 10), (24, 10), (32, 10), (40, 10),
          (24, 12), (32, 12), (40, 12), (48, 12),
          (32, 16), (48, 16)]
MULTI_PAGE = [
    ("Compare the strengths-opportunities and weaknesses-opportunities Apple examples in TOWS.",
     [("L9", 84, ["brand awareness", "touchscreen smartphones"]),
      ("L9", 86, ["smaller product portfolio", "apple watch in 2015"])]),
    ("Compare Apple's SO iPhone strategy with its ST strategy responding to charger regulations.",
     [("L9", 84, ["product design", "touchscreen smartphones"]),
      ("L9", 85, ["brand loyalty", "regulators", "type c"])]),
    ("How do Apple Watch and Apple TV+ illustrate different responses to internal weaknesses in TOWS?",
     [("L9", 86, ["smaller product portfolio", "wearables"]),
      ("L9", 87, ["limited functionality", "apple tv+"])]),
    ("How do the three dimensions of strategy relate to strategic, tactical, and operational planning?",
     [("L9", 12, ["long-term objectives", "course of action", "allocating"]),
      ("L9", 21, ["upper-level", "lower-level", "daily, weekly, or monthly"])]),
    ("How could TOWS connect electric vehicle strengths and weaknesses with market opportunities and threats?",
     [("L9", 78, ["silent engine", "high price", "government subsidy", "entry of competitors"]),
      ("L9", 79, ["internal strengths", "threats and opportunities"])]),
    ("Compare program benefits delivery activities with benefits transition acceptance checks.",
     [("SPM", 102, ["monitoring the organizational environment", "interdependencies"]),
      ("SPM", 105, ["business case", "acceptance criteria"])]),
    ("How do sponsor charter authorization and program manager appointment divide program responsibilities?",
     [("SPM", 80, ["signed by a sponsor", "organizational resources"]),
      ("SPM", 31, ["senior official", "leadership, conduct, and performance"])]),
    ("How do program manager responsibilities support tangible and intangible organizational value?",
     [("SPM", 31, ["program objectives", "delivering benefits and value"]),
      ("SPM", 30, ["monetary assets", "brand recognition", "strategic alignment"])]),
]


def run():
    sys.stdout.reconfigure(encoding="utf-8")
    started = time.perf_counter()
    documents = read_documents()
    chunks = [c for d in documents for c in chunker(d, 384, 48)]
    probes = [(query, [(prefix, page, phrases)]) for prefix, page, query, phrases in PROBES] + MULTI_PAGE
    for query, labels in probes:
        for prefix, page, phrases in labels:
            text = normalized(" ".join(c.content for c in chunks if c.source_name.startswith(prefix) and c.page_number == page))
            assert all(normalized(p) in text for p in phrases), (query, prefix, page, phrases)
    model = get_embedding_model()
    print(f"Embedding {len(chunks)} chunks and {len(probes)} questions on {model.device}", flush=True)
    matrix = model.encode([c.content for c in chunks], batch_size=8, normalize_embeddings=True,
                          convert_to_numpy=True, show_progress_bar=False)
    query_vectors = model.encode(["Represent this sentence for searching relevant passages: " + q for q, _ in probes],
                                 batch_size=8, normalize_embeddings=True, convert_to_numpy=True)
    lengths = {c.chunk_id: get_token_count(c.content) for c in chunks}
    rankings = []
    for (_, labels), vector in zip(probes, query_vectors):
        prefix, page, _ = labels[0]
        notebook_id = next(c.notebook_id for c in chunks if c.source_name.startswith(prefix) and c.page_number == page)
        allowed = np.array([i for i, c in enumerate(chunks) if c.notebook_id == notebook_id])
        rankings.append(allowed[np.argsort(-(matrix[allowed] @ vector))])
    service = object.__new__(WeaviateService)
    print("candidates provided evidence% single% multi% complete_questions% all_pages_hit% mean_context_tokens p95_context_tokens mmr_ms_per_query", flush=True)
    for candidate_count, provided in COUNTS:
        scores, complete, page_hits, contexts = [], [], [], []
        selection_seconds = 0
        for (_, labels), vector, ranked in zip(probes, query_vectors, rankings):
            candidates = ranked[:candidate_count]
            selection_started = time.perf_counter()
            selected = service._select_with_mmr(
                [chunks[i] for i in candidates], [matrix[i].tolist() for i in candidates],
                vector.tolist(), limit=provided, lambda_val=0.75)
            selection_seconds += time.perf_counter() - selection_started
            found = total = 0
            all_pages = True
            for prefix, page, phrases in labels:
                relevant = [normalized(c.content) for c in selected if c.source_name.startswith(prefix) and c.page_number == page]
                all_pages &= bool(relevant)
                found += sum(any(normalized(phrase) in text for text in relevant) for phrase in phrases)
                total += len(phrases)
            scores.append(found / total)
            complete.append(found == total)
            page_hits.append(all_pages)
            contexts.append(sum(lengths[c.chunk_id] for c in selected))
        print(f"{candidate_count} {provided} {np.mean(scores)*100:.2f} "
              f"{np.mean(scores[:len(PROBES)])*100:.2f} {np.mean(scores[len(PROBES):])*100:.2f} "
              f"{np.mean(complete)*100:.2f} {np.mean(page_hits)*100:.2f} "
              f"{np.mean(contexts):.0f} {np.percentile(contexts,95):.0f} "
              f"{selection_seconds/len(probes)*1000:.1f}", flush=True)
    print(f"Elapsed: {time.perf_counter()-started:.1f}s", flush=True)


if __name__ == "__main__":
    run()
