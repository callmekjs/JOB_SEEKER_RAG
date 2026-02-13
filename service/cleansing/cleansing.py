"""
JD(채용공고) Cleansing.
- 정보 삭제·추론적 재작성 금지. 의미 보존 전제로 노이즈만 제거.
- HTML/이스케이프 제거, 공백·줄바꿈 정리, null 규칙 처리.
- job_role: '채용' 제거, location: '지도보기', '·', '주소복사' 등 제거.
- 불릿 제거, 줄바꿈 정규화, tech_stack 정규화.
- 대괄호 제목 줄 제거, 소괄호 () 및 내용 제거, 이모지·아이콘 문자 제거, 텍스트 필드 list 분리.
- main_tasks: URL·URL 소개 문구·제목·소개 문단 제거.
- 전체 텍스트: URL 제거(link 제외), 특수문자 * : , - / 제거(tech_stack 제외), 이모지·그림 문자 제거.
"""
import re
from pathlib import Path
from typing import Optional, Union

import pandas as pd


# 정제 시 빈 값으로 둘 문자열 (필요 시 "(없음)" 등으로 변경 가능)
EMPTY_PLACEHOLDER = ""

# location에서 제거할 문구 (크롤러와 동일 규칙)
LOCATION_REMOVE_STRINGS = ("지도보기", "·", "주소복사", "주소 복사")

# job_role에서 제거할 문구
JOB_ROLE_REMOVE_STRINGS = ("채용",)

# 줄 시작 불릿·번호 제거: •, ㆍ, ·, ○, ●, ▶, ■, ※, "- ", o (알파벳), 1. 2) ①~⑳ 등 (반복 제거)
_RE_LEADING_BULLET = re.compile(
    r"^[\s\u00a0\u3000]*(?:"
    r"[•ㆍ·\u25CB\u25CF\u25CE\u25EF\u25B6\u25A0\u25A1\u25AA\u25AB\u203B][\s\u00a0\u3000]*|"
    r"[\-－][\s\u00a0\u3000]+|"
    r"[\u2460-\u2473\u2488-\u249b][.\s)]*|"
    r"\d{1,2}[.)]\s*|"
    r"o[\s\u00a0\u3000]+"
    r")*",
    re.UNICODE,
)

# 줄 전체가 대괄호/꺾쇠 제목인 경우 제거: [제목], <제목>, ＜제목＞
_RE_BRACKET_TITLE_LINE = re.compile(
    r"^\s*[\[<＜].*[\]>＞]\s*$",
    re.UNICODE,
)

# 줄 안의 대괄호 제거 후 내용만 유지: [x] → x, 【x】 → x, ［x］ → x
_RE_INLINE_SQUARE = re.compile(r"\[([^\[\]]*)\]", re.UNICODE)       # [신입] → 신입
_RE_INLINE_LENTICULAR = re.compile(r"【([^【】]*)】", re.UNICODE)   # 【제목】 → 제목
_RE_INLINE_FULLWIDTH = re.compile(r"［([^［］]*)］", re.UNICODE)     # ［x］ → x

# 괄호와 그 안 내용 통째로 제거: (x) → '', （x） → ''
_RE_PAREN_HALF = re.compile(r"\([^()]*\)", re.UNICODE)             # (핵심 책임 중심) 제거
_RE_PAREN_FULL = re.compile(r"（[^（）]*）", re.UNICODE)             # （전각） 제거

# URL 제거 (link 컬럼 제외한 텍스트 필드)
_RE_URL = re.compile(r"https?://[^\s\]\)\>\]]+", re.UNICODE)

# 특수문자 제거 (공백으로 치환): * : , - / · • ○ ● ▶ ■ □ ▪ ▫ % ? = " ※ § ¶ 〓 등
# tech_stack은 구분자 유지 위해 별도 적용 제외. deadline은 - 유지(preserve_hyphen).
_RE_SPECIAL_CHARS = re.compile(
    r"[*:,/\-\u00B7\u2022\u25CB\u25CF\u25CE\u25EF\u25B6\u25A0\u25A1\u25AA\u25AB%?=\"\u203B\u00A7\u00B6\u3013]+",
    re.UNICODE,
)
# - 제외 (deadline 등 날짜 형식 유지용)
_RE_SPECIAL_CHARS_NO_HYPHEN = re.compile(
    r"[*:,/\u00B7\u2022\u25CB\u25CF\u25CE\u25EF\u25B6\u25A0\u25A1\u25AA\u25AB%?=\"\u203B\u00A7\u00B6\u3013]+",
    re.UNICODE,
)

