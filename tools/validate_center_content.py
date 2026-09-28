"""Phase 2 regression checks against saved source bytes and editorial evidence."""
import argparse
import copy
import hashlib
import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote, urlsplit, urljoin
from lxml import html

from improve_center_content import ROOT, DAY, MARKER, load, save, text, byclass


def check_page(raw,before,record,profile,photo_mode=None):
    d=html.fromstring(raw);old=html.fromstring(before);main=d.xpath('//main')[0];issues=[]
    def require(ok,why):
        if not ok:issues.append(why)
    require(main.get(MARKER)==DAY,'phase 2 marker')
    for xpath,label in [('//link[@rel="canonical"]/@href','canonical'),('//meta[@name="robots"]/@content','robots'),
                        ('//title/text()','title'),('//h1/text()','H1')]:
        require(d.xpath(xpath)==old.xpath(xpath),'changed '+label)
    for tag in ['header','footer']:
        require(re.findall(r'<'+tag+r'\b.*?</'+tag+'>',raw,re.S)==re.findall(r'<'+tag+r'\b.*?</'+tag+'>',before,re.S),tag+' changed')
    require(Counter(d.xpath('//img/@src'))==Counter(old.xpath('//img/@src')),'image inventory changed')
    require([(i.get('src'),i.get('width'),i.get('height')) for i in d.xpath('//img')]==
            [(i.get('src'),i.get('width'),i.get('height')) for i in old.xpath('//img')],'image sequence/dimensions changed')
    old_graph=json.loads(old.xpath('//script[@type="application/ld+json"]')[0].text)['@graph']
    graph=json.loads(d.xpath('//script[@type="application/ld+json"]')[0].text)['@graph']
    for kind in ['Service','FAQPage','BreadcrumbList']:
        require([n for n in graph if n.get('@type')==kind]==[n for n in old_graph if n.get('@type')==kind],kind+' changed')
    org=lambda ns:[n for n in ns if 'EducationalOrganization' in n.get('@type',[])]
    require(org(graph)==org(old_graph),'center identity/claims changed')
    desc=d.xpath('//meta[@name="description"]/@content')
    require(len(desc)==1 and 1<=len(desc[0])<=80,'description length/count')
    require(desc==d.xpath('//meta[@property="og:description"]/@content')==d.xpath('//meta[@name="twitter:description"]/@content'),'description alignment')
    require(all(n.get('description')==desc[0] for n in graph if n.get('@type') in ['WebPage','Article']),'page schema description')
    ids=d.xpath('//*[@id]/@id');require(len(ids)==len(set(ids)),'duplicate ids')
    for href in d.xpath('//a[starts-with(@href,"#")]/@href'):
        require(unquote(href[1:]) in ids,'missing anchor '+href)
    if record['branchPage']:
        for section in ['center-facts','courses','schools','fees','consultation','faq']:
            require([text(n) for n in main.xpath('.//section[@id="'+section+'"]')]==
                    [text(n) for n in old.xpath('//main//section[@id="'+section+'"]')],section+' facts changed')
        sections=main.xpath('.//section/@id')
        require(sections.index('courses')<sections.index('learning-materials'),'images before course facts')
        require(len(d.xpath('//link[contains(@href,"/assets/center-content.css")]'))==1,'stylesheet missing/duplicate')
        if profile:
            nodes=main.xpath('.//section[@id="learning-management"]')
            require(len(nodes)==1,'profile coverage')
            if nodes:
                require(text(byclass(nodes[0],'cc-profile-body')[0])==profile['body'],'profile differs from reviewed source copy')
                require(nodes[0].xpath('string(.//h3)')==profile['topic'],'profile topic mismatch')
                require('적용 과목·학년과 현재 운영은 상담에서 확인' in text(nodes[0]),'source qualification missing')
                require(sections.index('learning-management')<sections.index('learning-materials'),'profile after images')
        else:require(not main.xpath('.//*[@id="learning-management"]'),'unsupported profile added')
        figures=main.xpath('.//figure[@data-photo-source]')
        old_photos=old.xpath('//section[@id="learning-space"]//figure | //section[@id="learning-materials"]//figure[1]')
        require(len(figures)==len(old_photos),'photo source coverage')
        common=record['commonPhotos']
        for f in figures:
            caption=text(f.find('figcaption'));alt=f.xpath('string(.//img/@alt)')
            require(caption==alt,'image text differs')
            require(f.get('data-photo-source')==('common' if common else 'center'),'photo source mode')
            require(('실제 사진 아님' in caption)==common,'common photo represented as branch')
        require(('공용 예시' in text(byclass(main,'cc-photo-note')[0]))==common,'photo notice mismatch')
        page=next(n for n in graph if n.get('@type')=='WebPage')
        parts={unquote(n['@id']).split('#')[-1]:n['name'] for n in page['hasPart']}
        require(parts=={n.get('id'):text(n.xpath('.//h2')[0]) for n in main.xpath('.//section[@id]') if n.xpath('.//h2')},'schema sections differ from headings')
    else:
        require(desc==old.xpath('//meta[@name="description"]/@content'),'detail description changed')
        comparison=copy.deepcopy(graph)
        if main.get('data-center-visit')==DAY:
            # Phase 3 adds only the reviewed photo caption to these phase 2
            # detail schemas. Keep every other schema field under comparison.
            from improve_center_visits import photo_notice
            require(photo_mode in ['center','common'],'missing phase 3 photo provenance')
            for node,previous in zip(comparison,old_graph):
                primary=node.get('primaryImageOfPage')
                if isinstance(primary,dict):
                    require(primary.get('caption')==photo_notice({'routeName':record['branch']},photo_mode),'incorrect phase 3 photo caption')
                    old_primary=previous.get('primaryImageOfPage',{})
                    if 'caption' in old_primary:primary['caption']=old_primary['caption']
                    else:primary.pop('caption',None)
        require(comparison==old_graph,'detail schema changed')
        links=byclass(main,'cc-profile-link')
        require(len(links)==1,'profile link coverage')
        if links:require([unquote(u) for u in links[0].xpath('.//a/@href')]==[record['profileTarget']],'wrong profile target')
    return issues


