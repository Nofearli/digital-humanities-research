"""Discover themes in the cleaned English corpus with BERTopic."""

from __future__ import annotations

from collections import Counter

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from bertopic import BERTopic
from hdbscan import HDBSCAN
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, CountVectorizer
from umap import UMAP

from pipeline_common import (
    DATA_DIR,
    FIGURES_DIR,
    MODELS_DIR,
    RANDOM_SEED,
    RESULTS_DIR,
    configure_matplotlib,
    ensure_directories,
    set_reproducibility,
    utc_now,
    write_json,
)


EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TARGET_TOPICS = 8
# All labels inside figures use English in a Times New Roman-safe style. Chinese
# interpretations are provided by the Word report rather than matplotlib.
DOMAIN_STOP_WORDS = {
    "ne", "zha", "nezha", "movie", "movies", "film", "video", "youtube",
    "watch", "watching", "like", "just", "think", "good", "people", "time",
    "see", "know", "want", "thing", "really", "im", "ive", "dont", "didnt",
    "doesnt", "cant", "wont", "youre", "thats", "its", "theres", "also",
    "still", "would", "could", "should", "one",
}
INTERPRETED_TOPIC_LABELS = {
    0: "Viewing, value and growth",
    1: "Animation quality and review interaction",
    2: "China, Hollywood and industry competition",
    3: "Creator interaction and wellbeing",
    4: "Narrative, characters and visual interpretation",
    5: "Ugly-duckling metaphor and identity",
    6: "East Asian culture, pronunciation and identity",
}


def topic_label(words: list[tuple[str, float]]) -> str:
    return " | ".join(word for word, _ in words[:4])


