"""Render 30 reviewed articles and add a discoverable index of 68 existing articles.

Source selection and provenance remain in a private report directory. Only
reviewed HTML and unchanged illustrative images enter the public allow-list.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from html import escape, unescape
from urllib.parse import quote, unquote, urlsplit
import argparse, hashlib, json, re, shutil, zipfile
from lxml import html
from education_info import CATEGORIES, SOURCES, part1, part2, part3, part4, part5, part6
from education_info.images import ALTS
from build_learning_guides import GUIDES

ROOT = Path(__file__).resolve().parents[1]
DAY = '2026-10-03'
DOMAIN = 'https://xn--3e0bl59bm0ad17a.com'
ARTICLES = sum((m.ARTICLES for m in (part1,part2,part3,part4,part5,part6)),[])
E = lambda s: escape(str(s),quote=True)
H = lambda s: quote(s,safe='/#-._~?=&')
J = lambda obj: json.dumps(obj,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
digest = lambda b: hashlib.sha256(b).hexdigest()
MENU = '<a href="/교육정보/" data-education-menu>교육정보</a>'
START = '<!-- education-info:start -->'
END = '<!-- education-info:end -->'
REGIONS = ['서울','경기','인천','강원','대전','세종','충북','충남','대구','부산','울산','경북','경남','광주','전북','전남','제주']
NEIGHBORHOOD_REGION = {'세종':'충청','충북':'충청','충남':'충청','경북':'경상','경남':'경상','전북':'전라','전남':'전라'}

def write(path, data):
    if isinstance(data,str): data=data.encode('utf-8')
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists() or path.read_bytes()!=data: path.write_bytes(data)

def route(a=None): return '/교육정보/'+(a['slug']+'/' if a else '')
def load(path): return json.loads(path.read_text('utf-8-sig'))
def paragraphs(items): return ''.join('<p>'+E(p)+'</p>' for p in items)

def add_menu(raw):
    for pattern in [r'(<div\b[^>]*data-unified-nav[^>]*>)([\s\S]*?)(</div>)',r'(<nav\b[^>]*class="footer-links"[^>]*>)([\s\S]*?)(</nav>)']:
        def replace(m):
            if 'data-education-menu' in m[2]: return m[0]
            links=re.sub(r'(<a\b[^>]*>학습가이드</a>)',r'\1'+MENU,m[2],count=1)
            assert links!=m[2], 'Expected learning-guide navigation'
            return m[1]+links+m[3]
        raw=re.sub(pattern,replace,raw,count=1)
    return re.sub(r'(/assets/unified-ui\.css)(?:\?[^"\s>]*)?',r'\1?v=20261002-education',raw)

def existing_library():
    guide_by_path={'/학습가이드/'+g['slug']+'/':g for g in GUIDES}
    mapped={'school':'exam','math':'subject','english':'subject','subjects':'subject','habits':'plan','parents':'support'}
    items=[]
    for family in ('학습가이드','학습코칭'):
        for path in sorted((ROOT/family).glob('*/index.html')):
            doc=html.fromstring(path.read_bytes())
            public='/'+path.relative_to(ROOT).as_posix().removesuffix('index.html')
            title=''.join(doc.xpath('//h1')[0].itertext()).strip()
            desc=doc.xpath('//meta[@name="description"]/@content')[0]
            if public in guide_by_path:
                g=guide_by_path[public]; cat=mapped[g['category']]
                audience=' · '.join({'elementary':'초등학생','middle':'중학생','high':'고등학생','parent':'학부모'}[v] for v in g['audience'].split())
            else:
                cat='support' if '부모' in title else 'exam' if any(w in title for w in ['시험','내신','서술형']) else 'subject' if any(w in title for w in ['영어','국어','과학','사회','독서']) else 'plan'
                audience='학생 · 학부모'
            items.append(dict(path=public,title=title,description=desc,category=cat,audience=audience,kind='guide' if family=='학습가이드' else 'coaching'))
    assert Counter(a['kind'] for a in items)=={'guide':48,'coaching':20}
    return items

def card(a,heading='h3',filterable=False):
    cat=CATEGORIES[a['category']]
    kind={'new':'교육정보','guide':'학습가이드','coaching':'학습코칭'}[a['kind']]
    attributes=f' data-library-card data-topic="{a["category"]}" data-kind="{a["kind"]}" data-search="{E(a["title"]+" "+a["description"]+" "+a["audience"]+" "+cat)}"' if filterable else ''
    media=''
    if a.get('images'):
        p=a['images'][0]
        media=f'<img class="ei-card-image" src="/{p["path"]}" alt="" width="{p["width"]}" height="{p["height"]}" loading="lazy" decoding="async">'
    return f'<article class="ei-card"{attributes}>{media}<div class="ei-card-copy"><p class="ei-kicker">{cat} <span>· {kind}</span></p><{heading}><a href="{H(a["path"])}">{E(a["title"])}</a></{heading}><p>{E(a["description"])}</p><span class="ei-card-end">{E(a["audience"])}</span></div></article>'

def finder(branches):
    options=''.join(f'<option value="{r}" data-neighborhood-href="{H("/전국학원/"+NEIGHBORHOOD_REGION.get(r,r)+"/")}" data-neighborhood-label="{NEIGHBORHOOD_REGION.get(r,r)}">{r}</option>' for r in REGIONS)
    neighborhood_regions=list(dict.fromkeys(NEIGHBORHOOD_REGION.get(r,r) for r in REGIONS))
    links=''.join(f'<a href="{H("/전국학원/"+r+"/")}">{r} 동네 찾기</a>' for r in neighborhood_regions)
    assert all((ROOT/'전국학원'/r/'index.html').exists() for r in neighborhood_regions)
    branch_regions=[r for r in REGIONS if any(b['region']==r for b in branches)]
    direct=''.join(f'<a href="{H("/지점안내/"+r+"/")}">{r} 지점 안내</a>' for r in branch_regions)
    return f'''<section class="ei-local" id="local-help" aria-labelledby="ei-local-title"><p class="ei-kicker">우리 지역에서 이어서 확인하기</p><h2 id="ei-local-title">읽은 내용을 상담 질문으로 가져가세요</h2><p>최근 답안과 학생의 질문을 준비한 뒤, 가까운 동네와 지점의 안내를 살펴보세요. 학년·과목·시간·비용은 해당 지점의 현재 안내로 확인하세요.</p>
<div class="ei-location-form" data-location-form hidden><div><label for="ei-region">지역 선택</label><select id="ei-region"><option value="">지역을 선택하세요</option>{options}</select></div><div><label for="ei-branch">지점 선택</label><select id="ei-branch" disabled><option value="">지역을 먼저 선택하세요</option></select></div></div><div id="ei-location-result" class="ei-location-result" role="status" aria-live="polite"></div>
<div class="ei-actions"><a class="ei-btn" href="/전국학원/">우리 동네 학원 찾기</a><a class="ei-btn ei-secondary" href="/지점안내/">전체 지점 안내</a><a class="ei-text-link" href="/선생님찾기/">선생님 소개 보기 →</a></div>
<details class="ei-region-list"><summary>지역별 동네·지점 바로가기</summary><nav aria-label="지역별 동네 안내">{links}</nav><nav aria-label="지역별 지점 안내">{direct}</nav></details>
<script type="application/json" id="ei-locations">{J(branches)}</script></section>'''

def shell(a,title,desc,body,graph,header,footer):
    url=DOMAIN+H(route(a))
    current=re.sub(r'\sclass="active"\saria-current="page"','',header)
    current=current.replace('data-education-menu>','data-education-menu class="active" aria-current="page">')
    og=DOMAIN+'/'+a['images'][0]['path'] if a else DOMAIN+'/assets/title.png'
    return f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{E(title)} | 전국학원</title><meta name="description" content="{E(desc)}"><meta name="robots" content="index,follow"><link rel="canonical" href="{url}"><link rel="icon" href="/assets/favicon.png"><meta name="theme-color" content="#173b32">
<meta property="og:type" content="{'article' if a else 'website'}"><meta property="og:locale" content="ko_KR"><meta property="og:site_name" content="전국학원"><meta property="og:title" content="{E(title)} | 전국학원"><meta property="og:description" content="{E(desc)}"><meta property="og:url" content="{url}"><meta property="og:image" content="{og}"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{E(title)} | 전국학원"><meta name="twitter:description" content="{E(desc)}"><meta name="twitter:image" content="{og}">
<link rel="stylesheet" href="/assets/site.css"><link rel="stylesheet" href="/assets/unified-ui.css?v=20261002-education"><link rel="stylesheet" href="/assets/education-info.css?v=20261002"><script defer src="/assets/unified-ui.js?v=20260914-2"></script><script defer src="/assets/education-info.js?v=20261002"></script><script type="application/ld+json">{J({'@context':'https://schema.org','@graph':graph})}</script></head>
<body class="unified-ui ei-page" data-education-info="{DAY}"><a class="skip-link" href="#main">본문 바로가기</a>{current}<main id="main">{body}</main>{footer}</body></html>'''

def breadcrumbs(a=None):
    items=[('홈','/'),('교육정보',route())]+([(a['title'],route(a))] if a else [])
    return {'@type':'BreadcrumbList','@id':DOMAIN+H(route(a))+'#breadcrumb','itemListElement':[{'@type':'ListItem','position':i,'name':n,'item':DOMAIN+H(p)} for i,(n,p) in enumerate(items,1)]}

def figure(a,index):
    p=a['images'][index]
    return f'<figure class="ei-figure" data-education-image><img src="/{p["path"]}" alt="{E(p["alt"])}" width="{p["width"]}" height="{p["height"]}" loading="lazy" decoding="async"><figcaption>학습 상황을 표현한 참고 이미지입니다.</figcaption></figure>'

def render_article(a,library,branches,header,footer):
    category=CATEGORIES[a['category']]
    crumbs=f'<nav class="ei-breadcrumb" aria-label="현재 위치"><a href="/">홈</a><span>/</span><a href="/교육정보/">교육정보</a><span>/</span><a href="/교육정보/?topic={a["category"]}#library">{category}</a></nav>'
    toc=[(f'section-{i}',t) for i,(t,_) in enumerate(a['sections'],1)]+[('example','예시로 적용하기'),('check','나에게 적용하기'),('question','궁금한 점'),('sources','참고 자료'),('local-help','동네·지점 안내')]
    contents=''.join(f'<a href="#{key}">{E(t)}</a>' for key,t in toc)
    sections=''
    for i,(t,ps) in enumerate(a['sections'],1):
        sections+=f'<section id="section-{i}" class="ei-prose-section"><p class="ei-section-number">0{i}</p><h2>{E(t)}</h2>{paragraphs(ps)}</section>'
        if i<3: sections+=figure(a,i-1)
    title,intro,heads,rows,after=a['example']
    table='<div class="ei-table-scroll" tabindex="0" role="region" aria-label="'+E(title)+' 표"><table><caption>'+E(title)+'</caption><thead><tr>'+''.join('<th scope="col">'+E(h)+'</th>' for h in heads)+'</tr></thead><tbody>'+''.join('<tr><th scope="row">'+E(r[0])+'</th>'+''.join('<td>'+E(v)+'</td>' for v in r[1:])+'</tr>' for r in rows)+'</tbody></table></div>'
    example=f'<section class="ei-example" id="example"><p class="ei-kicker">예시로 적용하기</p><h2>{E(title)}</h2><p>{E(intro)}</p>{table}<p>{E(after)}</p></section>'+figure(a,2)
    checks='<ul class="ei-checks">'+''.join('<li>'+E(v)+'</li>' for v in a['checks'])+'</ul>'
    faq=f'<section id="question" class="ei-prose-section"><h2>궁금한 점</h2><details open><summary>{E(a["faq"][0])}</summary><p>{E(a["faq"][1])}</p></details></section>'
    sources='<section id="sources" class="ei-sources"><h2>참고 자료</h2><ul>'+''.join(f'<li><a href="{E(SOURCES[k][1])}" target="_blank" rel="noopener noreferrer">{E(SOURCES[k][0])}<span class="ei-sr"> (새 창)</span></a><p>{E(SOURCES[k][2])}</p></li>' for k in a['sources'])+'</ul><p>확인일: 2026년 10월 2일 · 예시의 시간·분량은 학생의 과제와 학교 안내에 맞춰 조정하세요.</p></section>'
    by_path={x['path']:x for x in library}
    related=[by_path[p] for p in a['related']]
    next_new=next(x for x in library if x['kind']=='new' and x['category']==a['category'] and x['number']!=a['number'])
    related.append(next_new)
    body=f'''<div class="wrap ei-article-top">{crumbs}<header class="ei-article-heading"><p class="ei-kicker">{category} · {E(a['audience'])}</p><h1>{E(a['title'])}</h1><p class="ei-deck">{E(a['description'])}</p><p class="ei-byline">전국학원 · 2026년 10월 3일</p></header></div>
<div class="wrap ei-reading-layout"><aside class="ei-toc"><p class="ei-kicker">이 글에서 확인할 내용</p><nav aria-label="글 목차">{contents}</nav><a class="ei-toc-back" href="/교육정보/#library">← 교육정보 전체 보기</a></aside><article class="ei-prose" data-education-article><p class="ei-intro">{E(a['intro'])}</p>{sections}{example}<section class="ei-try" id="check"><h2>나에게 적용하기</h2>{checks}<p>이 중 아직 확인하지 못한 한 가지를 골라, 오늘의 실제 과제에 적용해 보세요.</p></section>{faq}{sources}</article></div>
<div class="wrap ei-after-reading">{finder(branches)}<section class="ei-related" id="related-reading"><p class="ei-kicker">함께 읽으면 좋은 글</p><h2>다음 질문으로 이어 읽으세요</h2><div class="ei-grid">{''.join(card(x) for x in related)}</div><a class="ei-text-link" href="/교육정보/#library">교육정보 전체 목록 보기 →</a></section></div>'''
    url=DOMAIN+H(route(a))
    article_node={'@type':'Article','@id':url+'#article','url':url,'headline':a['title'],'description':a['description'],'inLanguage':'ko-KR','articleSection':category,'datePublished':DAY,'dateModified':DAY,'author':{'@type':'Organization','name':'전국학원','url':DOMAIN+'/'},'publisher':{'@id':DOMAIN+'/#organization'},'mainEntityOfPage':{'@id':url+'#webpage'},'image':[DOMAIN+'/'+p['path'] for p in a['images']],'citation':[SOURCES[k][1] for k in a['sources']]}
    graph=[{'@type':'Organization','@id':DOMAIN+'/#organization','name':'전국학원','url':DOMAIN+'/'},{'@type':'WebPage','@id':url+'#webpage','url':url,'name':a['title'],'description':a['description'],'breadcrumb':{'@id':url+'#breadcrumb'}},breadcrumbs(a),article_node]
    return shell(a,a['title'],a['description'],body,graph,header,footer)

def hub(library,branches,header,footer):
    desc='시험 준비·과목별 공부·계획과 습관·학부모 도움을 다루는 교육정보와 기존 학습가이드를 모아 필요한 글을 찾도록 안내합니다.'
    categories=''.join(f'<a href="?topic={k}#library" data-topic-link="{k}"><span>0{i}</span><strong>{v}</strong><b aria-hidden="true">↗</b></a>' for i,(k,v) in enumerate(CATEGORIES.items(),1))
    body=f'''<section class="wrap ei-hub-hero"><div><p class="ei-kicker">전국학원 교육정보</p><h1>공부의 방법을 찾고,<br>우리 아이에게 맞춰 보세요.</h1><p class="ei-deck">시험 앞의 막막함부터 매일의 작은 습관까지.<br>학생과 학부모의 질문에서 출발하는 읽을거리를 모았습니다.</p><a class="ei-btn" href="#library">지금 필요한 글 찾기 ↓</a></div><aside class="ei-hero-note"><span class="ei-note-number">30</span><h2>새롭게 더한 교육정보</h2><p>구체적인 예시와 점검 질문으로<br>오늘의 공부에 이어 보세요.</p><div><span>학습가이드 <b>48</b></span><span>학습코칭 글 <b>20</b></span></div></aside></section>
<nav class="wrap ei-topic-tiles" aria-label="고민별 교육정보">{categories}</nav>
<section class="wrap ei-library" id="library"><div class="ei-section-heading"><div><p class="ei-kicker">교육정보 모아보기</p><h2>어떤 도움이 필요한가요?</h2></div><p>새 교육정보와 기존 가이드를 한곳에서 찾아보세요.</p></div>
<form class="ei-filters" data-library-filters hidden role="search"><div><label for="ei-search">궁금한 내용</label><input id="ei-search" type="search" maxlength="120" placeholder="예: 기말고사, 영어, 플래너" autocomplete="off"></div><div><label for="ei-topic">주제</label><select id="ei-topic"><option value="all">모든 주제</option>{''.join(f'<option value="{k}">{v}</option>' for k,v in CATEGORIES.items())}</select></div><div><label for="ei-kind">글 종류</label><select id="ei-kind"><option value="all">모든 글</option><option value="new">새 교육정보 30편</option><option value="guide">학습가이드 48편</option><option value="coaching">학습코칭 20편</option></select></div><button class="ei-btn ei-secondary" type="reset">초기화</button></form>
<p id="ei-result-count" class="ei-result-count" role="status" aria-live="polite">전체 98편 · 교육정보 30편, 학습가이드 48편, 학습코칭 20편</p><noscript><p>전체 글을 아래에서 읽을 수 있습니다. 검색과 주제 필터는 자바스크립트를 켜면 사용할 수 있습니다.</p></noscript>
<div class="ei-grid" id="ei-results">{''.join(card(x,filterable=True) for x in library)}</div><div id="ei-empty" class="ei-empty" hidden><h3>조건에 맞는 글이 없습니다</h3><p>검색어를 짧게 바꾸거나 주제·종류를 넓혀 보세요.</p><button class="ei-btn" type="button" data-library-reset>전체 글 다시 보기</button></div><button id="ei-more" class="ei-btn ei-secondary ei-more" type="button" hidden>글 더 보기</button></section>
<div class="wrap ei-after-reading">{finder(branches)}</div>'''
    url=DOMAIN+H(route());title='학생과 학부모를 위한 교육정보'
    graph=[{'@type':'CollectionPage','@id':url+'#webpage','url':url,'name':title,'description':desc,'inLanguage':'ko-KR','dateModified':DAY,'mainEntity':{'@id':url+'#library'},'breadcrumb':{'@id':url+'#breadcrumb'}},breadcrumbs(),{'@type':'ItemList','@id':url+'#library','numberOfItems':len(library),'itemListElement':[{'@type':'ListItem','position':i,'name':x['title'],'url':DOMAIN+H(x['path'])} for i,x in enumerate(library,1)]}]
    return shell(None,title,desc,body,graph,header,footer),desc

def contextual(name):
    if name=='index.html': category='exam'; heading='공부가 막힐 때, 교육정보에서 실마리를 찾으세요'
    elif any(x in name for x in ['수학','영어','국어','과학','사회']): category='subject'; heading='과목별 공부 방법도 함께 살펴보세요'
    elif name.startswith(('선생님찾기/','상담문의/')): category='support'; heading='상담 전에 학생의 질문을 정리해 보세요'
    elif name.startswith('학습코칭/'): category='plan'; heading='오늘의 학습에 적용할 교육정보'
    else: category='exam'; heading='학원 정보와 함께 읽는 공부 안내'
    candidates=[a for a in ARTICLES if a['category']==category]
    if '수학' in name: selected=[a for a in ARTICLES if a['number'] in (3,7)]
    elif '영어' in name: selected=[a for a in ARTICLES if a['number'] in (18,19)]
    elif '과학' in name: selected=[a for a in ARTICLES if a['number'] in (28,29)]
    else: selected=candidates[:2]
    links=''.join(f'<a href="{H(route(a))}">{E(a["title"])} <span aria-hidden="true">↗</span></a>' for a in selected)
    return START+f'<section class="education-bridge" data-education-bridge="{category}"><div><p class="education-kicker">학생·학부모 교육정보</p><h2>{heading}</h2><p>시험 준비, 과목별 공부와 학습 습관을 구체적인 예시로 확인하세요.</p></div><nav aria-label="함께 읽는 교육정보">{links}<a class="education-all" href="/교육정보/">교육정보 전체 보기 →</a></nav></section>'+END

def main():
    p=argparse.ArgumentParser();p.add_argument('--report-dir',required=True);p.add_argument('--teacher-model',required=True);p.add_argument('--articles-only',action='store_true');args=p.parse_args()
    out=Path(args.report_dir).resolve();source=load(out/'selection.json');baseline=load(out/'before-release-public-manifest.json')
    assert len(ARTICLES)==30 and len({a['slug'] for a in ARTICLES})==30 and [a['number'] for a in ARTICLES]==list(range(1,31))
    overrides=load(out/'image-overrides.json') if (out/'image-overrides.json').exists() else []
    for change in overrides: source['articles'][change['number']-1]['images'][change['index']]={k:change[k] for k in ('source','sha256','width','height','bytes')}
    # Backup the exact reviewed public HTML once before any global insertion.
    pages=[n for n in baseline['files'] if n.endswith('.html')]
    backup=out/'before-pages.zip'
    if not backup.exists():
        with ThreadPoolExecutor(max_workers=12) as pool,zipfile.ZipFile(backup,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
            for name,data in pool.map(lambda n:(n,(ROOT/n).read_bytes()),pages):z.writestr(name,data)
    with zipfile.ZipFile(backup) as z:
        originals={name:z.read(name).decode('utf-8') for name in (['학습가이드/index.html'] if args.articles_only else pages)}
    model=load(Path(args.teacher_model));branches=[{k:b[k] for k in ('name','region','address','sitePath','neighborhoods')} for b in model['branches'] if b['sitePath']]
    assert len(branches)==193
    for b in branches:
        assert (ROOT/b['sitePath'].lstrip('/')/'index.html').exists()
        for n in b['neighborhoods']: assert (ROOT/n['path'].lstrip('/')/'index.html').exists()
    changed=set();mappings=[]
    for a,selected,alts in zip(ARTICLES,source['articles'],ALTS):
        assert a['number']==selected['number'] and len(selected['images'])==len(alts)==3
        assert a['title']!=selected['folder'] and len(a['description'])<=80 and a['description'].endswith('.')
        assert all(k in SOURCES for k in a['sources'])
        a['kind']='new';a['path']=route(a);a['images']=[]
        for i,(photo,alt) in enumerate(zip(selected['images'],alts),1):
            path=f'assets/education-info/{a["number"]:02d}-{i}'+Path(photo['source']).suffix.lower()
            origin=Path(source['source'])/'1 이미지'/photo['source'];data=origin.read_bytes()
            assert digest(data)==photo['sha256']
            write(ROOT/path,data);changed.add(path)
            a['images'].append({**photo,'path':path,'alt':alt+' · 참고 이미지'})
        mappings.append(dict(number=a['number'],sourceFolder=selected['folder'],sourceHash=selected['sha256'],path=a['path'],title=a['title'],images=a['images']))
    library=[*ARTICLES,*existing_library()]
    assert len(library)==98 and len({x['path'] for x in library})==98
    original=originals['학습가이드/index.html']
    header=add_menu(re.search(r'<header class="site-header">[\s\S]*?</header>',original)[0])
    footer=add_menu(re.search(r'<footer class="site-footer">[\s\S]*?</body>',original)[0].replace('</body>',''))
    assert 'tel:010-3957-8283' in footer and 'blogsms.net/01039578283' in footer
    def update_existing(name):
        raw=originals[name];updated=add_menu(raw);module=contextual(name)
        if name=='index.html':
            found=re.search(r'<section\b[^>]*id="learning-paths"',updated)
            assert found;updated=updated[:found.start()]+module+updated[found.start():]
        else:
            first_main=updated.index('<main');closing=updated.index('</main>',first_main)
            bridge=re.search(r'<section\b[^>]*data-teacher-bridge=',updated[first_main:closing])
            first_section=re.search(r'</section>',updated[first_main:closing])
            offset=first_main+bridge.start() if bridge else first_main+first_section.end() if first_section else closing
            updated=updated[:offset]+module+updated[offset:]
        assert updated.count('data-education-menu')==2 and updated.count('data-education-bridge=')==1,name
        write(ROOT/name,updated);return name
    if args.articles_only:
        changed.update(pages)
    else:
        with ThreadPoolExecutor(max_workers=12) as pool:
            for count,name in enumerate(pool.map(update_existing,pages),1):
                changed.add(name)
                if count%2000==0:print(json.dumps({'updatedExistingPages':count,'total':len(pages)}),flush=True)
    config=load(ROOT/'seo-descriptions.json');rendered,desc=hub(library,branches,header,footer)
    new_pages=['교육정보/index.html'];write(ROOT/new_pages[0],rendered);changed.add(new_pages[0])
    config['pages']['/교육정보']={'description':desc,'sources':[desc]}
    for a in ARTICLES:
        name=route(a).lstrip('/')+'index.html';write(ROOT/name,render_article(a,library,branches,header,footer));new_pages.append(name);changed.add(name)
        config['pages'][route(a).rstrip('/')]={'description':a['description'],'sources':[a['description']]}
    write(ROOT/'seo-descriptions.json',json.dumps(config,ensure_ascii=False,indent=2)+'\n')
    sitemap=(out/'before-sitemap.xml').read_text('utf-8')
    # Every existing page gains a main-content discovery module in this release.
    sitemap=re.sub(r'<lastmod>.*?</lastmod>',f'<lastmod>{DAY}</lastmod>',sitemap)
    additions=''.join(f'<url><loc>{DOMAIN+H(route(a))}</loc><lastmod>{DAY}</lastmod></url>\n' for a in [None,*ARTICLES])
    sitemap=sitemap.replace('</urlset>',additions+'</urlset>');write(ROOT/'sitemap.xml',sitemap)
    changed|={'assets/education-info.css','assets/education-info.js','assets/unified-ui.css','sitemap.xml'}
    manifest=load(out/'before-release-public-manifest.json')
    def hash_file(name):
        data=(ROOT/name).read_bytes();return name,digest(data),digest(data.replace(b'\r\n',b'\n')) if re.search(r'\.(html|css|js|xml|txt|json)$',name) else None
    with ThreadPoolExecutor(max_workers=12) as pool:
        for name,sha,lf in pool.map(hash_file,sorted(changed)):
            manifest['files'][name]=sha
            if lf: manifest.setdefault('textSha256',{})[name]=lf
    manifest['createdAt']=DAY;manifest['sitemapPages']=sum(n.endswith('.html') for n in manifest['files'])
    write(ROOT/'release-public-manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    result=dict(date=DAY,newArticles=30,articleImages=90,existingArticles=68,libraryArticles=98,newPages=new_pages,navigationPages=manifest['sitemapPages'],contextualPages=len(pages),sitemapPages=manifest['sitemapPages'],publicFiles=len(manifest['files']),publicChanges=sorted(changed),sourceSeed=source['seed'],deployed=False)
    write(out/'generation.json',json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    write(out/'article-data.json',json.dumps(ARTICLES,ensure_ascii=False,indent=2)+'\n')
    write(out/'library.json',json.dumps(library,ensure_ascii=False,indent=2)+'\n')
    write(out/'source-mapping.json',json.dumps(mappings,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('newPages','publicChanges')},ensure_ascii=False))

if __name__=='__main__':main()
