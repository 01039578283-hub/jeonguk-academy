"""Prepare an isolated commit for the existing GitHub production integration."""
from pathlib import Path
from collections import Counter
import hashlib,json,shutil,subprocess

ROOT=Path(__file__).resolve().parents[1]
DEST=Path('C:/Users/1992k/Desktop/CodexData/worktrees/jeonguk-branches-20260925').resolve()
REPORT=ROOT/'tools/reports/branch-directory-20260925'
audit=json.loads((REPORT/'audit.json').read_text('utf-8'))
assert not audit['errors'] and audit['newPages']==210
assert DEST.parent==Path('C:/Users/1992k/Desktop/CodexData/worktrees').resolve()
assert (DEST/'.git').is_file()
def git(*args):return subprocess.check_output(['git',*args],cwd=DEST,encoding='utf-8')
def sha(p):return hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
assert not git('status','--porcelain').strip(),'Release worktree must initially be clean'
assert git('rev-parse','HEAD')==git('rev-parse','origin/main')
families=['지점안내','전국학원','과목별학원','학습가이드','학습코칭','상담문의']
files=[p for family in families for p in (ROOT/family).rglob('index.html')]+[p for p in (ROOT/'assets').rglob('*') if p.is_file()]
assert not any(p.is_symlink() for p in files)
files += [ROOT/n for n in ['index.html','favicon.ico','robots.txt','sitemap.xml','llms.txt','branch-updates.xml','vercel.json','.vercelignore','.gitignore','build-public.mjs','wawa-analytics-build.mjs','seo-descriptions.mjs','seo-descriptions.json','BRANCH_DIRECTORY_20260925.md']]
files += [ROOT/'tools'/n for n in ['prepare_branch_directory.py','build_branch_directory.py','audit_branch_directory.py','prepare_branch_git_release.py','verify_branch_directory_live.py']]
assert len([p for p in files if p.name=='index.html'])==7396
asset_ext={'.css','.js','.png','.jpg','.jpeg','.webp','.gif','.svg','.ico','.avif','.woff','.woff2','.ttf','.otf'}
changed=[];hashes={}
for src in files:
    rel=src.relative_to(ROOT);dest=(DEST/rel).resolve()
    assert dest.is_relative_to(DEST) and not dest.is_symlink()
    assert src.stat().st_size<95*1024*1024
    if rel.parts[0]=='assets':assert src.suffix.lower() in asset_ext,rel
    digest=sha(src);hashes[rel.as_posix()]=digest
    if not dest.exists() or sha(dest)!=digest:
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest);changed.append(rel.as_posix())
    assert sha(dest)==digest
result={'worktree':str(DEST),'baseCommit':git('rev-parse','HEAD').strip(),'files':len(files),'changedFiles':len(changed),'changesByRoot':dict(Counter(Path(p).parts[0] for p in changed)),'sourceHashes':hashes,'privateWorkbookAndReportFiles':0}
(REPORT/'git-release.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='sourceHashes'},ensure_ascii=False))
