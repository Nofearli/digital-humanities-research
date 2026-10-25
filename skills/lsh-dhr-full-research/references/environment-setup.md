# 参考资料：环境与依赖完全指南（零基础版）

> 本文件解决一个问题：**"我电脑上要装什么、命令敲在哪里。"**
> 目标读者：从没装过 Python、没听说过 conda、看到"环境"两个字就头疼的人。
> 全程只需要复制粘贴，不需要理解原理。看不懂的名词先跳过，照做即可。

---

## 一、先认识三个词（各用一句话）

| 名词 | 生活化解释 | 你只需要知道 |
| --- | --- | --- |
| **Python** | 一个"翻译官"，把我们写的 `pachong.py` 翻译成电脑能执行的指令 | 版本要 **3.8 以上**，本项目用 **3.11** |
| **conda / Anaconda** | 一个"工具箱管理器"，用来装 Python、并把不同项目的工具分开放，互不打架 | 本流程建议环境名 **`dhr`**（可自定义） |
| **库（package）** | 别人写好的现成工具，装上就能直接用 | **采集数据一个库都不用装**；只有做分析才需要 |

**最重要的一句话**：本项目的"采集数据"环节**零第三方依赖**——`pachong.py` 只用了 Python 自带的工具。所以哪怕你什么库都不装，也能把评论抓下来。

---

## 二、先选一条路线（只看电脑有没有 Anaconda）

打开电脑的"开始菜单"，搜索 `Anaconda Prompt`：

- **搜得到** → 走 **路线 A**（省事，5 分钟，推荐）
- **搜不到** → 走 **路线 B**（从零安装，约 30 分钟）

> 如果你电脑上已经有 Anaconda，直接走路线 A，**不要**重复安装。

---

## 三、路线 A：电脑已有 Anaconda（推荐）

### A1. 打开 Anaconda Prompt

开始菜单 → 搜索 `Anaconda Prompt` → 点击打开，会出现一个黑色（或白色）命令行窗口。以后所有命令都敲在这里。

### A2. 看看有哪些环境

```bash
conda env list
```

会列出类似下面的内容（星号 `*` 表示当前所在环境）：

```text
# conda environments:
#
base                     C:\Users\<你的用户名>\anaconda3
myproject                C:\Users\<你的用户名>\anaconda3\envs\myproject
dhr                     C:\Users\<你的用户名>\anaconda3\envs\dhr
```

- **列表里有 `dhr`** → 太好了，跳到 A3；
- **列表里没有 `dhr`** → 执行下面这行创建（约 2 分钟）：

```bash
conda create -n dhr python=3.11 -y
```

### A3. 激活环境

```bash
conda activate dhr
```

激活成功的标志：命令行最前面的括号从 `(base)` 变成 `(dhr)`。

> **每次开新窗口都要先敲这一行**。忘记激活是最常见的错误，报错通常是"找不到某个库"。

### A4. 进入项目文件夹

```bash
cd /d <你的项目文件夹>
```

把 `<你的项目文件夹>` 换成你自己放 `pachong.py` 的那个文件夹，例如 `D:\MyResearch\youtube-comments`。
（`/d` 是 Windows 下切换盘符用的；如果项目在 C 盘可以不写。）

### A5. 确认能用

```bash
python --version
```

显示 `Python 3.11.x` 就成功了。

---

## 四、路线 B：从零安装 Anaconda

### B1. 下载

打开浏览器访问 <https://www.anaconda.com/download>，选择 **Windows** 版本下载。
（文件较大，约 1 GB，耐心等。若下载慢，可搜索"Anaconda 清华镜像 下载"。）

### B2. 安装

双击下载的 `.exe`，一路点 **Next**。遇到下面两处请按提示选：

- "Installation Type" → 选 **Just Me**（只给当前用户装，最省事）；
- "Advanced Options" → 勾选 **Add Anaconda3 to my PATH environment variable**（虽然官方标注不推荐，但能避免后面"conda 不是内部命令"的报错）；
- 其余默认，最后点 **Install**，等它跑完（约 5～10 分钟）。

### B3. 验证安装

安装完成后**关闭所有命令行窗口，重新打开** Anaconda Prompt，敲：

```bash
conda --version
```

显示类似 `conda 24.x.x` 就装好了。

### B4. 建环境并激活

```bash
conda create -n dhr python=3.11 -y
conda activate dhr
```

---

## 五、装库（只有做"分析"才需要）

请先明确你要做哪一步：

| 你要做的事 | 需要装的库 |
| --- | --- |
| 只抓评论数据、导出 CSV | **什么都不用装**（0 个库） |
| 主题建模、情感分析、语义网络、生成图表 | 需要装下面这一批 |

### 档位 1：只采集（零安装）

确认环境已激活（命令行显示 `(dhr)`），直接运行即可。跳到第六节自检。

### 档位 2：要做分析

先进到分析脚本所在目录（分析脚本和 `requirements.txt` 放在一起）：

```bash
cd /d <你的项目文件夹>\<主题slug>_analysis_YYYYMMDD
```

再一次性安装全部依赖：

```bash
pip install -r requirements.txt
```

**中文分析需要的库共 18 个**（英文分析不需要 `jieba`、`snownlp`）：

```text
pandas          # 表格数据处理
numpy           # 数值计算
matplotlib      # 画图基础
seaborn         # 统计图表美化
wordcloud       # 词云
openpyxl        # 读写 Excel
fasttext-wheel  # 语种识别（区分中英文评论）
jieba           # 中文分词（仅中文分析）
snownlp         # 中文情感对照（仅中文分析）
scikit-learn    # 机器学习基础工具
umap-learn      # 降维（主题建模用）
hdbscan         # 聚类
bertopic        # 主题建模（核心）
transformers    # 预训练模型（情感分析用）
sentence-transformers  # 句向量（主题建模用）
torch           # 深度学习后端
networkx        # 语义网络图
python-docx     # 生成 Word 报告
```

