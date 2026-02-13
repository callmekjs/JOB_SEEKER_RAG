"""
Rerank: 검색 결과를 (query, document) 관련도로 재정렬.
Cross-encoder 기반: Retriever가 준 상위 k개를 질의-문서 쌍으로 점수 매겨 순서 조정.
"""

import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# 기본 모델. 한국어 강화 시 .env에 RERANK_MODEL=dragonkue/bge-reranker-v2-m3-ko
DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def _get_cross_encoder(model_name: Optional[str] = None):
    """CrossEncoder 로드."""
    from sentence_transformers import CrossEncoder

    name = model_name or os.environ.get("RERANK_MODEL") or DEFAULT_MODEL
    if "bge-reranker" in name.lower():
        import torch.nn as nn
        return CrossEncoder(name, default_activation_function=nn.Sigmoid())
    return CrossEncoder(name)


def rerank(
    query: str,
    items: list[dict[str, Any]],
    top_k: Optional[int] = None,
    model_name: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    (query, document) 관련도로 검색 결과 재정렬.

    Args:
        query: 검색 질의문.
        items: Retriever 등에서 나온 목록. 각 항목에 "text" 키 필수.
        top_k: 상위 몇 건만 반환. None이면 전부 반환 (정렬만).
        model_name: Cross-encoder 모델명. 미지정 시 RERANK_MODEL 또는 기본 모델 사용.

    Returns:
        동일 항목들, rerank_score 내림차순. 각 항목에 "rerank_score" 추가.
    """
    if not items:
        return []

    pairs = [(query.strip(), item.get("text") or "") for item in items]
    model = _get_cross_encoder(model_name)
    scores = model.predict(pairs)

    out = []
    for item, score in zip(items, scores):
        out.append({**item, "rerank_score": float(score)})
    out.sort(key=lambda x: x["rerank_score"], reverse=True)

    if top_k is not None:
        out = out[:top_k]
    return out
