# 参考资料：代码逐段导读

> 用法：当你想弄明白"这段代码到底在干什么"，或者想改代码但怕改坏时看这份文档。
> 目标读者：没写过 Python 或只写过一点点，但需要理解研究工具在做什么。
> 写法：按函数逐个讲，每个函数说清**它解决什么问题**、**关键参数**、**注意什么**。

---

## 一、采集脚本 `pachong.py`

这个脚本约 500 行，只使用 Python 标准库，是全流程唯一负责"上网拿数据"的代码。

### 1.1 顶部常量：排除规则

```python
EXCLUSION_TERMS = (
    "trailer", "teaser", "clip", "official trailer", "music video",
    "预告", "預告", "片段", "官方",
)
```

**作用**：任何一个视频，只要标题或简介里出现这些词，直接淘汰。

**为什么**：预告片、片段剪辑、官方宣传的评论区讨论的是"宣发物料"，不是"作品接受"。把它们混进来，主题分析会被带偏。

```python
NEZHA2_EXCLUSION_TERMS = ("封神", "fengshen", "creation of the gods")
```

**作用**：哪吒2 主题专属的额外排除。

**为什么需要主题级排除**：《封神》和《哪吒》同属封神宇宙、上映档期接近、观众重合度高，搜索"哪吒2 影评"时经常混进《封神》的视频。不排除就是数据串味。

> **做新主题时**：这个常量是针对哪吒2硬编码的。如果新主题也需要硬排除（比如西游记要排除《黑神话：悟空》），要在 `matches_eligibility` 里加一条同样写法的判断。

### 1.2 `Topic` 数据类：一个主题的全部规则

```python
@dataclass(frozen=True)
class Topic:
    slug: str                              # 主题短名，如 nezha2
    title: str                             # 主题全名
    published_after: str                   # 时间起点，ISO 格式
    language_queries: dict[str, list[str]] # 每种语言的检索词
    inclusion_terms: dict[str, tuple]      # 必须包含的语境词（影评/解析/反应）
    subject_terms: tuple[str, ...]         # 对象别名（哪吒2 / Ne Zha 2 …）
    per_language: int                      # 每种语言选几个视频
```

`frozen=True` 表示**创建后不可修改**——防止代码运行中被意外改掉规则，破坏可复现性。

**三个字段的过滤逻辑**（在 `matches_eligibility` 里依次执行）：

```text
① 含 EXCLUSION_TERMS？        → 淘汰（预告/片段/官方）
② 是主题专属排除词？           → 淘汰（封神）
③ subject_terms 非空且都不含？ → 淘汰（不是这个电影）
④ inclusion_terms 都不含？     → 淘汰（不是影评类内容）
⑤ 以上都通过                   → 保留
```

**顺序很重要**：先排除再加必须项。反过来会导致逻辑混乱。

### 1.3 `YouTubeClient.get()`：唯一的网络出口

```python
def get(self, resource: str, **params):
    query = {k: v for k, v in params.items() if v is not None}
    query["key"] = self.api_key
    url = f"{API_ROOT}/{resource}?{urlencode(query, doseq=True)}"
```

所有 API 调用都走这一个方法。核心设计是**重试机制**：

| 错误类型 | 处理 |
| --- | --- |
| 429 / 500 / 502 / 503 / 504 | 退避重试，最多 3 次；间隔 1s → 2s → 4s（`2**attempt`） |
| 其他 HTTP 错误 | 立即抛出 `ApiRequestError`，记入日志 |
| 网络超时 / URLError | 同样退避重试 3 次 |

**为什么用指数退避**：服务端限流时立刻重试只会雪上加霜。等 1 秒、2 秒、4 秒能让服务端恢复。这是与 API 打交道的基本礼貌。

### 1.4 `sanitize()`：隐私保护的核心

```python
def sanitize(value):
    sensitive = {"authorDisplayName", "authorProfileImageUrl", "authorChannelId", "authorChannelUrl"}
    if isinstance(value, dict):
        return {k: sanitize(v) for k, v in value.items() if k not in sensitive}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value
```

**这个函数是整个项目最重要的伦理设计。** 它在数据落盘前递归遍历 API 响应，删掉四个身份字段：

- `authorDisplayName` —— 评论者昵称
- `authorProfileImageUrl` —— 头像地址
- `authorChannelId` —— 频道唯一 ID
- `authorChannelUrl` —— 主页链接

**为什么必须是递归的**：API 响应的嵌套层级不固定，评论可能在 `items[].snippet.topLevelComment.snippet` 里。手写路径容易漏，递归遍历才可靠。

**谁调用它**：`write_json()` 里。也就是说**所有写入磁盘的 JSON 都自动过一遍脱敏**。这个设计保证"忘记脱敏"这种错误不可能发生。

### 1.5 `write_json()`：原子写入

```python
temporary = path.with_suffix(path.suffix + ".tmp")
temporary.write_text(json.dumps(sanitize(data), ...), encoding="utf-8")
temporary.replace(path)
```

**为什么先写临时文件再 rename**：如果直接写目标文件，中途断电或崩溃会留下一个**半截的损坏文件**。先写 `.tmp` 再原子替换，保证磁盘上要么是完整的旧文件、要么是完整的新文件。

