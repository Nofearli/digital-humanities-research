# 资产索引：全部代码文件清单

> 用途：快速定位"哪个文件干什么"。看到某个脚本名不知道它是干吗的，查这里。
> 所有脚本都使用 Python 标准库或已在 `requirements.txt` 中列明的第三方库。

---

## 一、采集层

| 文件 | 位置 | 作用 | 依赖 |
| --- | --- | --- | --- |
| `pachong.py` | 项目根目录 | 搜索候选视频、筛选、采集公开顶层评论、输出五件套 CSV | **零第三方依赖**（仅 `urllib`/`csv`/`json`） |

### `pachong.py` 的七个命令行参数

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--topic <slug>` | `nezha2` | 主题名，必须是 `TOPICS` 字典里已有的键 |
| `--output-dir <路径>` | `<slug>_youtube_<YYYYMMDD>` | 输出目录 |
| `--per-language <1..50>` | 主题配置里的值 | 每种语言选几个视频 |
| `--max-comments <1..1000>` | `1000` | 每个视频最多抓多少条评论 |
| `--api-key-file <路径>` | 脚本同级的 `youtube_api_key.txt` | 密钥文件位置 |
| `--dry-run` | 关 | 只搜候选视频、不抓评论（不消耗评论配额） |
| `--resume` | 关 | 复用已选视频、跳过已完成的视频 |

### 采集产出（五件套）

| 文件 | 内容 |
| --- | --- |
| `videos.csv` | 入选视频：ID、语种、命中检索词、标题、简介、频道、发布时间、播放量、评论数、链接 |
| `comments.csv` | **核心数据**：评论 ID、所属视频、发布/修改时间、点赞数、正文、采集时间 |
| `candidates.csv` | 全部候选视频（含被淘汰的），用于审查选样规则 |
| `collection_log.csv` | 全程日志：搜索状态、选样、短缺、评论关闭、错误 |
| `raw/` | 已去标识化的 API 原始响应（`discovery/`、`comments/<video_id>/`、`selection.json`、`run_manifest.json`） |

---

## 二、分析层：公共文件

| 文件 | 作用 |
| --- | --- |
| `pipeline_common.py` | 路径集中管理、随机种子、缓存位置、绘图风格。**不单独运行**，被其他脚本导入 |
| `run_analysis.py` | 按顺序启动五个阶段（子进程隔离，任一步失败即停止） |
| `requirements.txt` | 分析依赖清单 |

> ⚠️ **`pipeline_common.py` 里 `RAW_ROOT` 是换主题时最容易忘改的一处。**

---

## 三、分析层：五个阶段

### 阶段① `01_prepare_data.py` —— 语料准备

| 项目 | 说明 |
| --- | --- |
| 输入 | `../<slug>_youtube_<日期>/comments.csv`、`videos.csv` |
| 做什么 | 文本清洗（空白/过短/纯链接/纯符号/重复）→ fastText 语种识别（阈值 0.80）→ 输出正式语料 |
| 产出 | `data/english_comments.csv`（或 `chinese_comments.csv`）、`data/cleaning_audit.csv`、`data/preparation_summary.json`、`figures/fig_01_cleaning_funnel.png` |
| 关键数字 | 正式语料 < 100 条则报错退出，应回头扩大采集 |
| 关键字段 | `raw_hashes_unchanged` 必须为 `true` |

### 阶段② `02_topic_analysis.py` —— 主题建模

| 项目 | 说明 |
| --- | --- |
| 输入 | `data/<语种>_comments.csv` |
| 做什么 | 句向量 → UMAP 降维 → HDBSCAN（英文）/ KMeans（中文）聚类 → c-TF-IDF 提取关键词 |
| 产出 | `results/topic_summary.csv`、`topic_keywords.csv`、`topic_assignments.csv`、`topic_representative_quotes.csv`、`topic_metadata.json`、`document_embeddings.npy`、`bertopic_model/`、`figures/fig_02`、`fig_03` |
| ⚠️ 注意 | `INTERPRETED_TOPIC_LABELS` 字典必须**自己重写**，不能沿用例子里的人写的主题名 |

### 阶段③ `03_sentiment_analysis.py` —— 情感分析

| 项目 | 说明 |
| --- | --- |
| 输入 | `data/<语种>_comments.csv` |
| 做什么 | 主模型打三分类标签 + 对照方法做稳健性检验 |
| 主模型 | 英文 `cardiffnlp/twitter-roberta-base-sentiment-latest`；中文 `uer/roberta-base-finetuned-jd-binary-chinese` |
| 对照 | 英文 VADER；中文 SnowNLP |
| 产出 | `results/sentiment_assignments.csv`、`sentiment_summary.csv`、`sentiment_keywords.csv`、`monthly_sentiment.csv`、`topic_sentiment_crosstab.csv`、`sentiment_metadata.json`、`figures/fig_04`、`fig_05`、`fig_06`×2、`fig_09` |
| 可选参数 | `--reuse-classifications` 复用已有预测，只重画图表 |
| ⚠️ 注意 | 中文的"中性"来自概率阈值（0.40~0.60），须在报告中说明 |

### 阶段④ `04_semantic_network.py` —— 语义网络

| 项目 | 说明 |
| --- | --- |
| 输入 | `data/<语种>_comments.csv` |
| 做什么 | 词性过滤 → 五词窗口共现统计 → 保留 Top-60 节点/Top-180 边 → Louvain 社群发现 → 中心性计算 |
| 产出 | `results/network_nodes.csv`、`network_edges.csv`、`network_centrality_top25.csv`、`network_metadata.json`、`figures/fig_07`、`fig_08` |
| 语言差异 | 英文用 spaCy 词形还原；中文用 jieba 词性标注 |
| ⚠️ 注意 | 边只表示共现倾向，不作因果解释 |

### 阶段⑤ `05_build_report.py` —— 报告生成

| 项目 | 说明 |
| --- | --- |
| 输入 | 前面四个阶段的全部结果表 |
| 做什么 | 动态读取数字 → 生成十章节中文学术风格 Word 报告（插图、插表、题注） |
| 产出 | `reports/<主题名>分析报告.docx`、`reports/reproducibility_metadata.json` |
| ⚠️ 注意 | `TOPIC_CN` 字典与 `theme_sentence()` 函数必须**自己重写** |

---

## 四、完整输出目录树

```text
<项目文件夹>/
├── pachong.py                          ← 采集脚本
├── youtube_api_key.txt                 ← 密钥（.gitignore 已排除，不入库）
├── <slug>_youtube_YYYYMMDD/            ← 采集产出（只读输入）
│   ├── videos.csv
│   ├── comments.csv
│   ├── candidates.csv
│   ├── collection_log.csv
│   └── raw/
└── <slug>_analysis_YYYYMMDD/           ← 分析目录
    ├── pipeline_common.py
    ├── run_analysis.py
    ├── requirements.txt
    ├── 01_prepare_data.py
    ├── 02_topic_analysis.py
    ├── 03_sentiment_analysis.py
    ├── 04_semantic_network.py
    ├── 05_build_report.py
    ├── data/
    │   ├── <语种>_comments.csv
    │   ├── cleaning_audit.csv
    │   └── preparation_summary.json
    ├── results/
    ├── figures/
    ├── reports/
    └── cache/
