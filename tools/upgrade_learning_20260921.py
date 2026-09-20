"""One-release upgrade. Reads the production baseline; refuses unrelated edits.

Run with --apply, then audit_learning_20260921.py. Never use this frozen renderer
to regenerate later editorial releases. Existing destination URLs are retained.
"""
import argparse
import hashlib
import html as esc
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

from lxml import etree, html

ROOT = Path(__file__).resolve().parents[1]
BASE = 'e1be0e55ae73bfe6a37d5f659bce91677f8f10ce'
ORIGIN = 'https://xn--3e0bl59bm0ad17a.com'
DATE = '2026-09-21'
DATA = json.loads((ROOT / 'tools/learning-upgrade-20260921.json').read_text('utf-8'))
SOURCES = [
    'https://www.wawacenter.com/brand/wawacenter',
    'https://www.wawacenter.com/intro/coachingSystem',
    'https://www.wawacenter.com/intro/AISystem',
]
E = esc.escape


def baseline(path):
    return subprocess.check_output(['git', 'show', f'{BASE}:{path}'], cwd=ROOT)


def fragment(markup):
    return html.fromstring(markup)


def plain(element):
    return ' '.join(element.text_content().split())


def link(href, label):
    return f'<a class="lp-link" href="{E(href, quote=True)}">{E(label)} <span aria-hidden="true">→</span></a>'


def box(id_, kicker, title, intro, body):
    return fragment(f'<section class="lp-section" id="{id_}" aria-labelledby="{id_}-title"><p class="lp-kicker">{E(kicker)}</p><h2 id="{id_}-title">{E(title)}</h2><p class="lp-intro">{E(intro)}</p>{body}</section>')


def cards(items):
    return '<div class="lp-grid">' + ''.join(f'<article class="lp-card"><h3>{E(t)}</h3><p>{E(p)}</p>{link(h,l) if h else ""}</article>' for t,p,h,l in items) + '</div>'


def meta(doc, key, value, attr='name'):
    nodes = doc.xpath(f'//head/meta[@{attr}="{key}"]')
    assert len(nodes) <= 1, key
    node = nodes[0] if nodes else etree.SubElement(doc.find('head'), 'meta', {attr:key})
    node.set('content', value)


def update_graph(doc, url, description):
    scripts = doc.xpath('//script[@type="application/ld+json"]')
    assert len(scripts) == 1
    data = json.loads(scripts[0].text)
    graph = data.get('@graph', [{k:v for k,v in data.items() if k != '@context'}])
    page = next(n for n in graph if n.get('@type') in ('WebPage','CollectionPage'))
    page.setdefault('@id', url + '#webpage')
    page.update(url=url, name=doc.xpath('string(//title)'), description=description, dateModified=DATE, inLanguage='ko-KR')
    parts = page.get('hasPart', [])
    parts = parts if isinstance(parts,list) else [parts]
    for section in doc.xpath('//main//section[contains(concat(" ",normalize-space(@class)," ")," lp-section ")]'):
        section_url = url + '#' + section.get('id')
        node = {'@type':'WebPageElement','@id':section_url,'url':section_url,'name':plain(section.xpath('.//h2')[0]),'isPartOf':{'@id':page['@id']}}
        graph.append(node)
        parts.append({'@id':section_url})
    page['hasPart'] = parts
    for article in [n for n in graph if n.get('@type') == 'Article']:
        article.update(description=description, dateModified=DATE, headline=doc.xpath('string(//h1)'))
        article['articleSection'] = [plain(h) for h in doc.xpath('//main//h2')]
        article['citation'] = SOURCES
        # FAQ is a separate page entity, not the article's editorial sections.
        article['hasPart'] = [p for p in parts if 'faq' not in p.get('@id','')]
    faqs = []
    for detail in doc.xpath('//main//details[summary]'):
        q = plain(detail.find('summary'))
        answers = [plain(n) for n in detail if n.tag != 'summary']
        if q and answers:
            faqs.append({'@type':'Question','name':q,'acceptedAnswer':{'@type':'Answer','text':' '.join(answers)}})
    faq = next((n for n in graph if n.get('@type') == 'FAQPage'),None)
    if faq:
        faq['mainEntity'] = faqs
        faq['isPartOf'] = {'@id':page['@id']}
    breadcrumb = next((n for n in graph if n.get('@type') == 'BreadcrumbList'),None)
    if breadcrumb:
        page['breadcrumb'] = {'@id':breadcrumb['@id']}
    # Reference lists are not CreativeWork parts. Give the article list its own
    # relation while retaining its existing linked entries and identifiers.
    lists = {n.get('@id') for n in graph if n.get('@type') == 'ItemList'}
    for node in graph:
        if isinstance(node.get('hasPart'),list):
            node['hasPart'] = [p for p in node['hasPart'] if p.get('@id') not in lists]
    scripts[0].text = json.dumps({'@context':'https://schema.org','@graph':graph},ensure_ascii=False,separators=(',',':')).replace('</','<\\/')


