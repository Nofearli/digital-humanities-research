#!/usr/bin/env python3
"""Collect small, reproducible YouTube comment corpora about selected films.

The collector uses the public YouTube Data API v3.  It deliberately collects
only top-level, published comments and removes display-name/profile fields
before API responses are written to disk.

Usage (PowerShell):
  # Put the key in youtube_api_key.txt beside this script (recommended), or
  # set YOUTUBE_API_KEY for the current terminal.
  python pachong.py --topic fengshen --dry-run
  python pachong.py --topic nezha2 --resume
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


API_ROOT = "https://www.googleapis.com/youtube/v3"
EXCLUSION_TERMS = (
    "trailer", "teaser", "clip", "official trailer", "music video", "预告", "預告", "片段", "官方",
)
NEZHA2_EXCLUSION_TERMS = ("封神", "fengshen", "creation of the gods")


@dataclass(frozen=True)
class Topic:
    """The reproducible search and selection policy for one film corpus."""

    slug: str
    title: str
    published_after: str
    language_queries: dict[str, list[str]]
    inclusion_terms: dict[str, tuple[str, ...]]
    subject_terms: tuple[str, ...]
    per_language: int


TOPICS = {
    "fengshen": Topic(
        slug="fengshen",
        title="Fengshen Part I",
        published_after="2023-07-01T00:00:00Z",
        language_queries={
            "zh": ["封神第一部 影评", "封神第一部 电影评价", "封神第一部 解析"],
            "en": [
                "Creation of the Gods I review",
                "Creation of the Gods I Kingdom of Storms review",
                "Fengshen First Part review",
            ],
        },
        inclusion_terms={
            "zh": ("影评", "影評", "评价", "評價", "解析", "观后感", "觀後感", "反应", "反應"),
            "en": ("review", "reaction", "analysis", "ending explained", "thoughts"),
        },
        subject_terms=(),
        per_language=10,
    ),
    "nezha2": Topic(
        slug="nezha2",
        title="Ne Zha 2 / 哪吒之魔童闹海",
        published_after="2025-01-01T00:00:00Z",
        language_queries={
            "zh": ["哪吒之魔童闹海 影评", "哪吒2 影评", "哪吒之魔童闹海 解析", "哪吒2 观后感"],
            "en": ["Ne Zha 2 review", "Ne Zha 2 reaction", "Nezha 2 review", "Ne Zha 2 analysis"],
        },
        inclusion_terms={
            "zh": (
                "影评", "影評", "评价", "評價", "解析", "观后感", "觀後感", "反应", "反應", "解说", "解說", "讲解", "講解",
            ),
            "en": ("review", "reaction", "analysis", "ending explained", "thoughts", "explained", "recap"),
        },
        subject_terms=("哪吒之魔童闹海", "哪吒2", "哪吒 2", "魔童闹海", "ne zha 2", "nezha 2", "ne zha ii", "nezha ii"),
        per_language=15,
    ),
}
VIDEO_FIELDS = [
    "video_id", "language", "matched_queries", "title", "description", "channel_id", "channel_title",
    "published_at", "view_count", "comment_count", "url", "selection_timestamp",
]
COMMENT_FIELDS = [
    "comment_id", "video_id", "published_at", "updated_at", "like_count", "text", "collection_timestamp",
]
LOG_FIELDS = ["timestamp", "stage", "video_id", "status", "detail"]


class ApiRequestError(RuntimeError):
    """An API response that should be recorded rather than silently ignored."""

    def __init__(self, status: int | None, reason: str, detail: str = "") -> None:
        self.status, self.reason, self.detail = status, reason, detail
        super().__init__(f"YouTube API error {status or 'network'}: {reason} {detail}".strip())


class YouTubeClient:
    def __init__(self, api_key: str, retries: int = 3, sleeper: Callable[[float], None] = time.sleep) -> None:
        self.api_key = api_key
        self.retries = retries
        self.sleeper = sleeper

    def get(self, resource: str, **params: Any) -> dict[str, Any]:
        query = {key: value for key, value in params.items() if value is not None}
        query["key"] = self.api_key
        url = f"{API_ROOT}/{resource}?{urlencode(query, doseq=True)}"
        for attempt in range(self.retries + 1):
            try:
                with urlopen(url, timeout=30) as response:  # nosec B310: fixed Google API root
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                payload = _read_error_payload(exc)
                reason = _api_reason(payload) or exc.reason or "httpError"
                if exc.code in (429, 500, 502, 503, 504) and attempt < self.retries:
                    self.sleeper(2**attempt)
                    continue
                raise ApiRequestError(exc.code, str(reason), _api_message(payload)) from exc
            except (URLError, TimeoutError) as exc:
                if attempt < self.retries:
                    self.sleeper(2**attempt)
                    continue
                raise ApiRequestError(None, "networkError", str(exc.reason if isinstance(exc, URLError) else exc)) from exc


@dataclass
class Candidate:
    video_id: str
    language: str
    matched_queries: set[str]
    title: str
    description: str
    channel_id: str
    channel_title: str
    published_at: str
    view_count: int
    comment_count: int

    def as_row(self, timestamp: str) -> dict[str, Any]:
        return {
            "video_id": self.video_id, "language": self.language,
            "matched_queries": " | ".join(sorted(self.matched_queries)), "title": self.title,
            "description": self.description, "channel_id": self.channel_id,
            "channel_title": self.channel_title, "published_at": self.published_at,
            "view_count": self.view_count, "comment_count": self.comment_count,
            "url": f"https://www.youtube.com/watch?v={self.video_id}", "selection_timestamp": timestamp,
        }


def _read_error_payload(error: HTTPError) -> dict[str, Any]:
    try:
        return json.loads(error.read().decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}


def _api_reason(payload: dict[str, Any]) -> str:
    errors = payload.get("error", {}).get("errors", [])
    return str(errors[0].get("reason", "")) if errors else ""


def _api_message(payload: dict[str, Any]) -> str:
    return str(payload.get("error", {}).get("message", ""))


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sanitize(value: Any) -> Any:
    """Remove display/profile identity fields recursively before persistence."""
    sensitive = {"authorDisplayName", "authorProfileImageUrl", "authorChannelId", "authorChannelUrl"}
    if isinstance(value, dict):
        return {key: sanitize(item) for key, item in value.items() if key not in sensitive}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(sanitize(data), ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def append_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    # utf-8-sig is useful for Excel on first creation, but appending with it
    # would insert an additional BOM before every later batch/page.
    with path.open("a", newline="", encoding="utf-8" if exists else "utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def log_event(path: Path, stage: str, status: str, detail: str = "", video_id: str = "") -> None:
    append_csv(path, LOG_FIELDS, [{"timestamp": utc_now(), "stage": stage, "video_id": video_id, "status": status, "detail": detail}])


def render_progress(video_number: int, total_videos: int, video_id: str, scanned: int, maximum: int, saved: int) -> None:
    """Render a single-line progress bar without a third-party dependency."""
    width = 24
    ratio = min(scanned / maximum, 1) if maximum else 1
    filled = round(width * ratio)
    bar = "#" * filled + "-" * (width - filled)
    message = (
        f"\r视频 {video_number}/{total_videos} [{bar}] {scanned}/{maximum} "
        f"已扫描，{saved} 条新评论  ({video_id})"
    )
    print(message, end="", flush=True)


def matches_eligibility(title: str, description: str, language: str, topic: Topic | None = None) -> bool:
    """Keep review-like videos and, when configured, require the film title."""
    topic = topic or TOPICS["fengshen"]
    corpus = f"{title} {description}".lower()
    if any(term.lower() in corpus for term in EXCLUSION_TERMS):
        return False
    if topic.slug == "nezha2" and any(term in corpus for term in NEZHA2_EXCLUSION_TERMS):
        return False
    if topic.subject_terms and not any(term.lower() in corpus for term in topic.subject_terms):
        return False
    return any(term.lower() in corpus for term in topic.inclusion_terms[language])


def chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def discover_candidates(
    client: Any, run_timestamp: str, raw_dir: Path, log_path: Path, topic: Topic, max_comments: int,
) -> list[Candidate]:
    """Search all fixed queries and enrich their unique video IDs with statistics."""
    provenance: dict[tuple[str, str], set[str]] = defaultdict(set)
    for language, queries in topic.language_queries.items():
        for index, query in enumerate(queries, start=1):
            try:
                response = client.get(
                    "search", part="snippet", q=query, type="video", maxResults=50,
                    order="relevance", relevanceLanguage="zh-Hans" if language == "zh" else "en",
                    publishedAfter=topic.published_after,
                )
                write_json(raw_dir / "discovery" / f"{language}_{index}_search.json", response)
                for item in response.get("items", []):
                    video_id = item.get("id", {}).get("videoId")
                    if video_id:
                        provenance[(language, video_id)].add(query)
                log_event(log_path, "search", "ok", query)
            except ApiRequestError as exc:
                log_event(log_path, "search", "error", f"{query}: {exc}")

    candidates: list[Candidate] = []
    by_language: dict[str, list[str]] = defaultdict(list)
    for language, video_id in provenance:
        by_language[language].append(video_id)
    for language, video_ids in by_language.items():
        for batch_index, batch in enumerate(chunks(video_ids, 50), start=1):
            try:
                response = client.get("videos", part="snippet,statistics", id=",".join(batch), maxResults=50)
                write_json(raw_dir / "discovery" / f"{language}_{batch_index}_videos.json", response)
                for item in response.get("items", []):
                    snippet, statistics = item.get("snippet", {}), item.get("statistics", {})
                    title, description = snippet.get("title", ""), snippet.get("description", "")
                    if matches_eligibility(title, description, language, topic):
                        video_id = str(item["id"])
                        candidates.append(Candidate(
                            video_id=video_id, language=language,
                            matched_queries=provenance[(language, video_id)], title=title, description=description,
                            channel_id=str(snippet.get("channelId", "")), channel_title=str(snippet.get("channelTitle", "")),
                            published_at=str(snippet.get("publishedAt", "")), view_count=int(statistics.get("viewCount", 0)),
                            comment_count=int(statistics.get("commentCount", 0)),
                        ))
                log_event(log_path, "videos", "ok", f"{language} batch {batch_index}")
            except ApiRequestError as exc:
                log_event(log_path, "videos", "error", f"{language} batch {batch_index}: {exc}")
    write_json(raw_dir / "run_manifest.json", {
        "topic": topic.slug, "title": topic.title, "run_timestamp": run_timestamp,
        "published_after": topic.published_after, "queries": topic.language_queries,
        "title_aliases": list(topic.subject_terms),
        "selection": f"highest view count; {topic.per_language} videos per language by default",
        "comment_policy": f"top-level published comments only; newest {max_comments} maximum per video",
    })
    return candidates


def select_candidates(candidates: Iterable[Candidate], per_language: int = 10) -> list[Candidate]:
    grouped: dict[str, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate.language].append(candidate)
    selected: list[Candidate] = []
    selected_ids: set[str] = set()
    for language in ("zh", "en"):
        for candidate in sorted(grouped[language], key=lambda item: (-item.view_count, item.video_id)):
            if candidate.video_id in selected_ids:
                continue
            selected.append(candidate)
            selected_ids.add(candidate.video_id)
            if sum(item.language == language for item in selected) == per_language:
                break
    return selected


def normalize_thread(thread: dict[str, Any], video_id: str, timestamp: str) -> dict[str, Any] | None:
    top_level = thread.get("snippet", {}).get("topLevelComment", {})
    snippet = top_level.get("snippet", {})
    comment_id = top_level.get("id")
    if not comment_id or not snippet.get("textOriginal"):
        return None
    return {
        "comment_id": str(comment_id), "video_id": video_id,
        "published_at": str(snippet.get("publishedAt", "")), "updated_at": str(snippet.get("updatedAt", "")),
        "like_count": int(snippet.get("likeCount", 0)), "text": str(snippet["textOriginal"]),
        "collection_timestamp": timestamp,
    }


def without_replies(response: dict[str, Any]) -> dict[str, Any]:
    """Ensure raw comment snapshots do not retain reply payloads."""
    cleaned = dict(response)
    cleaned["items"] = [{key: value for key, value in item.items() if key != "replies"} for item in response.get("items", [])]
    return cleaned


def collect_top_level_comments(
    client: Any, video_id: str, max_comments: int, raw_dir: Path, timestamp: str,
    existing_ids: set[str], on_page: Callable[[list[dict[str, Any]]], None],
    on_progress: Callable[[int, int, int], None] | None = None,
) -> int:
    """Collect newest top-level comments; replies are intentionally ignored."""
    page_token: str | None = None
    collected = 0
    examined = 0
    page_number = 0
    while examined < max_comments:
        response = client.get(
            "commentThreads", part="snippet", videoId=video_id, maxResults=min(100, max_comments - examined),
            order="time", textFormat="plainText", pageToken=page_token,
        )
        page_number += 1
        write_json(raw_dir / "comments" / video_id / f"page_{page_number:04}.json", without_replies(response))
        rows: list[dict[str, Any]] = []
        for thread in response.get("items", []):
            if examined >= max_comments:
                break
            examined += 1
            row = normalize_thread(thread, video_id, timestamp)
            if row and row["comment_id"] not in existing_ids:
                existing_ids.add(row["comment_id"])
                rows.append(row)
        if rows:
            on_page(rows)
            collected += len(rows)
        if on_progress:
            on_progress(examined, max_comments, collected)
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return collected


def output_default(topic: Topic) -> Path:
    date = datetime.now().strftime("%Y%m%d")
    return Path.cwd() / f"{topic.slug}_youtube_{date}"


def default_key_file() -> Path:
    return Path(__file__).resolve().with_name("youtube_api_key.txt")


def load_api_key(key_file: Path) -> str:
    """Read a local key file first, falling back to an environment variable."""
    if key_file.exists():
        key = key_file.read_text(encoding="utf-8").strip()
        if key:
            return key
    return os.getenv("YOUTUBE_API_KEY", "").strip()


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(description="Collect public, top-level YouTube comments about a selected film.")
    argument_parser.add_argument("--topic", choices=sorted(TOPICS), default="nezha2")
    argument_parser.add_argument("--output-dir", type=Path, help="Destination directory (default is topic-specific).")
    argument_parser.add_argument(
        "--per-language", type=int, choices=range(1, 51), metavar="1..50",
        help="Videos to select from each language pool (default depends on --topic).",
    )
    argument_parser.add_argument(
        "--api-key-file", type=Path, default=default_key_file(),
        help="Local text file containing the API key (default: youtube_api_key.txt beside this script).",
    )
    argument_parser.add_argument("--resume", action="store_true", help="Reuse selected videos and avoid completed videos.")
    argument_parser.add_argument("--dry-run", action="store_true", help="Discover and export candidates only; do not request comments.")
    argument_parser.add_argument("--max-comments", type=int, default=1000, choices=range(1, 1001), metavar="1..1000")
    return argument_parser


def selected_from_rows(rows: Iterable[dict[str, str]]) -> list[Candidate]:
    result = []
    for row in rows:
        result.append(Candidate(
            video_id=row["video_id"], language=row["language"], matched_queries=set(row.get("matched_queries", "").split(" | ")) - {""},
            title=row.get("title", ""), description=row.get("description", ""), channel_id=row.get("channel_id", ""),
            channel_title=row.get("channel_title", ""), published_at=row.get("published_at", ""),
            view_count=int(row.get("view_count", 0) or 0), comment_count=int(row.get("comment_count", 0) or 0),
        ))
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    topic = TOPICS[args.topic]
    per_language = args.per_language or topic.per_language
    api_key = load_api_key(args.api_key_file)
    if not api_key:
        print(
            f"Missing API key. Put it in {args.api_key_file} or set YOUTUBE_API_KEY; never add it to pachong.py.",
            file=sys.stderr,
        )
        return 2

    output_dir: Path = args.output_dir or output_default(topic)
    raw_dir, log_path = output_dir / "raw", output_dir / "collection_log.csv"
    output_dir.mkdir(parents=True, exist_ok=True)
    client, timestamp = YouTubeClient(api_key), utc_now()
    videos_path, comments_path = output_dir / "videos.csv", output_dir / "comments.csv"

    if args.resume and videos_path.exists():
        selected = selected_from_rows(read_csv(videos_path))
        log_event(log_path, "resume", "ok", f"Loaded {len(selected)} selected videos")
    else:
        candidates = discover_candidates(client, timestamp, raw_dir, log_path, topic, args.max_comments)
        append_csv(output_dir / "candidates.csv", VIDEO_FIELDS, [item.as_row(timestamp) for item in candidates])
        selected = select_candidates(candidates, per_language)
        write_json(raw_dir / "selection.json", [item.as_row(timestamp) for item in selected])
        append_csv(videos_path, VIDEO_FIELDS, [item.as_row(timestamp) for item in selected])
        for language in ("zh", "en"):
            amount = sum(item.language == language for item in selected)
            log_event(log_path, "selection", "ok" if amount == per_language else "shortfall", f"{language}: {amount}/{per_language}")

    if args.dry_run:
        print(f"Candidate discovery complete: {len(selected)} selected videos. Output: {output_dir}")
        return 0

    existing_ids = {row.get("comment_id", "") for row in read_csv(comments_path)}
    completed = {row.get("video_id", "") for row in read_csv(log_path) if row.get("stage") == "comments" and row.get("status") == "complete"}
    for video_number, video in enumerate(selected, start=1):
        if args.resume and video.video_id in completed:
            render_progress(video_number, len(selected), video.video_id, args.max_comments, args.max_comments, 0)
            print(" 已跳过")
            log_event(log_path, "comments", "skipped", "already complete", video.video_id)
            continue
        try:
            count = collect_top_level_comments(
                client, video.video_id, args.max_comments, raw_dir, timestamp, existing_ids,
                lambda rows: append_csv(comments_path, COMMENT_FIELDS, rows),
                lambda scanned, maximum, saved: render_progress(
                    video_number, len(selected), video.video_id, scanned, maximum, saved
                ),
            )
            print()
            log_event(log_path, "comments", "complete", f"{count} new top-level comments", video.video_id)
        except ApiRequestError as exc:
            print()
            status = "comments_disabled" if exc.reason == "commentsDisabled" else "error"
            log_event(log_path, "comments", status, str(exc), video.video_id)
    print(f"Collection finished. Output: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
