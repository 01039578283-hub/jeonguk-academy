"""Verify the complete sitemap, and compare migration output with its baseline."""
import argparse
import hashlib
import json
import posixpath
import re
from collections import Counter, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
from lxml import html, etree

ROOT=Path(__file__).resolve().parents[1]
HOST='xn--3e0bl59bm0ad17a.com'
ORIGIN='https://'+HOST


def digest(s):return hashlib.sha256(s.encode()).hexdigest()
def text(n):return ' '.join(n.text_content().split())
def cls(n,c):return c in (n.get('class') or '').split()
def byclass(d,c):return d.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " '+c+' ")]')
def urlkey(u):return unquote(urlsplit(u).path).removesuffix('index.html') or '/'


def inspect(raw):
    d=html.fromstring(raw)
    graph=[]
    for script in d.xpath('//script[@type="application/ld+json"]'):
        obj=json.loads(script.text);graph.extend(obj.get('@graph',[obj]))
    def walk(n):
        if isinstance(n,list):
            for v in n:yield from walk(v)
        elif isinstance(n,dict):
            yield n
            for v in n.values():yield from walk(v)
    nodes=list(walk(graph))
    canonical=d.xpath('//link[@rel="canonical"]/@href')
    desc=d.xpath('//meta[@name="description"]/@content')
    main=d.xpath('//main')[0]
    return d,main,graph,{
        'canonical':canonical,'h1':[text(x) for x in d.xpath('//h1')],
        'title':d.xpath('string(//title)'),'description':desc,
        'og':d.xpath('//meta[@property="og:description"]/@content'),
        'twitter':d.xpath('//meta[@name="twitter:description"]/@content'),
        'robots':d.xpath('//meta[@name="robots"]/@content'),
        'header':digest(''.join(re.findall(r'<header\b.*?</header>',raw,re.S))),
        'footer':digest(''.join(re.findall(r'<footer\b.*?</footer>',raw,re.S))),
        'images':Counter(d.xpath('//img/@src')),
        'reviews':sum(any(t in (n.get('@type') if isinstance(n.get('@type'),list) else [n.get('@type')]) for t in ['Review','AggregateRating']) for n in nodes),
        'oldHours':sum(n.get('openingHours')=='Mo-Sa 12:00-24:00' for n in nodes),
        'tracker':len([x for x in d.xpath('//script[@src]/@src') if 'wawa-visit-collector' in x]),
        'ids':d.xpath('//*[@id]/@id'),
        'links':d.xpath('//a[@href]/@href'),
        'assets':d.xpath('//img/@src | //script[@src]/@src | //link[@rel="stylesheet"]/@href'),
        'migrated':main.get('data-naver-improved')=='2026-09-28',
        'schemaDescriptions':[n.get('description') for n in graph if n.get('@type') in ['WebPage','Article']]
    }


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--site',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True);parser.add_argument('--built',action='store_true')
    args=parser.parse_args()
    migration=json.loads((args.report/'migration.json').read_text(encoding='utf-8'))
    changed={p['path']:p for p in migration['pages']}
    baseline_path=args.report/'baseline-checks.json'
    baseline=json.loads(baseline_path.read_text(encoding='utf-8')) if baseline_path.exists() else {}
    manifest=json.loads((ROOT/'release-public-manifest.json').read_text(encoding='utf-8'))
    available=set(manifest['files'])|{'assets/naver-region-guide.css'}
    rels=[p for p in manifest['files'] if p.endswith('.html')]
    records={};errors=[];baseline_added={};counts=Counter()
    def file_for(rel):
        p=args.site/rel
        return p if p.exists() else ROOT/rel
    def examine(rel):
        path=file_for(rel);raw=path.read_text(encoding='utf-8-sig')
        d,main,graph,r=inspect(raw);issues=[]
        old=baseline.get(rel)
        if old is None:
            _,_,_,old=inspect((ROOT/'.public-release'/rel).read_text(encoding='utf-8-sig'))
        if r['canonical']!=old['canonical']:issues.append('canonical changed')
        if r['robots']!=old['robots']:issues.append('index policy changed')
        if len(r['h1'])!=1:issues.append('H1 count')
        if len(r['description'])!=1 or not 1<=len(r['description'][0])<=80:issues.append('description length/count')
        if r['description']!=r['og'] or r['description']!=r['twitter']:issues.append('meta descriptions differ')
        if r['reviews']:issues.append('review/rating remains')
        if args.built and r['tracker']!=1:issues.append('analytics missing/duplicated')
        if rel in changed:
            if not r['migrated']:issues.append('migration marker missing')
            if r['oldHours']:issues.append('fabricated fixed hours remains')
            if r['header']!=old['header'] or r['footer']!=old['footer']:issues.append('header/footer changed')
            expected_images=Counter()
            replacements={x['from']:x['to'] for x in changed[rel].get('mapImageRepairs',[])}
            for src,n in old['images'].items():
                normalized=unquote(src)
                expected_images[replacements.get(normalized,normalized)]+=n
            for src,target in replacements.items():
                old_asset=unquote(urlsplit(urljoin(r['canonical'][0],src)).path).lstrip('/')
                new_asset=unquote(urlsplit(urljoin(r['canonical'][0],target)).path).lstrip('/')
                if old_asset in available or new_asset not in available or not new_asset.startswith('assets/maps/'):
                    issues.append('unverified map replacement')
            actual_images=Counter()
            for src,n in r['images'].items():actual_images[unquote(src)]+=n
            if actual_images!=expected_images:issues.append('images unexpectedly changed')
            if any(desc!=r['description'][0] for desc in r['schemaDescriptions']):issues.append('page schema descriptions differ')
            if 'data-naver-improved="2026-09-28"' not in raw:issues.append('marker')
            # New FAQ text must be exactly present in the visible DOM.
            visible=text(main)
            for n in graph:
                if n.get('@type')=='FAQPage':
                    for q in n['mainEntity']:
                        if q['name'] not in visible or q['acceptedAnswer']['text'] not in visible:issues.append('FAQ body/schema mismatch')
            if 'branchHighImproved' not in changed[rel]:
                if len(byclass(main,'ng-facts'))!=1 or len(byclass(main,'wawa-center-snippet'))!=1:issues.append('factual section coverage')
                branch_links=[u for u in main.xpath('.//section[@id="center-summary"]//a/@href') if urlkey(u).startswith('/지점안내/')]
                if not branch_links:issues.append('actual branch link missing')
                h1=main.xpath('.//h1')[0];media=byclass(main,'ng-media')
                if len(media)!=1 or media[0].get('open') is not None:issues.append('long media not collapsed')
                if changed[rel]['mathRewritten'] and not changed[rel]['supported']:
                    if '수강 전 확인사항' not in r['h1'][0]:issues.append('unconfirmed grade title')
                    if any(n.get('@type')=='Service' for n in graph):issues.append('unconfirmed class advertised as service')
            if re.search(r'\[후보|\[.*?휴·폐교|OO학생|ㅇㅇ학생',text(main)):issues.append('unverified school/placeholder')
        # Every changed page's local fragment must remain usable. Existing
        # unrelated pre-migration fragment defects are recorded separately.
        if rel in changed:
            for href in r['links']:
                if href.startswith('#') and len(href)>1 and unquote(href[1:]) not in r['ids']:issues.append('missing anchor '+href)
        if len(r['ids'])!=len(set(r['ids'])) and rel in changed:issues.append('duplicate id')
        return rel,r,old,issues
    with ThreadPoolExecutor(max_workers=12) as pool:
        for i,(rel,r,old,issues) in enumerate(pool.map(examine,rels),1):
            records[rel]=r
            if rel not in baseline:baseline_added[rel]=old
            errors.extend({'file':rel,'reason':e} for e in issues)
            counts['pages']+=1;counts['migrated']+=r['migrated'];counts['reviewNodes']+=r['reviews']
            if i%2000==0:print('Validated',i,flush=True)
    urls={urlkey(r['canonical'][0]):rel for rel,r in records.items()}
    edges={};missing=[];assets_missing=[]
    for rel,r in records.items():
        base=r['canonical'][0];destinations=set()
        for href in r['links']:
            target=urlsplit(urljoin(base,href))
            if target.hostname not in [HOST,'전국학원.com']:continue
            key=urlkey(target.geturl())
            if key in urls:destinations.add(key)
            elif unquote(target.path).lstrip('/') not in available:missing.append((rel,href))
        edges[urlkey(base)]=destinations
        for src in r['assets']:
            target=urlsplit(urljoin(base,src))
            if target.hostname in [HOST,'전국학원.com'] and unquote(target.path).lstrip('/') not in available:assets_missing.append((rel,src))
    seen={'/'};queue=deque(['/'])
    while queue:
        for nxt in edges.get(queue.popleft(),set())-seen:seen.add(nxt);queue.append(nxt)
    orphaned=sorted(set(urls)-seen)
    dup_titles=[v for v,n in Counter(r['title'] for r in records.values()).items() if n>1]
    dup_desc=[v for v,n in Counter(r['description'][0] for r in records.values()).items() if n>1]
    if dup_titles:errors.append({'reason':'duplicate titles','count':len(dup_titles),'examples':dup_titles[:5]})
    if dup_desc:errors.append({'reason':'duplicate descriptions','count':len(dup_desc),'examples':dup_desc[:5]})
    if missing:errors.append({'reason':'missing internal pages','count':len(missing),'examples':missing[:12]})
    if assets_missing:errors.append({'reason':'missing assets','count':len(assets_missing),'examples':assets_missing[:12]})
    if orphaned:errors.append({'reason':'orphaned pages','count':len(orphaned),'examples':orphaned[:12]})
    counts.update({'changedPages':len(changed),'brokenInternalLinks':len(missing),'missingAssets':len(assets_missing),
                   'orphanedPages':len(orphaned),'duplicateTitles':len(dup_titles),'duplicateDescriptions':len(dup_desc),
                   'errors':len(errors)})
    if baseline_added:
        baseline.update(baseline_added);baseline_path.write_text(json.dumps(baseline,ensure_ascii=False),encoding='utf-8')
    result={'site':str(args.site),'built':args.built,'migrationSha256':hashlib.sha256((args.report/'migration.json').read_bytes()).hexdigest(),'counts':dict(counts),'errors':errors}
    (args.report/('verification-built.json' if args.built else 'verification-preview.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'counts':dict(counts),'errors':errors[:15]},ensure_ascii=False),flush=True)
    raise SystemExit(bool(errors))


if __name__=='__main__':main()
