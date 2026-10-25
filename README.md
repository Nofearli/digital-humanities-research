# lsh-digital-humanities-research — zero-background skills for digital-humanities field research

Step-by-step skills that take someone with **no technical background** from a blank computer to a
finished, reproducible digital-humanities study.

Default data source is **YouTube Data API v3** (public top-level comments only).

The guiding principle is that a beginner should only ever have to answer questions and paste commands.
Every command, every error message, and every folder is explained in plain language, and the skills
distinguish clearly between a **zero-dependency collection step** and a **heavier analysis step** so
nobody is scared off by a long dependency list.

## What's inside

### `skills/lsh-digital-humanities-research/` — collection only (7 steps)

Environment setup → API credentials → topic brief → volume → collect → organize → plain-text report.

| Document | Purpose |
|---|---|
| `SKILL.md` | The 7-step collection workflow, hard rules, completion checklist |
| `references/environment-setup.md` | Installing Anaconda from zero, creating the environment, the two dependency tiers, where caches land, a three-command readiness check |
| `references/api-key-guide.md` | Obtaining a YouTube Data API v3 key from zero, where the key file must live, security red lines |
| `references/topic-brief-template.md` | The six questions that define a study, slug rules, output-directory rules, `TOPICS` entry syntax |
| `references/troubleshooting-checklist.md` | Error tables, pre-flight / in-flight / post-flight checklists |
| `assets/report_template.txt` | Plain-text report template |

### `skills/lsh-dhr-full-research/` — collection **and** analysis (12 steps)

Everything above, plus the five-stage analysis pipeline and a full code walkthrough.

| Document | Purpose |
|---|---|
| `SKILL.md` | The 12-step workflow covering collection **and** analysis |
| `references/analysis-pipeline.md` | The five analysis stages in detail: script duties, model choices, parameter meaning, Chinese/English differences, result-table fields |
| `references/code-walkthrough.md` | Function-level walkthrough of `pachong.py` and all five analysis scripts |
| `references/report-writing-guide.md` | Academic writing: structure, register, figure captions, how to phrase findings and limitations |
| `references/environment-setup.md` | Environment guide, extended with the analysis dependencies |
| `references/api-key-guide.md` | API key guide |
| `references/topic-brief-template.md` | Topic brief template |
| `references/troubleshooting-checklist.md` | Error tables, extended with analysis-stage errors |
| `assets/report_template.txt` | Plain-text report template |
| `assets/analysis_report_template.txt` | Academic analysis report outline |
| `assets/scripts_manifest.md` | Index of every code file and what it does |

## The collection workflow (7 steps)

| Step | What happens | Who decides |
|---|---|---|
| 0 · Environment | install/activate Python environment, check readiness | skill runs the checks |
| 1 · API key | obtain key, place `youtube_api_key.txt` beside the collector | user creates the file |
| 2 · Topic brief | six questions: subject, aliases, content type, exclusions, language/period, volume | **user** |
| 3 · Volume | videos per language, comments per video, total ceiling | **user** |
| 4 · Collect | dry-run to audit candidates, then full collection, resumable | skill runs it |
| 5 · Organize | the five-file output set plus raw evidence folder | skill runs it |
| 6 · Report | plain-text `.txt` report from real statistics | skill writes it |

## The analysis workflow (5 additional stages)

| Stage | Script | What it produces |
|---|---|---|
| 1 · Prepare | `01_prepare_data.py` | Cleaned, language-filtered corpus with an auditable exclusion trail |
| 2 · Topics | `02_topic_analysis.py` | BERTopic themes, keywords, representative quotes |
| 3 · Sentiment | `03_sentiment_analysis.py` | Three-class sentiment plus a second-method robustness check |
| 4 · Network | `04_semantic_network.py` | Weighted co-occurrence network with communities and centrality |
| 5 · Report | `05_build_report.py` | Academic Word report with figures, tables and reproducibility metadata |

`run_analysis.py` runs all five in order.

## Reference implementation

`code/` holds a working implementation you can copy into your project folder:

```
code/
├── collector/
│   └── pachong.py              # the collector (zero third-party dependencies)
├── analysis-en/                # English-comment pipeline
│   ├── pipeline_common.py
│   ├── run_analysis.py
│   ├── requirements.txt
│   └── 01_…05_*.py
└── analysis-zh/                # Chinese-comment pipeline
    ├── pipeline_common.py
    ├── run_analysis.py
    ├── requirements.txt
    └── 01_…05_*.py
```

To use it: copy `collector/pachong.py` into your project folder, put your
`youtube_api_key.txt` beside it, then copy one of the `analysis-*` folders and point
`RAW_ROOT` in `pipeline_common.py` at your own collection directory.

> The `analysis-*` scripts contain study-specific labels (`INTERPRETED_TOPIC_LABELS`,
> `TOPIC_CN`) that must be rewritten for a new subject. The templates are provided as
> examples of *how* to write them, not as content to reuse.

## Design notes

**Two dependency tiers.** Collection runs on the Python standard library alone — no `pip install`
needed. Only the analysis stage needs third-party packages, and each pipeline carries its own
`requirements.txt`.

**Key handling.** Credentials never go into chat, into source files, or into Git. The skills require a
local key file sitting next to the collector script, and say so in several places because this is the
single most common beginner failure. `*_api_key.txt` is git-ignored.

**Plain text by default for the collection report.** The required collection deliverable is a `.txt`
report in UTF-8, not a Word or PDF file, so it stays diffable, portable and reproducible. The
analysis stage additionally produces a formatted Word report, because academic use needs figures and
tables.

**Evidence, not vibes.** The collection output keeps `candidates.csv`, `collection_log.csv` and a
`raw/` folder of de-identified API responses, so selection rules can be audited and the run
reproduced. Identity fields (display names, avatars, channel links) are stripped before anything is
written. The analysis pipeline re-hashes its inputs before and after running and records whether they
changed, so "the analysis did not touch the data" is verifiable rather than asserted.

**Reproducibility is recorded, not promised.** Every analysis stage writes metadata: model names,
parameters, random seed, cleaning funnel and package versions. The final report's appendix points to it.

## Requirements

- Windows (instructions are written for Anaconda Prompt; the commands are portable)
- Python 3.8+ (3.11 recommended)
- A Google account (for the API key)
- Collection: no third-party packages
- Analysis: ~17 packages per language pipeline, listed in each `requirements.txt`

## Scope and ethics

Reads public information only: searches public videos and reads public top-level comments. It does
not post, log in, collect replies, or retain commenter identity. Collection volume is bounded by
default and every deviation is recorded in the study's own report.

## License

MIT.
