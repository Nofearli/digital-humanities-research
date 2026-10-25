---
name: lsh-dhr-full-research
description: 面向完全零基础用户的数字人文调研全流程，覆盖「采集 → 分析 → 报告」三大阶段共 12 步。当用户想从零完成一次完整的网络评论研究——准备 Python/conda 环境、申请并配置 API 密钥、填写调研主题、抓取公开评论、清洗语料、主题建模、情感分析、语义网络分析、生成学术报告——时使用本技能。典型场景是采集 YouTube 视频评论做主题/情感/传播分析。包含可运行的 `pachong.py` 采集脚本与五阶段分析流水线的逐段讲解、中英双语分析版本差异、学术报告写法、常见报错排查与三张操作检查清单。触发词：数字人文、评论采集、API key、YouTube 采集、调研报告、主题建模、情感分析、语义网络、BERTopic、环境配置、装库、conda 环境。
agent_created: true
---

# lsh-dhr-full-research：零基础数字人文调研全流程（采集 + 分析）

## Overview

本技能提供一条"傻瓜式"的数字人文研究流水线，从**准备运行环境**开始，经过申请 API 密钥、填写调研主题、抓取公开评论、清洗语料，一直到**主题建模、情感分析、语义网络分析**，最终产出**纯文字报告**与**学术分析报告**。面向完全没有技术背景的用户：所有命令由 WorkBuddy 代跑，用户只需回答几个问题、点几下鼠标。

默认数据源为 **YouTube Data API v3**，采集脚本为 `pachong.py`，分析流水线为五个阶段的 Python 脚本。

**三条关键事实（必须向用户讲清，避免被依赖清单吓退）：**

- **采集数据环节零第三方依赖** —— `pachong.py` 只使用 Python 标准库（`urllib` / `csv` / `json`），任何 Python 3.8+ 都能跑，一个库都不装也能完成数据采集；
- **只有"分析"环节才需要装库** —— 主题建模、情感分析、语义网络需要约 17 个第三方库（见 `references/environment-setup.md` 第五节）；
- **模型无需手动下载** —— fastText 语种模型与 Hugging Face 情感模型都会在首次运行分析脚本时自动下载到项目内的 `cache/`。

工作目录以用户的调研项目文件夹为准（下文统一用 `<项目文件夹>` 代指），采集脚本为 `<项目文件夹>/pachong.py`，分析脚本位于 `<项目文件夹>/<主题>_analysis_<日期>/`。

> **本技能与"采集专用"技能的关系**：另一份 `lsh-digital-humanities-research` 技能只覆盖采集阶段的 7 步；本技能在其基础上**增加**了分析阶段的完整内容（代码导读、五阶段流水线、报告写作），覆盖 12 步。两者可以共存，也可只装本技能。

## 何时使用

- 用户说"我想调研某个话题/电影/事件在网络上的评论、口碑"，且之前没有数据；
- 用户提到"申请 API key""抓评论""数字人文""做一份调研报告"；
- 用户想对**已采集的数据**做主题建模、情感分析、语义网络分析；
- 用户提到"环境怎么配""要装什么库""conda 环境"等环境准备问题；
- 用户想了解 `pachong.py` 或分析脚本**某段代码在做什么**。

若用户只想做采集、不做分析，也可以走本流程，在第 8 步停下即可。

## 总体流程（12 步，严格按顺序执行）

```
【第一阶段：采集】
① 准备运行环境与依赖       ← 最容易卡住的一步，必读 environment-setup.md
② 申请并配置 API 密钥
③ 填写《调研主题单》（用户回答 6 个问题）
④ 确认采集数量配置
⑤ 试运行 + 正式抓取

【第二阶段：分析与成文】
⑥ 整理结果文件与建立分析目录
⑦ 语料准备（清洗 + 语种识别）
⑧ 主题建模（BERTopic）
⑨ 情感分析
⑩ 语义网络分析

【第三阶段：产出】
⑪ 生成纯文字调研报告
⑫ 生成学术分析报告（Word）
→ 最后逐项过《操作检查清单》
```

