from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote, unquote, urlparse


SITE = Path(__file__).resolve().parents[1]
BASE_URL = "https://xn--3e0bl59bm0ad17a.com"
CURRENT_DATE = "2026-08-05"
SKIP = {".git", ".vercel", "tmp", "node_modules"}


def html_paths() -> list[str]:
    paths: list[str] = []
    for root, directories, files in os.walk(SITE):
        directories[:] = [name for name in directories if name not in SKIP]
        if "index.html" not in files:
            continue
        relative = (Path(root) / "index.html").relative_to(SITE)
        parent = relative.parent.as_posix()
        paths.append("/" if parent == "." else f"/{parent}/")
    return sorted(set(paths), key=lambda value: (value.count("/"), value))


def previous_dates() -> dict[str, str]:
    sitemap = SITE / "sitemap.xml"
    if not sitemap.exists():
        return {}
    root = ET.parse(sitemap).getroot()
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    result: dict[str, str] = {}
    for node in root.findall("sm:url", namespace):
        loc = node.findtext("sm:loc", default="", namespaces=namespace).strip()
        lastmod = node.findtext("sm:lastmod", default="", namespaces=namespace).strip()
        if loc and lastmod:
            result[unquote(urlparse(loc).path)] = lastmod
    return result


def main() -> None:
    paths = html_paths()
    old_dates = previous_dates()
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path in paths:
        lastmod = CURRENT_DATE if path == "/과목별학원/" or path not in old_dates else old_dates[path]
        lines.extend([
            "  <url>",
            f"    <loc>{BASE_URL}{quote(path, safe='/')}</loc>",
            f"    <lastmod>{lastmod}</lastmod>",
            "  </url>",
        ])
    lines.append("</urlset>")
    (SITE / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"sitemap_urls={len(paths)} unique={len(set(paths))}")


if __name__ == "__main__":
    main()
