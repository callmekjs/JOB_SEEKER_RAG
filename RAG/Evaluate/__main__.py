"""
CLI: python -m RAG.Evaluate [eval_json_path] [--k 20] [--rerank] [--rerank-top-k 10]
"""
import argparse
import json
from pathlib import Path

from .evaluate import evaluate_retrieval, load_eval_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Retriever/Rerank 품질 평가 (Recall@k, MRR, Hit@k)")
    parser.add_argument(
        "eval_path",
        nargs="?",
        default=None,
        help="평가 세트 JSON/JSONL 경로 (미지정 시 기본 eval_sample.json)",
    )
    parser.add_argument("--k", type=int, default=20, help="Retriever 상위 k건")
    parser.add_argument("--rerank", action="store_true", help="Rerank 적용 후 평가")
    parser.add_argument("--rerank-top-k", type=int, default=10, dest="rerank_top_k", help="Rerank 상위 k건")
    args = parser.parse_args()

    default_path = Path(__file__).resolve().parent / "eval_sample.json"
    path = args.eval_path or str(default_path)
    eval_data = load_eval_data(path)
    if not eval_data:
        print("평가 데이터가 없습니다.")
        return

    metrics = evaluate_retrieval(
        eval_data,
        k=args.k,
        use_rerank=args.rerank,
        rerank_top_k=args.rerank_top_k,
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