def main():
    p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True)
    p.add_argument('--site',type=Path,required=True);p.add_argument('--built',action='store_true')
    p.add_argument('--output',type=Path,help='Write new validation results here while retaining historical evidence')
    args=p.parse_args();report=load(args.report/'phase2.json');profiles={p['branch']:p for p in report['profiles']}
    errors=[];counts=Counter()
    photo_modes={r['branch']:('common' if r['commonPhotos'] else 'center') for r in report['pages'] if r['branchPage']}
    def inspect(r):
        raw=(args.site/r['path']).read_text(encoding='utf-8-sig')
        before=(args.report/'before'/r['path']).read_text(encoding='utf-8-sig')
        issues=check_page(raw,before,r,profiles.get(r['branch']),photo_modes[r['branch']])
        if args.built and raw.count('wawa-visit-collector')!=1:issues.append('tracker missing/duplicated')
        return r,issues
    with ThreadPoolExecutor(max_workers=12) as pool:
        for r,issues in pool.map(inspect,report['pages']):
            counts['pages']+=1
            errors.extend({'file':r['path'],'reason':x} for x in issues)
    targets={p['path']+'#learning-management' for p in profiles.values()}
    for r in report['pages']:
        if not r['branchPage'] and r['profileTarget'] not in targets:errors.append({'file':r['path'],'reason':'missing profile destination'})
    for p,sha in report['sources'].items():
        if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=sha:errors.append({'file':p,'reason':'input modified'})
    counts.update(report['summary']);counts['errors']=len(errors)
    result={'site':str(args.site),'built':args.built,'counts':dict(counts),'errors':errors}
    save((args.output or args.report)/('phase2-validation-built.json' if args.built else 'phase2-validation.json'),result)
    print(json.dumps({'counts':dict(counts),'errors':errors[:20]},ensure_ascii=False),flush=True)
    raise SystemExit(bool(errors))


if __name__=='__main__':main()
