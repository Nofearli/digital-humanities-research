"""Chinese sentiment analysis with a native Transformer and SnowNLP check."""

from __future__ import annotations

import argparse
from collections import Counter
import os
import re

import jieba
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import torch
from snownlp import SnowNLP
from sklearn.feature_extraction.text import TfidfVectorizer
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from wordcloud import WordCloud

from pipeline_common import DATA_DIR, FIGURES_DIR, MODELS_DIR, RANDOM_SEED, RESULTS_DIR, configure_jieba_cache, configure_matplotlib, ensure_directories, set_reproducibility, utc_now, write_json


SENTIMENT_MODEL = "uer/roberta-base-finetuned-jd-binary-chinese"
POSITIVE_THRESHOLD = 0.60
NEGATIVE_THRESHOLD = 0.40
CHINESE_FONT_PATH = "C:\\Windows\\Fonts\\msyh.ttc"
STOP_WORDS = {"的", "了", "是", "我", "你", "他", "她", "它", "我们", "你们", "他们", "这", "那", "这个", "那个", "一个", "没有", "就是", "真的", "感觉", "觉得", "看到", "看了", "看过", "一下", "还是", "可以", "什么", "怎么", "因为", "所以", "如果", "但是", "而且", "以及", "然后", "现在", "已经", "非常", "比较", "很多", "太", "很", "都", "也", "还", "又", "被", "把", "在", "和", "与", "对", "给", "让", "从", "到", "着", "啊", "呀", "吧", "吗", "呢", "哦", "哈哈", "哈哈哈", "哪吒", "哪吒2", "魔童", "闹海", "电影", "影片", "视频", "评论", "youtube", "油管", "观看", "观影", "看", "作品", "第二部", "续集"}
CJK_TOKEN = re.compile(r"[\u4e00-\u9fff]")


def tokenized_content(text: str) -> str:
    return " ".join(token.strip() for token in jieba.lcut(text) if len(token.strip()) >= 2 and CJK_TOKEN.search(token.strip()) and token.strip() not in STOP_WORDS and not token.strip().isdigit())


def to_three_class(score: float) -> str:
    return "positive" if score >= POSITIVE_THRESHOLD else "negative" if score <= NEGATIVE_THRESHOLD else "neutral"


