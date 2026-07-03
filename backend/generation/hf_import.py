"""Import Q/A pairs from a curated Hugging Face dataset preset.

Loads a slice of the dataset (streaming, so no full download), maps each row's configured fields to
our question/answer, and skips rows missing either field. Preset definitions live in presets.py.
"""

from collections.abc import Iterable

from datasets import load_dataset

from generation.presets import IMPORT_PRESETS


def extract_pairs(
    rows: Iterable[dict], question_field: str, answer_field: str, count: int
) -> list[dict]:
    """Map each row's question/answer fields to our shape, skipping rows missing either field or
    with an empty value. Stops once `count` pairs are collected."""
    pairs = []
    for row in rows:
        question = row.get(question_field)
        answer = row.get(answer_field)
        if question and answer:
            pairs.append({"question": str(question), "answer": str(answer)})
            if len(pairs) >= count:
                break
    return pairs


def import_pairs(preset_key: str, count: int) -> list[dict]:
    """Import up to `count` Q/A pairs from a named preset. Streams the dataset from the Hub and maps
    its fields. Any loading error propagates to the caller to surface as a clean API error."""
    preset = IMPORT_PRESETS[preset_key]
    rows = load_dataset(
        preset["hf_id"], name=preset["subset"], split=preset["split"], streaming=True
    )
    return extract_pairs(rows, preset["question_field"], preset["answer_field"], count)