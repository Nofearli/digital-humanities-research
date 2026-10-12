"""Discover Chinese-comment themes with jieba, BGE embeddings and BERTopic."""

from __future__ import annotations

from collections import Counter
import re

import jieba
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from umap import UMAP

from pipeline_common import DATA_DIR, FIGURES_DIR, MODELS_DIR, RANDOM_SEED, RESULTS_DIR, configure_jieba_cache, configure_matplotlib, ensure_directories, set_reproducibility, utc_now, write_json


EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
TARGET_TOPICS = 8
INTERPRETED_TOPIC_LABELS = {
    0: "票房、家庭与作品价值评价",
    1: "中国电影、票房与上映传播",
    2: "“我命由我”与文化体制隐喻",
    3: "第三部、封神榜与角色延展讨论",
    4: "导演、影评与剧情质量争议",
    5: "台港及海外上映、配音与文化传播",
    6: "影评创作者互动与支持表达",
    7: "太乙真人设定与前作剧情衔接",
}
STOP_WORDS = {
    "的", "了", "是", "我", "你", "他", "她", "它", "我们", "你们", "他们", "这", "那", "这个", "那个", "一个", "没有", "就是", "真的", "感觉", "觉得", "看到", "看了", "看过", "一下", "还是", "可以", "什么", "怎么", "因为", "所以", "如果", "但是", "而且", "以及", "然后", "现在", "已经", "非常", "比较", "很多", "太", "很", "都", "也", "还", "又", "被", "把", "在", "和", "与", "对", "给", "让", "从", "到", "着", "啊", "呀", "吧", "吗", "呢", "哦", "哈哈", "哈哈哈", "哈哈哈哈", "up", "啊啊", "哪吒", "哪吒2", "魔童", "闹海", "电影", "影片", "视频", "评论", "youtube", "油管", "观看", "观影", "看", "作品", "第二部", "续集",
}
CJK_TOKEN = re.compile(r"[\u4e00-\u9fff]")


def tokenize(text: str) -> str:
    return " ".join(token.strip() for token in jieba.lcut(text) if len(token.strip()) >= 2 and CJK_TOKEN.search(token.strip()) and token.strip() not in STOP_WORDS and not token.strip().isdigit())


def keyword_label(words: list[tuple[str, float]]) -> str:
    return "、".join(word for word, _ in words[:4])


