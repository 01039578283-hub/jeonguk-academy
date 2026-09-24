"""Compare the published directory with the audited build, without external writes."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from urllib.parse import quote,unquote,urlsplit
from datetime import datetime,timezone
import hashlib,json,sys
from lxml import html,etree

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'tools/reports/branch-directory-20260925'
ORIGIN='https://xn--3e0bl59bm0ad17a.com'
load=lambda p:json.loads(p.read_text('utf-8'))
build=load(REPORT/'build.json');audit=load(REPORT/'audit.json');source=load(REPORT/'source-audit.json')
assert not audit['errors']
def fetch(path,method='GET'):
    request=Request(ORIGIN+quote(path,safe='/%?=&-._~'),method=method,headers={'User-Agent':'Jeonguk-branch-release-verification/1.0'})
    with urlopen(request,timeout=45) as r:return r.status,r.read(),{k.lower():v for k,v in r.headers.items()}
def text(n):return ' '.join(n.text_content().split())
def verify(path):
    try:
        status,raw,headers=fetch(path);d=html.document_fromstring(raw)
        local=html.document_fromstring((ROOT/path.strip('/')/'index.html').read_bytes()) if path!='/' else html.document_fromstring((ROOT/'index.html').read_bytes())
        comparisons={key:d.xpath(expr)==local.xpath(expr) for key,expr in [('title','string(//title)'),('description','string(//meta[@name="description"]/@content)'),('canonical','string(//link[@rel="canonical"]/@href)'),('ogDescription','string(//meta[@property="og:description"]/@content)'),('twitterDescription','string(//meta[@name="twitter:description"]/@content)')]}
        comparisons['body']=text(d.find('body'))==text(local.find('body'))
        comparisons['directoryNav']=bool(d.xpath('//header//a[@href="/지점안내/"]'))
        comparisons['schema']=[json.loads(n.text) for n in d.xpath('//script[@type="application/ld+json"]')]==[json.loads(n.text) for n in local.xpath('//script[@type="application/ld+json"]')]
        comparisons['tracker']=len(d.xpath('//script[@data-site="wawa-02"]'))==1
        comparisons['indexable']='noindex' not in headers.get('x-robots-tag','').lower() and 'noindex' not in d.xpath('string(//meta[@name="robots"]/@content)').lower()
        return {'path':path,'status':status,'comparisons':comparisons,'ok':status==200 and all(comparisons.values())}
    except Exception as e:return {'path':path,'ok':False,'error':str(e)}
def head_image(path):
    try:
        status,_,headers=fetch(path,'HEAD');return {'path':path,'status':status,'ok':status==200 and headers.get('content-type','').startswith('image/')}
    except Exception as e:return {'path':path,'ok':False,'error':str(e)}
def private(path):
    try:status,_,_=fetch(path);return {'path':path,'status':status,'ok':False}
    except HTTPError as e:return {'path':path,'status':e.code,'ok':e.code==404}
    except Exception as e:return {'path':path,'error':str(e),'ok':False}

pages=build['created']+['/','/전국학원/','/과목별학원/','/상담문의/']
results=list(ThreadPoolExecutor(6).map(verify,pages))
print('Published pages checked:',len(results),'Failures:',sum(not r['ok'] for r in results),flush=True)
images=list(ThreadPoolExecutor(6).map(head_image,source['media']))
print('Published images checked:',len(images),'Failures:',sum(not r['ok'] for r in images),flush=True)
resources=[]
for path in ['/assets/branch-directory.css','/assets/branch-directory.js','/assets/unified-ui.css','/branch-updates.xml','/llms.txt','/robots.txt','/sitemap.xml']:
    try:
        status,raw,_=fetch(path);local=(ROOT/path.lstrip('/')).read_bytes()
        good=raw.replace(b'\r\n',b'\n')==local.replace(b'\r\n',b'\n')
        resources.append({'path':path,'status':status,'ok':status==200 and good})
    except Exception as e:resources.append({'path':path,'error':str(e),'ok':False})
private_checks=[private(p) for p in ['/seo-descriptions.json','/tools/data/branch-directory/centers.json','/tools/reports/branch-directory-20260925/baseline.json','/.env.local']]
errors=[r for r in results+images+resources+private_checks if not r['ok']]
report={'verifiedAt':datetime.now(timezone.utc).isoformat(),'pages':results,'images':images,'resources':resources,'privateFiles':private_checks,'errors':errors}
(REPORT/'production-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'pages':len(results),'images':len(images),'resources':len(resources),'privatePathsBlocked':sum(r['ok'] for r in private_checks),'errors':errors},ensure_ascii=False))
sys.exit(bool(errors))
