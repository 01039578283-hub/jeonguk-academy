"""Audit all new directory pages and preservation of the pre-existing site."""
from pathlib import Path
from collections import Counter
from urllib.parse import unquote, urlsplit, urljoin
import hashlib, json, re, sys, zipfile
from lxml import html, etree
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'tools/reports/branch-directory-20260925'
DATA=ROOT/'tools/data/branch-directory'
ORIGIN='https://xn--3e0bl59bm0ad17a.com'
load=lambda p:json.loads(p.read_text('utf-8'))
build=load(REPORT/'build.json');base=load(REPORT/'baseline.json');facts=load(DATA/'centers.json')
centers={c['path']:c for c in facts['centers']}
errors=[];checks=0;links_checked=0;images_checked=set();old_count=0;related_count=0
def check(ok,label,path):
    global checks
    checks+=1
    if not ok:errors.append({'path':path,'issue':label})
def text(n):return ' '.join(n.text_content().split())
cache={}
def doc(p):
    if p not in cache:cache[p]=html.document_fromstring(p.read_bytes())
    return cache[p]
titles=[];descs=[];types=Counter()
for path in build['created']:
    file=ROOT/path.strip('/')/'index.html';d=doc(file);plain=text(d.find('body'))
    meta=lambda name,prop=False:d.xpath('//meta[@'+('property' if prop else 'name')+'="'+name+'"]/@content')
    desc=meta('description');title=d.xpath('//title/text()');titles+=title;descs+=desc
    check(len(title)==1 and len(d.xpath('//h1'))==1,'single title and h1',path)
    check(len(desc)==1 and 25<=len(desc[0])<=80,'description length',path)
    check(desc==meta('og:description',True)==meta('twitter:description'),'description alignment',path)
    check(title==meta('og:title',True)==meta('twitter:title'),'title alignment',path)
    canonical=d.xpath('//link[@rel="canonical"]/@href')
    check(len(canonical)==1 and unquote(canonical[0])==ORIGIN+path,'self canonical',path)
    check(canonical==meta('og:url',True),'OG canonical alignment',path)
    check(meta('robots')==['index,follow'],'robots',path)
    check(meta('og:image',True)==meta('twitter:image') and bool(meta('og:image',True)),'social image',path)
    check(d.xpath('string(//p[@class="jd-lead"])')==desc[0],'lead is accurate shared answer',path)
    check(d.xpath('//time/@datetime')==['2026-09-25'],'real date visible',path)
    check(not any(t in plain for t in ['OO학생','학부모님 학생','[후보','휴·폐교','대상 미확인']),'no unverified placeholders',path)
    nodes=d.xpath('//*[@id]');ids=[n.get('id') for n in nodes]
    check(len(ids)==len(set(ids)),'unique fragment IDs',path)
    graph=json.loads(d.xpath('string(//script[@type="application/ld+json"])'))['@graph']
    bytype={}
    for n in graph:
        ts=n.get('@type',[]);ts=[ts] if isinstance(ts,str) else ts
        for t in ts:bytype.setdefault(t,[]).append(n);types[t]+=1
    wp=bytype.get('WebPage',bytype.get('CollectionPage'))
    check(wp and wp[0]['description']==desc[0] and wp[0]['dateModified']=='2026-09-25','page schema description/date',path)
    breadcrumb=bytype['BreadcrumbList'][0]['itemListElement']
    check([n['position'] for n in breadcrumb]==list(range(1,len(breadcrumb)+1)),'breadcrumb positions',path)
    check(unquote(breadcrumb[-1]['item'])==ORIGIN+path,'breadcrumb last URL',path)
    faqs=[(text(n.find('summary')),text(n.find('p'))) for n in d.xpath('//details[@class="jd-faq"]')]
    check(faqs==[(n['name'],n['acceptedAnswer']['text']) for n in bytype['FAQPage'][0]['mainEntity']],'FAQ visible/schema equality',path)
    for a in d.xpath('//a[@href]|//link[@rel="stylesheet"]|//script[@src]'):
        u=a.get('href') or a.get('src');absolute=urljoin(ORIGIN+path,u);parsed=urlsplit(absolute)
        if parsed.netloc!=urlsplit(ORIGIN).netloc:continue
        route=unquote(parsed.path);dest=ROOT/route.lstrip('/')
        if route.endswith('/'):dest=dest/'index.html'
        check(dest.is_file(),'internal destination '+u,path);links_checked+=1
        if parsed.fragment and dest.is_file() and dest.suffix=='.html':
            check(unquote(parsed.fragment) in doc(dest).xpath('//*[@id]/@id'),'fragment '+u,path)
    for im in d.xpath('//img'):
        src=im.get('src');asset=ROOT/unquote(src).lstrip('/')
        check(asset.is_file(),'image exists '+src,path)
        if asset.is_file() and src not in images_checked:
            with Image.open(asset) as picture:check((int(im.get('width')),int(im.get('height')))==picture.size,'image dimensions '+src,path)
            images_checked.add(src)
        check(bool(im.get('alt')) or im.get('hidden') is not None,'image text alternative',path)
    if path in centers:
        c=centers[path]
        check(c['registeredName'] in plain and c['address'] in plain,'actual registration/address',path)
        check(c['registrationNumber'] in plain,'registration number',path)
        for t in c['fees']:
            for row in t['rows']:
                check(all(v in plain for v in row),'tuition row matches source',path)
        check(bool(bytype.get('EducationalOrganization')) and bool(bytype.get('LocalBusiness')),'center types',path)
        check(bytype['LocalBusiness'][0]['address']['streetAddress']==c['address'],'center schema address',path)
        check(len(bytype.get('Service',[]))==len([g for g in c['subjects'].values() if g]),'verified services only',path)
        check(all(m['mode']=='center' for m in c['photos']) or 'image' not in bytype['LocalBusiness'][0] or len(bytype['LocalBusiness'][0]['image'])==len([m for m in c['photos'] if m['mode']=='center']),'no common photo asserted as actual branch',path)
        image_nodes=d.xpath('//section[@id="learning-materials"]//img')
        check(len(image_nodes)==3 and image_nodes[0].get('hidden') is not None and image_nodes[1].get('src')==c['photos'][0]['src'] and image_nodes[2].get('src')==c['map']['src'],'representative body map order',path)
        order=d.xpath('//main//section/@id');check(order.index('learning-materials')<order.index('center-facts'),'images before center facts',path)
        if 'learning-space' in order:check(order.index('learning-space')>order.index('learning-materials'),'gallery after map',path)
        if c['feeMode']=='regional-reference':check('이 지점의 확정 교습비를 뜻하지 않습니다' in plain,'reference fee disclosure',path)
        related_count+=len(d.xpath('//section[@id="related-pages"]//a[contains(@href,"전국학원")]'))
    else:
        check(not d.xpath('//main//img'),'no long promotional media on hubs',path)
        visible=d.xpath('//article[@data-branch-card]//h3/a/@href')
        check(len(visible)==bytype['ItemList'][0]['numberOfItems'],'ItemList count',path)
        check(set(visible)=={unquote(urlsplit(x['url']).path) for x in bytype['ItemList'][0]['itemListElement']},'ItemList destinations',path)