# main_tasks에서 제거할 소개/제목용 문구 (해당 줄 전체 제거)
MAIN_TASKS_INTRO_PHRASES = (
    "바로가기",
    "오시면 이런 업무",
    "하게 되실 거예요",
    "다음과 같은 업무를 수행",
    "이런 업무를 하게 되실",
    "개발의 마지막 관문",
    "비즈니스 임팩트를 최우선",
    "유기적 소통으로",
    "실행력을 중시",
    "복잡한 업무 프로세스",
    "고객 중심의 제품",
    "패스오더 유저와",
    "점주님을 연결",
)


def _strip_inline_brackets(line: str) -> str:
    """줄 안의 대괄호만 제거하고 괄호 안 내용은 유지. [신입] → 신입, 【팀명】 → 팀명."""
    line = _RE_INLINE_SQUARE.sub(r"\1", line)
    line = _RE_INLINE_LENTICULAR.sub(r"\1", line)
    line = _RE_INLINE_FULLWIDTH.sub(r"\1", line)
    return line


def _strip_parens(line: str) -> str:
    """줄 안의 소괄호 ( ) 및 전각 （ ） 와 그 안 내용을 통째로 제거."""
    line = _RE_PAREN_HALF.sub("", line)
    line = _RE_PAREN_FULL.sub("", line)
    return re.sub(r"[ \t]+", " ", line).strip()  # 제거 후 남은 공백 정리


def _strip_special_chars(s: str) -> str:
    """특수문자 * : , - / 등을 공백으로 치환."""
    s = _RE_SPECIAL_CHARS.sub(" ", s)
    return re.sub(r"[ \t]+", " ", s).strip()


def _strip_special_chars_preserve_hyphen(s: str) -> str:
    """특수문자 치환하되 - 는 유지 (deadline 등 날짜용)."""
    s = _RE_SPECIAL_CHARS_NO_HYPHEN.sub(" ", s)
    return re.sub(r"[ \t]+", " ", s).strip()


def _strip_emoji_and_symbols(s: str) -> str:
    """이모지·아이콘(별·클립보드·■●○▶ 등) 장식 문자 제거."""
    result = []
    for c in s:
        cp = ord(c)
        if (
            (0x25A0 <= cp <= 0x25FF)   # Geometric Shapes (■ □ ● ○ ▶ ▪ ▫ 등)
            or (0x2600 <= cp <= 0x26FF)   # Misc Symbols (★ ☆ 등)
            or (0x2700 <= cp <= 0x27BF)  # Dingbats
            or (0x1F300 <= cp <= 0x1F9FF)  # Emoji, Symbols
            or (0x1F600 <= cp <= 0x1F64F)  # Emoticons
            or (0x1F650 <= cp <= 0x1F67F)  # Supplemental
            or (0x1F680 <= cp <= 0x1F6FF)  # Transport, Map
            or (0x1FA00 <= cp <= 0x1FAFF)   # Chess, etc.
        ):
            continue
        result.append(c)
    return "".join(result)


def _strip_leading_bullet(line: str) -> str:
    """한 줄에서 앞쪽 불릿·번호만 제거. 내용은 유지."""
    return _RE_LEADING_BULLET.sub("", line).strip()


def _is_bracket_title_line(line: str) -> bool:
    """줄 전체가 [제목] 또는 <제목> 형태인지 (대괄호 제목)."""
    return bool(_RE_BRACKET_TITLE_LINE.match(line.strip()))


