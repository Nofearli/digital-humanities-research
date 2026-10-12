# digital-humanities-research — a zero-background skill for digital-humanities field research

A step-by-step skill that takes someone with **no technical background** from a blank computer to a
finished, reproducible digital-humanities study: environment setup → API credentials → topic brief →
comment collection → file organization → plain-text report.

Default data source is **YouTube Data API v3** (public top-level comments only).

The guiding principle is that a beginner should only ever have to answer questions and paste commands.
Every command, every error message, and every folder is explained in plain language, and the skill
distinguishes clearly between a **zero-dependency collection step** and an optional
**heavier analysis step** so nobody is scared off by a long dependency list.

## What's inside

- **Entry point:** `SKILL.md` — the 7-step workflow (environment → API key → topic brief → volume → collect → organize → report), plus hard rules and a completion checklist.
- **`references/environment-setup.md`** — the full guide for people who have never installed Python:
  what Python / conda / a library actually are, installing Anaconda from scratch, creating the
  environment, the two dependency tiers, where caches land, a three-command readiness check, and an
  environment-error table.
- **`references/api-key-guide.md`** — obtaining a YouTube Data API v3 key from zero (Google Cloud
  Console, step by step), where the key file must live, and the security red lines.
- **`references/topic-brief-template.md`** — the six questions that define a study, a filled-in brief
  template, slug rules, output-directory rules, and how to translate the brief into a collector
  `TOPICS` entry.
- **`references/troubleshooting-checklist.md`** — an environment-error table, a collection/data-error
  table, and pre-flight / in-flight / post-flight checklists.
- **`assets/report_template.txt`** — the plain-text report template (the required deliverable format).

## The 7 steps

| Step | What happens | Who decides |
|---|---|---|
| 0 · Environment | install/activate Python environment, check readiness | skill runs the checks |
| 1 · API key | obtain key, place `youtube_api_key.txt` beside the collector | user creates the file |
| 2 · Topic brief | six questions: subject, aliases, content type, exclusions, language/period, volume | **user** |
| 3 · Volume | videos per language, comments per video, total ceiling | **user** |
| 4 · Collect | dry-run to audit candidates, then full collection, resumable | skill runs it |
| 5 · Organize | the five-file output set plus raw evidence folder | skill runs it |
| 6 · Report | plain-text `.txt` report from real statistics | skill writes it |

## Design notes

**Two dependency tiers.** Collection runs on the Python standard library alone — no `pip install`
needed. Only the optional analysis stage needs third-party packages, and that list is given explicitly
with its own install command.

**Key handling.** Credentials never go into chat, into source files, or into Git. The skill requires a
local key file sitting next to the collector script, and says so in several places because this is the
single most common beginner failure.

**Plain text by default.** The required deliverable is a `.txt` report in UTF-8, not a Word or PDF
file, so it stays diffable, portable, and reproducible.

**Evidence, not vibes.** The output layout keeps `candidates.csv`, `collection_log.csv`, and a `raw/`
folder of de-identified API responses, so the selection rules can be audited and the run reproduced.
Identity fields (display names, avatars, channel links) are stripped before anything is written.

## Requirements

- Windows (instructions are written for Anaconda Prompt; the commands are portable)
- Python 3.8+ (3.11 recommended)
- A Google account (for the API key)
- Collection: no third-party packages. Analysis: 17 packages, listed in `references/environment-setup.md`

## Usage

Copy the skill into a project's skills directory and ask for a study to be run:

```text
.workbuddy-ai/skills/digital-humanities-research/
```

The skill triggers on requests such as "collect comments about X", "do a digital-humanities study",
"set up the environment for comment collection", or "write up a survey report".

## Scope and ethics

Reads public information only: searches public videos and reads public top-level comments. It does not
post, log in, collect replies, or retain commenter identity. Collection volume is bounded by default
and every deviation is recorded in the study's own report.

## License

MIT. See the repository for details.
