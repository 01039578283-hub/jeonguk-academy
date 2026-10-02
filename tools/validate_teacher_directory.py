"""Audit every supplied introduction, branch mapping, image and changed page."""
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote,urlsplit,urljoin
from html import unescape
import argparse,hashlib,json,re,zipfile
from lxml import html,etree
import openpyxl

ROOT=Path(__file__).resolve().parents[1]
DOMAIN='https://xn--3e0bl59bm0ad17a.com'
def load(p):return json.loads(p.read_text('utf-8'))
def clean_changes(raw):
    # Zip bytes retain the pre-existing Windows line endings, while read_text
    # normalizes them. Compare the actual content on both sides consistently.
    raw=raw.replace('\r\n','\n')
    raw=re.sub(r'<a\b[^>]*data-teacher-menu[^>]*>선생님찾기</a>','',raw)
    raw=re.sub(r'<section\b[^>]*data-teacher-bridge="[^"]+"[^>]*>[\s\S]*?</section>','',raw)
    raw=re.sub(r'(/assets/unified-ui\.css)(?:\?[^"\s>]*)?',r'\1',raw)
    return raw.strip()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',default=str(ROOT));parser.add_argument('--report-dir',required=True);parser.add_argument('--teacher-file',required=True);parser.add_argument('--built',action='store_true');a=parser.parse_args()
    root=Path(a.root).resolve();out=Path(a.report_dir);manifest=load(ROOT/'release-public-manifest.json');baseline=load(out/'before-release-public-manifest.json')
    model=load(out/'teacher-model.json');generated=load(out/'generation.json');errors=[];links=0;cards_seen=[];docs={};canonicals=[];descriptions=[]
    def check(ok,message,file=''):
        if not ok:errors.append({'file':file,'error':message})
    def doc(name):
        if name not in docs:docs[name]=html.fromstring((root/name).read_bytes())
        return docs[name]
    source=Path(a.teacher_file);check(hashlib.sha256(source.read_bytes()).hexdigest()==model['sourceHash'],'Source workbook changed')
    wb=openpyxl.load_workbook(source,read_only=True,data_only=True)
    rows={i:[str(v or '').strip() for v in values] for sheet in wb for i,values in enumerate(sheet.iter_rows(values_only=True),1) if any(v is not None for v in values)}
    check(len(rows)==1002,'Source count')
    expected_aliases={'목감점(모두)':'목감점','별내중앙점(모두)':'별내중앙점','용인백현점(모두)':'용인백현점','진천점(모두)':'진천점','탕정점(모두)':'탕정점','석사2호점':'석사점','주엽2호점':'주엽점'}
    expected_branches=Counter(expected_aliases.get(r[0],r[0]) for r in rows.values())
    check(len(expected_branches)==204,'Expected normalized branches')
    for b in model['branches']:
        name='선생님찾기/'+b['slug']+'/index.html';d=doc(name)
        cards=d.xpath('//*[@data-teacher-card]');check(len(cards)==expected_branches[b['slug']],'Branch card count',name)
        images=[]
        for card in cards:
            row=int(card.get('data-source-row'));cards_seen.append(row);src=rows[row]
            check(expected_aliases.get(src[0],src[0])==b['slug'],'Teacher assigned to wrong branch',name)
            check(' '.join(' '.join(card.xpath('.//*[contains(@class,"td-bio")]/p/text()')).split())==' '.join(src[3].split()),'Source introduction changed',name)
            check(card.xpath('string(.//h2)').strip()==src[1]+' 선생님','Masked name changed',name)
            check(card.xpath('.//*[contains(@class,"td-tags")]/span/text()')==src[2].split(' / '),'Teaching focus changed',name)
            check(card.xpath('string(.//*[contains(@class,"td-teacher-branch")])')==src[0],'Original branch label changed',name)
            img=card.xpath('.//img');check(len(img)==1,'Exactly one portrait',name)
            if img:
                images.append(img[0].get('src'))
                check(img[0].get('alt')=='교사 소개용 공용 이미지','Representative alt missing',name)
                check(img[0].get('width') and img[0].get('height') and img[0].get('loading')=='lazy','Image sizing/lazy loading',name)
            check(card.xpath('string(.//figcaption)')=='소개용 이미지','Representative caption missing',name)
        check(len(images)==len(set(images)),'Repeated photo within the same branch',name)
        check('실제 교사 사진이 아닙니다.' in d.text_content(),'Representative image disclosure',name)
        if b['sitePath']:check(any(unquote(u)==b['sitePath'] for u in d.xpath('//main//a/@href')),'Reverse branch link missing',name)
    check(sorted(cards_seen)==sorted(rows),'Missing or duplicated source introduction rows')
    hub=doc('선생님찾기/index.html');hub_cards=hub.xpath('//*[@id="teacher-results"]/*[@data-branch-card]')
    check(len(hub_cards)==204,'Hub branch coverage');check(sum(int(x.get('data-count')) for x in hub_cards)==1002,'Hub introduction total')
    for name in generated['newPagePaths']:
        d=doc(name);raw=(root/name).read_text('utf-8');path='/'+name.removesuffix('index.html')
        canonical=d.xpath('//link[@rel="canonical"]/@href');description=d.xpath('//meta[@name="description"]/@content')
        check(len(d.xpath('//h1'))==1,'H1',name);check(len(canonical)==1,'Canonical count',name)
        canonicals+=canonical;descriptions+=description
        check(unquote(urlsplit(canonical[0]).path)==path,'Canonical route',name)
        check(len(description)==1 and len(description[0])<=80 and description[0].endswith('.'),'Complete description <=80 characters',name)
        check(d.xpath('//meta[@property="og:description"]/@content')==description and d.xpath('//meta[@name="twitter:description"]/@content')==description,'Description consistency',name)
        graph=json.loads(d.xpath('//script[@type="application/ld+json"]/text()')[0])['@graph']
        page=next(x for x in graph if x['@type']=='CollectionPage');check(page['description']==description[0],'Schema description',name)
        listing=next(x for x in graph if x['@type']=='ItemList');expected=204 if name=='선생님찾기/index.html' else len(d.xpath('//*[@data-teacher-card]'))
        check(listing['numberOfItems']==len(listing['itemListElement'])==expected,'ItemList coverage',name)
        check(not any(x.get('@type') in ('Person','Review','AggregateRating') for x in graph),'Unverified person identity/rating schema',name)
        ids=d.xpath('//*[@id]/@id');check(len(ids)==len(set(ids)),'Duplicate IDs',name)
        check(len(d.xpath('//header//*[@data-teacher-menu]'))==len(d.xpath('//footer//*[@data-teacher-menu]'))==1,'New shared menu',name)
        check(len(d.xpath('//header//a[@aria-current="page"]'))==1,'Active menu unique',name)
        for url in d.xpath('//*[@href]/@href | //*[@src]/@src'):
            parts=urlsplit(urljoin(canonical[0],url))
            if parts.scheme not in ('http','https') or parts.netloc!=urlsplit(DOMAIN).netloc:continue
            target=unquote(parts.path).lstrip('/')+('index.html' if parts.path.endswith('/') else '')
            links+=1;check(target in manifest['files'],'Internal target missing: '+target,name)
            if target in manifest['files'] and target.endswith('.html') and parts.fragment:
                check(bool(doc(target).xpath('//*[@id=$id]',id=unquote(parts.fragment))),'Broken anchor '+url,name)
        if a.built:check(raw.count('data-site="wawa-02"')==1 and raw.count('wawa-visit-collector')==1,'Analytics missing/duplicate',name)
    check(len(set(canonicals))==205 and len(set(descriptions))==205,'Duplicate teacher URLs/descriptions')
    preservation=0
    if not a.built:
        with zipfile.ZipFile(out/'before-pages.zip') as z:
            check(len(z.namelist())==10400,'Baseline page backup coverage')
            def compare_existing(name):
                raw=(root/name).read_text('utf-8');before=z.read(name).decode('utf-8')
                check(clean_changes(raw)==clean_changes(before),'Unrelated existing content changed',name)
                check(raw.count('data-teacher-menu')==2,'Existing page shared navigation',name)
                bridges=re.findall(r'<section\b[^>]*data-teacher-bridge="([^"]+)"[^>]*>([\s\S]*?)</section>',raw)
                expected=generated['contextLinks'].get(name)
                check(len(bridges)==(1 if expected else 0),'Context link count',name)
                if bridges:
                    check(bridges[0][0]==expected,'Wrong contextual branch',name)
                    hrefs=re.findall(r'href="([^"]+)"',bridges[0][1]);check(len(hrefs)==1 and unquote(hrefs[0])=='/선생님찾기/'+expected+'/','Wrong teacher destination',name)
                return 1
            with ThreadPoolExecutor(max_workers=12) as pool:preservation=sum(pool.map(compare_existing,z.namelist()))
        def verify_hash(name):
            check(hashlib.sha256((root/name).read_bytes()).hexdigest()==manifest['files'].get(name),'Reviewed hash mismatch',name)
        with ThreadPoolExecutor(max_workers=12) as pool:list(pool.map(verify_hash,generated['publicChanges']))
    for photo in model['photos']:
        check(hashlib.sha256((root/photo['path']).read_bytes()).hexdigest()==photo['sha256'],'Supplied image bytes changed',photo['path'])
    ns={'s':'http://www.sitemaps.org/schemas/sitemap/0.9'}
    tree=etree.parse(str(root/'sitemap.xml'));locs=tree.xpath('//s:loc/text()',namespaces=ns)
    urls={unquote(urlsplit(e.findtext('s:loc',namespaces=ns)).path):e.findtext('s:lastmod',namespaces=ns) for e in tree.xpath('//s:url',namespaces=ns)}
    check(len(locs)==len(urls)==10605==manifest['sitemapPages'],'Sitemap coverage')
    before=etree.parse(str(out/'before-sitemap.xml'))
    for node in before.xpath('//s:url',namespaces=ns):
        path=unquote(urlsplit(node.findtext('s:loc',namespaces=ns)).path);old_date=node.findtext('s:lastmod',namespaces=ns)
        expected='2026-10-02' if path in generated['contentChangedPaths'] else old_date
        check(path in urls and urls[path]==expected,'Existing sitemap URL/date changed unexpectedly: '+path)
    for path in urls:check(path.lstrip('/')+'index.html' in manifest['files'],'Sitemap target missing: '+path)
    extra=set(manifest['files'])-set(baseline['files']);check(not any(re.search(r'\.(xlsx|zip)$',n) or n.startswith('tools/') for n in extra),'Private source included in public files')
    result={'mode':'built' if a.built else 'source','newPages':205,'branches':204,'teacherIntroductions':len(cards_seen),'distinctPhotosPerBranch':True,
      'photoAssets':len(model['photos']),'existingPagesPreserved':preservation,'contextLinks':len(generated['contextLinks']),'internalLinksChecked':links,'sitemapPages':len(urls),'errors':errors,'errorCount':len(errors)}
    (out/('verification-built.json' if a.built else 'verification-source.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='errors'},ensure_ascii=False))
    if errors:print(json.dumps(errors[:15],ensure_ascii=False));raise SystemExit(1)
if __name__=='__main__':main()
