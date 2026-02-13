"""
CLI: python -m RAG.Generate "질문" [--no-rerank] [--company 회사명] [--career-type 신입] ...
"""
import argparse
import json

from .generate import generate


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG: 질의 → 검색 → LLM 답변 생성")
    parser.add_argument("query", help="질문")
    parser.add_argument("--company", default=None, help="회사명 필터")
    parser.add_argument("--job-role", default=None, dest="job_role", help="직무 필터")
    parser.add_argument("--career-type", default=None, dest="career_type", help="경력 여부 (신입/경력/무관)")
    parser.add_argument("--company-years", default=None, dest="company_years_num", help="회사 규모/업력 필터")
    parser.add_argument("--retrieve-limit", type=int, default=20, help="Retriever 상위 건수")
    parser.add_argument("--no-rerank", action="store_true", help="Rerank 비활성화")
    parser.add_argument("--rerank-top-k", type=int, default=5, dest="rerank_top_k", help="Rerank 후 context 건수")
    parser.add_argument("--model", default=None, help="OpenAI 채팅 모델 (기본 gpt-4o-mini)")
    parser.add_argument("--json", action="store_true", dest="output_json", help="전체 결과를 JSON으로 출력")
    args = parser.parse_args()

    result = generate(
        args.query,
        company=args.company,
        job_role=args.job_role,
        career_type=args.career_type,
        company_years_num=args.company_years_num,
        retrieve_limit=args.retrieve_limit,
        use_rerank=not args.no_rerank,
        rerank_top_k=args.rerank_top_k,
        model=args.model,
    )
    if args.output_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["answer"])


if __name__ == "__main__":
    main()