第 ① ~ ⑤ 步与采集专用技能完全一致；第 ⑥ ~ ⑫ 步为本技能新增。

---

## Step 0 准备运行环境与依赖

完整保姆级说明（含 Anaconda 从零安装、建环境、装库、缓存位置、环境自检三连、环境类报错）见 `references/environment-setup.md`，按其引导用户操作。核心规则：

1. **建议环境名 `dhr`，Python 3.11**（环境名可自定义，下文统一用 `dhr` 举例）。命令一律以下列两步开头：

```bash
conda activate dhr
cd /d <项目文件夹>
```

2. **采集环节零依赖**：`pachong.py` 仅用标准库（`urllib`/`csv`/`json`），无需 `pip install` 任何东西。不要为了"看起来专业"给采集脚本引入新库。
3. **分析环节才有依赖**：需要 17 个库，清单与安装命令见 `references/environment-setup.md` 第五节；在分析脚本目录执行 `pip install -r requirements.txt`。
4. **模型无需手动下载**：fastText 语种模型 `lid.176.bin`（约 130 MB）会在首次运行 `01_prepare_data.py` 时自动下载到 `cache/models/`；情感分析模型落在 `cache/huggingface/`。
5. **遇到"Environment"类报错**（conda 未激活、`No module named xxx`、装错环境、pip 太慢）直接查 `references/environment-setup.md` 第八节，不要盲目重装 Anaconda。
6. **环境自检三连**（做完才进入 Step 1）：`python --version` → `python -c "import pandas"`（仅分析需要）→ `python pachong.py --topic <slug> --dry-run`。

**注意：若项目目录没有 `test_*.py` 测试文件，`python -m unittest -v` 会显示 "Ran 0 tests"，这是正常现象，不代表环境有问题。** 环境是否就绪以 Step 0 第 6 条的自检三连为准。

---

## Step 1 申请并配置 API 密钥

详细图文步骤（含 YouTube Data API v3 从零申请）见 `references/api-key-guide.md`，按其引导用户操作。核心规则：

1. 默认数据源为 **YouTube Data API v3**（Google Cloud Console 免费申请，日配额 10,000 单位，足够一次调研）。
2. 密钥文件的存放位置有且仅有一处：**项目文件夹根目录下的 `youtube_api_key.txt`**，即与 `pachong.py` **同级同一个文件夹**。示例路径：`<项目文件夹>/youtube_api_key.txt`
3. 密钥安全红线：绝不把 key 发到聊天里、写进 `pachong.py`、上传 Git；key 泄露后去 Google Cloud Console 删除重建。
4. 若换用其他数据源（如 B 站、微博、RSS），同样在项目文件夹根目录存一个 `<来源名>_api_key.txt`，流程不变。
5. 密钥就位后先用 `python pachong.py --topic <主题名> --dry-run` 验证能否连通，见 Step 4。

## Step 2 填写《调研主题单》

让用户按 `references/topic-brief-template.md` 的模板逐项回答，不要替用户编造。必填 6 项：

1. 调研主题名称（中文，如"哪吒之魔童闹海海外评论"）；
2. 对象的别名列表（中英文各若干，如 `哪吒2 / Ne Zha 2`，用于过滤视频）；
3. 内容类型与必含语境词（如"影评/review/解析/反应"）；
4. 排除词（预告、片段、官方宣传、易混淆的其他作品）；
5. 语言与时间范围（默认中英双语、2025-01-01 至今）；
6. 每语言视频数、每视频评论数（默认值见 Step 3）。

主题名转成英文 slug（小写字母数字下划线，如 `nezha2`）后：若 `pachong.py` 的 `TOPICS` 字典里已有该主题直接复用；没有则按 `references/topic-brief-template.md` 末尾的示例，在 `TOPICS` 中新增一条 `Topic(...)` 配置，字段全部来自用户填写的内容，不得自行加戏。

## Step 3 采集数量配置（默认值，用户可改）

