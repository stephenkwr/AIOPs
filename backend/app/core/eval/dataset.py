"""Load the version-controlled golden dataset + its corpus from disk.

The dataset (backend/eval/dataset.json) and corpus (backend/eval/corpus/*.md) are
committed to the repo so evaluation is fully reproducible — no external fixtures.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# app/core/eval/dataset.py -> parents[3] == backend/
EVAL_DIR = Path(__file__).resolve().parents[3] / "eval"
DATASET_PATH = EVAL_DIR / "dataset.json"
CORPUS_DIR = EVAL_DIR / "corpus"


@dataclass(frozen=True)
class DatasetItem:
    id: str
    question: str
    reference_answer: str
    category: str
    answerable: bool
    gold_doc: str | None


@dataclass(frozen=True)
class CorpusFile:
    filename: str
    text: str


@lru_cache(maxsize=1)
def load_dataset() -> tuple[str, list[DatasetItem]]:
    """Return (dataset_name, items). Cached — the dataset is immutable at runtime."""
    raw = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    items = [
        DatasetItem(
            id=it["id"],
            question=it["question"],
            reference_answer=it.get("reference_answer", ""),
            category=it.get("category", "general"),
            answerable=bool(it["answerable"]),
            gold_doc=it.get("gold_doc"),
        )
        for it in raw["items"]
    ]
    return raw.get("name", "dataset"), items


def load_corpus() -> list[CorpusFile]:
    """Every corpus document, sorted by filename for deterministic seeding order."""
    files = sorted(CORPUS_DIR.glob("*.md"))
    return [CorpusFile(filename=p.name, text=p.read_text(encoding="utf-8")) for p in files]
