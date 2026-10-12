"""Build a weighted semantic co-occurrence network for English comments."""

from __future__ import annotations

from collections import Counter
from itertools import combinations

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import spacy

from pipeline_common import DATA_DIR, FIGURES_DIR, RANDOM_SEED, RESULTS_DIR, TIMES_NEW_ROMAN, configure_matplotlib, ensure_directories, set_reproducibility, utc_now, write_json


WINDOW_SIZE = 5
TOP_TERMS = 60
TOP_EDGES = 180
DOMAIN_STOP_WORDS = {"ne", "zha", "nezha", "movie", "movies", "film", "video", "youtube", "watch", "watching", "like", "just", "think", "good", "people", "time", "see", "know", "want", "thing", "really", "im", "ive", "dont", "didnt", "doesnt", "cant", "wont", "youre", "thats", "its", "theres", "also", "still", "would", "could", "should", "one", "say", "said", "make", "made", "doing"}


def load_nlp():
    try:
        return spacy.load("en_core_web_sm", disable=["ner", "parser"])
    except OSError as exc:
        raise RuntimeError("Missing spaCy English model. Run: python -m spacy download en_core_web_sm") from exc


def main() -> None:
    ensure_directories()
    set_reproducibility(RANDOM_SEED)
    configure_matplotlib()
    corpus = pd.read_csv(DATA_DIR / "english_comments.csv", encoding="utf-8-sig")
    nlp = load_nlp()
    token_lists: list[list[str]] = []
    document_frequency: Counter[str] = Counter()
    for document in nlp.pipe(corpus["normalized_text"].tolist(), batch_size=128):
        tokens = [
            token.lemma_.lower()
            for token in document
            if token.is_alpha and not token.is_stop and token.lemma_.lower() not in DOMAIN_STOP_WORDS and len(token.lemma_) >= 3 and token.pos_ in {"NOUN", "PROPN", "ADJ", "VERB"}
        ]
        token_lists.append(tokens)
        document_frequency.update(set(tokens))
    minimum_document_frequency = max(8, len(corpus) // 200)
    vocabulary = {
        term
        for term, frequency in document_frequency.most_common()
        if frequency >= minimum_document_frequency
    }
    vocabulary = set(sorted(vocabulary, key=lambda term: (-document_frequency[term], term))[:TOP_TERMS])
    edge_counts: Counter[tuple[str, str]] = Counter()
    for tokens in token_lists:
        filtered = [token for token in tokens if token in vocabulary]
        for start in range(len(filtered)):
            window = filtered[start + 1 : start + WINDOW_SIZE]
            for partner in window:
                if filtered[start] != partner:
                    edge_counts[tuple(sorted((filtered[start], partner)))] += 1
    retained_edges = edge_counts.most_common(TOP_EDGES)
    graph = nx.Graph()
    for term in vocabulary:
        graph.add_node(term, document_frequency=document_frequency[term])
    for (source, target), weight in retained_edges:
        graph.add_edge(source, target, weight=weight)
    graph.remove_nodes_from(list(nx.isolates(graph)))
    try:
        communities = list(nx.community.louvain_communities(graph, weight="weight", seed=RANDOM_SEED))
    except AttributeError:
        communities = list(nx.community.greedy_modularity_communities(graph, weight="weight"))
    membership = {node: index for index, group in enumerate(communities) for node in group}
    weighted_degree = dict(graph.degree(weight="weight"))
    betweenness = nx.betweenness_centrality(graph, weight="weight", normalized=True)
    nodes = pd.DataFrame(
        [
            {"term": node, "document_frequency": graph.nodes[node]["document_frequency"], "weighted_degree": weighted_degree[node], "betweenness": betweenness[node], "community": membership[node]}
            for node in graph.nodes
        ]
    ).sort_values("weighted_degree", ascending=False)
    edges = pd.DataFrame([{"source": source, "target": target, "weight": attrs["weight"]} for source, target, attrs in graph.edges(data=True)]).sort_values("weight", ascending=False)
    nodes.to_csv(RESULTS_DIR / "network_nodes.csv", index=False, encoding="utf-8-sig")
    edges.to_csv(RESULTS_DIR / "network_edges.csv", index=False, encoding="utf-8-sig")
    nodes.head(25).to_csv(RESULTS_DIR / "network_centrality_top25.csv", index=False, encoding="utf-8-sig")

    position = nx.spring_layout(graph, seed=RANDOM_SEED, k=1.2 / max(1, graph.number_of_nodes() ** 0.5), weight="weight", iterations=150)
    fig, axis = plt.subplots(figsize=(14, 10.5))
    nx.draw_networkx_edges(graph, position, width=[0.3 + data["weight"] / max(1, edges["weight"].max()) * 2.7 for _, _, data in graph.edges(data=True)], alpha=0.22, edge_color="#64748b", ax=axis)
    nx.draw_networkx_nodes(graph, position, node_size=[95 + weighted_degree[node] * 9 for node in graph.nodes], node_color=[membership[node] for node in graph.nodes], cmap="tab20", alpha=0.94, linewidths=0.5, edgecolors="white", ax=axis)
    nx.draw_networkx_labels(graph, position, font_size=8.5, font_family=TIMES_NEW_ROMAN, font_weight="bold", ax=axis)
    axis.set_title("Semantic co-occurrence network of English Ne Zha 2 comments", pad=14)
    axis.axis("off")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_07_semantic_network.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    top = nodes.head(15).sort_values("weighted_degree")
    fig, axis = plt.subplots(figsize=(9.5, 6.2))
    bars = axis.barh(top["term"], top["weighted_degree"], color="#5b4b8a", edgecolor="white", linewidth=0.7)
    axis.set_title("Most central semantic-network terms", pad=12)
    axis.set_xlabel("Weighted degree")
    axis.set_ylabel("")
    fig.tight_layout()
    for bar, value in zip(bars, top["weighted_degree"]):
        axis.text(value + max(top["weighted_degree"]) * 0.01, bar.get_y() + bar.get_height() / 2, f"{value:,.0f}", va="center")
    fig.savefig(FIGURES_DIR / "fig_08_network_centrality.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    write_json(RESULTS_DIR / "network_metadata.json", {"generated_at": utc_now(), "comments": len(corpus), "nodes": graph.number_of_nodes(), "edges": graph.number_of_edges(), "communities": len(communities), "window_size": WINDOW_SIZE})
    print(f"Created semantic network with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges.")


if __name__ == "__main__":
    main()