def finish(doc, title, description):
    doc.find('head/title').text = title
    canonical = doc.xpath('//link[@rel="canonical"]/@href')[0]
    url = unquote(canonical)
    for key,value,attr in [('description',description,'name'),('og:title',title,'property'),('og:description',description,'property'),('og:url',canonical,'property'),('twitter:title',title,'name'),('twitter:description',description,'name')]:
        meta(doc,key,value,attr)
    etree.SubElement(doc.find('head'),'link',rel='stylesheet',href='/assets/learning-paths.css?v=20260921-2')
    doc.find('body').set('data-learning-release',DATE)
    main = doc.find('body/main')
    main.append(fragment(f'<p class="lp-updated">내용 업데이트 <time datetime="{DATE}">2026년 9월 21일</time></p>'))
    update_graph(doc,url,description)
    output='<!doctype html>\n'+html.tostring(doc,encoding='unicode',method='html')+'\n'
    # lxml percent-encodes href attributes but not meta content. Preserve the
    # original canonical spelling as well as its URL identity and OG parity.
    output,count=re.subn(r'(<link rel="canonical" href=")[^"]+("[^>]*>)',lambda m:m[1]+E(canonical,quote=True)+m[2],output)
    assert count==1
    return output.encode('utf-8')


def render_home(doc):
    choices = cards([
        ('공부를 시작해도 끝내기 어려워요','실행하지 못한 계획을 더 크게 잡기보다, 끝낼 과제와 막힌 이유를 남겨 보세요. 플랜·학습·생활 관리를 구분하면 필요한 도움을 찾을 수 있습니다.','/학습코칭/#daily-care','매일의 관리 방식 보기'),
        ('배운 문제도 혼자 풀면 막혀요','진단 점수와 실제 풀이를 함께 보고 연습 범위를 정합니다. 설명을 들은 문제와 혼자 해결한 문제를 나누어 다음 복습으로 연결하세요.','/학습코칭/#practice-loop','진단에서 재확인까지'),
        ('어떤 학년·과목 안내를 봐야 할까요?','학교 학년을 출발점으로 삼되, 현재 교재와 학생이 남긴 질문도 함께 살펴보세요. 학년·과목별 학습 안내에서 가까운 동네까지 이어집니다.','/과목별학원/','학년·과목별 학원 찾기'),
    ])
    doc.xpath('//nav[contains(@class,"ju-page-nav")]')[0].addnext(box('learning-paths','지금 필요한 도움부터','우리 아이의 공부 고민에서 출발하세요','와와의 진단·코칭·AI 학습 자료를 읽을 때는 학생이 지금 혼자 할 수 있는 일과 도움이 필요한 일을 나누어 보세요.',choices))
    doc.xpath('//nav[contains(@class,"ju-page-nav")]')[0].insert(0,fragment('<a href="#learning-paths">고민별 학습 안내</a>'))
    return finish(doc,'전국학원 찾기 | 학년·과목별 학원과 와와 학습코칭','지역·학년·과목별 학원을 찾고 와와의 진단·플랜 관리·AI 학습 방식을 확인하세요. 공부 고민에 맞는 학습 가이드와 상담 준비 내용을 사진·영상으로 안내합니다.')


