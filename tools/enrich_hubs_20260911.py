"""One-release-only, additive enrichment of 12 hubs from frozen source snapshots.

Never re-run these old snapshots after future editing. Does not regenerate
regional manuscripts, images, discovery URLs or the existing site architecture.
"""
from pathlib import Path
from html import escape
from urllib.parse import quote,urlsplit,unquote,urljoin
import argparse,json,re,zipfile,subprocess

ROOT=Path(__file__).resolve().parents[1]
BASE='https://xn--3e0bl59bm0ad17a.com'
DATE='2026-09-11'
LD=re.compile(r'(<script[^>]*type="application/ld\+json"[^>]*>)(.*?)(</script>)',re.S)
def array(x):return x if isinstance(x,list) else [x] if x else []
def original_newline(rel):
 blob=subprocess.check_output(['git','show','399cc49b6d4e002cb1b3406b50bdd758b91fd6d8:'+rel],cwd=ROOT)
 return '\r\n' if b'\r\n' in blob else '\n'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--research',type=Path,required=True);args=ap.parse_args()
 content={}
 for name in ['math-copy.json','english-copy.json']:
  batch=json.loads((args.research/name).read_text('utf-8-sig'));assert not content.keys() & batch.keys();content.update(batch)
 assert len(content)==12
 for route,item in content.items():
  assert len(item['sections'])==3 and len(item['faqs'])==4 and len(item['readLinks'])==2
  for link in item['readLinks']:
   u=urlsplit(link['href']);p=ROOT/u.path.strip('/')/'index.html';assert p.is_file(),p
   assert not u.fragment or 'id="'+u.fragment+'"' in p.read_text('utf-8-sig')
 (ROOT/'tools/hub-content-20260911.json').write_text(json.dumps(content,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
 centers=[]
 for local,branch,region,city in [('명일동','명일점','서울','강동구'),('송촌동','송촌점','대전','대덕구'),('수완동','수완점','광주','광산구')]:
  source=ROOT/f'과목별학원/초5수학학원/{local}/index.html'
  doc=json.loads(LD.search(source.read_text('utf-8-sig')).group(2))
  n=next(x for x in doc['@graph'] if 'EducationalOrganization' in array(x.get('@type')))
  node={k:n[k] for k in ['@type','@id','name','address','identifier']}
  assert branch in node['name'] and node['address']['addressRegion']==region
  href=f'/전국학원/{region}/{city}/{local}/';target=ROOT/href.strip('/')/'index.html';assert target.is_file()
  assert node['address']['streetAddress'] in target.read_text('utf-8-sig')
  centers.append({'node':node,'href':href,'branch':branch})
 with zipfile.ZipFile(args.research/'baseline-snapshots.zip') as z:
  for route,item in content.items():
   rel=route.strip('/')+'/index.html';original=z.read(rel).decode('utf-8-sig').replace('\r\n','\n')
   current=(ROOT/rel).read_text('utf-8-sig')
   assert current==original or 'jeonguk-hub-learning:start' in current,rel
   m=LD.search(original);old=json.loads(m.group(2))
   doc=old if '@graph' in old else {'@context':old.get('@context','https://schema.org'),'@graph':[{k:v for k,v in old.items() if k!='@context'}]}
   graph=doc['@graph'];page=next(n for n in graph if n.get('@type')=='CollectionPage')
   url=BASE+route;page.setdefault('@id',url+'#webpage');page.setdefault('url',url)
   listing=next((n for n in graph if n.get('@type')=='ItemList'),None)
   if listing is None:
    regions=re.findall(r'<a class="academy-region-card[^"<>]*" href="([^"]+)">.*?<h3>([^<]+)</h3>',original,re.S)
    assert len(regions)==13
    listing={'@type':'ItemList','@id':url+'#regions','name':'전국학원 지역 목록','itemListElement':[{'@type':'ListItem','position':i+1,'name':name,'url':urljoin(url,href)} for i,(href,name) in enumerate(regions)]}
    graph.append(listing)
    graph.append({'@type':'BreadcrumbList','@id':url+'#breadcrumb','itemListElement':[{'@type':'ListItem','position':1,'name':'홈','item':BASE+'/'},{'@type':'ListItem','position':2,'name':'전국학원','item':url}]})
   page.setdefault('mainEntity',{'@id':listing['@id']})
   faq={'@type':'FAQPage','@id':url+'#hub-faq','mainEntity':[{'@type':'Question','name':q['question'],'acceptedAnswer':{'@type':'Answer','text':q['answer']}} for q in item['faqs']]}
   assert not any(n.get('@type')=='FAQPage' for n in graph);graph.append(faq)
   parts=[];lessons=[]
   for i,s in enumerate(item['sections']):
    assert len(s['paragraphs'])==2 and re.fullmatch('[a-z0-9-]+',s['id'])
    assert 'id="'+s['id']+'"' not in original
    sid=url+'#'+s['id'];parts.append({'@id':sid})
    graph.append({'@type':'WebPageElement','@id':sid,'url':sid,'name':s['title'],'text':'\n\n'.join(s['paragraphs']),'isPartOf':{'@id':page['@id']}})
    lessons.append('<section class="jk-lesson" id="'+s['id']+'"><span class="jk-number" aria-hidden="true">'+f'{i+1:02}'+'</span><div class="jk-lesson-copy"><h3>'+escape(s['title'])+'</h3>'+''.join('<p>'+escape(p)+'</p>' for p in s['paragraphs'])+'</div></section>')
   cards=[];mentions=[]
   for c in centers:
    n=c['node'];graph.append(n);mentions.append({'@id':n['@id']})
    cards.append('<article class="jk-center"><p class="jk-region">'+escape(n['address']['addressRegion']+' '+n['address']['addressLocality'])+'</p><h3>'+escape(n['name'])+'</h3><p>'+escape(n['address']['streetAddress'])+'</p><p class="jk-registration">'+escape(n['identifier'])+'</p><a href="'+quote(c['href'])+'">'+c['branch']+' 지역 안내</a></article>')
   page['hasPart']=array(page.get('hasPart'))+parts+[{'@id':faq['@id']}]
   page['mentions']=array(page.get('mentions'))+mentions;page['dateModified']=DATE
   faqs=''.join('<details><summary>'+escape(q['question'])+'</summary><p>'+escape(q['answer'])+'</p></details>' for q in item['faqs'])
   photos=''.join(f'<figure><img src="/assets/hub-classroom-{i}.webp" width="{w}" height="{h}" loading="lazy" decoding="async" alt="{escape(item["label"])} 학습 공간 예시 {i}"><figcaption>{caption}</figcaption></figure>' for i,w,h,caption in [(1,500,300,'개별 학습 좌석과 책상 배치 예시'),(2,800,600,'교실 안 학습 공간 구성 예시')])
   links=''.join('<a href="'+quote(l['href'],safe='/#')+'">'+escape(l['label'])+'</a>' for l in item['readLinks'])
   addition=f'''\n<!-- jeonguk-hub-learning:start 2026-09-11 -->
<div class="jk-content">
 <div class="jk-intro" id="hub-learning"><p class="jk-kicker">학습 안내</p><h2>{escape(item['label'])}, 상담 전에 살펴볼 학습 장면</h2><p>학생이 직접 해본 과제와 설명을 바탕으로 필요한 도움을 구체적으로 정리해 보세요.</p></div>
 <div class="jk-lessons">{''.join(lessons)}</div>
 <section class="jk-centers" id="hub-centers"><div class="jk-intro"><p class="jk-kicker">지점 확인</p><h2>방문할 곳의 이름과 주소를 함께 확인하세요</h2><p>사이트에 안내된 지점 가운데 세 곳의 예시입니다. 지역 안내에서 주소와 등록 정보를 살펴보고, 학생의 학년·과목에 맞는 현재 수강 가능 여부는 해당 지점 상담 시 확인해 주세요.</p></div><div class="jk-center-grid">{''.join(cards)}</div><div class="jk-photos">{photos}</div><p class="jk-photo-note">사진은 공통 학습 공간 예시입니다. 특정 지점의 현재 시설을 나타내지는 않습니다.</p></section>
 <section class="jk-faq" id="hub-faq"><div class="jk-intro"><p class="jk-kicker">학습 Q&amp;A</p><h2>자료를 읽고 더 궁금한 점</h2></div><div class="jk-faq-list">{faqs}</div></section>
 <nav class="jk-reading" id="hub-reading" aria-label="함께 읽을 학습 안내"><h2>집에서 이어갈 학습 준비</h2><div class="jk-reading-links">{links}</div></nav>
</div>
<!-- jeonguk-hub-learning:end -->\n'''
   output=LD.sub(lambda m:m.group(1)+json.dumps(doc,ensure_ascii=False,separators=(',',':'))+m.group(3),original,count=1)
   output=output.replace('</head>','<link rel="stylesheet" href="/assets/hub-learning.css?v=20260911"></head>',1)
   def body(m):
    tag=m.group(0);return tag.replace('class="','class="jk-hub-page ',1) if 'class="' in tag else tag[:-1]+' class="jk-hub-page">'
   output=re.sub(r'<body[^>]*>',body,output,count=1)
   def mainid(m):return m.group(0) if re.search(r'\bid=',m.group(0)) else m.group(0)[:-1]+' id="main">'
   output=re.sub(r'<main\b[^>]*>',mainid,output,count=1)
   jump='<nav class="jk-jump" aria-label="허브 내용 바로가기"><a href="#hub-learning">학습 선택 기준</a><a href="#hub-centers">지점 정보</a><a href="#hub-faq">학습 Q&amp;A</a></nav>'
   output=output.replace('</section>','</section>'+jump,1).replace('</main>',addition+'</main>',1)
   output=re.sub(r'^[ \t]+$','',output,flags=re.M)
   (ROOT/rel).write_text(output,encoding='utf-8',newline=original_newline(rel))
 sitemap=(ROOT/'sitemap.xml').read_text('utf-8');changed=0
 def dates(m):
  nonlocal changed
  text=m.group(0);loc=re.search('<loc>(.*?)</loc>',text).group(1)
  if unquote(urlsplit(loc).path) in content:
   assert '<lastmod>' in text;changed+=1;text=re.sub('<lastmod>.*?</lastmod>',f'<lastmod>{DATE}</lastmod>',text)
  return text
 sitemap=re.sub(r'<url>.*?</url>',dates,sitemap,flags=re.S);assert changed==12
 (ROOT/'sitemap.xml').write_text(sitemap,encoding='utf-8',newline=original_newline('sitemap.xml'))
 print(json.dumps({'hubs':12,'sections':36,'paragraphs':72,'faqs':48,'sitemap_dates':changed}))
if __name__=='__main__':main()
