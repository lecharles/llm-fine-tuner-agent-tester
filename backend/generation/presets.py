"""Curated Hugging Face import presets: dataset id, split, and which fields map to our
question/answer. Fields are per dataset (see docs/RESEARCH_DATASETS.md), so verify a preset's
fields by importing a few rows before trusting it. Adding a preset is one entry here.

Starting with two we are confident about (flat fields, parquet-backed so they load on datasets
4.x). Medical, legal, and scriptwriting get added once their field mappings are verified on-device.
"""

IMPORT_PRESETS = {
    "general": {
        "label": "General instructions (Dolly)",
        "hf_id": "databricks/databricks-dolly-15k",
        "subset": None,
        "split": "train",
        "question_field": "instruction",
        "answer_field": "response",
    },
    "finance": {
        "label": "Finance Q&A",
        "hf_id": "Josephgflowers/Finance-Instruct-500k",
        "subset": None,
        "split": "train",
        "question_field": "user",
        "answer_field": "assistant",
    },
}