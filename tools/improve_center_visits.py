"""Phase 3 preview/apply: reviewed directions and accurate descendant photo labels.

Preserves routes, metadata descriptions, factual course sections and all media.
Application requires unchanged source hashes and exact reviewed preview bytes.
"""
import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote
import openpyxl
from lxml import html

from improve_center_content import ROOT, DAY, E, load, save, digest, norm, text, fragment, serialize, byclass, graph
from improve_naver_pages import refresh_manifest, update_sitemap
from center_visit_content import DIRECTIONS, SOURCE_NOTES

MARKER='data-center-visit'
SOURCE_NOTE='센터 제공 자료에 따른 위치 안내입니다. 주변 상호와 출입 동선은 달라질 수 있으니 방문 전 현재 지도를 확인해 주세요.'


def inventory(args):
    centers=load(args.centers)['centers'];assert len(centers)==193
    wb=openpyxl.load_workbook(args.references/'코칭센터_데이터_.xlsx',read_only=True,data_only=True)
    rows=list(wb['센터정보'].values);evidence=[];pending=[]
    for c in centers:
        matches=[(i,r) for i,r in enumerate(rows,1) if i>1 and norm(r[6])==norm(c['registeredName']) and norm(r[11])==norm(c['address'])]
        assert len(matches)==1 or c['key']=='화성태안점',(c['key'],'ambiguous source')
        c['directions']=None
        if c['key'] in DIRECTIONS:
            assert len(matches)==1
            i,r=matches[0];body,quotes=DIRECTIONS[c['key']]
            assert r[12] and all(norm(q) in norm(r[12]) for q in quotes),('unsupported directions',c['key'],quotes)
            assert not re.search(r'OO학생|학부모님|주차가능|무료주차|도보\s*\d|\d+분|\d+미터',body),c['key']
            c['directions']=body
            evidence.append({'branch':c['key'],'path':c['path'],'cell':f'M{i}','body':body,'sourceExcerpts':quotes})
        else:
            has_source=bool(matches and matches[0][1][12])
            pending.append({'branch':c['key'],'path':c['path'],
                'reason':SOURCE_NOTES.get(c['key'],'주소와 중복되는 설명만 있어 별도 동선으로 추가하지 않았습니다.' if has_source else '제공 자료에서 사용할 위치 설명을 확보하지 못했습니다.')})
    wb.close()
    assert len(evidence)==len(DIRECTIONS) and len(evidence)+len(pending)==193
    return centers,evidence,pending


def photo_label(c,mode):
    return f'공용 학습 공간 예시 · {c["routeName"]} 실제 사진 아님' if mode=='common' else f'{c["routeName"]} 제공 학습 공간 사진'


def photo_notice(c,mode):
    return (f'학습 공간 사진은 공용 예시입니다. {c["routeName"]}의 실제 모습은 방문 전 확인해 주세요.' if mode=='common' else
            f'{c["routeName"]} 폴더로 제공된 사진입니다. 촬영 시점과 현재 공간 구성이 다를 수 있습니다.')


