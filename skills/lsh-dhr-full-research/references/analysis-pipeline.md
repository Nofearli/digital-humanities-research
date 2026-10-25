# 参考资料：五阶段分析流水线详解

> 用法：读完采集阶段、拿到 `comments.csv` 之后看这份文档。
> 它回答三个问题：**分析目录怎么搭、每个脚本做什么、中英文版本差在哪。**
> 目标读者：没做过文本分析、看到 BERTopic / UMAP 这类词就发怵的人。

---

## 一、先建立整体印象

采集拿到的是**一张评论表**（`comments.csv`）。分析要做的是把这张表变成**可解释的研究结论**。中间经过五个阶段：

```text
comments.csv
    ↓ ① 语料准备        → 洗净、按语种切分         → 正式语料
    ↓ ② 主题建模        → 大家主要在聊什么         → 主题表
    ↓ ③ 情感分析        → 态度是正面还是负面       → 情感表
    ↓ ④ 语义网络        → 哪些概念连在一起         → 网络表
    ↓ ⑤ 报告生成        → 把上面三样写成一篇文章   → Word 报告
```

这五个阶段对应五个脚本，文件名前面带编号，**必须按编号顺序跑**，因为后面的阶段依赖前面阶段的产出。

一个完整的分析目录长这样：

```text
<主题slug>_analysis_YYYYMMDD/
├── pipeline_common.py        ← 公共配置（路径、随机种子、绘图风格）
├── run_analysis.py           ← 一键按顺序跑完五个阶段
├── requirements.txt          ← 需要装的 17 个库
├── 01_prepare_data.py        ← 阶段①
├── 02_topic_analysis.py      ← 阶段②
├── 03_sentiment_analysis.py  ← 阶段③
├── 04_semantic_network.py    ← 阶段④
├── 05_build_report.py        ← 阶段⑤
├── data/                     ← 派生语料（阶段①产出）
├── results/                  ← 结果表（阶段②③④产出）
├── figures/                  ← 图表 PNG
├── reports/                  ← Word 报告（阶段⑤产出）
└── cache/                    ← 模型与 pip 缓存
```

### 两种跑法

**一键跑完**（推荐，省事）：

```bash
conda activate dhr
cd /d <项目文件夹>\<主题slug>_analysis_YYYYMMDD
conda run -n dhr python run_analysis.py
```

**逐阶段跑**（调试时用，某一步出错不用从头再来）：

```bash
conda run -n dhr python 01_prepare_data.py
conda run -n dhr python 02_topic_analysis.py
conda run -n dhr python 03_sentiment_analysis.py
conda run -n dhr python 04_semantic_network.py
conda run -n dhr python 05_build_report.py
```

### 首次运行会很慢，正常

第一次跑会在 `cache/` 里下载模型：fastText 语种模型约 130 MB，句向量模型与情感模型另有几百 MB。下完之后复用本地缓存，第二次开始就快了。**卡住或超时就直接重跑**，已下好的部分不会重复下载。

---

## 二、`pipeline_common.py`：公共配置

这个脚本不单独运行，它被其他五个脚本导入。作用是**把路径和配置集中在一处**，避免每个脚本各写一套。

| 配置项 | 作用 |
| --- | --- |
| `ROOT` | 当前分析目录 |
| `RAW_ROOT` | 原始采集目录（**只读**），默认是 `../<主题slug>_youtube_<日期>` |
| `RAW_COMMENTS` / `RAW_VIDEOS` | 输入的两个 CSV |
| `DATA_DIR` / `RESULTS_DIR` / `FIGURES_DIR` / `REPORTS_DIR` | 四类产出的落盘位置 |
| `CACHE_DIR` / `MODELS_DIR` / `HF_HOME` | 模型与缓存位置（都在项目内） |
| `RANDOM_SEED = 42` | 全局随机种子，保证结果可复现 |

两个重要函数：

- `set_reproducibility()` —— 把随机种子同时设给 `random`、`numpy`、`torch`。**没有这一步，每次跑出来的主题编号都不一样，报告就没法复现。**
- `sha256()` —— 算文件指纹，用来证明"分析没改动原始数据"。

### ⚠️ 换主题时必须改的一行

`pipeline_common.py` 里的这一行指向原始数据目录：

```python
RAW_ROOT = ROOT.parent / "<主题slug>_youtube_YYYYMMDD"
```

**复用分析目录做新主题时，这一行必须同步改**，否则脚本会去读旧主题的数据，而你还以为在分析新主题。这是最常见的"数据串味"事故。

---

## 三、阶段①：语料准备（`01_prepare_data.py`）

