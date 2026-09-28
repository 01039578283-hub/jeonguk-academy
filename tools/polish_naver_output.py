"""Remove indentation-only leftovers without changing rendered content."""
import argparse,hashlib,json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from improve_naver_pages import ROOT,clean_changed_blocks,refresh_manifest

p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);a=p.parse_args()
path=a.report/'migration.json';data=json.loads(path.read_text(encoding='utf-8'))
def polish(row):
    rel=row['path'];source=ROOT/rel;preview=a.report/'preview'/rel
    raw=source.read_text(encoding='utf-8-sig');staged=preview.read_text(encoding='utf-8-sig')
    assert raw==staged and hashlib.sha256(raw.encode()).hexdigest()==row['afterSha256'],rel
    cleaned=clean_changed_blocks(raw)
    if cleaned==raw:return None
    source.write_text(cleaned,encoding='utf-8');preview.write_text(cleaned,encoding='utf-8')
    row['afterSha256']=hashlib.sha256(cleaned.encode()).hexdigest()
    return rel
with ThreadPoolExecutor(max_workers=12) as pool:
    changed=[r for r in pool.map(polish,data['pages']) if r]
refresh_manifest(changed)
data['summary']['formattingCleaned']=len(changed)
path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Normalized changed HTML formatting:',len(changed),flush=True)