def _normalize_line_breaks_and_strip_bullets(s: str) -> str:
    """
    - 전각 공백·NBSP → 반각 공백
    - 전각 ＞＜－ → 반각 ><-
    - 각 줄 앞뒤 공백 제거, 줄 시작 불릿 제거
    - 대괄호 제목 줄 제거 ([제목], <제목> 등)
    - list 분리: 빈 줄 제거하여 한 줄 = 한 항목으로 정리
    """
    if not s or not s.strip():
        return s
    s = s.replace("\u3000", " ")   # 전각 공백
    s = s.replace("\u00a0", " ")   # NBSP
    s = s.replace("＞", ">").replace("＜", "<").replace("－", "-")
    lines = [ln.strip() for ln in s.split("\n")]
    out = []
    for ln in lines:
        if not ln:
            continue
        ln = _strip_leading_bullet(ln)
        ln = _strip_inline_brackets(ln).strip()
        ln = _strip_parens(ln)
        if not ln:
            continue
        if _is_bracket_title_line(ln):
            continue
        out.append(ln)
    return "\n".join(out)


def clean_text(
    value: Union[str, float, int],
    *,
    collapse_newlines: bool = True,
    collapse_spaces: bool = True,
    strip_html: bool = True,
    strip_urls: bool = True,
    strip_special_chars: bool = True,
    preserve_hyphen: bool = False,
) -> str:
    """
    단일 텍스트 필드 정제. 정보 삭제 없이 노이즈만 제거.

    - None/NaN → EMPTY_PLACEHOLDER
    - HTML 태그 제거(선택)
    - URL 제거(선택, link 컬럼은 False로 호출)
    - 특수문자 제거(선택, tech_stack은 False, deadline은 preserve_hyphen=True로 - 유지)
    - 이모지·그림 문자 제거
    - 연속 줄바꿈/공백 축소
    """
    if value is None:
        return EMPTY_PLACEHOLDER
    if isinstance(value, float) and pd.isna(value):
        return EMPTY_PLACEHOLDER
    if isinstance(value, (int, float)):
        value = str(value).strip()
    if not isinstance(value, str):
        return EMPTY_PLACEHOLDER
    s = value.strip()
    if not s:
        return EMPTY_PLACEHOLDER
    if strip_html:
        s = re.sub(r"<[^>]+>", "", s)
        s = re.sub(r"&nbsp;|&amp;|&lt;|&gt;|&quot;|&#?\w+;", " ", s)
    if strip_urls:
        s = _RE_URL.sub("", s)
    if strip_special_chars:
        s = _strip_special_chars_preserve_hyphen(s) if preserve_hyphen else _strip_special_chars(s)
    if collapse_newlines:
        s = re.sub(r"\n\s*\n", "\n", s)
        s = re.sub(r"[\r\n]+", "\n", s)
    if collapse_spaces:
        s = re.sub(r"[ \t]+", " ", s)
    s = s.strip() or EMPTY_PLACEHOLDER
    if s:
        s = _strip_emoji_and_symbols(s)
        s = _normalize_line_breaks_and_strip_bullets(s)
    return s or EMPTY_PLACEHOLDER


def _clean_job_role(s: str) -> str:
    """job_role 전용: '채용' 제거, []/() 제거, 이모지·아이콘 제거."""
    if not s or not str(s).strip():
        return EMPTY_PLACEHOLDER
    t = str(s).strip()
    for remove in JOB_ROLE_REMOVE_STRINGS:
        t = t.replace(remove, "")
    t = _strip_inline_brackets(t)
    t = _strip_parens(t)
    t = _strip_emoji_and_symbols(t)
    t = re.sub(r"[ \t]+", " ", t).strip()
    return t or EMPTY_PLACEHOLDER


def _clean_location(s: str) -> str:
    """location 전용: 지도보기, ·, 주소복사 등 제거."""
    if not s or not str(s).strip():
        return EMPTY_PLACEHOLDER
    t = str(s).strip()
    for remove in LOCATION_REMOVE_STRINGS:
        t = t.replace(remove, "")
    t = re.sub(r"[ \t]+", " ", t).strip()
    return t or EMPTY_PLACEHOLDER


