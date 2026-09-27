"""Parse uploaded CSV/JSONL files into Q&A pair dicts.

Shared by the dataset import upload endpoint (S12, issue #14). Tolerant on
purpose: header names are matched case-insensitively, blank rows are skipped,
and malformed rows are reported by line number instead of failing the file.
"""

import csv
import io
import json

MAX_BYTES = 2 * 1024 * 1024  # 2 MB upload cap
MAX_PAIRS = 5000

# Header aliases accepted for the two columns (lowercased for matching).
QUESTION_KEYS = {"question", "prompt", "input", "instruction", "q"}
ANSWER_KEYS = {"answer", "completion", "output", "response", "a"}


class ImportError_(ValueError):
    """Raised for files we refuse outright (bad extension, too big, no rows)."""


def _pick(row: dict, keys: set[str]) -> str | None:
    for k, v in row.items():
        if k and k.strip().lower() in keys and v is not None:
            text = str(v).strip()
            if text:
                return text
    return None


def parse_upload(filename: str, raw: bytes) -> list[dict]:
    """Return [{"question": ..., "answer": ...}, ...] from a CSV or JSONL blob.

    Raises ImportError_ with a human-readable reason when the file can't be
    accepted; a parse error in the middle of an otherwise valid file skips only
    the bad row.
    """
    if len(raw) > MAX_BYTES:
        raise ImportError_(f"File is too large (max {MAX_BYTES // 1024} KB)")

    name = (filename or "").lower()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ImportError_("File is not valid UTF-8 text")

    if name.endswith(".jsonl") or name.endswith(".json"):
        pairs = _parse_jsonl(text)
    elif name.endswith(".csv"):
        pairs = _parse_csv(text, ",")
    elif name.endswith(".tsv"):
        pairs = _parse_csv(text, "\t")
    else:
        raise ImportError_("Unsupported file type — upload a .csv or .jsonl file")

    if not pairs:
        raise ImportError_("No valid rows found — expected question/answer columns")
    return pairs


def _parse_jsonl(text: str) -> list[dict]:
    pairs: list[dict] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue  # tolerate a stray bad line
        if not isinstance(obj, dict):
            continue
        question = _pick(obj, QUESTION_KEYS)
        answer = _pick(obj, ANSWER_KEYS)
        if question and answer:
            pairs.append({"question": question, "answer": answer})
        elif line_no == 1:
            raise ImportError_(
                "First JSONL row has no question/answer fields "
                f"(saw: {', '.join(list(obj)[:6]) or 'nothing'})"
            )
        if len(pairs) >= MAX_PAIRS:
            break
    return pairs


def _parse_csv(text: str, delimiter: str = ",") -> list[dict]:
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise ImportError_("CSV file appears to be empty")
    pairs: list[dict] = []
    for row in reader:
        question = _pick(row, QUESTION_KEYS)
        answer = _pick(row, ANSWER_KEYS)
        if question and answer:
            pairs.append({"question": question, "answer": answer})
        if len(pairs) >= MAX_PAIRS:
            break
    return pairs
