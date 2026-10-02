"""Render only the reviewed learning-guide library and refresh its release allow-list.

Run from the release checkout. Content modules contain original examples, not
source transcripts. Existing guide URLs, unrelated pages and sitemap dates stay.
"""
from pathlib import Path
from html import escape, unescape
from urllib.parse import quote, unquote, urlsplit
import argparse
import hashlib
import json
import re
from learning_guides import grade_exam, mathematics, english, reading_science, habits, parents
from learning_guides.sources import SOURCES
from learning_guides.adaptations import ADAPTATIONS

ROOT = Path(__file__).resolve().parents[1]
DAY = '2026-10-02'
DOMAIN = 'https://xn--3e0bl59bm0ad17a.com'
GUIDES = sum((m.GUIDES for m in (grade_exam, mathematics, english, reading_science, habits, parents)), [])
BY_SLUG = {g['slug']: g for g in GUIDES}
CATEGORIES = {
 'school': ('학년·시험', '학교가 바뀌거나 평가를 준비할 때'),
 'math': ('수학', '식과 조건, 풀이의 이유를 확인할 때'),
 'english': ('영어', '단어부터 읽기·듣기·쓰기까지'),
 'subjects': ('국어·사회·과학', '읽은 근거를 설명과 답안으로 옮길 때'),
 'habits': ('계획·습관', '오늘의 계획을 실제 공부로 이어 갈 때'),
 'parents': ('학부모 도움', '학생의 말을 듣고 필요한 도움을 정할 때'),
}
AUDIENCES = {'elementary':'초등학생', 'middle':'중학생', 'high':'고등학생', 'parent':'학부모'}
LEGACY = {'고1수학학습법','고1영어학습법','고2수학학습법','고2영어학습법','중2수학학습법','중2영어학습법','중3수학학습법','중3영어학습법','시험기간계획표','오답관리방법','플래너관리방법','학습진단상담준비'}
JOURNEYS = [
 ('초등학생의 첫 공부 습관', '준비와 읽기부터 학생이 맡을 일을 정해 보세요.', ['초등공부습관','초등읽기도움','수학문장제']),
 ('시험 준비가 막막할 때', '범위를 확인하고 남은 공부와 시험 뒤 점검을 연결하세요.', ['시험기간계획표','시험2주계획','시험후점검']),
 ('혼자 풀면 멈추는 수학', '오류를 찾고 필요한 도움과 설명을 구분하세요.', ['오답관리방법','해설의존줄이기','수학서술형']),
 ('읽기는 되는데 영어 답이 틀릴 때', '문장 관계와 글의 범위를 쓰기까지 이어 보세요.', ['영어문장읽기','고2영어학습법','영어서술형쓰기']),
 ('계획이 계속 밀릴 때', '시작 장면, 실제 시간, 다음 계획을 함께 보세요.', ['공부미루기','숙제시간관리','플래너관리방법']),
 ('보호자가 어디까지 도울지 고민될 때', '학생의 말과 실제 자료를 상담의 출발점으로 삼으세요.', ['공부대화방법','학습진단상담준비','학습변화관찰']),
]
E = lambda value: escape(str(value), quote=True)
J = lambda obj: json.dumps(obj, ensure_ascii=False, separators=(',', ':')).replace('<','\\u003c')
def route(slug=''):
    return '/학습가이드/' + (slug+'/' if slug else '')
def href(slug=''):
    return quote(route(slug), safe='/')
def canonical(slug=''):
    existing = ROOT / route(slug).lstrip('/') / 'index.html'
    if existing.exists():
        found = re.search(r'<link\b[^>]*rel="canonical"[^>]*href="([^"]+)"', existing.read_text('utf-8'))
        if found:
            url = unescape(found[1])
            assert unquote(urlsplit(url).path) == route(slug), ('Unexpected canonical', slug, url)
            return url
    return DOMAIN + href(slug)
def audiences(g):
    return ' · '.join(AUDIENCES[a] for a in g['audience'].split())
def li(items):
    return ''.join('<li>'+E(t)+'</li>' for t in items)
def breadcrumbs(title, slug):
    items = [('홈',DOMAIN+'/'), ('학습가이드',canonical())]
    if slug: items.append((title,canonical(slug)))
    return {'@type':'BreadcrumbList','@id':canonical(slug)+'#breadcrumb','itemListElement':[
      {'@type':'ListItem','position':i+1,'name':name,'item':url} for i,(name,url) in enumerate(items)]}
