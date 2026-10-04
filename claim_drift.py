#!/usr/bin/env python3
"""Track explicit transformations between claim versions without inferring motive."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

FORMAT = "claim-drift/0.1"
SOURCE_KINDS = ("primary", "contemporary-report", "later-retelling", "reference", "analysis", "other")
DRIFT_TYPES = (
    "addition", "omission", "intensification", "attenuation",
    "certainty-shift", "causal-shift", "identity-shift", "temporal-shift",
    "location-shift", "quantity-shift", "sequence-shift",
    "semantic-substitution", "other",
)


class DriftError(Exception):
    pass


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def valid_date(value: str) -> bool:
    if re.fullmatch(r"\d{4}", value):
        return True
    try:
        if re.fullmatch(r"\d{4}-\d{2}", value):
            dt.date.fromisoformat(value + "-01")
            return True
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            dt.date.fromisoformat(value)
            return True
    except ValueError:
        return False
    return False


def date_key(value: str) -> tuple[int, int, int] | None:
    if not value:
        return None
    parts = [int(p) for p in value.split("-")]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def new_project(title: str) -> dict[str, Any]:
    title = title.strip()
    if not title:
        raise DriftError("title cannot be empty")
    return {
        "format": FORMAT,
        "title": title,
        "created_at": now_utc(),
        "sources": [],
        "versions": [],
        "transitions": [],
    }


def next_id(items: list[dict[str, Any]], prefix: str) -> str:
    high = 0
    for item in items:
        value = item.get("id", "")
        if value.startswith(prefix) and value[len(prefix):].isdigit():
            high = max(high, int(value[len(prefix):]))
    return f"{prefix}{high + 1:03d}"


def find(items: list[dict[str, Any]], item_id: str, label: str) -> dict[str, Any]:
    for item in items:
        if item["id"] == item_id:
            return item
    raise DriftError(f"{label} not found: {item_id}")


def validate(data: dict[str, Any]) -> None:
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise DriftError("unsupported project format")
    if not isinstance(data.get("title"), str) or not data["title"].strip():
        raise DriftError("project requires a title")
    for key in ("sources", "versions", "transitions"):
        if not isinstance(data.get(key), list):
            raise DriftError(f"project requires a {key} list")

    sids: set[str] = set()
    for source in data["sources"]:
        sid = source.get("id")
        if not isinstance(sid, str) or not sid or sid in sids:
            raise DriftError("invalid or duplicate source id")
        sids.add(sid)
        if source.get("kind") not in SOURCE_KINDS:
            raise DriftError(f"{sid}: invalid source kind")
        if not isinstance(source.get("label"), str) or not source["label"].strip():
            raise DriftError(f"{sid}: source label cannot be empty")
        if source.get("date") and not valid_date(source["date"]):
            raise DriftError(f"{sid}: invalid source date")

    vids: set[str] = set()
    for version in data["versions"]:
        vid = version.get("id")
        if not isinstance(vid, str) or not vid or vid in vids:
            raise DriftError("invalid or duplicate version id")
        vids.add(vid)
        if not isinstance(version.get("text"), str) or not version["text"].strip():
            raise DriftError(f"{vid}: version text cannot be empty")
        for sid in version.get("sources", []):
            if sid not in sids:
                raise DriftError(f"{vid}: unknown source {sid}")

    tids: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    for transition in data["transitions"]:
        tid = transition.get("id")
        if not isinstance(tid, str) or not tid or tid in tids:
            raise DriftError("invalid or duplicate transition id")
        tids.add(tid)
        before = transition.get("from")
        after = transition.get("to")
        if before not in vids or after not in vids or before == after:
            raise DriftError(f"{tid}: invalid version transition")
        pair = (before, after)
        if pair in pairs:
            raise DriftError(f"{tid}: duplicate transition")
        pairs.add(pair)
        observations = transition.get("changes")
        if not isinstance(observations, list) or not observations:
            raise DriftError(f"{tid}: transition requires at least one drift observation")
        for change in observations:
            if change.get("type") not in DRIFT_TYPES:
                raise DriftError(f"{tid}: invalid drift type")
            if not isinstance(change.get("before"), str) or not isinstance(change.get("after"), str):
                raise DriftError(f"{tid}: change requires before and after text")


def load(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise DriftError(f"project not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DriftError(f"invalid JSON: {exc}") from exc
    validate(data)
    return data


def save(path: str | Path, data: dict[str, Any]) -> None:
    validate(data)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def add_source(data: dict[str, Any], label: str, kind: str, date: str | None = None, url: str | None = None, note: str | None = None) -> str:
    if kind not in SOURCE_KINDS:
        raise DriftError("invalid source kind")
    if date and not valid_date(date):
        raise DriftError("date must be YYYY, YYYY-MM, or YYYY-MM-DD")
    if not label.strip():
        raise DriftError("source label cannot be empty")
    sid = next_id(data["sources"], "S")
    data["sources"].append({
        "id": sid, "label": label.strip(), "kind": kind,
        "date": date or "", "url": url or "", "note": note or "",
    })
    return sid


def add_version(data: dict[str, Any], text: str, sources: list[str] | None = None, label: str | None = None, note: str | None = None) -> str:
    if not text.strip():
        raise DriftError("version text cannot be empty")
    source_ids = list(dict.fromkeys(sources or []))
    for sid in source_ids:
        find(data["sources"], sid, "source")
    vid = next_id(data["versions"], "V")
    data["versions"].append({
        "id": vid, "label": label or "", "text": text.strip(),
        "sources": source_ids, "note": note or "",
    })
    return vid


def get_transition(data: dict[str, Any], before: str, after: str) -> dict[str, Any] | None:
    for transition in data["transitions"]:
        if transition["from"] == before and transition["to"] == after:
            return transition
    return None


def add_drift(data: dict[str, Any], before: str, after: str, drift_type: str, old_text: str, new_text: str, note: str | None = None) -> str:
    find(data["versions"], before, "version")
    find(data["versions"], after, "version")
    if before == after:
        raise DriftError("a version cannot drift into itself")
    if drift_type not in DRIFT_TYPES:
        raise DriftError("invalid drift type")

    transition = get_transition(data, before, after)
    if transition is None:
        tid = next_id(data["transitions"], "T")
        transition = {"id": tid, "from": before, "to": after, "changes": []}
        data["transitions"].append(transition)
    else:
        tid = transition["id"]

    transition["changes"].append({
        "type": drift_type,
        "before": old_text,
        "after": new_text,
        "note": note or "",
    })
    return tid


def version_date(data: dict[str, Any], version: dict[str, Any]) -> tuple[int, int, int] | None:
    dates = []
    for sid in version.get("sources", []):
        source = find(data["sources"], sid, "source")
        key = date_key(source.get("date", ""))
        if key is not None:
            dates.append(key)
    return min(dates) if dates else None


def audit(data: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    for version in data["versions"]:
        if not version.get("sources"):
            findings.append(f"{version['id']}: version has no recorded source")

    for transition in data["transitions"]:
        before = find(data["versions"], transition["from"], "version")
        after = find(data["versions"], transition["to"], "version")
        d1 = version_date(data, before)
        d2 = version_date(data, after)
        if d1 is not None and d2 is not None and d1 > d2:
            findings.append(f"{transition['id']}: transition points from a later dated version to an earlier dated version")
        for i, change in enumerate(transition["changes"], start=1):
            if not change.get("note", "").strip():
                findings.append(f"{transition['id']}.{i}: drift observation has no classification note")
    return findings


def render_timeline(data: dict[str, Any]) -> str:
    source_labels = {s["id"]: s for s in data["sources"]}
    lines = ["# Claim Drift timeline", ""]
    for version in data["versions"]:
        refs = []
        for sid in version["sources"]:
            source = source_labels[sid]
            refs.append(f"{sid} · {source['date'] or 'undated'} · {source['label']}")
        lines += [f"## {version['id']}" + (f" · {version['label']}" if version.get("label") else ""), "", version["text"], ""]
        if refs:
            lines += ["**Sources:** " + "; ".join(refs), ""]
        outgoing = [t for t in data["transitions"] if t["from"] == version["id"]]
        for transition in outgoing:
            types = ", ".join(change["type"] for change in transition["changes"])
            lines.append(f"- → {transition['to']} · {types}")
        if outgoing:
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_markdown(data: dict[str, Any]) -> str:
    sources = {s["id"]: s for s in data["sources"]}
    versions = {v["id"]: v for v in data["versions"]}
    lines = [
        f"# {data['title']}", "",
        f"_Claim Drift format: `{FORMAT}`_", "",
        "> Drift labels describe recorded changes. They do not establish motive, error, or fabrication.", "",
        "## Versions", "",
    ]
    if not data["versions"]:
        lines += ["_No versions yet._", ""]
    for version in data["versions"]:
        lines += [f"### {version['id']}" + (f" · {version['label']}" if version.get("label") else ""), "", version["text"], ""]
        if version.get("sources"):
            refs = []
            for sid in version["sources"]:
                source = sources[sid]
                refs.append(f"{sid} · {source['label']}" + (f" · {source['date']}" if source.get("date") else ""))
            lines += ["**Sources:** " + "; ".join(refs), ""]
        if version.get("note"):
            lines += [f"**Note:** {version['note']}", ""]

    lines += ["## Drift transitions", ""]
    if not data["transitions"]:
        lines += ["_No transitions recorded._", ""]
    for transition in data["transitions"]:
        before = versions[transition["from"]]
        after = versions[transition["to"]]
        lines += [
            f"### {transition['id']} · {transition['from']} → {transition['to']}", "",
            f"**From:** {before['text']}", "",
            f"**To:** {after['text']}", "",
        ]
        for change in transition["changes"]:
            lines += [
                f"#### {change['type']}", "",
                f"**Before:** {change['before'] or '∅'}", "",
                f"**After:** {change['after'] or '∅'}", "",
            ]
            if change.get("note"):
                lines += [f"**Classification note:** {change['note']}", ""]

    lines += ["## Structural audit", ""]
    findings = audit(data)
    lines += [f"- {finding}" for finding in findings] if findings else ["_No structural audit flags._"]
    return "\n".join(lines).rstrip() + "\n"


def render_mermaid(data: dict[str, Any]) -> str:
    lines = ["flowchart LR"]
    for version in data["versions"]:
        label = version["text"].replace('"', "'").replace("\n", " ")
        lines.append(f'  {version["id"]}["{version["id"]} · {label}"]')
    for transition in data["transitions"]:
        types = ", ".join(change["type"] for change in transition["changes"])
        lines.append(f'  {transition["from"]} -->|"{transition["id"]} · {types}"| {transition["to"]}')
    return "\n".join(lines) + "\n"


def summary(data: dict[str, Any]) -> str:
    change_count = sum(len(t["changes"]) for t in data["transitions"])
    return (
        f"{data['title']}: {len(data['versions'])} version(s), "
        f"{len(data['transitions'])} transition(s), {change_count} drift observation(s), "
        f"{len(audit(data))} audit flag(s)"
    )


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="claim-drift", description="Track transformations between claim versions.")
    sub = p.add_subparsers(dest="command", required=True)

    q = sub.add_parser("new"); q.add_argument("file"); q.add_argument("--title", required=True)
    q = sub.add_parser("source"); q.add_argument("file"); q.add_argument("label"); q.add_argument("--kind", choices=SOURCE_KINDS, default="other"); q.add_argument("--date"); q.add_argument("--url"); q.add_argument("--note")
    q = sub.add_parser("version"); q.add_argument("file"); q.add_argument("text"); q.add_argument("--source", action="append", default=[]); q.add_argument("--label"); q.add_argument("--note")
    q = sub.add_parser("drift"); q.add_argument("file"); q.add_argument("from_version"); q.add_argument("to_version"); q.add_argument("--type", choices=DRIFT_TYPES, required=True); q.add_argument("--before", default=""); q.add_argument("--after", default=""); q.add_argument("--note")

    for name in ("show", "check", "audit"):
        q = sub.add_parser(name); q.add_argument("file")
    for name in ("render", "timeline", "mermaid"):
        q = sub.add_parser(name); q.add_argument("file"); q.add_argument("-o", "--output")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "new":
            if Path(args.file).exists():
                raise DriftError(f"refusing to overwrite existing file: {args.file}")
            save(args.file, new_project(args.title))
            print(f"created {args.file}")
            return 0

        data = load(args.file)
        if args.command == "source":
            sid = add_source(data, args.label, args.kind, args.date, args.url, args.note); save(args.file, data); print(sid)
        elif args.command == "version":
            vid = add_version(data, args.text, args.source, args.label, args.note); save(args.file, data); print(vid)
        elif args.command == "drift":
            tid = add_drift(data, args.from_version, args.to_version, args.type, args.before, args.after, args.note); save(args.file, data); print(tid)
        elif args.command == "show":
            print(summary(data))
        elif args.command == "check":
            print(f"ok: {args.file}")
        elif args.command == "audit":
            findings = audit(data); print("\n".join(findings) if findings else "no structural audit flags")
        else:
            output = {"render": render_markdown, "timeline": render_timeline, "mermaid": render_mermaid}[args.command](data)
            if args.output:
                Path(args.output).write_text(output, encoding="utf-8"); print(args.output)
            else:
                print(output, end="")
        return 0
    except DriftError as exc:
        print(f"claim-drift: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