**为什么 `ensure_ascii=False`**：让中文以原本的样子存进去，而不是 `\u4e2d\u6587` 这种转义序列。文件可读性完全不同。

### 1.6 `append_csv()`：一个容易踩的 BOM 坑

```python
exists = path.exists() and path.stat().st_size > 0
with path.open("a", newline="", encoding="utf-8" if exists else "utf-8-sig") as handle:
```

**背景**：`utf-8-sig` 会在文件开头写入 BOM（字节顺序标记），让 Excel 能正确识别中文编码。但 BOM **只能出现在文件开头**。

**坑在哪**：采集是分页追加写的——抓一页追加一批。如果每次都写 `utf-8-sig`，第一页之后再追加的内容前面都会多插一个 BOM，文件就坏了。

**解法**：只有文件不存在时才用 `utf-8-sig`（写表头的那一次），后续追加一律用 `utf-8`。这样既让 Excel 能打开，又不会中途插 BOM。

### 1.7 `matches_eligibility()`：准入判断

```python
def matches_eligibility(title, description, language, topic=None):
    topic = topic or TOPICS["fengshen"]
    corpus = f"{title} {description}".lower()
    if any(term.lower() in corpus for term in EXCLUSION_TERMS):
        return False
    if topic.slug == "nezha2" and any(term in corpus for term in NEZHA2_EXCLUSION_TERMS):
        return False
    if topic.subject_terms and not any(term.lower() in corpus for term in topic.subject_terms):
        return False
    return any(term.lower() in corpus for term in topic.inclusion_terms[language])
```

四道关卡依次判断，逻辑就是 1.2 里那张流程图。注意最后一行是 `return`，前面都是提前 `return False`。

**`subject_terms` 为空时跳过第三关**——`fengshen` 主题的 `subject_terms=()` 就是这种情况，因为"封神"这个词本身就是唯一的标题标识，不需要别名列表。

### 1.8 `discover_candidates()`：搜索 + 元数据

两步走：

**第一步：跑检索词，建立 video_id → 检索词的映射**

```python
provenance: dict[tuple[str, str], set[str]] = defaultdict(set)
for language, queries in topic.language_queries.items():
    for index, query in enumerate(queries, start=1):
        response = client.get("search", part="snippet", q=query, type="video",
                             maxResults=50, order="relevance",
                             relevanceLanguage="zh-Hans" if language == "zh" else "en",
                             publishedAfter=topic.published_after)
```

关键点：

- **每次搜索花 100 单位配额**。4 个中文检索词 + 4 个英文检索词 = 8 次搜索 = 800 单位，占日配额的 8%。
- `provenance` 是**双向映射**：记录"哪些检索词命中了这个视频"。一个视频可能被多个检索词命中，这些命中词会写进 `videos.csv` 的 `matched_queries` 列，供审查选样规则。
- 每次搜索的原始响应都存到 `raw/discovery/zh_1_search.json` 等文件——**这是证据链**，日后可以核对"当时搜出来的到底是什么"。

**第二步：批量补充视频统计信息**

```python
for batch_index, batch in enumerate(chunks(video_ids, 50), start=1):
    response = client.get("videos", part="snippet,statistics", id=",".join(batch), maxResults=50)
```

**为什么要第二步**：搜索接口（`search`）返回的统计信息不可靠、且不包含完整字段。要拿准确的播放量和评论数，必须用 `videos` 接口查。

**为什么按 50 个一批**：API 单次请求的 ID 上限就是 50 个。

### 1.9 `select_candidates()`：按播放量取前 N

```python
for language in ("zh", "en"):
    for candidate in sorted(grouped[language], key=lambda item: (-item.view_count, item.video_id)):
```

排序键是 `(-view_count, video_id)`：**先按播放量降序，播放量相同时按 ID 升序**。

**为什么要加第二个排序键**：只按播放量排，播放量相同的视频顺序取决于原始顺序，可能导致每次运行选出不同的视频，破坏可复现性。加 ID 作为决胜键，结果就唯一了。

**`selected_ids` 集合的作用**：防止同一个视频在中英两个池子里被重复选中。虽然罕见，但中英检索词可能命中同一个视频（比如带双语标题的）。

### 1.10 `collect_top_level_comments()`：抓评论

```python
while examined < max_comments:
    response = client.get("commentThreads", part="snippet", videoId=video_id,
                         maxResults=min(100, max_comments - examined),
                         order="time", textFormat="plainText", pageToken=page_token)
```

四个关键参数：

| 参数 | 值 | 原因 |
| --- | --- | --- |
| `order="time"` | 按时间倒序 | 取"最新"的评论，与研究设定一致 |
| `textFormat="plainText"` | 纯文本 | 避免 HTML 标签混进语料 |
| `maxResults` | 最多 100 | API 单页上限 |
| `min(100, max_comments - examined)` | 动态 | 最后一页只取需要的那几条，不浪费配额 |

**`examined` 与 `collected` 是两个不同计数器**：

- `examined` —— **扫描过**多少条（含已存在的重复评论）
- `collected` —— **新写入**多少条

这个区分很重要。用 `--resume` 续跑时会加载已有的 `comment_id` 集合，重复的评论会被跳过但 `examined` 仍然递增。所以进度条显示的"已扫描 X 条，X 条新评论"两个数字可能不相等，这是正常的。

