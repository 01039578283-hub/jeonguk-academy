/** Preserve the approved public facts and media while checking the consultation journey. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const project=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(project,process.argv[2]||'.public-release');
const review=JSON.parse(fs.readFileSync(path.join(project,'journey-review.json'),'utf8'));
const policy=JSON.parse(fs.readFileSync(path.join(project,'content-review-policy.json'),'utf8'));
const errors=[];
const fail=(file,reason)=>errors.push({file,reason});
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const decode=s=>s.replaceAll('&amp;','&').replaceAll('&quot;','"').replaceAll('&#x27;',"'").replaceAll('&#39;',"'");
const get=(tag,key)=>decode(tag.match(new RegExp('\\b'+key+'="([^"]*)"'))?.[1]||'');
for(const [file,item] of Object.entries(review.pages)){
 const source=fs.readFileSync(path.join(root,file),'utf8');
 if(!same(source.match(/<img\b[^>]*>/g)||[],item.beforeImageTags))fail(file,'Image tags or order changed');
 if(!same(source.match(/<iframe\b[^>]*>/g)||[],item.beforeIframeTags))fail(file,'Map iframe changed');
 if(!same([...source.matchAll(/<link\b[^>]*rel="canonical"[^>]*href="([^"]*)"/g)].map(m=>m[1]),item.canonical))fail(file,'Canonical changed');
 if(!same([...source.matchAll(/<title>(.*?)<\/title>/gs)].map(m=>decode(m[1])),item.beforeTitle))fail(file,'Title changed');
 if(!same([...source.matchAll(/<meta\b[^>]*name="description"[^>]*content="([^"]*)"/g)].map(m=>decode(m[1])),item.beforeDescription))fail(file,'Description changed');
 const ids=[...source.matchAll(/\bid="([^"]*)"/g)].map(m=>m[1]);
 if(item.originalIds.some(id=>!ids.includes(id)))fail(file,'Existing section anchor removed');
 if(item.kind==='branch'){
  const branch=policy.branches.find(b=>b.key===item.branch);
  const forms=source.match(/<form\b[^>]*data-journey-branch[^>]*>/g)||[];
  if(forms.length!==1)fail(file,'Branch preparation form missing or repeated');
  else{
   if(get(forms[0],'action')!=='/상담문의/#consultation-plan'||get(forms[0],'method')!=='get')fail(file,'Incorrect continuation');
   if(!same(JSON.parse(get(forms[0],'data-courses')),branch.subjects)||!same(JSON.parse(get(forms[0],'data-unconfirmed')),branch.unconfirmed))fail(file,'Course conditions differ');
  }
  if(!source.includes('name="branch" value="'+item.branch+'"')||!source.includes(item.address))fail(file,'Branch identity lost');
  if((source.match(/class="sg-visit-record"/g)||[]).length!==1)fail(file,'Duplicate consultation preparation');
 }
}
const contact=fs.readFileSync(path.join(root,'상담문의/index.html'),'utf8');
const options=contact.match(/<option\b[^>]*data-path=[^>]*>/g)||[];
if(options.length!==193)fail('contact','193 branch options required');
for(const b of policy.branches){const option=options.find(o=>get(o,'value')===b.key);if(!option||get(option,'data-path')!==b.path||!same(JSON.parse(get(option,'data-courses')),b.subjects)||!same(JSON.parse(get(option,'data-unconfirmed')),b.unconfirmed))fail('contact',b.key+' data mismatch');}
if(!contact.includes('010-3957-8283')||contact.includes('010-6839-8283'))fail('contact','Approved website phone differs');
const counts=Object.values(review.pages).reduce((acc,p)=>(acc[p.kind]=(acc[p.kind]||0)+1,acc),{});
if(!same(counts,{home:1,branch:193,directory:17,consultation:1}))fail('coverage','Unexpected changed scope');
console.log(JSON.stringify({pages:Object.keys(review.pages).length,counts,errorCount:errors.length,errors:errors.slice(0,20)}));
if(errors.length)process.exitCode=1;
