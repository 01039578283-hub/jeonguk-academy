from __future__ import annotations

import json
import re
from pathlib import Path

from content_banks import (
    FAQ_SLOT2_BANK,
    FAQ_SLOT3_BANK,
    FAQ_SLOT4_BANK,
    REVIEW_BANK_4,
    REVIEW_BANK_5,
    pick,
    pick_unique,
)

ROOT = Path(__file__).resolve().parents[1]
CENTER_ROOT = ROOT / "전국학원"

REVIEW_CARD_RE = re.compile(
    r'<article class="parent-review-card">\s*'
    r'<div class="parent-review-stars" aria-label="(\d)점 후기">[^<]*</div>\s*'
    r'<p>(.*?)</p>\s*'
    r'<strong>학부모 후기</strong>\s*'
    r'</article>',
    re.S,
)
FAQ_ITEM_RE = re.compile(
    r'<details class="parent-faq-item"( open)?>\s*'
    r'<summary><span class="parent-faq-q">Q</span>(.*?)</summary>\s*'
    r'<p class="parent-faq-answer">(.*?)</p>\s*'
    r'</details>',
    re.S,
)


def target_dirs() -> list[Path]:
    result = []
    for f in CENTER_ROOT.rglob("index.html"):
        depth = len(f.parent.relative_to(CENTER_ROOT).parts)
        if depth >= 3:
            result.append(f.parent)
    return sorted(result)


def type_names(node) -> list[str]:
    t = node.get("@type")
    return t if isinstance(t, list) else [t]


def find_node(graph: list[dict], type_name: str) -> dict | None:
    for node in graph:
        if isinstance(node, dict) and type_name in type_names(node):
            return node
    return None


def remove_orphan_faq_block(source: str) -> str:
    """Remove the standalone FAQPage <script> block that has no @graph wrapper
    (the one with no visible-page backing)."""
    def is_orphan(match: re.Match) -> bool:
        try:
            data = json.loads(match.group(1))
        except Exception:
            return False
        return isinstance(data, dict) and data.get("@type") == "FAQPage" and "@graph" not in data

    pattern = re.compile(r'\s*<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
    matches = list(pattern.finditer(source))
    for m in reversed(matches):
        if is_orphan(m):
            source = source[: m.start()] + source[m.end():]
    return source


def process_page(page_dir: Path, seen_reviews: set, seen_faqs: set) -> bool:
    path = page_dir / "index.html"
    source = path.read_text(encoding="utf-8", errors="ignore")
    page_url = path.as_posix()
    updated = source

    # 1) grammar fix: "학원를" -> "학원을" (학원 always ends in a batchim syllable)
    updated = updated.replace("학원를", "학원을")

    # 2) remove orphaned FAQPage block with no visible backing
    updated = remove_orphan_faq_block(updated)

    # 3) reviews: keep slots 0-1 (dong-specific openers), regenerate slots 2-5
    review_matches = REVIEW_CARD_RE.findall(updated)
    if len(review_matches) != 6:
        raise RuntimeError(f"expected 6 reviews, found {len(review_matches)} in {path}")
    opener_reviews = [(r, b) for r, b in review_matches[:2]]
    # Uniqueness key is the combined (3 five-star + 1 four-star) tuple, not just
    # the five-star draw alone: C(28,3)=3,276 unique 3-item combos is fewer than
    # our 3,339 pages, so drawing uniqueness from the 3-item pool alone runs out
    # and pick_unique retries forever. Folding the four-star pick (6 options) in
    # gives up to 3,276 * 6 = 19,656 distinct combos, comfortably more than needed.
    seen = seen_reviews.setdefault("combo", set())
    attempt = 0
    while True:
        salt = f"retry{attempt}" if attempt else ""
        five_star = pick(REVIEW_BANK_5, 3, page_url, "review5", salt)
        four_star = pick(REVIEW_BANK_4, 1, page_url, "review4", salt)[0]
        combo = frozenset(five_star + [four_star])
        if combo not in seen:
            seen.add(combo)
            break
        attempt += 1
    new_reviews = opener_reviews + [("5", b) for b in five_star] + [("4", four_star)]

    def review_repl(_match, _iter=iter(new_reviews)):
        rating, body = next(_iter)
        stars = "★" * int(rating) + "☆" * (5 - int(rating))
        return (
            f'<article class="parent-review-card">\n'
            f'      <div class="parent-review-stars" aria-label="{rating}점 후기">{stars}</div>\n'
            f'      <p>{body}</p>\n'
            f'      <strong>학부모 후기</strong>\n'
            f'    </article>'
        )

    updated = REVIEW_CARD_RE.sub(review_repl, updated)

    # 4) FAQ: keep slots 0-1, regenerate slots 2-4
    faq_matches = FAQ_ITEM_RE.findall(updated)
    if len(faq_matches) != 5:
        raise RuntimeError(f"expected 5 FAQ items, found {len(faq_matches)} in {path}")
    opener_faqs = [(q, a) for _open, q, a in faq_matches[:2]]
    slot2 = pick(FAQ_SLOT2_BANK, 1, page_url, "faq2")[0]
    slot3 = pick(FAQ_SLOT3_BANK, 1, page_url, "faq3")[0]
    slot4 = pick(FAQ_SLOT4_BANK, 1, page_url, "faq4")[0]
    new_faqs = opener_faqs + [slot2, slot3, slot4]

    def faq_repl(_match, _iter=iter(new_faqs)):
        q, a = next(_iter)
        open_attr = " open" if _match.group(1) else ""
        return (
            f'<details class="parent-faq-item"{open_attr}>\n'
            f'      <summary><span class="parent-faq-q">Q</span>{q}</summary>\n'
            f'      <p class="parent-faq-answer">{a}</p>\n'
            f'    </details>'
        )

    updated = FAQ_ITEM_RE.sub(faq_repl, updated)

    # 5) sync JSON-LD (primary @graph block only - orphan already removed)
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', updated, re.S)
    data = json.loads(m.group(1))
    graph = data["@graph"]

    org = find_node(graph, "EducationalOrganization")
    org["review"] = [
        {
            "@type": "Review",
            "author": {"@type": "Person", "name": "학부모"},
            "reviewBody": body,
            "reviewRating": {"@type": "Rating", "ratingValue": rating, "bestRating": "5"},
        }
        for rating, body in new_reviews
    ]

    faq_node = find_node(graph, "FAQPage")
    faq_node["mainEntity"] = [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
        for q, a in new_faqs
    ]

    new_jsonld = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    updated = updated[: m.start()] + '<script type="application/ld+json">' + new_jsonld + "</script>" + updated[m.end():]

    if updated != source:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def main() -> None:
    targets = target_dirs()
    seen_reviews: dict[str, set] = {}
    seen_faqs: set = set()
    changed = 0
    errors = 0
    for page_dir in targets:
        try:
            if process_page(page_dir, seen_reviews, seen_faqs):
                changed += 1
        except Exception as exc:  # noqa: BLE001
            errors += 1
            print(f"ERROR {page_dir}: {exc}")
    print(json.dumps({"targets": len(targets), "changed": changed, "errors": errors}, ensure_ascii=False))


if __name__ == "__main__":
    main()
