"""Create an auditable high-confidence Chinese comment corpus."""

from __future__ import annotations

import re
import urllib.request
from collections import Counter

import fasttext
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from pipeline_common import DATA_DIR, FIGURES_DIR, MODELS_DIR, RAW_COMMENTS, RAW_VIDEOS, RANDOM_SEED, configure_matplotlib, ensure_directories, set_reproducibility, sha256, utc_now, write_json


LID_MODEL = MODELS_DIR / "lid.176.bin"
LID_URL = "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin"
CHINESE_CONFIDENCE = 0.80


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


def ensure_language_model() -> None:
    if not LID_MODEL.exists():
        LID_MODEL.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(LID_URL, LID_MODEL)  # nosec B310: fixed upstream model URL
    return None


def detect_language(model: fasttext.FastText._FastText, text: str) -> tuple[str, float]:
    probability, label = model.f.predict(text.replace("\n", " "), 1, 0.0, "__label__")[0]
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
    retained: list[int] = []
    seen: set[str] = set()
    for index, row in comments.iterrows():
        text = row["normalized_text"]
        reason = pre_language_reason(text)
        if reason is None and text.lower() in seen:
            reason = "normalized_duplicate"
        if reason is None:
            seen.add(text.lower())
            retained.append(index)
        else:
            audit_rows.append({"comment_id": row["comment_id"], "video_id": row["video_id"], "published_at": row["published_at"], "stage": "text_cleaning", "reason": reason, "language_code": "", "language_confidence": ""})

    eligible = comments.loc[retained].copy()
    ensure_language_model()
    model = fasttext.load_model(str(LID_MODEL))
    detected = eligible["normalized_text"].map(lambda value: detect_language(model, value))
    eligible[["language_code", "language_confidence"]] = pd.DataFrame(detected.tolist(), index=eligible.index)
    chinese = eligible[(eligible["language_code"] == "zh") & (eligible["language_confidence"] >= CHINESE_CONFIDENCE)].copy()
    for _, row in eligible.drop(index=chinese.index).iterrows():
        reason = "non_chinese" if row["language_code"] != "zh" else "chinese_confidence_below_0.80"
        audit_rows.append({"comment_id": row["comment_id"], "video_id": row["video_id"], "published_at": row["published_at"], "stage": "language_filter", "reason": reason, "language_code": row["language_code"], "language_confidence": row["language_confidence"]})

    chinese = chinese.merge(videos[["video_id", "language", "title", "channel_title", "published_at"]].rename(columns={"language": "source_query_language", "published_at": "video_published_at"}), on="video_id", how="left", validate="many_to_one")
    chinese["published_at"] = chinese["published_at"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    chinese["month"] = pd.to_datetime(chinese["published_at"], utc=True).dt.to_period("M").astype(str)
    chinese = chinese[["comment_id", "video_id", "published_at", "updated_at", "like_count", "text", "normalized_text", "month", "language_code", "language_confidence", "source_query_language", "title", "video_published_at"]].sort_values(["published_at", "comment_id"], kind="stable")
    audit = pd.DataFrame(audit_rows).sort_values(["stage", "reason", "comment_id"], kind="stable")
    chinese.to_csv(DATA_DIR / "chinese_comments.csv", index=False, encoding="utf-8-sig")
    audit.to_csv(DATA_DIR / "cleaning_audit.csv", index=False, encoding="utf-8-sig")
    chinese[["comment_id", "video_id", "month", "source_query_language", "title"]].to_csv(DATA_DIR / "comment_video_linkage.csv", index=False, encoding="utf-8-sig")

    funnel = {"原始评论": len(comments), "文本清洗后": len(eligible), "高置信度中文": len(chinese)}
    raw_hashes_after = {"comments.csv": sha256(RAW_COMMENTS), "videos.csv": sha256(RAW_VIDEOS)}
    write_json(DATA_DIR / "preparation_summary.json", {"generated_at": utc_now(), "raw_hashes_before": raw_hashes_before, "raw_hashes_after": raw_hashes_after, "raw_hashes_unchanged": raw_hashes_before == raw_hashes_after, "chinese_confidence_threshold": CHINESE_CONFIDENCE, "funnel": funnel, "exclusion_reasons": dict(Counter(audit["reason"].tolist())), "detected_languages_before_chinese_filter": dict(Counter(eligible["language_code"].tolist()))})

    sns.set_theme(style="whitegrid", font="Microsoft YaHei")
    fig, axis = plt.subplots(figsize=(9, 5))
    bars = sns.barplot(x=list(funnel), y=list(funnel.values()), color="#3977af", ax=axis)
    axis.set_title("中文语料构建漏斗", pad=12)
    axis.set_xlabel("")
    axis.set_ylabel("评论数")
    for bar, value in zip(bars.patches, funnel.values()):
        axis.text(bar.get_x() + bar.get_width() / 2, value, f"{value:,}", ha="center", va="bottom")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_01_cleaning_funnel.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Prepared {len(chinese):,} high-confidence Chinese comments from {len(comments):,} raw comments.")


if __name__ == "__main__":
    main()