**只抓顶层评论**：代码从不请求 `comments` 接口（那是抓回复的），只请求 `commentThreads` 并只取 `snippet.topLevelComment`。这一约束在 `normalize_thread` 里落实。

### 1.11 `normalize_thread()`：只要研究需要的字段

```python
top_level = thread.get("snippet", {}).get("topLevelComment", {})
snippet = top_level.get("snippet", {})
comment_id = top_level.get("id")
if not comment_id or not snippet.get("textOriginal"):
    return None
return {
    "comment_id": str(comment_id), "video_id": video_id,
    "published_at": ..., "updated_at": ...,
    "like_count": int(snippet.get("likeCount", 0)),
    "text": str(snippet["textOriginal"]),
    "collection_timestamp": timestamp,
}
```

**双重保护**：

1. 返回 `None` 的条件——没有 ID 或没有正文的评论被丢弃（可能是已删除评论的残留）；
2. 只挑 7 个字段输出。**即使 `sanitize()` 失效了，这里也只输出不含身份的字段**。两道防线。

**为什么用 `textOriginal` 而不是 `textDisplay`**：`textDisplay` 含 HTML 标签，`textOriginal` 是评论者输入的原始文本。

### 1.12 `without_replies()`：原始快照也要干净

```python
cleaned["items"] = [{k: v for k, v in item.items() if k != "replies"} for item in response.get("items", [])]
```

API 响应里如果带上 `replies` 字段，会包含回复内容和回复者信息。这个函数在写入原始 JSON 前把它剥掉。

**为什么单独处理**：`sanitize()` 删的是身份字段，`without_replies()` 删的是**整个回复分支**。两个函数解决不同问题，都不能省。

### 1.13 `main()`：命令行入口与流程编排

```python
parser.add_argument("--topic", choices=sorted(TOPICS), default="nezha2")
parser.add_argument("--output-dir", type=Path)
parser.add_argument("--per-language", type=int, choices=range(1, 51))
parser.add_argument("--api-key-file", type=Path, default=default_key_file())
parser.add_argument("--resume", action="store_true")
parser.add_argument("--dry-run", action="store_true")
parser.add_argument("--max-comments", type=int, default=1000, choices=range(1, 1001))
```

**密钥加载顺序**（`load_api_key`）：

```python
if key_file.exists():
    key = key_file.read_text(encoding="utf-8").strip()
    if key:
        return key
return os.getenv("YOUTUBE_API_KEY", "").strip()
```

**先读文件，再读环境变量**。文件优先，环境变量是备选。

**`--resume` 的两层跳过逻辑**：

```python
if args.resume and videos_path.exists():
    selected = selected_from_rows(read_csv(videos_path))     # 复用已选视频
...
completed = {row["video_id"] for row in read_csv(log_path)
             if row["stage"] == "comments" and row["status"] == "complete"}
for video_number, video in enumerate(selected, start=1):
    if args.resume and video.video_id in completed:
        log_event(log_path, "comments", "skipped", "already complete", video.video_id)
        continue
```

第一层：**跳过整轮的搜索**（复用 `videos.csv` 里已选的视频，不再花搜索配额）；
第二层：**跳过已抓完的视频**（查日志里有 `complete` 记录的）。

**第三层去重**在 `collect_top_level_comments` 里：`existing_ids` 从已有 `comments.csv` 加载，重复评论不写入。所以中断的视频会重新扫描，但不会产生重复行。

**这就是为什么 `--resume` 必须在同一输出目录**：它依赖 `videos.csv` 和 `collection_log.csv` 里的历史记录。换了目录，这两份文件不存在，`--resume` 就退化成一次全新采集。

### 1.14 `render_progress()`：无依赖进度条

```python
ratio = min(scanned / maximum, 1) if maximum else 1
filled = round(width * ratio)
bar = "#" * filled + "-" * (width - filled)
print(f"\r视频 {video_number}/{total_videos} [{bar}] ...", end="", flush=True)
```

用 `\r`（回车不换行）在原地刷新，`flush=True` 保证立即输出而不是等缓冲区满。

**为什么不用 `tqdm` 这类进度条库**：为了让采集脚本**保持零依赖**。多引入一个库，就多一个"新手装不上环境"的失败点。

---

## 二、分析脚本的公共部分

### 2.1 `pipeline_common.py`

不单独运行，被其他五个脚本导入。核心是路径集中管理。

```python
ROOT = Path(__file__).resolve().parent
RAW_ROOT = ROOT.parent / "<主题slug>_youtube_YYYYMMDD"
```

**⚠️ 换主题时必须改 `RAW_ROOT`**，否则脚本会去读旧主题的数据。这是"数据串味"的头号原因。

```python
def set_reproducibility(seed=RANDOM_SEED):
    random.seed(seed)
    try:
        import numpy as np
        np.random.seed(seed)
    except ImportError:
        pass
    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass
```

**三个库都要设**：`random`（Python 内置）、`numpy`、`torch`。BERTopic 内部会用到后两者，只设 Python 的 `random` 不够。

**用 `try/except ImportError` 包住**：这样只装了部分库时脚本仍能跑（比如只想重画图表）。

