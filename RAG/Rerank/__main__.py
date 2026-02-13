"""
CLI: Retriever 결과를 rerank.
예: python -m RAG.Retriever "백엔드" --career-type "신입" --limit 20 | python -m RAG.Rerank "백엔드" --top-k 5
또는: python -m RAG.Rerank "백엔드" --top-k 5  (stdin에 Retriever JSON 배열 입력)
"""
import argparse
import json
import sys

from .rerank import rerank


def main() -> None:
    parser = argparse.ArgumentParser(description="검색 결과 Rerank (query-document 관련도 재정렬)")
    parser.add_argument("query", help="검색 질의문")
    parser.add_argument("--top-k", type=int, default=None, dest="top_k", help="상위 k건만 반환")
    parser.add_argument("--model", default=None, dest="model_name", help="Cross-encoder 모델명")
    args = parser.parse_args()

    if sys.stdin.isatty():
        # stdin 없으면 Retriever 직접 호출해서 20건 가져온 뒤 rerank
        from RAG.Retriever import retrieve
        items = retrieve(args.query, limit=20)
    else:
        raw = sys.stdin.read().strip()
        items = json.loads(raw) if raw else []

    result = rerank(args.query, items, top_k=args.top_k, model_name=args.model_name)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
