"""
CLI: python -m RAG.Retriever "질의문" [--company 회사명] [--job-role 직무] [--career-type 경력] [--company-years 업력] [--limit N]
"""
import argparse
import json

from .retriever import retrieve


def main() -> None:
    parser = argparse.ArgumentParser(description="벡터 검색 + 메타데이터 필터 (팀장님 요구: 회사명·직무·경력·회사규모)")
    parser.add_argument("query", help="검색 질의문")
    parser.add_argument("--company", default=None, help="회사명 필터")
    parser.add_argument("--job-role", default=None, help="직무/직무 카테고리 필터")
    parser.add_argument("--career-type", default=None, help="경력 여부 (예: 신입, 경력, 무관)")
    parser.add_argument("--company-years", default=None, dest="company_years_num", help="회사 규모/업력 필터 (예: 5년차)")
    parser.add_argument("--limit", type=int, default=5, help="반환 건수 (기본 5)")
    args = parser.parse_args()

    results = retrieve(
        args.query,
        company=args.company,
        job_role=args.job_role,
        career_type=args.career_type,
        company_years_num=args.company_years_num,
        limit=args.limit,
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