def main() -> None:
    ensure_directories()
    set_reproducibility(RANDOM_SEED)
    configure_matplotlib()
    configure_jieba_cache()
    corpus = pd.read_csv(DATA_DIR / "chinese_comments.csv", encoding="utf-8-sig")
    if len(corpus) < 100:
        raise RuntimeError("Fewer than 100 Chinese comments remain after cleaning; topic analysis is not reliable.")
    documents = corpus["normalized_text"].tolist()
    tokenized = [tokenize(text) for text in documents]
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    encoder = SentenceTransformer(EMBEDDING_MODEL, cache_folder=str(MODELS_DIR / "sentence_transformers"), device=device)
    embeddings = encoder.encode(documents, batch_size=64 if device == "cuda" else 16, show_progress_bar=True, normalize_embeddings=True)
    np.save(RESULTS_DIR / "document_embeddings.npy", embeddings)
    min_topic_size = 15
    # BERTopic fits this vectorizer on the small set of aggregated topic
    # documents, so min_df must remain one rather than corpus-level frequency.
    vectorizer = CountVectorizer(tokenizer=str.split, token_pattern=None, preprocessor=None, lowercase=False, min_df=1, ngram_range=(1, 2))
    # Fixed-k clustering avoids the initial HDBSCAN solution's one oversized
    # mixed cluster and several 15-20-comment noise clusters on this corpus.
    topic_model = BERTopic(embedding_model=None, min_topic_size=min_topic_size, nr_topics=None, vectorizer_model=vectorizer, umap_model=UMAP(n_neighbors=20, n_components=8, min_dist=.05, metric="cosine", random_state=RANDOM_SEED), hdbscan_model=KMeans(n_clusters=TARGET_TOPICS, random_state=RANDOM_SEED, n_init=20), calculate_probabilities=False, verbose=True)
    topics, _ = topic_model.fit_transform(tokenized, embeddings)
    info = topic_model.get_topic_info().rename(columns={"Topic": "topic_id", "Count": "comment_count", "Name": "model_name"})
    info["is_outlier"] = info["topic_id"].eq(-1)
    # Extract cluster keywords independently from BERTopic's representation
    # layer. This preserves meaningful Chinese tokens when a fixed-k clusterer
    # is used and records the exact mean TF-IDF score for every keyword.
    keyword_vectorizer = TfidfVectorizer(tokenizer=str.split, token_pattern=None, preprocessor=None, lowercase=False, min_df=1, ngram_range=(1, 2))
    keyword_matrix = keyword_vectorizer.fit_transform(tokenized)
    keyword_features = keyword_vectorizer.get_feature_names_out()
    rows: list[dict[str, object]] = []
    label_map: dict[int, str] = {}
    topic_array = np.asarray(topics)
    for topic_id in info.loc[~info["is_outlier"], "topic_id"]:
        scores = keyword_matrix[topic_array == int(topic_id)].mean(axis=0).A1
        top_indices = scores.argsort()[::-1][:10]
        words = [(keyword_features[index], float(scores[index])) for index in top_indices if scores[index] > 0]
        label_map[int(topic_id)] = keyword_label(words)
        for rank, (word, score) in enumerate(words, start=1):
            rows.append({"topic_id": topic_id, "rank": rank, "keyword": word, "c_tf_idf_score": score})
    info["keyword_label"] = ["离群或混合评论" if row.topic_id == -1 else label_map.get(int(row.topic_id), "未命名主题") for row in info.itertuples()]
    info["interpreted_label"] = info["topic_id"].map(INTERPRETED_TOPIC_LABELS).fillna(info["keyword_label"])
    assignments = corpus.copy()
    assignments["topic_id"] = topics
    assignments = assignments.merge(info[["topic_id", "keyword_label", "interpreted_label", "is_outlier"]], on="topic_id", how="left")
    representatives: list[dict[str, object]] = []
    for topic_id in info.loc[~info["is_outlier"], "topic_id"]:
        examples = assignments[assignments["topic_id"] == topic_id].sort_values("like_count", ascending=False).head(5)
        for rank, (_, item) in enumerate(examples.iterrows(), start=1):
            representatives.append({"topic_id": topic_id, "rank": rank, "comment_id": item["comment_id"], "quote": item["text"][:300]})
    info.to_csv(RESULTS_DIR / "topic_summary.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(rows).to_csv(RESULTS_DIR / "topic_keywords.csv", index=False, encoding="utf-8-sig")
    assignments.to_csv(RESULTS_DIR / "topic_assignments.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(representatives).to_csv(RESULTS_DIR / "topic_representative_quotes.csv", index=False, encoding="utf-8-sig")
    topic_model.save(RESULTS_DIR / "bertopic_model", serialization="safetensors", save_ctfidf=True, save_embedding_model=False)

    visible = info[~info["is_outlier"]].sort_values("comment_count", ascending=True).tail(12)
    sns.set_theme(style="whitegrid", font="Microsoft YaHei")
    fig, axis = plt.subplots(figsize=(11, 6.7))
    bars = axis.barh(visible["interpreted_label"], visible["comment_count"], color=sns.color_palette("Blues_r", n_colors=len(visible) + 2)[1:], edgecolor="white")
    axis.set_title("中文评论的 BERTopic 主要主题", pad=12)
    axis.set_xlabel("评论数")
    axis.set_ylabel("")
    axis.grid(axis="y", visible=False)
    for bar, value in zip(bars, visible["comment_count"]):
        axis.text(value + max(visible["comment_count"]) * 0.012, bar.get_y() + bar.get_height() / 2, f"{value:,}", va="center")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_02_topic_sizes.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    sample = assignments.sample(min(2500, len(assignments)), random_state=RANDOM_SEED).copy()
    points = UMAP(n_neighbors=15, n_components=2, min_dist=0.05, metric="cosine", random_state=RANDOM_SEED).fit_transform(embeddings[sample.index.to_numpy()])
    sample["umap_1"], sample["umap_2"] = points[:, 0], points[:, 1]
    fig, axis = plt.subplots(figsize=(10.5, 7.5))
    scatter = axis.scatter(sample["umap_1"], sample["umap_2"], c=sample["topic_id"], cmap="tab20", s=10, alpha=0.62, linewidths=0)
    axis.set_title("中文评论主题空间二维投影", pad=12)
    axis.set_xlabel("UMAP 维度 1")
    axis.set_ylabel("UMAP 维度 2")
    fig.colorbar(scatter, ax=axis, label="主题编号")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_03_topic_umap.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    write_json(RESULTS_DIR / "topic_metadata.json", {"generated_at": utc_now(), "documents": len(documents), "embedding_model": EMBEDDING_MODEL, "device": device, "min_topic_size": min_topic_size, "target_topics": TARGET_TOPICS, "topic_counts": dict(Counter(topics)), "stop_words": sorted(STOP_WORDS)})
    print(f"BERTopic created {(~info['is_outlier']).sum()} non-outlier themes on {len(documents):,} Chinese comments.")


if __name__ == "__main__":
    main()