# tech_stack 표준 사전: 소문자 키 → 표준 표기 (중복 없이 치환 후 list 순서 유지)
TECH_STACK_CANONICAL = {
    "nginx": "Nginx",
    "ai": "AI",
    "인공지능": "AI",
    "java": "Java",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "x-javascript": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "python": "Python",
    "py": "Python",
    "react": "React",
    "vue": "Vue.js",
    "vue.js": "Vue.js",
    "vuejs": "Vue.js",
    "angular": "Angular",
    "node": "Node.js",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "spring": "Spring",
    "spring boot": "Spring Boot",
    "springboot": "Spring Boot",
    "spring framework": "Spring",
    "git": "Git",
    "github": "GitHub",
    "mysql": "MySQL",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "aws": "AWS",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "rest api": "REST API",
    "restful api": "REST API",
    "restful": "REST API",
    "graphql": "GraphQL",
    "html5": "HTML5",
    "html": "HTML5",
    "junit": "JUnit",
    "gradle": "Gradle",
    "maven": "Maven",
    "redis": "Redis",
    "mongodb": "MongoDB",
    "mongo": "MongoDB",
    "linux": "Linux",
    "react native": "React Native",
    "reactnative": "React Native",
    "next.js": "Next.js",
    "nextjs": "Next.js",
    "nest": "NestJS",
    "nestjs": "NestJS",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "kotlin": "Kotlin",
    "kotiln": "Kotlin",
    "go": "Go",
    "golang": "Go",
    "c++": "C++",
    "c#": "C#",
    "rds": "RDS",
    "ec2": "EC2",
    "lambda": "AWS Lambda",
    "s3": "S3",
    "terraform": "Terraform",
    "jenkins": "Jenkins",
    "github action": "GitHub Actions",
    "github actions": "GitHub Actions",
    "jira": "Jira",
    "confluence": "Confluence",
}


def _normalize_tech_stack(s: str) -> str:
    """
    tech_stack 문자열 정규화: 쉼표·슬래시로 분리, strip, 표준 표기 매핑, 중복 제거 후 ", " 로 재결합.
    """
    if not s or not str(s).strip():
        return EMPTY_PLACEHOLDER
    parts = re.split(r"[,/]", str(s))
    seen = set()
    result = []
    for p in parts:
        t = p.strip()
        if not t:
            continue
        key = t.lower()
        canonical = TECH_STACK_CANONICAL.get(key)
        if canonical is not None:
            t = canonical
        if t not in seen:
            seen.add(t)
            result.append(t)
    return ", ".join(result) if result else EMPTY_PLACEHOLDER


def _is_main_tasks_intro_or_title_line(line: str) -> bool:
    """main_tasks에서 제거할 소개/제목 줄인지 판별."""
    line = line.strip()
    if not line:
        return True
    if "바로가기" in line:
        return True
    for phrase in MAIN_TASKS_INTRO_PHRASES:
        if phrase in line:
            return True
    # 짧은 제목 줄: "페이타랩 프로덕트팀", "○○ 개발팀" 등
    if len(line) <= 45:
        if line.endswith("팀") or line.endswith("부서"):
            return True
        if "프로덕트팀" in line or "개발팀" in line or "연구팀" in line:
            return True
    return False


def _drop_banner_lines(s: str) -> str:
    """'바로가기' 포함 줄 제거 (benefits, qualifications 등 공통). URL은 이미 clean_text에서 제거됨."""
    if not s or not str(s).strip():
        return EMPTY_PLACEHOLDER
    lines = [ln.strip() for ln in str(s).split("\n") if ln.strip() and "바로가기" not in ln]
    return "\n".join(lines).strip() if lines else EMPTY_PLACEHOLDER