def main() -> None:
    ensure_directories()
    set_reproducibility(RANDOM_SEED)
    configure_matplotlib()
    corpus = pd.read_csv(DATA_DIR / "english_comments.csv", encoding="utf-8-sig")
    documents = corpus["normalized_text"].tolist()
    if len(documents) < 100:
        raise RuntimeError("Fewer than 100 English comments remain after cleaning; topic analysis is not reliable.")

    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    encoder = SentenceTransformer(
        EMBEDDING_MODEL, cache_folder=str(MODELS_DIR / "sentence_transformers"), device=device
    )
    embeddings = encoder.encode(
        documents, batch_size=64 if device == "cuda" else 16, show_progress_bar=True, normalize_embeddings=True
    )
    np.save(RESULTS_DIR / "document_embeddings.npy", embeddings)
    min_topic_size = 20
    vectorizer = CountVectorizer(
        stop_words=sorted(ENGLISH_STOP_WORDS | DOMAIN_STOP_WORDS),
        ngram_range=(1, 2),
        min_df=max(3, len(documents) // 1000),
    )
    umap_model = UMAP(n_neighbors=15, n_components=5, min_dist=0.0, metric="cosine", random_state=RANDOM_SEED)
    hdbscan_model = HDBSCAN(
        min_cluster_size=min_topic_size,
        min_samples=3,
        metric="euclidean",
        cluster_selection_method="eom",
        prediction_data=True,
    )
    topic_model = BERTopic(
        embedding_model=None,
        min_topic_size=min_topic_size,
        nr_topics=TARGET_TOPICS,
        vectorizer_model=vectorizer,
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        calculate_probabilities=False,
        verbose=True,
    )
    topics, _ = topic_model.fit_transform(documents, embeddings)
    topic_info = topic_model.get_topic_info().rename(
        columns={"Topic": "topic_id", "Count": "comment_count", "Name": "model_name"}
    )
    topic_info["is_outlier"] = topic_info["topic_id"].eq(-1)

    keyword_rows: list[dict[str, object]] = []
    for topic_id in topic_info.loc[~topic_info["is_outlier"], "topic_id"]:
        for rank, (word, score) in enumerate(topic_model.get_topic(int(topic_id)) or [], start=1):
            if rank > 10:
                break
            keyword_rows.append({"topic_id": topic_id, "rank": rank, "keyword": word, "c_tf_idf_score": score})
    keywords = pd.DataFrame(keyword_rows)
    topic_info["keyword_label"] = [
        "Outlier / mixed" if row.topic_id == -1 else topic_label(topic_model.get_topic(int(row.topic_id)) or [])
        for row in topic_info.itertuples()
    ]
    topic_info["interpreted_label"] = topic_info["topic_id"].map(INTERPRETED_TOPIC_LABELS).fillna("Outlier / mixed")
    topic_info["chart_label"] = topic_info["interpreted_label"]

    assignments = corpus.copy()
    assignments["topic_id"] = topics
    assignments = assignments.merge(
        topic_info[["topic_id", "keyword_label", "interpreted_label", "chart_label", "is_outlier"]],
        on="topic_id",
        how="left",
    )
    representatives: list[dict[str, object]] = []
    for topic_id in topic_info.loc[~topic_info["is_outlier"], "topic_id"]:
        examples = assignments[assignments["topic_id"] == topic_id].sort_values("like_count", ascending=False).head(5)
        for rank, (_, row) in enumerate(examples.iterrows(), start=1):
            representatives.append({"topic_id": topic_id, "rank": rank, "comment_id": row["comment_id"], "quote": row["text"][:300]})

    topic_info.to_csv(RESULTS_DIR / "topic_summary.csv", index=False, encoding="utf-8-sig")
    keywords.to_csv(RESULTS_DIR / "topic_keywords.csv", index=False, encoding="utf-8-sig")
    assignments.to_csv(RESULTS_DIR / "topic_assignments.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(representatives).to_csv(RESULTS_DIR / "topic_representative_quotes.csv", index=False, encoding="utf-8-sig")
    topic_model.save(RESULTS_DIR / "bertopic_model", serialization="safetensors", save_ctfidf=True, save_embedding_model=False)

    visible = topic_info[~topic_info["is_outlier"]].sort_values("comment_count", ascending=True).tail(12)
    sns.set_theme(style="whitegrid", font="Times New Roman")
    palette = sns.color_palette("Blues_r", n_colors=len(visible) + 2)[1:]
    fig, axis = plt.subplots(figsize=(11.5, 6.7))
    bars = axis.barh(visible["chart_label"], visible["comment_count"], color=palette, edgecolor="white", linewidth=0.7)
    axis.set_title("Largest BERTopic themes in English comments", pad=12)
    axis.set_xlabel("Comments")
    axis.set_ylabel("")
    axis.grid(axis="x", color="#d9dee7", linewidth=0.8)
    axis.grid(axis="y", visible=False)
    axis.set_axisbelow(True)
    for bar, value in zip(bars, visible["comment_count"]):
        axis.text(value + max(visible["comment_count"]) * 0.012, bar.get_y() + bar.get_height() / 2, f"{value:,}", va="center")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_02_topic_sizes.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    reducer = UMAP(n_neighbors=15, n_components=2, min_dist=0.05, metric="cosine", random_state=RANDOM_SEED)
    sample = assignments.sample(min(3000, len(assignments)), random_state=RANDOM_SEED).copy()
    points = reducer.fit_transform(embeddings[sample.index.to_numpy()])
    sample["umap_1"], sample["umap_2"] = points[:, 0], points[:, 1]
    fig, axis = plt.subplots(figsize=(11, 7.5))
    scatter = axis.scatter(sample["umap_1"], sample["umap_2"], c=sample["topic_id"], cmap="tab20", s=9, alpha=0.62, linewidths=0)
    axis.set_title("English comments: topic-space projection", pad=12)
    axis.set_xlabel("UMAP dimension 1")
    axis.set_ylabel("UMAP dimension 2")
    fig.colorbar(scatter, ax=axis, label="Topic ID")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_03_topic_umap.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    write_json(
        RESULTS_DIR / "topic_metadata.json",
        {
            "generated_at": utc_now(), "documents": len(documents), "embedding_model": EMBEDDING_MODEL,
            "device": device, "min_topic_size": min_topic_size, "target_topics": TARGET_TOPICS,
            "topics_including_outlier": len(topic_info), "topic_counts": dict(Counter(topics)),
            "domain_and_function_stopwords_removed": sorted(DOMAIN_STOP_WORDS),
        },
    )
    print(f"BERTopic created {len(topic_info) - 1} non-outlier themes on {len(documents):,} English comments.")


if __name__ == "__main__":
    main()
