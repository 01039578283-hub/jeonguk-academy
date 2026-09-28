"""Reviewable phase 2: source-bound management profiles and honest photo labels.

Preview by default. --apply copies only reviewed bytes after checking all source
hashes. No network, Git publishing, student records or live operating claims.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import format_datetime
from html import escape
from pathlib import Path
from urllib.parse import unquote

import openpyxl
from lxml import etree, html
from center_management_content import MANAGEMENT
from improve_naver_pages import refresh_manifest, update_sitemap

ROOT = Path(__file__).resolve().parents[1]
DAY = '2026-09-28'
MARKER = 'data-center-content'
HIGH_EXCLUSIONS = {'가경점', '관평점', '마두점', '첨단점', '치평점'}
E = escape


def load(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(b): return hashlib.sha256(b).hexdigest()
def save(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def norm(s): return re.sub(r'\s+', '', str(s or ''))
def text(n): return ' '.join(n.text_content().split())
def fragment(s): return html.fragment_fromstring(s)
def serialize(n): return html.tostring(n, encoding='unicode', with_tail=False)
def byclass(n, cls):
    return n.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," '+cls+' ")]')
def graph(d):
    scripts=d.xpath('//script[@type="application/ld+json"]')
    assert len(scripts)==1
    return scripts[0], json.loads(scripts[0].text)


def inventory(args):
    centers=load(args.centers)['centers']
    assert len(centers)==193
    wb=openpyxl.load_workbook(args.references/'코칭센터_데이터_.xlsx', read_only=True, data_only=True)
    rows={str(r[0]):(i,r) for i,r in enumerate(wb['센터정보'].values,1) if i>1 and r[0]}
    assert len(rows)==203
    evidence=[]
    for c in centers:
        candidates=[(name,i,r) for name,(i,r) in rows.items()
                    if norm(r[6])==norm(c['registeredName']) and norm(r[11])==norm(c['address'])]
        assert len(candidates)==1 or c['key']=='화성태안점', (c['key'],len(candidates))
        if not candidates:continue
        source_name,i,r=candidates[0]
        c['workbookRow']=i
        c['profile']=None
        if source_name not in MANAGEMENT:continue
        topic,body,quotes=MANAGEMENT[source_name]
        assert all(norm(q) in norm(r[29]) for q in quotes), ('unsupported profile',source_name,quotes)
        assert len(body)>30 and not re.search(r'OO학생|ㅇㅇ학생|성적향상|성적 향상|유지율|최우수|전문강사|10년',body)
        c['profile']={'topic':topic,'body':body}
        evidence.append({'branch':c['routeName'],'path':c['path'],'workbookRow':i,'cell':f'AD{i}',
                         'topic':topic,'body':body,'sourceExcerpts':quotes,
                         'highLink':c['key'] not in HIGH_EXCLUSIONS})
    wb.close()
    assert len({c['path'] for c in centers})==193
    return centers,evidence


def profile_section(c):
    n=c['routeName'];p=c['profile']
    return fragment(f'''<section class="jd-section cc-management" id="learning-management" aria-labelledby="learning-management-title">
<p class="jd-kicker">수업과 피드백</p><h2 id="learning-management-title">{E(n)} 학습관리 안내</h2>
<h3>{E(p['topic'])}</h3><p class="cc-profile-body">{E(p['body'])}</p>
<p class="cc-source-note">센터 소개 자료에 기재된 관리 방식입니다. 적용 과목·학년과 현재 운영은 상담에서 확인해 주세요.</p>
<a class="jd-link" href="#courses">{E(n)} 수강 학년 확인<span aria-hidden="true"> ↗</span></a>
</section>''')


def render_branch(raw,c):
    d=html.fromstring(raw);main=d.xpath('//main')[0]
    assert main.get(MARKER) is None, 'Use the saved preview for an interrupted application'
    main.set(MARKER,DAY)
    script,structured=graph(d)
    org=next(n for n in structured['@graph'] if 'EducationalOrganization' in n.get('@type',[]))
    assert norm(org['name'])==norm(c['registeredName'])
    assert norm(org['address']['streetAddress'])==norm(c['address'])
    media=main.get_element_by_id('learning-materials');wrap=media.getparent()
    courses=main.get_element_by_id('courses')
    # Keep the media section and image sequence intact, after the factual text.
    wrap.remove(media)
    fees=main.get_element_by_id('fees');wrap.insert(list(wrap).index(fees)+1,media)
    photos={m['src']:m for m in c['photos']}
    assert len(photos)==len(c['photos'])
    found=[]
    for img in main.xpath('.//img[@src]'):
        m=photos.get(img.get('src'))
        if m is None:continue
        found.append(img.get('src'))
        figure=img.getparent()
        assert figure.tag=='figure'
        cap=figure.find('figcaption');assert cap is not None
        i=list(photos).index(img.get('src'))+1
        label=f'{c["routeName"]} 제공 사진 {i}' if m['mode']=='center' else f'공용 학습 공간 예시 {i} · {c["routeName"]} 실제 사진 아님'
        img.set('alt',label);cap.text=label
        figure.set('data-photo-source',m['mode'])
    assert Counter(found)==Counter(photos.keys()), (c['key'],'photo mismatch')
    common=all(m['mode']=='common' for m in c['photos'])
    assert common or all(m['mode']=='center' for m in c['photos'])
    notice=('아래 학습 공간 사진은 공용 예시입니다. '+c['routeName']+'의 실제 모습은 방문 전 확인해 주세요.' if common else
            c['routeName']+' 폴더로 제공된 사진입니다. 촬영 시점과 현재 공간 구성이 다를 수 있습니다.')
    # A visible notice precedes images, so the distinction is useful on mobile.
    media.insert(2,fragment('<p class="cc-photo-note">'+E(notice)+'</p>'))
    gal=main.xpath('.//section[@id="learning-space"]')
    if gal:
        heading=gal[0].xpath('./h2')[0]
        heading.text='공용 학습 공간 예시 더 보기' if common else c['routeName']+' 제공 사진 더 보기'
    for meta in d.xpath('//meta[@property="og:image:alt"]'):
        meta.set('content',c['routeName']+' 안내 · 공용 학습 공간 예시' if common else c['routeName']+' 제공 학습 공간 사진')
    page=next(n for n in structured['@graph'] if n.get('@type')=='WebPage')
    if 'primaryImageOfPage' in page:
        page['primaryImageOfPage']['caption']=notice
    before_desc=d.xpath('string(//meta[@name="description"]/@content)')
    desc=before_desc
    if c.get('profile'):
        wrap.insert(list(wrap).index(courses)+1,profile_section(c))
        toc=byclass(main,'jd-toc')[0]
        toc.insert(2,fragment('<a class="jd-link" href="#learning-management">학습관리 방식<span aria-hidden="true"> ↗</span></a>'))
        desc=f'{c["region"]} {c["district"]} {c["routeName"]}의 {c["profile"]["topic"]}, 과목별 수강 학년·주소·교육비를 안내합니다.'
        desc=' '.join(desc.split())
        assert 25<=len(desc)<=80,(c['key'],len(desc))
        for meta in d.xpath('//meta[@name="description" or @property="og:description" or @name="twitter:description"]'):
            meta.set('content',desc)
        byclass(main,'jd-lead')[0].text=desc
        page['description']=desc
    page['dateModified']=DAY
    page['hasPart']=[{'@type':'WebPageElement','@id':page['url']+'#'+n.get('id'),'name':text(n.xpath('.//h2')[0])}
                     for n in main.xpath('.//section[@id]') if n.xpath('.//h2')]
    for t in byclass(main,'jd-updated'):
        for x in t.xpath('./time'):x.set('datetime',DAY);x.text=DAY
    head=d.xpath('//head')[0]
    head.append(fragment('<link rel="stylesheet" href="/assets/center-content.css?v=20260928">'))
    script.text=json.dumps(structured,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    out=re.sub(r'<head\b[^>]*>.*?</head>',lambda m:serialize(head),raw,count=1,flags=re.S)
    out=re.sub(r'<main\b[^>]*>.*?</main>',lambda m:serialize(main),out,count=1,flags=re.S)
    return out,{'branch':c['routeName'],'branchPage':True,'profile':bool(c.get('profile')),
                'commonPhotos':common,'oldDescription':before_desc,'description':desc}


def render_link(raw,c,old_record):
    d=html.fromstring(raw);main=d.xpath('//main')[0]
    assert main.get(MARKER) is None
    main.set(MARKER,DAY)
    section=main.get_element_by_id('manuscript-focus' if old_record.get('branchHighImproved') else 'center-summary')
    # Do not reinterpret a general center profile as a confirmed high-school class.
    block=fragment('<p class="cc-profile-link"><a href="'+E(c['path'])+'#learning-management">'+E(c['routeName']+'의 '+c['profile']['topic'])+' 안내 보기</a> · 해당 학년의 적용 여부는 상담에서 확인해 주세요.</p>')
    section.append(block)
    out=re.sub(r'<main\b[^>]*>.*?</main>',lambda m:serialize(main),raw,count=1,flags=re.S)
    return out,{'branch':c['routeName'],'branchPage':False,'profileTarget':c['path']+'#learning-management'}


def preview(args):
    assert not (args.report/'phase2.json').exists(), 'Keep existing evidence; choose a fresh report directory'
    centers,evidence=inventory(args);byname={c['routeName']:c for c in centers}
    migration=load(args.phase1/'migration.json')
    jobs=[(c['path'].strip('/')+'/index.html',c,None) for c in centers]
    for item in migration['pages']:
        c=byname[item['branch']]
        if (item['mathRewritten'] or item.get('branchHighImproved')) and c.get('profile') and c['key'] not in HIGH_EXCLUSIONS:
            jobs.append((item['path'],c,item))
    inputs=[args.centers,args.references/'코칭센터_데이터_.xlsx',ROOT/'tools/center_management_content.py']
    sources={str(p):digest(p.read_bytes()) for p in inputs}
    records=[]
    def render(job):
        rel,c,old=job;before=(ROOT/rel).read_bytes();raw=before.decode('utf-8-sig')
        out,record=render_link(raw,c,old) if old else render_branch(raw,c)
        after=(out.rstrip()+'\n').encode('utf-8')
        record.update(path=rel,beforeSha256=digest(before),afterSha256=digest(after))
        for sub,content in [('before',before),('preview',after)]:
            p=args.report/sub/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content)
        return record
    with ThreadPoolExecutor(max_workers=12) as pool:
        records=list(pool.map(render,jobs))
    save(args.report/'phase2.json',{'date':DAY,'sources':sources,'profiles':evidence,'pages':records,
        'summary':{'branchPages':193,'profiles':len(evidence),'profileLinks':len(records)-193,
                   'commonPhotoBranches':sum(r.get('commonPhotos',False) for r in records),
                   'actualPhotoBranches':sum(r.get('branchPage',False) and not r.get('commonPhotos') for r in records)}})
    # Only source excerpts used in public copy are exported for editorial review.
    lines=['# 지점 학습관리 반영 근거','', '원본: 코칭센터_데이터_.xlsx / 센터정보 시트 / 센터강점(AD열). 현재 운영을 새로 확인한 자료는 아닙니다.','']
    for e in evidence:
        lines += [f'## {e["branch"]} · {e["cell"]}', '', e['body'], '', '**원문 근거:** '+ ' / '.join(e['sourceExcerpts']), '']
    (args.report/'학습관리_반영근거.md').write_text('\n'.join(lines),encoding='utf-8')
    missing=[c for c in centers if not c.get('profile')]
    lines=['# 다음에 확보할 지점 자료','',f'학습관리 설명을 보강한 지점: {len(evidence)}곳. 이번에 사용할 구체적인 설명을 확보하지 못한 지점: {len(missing)}곳.','',
           '아래 항목은 담당자가 현재 운영을 확인한 뒤 채울 자료입니다. 외부 연락이나 자료 요청 발송은 하지 않았습니다.','',
           '- 적용 학년과 수학 선택 과목, 현재 모집 여부와 적용일',
           '- 사용하는 교재와 선택 기준, 과제 확인·오답 재풀이 절차',
           '- 학부모 피드백 주기와 공개 가능한 익명 예시',
           '- 교습비·수업 횟수·시간·추가 비용',
           '- 현재 지점 사진과 촬영일, 공개 사용 가능 여부','',
           '## 학습관리 설명 추가 확인 대상','', ' · '.join(c['routeName'] for c in missing),'',
           '## 실제 지점 사진 추가 확보 대상','', ' · '.join(c['routeName'] for c in centers if all(p['mode']=='common' for p in c['photos'])),'',
           '고등 수학 운영 미확인 23개 지점·62페이지는 1차 확인 목록을 유지합니다. 이 자료로 개설 범위를 넓히지 않았습니다.']
    (args.report/'다음_자료확인목록.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(load(args.report/'phase2.json')['summary'],ensure_ascii=False),flush=True)


def apply(args):
    report=load(args.report/'phase2.json')
    for p,sha in report['sources'].items():assert digest(Path(p).read_bytes())==sha,('input changed',p)
    def verify(r):
        assert digest((ROOT/r['path']).read_bytes()) in {r['beforeSha256'],r['afterSha256']},('source changed',r['path'])
        assert digest((args.report/'preview'/r['path']).read_bytes())==r['afterSha256'],('preview changed',r['path'])
    with ThreadPoolExecutor(max_workers=12) as pool:list(pool.map(verify,report['pages']))
    for name in ['release-public-manifest.json','seo-descriptions.json','sitemap.xml','branch-updates.xml']:
        p=args.report/'before'/name
        if not p.exists():p.write_bytes((ROOT/name).read_bytes())
    config=load(ROOT/'seo-descriptions.json');changed=[]
    def copy(r):
        (ROOT/r['path']).write_bytes((args.report/'preview'/r['path']).read_bytes())
        return r['path']
    with ThreadPoolExecutor(max_workers=12) as pool:changed=list(pool.map(copy,report['pages']))
    descs={}
    for r in report['pages']:
        if not r.get('branchPage'):continue
        route='/'+r['path'].removesuffix('index.html');descs[route]=r['description']
        entry=config['pages'][route.rstrip('/')]
        entry['description']=r['description']
        entry['sources']=list(dict.fromkeys(entry['sources']+[r['oldDescription'],r['description']]))
    save(ROOT/'seo-descriptions.json',config);update_sitemap(changed)
    rss=etree.fromstring((ROOT/'branch-updates.xml').read_bytes());count=0
    for item in rss.findall('./channel/item'):
        route=unquote(item.findtext('link')).replace('https://xn--3e0bl59bm0ad17a.com','')
        if route in descs:
            item.find('description').text=descs[route];count+=1
            item.find('pubDate').text=format_datetime(datetime.now(timezone.utc))
    if count:
        rss.find('./channel/lastBuildDate').text=format_datetime(datetime.now(timezone.utc))
        (ROOT/'branch-updates.xml').write_text(etree.tostring(rss,encoding='unicode',pretty_print=True),encoding='utf-8')
    refresh_manifest(changed+['sitemap.xml','branch-updates.xml','assets/center-content.css'])
    save(args.report/'applied.json',{'date':DAY,'pages':len(changed),'rssItems':count,'deployed':False})
    print('Applied reviewed phase 2 pages:',len(changed),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--references',type=Path,required=True)
    p.add_argument('--centers',type=Path,required=True);p.add_argument('--phase1',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True);p.add_argument('--apply',action='store_true')
    args=p.parse_args();args.report.mkdir(parents=True,exist_ok=True)
    apply(args) if args.apply else preview(args)
