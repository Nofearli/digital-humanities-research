# 参考资料：常见错误排查表 + 操作检查清单

> 用法：采集过程中遇到报错先查第一节和第二节；任务收尾前必须逐项过第三节的清单。
> 所有命令都在项目文件夹下、环境激活后执行（下文以 `dhr` 指代环境名）。

---

## 一、环境类报错（新手最常卡在这里）

| 报错 / 现象 | 原因 | 处理办法 |
| --- | --- | --- |
| `'conda' 不是内部或外部命令` | 没装 Anaconda，或装的时候没勾选加入 PATH | 改用"开始菜单 → Anaconda Prompt"打开；或走 `environment-setup.md` 路线 B 重装 |
| `conda: command not found` | 在普通 CMD / PowerShell 里敲 conda | 换 Anaconda Prompt 窗口；或先执行 conda 安装目录下的 `Scripts\activate.bat` |
| 命令行开头是 `(base)` 而不是 `(dhr)` | 忘了激活本项目环境 | 执行 `conda activate dhr` |
| `ModuleNotFoundError: No module named 'pandas'`（或 bertopic / transformers 等） | ①没装库；②装到了别的环境；③环境没激活 | 先 `conda activate dhr`；再 `pip install -r requirements.txt`（在分析脚本目录执行）。只做采集的话可忽略此报错 |
| 装完库仍报找不到模块 | 库装进了 `base` 或别的环境 | 用 `pip -V` 看路径里有没有 `envs\dhr`；不对就激活 dhr 后重装 |
| pip 下载很慢 / 超时 | 默认源在国外 | 加国内源：`pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple` |
| `python: command not found` | 环境没激活，系统也没有独立 Python | 先 `conda activate dhr` |
| 显示的 Python 版本不是 3.11.x | 当前不在 dhr 环境（可能是系统 Python 或其他环境） | 先 `conda deactivate` 再 `conda activate dhr` |
| `python -m unittest -v` 显示 "Ran 0 tests" | **正常现象**：项目目录没有 `test_*.py` 测试文件 | 无需处理，这不是错误；环境是否就绪请看 `environment-setup.md` 第七节的"自检三连" |
| fastText / HuggingFace 模型下载卡住 | 首次运行需联网下载模型（约 130 MB 起） | 重跑脚本即可，已下载部分不会重复下载；或检查网络代理 |
| `Permission denied` / 写入被拒 | 文件夹只读或无权限 | 把项目放在用户目录下（如 `D:\MyResearch\`），不要放 `C:\Program Files\` |

## 二、采集与数据类报错

| 现象 / 报错 | 原因 | 处理办法 |
| --- | --- | --- |
| `Missing API key` | 找不到 `youtube_api_key.txt`，或文件是空的 | 确认 `youtube_api_key.txt` **与 `pachong.py` 在同一个文件夹**（项目根目录），仅一行密钥、无引号无空格；或用 `--api-key-file` 指定实际路径 |
| HTTP 403 `quotaExceeded` | 今日 API 配额（10,000 单位）用尽 | 等次日（太平洋时间零点重置）；或去 Google Cloud Console 新建密钥明天用；近期同一主题不要重复全量采集 |
| HTTP 403 `accessNotConfigured` / `SERVICE_DISABLED` | 项目没启用 YouTube Data API v3 | 回 Console → API 和服务 → 库 → 启用后重试 |
| HTTP 400 `keyInvalid` | 密钥复制错、多了空格或换行 | 重新复制，检查文件只有一行 39 个字符左右 |
| 日志出现 `comments_disabled` | 该视频关闭评论，平台正常状态 | 无需处理，程序自动跳过；最终报告里如实写明"部分视频评论关闭" |
| 日志出现 `error` + `networkError` / `TimeoutError` | 网络波动 | 脚本自带 3 次重试；仍失败就用 `--resume` 重跑，只补未完成的视频 |
| 429 / 5xx 反复出现 | 请求太密或 Google 侧波动 | 稍等几分钟后用 `--resume` 续跑 |
| 选中的视频少于预期（日志 `shortfall`） | 合格视频不足 | 检查 `candidates.csv` 是否被过滤太狠：补检索词、补别名；**不要**为凑数放宽排除规则 |
| `comments.csv` 打不开或中文乱码 | Excel 默认编码不是 UTF-8 | 用 VS Code / pandas 打开；需要 Excel 就"数据→自文本/自 CSV"导入并选 UTF-8 |
| `--resume` 没有跳过已完成视频 | 上次运行没写 `complete` 日志或换了输出目录 | `--resume` 只能在**同一个输出目录**用；确认 `collection_log.csv` 里有对应 `complete` 记录 |
| 评论抓下来数量远低于预期 | 视频本身评论少，或已达 1,000 上限 | 属正常；核对 `videos.csv` 的 `comment_count` 快照对比即可 |
| 误把不同批次数据混在一起 | 复用了旧输出目录 | 每次新调研换新目录（新 slug 或 `--output-dir`），旧目录只读保留 |

---

## 三、执行前检查清单

- [ ] **环境就绪**：`conda activate dhr` 成功（命令行显示 `(dhr)`），`python --version` 显示 3.11.x
- [ ] **依赖就绪**：只采集则无需装库；要分析则 `python -c "import pandas"` 不报错
- [ ] `youtube_api_key.txt` 在项目根目录、与 `pachong.py` 同级、仅一行密钥，且未出现在聊天/Git/代码里
- [ ] YouTube Data API v3 已在 Google Cloud 项目启用，密钥已限制到该 API
- [ ] 《调研主题单》六问全部有答案，slug 命名合规（小写字母数字下划线）
- [ ] `TOPICS` 配置与主题单一致（新增主题时已写入并保存文件）
- [ ] 采集数量（每语言视频数、每视频评论数）已与用户确认并记录
- [ ] 已 dry-run 并和用户一起核对过 `candidates.csv`

## 四、执行中检查清单

- [ ] 正式采集使用正确的 `--topic <slug>` 与输出目录
- [ ] 进度条正常滚动；中断后用 `--resume` 续跑
- [ ] `collection_log.csv` 无遗留未解决的 `error`（`shortfall`、`comments_disabled` 需在报告中说明）

## 五、完成后检查清单

- [ ] 输出目录为 `<slug>_youtube_YYYYMMDD`，`videos.csv` / `comments.csv` / `candidates.csv` / `collection_log.csv` / `raw/` 五件套齐全
- [ ] `comments.csv` 行数与日志统计吻合，不含评论者用户名、头像、频道链接等身份字段
- [ ] 实际采集数量（视频数、评论数）已统计，报告里写真实值不写默认值
- [ ] 纯文字报告已按 `assets/report_template.txt` 生成，保存为 `<主题名>_调研报告_YYYYMMDD.txt`，位于该主题输出目录的 `reports/` 子目录，UTF-8 编码
- [ ] 已向用户汇报：报告位置、数据规模、`shortfall` / `comments_disabled` 等例外情况、复现命令
- [ ] 提醒用户：如需再采一批，换新目录；旧目录只读留存