def _clean_main_tasks(s: str) -> str:
    """
    main_tasks 전용: URL 전부 제거, URL 소개 문구(바로가기 등) 줄 제거,
    제목·소개 문단(팀명, 오시면 이런 업무 등) 줄 제거.
    """
    if not s or not str(s).strip():
        return EMPTY_PLACEHOLDER
    s = str(s).strip()
    s = _RE_URL.sub("", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n", "\n", s)
    lines = []
    for ln in s.split("\n"):
        ln = ln.strip()
        ln = _RE_URL.sub("", ln).strip()  # 줄 안 남은 URL 제거
        if not ln:
            continue
        if _is_main_tasks_intro_or_title_line(ln):
            continue
        lines.append(ln)
    return "\n".join(lines).strip() if lines else EMPTY_PLACEHOLDER


def clean_jd_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    JD DataFrame 전체 정제.
    - 모든 문자열 컬럼: clean_text 적용 (불릿 제거, 줄바꿈 정규화 포함)
    - job_role: '채용' 제거
    - location: 지도보기·주소복사 등 제거
    - tech_stack: 정규화(표준 표기, 중복 제거)
    - main_tasks: URL·바로가기·제목·소개 문단 제거
    - link 컬럼은 출력에서 제거
    - 원본 컬럼 순서/이름 유지, 정보 삭제 없음.
    """
    out = df.copy()
    if "link" in out.columns:
        out = out.drop(columns=["link"])
    text_columns = [c for c in out.columns if out[c].dtype == object or out[c].dtype.name == "string"]
    for col in text_columns:
        if col == "job_role":
            out[col] = out[col].fillna("").astype(str).map(_clean_job_role)
        elif col == "location":
            out[col] = out[col].fillna("").astype(str).map(_clean_location)
        elif col == "tech_stack":
            out[col] = (
                out[col]
                .fillna("")
                .astype(str)
                .map(lambda x: clean_text(x, strip_special_chars=False))
                .map(_normalize_tech_stack)
            )
        elif col == "deadline":
            out[col] = out[col].fillna("").astype(str).map(lambda x: clean_text(x, preserve_hyphen=True))
        elif col == "main_tasks":
            out[col] = (
                out[col].fillna("").astype(str).map(clean_text).map(_clean_main_tasks)
            )
        elif col in ("benefits", "qualifications", "preferred", "recruitment_process"):
            out[col] = (
                out[col].fillna("").astype(str).map(clean_text).map(_drop_banner_lines)
            )
        else:
            out[col] = out[col].fillna("").astype(str).map(clean_text)
    return out


def load_csv(path: Union[str, Path], encoding: str = "utf-8-sig") -> pd.DataFrame:
    """점핏 공고 CSV 로드."""
    return pd.read_csv(path, encoding=encoding)


def save_cleaned_csv(df: pd.DataFrame, path: Union[str, Path], encoding: str = "utf-8-sig") -> Path:
    """정제된 DataFrame을 CSV로 저장."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding=encoding)
    return path


# 정제 결과 기본 저장 디렉터리 (cleansing.py 기준 service/cleansing/cleansed/)
CLEANSED_DIR = Path(__file__).resolve().parent / "cleansed"


def run_cleansing(
    input_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    encoding: str = "utf-8-sig",
) -> pd.DataFrame:
    """
    CSV 경로를 받아 정제 후 저장하고 DataFrame 반환.
    output_path 미지정 시 service/cleansing/cleansed/ 안에 cleaned_{입력파일명}_1, _2, ... 순으로 저장.
    """
    input_path = Path(input_path)
    if output_path is None:
        CLEANSED_DIR.mkdir(parents=True, exist_ok=True)
        base = f"cleaned_{input_path.stem}"
        pattern = f"{base}_*.csv"
        existing = list(CLEANSED_DIR.glob(pattern))
        nums = []
        for p in existing:
            suffix = p.stem[len(base):].lstrip("_")
            if suffix.isdigit():
                nums.append(int(suffix))
        n = max(nums) + 1 if nums else 1
        output_path = CLEANSED_DIR / f"{base}_{n}.csv"
    else:
        output_path = Path(output_path)
    df = load_csv(input_path, encoding=encoding)
    cleaned = clean_jd_data(df)
    save_cleaned_csv(cleaned, output_path, encoding=encoding)
    print(f"Cleansing 완료: {len(cleaned)}건 → {output_path}")
    return cleaned


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("사용법: python -m service.cleansing.cleansing <입력.csv> [출력.csv]")
        sys.exit(1)
    inp = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    run_cleansing(inp, out)
