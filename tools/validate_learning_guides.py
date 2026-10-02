"""Validate every guide, worksheet, internal target, metadata and sitemap entry."""
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit, unquote, urljoin
from lxml import html, etree
import argparse, hashlib, json, re, subprocess
from build_learning_guides import GUIDES, CATEGORIES, LEGACY, SOURCES, DAY, DOMAIN, route, validate_content
from learning_guides.adaptations import ADAPTATIONS

ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser(); p.add_argument('--root',default=str(ROOT)); p.add_argument('--report-dir',required=True); p.add_argument('--built',action='store_true'); p.add_argument('--related-release-report'); a=p.parse_args()
    root=Path(a.root).resolve(); out=Path(a.report_dir).resolve(); validate_content()
    manifest=json.loads((ROOT/'release-public-manifest.json').read_text('utf-8'))
    baseline=json.loads((out/'before-release-public-manifest.json').read_text('utf-8'))
    generated=json.loads((out/'generation.json').read_text('utf-8'))
    related=json.loads(Path(a.related_release_report).read_text('utf-8')) if a.related_release_report else {}
    errors=[]; pages=['학습가이드/index.html']+['학습가이드/'+g['slug']+'/index.html' for g in GUIDES]
    slugs={g['slug']:g for g in GUIDES}; stats=[]; cache={}; link_count=0
    def check(ok,message,file=''):
        if not ok: errors.append({'file':file,'error':message})
    def doc_for(name):
        if name not in cache: cache[name]=html.fromstring((root/name).read_bytes())
        return cache[name]
    ns={'s':'http://www.sitemaps.org/schemas/sitemap/0.9'}
    sitemap=etree.parse(str(root/'sitemap.xml'))
    urls={unquote(urlsplit(el.findtext('s:loc',namespaces=ns)).path):el.findtext('s:lastmod',namespaces=ns) for el in sitemap.xpath('//s:url',namespaces=ns)}
    raw_locs=sitemap.xpath('//s:loc/text()',namespaces=ns)
    check(len(raw_locs)==len(urls)==10400+related.get('newPages',0)==manifest['sitemapPages'],'Sitemap count, URL uniqueness or manifest mismatch')
    for u in urls:
        check(u.endswith('/'),'Sitemap trailing slash: '+u)
        check((u.lstrip('/')+'index.html') in manifest['files'],'Sitemap target not reviewed: '+u)
    before_tree=etree.parse(str(out/'before-sitemap.xml'))
    for el in before_tree.xpath('//s:url',namespaces=ns):
        u=unquote(urlsplit(el.findtext('s:loc',namespaces=ns)).path)
        old_date=el.findtext('s:lastmod',namespaces=ns)
        check(u in urls,'Existing sitemap URL removed: '+u)
        if not u.startswith('/학습가이드/') and u not in related.get('contentChangedPaths',[]):
            check(urls.get(u)==old_date,'Unrelated sitemap date changed: '+u)
    descriptions=[]; titles=[]
    for name in pages:
        doc=doc_for(name); raw=(root/name).read_text('utf-8'); slug=name.split('/')[1] if name.count('/')==2 else ''
        g=slugs.get(slug); canon=doc.xpath('//link[@rel="canonical"]/@href')
        check(len(doc.xpath('//h1'))==1,'H1 count',name); check(len(canon)==1,'Canonical count',name)
        check(unquote(urlsplit(canon[0]).path)==route(slug),'Canonical route',name)
        check(urls.get(route(slug))==DAY,'Sitemap date',name)
        desc=doc.xpath('//meta[@name="description"]/@content')
        check(len(desc)==1 and 0<len(desc[0])<=80 and desc[0].endswith('.'),'Description format',name)
        descriptions+=desc; titles+=doc.xpath('//title/text()')
        for selector in ['//meta[@property="og:description"]/@content','//meta[@name="twitter:description"]/@content']:
            check(doc.xpath(selector)==desc,'Social description drift',name)
        graph=json.loads(doc.xpath('//script[@type="application/ld+json"]/text()')[0])['@graph']
        for node in graph:
            if node['@type'] in ('WebPage','CollectionPage','Article'): check(node.get('description')==desc[0],'Schema description drift',name)
        ids=doc.xpath('//*[@id]/@id'); check(len(ids)==len(set(ids)),'Duplicate element IDs',name)
        check(not re.search(r'편집\s*원칙',doc.text_content()),'Excluded policy phrase',name)
        check('tel:010-3957-8283' in raw and 'blogsms.net/01039578283' in raw,'Existing contact destinations',name)
        for url in doc.xpath('//*[@href]/@href | //*[@src]/@src'):
            parts=urlsplit(urljoin(canon[0],url))
            if parts.scheme not in ('http','https') or parts.netloc!=urlsplit(DOMAIN).netloc: continue
            path=unquote(parts.path); target=path.lstrip('/')+('index.html' if path.endswith('/') else '')
            check(target in manifest['files'],'Internal target missing: '+target,name); link_count+=1
            if parts.fragment and target in manifest['files'] and target.endswith('.html'):
                target_doc=doc_for(target)
                check(bool(target_doc.xpath('//*[@id=$id]',id=unquote(parts.fragment))),'Broken anchor: '+url,name)
        if g:
            check(len(doc.xpath('//textarea[@data-record-field]'))==4,'Record field count',name)
            qa=next(n for n in graph if n['@type']=='FAQPage')['mainEntity']
            visible=[(x.xpath('string(summary)').strip(),x.xpath('string(p)').strip()) for x in doc.xpath('//*[@id="faq"]/details')]
            check(visible==[(q['name'],q['acceptedAnswer']['text']) for q in qa],'FAQ visible/schema mismatch',name)
            article=next(n for n in graph if n['@type']=='Article')
            check(article['citation']==[SOURCES[k][1] for k in g['sources']],'Article citations',name)
            source_urls=doc.xpath('//*[@id="sources"]//a/@href')
            check(source_urls==article['citation'],'Visible sources differ',name)
            worksheet=root/'assets/guide-worksheets'/f'{slug}.txt'
            data=worksheet.read_bytes(); check(data.startswith(b'\xef\xbb\xbf'),'TXT UTF-8 BOM',name)
            check(b'\n' not in data.replace(b'\r\n',b''),'TXT CRLF',name)
            text=data.decode('utf-8-sig'); check(all(label in text for label in g['fields']),'Worksheet labels',name)
            core=g['lead']+''.join(g['check'])+''.join(t+b for t,b in g['steps'])+g['example_title']+g['example']+''.join(''.join(row) for row in g['rows'])+''.join(g['pitfalls'])+ADAPTATIONS[slug]+g['next']+''.join(q+b for q,b in g['faq'])
            stats.append({'slug':slug,'coreCharacters':len(core),'descriptionCharacters':len(desc[0])})
            check(len(core)>=1000,'Substantive core too short',name)
        else:
            check(len(doc.xpath('//*[@data-guide-card]'))==48,'Hub cards',name)
            itemlist=next(n for n in graph if n['@type']=='ItemList'); check(itemlist['numberOfItems']==len(itemlist['itemListElement'])==48,'ItemList count',name)
        if a.built:
            check(raw.count('data-site="wawa-02"')==1 and raw.count('wawa-visit-collector')==1,'Built analytics tag count',name)
        if slug in LEGACY or not slug:
            old=subprocess.run(['git','show','HEAD:'+name],cwd=ROOT,capture_output=True,check=True).stdout
            check(html.fromstring(old).xpath('//link[@rel="canonical"]/@href')==canon,'Legacy canonical changed',name)
    check(len(descriptions)==len(set(descriptions)),'Duplicate guide descriptions')
    check(len(titles)==len(set(titles)),'Duplicate guide titles')
    allowed=set(generated['publicChanges'])|set(related.get('publicChanges',[]))
    unrelated=[name for name,value in baseline['files'].items() if name not in allowed and manifest['files'].get(name)!=value]
    check(not unrelated,'Unrelated manifest hashes changed: '+str(unrelated[:5]))
    if not a.built:
        def verify_hash(name):
            check(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==manifest['files'].get(name),'Manifest hash mismatch',name)
        with ThreadPoolExecutor(max_workers=12) as pool: list(pool.map(verify_hash,allowed))
    result={'mode':'built' if a.built else 'source','guides':48,'guidePages':len(pages),'categories':dict(Counter(g['category'] for g in GUIDES)),'worksheets':48,'sourceCount':len(SOURCES),'sitemapURLs':len(urls),'internalLinksAndAssetsChecked':link_count,'minimumCoreCharacters':min(s['coreCharacters'] for s in stats),'maximumCoreCharacters':max(s['coreCharacters'] for s in stats),'unchangedPublicManifestEntries':len(baseline['files'])-len(set(baseline['files'])&allowed),'errors':errors,'errorCount':len(errors),'articles':stats}
    (out/('verification-built.json' if a.built else 'verification-source.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('articles','errors')},ensure_ascii=False))
    if errors: print(json.dumps(errors[:20],ensure_ascii=False)); raise SystemExit(1)
if __name__=='__main__': main()