def source_html(g):
    return '<ul class="lg-sources">'+''.join(f'<li><a href="{E(SOURCES[k][1])}" rel="noopener noreferrer" target="_blank">{E(SOURCES[k][0])}<span class="lg-sr"> (새 창)</span></a><p>{E(SOURCES[k][2])}</p></li>' for k in g['sources'])+'</ul>'
def card(g):
    # All article links and summaries are server-rendered; filtering is optional.
    search = ' '.join([g['title'],g['description'],audiences(g),CATEGORIES[g['category']][0],*g['check'],*g['fields']])
    return f'''<article class="lg-card" data-guide-card data-category="{g['category']}" data-audience="{g['audience']}" data-search="{E(search)}">
      <p class="lg-card-audience">{E(audiences(g))}</p><h3><a href="{href(g['slug'])}">{E(g['title'])}</a></h3>
      <p>{E(g['description'])}</p><span class="lg-card-end" aria-hidden="true">연습 예시 · 기록 양식 <b>↗</b></span></article>'''
def shell(title, description, slug, content, graph, header, footer):
    url = canonical(slug)
    return f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)} | 전국학원</title><link rel="canonical" href="{E(url)}"><meta name="robots" content="index, follow">
<meta name="description" content="{E(description)}"><meta property="og:description" content="{E(description)}"><meta name="twitter:description" content="{E(description)}">
<meta property="og:title" content="{E(title)} | 전국학원"><meta property="og:url" content="{E(url)}"><meta property="og:type" content="{'article' if slug else 'website'}">
<meta property="og:locale" content="ko_KR"><meta property="og:site_name" content="전국학원"><meta property="og:image" content="{DOMAIN}/assets/title.png">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{E(title)} | 전국학원"><meta name="twitter:image" content="{DOMAIN}/assets/title.png">
<link rel="icon" href="/assets/favicon.png"><link rel="apple-touch-icon" href="/assets/favicon.png">
<link rel="stylesheet" href="/assets/site.css"><link rel="stylesheet" href="/assets/unified-ui.css?v=20260925"><link rel="stylesheet" href="/assets/learning-guides.css?v=20261002">
<script defer src="/assets/unified-ui.js?v=20260914-2"></script><script defer src="/assets/learning-guides.js?v=20261002"></script>
<script type="application/ld+json">{J({'@context':'https://schema.org','@graph':graph})}</script></head>
<body class="unified-ui learning-guides" data-learning-guides="{DAY}"><a class="skip-link" href="#main">본문 바로가기</a>
{header}<main id="main">{content}</main>{footer}</body></html>
'''
def article(g, header, footer):
    slug, title, desc = g['slug'], g['title'], g['description']
    cat = CATEGORIES[g['category']][0]
    steps = ''.join(f'<li><h3>{E(t)}</h3><p>{E(b)}</p></li>' for t,b in g['steps'])
    rows = ''.join('<tr><th scope="row">'+E(row[0])+'</th>'+''.join('<td>'+E(v)+'</td>' for v in row[1:])+'</tr>' for row in g['rows'])
    checks = ''.join(f'<li><label><input type="checkbox" data-check><span>{E(t)}</span></label></li>' for t in g['check'])
    fields = ''.join(f'<label for="note-{i}">{E(label)}</label><textarea id="note-{i}" data-record-field data-label="{E(label)}" rows="3" maxlength="1800" placeholder="내 과제에 맞게 적어 보세요."></textarea>' for i,label in enumerate(g['fields']))
    faq = ''.join(f'<details><summary>{E(q)}</summary><p>{E(a)}</p></details>' for q,a in g['faq'])
    related = ''.join(card(BY_SLUG[s]) for s in g['related'])
    toc = [('start','시작 전 점검'),('steps','실천 순서'),('example','연습 예시'),('record','나의 실천 기록'),('faq','자주 묻는 질문'),('sources','참고 자료')]
    contents = ''.join(f'<a href="#{key}">{E(name)}</a>' for key,name in toc)
    body = f'''
