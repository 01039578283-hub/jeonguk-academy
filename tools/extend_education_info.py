"""Add the reviewed October batch to a current snapshot without rebuilding old copy.

Requires the pre-change manifest, HTML archive and reviewed selection in a private
report directory. Original drafts and provenance never enter the public snapshot.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from urllib.parse import unquote
import argparse,copy,hashlib,json,re,zipfile
from lxml import html
import build_education_info as base
from education_info.batch_20261005 import ARTICLES,SOURCES
from education_info.images_20261005 import ALTS

ROOT=Path(__file__).resolve().parents[1]
DAY='2026-10-05'
START='<!-- education-expansion:start -->'
END='<!-- education-expansion:end -->'
sha=lambda b:hashlib.sha256(b).hexdigest()
load=lambda p:json.loads(p.read_text('utf-8-sig'))
write=base.write
NEXT={31:44,32:46,33:55,34:50,35:58,36:52,37:56,38:55,39:50,40:54,41:33,42:56,43:32,44:48,45:31,46:37,47:51,48:44,49:58,50:34,51:47,52:36,53:60,54:40,55:38,56:37,57:48,58:35,59:60,60:59}

def original_library(raw):
    items=[]
    for c in html.fromstring(raw).xpath('//*[@data-library-card]'):
        a=c.xpath('.//h3/a')[0];p=c.xpath('.//*[@class="ei-card-copy"]/p[not(@class)]')[0]
        item={'path':unquote(a.get('href')),'title':a.text_content(),'description':p.text_content(),'category':c.get('data-topic'),'kind':c.get('data-kind'),'audience':c.xpath('.//*[@class="ei-card-end"]')[0].text_content()}
        photos=c.xpath('.//img')
        if photos:
            im=photos[0];item['images']=[{'path':im.get('src').lstrip('/'),'width':int(im.get('width')),'height':int(im.get('height'))}]
        items.append(item)
    assert len(items)==98 and len({a['path'] for a in items})==98
    return items

def chosen_for(name,old_by_path,new_by_number):
    if name=='index.html':return [new_by_number[n] for n in (52,38,33)]
    elementary=bool(re.search(r'초등|초[1-6]',name))
    if '수학' in name:n=44 if elementary else 50 if '고' in name else 34
    elif '영어' in name:n=44 if elementary else 38
    elif '국어' in name:n=45
    elif any(t in name for t in ('과학','사회','역사')):n=31
    elif name.startswith('선생님찾기/'):n=60
    elif '학습진단' in name or name.startswith('상담문의/'):n=48
    elif elementary:n=35
    else:
        path='/'+name.removesuffix('index.html')
        old=old_by_path.get(path)
        if old:
            lists={'exam':[39,40,52,54],'subject':[31,34,38,44,45,50],'plan':[32,35,43,46,47,49,51,58],'support':[33,36,37,41,42,48,53,55,56,57,59,60]}
            candidates=lists[old['category']]
        elif name.startswith(('학습코칭/','학습커리큘럼/')):candidates=[32,35,43,46,47,49,51,58]
        elif name.startswith('지점안내/'):candidates=[33,41,55,59,60]
        else:candidates=[39,40,52,54]
        n=candidates[int(sha(name.encode())[:8],16)%len(candidates)]
    return [new_by_number[n]]

def links_for(items):
    return ''.join(f'<a href="{base.H(a["path"])}" data-education-added="{a["number"]}">{base.E(a["title"])} <span aria-hidden="true">↗</span></a>' for a in items)

def main():
    p=argparse.ArgumentParser();p.add_argument('--report-dir',required=True);p.add_argument('--teacher-model',required=True);args=p.parse_args()
    out=Path(args.report_dir).resolve();selected=load(out/'selection-final.json');before=load(out/'before-release-public-manifest.json')
    assert [a['number'] for a in ARTICLES]==list(range(31,61))
    with zipfile.ZipFile(out/'before-pages.zip') as z:originals={n:z.read(n).decode('utf-8') for n in z.namelist()}
    assert len(originals)==10720
    old=original_library(originals['교육정보/index.html']);old_by_path={a['path']:a for a in old}
    base.DAY=DAY;base.SOURCES.update(SOURCES)
    articles=copy.deepcopy(ARTICLES);changed=set();mapping=[]
    for a,selection in zip(articles,selected['articles']):
        assert a['number']==selection['number'] and a['title']!=selection['folder']
        assert len(a['description'])<=80 and a['description'].endswith('.')
        assert len(a['sections'])==4 and len(a['checks'])==3
        assert all(k in base.SOURCES for k in a['sources'])
        a['path']=base.route(a);a['kind']='new';a['nextPath']=base.route(next(v for v in articles if v['number']==NEXT[a['number']]))
        assert a['path'] not in old_by_path
        name=a['path'].lstrip('/')+'index.html'
        assert not (ROOT/name).exists() or ((out/'generation.json').exists() and name in load(out/'generation.json')['newPages'])
        a['images']=[]
        for i,(photo,alt) in enumerate(zip(selection['images'],ALTS[a['number']]),1):
            origin=Path(selected['source'])/'1 이미지'/photo['source'];raw=origin.read_bytes();assert sha(raw)==photo['sha256']
            path=f'assets/education-info/{a["number"]:02d}-{i}'+origin.suffix.lower()
            write(ROOT/path,raw);changed.add(path);a['images'].append({**photo,'path':path,'alt':alt+' · 참고 이미지'})
        mapping.append({'number':a['number'],'sourceFolder':selection['folder'],'sourceFile':selection['file'],'sourceHash':selection['sha256'],'intent':selection['intent'],'title':a['title'],'path':a['path'],'images':a['images']})
    assert len({p['sha256'] for a in articles for p in a['images']})==90
    new_by_number={a['number']:a for a in articles};library=[*articles,*old]
    assert len(library)==128 and len({a['path'] for a in library})==128
    original_hub=originals['교육정보/index.html']
    header=re.search(r'<header class="site-header">[\s\S]*?</header>',original_hub)[0]
    footer=re.search(r'<footer class="site-footer">[\s\S]*?</body>',original_hub)[0].replace('</body>','')
    model=load(Path(args.teacher_model));branches=[{k:b[k] for k in ('name','region','address','sitePath','neighborhoods')} for b in model['branches'] if b['sitePath']]
    assert len(branches)==193
    for b in branches:
        assert (ROOT/b['sitePath'].lstrip('/')/'index.html').is_file()
        for n in b['neighborhoods']:assert (ROOT/n['path'].lstrip('/')/'index.html').is_file()
    def update_existing(name):
        if name=='교육정보/index.html':return None
        raw=originals[name];chosen=chosen_for(name,old_by_path,new_by_number);links=links_for(chosen)
        if name=='index.html':
            module=START+f'<section class="education-bridge ju-wrap" id="home-new-education" data-education-expansion><div><p class="education-kicker">새로 더한 교육정보 30편</p><h2>오늘의 질문에서 다음 공부를 찾아보세요</h2><p>과목별 공부, 수업 선택과 학생·학부모의 생활 고민을 구체적인 예시로 안내합니다.</p></div><nav aria-label="새 교육정보 바로가기">{links}<a class="education-all" href="/교육정보/#library">교육정보 60편과 기존 가이드 보기 →</a></nav></section>'+END
            boundary=re.search(r'<section\b[^>]*id="home-curriculum"[^>]*>',raw);assert boundary
            updated=raw[:boundary.start()]+module+raw[boundary.start():]
        elif name.startswith('교육정보/'):
            module=START+f'<section class="education-bridge" data-education-expansion><div><p class="education-kicker">이어서 살펴볼 교육정보</p><h2>다음 고민도 함께 확인하세요</h2><p>새로 더한 글에서 구체적인 점검 방법을 찾아보세요.</p></div><nav aria-label="새로 더한 관련 교육정보">{links}<a class="education-all" href="/교육정보/#library">교육정보 전체 보기 →</a></nav></section>'+END
            assert '<section class="ei-related"' in raw
            updated=raw.replace('<section class="ei-related"',module+'<section class="ei-related"',1)
        else:
            bridge=re.search(r'<!-- education-info:start -->([\s\S]*?)<!-- education-info:end -->',raw);assert bridge,name
            marker='<a class="education-all"'
            assert bridge[1].count(marker)==1,name
            replacement=bridge[0].replace(marker,START+links+END+marker,1)
            updated=raw[:bridge.start()]+replacement+raw[bridge.end():]
        updated=re.sub(r'("dateModified"\s*:\s*")[^"]+("\s*)',lambda m:m[1]+DAY+m[2],updated)
        assert updated.count(START)==updated.count(END)==1,name
        write(ROOT/name,updated)
        return {'page':name,'targets':[a['path'] for a in chosen],'category':chosen[0]['category']}
    with ThreadPoolExecutor(max_workers=12) as pool:
        link_mapping=[v for v in pool.map(update_existing,originals) if v]
    changed.update(v['page'] for v in link_mapping)
    rendered,desc=base.hub(library,branches,header,footer)
    rendered=rendered.replace('<span class="ei-note-number">30</span>','<span class="ei-note-number">60</span>').replace('새롭게 더한 교육정보','주제별 교육정보').replace('새 교육정보 30편','교육정보 60편').replace('전체 98편 · 교육정보 30편','전체 128편 · 교육정보 60편')
    rendered=rendered.replace('새 교육정보와 기존 가이드를 한곳에서 찾아보세요.','새로 추가한 30편과 기존 글을 함께 찾아보세요.')
    curriculum=re.search(r'<!-- curriculum-link:start -->[\s\S]*?<!-- curriculum-link:end -->',original_hub)[0]
    rendered=rendered.replace('</main>',curriculum+'</main>',1)
    rendered=rendered.replace('</head>','<link rel="stylesheet" href="/assets/curriculum.css?v=20261003"></head>',1)
    write(ROOT/'교육정보/index.html',rendered);changed.add('교육정보/index.html')
    new_pages=[]
    config=load(out/'before-seo-descriptions.json')
    assert config['pages']['/교육정보']['description']==desc
    for a in articles:
        name=a['path'].lstrip('/')+'index.html'
        raw=base.render_article(a,library,branches,header,footer)
        raw=raw.replace('2026년 10월 3일','2026년 10월 5일').replace('확인일: 2026년 10월 2일','확인일: 2026년 10월 5일')
        write(ROOT/name,raw);changed.add(name);new_pages.append(name)
        config['pages'][a['path'].rstrip('/')]={'description':a['description'],'sources':[a['description']]}
    write(ROOT/'seo-descriptions.json',json.dumps(config,ensure_ascii=False,indent=2)+'\n')
    sitemap=(out/'before-sitemap.xml').read_text('utf-8')
    # Every prior indexed page received a content link; only genuinely changed pages are dated.
    assert {v['page'] for v in link_mapping}|{'교육정보/index.html'}==set(originals)
    sitemap=re.sub(r'<lastmod>[^<]+</lastmod>',f'<lastmod>{DAY}</lastmod>',sitemap)
    additions=''.join(f'<url><loc>{base.DOMAIN+base.H(a["path"])}</loc><lastmod>{DAY}</lastmod></url>\n' for a in articles)
    write(ROOT/'sitemap.xml',sitemap.replace('</urlset>',additions+'</urlset>'));changed.add('sitemap.xml')
    manifest=copy.deepcopy(before)
    def hash_file(name):
        data=(ROOT/name).read_bytes();return name,sha(data),sha(data.replace(b'\r\n',b'\n')) if re.search(r'\.(html|css|js|xml|txt|json)$',name) else None
    with ThreadPoolExecutor(max_workers=12) as pool:
        for name,digest,lf in pool.map(hash_file,sorted(changed)):
            manifest['files'][name]=digest
            if lf:manifest.setdefault('textSha256',{})[name]=lf
    manifest['createdAt']=DAY;manifest['sitemapPages']=10750
    assert len(manifest['files'])==len(before['files'])+120
    write(ROOT/'release-public-manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    generation={'date':DAY,'newArticles':30,'newPages':new_pages,'newImages':90,'existingArticles':98,'libraryArticles':128,'contextualPages':len(link_mapping),'sitemapPages':10750,'publicFiles':len(manifest['files']),'publicChanges':sorted(changed),'sourceSeed':selected['seed']}
    for name,value in [('generation.json',generation),('article-data.json',articles),('library.json',library),('source-mapping.json',mapping),('link-mapping.json',link_mapping),('public-changes.json',sorted(changed))]:write(out/name,json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in generation.items() if k not in ('newPages','publicChanges')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