def infer_transformer(corpus: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        torch.set_num_threads(min(8, os.cpu_count() or 4))
    model_dir = MODELS_DIR / "transformers"
    tokenizer = AutoTokenizer.from_pretrained(SENTIMENT_MODEL, cache_dir=str(model_dir))
    model = AutoModelForSequenceClassification.from_pretrained(SENTIMENT_MODEL, cache_dir=str(model_dir)).to(device)
    model.eval()
    label_map = {str(key).lower(): str(value).lower() for key, value in model.config.id2label.items()}
    positive_index = next((int(key) for key, value in label_map.items() if "positive" in value or value in {"label_1", "1"}), 1)
    rows: list[dict[str, object]] = []
    # A 128-token limit retains short-comment sentiment cues while avoiding
    # excessive CPU cost from a small number of very long comments.
    batch_size = 64 if device == "cuda" else 32
    for start in range(0, len(corpus), batch_size):
        batch = corpus.iloc[start:start + batch_size]
        inputs = tokenizer(batch["normalized_text"].tolist(), truncation=True, max_length=128, padding=True, return_tensors="pt").to(device)
        with torch.no_grad():
            probabilities = torch.softmax(model(**inputs).logits, dim=1).detach().cpu().numpy()
        for (_, item), scores in zip(batch.iterrows(), probabilities):
            probability = float(scores[positive_index])
            snow_probability = float(SnowNLP(item["normalized_text"]).sentiments)
            rows.append({"comment_id": item["comment_id"], "month": item["month"], "positive_probability": probability, "negative_probability": 1 - probability, "sentiment": to_three_class(probability), "primary_confidence": max(probability, 1 - probability), "snownlp_probability": snow_probability, "snownlp_sentiment": to_three_class(snow_probability)})
    return pd.DataFrame(rows), device


def make_topic_heatmap(sentiment: pd.DataFrame) -> None:
    topic_path = RESULTS_DIR / "topic_assignments.csv"
    if not topic_path.exists():
        return
    topics = pd.read_csv(topic_path, encoding="utf-8-sig")
    merged = topics[["comment_id", "interpreted_label", "is_outlier"]].merge(sentiment[["comment_id", "sentiment"]], on="comment_id", how="inner")
    merged = merged[~merged["is_outlier"].astype(str).str.lower().eq("true")]
    counts = pd.crosstab(merged["interpreted_label"], merged["sentiment"]).reindex(columns=["positive", "neutral", "negative"], fill_value=0)
    shares = counts.div(counts.sum(axis=1), axis=0).fillna(0)
    counts.add_suffix("_count").join(shares.add_suffix("_share")).rename_axis("theme").to_csv(RESULTS_DIR / "topic_sentiment_crosstab.csv", encoding="utf-8-sig")
    ordered = shares.loc[counts.sum(axis=1).sort_values(ascending=False).index]
    fig, axis = plt.subplots(figsize=(10.5, 5.6))
    sns.heatmap(ordered * 100, annot=True, fmt=".1f", cmap="RdYlGn", vmin=0, vmax=100, linewidths=.8, linecolor="white", cbar_kws={"label": "主题内占比（%）"}, ax=axis)
    axis.set_title("不同主题的情感构成", pad=12)
    axis.set_xlabel("")
    axis.set_ylabel("")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_09_topic_sentiment_heatmap.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-classifications", action="store_true")
    args = parser.parse_args()
    ensure_directories()
    set_reproducibility(RANDOM_SEED)
    configure_matplotlib()
    configure_jieba_cache()
    corpus = pd.read_csv(DATA_DIR / "chinese_comments.csv", encoding="utf-8-sig")
    assignments_path = RESULTS_DIR / "sentiment_assignments.csv"
    if args.reuse_classifications and assignments_path.exists():
        sentiment = pd.read_csv(assignments_path, encoding="utf-8-sig")
        device = "reused cached classifications"
    else:
        sentiment, device = infer_transformer(corpus)
        sentiment.to_csv(assignments_path, index=False, encoding="utf-8-sig")
    summary = sentiment["sentiment"].value_counts().reindex(["positive", "neutral", "negative"], fill_value=0).rename_axis("sentiment").reset_index(name="comment_count")
    summary["share"] = summary["comment_count"] / len(sentiment)
    summary.to_csv(RESULTS_DIR / "sentiment_summary.csv", index=False, encoding="utf-8-sig")
    agreement = (sentiment["sentiment"] == sentiment["snownlp_sentiment"]).mean()
    monthly = pd.crosstab(sentiment["month"], sentiment["sentiment"], normalize="index").reindex(columns=["positive", "neutral", "negative"], fill_value=0)
    monthly["comment_count"] = sentiment.groupby("month").size()
    monthly.to_csv(RESULTS_DIR / "monthly_sentiment.csv", encoding="utf-8-sig")

    sns.set_theme(style="whitegrid", font="Microsoft YaHei")
    colors = {"positive": "#238b45", "neutral": "#8c8c8c", "negative": "#cb181d"}
    label_cn = {"positive": "正面", "neutral": "中性", "negative": "负面"}
    chart_summary = summary.copy()
    chart_summary["情感"] = chart_summary["sentiment"].map(label_cn)
    fig, axis = plt.subplots(figsize=(7.6, 5))
    bars = axis.bar(chart_summary["情感"], chart_summary["comment_count"], color=[colors[value] for value in chart_summary["sentiment"]], edgecolor="white")
    axis.set_title("中文评论情感分布", pad=12)
    axis.set_xlabel("")
    axis.set_ylabel("评论数")
    for bar, share in zip(bars, chart_summary["share"]):
        axis.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{share:.1%}", ha="center", va="bottom")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_04_sentiment_distribution.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(10.5, 5.2))
    monthly[["positive", "neutral", "negative"]].rename(columns=label_cn).plot(kind="bar", stacked=True, color=[colors["positive"], colors["neutral"], colors["negative"]], width=.78, ax=axis)
    axis.set_title("月度情感占比（描述性展示）", pad=12)
    axis.set_xlabel("月份")
    axis.set_ylabel("占比")
    axis.legend(title="情感", bbox_to_anchor=(1.02, 1), loc="upper left", frameon=False)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_05_monthly_sentiment.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    merged = corpus[["comment_id", "normalized_text"]].merge(sentiment[["comment_id", "sentiment"]], on="comment_id")
    merged["content_terms"] = merged["normalized_text"].map(tokenized_content)
    for label, colormap in (("positive", "Greens"), ("negative", "Reds")):
        content = " ".join(merged.loc[merged["sentiment"] == label, "content_terms"].tolist())
        if content:
            WordCloud(font_path=CHINESE_FONT_PATH, width=1800, height=1000, background_color="white", colormap=colormap, collocations=False, prefer_horizontal=.92, margin=6).generate(content).to_file(str(FIGURES_DIR / f"fig_06_{label}_wordcloud.png"))
    vectorizer = TfidfVectorizer(tokenizer=str.split, token_pattern=None, preprocessor=None, lowercase=False, min_df=max(3, len(merged) // 400), ngram_range=(1, 2), max_features=4000)
    matrix = vectorizer.fit_transform(merged["content_terms"])
    features = vectorizer.get_feature_names_out()
    rows: list[dict[str, object]] = []
    for label in ("positive", "neutral", "negative"):
        scores = matrix[merged["sentiment"].eq(label).to_numpy()].mean(axis=0).A1
        for rank, index in enumerate(scores.argsort()[::-1][:30], start=1):
            rows.append({"sentiment": label, "rank": rank, "term": features[index], "mean_tfidf": scores[index]})
    pd.DataFrame(rows).to_csv(RESULTS_DIR / "sentiment_keywords.csv", index=False, encoding="utf-8-sig")
    make_topic_heatmap(sentiment)
    write_json(RESULTS_DIR / "sentiment_metadata.json", {"generated_at": utc_now(), "model": SENTIMENT_MODEL, "device": device, "positive_threshold": POSITIVE_THRESHOLD, "negative_threshold": NEGATIVE_THRESHOLD, "snownlp_agreement": agreement, "three_class_method": "binary positive probability with 0.40-0.60 neutral band"})
    print(f"Classified {len(sentiment):,} Chinese comments. Transformer/SnowNLP agreement: {agreement:.1%}.")


if __name__ == "__main__":
    main()
