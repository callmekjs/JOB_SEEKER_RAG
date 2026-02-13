"""
python -m service.chunking <정규화된_CSV_경로>
결과: service/chunking/chunked/chunked_1.jsonl, chunked_2.jsonl, ...
"""
import sys

from .chunking import run_chunking


def main() -> None:
    if len(sys.argv) < 2:
        print("사용법: python -m service.chunking <정규화된_CSV_경로>", file=sys.stderr)
        sys.exit(1)
    input_path = sys.argv[1]
    run_chunking(input_path)


if __name__ == "__main__":
    main()
