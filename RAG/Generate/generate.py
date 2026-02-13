"""
Generate: Retriever(및 Rerank) 결과를 context로 LLM에 넣어 답변 생성.
"""

import re
import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

DEFAULT_MODEL = "gpt-4o-mini"


def _job_key(item: dict[str, Any]) -> tuple[Any, ...]:
    """공고 구분 키 (중복 source 제거용)."""
    meta = item.get("metadata") or {}
    sid = meta.get("source_row_id")
    c = meta.get("company")
    j = meta.get("job_role")
    if sid is not None:
        return (sid, c, j)
    return (c, j)


def _importance_sort_key(item: dict[str, Any]) -> tuple[float, int, int]:
    """참고 공고 정렬: 관련도(rerank_score) → 마감일(늦을수록 우선) → 회사 업력(길수록 우선)."""
    score = float(item.get("rerank_score") or 0)
    meta = item.get("metadata") or {}
    # 마감일: YYYY-MM-DD 등에서 숫자만 추출해 20260219 형태, 없으면 0 (앞에 오지 않게)
    deadline_s = str(meta.get("deadline") or "")
    digits = re.sub(r"\D", "", deadline_s)[:8]
    deadline_ord = int(digits) if len(digits) >= 8 else 0
    # 회사 업력: "18년차" 등에서 숫자 추출
    cy_s = str(meta.get("company_years_num") or "")
    cy_match = re.search(r"\d+", cy_s)
    company_years = int(cy_match.group()) if cy_match else 0
    return (score, deadline_ord, company_years)


def _build_context(items: list[dict[str, Any]], max_chars: int = 6000) -> str:
    """검색된 청크들을 하나의 context 문자열로 합침 (호출측에서 공고 중복 제거된 리스트 전달)."""
    parts = []
    total = 0
    for i, item in enumerate(items, 1):
        text = (item.get("text") or "").strip()
        meta = item.get("metadata") or {}
        company = meta.get("company") or ""
        job_role = meta.get("job_role") or ""
        line = f"[{i}] (회사: {company}, 직무: {job_role})\n{text}"
        if total + len(line) + 2 > max_chars:
            break
        parts.append(line)
        total += len(line) + 2
    return "\n\n".join(parts) if parts else ""


def generate(
    query: str,
    *,
    company: Optional[str] = None,
    job_role: Optional[str] = None,
    career_type: Optional[str] = None,
    company_years_num: Optional[str] = None,
    retrieve_limit: int = 20,
    max_distance: Optional[float] = None,
    use_rerank: bool = True,
    rerank_top_k: int = 5,
    model: Optional[str] = None,
) -> dict[str, Any]:
    """
    질의 → Retriever(옵션 Rerank) → context 구성 → LLM 답변 생성.

    Args:
        query: 사용자 질문.
        company, job_role, career_type, company_years_num: Retriever 메타 필터.
        retrieve_limit: Retriever 상위 건수.
        max_distance: Retriever에서 이 값보다 큰 distance 제외 (None이면 미적용).
        use_rerank: True면 Rerank 적용 후 상위 rerank_top_k만 context에 사용.
        rerank_top_k: Rerank 후 context에 넣을 건수 (기본 5).
        model: OpenAI 채팅 모델 (미지정 시 gpt-4o-mini).

    Returns:
        {"answer": str, "sources": list[dict], "context_length": int}
    """
    from RAG.Retriever import retrieve
    from RAG.Rerank import rerank

    items = retrieve(
        query,
        company=company,
        job_role=job_role,
        career_type=career_type,
        company_years_num=company_years_num,
        limit=retrieve_limit,
        max_distance=max_distance,
    )
    # 회사명 없는 항목을 대체할 수 있도록 후보를 넉넉히 가져옴
    rerank_k = max(rerank_top_k * 2, 10) if use_rerank else retrieve_limit
    if use_rerank and items:
        items = rerank(query, items, top_k=rerank_k)

    # 공고당 1건만 사용 (중복 source 제거)
    seen_keys: set[tuple[Any, ...]] = set()
    deduped_items: list[dict[str, Any]] = []
    for item in items:
        key = _job_key(item)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped_items.append(item)

    # 회사명이 없는 항목 제외, 회사명 있는 다른 공고로 대체
    def _has_company(it: dict[str, Any]) -> bool:
        c = (it.get("metadata") or {}).get("company")
        return bool(c and str(c).strip())
    deduped_items = [it for it in deduped_items if _has_company(it)]

    # 내용이 동일한 항목 제거 (같은 주요업무가 다른 직무로 중복 노출되는 것 방지)
    seen_texts: set[str] = set()
    unique_items: list[dict[str, Any]] = []
    for it in deduped_items:
        text_key = (it.get("text") or "").strip()
        if not text_key or text_key in seen_texts:
            continue
        seen_texts.add(text_key)
        unique_items.append(it)
    # 중요한/많이 볼 법한 순: 관련도 → 마감일(늦을수록) → 회사 업력(길수록)
    unique_items.sort(key=_importance_sort_key, reverse=True)
    deduped_items = unique_items[: max(rerank_top_k, 1)]

    context = _build_context(deduped_items)
    if not context.strip():
        return {
            "answer": "검색된 채용 정보가 없어 답변을 생성할 수 없습니다.",
            "sources": [],
            "context_length": 0,
        }

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {
            "answer": "OPENAI_API_KEY가 설정되지 않았습니다.",
            "sources": deduped_items,
            "context_length": len(context),
        }

    from openai import OpenAI
    from Fine_tuning.Fine_tuning import get_finetune_system_prompt

    client = OpenAI(api_key=api_key)
    model_name = model or os.environ.get("RAG_CHAT_MODEL") or DEFAULT_MODEL

    system = (
        get_finetune_system_prompt()
        + "\n\n답변은 반드시 아래 채용 공고 문장에 나온 내용만 인용하고, 공고에 없는 표현으로 일반화하거나 요약하지 마세요."
        + "\n\n질문과 관련된 정보는 context에 있으면 빠짐없이 모두 답변에 포함하라. 반면 질문과 직접 관련 없거나 관련성이 낮은 내용은 절대 포함하지 마라."
        + "\n\n답변에는 각 공고의 주요업무만 요약·나열하고, 자격요건·우대사항 등은 답변에 포함하지 마세요. 질문과 관련된 공고는 적어도 3개 이상 포함하여 나열하세요."
    )

    user = f"""다음 채용 공고 내용을 참고해서 질문에 답해주세요. 질문과 관련된 내용은 모두 포함하고, 관련 없는 내용은 절대 넣지 마세요. 답변에는 각 공고별로 주요업무만 간단히 정리하고, 질문과 관련된 공고는 빠짐없이 나열하세요.

--- 채용 공고 ---
{context}
--- 끝 ---

질문: {query}"""

    resp = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=1024,
    )
    answer = (resp.choices[0].message.content or "").strip()

    return {
        "answer": answer,
        "sources": deduped_items,
        "context_length": len(context),
    }
