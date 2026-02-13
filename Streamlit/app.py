"""
Streamlit 앱: RAG(채용 공고 검색 + LLM 답변) 데모.
프로젝트 루트에서 실행: streamlit run Streamlit/app.py
"""
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가 (Streamlit 폴더에서 실행해도 RAG import 가능)
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

import re
import streamlit as st


def _extract_main_task_and_qualifications(text: str) -> str:
    """텍스트에서 '주요업무'와 '자격요건' 섹션만 추출해 합친 문자열 반환."""
    if not (text or text.strip()):
        return ""
    parts = []
    # 주요업무 / 자격요건 (공백 변형 포함) 으로 시작하는 블록 추출
    pattern = re.compile(
        r"(주요\s*업무|자격\s*요건)\s*[:\s]*\n?(.*?)(?=(?:주요\s*업무|자격\s*요건|$))",
        re.DOTALL | re.IGNORECASE,
    )
    for m in pattern.finditer(text):
        label, body = m.group(1).strip(), (m.group(2) or "").strip()
        if body and len(body) >= 5:
            parts.append(f"{label}:\n{body[:2000]}" + ("..." if len(body) > 2000 else ""))
    if parts:
        return "\n\n".join(parts)
    # chunk_group 메타데이터로 이미 그룹 단위면 전체가 해당 섹션일 수 있음
    if "주요업무" in text or "자격요건" in text:
        return text[:3000] + ("..." if len(text) > 3000 else "")
    return text[:1500] + ("..." if len(text) > 1500 else "")

st.set_page_config(page_title="채용 공고 RAG", page_icon="📋", layout="wide")

st.title("📋 채용 공고 RAG")
st.caption("질문을 입력하면 저장된 채용 공고를 검색해 답변합니다.")

query = st.text_area("질문", placeholder="예: 신입 개발자 채용하는 회사 알려줘", height=80)

# 사이드바: 필터 및 옵션
with st.sidebar:
    st.subheader("필터 (선택)")
    company = st.text_input("회사명", key="company")
    job_role = st.text_input("직무", key="job_role")
    career_type = st.selectbox("경력", [None, "신입", "경력", "무관"], format_func=lambda x: x or "전체")
    company_years_num = st.text_input("회사 규모/업력", key="company_years", placeholder="예: 5년차")
    st.divider()
    st.subheader("검색 옵션")
    retrieve_limit = st.slider("검색 후보 건수", 5, 50, 20)
    use_rerank = st.checkbox("Rerank 사용", value=True)
    rerank_top_k = st.number_input("Rerank 후 사용할 공고 수", min_value=1, max_value=10, value=5)

if st.button("검색", type="primary"):
    if not query.strip():
        st.warning("질문을 입력해 주세요.")
    else:
        try:
            from RAG.Generate import generate
            with st.spinner("검색 및 답변 생성 중..."):
                result = generate(
                    query.strip(),
                    company=company.strip() or None,
                    job_role=job_role.strip() or None,
                    career_type=career_type,
                    company_years_num=company_years_num.strip() or None,
                    retrieve_limit=retrieve_limit,
                    use_rerank=use_rerank,
                    rerank_top_k=rerank_top_k,
                )
            st.subheader("답변")
            st.markdown(result["answer"])
            st.caption(f"참고한 context 길이: {result['context_length']}자")
            sources = result.get("sources") or []
            if sources:
                with st.expander(f"참고한 채용 공고 ({len(sources)}건)"):
                    for i, src in enumerate(sources, 1):
                        meta = src.get("metadata") or {}
                        company_name = meta.get("company") or "-"
                        role = meta.get("job_role") or "-"
                        raw_text = (src.get("text") or "").strip()
                        text = _extract_main_task_and_qualifications(raw_text) or raw_text
                        st.markdown(f"**[{i}] {company_name} · {role}**")
                        if text:
                            st.code(text, language=None)
                        st.divider()
            else:
                st.caption("참고한 공고가 없습니다.")
        except Exception as e:
            st.error(f"오류: {e}")
            raise
