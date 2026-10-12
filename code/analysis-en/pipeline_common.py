"""Shared paths and reproducibility helpers for the Ne Zha 2 comment study."""

from __future__ import annotations

import hashlib
import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
RAW_ROOT = ROOT.parent / "nezha2_youtube_20260901"
RAW_COMMENTS = RAW_ROOT / "comments.csv"
RAW_VIDEOS = RAW_ROOT / "videos.csv"
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
FIGURES_DIR = ROOT / "figures"
REPORTS_DIR = ROOT / "reports"
CACHE_DIR = ROOT / "cache"
MODELS_DIR = CACHE_DIR / "models"
PIP_CACHE_DIR = CACHE_DIR / "pip"
HF_HOME = CACHE_DIR / "huggingface"
RANDOM_SEED = 42
TIMES_NEW_ROMAN = "Times New Roman"

# Set before importing transformers, sentence-transformers, or datasets.
os.environ.setdefault("HF_HOME", str(HF_HOME))
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(HF_HOME / "hub"))
os.environ.setdefault("TRANSFORMERS_CACHE", str(HF_HOME / "hub"))
os.environ.setdefault("PIP_CACHE_DIR", str(PIP_CACHE_DIR))


def ensure_directories() -> None:
    for path in (DATA_DIR, RESULTS_DIR, FIGURES_DIR, REPORTS_DIR, CACHE_DIR, MODELS_DIR, PIP_CACHE_DIR, HF_HOME):
        path.mkdir(parents=True, exist_ok=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def set_reproducibility(seed: int = RANDOM_SEED) -> None:
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:
        pass
    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


def configure_matplotlib() -> None:
    """Apply a consistent, Latin-safe publication style to all figures."""
    import matplotlib as mpl

    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": [TIMES_NEW_ROMAN, "DejaVu Serif"],
            "font.size": 11,
            "axes.titlesize": 14,
            "axes.labelsize": 12,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            "axes.titleweight": "bold",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.unicode_minus": False,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )
