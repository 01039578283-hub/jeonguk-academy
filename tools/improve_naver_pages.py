"""Source-bound migration for the reviewed 전국학원 release, never a publisher.

Read the supplied CSV/XLSX, match existing URLs and registered centers, and
preview before --apply. Private inputs and reports are outside the public manifest.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import openpyxl
from lxml import etree, html

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'https://xn--3e0bl59bm0ad17a.com'
DAY = '2026-09-28'
SUBJECTS = ['국어', '영어', '수학', '과학', '사회']
H = escape


def norm(value):
    return re.sub(r'\s+', '', str(value or ''))


def text(node):
    return ' '.join(node.text_content().split())


def has_class(node, cls):
    return cls in (node.get('class') or '').split()


def by_class(node, cls):
    return node.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " '+cls+' ")]')


def fragment(source):
    return html.fragment_fromstring(source)


def serialize(node):
    return html.tostring(node, encoding='unicode', with_tail=False)


def repair_map_images(main):
    repairs=[]
    for img in main.xpath('.//img[@src]'):
        src=unquote(img.get('src'))
        if 'assets/maps/' not in src:continue
        prefix,name=src.rsplit('/',1)
        if ' ' not in name and name!='jincheondong.jpg':continue
        old_asset=ROOT/'assets/maps'/name
        if old_asset.is_file():continue
        fixed=name.replace(' ','-')
        if name=='jincheondong.jpg':fixed='jincheondong.png'
        assert (ROOT/'assets/maps'/fixed).is_file(), ('Missing map replacement',src)
        target=prefix+'/'+fixed
        img.set('src',target)
        repairs.append({'from':src,'to':target})
    return repairs


def clean_changed_blocks(raw):
    # Removing old sections leaves indentation-only lines. Keep the unchanged
    # header/footer byte-for-byte and normalize only the rewritten head/main.
    return re.sub(r'<(?:head|main)\b[^>]*>.*?</(?:head|main)>',
                  lambda m:re.sub(r'(?m)^[ \t]+\r?$','',m[0]),raw,flags=re.S)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def path_url(rel):
    return '/'+rel.removesuffix('index.html') if rel != 'index.html' else '/'


def absolute(path):
    return ORIGIN+quote(path, safe='/#')


def grades(value):
    return re.findall(r'[초중고][1-6]', str(value or ''))


def grade_label(values):
    groups = []
    for prefix in ['초', '중', '고']:
        nums = sorted({int(g[1:]) for g in values if g.startswith(prefix)})
        if not nums:
            continue
        if len(nums)>1 and nums == list(range(nums[0], nums[-1]+1)):
            groups.append(f'{prefix}{nums[0]}~{prefix}{nums[-1]}')
        else:
            groups.append('·'.join(f'{prefix}{n}' for n in nums))
    return ' / '.join(groups) or '개설 학년 확인 필요'


def graph_of(doc):
    result = []
    for script in doc.xpath('//script[@type="application/ld+json"]'):
        obj = json.loads(script.text)
        result.extend(obj.get('@graph', [obj]))
    return result


def data_from_sources(references):
    source_names = ['센터정보 정리.csv', '센터 정보 및 교육비 371개 코드_최신화.csv',
                    '코칭센터_데이터_.xlsx', '타깃학교 v2.xlsx', '상담방식.txt']
    hashes = {name: sha(references/name) for name in source_names}
    with (references/source_names[0]).open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.reader(f))
    with (references/source_names[1]).open(encoding='utf-8-sig', newline='') as f:
        snippets = list(csv.reader(f))
    assert len(rows) == 372 and len(snippets) == 371
    assert all(len(r)==20 for r in rows) and all(len(r)==1 for r in snippets)
    wb = openpyxl.load_workbook(references/source_names[2], read_only=True, data_only=True)
    sheet = list(wb['센터정보'].values)
    workbook = {norm(r[0]): {'row': i+2, 'registered': str(r[6] or ''),
                            'address': str(r[11] or ''),
                            'grades': {s: grades(r[16+j]) for j,s in enumerate(SUBJECTS)}}
                for i,r in enumerate(sheet[1:]) if r[0]}
    wb.close()
    wb = openpyxl.load_workbook(references/source_names[3], read_only=True, data_only=True)
    school_rows = list(wb.active.values)[1:]
    wb.close()
    assert len(school_rows)==371

    branches = []
    for p in sorted((ROOT/'지점안내').glob('*/*/index.html')):
        doc = html.fromstring(p.read_bytes())
        orgs = [n for n in graph_of(doc) if 'EducationalOrganization' in n.get('@type', [])]
        assert len(orgs)==1, p
        branches.append({'route': '/'+p.parent.relative_to(ROOT).as_posix()+'/',
                         'name': p.parent.name, 'org': orgs[0], 'doc': doc})
    assert len(branches)==193
    areas = []
    for i,(row,snippet,school) in enumerate(zip(rows[1:],snippets,school_rows)):
        assert tuple(norm(x) for x in row[0:7:2]) == tuple(norm(school[x]) for x in [0,1,2,3]), ('school alignment',i)
        dom = html.fragment_fromstring(snippet[0], create_parent='div')
        snips = by_class(dom, 'wawa-center-snippet')
        assert len(snips)==1, ('snippet count', i+1)
        snip = snips[0]
        address_card = next(n for n in by_class(snip,'wawa-info-card') if text(by_class(n,'wawa-label')[0])=='주소')
        current_address = text(by_class(address_card,'wawa-text')[0])
        candidates = [b for b in branches if norm(b['org']['name'])==norm(row[8])
                      and norm(b['org']['address']['streetAddress'])==norm(current_address)]
        assert len(candidates)==1, ('branch mapping', i+2, row[:7], [b['name'] for b in candidates])
        branch = candidates[0]
        assert norm(row[8]) in norm(text(snip)), ('snippet identity',i)
        subject_grades = {}
        for grade_row in by_class(snip,'wawa-grade-row'):
            name = text(by_class(grade_row,'wawa-grade-subject')[0])
            subject_grades[name] = [text(p) for p in by_class(grade_row,'wawa-pill')]
            assert all(re.fullmatch(r'[초중고][1-6]',g) for g in subject_grades[name])
        assert set(subject_grades)==set(SUBJECTS), ('snippet grades',i+1)
        book = workbook.get(norm(branch['name']))
        if book is None:
            book = next((v for v in workbook.values() if norm(v['address'])==norm(current_address)
                         and norm(v['registered'])==norm(row[8])), None)
        if book:
            assert norm(book['address'])==norm(current_address), ('workbook address',i)
            # The latest public snippets narrow the raw spreadsheet using its
            # subject/grade restrictions. Never expand those vetted scopes.
            assert all(set(subject_grades[s])<=set(book['grades'][s]) for s in SUBJECTS), ('unsupported snippet grade',i+2)
        else:
            assert branch['name']=='화성태안점', ('unmatched workbook',i)
        # Only the already vetted school names in the owner's public HTML are used.
        schools = {}
        for level,cls in [('초등','is-elementary'),('중등','is-middle'),('고등','is-high')]:
            cards = [n for n in by_class(snip,'wawa-school-card') if has_class(n,cls)]
            schools[level] = [text(p) for card in cards for p in by_class(card,'wawa-pill')]
        assert not re.search(r'\[후보|확인 필요|휴·폐교|대상 미확인', ' '.join(sum(schools.values(),[])))
        # Show the common price reference for the actual branch address only.
        # Center-specific tables and every qualifying note remain intact.
        for block in by_class(snip,'wawa-fee-block'):
            title=' '.join(block.xpath('.//h3/text()'))
            if '기존 공통 안내:' in title:
                is_other='서울 외' in title
                if is_other == current_address.startswith('서울'):
                    block.getparent().remove(block)
        for heading in snip.xpath('.//h2'):
            if text(heading)=='학교별 수업 안내':heading.text='상담에 참고할 학교 목록'
        fees=by_class(snip,'wawa-fee-accordion')
        if fees:
            summ=fees[0].xpath('./summary')[0];summ.text='교육비 참고와 확인할 조건'
            if '기존 공통 안내:' in text(fees[0]):
                fees[0].insert(1,fragment('<p class="ng-fee-notice">지역 공통 참고 금액입니다. 이 지점의 확정 교습비는 안내 자료와 상담에서 확인해 주세요.</p>'))
        areas.append({'area':row[0], 'region':row[2], 'district':row[4], 'branch':branch,
                      'grades':subject_grades, 'snippet':serialize(snip), 'sourceRow':i+2,
                      'schools':schools, 'address':current_address,
                      'addressUpdated':norm(current_address)!=norm(row[10])})
    return areas, branches, hashes


def map_pages(areas):
    by_area = defaultdict(list)
    for a in areas:
        by_area[norm(a['area'])].append(a)
    result = []
    for family in ['전국학원', '과목별학원']:
        for p in sorted((ROOT/family).rglob('index.html')):
            parts = p.relative_to(ROOT).parts
            if family=='전국학원':
                if len(parts) not in [5,6]: continue
                candidates = [a for a in by_area[norm(parts[3])] if norm(a['district'])==norm(parts[2]) and norm(a['region'])==norm(parts[1])]
                if not candidates:
                    # Existing Jeju URLs use /시/ although the record says 제주시.
                    # Keep that indexed route and resolve by a unique region+area.
                    candidates = [a for a in by_area[norm(parts[3])] if norm(a['region'])==norm(parts[1])]
                topic = parts[4].replace('학원','') if len(parts)==6 else '학원'
            else:
                if len(parts)!=4: continue
                candidates = by_area[norm(parts[2])]
                topic = parts[1].replace('학원','')
            assert len(candidates)==1, ('page mapping',p,len(candidates))
            result.append((p,candidates[0],topic))
    assert len(result)==7049, len(result)
    return result


def topic_state(area,topic):
    subject = next((s for s in SUBJECTS if s in topic), None)
    grade = re.search(r'[초중고][1-6]',topic)
    grade = grade[0] if grade else None
    supported = bool(subject and grade and grade in area['grades'][subject])
    return subject,grade,supported


def scope_sentence(area,topic):
    branch = area['branch']['name']
    subject,grade,supported = topic_state(area,topic)
    if subject and grade:
        if supported:
            return f'제공된 지점 자료에서 {branch}의 {grade} {subject} 수강 학년을 확인했습니다. 현재 모집과 시간표는 상담에서 확인해 주세요.'
        return f'{branch}의 제공 자료에서는 {grade} {subject} 수강 가능 여부가 확인되지 않습니다. 등록 전 해당 학년의 개설 여부와 수업 조건을 먼저 문의해 주세요.'
    actual = ' · '.join(s+' '+grade_label(gs) for s,gs in area['grades'].items() if gs)
    return f'{branch} 자료에 기재된 과목별 수강 범위는 {actual}입니다. 현재 모집 여부는 지점에 확인해 주세요.'


def description(area,topic):
    subject,grade,supported = topic_state(area,topic)
    local = area['area']; branch = area['branch']['name']
    if subject and grade:
        if supported:
            value=f'{local} {grade} {subject}학원을 찾는 분께 {branch}의 수강 학년·위치·교육비 확인 방법을 안내합니다.'
        else:
            value=f'{local} {grade} {subject} 수강 전 확인할 {branch}의 개설 학년과 상담 준비·교육비를 안내합니다.'
    else:
        value=f'{local}에서 연결되는 {branch}의 과목별 수강 학년·주소·교육비와 상담 준비를 안내합니다.'
    assert 1<=len(value)<=80, (len(value),value)
    return value


def facts_panel(area,topic):
    b=area['branch']; subject,grade,supported=topic_state(area,topic)
    scope = grade_label(area['grades'][subject]) if subject else ' · '.join(s for s,g in area['grades'].items() if g)
    label = f'{subject} 수강 학년' if subject else '자료에 기재된 과목'
    return fragment(f'''<section class="ng-facts" id="center-summary" aria-labelledby="center-summary-title">
<p class="ng-kicker">방문할 지점과 수강 조건</p><h2 id="center-summary-title">{H(b['name'])} 수강 정보</h2>
<dl><div><dt>연결 지점</dt><dd><a href="{H(b['route'])}">{H(b['org']['name'])}</a></dd></div>
<div><dt>{H(label)}</dt><dd>{H(scope)}</dd></div><div><dt>방문 주소</dt><dd>{H(area['address'])}</dd></div></dl>
<p class="ng-status{' ng-status-check' if subject and grade and not supported else ''}">{H(scope_sentence(area,topic))}</p>
<div class="ng-actions"><a href="{H(b['route'])}#courses">{H(b['name'])} 전체 수강 학년</a><a href="{H(b['route'])}#fees">교습비·수업 조건 확인</a><a href="/상담문의/">공통 상담 신청</a></div>
</section>''')


def faq_content(area,topic):
    b=area['branch'];subject,grade,_=topic_state(area,topic)
    return [
        (f'{area["area"]}에 있는 별도 지점인가요?', f'이 동네 안내에서 연결되는 곳은 {b["org"]["name"]}입니다. 실제 방문 주소는 {area["address"]}입니다.'),
        (f'{grade+" " if grade else ""}{subject or "희망 과목"}을 수강할 수 있나요?', scope_sentence(area,topic)),
        ('교육비 표의 금액으로 바로 등록할 수 있나요?', '지역 공통 참고표는 개별 지점의 확정 교습비가 아닙니다. 교습비 안내 자료에서 과목당 금액과 수업 시간·횟수·교재비를 확인하고 최종 비용을 상담에서 확인하세요.')]


def faq_section(items):
    return fragment('<section class="ng-section" id="enrollment-faq"><h2>수강 전에 자주 묻는 질문</h2>'+''.join(
        f'<details><summary>{H(q)}</summary><p>{H(a)}</p></details>' for q,a in items)+'</section>')


def math_preparation(area,grade):
    if grade=='고1':
        rows=[('개념과 계산을 나누어 살펴보기','최근 오답 두세 개를 골라 사용한 개념을 말로 설명해 보세요. 개념을 몰랐는지, 식을 세운 뒤 계산에서 틀렸는지 구분하면 복습할 부분이 분명해집니다.'),
              ('학교 진도와 복습 단원 함께 적기','학교에서 배우는 단원, 사용하는 교재, 다음 평가 범위를 적어 가세요. 이전 학년의 계산·문자식에서 막히는 부분이 있다면 새 진도와 함께 보완할 수 있는지 질문하세요.'),
              ('풀이를 혼자 이어갈 수 있는지 확인하기','해설을 본 문제와 혼자 다시 푼 문제를 구분해 가져가세요. 도움 없이 설명할 수 있는 단계와 다시 연습할 단계를 상담에서 비교해 보세요.')]
    else:
        rows=[('현재 이수 과목부터 확인하기','학년 이름만으로 교재나 진도를 정하지 말고 학교에서 현재 이수하는 수학 과목, 교재, 평가 범위를 적어 가세요. 선택한 과정에 맞는 수업이 가능한지 먼저 확인하세요.'),
              ('오답이 생긴 앞 단원까지 확인하기','최근 틀린 문제의 조건 해석, 식의 변형, 그래프 읽기 중 어느 단계에서 막혔는지 표시해 보세요. 앞에서 배운 개념이 필요한 문제라면 그 단원도 함께 적어 가세요.'),
              ('내신 준비와 다른 학습의 시간 나누기','학교 평가까지 남은 기간과 현재 학습량을 함께 전달하세요. 내신 범위의 복습, 다음 진도, 추가 시험 준비를 병행할 수 있는지 지점에 구체적으로 질문하세요.')]
    schools=area['schools']['고등']
    school_text=' · '.join(schools) if schools else '학교명과 현재 교재·평가 범위를 상담 시 알려 주세요.'
    return fragment('<section class="ng-section" id="math-preparation"><h2>'+H(grade)+' 수학 상담에 가져갈 자료</h2><p>아래는 학생의 학습 상태를 정리하는 방법입니다. 실제 교재·과제·피드백 방식은 지점 상담에서 확인하세요.</p><div class="ng-study-grid">'+''.join(
        f'<article><h3>{H(title)}</h3><p>{H(body)}</p></article>' for title,body in rows)+
        '</div><h3>'+H(area['area'])+' 학교 자료와 함께 준비하기</h3><p>'+H(school_text)+
        '</p><p class="ng-note">학교 이름은 상담 참고 목록입니다. 해당 학교의 재원생·지도 실적이나 학교와의 제휴를 뜻하지 않습니다. 본인의 교재와 평가 범위를 기준으로 문의해 주세요.</p></section>')


def related_links(main,area):
    found={}
    for cls in ['local-topic-links-section','child-page-links']:
        for section in by_class(main,cls):
            for a in section.xpath('.//a[@href]'):
                href=a.get('href');label=text(a)
                if label and href not in found:found[href]=label
    b=area['branch']
    items=[(b['route'],b['name']+' 지점 안내')]+list(found.items())[:12]
    return fragment('<nav class="ng-section" aria-label="관련 학년과 지점 안내"><h2>관련 학년과 지점 안내</h2><div class="ng-related">'+''.join(
        f'<a href="{H(href)}">{H(label)}</a>' for href,label in items)+'</div></nav>')


def wrap_media(main):
    for cls in ['local-media-section','subject-media-section']:
        for media in by_class(main,cls):
            if has_class(media.getparent(),'ng-media'):continue
            media.getparent().remove(media)
            wrapper=fragment('<details class="ng-media"><summary>학습코칭 안내 이미지와 위치 지도 보기</summary></details>')
            for img in media.xpath('.//img'):
                if '/centers/common/' in img.get('src',''):
                    img.set('width','918');img.set('height','16116');img.set('decoding','async')
            wrapper.append(media);main.append(wrapper)


def update_main(doc,area,topic):
    main=doc.xpath('//main')[0]
    assert main.get('data-naver-improved') is None, 'Already migrated; use --check, not a second migration.'
    main.set('data-naver-improved',DAY)
    if not main.get('id'):main.set('id','main')
    old_reviews=len(by_class(main,'parent-review-card'))
    for section in by_class(main,'parent-review-section'):
        section.getparent().remove(section)
    # The public HTML supplied by the owner already separates common fee references
    # and excludes uncertain school candidates. Preserve those distinctions.
    old_snips=by_class(main,'wawa-center-snippet')
    if not old_snips:old_snips=by_class(main,'subject-center-card')
    assert len(old_snips)==1, ('snippet missing',topic,area['area'])
    snip=fragment(area['snippet']);snip.set('id','enrollment-details')
    old_snips[0].getparent().replace(old_snips[0],snip)
    subject,grade,supported=topic_state(area,topic)
    is_math=subject=='수학' and grade in ['고1','고2']
    h1=doc.xpath('//h1')[0]
    if is_math:
        media=by_class(main,'local-media-section')[0]
        related=related_links(main,area)
        heading=f'{area["area"]} {grade} 수학학원 '+('수강 안내' if supported else '수강 전 확인사항')
        hero=fragment(f'<section class="ng-hero"><p class="ng-kicker">{H(area["region"])} · {H(area["district"])} · {H(area["branch"]["name"])}</p><h1>{H(heading)}</h1><p>{H(description(area,topic))}</p></section>')
        for node in list(main):main.remove(node)
        main.text='\n';main.append(hero);main.append(facts_panel(area,topic))
        main.append(fragment('<nav class="ng-jump" aria-label="수강 안내 목차"><a href="#math-preparation">수학 상담 준비</a><a href="#enrollment-details">학교·교습비 자료</a><a href="#enrollment-faq">수강 질문</a></nav>'))
        main.append(math_preparation(area,grade));main.append(snip)
        main.append(faq_section(faq_content(area,topic)));main.append(related);main.append(media)
    else:
        # Move the existing title/intro before the common poster; preserve the
        # established subject manuscript and its links.
        if h1.getparent().get('class')=='article-hero':
            hero=h1.getparent();hero.getparent().remove(hero);main.insert(0,hero)
            eyebrow=by_class(hero,'article-eyebrow')
            if eyebrow:eyebrow[0].text='지역별 수강 안내'
            main.insert(1,facts_panel(area,topic))
        else:
            top=h1
            while top.getparent() is not main:top=top.getparent()
            main.insert(list(main).index(top)+1,facts_panel(area,topic))
        # These generated summaries repeat the manuscript and imply local
        # services without adding independently verified center facts.
        for cls in ['seo-geo-section','seo-answer-section','parent-faq-section']:
            for node in by_class(main,cls):node.getparent().remove(node)
        if not supported and subject and grade:
            # Do not let an old introduction contradict the verified grade card.
            for node in by_class(main,'article-intro'):
                node.clear();node.set('class','article-intro');node.text=scope_sentence(area,topic)
        main.append(faq_section(faq_content(area,topic)))
    wrap_media(main)
    main.append(fragment(f'<p class="ng-updated">안내 자료 대조: <time datetime="{DAY}">{DAY}</time>. 현재 모집·시간표·최종 비용은 지점에서 확인해 주세요.</p>'))
    return main,is_math,old_reviews


def schema_for(doc,area,topic,desc,is_math):
    old=graph_of(doc)
    canonical=doc.xpath('string(//link[@rel="canonical"]/@href)')
    h1=text(doc.xpath('//h1')[0]);center=copy.deepcopy(area['branch']['org'])
    for key in ['review','aggregateRating','openingHours','openingHoursSpecification','telephone','priceRange']:
        center.pop(key,None)
    breadcrumbs=next((n for n in old if n.get('@type')=='BreadcrumbList'),None)
    published=next((n.get('datePublished') for n in old if n.get('@type')=='Article'),None)
    site={'@type':'WebSite','@id':ORIGIN+'/#website','url':ORIGIN+'/','name':'전국학원','inLanguage':'ko-KR'}
    publisher={'@type':'Organization','@id':ORIGIN+'/#organization','name':'전국학원','url':ORIGIN+'/'}
    page={'@type':'WebPage','@id':canonical+'#webpage','url':canonical,'name':h1,'description':desc,
          'inLanguage':'ko-KR','isPartOf':{'@id':site['@id']},'publisher':{'@id':publisher['@id']},
          'about':{'@id':center['@id']},'mainEntity':{'@id':canonical+'#article'},'dateModified':DAY}
    if breadcrumbs:page['breadcrumb']={'@id':breadcrumbs['@id']}
    article={'@type':'Article','@id':canonical+'#article','headline':h1,'description':desc,
             'abstract':scope_sentence(area,topic),'mainEntityOfPage':{'@id':page['@id']},
             'author':{'@id':publisher['@id']},'publisher':{'@id':publisher['@id']},
             'about':{'@id':center['@id']},'inLanguage':'ko-KR','dateModified':DAY}
    if published:article['datePublished']=published
    image=doc.xpath('string(//meta[@property="og:image"]/@content)')
    if image:article['image']=image
    graph=[site,publisher,page,article,center]
    if breadcrumbs:graph.append(breadcrumbs)
    subject,grade,supported=topic_state(area,topic)
    if supported:
        graph.append({'@type':'Service','@id':area['branch']['org']['@id'].removesuffix('#center')+'#service-'+quote(subject),
                      'name':area['branch']['name']+' '+subject+' 수강 안내', 'serviceType':subject+' 학습',
                      'description':'자료상 수강 학년: '+grade_label(area['grades'][subject]),'provider':{'@id':center['@id']}})
    graph.append({'@type':'FAQPage','@id':canonical+'#enrollment-faq','mainEntity':[
        {'@type':'Question','name':q,'acceptedAnswer':{'@type':'Answer','text':a}}
        for q,a in faq_content(area,topic)]})
    return {'@context':'https://schema.org','@graph':graph}


def replace_metadata(raw,desc,heading,graph):
    # Restrict byte-level changes to intended main/head fields. Header, footer,
    # analytics and other scripts retain their original bytes.
    raw=re.sub(r'<title>.*?</title>',lambda _: '<title>'+H(heading)+' | 전국학원</title>',raw,count=1,flags=re.S)
    def meta(m):
        node=fragment(m[0]);name=node.get('name') or node.get('property')
        if name in ['description','og:description','twitter:description']:node.set('content',desc)
        elif name in ['og:title','twitter:title']:node.set('content',heading+' | 전국학원')
        else:return m[0]
        return serialize(node)
    raw=re.sub(r'<meta\b[^>]*>',meta,raw,flags=re.I)
    schema='<script type="application/ld+json">'+json.dumps(graph,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')+'</script>'
    raw=re.sub(r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>.*?</script>','',raw,flags=re.S|re.I)
    if '/assets/naver-region-guide.css' not in raw:
        schema+='<link rel="stylesheet" href="/assets/naver-region-guide.css?v=20260928">'
    return clean_changed_blocks(raw.replace('</head>',schema+'\n</head>',1))


def improve_page(job):
    p,area,topic=job
    raw=p.read_text(encoding='utf-8-sig');doc=html.fromstring(raw)
    desc=description(area,topic)
    main,is_math,reviews=update_main(doc,area,topic)
    map_repairs=repair_map_images(main)
    heading=text(doc.xpath('//h1')[0])
    new=re.sub(r'<main\b[^>]*>.*?</main>',lambda _:serialize(main),raw,count=1,flags=re.S)
    new=replace_metadata(new,desc,heading,schema_for(doc,area,topic,desc,is_math))
    assert new!=raw
    return p,new,{'path':p.relative_to(ROOT).as_posix(),'description':desc,
                  'oldDescription':html.fromstring(raw).xpath('string(//meta[@name="description"]/@content)'),
                  'mathRewritten':is_math,'reviewsRemoved':reviews,'topic':topic,'mapImageRepairs':map_repairs,
                  'branch':area['branch']['name'],'supported':topic_state(area,topic)[2],
                  'beforeSha256':hashlib.sha256(raw.encode()).hexdigest(),'afterSha256':hashlib.sha256(new.encode()).hexdigest()}


def resume_page(job,report,branch=False):
    p,area,topic=job
    f=report/'preview'/p.relative_to(ROOT)
    try:new=f.read_text(encoding='utf-8-sig')
    except FileNotFoundError:new=''
    if new and '</head>' in new and '</main>' in new:
        if 'data-naver-improved="2026-09-28"' in new:
            # Reuse staged output after an interrupted long run. Full independent
            # validation still precedes copying anything into the release.
            rel=p.relative_to(ROOT).as_posix();key=path_url(rel).rstrip('/') or '/'
            d=html.fromstring(new[:new.index('</head>')+7])
            canonical=d.xpath('string(//link[@rel="canonical"]/@href)')
            if '<h1' in new and unquote(urlsplit(canonical).path)==path_url(rel):
                record={'path':rel,'description':d.xpath('string(//meta[@name="description"]/@content)'),
                        'oldDescription':PREVIEW_BASE['config']['pages'][key]['description'],
                        'mathRewritten':False if branch else topic in ['고1수학','고2수학'],
                        'reviewsRemoved':6 if rel.startswith('전국학원/') else 0, 'branch':area['branch']['name'],
                        'beforeSha256':PREVIEW_BASE['manifest'].get('textSha256',{}).get(rel,PREVIEW_BASE['manifest']['files'][rel]),'afterSha256':hashlib.sha256(new.encode()).hexdigest(),'reused':True}
                if branch:record['branchHighImproved']=True
                else:record.update({'topic':topic,'supported':topic_state(area,topic)[2]})
                return p,new,record
    return improve_branch_high(*job) if branch else improve_page(job)


def refine_branch_intro(main,desc):
    leads=by_class(main,'jd-lead')
    assert len(leads)==1
    leads[0].text=desc
    # Topic-specific practice records should not distract from choosing a local
    # high-school course. Retain stable section IDs and course/fee facts.
    for section_id,heading,body in [
        ('study-start','고등 학습을 시작하기 전',
         '현재 이수 과목과 교재, 학교 평가 범위를 기준으로 학습 계획을 정리하세요. 최근 답안에서 혼자 해결한 부분과 도움이 필요한 부분을 나누고, 복습과 다음 진도 중 먼저 할 일을 상담에서 확인하세요. 실제 교재·과제·피드백 방식은 지점별 수업 조건을 기준으로 비교해야 합니다.'),
        ('review-plan','다음 복습에서 달라진 점 확인하기',
         '최근 틀린 수학 문제를 해설 없이 다시 풀어 보고, 혼자 설명할 수 있는 단계와 도움이 필요한 단계를 나눠 보세요. 같은 유형에서 조건을 놓치는지, 식을 세운 뒤 계산에서 틀리는지 기록하면 다음 상담에서 보완할 부분을 비교할 수 있습니다.'),
        ('consultation','답안을 가지고 물어볼 질문',
         '현재 학년과 이수 과목을 지도하는지, 교재와 진도는 어떻게 정하는지 먼저 물어보세요. 직접 푼 답안을 바탕으로 과제 확인·오답 피드백 방식과 수업 횟수·시간·비용을 함께 확인하세요.')]:
        nodes=main.xpath('.//section[@id="'+section_id+'"]')
        assert len(nodes)==1
        node=fragment(f'<section class="jd-section" id="{section_id}" aria-labelledby="{section_id}-title"><h2 id="{section_id}-title">{heading}</h2><p>{body}</p></section>')
        nodes[0].getparent().replace(nodes[0],node)


def improve_branch_high(p,area,legacy):
    raw=p.read_text(encoding='utf-8-sig');doc=html.fromstring(raw)
    main=doc.xpath('//main')[0]
    assert not main.get('data-naver-improved'), 'Already migrated branch high page'
    main.set('data-naver-improved',DAY)
    b=area['branch']; math_grades=[g for g in area['grades']['수학'] if g.startswith('고')]
    scope=grade_label(math_grades)
    bundle='국영수' if p.parent.parent.name.endswith('국영수학원') else '영어수학'
    desc=f'{area["area"]} 고등 {bundle}학원 안내로 {b["name"]}의 개설 학년·교육비와 수학 상담 준비를 확인하세요.'
    assert len(desc)<=80,(len(desc),desc)
    refine_branch_intro(main,desc)
    links=''.join(f'<a href="{H(legacy[(norm(area["area"]),grade)])}">{grade} 수학 '+('수강 안내' if grade in math_grades else '개설 여부 확인')+'</a>' for grade in ['고1','고2'])
    scope_text=f'{b["name"]} 자료에서 확인되는 고등 수학 학년은 {scope}입니다.' if math_grades else f'{b["name"]} 자료에서는 고등 수학 개설 학년이 확인되지 않습니다.'
    section=fragment(f'''<section class="jd-section ng-branch-math" id="manuscript-focus" aria-labelledby="manuscript-focus-title">
<p class="jd-kicker">수학 수강과 상담 준비</p><h2 id="manuscript-focus-title">{H(area['area'])} 고등 수학 수강 전 확인할 내용</h2>
<p>{H(scope_text)} 현재 모집과 시간표, 조건부 수강 여부는 지점에 문의해 주세요.</p>
<div class="ng-actions">{links}<a href="{H(b['route'])}#courses">{H(b['name'])} 전체 수강 학년</a></div>
<h3>학교 교재와 직접 푼 답안을 준비하세요</h3><p>현재 이수하는 수학 과목, 학교 교재와 평가 범위, 최근 오답을 함께 가져가세요. 개념 설명·조건 해석·계산 중 막히는 부분을 표시하면 필요한 복습과 다음 진도를 상담하기 좋습니다.</p>
<h3>과제와 피드백 방식을 물어보세요</h3><p>혼자 풀 수 있는 문제와 해설을 보고 푼 문제를 구분해 전달하세요. 지점에서는 어떤 방식으로 풀이를 확인하는지, 오답 재학습과 과제 조정은 어떻게 진행하는지 질문해 보세요.</p>
</section>''')
    focus=doc.get_element_by_id('manuscript-focus');focus.getparent().replace(focus,section)
    # Course facts and subject-specific navigation belong before large media.
    courses=doc.get_element_by_id('courses');wrap=courses.getparent()
    courses.getparent().remove(courses);section.getparent().remove(section)
    toc=by_class(wrap,'jd-toc')[0];index=list(wrap).index(toc)+1
    wrap.insert(index,courses);wrap.insert(index+1,section)
    faqs=doc.get_element_by_id('faq').xpath('.//details')
    assert len(faqs)==4,p
    q='고등 수학 상담에는 무엇을 준비하면 좋을까요?'
    a='현재 이수하는 수학 과목, 학교 교재와 평가 범위, 최근 직접 푼 답안을 준비해 주세요. 개념·조건 해석·계산 중 어려운 부분을 표시하고 개설 학년과 수업 조건을 먼저 확인하세요.'
    summary=faqs[2].xpath('./summary')[0];summary.clear();summary.text=q
    paras=faqs[2].xpath('./p');assert len(paras)==1
    paras[0].clear();paras[0].text=a
    for date in by_class(main,'jd-updated'):
        t=date.xpath('.//time')[0];t.text=DAY;t.set('datetime',DAY)
    graph=graph_of(doc)
    for node in graph:
        if node.get('@type') in ['WebPage','Article']:
            node['description']=desc;node['dateModified']=DAY
        if node.get('@type')=='Article':
            node['abstract']=scope_text+' 학교 교재와 직접 푼 답안을 준비해 수업 조건을 확인하세요.'
            node['articleSection']=['고등','수강 학년','수학 상담 준비','교육비']
        if node.get('@type')=='WebPage':
            for part in node.get('hasPart',[]):
                if str(part.get('@id','')).endswith('#manuscript-focus'):
                    part['name']=text(section.xpath('.//h2')[0])
        if node.get('@type')=='FAQPage':
            node['mainEntity'][2]={'@type':'Question','name':q,'acceptedAnswer':{'@type':'Answer','text':a}}
    new=re.sub(r'<main\b[^>]*>.*?</main>',lambda _:serialize(main),raw,count=1,flags=re.S)
    new=replace_metadata(new,desc,text(doc.xpath('//h1')[0]),{'@context':'https://schema.org','@graph':graph})
    return p,new,{'path':p.relative_to(ROOT).as_posix(),'description':desc,
                  'oldDescription':doc.xpath('string(//meta[@name="description"]/@content)'),
                  'mathRewritten':False,'branchHighImproved':True,'reviewsRemoved':0,
                  'branch':b['name'],'beforeSha256':hashlib.sha256(raw.encode()).hexdigest(),
                  'afterSha256':hashlib.sha256(new.encode()).hexdigest()}


def refresh_manifest(changed):
    p=ROOT/'release-public-manifest.json';manifest=json.loads(p.read_text(encoding='utf-8'))
    def hashes(rel):
        data=(ROOT/rel).read_bytes()
        raw=hashlib.sha256(data).hexdigest();normalized=None
        if Path(rel).suffix in ['.html','.css','.js','.json','.xml','.txt','.svg']:
            normalized=hashlib.sha256(data.decode('utf-8-sig').replace('\r\n','\n').encode()).hexdigest()
        return rel,raw,normalized
    with ThreadPoolExecutor(max_workers=12) as pool:
        for rel,raw,normalized in pool.map(hashes,changed):
            manifest['files'][rel]=raw
            if normalized:manifest.setdefault('textSha256',{})[rel]=normalized
    manifest['createdAt']=DAY
    save(p,manifest)


def update_sitemap(changed):
    p=ROOT/'sitemap.xml';doc=etree.fromstring(p.read_bytes());ns={'s':'http://www.sitemaps.org/schemas/sitemap/0.9'}
    selected={path_url(rel) for rel in changed if rel.endswith('index.html')}
    updated=0
    for node in doc:
        loc=node.find('s:loc',ns)
        if loc is not None and unquote(urlsplit(loc.text).path) in selected:
            last=node.find('s:lastmod',ns)
            if last is None:last=etree.SubElement(node,'{'+ns['s']+'}lastmod')
            last.text=DAY;updated+=1
    p.write_bytes(etree.tostring(doc,encoding='UTF-8',xml_declaration=True))
    assert updated==len(selected),(updated,len(selected))


def apply_reviewed(report,references):
    migration=json.loads((report/'migration.json').read_text(encoding='utf-8'))
    verification=json.loads((report/'verification-preview.json').read_text(encoding='utf-8'))
    assert verification['counts']['errors']==0 and verification['counts']['changedPages']==7791
    assert verification['migrationSha256']==sha(report/'migration.json'), 'Preview changed after verification'
    records=migration['pages'];assert len(records)==7791
    assert migration['summary']['sources']=={name:sha(references/name) for name in migration['summary']['sources']}
    def check_reviewed(item):
        original=(ROOT/item['path']).read_bytes()
        reviewed=(report/'preview'/item['path']).read_bytes()
        source_hashes={hashlib.sha256(original).hexdigest(),hashlib.sha256(original.decode('utf-8-sig').replace('\r\n','\n').encode()).hexdigest()}
        assert source_hashes & {item['beforeSha256'],item['afterSha256']}, ('source changed',item['path'])
        assert hashlib.sha256(reviewed.decode('utf-8-sig').replace('\r\n','\n').encode()).hexdigest()==item['afterSha256'], ('preview changed',item['path'])
    # Check every source before the first write. An interrupted application may
    # resume only when each file is still the baseline or this exact reviewed output.
    with ThreadPoolExecutor(max_workers=12) as pool:
        for i,_ in enumerate(pool.map(check_reviewed,records),1):
            if i%2000==0:print('Verified reviewed hashes',i,flush=True)
    config_path=ROOT/'seo-descriptions.json';config=json.loads(config_path.read_text(encoding='utf-8-sig'))
    if not (report/'before-release-manifest.json').exists():
        save(report/'before-release-manifest.json',json.loads((ROOT/'release-public-manifest.json').read_text(encoding='utf-8')))
    changed=[]
    def copy_reviewed(item):
        rel=item['path'];(ROOT/rel).write_bytes((report/'preview'/rel).read_bytes());return item
    with ThreadPoolExecutor(max_workers=12) as pool:
        for i,item in enumerate(pool.map(copy_reviewed,records),1):
            rel=item['path'];changed.append(rel)
            entry=config['pages'][path_url(rel).rstrip('/') or '/']
            entry['sources']=list(dict.fromkeys(entry['sources']+[item['oldDescription'],item['description']]))
            entry['description']=item['description']
            if i%1000==0:print('Applied reviewed pages',i,flush=True)
    save(config_path,config);update_sitemap(changed)
    refresh_manifest(changed+['sitemap.xml','assets/naver-region-guide.css'])
    save(report/'applied.json',{'pages':len(records),'branch':'codex/naver-improvements-20260928','date':DAY,'deployed':False})
    print('Applied',len(records),'reviewed pages. No deployment performed.',flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--references',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--apply-reviewed',action='store_true')
    parser.add_argument('--sample',action='store_true')
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    if args.apply_reviewed:
        assert not (args.apply or args.sample)
        return apply_reviewed(args.report,args.references)
    assert not (args.sample and args.apply), 'Sample mode is for preview only.'
    areas,branches,source_hashes=data_from_sources(args.references)
    jobs=map_pages(areas)
    summary={'areas':len(areas),'mappedCenters':len({a['branch']['route'] for a in areas}),
             'branchPages':len(branches),'legacyPages':len(jobs),'sources':source_hashes,
             'mode':'apply' if args.apply else 'preview'}
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    if args.sample:
        jobs=[job for job in jobs if job[1]['area'] in ['명일동','식사동','사우동','다산동'] and (job[2] in ['고1수학','고2수학','중1수학','학원'])]
    results=[];changed=[]
    config_path=ROOT/'seo-descriptions.json';config=json.loads(config_path.read_text(encoding='utf-8-sig'))
    global PREVIEW_BASE
    PREVIEW_BASE={'config':config,'manifest':json.loads((ROOT/'release-public-manifest.json').read_text(encoding='utf-8'))}
    legacy={(norm(a['area']),grade):path_url(p.relative_to(ROOT).as_posix()) for p,a,t in jobs for grade in ['고1','고2'] if t==grade+'수학'}
    branch_jobs=[]
    for p in sorted((ROOT/'지점안내').glob('*/*/*/고등/index.html')):
        route='/'+p.parents[2].relative_to(ROOT).as_posix()+'/'
        name=p.parent.parent.name.removesuffix('영어수학학원').removesuffix('국영수학원')
        found=[a for a in areas if a['branch']['route']==route and norm(a['area'])==norm(name)]
        assert len(found)==1,('branch high mapping',p)
        if args.sample and norm(found[0]['area']) not in ['명일동','식사동','사우동','다산동']:continue
        branch_jobs.append((p,found[0],legacy))
    assert len(branch_jobs)==(8 if args.sample else 742),len(branch_jobs)
    all_jobs=[(job,False) for job in jobs]+[(job,True) for job in branch_jobs]
    def render(item):
        job,branch=item
        if args.resume:return resume_page(job,args.report,branch)
        return improve_branch_high(*job) if branch else improve_page(job)
    with ThreadPoolExecutor(max_workers=12) as pool:
      for offset in range(0,len(all_jobs),250):
        for p,new,record in pool.map(render,all_jobs[offset:offset+250]):
            i=len(results)+1
            rel=p.relative_to(ROOT).as_posix();results.append(record)
            if args.apply:
                p.write_text(new,encoding='utf-8');changed.append(rel)
                key=path_url(rel).rstrip('/') or '/';entry=config['pages'][key]
                entry['sources']=list(dict.fromkeys(entry['sources']+[record['oldDescription'],record['description']]))
                entry['description']=record['description']
            else:
                out=args.report/'preview'/rel
                if not record.get('reused'):
                    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(new,encoding='utf-8')
            if i%500==0:print('Processed',i,flush=True)
        save(args.report/'migration-progress.json',{'processed':len(results),'expected':len(all_jobs)})
    summary.update({'processed':len(results),'reviewsRemoved':sum(r['reviewsRemoved'] for r in results),
                    'mathRewritten':sum(r['mathRewritten'] for r in results),
                    'mathNeedsConfirmation':sum(r['mathRewritten'] and not r['supported'] for r in results),
                    'branchHighImproved':sum(r.get('branchHighImproved',False) for r in results),
                    'addressUpdatedAreas':sum(a['addressUpdated'] for a in areas)})
    if args.apply:
        assert not args.sample, 'Sample mode is for preview only.'
        save(config_path,config);update_sitemap(changed)
        refresh_manifest(changed+['sitemap.xml','assets/naver-region-guide.css'])
    save(args.report/'migration.json',{'summary':summary,'pages':results})
    assert source_hashes=={name:sha(args.references/name) for name in source_hashes}, 'Reference files changed'
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
