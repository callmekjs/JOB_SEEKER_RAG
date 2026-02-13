"""
JD(채용공고) Normalizing.
- 형식 통일 + 구조 정규화 + 분석용 컬럼 추가.
- 의미 삭제·추론적 재작성 금지.
"""

import re
from pathlib import Path
from typing import Optional, Union
import pandas as pd


NORMALIZED_DIR = Path(__file__).resolve().parent / "normalized"

DOCUMENT_FIELD_LABELS = [
    ("company", "회사"),
    ("job_role", "직무"),
    ("career", "경력"),
    ("education", "학력"),
    ("company_years", "업력"),
    ("location", "근무지역"),
    ("deadline", "마감일"),
    ("tech_stack", "기술스택"),
    ("main_tasks", "주요업무"),
    ("qualifications", "자격요건"),
    ("preferred", "우대사항"),
    ("benefits", "복지 및 혜택"),
    ("recruitment_process", "채용절차"),
]


# ==============================
# 기본 정리
# ==============================

def _normalize_value(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val).strip()


def _clean_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip()) if s else ""


# ==============================
# 오타·표기 정규화
# ==============================

TYPO_REPLACEMENTS = [
    ("Kotiln", "Kotlin"),
    ("했을 대", "했을 때"),
    ("RestFul", "RESTful"),
    ("맥북프로과", "맥북프로와"),
    ("4대보험외", "4대보험 외"),
    ("Spring x javascript", "Spring 및 JavaScript"),
    ("Spring x JavaScript", "Spring 및 JavaScript"),
]


def _apply_typo_normalization(s: str) -> str:
    """오타 및 표기 통일 적용. 의미 변경·추론 없음."""
    if not s:
        return s
    t = s
    for old, new in TYPO_REPLACEMENTS:
        t = t.replace(old, new)
    # S W (공백) → S/W (앞뒤 문맥 없이 등장하는 경우)
    t = re.sub(r"(?<![./])\bS\s+W\b(?![/])", "S/W", t)
    return t


# ==============================
# career 정규화
# ==============================

def _parse_career_years(s: str) -> tuple:
    if not s:
        return (None, None)
    t = _clean_spaces(s)

    if "신입" in t and "경력" not in t:
        return (0, 0)

    m = re.search(r"경력\s*(\d+)\s*~\s*(\d+)", t)
    if m:
        return (int(m.group(1)), int(m.group(2)))

    m = re.search(r"(\d+)\s*년\s*이상", t)
    if m:
        return (int(m.group(1)), None)

    return (None, None)


def _career_type(s: str) -> str:
    if not s:
        return ""
    if "신입" in s:
        return "신입"
    if "경력" in s:
        return "경력"
    return "무관"


# ==============================
# company_years 숫자화
# ==============================

def _parse_company_years_num(s: str):
    if not s:
        return None
    m = re.search(r"(\d+)\s*년차", s)
    return int(m.group(1)) if m else None


# ==============================
# location 분리
# ==============================

def _parse_location_parts(s: str) -> tuple:
    if not s:
        return ("", "", "")
    t = _clean_spaces(s)
    parts = t.split(None, 2)

    sido = parts[0] if len(parts) > 0 else ""
    gu = ""
    detail = ""

    if len(parts) > 1:
        if parts[1].endswith(("구", "시", "군")):
            gu = parts[1]
            detail = parts[2] if len(parts) > 2 else ""
        else:
            detail = parts[1] if len(parts) > 1 else ""

    return (sido, gu, detail)


# ==============================
# tech_stack 정규화
# ==============================

TECH_NORMALIZE_MAP = {
    "ai": "인공지능",
    "인공지능": "인공지능",
    "spring boot": "Spring Boot",
    "spring": "Spring",
    "spring framework": "Spring Framework",
    "springframework": "Spring Framework",
    "nodejs": "Node.js",
    "node js": "Node.js",
    "node.js": "Node.js",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "react": "React",
    "react.js": "React",
    "reactjs": "React",
    "vue": "Vue",
    "vue.js": "Vue.js",
    "vuejs": "Vue.js",
    "angular": "Angular",
    "html5": "HTML5",
    "html": "HTML",
    "mysql": "MySQL",
    "mssql": "MSSQL",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "oracle": "Oracle",
    "rest api": "REST API",
    "restapi": "REST API",
    "java": "Java",
    "kotlin": "Kotlin",
    "kotiln": "Kotlin",
    "python": "Python",
    "go": "Go",
    "golang": "Go",
    "c#": "C#",
    ".net": ".NET",
    "aws": "AWS",
    "jsp": "JSP",
    "sql": "SQL",
    "gradle": "Gradle",
    "maven": "Maven",
    "junit": "JUnit",
    "querydsl": "QueryDSL",
    "git": "Git",
    "github": "GitHub",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "redis": "Redis",
    "mongodb": "MongoDB",
    "elasticsearch": "Elasticsearch",
    "graphql": "GraphQL",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "sw": "S/W",
    "s/w": "S/W",
    "s w": "S/W",
    "amazon aurora": "Amazon Aurora",
    "erp": "ERP",
}


def _normalize_tech_stack(s: str) -> str:
    if not s:
        return ""
    items = [x.strip().lower() for x in s.split(",") if x.strip()]
    normalized = []
    for item in items:
        std = TECH_NORMALIZE_MAP.get(item, item)
        normalized.append(std)
    normalized = list(dict.fromkeys(normalized))  # 중복 제거
    return ", ".join(normalized)