check(len(titles)==len(set(titles)),'no duplicate titles','all new pages')
check(len(descs)==len(set(descs)),'no duplicate descriptions','all new pages')

with zipfile.ZipFile(base['backup']) as z:
    for rel,previous in base['pages'].items():
        f=ROOT/rel;raw=f.read_text('utf-8-sig');before=z.read(rel).decode('utf-8-sig')
        # Parsing normalizes harmless CRLF differences from the snapshot.
        d=html.document_fromstring(raw)
        for key,expr in [('title','string(//title)'),('description','string(//meta[@name="description"]/@content)'),('canonical','string(//link[@rel="canonical"]/@href)'),('robots','string(//meta[@name="robots"]/@content)')]:check(d.xpath(expr)==previous[key],'legacy '+key+' preserved',rel)
        oldmain=re.search(r'<main\b.*?</main>',before,re.S)
        newmain=re.search(r'<main\b.*?</main>',raw,re.S)
        if oldmain and newmain:
            stripped=re.sub(r'<section class="ui-section wrap" id="branch-directory-entry">.*?</section>','',newmain[0],flags=re.S)
            check(re.sub(r'\r\n?', '\n', stripped)==re.sub(r'\r\n?', '\n', oldmain[0]),'legacy manuscript preserved',rel)
        check(len(d.xpath('//header//a[@href="/지점안내/"]'))==1,'legacy header directory link',rel)
        check(len(d.xpath('//footer//a[@href="/지점안내/"]'))==1,'legacy footer directory link',rel)
        old_count+=1
    original=etree.fromstring(z.read('sitemap.xml'))
sitemap=etree.parse(str(ROOT/'sitemap.xml'));ns={'s':'http://www.sitemaps.org/schemas/sitemap/0.9'}
urls=sitemap.xpath('//s:loc/text()',namespaces=ns);oldurls=original.xpath('//s:loc/text()',namespaces=ns)
norm=lambda u:unquote(u)
check(len(urls)==7396 and len(set(map(norm,urls)))==7396,'sitemap count and uniqueness','sitemap')
check(set(map(norm,oldurls)).issubset(set(map(norm,urls))),'old sitemap URLs preserved','sitemap')
check(set(ORIGIN+p for p in build['created']).issubset(set(map(norm,urls))),'new pages in sitemap','sitemap')
check('Disallow: /' not in (ROOT/'robots.txt').read_text('utf-8'),'robots does not block','robots.txt')
check(len(etree.parse(str(ROOT/'branch-updates.xml')).xpath('//item'))==50,'feed latest entries','branch-updates.xml')
check('/지점안내/' in (ROOT/'llms.txt').read_text('utf-8'),'directory guidance available','llms.txt')
report={'newPages':len(build['created']),'centers':len(centers),'existingPagesPreserved':old_count,'checks':checks,'internalLinksChecked':links_checked,'distinctImagesChecked':len(images_checked),'contextualLegacyLinks':related_count,'descriptionLength':{'min':min(map(len,descs)),'max':max(map(len,descs))},'duplicateTitles':len(titles)-len(set(titles)),'duplicateDescriptions':len(descs)-len(set(descs)),'schemaTypes':dict(types),'errors':errors}
(REPORT/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
sys.exit(bool(errors))
