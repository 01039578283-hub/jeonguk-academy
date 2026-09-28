"""Verify phase 3 additions against saved HTML and the reviewed source evidence."""
import argparse
import copy
import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote, urlsplit
from lxml import html
from improve_center_content import load, save, digest, text, byclass, serialize
from improve_center_visits import MARKER, DAY, SOURCE_NOTE, photo_label, photo_notice


def check_page(raw,before,record,evidence):
    d=html.fromstring(raw);old=html.fromstring(before);main=d.xpath('//main')[0];issues=[]
    def require(ok,why):
        if not ok:issues.append(why)
    require(main.get(MARKER)==DAY,'phase 3 marker')
    for xpath,label in [('//title/text()','title'),('//h1/text()','H1'),('//link[@rel="canonical"]/@href','canonical'),
                        ('//meta[@name="robots"]/@content','robots'),('//meta[@name="description"]/@content','description'),
                        ('//meta[@property="og:description"]/@content','OG description'),('//meta[@name="twitter:description"]/@content','Twitter description')]:
        require(d.xpath(xpath)==old.xpath(xpath),label+' changed')
    for tag in ['header','footer']:
        require(re.findall(r'<'+tag+r'\b.*?</'+tag+'>',raw,re.S)==re.findall(r'<'+tag+r'\b.*?</'+tag+'>',before,re.S),tag+' changed')
    require([(i.get('src'),i.get('width'),i.get('height'),i.get('loading'),i.get('hidden')) for i in d.xpath('//img')]==
            [(i.get('src'),i.get('width'),i.get('height'),i.get('loading'),i.get('hidden')) for i in old.xpath('//img')],'image inventory/order/dimensions changed')
    require(len(d.xpath('//link[contains(@href,"/assets/center-visit.css")]'))==1,'stylesheet coverage')
    ids=d.xpath('//*[@id]/@id');require(len(ids)==len(set(ids)),'duplicate ids')
    for href in d.xpath('//a[starts-with(@href,"#")]/@href'):require(unquote(href[1:]) in ids,'missing local anchor '+href)
    # Existing factual and editorial sections must retain their complete content.
    for section in old.xpath('//main//section[@id]'):
        key=section.get('id')
        if key=='learning-materials':continue
        nodes=main.xpath('.//section[@id="'+key+'"]');require(len(nodes)==1,'missing section '+key)
        if nodes:
            normalized=copy.deepcopy(nodes[0])
            for link in byclass(normalized,'cv-direction-link'):link.getparent().remove(link)
            require(serialize(normalized)==serialize(section),'existing section changed: '+key)
    old_graph=json.loads(old.xpath('//script[@type="application/ld+json"]')[0].text)['@graph']
    new_graph=json.loads(d.xpath('//script[@type="application/ld+json"]')[0].text)['@graph']
    normalized=copy.deepcopy(new_graph);require(len(normalized)==len(old_graph),'schema node inventory')
    for n,o in zip(normalized,old_graph):
        if n.get('@type') in ['WebPage','CollectionPage','Article']:
            require(n.get('dateModified')==DAY,'schema modification date')
            if 'dateModified' in o:n['dateModified']=o['dateModified']
            else:n.pop('dateModified',None)
        if record['branchPage'] and n.get('@type')=='WebPage':
            parts={unquote(p['@id']).split('#')[-1]:p['name'] for p in n.get('hasPart',[])}
            expected={s.get('id'):text(s.xpath('.//h2')[0]) for s in main.xpath('.//section[@id]') if s.xpath('.//h2')}
            require(parts==expected,'schema sections differ')
            n['hasPart']=o['hasPart']
        elif not record['branchPage'] and isinstance(n.get('primaryImageOfPage'),dict):
            primary=n['primaryImageOfPage'];require(primary.get('caption')==photo_notice({'routeName':record['branch']},record['photoMode']),'schema photo provenance')
            if 'caption' in o['primaryImageOfPage']:primary['caption']=o['primaryImageOfPage']['caption']
            else:primary.pop('caption',None)
    require(normalized==old_graph,'unreviewed schema claims changed')
    sections=main.xpath('.//section/@id')
    if record['branchPage']:
        require(evidence is not None,'missing location evidence')
        nodes=main.xpath('.//section[@id="directions"]');require(len(nodes)==1,'directions coverage')
        if nodes and evidence:
            sec=nodes[0];require([text(n) for n in byclass(sec,'cv-directions-body')]==[evidence['body']],'unreviewed directions copy')
            require([text(n) for n in byclass(sec,'cv-source-note')]==[SOURCE_NOTE],'directions source qualification')
            require(sec.xpath('.//a/@href')==old.xpath('//section[@id="center-facts"]//a[contains(@href,"map.naver.com")]/@href'),'map destination changed')
            old_address=old.xpath('//section[@id="center-facts"]//dt[text()="주소"]/following-sibling::dd[1]/text()')
            require(len(old_address)==1 and text(byclass(sec,'cv-address')[0])=='방문 주소 '+old_address[0],'visit address changed')
        require(len(main.xpath('.//nav//a[@href="#directions"]'))==1 or len(byclass(main,'jd-toc')[0].xpath('.//a[@href="#directions"]'))==1,'directions navigation')
        require(sections.index('directions')<sections.index('learning-materials'),'directions after media')
        require(d.xpath('//img/@alt')==old.xpath('//img/@alt'),'main photo labels changed')
    else:
        require(sections.index('courses')<sections.index('learning-materials') and sections.index('center-facts')<sections.index('learning-materials') and sections.index('fees')<sections.index('learning-materials'),'photos precede useful facts')
        figures=main.xpath('.//figure[@data-photo-source]');require(len(figures)==1,'photo source count')
        if figures:
            f=figures[0];label=photo_label({'routeName':record['branch']},record['photoMode'])
            require(f.get('data-photo-source')==record['photoMode'],'incorrect photo origin')
            require(f.xpath('.//img/@alt')==[label] and text(f.find('figcaption'))==label,'photo label differs from source')
            require(f.xpath('.//img/@src')==[record['photoSrc']],'wrong photo file')
            require(d.xpath('//meta[@property="og:image:alt"]/@content')==[label],'OG photo label')
        require([text(n) for n in byclass(main,'cv-photo-note')]==[photo_notice({'routeName':record['branch']},record['photoMode'])],'photo notice mismatch')
        for a,b in zip(d.xpath('//img'),old.xpath('//img')):
            if a.get('src')!=record['photoSrc']:require(a.get('alt')==b.get('alt'),'map/representative alt changed')
        links=byclass(main,'cv-direction-link')
        require(len(links)==int(record['directions']),'location link coverage')
        if links:
            require(unquote(links[0].get('href'))==record['directionTarget'],'wrong branch directions link')
            require(evidence is not None and record['directionTarget']==evidence['path']+'#directions','unreviewed destination')
    return issues


