---
name: digital-humanities-research
description: 面向完全零基础用户的数字人文调研全流程。当用户想从零完成一次"准备 Python/conda 环境 → 安装依赖库 → 申请并配置 API 密钥 → 填写调研主题 → 按指定数量抓取网络评论 → 保存整理结果 → 输出纯文字报告"时使用本技能，典型场景是采集 YouTube 视频评论做主题/情感/传播分析。覆盖环境与依赖安装（用什么环境、装哪些库、装到哪里）、密钥申请与存放文件夹、调研主题填写模板、采集数量配置、纯文字输出规范、常见报错排查与操作检查清单。触发词：数字人文、评论采集、API key、YouTube 采集、调研报告、环境配置、装库、conda 环境、评论爬取。
agent_created: true
---

# digital-humanities-research：零基础数字人文调研全流程

## Overview

本技能提供一条"傻瓜式"的数字人文调研流水线，从**准备运行环境**开始，到申请数据源 API 密钥、填写调研主题、按既定数量抓取公开评论、保存整理结果文件，最终输出一份**纯文字（.txt）调研报告**。面向完全没有技术背景的用户：所有命令由 WorkBuddy 代跑，用户只需回答几个问题、点几下鼠标。

默认调研对象为网络视频平台的公开评论，采集脚本 `pachong.py` 基于 **YouTube Data API v3**。

**两条关键事实（必须向用户讲清，避免被依赖清单吓退）：**

- **采集数据环节零第三方依赖** —— `pachong.py` 只用 Python 标准库，任何 Python 3.8+ 都能跑，一个库都不装也能完成任务；
- **只有做主题建模/情感分析/语义网络分析时**才需要安装 17 个第三方库（见 `references/environment-setup.md`）。

工作目录以用户自己的调研项目文件夹为准（下文以 `<项目文件夹>` 代指），采集脚本为 `pachong.py`。

## 何时使用

- 用户说"我想调研某个话题/电影/事件在网络上的评论、口碑"，且之前没有数据；
- 用户提到"申请 API key""抓评论""数字人文""做一份调研报告"；
- 用户提到"环境怎么配""要装什么库""conda 环境"等环境准备问题；
- 用户已有采集脚本但不知道如何配置密钥、填写主题、设定数量。

若用户的目标是"分析已采好的数据"（数据已存在），不要走本流程，直接进入分析阶段。

## 总体流程（7 步，严格按顺序执行）

```
① 准备运行环境与依赖      ← 零基础用户最容易卡住的一步，必读 environment-setup.md
② 申请并配置 API 密钥
③ 填写《调研主题单》（用户回答 6 个问题）
④ 确认采集数量配置
⑤ 试运行 + 正式抓取
⑥ 整理结果文件
⑦ 生成纯文字调研报告
→ 最后逐项过《操作检查清单》
```

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
2. 密钥文件的存放位置有且仅有一处：**项目文件夹根目录下的 `youtube_api_key.txt`**，即与 `pachong.py` **同级同一个文件夹**。示例路径：
   `<项目文件夹>/youtube_api_key.txt`
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

主题名转成英文 slug（小写字母数字下划线，如 `nezha2`）后：若 `pachong.py` 的 `TOPICS` 字典里已有该主题（如示例内置主题）直接复用；没有则按 `references/topic-brief-template.md` 末尾的示例，在 `TOPICS` 中新增一条 `Topic(...)` 配置，字段全部来自用户填写的内容，不得自行加戏。

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

## Step 6 输出纯文字调研报告

最终交付物**必须且只能是纯文字版 .txt**（UTF-8 编码），不要 docx/pdf/xlsx。文件名：`<主题名>_调研报告_YYYYMMDD.txt`，存入该主题输出文件夹的 `reports/` 子目录。报告结构按 `assets/report_template.txt` 模板填充，至少包含：调研对象与方法、采集数量（实际值）、数据概览、主要发现、局限与复现说明。发现必须来自 `comments.csv`/`videos.csv` 的真实统计，禁止虚构数字。

## 常见错误与检查清单

完整排查表（环境类报错、Missing API key、429 配额、commentsDisabled、网络超时、候选短缺、CSV 乱码、resume 不生效等）和执行前/中/后三张检查清单，统一见 `references/troubleshooting-checklist.md`。任务收尾前必须逐项过完"完成后检查清单"并向用户汇报结果。

## Resources

- `references/environment-setup.md` — **环境与依赖完全指南（Step 0 必读）**：Python/conda/库概念、Anaconda 从零安装、建环境、两档依赖（采集零依赖 / 分析 17 个库）、缓存位置、环境自检三连、环境类报错表。
- `references/api-key-guide.md` — YouTube Data API v3 密钥从零申请图文步骤 + 密钥文件存放位置与安全规范（Step 1 必读）。
- `references/topic-brief-template.md` — 《调研主题单》填写模板 + 新增 `Topic` 配置示例（Step 2 必读）。
- `references/troubleshooting-checklist.md` — 常见错误排查表 + 执行前/中/后检查清单（Step 4、收尾时读）。
- `assets/report_template.txt` — 纯文字调研报告模板（Step 6 复制填充）。

