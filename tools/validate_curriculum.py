"""Verify workbook coverage, contextual destinations, and full preservation."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from urllib.parse import unquote, urlsplit
from html import unescape
import argparse, hashlib, json, re, subprocess, zipfile
from lxml import html, etree

SOURCE=Path(__file__).resolve().parents[1]
DOMAIN='https://xn--3e0bl59bm0ad17a.com'
WORKBOOK=Path(r'C:\Users\1992k\Desktop\홈페이지 작업 폴더\센터정보\초중고_학년과목별_공부커리큘럼_기초표준심화.xlsx')
AUTHOR=Path(r'C:\Users\1992k\Desktop\홈페이지 작업 폴더\홈페이지 정리\새 홈페이지')
sha=lambda b:hashlib.sha256(b).hexdigest()
def load(p):return json.loads(p.read_text('utf-8-sig'))
def require(condition,message,errors):
    if not condition:errors.append(message)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=SOURCE);parser.add_argument('--report-dir',type=Path,required=True);parser.add_argument('--report-name',default='validation.json');parser.add_argument('--homepage-review',type=Path);args=parser.parse_args();root=args.root;out=args.report_dir
    errors=[];pages=load(out/'pages.json');mappings=load(out/'link-mapping.json');mapped={v['page']:v for v in mappings}
    manifest=load(SOURCE/'release-public-manifest.json');old_manifest=load(out/'before-release-public-manifest.json');catalog=load(SOURCE/'tools/curriculum_catalog.json')
    sheets={s['name']:s['records'] for s in catalog['sheets']}
    require(sha(WORKBOOK.read_bytes())==catalog['sha256'],'Original workbook changed',errors)
    require(len(pages)==84 and sum(v['kind']=='subject' for v in pages.values())==66,'New curriculum page coverage differs',errors)
    with zipfile.ZipFile(out/'before-pages.zip') as archive:originals={n:archive.read(n) for n in archive.namelist()}
    require(len(originals)==10636,'Existing page baseline differs',errors)
    home_review=load(args.homepage_review) if args.homepage_review else None
    if home_review:
        require(home_review.get('path')=='index.html' and home_review.get('originalSha256')==sha(originals['index.html']),'Homepage review baseline differs',errors)
        require(home_review.get('approvedSourceSha256')==sha((SOURCE/'index.html').read_bytes()),'Homepage differs from separately reviewed update',errors)
    def preservation(name):
        raw=(SOURCE/name).read_bytes();expected=originals[name]
        if name in mapped:
            text=raw.decode('utf-8');count=text.count('<!-- curriculum-link:start -->')
            if count!=1:return name+' has wrong contextual link count'
            stripped=re.sub(r'<!-- curriculum-link:start -->[\s\S]*?<!-- curriculum-link:end -->','',text).replace('<link rel="stylesheet" href="/assets/curriculum.css?v=20261003">','').encode('utf-8')
            if stripped!=expected and not (name=='index.html' and home_review and home_review.get('approvedSourceSha256')==sha(raw)):return name+' changed existing content'
            module=re.search(r'<!-- curriculum-link:start -->(.*?)<!-- curriculum-link:end -->',text,re.S)[1]
            doc=html.fromstring(module);hrefs=[unquote(unescape(p)) for p in doc.xpath('//a/@href')]
            record=mapped[name]
            if hrefs!=[record['target'],record['levelTarget']]:return name+' has wrong learning destination'
            segments=name.split('/')[:-1]
            tokens=[re.match(r'^(초[1-6]|중[1-3]|고[1-3])(국어|영어|수학|사회|과학|역사)',s) for s in segments]
            tokens=[v for v in tokens if v]
            if tokens:
                token=tokens[-1];correct='/학습커리큘럼/'+token[1]+'/'+token[2]+'/'
                if hrefs[0]!=correct:return name+' leads to another grade or subject'
            else:
                stage=next((s for s in reversed(segments) if s in ('초등','중등','고등')),None)
                if stage and hrefs[0]!='/학습커리큘럼/'+stage+'/':return name+' leads to another school level'
            if 'data-curriculum-bridge' not in (root/name).read_text('utf-8'):return name+' built contextual link missing'
        elif raw!=expected:return name+' was changed outside requested scope'
        return None
    with ThreadPoolExecutor(max_workers=12) as pool:
        for index,problem in enumerate(pool.map(preservation,originals),1):
            if problem:errors.append(problem)
            if index%3000==0:print(json.dumps({'preservedPagesChecked':index,'errors':len(errors)}),flush=True)
    expected_targets={n for n in originals if n.startswith(('전국학원/','과목별학원/','지점안내/')) or n in ('index.html','교육정보/index.html','학습가이드/index.html')}
    require(set(mapped)==expected_targets and len(mapped)==10331,'Requested internal link coverage differs',errors)
    checked_destinations=set();docs={}
    def document(name):
        if name not in docs:docs[name]=html.fromstring((root/name).read_bytes())
        return docs[name]
    def destination(url,origin):
        parts=urlsplit(url)
        if parts.scheme not in ('','http','https') or (parts.netloc and parts.netloc not in ('xn--3e0bl59bm0ad17a.com','전국학원.com')):return
        path=unquote(parts.path)
        if not path:name=origin
        elif path.startswith('/'):name=path.lstrip('/')+('index.html' if path.endswith('/') or path=='/' else '')
        else:
            name=(Path(origin).parent/path).as_posix()
            if name.endswith('/'):name+='index.html'
        if name in ('assets/wawa-analytics.js','wawa-analytics.js') or name.startswith('_wawa'):return
        key=(name,unquote(parts.fragment))
        if key in checked_destinations:return
        checked_destinations.add(key)
        require(name in manifest['files'],origin+' links outside public manifest: '+url,errors)
        require((root/name).is_file(),origin+' destination is missing: '+url,errors)
        if (root/name).is_file() and parts.fragment and name.endswith('.html'):
            require(bool(document(name).xpath('//*[@id=$id]',id=unquote(parts.fragment))),origin+' anchor missing: '+url,errors)
    descriptions=[];minimum=100000
    for name,page in pages.items():
        doc=document(name);raw=(root/name).read_text('utf-8');body=doc.xpath('//body')[0]
        require(len(doc.xpath('//h1'))==1,name+' H1 count differs',errors)
        require(unquote(doc.xpath('//link[@rel="canonical"]/@href')[0])==DOMAIN+page['path'],name+' canonical differs',errors)
        desc=doc.xpath('//meta[@name="description"]/@content')[0];descriptions.append(desc)
        require(desc==page['description'] and len(desc)<=80 and desc.endswith('.'),name+' description differs',errors)
        for attribute,value in [('data-curriculum-kind',page['kind']),('data-curriculum-grade',page['grade'] or ''),('data-curriculum-subject',page['subject'] or '')]:require(body.get(attribute)==value,name+' page identity differs',errors)
        for attribute,needle in [('property','og:description'),('name','twitter:description')]:require(doc.xpath('//meta[@'+attribute+'=$needle]/@content',needle=needle)==[desc],name+' social description differs',errors)
        require('편집 원칙' not in raw and 'C:\\Users\\' not in raw,name+' internal authoring information exposed',errors)
        ids=doc.xpath('//*[@id]/@id');require(len(ids)==len(set(ids)),name+' duplicate anchors',errors)
        for script in doc.xpath('//script[@type="application/ld+json"]/text()'):
            graph=json.loads(script).get('@graph',[])
            for node in graph:
                if node.get('@type') in ('Article','WebPage','CollectionPage'):require(node.get('description')==desc,name+' structured description differs',errors)
        for url in doc.xpath('//@href|//img/@src|//script/@src'):destination(url,name)
        if page['kind']=='subject':
            sheet='초등과목' if page['grade'].startswith('초') else '중등과목' if page['grade'].startswith('중') else '고등과목'
            record=next(r for r in sheets[sheet] if r['values']['학년']==page['grade'] and r['values']['과목']==page['subject']);v=record['values']
            text=' '.join(doc.xpath('//main')[0].itertext())
            require(v['주요 학습 중점(편집)'] in text and v['확인 과제(예시)'] in text and v['학교별 조정'] in text,name+' workbook learning content omitted',errors)
            steps=doc.xpath('//*[@id="sequence"]//li/strong/text()')
            require(steps==[s.strip() for s in v['권장 순서(예시)'].split('→')],name+' workbook learning sequence differs',errors)
            cards=doc.xpath('//*[@id="levels"]//*[@data-level]')
            require([card.get('data-level') for card in cards]==['기초','표준','심화'],name+' learning levels incomplete',errors)
            require(v['2026 적용'] in text,name+' curriculum cohort differs',errors)
            minimum=min(minimum,len(re.sub(r'\s+','',text)))
            if page['grade'] in ('초1','초2') and page['subject']=='영어':require('영어 선택 활동' in ''.join(doc.xpath('//h1')[0].itertext()),name+' optional early English distinction missing',errors)
            if page['grade'] in ('초1','초2') and page['subject'] in ('사회','과학'):require('통합교과' in ''.join(doc.xpath('//h1')[0].itertext()),name+' integrated early subject distinction missing',errors)
            if page['grade'] in ('중3','고3'):require('2027학년도' in text and '2015 개정' in text,name+' cohort transition distinction missing',errors)
    require(len(descriptions)==len(set(descriptions)),'New page descriptions duplicate',errors)
    level_doc=document('학습커리큘럼/학습단계선택/index.html')
    level_cards=level_doc.xpath('//*[@data-level]')
    require(len(level_cards)==45,'All workbook level examples not present',errors)
    require({int(c.get('data-level-row')) for c in level_cards}=={r['row'] for r in sheets['반별운영']},'Workbook level row coverage differs',errors)
    for card in level_cards:
        v=next(r['values'] for r in sheets['반별운영'] if r['row']==int(card.get('data-level-row')));text=' '.join(card.itertext())
        require(all(v[k] in text for k in ['대상(예시)','학습 순서(예시)','확인 과제(예시)','다음 단계 판단(예시)']),'Learning stage source example changed',errors)
    elective_doc=document('학습커리큘럼/고등선택과목/index.html');electives=elective_doc.xpath('//*[@data-elective-card]')
    require(len(electives)==29,'Elective example coverage differs',errors)
    for card in electives:
        row=int(card.get('data-workbook-row'));v=next(r['values'] for r in sheets['고등선택과목'] if r['row']==row);text=' '.join(card.itertext())
        require(all(v[k] in text for k in ['과목명','공식 내용 범위 요약','선이수·준비 개념','권장 학습 연결(예시)']),'Elective source content changed: '+v['과목명'],errors)
    sitemap=etree.fromstring((root/'sitemap.xml').read_bytes());urls=sitemap.findall('{http://www.sitemaps.org/schemas/sitemap/0.9}url')
    paths=[unquote(url.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc').text).removeprefix(DOMAIN).lstrip('/')+'index.html' for url in urls]
    require(len(paths)==10720 and len(paths)==len(set(paths)),'Sitemap URL count or uniqueness differs',errors)
    require(set(paths)==set(originals)|set(pages),'Sitemap scope differs',errors)
    old_config=load(out/'before-seo-descriptions.json');config=load(SOURCE/'seo-descriptions.json')
    require(all(config['pages'].get(k)==v for k,v in old_config['pages'].items() if not (k=='/' and home_review)),'Existing description configuration changed',errors)
    if home_review:
        require(sha(json.dumps(config['pages']['/'],ensure_ascii=False,sort_keys=True).encode('utf-8'))==home_review.get('approvedDescriptionEntrySha256'),'Homepage description differs from separately reviewed update',errors)
    changed=set(load(out/'generation.json')['publicChanges'])
    require(all(manifest['files'].get(n)==value for n,value in old_manifest['files'].items() if n not in changed),'Unrelated public asset hash changed',errors)
    require(not any(n.startswith('tools/') or n.endswith(('.xlsx','.zip','.py')) for n in manifest['files']),'Private curriculum sources included publicly',errors)
    status=subprocess.check_output(['git','status','--porcelain=v1','-z','--untracked-files=all'],cwd=AUTHOR)
    before=load(out/'authoring-before.json');source_unchanged=sha(status)==before['statusSha256']
    require(source_unchanged,'Authoring checkout status changed during work',errors)
    result=dict(root=str(root),newPages=len(pages),subjectPages=66,gradePages=12,learningExamples=45,electiveExamples=29,existingPagesPreserved=len(originals)-(1 if home_review else 0),separatelyReviewedHomepage=bool(home_review),linkedExistingPages=len(mapped),internalDestinationsChecked=len(checked_destinations),sitemapPages=len(paths),minimumSubjectMainCharacters=minimum,workbookUnchanged=True,authoringSourceUnchanged=source_unchanged,errorCount=len(errors),errors=errors[:40])
    (out/args.report_name).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
    if errors:raise SystemExit(1)
if __name__=='__main__':main()
