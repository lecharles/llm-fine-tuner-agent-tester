"""Convert a dataset's QA pairs into the JSONL files mlx-lm reads for training.

mlx-lm's `mlx_lm.lora --train --data <dir>` expects a directory holding a
`train.jsonl` file (and an optional `valid.jsonl`), where every line is one
JSON example. We use the chat format so the model trains on the same turn
structure it will see in the compare-chat at inference:

    {"messages": [{"role": "user", "content": "..."},
                  {"role": "assistant", "content": "..."}]}
"""

import json
import random
from collections.abc import Iterable
from pathlib import Path


def build_chat_record(question: str, answer: str) -> dict:
    """One chat-format example: question as the user turn, answer as the assistant turn."""
    return {
        "messages": [
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ]
    }


def write_jsonl(records: Iterable[dict], path: Path) -> int:
    """Write each record as its own JSON line to `path`; return how many were written."""
    count = 0
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def build_training_files(
    qa_pairs: Iterable,
    output_dir: Path,
    valid_fraction: float = 0.0,
    seed: int = 42,
) -> dict:
    """Turn a dataset's QA pairs into train.jsonl (and valid.jsonl when valid_fraction
    is above zero) inside output_dir, the directory handed to mlx-lm. Each item only
    needs a `.question` and an `.answer`, so this runs directly on QAPair rows. Returns
    the written paths and row counts for logging and storage."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records = [build_chat_record(pair.question, pair.answer) for pair in qa_pairs]

    if not records:
        raise ValueError("No QA pairs to convert; the dataset is empty.")

    random.Random(seed).shuffle(records)

    valid_count = int(len(records) * valid_fraction)
    valid_records = records[:valid_count]
    train_records = records[valid_count:]

    train_path = output_dir / "train.jsonl"
    written_train = write_jsonl(train_records, train_path)

    result = {"train_path": str(train_path), "train_count": written_train}

    if valid_records:
        valid_path = output_dir / "valid.jsonl"
        written_valid = write_jsonl(valid_records, valid_path)
        result["valid_path"] = str(valid_path)
        result["valid_count"] = written_valid

    return result