```python
os.environ.setdefault("HF_HOME", str(HF_HOME))
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(HF_HOME / "hub"))
os.environ.setdefault("TRANSFORMERS_CACHE", str(HF_HOME / "hub"))
os.environ.setdefault("PIP_CACHE_DIR", str(PIP_CACHE_DIR))
```

**为什么必须在导入 transformers 之前设**：这些库在**导入时**就读环境变量决定缓存位置。晚设无效，模型会下到系统盘的用户目录里，把 C 盘撑爆。

**这就是"缓存都在项目内"的实现方式**——不是靠自觉，是靠环境变量强制指定。

### 2.2 `run_analysis.py`

```python
STAGES = ["01_prepare_data.py", "02_topic_analysis.py", "03_sentiment_analysis.py",
          "04_semantic_network.py", "05_build_report.py"]

for stage in STAGES:
    print(f"\n=== Running {stage} ===")
    subprocess.run([sys.executable, str(ROOT / stage)], cwd=ROOT, check=True)
```

用 `subprocess` 逐个启动子进程，`check=True` 表示**某一步失败就立刻停止**，不会带着错误数据继续往下跑。

**为什么用子进程而不是 `import` 后调用**：每个阶段会加载大量库并占用内存，跑完就释放。子进程隔离避免了内存累积和模块状态污染。

---

## 三、阶段①：`01_prepare_data.py`

### 3.1 清洗判断函数

```python
def pre_language_reason(text):
    if not text:
        return "blank"
    if len(text) < 5:
        return "shorter_than_5_characters"
    if re.fullmatch(r"(?:https?://\S+\s*)+", text, flags=re.IGNORECASE):
        return "url_only"
    if not re.search(r"[A-Za-z\u4e00-\u9fff]", text):
        return "no_alphabetic_or_cjk_content"
    return None
```

**返回 `None` 表示"通过"，返回字符串表示"拒绝原因"。** 这个设计让拒绝原因能直接写进审计表，不用另写映射。

四个判断的含义：

| 判断 | 拦掉什么 |
| --- | --- |
| `not text` | 空文本 |
| `len < 5` | "好""👍""nb"这类无信息量短评 |
| 纯链接 | 只有 URL，无观点 |
| 无字母也无汉字 | 纯 emoji、纯数字、纯符号 |

注意最后一个用 `\u4e00-\u9fff` 匹配 CJK 汉字区间。**这是"纯符号评论"的判定**——一堆 ❤️ 或 🔥 对文本分析无意义。

### 3.2 去重的实现细节

```python
seen_normalized: set[str] = set()
...
if reason is None and text.lower() in seen_normalized:
    reason = "normalized_duplicate"
if reason is None:
    seen_normalized.add(text.lower())
    retained_pre_language.append(index)
```

用 **小写 + 规范化空白** 后的文本做去重键。这样 "太好 了" 和 "太好　了"（不同空白字符）会被识别为重复。

**为什么要去重**：社交平台上复制粘贴的评论、刷屏的同一句话会大量重复，不去重会让某个观点在主题模型里被过度放大。

### 3.3 fastText 语种识别的兼容性处理

```python
def detect_language(model, text):
    # fasttext-wheel's public ``predict`` currently calls ``np.array(...,
    # copy=False)``, which is incompatible with NumPy 2.  Its wrapped C++
    # object returns the same label/probability pair without that conversion.
    prediction = model.f.predict(text.replace("\n", " "), 1, 0.0, "__label__")
    probability, label = prediction[0]
    return str(label).replace("__label__", ""), float(probability)
```

**这是一个真实的坑，值得展开说**：

`fasttext-wheel` 库的公开方法 `model.predict()` 内部调用了 `np.array(..., copy=False)`。NumPy 2.0 之后这个 `copy=False` 参数的行为变了，会直接报错。绕过方法是**直接调用底层的 C++ 对象** `model.f.predict()`——它返回同样的结果，但没走那个有问题的转换。

**这就是"为什么用 `model.f` 而不是 `model`"的答案。** 看到这行代码不要以为是笔误。

另外 `text.replace("\n", " ")`：fastText 把换行当作记录分隔符，多行文本会被当成多条。必须先换成空格。

### 3.4 哈希校验：证明数据没被动过

```python
raw_hashes_before = {"comments.csv": sha256(RAW_COMMENTS), "videos.csv": sha256(RAW_VIDEOS)}
# ... 整个处理过程 ...
raw_hashes_after = {"comments.csv": sha256(RAW_COMMENTS), "videos.csv": sha256(RAW_VIDEOS)}
metadata = {..., "raw_hashes_unchanged": raw_hashes_before == raw_hashes_after}
```

**在流程开始和结束时各算一次输入文件的 SHA-256，比对结果。**

这是"可复现研究"的标准做法：如果分析过程中不小心写了原始文件，哈希会变，`raw_hashes_unchanged` 变成 `false`，立刻暴露问题。

### 3.5 漏斗图为什么用 `Counter`

```python
funnel = Counter({"raw_comments": len(comments), "after_text_cleaning": len(eligible),
                  "english_analysis_corpus": len(english)})
```

用 `Counter` 而非 `dict` 是为了后续能方便地做计数运算。中文版直接用了普通 dict，效果一样，只是写法差异。