### 它做什么

```text
原始评论
  ├─ 空白文本              ─┐
  ├─ 少于 5 个字符          │
  ├─ 纯链接、纯符号数字     ├→ 记入 cleaning_audit.csv（可回溯）
  ├─ 规范化后重复           │
  └─ 语种不符 / 置信度低    ─┘
        ↓ 剩下的
   正式语料（english_comments.csv 或 chinese_comments.csv）
```

### 两个阈值

| 参数 | 值 | 含义 |
| --- | --- | --- |
| `ENGLISH_CONFIDENCE` / `CHINESE_CONFIDENCE` | `0.80` | fastText 判为某语种的概率必须 ≥ 0.80 才收进来 |
| 最短长度 | 5 个字符 | 太短的评论没有分析价值（如"好""👍"） |

**为什么阈值是 0.80 而不是更低？** 因为中英混写、拼音、网络缩写会让语种判断变得模糊。阈值定高一些，宁可错杀，不要放进噪音污染主题模型。这个数字写进报告的方法部分，读者才知道你的筛选标准。

### 产出

| 文件 | 内容 |
| --- | --- |
| `data/english_comments.csv`（或 `chinese_comments.csv`） | 正式语料，含语种、置信度、月份、来源视频信息 |
| `data/cleaning_audit.csv` | **每条被删掉的评论**及其删除原因——这是审计凭据 |
| `data/preparation_summary.json` | 清洗漏斗数量、排除原因统计、输入文件的 SHA-256 前后对比 |
| `figures/fig_01_cleaning_funnel.png` | 漏斗图 |

### 必须核对的指标

打开 `preparation_summary.json`，看这两个字段：

```json
{
  "funnel": { "raw_comments": 11770, "after_text_cleaning": 9800, "english_analysis_corpus": 4200 },
  "raw_hashes_unchanged": true
}
```

- `funnel` 三个数字要能对上：原始数 → 清洗后 → 正式语料，逐级递减；
- `raw_hashes_unchanged` **必须是 `true`**。如果是 `false`，说明原始数据被动过，整条流水线的可信度就没了，必须查清原因。

### 一条经验

如果正式语料少于 **100 条**，主题分析会直接报错退出。原因是样本太小时 BERTopic 的聚类结果毫无统计意义——它会给你 8 个"主题"，但每个主题只有三五条评论，纯属噪声。这种情况下正确的做法是**回头扩大采集量**，而不是调低阈值硬跑。

---

## 四、阶段②：主题建模（`02_topic_analysis.py`）

### 技术链路

```text
评论文本
  ↓ Sentence-Transformer 编码
句向量（768 维，捕捉语义而非字面）
  ↓ UMAP 降维
低维向量（英文 5 维 / 中文 8 维）
  ↓ HDBSCAN 或 KMeans 聚类
若干语义簇
  ↓ c-TF-IDF 提取特征词
每个簇的关键词
  ↓ 研究者阅读关键词 + 代表性评论
可读的主题名称
```

### 每一步为什么需要

- **句向量**：把文字变成数字。关键在于它是**语义**编码——"这部电影真棒"和"这片子太好了"的向量会很接近，虽然用词完全不同。
- **UMAP 降维**：768 维空间里距离没有意义（维度诅咒），必须先降到低维才能聚类。
- **HDBSCAN / KMeans**：把相近的评论归成一堆。HDBSCAN 会自动决定堆数、并把不合群的评论标为离群（`topic_id = -1`）；KMeans 需要你指定堆数。
- **c-TF-IDF**：给每个簇找"最有代表性"的词。它的逻辑是：这个词在本簇里出现多、在其他簇里出现少，那它就是这个簇的标志词。

### ⚠️ 最关键的一步：主题命名是"人写的"

模型输出的 `keyword_label` 长这样：

```text
story | animation | character | beautiful
```

这**不是**一个可以写进论文的主题名。你必须结合三样东西自己命名：

1. **主题规模**（多少条评论）——太小的主题不值得单列；
2. **关键词**（上面那串词）——提示讨论焦点；
3. **代表性引文**（`topic_representative_quotes.csv` 里点赞最高的几条）——看真实语境。

然后写出：

```text
动画品质、影评互动与观影推荐
```

脚本里有一个 `INTERPRETED_TOPIC_LABELS` 字典，就是放这些人工主题名的：

```python
INTERPRETED_TOPIC_LABELS = {
    0: "观影评价、价值判断与成长叙事",
    1: "动画品质、影评互动与观影推荐",
    ...
}
```