| 项目 | 默认值 | 说明 |
| --- | --- | --- |
| 每种语言入选视频数 | 15 个（中文 15 + 英文 15 = 30） | 按播放量从高到低选影评/反应类视频 |
| 每个视频抓取评论数 | 最多 1,000 条 | 仅顶层公开评论，不抓回复 |
| 单个主题评论总量上限 | 30,000 条（30 视频 × 1,000） | 实际通常 1 万～2 万条 |
| 搜索候选池 | 每种语言 4 个检索词，各取前 50 条结果 | 全部写入 `candidates.csv` 供审查 |

命令行对应参数：`--per-language 15`、`--max-comments 1000`、`--output-dir .\<slug>_youtube_<日期>`。任何数量调整都必须记录到主题单里，并在最终报告中如实写明实际采集量。

## Step 4 抓取数据

在项目文件夹、环境激活状态下依次执行（Anaconda Prompt 用反斜杠路径，Git Bash 用正斜杠路径）：

```bash
# 0) 环境就绪（每次开新窗口都要做）
conda activate dhr
cd /d <项目文件夹>

# 1) 试运行：只搜候选视频、不抓评论，产出 candidates.csv（不消耗评论配额）
python pachong.py --topic <主题slug> --dry-run

# 2) 检查 candidates.csv：数量是否正常、有无混入无关视频
#    这一步必须和用户一起核对，确认后才进入下一步

# 3) 正式抓取
python pachong.py --topic <主题slug>

# 4) 若中断，续跑（自动跳过已完成视频、按评论 ID 去重）
python pachong.py --topic <主题slug> --resume
```

硬性要求：正式抓取前必须先 dry-run 并和用户一起确认候选池；`collection_log.csv` 里出现 `error` 状态的条目必须先按 `references/troubleshooting-checklist.md` 排查解决，再视为完成。

`pachong.py` 的完整逻辑讲解见 `references/code-walkthrough.md` 第一节。

---

## Step 5 保存与整理结果

采集结果固定落在项目文件夹下的 `<主题slug>_youtube_<日期8位>` 目录，结构：

```
<主题slug>_youtube_YYYYMMDD/
├── videos.csv        # 入选视频表（含 url、播放量快照）
├── comments.csv      # 评论主表（comment_id / video_id / 时间 / 点赞 / 正文）
├── candidates.csv    # 全部候选视频，供审查选样规则
├── collection_log.csv# 搜索、短缺、配额、网络错误全程记录
└── raw/              # 已去标识化的 API 原始响应，保证可复现
```

整理规则：一次调研一个文件夹，新数据不覆盖旧目录（需要新一批就换 `--output-dir` 指定新文件夹，或换主题 slug）；`raw/` 与日志视为证据链，禁止删改。

**`comments.csv` 是纯净、无身份字段的数据**：写入前已移除评论者显示名、头像、频道链接。这一点在 Step 6 建立分析目录时要保持——分析脚本只读它，绝不修改。

## Step 6 整理结果文件与建立分析目录

分析需要一个**独立的目录**，与采集目录并列，原始采集数据只读：

```
<项目文件夹>/
├── pachong.py
├── youtube_api_key.txt
├── <主题slug>_youtube_YYYYMMDD/     ← 采集产出（只读输入）
└── <主题slug>_analysis_YYYYMMDD/    ← 分析目录（本阶段新建）
    ├── pipeline_common.py           ← 共享路径与复现配置
    ├── run_analysis.py              ← 一键跑完五个阶段
    ├── requirements.txt
    ├── 01_prepare_data.py
    ├── 02_topic_analysis.py
    ├── 03_sentiment_analysis.py
    ├── 04_semantic_network.py
    ├── 05_build_report.py
    ├── data/       ← 派生语料（清洗后）
    ├── results/    ← 结果表（主题、情感、网络）
    ├── figures/    ← 图表 PNG
    ├── reports/    ← Word 分析报告
    └── cache/      ← 模型与 pip 缓存（都在项目内，不污染系统）
```

