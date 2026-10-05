"""Validate the full snapshot, current-post preservation and new batch provenance."""
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit,urljoin,unquote
import argparse,hashlib,json,re,subprocess,zipfile
from lxml import html,etree
from PIL import Image

REPO=Path(__file__).resolve().parents[1]
AUTHOR=Path(r'C:\Users\1992k\Desktop\홈페이지 작업 폴더\홈페이지 정리\새 홈페이지')
DOMAIN='https://xn--3e0bl59bm0ad17a.com'
DAY='2026-10-05'
TRACKER=b'<script defer src="https://wawa-visit-collector.clean-peach-8202.chatgpt.site/tracker.js" data-site="wawa-02" crossorigin="anonymous" referrerpolicy="no-referrer"></script>'
load=lambda p:json.loads(p.read_text('utf-8-sig'))
sha=lambda b:hashlib.sha256(b).hexdigest()
norm=lambda b:b.replace(b'\r\n',b'\n')
def main():
    p=argparse.ArgumentParser();p.add_argument('--report-dir',type=Path,required=True);p.add_argument('--root',type=Path,default=REPO);p.add_argument('--report-name',default='validation-source.json');args=p.parse_args();out=args.report_dir;root=args.root.resolve()
    before=load(out/'before-release-public-manifest.json');manifest=load(REPO/'release-public-manifest.json');generation=load(out/'generation.json');articles=load(out/'article-data.json');library=load(out/'library.json');mapping=load(out/'link-mapping.json');selection=load(out/'selection-final.json')
    errors=[];stats=Counter();destinations=set();all_ids={};article_texts=[];incoming=Counter()
    def check(ok,reason,**details):
        if not ok:errors.append({'reason':reason,**details})
    check(len(articles)==30 and len(generation['newPages'])==30,'New batch page coverage')
    check(len(library)==128 and Counter(a['kind'] for a in library)=={'new':60,'guide':48,'coaching':20},'Library coverage')
    check(len(manifest['files'])==len(before['files'])+120,'Public file growth')
    check(set(before['files'])<=set(manifest['files']),'Prior public asset removed')
    changed=set(generation['publicChanges'])
    check(all(manifest['files'][n]==digest for n,digest in before['files'].items() if n not in changed),'Unrelated asset changed')
    check(not any(n.startswith('tools/') or n.endswith(('.py','.xlsx','.csv','.zip')) for n in manifest['files']),'Private source in public manifest')
    with zipfile.ZipFile(out/'before-pages.zip') as z:originals={n:z.read(n).decode('utf-8') for n in z.namelist()}
    def preserve(name):
        if name=='교육정보/index.html':return name,True
        old=originals[name];new=(REPO/name).read_bytes().decode('utf-8')
        stripped=re.sub(r'<!-- education-expansion:start -->[\s\S]*?<!-- education-expansion:end -->','',new)
        old_dates=re.findall(r'"dateModified"\s*:\s*"([^"]+)"',old)
        new_dates=re.findall(r'"dateModified"\s*:\s*"([^"]+)"',stripped)
        if len(old_dates)!=len(new_dates):return name,False
        it=iter(old_dates)
        stripped=re.sub(r'("dateModified"\s*:\s*")[^"]+("\s*)',lambda m:m[1]+next(it)+m[2],stripped)
        return name,stripped==old
    with ThreadPoolExecutor(max_workers=12) as pool:
        for name,ok in pool.map(preserve,originals):check(ok,'Original HTML changed outside approved link/date additions',file=name);stats['preserved']+=int(ok)
    expected_config=load(out/'before-seo-descriptions.json');current_config=load(REPO/'seo-descriptions.json')
    check(all(current_config['pages'].get(k)==v for k,v in expected_config['pages'].items()),'Existing descriptions changed')
    sitemap=etree.fromstring((root/'sitemap.xml').read_bytes());ns={'s':'http://www.sitemaps.org/schemas/sitemap/0.9'}
    urls=sitemap.xpath('//s:url/s:loc/text()',namespaces=ns)
    expected={'/'+n.removesuffix('index.html') for n in manifest['files'] if n.endswith('.html')}
    check(len(urls)==len(set(urls))==10750 and {unquote(urlsplit(u).path) for u in urls}==expected,'Complete unique sitemap coverage')
    check(set(sitemap.xpath('//s:lastmod/text()',namespaces=ns))=={DAY},'Changed-page lastmod')
    def resolve(value,name):
        u=urlsplit(urljoin(DOMAIN+'/'+name,value))
        if u.scheme not in ('http','https') or u.netloc not in ('xn--3e0bl59bm0ad17a.com','전국학원.com'):return
        dest=unquote(u.path).lstrip('/')
        if not dest or dest.endswith('/'):dest+='index.html'
        elif not Path(dest).suffix:dest+='/index.html'
        return dest,unquote(u.fragment)
    def inspect(item):
        name,digest=item;raw=(root/name).read_bytes();local_errors=[]
        source=(REPO/name).read_bytes()
        if sha(source)!=digest:local_errors.append('Source differs from approved manifest')
        if root!=REPO and name.endswith('.html'):
            if raw.count(TRACKER)!=1:local_errors.append('Analytics count')
            raw=raw.replace(TRACKER,b'')
        if norm(raw)!=norm(source):local_errors.append('Output differs from source')
        if not name.endswith('.html'):return name,local_errors,None,[],set(),None
        doc=html.fromstring(raw);ids=doc.xpath('//@id')
        if len(ids)!=len(set(ids)):local_errors.append('Duplicate HTML anchors')
        if len(doc.xpath('//h1'))!=1:local_errors.append('H1 count')
        canonicals=doc.xpath('//link[@rel="canonical"]/@href');path='/'+name.removesuffix('index.html')
        if len(canonicals)!=1 or unquote(urlsplit(canonicals[0]).path)!=path:local_errors.append('Canonical path')
        desc=doc.xpath('//meta[@name="description"]/@content')
        if len(desc)!=1 or not (0<len(desc[0])<=80) or not desc[0].endswith('.'):local_errors.append('Description sentence')
        elif doc.xpath('//meta[@property="og:description"]/@content')!=desc or doc.xpath('//meta[@name="twitter:description"]/@content')!=desc:local_errors.append('Description metadata mismatch')
        for script in doc.xpath('//script[@type="application/ld+json"]/text()'):
            try:json.loads(script)
            except Exception:local_errors.append('Invalid JSON-LD')
        values=doc.xpath('//@href | //img/@src | //script/@src')
        links=[v for value in values if (v:=resolve(value,name))]
        counts=[]
        for href in doc.xpath('//*[@data-education-added]/@href'):
            dest=resolve(href,name)
            if dest:counts.append(dest[0])
        details=None
        if name in generation['newPages'] or name=='교육정보/index.html':
            schema=[node for script in doc.xpath('//script[@type="application/ld+json"]/text()') for obj in [json.loads(script)] for node in obj.get('@graph',[obj])]
            if '편집 원칙' in raw.decode() or 'WAWA_유용한정보' in raw.decode() or 'C:\\Users' in raw.decode():local_errors.append('Excluded/private text in article')
            if name=='교육정보/index.html':
                cards=doc.xpath('//*[@data-library-card]');listing=next(n for n in schema if n.get('@type')=='ItemList')
                rendered={unquote(urlsplit(c.xpath('.//h3/a/@href')[0]).path) for c in cards}
                if len(cards)!=128 or rendered!={a['path'] for a in library} or listing['numberOfItems']!=128 or len(listing['itemListElement'])!=128:local_errors.append('Library/card/schema coverage')
                if any(c.get('hidden') is not None for c in cards):local_errors.append('No-JavaScript coverage')
            else:
                a=next(a for a in articles if a['path']==path);prose=doc.xpath('//*[@data-education-article]')
                if len(prose)!=1:local_errors.append('Article container')
                else:
                    text=' '.join(prose[0].itertext());details=(name,len(text))
                    if len(text)<1700:local_errors.append('Insufficient substantive body')
                    if len(prose[0].xpath('.//section[@class="ei-prose-section"][starts-with(@id,"section-")]'))!=4:local_errors.append('Incomplete article sections')
                node=next(n for n in schema if n.get('@type')=='Article')
                if node['headline']!=a['title'] or node['description']!=desc[0] or node['datePublished']!=DAY or node['dateModified']!=DAY:local_errors.append('Article identity/schema')
                figures=doc.xpath('//*[@data-education-image]')
                if len(figures)!=3:local_errors.append('Image count')
                for figure,p in zip(figures,a['images']):
                    im=figure.xpath('.//img')[0]
                    if im.get('src')!='/'+p['path'] or im.get('alt')!=p['alt'] or im.get('width')!=str(p['width']) or im.get('height')!=str(p['height']) or im.get('loading')!='lazy' or '참고 이미지' not in figure.text_content():local_errors.append('Image attributes or disclosure')
                if len(doc.xpath('//*[@id="check"]//li'))!=3 or not doc.xpath('//*[@id="example"]//table'):local_errors.append('Action/table coverage')
            locations=json.loads(doc.xpath('//script[@id="ei-locations"]/text()')[0])
            if len(locations)!=193:local_errors.append('Branch chooser coverage')
            for b in locations:
                links.append(resolve(b['sitePath'],name))
                links.extend(resolve(n['path'],name) for n in b['neighborhoods'])
        return name,local_errors,details,links,set(ids)|set(doc.xpath('//a/@name')),counts
    with ThreadPoolExecutor(max_workers=12) as pool:
        for i,(name,problems,details,links,ids,counts) in enumerate(pool.map(inspect,manifest['files'].items()),1):
            for problem in problems:check(False,problem,file=name)
            destinations.update(links)
            if name.endswith('.html'):all_ids[name]=ids;incoming.update(counts or [])
            if details:article_texts.append(details)
            if i%2000==0:print(json.dumps({'filesChecked':i,'errors':len(errors)}),flush=True)
    for dest,fragment in destinations:
        check(dest in manifest['files'] and (root/dest).is_file(),'Internal destination missing/outside snapshot',file=dest)
        if fragment and dest.endswith('.html'):check(fragment in all_ids.get(dest,set()),'Internal anchor missing',file=dest,anchor=fragment)
    for a,chosen in zip(articles,selection['articles']):
        check(a['number']==chosen['number'] and a['title']!=chosen['folder'],'Title adaptation')
        check(sha((Path(selection['source'])/chosen['folder']/chosen['file']).read_bytes())==chosen['sha256'],'Manuscript changed',folder=chosen['folder'])
        for image in a['images']:
            origin=Path(selection['source'])/'1 이미지'/image['source']
            check(sha(origin.read_bytes())==sha((root/image['path']).read_bytes())==image['sha256'],'Original photo bytes changed',file=image['path'])
            with Image.open(root/image['path']) as im:check(im.size==(image['width'],image['height']),'Photo dimensions')
    previous=load(out.parent/'jeonguk-education-info-20261002'/'source-mapping.json')
    check(not ({a['folder'] for a in selection['articles']}&{a['sourceFolder'] for a in previous}),'Previously posted source selected')
    check(not ({a['sha256'] for a in selection['articles']}&{a['sourceHash'] for a in previous}),'Previously posted manuscript hash')
    def shingles(text):
        text=re.sub(r'\s+','',text);return set(text[i:i+10] for i in range(len(text)-9))
    new_cores=[shingles(a['intro']+''.join(p for _,ps in a['sections'] for p in ps)) for a in articles]
    old_cores=[]
    for old in load(out/'existing-articles.json'):
        name=old['path'].lstrip('/')+'index.html';doc=html.fromstring(originals[name])
        old_cores.append((name,shingles(''.join(doc.xpath('//main//p/text()')))))
    pair=max((len(x&y)/len(x|y),articles[i]['number'],articles[j]['number']) for i,x in enumerate(new_cores) for j,y in enumerate(new_cores) if j>i)
    old_pair=max((len(x&y)/len(x|y),articles[i]['number'],name) for i,x in enumerate(new_cores) for name,y in old_cores if y)
    check(pair[0]<.18 and old_pair[0]<.18,'Near duplicate article text',newMaximum=pair,priorMaximum=old_pair)
    state=load(out/'initial-state.json');status=subprocess.check_output(['git','--no-optional-locks','status','--porcelain=v1','-z','--untracked-files=all'],cwd=AUTHOR)
    check(sha(status)==state['authorStatusHash'],'Authoring checkout changed')
    report={'root':str(root),'sitemapPages':10750,'publicFilesChecked':len(manifest['files']),'existingPagesPreserved':stats['preserved'],'newArticles':30,'articleImages':90,'indexedArticles':128,'contextualPages':len(mapping),'internalDestinationsChecked':len(destinations),'minimumArticleCharacters':min(v for _,v in article_texts),'maximumNewSimilarity':pair,'maximumPriorSimilarity':old_pair,'sourceUnchanged':sha(status)==state['authorStatusHash'],'errorCount':len(errors),'errors':errors,'newArticleIncomingContextLinks':{a['path']:incoming[a['path'].lstrip('/')+'index.html'] for a in articles}}
    (out/args.report_name).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('errors','newArticleIncomingContextLinks')},ensure_ascii=False),flush=True)
    if errors:print(json.dumps(errors[:20],ensure_ascii=False));raise SystemExit(1)

if __name__=='__main__':main()
