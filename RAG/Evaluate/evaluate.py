"""
Evaluate: Retriever(및 Rerank) 품질 평가.
평가 세트(query + 관련 공고의 source_row_id)로 Recall@k, Hit@k, MRR 계산.
"""

import json
from pathlib import Path
from typing import Any, Callable, Optional

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


def _relevant_in_retrieved(
    retrieved: list[dict[str, Any]],
    relevant_source_row_ids: list[int],
) -> tuple[bool, Optional[int], int]:
    """
    retrieved 중 relevant_source_row_ids에 해당하는 고유 공고가 있는지,
    첫 등장 순위(1-based), 매칭된 고유 공고 수 반환.
    """
    relevant_set = set(relevant_source_row_ids)
    first_rank = None
    matched_ids = set()
    for rank, item in enumerate(retrieved, start=1):
        meta = item.get("metadata") or {}
        sid = meta.get("source_row_id")
        if sid is not None and sid in relevant_set:
            matched_ids.add(sid)
            if first_rank is None:
                first_rank = rank
    hit = len(matched_ids) > 0
    return hit, first_rank, len(matched_ids)


def evaluate_retrieval(
    eval_data: list[dict[str, Any]],
    retrieve_fn: Optional[Callable[..., list[dict[str, Any]]]] = None,
    k: int = 20,
    use_rerank: bool = False,
    rerank_top_k: Optional[int] = 10,
) -> dict[str, float]:
    """
    평가 세트로 Retriever(및 Rerank) 품질 측정.

    Args:
        eval_data: [{"query": str, "relevant_source_row_ids": [int, ...]}, ...]
        retrieve_fn: (query, limit=...) -> list[dict]. None이면 RAG.Retriever.retrieve 사용.
        k: Retriever에서 가져올 상위 k건.
        use_rerank: True면 Rerank 적용 후 순위 사용.
        rerank_top_k: Rerank 시 상위 몇 건만 사용할지 (None이면 전부).

    Returns:
        {"hit_at_k": 0~1, "mrr": 0~1, "recall_at_k": 0~1, "n_queries": int}
    """
    if retrieve_fn is None:
        from RAG.Retriever import retrieve as _retrieve
        def _fn(q: str, limit: int):
            return _retrieve(q, limit=limit)
        retrieve_fn = _fn

    hit_sum = 0.0
    mrr_sum = 0.0
    recall_sum = 0.0
    n = len(eval_data)
    if n == 0:
        return {"hit_at_k": 0.0, "mrr": 0.0, "recall_at_k": 0.0, "n_queries": 0}

    for item in eval_data:
        query = item.get("query") or ""
        relevant_ids = list(item.get("relevant_source_row_ids") or [])
        if not relevant_ids:
            continue

        retrieved = retrieve_fn(query, limit=k)
        if use_rerank:
            from RAG.Rerank import rerank
            retrieved = rerank(query, retrieved, top_k=rerank_top_k or k)

        hit, first_rank, matched_count = _relevant_in_retrieved(retrieved, relevant_ids)
        hit_sum += 1.0 if hit else 0.0
        mrr_sum += (1.0 / first_rank) if first_rank is not None else 0.0
        recall_sum += min(1.0, matched_count / len(relevant_ids))

    return {
        "hit_at_k": hit_sum / n,
        "mrr": mrr_sum / n,
        "recall_at_k": recall_sum / n,
        "n_queries": n,
    }


def load_eval_data(path: Path | str) -> list[dict[str, Any]]:
    """JSON 또는 JSONL 파일에서 평가 세트 로드. [{query, relevant_source_row_ids}, ...]"""
    path = Path(path)
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        return json.loads(text)
    return [json.loads(line) for line in text.splitlines() if line.strip()]