**注意中文版的键名是中文**：`{"原始评论": ..., "文本清洗后": ..., "高置信度中文": ...}`。因为中文版报告的漏斗图要用中文标签，直接拿这个 dict 当图表的 x 轴。英文版则用英文键名配英文图表。

---

## 四、阶段②：主题建模代码

### 4.1 英文版：完整的 BERTopic 链路

```python
encoder = SentenceTransformer(EMBEDDING_MODEL, cache_folder=str(MODELS_DIR / "sentence_transformers"), device=device)
embeddings = encoder.encode(documents, batch_size=64 if device == "cuda" else 16,
                            show_progress_bar=True, normalize_embeddings=True)
np.save(RESULTS_DIR / "document_embeddings.npy", embeddings)
```

**三个要点**：

- `cache_folder` 指到项目内，模型不进系统盘；
- `batch_size` 根据设备自动调整，GPU 用 64，CPU 用 16（CPU 上大批量反而慢）；
- `normalize_embeddings=True` —— 把向量归一化，之后用**余弦距离**衡量相似度才正确；
- **`np.save` 把向量存下来**，后续阶段（比如 UMAP 画图）可以直接复用，不用重新编码。这是很实际的性能优化——编码 1 万条评论在 CPU 上要几分钟。

```python
vectorizer = CountVectorizer(
    stop_words=sorted(ENGLISH_STOP_WORDS | DOMAIN_STOP_WORDS),
    ngram_range=(1, 2),
    min_df=max(3, len(documents) // 1000),
)
```

- `ngram_range=(1, 2)` —— 同时考虑单词和双词组合（"animation quality" 比单独的 "animation" 更有信息量）；
- `min_df` 动态计算：语料越大，要求词出现次数越多。1000 条以下要求 3 次，10000 条就要求 10 次。

```python
umap_model = UMAP(n_neighbors=15, n_components=5, min_dist=0.0, metric="cosine", random_state=RANDOM_SEED)
hdbscan_model = HDBSCAN(min_cluster_size=min_topic_size, min_samples=3,
                        metric="euclidean", cluster_selection_method="eom", prediction_data=True)
```

**`n_components=5` 而不是 2**：降到 5 维是为了聚类（保留更多结构信息），降到 2 维只是为了画图。这是两件事，不要混淆——脚本里后面画 UMAP 图时**另建了一个 `n_components=2` 的 UMAP**，原因就在这。

**`min_dist=0.0`**：让点尽量聚紧，利于聚类算法识别密集区域。

**`prediction_data=True`**：允许后续给新文本预测主题归属。

### 4.2 离群标记与关键词提取

```python
topic_info["is_outlier"] = topic_info["topic_id"].eq(-1)

keyword_rows = []
for topic_id in topic_info.loc[~topic_info["is_outlier"], "topic_id"]:
    for rank, (word, score) in enumerate(topic_model.get_topic(int(topic_id)) or [], start=1):
        if rank > 10:
            break
        keyword_rows.append({"topic_id": topic_id, "rank": rank, "keyword": word, "c_tf_idf_score": score})
```

`~topic_info["is_outlier"]` 是布尔取反，即"只要非离群主题"。每个主题取前 10 个关键词。

### 4.3 人工解释标签的应用

```python
topic_info["interpreted_label"] = topic_info["topic_id"].map(INTERPRETED_TOPIC_LABELS).fillna("Outlier / mixed")
```

用 `.map()` 把字典里的中文/英文主题名映射到每个主题上，`.fillna()` 给没定义的主题（含离群）填默认值。

**这行的意义**：模型给的是数字编号和关键词串，`interpreted_label` 才是人写的、能进报告的主题名。

### 4.4 中文版的固定 KMeans

```python
topic_model = BERTopic(
    ...,
    hdbscan_model=KMeans(n_clusters=TARGET_TOPICS, random_state=RANDOM_SEED, n_init=20),
    ...
)
```

**为什么中文版改用 KMeans**（代码注释原话）：初始的 HDBSCAN 方案在这个语料上产生了"一个过大的混合簇和若干 15-20 条评论的噪声簇"——自动聚类失效了。固定 8 簇能得到可解释的结果。

**代价**：KMeans 没有离群概念，所有评论都被分配，中文版结果里没有 `topic_id = -1`。

### 4.5 中文版独立提取关键词

```python
keyword_vectorizer = TfidfVectorizer(tokenizer=str.split, token_pattern=None, preprocessor=None,
                                     lowercase=False, min_df=1, ngram_range=(1, 2))
keyword_matrix = keyword_vectorizer.fit_transform(tokenized)
```

**注意四个特殊参数**：

- `tokenizer=str.split` —— 因为文本已经用 jieba 分好词、用空格连成了字符串，所以直接按空格切；
- `token_pattern=None` —— 必须显式设为 None，否则 sklearn 会用默认的正则去切，把中文切碎；
- `preprocessor=None` —— 禁用默认的小写转换（中文不需要）；
- `lowercase=False` —— 同上。

**为什么绕开 BERTopic 的内建关键词**：用固定 KMeans 聚类时，BERTopic 的表示层有时产不出有意义的中文词。独立用 TF-IDF 在每个簇内重新算，并把原始分数完整保留。

---

## 五、阶段③：情感分析代码

### 5.1 三分类结果的归一化