**做新主题时，这个字典必须重写。** 直接沿用别人的主题名是最严重的学术错误——主题编号在每次运行时都可能对应完全不同的内容。

### 产出

| 文件 | 用途 |
| --- | --- |
| `topic_summary.csv` | 主题总表：编号、评论数、模型关键词、人工主题名 |
| `topic_keywords.csv` | 每主题 Top-10 关键词及分数（写方法部分时引用） |
| `topic_assignments.csv` | 每条评论的主题归属（后续情感交叉分析要用） |
| `topic_representative_quotes.csv` | 每主题 Top-5 代表评论（**写报告引用原文用这个**） |
| `topic_metadata.json` | 模型参数与元数据 |

图表：`fig_02_topic_sizes.png`（横向条形图，看主题规模）、`fig_03_topic_umap.png`（散点图，看主题空间分布）。

### 离群主题怎么处理

`topic_id = -1` 是离群组，里面是**不适合归入任何主题的杂项评论**。

**正确做法：如实报告它的存在和数量，不强行解释。** 报告里写"另有 N 条评论被归入离群/混合组，不被强行解释为单一主题"，这体现的是方法自觉，不是失败。把离群组硬塞一个主题名反而是硬伤。

---

## 五、阶段③：情感分析（`03_sentiment_analysis.py`）

### 主模型 + 对照方法的双轨设计

这是本流水线在方法上的一个刻意设计：**每个语种用两个独立方法打标签，报告两者的一致率。**

| 语种 | 主模型 | 对照方法 |
| --- | --- | --- |
| 英文 | `cardiffnlp/twitter-roberta-base-sentiment-latest`（三分类） | VADER（词典法） |
| 中文 | `uer/roberta-base-finetuned-jd-binary-chinese`（二分类） | SnowNLP（原生中文） |

**为什么必须做对照？** 因为情感分类在社交媒体语料上从来不是精确科学。反讽、文化梗、平台黑话都会让模型翻车。跑两个方法、报告一致率（比如"Transformer 与 VADER 的逐条一致率为 68%"），读者才知道这个结果能信到什么程度。**报告里必须把情感结果表述为"分布性指标"，而不是对单条评论的绝对判定。**

### 中文的特殊处理：二分类变三分类

中文主模型是**二分类**（正/负），没有"中性"类别。为了得到三分类结果，脚本用了一个概率阈值策略：

```python
POSITIVE_THRESHOLD = 0.60   # 正向概率 ≥ 0.60 → 正面
NEGATIVE_THRESHOLD = 0.40   # 正向概率 ≤ 0.40 → 负面
                            # 中间 (0.40, 0.60) → 中性
```

**这个方法学含义必须在报告里写明**：中文的"中性"是**概率区间策略的产物**，不是模型独立训练出来的类别。这是一个真实的局限，藏起来比说出来危险得多。

英文主模型本身是三分类，直接用。

### 停用词：为什么不只用标准停用词表

脚本用了三层停用词：

1. **标准英语停用词**（`the`、`and`、`is`…）；
2. **领域与平台泛词** —— 片名（`nezha`、`zha`）、`movie`、`film`、`video`、`youtube`、`watch`、`review` 等。这些词频次极高但不携带评价信息；
3. **国家地区词**（仅中文/英文词云用） —— `china`、`american` 等。

第 3 点值得单独说明：国家地区词在**主题分析和网络分析里要保留**（它们是重要的分析对象），但**在情感词云里要去掉**，否则词云会被 `china`、`chinese` 这些词占满，掩盖真正的评价性词汇。这个区别处理写进了代码注释，报告的方法部分应该提到。

### 产出

| 文件 | 用途 |
| --- | --- |
| `sentiment_assignments.csv` | 每条评论的标签与概率 |
| `sentiment_summary.csv` | 三类各多少条、占比 |
| `sentiment_keywords.csv` | 每类 Top-30 高权重内容词 |
| `monthly_sentiment.csv` | 逐月情感占比 |
| `topic_sentiment_crosstab.csv` | 主题 × 情感交叉表 |
| `sentiment_metadata.json` | 模型、阈值、一致率 |

图表：`fig_04`（分布柱状图）、`fig_05`（月度堆叠图）、`fig_06_positive/negative_wordcloud.png`（两张词云）、`fig_09`（主题情感热力图）。

### 一个可选的省时参数

`--reuse-classifications` 复用已缓存的预测结果，只重画图表。改了配色或标题时用它，不用重新跑一遍模型推理：

```bash
conda run -n dhr python 03_sentiment_analysis.py --reuse-classifications
```

### 月度结果的红线

