from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import re
import statistics
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse


SITE = Path(__file__).resolve().parents[1]
COMMON = SITE.parent / "참고자료" / "공통자료"
BASE_URL = "https://xn--3e0bl59bm0ad17a.com"
SITE_NAME = "전국학원 영어수학 전문학원 찾기"
SUBJECT_ROOT = "과목별학원"

CATEGORIES: tuple[dict[str, str], ...] = (
    {
        "slug": "중1수학학원",
        "label": "중1 수학학원",
        "grade": "중학교 1학년",
        "grade_token": "중1",
        "subject": "수학",
        "school_field": "타깃학교\n(중)",
        "grade_field": "가능학년\n(수학)",
    },
    {
        "slug": "중1영어학원",
        "label": "중1 영어학원",
        "grade": "중학교 1학년",
        "grade_token": "중1",
        "subject": "영어",
        "school_field": "타깃학교\n(중)",
        "grade_field": "가능학년\n(영어)",
    },
    {
        "slug": "초6수학학원",
        "label": "초6 수학학원",
        "grade": "초등학교 6학년",
        "grade_token": "초6",
        "subject": "수학",
        "school_field": "타깃학교\n(초)",
        "grade_field": "가능학년\n(수학)",
    },
    {
        "slug": "초6영어학원",
        "label": "초6 영어학원",
        "grade": "초등학교 6학년",
        "grade_token": "초6",
        "subject": "영어",
        "school_field": "타깃학교\n(초)",
        "grade_field": "가능학년\n(영어)",
    },
    {
        "slug": "초5수학학원",
        "label": "초5 수학학원",
        "grade": "초등학교 5학년",
        "grade_token": "초5",
        "subject": "수학",
        "school_field": "타깃학교\n(초)",
        "grade_field": "가능학년\n(수학)",
    },
    {
        "slug": "초5영어학원",
        "label": "초5 영어학원",
        "grade": "초등학교 5학년",
        "grade_token": "초5",
        "subject": "영어",
        "school_field": "타깃학교\n(초)",
        "grade_field": "가능학년\n(영어)",
    },
    {
        "slug": "초4수학학원",
        "label": "초4 수학학원",
        "grade": "초등학교 4학년",
        "grade_token": "초4",
        "subject": "수학",
        "school_field": "타깃학교\n(초)",
        "grade_field": "가능학년\n(수학)",
    },
    {
        "slug": "초4영어학원",
        "label": "초4 영어학원",
        "grade": "초등학교 4학년",
        "grade_token": "초4",
        "subject": "영어",
        "school_field": "타깃학교\n(초)",
        "grade_field": "가능학년\n(영어)",
    },
)

REQUIRED_SCHEMA_TYPES = {
    "EducationalOrganization",
    "LocalBusiness",
    "WebPage",
    "BreadcrumbList",
    "Article",
    "Service",
    "FAQPage",
    "ItemList",
}
FORBIDDEN_SCHEMA_TYPES = {"Review", "AggregateRating"}
AUTHORING_TOKENS = (
    "원고",
    "JSON-LD",
    "JSON 구조화 데이터",
    "구조화 데이터",
    "생성형 검색",
    "검색 품질",
    "검색 노출",
    "SEO",
    "AEO",
    "GEO",
    "제공된 자료",
    "제공된 학교",
    "제공된 위치",
    "정보성 페이지",
    "정보성 학원 페이지",
    "지역명만 바꾼",
    "페이지 개별화",
    "후기 예시",
    "학부모가 상담 후 남길 법한",
    "프롬프트",
    "AI 생성",
    "D열",
    "행에 적힌 수업학교",
    "본문에서는 해당 이름을 과도하게 반복",
    "정보형 페이지",
    "참고 키워드",
    "키워드 항목",
    "키워드",
    "정보성 안내는",
    "많이 검색되는 페이지",
    "단순 광고 표현",
    "차별점을 설명하는 단어",
)
BAD_LANGUAGE = (
    "학원를",
    "준비이 필요",
    "대비이 필요",
    "시간표이 필요",
    "테스트이 필요",
    "난이도이 필요",
    "분류이 필요",
    "말하기이 필요",
    "방식를 확인",
    "관리 관리",
    "상담 상담",
    "수업 수업",
    "학습 학습",
    "학생 학생",
    "합니다 이 기록",
    "참고 항목 항목",
    "이 이 안내",
    "항목로",
    "정확도을",
    "순서을",
    "입니다.을 위치",
    "하지만이 안내",
    ", 등 센터 안내",
    "학교에는 등이",
    "가늠하는 데 다음 계획",
    "가늠하는 데 학습 순서",
    "교육상담와 같은",
    "확인 의도",
    "확인어",
    "항목는",
    "조절를",
    "정확도이나",
    "않고이 안내",
    "없는 행",
    "임의 학교",
    "정보인을",
    "주소 항목에는",
    "가 제공되어 있으니",
    "페이지의 핵심",
    "등 센터 안내",
    "학교로 제시된 등을",
    "수업 학교로 제시된 등을",
    "이 행에는 수업 학교명",
    "학원 이 안내",
    "수학 이 안내",
    "영어 이 안내",
    "상담 주제",
    "특정 학교를 근거 없이 만들지 않고",
    "없는 학교를 만들지 않고",
    "자기 말으로",
    "수지구청 맞으면",
    "건겅검진센터",
    "뒷 건물 로",
)
REQUIRED_RELATIONS = {
    "WebPage": ("about", "mentions", "hasPart"),
    "Article": ("about", "mentions", "articleSection"),
    "EducationalOrganization": ("makesOffer",),
}

