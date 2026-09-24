"""전국학원: actual-center directory, source-bound facts and a small shared-nav addition."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
from email.utils import format_datetime
from html import escape
from urllib.parse import quote, unquote, urlsplit
import hashlib, json, re, zipfile
from lxml import html, etree

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'tools/data/branch-directory'
REPORT=ROOT/'tools/reports/branch-directory-20260925'
ORIGIN='https://xn--3e0bl59bm0ad17a.com'
DAY='2026-09-25'
load=lambda p:json.loads(p.read_text('utf-8'))
FACTS=load(DATA/'centers.json'); CENTERS=FACTS['centers'];REGIONS=FACTS['regions']
MAP=load(DATA/'neighborhood-map.json');BASE=load(REPORT/'baseline.json')
CONFIG=load(ROOT/'seo-descriptions.json')
E=lambda s:escape(str(s),quote=True)
URL=lambda p:ORIGIN+quote(p,safe='/#-._~')
CREATED=[];PAGES=[];CONTEXT=['/','/전국학원/','/과목별학원/','/상담문의/']
HOME=(ROOT/'index.html').read_text('utf-8-sig')
VERIFICATIONS=''.join(re.findall(r'<meta\s+name="(?:naver|google)-site-verification"[^>]+>',HOME))
NAV=[('홈','/'),('지점안내','/지점안내/'),('학습코칭','/학습코칭/'),('학습가이드','/학습가이드/'),('과목별학원','/과목별학원/'),('전국학원','/전국학원/'),('상담문의','/상담문의/')]

def write(p,s):
    p.parent.mkdir(parents=True,exist_ok=True)
    raw=(s.rstrip()+'\n').encode('utf-8')
    if not p.exists() or p.read_bytes()!=raw:p.write_bytes(raw)
def save(p,v):write(p,json.dumps(v,ensure_ascii=False,indent=2))
def p(s):return '<p>'+E(s)+'</p>'
def link(path,label):return f'<a class="jd-link" href="{E(path)}">{E(label)}<span aria-hidden="true"> ↗</span></a>'
def links(items):return '<div class="jd-links">'+''.join(link(u,t) for u,t in items)+'</div>'
def section(id,title,body,kicker=''):
    return f'<section class="jd-section" id="{id}" aria-labelledby="{id}-title">'+(f'<p class="jd-kicker">{E(kicker)}</p>' if kicker else '')+f'<h2 id="{id}-title">{E(title)}</h2>{body}</section>'
def cards(items):return '<div class="jd-cards">'+''.join(f'<article class="jd-card"><h3>{E(t)}</h3>{p(s)}</article>' for t,s in items)+'</div>'
def grades(values):
    out=[]
    for prefix in ['초','중','고']:
        nums=sorted({int(v[1:]) for v in values if v.startswith(prefix)})
        if nums:out.append(prefix+str(nums[0])+('~'+prefix+str(nums[-1]) if len(nums)>1 and nums==list(range(nums[0],nums[-1]+1)) else ('·'+'·'.join(prefix+str(n) for n in nums[1:]) if len(nums)>1 else '')))
    return ' · '.join(out) or '개설 학년 확인 필요'
def subjects(c):return ' / '.join(s+' '+grades(g) for s,g in c['subjects'].items() if g)
def header(path):
    items=''.join(f'<a href="{u}"'+(' class="active" aria-current="page"' if (u=='/' and path=='/') or (u!='/' and path.startswith(u)) else '')+f'>{t}</a>' for t,u in NAV)
    return '<header class="site-header"><nav class="nav" aria-label="주요 메뉴"><a class="brand" href="/" aria-label="전국학원 홈"><span class="brand-mark" aria-hidden="true">W</span><span class="brand-label"><strong>전국학원</strong><small>영어·수학 학원 찾기</small></span></a><div class="nav-links" data-unified-nav>'+items+'</div><a class="nav-cta" href="/상담문의/">상담 신청</a></nav></header>'
def footer():
    return '<footer class="site-footer"><div class="wrap footer-inner"><div><strong>전국학원 영어수학 전문학원 찾기</strong><p>학생별 학습관리와 공부습관 코칭 안내 홈페이지</p></div><nav class="footer-links" aria-label="하단 메뉴">'+''.join(f'<a href="{u}">{t}</a>' for t,u in NAV)+'</nav></div></footer>'
def breadcrumbs(items):
    return '<nav class="ui-breadcrumb" aria-label="현재 위치"><ol>'+''.join('<li>'+(f'<a href="{E(u)}">{E(t)}</a>' if i<len(items)-1 else f'<span aria-current="page">{E(t)}</span>')+'</li>' for i,(u,t) in enumerate(items))+'</ol></nav>'
def picture(m,alt,hidden=False):
    return f'<img src="{E(m["src"])}" alt="{E(alt)}" width="{m["width"]}" height="{m["height"]}" decoding="async" loading="lazy"'+(' hidden aria-hidden="true"' if hidden else '')+'>'
def basegraph(path,title,desc,crumbs,kind='WebPage'):
    u=URL(path)
    return [{'@type':'Organization','@id':ORIGIN+'/#organization','name':'전국학원','url':ORIGIN+'/'},
      {'@type':'WebSite','@id':ORIGIN+'/#website','name':'전국학원','url':ORIGIN+'/', 'inLanguage':'ko-KR'},
      {'@type':kind,'@id':u+'#webpage','url':u,'name':title,'description':desc,'dateModified':DAY,'inLanguage':'ko-KR','isPartOf':{'@id':ORIGIN+'/#website'},'publisher':{'@id':ORIGIN+'/#organization'},'breadcrumb':{'@id':u+'#breadcrumb'}},
      {'@type':'BreadcrumbList','@id':u+'#breadcrumb','itemListElement':[{'@type':'ListItem','position':i,'name':n,'item':URL(p)} for i,(p,n) in enumerate(crumbs,1)]}]
def faq(path,items):
    graph={'@type':'FAQPage','@id':URL(path)+'#faq','mainEntity':[{'@type':'Question','name':q,'acceptedAnswer':{'@type':'Answer','text':a}} for q,a in items]}
    body=''.join(f'<details class="jd-faq"><summary>{E(q)}</summary>{p(a)}</details>' for q,a in items)
    return section('faq','방문 전에 자주 묻는 질문',body,'QUESTIONS'),graph
def render(path,title,desc,lead,crumbs,body,graph,image='/assets/title.png'):
    assert 25<=len(desc)<=80,(path,len(desc))
    graph[2]['primaryImageOfPage']={'@type':'ImageObject','url':URL(image)}
    doc=html.fragment_fromstring(body,create_parent='div')
    graph[2]['hasPart']=[{'@type':'WebPageElement','@id':URL(path)+'#'+n.get('id'),'name':n.xpath('string(.//h2)')} for n in doc.xpath('.//section[@id]') if n.xpath('.//h2')]
    canonical=URL(path)
    document=f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title><meta name="description" content="{E(desc)}"><meta name="robots" content="index,follow">{VERIFICATIONS}
<link rel="canonical" href="{canonical}"><link rel="icon" href="/assets/favicon.png"><meta name="theme-color" content="#173b32">
<meta property="og:type" content="website"><meta property="og:locale" content="ko_KR"><meta property="og:site_name" content="전국학원"><meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}"><meta property="og:url" content="{canonical}"><meta property="og:image" content="{URL(image)}"><meta property="og:image:alt" content="{E(title.split(' | ')[0])}">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{E(title)}"><meta name="twitter:description" content="{E(desc)}"><meta name="twitter:image" content="{URL(image)}">
<link rel="alternate" type="application/rss+xml" title="전국학원 지점안내 업데이트" href="{ORIGIN}/branch-updates.xml">
<link rel="stylesheet" href="/assets/site.css"><link rel="stylesheet" href="/assets/unified-ui.css?v=20260925"><link rel="stylesheet" href="/assets/branch-directory.css?v=20260925"><script defer src="/assets/unified-ui.js?v=20260914"></script><script defer src="/assets/branch-directory.js?v=20260925"></script>
<script type="application/ld+json">{json.dumps({'@context':'https://schema.org','@graph':graph},ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')}</script>
</head><body class="unified-ui jd-page"><a class="skip-link" href="#main">본문 바로가기</a>{header(path)}<main id="main"><div class="jd-wrap"><section class="jd-hero">{breadcrumbs(crumbs)}<p class="jd-kicker">전국학원 · 지점안내</p><h1>{E(title.split(' | ')[0])}</h1><p class="jd-lead">{E(desc)}</p><div class="jd-answer">{E(lead)}</div></section>{body}<p class="jd-updated">자료 대조·안내 검토 <time datetime="{DAY}">{DAY}</time> · 수업 일정과 최종 비용은 방문 전 확인해 주세요.</p></div></main>{footer()}</body></html>'''
    write(ROOT/path.strip('/')/'index.html',document)
    CONFIG['pages'][path.rstrip('/')]={'description':desc,'sources':[desc]}
    CREATED.append(path);PAGES.append({'path':path,'title':title,'description':desc})

def fee_content(c):
    exact=c['feeMode']=='center-specific'
    label='지점별 교육비 안내' if exact else '지역 공통 교육비 참고'
    body=f'<p class="jd-badge">{label}</p>'+p('지점 자료에 기재된 금액입니다. 수강 과목과 횟수·시간이 동일한지 확인한 뒤 비교하세요.' if exact else '이 표는 지역 공통 참고 금액으로, 이 지점의 확정 교습비를 뜻하지 않습니다. 과목과 수업 시간에 따른 최종 금액은 지점 안내 자료로 확인하세요.')
    for i,t in enumerate(c['fees']):
        heads=t['headers'];rows=t['rows']
        body+='<div class="jd-table-wrap" role="region" tabindex="0" aria-label="'+E(t['heading'])+'"><table><caption>'+E(t['heading'])+'</caption><thead><tr>'+''.join('<th scope="col">'+E(x)+'</th>' for x in heads)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(('<th scope="row">'+E(x)+'</th>' if k==0 else '<td>'+E(x)+'</td>') for k,x in enumerate(r))+'</tr>' for r in rows)+'</tbody></table></div>'
        body+='<div class="jd-fee-cards" role="group" aria-label="'+E(t['heading'])+'">'+p(t['heading'])+''.join('<dl>'+''.join('<div><dt>'+E(heads[k])+'</dt><dd>'+E(value)+'</dd></div>' for k,value in enumerate(row))+'</dl>' for row in rows)+'</div>'
    body+=''.join(p(n.replace('기존 공통 안내 금액','지역 공통 참고 금액')) for n in c['feeNotes'])
    if c['feeLink']:body+=f'<a class="jd-link" href="{E(c["feeLink"])}" target="_blank" rel="noopener">{E(c["routeName"])} 교습비 안내 자료 확인 ↗</a>'
    return body

def existing_area_links(c):
    found=[]
    for m in MAP:
        if m['branch']!=c['key']:continue
        compact=re.sub(r'\s','',m['area'])
        # Use only a real, unambiguous legacy neighborhood hub under its observed district.
        for rel in BASE['pages']:
            parts=Path(rel).parts
            if len(parts)==5 and parts[0]=='전국학원' and norm(parts[3])==norm(compact) and norm(parts[2])==norm(m['district']):
                found.append(('/'+Path(rel).parent.as_posix()+'/',m['area']+' 학년별 학습 안내'))
    return list(dict.fromkeys(found))[:3]
def norm(s):return re.sub(r'\s','',s)

def branch_pages():
    for c in CENTERS:
        n=c['routeName'];path=c['path'];location=' '.join(x for x in [c['region'],c['district']] if x)
        actual='·'.join(s for s,g in c['subjects'].items() if g)
        title=f'{n} 지점안내 | {location} 과목·학년·교육비'
        desc=f'{location} {n}의 {actual} 수강 학년과 주소·교육비를 정리했습니다. 방문 전 수업 조건을 확인하세요.' if actual else f'{location} {n}의 등록 정보·주소·교육비와 상담 준비를 안내합니다. 개설 과목과 학년은 지점에 확인하세요.'
        if len(desc)>80:desc=f'{location} {n}의 과목별 수강 학년·교육비·주소와 수업 상담에 필요한 정보를 안내합니다.'
        areas='·'.join(c['neighborhoods'][:3]) or location
        lead=f'{areas}에서 {c["brand"]} {n} 방문을 준비한다면, 학생의 학년과 희망 과목을 먼저 대조해 보세요. 실제 방문지는 {c["address"]}이며, 같은 학년이라도 과목별 수강 범위는 다를 수 있습니다.'
        crumbs=[('/','홈'),('/지점안내/','지점안내'),(f'/지점안내/{c["region"]}/',c['region']),(path,n)]
        jumps=[('#center-facts','주소·등록 정보'),('#courses','수강 학년'),('#fees','교육비'),('#learning-materials','사진·지도'),('#faq','자주 묻는 질문')]
        body='<nav class="jd-toc" aria-label="페이지 목차">'+''.join(link(u,t) for u,t in jumps)+'</nav>'
        photo=c['photos'][0]
        media=picture(c['representative'],'',True)+'<div class="jd-media"><figure>'+picture(photo,n+' 학습 공간' if photo['mode']=='center' else '학습 공간 안내 이미지')+'<figcaption>수업 공간 살펴보기</figcaption></figure><figure>'+picture(c['map'],n+' 위치 안내 지도')+'<figcaption>'+E(n+' · '+c['address'])+'</figcaption></figure></div>'+p('지도 이미지와 도로명주소를 함께 확인하고, 방문 전 아래 지도 링크에서 위치를 다시 확인하세요.')
        body+=section('learning-materials','수업 공간과 방문 위치',media,'PHOTO & MAP')
        facts=[('등록 학원명',c['registeredName']),('브랜드',c['brand']),('주소',c['address']),('학원 등록 정보',c['registrationNumber']),('방문 시간 참고',c['openingReference']),('주말 수업 안내',c['weekend'])]
        body+=section('center-facts',n+' 기본정보','<dl class="jd-facts">'+''.join(f'<div><dt>{E(k)}</dt><dd>{E(v or "센터 확인 필요")}</dd></div>' for k,v in facts)+'</dl>'+p('방문 시간은 상담 예약 확정이나 수업 시작·종료 시각을 뜻하지 않습니다. 희망 방문일을 먼저 알려 주세요.')+f'<a class="jd-link" href="{E(c["mapLink"])}" target="_blank" rel="noopener">네이버 지도에서 {E(n)} 위치 보기 ↗</a>','CENTER INFORMATION')
        coursebody='<div class="jd-course-list">'+''.join('<article><h3>'+E(s)+'</h3>'+p(grades(g))+''.join('<p class="jd-note">'+E(note)+'</p>' for note in c['subjectNotes'].get(s,[]))+'</article>' for s,g in c['subjects'].items())+'</div>'
        if not c['subjects']:coursebody=p('제공된 자료에 과목별 개설 학년이 없어 현재 수강 가능 범위를 단정하지 않습니다. 희망 학년·과목을 알려 확인해 주세요.')
        coursebody+=''.join('<p class="jd-note">'+E(note)+'</p>' for note in c['courseNotes'])+p('아래 학습 안내에 나온 과목이나 학년이 모두 개설된다는 의미는 아닙니다. 수강 학년 표에 없는 과정과 선택 과목은 별도로 확인해 주세요.')
        body+=section('courses',n+' 과목별 수강 학년',coursebody,'SUBJECTS & GRADES')
        available_stages={v[0] for g in c['subjects'].values() for v in g}
        stages=[]
        if '초' in available_stages:stages.append(('초등 상담 준비','지금 사용하는 교재에서 혼자 설명할 수 있는 부분과 도움을 받아야 하는 부분을 표시해 보세요. 숙제를 마치는 시간도 적어 가면 연습 분량을 상의하기 좋습니다.'))
        if '중' in available_stages:stages.append(('중등 상담 준비','학교 시험 범위와 최근 답안을 준비하세요. 개념 이해, 조건 읽기, 풀이 기록 중 어디에서 오답이 생겼는지 나누어 설명하면 보완할 순서를 정하기 쉽습니다.'))
        if '고' in available_stages:stages.append(('고등 상담 준비','현재 선택 과목과 교재, 시험 일정을 먼저 정리하세요. 내신과 다음 진도 중 무엇을 우선할지, 필요한 과정이 실제로 개설되어 있는지 함께 확인합니다.'))
        if stages:body+=section('learning-preparation','현재 학년에 맞춰 준비할 자료',cards(stages)+links([('/학습코칭/','진단·수업·복습 흐름 알아보기'),('/학습가이드/','과목별 공부 방법 읽기')]),'LEARNING PREPARATION')
        if any(c['schools'].values()):
            body+=section('schools','학교 자료와 함께 상담 준비하기',cards([(k,' · '.join(v)) for k,v in c['schools'].items() if v])+p('위 학교는 제공 자료에 포함된 상담 참고 학교입니다. 해당 학교와의 제휴, 학생 재원, 통학 지원 또는 시험 성과를 뜻하지 않습니다. 실제 재학 학교의 교재·평가 범위를 준비해 주세요.'),'SCHOOL CHECK')
        body+=section('fees',n+' 교육비와 수강 조건',fee_content(c),'TUITION')
        if len(c['photos'])>1:
            body+=section('learning-space','학습 공간 더 살펴보기','<div class="jd-gallery">'+''.join('<figure>'+picture(m,n+f' 학습 공간 {i}' if m['mode']=='center' else f'학습 공간 안내 {i}')+f'<figcaption>학습 공간 {i}</figcaption></figure>' for i,m in enumerate(c['photos'][1:],2))+'</div>','LEARNING SPACE')
        body+=section('consultation','상담 후에는 이 내용을 비교하세요',cards([('수업에 어떻게 참여하나요?','학생이 질문하거나 풀이를 설명하는 시점, 개인별 교재와 과제 조정 기준을 물어보세요. 반 이름이나 진도만으로 수업 방식을 판단하지 않는 것이 좋습니다.'),('복습 결과는 어떻게 확인하나요?','틀렸던 문제를 언제 다시 풀고, 어떤 기록을 보호자와 공유하는지 확인하세요. 확인 주기와 실제 전달 방식을 구체적으로 질문하면 비교하기 쉽습니다.'),('등록 조건에 무엇이 포함되나요?','주간 수업 횟수와 시간, 교재비·프로그램 비용, 시작 가능한 일정을 확인하세요. 방문 시간 안내와 실제 수업 시간표는 별개입니다.')])+p(f'{n}의 주소와 희망 과목을 확인한 뒤 공통 상담 창구로 문의할 수 있습니다. 공통 상담 번호는 지점 직통번호로 표시하지 않습니다.')+links([('/상담문의/','공통 상담 안내')]),'CONSULTATION')
        faqs=[(f'{n}에서 어떤 과목과 학년을 확인할 수 있나요?',('자료상 수강 범위는 '+subjects(c)+'입니다. 표에 없는 과정과 실제 시간표는 지점에 문의해 주세요.') if actual else '과목별 개설 학년이 자료에 명시되어 있지 않아 지점 확인이 필요합니다. 희망 과목과 학생의 학년을 먼저 알려 주세요.'),
              (f'{n} 교육비는 확정 금액인가요?',('지점 안내 자료에 기재된 금액을 표시했습니다. 희망 과목, 수업 횟수·시간, 별도 비용을 대조한 뒤 최종 조건을 확인하세요.' if c['feeMode']=='center-specific' else '지역 공통 참고표입니다. 해당 지점의 확정 금액이 아니므로 교습비 안내 자료와 상담을 통해 실제 과목·시간별 금액을 확인하세요.')),
              (f'{n} 방문 전 무엇을 확인해야 하나요?',f'주소는 {c["address"]}입니다. 학생의 학년과 희망 과목, 방문일을 먼저 알려 주세요. 최근 교재나 답안이 있으면 필요한 학습 도움을 설명하기 좋습니다.')]
        faqbody,faqgraph=faq(path,faqs);body+=faqbody
        nearby=sorted([o for o in CENTERS if o['region']==c['region'] and o['district']==c['district'] and o['key']!=c['key']],key=lambda x:x['routeName'])[:2]
        related=[(f'/지점안내/{c["region"]}/',c['region']+' 지점 목록'),*[(o['path'],o['routeName']+' 수강 조건') for o in nearby],*existing_area_links(c)]
        body+=section('related-pages','지역·학습 안내 이어서 보기',links(related)+p('동네 학습 글은 공부 방법을 살펴보는 자료입니다. 실제 수강 조건은 방문할 지점의 과목별 학년과 교육비 안내를 기준으로 확인하세요.'),'RELATED GUIDES')
        graph=basegraph(path,title,desc,crumbs);identity=URL(path)+'#center';graph[2]['mainEntity']={'@id':identity};graph[2]['about']={'@id':identity}
        center_node={'@type':['EducationalOrganization','LocalBusiness'],'@id':identity,'name':c['registeredName'],'alternateName':c['brand']+' '+n,'url':URL(path),'address':{'@type':'PostalAddress','streetAddress':c['address'],'addressRegion':c['region'],'addressLocality':c['district'],'addressCountry':'KR'}}
        real=[URL(m['src']) for m in c['photos'] if m['mode']=='center']
        if real:center_node['image']=real
        graph.append(center_node)
        for s,g in c['subjects'].items():
            if g:graph.append({'@type':'Service','@id':URL(path)+'#service-'+quote(s),'name':n+' '+s+' 수강 안내','description':'자료상 수강 학년: '+grades(g),'serviceType':s+' 학습','provider':{'@id':identity},'areaServed':{'@type':'AdministrativeArea','name':location}})
        graph.append(faqgraph);render(path,title,desc,lead,crumbs,body,graph,photo['src'])

def filters(region):
    fields='<label>지점·동네·주소 검색<input id="branch-search" type="search" placeholder="예: 명일점, 명일동, 강동구" autocomplete="off"></label>'
    if not region:fields+='<label>지역<select id="branch-region"><option value="">전체 지역</option>'+''.join(f'<option>{r}</option>' for r in REGIONS)+'</select></label>'
    fields+='<label>과목<select id="branch-subject"><option value="">전체 과목</option>'+''.join(f'<option>{s}</option>' for s in ['국어','영어','수학','과학','사회'])+'</select></label><label>학년<select id="branch-grade"><option value="">전체 학년</option>'+''.join(f'<option>{a}{i}</option>' for a,count in [('초',6),('중',3),('고',3)] for i in range(1,count+1))+'</select></label>'
    return '<form class="jd-filter" data-branch-filter role="search" aria-label="지점 찾기">'+fields+'<button class="jd-reset" type="reset">초기화</button></form><p class="jd-result" role="status" aria-live="polite" data-branch-count></p><p class="jd-empty" data-branch-empty hidden>조건에 맞는 지점이 없습니다. 과목·학년 조건을 줄이거나 다른 동네 이름으로 찾아보세요.</p><noscript><p>검색 기능은 JavaScript가 필요합니다. 아래 지역별 목록으로 모든 지점에 이동할 수 있습니다.</p></noscript>'
def branch_card(c):
    available={s:g for s,g in c['subjects'].items() if g}
    return '<article class="jd-branch-card" data-branch-card data-region="'+E(c['region'])+'" data-search="'+E(' '.join([c['routeName'],c['district'],c['address'],c['brand'],*c['neighborhoods']]))+'" data-courses="'+E(json.dumps(available,ensure_ascii=False))+'"><p class="jd-kicker">'+E(c['district'] or c['region'])+'</p><h3><a href="'+E(c['path'])+'">'+E(c['routeName'])+'<span aria-hidden="true"> ↗</span></a></h3><p class="jd-brand">'+E(c['brand'])+'</p>'+p(c['address'])+'<p class="jd-card-courses">'+E(subjects(c) or '개설 과목·학년은 센터 확인 필요')+'</p></article>'
def directory_pages():
    for region in ['']+REGIONS:
        path='/지점안내/'+(region+'/' if region else '');subset=[c for c in CENTERS if not region or c['region']==region];n=len(subset)
        name=region or '전국';title=f'{name} 지점안내 | 학년·과목·교육비로 찾는 실제 지점'
        desc=f'{name} {n}개 지점의 주소·수강 학년·과목과 교육비 안내를 확인하세요. 지점·동네 검색으로 방문할 곳을 찾을 수 있습니다.'
        districts=list(dict.fromkeys(c['district'] for c in subset if c['district']))
        areas='·'.join(districts[:4])
        lead=(f'{region}의 '+(areas+' 등 ' if areas else '')+f'{n}개 지점을 모았습니다. 학습 주제로 읽는 전국학원 안내와 달리, 이 목록은 등록 학원과 방문 주소를 기준으로 제공합니다.' if region else f'{len(REGIONS)}개 지역, {n}개 실제 지점의 방문 정보를 모았습니다. 먼저 희망 과목과 학생의 학년으로 범위를 좁히고, 지점 페이지에서 주소·교육비·수강 조건을 확인하세요.')
        crumbs=[('/','홈'),('/지점안내/','지점안내')]+([(path,region)] if region else [])
        body='<nav class="jd-toc" aria-label="지점 찾기 목차">'+link('#find-branch','지점 검색')+link('#select-guide','선택 전 확인 사항')+(link('/지점안내/','전체 지역 보기') if region else link('#region-pages','지역별 페이지'))+'</nav>'
        if not region:
            body+=section('region-pages','어느 지역에서 찾으시나요?','<div class="jd-regions">'+''.join(f'<a href="/지점안내/{r}/"><strong>{r}</strong><span>{sum(c["region"]==r for c in CENTERS)}개 지점 ↗</span></a>' for r in REGIONS)+'</div>','REGIONS')
        listing=filters(region)
        for r in ([region] if region else REGIONS):
            cs=sorted([c for c in subset if c['region']==r],key=lambda c:c['routeName'])
            listing+=f'<details class="jd-region-group" data-region-group="{r}"'+(' open' if region or r==REGIONS[0] else '')+f'><summary>{r} <span>{len(cs)}개 지점</span></summary><div class="jd-branch-grid">'+''.join(branch_card(c) for c in cs)+'</div></details>'
        body+=section('find-branch','수강 조건으로 지점 찾기',p('과목과 학년을 함께 선택하면 그 과목에 해당 학년이 기재된 지점만 표시됩니다. 검색 결과는 개설 자료 기준이며 현재 시간표나 모집 여부와는 다를 수 있습니다.')+listing,'FIND YOUR CENTER')
        body+=section('select-guide','주소 다음으로 확인할 세 가지',cards([('01 · 과목별 학년','한 지점이라도 국어·영어·수학의 수강 가능 학년이 다를 수 있습니다. 학생의 현재 학년과 원하는 과목을 함께 확인하세요.'),('02 · 비용의 기준','지점별 교육비 자료와 지역 공통 참고 금액을 구분했습니다. 수업 시간·횟수, 별도 교재비가 같은 조건인지 비교하세요.'),('03 · 방문과 수업 일정','방문 시간 안내가 실제 수업 시간표를 뜻하지는 않습니다. 등하교 일정과 가능한 요일을 정해 문의하면 상담을 준비하기 쉽습니다.')]),'BEFORE YOU VISIT')
        questions=[('동네별 학원 안내와 지점안내는 어떻게 다른가요?','동네별 학원 안내는 학년·과목에 맞는 학습 방법을 읽는 페이지입니다. 지점안내는 실제 등록 학원명과 주소, 과목별 수강 학년, 교육비를 확인하는 페이지입니다.'),
                    (f'{name} 목록의 모든 지점에서 같은 과목을 배울 수 있나요?','지점마다 과목별 수강 학년이 다릅니다. 검색에서 희망 과목과 학년을 함께 선택한 뒤 지점의 별도 수강 조건을 확인해 주세요.'),
                    ('교육비와 시간표는 어떻게 확인하나요?','지점 페이지의 교육비 표와 교습비 자료 링크를 확인하세요. 지역 공통 참고표는 해당 지점의 확정 금액이 아닙니다. 실제 시간표와 최종 비용은 방문 전 확인해야 합니다.')]
        fs,fg=faq(path,questions);body+=fs
        body+=section('related-pages','수업 방식과 공부 방법도 함께 살펴보세요',links([('/학습코칭/','학습코칭의 진단·복습 방식'),('/학습가이드/','공부 방법과 준비 자료'),('/전국학원/','동네별 학년·과목 안내'),('/상담문의/','공통 상담 안내')]),'NEXT STEP')
        graph=basegraph(path,title,desc,crumbs,'CollectionPage');iid=URL(path)+'#branches';graph[2]['mainEntity']={'@id':iid}
        graph.extend([{'@type':'ItemList','@id':iid,'name':name+' 실제 지점 목록','numberOfItems':n,'itemListElement':[{'@type':'ListItem','position':i,'name':c['routeName'],'url':URL(c['path'])} for i,c in enumerate(subset,1)]},fg])
        render(path,title,desc,lead,crumbs,body,graph)

def enhance_navigation():
    for rel,entry in BASE['pages'].items():
        file=ROOT/rel;raw=file.read_text('utf-8-sig');path=unquote(urlsplit(entry['canonical']).path)
        # Change only the shared menus, not existing manuscripts or metadata.
        for pattern in [r'(<div\b[^>]*class="nav-links"[^>]*>)(.*?)(</div>)',r'(<nav\b[^>]*class="footer-links"[^>]*>)(.*?)(</nav>)']:
            def add(m):
                if re.search(r'>지점안내</a>',m[2]):return m[0]
                items=m[2];pos=items.find('</a>')+4
                return m[1]+items[:pos]+'<a href="/지점안내/">지점안내</a>'+items[pos:]+m[3]
            raw,count=re.subn(pattern,add,raw,count=1,flags=re.S)
            assert count==1,('nav missing',rel)
        raw=re.sub(r'/assets/unified-ui.css\?v=[^"\s]+','/assets/unified-ui.css?v=20260925',raw)
        if rel in ['index.html','전국학원/index.html','과목별학원/index.html','상담문의/index.html'] and 'id="branch-directory-entry"' not in raw:
            label='실제 지점의 주소·수강 조건을 확인하세요'
            block='<section class="ui-section wrap" id="branch-directory-entry"><h2>'+label+'</h2><p>학습 방법을 살펴봤다면 방문할 지점의 정보를 비교해 보세요. 과목별 수강 학년과 교육비, 사진·지도를 지점별로 확인할 수 있습니다.</p><div class="ui-actions"><a class="ui-btn ui-primary" href="/지점안내/">전국 지점안내</a><a class="ui-btn" href="/지점안내/서울/">서울 지점</a><a class="ui-btn" href="/지점안내/경기/">경기 지점</a></div></section>'
            raw=raw.replace('</main>',block+'</main>',1)
        write(file,raw)

def discovery():
    with zipfile.ZipFile(BASE['backup']) as z:sitemap=etree.fromstring(z.read('sitemap.xml'))
    ns='http://www.sitemaps.org/schemas/sitemap/0.9';old={unquote(n.findtext('{'+ns+'}loc')):n for n in sitemap}
    for path in CONTEXT:
        node=old.get(ORIGIN+path)
        if node is not None:
            lm=node.find('{'+ns+'}lastmod')
            if lm is None:lm=etree.SubElement(node,'{'+ns+'}lastmod')
            lm.text=DAY
    for path in CREATED:
        assert ORIGIN+path not in old,path
        node=etree.SubElement(sitemap,'{'+ns+'}url');etree.SubElement(node,'{'+ns+'}loc').text=URL(path);etree.SubElement(node,'{'+ns+'}lastmod').text=DAY
    write(ROOT/'sitemap.xml',etree.tostring(sitemap,encoding='unicode',pretty_print=True))
    feed=etree.Element('rss',version='2.0');channel=etree.SubElement(feed,'channel')
    now=format_datetime(datetime.now(timezone.utc))
    for key,val in [('title','전국학원 지점안내 업데이트'),('link',URL('/지점안내/')),('description','최근 추가한 지역·지점의 주소, 수강 학년과 교육비 안내'),('language','ko'),('lastBuildDate',now)]:etree.SubElement(channel,key).text=val
    for item in PAGES[:50]:
        n=etree.SubElement(channel,'item')
        for key,val in [('title',item['title']),('link',URL(item['path'])),('guid',URL(item['path'])),('description',item['description']),('pubDate',now)]:etree.SubElement(n,key).text=val
    write(ROOT/'branch-updates.xml',etree.tostring(feed,encoding='unicode',pretty_print=True))
    llms=(ROOT/'llms.txt').read_text('utf-8-sig')
    if '## 실제 지점안내' not in llms:
        llms+='\n## 실제 지점안내\n\n'+f'- 지점 찾기: {ORIGIN}/지점안내/\n'+''.join(f'- {r} 지점: {ORIGIN}/지점안내/{r}/\n' for r in REGIONS)+'\n193개 실제 지점을 등록 학원명·주소 기준으로 구분합니다. 371개 동네 자료는 실제 지점 수가 아닙니다. 과목별 수강 학년, 주소, 등록 정보와 교육비를 확인할 수 있습니다. 지역 공통 교육비 참고표는 개별 지점의 확정 교습비가 아닙니다.\n'
    write(ROOT/'llms.txt',llms)
    save(ROOT/'seo-descriptions.json',CONFIG)

def main():
    directory_pages();branch_pages();enhance_navigation();discovery()
    save(REPORT/'build.json',{'created':CREATED,'newPages':len(CREATED),'centerPages':len(CENTERS),'regionPages':len(REGIONS),'existingMenuPages':len(BASE['pages']),'existingContentAdditions':CONTEXT,'pages':PAGES})
    print(json.dumps({'newPages':len(CREATED),'centerPages':len(CENTERS),'regionPages':len(REGIONS),'existingMenuPages':len(BASE['pages'])},ensure_ascii=False))
if __name__=='__main__':main()