`monthly_sentiment.csv` 里的月度变化**只能作描述性展示**。原因：各月的样本量和视频来源都不同，某月负面比例高可能只是因为那个月恰好有个批评视频火了。**不能据此说"情绪在恶化"或"口碑在下滑"**——那是因果推断，数据不支持。报告里要明确写这一句。

---

## 六、阶段④：语义网络（`04_semantic_network.py`）

### 它做什么

把评论内容词建成一张"谁和谁经常一起出现"的网络图。

```text
评论："这部电影的动画真的很棒，故事也很感人"
  ↓ 词性过滤（只留名词、动词、形容词）
["动画", "棒", "故事", "感人"]
  ↓ 五词滑动窗口统计共现
动画—棒、动画—故事、故事—感人 …
  ↓ 汇总全语料
一张加权网络图
```

### 两个核心参数

| 参数 | 值 | 含义 |
| --- | --- | --- |
| `WINDOW_SIZE` | 5 | 前后各看 5 个词，在这个范围内算"一起出现" |
| `TOP_TERMS` / `TOP_EDGES` | 60 / 180 | 只保留最强的 60 个节点、180 条边，否则图太密看不清 |

### 网络指标怎么看

- **加权度（weighted degree）** —— 一个词和其他词共现的总强度。度高 = 这个词在话语中很"中心"。
- **介数中心性（betweenness）** —— 一个词在多少条"最短路径"上。高 = 这个词是不同话题之间的**桥梁**。
- **社群（community）** —— 用 Louvain 算法把词分成几组，组内的词关系更紧密，通常对应一个话题领域。

### ⚠️ 解读红线（必须写进报告）

**边只表示"共现倾向"，不表示因果关系。**

网络图很容易被误读成因果结构——"动画"和"优秀"连在一起，不代表动画质量导致了正面评价。报告里必须明确写：**网络中的边表示评论中词语在局部语境内共同出现的倾向，不表示概念之间具有因果方向。** 中心性高也不等于"影响力大"。

### 产出

`network_nodes.csv`、`network_edges.csv`、`network_centrality_top25.csv`、`network_metadata.json`；图表 `fig_07`（网络图）、`fig_08`（中心性排行）。

### 语言差异：分词方式完全不同

| 语种 | 处理方式 |
| --- | --- |
| 英文 | spaCy 做**词形还原**（lemmanization），`running` → `run`，只留 NOUN/PROPN/ADJ/VERB |
| 中文 | jieba 词性标注（`pseg`），只留 n / v / a 开头的词类，无还原概念 |

英文的 spaCy 模型需要单独下载一次：

```bash
python -m spacy download en_core_web_sm
```

中文用 jieba，无需额外模型。中英文各有一份独立的中文停用词表（概念相同但词表不同）。

---

## 七、阶段⑤：报告生成（`05_build_report.py`）

### 它做什么

读取前面四个阶段的全部结果表，生成一份**中文学术风格的 Word 报告**。它不是简单拼接，而是：

1. 从结果表里**动态读取每一个数字**——评论总数、各主题规模、情感占比、一致率、节点边数；
2. 按十章的学术结构组织（见 `assets/analysis_report_template.txt`）；
3. 插入所有图表并配中英双语题注；
4. 生成 Word 表格（主题概览表、核心概念表）；
5. 在附录写入完整的复现元数据。

### 报告里的数字绝不能写死

看这行代码：

```python
add_body(document, f"...正面评论为 {int(sentiment_count.get('positive', 0)):,} 条（{sentiment_map.get('positive', 0):.1%}）...")
```

数字从 `sentiment_summary.csv` 读出来填进去。**这样做的意义**：数据换了，报告自动跟着变，不会出现"表格是新的、正文数字是旧的"这种致命不一致。

### 人工解释部分需要重写

脚本里有个 `TOPIC_CN` 字典和 `theme_sentence()` 函数，后者为每个主题写一段解释性文字：

```python
0: "这一最大主题把作品体验与个人成长、价值判断连在一起……"
```

**做新主题时这些必须重写。** 它们是对特定数据的解读，换个主题就完全不适用了。脚本里保留这些只是提供写法范例。

### 附录里的复现元数据

`reports/reproducibility_metadata.json` 会记录：

- 输入文件的 SHA-256（证明数据未被改动）；
- 完整清洗漏斗；
- 各阶段模型名与参数；
- 随机种子；
- 七个关键依赖包的版本号。

**这是"可复现研究"的核心凭据。** 报告正文也必须写一句"原始输入文件哈希、清洗漏斗、模型信息、随机种子、依赖版本和运行元数据已写入 `reports/reproducibility_metadata.json`"。