def render_coaching(doc):
    article_list = doc.xpath('//section[@id="learning-articles"]')[0]
    article_list.getparent().remove(article_list)
    doc.xpath('//section[@id="coaching-questions"]')[0].addnext(article_list)
    article_list.set('class',article_list.get('class')+' lp-article-list')
    toc = doc.xpath('//nav[contains(@class,"ju-page-nav")]')[0]
    old = toc.xpath('a[@href="#learning-articles"]')[0]
    toc.remove(old); toc.append(old)
    toc.insert(1,fragment('<a href="#practice-loop">수업·복습 연결</a>'))
    body = '<ol class="lp-steps">'+''.join(f'<li><strong>{E(t)}</strong>{E(p)}</li>' for t,p in [
        ('진단 자료 읽기','점수와 함께 실제 답안·풀이를 놓고 어디에서 막혔는지 확인합니다.'),
        ('연습 범위 정하기','필요한 개념과 문제 유형을 골라, 끝낼 수 있는 분량으로 나눕니다.'),
        ('질문과 설명 남기기','정답뿐 아니라 풀이를 선택한 이유를 말하고 아직 모르는 부분을 질문합니다.'),
        ('혼자 다시 확인하기','도움을 받았던 문제와 새로운 문제를 구분해 보고 다음 연습에 반영합니다.'),
    ])+'</ol><div class="lp-example" style="margin-top:20px"><strong>가정에서도 해볼 수 있는 기록 예시</strong><p>오늘 혼자 한 것 / 도움을 받은 것 / 다음에 다시 볼 것을 한 줄씩 적어 보세요. AI의 완료 표시나 정답률과 학생이 남긴 설명을 함께 살피면 상담 질문을 구체화할 수 있습니다.</p></div><div class="lp-links">'+link('/학습코칭/수업후자습순서/','수업 뒤 자습으로 연결하기')+link('/학습가이드/오답관리방법/','다시 풀 문제 고르는 법')+'</div><p class="lp-note">위 과정은 학습을 살펴보는 활용 예시입니다. 센터별 고정 수업 일정이나 관리 주기를 뜻하지 않습니다.</p>'
    doc.xpath('//section[@id="four-c"]')[0].addnext(box('practice-loop','수업과 복습의 연결','AI 결과에서 끝내지 않고, 학생의 설명까지','본사 프로그램은 진단·분석과 맞춤 학습 자료를 제공합니다. 어떤 과제를 선택하고 다시 확인할지는 학생의 실제 풀이와 질문을 함께 보며 정리할 수 있습니다.',body))
    for subject,href,label in [('english','/학습코칭/영어단어문장활용/','영어 단어를 문장에 쓰는 연습'),('math','/학습가이드/오답관리방법/','수학 오답을 다음 연습으로 연결하기'),('korean','/학습코칭/국어내신근거찾기/','국어 답의 근거를 찾는 연습'),('reading','/학습코칭/초등독서습관/','책을 읽은 뒤 대화하는 방법')]:
        doc.xpath(f'//article[@id="ai-{subject}"]/div')[0].append(fragment('<div class="lp-links">'+link(href,label)+'</div>'))
    return finish(doc,'와와 학습코칭·AI 학습 | 진단부터 혼자 복습하는 과정','4C 진단·처방·지도·상담과 플랜·학습·생활 관리, AI 영어·수학·국어·독서를 살펴보세요. 실제 공부에 연결하는 예시, 소개 영상과 학습 가이드를 안내합니다.')