SCRIPT_RE = re.compile(
    r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")
ATTR_PAIR_RE = re.compile(r'([:\w-]+)\s*=\s*(["\'])(.*?)\2', re.DOTALL)
IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE | re.DOTALL)
ANCHOR_TAG_RE = re.compile(r"<a\b[^>]*>", re.IGNORECASE | re.DOTALL)
LINK_TAG_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE | re.DOTALL)


class VisibleMainParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.main_depth = 0
        self.skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "main":
            self.main_depth += 1
        if tag in {"script", "style", "template", "noscript"}:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "template", "noscript"} and self.skip_depth:
            self.skip_depth -= 1
        if tag == "main" and self.main_depth:
            self.main_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.main_depth and not self.skip_depth and data.strip():
            self.parts.append(data.strip())


def plain_text(value: str) -> str:
    value = re.sub(r"<script\b.*?</script>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<style\b.*?</style>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub(" ", value))).strip()


def visible_main(source: str) -> str:
    parser = VisibleMainParser()
    parser.feed(source)
    return re.sub(r"\s+", " ", html.unescape(" ".join(parser.parts))).strip()


def attrs(tag: str) -> dict[str, str]:
    return {
        key.lower(): html.unescape(value).strip()
        for key, _, value in ATTR_PAIR_RE.findall(tag)
    }


def split_values(value: str) -> list[str]:
    return list(
        dict.fromkeys(
            part.strip()
            for part in re.split(r"[,/\n·]+", value or "")
            if part.strip()
        )
    )


def split_school_values(value: str) -> list[str]:
    return list(
        dict.fromkeys(
            part.strip()
            for part in re.split(r"[,/\n·.\s]+", value or "")
            if part.strip()
            and part.strip() not in {"초등학교", "중학교", "고등학교"}
            and re.search(r"(?:초등학교|중학교|고등학교|초|중|고)$", part.strip())
        )
    )


def slug_local(value: str) -> str:
    return re.sub(r"\s+", "", value.strip())


def absolute_path(*parts: str) -> str:
    clean = "/".join(part.strip("/") for part in parts if part.strip("/"))
    return BASE_URL + "/" + clean + ("/" if clean else "")


def canonical_key(value: str) -> str:
    parsed = urlparse(html.unescape(value).strip())
    path = re.sub(r"/{2,}", "/", unquote(parsed.path or "/"))
    if not path.endswith("/"):
        path += "/"
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"


def load_rows() -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    path = COMMON / "센터정보 정리.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_slug: dict[str, dict[str, str]] = {}
    for row in rows:
        slug = slug_local(row.get("근처 수업가능 동네", ""))
        if not slug:
            raise ValueError("센터정보 정리.csv에 동네명이 비어 있는 행이 있습니다")
        if slug in by_slug:
            raise ValueError(f"센터정보 정리.csv 동네 슬러그 중복: {slug}")
        by_slug[slug] = row
    return rows, by_slug


def representative_urls() -> set[str]:
    source = (COMMON / "대표 이미지 url.csv").read_text(encoding="utf-8-sig")
    return set(
        re.findall(r'https?://[^"\s<>]+\.(?:jpg|jpeg|png|webp|gif)', source, re.IGNORECASE)
    )


def all_school_names(rows: list[dict[str, str]]) -> set[str]:
    result: set[str] = set()
    for row in rows:
        for field, value in row.items():
            if "타깃학교" in field:
                result.update(split_school_values(value))
    return result


def schema_types(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        node_type = value.get("@type")
        if isinstance(node_type, str):
            found.add(node_type)
        elif isinstance(node_type, list):
            found.update(item for item in node_type if isinstance(item, str))
        for child in value.values():
            found.update(schema_types(child))
    elif isinstance(value, list):
        for child in value:
            found.update(schema_types(child))
    return found


def graph_nodes(blocks: list[object]) -> list[dict]:
    nodes: list[dict] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        graph = block.get("@graph")
        if isinstance(graph, list):
            nodes.extend(node for node in graph if isinstance(node, dict))
        else:
            nodes.append(block)
    return nodes


def graph_node(nodes: list[dict], wanted: str) -> dict:
    for node in nodes:
        node_type = node.get("@type")
        if node_type == wanted or isinstance(node_type, list) and wanted in node_type:
            return node
    return {}


def parse_json_ld(source: str, page_key: str, errors: list[str]) -> tuple[list[object], list[dict]]:
    raw_blocks = SCRIPT_RE.findall(source)
    if len(raw_blocks) != 1:
        errors.append(f"jsonld-block-count:{page_key}:expected-1:actual-{len(raw_blocks)}")
    blocks: list[object] = []
    for index, raw in enumerate(raw_blocks, 1):
        try:
            blocks.append(json.loads(html.unescape(raw).strip()))
        except json.JSONDecodeError as exc:
            errors.append(f"jsonld-invalid:{page_key}:block-{index}:{exc.msg}")
    return blocks, graph_nodes(blocks)


def visible_faq(source: str) -> list[tuple[str, str]]:
    return [
        (plain_text(question), plain_text(answer))
        for question, answer in re.findall(
            r'<details\b[^>]*class=["\'][^"\']*\bfaq-item\b[^"\']*["\'][^>]*>'
            r'\s*<summary\b[^>]*>(.*?)</summary>\s*<p\b[^>]*>(.*?)</p>\s*</details>',
            source,
            flags=re.IGNORECASE | re.DOTALL,
        )
    ]


def structured_faq(nodes: list[dict]) -> list[tuple[str, str]]:
    node = graph_node(nodes, "FAQPage")
    result: list[tuple[str, str]] = []
    for item in node.get("mainEntity", []) if node else []:
        if not isinstance(item, dict):
            continue
        answer = item.get("acceptedAnswer", {})
        if not isinstance(answer, dict):
            answer = {}
        result.append((plain_text(str(item.get("name", ""))), plain_text(str(answer.get("text", "")))))
    return result


def section_by_class(source: str, class_name: str) -> str:
    match = re.search(
        rf'<section\b[^>]*class=["\'][^"\']*\b{re.escape(class_name)}\b[^"\']*["\'][^>]*>(.*?)</section>',
        source,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return match.group(1) if match else ""


def meta_value(source: str, key: str, wanted: str) -> list[str]:
    result: list[str] = []
    for tag in re.findall(r"<meta\b[^>]*>", source, flags=re.IGNORECASE | re.DOTALL):
        values = attrs(tag)
        if values.get(key) == wanted and "content" in values:
            result.append(values["content"])
    return result


def canonical_values(source: str) -> list[str]:
    result: list[str] = []
    for tag in re.findall(r"<link\b[^>]*>", source, flags=re.IGNORECASE | re.DOTALL):
        values = attrs(tag)
        if "canonical" in values.get("rel", "").lower().split() and "href" in values:
            result.append(values["href"])
    return result


def resolve_local(page: Path, value: str) -> Path | None:
    value = html.unescape(value).strip()
    if not value or value.startswith(("#", "tel:", "sms:", "mailto:", "data:", "javascript:")):
        return None
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"}:
        if parsed.netloc.lower() != urlparse(BASE_URL).netloc.lower():
            return None
        raw_path = unquote(parsed.path)
        target = SITE / raw_path.lstrip("/")
    elif parsed.scheme or value.startswith("//"):
        return None
    else:
        raw_path = unquote(parsed.path)
        target = SITE / raw_path.lstrip("/") if raw_path.startswith("/") else page.parent / raw_path
    if not raw_path or raw_path.endswith("/"):
        target = target / "index.html"
    elif target.is_dir():
        target = target / "index.html"
    return target.resolve()


def normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", plain_text(value)).strip()


def masked_text(text: str, values: list[str]) -> str:
    masked = text
    for value in sorted({item.strip() for item in values if item and item.strip()}, key=len, reverse=True):
        masked = masked.replace(value, " 변수 ")
    masked = re.sub(r"\d+(?:[.,]\d+)?", " 수치 ", masked)
    return re.sub(r"\s+", " ", masked).strip()


def word_shingles(value: str, size: int = 5) -> set[str]:
    tokens = re.findall(r"[가-힣A-Za-z]+", value)
    return {
        "\x1f".join(tokens[index : index + size])
        for index in range(max(0, len(tokens) - size + 1))
    }


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def similarity_worker(job: tuple[str, list[tuple[str, str, str]]]) -> tuple[str, dict]:
    category, records = job
    sets = [word_shingles(masked) for _, _, masked in records]
    best = [0.0] * len(sets)
    best_peer = [-1] * len(sets)
    pairs_075 = 0
    pairs_085 = 0
    for left_index, left in enumerate(sets):
        for right_index in range(left_index + 1, len(sets)):
            right = sets[right_index]
            intersection = len(left & right)
            union = len(left) + len(right) - intersection
            score = intersection / union if union else 1.0
            if score >= 0.75:
                pairs_075 += 1
            if score >= 0.85:
                pairs_085 += 1
            if score > best[left_index]:
                best[left_index] = score
                best_peer[left_index] = right_index
            if score > best[right_index]:
                best[right_index] = score
                best_peer[right_index] = left_index
    worst_index = max(range(len(best)), key=best.__getitem__) if best else 0
    peer_index = best_peer[worst_index] if best else -1
    masked_hashes = [hashlib.sha256(masked.encode("utf-8")).hexdigest() for _, _, masked in records]
    return category, {
        "pages": len(records),
        "masked_exact_duplicate_articles": len(records) - len(set(masked_hashes)),
        "average_best": round(statistics.mean(best), 4) if best else 0.0,
        "median_best": round(statistics.median(best), 4) if best else 0.0,
        "p95_best": round(percentile(best, 0.95), 4),
        "maximum": round(best[worst_index], 4) if best else 0.0,
        "worst_pair": [records[worst_index][0], records[peer_index][0]] if peer_index >= 0 else [],
        "pairs_at_or_above_0_75": pairs_075,
        "pairs_at_or_above_0_85": pairs_085,
    }


def explicit_school_list(source: str) -> list[str]:
    match = re.search(
        r"<dt>\s*(?:수업 가능 학교|학교 참고)\s*</dt>\s*<dd>(.*?)</dd>",
        source,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return []
    return [plain_text(item) for item in re.findall(r"<li\b[^>]*>(.*?)</li>", match.group(1), re.DOTALL)]


def school_item_list(nodes: list[dict]) -> list[str]:
    for node in nodes:
        if str(node.get("@id", "")).endswith("#schools"):
            result: list[str] = []
            for item in node.get("itemListElement", []):
                if isinstance(item, dict) and item.get("name"):
                    result.append(plain_text(str(item["name"])))
            return result
    return []


def local_resource_errors(page: Path, source: str, page_key: str) -> tuple[list[str], int, int]:
    errors: list[str] = []
    image_count = 0
    link_count = 0
    for tag in IMG_TAG_RE.findall(source):
        value = attrs(tag).get("src", "")
        if not value:
            errors.append(f"image-src-missing:{page_key}")
            continue
        image_count += 1
        target = resolve_local(page, value)
        if target is not None and not target.is_file():
            errors.append(f"image-file-missing:{page_key}:{value}")
    for tag in ANCHOR_TAG_RE.findall(source):
        value = attrs(tag).get("href", "")
        if not value:
            errors.append(f"anchor-href-missing:{page_key}")
            continue
        target = resolve_local(page, value)
        if target is None:
            continue
        link_count += 1
        try:
            target.relative_to(SITE.resolve())
        except ValueError:
            errors.append(f"internal-link-outside-site:{page_key}:{value}")
            continue
        if not target.is_file():
            errors.append(f"internal-link-missing:{page_key}:{value}")
    for tag in LINK_TAG_RE.findall(source):
        value = attrs(tag).get("href", "")
        if not value:
            errors.append(f"link-resource-href-missing:{page_key}")
            continue
        target = resolve_local(page, value)
        if target is None:
            continue
        link_count += 1
        try:
            target.relative_to(SITE.resolve())
        except ValueError:
            errors.append(f"link-resource-outside-site:{page_key}:{value}")
            continue
        if not target.is_file():
            errors.append(f"link-resource-missing:{page_key}:{value}")
    return errors, image_count, link_count


def audit_category(
    config: dict[str, str],
    row_by_slug: dict[str, dict[str, str]],
    known_schools: set[str],
    approved_representatives: set[str],
) -> tuple[dict, list[tuple[str, str, str]], set[str]]:
    category = config["slug"]
    root = SITE / SUBJECT_ROOT / category
    pages = sorted(root.glob("*/index.html")) if root.is_dir() else []
    errors: list[str] = []
    warnings: list[str] = []
    if not (root / "index.html").is_file():
        errors.append(f"category-hub-missing:{category}")
    if len(pages) != 371:
        errors.append(f"page-count:{category}:expected-371:actual-{len(pages)}")

    expected_urls = {absolute_path(SUBJECT_ROOT, category)}
    titles: list[str] = []
    descriptions: list[str] = []
    canonicals: list[str] = []
    faq_sets: list[str] = []
    scenario_sets: list[str] = []
    raw_articles: list[str] = []
    masked_articles: list[str] = []
    summary_sets: list[str] = []
    similarity_records: list[tuple[str, str, str]] = []
    checked_images = 0
    checked_links = 0
    unsupported_pages = 0
    supported_pages = 0
    school_alternatives = "|".join(
        re.escape(name)
        for name in sorted((name for name in known_schools if len(name) >= 3), key=len, reverse=True)
    )
    school_pattern = re.compile(
        rf"(?<![가-힣A-Za-z0-9])(?:{school_alternatives})"
        rf"(?=$|[^가-힣A-Za-z0-9]|(?:은|는|이|가|을|를|와|과|의|에|에서|으로|로|도|만|처럼|학생|재학생|이며|이고|입니다|이라|이었|였|까지|부터))"
    ) if school_alternatives else re.compile(r"(?!x)x")

    for page in pages:
        slug = page.parent.name
        page_key = f"{category}/{slug}"
        row = row_by_slug.get(slug)
        if row is None:
            errors.append(f"center-row-missing:{page_key}")
            continue
        local = row["근처 수업가능 동네"].strip()
        expected_title = f"{local} {config['label']}"
        expected_url = absolute_path(SUBJECT_ROOT, category, slug)
        expected_urls.add(expected_url)
        source = page.read_text(encoding="utf-8")
        screen_text = visible_main(source)

        title_nodes = re.findall(r"<title\b[^>]*>(.*?)</title>", source, flags=re.IGNORECASE | re.DOTALL)
        h1_nodes = re.findall(r"<h1\b[^>]*>(.*?)</h1>", source, flags=re.IGNORECASE | re.DOTALL)
        description_nodes = meta_value(source, "name", "description")
        canonical_nodes = canonical_values(source)
        og_url_nodes = meta_value(source, "property", "og:url")
        og_title_nodes = meta_value(source, "property", "og:title")
        og_image_nodes = meta_value(source, "property", "og:image")
        robots_nodes = meta_value(source, "name", "robots")

        document_title = plain_text(title_nodes[0]) if len(title_nodes) == 1 else ""
        h1 = plain_text(h1_nodes[0]) if len(h1_nodes) == 1 else ""
        description = plain_text(description_nodes[0]) if len(description_nodes) == 1 else ""
        canonical = canonical_nodes[0] if len(canonical_nodes) == 1 else ""
        og_url = og_url_nodes[0] if len(og_url_nodes) == 1 else ""
        titles.append(document_title)
        descriptions.append(description)
        canonicals.append(canonical_key(canonical) if canonical else "")

        if len(title_nodes) != 1:
            errors.append(f"title-count:{page_key}:{len(title_nodes)}")
        elif document_title != f"{expected_title} | {SITE_NAME}":
            errors.append(f"title-mismatch:{page_key}:{document_title}")
        if len(h1_nodes) != 1:
            errors.append(f"h1-count:{page_key}:{len(h1_nodes)}")
        elif h1 != expected_title:
            errors.append(f"h1-mismatch:{page_key}:{h1}")
        if len(description_nodes) != 1 or not description:
            errors.append(f"description-count-or-empty:{page_key}:{len(description_nodes)}")
        elif not 70 <= len(description) <= 100:
            errors.append(f"description-length:{page_key}:{len(description)}")
        if len(canonical_nodes) != 1:
            errors.append(f"canonical-count:{page_key}:{len(canonical_nodes)}")
        elif canonical_key(canonical) != canonical_key(expected_url):
            errors.append(f"canonical-mismatch:{page_key}:{canonical}")
        if len(og_url_nodes) != 1:
            errors.append(f"og-url-count:{page_key}:{len(og_url_nodes)}")
        elif canonical_key(og_url) != canonical_key(expected_url):
            errors.append(f"og-url-mismatch:{page_key}:{og_url}")
        if canonical and og_url and canonical_key(canonical) != canonical_key(og_url):
            errors.append(f"canonical-og-url-drift:{page_key}")
        if len(og_title_nodes) != 1 or plain_text(og_title_nodes[0]) != f"{expected_title} | {SITE_NAME}":
            errors.append(f"og-title-mismatch:{page_key}")
        if len(robots_nodes) != 1 or "index" not in robots_nodes[0].lower() or "noindex" in robots_nodes[0].lower():
            errors.append(f"robots-indexing-invalid:{page_key}")
        if 'lang="ko"' not in source[:500].lower() and "lang='ko'" not in source[:500].lower():
            errors.append(f"html-lang-ko-missing:{page_key}")
        if "/과목별학원/" not in source[source.find('<div class="nav-links"'):source.find("</nav>")]:
            errors.append(f"subject-navigation-missing:{page_key}")

        blocks, nodes = parse_json_ld(source, page_key, errors)
        present_types: set[str] = set()
        for block in blocks:
            present_types.update(schema_types(block))
        missing_schema = REQUIRED_SCHEMA_TYPES - present_types
        if missing_schema:
            errors.append(f"schema-missing:{page_key}:{','.join(sorted(missing_schema))}")
        forbidden_schema = FORBIDDEN_SCHEMA_TYPES & present_types
        if forbidden_schema:
            errors.append(f"schema-forbidden:{page_key}:{','.join(sorted(forbidden_schema))}")
        for node_type, relations in REQUIRED_RELATIONS.items():
            node = graph_node(nodes, node_type)
            for relation in relations:
                if node and not node.get(relation):
                    errors.append(f"schema-relation-missing:{page_key}:{node_type}.{relation}")
        webpage = graph_node(nodes, "WebPage")
        if webpage and canonical_key(str(webpage.get("url", ""))) != canonical_key(expected_url):
            errors.append(f"webpage-url-mismatch:{page_key}")

        screen_faq = visible_faq(source)
        json_faq = structured_faq(nodes)
        if len(screen_faq) != 4:
            errors.append(f"faq-count:{page_key}:expected-4:actual-{len(screen_faq)}")
        if screen_faq != json_faq:
            errors.append(f"faq-visible-json-mismatch:{page_key}")
        faq_sets.append("|".join(f"{q}\x1e{a}" for q, a in screen_faq))

        scenario_values = [
            plain_text(value)
            for value in re.findall(
                r'<article\b[^>]*class=["\'][^"\']*\breview-card\b[^"\']*["\'][^>]*>(.*?)</article>',
                source,
                flags=re.IGNORECASE | re.DOTALL,
            )
        ]
        if len(scenario_values) != 3:
            errors.append(f"consultation-scenario-count:{page_key}:expected-3:actual-{len(scenario_values)}")
        scenario_sets.append("|".join(scenario_values))

        media = section_by_class(source, "subject-media-section")
        media_images = IMG_TAG_RE.findall(media)
        hidden_tags = [tag for tag in media_images if "subject-hidden-representative" in attrs(tag).get("class", "").split()]
        if len(hidden_tags) != 1:
            errors.append(f"hidden-representative-count:{page_key}:{len(hidden_tags)}")
            representative = ""
        else:
            hidden = attrs(hidden_tags[0])
            representative = hidden.get("src", "")
            compact_style = re.sub(r"\s+", "", hidden.get("style", "").lower())
            if "display:none" not in compact_style:
                errors.append(f"hidden-representative-style:{page_key}")
            if hidden.get("loading"):
                errors.append(f"hidden-representative-loading-present:{page_key}")
            if hidden.get("alt") != f"{expected_title} {SITE_NAME} 대표":
                errors.append(f"hidden-representative-alt:{page_key}")
            if not representative.startswith("https://"):
                errors.append(f"hidden-representative-not-https:{page_key}:{representative}")
            elif representative not in approved_representatives:
                errors.append(f"hidden-representative-not-approved:{page_key}:{representative}")
            if media_images and media_images[0] != hidden_tags[0]:
                errors.append(f"hidden-representative-not-first:{page_key}")
        if len(og_image_nodes) != 1 or representative and og_image_nodes[0] != representative:
            errors.append(f"og-image-representative-mismatch:{page_key}")
        primary_image = graph_node(nodes, "ImageObject")
        if primary_image and representative and str(primary_image.get("url", "")) != representative:
            errors.append(f"schema-primary-image-mismatch:{page_key}")

        resource_errors, image_count, link_count = local_resource_errors(page, source, page_key)
        errors.extend(resource_errors)
        checked_images += image_count
        checked_links += link_count

        allowed_schools = split_school_values(row.get(config["school_field"], ""))
        visible_schools = explicit_school_list(source)
        expected_visible_schools = allowed_schools or ["상담 시 재학 학교와 진도를 확인합니다."]
        if visible_schools != expected_visible_schools:
            errors.append(f"visible-school-list-mismatch:{page_key}:{visible_schools}")
        structured_schools = school_item_list(nodes)
        if structured_schools != allowed_schools:
            errors.append(f"schema-school-list-mismatch:{page_key}:{structured_schools}")
        school_scan_text = screen_text
        verified_non_school_context = [
            *allowed_schools,
            row.get("센터명", ""),
            row.get("센터 주소", ""),
            row.get("위치안내", ""),
            row.get("교육지원청명칭", ""),
            row.get("교육지원청 등록번호", ""),
        ]
        for verified in sorted(
            {re.sub(r"\s+", " ", value).strip() for value in verified_non_school_context if value.strip()},
            key=len,
            reverse=True,
        ):
            school_scan_text = school_scan_text.replace(verified, " ")
        found_known = set(school_pattern.findall(school_scan_text)) if school_pattern.pattern else set()
        contaminated = sorted(found_known - set(allowed_schools))
        if contaminated:
            errors.append(f"school-contamination:{page_key}:{','.join(contaminated[:8])}")

        supported = config["grade_token"] in split_values(row.get(config["grade_field"], ""))
        service = graph_node(nodes, "Service")
        if supported:
            supported_pages += 1
        else:
            unsupported_pages += 1
            disclosure = re.search(
                r"(?:수업 가능 여부.{0,55}(?:확인|상담)|(?:확인|상담).{0,55}수업 가능 여부)",
                screen_text,
            )
            if not disclosure:
                errors.append(f"unsupported-grade-disclosure-missing:{page_key}")
            if "수업 가능 여부" not in description:
                errors.append(f"unsupported-grade-meta-disclosure-missing:{page_key}")
            service_type = str(service.get("serviceType", "")) if service else ""
            if service_type == "TutoringService" or not re.search(r"consult|guidance|상담|안내", service_type, re.I):
                errors.append(f"unsupported-grade-service-claim:{page_key}:{service_type}")
            if service and "TutoringService" in json.dumps(service.get("offers", []), ensure_ascii=False):
                errors.append(f"unsupported-grade-offer-claim:{page_key}")
            for phrase in (
                "학원을 선택한 뒤", "학원 수업에서", "학원 등록 후", "수업을 시작한 뒤",
                "수업을 시작하면", "수업을 시작했다면", "등록한 뒤", "등록했다면",
                "오답 노트가 실제 수업에서 어떻게 활용되는지",
                "오답 관리가 실제 수업에서 어떻게 활용되는지",
                "그 노트가 실제 수업에서 다시 활용되는지",
                "오답 관리가 실제 수업에서 어떻게 이루어지는지",
            ):
                if phrase in screen_text:
                    errors.append(f"unsupported-grade-assumption:{page_key}:{phrase}")

        for school in allowed_schools:
            if re.search(
                rf"{re.escape(school)}\s*,\s*(?:을|를|은|는|이|가|와|과|의|에|에서|으로|로|이며|이고|입니다)\b",
                screen_text,
            ):
                errors.append(f"school-particle-separator:{page_key}:{school}")
                break
        if re.search(r"검토할 때는[^.!?]{1,220}상담을 준비할 때는", screen_text):
            errors.append(f"repeated-clause-ending:{page_key}:때는")

        schema_text = json.dumps(blocks, ensure_ascii=False)
        for token in AUTHORING_TOKENS:
            visible_hit = bool(re.search(r"(?<![가-힣A-Za-z0-9])원고", screen_text)) if token == "원고" else token in screen_text
            schema_hit = bool(re.search(r"(?<![가-힣A-Za-z0-9])원고", schema_text)) if token == "원고" else token in schema_text
            if visible_hit:
                errors.append(f"authoring-token-visible:{page_key}:{token}")
            elif schema_hit:
                errors.append(f"authoring-token-jsonld:{page_key}:{token}")
        for token in BAD_LANGUAGE:
            if token in screen_text:
                errors.append(f"malformed-language:{page_key}:{token}")
        if category == "초4수학학원" and "약수와 배수" in screen_text:
            errors.append(f"curriculum-mismatch:{page_key}:약수와 배수")

        manuscript_html = section_by_class(source, "subject-manuscript")
        article = normalized_text(manuscript_html)
        if len(article) < 1800:
            warnings.append(f"manuscript-short:{page_key}:{len(article)}")
        summary = normalized_text(section_by_class(source, "subject-answer-summary"))
        mask_values = [
            expected_title,
            local,
            row.get("지역", ""),
            row.get("시or구", ""),
            row.get("센터명", ""),
            row.get("센터 주소", ""),
            row.get("위치안내", ""),
            row.get("교육지원청명칭", ""),
            row.get("교육지원청 등록번호", ""),
            config["label"],
            config["grade"],
            config["grade_token"],
            config["subject"],
            *allowed_schools,
        ]
        masked = masked_text(article, mask_values)
        raw_articles.append(article)
        masked_articles.append(masked)
        summary_sets.append(summary)
        similarity_records.append((page_key, article, masked))

    duplicate_metrics = {
        "titles": len(titles) - len(set(titles)),
        "meta_descriptions": len(descriptions) - len(set(descriptions)),
        "canonicals": len(canonicals) - len(set(canonicals)),
        "articles": len(raw_articles) - len(set(raw_articles)),
        "masked_articles": len(masked_articles) - len(set(masked_articles)),
        "faq_sets": len(faq_sets) - len(set(faq_sets)),
        "consultation_scenario_sets": len(scenario_sets) - len(set(scenario_sets)),
        "answer_summaries": len(summary_sets) - len(set(summary_sets)),
    }
    for name, count in duplicate_metrics.items():
        if count:
            errors.append(f"exact-duplicates:{category}:{name}:{count}")

    report = {
        "category": category,
        "label": config["label"],
        "pages": len(pages),
        "supported_grade_pages": supported_pages,
        "unsupported_grade_pages": unsupported_pages,
        "unique_titles": len(set(titles)),
        "unique_meta_descriptions": len(set(descriptions)),
        "description_length": {
            "min": min(map(len, descriptions)) if descriptions else 0,
            "average": round(statistics.mean(map(len, descriptions)), 1) if descriptions else 0.0,
            "max": max(map(len, descriptions)) if descriptions else 0,
        },
        "exact_duplicates": duplicate_metrics,
        "checked_images": checked_images,
        "checked_internal_links": checked_links,
        "errors": len(errors),
        "warnings": len(warnings),
        "error_counts": dict(sorted(Counter(item.split(":", 1)[0] for item in errors).items())),
        "warning_counts": dict(sorted(Counter(item.split(":", 1)[0] for item in warnings).items())),
        "error_sample": errors[:60],
        "warning_sample": warnings[:30],
    }
    return report, similarity_records, expected_urls


def audit_hubs(row_count: int) -> list[str]:
    errors: list[str] = []
    root = SITE / SUBJECT_ROOT / "index.html"
    if not root.is_file():
        return ["subject-root-hub-missing"]
    source = root.read_text(encoding="utf-8")
    for config in CATEGORIES:
        href = f'/{SUBJECT_ROOT}/{config["slug"]}/'
        if href not in source:
            errors.append(f"subject-root-category-link-missing:{config['slug']}")
        hub = SITE / SUBJECT_ROOT / config["slug"] / "index.html"
        if not hub.is_file():
            errors.append(f"category-hub-missing:{config['slug']}")
            continue
        hub_source = hub.read_text(encoding="utf-8")
        expected_links = {
            f'/{SUBJECT_ROOT}/{config["slug"]}/{slug_local(row["근처 수업가능 동네"])}/'
            for row in ROWS_FOR_HUB_AUDIT
        }
        actual_links = {
            attrs(tag).get("href", "")
            for tag in ANCHOR_TAG_RE.findall(hub_source)
        }
        missing = expected_links - actual_links
        if missing:
            errors.append(f"category-hub-local-links-missing:{config['slug']}:{len(missing)}")
        if len(expected_links) != row_count:
            errors.append(f"center-row-count:expected-{row_count}:actual-{len(expected_links)}")
    return errors


def audit_sitemap(expected_urls: set[str]) -> tuple[dict, list[str]]:
    path = SITE / "sitemap.xml"
    if not path.is_file():
        return {"exists": False, "missing_expected": len(expected_urls)}, ["sitemap-missing"]
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        return {"exists": True, "missing_expected": len(expected_urls)}, [f"sitemap-invalid:{exc}"]
    urls = [html.unescape(node.text or "").strip() for node in root.findall("{*}url/{*}loc")]
    keys = [canonical_key(url) for url in urls]
    expected_keys = {canonical_key(url) for url in expected_urls}
    counts = Counter(keys)
    duplicates = sorted(key for key, count in counts.items() if count > 1)
    missing = sorted(expected_keys - set(keys))
    errors: list[str] = []
    if duplicates:
        errors.append(f"sitemap-duplicate-urls:{len(duplicates)}")
    if missing:
        errors.append(f"sitemap-missing-subject-urls:{len(missing)}")
    return {
        "exists": True,
        "urls": len(urls),
        "unique_urls": len(set(keys)),
        "duplicate_urls": len(duplicates),
        "missing_expected": len(missing),
        "missing_sample": missing[:10],
    }, errors


ROWS_FOR_HUB_AUDIT: list[dict[str, str]] = []


def main() -> int:
    parser = argparse.ArgumentParser(description="전국학원.com 과목별학원 8×371 페이지 감사")
    parser.add_argument(
        "--category",
        action="append",
        choices=[config["slug"] for config in CATEGORIES],
        help="지정한 카테고리만 검사합니다. 여러 번 사용할 수 있습니다.",
    )
    parser.add_argument("--skip-similarity", action="store_true", help="마스킹 5-shingle 유사도 계산을 생략합니다.")
    parser.add_argument("--json-out", type=Path, help="동일 보고서를 JSON 파일로도 저장합니다.")
    args = parser.parse_args()

    global ROWS_FOR_HUB_AUDIT
    rows, row_by_slug = load_rows()
    ROWS_FOR_HUB_AUDIT = rows
    if len(rows) != 371:
        raise SystemExit(f"센터정보 정리.csv 행 수가 371개가 아닙니다: {len(rows)}")
    known_schools = all_school_names(rows)
    approved_representatives = representative_urls()
    selected = [
        config for config in CATEGORIES
        if not args.category or config["slug"] in set(args.category)
    ]

    category_reports: list[dict] = []
    similarity_jobs: list[tuple[str, list[tuple[str, str, str]]]] = []
    expected_urls = {absolute_path(SUBJECT_ROOT)}
    for config in selected:
        report, records, urls = audit_category(config, row_by_slug, known_schools, approved_representatives)
        category_reports.append(report)
        similarity_jobs.append((config["slug"], records))
        expected_urls.update(urls)

    similarity: dict[str, dict] = {}
    similarity_errors: list[str] = []
    if not args.skip_similarity and similarity_jobs:
        with ProcessPoolExecutor(max_workers=min(4, len(similarity_jobs))) as executor:
            futures = [executor.submit(similarity_worker, job) for job in similarity_jobs]
            for future in as_completed(futures):
                category, result = future.result()
                similarity[category] = result
                if result["masked_exact_duplicate_articles"]:
                    similarity_errors.append(
                        f"masked-exact-duplicate-articles:{category}:{result['masked_exact_duplicate_articles']}"
                    )
                if result["pairs_at_or_above_0_75"]:
                    similarity_errors.append(
                        f"masked-5-shingle-pairs-ge-0.75:{category}:{result['pairs_at_or_above_0_75']}"
                    )

    hub_errors = audit_hubs(len(rows)) if len(selected) == len(CATEGORIES) else []
    sitemap_report, sitemap_errors = audit_sitemap(expected_urls)
    structural_errors = sum(report["errors"] for report in category_reports)
    total_errors = structural_errors + len(similarity_errors) + len(hub_errors) + len(sitemap_errors)
    output = {
        "site": "전국학원.com",
        "site_root": str(SITE),
        "categories_checked": len(selected),
        "detail_pages_checked": sum(report["pages"] for report in category_reports),
        "status": "pass" if total_errors == 0 else "fail",
        "total_errors": total_errors,
        "categories": category_reports,
        "similarity": {key: similarity[key] for key in sorted(similarity)},
        "similarity_errors": similarity_errors,
        "hub_errors": hub_errors,
        "sitemap": sitemap_report,
        "sitemap_errors": sitemap_errors,
    }
    rendered = json.dumps(output, ensure_ascii=False, indent=2)
    print(rendered)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
