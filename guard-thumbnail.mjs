/** Fixed, reviewed representative photos must stay visible in initial HTML. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const sourceRoot=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(process.argv[2]||sourceRoot);
const selections=JSON.parse(fs.readFileSync(path.join(sourceRoot,'thumbnail-selections.json'),'utf8'));
const errors=[];
const decode=s=>(s||'').replaceAll('&quot;','"').replaceAll('&#39;',"'").replaceAll('&amp;','&').replaceAll('&lt;','<').replaceAll('&gt;','>');
const attr=(tag,key)=>decode(tag.match(new RegExp('\\b'+key+'="([^"]*)"'))?.[1]);
let checked=0,appended=0;
const imageSizes=new Map(await Promise.all([...new Set(Object.values(selections).map(p=>p.image))].map(async image=>[image,await fs.promises.stat(path.join(root,new URL(image).pathname)).then(s=>s.size).catch(()=>0)])));
async function inspect(file,p){
 const source=await fs.promises.readFile(path.join(root,file),'utf8');
 const head=source.match(/<head\b[^>]*>([\s\S]*?)<\/head>/)?.[1]||'';
 const main=source.match(/<main\b[^>]*>([\s\S]*?)<\/main>/)?.[1]||'';
 const images=[...main.matchAll(/<img\b[^>]*>/g)].map(m=>m[0]);
 const chosen=images.filter(i=>attr(i,'src')===p.image);
 const marked=images.filter(i=>i.includes('data-branch-thumbnail='));
 const metas=[...head.matchAll(/<meta\b[^>]*>/g)].map(m=>m[0]);
 const values=key=>metas.filter(m=>(attr(m,'property')||attr(m,'name'))===key).map(m=>attr(m,'content'));
 const fail=reason=>errors.push({file,reason});
 if(chosen.length!==1||marked.length!==1||chosen[0]!==marked[0])fail('Representative must be exactly one visible inline image');
 const image=chosen[0]||'';
 if(attr(image,'alt')!==p.alt||attr(image,'data-branch-thumbnail')!==p.mode||attr(image,'width')!==String(p.width)||attr(image,'height')!==String(p.height)||attr(image,'loading')!=='lazy')fail('Image metadata differs from reviewed selection');
 if(!attr(image,'style').includes(`aspect-ratio:${p.width} / ${p.height}`))fail('Representative space must be reserved before lazy loading');
 if(/\bhidden\b|display\s*:\s*none/.test(image)||!main.includes(p.alt))fail('Representative must have visible description');
 if(!p.image.startsWith('https://xn--3e0bl59bm0ad17a.com/assets/branches/'))fail('Unexpected image origin');
 for(const key of ['og:image','twitter:image'])if(values(key).length!==1||values(key)[0]!==p.image)fail('Conflicting or missing '+key);
 if(values('og:image:width')[0]!==String(p.width)||values('og:image:height')[0]!==String(p.height))fail('OG dimensions mismatch');
 if(p.mode==='common'&&!p.alt.includes('실제 사진 아님'))fail('Common image must be disclosed');
 if(p.width<=150||p.height<=150||p.width/p.height>3)fail('Image dimensions below reviewed criteria');
 if(imageSizes.get(p.image)<5000)fail('Image missing or too small');
 if(images.some(i=>i.includes('subject-hidden-representative')||i.includes('data-role="representative-image"')||/\bhidden\b/.test(i)))fail('Old hidden representative returned');
 if(p.action==='append'){
  appended++;
  const section=main.match(/<section class="branch-photo-bottom"[\s\S]*?<\/section>\s*$/)?.[0];
  if(!section||!section.includes(image))fail('New photo must be last in main');
 }
 checked++;
}
const entries=Object.entries(selections);let cursor=0;
await Promise.all(Array.from({length:12},async()=>{while(cursor<entries.length){const [file,p]=entries[cursor++];await inspect(file,p)}}));
if(checked!==10210||appended!==7049)errors.push({reason:'Selection coverage differs',checked,appended});
console.log(JSON.stringify({thumbnailPages:checked,newBottomPhotos:appended,errorCount:errors.length,errors:errors.slice(0,20)}));
if(errors.length)process.exitCode=1;