# ==============================
# job_role 구분자 통일
# ==============================

def _normalize_job_role(s: str) -> str:
    """job_role 내 언더스코어(_)를 공백으로 통일."""
    if not s:
        return ""
    return _clean_spaces(s.replace("_", " "))


# ==============================
# education 표준화
# ==============================

# 원문 표현 → 표준 문구 (education 컬럼용)
def _normalize_education_text(s: str) -> str:
    """학력 원문을 표준 문구로 통일. 고졸/초대졸/대졸/무관."""
    if not s:
        return ""
    t = s.strip()
    if "무관" in t or "제한없" in t:
        return "무관"
    if "고등학교" in t:
        return "고졸 이상"
    if "초대졸" in t or "전문대" in t or "전문학사" in t:
        return "초대졸 이상"
    if "대학" in t or "학사" in t or "4년제" in t or "대졸" in t:
        return "대졸 이상"
    return "무관"


def _normalize_education_level(s: str) -> str:
    """education_level 컬럼용: 고졸/초대졸/대졸/무관."""
    if not s:
        return ""
    if "고등학교" in s or s.startswith("고졸"):
        return "고졸"
    if "초대졸" in s or "전문대" in s or "전문학사" in s:
        return "초대졸"
    if "대학" in s or "대졸" in s or "학사" in s or "4년제" in s:
        return "대졸"
    return "무관"


# ==============================
# 메인 정규화 함수
# ==============================

def normalize_jd_data(df: pd.DataFrame, add_document_column: bool = True) -> pd.DataFrame:
    out = df.copy()

    # 기본 공백 정리
    for col in out.columns:
        if out[col].dtype == object:
            out[col] = out[col].fillna("").astype(str).map(_normalize_value)
            out[col] = out[col].map(_clean_spaces)
            out[col] = out[col].map(_apply_typo_normalization)

    # career 수치화
    if "career" in out.columns:
        parsed = out["career"].map(_parse_career_years)
        out["career_min_years"] = parsed.map(lambda x: x[0])
        out["career_max_years"] = parsed.map(lambda x: x[1])
        out["career_type"] = out["career"].map(_career_type)

    # company_years 숫자화
    if "company_years" in out.columns:
        out["company_years_num"] = out["company_years"].map(_parse_company_years_num)

    # location 분리
    if "location" in out.columns:
        loc_parsed = out["location"].map(_parse_location_parts)
        out["location_sido"] = loc_parsed.map(lambda x: x[0])
        out["location_gu"] = loc_parsed.map(lambda x: x[1])
        out["location_detail"] = loc_parsed.map(lambda x: x[2])

    # tech_stack 정규화
    if "tech_stack" in out.columns:
        out["tech_stack"] = out["tech_stack"].map(_normalize_tech_stack)

    # job_role 구분자 통일 (_ → 공백)
    if "job_role" in out.columns:
        out["job_role"] = out["job_role"].map(_normalize_job_role)

    # education 원문 통일 + 레벨 컬럼 추가
    if "education" in out.columns:
        out["education"] = out["education"].map(_normalize_education_text)
        out["education_level"] = out["education"].map(_normalize_education_level)

    # RAG document 생성
    if add_document_column:
        def build_document(row):
            parts = []
            for field_key, label in DOCUMENT_FIELD_LABELS:
                if field_key not in row:
                    continue
                val = _normalize_value(row[field_key])
                if val:
                    parts.append(f"{label}: {val}")
            return "\n\n".join(parts)

        out["document"] = out.apply(build_document, axis=1)

    return out


def load_csv(path: Union[str, Path], encoding: str = "utf-8-sig") -> pd.DataFrame:
    """CSV 로드 (cleansed 또는 원본 점핏 CSV)."""
    return pd.read_csv(path, encoding=encoding)


def save_normalized_csv(df: pd.DataFrame, path: Union[str, Path], encoding: str = "utf-8-sig") -> Path:
    """정규화된 DataFrame을 CSV로 저장."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding=encoding)
    return path


def run_normalizing(
    input_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    encoding: str = "utf-8-sig",
    add_document_column: bool = True,
) -> pd.DataFrame:
    """
    CSV 경로를 받아 정규화 후 저장하고 DataFrame 반환.
    output_path 미지정 시 service/normalizing/normalized/ 안에 normalized_{입력파일명}_1, _2, ... 순으로 저장.
    """
    input_path = Path(input_path)
    if output_path is None:
        NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
        base = f"normalized_{input_path.stem}"
        pattern = f"{base}_*.csv"
        existing = list(NORMALIZED_DIR.glob(pattern))
        nums = []
        for p in existing:
            suffix = p.stem[len(base):].lstrip("_")
            if suffix.isdigit():
                nums.append(int(suffix))
        n = max(nums) + 1 if nums else 1
        output_path = NORMALIZED_DIR / f"{base}_{n}.csv"
    else:
        output_path = Path(output_path)
    df = load_csv(input_path, encoding=encoding)
    normalized = normalize_jd_data(df, add_document_column=add_document_column)
    save_normalized_csv(normalized, output_path, encoding=encoding)
    print(f"Normalizing 완료: {len(normalized)}건 → {output_path}")
    return normalized
