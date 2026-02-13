"""
python -m service.embedding <chunked_JSONL_경로>
결과: service/embedding/embedded/embedded_1.jsonl, embedded_2.jsonl, ...
"""
import sys

from .embedding import run_embedding


def main() -> None:
    if len(sys.argv) < 2:
        print("사용법: python -m service.embedding <chunked_JSONL_경로>", file=sys.stderr)
        sys.exit(1)
    input_path = sys.argv[1]
    run_embedding(input_path)


if __name__ == "__main__":
    main()
