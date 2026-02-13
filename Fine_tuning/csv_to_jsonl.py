"""
학습 데이터 CSV → OpenAI 파인튜닝용 JSONL 변환.
CSV 열: query, context, assistant_answer (UTF-8)
"""
import csv
import json
from pathlib import Path

from .Fine_tuning import build_finetune_messages_example


def csv_to_openai_jsonl(csv_path: Path | str, out_path: Path | str) -> int:
    """
    CSV 파일(query, context, assistant_answer)을 읽어
    OpenAI 파인튜닝용 JSONL로 저장. 한 줄에 한 건, {"messages": [...]}.
    """
    csv_path = Path(csv_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(csv_path, encoding="utf-8") as f_in, open(out_path, "w", encoding="utf-8") as f_out:
        reader = csv.DictReader(f_in)
        if not reader.fieldnames or "query" not in reader.fieldnames or "context" not in reader.fieldnames or "assistant_answer" not in reader.fieldnames:
            raise ValueError("CSV에 query, context, assistant_answer 열이 있어야 합니다.")
        for row in reader:
            query = (row.get("query") or "").strip()
            context = (row.get("context") or "").strip()
            answer = (row.get("assistant_answer") or "").strip()
            if not query or not context or not answer:
                continue
            messages = build_finetune_messages_example(query, context, answer)
            f_out.write(json.dumps({"messages": messages}, ensure_ascii=False) + "\n")
            count += 1
    return count
