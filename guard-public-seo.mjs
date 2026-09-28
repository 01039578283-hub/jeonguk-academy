/** Fail the release when factual cleanups or basic crawlability regress. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const project=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(project,process.argv[2]||'.public-release');
const manifest=JSON.parse(fs.readFileSync(path.join(project,'release-public-manifest.json'),'utf8'));
const pages=Object.keys(manifest.files).filter(p=>p.endsWith('.html'));
const errors=[];
let improved=0;
let centerContent=0,centerPages=0,managementProfiles=0,managementLinks=0,commonPhotoBranches=0;
let visitPages=0,directions=0,visitChildren=0,directionLinks=0,commonPhotoPages=0,centerPhotoPages=0;
const decode=s=>s.replaceAll('&quot;','"').replaceAll('&#39;',"'").replaceAll('&amp;','&').replaceAll('&lt;','<').replaceAll('&gt;','>');
function check(node,file,migrated){
  if(!node||typeof node!=='object')return;
  if(Array.isArray(node)){node.forEach(n=>check(n,file,migrated));return;}
  const types=Array.isArray(node['@type'])?node['@type']:[node['@type']];
  if(types.some(t=>t==='Review'||t==='AggregateRating')||node.review||node.aggregateRating)
    errors.push({file,reason:'Unverified generated review/rating returned'});
  if(migrated && node.openingHours==='Mo-Sa 12:00-24:00')errors.push({file,reason:'Unverified fixed hours returned'});
  Object.values(node).forEach(n=>check(n,file,migrated));
}
async function inspect(file){
  const source=await fs.promises.readFile(path.join(root,file),'utf8');
  const migrated=source.includes('data-naver-improved="2026-09-28"');
  if(migrated)improved++;
  if(source.includes('data-center-content="2026-09-28"')){
    centerContent++;
    const branchPage=file.startsWith('지점안내/')&&file.split('/').length===4;
    if(branchPage){
      centerPages++;
      if(source.includes('id="learning-management"'))managementProfiles++;
      if(!source.includes('/assets/center-content.css'))errors.push({file,reason:'Branch content stylesheet missing'});
      if(source.indexOf('id="courses"')>source.indexOf('id="learning-materials"'))errors.push({file,reason:'Branch facts moved below large images'});
      const shared=[...source.matchAll(/<figure\b[^>]*data-photo-source="common"[^>]*>([\s\S]*?)<\/figure>/g)];
      if(shared.length){
        commonPhotoBranches++;
        if(shared.length!==4||shared.some(m=>!m[1].includes('실제 사진 아님')))errors.push({file,reason:'Shared photo label missing'});
      }
    }else if(source.includes('class="cc-profile-link"'))managementLinks++;
    else errors.push({file,reason:'Reviewed management link missing'});
  }
  if(source.includes('data-center-visit="2026-09-28"')){
    visitPages++;
    if(!source.includes('/assets/center-visit.css'))errors.push({file,reason:'Visiting information stylesheet missing'});
    const branchPage=file.startsWith('지점안내/')&&file.split('/').length===4;
    if(branchPage){
      directions++;
      if(!source.includes('id="directions"')||!source.includes('센터 제공 자료에 따른 위치 안내'))errors.push({file,reason:'Reviewed directions or source note missing'});
    }else{
      visitChildren++;
      const media=source.indexOf('id="learning-materials"');
      if(['center-facts','courses','fees'].some(id=>source.indexOf(`id="${id}"`)<0||source.indexOf(`id="${id}"`)>media))errors.push({file,reason:'Child page facts moved below images'});
      const figures=[...source.matchAll(/<figure\b[^>]*data-photo-source="(common|center)"[^>]*>([\s\S]*?)<\/figure>/g)];
      if(figures.length!==1)errors.push({file,reason:'Child photo source count changed'});
      else{
        const mode=figures[0][1],body=figures[0][2],branch=file.split('/')[2];
        if(mode==='common')commonPhotoPages++;else centerPhotoPages++;
        const expected=mode==='common'?`공용 학습 공간 예시 · ${branch} 실제 사진 아님`:`${branch} 제공 학습 공간 사진`;
        if(!body.includes(`alt="${expected}"`)||!body.includes(`<figcaption>${expected}</figcaption>`))errors.push({file,reason:'Child photo description missing or misleading'});
      }
      if(!source.includes('class="cv-photo-note"'))errors.push({file,reason:'Child photo source notice missing'});
      const links=[...source.matchAll(/<a\b[^>]*class="[^"]*cv-direction-link[^"]*"[^>]*href="([^"]*)"/g)];
      directionLinks+=links.length;
      if(links.length>1||links.some(m=>decodeURIComponent(decode(m[1]))!=='/'+file.split('/').slice(0,3).join('/')+'/#directions'))errors.push({file,reason:'Wrong directions destination'});
    }
  }
  if((source.match(/<h1\b/gi)||[]).length!==1)errors.push({file,reason:'Expected one H1'});
  if((source.match(/<link\b[^>]*rel=["']canonical["']/gi)||[]).length!==1)errors.push({file,reason:'Expected one canonical'});
  const meta=[...source.matchAll(/<meta\b[^>]*>/gi)].map(m=>m[0]);
  const descriptions=meta.filter(m=>/\bname=["']description["']/i.test(m));
  const description=descriptions[0]?.match(/\bcontent="([^"]*)"/i)?.[1];
  if(descriptions.length!==1||!description||[...decode(description)].length>80)errors.push({file,reason:'Description missing or over 80 characters'});
  if(/class=["'][^"']*parent-review-card/.test(source))errors.push({file,reason:'Generated testimonial markup returned'});
  for(const script of source.matchAll(/<script\b[^>]*type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi)){
    try{check(JSON.parse(script[1]),file,migrated);}catch{errors.push({file,reason:'Invalid structured data'});}
  }
}
let cursor=0;
await Promise.all(Array.from({length:12},async()=>{
  while(cursor<pages.length)await inspect(pages[cursor++]);
}));
if(pages.length!==manifest.sitemapPages)errors.push({reason:'Manifest HTML/sitemap count differs'});
// This migration is intentionally explicit; new pages need reviewed coverage.
if(improved!==7791)errors.push({reason:'Expected all 7,791 reviewed pages to retain their migration marker',improved});
if(centerContent!==709||centerPages!==193||managementProfiles!==74||managementLinks!==516||commonPhotoBranches!==97)
  errors.push({reason:'Reviewed branch content coverage changed',centerContent,centerPages,managementProfiles,managementLinks,commonPhotoBranches});
if(visitPages!==3082||directions!==114||visitChildren!==2968||directionLinks!==1752||commonPhotoPages!==1472||centerPhotoPages!==1496)
  errors.push({reason:'Reviewed visiting information coverage changed',visitPages,directions,visitChildren,directionLinks,commonPhotoPages,centerPhotoPages});
errors.sort((a,b)=>(a.file||'').localeCompare(b.file||'')||a.reason.localeCompare(b.reason));
console.log(JSON.stringify({pages:pages.length,improved,centerContent,centerPages,managementProfiles,managementLinks,commonPhotoBranches,visitPages,directions,visitChildren,directionLinks,commonPhotoPages,centerPhotoPages,errors:errors.slice(0,30),errorCount:errors.length}));
if(errors.length)process.exitCode=1;