<div class="wrap lg-article-top"><nav class="guide-breadcrumb" aria-label="현재 위치"><a href="/">홈</a><span aria-hidden="true">›</span><a href="{href()}">학습가이드</a><span aria-hidden="true">›</span><a href="{href()}#category-{g['category']}">{cat}</a></nav>
<p class="lg-eyebrow">{cat} / LEARNING GUIDE</p><h1>{E(title)}</h1><p class="lg-byline">{E(audiences(g))}<span>전국학원 · 내용 확인 <time datetime="{DAY}">2026.10.02</time></span></p>
<div class="lg-answer"><strong>이 글에서 시작할 일</strong><p>{E(g['lead'])}</p></div></div>
<div class="wrap lg-reading-layout"><article class="lg-reading"><section id="start"><h2>시작 전에 확인해 보세요</h2><ul class="lg-checklist">{checks}</ul></section>
<section id="steps"><h2>과제에 적용하는 실천 순서</h2><ol class="lg-steps">{steps}</ol></section>
<section id="example" class="lg-example"><p class="lg-eyebrow">직접 해 보는 연습</p><h2>{E(g['example_title'])}</h2><p>{E(g['example'])}</p>
<div class="lg-table" role="region" aria-label="{E(g['example_title'])} 정리표" tabindex="0"><table><caption>연습 예시 정리</caption><thead><tr><th scope="col">확인할 부분</th><th scope="col">연습 내용</th><th scope="col">점검 포인트</th></tr></thead><tbody>{rows}</tbody></table></div>
<p class="lg-small">학습을 위해 만든 예시입니다. 실제 과제의 범위·조건·평가 기준은 학교 안내를 확인하세요.</p></section>
<section id="adjust"><h2>내 상황에 맞게 조정하기</h2><p>{E(ADAPTATIONS[slug])}</p><h3>연습할 때 구분할 점</h3><ul>{li(g['pitfalls'])}</ul><div class="lg-next"><h3>다음 과제에서는</h3><p>{E(g['next'])}</p></div></section>
<section id="record" class="lg-record" data-record data-title="{E(title)}" data-slug="{E(slug)}"><h2>나의 실천 기록</h2><p>오늘의 실제 과제 한 가지로 기록해 보세요. 이름이나 연락처를 적을 필요는 없습니다.</p>
<a class="lg-text-link" href="/assets/guide-worksheets/{quote(slug)}.txt" download="{E(slug)}-빈양식.txt">빈 기록 양식 내려받기 (TXT)</a>
<div class="lg-record-editor" hidden data-js-only><p class="lg-small">작성 내용은 자동 저장되지 않습니다. 새로고침하거나 페이지를 떠나기 전에 TXT 파일로 저장하세요.</p>
<label for="record-date">작성 날짜 (선택)</label><input id="record-date" type="date" data-record-date>
{fields}<div class="lg-actions"><button type="button" class="btn btn-primary" data-save-record disabled>작성한 기록 TXT 저장</button><button type="button" class="btn" data-print>가이드·기록 인쇄</button></div>
<p class="lg-record-status" role="status" aria-live="polite">한 항목 이상 적으면 저장할 수 있습니다.</p></div>
<noscript><p>빈 양식을 내려받아 사용하세요. 페이지 안의 기록 작성과 검색은 자바스크립트를 켜면 사용할 수 있습니다.</p></noscript><pre class="lg-print-record" aria-hidden="true"></pre></section>
<section id="faq" class="lg-faq"><h2>자주 묻는 질문</h2>{faq}</section>
<section id="sources"><h2>더 살펴볼 참고 자료</h2><p class="lg-small">2026.10.02 확인 · 해외 자료는 학습 활동을 살펴보는 참고 자료이며 국내 학교의 교육과정·평가 기준을 대신하지 않습니다.</p>{source_html(g)}</section></article>
<aside class="lg-side"><nav aria-label="글 목차" data-ui-toc><strong>이 글의 순서</strong>{contents}</nav><a class="lg-back" href="{href()}">← 전체 48개 가이드</a></aside></div>
<section class="wrap lg-related" id="related"><p class="lg-eyebrow">다음으로 읽기</p><h2>이런 질문도 이어서 살펴보세요</h2><div class="lg-grid">{related}</div><p class="lg-bottom-links"><a href="{href()}">전체 학습가이드</a><a href="/지점안내/">실제 지점 정보 확인</a></p></section>
'''
    url = canonical(slug)
    webpage = {'@type':'WebPage','@id':url+'#webpage','url':url,'name':title,'description':desc,'inLanguage':'ko-KR','dateModified':DAY,'isPartOf':{'@id':canonical()+'#webpage'}}
    article_node = {'@type':'Article','@id':url+'#article','headline':title,'description':desc,'abstract':g['lead'],'mainEntityOfPage':{'@id':url+'#webpage'},'dateModified':DAY,'author':{'@type':'Organization','name':'전국학원'},'publisher':{'@type':'Organization','name':'전국학원','url':DOMAIN+'/'},'inLanguage':'ko-KR','articleSection':cat,'image':DOMAIN+'/assets/title.png','citation':[SOURCES[k][1] for k in g['sources']]}
    if slug not in LEGACY: article_node['datePublished'] = DAY
    faq_node = {'@type':'FAQPage','@id':url+'#faq','mainEntity':[{'@type':'Question','name':q,'acceptedAnswer':{'@type':'Answer','text':a}} for q,a in g['faq']]}
    return shell(title,desc,slug,body,[webpage,article_node,breadcrumbs(title,slug),faq_node],header,footer)
def hub(header,footer):
    quick = [('시험이 얼마 안 남았어요','시험2주계획'),('수학 해설을 봐야 풀려요','해설의존줄이기'),('영어 문장이 길면 막혀요','영어문장읽기'),('숙제가 매번 남아요','숙제시간관리'),('새 학교 준비가 궁금해요','예비고등학교준비'),('공부 이야기가 어려워요','공부대화방법')]
    questions = ''.join(f'<a href="{href(slug)}"><span>{E(text)}</span><b aria-hidden="true">↗</b></a>' for text,slug in quick)
    buttons = '<button type="button" data-topic="all" aria-pressed="true">전체 <span>48</span></button>'+''.join(f'<button type="button" data-topic="{key}" aria-pressed="false">{name}</button>' for key,(name,_) in CATEGORIES.items())
    jumps = ''.join(f'<a href="#category-{key}">{name} <span>8</span></a>' for key,(name,_) in CATEGORIES.items())
    sections = ''.join(f'<section id="category-{key}" class="lg-category" data-guide-group><div class="lg-category-heading"><div><p class="lg-eyebrow">{i+1:02d} / LEARNING GUIDES</p><h2>{name}</h2><p>{E(text)}</p></div><span class="lg-count" data-group-count>8개</span></div><div class="lg-grid">'+''.join(card(g) for g in GUIDES if g['category']==key)+'</div></section>' for i,(key,(name,text)) in enumerate(CATEGORIES.items()))
    journeys = ''.join(f'<article class="lg-journey"><h3>{E(t)}</h3><p>{E(d)}</p><ol>'+''.join(f'<li><a href="{href(s)}">{E(BY_SLUG[s]["title"])}</a></li>' for s in slugs)+'</ol></article>' for t,d,slugs in JOURNEYS)
    title = '학생·학부모를 위한 학습가이드'
    desc = '학생과 학부모를 위한 48개 학습가이드에서 과목별 공부, 시험 준비와 학습 습관을 찾고 실천 기록을 작성해 보세요.'
    body = f'''