**关键约束：原始采集目录是只读的。** 分析流水线的第一步会计算 `comments.csv` 与 `videos.csv` 的 SHA-256，跑完再算一次并比对，写入 `data/preparation_summary.json` 的 `raw_hashes_unchanged` 字段。这个设计保证"分析没有偷偷改数据"。

各脚本的职责、路径配置方式与中英文版本的差异，见 `references/analysis-pipeline.md`。

## Step 7 语料准备（清洗 + 语种识别）

运行 `01_prepare_data.py`。它做四件事：

1. **文本清洗**：删除空白、少于 5 字符、纯链接、纯符号数字的内容，以及规范化后的重复评论；每一步的排除原因都记录在 `data/cleaning_audit.csv`，可回溯。
2. **语种识别**：用 fastText 的 `lid.176.bin` 模型判断每条评论的语种；只保留目标语种且**置信度 ≥ 0.80** 的内容。
3. **产出正式语料**：`data/english_comments.csv` 或 `data/chinese_comments.csv`。
4. **绘制漏斗图**：`figures/fig_01_cleaning_funnel.png`，直观展示"原始评论 → 清洗后 → 正式语料"的数量变化。

```bash
conda activate dhr
cd /d <项目文件夹>\<主题slug>_analysis_YYYYMMDD
conda run -n dhr python 01_prepare_data.py
```

**为什么要做语种过滤？** 中英混合语料直接做主题建模会把两种语言的词向量混在一起，主题变得不可解释。所以分析前必须先按语种切分。中英两个语言通常各建一个分析目录，各自独立跑完五个阶段。

## Step 8 主题建模（BERTopic）

运行 `02_topic_analysis.py`。技术链路是：

```
句向量（Sentence-Transformer） → UMAP 降维 → HDBSCAN/KMeans 聚类 → c-TF-IDF 提取关键词
```

产出（都在 `results/`）：

| 文件 | 内容 |
| --- | --- |
| `topic_summary.csv` | 每个主题的编号、评论数、模型关键词标签、研究者解释标签 |
| `topic_keywords.csv` | 每个主题的 Top-10 关键词及 c-TF-IDF 分数 |
| `topic_assignments.csv` | 每条评论归属哪个主题（含离群标记） |
| `topic_representative_quotes.csv` | 每个主题点赞最高的 5 条代表性评论（写作时引用） |
| `topic_metadata.json` | 模型名、设备、参数、主题计数等元数据 |

图表：`fig_02_topic_sizes.png`（主题规模）与 `fig_03_topic_umap.png`（主题空间平面投影）。

**关键点——主题命名是"研究者解释"，不是模型自动生成。** 模型的 `keyword_label` 只是一串高频词（如 `story | animation | character`），必须结合主题规模、关键词和代表性引文，由人写出可读的主题名（如"动画品质与观影推荐"）。这一步的写法见 `references/analysis-pipeline.md`。

## Step 9 情感分析

运行 `03_sentiment_analysis.py`。产出：

| 文件 | 内容 |
| --- | --- |
| `sentiment_assignments.csv` | 每条评论的三分类标签与各概率 |
| `sentiment_summary.csv` | 正面/中性/负面各多少条、占比多少 |
| `sentiment_keywords.csv` | 每类情感的 Top-30 高权重内容词（TF-IDF） |
| `monthly_sentiment.csv` | 逐月情感占比（**仅描述性**，不做趋势推断） |
| `topic_sentiment_crosstab.csv` | 主题 × 情感的交叉表（百分比） |
| `sentiment_metadata.json` | 模型名、阈值、与对照方法的一致率 |

图表：情感分布柱状图、月度堆叠图、正负面词云两张、主题情感热力图。

**必须用第二种方法做稳健性对照。** 主模型之外再跑一个独立方法，报告两者一致率，用它说明"结果能站到什么程度"。中英文的对照方法选择见 `references/analysis-pipeline.md`。

## Step 10 语义网络分析

