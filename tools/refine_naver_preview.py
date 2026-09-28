"""Apply visual-review copy refinements to the preview before verification."""
from pathlib import Path
import argparse,hashlib,json,re
from lxml import html
from improve_naver_pages import refine_branch_intro,serialize

def main():
    p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);args=p.parse_args()
    path=args.report/'migration.json';data=json.loads(path.read_text(encoding='utf-8'));changed=0
    assert data['summary']['processed']==7791
    for row in data['pages']:
        if not row.get('branchHighImproved'):continue
        f=args.report/'preview'/row['path'];old=f.read_text(encoding='utf-8')
        doc=html.fromstring(old);main=doc.xpath('//main')[0];refine_branch_intro(main,row['description'])
        updated=re.sub(r'<main\b[^>]*>.*?</main>',lambda _:serialize(main),old,count=1,flags=re.S)
        f.write_text(updated,encoding='utf-8');row['afterSha256']=hashlib.sha256(updated.encode()).hexdigest();changed+=1
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Refined branch previews:',changed,flush=True)

if __name__=='__main__':main()
