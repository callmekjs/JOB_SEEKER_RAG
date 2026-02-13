"""
CLI: python -m Fine_tuning [train_data.csv] [-o train.jsonl]
학습 데이터 CSV를 OpenAI 파인튜닝용 JSONL로 변환.
"""
import argparse
from pathlib import Path

from .csv_to_jsonl import csv_to_openai_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description="CSV( query, context, assistant_answer ) → OpenAI 파인튜닝 JSONL")
    parser.add_argument(
        "csv_path",
        nargs="?",
        default=None,
        help="입력 CSV 경로 (미지정 시 Fine_tuning/train_data_sample.csv)",
    )
    parser.add_argument("-o", "--output", dest="out_path", default=None, help="출력 JSONL 경로 (기본: 입력과 같은 이름에 .jsonl)")
    args = parser.parse_args()

    default_csv = Path(__file__).resolve().parent / "train_data_sample.csv"
    csv_path = Path(args.csv_path) if args.csv_path else default_csv
    if not csv_path.exists():
        print(f"파일이 없습니다: {csv_path}")
        return
    out_path = Path(args.out_path) if args.out_path else csv_path.with_suffix(".jsonl")

    n = csv_to_openai_jsonl(csv_path, out_path)
    print(f"변환 완료: {n}건 → {out_path}")


if __name__ == "__main__":
    main()
