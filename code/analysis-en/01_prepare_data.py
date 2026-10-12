"""Create an English-only, auditable comment corpus without modifying raw data."""

from __future__ import annotations

import re
import urllib.request
from collections import Counter
from pathlib import Path

import fasttext
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from pipeline_common import (
    DATA_DIR,
    FIGURES_DIR,
    MODELS_DIR,
    RAW_COMMENTS,
    RAW_VIDEOS,
    RANDOM_SEED,
    TIMES_NEW_ROMAN,
    configure_matplotlib,
    ensure_directories,
    set_reproducibility,
    sha256,
    utc_now,
    write_json,
)


LID_MODEL = MODELS_DIR / "lid.176.bin"
LID_URL = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin"
ENGLISH_CONFIDENCE = 0.80


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def pre_language_reason(text: str) -> str | None:
    if not text:
        return "blank"
    if len(text) < 5:
        return "shorter_than_5_characters"
    if re.fullmatch(r"(?:https?://\S+\s*)+", text, flags=re.IGNORECASE):
        return "url_only"
    if not re.search(r"[A-Za-z\u4e00-\u9fff]", text):
        return "no_alphabetic_or_cjk_content"
    return None


def ensure_language_model() -> Path:
    if not LID_MODEL.exists():
        LID_MODEL.parent.mkdir(parents=True, exist_ok=True)
        print("Downloading fastText language-identification model to analysis cache...")
        urllib.request.urlretrieve(LID_URL, LID_MODEL)  # nosec B310: fixed Meta model URL
    return LID_MODEL


def detect_language(model: fasttext.FastText._FastText, text: str) -> tuple[str, float]:
    # fasttext-wheel's public ``predict`` currently calls ``np.array(...,
    # copy=False)``, which is incompatible with NumPy 2.  Its wrapped C++
    # object returns the same label/probability pair without that conversion.
    prediction = model.f.predict(text.replace("\n", " "), 1, 0.0, "__label__")
    probability, label = prediction[0]
    return str(label).replace("__label__", ""), float(probability)


def main() -> None:
    ensure_directories()
    set_reproducibility(RANDOM_SEED)
    configure_matplotlib()
    raw_hashes_before = {"comments.csv": sha256(RAW_COMMENTS), "videos.csv": sha256(RAW_VIDEOS)}
    comments = pd.read_csv(RAW_COMMENTS, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    videos = pd.read_csv(RAW_VIDEOS, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    comments["normalized_text"] = comments["text"].map(normalize)
    comments["published_at"] = pd.to_datetime(comments["published_at"], utc=True, errors="coerce")
    comments = comments.sort_values(["published_at", "comment_id"], kind="stable").reset_index(drop=True)

    audit_rows: list[dict[str, object]] = []
    retained_pre_language: list[int] = []
    seen_normalized: set[str] = set()
    for index, row in comments.iterrows():
        text = row["normalized_text"]
        reason = pre_language_reason(text)
        if reason is None and text.lower() in seen_normalized:
            reason = "normalized_duplicate"
        if reason is None:
            seen_normalized.add(text.lower())
            retained_pre_language.append(index)
        else:
            audit_rows.append(
                {
                    "comment_id": row["comment_id"], "video_id": row["video_id"], "published_at": row["published_at"],
                    "stage": "text_cleaning", "reason": reason, "language_code": "", "language_confidence": "",
                }
            )

    eligible = comments.loc[retained_pre_language].copy()
    model = fasttext.load_model(str(ensure_language_model()))
    detections = eligible["normalized_text"].map(lambda text: detect_language(model, text))
    eligible[["language_code", "language_confidence"]] = pd.DataFrame(detections.tolist(), index=eligible.index)
    english = eligible[(eligible["language_code"] == "en") & (eligible["language_confidence"] >= ENGLISH_CONFIDENCE)].copy()
    excluded_language = eligible.drop(index=english.index)
    for _, row in excluded_language.iterrows():
        reason = "non_english" if row["language_code"] != "en" else "english_confidence_below_0.80"
        audit_rows.append(
            {
                "comment_id": row["comment_id"], "video_id": row["video_id"], "published_at": row["published_at"],
                "stage": "language_filter", "reason": reason, "language_code": row["language_code"],
                "language_confidence": row["language_confidence"],
            }
        )

    english = english.merge(
        videos[["video_id", "language", "title", "channel_title", "published_at"]].rename(
            columns={"language": "source_query_language", "published_at": "video_published_at"}
        ),
        on="video_id",
        how="left",
        validate="many_to_one",
    )
    english["published_at"] = english["published_at"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    english["month"] = pd.to_datetime(english["published_at"], utc=True).dt.to_period("M").astype(str)
    english = english[
        [
            "comment_id", "video_id", "published_at", "updated_at", "like_count", "text", "normalized_text", "month",
            "language_code", "language_confidence", "source_query_language", "title", "video_published_at",
        ]
    ].sort_values(["published_at", "comment_id"], kind="stable")
    audit = pd.DataFrame(audit_rows).sort_values(["stage", "reason", "comment_id"], kind="stable")
    english.to_csv(DATA_DIR / "english_comments.csv", index=False, encoding="utf-8-sig")
    audit.to_csv(DATA_DIR / "cleaning_audit.csv", index=False, encoding="utf-8-sig")

    funnel = Counter({"raw_comments": len(comments), "after_text_cleaning": len(eligible), "english_analysis_corpus": len(english)})
    reason_counts = Counter(audit["reason"].tolist())
    raw_hashes_after = {"comments.csv": sha256(RAW_COMMENTS), "videos.csv": sha256(RAW_VIDEOS)}
    metadata = {
        "generated_at": utc_now(), "raw_hashes_before": raw_hashes_before, "raw_hashes_after": raw_hashes_after,
        "raw_hashes_unchanged": raw_hashes_before == raw_hashes_after, "english_confidence_threshold": ENGLISH_CONFIDENCE,
        "funnel": dict(funnel), "exclusion_reasons": dict(reason_counts),
        "detected_languages_before_english_filter": dict(Counter(eligible["language_code"].tolist())),
    }
    write_json(DATA_DIR / "preparation_summary.json", metadata)

    sns.set_theme(style="whitegrid", font=TIMES_NEW_ROMAN)
    fig, axis = plt.subplots(figsize=(9, 5))
    labels, values = list(funnel.keys()), list(funnel.values())
    sns.barplot(x=labels, y=values, color="#3977af", ax=axis)
    axis.set_title("English corpus construction funnel")
    axis.set_xlabel("")
    axis.set_ylabel("Comments")
    axis.tick_params(axis="x", rotation=15)
    for bar, value in zip(axis.patches, values):
        axis.text(bar.get_x() + bar.get_width() / 2, value, f"{value:,}", ha="center", va="bottom")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_01_cleaning_funnel.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Prepared {len(english):,} English comments from {len(comments):,} raw comments.")


if __name__ == "__main__":
    main()
