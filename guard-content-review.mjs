/** Verify the reviewed course distinctions and permanent HTML discovery paths. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const project=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(project,process.argv[2]||'.public-release');
const policy=JSON.parse(fs.readFileSync(path.join(project,'content-review-policy.json'),'utf8'));
const manifest=JSON.parse(fs.readFileSync(path.join(project,'release-public-manifest.json'),'utf8'));
const errors=[];
const decode=s=>(s||'').replaceAll('&quot;','"').replaceAll('&#39;',"'").replaceAll('&amp;','&').replaceAll('&lt;','<').replaceAll('&gt;','>');
function attr(tag,key){const m=tag.match(new RegExp('\\b'+key+'=(?:"([^"]*)"|\'([^\']*)\')'));return decode(m?.[1]??m?.[2]);}
const confirmed={};for(const c of policy.branches)confirmed[c.path]=c;
let branches=0,cards=0,stagePages=0;
for(const c of policy.branches){
 const file=c.path.slice(1)+'index.html';const s=fs.readFileSync(path.join(root,file),'utf8');
 if((s.match(/id="course-overview"/g)||[]).length!==1||!s.includes('href="#teacher-introductions"')||!s.includes('/assets/content-review-20261012.css'))errors.push({file,reason:'Course summary or teacher discovery missing'});
 if(!s.includes('id="center-facts"')||!s.includes('id="courses"')||!s.includes('id="fees"'))errors.push({file,reason:'Existing factual anchors removed'});
 for(const [sub,v] of Object.entries(c.unconfirmed))if(!s.includes(v.note))errors.push({file,reason:'Missing visible condition note',sub});
 branches++;
}
for(const file of Object.keys(manifest.files).filter(n=>n==='지점안내/index.html'||(/^지점안내\/[^/]+\/index\.html$/.test(n)))){
 const s=fs.readFileSync(path.join(root,file),'utf8');
 for(const m of s.matchAll(/<article\b[^>]*data-branch-card[^>]*>[\s\S]*?<\/article>/g)){
  const block=m[0];const href=block.match(/<h3><a\b[^>]*href="([^"]*)"/)?.[1];const route=href?decodeURIComponent(decode(href)):'';const c=confirmed[route];
  if(!c){errors.push({file,reason:'Unknown directory branch'});continue;}
  try{
   if(JSON.stringify(JSON.parse(attr(block,'data-courses')))!==JSON.stringify(c.subjects))errors.push({file,branch:c.key,reason:'Filter uses different confirmed grades'});
   if(Object.keys(c.unconfirmed).length){
    if(JSON.stringify(JSON.parse(attr(block,'data-unconfirmed-courses')))!==JSON.stringify(c.unconfirmed)||!block.includes('data-course-confirmation'))errors.push({file,branch:c.key,reason:'Missing visible conditional filter result'});
   }
  }catch(e){errors.push({file,branch:c.key,reason:'Invalid course JSON'});}
  cards++;
 }
}
if(branches!==193||cards!==386)errors.push({reason:'Unexpected branch or directory card count',branches,cards});
for(const file of Object.keys(manifest.files).filter(n=>n.startsWith('지점안내/')&&/\/(초등|중등|고등)\/index\.html$/.test(n))){
 const stage=file.match(/\/(초등|중등|고등)\/index\.html$/)[1][0];const s=fs.readFileSync(path.join(root,file),'utf8');
 for(const m of s.matchAll(/<article\b[^>]*data-course="[^"]+"[^>]*>[\s\S]*?<\/article>/g)){
  const grades=attr(m[0],'data-grades').split(',');const shown=decode(m[0].match(/<p\b[^>]*>([\s\S]*?)<\/p>/)?.[1]||'');
  if(grades.some(g=>g&&!g.startsWith(stage))||[...shown.matchAll(/[초중고][1-6]/g)].some(g=>g[0][0]!==stage))errors.push({file,reason:'Course card does not match school stage'});
 }
 stagePages++;
}
console.log(JSON.stringify({reviewedBranches:branches,directoryCards:cards,stagePages,errorCount:errors.length,errors:errors.slice(0,30)}));
if(errors.length)process.exitCode=1;