def render_subject(doc,key):
    item = DATA[key]
    math = '수학' in key
    subject, suffix, w, h = ('수학','math',589,418) if math else ('영어','english',375,228)
    doc.xpath('//section[contains(@class,"page-hero")]//p[@class="lead"]')[0].text = item['summary']+' 아래 지역 목록에서 동네별 안내를 찾을 수 있습니다.'
    body = cards([(t,p,None,None) for t,p in item['steps']])
    body += f'<div class="lp-media"><div class="lp-example"><strong>학습 장면 예시</strong><p>{E(item["example"])}</p></div><figure><img src="/assets/official-learning/ai-{suffix}.png" width="{w}" height="{h}" loading="lazy" decoding="async" alt="{E(item["name"])} 학습 이해를 돕는 AI {subject} 프로그램 화면 예시"><figcaption>본사 AI {subject} 프로그램 화면 예시</figcaption></figure></div>'
    body += '<div class="lp-links">'+link('/학습코칭/#ai-'+suffix,f'AI {subject}의 진단·연습 방식')+link(*item['reading'])+'</div><p class="lp-note">본사 AI 영어·수학의 소개 대상은 초1~고3입니다. 이 학년의 안내 페이지가 있다는 것과 센터의 현재 개설 여부는 다르므로 교재·시간·프로그램 이용 조건을 상담에서 확인해 주세요.</p>'
    jump = doc.xpath('//nav[@class="jk-jump"]')[0]
    jump.addnext(box('hub-coaching-summary',item['name']+' 학습코칭',item['focus'],f'{subject} 학습에서 필요한 도움을 찾는 세 가지 관찰 기준입니다. 교재와 답안, 학생이 남긴 질문을 함께 놓고 살펴보세요.',body))
    jump.insert(0,fragment('<a href="#hub-coaching-summary">학년별 코칭</a>'))
    jump.insert(1,fragment('<a href="#local-directory">동네 찾기</a>'))
    directory = doc.xpath('//section[contains(@class,"subject-directory")]')[0]
    directory.set('id','local-directory')
    directory.insert(1,fragment('<form class="lp-search" data-hub-search role="search"><label for="hub-location-query">지역·동네 이름으로 찾기</label><div class="lp-search-row"><input id="hub-location-query" name="location" type="search" placeholder="예: 서울 명일동" autocomplete="off" aria-controls="hub-search-results"><button type="reset">초기화</button></div><p role="status" aria-live="polite"></p></form>'))
    results = etree.Element('div',id='hub-search-results')
    for block in list(directory.xpath('./section[contains(@class,"region-block")]')):
        directory.remove(block);results.append(block)
    directory.append(results)
    script = etree.SubElement(doc.find('head'),'script',src='/assets/hub-search.js?v=20260921',defer='defer');script.text=''
    detail = fragment(f'<details><summary>{E(item["question"])}</summary><p>{E(item["answer"])}</p></details>')
    doc.xpath('//section[@id="hub-faq"]//div[@class="jk-faq-list"]')[0].append(detail)
    return finish(doc,item['name']+' | '+item['focus'],item['summary'])


def render_directory(doc, national=False):
    if national:
        title = '전국학원 지역 찾기 | 동네 안내와 수업 선택 기준'
        intro = '지역 목록은 가까운 동네를 찾는 출발점입니다. 그다음에는 학생의 학년과 과목, 현재 교재와 어려운 부분을 함께 살펴보세요. 본사 프로그램 안내와 실제 센터에서 가능한 수업은 나누어 확인하는 것이 좋습니다.'
        content = cards([
            ('먼저 동네와 주소','시·군·구와 동네 안내에서 방문할 곳의 주소를 확인하세요. 학생의 이동 동선과 가능한 시간을 함께 정리하면 상담 대상을 좁히기 좋습니다.','#region-list','전국 지역 목록으로'),
            ('다음으로 수업의 출발점','4C의 진단·처방·지도·상담 흐름을 참고해 무엇을 진단하고 어떻게 학습 범위를 정하는지 물어보세요. 점수뿐 아니라 학생의 풀이도 준비합니다.','/학습코칭/#four-c','4C 코칭 단계 살펴보기'),
            ('마지막으로 복습 연결','AI 프로그램을 이용한다면 온라인 활동 뒤 어떤 질문과 복습이 이어지는지 확인하세요. 과목별 구성과 대상 범위를 먼저 읽어 볼 수 있습니다.','/학습코칭/#ai-programs','과목별 AI 학습 확인'),
        ])
    else:
        title = '과목별학원 | 초등·중1 영어·수학과 학습코칭 안내'
        intro = '학년 이름은 찾기의 기준이고, 학습의 출발점은 학생이 남긴 답안과 질문입니다. 영어는 소리·단어·문장 이해를, 수학은 개념·식·계산을 나누어 살펴보고 필요한 지역 안내로 이동하세요.'
        content = cards([
            ('영어: 아는 단어를 문장으로','영역별 진단 뒤 말하기·어휘·구문·듣기 등 필요한 연습을 찾습니다. 초등과 중학교에서 활용할 수 있는 활동 구성을 구분하여 읽어보세요.','/학습코칭/#ai-english','AI 영어의 학습 구성'),
            ('수학: 틀린 이유에 맞는 연습','성취도와 오답 유형에 맞는 문제를 고르더라도 실제 풀이를 함께 보아야 합니다. 설명을 들은 뒤 혼자 풀 수 있는지까지 확인해 보세요.','/학습코칭/#ai-math','AI 수학의 오답 학습'),
            ('공통: 계획을 실행 기록으로','영어와 수학 과제를 한 줄에 묶지 말고 끝낼 분량과 미완료 이유를 각각 적습니다. 플래너는 다음 계획을 조정하는 자료로 활용할 수 있습니다.','/학습코칭/#daily-care','플랜·학습·생활 관리'),
        ])
    content += '<div class="lp-links">'+link('/학습코칭/#coaching-videos','사진과 소개 영상으로 수업 방식 살펴보기')+'</div><p class="lp-note">수업 대상·AI 프로그램·수강 조건은 센터별로 다를 수 있습니다. 동네별 안내 개수는 실제 지점 수를 의미하지 않습니다.</p>'
    jump = doc.xpath('//nav[@class="jk-jump"]')[0]
    jump.insert(0,fragment('<a href="#hub-coaching-summary">수업 선택 순서</a>'))
    jump.addnext(box('hub-coaching-summary','학원 선택과 학습코칭','찾기 → 수업 확인 → 복습까지 연결하세요',intro,content))
    desc = ('전국 13개 권역의 시·군·구와 동네별 학원 안내를 찾아보세요. 주소·이동 동선과 4C 코칭, AI 학습의 수업·복습 연결을 함께 확인할 수 있습니다.' if national else '초3·초4·초5·초6·중1 영어와 수학 학습 안내를 찾으세요. 학년별 확인할 과제, AI 학습 구성과 동네별 학원 정보를 함께 살펴볼 수 있습니다.')
    return finish(doc,title,desc)


