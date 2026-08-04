#!/usr/bin/env python3
"""과목별학원 링크를 기존 헤더/푸터에 안전하게 추가합니다.

기본 실행은 미리보기이며 실제 파일을 바꾸려면 ``--apply``를 사용합니다.
같은 파일에 여러 번 실행해도 과목별학원 링크는 영역별 한 개만 유지됩니다.
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path


SITE = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".git", ".vercel", "tmp", "node_modules"}
SUBJECT_LINK = '<a href="/과목별학원/">과목별학원</a>'

BLOCK_PATTERNS = {
    "nav": re.compile(
        r'<div\b[^>]*class=["\'][^"\']*\bnav-links\b[^"\']*["\'][^>]*>.*?</div>',
        re.IGNORECASE | re.DOTALL,
    ),
    "footer": re.compile(
        r'<div\b[^>]*class=["\'][^"\']*\bfooter-links\b[^"\']*["\'][^>]*>.*?</div>',
        re.IGNORECASE | re.DOTALL,
    ),
}

SUBJECT_ANCHOR = re.compile(
    r'<a\b[^>]*href=["\'][^"\']*과목별학원/[^"\']*["\'][^>]*>\s*과목별학원\s*</a>',
    re.IGNORECASE,
)

ANCHOR_TARGETS = (
    re.compile(
        r'<a\b[^>]*href=["\'][^"\']*전국학원/[^"\']*["\'][^>]*>\s*전국학원\s*</a>',
        re.IGNORECASE,
    ),
    re.compile(
        r'<a\b[^>]*href=["\'][^"\']*상담문의/[^"\']*["\'][^>]*>\s*상담문의\s*</a>',
        re.IGNORECASE,
    ),
)


def html_files() -> list[Path]:
    files: list[Path] = []
    for root, directories, names in os.walk(SITE):
        directories[:] = [name for name in directories if name not in SKIP_PARTS]
        if "index.html" in names:
            files.append(Path(root) / "index.html")
    return sorted(files)


def insertion_text(block: str, position: int) -> str:
    """대상 링크가 줄 단위면 같은 들여쓰기를, 인라인이면 인라인을 유지합니다."""
    line_start = block.rfind("\n", 0, position)
    if line_start >= 0:
        leading = block[line_start + 1 : position]
        if not leading.strip():
            return SUBJECT_LINK + "\n" + leading
    return SUBJECT_LINK


def normalize_block(block: str) -> tuple[str, bool]:
    matches = list(SUBJECT_ANCHOR.finditer(block))
    changed = False

    # 이미 중복돼 있다면 첫 링크만 남겨 idempotent하게 정리합니다.
    if len(matches) > 1:
        for match in reversed(matches[1:]):
            block = block[: match.start()] + block[match.end() :]
        matches = list(SUBJECT_ANCHOR.finditer(block))
        changed = True

    if matches:
        return block, changed

    for target_pattern in ANCHOR_TARGETS:
        target = target_pattern.search(block)
        if target:
            insert = insertion_text(block, target.start())
            return block[: target.start()] + insert + block[target.start() :], True

    # 매우 오래된 템플릿이라 기준 링크가 없으면 닫는 div 직전에 추가합니다.
    close_at = block.lower().rfind("</div>")
    if close_at >= 0:
        separator = "\n        " if "\n" in block else ""
        return block[:close_at] + separator + SUBJECT_LINK + block[close_at:], True
    return block, changed


def update_html(source: str) -> tuple[str, dict[str, int]]:
    stats = {"nav_blocks": 0, "footer_blocks": 0, "changed_blocks": 0}
    updated = source

    for kind, pattern in BLOCK_PATTERNS.items():
        def replace(match: re.Match[str]) -> str:
            stats[f"{kind}_blocks"] += 1
            block, changed = normalize_block(match.group(0))
            if changed:
                stats["changed_blocks"] += 1
            return block

        updated = pattern.sub(replace, updated)

    return updated, stats


def validate_scoped_links(source: str, path: Path) -> list[str]:
    errors: list[str] = []
    for kind, pattern in BLOCK_PATTERNS.items():
        for index, match in enumerate(pattern.finditer(source), 1):
            count = len(SUBJECT_ANCHOR.findall(match.group(0)))
            if count != 1:
                errors.append(f"{path}: {kind} 영역 {index}의 과목별학원 링크가 {count}개입니다")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="미리보기가 아니라 파일을 실제로 수정")
    args = parser.parse_args()

    files = html_files()
    changed_files = 0
    nav_blocks = 0
    footer_blocks = 0
    errors: list[str] = []

    for path in files:
        source = path.read_text(encoding="utf-8")
        updated, stats = update_html(source)
        nav_blocks += stats["nav_blocks"]
        footer_blocks += stats["footer_blocks"]
        if updated != source:
            changed_files += 1
            if args.apply:
                path.write_text(updated, encoding="utf-8", newline="")
        errors.extend(validate_scoped_links(updated, path))

    mode = "적용" if args.apply else "미리보기"
    print(
        f"[{mode}] HTML {len(files):,}개 / 변경 대상 {changed_files:,}개 / "
        f"헤더 {nav_blocks:,}개 / 푸터 {footer_blocks:,}개"
    )
    if errors:
        print("검증 오류:")
        for error in errors[:30]:
            print(f"- {error}")
        if len(errors) > 30:
            print(f"- 외 {len(errors) - 30:,}건")
        return 1
    print("검증 완료: 발견된 각 헤더/푸터 영역에 과목별학원 링크가 정확히 1개입니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