```python
def canonical_label(label):
    label = label.lower()
    if "neg" in label or label.endswith("0"):
        return "negative"
    if "neu" in label or label.endswith("1"):
        return "neutral"
    if "pos" in label or label.endswith("2"):
        return "positive"
    return label
```

**为什么需要这个函数**：不同模型的标签命名不统一。有的是 `LABEL_0/1/2`，有的是 `negative/neutral/positive`，有的是 `NEG/NEGATIVE`。这个函数把它们统一成 `negative/neutral/positive` 三个标准名。

**注意 `endswith("0")` 这种判断**：这是给 `LABEL_0` 这类命名准备的。这种映射依赖模型的固定约定，换模型时必须核对——把 `LABEL_0` 当成正面还是负面搞反了，整个结论就颠倒了。

### 5.2 停用词的三层设计

```python
ANALYSIS_STOP_WORDS = set(ENGLISH_STOP_WORDS) | { ... 大量领域词 ... }
GEOPOLITICAL_STOP_WORDS = { "china", "chinese", "american", ... }
ANALYSIS_STOP_WORDS |= GEOPOLITICAL_STOP_WORDS
```

**关键在注释里**：

```python
# Country, regional and national-identity terms are analytically important for
# the topic/network stages, but are excluded from the two sentiment word clouds
# so that their visual emphasis falls on evaluative adjectives/adverbs...
```

**国家地区词在这个脚本里被排除，但在主题和网络阶段保留。** 因为它们是重要的分析对象，但在情感词云里会淹没真正的评价性词汇。

**这是个有意的、局部的处理，不是全局规则。** 报告方法部分应该说明这一点。

### 5.3 VADER 作为对照

```python
vader = SentimentIntensityAnalyzer()
...
compound = vader.polarity_scores(comment["normalized_text"])["compound"]
rows.append({..., "vader_compound": compound, "vader_sentiment": vader_label(compound)})

def vader_label(score):
    return "positive" if score >= 0.05 else "negative" if score <= -0.05 else "neutral"
```

阈值 ±0.05 是 VADER 的**官方推荐值**，不是随便定的。

**一致率的计算**：

```python
agreement = (sentiment["sentiment"] == sentiment["vader_sentiment"]).mean()
```

逐条比对两个方法的标签，算相同比例。这个数字会写进 `sentiment_metadata.json`，也在报告里出现。

### 5.4 词云的内容词处理

```python
TOKEN_PATTERN = re.compile(r"[A-Za-z]{3,}")

def content_terms(text):
    return " ".join(token.lower() for token in TOKEN_PATTERN.findall(text) if token.lower() not in ANALYSIS_STOP_WORDS)
```

只保留 **3 个字母以上**的英文词，且不在停用词表里。

**为什么要额外过滤一次**：词云的输入虽然已经经过停用词处理，但 `WordCloud` 只接受一个词表参数，处理粒度不如正则精确。先手工清洗成纯内容词再喂给词云，效果更可控。

### 5.5 中文的特殊处理

```python
SENTIMENT_MODEL = "uer/roberta-base-finetuned-jd-binary-chinese"
POSITIVE_THRESHOLD = 0.60
NEGATIVE_THRESHOLD = 0.40

def to_three_class(score):
    return "positive" if score >= POSITIVE_THRESHOLD else "negative" if score <= NEGATIVE_THRESHOLD else "neutral"
```

**二分类变三分类的机制**：模型输出"正面概率"，≥0.60 判正面，≤0.40 判负面，中间的 (0.40, 0.60) 判中性。

**这个方法学局限必须写进报告**：中文的"中性"是**概率区间策略**的产物，不是模型独立训练出来的类别。它反映的是"模型不太确定"，而不是"态度中立"。

```python
model_dir = MODELS_DIR / "transformers"
tokenizer = AutoTokenizer.from_pretrained(SENTIMENT_MODEL, cache_dir=str(model_dir))
```

中文版手动控制批次和 `torch.no_grad()`：

```python
with torch.no_grad():
    probabilities = torch.softmax(model(**inputs).logits, dim=1).detach().cpu().numpy()
```

`torch.no_grad()` **关闭梯度计算**——推理时不需要梯度，关掉能省大量内存和计算。

### 5.6 `--reuse-classifications` 参数

```python
if args.reuse_classifications and assignment_path.exists():
    sentiment = pd.read_csv(assignment_path, encoding="utf-8-sig")
    model_device = "reused cached classifications"
else:
    sentiment, model_device = infer_sentiment(corpus)
```

模型推理很慢（CPU 上 1 万条评论要十几分钟），但画图很快。改了配色、标题、字号时用这个参数跳过推理，几秒钟就重画完了。

---

## 六、阶段④：语义网络代码

### 6.1 英文版的词形还原

```python
tokens = [
    token.lemma_.lower()
    for token in document
    if token.is_alpha
    and not token.is_stop
    and token.lemma_.lower() not in DOMAIN_STOP_WORDS
    and len(token.lemma_) >= 3
    and token.pos_ in {"NOUN", "PROPN", "ADJ", "VERB"}
]
```

**五个过滤条件**：

| 条件 | 作用 |
| --- | --- |
| `token.is_alpha` | 只留纯字母词（排除数字、标点） |
| `not token.is_stop` | 用 spaCy 内置停用词表 |
| 不在 `DOMAIN_STOP_WORDS` | 领域泛词 |
| `len >= 3` | 太短的词信息量低 |
| `pos_ in {...}` | **只留名词、专有名词、形容词、动词** |

