/** Check branch identity, original embed codes, placement, and existing-page preservation. */
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
const project=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(project,process.argv[2]||'.public-release');
const review=JSON.parse(fs.readFileSync(path.join(project,'kakaomap-selections.json'),'utf8'));
const hash=value=>createHash('sha256').update(value).digest('hex');
const normalized=value=>value.replaceAll('\r\n','\n');
const decode=value=>(value||'').replaceAll('&quot;','"').replaceAll('&#x27;',"'").replaceAll('&#39;',"'").replaceAll('&lt;','<').replaceAll('&gt;','>').replaceAll('&amp;','&');
const attr=(source,key)=>decode(source.match(new RegExp('\\b'+key+'="([^"]*)"'))?.[1]);
const strip=source=>source.replace(/<!-- kakaomap-assets:start -->[\s\S]*?<!-- kakaomap-assets:end -->/g,'').replace(/<!-- kakaomap-directions:start -->[\s\S]*?<!-- kakaomap-directions:end -->/g,'').replaceAll('<!-- kakaomap-stack:start --><div class="kakao-map-stack">','').replaceAll('</div><!-- kakaomap-stack:end -->','');
const tracker='<script defer src="https://wawa-visit-collector.clean-peach-8202.chatgpt.site/tracker.js" data-site="wawa-02" crossorigin="anonymous" referrerpolicy="no-referrer"></script>';
const buildOwned=source=>normalized(strip(source).replace(tracker,'').replace(/<link\b[^>]*>/gi,tag=>/^(?:icon|shortcut icon|apple-touch-icon|apple-touch-icon-precomposed)$/i.test(attr(tag,'rel'))?'':tag));
const read=file=>fs.promises.readFile(path.join(root,file),'utf8');
const errors=[];
const fail=(file,reason)=>errors.push({file,reason});
const counts={branchCodes:0,detailPages:0,hubPages:0,preservedPages:0};
for(const branch of Object.values(review.branches)){
  const shell=await read(branch.frame);
  const encoded=shell.match(/<script type="application\/json" id="kakao-map-document">([\s\S]*?)<\/script>/)?.[1];
  if(review.executionPolicy&&!encoded)fail(branch.frame,'Map must defer provider execution until near the viewport');
  const source=encoded?JSON.parse(encoded):shell;
  if(encoded){
    if(hash(normalized(source))!==branch.renderDocumentTextSha256)fail(branch.frame,'Original executable map document changed');
    if(!shell.includes("event.source===parent")||!shell.includes('wawa:kakao-map-activate')||!shell.includes('wawa:kakao-map-ready'))fail(branch.frame,'Automatic map activation handshake missing');
    const originalDocument=review.mapViewPolicy?source.replace(/<!-- kakaomap-map-only-style:start -->[\s\S]*?<!-- kakaomap-map-only-style:end -->/g,'').replace(/<!-- kakaomap-map-only-script:start -->[\s\S]*?<!-- kakaomap-map-only-script:end -->/g,''):source;
    if(!branch.originalFrame||normalized(await read(branch.originalFrame))!==normalized(originalDocument))fail(branch.frame,'Original map document not preserved');
    if(review.mapViewPolicy&&(!source.includes('.root_daum_roughmap > .wrap_controllers,.root_daum_roughmap > .cont{display:none!important}')||!source.includes("anchor.removeAttribute('href')")||!source.includes('stayOnMap')||!source.includes("root.addEventListener('click',stayOnMap,true)")))fail(branch.frame,'Map-only presentation and external navigation removal missing');
  }
  const original=source.match(/<!-- kakaomap-original:start -->([\s\S]*?)<!-- kakaomap-original:end -->/)?.[1];
  if(!original||hash(normalized(original))!==branch.sourceTextSha256)fail(branch.frame,'Copied original code changed');
  if(!original?.includes('"timestamp" : "'+branch.timestamp+'"')||!original?.includes('"key" : "'+branch.key+'"')||!original?.includes('id="daumRoughmapContainer'+branch.timestamp+'"'))fail(branch.frame,'Branch key, timestamp or node mismatch');
  const remote=[...source.matchAll(/<script\b[^>]*src="([^"]*)"/g)].map(m=>m[1]);
  if(remote.length!==1||remote[0]!=='https://t1.kakaocdn.net/kakaomapweb/roughmap/loader/prod/roughmapLoader.js')fail(branch.frame,'Unexpected or duplicate map loader');
  if(!source.includes('<meta name="robots" content="noindex,follow">')||!source.includes('name="viewport"')||source.includes('appkey='))fail(branch.frame,'Component document policy changed');
  counts.branchCodes++;
}
const sitemap=await read('sitemap.xml');
const sitemapEntries=new Map([...sitemap.matchAll(/<url>[\s\S]*?<\/url>/g)].map(m=>[m[0].match(/<loc>(.*?)<\/loc>/)?.[1],m[0]]));
let cursor=0;
await Promise.all(Array.from({length:12},async()=>{while(cursor<review.files.length){
  const item=review.files[cursor++],source=await read(item.file);
  if(hash(normalized(strip(source)))!==item.originalTextSha256&&hash(buildOwned(source))!==item.originalBuildSafeSha256){fail(item.file,'Existing HTML content or metadata changed');continue}
  counts.preservedPages++;
  if((source.match(/<!-- kakaomap-directions:start -->/g)||[]).length!==1||(source.match(/id="kakao-directions"/g)||[]).length!==1)fail(item.file,'Directions section must exist exactly once');
  const section=source.match(/<!-- kakaomap-directions:start -->([\s\S]*?)<!-- kakaomap-directions:end -->/)?.[1]||'';
  const frames=[...section.matchAll(/<iframe\b[^>]*>/g)].map(m=>m[0]);
  if(frames.length!==1){fail(item.file,'Exactly one initially visible map is required');continue}
  const selected=item.type==='detail'?item.branch:item.branches[0];
  const branch=review.branches[selected],frame=frames[0];
  if(attr(frame,'src')!=='/'+branch.frame||attr(frame,'data-map-timestamp')!==branch.timestamp||attr(frame,'loading')!=='lazy'||attr(frame,'title')!==selected+(review.mapViewPolicy?' 카카오맵 위치 안내':' 카카오맵 위치와 교통 안내'))fail(item.file,'Wrong branch map, accessible title, or loading policy');
  if(review.mapViewPolicy&&(/data-map-place-link/.test(section)||/<a\b[^>]*href="(?:https?:)?\/\/(?:place\.)?map\.kakao\.com/i.test(section)||attr(frame,'height')!=='364'))fail(item.file,'External map link or outdated map-only height remains');
  if(/\bhidden\b|display\s*:\s*none/.test(frame))fail(item.file,'Map must not be hidden behind a button');
  if((source.match(/<!-- kakaomap-assets:start -->/g)||[]).length!==1||!source.includes('href="/'+review.css+'"')||!source.includes('src="/'+review.js+'" defer'))fail(item.file,'Map support assets missing or duplicated');
  if(item.type==='detail'){
    counts.detailPages++;
    const start=source.indexOf('<!-- kakaomap-directions:start -->'),before=source.slice(0,start);
    if(!before.endsWith('</figure>')||!before.slice(before.lastIndexOf('<figure')).includes('지도'))fail(item.file,'Directions must immediately follow the existing map figure');
    if(!source.includes('<!-- kakaomap-stack:start --><div class="kakao-map-stack">'))fail(item.file,'Map/image grouping missing');
  }else{
    counts.hubPages++;
    const options=[...section.matchAll(/<option\b[^>]*>/g)].map(m=>m[0]);
    if(options.length!==item.branches.length)fail(item.file,'Hub branch coverage mismatch');
    for(let i=0;i<options.length;i++){
      const expected=review.branches[item.branches[i]],option=options[i];
      if(!expected||attr(option,'value')!=='/'+expected.frame||attr(option,'data-branch')!==expected.branch||attr(option,'data-address')!==expected.address||attr(option,'data-timestamp')!==expected.timestamp||attr(option,'data-branch-url')!==expected.url||attr(option,'data-place-url')!==expected.placeUrl)fail(item.file,'Hub option points to another branch');
    }
  }
  const canonical=source.match(/<link\b[^>]*rel="canonical"[^>]*href="([^"]*)"/)?.[1];
  const block=canonical?sitemapEntries.get(new URL(canonical).href):undefined;
  if(!block?.includes('<lastmod>'+review.date+'</lastmod>'))fail(item.file,'Changed page missing actual sitemap modification date');
}}));
if(counts.branchCodes!==193||counts.detailPages!==10210||counts.hubPages!==119||counts.preservedPages!==10329)fail('coverage','Reviewed page coverage differs');
console.log(JSON.stringify({...counts,errorCount:errors.length,errors:errors.slice(0,20)}));
if(errors.length)process.exitCode=1;
