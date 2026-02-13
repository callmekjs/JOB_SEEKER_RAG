"""
채용공고 청킹: 정규화 CSV → 의미 단위(그룹) chunk.
직무/경력, 기술스택, 주요업무, 자격요건, 조건 5개 그룹으로 세분화하여 저장.
결과물: service/chunking/chunked/ 에 JSONL 저장.
"""

import json
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd


CHUNKED_DIR = Path(__file__).resolve().parent / "chunked"

# 의미 단위 그룹: 그룹명 → 해당 레이블 목록 (세분화)
CHUNK_GROUPS = {
    "직무/경력": ["회사", "직무", "경력", "학력", "업력"],
    "기술스택": ["기술스택"],
    "주요업무": ["주요업무"],
    "자격요건": ["자격요건"],
    "조건": ["근무지역", "우대사항", "복지 및 혜택", "채용절차", "마감일"],
}

# 레이블 → 어느 그룹에 속하는지
LABEL_TO_GROUP: dict[str, str] = {}
for group_name, labels in CHUNK_GROUPS.items():
    for label in labels:
        LABEL_TO_GROUP[label] = group_name

SECTION_LABELS = list(LABEL_TO_GROUP.keys())  # 파싱 시 사용
MIN_CHUNK_LENGTH = 10  # 이 길이 미만 섹션은 제외

# chunk 메타데이터로 붙일 컬럼
METADATA_COLUMNS = [
    "job_role",
    "company",
    "location_sido",
    "location_gu",
    "career_type",
    "education_level",
    "deadline",
    "company_years_num",
]


def load_csv(path: Union[str, Path], encoding: str = "utf-8-sig") -> pd.DataFrame:
    """정규화된 CSV 로드."""
    return pd.read_csv(path, encoding=encoding)


def split_document_into_groups(document: str) -> list[tuple[str, str]]:
    """
    document를 파싱해 '의미 단위 그룹'별로 묶음.
    Returns: [(그룹명, 합친텍스트), ...] (최대 5개: 직무/경력, 기술스택, 주요업무, 자격요건, 조건)
    """
    if not document or not document.strip():
        return []
    blocks = [b.strip() for b in document.split("\n\n") if b.strip()]
    group_order = list(CHUNK_GROUPS.keys())
    collected: dict[str, list[str]] = {g: [] for g in group_order}
    for block in blocks:
        for label in SECTION_LABELS:
            prefix = label + ":"
            if block.startswith(prefix) and len(block) >= MIN_CHUNK_LENGTH:
                group_name = LABEL_TO_GROUP[label]
                collected[group_name].append(block)
                break
    result: list[tuple[str, str]] = []
    for group_name in group_order:
        if collected[group_name]:
            result.append((group_name, "\n\n".join(collected[group_name])))
    return result


def build_chunks(df: pd.DataFrame) -> list[dict[str, Any]]:
    """DataFrame을 의미 단위(그룹) chunk 리스트로 변환. document 컬럼 필수. 메타데이터 포함."""
    if "document" not in df.columns:
        raise ValueError("CSV에 'document' 컬럼이 없습니다.")
    chunks = []
    for idx, row in df.iterrows():
        text = row.get("document")
        if pd.isna(text) or not str(text).strip():
            continue
        document = str(text).strip()
        group_list = split_document_into_groups(document)
        if not group_list:
            continue
        base_meta: dict[str, Any] = {"source_row_id": int(idx)}
        for col in METADATA_COLUMNS:
            if col in row.index:
                val = row[col]
                if pd.isna(val):
                    base_meta[col] = None
                else:
                    base_meta[col] = str(val).strip() if isinstance(val, str) else val
        for group_name, group_text in group_list:
            meta = {**base_meta, "chunk_group": group_name}
            chunks.append({"text": group_text, "metadata": meta})
    return chunks


def save_chunked_jsonl(chunks: list[dict[str, Any]], path: Union[str, Path]) -> Path:
    """chunk 리스트를 JSONL 파일로 저장."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for item in chunks:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    return path


def run_chunking(
    input_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    encoding: str = "utf-8-sig",
) -> list[dict[str, Any]]:
    """
    정규화 CSV를 읽어 의미 단위(섹션) 청킹 후 저장.
    결과물: service/chunking/chunked/chunked_1.jsonl, chunked_2.jsonl, ... (번호로 구분)
    """
    input_path = Path(input_path)
    df = load_csv(input_path, encoding=encoding)
    chunks = build_chunks(df)
    if output_path is None:
        CHUNKED_DIR.mkdir(parents=True, exist_ok=True)
        # chunked_1.jsonl, chunked_2.jsonl, ... 로 구분하기 쉽게 저장
        pattern = "chunked_*.jsonl"
        existing = list(CHUNKED_DIR.glob(pattern))
        nums = []
        for p in existing:
            # chunked_1 → 1, chunked_2 → 2
            suffix = p.stem.replace("chunked_", "")
            if suffix.isdigit():
                nums.append(int(suffix))
        n = max(nums) + 1 if nums else 1
        output_path = CHUNKED_DIR / f"chunked_{n}.jsonl"
    else:
        output_path = Path(output_path)
    save_chunked_jsonl(chunks, output_path)
    print(f"Chunking 완료: {len(chunks)}개 chunk → {output_path}")
    _print_grouping_report()
    return chunks


def _print_grouping_report() -> None:
    """의미 단위 묶음 방식을 출력."""
    print("\n[의미 단위 청킹 묶음]")
    for group_name, labels in CHUNK_GROUPS.items():
        print(f"  • {group_name}: {', '.join(labels)}")
