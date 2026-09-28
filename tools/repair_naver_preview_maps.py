"""Repair existing broken map references in the staged, reviewed migration."""
import argparse,hashlib,json,re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote,urljoin,urlsplit
from lxml import html
from improve_naver_pages import ROOT,repair_map_images,serialize

p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);a=p.parse_args()
path=a.report/'migration.json';data=json.loads(path.read_text(encoding='utf-8'))
baseline=json.loads((a.report/'baseline-checks.json').read_text(encoding='utf-8'))
available=set(json.loads((ROOT/'release-public-manifest.json').read_text(encoding='utf-8'))['files'])
changed={r['path']:r for r in data['pages']};jobs=[]
for rel,r in baseline.items():
    missing=[s for s in r['images'] if 'assets/maps/' in s and unquote(urlsplit(urljoin(r['canonical'][0],s)).path).lstrip('/') not in available]
    if missing:
        assert rel in changed
        jobs.append(rel)
def repair(rel):
    f=a.report/'preview'/rel;old=f.read_text(encoding='utf-8')
    doc=html.fromstring(old);main=doc.xpath('//main')[0];fixes=repair_map_images(main)
    assert fixes,rel
    new=re.sub(r'<main\b[^>]*>.*?</main>',lambda _:serialize(main),old,count=1,flags=re.S)
    f.write_text(new,encoding='utf-8')
    changed[rel]['mapImageRepairs']=fixes
    changed[rel]['afterSha256']=hashlib.sha256(new.encode()).hexdigest()
    return len(fixes)
with ThreadPoolExecutor(max_workers=12) as pool:count=sum(pool.map(repair,jobs))
data['summary']['mapImageRepairs']=count
path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Repaired map references:',count,flush=True)