```

---

## 五、图表清单（10 张）

| 文件 | 内容 | 由哪个阶段生成 |
| --- | --- | --- |
| `fig_01_cleaning_funnel.png` | 语料构建漏斗 | ① |
| `fig_02_topic_sizes.png` | 主题规模横向条形图 | ② |
| `fig_03_topic_umap.png` | 主题空间二维投影 | ② |
| `fig_04_sentiment_distribution.png` | 情感三分类分布 | ③ |
| `fig_05_monthly_sentiment.png` | 月度情感占比堆叠图 | ③ |
| `fig_06_positive_wordcloud.png` | 正面内容词词云 | ③ |
| `fig_06_negative_wordcloud.png` | 负面内容词词云 | ③ |
| `fig_07_semantic_network.png` | 语义共现网络图 | ④ |
| `fig_08_network_centrality.png` | 中心性排行 | ④ |
| `fig_09_topic_sentiment_heatmap.png` | 主题×情感热力图 | ③ |

---

## 六、执行顺序

```bash
# 采集
conda activate dhr
cd /d <项目文件夹>
python pachong.py --topic <slug> --dry-run     # 先试运行核对候选
python pachong.py --topic <slug>               # 正式采集

# 分析
cd /d <项目文件夹>\<slug>_analysis_YYYYMMDD
conda run -n dhr python run_analysis.py        # 一键跑完五阶段
# 或逐阶段：conda run -n dhr python 01_prepare_data.py 等
```
