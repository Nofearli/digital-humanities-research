"""Classify English comments and produce cleaned sentiment diagnostics."""

from __future__ import annotations

import argparse
import re

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from wordcloud import WordCloud

from pipeline_common import (
    DATA_DIR,
    FIGURES_DIR,
    MODELS_DIR,
    RANDOM_SEED,
    RESULTS_DIR,
    TIMES_NEW_ROMAN,
    configure_matplotlib,
    ensure_directories,
    set_reproducibility,
    utc_now,
    write_json,
)


SENTIMENT_MODEL = "cardiffnlp/twitter-roberta-base-sentiment-latest"
# Stop words are deliberately broader than a general English list.  They remove
# pronouns, auxiliaries, contractions and generic platform/title terms so that
# sentiment vocabulary reflects evaluative or topical content instead of syntax.
ANALYSIS_STOP_WORDS = set(ENGLISH_STOP_WORDS) | {
    "ne", "zha", "nezha", "movie", "movies", "film", "video", "youtube", "watch", "watching",
    "like", "just", "think", "good", "people", "time", "see", "know", "want", "thing", "really",
    "im", "ive", "id", "ill", "dont", "didnt", "doesnt", "cant", "wont", "wouldnt", "couldnt",
    "isnt", "arent", "wasnt", "werent", "youre", "youve", "youll", "thats", "its", "theres",
    "theyre", "theyve", "weve", "hes", "shes", "aint", "also", "still", "one", "something",
    "someone", "everything", "anything", "lot", "way", "got", "make", "made", "did", "does",
    "doing", "say", "said", "let", "come", "came", "going", "use", "used", "need", "give",
    "don", "didn", "doesn", "isn", "aren", "wasn", "weren", "wouldn", "couldn", "shouldn",
    "haven", "hasn", "hadn", "watch", "watched", "watches", "review", "reviews", "reviewing",
    "comment", "comments", "channel", "channels", "thank", "thanks", "bro", "jeremy",
}
# Country, regional and national-identity terms are analytically important for
# the topic/network stages, but are excluded from the two sentiment word clouds
# so that their visual emphasis falls on evaluative adjectives/adverbs and a
# small number of substantive nouns rather than geopolitical references.
GEOPOLITICAL_STOP_WORDS = {
    "china", "chinese", "ccp", "america", "american", "usa", "western", "west", "eastern",
    "asian", "asia", "east", "korea", "korean", "japan", "japanese", "india", "indian",
    "britain", "british", "england", "english", "europe", "european", "russia", "russian",
    "canada", "canadian", "australia", "australian", "france", "french", "germany", "german",
    "italy", "italian", "spain", "spanish", "mexico", "mexican", "brazil", "brazilian",
    "vietnam", "vietnamese", "thailand", "thai", "indonesia", "indonesian", "philippines",
    "filipino", "malaysia", "malaysian", "singapore", "singaporean", "taiwan", "taiwanese",
    "country", "countries", "government", "governments", "politic", "politics", "political", "policy",
    "policies", "nation", "nations", "national", "state", "states",
}
ANALYSIS_STOP_WORDS |= GEOPOLITICAL_STOP_WORDS
TOKEN_PATTERN = re.compile(r"[A-Za-z]{3,}")


def canonical_label(label: str) -> str:
    label = label.lower()
    if "neg" in label or label.endswith("0"):
        return "negative"
    if "neu" in label or label.endswith("1"):
        return "neutral"
    if "pos" in label or label.endswith("2"):
        return "positive"
    return label


def vader_label(score: float) -> str:
    return "positive" if score >= 0.05 else "negative" if score <= -0.05 else "neutral"


def content_terms(text: str) -> str:
    """Return a display/TF-IDF string free of pronouns and function words."""
    return " ".join(token.lower() for token in TOKEN_PATTERN.findall(text) if token.lower() not in ANALYSIS_STOP_WORDS)