---

## 八、中英文双版本的差异对照

做中英双语研究时，通常建两个分析目录各跑一遍。两者代码结构相同，但有多处关键差异：

| 环节 | 英文版 | 中文版 |
| --- | --- | --- |
| 语种代码 | `en` | `zh` |
| 正式语料文件名 | `english_comments.csv` | `chinese_comments.csv` |
| 句向量模型 | `sentence-transformers/all-MiniLM-L6-v2` | `BAAI/bge-small-zh-v1.5` |
| 聚类方式 | HDBSCAN（自动定簇数） | **KMeans 固定 8 簇** |
| 情感主模型 | RoBERTa 三分类 | RoBERTa 二分类 + 阈值转三类 |
| 情感对照 | VADER | SnowNLP |
| 分词 | spaCy 词形还原 | jieba 词性标注 |
| 网络词性过滤 | NOUN/PROPN/ADJ/VERB | 词性前缀 n/v/a |
| 绘图字体 | Times New Roman（serif） | Microsoft YaHei（sans-serif） |
| 图表标签语言 | 英文 | 中文 |
| 关键词提取 | BERTopic 内建 c-TF-IDF | **独立 TF-IDF 重新提取** |

### 两处必须理解的差异

**① 中文为什么用 KMeans 而不是 HDBSCAN？**

代码注释写得很清楚：中文语料上初始的 HDBSCAN 方案产生了"一个过大的混合簇 + 若干个只有 15-20 条评论的噪声簇"。也就是说自动聚类在这个语料上失效了。改成固定 8 簇的 KMeans 是为了得到**可解释的**主题划分。

这带来一个代价：**KMeans 没有离群概念**，所有评论都会被分配到某个簇里，没有 `-1` 组。这在报告里要如实说明——中文版没有"离群/混合组"这一项。

**② 中文为什么独立提取关键词？**

用固定 KMeans 聚类时，BERTopic 的表示层（representation layer）有时无法产出有意义的中文词。所以中文版绕开它，用独立的 TF-IDF 在每个簇内重新算关键词，并把原始分数完整保留在 `topic_keywords.csv`。

### 图表字体：一个容易踩的坑

**英文版**用 Times New Roman（衬线体），因为学术图表的惯例是衬线体。**中文版**必须用 Microsoft YaHei（无衬线），因为 Times New Roman 不含中文字形，直接画会变成一堆方框（豆腐块）。

中文词云还需要显式指定字体文件路径：

```python
CHINESE_FONT_PATH = "C:\\Windows\\Fonts\\msyh.ttc"
```

**换电脑时这个路径可能失效**，需要改成目标机器上实际存在的中文字体路径。

---

## 九、跑完之后的自查清单

逐个打开确认：

- [ ] `data/preparation_summary.json` 里 `raw_hashes_unchanged` 是 `true`
- [ ] 正式语料条数 ≥ 100（少于这个数主题分析不可靠）
- [ ] `results/topic_summary.csv` 里每个主题都有**人工写的** `interpreted_label`，不是模型关键词
- [ ] `results/topic_representative_quotes.csv` 里的引文确实读得通、能支撑主题名
- [ ] `results/sentiment_metadata.json` 里有一致率数值
- [ ] `results/network_metadata.json` 里节点数、边数、社群数合理
- [ ] `figures/` 里 10 张图都能正常打开，中文不乱码
- [ ] `reports/` 里的 Word 报告数字与结果表一致
- [ ] `reports/reproducibility_metadata.json` 已生成

---

## 十、想把流水线用到新主题上

假设已经用 `pachong.py` 采集了"西游记"的数据，现在要分析：

1. **复制分析目录**，改成新名字：`xiyouji1986_analysis_20261012/`；
2. **删掉旧产出**：清空 `data/`、`results/`、`figures/`、`reports/`（`cache/` 可以保留，模型不用重下）；
3. **改 `pipeline_common.py`**：把 `RAW_ROOT` 指向新的采集目录 `../xiyouji1986_youtube_20261012`；
4. **重写人工解释部分**：`02_topic_analysis.py` 的 `INTERPRETED_TOPIC_LABELS`、`05_build_report.py` 的 `TOPIC_CN` 和 `theme_sentence()`——这三处必须清空重写，不能沿用；
5. **按顺序跑** `run_analysis.py`；
6. **核对**：看新的 `topic_summary.csv`，重新命名主题、重写解释句子，再跑一次 `05_build_report.py`。

主题命名是个**迭代**过程：先跑一次看模型给出什么，命名后再跑。通常需要来回两三次才能得到满意的主题体系。