**英文分析**把 `jieba`、`snownlp` 换成 `spacy`（自然语言处理，用于词形还原）和 `vaderSentiment`（英文情感对照），共 17 个。

> **提示**：性能较好的机器上，以上依赖通常 10～20 分钟可装完（含 `torch` 等大包）。
> 如果换电脑、或新建环境时才需要跑 `pip install`；已有可用环境则跳过。
>
> 如果 pip 下载太慢，加国内镜像源重试：
>
> ```bash
> pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
> ```

### 还要单独下载 spaCy 英文模型（仅英文分析）

英文的语义网络分析需要 spaCy 的英文模型，它不在 `requirements.txt` 里，要单独装一次：

```bash
python -m spacy download en_core_web_sm
```

中文分析不需要这一步（用 jieba，无需额外模型）。

---

## 六、装到哪儿了？缓存都在哪？

你可能会担心"装一堆东西会不会把我电脑搞乱"。不会。本项目的设计是**所有缓存都落在项目文件夹内**：

| 内容 | 存放位置 | 说明 |
| --- | --- | --- |
| Python 环境本身 | conda 安装目录下的 `envs\dhr` | 由 conda 统一管理 |
| pip 下载缓存 | `<分析目录>\cache\pip` | 由脚本自动指定 |
| Hugging Face 模型 | `<分析目录>\cache\huggingface` | 句向量与情感分析模型首次运行时自动下载 |
| fastText 语种模型 | `<分析目录>\cache\models\lid.176.bin` | 首次运行 `01_prepare_data.py` 时**自动下载**，约 130 MB，无需手动操作 |
| 句向量模型 | `<分析目录>\cache\models\sentence_transformers` | 主题建模用 |
| jieba 词典缓存 | `<分析目录>\cache\jieba` | 仅中文分析，由脚本自动指定 |

也就是说：**模型不用你手动下载**，第一次跑分析脚本时它会自己下好，之后就复用本地缓存。

**为什么缓存要落在项目内**：`pipeline_common.py` 在导入 transformers 之前会设置 `HF_HOME`、`TRANSFORMERS_CACHE`、`PIP_CACHE_DIR` 等环境变量，强制把这些库的缓存写进项目目录。如果不这么做，模型会下到系统盘的用户目录，一个项目就能占掉好几个 GB。

> 模型下载需要联网。如果卡住或超时，重跑一次脚本即可（已下好的部分不会重复下载）。

---

## 七、环境自检三连（做完这三条再开始正式任务）

在项目文件夹、`dhr` 环境激活状态下，依次执行：

```bash
# 第 1 条：确认 Python 版本
python --version
# 期望：Python 3.11.x

# 第 2 条：确认环境里能读到库（做分析才需要）
python -c "import pandas; print('pandas OK', pandas.__version__)"
# 期望：打印 pandas OK 和版本号
# 报 ModuleNotFoundError 也没关系——只采集的话这步可以跳过

# 第 3 条：确认脚本和密钥都能读到（不消耗配额）
python pachong.py --topic <你的主题slug> --dry-run
# 期望：输出 "Candidate discovery complete: N selected videos."
```

第 3 条如果提示 `Missing API key`，说明密钥文件没配好，请看 `api-key-guide.md`。

---

## 八、环境类常见报错

| 报错 / 现象 | 原因 | 处理办法 |
| --- | --- | --- |
| `'conda' 不是内部或外部命令` | 没装 Anaconda，或没勾选加入 PATH | 走路线 B 重装并勾选 "Add to PATH"；或改用"开始菜单 → Anaconda Prompt"打开 |
| `conda: command not found` | 在普通 CMD/PowerShell 里敲了 conda | 换成 Anaconda Prompt；或先执行 conda 安装目录下的 `Scripts\activate.bat` |
| `ModuleNotFoundError: No module named 'pandas'`（或 bertopic 等） | ①没装库；②装到了别的环境；③忘了激活 | 先 `conda activate dhr`，再 `pip install -r requirements.txt` |
| 装完库还是报找不到模块 | 装到 `base` 环境去了 | 激活 `dhr` 后重装；用 `pip -V` 确认路径里含 `envs\dhr` |
| `pip` 下载超时 / 很慢 | 默认源在国外 | 加 `-i https://pypi.tuna.tsinghua.edu.cn/simple` |
| `python: command not found` | 环境没激活，系统里也没有 python | 先 `conda activate dhr` |
| 显示的不是 3.11.x 而是别的版本 | 激活的不是本项目环境（可能是别的环境或系统 Python） | 重新 `conda activate dhr`；必要时先 `conda deactivate` |
| 换电脑后什么都要重装 | 环境不会跟着文件夹走 | 在新电脑上按路线 A/B 重建环境、重装依赖、拷入密钥文件 |
| `Permission denied` / 无法写入 | 文件夹只读，或无权限 | 把项目放到用户目录下（如 `D:\MyResearch\`），不要放 `C:\Program Files\` |

---

## 九、给"完全不想碰命令行"的极简版

如果实在不想敲命令，WorkBuddy 可以代你执行全部命令。你只需要：

1. 在对话里说"帮我准备环境，我要开始调研了"；
2. WorkBuddy 会依次完成：检查 conda → 激活环境 → 检查依赖 → 运行 `--dry-run` 验证；
3. 你只负责提供 **API 密钥** 和回答 **调研主题的 6 个问题**。

但**密钥文件必须由你本人创建**（放在项目文件夹根目录，见 `api-key-guide.md`），不要让密钥出现在聊天记录里。
