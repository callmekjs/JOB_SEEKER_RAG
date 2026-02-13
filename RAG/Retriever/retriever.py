"""
Retriever: 벡터 검색 + 메타데이터 필터 결합.
팀장님 요구: 회사명·직무 카테고리·경력 여부·회사 규모로 필터하며 벡터 검색 결과와 결합.
"""

import json
import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

# 프로젝트 루트 .env 로드 (RAG/Retriever 기준 상위 두 단계)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# embedding 모델 차원 (service.embedding과 동일)
OPENAI_EMBED_DIM = 1536
PG_TABLE = "job_embeddings"


def _get_embed_fn():
    """OpenAI text-embedding-3-small 임베딩 함수. OPENAI_API_KEY 필요."""
    from service.embedding.embedding import get_openai_embed_fn

    fn = get_openai_embed_fn()
    if fn is None:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다. .env를 확인하세요.")
    return fn


def _get_pg_connection():
    """PostgreSQL 연결 (DATABASE_URL 또는 PGHOST 등)."""
    import psycopg2

    url = os.environ.get("DATABASE_URL")
    if url:
        return psycopg2.connect(url)
    host = os.environ.get("PGHOST", "localhost")
    port = os.environ.get("PGPORT", "5432")
    dbname = os.environ.get("PGDATABASE", "postgres")
    user = os.environ.get("PGUSER", "postgres")
    password = os.environ.get("PGPASSWORD", "")
    return psycopg2.connect(
        host=host, port=port, dbname=dbname, user=user, password=password
    )


def retrieve(
    query: str,
    *,
    company: Optional[str] = None,
    job_role: Optional[str] = None,
    career_type: Optional[str] = None,
    company_years_num: Optional[str] = None,
    limit: int = 10,
    max_distance: Optional[float] = None,
    embed_fn=None,
) -> list[dict[str, Any]]:
    """
    질의문으로 벡터 유사도 검색 + 메타데이터 필터 결합.
    팀장님 요구: 회사명·직무 카테고리·경력 여부·회사 규모 필터 지원.

    Args:
        query: 검색 질의문.
        company: 회사명 (정확 일치 필터).
        job_role: 직무/직무 카테고리 필터.
        career_type: 경력 여부 (예: 신입, 경력, 무관).
        company_years_num: 회사 규모(업력) 필터 (예: "5년차").
        limit: 반환할 최대 건수.
        max_distance: 이 값보다 큰 distance는 제외 (precision 향상, None이면 미적용).
        embed_fn: 임베딩 함수 (미지정 시 OpenAI 사용).

    Returns:
        [{"id", "text", "metadata", "distance"}, ...]
    """
    embed_fn = embed_fn or _get_embed_fn()
    query_vec = embed_fn(query.strip() or "")
    if len(query_vec) != OPENAI_EMBED_DIM:
        raise ValueError(f"임베딩 차원이 {OPENAI_EMBED_DIM}이어야 합니다.")

    # 메타데이터 필터 조건: 지정된 것만 WHERE에 추가
    filters = []
    params: list[Any] = [query_vec]

    if company is not None:
        filters.append("metadata->>'company' = %s")
        params.append(company)
    if job_role is not None:
        filters.append("metadata->>'job_role' = %s")
        params.append(job_role)
    if career_type is not None:
        filters.append("metadata->>'career_type' = %s")
        params.append(career_type)
    if company_years_num is not None:
        filters.append("metadata->>'company_years_num' = %s")
        params.append(company_years_num)

    where_sql = " AND ".join(filters) if filters else "TRUE"

    # 같은 공고 여러 청크가 나올 수 있으므로, 공고당 1건만 쓰려면 후보를 더 가져옴
    fetch_limit = max(limit * 15, 100)

    sql = f"""
        SELECT id, text, metadata,
               embedding <=> %s::vector AS distance
        FROM {PG_TABLE}
        WHERE {where_sql}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    # %s 순서: query_vec(SELECT), 필터값들..., query_vec(ORDER BY), fetch_limit
    params_insert = [query_vec] + params[1:] + [query_vec, fetch_limit]

    try:
        from pgvector.psycopg2 import register_vector
    except ImportError:
        raise RuntimeError("pgvector 패키지가 필요합니다. pip install pgvector")

    conn = _get_pg_connection()
    try:
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute(sql, params_insert)
            rows = cur.fetchall()
    finally:
        conn.close()

    results = [
        {
            "id": r[0],
            "text": r[1],
            "metadata": r[2] if isinstance(r[2], dict) else (json.loads(r[2]) if r[2] else {}),
            "distance": float(r[3]),
        }
        for r in rows
    ]

    # 같은 공고(동일 source_row_id + company + job_role)는 distance가 가장 좋은 1건만 유지
    deduped = _dedupe_by_job(results)
    if max_distance is not None:
        deduped = [x for x in deduped if x["distance"] <= max_distance]
    return sorted(deduped, key=lambda x: x["distance"])[:limit]


def _job_key(item: dict[str, Any]) -> tuple[Any, ...]:
    """같은 공고를 구분하는 키. source_row_id가 없으면 (company, job_role)로 대체."""
    meta = item.get("metadata") or {}
    sid = meta.get("source_row_id")
    company = meta.get("company")
    job_role = meta.get("job_role")
    if sid is not None:
        return (sid, company, job_role)
    return (company, job_role)


def _dedupe_by_job(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """공고당 distance가 가장 작은 1건만 남김."""
    by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    for item in items:
        k = _job_key(item)
        if k not in by_key or item["distance"] < by_key[k]["distance"]:
            by_key[k] = item
    return list(by_key.values())
