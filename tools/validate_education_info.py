"""Whole-site preservation and new educational library release validation."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from urllib.parse import urlsplit,unquote
from html import unescape
import argparse,hashlib,json,re,zipfile
from lxml import html,etree

ROOT=Path(__file__).resolve().parents[1]
DAY='2026-10-03'
def load(p):return json.loads(p.read_text('utf-8-sig'))
def sha(b):return hashlib.sha256(b).hexdigest()
def norm(s):return s.replace('\r\n','\n')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report-dir',required=True);parser.add_argument('--root',default='.public-release');args=parser.parse_args()
    out=Path(args.report_dir);public=(ROOT/args.root).resolve();baseline=load(out/'before-release-public-manifest.json');manifest=load(ROOT/'release-public-manifest.json')
    generated=load(out/'generation.json');articles=load(out/'article-data.json');library=load(out/'library.json');errors=[];stats=Counter()
    def check(condition,reason,**details):
        if not condition:errors.append(dict(reason=reason,**details))
    with zipfile.ZipFile(out/'before-pages.zip') as z:originals={name:z.read(name).decode('utf-8') for name in z.namelist()}
    def preserve(item):
        name,old=item;new=(ROOT/name).read_text('utf-8')
        reduced=re.sub(r'<!-- education-info:start -->[\s\S]*?<!-- education-info:end -->','',new)
        reduced=re.sub(r'<a\b[^>]*data-education-menu[^>]*>교육정보</a>','',reduced)
        old_query=re.search(r'/assets/unified-ui\.css(?:\?[^"\s>]*)?',old)
        if old_query:reduced=re.sub(r'/assets/unified-ui\.css(?:\?[^"\s>]*)?',lambda _:old_query[0],reduced)
        return name,norm(reduced)==norm(old),new.count('data-education-menu'),new.count('data-education-bridge=')
    with ThreadPoolExecutor(max_workers=12) as pool:
        for name,identical,menus,bridges in pool.map(preserve,originals.items()):
            check(identical,'Existing content changed outside authorized inserts',file=name)
            check(menus==2 and bridges==1,'Existing navigation/module count',file=name,menus=menus,bridges=bridges)
            stats['existingPagesPreserved']+=int(identical)
    check(set(baseline['files'])<=set(manifest['files']),'Existing public asset removed')
    new_pages=generated['newPages'];check(len(new_pages)==31,'New page count')
    anchor_cache={};links=set();bodies=[];new_titles=set();images=[]
    def internal(value,current):
        from urllib.parse import urljoin
        u=urlsplit(urljoin('https://xn--3e0bl59bm0ad17a.com/'+current,value))
        if u.scheme not in ('http','https') or u.netloc not in ('xn--3e0bl59bm0ad17a.com','전국학원.com'):return
        path=unquote(u.path).lstrip('/');dest=path+'index.html' if not path or path.endswith('/') else path
        if not Path(dest).suffix:dest+='/index.html'
        links.add((dest,unquote(u.fragment)))
    for name in new_pages:
        raw=(public/name).read_text('utf-8');doc=html.fromstring(raw);path='/'+name.removesuffix('index.html')
        ids=doc.xpath('//@id');check(len(ids)==len(set(ids)),'Duplicate HTML id',file=name)
        check(len(doc.xpath('//h1'))==1,'H1 count',file=name)
        check(len(doc.xpath('//link[@rel="canonical"]'))==1,'Canonical count',file=name)
        canonical=doc.xpath('//link[@rel="canonical"]/@href')[0]
        check(unquote(urlsplit(canonical).path)==path,'Canonical path',file=name)
        desc=doc.xpath('//meta[@name="description"]/@content')[0]
        check(0<len(desc)<=80 and desc.endswith('.'),'Description sentence/length',file=name)
        check(doc.xpath('//meta[@property="og:description"]/@content')==[desc] and doc.xpath('//meta[@name="twitter:description"]/@content')==[desc],'Social metadata mismatch',file=name)
        check('편집 원칙' not in raw and 'WAWA_유용한정보' not in raw and 'C:\\Users' not in raw,'Private or excluded content',file=name)
        check(raw.count('data-education-menu')==2,'Education menu count',file=name)
        schema=[json.loads(s) for s in doc.xpath('//script[@type="application/ld+json"]/text()')]
        graph=[node for obj in schema for node in obj.get('@graph',[obj])]
        for a in doc.xpath('//a[@href]'):internal(a.get('href'),name)
        for src in doc.xpath('//img/@src | //script[@src]/@src | //link[@rel="stylesheet"]/@href'):internal(src,name)
        locations=json.loads(doc.xpath('//script[@id="ei-locations"]/text()')[0]);check(len(locations)==193,'Location data count',file=name)
        for b in locations:
            internal(b['sitePath'],name)
            for n in b['neighborhoods']:internal(n['path'],name)
        if name=='교육정보/index.html':
            cards=doc.xpath('//*[@data-library-card]');check(len(cards)==98,'Library card count')
            check(Counter(c.get('data-kind') for c in cards)=={'new':30,'guide':48,'coaching':20},'Existing article coverage')
            check(not any(c.get('hidden') is not None for c in cards),'No-JS article coverage')
            rendered={unquote(urlsplit(c.xpath('.//h3/a/@href')[0]).path) for c in cards}
            check(rendered=={a['path'] for a in library},'Library destinations')
            listing=[n for n in graph if n.get('@type')=='ItemList'][0]
            check(listing['numberOfItems']==98 and len(listing['itemListElement'])==98,'Library schema count')
        else:
            a=next(x for x in articles if x['path']==path);title=doc.xpath('string(//h1)');new_titles.add(title)
            check(title==a['title'],'Article title mismatch',file=name)
            check(len(doc.xpath('//*[@data-education-article]'))==1,'Article container',file=name)
            content=doc.xpath('//*[@data-education-article]')[0];core=' '.join(content.itertext());bodies.append((name,core))
            check(len(core)>1700,'Insufficient article substance',file=name,length=len(core))
            article_schema=[n for n in graph if n.get('@type')=='Article']
            check(len(article_schema)==1 and article_schema[0]['headline']==title and article_schema[0]['datePublished']==DAY,'Article schema mismatch',file=name)
            photos=doc.xpath('//*[@data-education-image]');check(len(photos)==3,'Article image count',file=name)
            for figure,p in zip(photos,a['images']):
                img=figure.xpath('.//img')[0];check(img.get('src')=='/'+p['path'] and img.get('width')==str(p['width']) and img.get('height')==str(p['height']) and img.get('alt')==p['alt'],'Image attributes',file=name)
                check(img.get('loading')=='lazy' and '참고 이미지' in figure.text_content(),'Image loading/disclosure',file=name)
                images.append(p['path']);check(sha((public/p['path']).read_bytes())==p['sha256'],'Original image bytes changed',file=p['path'])
            check(len(doc.xpath('//*[@id="check"]//li'))==3,'Check list count',file=name)
    check(len(images)==len(set(images))==90,'Unique image destination count')
    check(len(new_titles)==30,'Unique title count')
    # Check new links on every old page; original links are preserved byte for byte.
    for name in originals:
        raw=(ROOT/name).read_text('utf-8');module=re.search(r'<!-- education-info:start -->([\s\S]*?)<!-- education-info:end -->',raw)
        check(module is not None,'Context module absent',file=name)
        if module:
            for href in re.findall(r'href="([^"]+)"',module[1]):internal(unescape(href),name)
    for dest,fragment in sorted(links):
        file=public/dest;check(file.is_file(),'Internal destination absent',file=dest)
        check(dest in manifest['files'],'Internal destination outside manifest',file=dest)
        if fragment and file.is_file() and dest.endswith('.html'):
            if dest not in anchor_cache:anchor_cache[dest]=set(html.fromstring(file.read_bytes()).xpath('//@id | //a/@name'))
            check(fragment in anchor_cache[dest],'Anchor absent',file=dest,anchor=fragment)
    sitemap=etree.fromstring((public/'sitemap.xml').read_bytes());ns={'s':'http://www.sitemaps.org/schemas/sitemap/0.9'}
    urls=sitemap.xpath('//s:url/s:loc/text()',namespaces=ns);paths=[unquote(urlsplit(u).path) for u in urls]
    expected={'/'+n.removesuffix('index.html') for n in manifest['files'] if n.endswith('.html')}
    check(len(paths)==len(set(paths))==10636 and set(paths)==expected,'Complete sitemap coverage',count=len(paths))
    baseline_config=load(out/'before-seo-descriptions.json');config=load(ROOT/'seo-descriptions.json')
    check(all(config['pages'].get(k)==v for k,v in baseline_config['pages'].items()),'Existing description config changed')
    # Character shingles flag near duplicates without penalizing shared short terms.
    cores=[]
    for a in articles:
        text=a['intro']+''.join(p for _,ps in a['sections'] for p in ps)
        text=re.sub(r'\s+','',text);cores.append(set(text[i:i+10] for i in range(len(text)-9)))
    similarity=max((len(x&y)/len(x|y),i+1,j+1) for i,x in enumerate(cores) for j,y in enumerate(cores) if j>i)
    check(similarity[0]<.18,'New articles too similar',maximum=similarity)
    report=dict(existingPagesPreserved=stats['existingPagesPreserved'],newPages=len(new_pages),newArticles=30,indexedArticles=98,articleImages=len(images),internalDestinationsChecked=len(links),sitemapPages=len(paths),minimumArticleCharacters=min(len(c) for _,c in bodies),maximumArticleSimilarity=similarity,errorCount=len(errors),errors=errors)
    (out/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({**report,'errors':errors[:20]},ensure_ascii=False))
    raise SystemExit(bool(errors))

if __name__=='__main__':main()