运行 `04_semantic_network.py`。它把评论内容词建成一张共现网络：

1. 只保留名词、专有名词、形容词、动词（词形还原 / 词性标注后）；
2. 在**五词滑动窗口**内统计两两共现次数；
3. 保留 Top-60 节点、Top-180 边，用 Louvain 算法划分概念社群；
4. 计算加权度与介数中心性。

产出 `results/network_nodes.csv`、`network_edges.csv`、`network_centrality_top25.csv`、`network_metadata.json`；图表为网络图与中心性排行。

**解读红线：边只表示"共现倾向"，不表示因果关系。** 报告里必须写明这一点，不能把网络中心性说成"影响力"或"因果机制"。

## Step 11 生成纯文字调研报告

最终交付物之一，**纯文字版 .txt**（UTF-8 编码），不要 docx/pdf/xlsx。文件名：`<主题名>_调研报告_YYYYMMDD.txt`，存入采集目录的 `reports/` 子目录。报告结构按 `assets/report_template.txt` 模板填充，至少包含：调研对象与方法、采集数量（实际值）、数据概览、主要发现、局限与复现说明。发现必须来自 `comments.csv`/`videos.csv` 的真实统计，禁止虚构数字。

## Step 12 生成学术分析报告（Word）

运行 `05_build_report.py`。它会读取全部结果表，生成一份**中文学术风格的 Word 报告**，落盘到分析目录的 `reports/`。

报告标准结构（十章，见 `assets/analysis_report_template.txt`）：

```
标题 / 副标题
摘要 + 关键词
一、研究问题与研究设计
二、数据处理与方法
三、主题发现
四、情感结构及其主题差异
五、语义网络
六、讨论
七、局限与结论
附录：可复现性信息
```

**报告里的每一个数字都从结果表动态读取，不写死。** 附录会写入输入文件哈希、清洗漏斗、模型参数、随机种子、依赖包版本，构成完整的复现凭据。

学术写作的体例要求（时态、引文、图表题注、局限性写法）见 `references/report-writing-guide.md`。

一键跑完第 7~12 步：

```bash
conda run -n dhr python run_analysis.py
```

---

## 常见错误与检查清单

完整排查表（环境类报错、Missing API key、429 配额、commentsDisabled、网络超时、候选短缺、CSV 乱码、resume 不生效、模型下载卡住、显存/内存不足等）和执行前/中/后三张检查清单，统一见 `references/troubleshooting-checklist.md`。任务收尾前必须逐项过完"完成后检查清单"并向用户汇报结果。

## Resources

- `references/environment-setup.md` — **环境与依赖完全指南（Step 0 必读）**：Python/conda/库概念、Anaconda 从零安装、建 `dhr` 环境、两档依赖（采集零依赖 / 分析 17 个库）、缓存位置、环境自检三连、环境类报错表。
- `references/api-key-guide.md` — YouTube Data API v3 密钥从零申请图文步骤 + 密钥文件存放位置与安全规范（Step 1 必读）。
- `references/topic-brief-template.md` — 《调研主题单》填写模板 + 新增 `Topic` 配置示例（Step 2 必读）。
- `references/analysis-pipeline.md` — **五阶段分析流水线详解（Step 6~12 必读）**：目录结构、脚本职责、模型选择与参数含义、中英文版本差异、结果表字段说明。
- `references/code-walkthrough.md` — **代码逐段导读**：`pachong.py` 与 5 个分析脚本的函数级讲解，想读懂或改代码时看。
- `references/report-writing-guide.md` — 学术报告写作指南：结构、体例、图表题注、发现表述、局限性写法。
- `references/troubleshooting-checklist.md` — 常见错误排查表 + 执行前/中/后检查清单（Step 4、收尾时读）。
- `assets/report_template.txt` — 纯文字调研报告模板（Step 11 复制填充）。
- `assets/analysis_report_template.txt` — 学术分析报告大纲模板（Step 12 参考）。
- `assets/scripts_manifest.md` — 全部代码文件清单与作用索引。