<section class="wrap lg-hub-hero"><div class="lg-hero-copy"><p class="lg-eyebrow">LEARNING LIBRARY · 학습가이드</p><h1>공부의 막힌 부분을,<br>오늘의 작은 실천으로.</h1><p class="lg-intro">학생의 과제에서 출발하는 공부 방법과<br class="lg-desktop-br"> 보호자가 함께 도울 수 있는 방법을 모았습니다.</p><div class="lg-stats"><span><b>48</b>개 가이드</span><span><b>6</b>개 주제</span><span>연습 예시 · 실천 기록</span></div><div class="lg-actions"><a class="btn btn-primary" href="#find-guides">내게 맞는 가이드 찾기 ↓</a><a class="lg-text-link" href="#reading-paths">어떤 순서로 읽을까요?</a></div></div>
<aside class="lg-starter"><p class="lg-eyebrow">한 번에 한 가지부터</p><ol><li><b>01</b><div><strong>지금의 고민을 고르세요</strong><p>학년·과목·상황으로 필요한 글을 찾습니다.</p></div></li><li><b>02</b><div><strong>내 과제에 적용해 보세요</strong><p>예시를 읽고 실제 자료로 한 번 해 봅니다.</p></div></li><li><b>03</b><div><strong>다음에 확인할 일을 남기세요</strong><p>혼자 한 부분과 질문을 기록으로 저장합니다.</p></div></li></ol></aside></section>
<section class="wrap lg-questions"><h2>이런 고민으로 찾아오셨나요?</h2><div>{questions}</div></section>
<section class="wrap lg-finder" id="find-guides"><p class="lg-eyebrow">FIND YOUR GUIDE</p><h2>지금 필요한 학습가이드 찾기</h2>
<div class="lg-filter" hidden data-js-only><div class="lg-search-row"><div><label for="guide-audience">읽는 대상</label><select id="guide-audience"><option value="all">모든 대상</option>{''.join(f'<option value="{k}">{v}</option>' for k,v in AUDIENCES.items())}</select></div><div><label for="guide-search">궁금한 내용</label><input id="guide-search" type="search" maxlength="120" placeholder="예: 분수, 듣기, 수행평가, 상담" autocomplete="off"></div><button type="button" class="btn" id="guide-reset">조건 초기화</button></div><div class="lg-topics" role="group" aria-label="주제별 가이드">{buttons}</div><p id="guide-count" role="status" aria-live="polite">48개 가이드를 볼 수 있습니다.</p></div>
<nav class="lg-category-jumps" aria-label="전체 주제 바로가기">{jumps}</nav><noscript><p>아래 전체 목록에서 글을 읽고 빈 기록 양식을 내려받을 수 있습니다. 검색과 대상·주제 필터는 자바스크립트를 켜면 사용할 수 있습니다.</p></noscript>
<div class="lg-empty" id="guide-empty" hidden><h3>조건에 맞는 가이드가 없습니다</h3><p>검색어를 짧게 바꾸거나 대상을 넓혀 보세요.</p><button type="button" class="btn" data-reset>전체 가이드 다시 보기</button></div>
<div id="guide-results">{sections}</div></section>
<section class="wrap lg-paths" id="reading-paths"><p class="lg-eyebrow">READING PATHS</p><h2>고민에 맞춰 세 편을 이어 읽어 보세요</h2><p>순서대로 읽되, 지금 필요한 글 한 편부터 시작해도 좋습니다.</p><div class="lg-journey-grid">{journeys}</div></section>
<section class="wrap lg-closing"><div><h2>읽은 뒤에는 실제 과제 하나로.</h2><p>모든 글에 연습 예시와 기록 양식이 있습니다. 직접 작성한 기록을 TXT로 저장하거나 빈 양식을 내려받아 학생과 함께 써 보세요.</p><p class="lg-small">시험 범위·제출 조건은 현재 학교 안내를, 수업의 학년·과목·시간·비용은 해당 지점의 안내를 확인하세요.</p></div><a class="btn" href="/지점안내/">지점 정보 살펴보기</a></section>
'''
    url = canonical()
    graph = [{'@type':'CollectionPage','@id':url+'#webpage','url':url,'name':title,'description':desc,'inLanguage':'ko-KR','dateModified':DAY,'mainEntity':{'@id':url+'#guides'}},breadcrumbs(title,''),{'@type':'ItemList','@id':url+'#guides','numberOfItems':48,'itemListElement':[{'@type':'ListItem','position':i+1,'name':g['title'],'url':canonical(g['slug'])} for i,g in enumerate(GUIDES)]}]
    return shell(title,desc,'',body,graph,header,footer), desc
def validate_content():
    assert len(GUIDES)==48 and len(BY_SLUG)==48
    assert LEGACY <= BY_SLUG.keys()
    assert set(ADAPTATIONS)==set(BY_SLUG)
    for g in GUIDES:
        assert g['category'] in CATEGORIES
        assert 0<len(g['description'])<=80 and g['description'].endswith('.'), g['slug']
        assert len(g['steps'])==4 and len(g['faq'])==2 and len(g['fields'])==4
        assert all(k in SOURCES for k in g['sources'])
        assert all(s in BY_SLUG and s!=g['slug'] for s in g['related'])
        assert all(a in AUDIENCES for a in g['audience'].split())
        assert '편집 원칙' not in json.dumps(g,ensure_ascii=False)
def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--report-dir',required=True); args=parser.parse_args()
    validate_content()
    report=Path(args.report_dir).resolve(); report.mkdir(parents=True,exist_ok=True)
    for name in ['release-public-manifest.json','seo-descriptions.json','sitemap.xml']:
        if not (report/('before-'+name)).exists(): (report/('before-'+name)).write_bytes((ROOT/name).read_bytes())
    original=(ROOT/'학습가이드/index.html').read_text('utf-8')
    header=re.search(r'<header class="site-header">[\s\S]*?</header>',original)[0]
    footer=re.search(r'<footer class="site-footer">[\s\S]*?</body>',original)[0].replace('</body>','')
    # Do not silently remove the owner's contact destinations.
    assert 'tel:010-3957-8283' in footer and 'blogsms.net/01039578283' in footer
    rendered, hub_desc=hub(header,footer)
    writes={'학습가이드/index.html':rendered.encode('utf-8')}
    descriptions={'/학습가이드':hub_desc}
    for g in GUIDES:
        relative='학습가이드/'+g['slug']+'/index.html'
        writes[relative]=article(g,header,footer).encode('utf-8')
        descriptions[route(g['slug']).rstrip('/')]=g['description']
        record='전국학원 학습가이드 | '+g['title']+'\n'+canonical(g['slug'])+'\n\n작성 날짜: \n\n'
        record+='\n\n'.join(label+':\n' for label in g['fields'])
        record+='\n\n다음 과제에서 확인할 일:\n'+g['next']+'\n'
        writes['assets/guide-worksheets/'+g['slug']+'.txt']=record.replace('\n','\r\n').encode('utf-8-sig')
    for name,data in writes.items():
        dest=ROOT/name; dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists() or dest.read_bytes()!=data: dest.write_bytes(data)
    config=json.loads((ROOT/'seo-descriptions.json').read_text('utf-8-sig'))
    for key,desc in descriptions.items():
        old=config['pages'].get(key,{'sources':[]})
        config['pages'][key]={'description':desc,'sources':list(dict.fromkeys([*old.get('sources',[]),*([old['description']] if 'description' in old else []),desc]))}
    (ROOT/'seo-descriptions.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    sitemap=(ROOT/'sitemap.xml').read_text('utf-8'); found=set()
    paths={route(''),*(route(g['slug']) for g in GUIDES)}
    def update_url(match):
        block=match[0]; loc=re.search(r'<loc>(.*?)</loc>',block)[1]; decoded=unquote(urlsplit(unescape(loc)).path)
        if decoded not in paths: return block
        found.add(decoded)
        if '<lastmod>' in block: return re.sub(r'<lastmod>.*?</lastmod>',f'<lastmod>{DAY}</lastmod>',block)
        return block.replace('</url>',f'<lastmod>{DAY}</lastmod></url>')
    sitemap=re.sub(r'<url\b[^>]*>[\s\S]*?</url>',update_url,sitemap)
    missing=sorted(paths-found)
    additions=''.join(f'<url><loc>{E(DOMAIN+quote(p,safe="/"))}</loc><lastmod>{DAY}</lastmod></url>\n' for p in missing)
    sitemap=sitemap.replace('</urlset>',additions+'</urlset>')
    (ROOT/'sitemap.xml').write_text(sitemap,encoding='utf-8',newline='\n')
    changed=set(writes)|{'assets/learning-guides.css','assets/learning-guides.js','sitemap.xml'}
    manifest=json.loads((ROOT/'release-public-manifest.json').read_text('utf-8'))
    for name in sorted(changed):
        data=(ROOT/name).read_bytes(); manifest['files'][name]=hashlib.sha256(data).hexdigest()
        manifest.setdefault('textSha256',{})[name]=hashlib.sha256(data.replace(b'\r\n',b'\n')).hexdigest()
    manifest['createdAt']=DAY
    manifest['sitemapPages']=sum(p.endswith('.html') for p in manifest['files'])
    baseline_manifest=json.loads((report/'before-release-public-manifest.json').read_text('utf-8'))
    for key in ('files','textSha256'):
        existing_order=list(baseline_manifest.get(key,{}))
        added=sorted(set(manifest[key])-set(existing_order))
        manifest[key]={name:manifest[key][name] for name in existing_order+added if name in manifest[key]}
    (ROOT/'release-public-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    result={'date':DAY,'guides':48,'categories':6,'existingGuidesRewritten':12,'newGuides':36,'guidePages':49,'worksheets':48,'sources':len(SOURCES),'sitemapPages':manifest['sitemapPages'],'publicFiles':len(manifest['files']),'publicChanges':sorted(changed),'deployed':False}
    (report/'generation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (report/'guide-data.json').write_text(json.dumps(GUIDES,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='publicChanges'},ensure_ascii=False))
if __name__=='__main__': main()
