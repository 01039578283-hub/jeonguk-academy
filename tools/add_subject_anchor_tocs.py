#!/usr/bin/env python3
"""Add accessible, page-specific TOCs to subject academy detail pages.

Only ``과목별학원/<category>/<local>/index.html`` pages are targeted. The
top-level and category directory pages keep their existing search/navigation
UI. TOC links are built from the H2 headings already present in each
``subject-copy-card`` so the script can be safely rerun after page generation.
"""

from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUBJECT_ROOT = ROOT / "과목별학원"
TOC_START = "<!-- subject-page-anchor-toc:start -->"
TOC_END = "<!-- subject-page-anchor-toc:end -->"

TOC_BLOCK_RE = re.compile(
    rf"{re.escape(TOC_START)}.*?{re.escape(TOC_END)}",
    re.IGNORECASE | re.DOTALL,
)
TOC_REMOVE_RE = re.compile(
    rf"^[ \t]*{re.escape(TOC_START)}[ \t]*\n.*?"
    rf"^[ \t]*{re.escape(TOC_END)}[ \t]*(?:\n)?",
    re.IGNORECASE | re.DOTALL | re.MULTILINE,
)
ARTICLE_RE = re.compile(
    r"<article(?P<attrs>[^>]*)>(?P<body>.*?)</article>",
    re.IGNORECASE | re.DOTALL,
)
H2_RE = re.compile(r"<h2\b[^>]*>(?P<body>.*?)</h2>", re.IGNORECASE | re.DOTALL)
CLASS_RE = re.compile(
    r"\bclass\s*=\s*([\"'])(?P<class_names>[^\"']+)\1", re.IGNORECASE
)
ID_RE = re.compile(r"\bid\s*=\s*([\"'])(?P<id>[^\"']+)\1", re.IGNORECASE)
ANY_ID_RE = re.compile(r"\bid\s*=\s*([\"'])(?P<id>[^\"']+)\1", re.IGNORECASE)
HERO_OPEN_RE = re.compile(
    r"<section\b[^>]*class\s*=\s*([\"'])[^\"']*\bsubject-local-hero\b[^\"']*\1[^>]*>",
    re.IGNORECASE,
)
SECTION_TAG_RE = re.compile(r"</?section\b[^>]*>", re.IGNORECASE)
UNCONFIRMED_RE = re.compile(
    r"class\s*=\s*([\"'])[^\"']*\bsubject-availability\b[^\"']*\bis-check\b[^\"']*\1",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TocTarget:
    start: int
    end: int
    attrs: str
    text: str


def visible_text(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    return " ".join(html.unescape(text).split())


def has_class(attrs: str, class_name: str) -> bool:
    match = CLASS_RE.search(attrs)
    return bool(match and class_name in match.group("class_names").split())


def detail_pages() -> list[Path]:
    if not SUBJECT_ROOT.exists():
        return []
    return sorted(
        SUBJECT_ROOT.glob("*/*/index.html"), key=lambda path: path.as_posix()
    )


def index_newlines() -> dict[str, str]:
    """Return the line ending stored in Git for every tracked detail page."""
    result = subprocess.run(
        [
            "git",
            "-c",
            "core.quotepath=false",
            "ls-files",
            "--eol",
            "--",
            ":(glob)과목별학원/*/*/index.html",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    newlines: dict[str, str] = {}
    for line in result.stdout.splitlines():
        match = re.match(r"^i/(?P<index_eol>\S+).*?\t(?P<path>.+)$", line)
        if not match:
            continue
        index_eol = match.group("index_eol")
        if index_eol == "crlf":
            newlines[match.group("path")] = "\r\n"
        elif index_eol == "lf":
            newlines[match.group("path")] = "\n"
    return newlines


def select_targets(source: str) -> list[TocTarget]:
    selected: list[TocTarget] = []
    for article in ARTICLE_RE.finditer(source):
        attrs = article.group("attrs")
        if not has_class(attrs, "subject-copy-card"):
            continue
        heading = H2_RE.search(article.group("body"))
        if not heading:
            continue
        text = visible_text(heading.group("body"))
        if not text:
            continue
        selected.append(
            TocTarget(
                start=article.start(),
                end=article.start("body"),
                attrs=attrs,
                text=text,
            )
        )
    return selected


def existing_target_id(target: TocTarget) -> str | None:
    match = ID_RE.search(target.attrs)
    return match.group("id") if match else None


def add_target_ids(
    source: str, targets: list[TocTarget]
) -> tuple[str, list[tuple[str, str]]]:
    used_ids = {match.group("id") for match in ANY_ID_RE.finditer(source)}
    replacements: list[tuple[int, int, str]] = []
    links: list[tuple[str, str]] = []

    for number, target in enumerate(targets, start=1):
        target_id = existing_target_id(target)
        if not target_id:
            base_id = f"section-{number:02d}"
            target_id = base_id
            suffix = 2
            while target_id in used_ids:
                target_id = f"{base_id}-{suffix}"
                suffix += 1
            used_ids.add(target_id)
            replacements.append(
                (target.start, target.end, f'<article id="{target_id}"{target.attrs}>')
            )
        links.append((target_id, target.text))

    for start, end, replacement in reversed(replacements):
        source = source[:start] + replacement + source[end:]
    return source, links


def section_end(source: str, opening: re.Match[str] | None) -> int | None:
    if not opening:
        return None

    depth = 0
    for match in SECTION_TAG_RE.finditer(source, opening.start()):
        if match.group(0).lower().startswith("</section"):
            depth -= 1
            if depth == 0:
                return match.end()
        else:
            depth += 1
    return None


def classed_section_end(source: str, class_name: str) -> int | None:
    opening = re.search(
        rf"<section\b[^>]*class\s*=\s*([\"'])[^\"']*\b{re.escape(class_name)}\b[^\"']*\1[^>]*>",
        source,
        re.IGNORECASE,
    )
    return section_end(source, opening)


def toc_markup(links: list[tuple[str, str]]) -> str:
    items = []
    for index, (target_id, text) in enumerate(links, start=1):
        items.append(
            "          <li>"
            f'<a href="#{html.escape(target_id, quote=True)}">'
            f'<span class="subject-page-toc-number" aria-hidden="true">{index:02d}</span>'
            f'<span>{html.escape(text)}</span>'
            "</a></li>"
        )
    return (
        "\n\n    "
        + TOC_START
        + "\n"
        + '    <nav class="section subject-page-toc" aria-labelledby="subject-page-toc-title">\n'
        + '      <div class="subject-page-toc-shell">\n'
        + '        <div class="subject-page-toc-heading">\n'
        + '          <p class="eyebrow">PAGE CONTENTS</p>\n'
        + '          <strong id="subject-page-toc-title">이 페이지에서 확인할 내용</strong>\n'
        + "        </div>\n"
        + '        <ol class="subject-page-toc-list">\n'
        + "\n".join(items)
        + "\n        </ol>\n"
        + "      </div>\n"
        + "    </nav>\n"
        + "    "
        + TOC_END
        + "\n\n    "
    )


def render_page(original: str) -> tuple[str, int]:
    source = TOC_REMOVE_RE.sub("", original, count=1)
    targets = select_targets(source)
    if len(targets) < 2:
        raise ValueError(f"Only {len(targets)} usable manuscript headings found")

    source, links = add_target_ids(source, targets)
    hero_insertion_point = section_end(source, HERO_OPEN_RE.search(source))
    if hero_insertion_point is None:
        raise ValueError("subject-local-hero section end not found")

    unconfirmed = bool(UNCONFIRMED_RE.search(source))
    insertion_point = hero_insertion_point
    if unconfirmed:
        media = re.search(
            r"<section\b[^>]*class\s*=\s*([\"'])[^\"']*\bsubject-media-section\b[^\"']*\1[^>]*>",
            source,
            re.IGNORECASE,
        )
        if not media or source[hero_insertion_point : media.start()].strip():
            raise ValueError("unexpected content between hero and media section")
        source = (
            source[:hero_insertion_point]
            + "\n\n    "
            + source[media.start() :]
        )
        insertion_point = classed_section_end(source, "subject-answer-summary")
        if insertion_point is None:
            raise ValueError("unconfirmed page answer summary section end not found")
    tail = source[insertion_point:].lstrip()
    source = source[:insertion_point] + toc_markup(links) + tail
    return source, len(links)


def validate_page(source: str) -> list[str]:
    errors: list[str] = []
    if source.count(TOC_START) != 1 or source.count(TOC_END) != 1:
        errors.append("TOC marker count is not exactly one")

    toc_match = TOC_BLOCK_RE.search(source)
    if not toc_match:
        errors.append("TOC block missing")
        return errors

    hrefs = re.findall(r'href=["\']#([^"\']+)["\']', toc_match.group(0))
    targets = select_targets(source)
    target_ids = [existing_target_id(target) for target in targets]
    if hrefs != target_ids:
        errors.append("TOC link order does not match manuscript cards")

    all_ids = [match.group("id") for match in ANY_ID_RE.finditer(source)]
    if len(all_ids) != len(set(all_ids)):
        errors.append("Duplicate id found")
    for target_id in hrefs:
        if all_ids.count(target_id) != 1:
            errors.append(
                f"Anchor target count for {target_id!r} is {all_ids.count(target_id)}"
            )

    manuscript = source.find('class="section subject-manuscript"')
    if manuscript < 0 or toc_match.start() > manuscript:
        errors.append("TOC is not before the manuscript")
    if UNCONFIRMED_RE.search(source):
        summary_end = classed_section_end(source, "subject-answer-summary")
        if summary_end is None or toc_match.start() < summary_end:
            errors.append("TOC appears before the unconfirmed availability notice")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write", action="store_true", help="Write generated TOCs to disk"
    )
    parser.add_argument(
        "--check", action="store_true", help="Fail if any detail page is not current"
    )
    newline_group = parser.add_mutually_exclusive_group()
    newline_group.add_argument(
        "--crlf", action="store_true", help="Write CRLF line endings"
    )
    newline_group.add_argument(
        "--lf", action="store_true", help="Write LF line endings"
    )
    newline_group.add_argument(
        "--index-eol",
        action="store_true",
        help="Preserve the LF or CRLF line ending stored in Git for each page",
    )
    args = parser.parse_args()

    pages = detail_pages()
    stored_newlines = index_newlines() if args.index_eol else {}
    changed = 0
    link_counts: list[int] = []
    failures: list[str] = []

    for path in pages:
        original = path.read_bytes().decode("utf-8")
        original_newline = "\r\n" if "\r\n" in original else "\n"
        canonical = original.replace("\r\n", "\n").replace("\r", "\n")
        try:
            rendered, link_count = render_page(canonical)
        except Exception as exc:
            failures.append(f"{path.relative_to(ROOT)}: {exc}")
            continue

        link_counts.append(link_count)
        validation_errors = validate_page(rendered)
        if validation_errors:
            failures.append(
                f"{path.relative_to(ROOT)}: " + "; ".join(validation_errors)
            )
            continue

        if args.lf:
            target_newline = "\n"
        elif args.crlf:
            target_newline = "\r\n"
        elif args.index_eol:
            relative_path = path.relative_to(ROOT).as_posix()
            target_newline = stored_newlines.get(relative_path)
            if target_newline is None:
                failures.append(f"{relative_path}: Git index line ending not found")
                continue
        else:
            target_newline = original_newline
        serialized = rendered.replace("\n", target_newline)
        if serialized != original:
            changed += 1
            if args.write:
                path.write_bytes(serialized.encode("utf-8"))

    print(f"pages={len(pages)} details={len(pages)}")
    if link_counts:
        print(
            "toc_links="
            f"min:{min(link_counts)} max:{max(link_counts)} "
            f"avg:{sum(link_counts) / len(link_counts):.2f}"
        )
    print(f"changed={changed} mode={'write' if args.write else 'dry-run'}")

    if failures:
        print(f"failures={len(failures)}", file=sys.stderr)
        for failure in failures[:50]:
            print(failure, file=sys.stderr)
        return 1
    if args.check and changed:
        print("Target pages are not up to date. Run with --write.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
