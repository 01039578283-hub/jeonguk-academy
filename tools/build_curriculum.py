"""Build a grade/subject reference from the supplied workbook catalog.

The catalog describes study examples, not confirmed branch offerings. Existing
pages receive only an additional contextual link; their factual content stays
byte-for-byte intact after removing that addition.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from html import escape
from urllib.parse import quote, unquote, urlsplit
import argparse, hashlib, json, re, zipfile
from lxml import html
from build_education_info import contextual as education_links

ROOT=Path(__file__).resolve().parents[1]
DAY='2026-10-03'
DOMAIN='https://xn--3e0bl59bm0ad17a.com'
BASE='/학습커리큘럼/'
STAGES={'초':'초등','중':'중등','고':'고등'}
SCHOOL={'초':'초등학생','중':'중학생','고':'고등학생'}
SUBJECTS=['국어','영어','수학','사회','과학','역사']
LEVELS=['기초','표준','심화']
START='<!-- curriculum-link:start -->'
END='<!-- curriculum-link:end -->'
STYLE='<link rel="stylesheet" href="/assets/curriculum.css?v=20261003">'
E=lambda s:escape(str(s),quote=True)
H=lambda s:quote(s,safe='/#-._~?=&')
J=lambda d:json.dumps(d,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
sha=lambda b:hashlib.sha256(b).hexdigest()

def load(p):return json.loads(p.read_text('utf-8-sig'))
def write(p,content):
    data=content.encode('utf-8') if isinstance(content,str) else content
    p.parent.mkdir(parents=True,exist_ok=True)
    if not p.exists() or p.read_bytes()!=data:p.write_bytes(data)
def long_grade(g):return {'초':'초등학교','중':'중학교','고':'고등학교'}[g[0]]+' '+g[1:]+'학년'
def grade_path(g):return BASE+g+'/'
def subject_path(g,s):return grade_path(g)+s+'/'
def display_subject(g,s):
    if g in ('초1','초2'):
        return {'영어':'영어 선택 활동','사회':'통합교과 · 사회 연계','과학':'통합교과 · 과학 연계'}.get(s,s)
    return s
def sentence(s):return s if s.endswith(('.', '?', '!')) else s+'.'
def button(path,label,secondary=False):return f'<a class="ci-button{" ci-secondary" if secondary else ""}" href="{H(path)}">{E(label)}</a>'
def short_note(g):
    if g in ('초1','초2'):return '국어·수학·통합교과를 구분해 보세요. 영어는 선택 활동이며, 사회·과학 연계 내용은 슬기로운 생활 안에서 살펴보는 예시입니다.'
    if g.startswith('중'):return '사회·역사의 이수 학년과 학기는 학교마다 다릅니다. 학교 시간표와 편제표를 먼저 확인하세요.'
    if g.startswith('고'):return '선택과목은 학교의 개설 학년·학기와 학생의 실제 이수 계획에 따라 달라집니다. 학교 수업 범위와 수능 응시 범위를 각각 확인하세요.'
    return '교육과정의 학년군 범위를 학교 교과서의 학년·학기·진도에 맞춰 살펴보세요.'

PRACTICE={
 '국어':('답을 적기 전에 글이나 작품에서 근거가 되는 부분을 표시해 보세요.','같은 내용을 자기 말로 설명하고, 처음 쓴 문장과 고친 문장을 비교해 보세요.','어떤 부분을 보고 그렇게 생각했니?','글을 고칠 때 무엇을 바꿨고, 왜 바꿨니?'),
 '영어':('단어의 뜻만 확인한 뒤 끝내지 말고, 실제 문장 속에서 듣고 읽어 보세요.','교과서 표현의 사람·장소·상황을 바꾸어 말하거나 짧게 써 보세요.','이 문장이나 대화에서 누가 무엇을 했니?','새로운 상황에도 같은 표현을 써 볼 수 있니?'),
 '수학':('문제의 조건을 식·그림·표 중 알맞은 표현으로 옮겨 보세요.','정답과 함께 첫 접근, 계산의 이유, 단위나 조건을 확인한 과정을 남겨 보세요.','이 식이나 그림은 문제의 어떤 조건을 나타내니?','답이 맞는지 다른 방법으로 확인할 수 있니?'),
 '사회':('지도·사진·통계의 제목과 기준을 먼저 확인하고, 자료에서 직접 읽은 정보를 표시해 보세요.','자료에서 읽은 사실과 그 사실을 해석한 의견을 나누어 설명해 보세요.','이 자료에서 직접 확인할 수 있는 것은 무엇이니?','그 설명을 뒷받침하는 자료는 어느 부분이니?'),
 '과학':('관찰한 사실, 예상한 내용, 결론을 나누어 기록해 보세요.','학교에서 안내한 안전 기준 안에서 변인·단위·측정 결과와 결론의 관계를 확인해 보세요.','실제로 관찰하거나 측정한 것은 무엇이니?','자료로 설명할 수 있는 범위는 어디까지일까?'),
 '역사':('사건의 시대와 장소를 확인하고, 배경·전개·결과를 자료와 연결해 보세요.','사료의 작성 시기와 관점을 살펴보고, 사건의 순서와 변화의 이유를 나누어 설명해 보세요.','이 사료의 어떤 단서로 시대를 판단했니?','이 사건 전후에 무엇이 달라졌고, 자료에서는 어떻게 확인되니?')}
GUIDE={
 '국어':('/학습가이드/국어독해학습법/','/교육정보/중학생공부순서/'),
 '영어':('/교육정보/영어어법독해검토/','/교육정보/과목별수준진단/'),
 '수학':('/교육정보/수학응용문제분석/','/교육정보/과목별수준진단/'),
 '사회':('/교육정보/암기과목단기대비/','/교육정보/과목연결학습/'),
 '과학':('/교육정보/과학탐구실험기록/','/교육정보/과목연결학습/'),
 '역사':('/교육정보/암기과목단기대비/','/교육정보/과목연결학습/')}

class Curriculum:
    def __init__(self,catalog):
        self.catalog=catalog
        self.sheets={s['name']:s['records'] for s in catalog['sheets']}
        self.overview={r['values']['학년']:r for r in self.sheets['학년별개요']}
        self.subjects=[]
        for name in ['초등과목','중등과목','고등과목']:
            for record in self.sheets[name]:
                r=record['values'];g=r['학년'];s=r['과목']
                for k in ['2026 적용','주요 학습 중점(편집)','권장 순서(예시)','확인 과제(예시)','학교별 조정','홈페이지 참고 문구']:assert r[k]
                self.subjects.append(dict(grade=g,subject=s,row=record['row'],sheet=name,values=r,path=subject_path(g,s)))
        assert len(self.subjects)==66 and len(self.overview)==12
        self.by_key={(a['grade'],a['subject']):a for a in self.subjects}
        self.levels={(r['values']['학교급'],r['values']['과목'],r['values']['반 수준'].removesuffix('반')):r for r in self.sheets['반별운영']}
        assert len(self.levels)==45 and len(self.sheets['고등선택과목'])==29
        self.pages={}
        self.original=(ROOT/'학습가이드/index.html').read_text('utf-8')
        self.header=re.search(r'<header class="site-header">[\s\S]*?</header>',self.original)[0]
        self.header=re.sub(r'\sclass="active"\saria-current="page"','',self.header)
        self.header=self.header.replace('<a href="/학습가이드/"','<a href="/학습가이드/" class="active" aria-current="page"')
        self.footer=re.search(r'<footer class="site-footer">[\s\S]*?</body>',self.original)[0].removesuffix('</body>')
        # Reuse the existing consultation-button styles on new curriculum pages.
        for original, styled in [('wawa-fixed-fab-call', 'wawa-fab-item fab-call'), ('wawa-fixed-fab-sms', 'wawa-fab-item fab-sms'), ('wawa-fixed-fab-form', 'wawa-fab-item fab-consult'), ('wawa-fixed-fab-icon', 'fab-icon')]:
            self.footer=self.footer.replace(original, original+' '+styled)
        self.related={}
        for subject,paths in GUIDE.items():
            self.related[subject]=[]
            for path in paths:
                p=ROOT/path.lstrip('/')/'index.html'
                if not p.exists():
                    path='/교육정보/과목별수준진단/';p=ROOT/path.lstrip('/')/'index.html'
                d=html.fromstring(p.read_bytes());self.related[subject].append((path,''.join(d.xpath('//h1')[0].itertext())))

    def shell(self,path,title,description,body,kind,crumbs,items=None,grade=None,subject=None):
        assert len(description)<=80 and description.endswith('.'),(path,description)
        url=DOMAIN+H(path)
        graph=[{'@type':'CollectionPage' if kind in ('hub','stage','grade','electives') else 'WebPage','@id':url+'#webpage','url':url,'name':title,'description':description,'inLanguage':'ko-KR','dateModified':DAY,'breadcrumb':{'@id':url+'#breadcrumb'}},
            {'@type':'BreadcrumbList','@id':url+'#breadcrumb','itemListElement':[{'@type':'ListItem','position':i,'name':n,'item':DOMAIN+H(p)} for i,(n,p) in enumerate(crumbs,1)]}]
        if kind=='subject':
            graph.append({'@type':'Article','@id':url+'#article','headline':title,'description':description,'datePublished':DAY,'dateModified':DAY,'inLanguage':'ko-KR','author':{'@type':'Organization','name':'전국학원','url':DOMAIN+'/'},'mainEntityOfPage':{'@id':url+'#webpage'},'educationalLevel':long_grade(grade),'learningResourceType':'학습 안내','citation':[self.by_key[(grade,subject)]['values']['출처 URL']]})
        if items:
            graph.append({'@type':'ItemList','@id':url+'#list','numberOfItems':len(items),'itemListElement':[{'@type':'ListItem','position':i,'name':n,'url':DOMAIN+H(p)} for i,(n,p) in enumerate(items,1)]})
        breadcrumb='<nav class="ci-crumb" aria-label="현재 위치">'+'<span aria-hidden="true">/</span>'.join(f'<a href="{H(p)}">{E(n)}</a>' if i<len(crumbs)-1 else f'<span aria-current="page">{E(n)}</span>' for i,(n,p) in enumerate(crumbs))+'</nav>'
        local='<section class="ci-local"><div><p class="ci-eyebrow">동네와 지점에서 이어 확인하기</p><h2>학습 자료를 준비한 뒤, 가까운 지점 안내를 살펴보세요</h2><p>최근 답안과 학교 진도, 궁금한 내용을 준비해 보세요. 수강 가능한 학년·과목과 현재 운영은 해당 지점의 안내로 확인할 수 있습니다.</p></div><nav class="ci-actions" aria-label="동네와 지점 안내">'+button('/전국학원/','우리 동네 학원 찾기')+button('/지점안내/','지점 안내 보기',True)+button('/선생님찾기/','선생님 소개 보기',True)+'</nav></section>'
        bridge=education_links('학습커리큘럼/'+(grade or '')+'/'+(subject or ''))
        raw=f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{E(title)} | 전국학원</title><meta name="description" content="{E(description)}"><meta name="robots" content="index,follow"><link rel="canonical" href="{url}"><link rel="icon" href="/assets/favicon.png"><meta name="theme-color" content="#173b32"><meta property="og:type" content="{'article' if kind=='subject' else 'website'}"><meta property="og:locale" content="ko_KR"><meta property="og:site_name" content="전국학원"><meta property="og:title" content="{E(title)} | 전국학원"><meta property="og:description" content="{E(description)}"><meta property="og:url" content="{url}"><meta property="og:image" content="{DOMAIN}/assets/title.png"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{E(title)} | 전국학원"><meta name="twitter:description" content="{E(description)}"><meta name="twitter:image" content="{DOMAIN}/assets/title.png"><link rel="stylesheet" href="/assets/site.css"><link rel="stylesheet" href="/assets/unified-ui.css?v=20261002-education">{STYLE}<script defer src="/assets/unified-ui.js?v=20260914-2"></script><script defer src="/assets/curriculum.js?v=20261003"></script><script type="application/ld+json">{J({'@context':'https://schema.org','@graph':graph})}</script></head><body class="unified-ui curriculum-page" data-curriculum="{DAY}" data-curriculum-kind="{kind}" data-curriculum-grade="{grade or ''}" data-curriculum-subject="{subject or ''}"><a class="skip-link" href="#main">본문 바로가기</a>{self.header}<main id="main"><div class="ci-wrap">{breadcrumb}{body}{local}{bridge}</div></main>{self.footer}</body></html>'''
        name=path.lstrip('/')+'index.html'
        self.pages[name]=dict(path=path,title=title,description=description,kind=kind,grade=grade,subject=subject)
        write(ROOT/name,raw)

    def crumbs(self,extra=()):return [('홈','/'),('학습가이드','/학습가이드/'),('학습커리큘럼',BASE),*extra]
    def sources(self,grade=None):
        r=self.overview[grade]['values'] if grade else None
        original=r['출처 URL'] if r else 'https://www.moe.go.kr/boardCnts/viewRenew.do?boardID=141&boardSeq=93458&lev=0'
        original=original.replace('view.do?','viewRenew.do?')
        label=('2015 개정 교육과정 총론·각론' if r and r['적용 교육과정']=='2015 개정' else '2022 개정 교육과정 총론·각론')
        links=[(label,original),('교육과정 일부개정 고시 안내 (2026-1호)','https://www.ne.go.kr/user/bbs/BD_selectBbs.do?q_bbsDocNo=20260121102419070&q_bbsSn=1016')]
        return '<section class="ci-sources" id="sources"><h2>참고 자료</h2><ul>'+''.join(f'<li><a href="{E(p)}" target="_blank" rel="noopener noreferrer">{E(n)} <span class="ci-sr">(새 창)</span></a></li>' for n,p in links)+'</ul><p>2026학년도 기준 · 확인일 2026년 10월 3일. 학습 중점과 순서는 학교 교과서·진도·평가 계획에 맞춰 조정하는 예시입니다.</p></section>'
    def hero(self,title,desc,eyebrow='학년·과목별 학습커리큘럼',actions=''):
        return f'<header class="ci-hero"><p class="ci-eyebrow">{E(eyebrow)}</p><h1>{E(title)}</h1><p class="ci-lead">{E(desc)}</p>{actions}</header>'
    def school_check(self,g):
        info=self.overview[g]['values']
        change='2026년 중3·고3은 2015 개정 교육과정이 적용됩니다. 2027학년도에는 해당 학년의 안내를 다시 확인해 주세요.' if g in ('중3','고3') else '학교마다 교과서와 단원 순서, 평가 범위가 다를 수 있습니다.'
        return f'<section class="ci-section ci-note" id="school-check"><h2>학교 자료와 맞춰 볼 내용</h2><p><strong>2026학년도: {E(info["적용 교육과정"])} 교육과정</strong></p><p>{E(short_note(g))}</p><ul><li>{E(info["학교에서 확인할 것"])}.</li><li>현재 학기 교과서·수업 자료와 평가 계획을 준비해 주세요.</li><li>{E(change)}</li></ul></section>'
    def subject_card(self,a,filterable=False):
        g=a['grade'];s=a['subject'];r=a['values'];title=long_grade(g)+' '+display_subject(g,s)
        attrs=f' data-curriculum-card data-grade="{g}" data-subject="{s}" data-search="{E(title+" "+r["주요 학습 중점(편집)"])}"' if filterable else ''
        return f'<article class="ci-card"{attrs}><p class="ci-eyebrow">{E(r["2026 적용"])} · {E(g)}</p><h3><a href="{H(a["path"])}">{E(title)}</a></h3><p>{E(r["주요 학습 중점(편집)"])}</p><span class="ci-card-end">학습 범위·순서·확인 과제 <span aria-hidden="true">↗</span></span></article>'
    def grade_card(self,g):
        r=self.overview[g]['values'];total=sum(a['grade']==g for a in self.subjects)
        return f'<article class="ci-card"><p class="ci-eyebrow">{E(r["적용 교육과정"])} · 과목/활동 {total}개</p><h3><a href="{H(grade_path(g))}">{E(long_grade(g))}</a></h3><p>{E(r["학년별 권장 중점"])}</p><p class="ci-card-end">{E(r["상세 정리 과목"])}</p></article>'
    def tools_links(self):return '<nav class="ci-tools" aria-label="함께 보는 커리큘럼 안내">'+button(BASE+'학습단계선택/','기초·표준·심화 비교',True)+button(BASE+'고등선택과목/','고등 공통·선택과목 안내',True)+'</nav>'
    def render_hub(self):
        title='초등·중등·고등 학년별 학습커리큘럼'
        desc='학년·과목별 학습 범위와 공부 순서, 확인 과제와 기초·표준·심화 학습 예시를 찾아 학생에게 맞는 공부를 준비하세요.'
        hero=self.hero(title,'이번 학기 학습 범위와 복습할 내용을 찾고, 현재 이해도에 맞는 공부 순서를 살펴보세요.',actions='<a class="ci-button" href="#catalog">학년과 과목으로 찾기</a>')
        stages='<nav class="ci-stage-grid" aria-label="학교급별 커리큘럼">'+''.join(f'<a href="{H(BASE+label+"/")}"><span>{"초1~초6" if p=="초" else "중1~중3" if p=="중" else "고1~고3"}</span><strong>{label} 커리큘럼</strong><b aria-hidden="true">↗</b></a>' for p,label in STAGES.items())+'</nav>'
        form='<form class="ci-filter" data-curriculum-filter hidden role="search"><div><label for="ci-grade">학년</label><select id="ci-grade"><option value="all">전체 학년</option>'+''.join(f'<option value="{g}">{long_grade(g)}</option>' for g in self.overview)+'</select></div><div><label for="ci-subject">과목·활동</label><select id="ci-subject"><option value="all">전체 과목·활동</option>'+''.join(f'<option value="{s}">{s}</option>' for s in SUBJECTS)+'</select></div><div><label for="ci-search">배우는 내용</label><input type="search" id="ci-search" maxlength="120" placeholder="예: 분수, 문장, 탐구" autocomplete="off"></div><button type="reset" class="ci-button ci-secondary">초기화</button></form>'
        library='<section class="ci-section" id="catalog"><div class="ci-section-head"><h2>학년·과목별 안내 찾기</h2><p>초1·2의 영어는 선택 활동, 사회·과학 연계는 통합교과 안에서 안내합니다.</p></div>'+form+'<p id="ci-count" role="status" aria-live="polite">전체 안내 66개</p><div class="ci-grid" id="ci-results">'+''.join(self.subject_card(a,True) for a in self.subjects)+'</div><div class="ci-empty" id="ci-empty" hidden><h3>조건에 맞는 안내가 없습니다</h3><p>검색어를 짧게 바꾸거나 학년·과목 선택을 넓혀 보세요.</p><button type="button" data-curriculum-reset class="ci-button">전체 안내 보기</button></div><button type="button" class="ci-button ci-secondary ci-more" id="ci-more" hidden>안내 더 보기</button></section>'
        note='<section class="ci-section ci-note"><h2>학년은 범위를, 현재 이해도는 시작점을 정합니다</h2><p>기초·표준·심화는 공부를 조정하는 예시입니다. 과목마다 막히는 내용과 필요한 도움이 다를 수 있으니, 점수 하나보다 실제 답안과 설명 과정을 함께 살펴보세요.</p><p>2026년에는 초1~6·중1~2·고1~2에 2022 개정, 중3·고3에 2015 개정 교육과정이 적용됩니다.</p></section>'
        self.shell(BASE,title,desc,hero+stages+self.tools_links()+library+note+self.sources(),'hub',self.crumbs(),[(long_grade(a['grade'])+' '+display_subject(a['grade'],a['subject']),a['path']) for a in self.subjects])
    def render_stage(self,prefix):
        label=STAGES[prefix];grades=[g for g in self.overview if g.startswith(prefix)];path=BASE+label+'/'
        title=label+' 학년별 커리큘럼과 공부 준비'
        desc=f'{label} 학년별 학습 중점과 과목별 공부 순서를 살펴보고, 현재 이해도와 학교 진도에 맞는 학습을 준비하세요.'
        text={'초':'한글·수 감각부터 교과 읽기와 자료 설명까지, 학년별 중점을 차례로 살펴보세요.','중':'교과 개념과 지문·자료를 연결하고, 학교의 실제 이수 범위와 평가 계획을 확인하세요.','고':'공통과목의 기초와 실제 선택과목을 구분하고, 입학 연도별 편제와 선이수를 함께 확인하세요.'}[prefix]
        body=self.hero(title,text)+self.tools_links()+'<section class="ci-section"><h2>학년을 선택하세요</h2><div class="ci-grid">'+''.join(self.grade_card(g) for g in grades)+'</div></section>'+self.school_check(grades[0])+self.sources(grades[0])
        self.shell(path,title,desc,body,'stage',self.crumbs([(label,path)]),[(long_grade(g),grade_path(g)) for g in grades])
    def render_grade(self,g):
        r=self.overview[g]['values'];title=long_grade(g)+' 과목별 커리큘럼';path=grade_path(g)
        desc=f'{long_grade(g)}의 과목별 학습 중점과 확인 과제를 살펴보고, 기초·표준·심화 공부와 학교별 준비사항을 확인하세요.'
        selected=[a for a in self.subjects if a['grade']==g]
        body=self.hero(title,r['학년별 권장 중점']+'을 중심으로 학습 범위와 현재 필요한 도움을 살펴보세요.',eyebrow='2026학년도 · '+r['적용 교육과정'])
        body+=self.school_check(g)+'<section class="ci-section"><h2>배우는 과목과 활동을 살펴보세요</h2><div class="ci-grid">'+''.join(self.subject_card(a) for a in selected)+'</div></section>'+self.tools_links()+self.sources(g)
        self.shell(path,title,desc,body,'grade',self.crumbs([(STAGES[g[0]],BASE+STAGES[g[0]]+'/'),(long_grade(g),path)]),[(display_subject(g,a['subject']),a['path']) for a in selected],grade=g)
    def level_cards(self,g,s):
        history=s=='역사';mapped='사회' if history else s
        result=''
        for index,level in enumerate(LEVELS,1):
            source=self.levels[(SCHOOL[g[0]],mapped,level)];r=source['values'];check=r['확인 과제(예시)'];flow=r['학습 순서(예시)']
            if g in ('초1','초2') and s in ('사회','과학'):
                check=self.by_key[(g,s)]['values']['확인 과제(예시)']
                flow={'기초':'생활 속 대상 살펴보기 → 눈에 보이는 사실 말하기','표준':'관찰 내용 나누기 → 기준에 따라 비교하기 → 기록하기','심화':'관찰 기록 비교하기 → 달라진 이유 질문하기 → 자기 말로 설명하기'}[level]
            result+=f'<article class="ci-level" data-level="{level}" data-level-row="{source["row"]}"><p class="ci-eyebrow">학습 단계 0{index}</p><h3>{level}</h3><p>{E(r["대상(예시)"])}</p><dl><dt>공부하는 순서</dt><dd>{E(flow)}</dd><dt>확인할 과제</dt><dd>{E(check)}</dd><dt>다음 단계로 넘어갈 때</dt><dd>{E(r["다음 단계 판단(예시)"])}</dd></dl></article>'
        return result
    def render_subject(self,a):
        g=a['grade'];s=a['subject'];r=a['values'];title=long_grade(g)+' '+display_subject(g,s)+' 학습커리큘럼';path=a['path'];practice=PRACTICE[s]
        desc=r['홈페이지 참고 문구'];assert len(desc)<=80 and desc.endswith('.'),(path,desc)
        toc='<nav class="ci-toc" aria-label="커리큘럼 목차">'+''.join(f'<a href="#{key}">{label}</a>' for key,label in [('scope','학습 범위'),('sequence','공부 순서'),('levels','기초·표준·심화'),('check-task','확인 과제'),('school-check','학교별 준비')])+'</nav>'
        hero=self.hero(title,desc,eyebrow='2026학년도 · '+r['2026 적용'])+toc
        scope=f'<section class="ci-section ci-reading" id="scope"><p class="ci-eyebrow">무엇을 배우나요?</p><h2>주요 학습 범위와 중점</h2><p class="ci-main-focus">{E(r["주요 학습 중점(편집)"])}</p><p>{E(short_note(g))}</p></section>'
        steps=[v.strip() for v in r['권장 순서(예시)'].split('→') if v.strip()]
        sequence='<section class="ci-section" id="sequence"><h2>공부를 연결하는 순서</h2><p>학교에서 현재 배우는 단원을 기준으로 시작하세요. 앞 단계에서 막히면 필요한 개념을 짧게 보완한 뒤 같은 과제로 다시 확인해 보세요.</p><ol class="ci-steps">'+''.join(f'<li><span aria-hidden="true">{i:02}</span><strong>{E(v)}</strong></li>' for i,v in enumerate(steps,1))+'</ol></section>'
        history_note='<p>역사는 사회·역사 자료 읽기의 공통 학습 기준을 참고한 예시입니다. 실제 이수 과목과 시대 범위에 맞춰 적용하세요.</p>' if s=='역사' else ''
        levels='<section class="ci-section" id="levels"><h2>기초·표준·심화에서 달라지는 공부</h2><p>같은 학년에서도 영역마다 필요한 도움이 다릅니다. 아래 예시는 학생이 실제 과제를 얼마나 독립적으로 설명하고 적용하는지 보며 조정하는 기준입니다.</p>'+history_note+'<div class="ci-level-grid">'+self.level_cards(g,s)+'</div><p class="ci-subnote">학습 단계는 공식 성취등급이나 지점의 모집반을 뜻하지 않습니다. 시간·분량·기간은 학생의 과제와 학교 일정에 맞춰 정하세요.</p></section>'
        check=f'<section class="ci-section ci-check-task" id="check-task" data-workbook-sheet="{a["sheet"]}" data-workbook-row="{a["row"]}"><p class="ci-eyebrow">스스로 이해도를 확인하기</p><h2>학습 뒤에 남겨 볼 과제</h2><p class="ci-task">{E(r["확인 과제(예시)"])}</p><div class="ci-two-col"><article><h3>학생이 해 볼 일</h3><ul><li>{E(practice[0])}</li><li>{E(practice[1])}</li><li>혼자 할 수 있었던 부분과 도움이 필요했던 부분을 답안 옆에 남겨 보세요.</li></ul></article><article><h3>학부모가 물어볼 질문</h3><ul><li>{E(practice[2])}</li><li>{E(practice[3])}</li><li>다음에는 어떤 부분부터 다시 확인하면 좋을까?</li></ul></article></div><p>자료를 보면서 한 것과 도움 없이 한 것을 구분해 보세요. 답안·설명·재확인 결과를 함께 보면 다음에 보완할 내용을 찾기 쉽습니다.</p></section>'
        school=self.school_check(g)+f'<p class="ci-school-adjust">이 과목에서 확인할 내용: {E(sentence(r["학교별 조정"]))}</p>'
        related=[(grade_path(g),long_grade(g)+' 다른 과목 보기'),*self.related[s]]
        nearby=list(self.overview);position=nearby.index(g)
        if position+1<len(nearby) and (nearby[position+1],s) in self.by_key:related.append((subject_path(nearby[position+1],s),long_grade(nearby[position+1])+' '+s+' 이어 보기'))
        onward='<section class="ci-section"><h2>함께 살펴볼 안내</h2><nav class="ci-related" aria-label="관련 학습 안내">'+''.join(f'<a href="{H(p)}">{E(n)} <span aria-hidden="true">↗</span></a>' for p,n in related)+'</nav></section>'
        self.shell(path,title,desc,hero+scope+sequence+levels+check+school+onward+self.sources(g),'subject',self.crumbs([(STAGES[g[0]],BASE+STAGES[g[0]]+'/'),(long_grade(g),grade_path(g)),(display_subject(g,s),path)]),grade=g,subject=s)
    def render_levels(self):
        path=BASE+'학습단계선택/';title='기초·표준·심화 학습 단계 고르는 방법';desc='학교급·과목별 기초·표준·심화 학습 예시를 비교하고, 학생의 실제 답안과 설명으로 필요한 도움을 정하는 방법을 안내합니다.'
        body=self.hero(title,'학년과 점수만으로 시작점을 정하기보다, 실제 과제에서 필요한 도움을 살펴보세요.')
        body+='<section class="ci-section ci-note"><h2>단계를 고를 때 확인할 세 가지</h2><ol><li>현재 학교 단원에서 짧은 과제를 골라 도움 없이 해 봅니다.</li><li>답의 이유를 말하거나 쓰고, 예시의 조건이 바뀌어도 적용하는지 확인합니다.</li><li>자료·힌트가 필요했던 부분을 표시하고 그 부분부터 보완합니다.</li></ol><p>개념을 다시 확인할 과제와 비교·추론으로 확장할 과제가 한 학생에게 함께 있을 수 있습니다. 단계는 과목과 영역에 따라 바꿔 적용하는 학습 예시입니다.</p></section>'
        body+='<form class="ci-filter ci-level-filter" data-level-filter hidden><div><label for="ci-school-level">학교급</label><select id="ci-school-level"><option value="all">전체 학교급</option>'+''.join(f'<option value="{p}">{v}</option>' for p,v in STAGES.items())+'</select></div><div><label for="ci-level-subject">과목</label><select id="ci-level-subject"><option value="all">전체 과목</option>'+''.join(f'<option value="{s}">{s}</option>' for s in SUBJECTS[:5])+'</select></div><button type="reset" class="ci-button ci-secondary">초기화</button></form><p data-level-count role="status" aria-live="polite">학교급·과목별 비교 15개</p>'
        for p,label in STAGES.items():
            g=next(g for g in self.overview if g.startswith(p) and (p!='초' or g=='초3'))
            for s in SUBJECTS[:5]:
                body+=f'<section class="ci-section" data-level-group data-school="{p}" data-subject="{s}"><h2>{label} {s} 학습 단계</h2><div class="ci-level-grid">{self.level_cards(g,s)}</div></section>'
        body+='<section class="ci-section"><h2>학교 과목과 현재 자료를 함께 확인하세요</h2><p>초1·2의 영어는 선택 활동, 사회·과학 연계는 통합교과 안에서 적용합니다. 역사의 자료 읽기는 사회·역사 공통 기준을 참고하되 실제 시대 범위에 맞춰 조정하세요.</p><p>교재를 고를 때는 학년·학기·개정판·과목명과 지금 필요한 연습을 먼저 확인하세요. 교과서와 학교 자료를 시작점으로 삼아 부족한 부분을 보완하는 자료를 살펴보세요.</p>'+button(BASE,'학년·과목별 범위 확인하기')+'</section>'+self.sources()
        self.shell(path,title,desc,body,'levels',self.crumbs([('학습 단계 선택',path)]))
    def render_electives(self):
        path=BASE+'고등선택과목/';title='고등 공통·선택과목의 범위와 준비 개념';desc='2022 개정 고등 공통·선택과목 29개 예시의 학습 범위와 준비 개념을 살펴보고, 학교의 개설 과목과 선이수를 확인하세요.'
        body=self.hero(title,'과목명뿐 아니라 배우는 내용과 준비 개념을 살펴보고, 학교의 실제 이수 계획과 맞춰 보세요.',eyebrow='2022 개정 교육과정 · 고등 과목 예시')
        body+='<section class="ci-section ci-note"><h2>먼저 학교의 과목 선택 안내를 확인하세요</h2><p>아래는 제공 자료에 정리된 공통·선택과목 29개 예시이며 전체 선택과목 목록은 아닙니다. 특정 학년에 모든 과목을 배우는 구성도 아닙니다.</p><p>2026년 고1·고2는 2022 개정, 고3은 2015 개정 교육과정이 적용됩니다. 과목을 비교할 때는 입학 연도와 개설 학년·학기, 선이수, 평가 계획을 함께 확인하세요.</p><p>과목별 준비 개념은 학습을 연결하기 위한 참고 내용입니다. 실제 이수 조건은 학교 편제표와 과목 선택 안내서로 확인하세요.</p></section>'
        body+='<form class="ci-filter ci-level-filter" data-elective-filter hidden><div><label for="ci-elective-subject">교과</label><select id="ci-elective-subject"><option value="all">전체 교과</option>'+''.join(f'<option value="{s}">{s}</option>' for s in SUBJECTS)+'</select></div><div><label for="ci-elective-type">과목 분류</label><select id="ci-elective-type"><option value="all">전체 분류</option>'+''.join(f'<option>{v}</option>' for v in ['공통','일반 선택','진로 선택','융합 선택'])+'</select></div><button type="reset" class="ci-button ci-secondary">초기화</button></form><p data-elective-count role="status" aria-live="polite">과목 예시 29개</p><div class="ci-grid ci-elective-grid">'
        items=[]
        for record in self.sheets['고등선택과목']:
            r=record['values'];anchor='elective-'+str(record['row']);items.append((r['과목명'],path+'#'+anchor))
            body+=f'<article class="ci-card ci-elective" id="{anchor}" data-elective-card data-subject="{r["교과"]}" data-type="{r["분류"]}" data-workbook-row="{record["row"]}"><p class="ci-eyebrow">{E(r["교과"])} · {E(r["분류"])}</p><h2>{E(r["과목명"])}</h2><dl><dt>배우는 내용</dt><dd>{E(r["공식 내용 범위 요약"])}</dd><dt>준비 개념</dt><dd>{E(r["선이수·준비 개념"])}</dd><dt>공부를 연결하는 방법</dt><dd>{E(r["권장 학습 연결(예시)"])}</dd></dl></article>'
        body+='</div><p data-elective-empty class="ci-empty" hidden>조건에 맞는 과목 예시가 없습니다. 교과나 분류를 넓혀 보세요.</p><section class="ci-section"><h2>학교에서 확인할 목록</h2><ul><li>현재 학교의 입학 연도별 교육과정 편제표</li><li>과목 선택 안내서의 실제 개설 학년·학기와 이수 조건</li><li>교과서와 수행평가·정기시험 평가 계획</li><li>학교 수업 범위와 해당 응시 연도의 공식 수능 안내</li></ul><div class="ci-actions">'+button(grade_path('고2'),'2026 고2 학습 안내',True)+button(grade_path('고3'),'2026 고3 학습 안내',True)+'</div></section>'+self.sources('고2')
        self.shell(path,title,desc,body,'electives',self.crumbs([('고등 공통·선택과목',path)]),items)

def contextual_destination(name):
    parts=name.split('/')[:-1]
    for part in reversed(parts):
        m=re.match(r'^(초[1-6]|중[1-3]|고[1-3])(국어|영어|수학|사회|과학|역사)',part)
        if m:return subject_path(m[1],m[2]),long_grade(m[1])+' '+display_subject(m[1],m[2])+' 커리큘럼',subject_path(m[1],m[2])+'#levels','이 과목의 학습 단계 비교','subject'
    for part in reversed(parts):
        if part in STAGES.values():return BASE+part+'/',part+' 학년별 커리큘럼',BASE+'학습단계선택/','기초·표준·심화 비교','stage'
    return BASE,'학년·과목별 커리큘럼',BASE+'학습단계선택/','기초·표준·심화 비교','all'

def discovery(name):
    path,label,level_path,level_label,kind=contextual_destination(name)
    return START+f'<section class="curriculum-bridge" data-curriculum-bridge="{kind}"><div><p class="ci-eyebrow">학습커리큘럼</p><h2>배우는 내용과 공부의 시작점을 함께 살펴보세요</h2><p>학교 진도와 현재 이해도에 맞춰 학습 범위·순서·확인 과제를 찾아보세요.</p></div><nav class="ci-actions" aria-label="함께 보는 학습커리큘럼"><a class="ci-button" data-curriculum-target href="{H(path)}">{E(label)}</a><a class="ci-button ci-secondary" href="{H(level_path)}">{E(level_label)}</a></nav></section>'+END

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report-dir',type=Path,required=True);parser.add_argument('--pages-only',action='store_true');args=parser.parse_args();out=args.report_dir
    catalog=load(ROOT/'tools/curriculum_catalog.json');model=Curriculum(catalog)
    old_manifest=load(out/'before-release-public-manifest.json')
    with zipfile.ZipFile(out/'before-pages.zip') as archive:originals={n:archive.read(n).decode('utf-8') for n in archive.namelist()}
    targets=[n for n in originals if n.startswith(('전국학원/','과목별학원/','지점안내/')) or n in ('index.html','학습가이드/index.html','교육정보/index.html')]
    changed={'assets/curriculum.css','assets/curriculum.js'}
    mappings=[]
    def update(n):
        raw=originals[n];module=discovery(n)
        assert START not in raw and END not in raw,n
        raw=raw.replace('</head>',STYLE+'</head>',1)
        first=raw.index('<main');closing=raw.index('</main>',first)
        preferred=re.search(r'<section\b[^>]*id="(?:learning-materials|math-preparation|hub-coaching-summary|learning-paths)"',raw[first:closing])
        education=re.search(r'<!-- education-info:start -->',raw[first:closing])
        offset=first+preferred.start() if preferred else first+education.start() if education else closing
        updated=raw[:offset]+module+raw[offset:]
        write(ROOT/n,updated)
        return n,contextual_destination(n)
    if not args.pages_only:
        with ThreadPoolExecutor(max_workers=12) as pool:
            for count,(name,destination) in enumerate(pool.map(update,targets),1):
                changed.add(name);mappings.append({'page':name,'target':destination[0],'levelTarget':destination[2],'kind':destination[4]})
                if count%2000==0:print(json.dumps({'linkedPages':count,'total':len(targets)}),flush=True)
    else:
        changed.update(targets);mappings=load(out/'link-mapping.json')
    model.render_hub()
    for p in STAGES:model.render_stage(p)
    for g in model.overview:model.render_grade(g)
    for a in model.subjects:model.render_subject(a)
    model.render_levels();model.render_electives()
    assert len(model.pages)==84,len(model.pages)
    changed.update(model.pages)
    config=load(out/'before-seo-descriptions.json')
    for page in model.pages.values():config['pages'][page['path'].rstrip('/')]={'description':page['description'],'sources':[page['description']]}
    write(ROOT/'seo-descriptions.json',json.dumps(config,ensure_ascii=False,indent=2)+'\n')
    sitemap=(out/'before-sitemap.xml').read_text('utf-8')
    for n in targets:
        uri=DOMAIN+H('/'+n.removesuffix('index.html'))
        sitemap=re.sub(r'(<url>\s*<loc>'+re.escape(uri)+r'</loc>\s*<lastmod>)[^<]*(</lastmod>)',lambda m:m[1]+DAY+m[2],sitemap,count=1)
    additions=''.join(f'<url><loc>{DOMAIN+H(p["path"])}</loc><lastmod>{DAY}</lastmod></url>\n' for p in model.pages.values())
    sitemap=sitemap.replace('</urlset>',additions+'</urlset>')
    write(ROOT/'sitemap.xml',sitemap);changed.add('sitemap.xml')
    manifest=old_manifest
    def hash_file(n):
        data=(ROOT/n).read_bytes();return n,sha(data),sha(data.replace(b'\r\n',b'\n'))
    with ThreadPoolExecutor(max_workers=12) as pool:
        for n,digest,text_digest in pool.map(hash_file,sorted(changed)):
            manifest['files'][n]=digest;manifest.setdefault('textSha256',{})[n]=text_digest
    manifest['createdAt']=DAY;manifest['sitemapPages']=sum(n.endswith('.html') for n in manifest['files'])
    write(ROOT/'release-public-manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    write(out/'pages.json',json.dumps(model.pages,ensure_ascii=False,indent=2)+'\n')
    write(out/'link-mapping.json',json.dumps(mappings,ensure_ascii=False,indent=2)+'\n')
    report=dict(date=DAY,newPages=len(model.pages),subjectPages=len(model.subjects),grades=len(model.overview),learningExamples=len(model.levels),electiveExamples=29,linkedExistingPages=len(targets),linksByRoot=dict(Counter(n.split('/')[0] for n in targets)),sitemapPages=manifest['sitemapPages'],publicFiles=len(manifest['files']),publicChanges=sorted(changed),sourceHash=catalog['sha256'],deployed=False)
    write(out/'generation.json',json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='publicChanges'},ensure_ascii=False))

if __name__=='__main__':main()
