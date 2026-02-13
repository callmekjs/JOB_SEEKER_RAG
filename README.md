# 📋 채용공고 RAG (Recruit Crawler + RAG)

점핏(Jumpit) 채용 공고를 크롤링하고, 정제·정규화·청킹·임베딩 후 PostgreSQL(pgvector)에 저장합니다.  
저장된 공고를 **RAG(검색 + 재순위 + LLM)** 로 질의하면 답변과 참고 공고를 확인할 수 있으며, **Streamlit** 웹 앱으로 사용할 수 있습니다.

<br/>

## ✨ 주요 기능

- ✅ **점핏 채용 공고 크롤링** (`jumpit_crawler.py`) — Playwright/Selenium 기반
- ✅ **데이터 파이프라인**: Cleansing → Normalizing → Chunking → Embedding → PostgreSQL(pgvector)
- ✅ **RAG**: Retriever(벡터 검색 + 메타 필터) → Rerank(Cross-encoder) → Generate(LLM 답변)
- ✅ **Streamlit 앱**: 질문 입력 → 답변 + 참고한 채용 공고(주요업무·자격요건) 표시
- ✅ **Fine_tuning**: JD 규칙·시스템 프롬프트 정의 (파인튜닝/프롬프트 설계용)

<br/>

## 📐 설계 플로우

### 데이터 파이프라인 (수집 → 저장)

```mermaid
flowchart LR
  A[점핏 크롤링] --> B[Cleansing]
  B --> C[Normalizing]
  C --> D[Chunking]
  D --> E[Embedding]
  E --> F[(pgvector)]
```

### RAG (질의 → 답변)

```mermaid
flowchart LR
  Q[질문] --> R[Retriever]
  R --> RR[Rerank]
  RR --> G[Generate]
  G --> A[답변 + 참고 공고]
  A --> S[Streamlit UI]
```

<br/>

## 📁 프로젝트 구조

```
recruit_crawler/
├── jumpit_crawler.py      # 점핏 크롤러
├── service/               # 데이터 파이프라인
│   ├── cleansing/         # CSV 정제
│   ├── normalizing/       # 정규화 + document 컬럼 생성
│   ├── chunking/          # 5그룹 청킹 (직무·기술스택·주요업무·자격요건·조건)
│   └── embedding/         # OpenAI 임베딩 → pgvector + JSONL
├── RAG/
│   ├── Retriever/         # 벡터 검색 + 메타 필터
│   ├── Rerank/            # Cross-encoder 재순위
│   ├── Generate/          # context → LLM 답변 생성
│   └── Evaluate/         # 검색/RAG 평가
├── Fine_tuning/           # JD 규칙, get_finetune_system_prompt() 등
├── Streamlit/
│   └── app.py             # RAG 질의·답변 웹 UI
├── requirements.txt
├── .env                   # OPENAI_API_KEY, DATABASE_URL (미커밋)
└── README.md
```

<br/>

## 🛠️ 설치 방법

### 1. 저장소 클론

```bash
git clone https://github.com/yujeong0411/recruit_crawler.git
cd recruit_crawler
```

### 2. 가상환경 (권장)

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate   # Mac/Linux
```

### 3. 패키지 설치

```bash
pip install -r requirements.txt
```

주요 의존성: `openai`, `psycopg2-binary`, `pgvector`, `python-dotenv`, `sentence-transformers`, `streamlit`, `playwright`, `pandas` 등.

### 4. 환경 변수 (.env)

프로젝트 루트에 `.env` 파일을 만들고 다음을 설정합니다.

| 변수 | 설명 |
|------|------|
| `OPENAI_API_KEY` | OpenAI API 키 (임베딩·채팅) |
| `DATABASE_URL` | PostgreSQL 연결 문자열 (예: `postgresql://user:pass@localhost:5432/postgres`) |

pgvector 확장이 설치된 PostgreSQL이 필요합니다.

### 5. 점핏 크롤링 → DB 적재 (선택)

1. 점핏 크롤러로 CSV 수집: `jumpit_crawler.py` 실행
2. Cleansing → Normalizing → Chunking → Embedding 순으로 파이프라인 실행 후, `service/embedding`에서 PostgreSQL에 저장

<br/>

## 🚀 사용법

### Streamlit으로 RAG 사용 (질의·답변)

```bash
streamlit run Streamlit/app.py
```

브라우저에서 질문을 입력하고 **검색** 버튼을 누르면, 저장된 채용 공고를 검색해 답변과 참고 공고(주요업무·자격요건)를 표시합니다.  
사이드바에서 회사명·직무·경력·회사 규모 필터와 검색 옵션(후보 건수, Rerank 사용, 공고 수)을 조정할 수 있습니다.

### RAG CLI (답변만 생성)

```bash
python -m RAG.Generate "데이터 파이프라인 경험 있는 회사 알려줘"
```

옵션: `--company`, `--job-role`, `--career-type`, `--company-years`, `--retrieve-limit`, `--no-rerank`, `--rerank-top-k` 등.

### 검색만 (Retriever)

```bash
python -m RAG.Retriever "백엔드 개발자" --limit 10
```

### Rerank만 테스트

```bash
python -m RAG.Rerank "질문"  # 내부에서 Retriever 호출 후 Rerank
```

<br/>

## 📊 RAG 흐름 요약

1. **Retriever**: 질의 임베딩 + 메타 필터 → pgvector 유사도 검색 → 공고당 1건 dedup
2. **Rerank**: Cross-encoder로 (질문, 문서) 관련도 재정렬 → 상위 k건
3. **Generate**: 공고 중복·회사명 없음·동일 본문 제거 후 context 구성 → LLM(기본 gpt-4o-mini)으로 답변 생성 → 답변 + sources 반환

<br/>

## ⚠️ 주의사항

- 점핏 사이트 구조가 바뀌면 크롤러가 동작하지 않을 수 있습니다.
- 과도한 요청 시 차단될 수 있으므로, 크롤링 시 간격을 두세요.
- `.env`는 API 키·DB 비밀번호가 포함되므로 Git에 커밋하지 마세요 (`.gitignore`에 포함 권장).

<br/>

## 📌 라이선스

이 프로젝트는 [MIT License](./LICENSE)를 따릅니다.
