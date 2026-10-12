"""Build a weighted Chinese semantic co-occurrence network."""

from __future__ import annotations

from collections import Counter
import re

import jieba.posseg as pseg
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

from pipeline_common import DATA_DIR, FIGURES_DIR, RANDOM_SEED, RESULTS_DIR, configure_jieba_cache, configure_matplotlib, ensure_directories, set_reproducibility, utc_now, write_json


WINDOW_SIZE = 5
TOP_TERMS = 60
TOP_EDGES = 180
STOP_WORDS = {"的", "了", "是", "我", "你", "他", "她", "它", "我们", "你们", "他们", "这", "那", "这个", "那个", "一个", "没有", "就是", "真的", "感觉", "觉得", "看到", "看了", "看过", "一下", "还是", "可以", "什么", "怎么", "因为", "所以", "如果", "但是", "而且", "以及", "然后", "现在", "已经", "非常", "比较", "很多", "太", "很", "都", "也", "还", "又", "被", "把", "在", "和", "与", "对", "给", "让", "从", "到", "着", "啊", "呀", "吧", "吗", "呢", "哦", "哈哈", "哈哈哈", "哪吒", "哪吒2", "魔童", "闹海", "电影", "影片", "视频", "评论", "youtube", "油管", "观看", "观影", "看", "作品", "第二部", "续集"}
KEEP_POS_PREFIXES = ("n", "v", "a")
CJK_TOKEN = re.compile(r"[\u4e00-\u9fff]")


def content_tokens(text: str) -> list[str]:
    return [pair.word.strip() for pair in pseg.cut(text) if len(pair.word.strip()) >= 2 and CJK_TOKEN.search(pair.word.strip()) and pair.word.strip() not in STOP_WORDS and pair.flag.startswith(KEEP_POS_PREFIXES) and not pair.word.strip().isdigit()]


def main() -> None:
    ensure_directories()
    set_reproducibility(RANDOM_SEED)
    configure_matplotlib()
    configure_jieba_cache()
    corpus = pd.read_csv(DATA_DIR / "chinese_comments.csv", encoding="utf-8-sig")
    token_lists: list[list[str]] = []
    document_frequency: Counter[str] = Counter()
    for text in corpus["normalized_text"]:
        tokens = content_tokens(text)
        token_lists.append(tokens)
        document_frequency.update(set(tokens))
    minimum_df = max(8, len(corpus) // 200)
    vocabulary = set(sorted((term for term, count in document_frequency.items() if count >= minimum_df), key=lambda term: (-document_frequency[term], term))[:TOP_TERMS])
    edges: Counter[tuple[str, str]] = Counter()
    for tokens in token_lists:
        filtered = [token for token in tokens if token in vocabulary]
        for index, token in enumerate(filtered):
            for partner in filtered[index + 1:index + WINDOW_SIZE]:
                if token != partner:
                    edges[tuple(sorted((token, partner)))] += 1
    graph = nx.Graph()
    for term in vocabulary:
        graph.add_node(term, document_frequency=document_frequency[term])
    for (source, target), weight in edges.most_common(TOP_EDGES):
        graph.add_edge(source, target, weight=weight)
    graph.remove_nodes_from(list(nx.isolates(graph)))
    try:
        communities = list(nx.community.louvain_communities(graph, weight="weight", seed=RANDOM_SEED))
    except AttributeError:
        communities = list(nx.community.greedy_modularity_communities(graph, weight="weight"))
    membership = {node: index for index, community in enumerate(communities) for node in community}
    weighted_degree = dict(graph.degree(weight="weight"))
    betweenness = nx.betweenness_centrality(graph, weight="weight", normalized=True)
    nodes = pd.DataFrame([{"term": node, "document_frequency": graph.nodes[node]["document_frequency"], "weighted_degree": weighted_degree[node], "betweenness": betweenness[node], "community": membership[node]} for node in graph.nodes]).sort_values("weighted_degree", ascending=False)
    edge_frame = pd.DataFrame([{"source": source, "target": target, "weight": data["weight"]} for source, target, data in graph.edges(data=True)]).sort_values("weight", ascending=False)
    nodes.to_csv(RESULTS_DIR / "network_nodes.csv", index=False, encoding="utf-8-sig")
    edge_frame.to_csv(RESULTS_DIR / "network_edges.csv", index=False, encoding="utf-8-sig")
    nodes.head(25).to_csv(RESULTS_DIR / "network_centrality_top25.csv", index=False, encoding="utf-8-sig")

    position = nx.spring_layout(graph, seed=RANDOM_SEED, k=1.2 / max(1, graph.number_of_nodes() ** .5), weight="weight", iterations=150)
    fig, axis = plt.subplots(figsize=(14, 10.5))
    nx.draw_networkx_edges(graph, position, width=[.3 + data["weight"] / max(1, edge_frame["weight"].max()) * 2.7 for _, _, data in graph.edges(data=True)], alpha=.22, edge_color="#64748b", ax=axis)
    nx.draw_networkx_nodes(graph, position, node_size=[95 + weighted_degree[node] * 9 for node in graph.nodes], node_color=[membership[node] for node in graph.nodes], cmap="tab20", alpha=.94, linewidths=.5, edgecolors="white", ax=axis)
    nx.draw_networkx_labels(graph, position, font_size=9, font_family="Microsoft YaHei", font_weight="bold", ax=axis)
    axis.set_title("中文评论内容词语义共现网络", pad=14)
    axis.axis("off")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_07_semantic_network.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    top = nodes.head(15).sort_values("weighted_degree")
    fig, axis = plt.subplots(figsize=(9.5, 6.2))
    bars = axis.barh(top["term"], top["weighted_degree"], color="#5b4b8a", edgecolor="white")
    axis.set_title("语义网络中连接度最高的概念", pad=12)
    axis.set_xlabel("加权度")
    axis.set_ylabel("")
    for bar, value in zip(bars, top["weighted_degree"]):
        axis.text(value + max(top["weighted_degree"]) * .01, bar.get_y() + bar.get_height() / 2, f"{value:,.0f}", va="center")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "fig_08_network_centrality.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    write_json(RESULTS_DIR / "network_metadata.json", {"generated_at": utc_now(), "comments": len(corpus), "nodes": graph.number_of_nodes(), "edges": graph.number_of_edges(), "communities": len(communities), "window_size": WINDOW_SIZE, "stop_words": sorted(STOP_WORDS)})
    print(f"Created Chinese semantic network with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges.")


if __name__ == "__main__":
    main()