**最后一条是关键**：副词（quickly）、介词、连词等对概念网络没有贡献，反而制造噪声。

**`token.lemma_.lower()`** —— 先还原再小写。spaCy 的 `lemma_` 自动把 `running` → `run`、`better` → `good`。

### 6.2 词汇表的两级筛选

```python
minimum_document_frequency = max(8, len(corpus) // 200)
vocabulary = {term for term, frequency in document_frequency.most_common()
              if frequency >= minimum_document_frequency}
vocabulary = set(sorted(vocabulary, key=lambda term: (-document_frequency[term], term))[:TOP_TERMS])
```

**两级筛选**：

1. **文档频次门槛** —— 出现在少于 8 条评论（或语料的 1/200）里的词直接扔掉。它们太冷门，共现统计没有统计意义。
2. **取 Top-60** —— 排序键又是 `(-频次, 词)`，和 `select_candidates` 一样，加第二个键保证可复现。

### 6.3 滑动窗口共现

```python
for tokens in token_lists:
    filtered = [token for token in tokens if token in vocabulary]
    for start in range(len(filtered)):
        window = filtered[start + 1 : start + WINDOW_SIZE]
        for partner in window:
            if filtered[start] != partner:
                edge_counts[tuple(sorted((filtered[start], partner)))] += 1
```

**三重循环的含义**：对每个位置，看它后面 **4 个词**（`WINDOW_SIZE=5` 表示含自己在内 5 个位置），每对词计数一次。

**`tuple(sorted((a, b)))`** —— 排序后组键，保证 `(a,b)` 和 `(b,a)` 是同一条边，不重复计数。

**`filtered[start] != partner`** —— 排除自环。

**窗口是在过滤后的序列上滑动的**，不是原始序列。也就是说停用词不占窗口位置。这个设计让共现更聚焦于内容词之间的关系。

### 6.4 社群发现与中心性

```python
try:
    communities = list(nx.community.louvain_communities(graph, weight="weight", seed=RANDOM_SEED))
except AttributeError:
    communities = list(nx.community.greedy_modularity_communities(graph, weight="weight"))
```

**`try/except AttributeError` 的原因**：Louvain 算法在较新版本的 NetworkX 里才有。旧版本会报 `AttributeError`，此时降级用贪心模块度算法。**这是向后兼容的写法**，保证不同版本的 NetworkX 都能跑。

```python
weighted_degree = dict(graph.degree(weight="weight"))
betweenness = nx.betweenness_centrality(graph, weight="weight", normalized=True)
```

`weight="weight"` 表示**按边的权重计算**，不是简单计数。`normalized=True` 把介数中心性归一化到 0-1 区间，方便比较。

### 6.5 绘图：节点大小与颜色映射

```python
nx.draw_networkx_nodes(graph, position,
                       node_size=[95 + weighted_degree[node] * 9 for node in graph.nodes],
                       node_color=[membership[node] for node in graph.nodes],
                       cmap="tab20", alpha=0.94, ...)
```

- **节点大小** = `95 + 加权度 × 9`，度数越大节点越大（有 95 的基础值，保证最小节点也看得见）；
- **节点颜色** = 社群编号，用 `tab20` 色板（20 种颜色的定性色板，适合区分类别）。

**边的宽度也做了映射**：

```python
width=[0.3 + data["weight"] / max(1, edge_frame["weight"].max()) * 2.7 for _, _, data in graph.edges(data=True)]
```

归一化到 0.3~3.0 像素之间。`max(1, ...)` 防止除以零。

### 6.6 中文版的词性过滤

```python
KEEP_POS_PREFIXES = ("n", "v", "a")

def content_tokens(text):
    return [pair.word.strip() for pair in pseg.cut(text)
            if len(pair.word.strip()) >= 2
            and CJK_TOKEN.search(pair.word.strip())
            and pair.word.strip() not in STOP_WORDS
            and pair.flag.startswith(KEEP_POS_PREFIXES)
            and not pair.word.strip().isdigit()]
```

用 `pseg.cut()` 做词性标注，`pair.flag` 是词性标签（如 `n`、`nr`、`v`、`a`）。用 `startswith(("n","v","a"))` 匹配前缀，比 `in` 更精确（`ns` 地名也以 n 开头）。

**中文没有词形还原**——中文不存在 `running/run` 这种变形，所以只需要过滤，不需要还原。

---

## 七、阶段⑤：报告生成代码

### 7.1 字体设置（中英文混排的关键）

```python
def set_run_font(run, size=10.5, bold=False):
    run.font.name = "Times New Roman"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
```

**这四行是 Word 中英文混排的标准写法**：

- `run.font.name = "Times New Roman"` 设置**西文**字体；
- `qn("w:eastAsia")` 是操作 OOXML 的东方字体属性，设置**中文**字体。

**为什么必须分开设**：Word 文档里西文和中文用不同的字体槽。只设 `font.name` 的话中文会用默认字体（宋体），和英文的 Times New Roman 混排时很不协调。这是 `python-docx` 的一个著名坑——它没有直接的中文字体 API，必须操作底层 XML。

