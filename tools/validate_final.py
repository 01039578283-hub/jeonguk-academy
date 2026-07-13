from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CENTER_ROOT = ROOT / "전국학원"


def target_dirs() -> list[Path]:
    result = []
    for f in CENTER_ROOT.rglob("index.html"):
        depth = len(f.parent.relative_to(CENTER_ROOT).parts)
        if depth >= 3:
            result.append(f)
    return sorted(result)


def main() -> None:
    files = target_dirs()
    print(f"total={len(files)}")

    grammar_bug = 0
    orphan_faq = 0
    parse_err = 0
    faq_mismatch = 0
    review_mismatch = 0
    h1_bad = 0
    multi_script = 0

    for f in files:
        text = f.read_text(encoding="utf-8", errors="ignore")

        visible_only = re.sub(r'<script type="application/ld\+json"[^>]*>.*?</script>', "", text, flags=re.S)
        if "학원를" in visible_only:
            grammar_bug += 1

        h1 = re.findall(r"<h1\b[^>]*>.*?</h1>", text, re.S)
        if len(h1) != 1:
            h1_bad += 1

        blocks = re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', text, re.S)
        if len(blocks) != 1:
            multi_script += 1

        try:
            data = json.loads(blocks[0])
        except Exception as exc:  # noqa: BLE001
            parse_err += 1
            print("PARSE ERR", f, exc)
            continue

        graph = data.get("@graph", [])

        def find(t):
            for n in graph:
                typ = n.get("@type")
                types = typ if isinstance(typ, list) else [typ]
                if t in types:
                    return n
            return None

        org = find("EducationalOrganization")
        faq = find("FAQPage")

        jsonld_reviews = [r["reviewBody"] for r in org["review"]]
        visible_reviews = re.findall(
            r'class="parent-review-card">\s*<div[^>]*>[^<]*</div>\s*<p>(.*?)</p>', text, re.S
        )
        if jsonld_reviews != visible_reviews:
            review_mismatch += 1

        jsonld_q = [q["name"] for q in faq["mainEntity"]]
        visible_q = re.findall(r'<summary><span[^>]*>Q</span>([^<]*)</summary>', text)
        if jsonld_q != visible_q:
            faq_mismatch += 1

    print(f"parse_err={parse_err}")
    print(f"multi_script_blocks_remaining={multi_script}")
    print(f"grammar_bug_remaining={grammar_bug}")
    print(f"h1_bad={h1_bad}")
    print(f"faq_mismatch={faq_mismatch}")
    print(f"review_mismatch={review_mismatch}")


if __name__ == "__main__":
    main()