def render_region(doc,name):
    main = doc.find('body/main')
    doc.xpath('//h1')[0].clear()
    doc.xpath('//h1')[0].text=name+' 영어·수학 학원 찾기'
    listing = main.xpath('./section[last()]')[0]
    listing.set('id','region-cities')
    anchors = listing.xpath('.//a[contains(@class,"card")][h3]')
    cities = [plain(a.find('h3')) for a in anchors]
    short = '·'.join(cities[:3])+(' 등' if len(cities)>3 else '')
    url = ORIGIN+'/전국학원/'+name+'/'
    breadcrumbs = fragment('<nav class="breadcrumb ui-wrap" aria-label="현재 위치"><a href="/">홈</a><span aria-hidden="true">/</span><a href="/전국학원/">전국학원</a><span aria-hidden="true">/</span><span aria-current="page">'+E(name)+'</span></nav>')
    main.insert(0,breadcrumbs)
    # Put usable location choices before longer program information on mobile.
    existing_check = main.xpath('./section')[1]
    main.remove(existing_check)
    listing.addnext(box('hub-coaching-summary',name+' 지역 상담 준비','가까운 동네를 찾았다면, 공부할 내용도 함께 정리하세요',f'{name} 안내는 {short}의 동네 페이지로 이어집니다. 아래 질문은 와와의 공통 학습관리 자료를 바탕으로 정리한 상담 준비 기준이며, 특정 센터의 운영 약속은 아닙니다.',cards([
        ('현재 상태를 어떤 자료로 볼까요?','최근 시험지, 학생이 직접 푼 문제와 남은 질문을 준비하세요. 진단 결과가 교재와 학습 범위를 정하는 과정에 어떻게 반영되는지 물어볼 수 있습니다.','/학습코칭/#four-c','4C 진단·처방 과정'),
        ('수업 밖 공부는 어떻게 이어갈까요?','수업 시간 외에 실행 가능한 과제량과 확인 방법을 정리해 보세요. 온라인 활동 완료와 혼자 이해한 내용은 구분하여 보는 편이 좋습니다.','/학습코칭/#practice-loop','수업에서 복습으로 연결'),
        ('학년·과목에 맞는 질문은 무엇일까요?','학교 학년만 전달하기보다 영어의 읽기·쓰기, 수학의 개념·계산 중 어디가 어려운지 적어보세요. 학년·과목 안내에서 구체적인 장면을 확인할 수 있습니다.','/과목별학원/','학년·과목별 안내'),
    ])))
    script = doc.xpath('//script[@type="application/ld+json"]')[0]
    old = json.loads(script.text)
    graph = old.get('@graph',[{k:v for k,v in old.items() if k!='@context'}])
    page = graph[0]; page.update({'@id':url+'#webpage','url':url,'mainEntity':{'@id':url+'#cities'},'breadcrumb':{'@id':url+'#breadcrumb'}})
    graph += [
        {'@type':'BreadcrumbList','@id':url+'#breadcrumb','itemListElement':[{'@type':'ListItem','position':i+1,'name':label,'item':href} for i,(label,href) in enumerate([('홈',ORIGIN+'/'),('전국학원',ORIGIN+'/전국학원/'),(name,url)])]},
        {'@type':'ItemList','@id':url+'#cities','name':name+' 시군구 안내','numberOfItems':len(anchors),'itemListElement':[{'@type':'ListItem','position':i+1,'name':cities[i],'url':urljoin(url,a.get('href'))} for i,a in enumerate(anchors)]},
    ]
    script.text=json.dumps({'@context':'https://schema.org','@graph':graph},ensure_ascii=False)
    desc=f'{name} {short}의 동네별 영어·수학 학원 안내를 찾으세요. 지역과 주소를 확인한 뒤 학습 진단·과제 관리·AI 복습을 상담에서 질문할 수 있도록 정리했습니다.'
    return finish(doc,name+' 학원 찾기 | 동네별 안내와 학습코칭 상담 준비',desc)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    outputs={}
    routes=['index.html','학습코칭/index.html','과목별학원/index.html','전국학원/index.html']
    routes += ['과목별학원/'+key+'/index.html' for key in DATA]
    regions=sorted(p for p in (ROOT/'전국학원').iterdir() if p.is_dir() and (p/'index.html').is_file())
    assert len(regions)==13
    routes += ['전국학원/'+p.name+'/index.html' for p in regions]
    for rel in routes:
        raw=baseline(rel)
        doc=html.document_fromstring(raw.decode('utf-8-sig'))
        if rel=='index.html': output=render_home(doc)
        elif rel=='학습코칭/index.html':output=render_coaching(doc)
        elif rel=='과목별학원/index.html':output=render_directory(doc)
        elif rel=='전국학원/index.html':output=render_directory(doc,True)
        elif rel.startswith('과목별학원/'):output=render_subject(doc,rel.split('/')[1])
        else:output=render_region(doc,rel.split('/')[1])
        outputs[rel]=output
    sm=baseline('sitemap.xml').decode('utf-8')
    modified={'/' if p=='index.html' else '/'+p.removesuffix('index.html') for p in routes}
    changed=[]
    def dates(m):
        block=m[0];loc=re.search(r'<loc>(.*?)</loc>',block)[1]
        if unquote(urlsplit(loc).path) not in modified:return block
        changed.append(loc)
        return re.sub(r'<lastmod>.*?</lastmod>',f'<lastmod>{DATE}</lastmod>',block) if '<lastmod>' in block else block.replace('</url>',f'<lastmod>{DATE}</lastmod></url>')
    sm=re.sub(r'<url>.*?</url>',dates,sm,flags=re.S)
    assert len(changed)==27,len(changed)
    outputs['sitemap.xml']=sm.encode('utf-8')
    lm=baseline('llms.txt').decode('utf-8')
    lm=lm.replace('## 과목별학원 신규 허브','## 과목별학원 허브')
    lm += '\n## 학습코칭 읽기\n\n- 4C 진단과 코칭: '+ORIGIN+'/학습코칭/#four-c\n- 수업과 복습 연결: '+ORIGIN+'/학습코칭/#practice-loop\n- AI 영어·수학·국어·독서: '+ORIGIN+'/학습코칭/#ai-programs\n- 본사 소개 영상: '+ORIGIN+'/학습코칭/#coaching-videos\n\n프로그램 대상 학년은 본사 소개 기준입니다. 실제 센터의 개설 과목·일정·이용 조건과 구분하여 확인하세요. 지역 안내 수는 지점 수와 다릅니다.\n'
    outputs['llms.txt']=lm.encode('utf-8')
    state_path=ROOT/'tmp/learning-upgrade-20260921-state.json'
    previous=json.loads(state_path.read_text('utf-8')) if state_path.exists() else {}
    for rel,data in outputs.items():
        current=(ROOT/rel).read_bytes()
        normalized = current.replace(b'\r\n',b'\n')
        assert normalized in (baseline(rel).replace(b'\r\n',b'\n'),data.replace(b'\r\n',b'\n')) or hashlib.sha256(normalized).hexdigest()==previous.get(rel),f'Refusing to overwrite unrelated changes: {rel}'
    if args.apply:
        for rel,data in outputs.items():(ROOT/rel).write_bytes(data)
        state_path.parent.mkdir(parents=True,exist_ok=True)
        state_path.write_text(json.dumps({rel:hashlib.sha256(data.replace(b'\r\n',b'\n')).hexdigest() for rel,data in outputs.items()},indent=2),encoding='utf-8')
    print(json.dumps({'applied':args.apply,'pages':len(routes),'sitemap_dates':len(changed),'routes':routes},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