`qn` 是 `qualified name`，把 `"w:eastAsia"` 展开成完整的命名空间路径。

### 7.2 段落格式

```python
def add_body(document, text):
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.first_line_indent = Cm(0.74)   # 首行缩进两个字
    paragraph.paragraph_format.line_spacing = 1.45            # 行距
    paragraph.paragraph_format.space_after = Pt(5)            # 段后间距
    run = paragraph.add_run(text)
    set_run_font(run, 10.5)
```

`Cm(0.74)` **是"首行缩进两字符"的标准实现**——10.5pt 字号下两个汉字约 0.74 厘米。这是中文学术文档的排版惯例。

### 7.3 图表插入与题注

```python
def add_figure(document, filename, caption, explanation="", width=15.5):
    path = FIGURES_DIR / filename
    if path.exists():
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.add_run().add_picture(str(path), width=Cm(width))
        add_caption(document, caption)
        if explanation:
            add_body(document, explanation)
```

**`if path.exists()` 这个判断很重要**：如果某张图没生成（比如某个阶段失败了），报告不会崩溃，只是缺那张图。这让报告生成有容错性。

**结构是"图 + 题注 + 说明文字"**，符合学术规范——图下标号，然后正文解释图说了什么。

### 7.4 表格生成

```python
def add_table(document, frame, columns, limit=None):
    display = frame.loc[:, columns].head(limit) if limit else frame.loc[:, columns]
    table = document.add_table(rows=1, cols=len(columns))
    table.style = "Table Grid"
```

`Table Grid` 样式给表格加全边框——学术表格的三线表需要更精细的设置，但全边框是最稳妥的默认。

### 7.5 数字全部动态读取

```python
english_total = prep["funnel"]["english_analysis_corpus"]
sentiment_map = dict(zip(sentiment["sentiment"], sentiment["share"]))
sentiment_count = dict(zip(sentiment["sentiment"], sentiment["comment_count"]))
positive_terms = "、".join(sentiment_keywords[sentiment_keywords["sentiment"].eq("positive")].head(8)["term"].tolist())
```

**这三个字典/字符串是报告的"数据源"**：正文里的每个数字、每个词列表都从这里取。

**`zip()` 把两列拼成字典**，之后用 `sentiment_map.get("positive", 0)` 取值，`.get` 的第二参数是默认值（防止某类情感没有数据时报错）。

### 7.6 复现元数据

```python
for package in ("pandas", "bertopic", "transformers", "sentence-transformers", "networkx", "spacy", "python-docx"):
    try:
        versions[package] = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        versions[package] = "not found"
```

用 `importlib.metadata` 读取已安装包的**实际版本号**，而不是读 `requirements.txt`（那里没写版本）。

**为什么重要**：模型和库的行为会随版本变化。记录确切版本，别人才能复现你的结果。

### 7.7 输出文件名的处理

```python
# The original report may be open in Word; keep it untouched and write the
# revised, expanded report to a distinct filename.
output = REPORTS_DIR / "哪吒2英语YouTube评论计算分析报告_修订版.docx"
```

**注释说明了原因**：如果原报告正在 Word 里打开着，直接覆盖会失败（Windows 文件锁）。写到一个新文件名可以避开这个问题。

**做新主题时这个文件名要改。** 保留 `_修订版` 后缀是个变通做法，更干净的方式是跑之前先关掉 Word。

---

## 八、想改代码时怎么办

### 8.1 安全的改法

| 想改什么 | 改哪里 | 注意 |
| --- | --- | --- |
| 换主题 | `pachong.py` 的 `TOPICS` | **只新增键，不改已有主题** |
| 换检索词 | 同上，`language_queries` | 每种语言 3~4 个 |
| 改数量 | 命令行参数 | 不用改代码 |
| 改分析的数据源 | `pipeline_common.py` 的 `RAW_ROOT` | **最容易忘的一处** |
| 改主题名 | `INTERPRETED_TOPIC_LABELS` / `TOPIC_CN` | 必须重写，不能沿用 |
| 改主题数 | `TARGET_TOPICS` | 只对中文版（KMeans）有效 |
| 改停用词 | 各脚本顶部的 `STOP_WORDS` | 三个脚本各有一份，要同步改 |
| 改图表配色 | 绘图代码里的 `palette` / `colormap` | 改完用 `--reuse-classifications` 快速重画 |

### 8.2 改之前

1. **先跑通再改**。原版能跑出结果，是你判断"改坏了没有"的唯一基准；
2. **一次只改一处**，改完就跑。同时改五处，出错了你根本不知道是哪个导致的；
3. **改完核对 `raw_hashes_unchanged`**。如果你不小心改动了原始数据，这个字段会暴露。

### 8.3 三条不要碰的红线

1. **不要去掉 `sanitize()`**。它是隐私保护的实现。去掉之后写进磁盘的 JSON 会带评论者昵称和头像链接，这是伦理问题，不是技术问题。
2. **不要为了凑数放宽排除规则**。合格视频不够时（日志出现 `shortfall`），正确做法是补检索词或补别名，**不是**放宽 `EXCLUSION_TERMS`。后者会让预告片混进来污染数据。
3. **不要把主题名沿用别人的**。主题编号在每次运行时对应不同内容，沿用等于造假。
