"""
채용공고 청크 임베딩: chunked JSONL → OpenAI text-embedding-3-small → embedded/ + PostgreSQL(pgvector).
결과물: service/embedding/embedded/embedded_1.jsonl, ... 및 DB 테이블 job_embeddings.
"""

import json
import os
from pathlib import Path
from typing import Any, Callable, Optional, Union

from dotenv import load_dotenv

# 프로젝트 루트의 .env 로드
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

EMBEDDED_DIR = Path(__file__).resolve().parent / "embedded"

# OpenAI text-embedding-3-small
OPENAI_EMBED_MODEL = "text-embedding-3-small"
OPENAI_EMBED_DIM = 1536

# PostgreSQL 테이블명
PG_TABLE = "job_embeddings"


def get_openai_embed_fn() -> Optional[Callable[[str], list[float]]]:
    """OpenAI text-embedding-3-small 임베딩 함수. OPENAI_API_KEY 필요."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    def embed(text: str) -> list[float]:
        if not text or not text.strip():
            return [0.0] * OPENAI_EMBED_DIM
        resp = client.embeddings.create(
            model=OPENAI_EMBED_MODEL,
            input=text.strip()[:8000],  # 대략 토큰 제한 내
        )
        return list(resp.data[0].embedding)

    return embed


def _dummy_embed(text: str) -> list[float]:
    """API 키 없을 때 더미 벡터 (테스트용)."""
    return [0.0] * OPENAI_EMBED_DIM


def load_chunked_jsonl(path: Union[str, Path]) -> list[dict[str, Any]]:
    """청킹된 JSONL 로드."""
    path = Path(path)
    chunks = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            chunks.append(json.loads(line))
    return chunks


def save_embedded_jsonl(
    items: list[dict[str, Any]], path: Union[str, Path]
) -> Path:
    """임베딩된 항목들을 JSONL로 저장."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    return path


def _get_pg_connection():
    """DATABASE_URL 또는 PGHOST 등으로 PostgreSQL 연결."""
    url = os.environ.get("DATABASE_URL")
    if url:
        import psycopg2
        return psycopg2.connect(url)
    host = os.environ.get("PGHOST", "localhost")
    port = os.environ.get("PGPORT", "5432")
    dbname = os.environ.get("PGDATABASE", "postgres")
    user = os.environ.get("PGUSER", "postgres")
    password = os.environ.get("PGPASSWORD", "")
    import psycopg2
    return psycopg2.connect(
        host=host, port=port, dbname=dbname, user=user, password=password
    )


def ensure_pgvector_table(conn) -> None:
    """pgvector 확장 및 job_embeddings 테이블 생성."""
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS job_embeddings (
                id SERIAL PRIMARY KEY,
                text TEXT NOT NULL,
                metadata JSONB,
                embedding vector(%s),
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """ % OPENAI_EMBED_DIM)
    conn.commit()


def save_to_postgres(
    items: list[dict[str, Any]],
) -> None:
    """임베딩 결과를 PostgreSQL job_embeddings 테이블에 저장."""
    try:
        from pgvector.psycopg2 import register_vector
    except ImportError:
        print("pgvector 패키지 없음. pip install pgvector 후 재시도.")
        return
    try:
        conn = _get_pg_connection()
    except Exception as e:
        print(f"PostgreSQL 연결 실패: {e}")
        return
    try:
        register_vector(conn)
        ensure_pgvector_table(conn)
        with conn.cursor() as cur:
            for item in items:
                text = item.get("text", "")
                meta = json.dumps(item.get("metadata", {}), ensure_ascii=False)
                vec = item.get("embedding", [])
                cur.execute(
                    """
                    INSERT INTO job_embeddings (text, metadata, embedding)
                    VALUES (%s, %s, %s);
                    """,
                    (text, meta, vec),
                )
        conn.commit()
        print(f"PostgreSQL 저장 완료: {len(items)}건 → 테이블 {PG_TABLE}")
    except Exception as e:
        print(f"PostgreSQL 저장 실패: {e}")
    finally:
        conn.close()


def run_embedding(
    input_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    embed_fn: Optional[Callable[[str], list[float]]] = None,
    save_jsonl: bool = True,
    save_pg: bool = True,
) -> list[dict[str, Any]]:
    """
    청킹 JSONL을 읽어 text 필드 임베딩 후 저장.
    - embed_fn 미지정 시 OpenAI text-embedding-3-small 사용 (OPENAI_API_KEY 필요).
    - save_jsonl=True 이면 embedded/embedded_1.jsonl, ... 저장.
    - save_pg=True 이고 DATABASE_URL 또는 PGHOST 등 설정 시 PostgreSQL job_embeddings 저장.
    """
    input_path = Path(input_path)
    chunks = load_chunked_jsonl(input_path)
    if not chunks:
        print("Chunk가 없습니다.")
        return []

    embed_fn = embed_fn or get_openai_embed_fn() or _dummy_embed
    if embed_fn is _dummy_embed and not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY 미설정 → 더미 벡터로 저장합니다.")

    results = []
    for item in chunks:
        text = item.get("text", "")
        vec = embed_fn(text)
        results.append({
            "text": text,
            "metadata": item.get("metadata", {}),
            "embedding": vec,
        })

    if save_jsonl:
        if output_path is None:
            EMBEDDED_DIR.mkdir(parents=True, exist_ok=True)
            pattern = "embedded_*.jsonl"
            existing = list(EMBEDDED_DIR.glob(pattern))
            nums = []
            for p in existing:
                suffix = p.stem.replace("embedded_", "")
                if suffix.isdigit():
                    nums.append(int(suffix))
            n = max(nums) + 1 if nums else 1
            output_path = EMBEDDED_DIR / f"embedded_{n}.jsonl"
        else:
            output_path = Path(output_path)
        save_embedded_jsonl(results, output_path)
        print(f"Embedding 완료: {len(results)}건 → {output_path}")

    if save_pg and (os.environ.get("DATABASE_URL") or os.environ.get("PGHOST")):
        save_to_postgres(results)
    elif save_pg:
        print("DATABASE_URL 또는 PGHOST 미설정 → PostgreSQL 저장 생략.")

    return results