def render(raw,c,branch_page):
    d=html.fromstring(raw);main=d.xpath('//main')[0];assert main.get(MARKER) is None
    main.set(MARKER,DAY);head=d.xpath('//head')[0];script,structured=graph(d)
    facts=main.get_element_by_id('center-facts');wrap=facts.getparent()
    record={'branch':c['key'],'branchPage':branch_page,'directions':bool(c['directions']),'directionTarget':c['path']+'#directions' if c['directions'] else None}
    if branch_page:
        assert c['directions']
        maps=facts.xpath('.//a[contains(@href,"map.naver.com")]/@href');assert len(maps)==1
        section=fragment(f'''<section class="jd-section cv-directions" id="directions" aria-labelledby="directions-title">
<p class="jd-kicker">방문 위치</p><h2 id="directions-title">{E(c['routeName'])} 오시는 길</h2>
<p class="cv-directions-body">{E(c['directions'])}</p>
<p class="cv-address"><strong>방문 주소</strong> {E(c['address'])}</p>
<a class="jd-link" href="{E(maps[0])}" target="_blank" rel="noopener">네이버 지도에서 {E(c['routeName'])} 위치 확인<span aria-hidden="true"> ↗</span></a>
<p class="cv-source-note">{E(SOURCE_NOTE)}</p></section>''')
        wrap.insert(list(wrap).index(facts)+1,section)
        toc=byclass(main,'jd-toc')[0]
        toc.insert(1,fragment('<a class="jd-link" href="#directions">오시는 길<span aria-hidden="true"> ↗</span></a>'))
        for node in structured['@graph']:
            if node.get('@type')=='WebPage':
                node['hasPart']=[{'@type':'WebPageElement','@id':node['url']+'#'+s.get('id'),'name':text(s.xpath('.//h2')[0])}
                                 for s in main.xpath('.//section[@id]') if s.xpath('.//h2')]
    else:
        photos={p['src']:p for p in c['photos']};found=[]
        for img in main.xpath('.//img[@src]'):
            if img.get('src') not in photos:continue
            mode=photos[img.get('src')]['mode'];found.append(img.get('src'))
            figure=img.getparent();assert figure.tag=='figure'
            caption=figure.find('figcaption');assert caption is not None
            label=photo_label(c,mode);img.set('alt',label);caption.text=label;figure.set('data-photo-source',mode)
        assert len(found)==1,(c['key'],'unexpected child photo count')
        mode=photos[found[0]]['mode'];record.update(photoMode=mode,photoSrc=found[0])
        media=main.get_element_by_id('learning-materials')
        media.insert(2,fragment('<p class="cv-photo-note">'+E(photo_notice(c,mode))+'</p>'))
        parent=media.getparent();parent.remove(media)
        fees=main.get_element_by_id('fees');assert fees.getparent() is parent
        parent.insert(list(parent).index(fees)+1,media)
        for meta in head.xpath('.//meta[@property="og:image:alt"]'):meta.set('content',photo_label(c,mode))
        for node in structured['@graph']:
            primary=node.get('primaryImageOfPage')
            if isinstance(primary,dict):
                assert unquote(primary['url']).endswith(found[0]),('schema photo mismatch',c['key'])
                primary['caption']=photo_notice(c,mode)
        if c['directions']:
            links=byclass(facts,'jd-links');assert len(links)==1
            links[0].append(fragment('<a class="jd-link cv-direction-link" href="'+E(c['path'])+'#directions">'+E(c['routeName'])+' 오시는 길<span aria-hidden="true"> ↗</span></a>'))
    for node in structured['@graph']:
        if node.get('@type') in ['WebPage','CollectionPage','Article']:node['dateModified']=DAY
    for block in byclass(main,'jd-updated'):
        for t in block.xpath('.//time'):t.set('datetime',DAY);t.text=DAY
    head.append(fragment('<link rel="stylesheet" href="/assets/center-visit.css?v=20260928">'))
    script.text=json.dumps(structured,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    out=re.sub(r'<head\b[^>]*>.*?</head>',lambda _:serialize(head),raw,count=1,flags=re.S)
    out=re.sub(r'<main\b[^>]*>.*?</main>',lambda _:serialize(main),out,count=1,flags=re.S)
    return out,record


def preview(args):
    assert not (args.report/'phase3.json').exists(),'Preserve existing preview evidence; choose a fresh report directory'
    args.report.mkdir(parents=True,exist_ok=True)
    centers,evidence,pending=inventory(args);byroute={c['path']:c for c in centers}
    manifest=load(ROOT/'release-public-manifest.json')
    children=[p for p in manifest['files'] if p.startswith('지점안내/') and p.endswith('.html') and len(p.split('/'))>=5]
    assert len(children)==2968
    jobs=[(c['path'].strip('/')+'/index.html',c,True) for c in centers if c['directions']]
    jobs += [(p,byroute['/'+'/'.join(p.split('/')[:3])+'/'],False) for p in children]
    inputs=[args.centers,args.references/'코칭센터_데이터_.xlsx',ROOT/'tools/center_visit_content.py',ROOT/'tools/improve_center_visits.py']
    sources={str(p):digest(p.read_bytes()) for p in inputs}
    def build(job):
        rel,c,is_main=job;before=(ROOT/rel).read_bytes()
        new,record=render(before.decode('utf-8-sig'),c,is_main);after=(new.rstrip()+'\n').encode()
        record.update(path=rel,beforeSha256=digest(before),afterSha256=digest(after))
        for sub,data in [('before',before),('preview',after)]:
            p=args.report/sub/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        return record
    with ThreadPoolExecutor(max_workers=12) as pool:records=list(pool.map(build,jobs))
    summary={'pages':len(records),'directions':len(evidence),'pendingBranches':len(pending),'childPages':len(children),
             'commonPhotoPages':sum(r.get('photoMode')=='common' for r in records),
             'centerPhotoPages':sum(r.get('photoMode')=='center' for r in records),
             'directionLinks':sum(not r['branchPage'] and r['directions'] for r in records)}
    save(args.report/'phase3.json',{'date':DAY,'sources':sources,'directions':evidence,'pending':pending,'pages':records,'summary':summary})
    lines=['# 지점 오시는 길 반영 근거','','원본: 코칭센터_데이터_.xlsx / 센터정보 시트 / 위치안내(M열). 센터 제공 자료이며 현재 상호나 출입 동선을 새로 확인한 것은 아닙니다.','']
    for e in evidence:lines += [f'## {e["branch"]} · {e["cell"]}','',e['body'],'','원문 근거: '+' / '.join(e['sourceExcerpts']),'']
    (args.report/'오시는길_반영근거.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    lines=['# 위치 안내 추가 확인 목록','','주소가 변경되었다고 판단한 목록은 아닙니다. 근거가 부족하거나 설명을 더 확인할 지점입니다.','', '| 지점 | 남은 확인 내용 |','|---|---|']
    lines += [f'| {r["branch"]} | {r["reason"]} |' for r in pending]
    (args.report/'위치안내_추가확인목록.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False),flush=True)


def apply(args):
    report=load(args.report/'phase3.json')
    for p,sha in report['sources'].items():assert digest(Path(p).read_bytes())==sha,('input changed',p)
    def check(r):
        assert digest((ROOT/r['path']).read_bytes()) in {r['beforeSha256'],r['afterSha256']},('source changed',r['path'])
        assert digest((args.report/'preview'/r['path']).read_bytes())==r['afterSha256'],('preview changed',r['path'])
    with ThreadPoolExecutor(max_workers=12) as pool:list(pool.map(check,report['pages']))
    for name in ['release-public-manifest.json','sitemap.xml']:
        p=args.report/'before'/name
        if not p.exists():p.write_bytes((ROOT/name).read_bytes())
    def copy(r):(ROOT/r['path']).write_bytes((args.report/'preview'/r['path']).read_bytes())
    with ThreadPoolExecutor(max_workers=12) as pool:list(pool.map(copy,report['pages']))
    changed=[r['path'] for r in report['pages']]
    update_sitemap(changed)
    refresh_manifest(changed+['assets/center-visit.css','sitemap.xml'])
    save(args.report/'application.json',{'appliedPages':len(changed),'sourcesVerified':True})
    print(json.dumps({'applied':len(changed),'published':False}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True)
    p.add_argument('--centers',type=Path,required=True);p.add_argument('--references',type=Path,required=True)
    p.add_argument('--apply',action='store_true');args=p.parse_args()
    apply(args) if args.apply else preview(args)
