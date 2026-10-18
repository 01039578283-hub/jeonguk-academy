/** Verify the reviewed SEO/GEO additions without changing existing URLs or images. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const project=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(project,process.argv[2]||'.public-release');
const review=JSON.parse(fs.readFileSync(path.join(project,'seo-geo-review.json'),'utf8'));
const policy=JSON.parse(fs.readFileSync(path.join(project,'content-review-policy.json'),'utf8'));
const manifest=JSON.parse(fs.readFileSync(path.join(project,'release-public-manifest.json'),'utf8'));
const errors=[];const fail=(file,reason)=>errors.push({file,reason});
const read=file=>fs.promises.readFile(path.join(root,file),'utf8');
const decode=s=>s.replaceAll('&amp;','&').replaceAll('&quot;','"').replaceAll('&#39;',"'").replaceAll('&#x27;',"'");
let cursor=0;const entries=Object.entries(review.pages);
await Promise.all(Array.from({length:12},async()=>{while(cursor<entries.length){
 const [file,item]=entries[cursor++],source=await read(file);
 if(JSON.stringify(source.match(/<img\b[^>]*>/g)||[])!==JSON.stringify(item.beforeImageTags))fail(file,'Existing image markup or order changed');
 const canonical=[...source.matchAll(/<link\b[^>]*rel="canonical"[^>]*href="([^"]*)"/g)].map(m=>m[1]);
 if(JSON.stringify(canonical)!==JSON.stringify(item.canonical))fail(file,'Existing canonical changed');
 if((source.match(/<h1\b/g)||[]).length!==1)fail(file,'Expected a single H1');
}}));
for(const item of review.branchRecords){
 const file=item.page.slice(1)+'index.html',source=await read(file),text=await read(item.record);
 if((source.match(/data-branch-record=/g)||[]).length!==1||!source.includes('href="/'+item.record+'" download'))fail(file,'Missing or repeated branch preparation sheet');
 const branch=policy.branches.find(b=>b.key===item.branch);
 if(!branch){fail(item.record,'Unknown branch');continue}
 if(!text.includes('실제 방문 지점: '+item.branch)||!text.includes('주소: '+item.address))fail(item.record,'Wrong branch or address');
 for(const [subject,grades] of Object.entries(branch.subjects))if(!text.includes('- '+subject+': '+(grades.length?grades.join(' · '):'개설 여부·학년 확인 필요')))fail(item.record,'Course facts differ from reviewed branch data');
 for(const value of Object.values(branch.unconfirmed))if(!text.includes(value.note))fail(item.record,'Missing unresolved course conditions');
}
for(const file of review.directoryPages){
 const source=await read(file),m=file.match(/\/([초중][1-6])(영어|수학)학원\//),grade=m[1],subject=m[2];
 const block=source.match(/<!-- seo-geo-directory:start -->([\s\S]*?)<!-- seo-geo-directory:end -->/)?.[1]||'';
 const expected=policy.branches.filter(b=>b.subjects[subject]?.includes(grade));
 const links=[...block.matchAll(/<a href="([^"]+)"/g)].map(m=>decodeURIComponent(decode(m[1])));
 if(links.length!==expected.length||expected.some(b=>!links.includes(b.path+'#courses')))fail(file,'Static directory has missing or unconfirmed branches');
}
for(const file of review.practicalArticles){
 const source=await read(file);
 if((source.match(/data-geo-practice=/g)||[]).length!==1||!source.includes('예시'))fail(file,'Missing direct answer or example attribution');
 if((source.match(/<table\b/g)||[]).length!==1)fail(file,'Keep the consolidated existing example table');
 if(!source.includes('scope="col"'))fail(file,'Comparison table needs accessible column headings');
}
const feed=await read('rss.xml');const links=[...feed.matchAll(/<item>([\s\S]*?)<\/item>/g)];
if(links.length!==review.feed.items.length||links.length>50)fail('rss.xml','Wrong feed item coverage');
for(const item of review.feed.items)if(!feed.includes('<link>'+item.url.replaceAll('&','&amp;')+'</link>'))fail('rss.xml','Article feed differs from reviewed canonical URLs');
for(const file of ['index.html','학습가이드/index.html','교육정보/index.html','학습코칭/index.html'])if(!(await read(file)).includes('rel="alternate" type="application/rss+xml"'))fail(file,'RSS discovery missing');
if(review.branchRecords.length!==193||review.directoryPages.length!==10||review.practicalArticles.length!==8)fail('coverage','Reviewed scope differs');
if(!manifest.files[review.css])fail(review.css,'Missing public style asset');
console.log(JSON.stringify({reviewedPages:entries.length,branchSheets:review.branchRecords.length,subjectDirectories:review.directoryPages.length,practicalArticles:review.practicalArticles.length,feedItems:links.length,errorCount:errors.length,errors:errors.slice(0,20)}));
if(errors.length)process.exitCode=1;