def main():
    p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True)
    p.add_argument('--site',type=Path,required=True);p.add_argument('--built',action='store_true');args=p.parse_args()
    report=load(args.report/'phase3.json');evidence={e['branch']:e for e in report['directions']};errors=[]
    def inspect(r):
        raw=(args.site/r['path']).read_text(encoding='utf-8-sig');before=(args.report/'before'/r['path']).read_text(encoding='utf-8-sig')
        issues=check_page(raw,before,r,evidence.get(r['branch']))
        if args.built and raw.count('wawa-visit-collector')!=1:issues.append('tracker missing/duplicated')
        return [{'file':r['path'],'reason':i} for i in issues]
    with ThreadPoolExecutor(max_workers=12) as pool:
        for result in pool.map(inspect,report['pages']):errors.extend(result)
    for source,sha in report['sources'].items():
        if digest(Path(source).read_bytes())!=sha:errors.append({'file':source,'reason':'input modified'})
    if len({e['body'] for e in evidence.values()})!=len(evidence):errors.append({'reason':'duplicate directions'})
    for e in evidence.values():
        path=e['path'].strip('/')+'/index.html'
        d=html.fromstring((args.site/path).read_bytes())
        if not d.xpath('//*[@id="directions"]'):errors.append({'file':path,'reason':'missing directions destination'})
    result={'site':str(args.site),'built':args.built,'counts':report['summary'],'errorCount':len(errors),'errors':errors}
    save(args.report/('phase3-validation-built.json' if args.built else 'phase3-validation.json'),result)
    print(json.dumps({'counts':report['summary'],'errorCount':len(errors),'errors':errors[:20]},ensure_ascii=False),flush=True)
    raise SystemExit(bool(errors))


if __name__=='__main__':main()
