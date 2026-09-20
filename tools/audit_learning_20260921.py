"""Static regression checks, optionally followed by HTTP checks of all 27 pages."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit
from urllib.request import Request, urlopen

from lxml import etree, html

ROOT = Path(__file__).resolve().parents[1]
BASE = 'e1be0e55ae73bfe6a37d5f659bce91677f8f10ce'
HOST = 'xn--3e0bl59bm0ad17a.com'
DATE = '2026-09-21'
checks = 0


def check(condition, message):
    global checks
    checks += 1
    if not condition: raise AssertionError(message)


def text(node): return ' '.join(node.text_content().split())


def graph(doc):
    return [n for s in doc.xpath('//script[@type="application/ld+json"]/text()') for g in [json.loads(s)] for n in g.get('@graph',[g])]


def types(node):
    t=node.get('@type');return t if isinstance(t,list) else [t]


def old(path): return subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT)


def parse(raw): return html.document_fromstring(raw.decode('utf-8-sig'))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--http-origin');args=ap.parse_args()
    data=json.loads((ROOT/'tools/learning-upgrade-20260921.json').read_text('utf-8'))
    paths=['index.html','학습코칭/index.html','과목별학원/index.html','전국학원/index.html']
    paths += ['과목별학원/'+s+'/index.html' for s in data]
    paths += [p.relative_to(ROOT).as_posix() for p in (ROOT/'전국학원').glob('*/index.html')]
    check(len(paths)==27,'27 pages')
    cache={};titles=[];descriptions=[];destinations=set();assets=set();existing_broken=[]
    def read(path):
        if path not in cache:cache[path]=parse(path.read_bytes())
        return cache[path]
    for rel in paths:
        doc=read(ROOT/rel);before=parse(old(rel));g=graph(doc);old_g=graph(before)
        check(doc.get('lang')=='ko',f'{rel}: language')
        check(len(doc.xpath('//h1'))==1,f'{rel}: h1')
        ids=doc.xpath('//@id');check(len(ids)==len(set(ids)),f'{rel}: duplicate DOM ids')
        check(len(doc.xpath('//title'))==1,f'{rel}: title count')
        title=doc.xpath('string(//title)');description=doc.xpath('string(//meta[@name="description"]/@content)')
        titles.append(title);descriptions.append(description)
        canonical=doc.xpath('//link[@rel="canonical"]/@href')
        check(canonical==before.xpath('//link[@rel="canonical"]/@href'),f'{rel}: canonical preserved')
        check(len(canonical)==1 and urlsplit(canonical[0]).hostname==HOST,f'{rel}: canonical domain')
        url=unquote(canonical[0]);destinations.add(urlsplit(url).path)
        for key,value,attr in [('og:title',title,'property'),('og:description',description,'property'),('og:url',canonical[0],'property'),('twitter:title',title,'name'),('twitter:description',description,'name')]:
            check(doc.xpath(f'//meta[@{attr}="{key}"]/@content')==[value],f'{rel}: {key}')
        for key in ['naver-site-verification','google-site-verification','robots']:
            check(doc.xpath(f'//meta[@name="{key}"]/@content')==before.xpath(f'//meta[@name="{key}"]/@content'),f'{rel}: {key} preserved')
        for tag in ['header','footer']:
            check([text(n) for n in doc.xpath('//'+tag)]==[text(n) for n in before.xpath('//'+tag)],f'{rel}: {tag} preserved')
        original_centers=[n for n in old_g if set(types(n)) & {'EducationalOrganization','LocalBusiness'}]
        check(original_centers==[n for n in g if set(types(n)) & {'EducationalOrganization','LocalBusiness'}],f'{rel}: verified center facts')
        check(set(before.xpath('//main//img/@src')) <= set(doc.xpath('//main//img/@src')),f'{rel}: previous images retained')
        check(not doc.xpath('//iframe'),f'{rel}: no eager video iframe')
        for n in g:
            if n.get('@type') in ('WebPage','CollectionPage','Article'):
                check(n.get('dateModified')==DATE,f'{rel}: modified date')
                check(n.get('description')==description,f'{rel}: schema description')
            if n.get('@type')=='FAQPage':
                visible=[(text(d.find('summary')),' '.join(text(x) for x in d if x.tag!='summary')) for d in doc.xpath('//main//details[summary]')]
                structured=[(x['name'],x['acceptedAnswer']['text']) for x in n['mainEntity']]
                check(visible==structured,f'{rel}: FAQ parity')
            if n.get('@type')=='ItemList':
                check(n.get('numberOfItems',len(n['itemListElement']))==len(n['itemListElement']),f'{rel}: ItemList size')
        before_links={unquote(h) for h in before.xpath('//a/@href')}
        check(before_links <= {unquote(h) for h in doc.xpath('//a/@href')},f'{rel}: old link destinations retained')
        for attr in ['//a/@href','//img/@src','//script[@src]/@src','//link[@rel="stylesheet"]/@href']:
            for href in doc.xpath(attr):
                u=urlsplit(urljoin(url,href))
                if u.hostname!=HOST or u.scheme not in ('https','http'):continue
                p=ROOT/unquote(u.path).lstrip('/')
                if p.is_dir():p=p/'index.html'
                if not p.is_file() and unquote(href) in before_links:
                    existing_broken.append((rel,href));continue
                check(p.is_file(),f'{rel}: missing {href}')
                if u.fragment and p.suffix=='.html':
                    target=read(p);matches=target.xpath('//*[@id=$id or @name=$id]',id=unquote(u.fragment))
                    if not matches and unquote(href) in before_links:
                        existing_broken.append((rel,href));continue
                    check(bool(matches),f'{rel}: missing fragment {href}')
                if p.suffix in ('.png','.webp','.jpg','.css','.js'):assets.add(u.path)
        for img in doc.xpath('//main//img'):
            check(bool(img.get('alt')),f'{rel}: image alt')
            check(bool(img.get('width') and img.get('height')),f'{rel}: image size')
        if rel.split('/')[0]=='과목별학원' and len(rel.split('/'))==3:
            check(len(doc.xpath('//div[@class="subject-local-grid"]/a'))==371,f'{rel}: all 371 links')
            check(len(doc.xpath('//form[@data-hub-search]'))==1,f'{rel}: search form')
    check(len(titles)==len(set(titles)),'unique titles')
    check(len(descriptions)==len(set(descriptions)),'unique descriptions')
    def sitemap(raw):
        root=etree.fromstring(raw)
        return {unquote(n.find('{*}loc').text):(n.find('{*}lastmod').text if n.find('{*}lastmod') is not None else None) for n in root}
    a=sitemap(old('sitemap.xml'));b=sitemap((ROOT/'sitemap.xml').read_bytes())
    check(a.keys()==b.keys(),'sitemap URL set unchanged')
    for url,date in b.items():
        if urlsplit(url).path in destinations:check(date==DATE,'changed sitemap date '+url)
        else:check(date==a[url],'unrelated sitemap date preserved '+url)
    coaching=read(ROOT/'학습코칭/index.html')
    positions=[x.get('id') for x in coaching.xpath('//main/section')]
    check(positions.index('learning-articles')>positions.index('coaching-questions'),'article list follows coaching information')
    check(len(coaching.xpath('//section[@id="learning-articles"]//a[contains(@class,"ui-card")]'))==20,'all 20 articles retained')
    check(not existing_broken,f'Existing broken links in touched pages need review: {existing_broken[:12]}')
    report={'passed_checks':checks,'pages':len(paths),'subject_hubs':10,'regional_hubs':13,'subject_child_links':3710,'sitemap_urls':len(b),'assets':len(assets)}
    if args.http_origin:
        origin=args.http_origin.rstrip('/')
        def request(path):
            req=Request(origin+quote(unquote(path),safe='/#?=&'),headers={'User-Agent':'Mozilla/5.0 (compatible; JeongukReleaseQA/1.0)'})
            with urlopen(req,timeout=45) as r:return path,r.status,r.headers.get('Content-Type',''),r.read()
        with ThreadPoolExecutor(max_workers=5) as pool:
            for path,status,ctype,body in pool.map(request,sorted(destinations)):
                check(status==200,'HTTP '+path)
                doc=parse(body)
                check(doc.xpath('//body/@data-learning-release')==[DATE],'live release '+path)
                local=read(ROOT/path.strip('/')/'index.html' if path!='/' else ROOT/'index.html')
                check(doc.xpath('string(//title)')==local.xpath('string(//title)'),'live title '+path)
                check(doc.xpath('//link[@rel="canonical"]/@href')==local.xpath('//link[@rel="canonical"]/@href'),'live canonical '+path)
                check(graph(doc)==graph(local),'live schema '+path)
                check(text(doc.find('body/main'))==text(local.find('body/main')),'live content '+path)
            for path,status,ctype,body in pool.map(request,sorted(assets)):
                check(status==200,'asset HTTP '+path)
                check(body==(ROOT/unquote(path).lstrip('/')).read_bytes(),'asset bytes '+path)
        report['http_pages']=len(destinations);report['http_assets']=len(assets);report['passed_checks']=checks
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