def infer_sentiment(corpus: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    import torch

    device = 0 if torch.cuda.is_available() else -1
    tokenizer = AutoTokenizer.from_pretrained(SENTIMENT_MODEL, cache_dir=str(MODELS_DIR / "transformers"))
    model = AutoModelForSequenceClassification.from_pretrained(SENTIMENT_MODEL, cache_dir=str(MODELS_DIR / "transformers"))
    classifier = pipeline("sentiment-analysis", model=model, tokenizer=tokenizer, device=device, top_k=None, truncation=True, max_length=512)
    predictions = classifier(corpus["normalized_text"].tolist(), batch_size=64 if device == 0 else 16)
    vader = SentimentIntensityAnalyzer()
    rows: list[dict[str, object]] = []
    for (_, comment), scores in zip(corpus.iterrows(), predictions):
        scores = scores if isinstance(scores, list) else [scores]
        normalized_scores = {canonical_label(item["label"]): float(item["score"]) for item in scores}
        primary = max(normalized_scores, key=normalized_scores.get)
        compound = vader.polarity_scores(comment["normalized_text"])["compound"]
        rows.append(
            {
                "comment_id": comment["comment_id"], "month": comment["month"], "sentiment": primary,
                "negative_probability": normalized_scores.get("negative", 0.0),
                "neutral_probability": normalized_scores.get("neutral", 0.0),
                "positive_probability": normalized_scores.get("positive", 0.0),
                "primary_confidence": normalized_scores[primary], "vader_compound": compound,
                "vader_sentiment": vader_label(compound),
            }
        )
    return pd.DataFrame(rows), "cuda" if device == 0 else "cpu"


def make_topic_sentiment_table(sentiment: pd.DataFrame) -> None:
    topics_path = RESULTS_DIR / "topic_assignments.csv"
    if not topics_path.exists():
        return
    topics = pd.read_csv(topics_path, encoding="utf-8-sig")
    merged = topics[["comment_id", "topic_id", "chart_label", "is_outlier"]].merge(
        sentiment[["comment_id", "sentiment"]], on="comment_id", how="inner"
    )
    non_outlier = merged[~merged["is_outlier"].astype(str).str.lower().eq("true")].copy()
    counts = pd.crosstab(non_outlier["chart_label"], non_outlier["sentiment"]).reindex(
        columns=["positive", "neutral", "negative"], fill_value=0
    )
    shares = counts.div(counts.sum(axis=1), axis=0).fillna(0)
    output = counts.add_suffix("_count").join(shares.add_suffix("_share"))
    output.index.name = "theme"
    output.to_csv(RESULTS_DIR / "topic_sentiment_crosstab.csv", encoding="utf-8-sig")
    ordered = shares.loc[counts.sum(axis=1).sort_values(ascending=False).index]
    fig, axis = plt.subplots(figsize=(11.5, 5.8))
    sns.heatmap(ordered * 100, annot=True, fmt=".1f", cmap="RdYlGn", vmin=0, vmax=100, linewidths=0.8,
                linecolor="white", cbar_kws={"label": "Share within theme (%)"}, ax=axis)
    axis.set_title("Sentiment composition within BERTopic themes", pad=12)
    axis.set_xlabel("")
    axis.set_ylabel("")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_09_topic_sentiment_heatmap.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-classifications", action="store_true", help="Reuse existing transformer predictions and redraw outputs.")
    args = parser.parse_args()
    ensure_directories()
    set_reproducibility(RANDOM_SEED)
    configure_matplotlib()
    corpus = pd.read_csv(DATA_DIR / "english_comments.csv", encoding="utf-8-sig")
    assignment_path = RESULTS_DIR / "sentiment_assignments.csv"
    if args.reuse_classifications and assignment_path.exists():
        sentiment = pd.read_csv(assignment_path, encoding="utf-8-sig")
        model_device = "reused cached classifications"
    else:
        sentiment, model_device = infer_sentiment(corpus)
        sentiment.to_csv(assignment_path, index=False, encoding="utf-8-sig")

    summary = sentiment["sentiment"].value_counts().reindex(["positive", "neutral", "negative"], fill_value=0).rename_axis("sentiment").reset_index(name="comment_count")
    summary["share"] = summary["comment_count"] / len(sentiment)
    summary.to_csv(RESULTS_DIR / "sentiment_summary.csv", index=False, encoding="utf-8-sig")
    agreement = (sentiment["sentiment"] == sentiment["vader_sentiment"]).mean()
    monthly = pd.crosstab(sentiment["month"], sentiment["sentiment"], normalize="index").reindex(columns=["positive", "neutral", "negative"], fill_value=0)
    monthly["comment_count"] = sentiment.groupby("month").size()
    monthly.to_csv(RESULTS_DIR / "monthly_sentiment.csv", encoding="utf-8-sig")

    sns.set_theme(style="whitegrid", font=TIMES_NEW_ROMAN)
    fig, axis = plt.subplots(figsize=(8, 5))
    palette = {"positive": "#238b45", "neutral": "#8c8c8c", "negative": "#cb181d"}
    sns.barplot(data=summary, x="sentiment", y="comment_count", hue="sentiment", dodge=False, palette=palette, legend=False, ax=axis)
    axis.set_title("Sentiment distribution of English comments", pad=12)
    axis.set_xlabel("")
    axis.set_ylabel("Comments")
    for bar, share in zip(axis.patches, summary["share"]):
        axis.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{share:.1%}", ha="center", va="bottom")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_04_sentiment_distribution.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(10.5, 5.2))
    monthly[["positive", "neutral", "negative"]].plot(kind="bar", stacked=True, color=[palette["positive"], palette["neutral"], palette["negative"]], width=0.78, ax=axis)
    axis.set_title("Monthly sentiment shares (descriptive only)", pad=12)
    axis.set_xlabel("Month")
    axis.set_ylabel("Share")
    axis.legend(title="Sentiment", bbox_to_anchor=(1.02, 1), loc="upper left", frameon=False)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_05_monthly_sentiment.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    merged = corpus[["comment_id", "normalized_text"]].merge(sentiment[["comment_id", "sentiment"]], on="comment_id")
    merged["content_terms"] = merged["normalized_text"].map(content_terms)
    keyword_rows: list[dict[str, object]] = []
    for label, color in (("positive", "#238b45"), ("negative", "#cb181d")):
        texts = merged.loc[merged["sentiment"] == label, "content_terms"]
        display_text = " ".join(text for text in texts if text.strip())
        if display_text:
            cloud = WordCloud(width=1800, height=1000, background_color="white", colormap="Greens" if label == "positive" else "Reds", stopwords=ANALYSIS_STOP_WORDS, font_path="C:\\Windows\\Fonts\\times.ttf", prefer_horizontal=0.92, collocations=False, margin=6).generate(display_text)
            cloud.to_file(str(FIGURES_DIR / f"fig_06_{label}_wordcloud.png"))
    vectorizer = TfidfVectorizer(stop_words=sorted(ANALYSIS_STOP_WORDS), token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z]+\b", ngram_range=(1, 2), min_df=max(3, len(merged) // 500), max_features=4000)
    matrix = vectorizer.fit_transform(merged["content_terms"])
    features = vectorizer.get_feature_names_out()
    for label in ("positive", "neutral", "negative"):
        score = matrix[merged["sentiment"].eq(label).to_numpy()].mean(axis=0).A1
        for rank, index in enumerate(score.argsort()[::-1][:30], start=1):
            keyword_rows.append({"sentiment": label, "rank": rank, "term": features[index], "mean_tfidf": score[index]})
    pd.DataFrame(keyword_rows).to_csv(RESULTS_DIR / "sentiment_keywords.csv", index=False, encoding="utf-8-sig")
    make_topic_sentiment_table(sentiment)
    write_json(RESULTS_DIR / "sentiment_metadata.json", {"generated_at": utc_now(), "model": SENTIMENT_MODEL, "device": model_device, "vader_agreement": agreement, "removed_display_stopwords": sorted(ANALYSIS_STOP_WORDS)})
    print(f"Classified {len(sentiment):,} comments. Transformer/VADER agreement: {agreement:.1%}.")


if __name__ == "__main__":
    main()
