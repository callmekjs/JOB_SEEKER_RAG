"""
python -m service.normalizing <입력.csv>
결과: service/normalizing/normalized/normalized_{입력파일명}_1.csv, _2.csv, ...
"""
import sys

from .normalizing import run_normalizing


def main() -> None:
    if len(sys.argv) < 2:
        print("사용법: python -m service.normalizing <입력.csv>", file=sys.stderr)
        sys.exit(1)
    input_path = sys.argv[1]
    run_normalizing(input_path, output_path=None)


if __name__ == "__main__":
    main()
