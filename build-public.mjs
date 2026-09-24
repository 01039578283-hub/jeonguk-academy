/** Stage only public files. Source workbooks, code, audit records and credentials never enter output. */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root=path.dirname(fileURLToPath(import.meta.url));
const output=path.join(root,'.public-release');
const marker=path.join(output,'.output-owner');
if(fs.existsSync(output)) {
  if(!fs.existsSync(marker)||fs.readFileSync(marker,'utf8')!=='jeonguk-public-v1') throw new Error('Unknown output folder');
  fs.rmSync(output,{recursive:true});
}
fs.mkdirSync(output,{recursive:true});fs.writeFileSync(marker,'jeonguk-public-v1');
const families=['과목별학원','전국학원','학습가이드','학습코칭','상담문의','지점안내'];
const assets=new Set(['.css','.js','.png','.jpg','.jpeg','.webp','.gif','.svg','.ico','.avif','.woff','.woff2','.ttf','.otf']);
let files=0, pages=0;
function copy(dir,kind) {
  for(const e of fs.readdirSync(dir,{withFileTypes:true})) {
    if(e.name.startsWith('.')||e.isSymbolicLink())continue;
    const p=path.join(dir,e.name);
    if(e.isDirectory()){copy(p,kind);continue;}
    if(kind==='page'&&e.name!=='index.html')continue;
    if(kind==='asset'&&!assets.has(path.extname(e.name).toLowerCase()))continue;
    const d=path.join(output,path.relative(root,p));fs.mkdirSync(path.dirname(d),{recursive:true});fs.copyFileSync(p,d);files++;if(e.name==='index.html')pages++;
  }
}
for(const family of families) if(fs.existsSync(path.join(root,family))) copy(path.join(root,family),'page');
copy(path.join(root,'assets'),'asset');
for(const name of ['index.html','favicon.ico','robots.txt','sitemap.xml','llms.txt','branch-updates.xml']) {
  if(!fs.existsSync(path.join(root,name)))continue;
  fs.copyFileSync(path.join(root,name),path.join(output,name));files++;if(name==='index.html')pages++;
}
if(pages!==10364)throw new Error(`Expected 10364 pages, found ${pages}`);
console.log(JSON.stringify({output:'.public-release',files,pages,privateSourceFiles:0}));
