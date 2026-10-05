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
let learningGuides=0,learningArticles=0;
let teacherPages=0,teacherCards=0,teacherBridges=0;
let educationPages=0,educationArticles=0,educationImages=0,educationBridges=0;
let curriculumPages=0,curriculumSubjects=0,curriculumBridges=0,curriculumElectives=0;
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
  if(file==='index.html'){
    if(!source.includes('home-content-upgrade')||!source.includes('/assets/home-content.css')||['home-library','home-curriculum','learning-paths','home-menu-list','home-reading-list'].some(id=>!source.includes(`id="${id}"`)))errors.push({file,reason:'Homepage content navigation missing'});
    if((source.match(/<a\b[^>]*data-home-hub\b/g)||[]).length!==8||(source.match(/<a\b[^>]*data-home-article\b/g)||[]).length!==18||(source.match(/<article\b[^>]*data-home-topic=/g)||[]).length!==6||(source.match(/<details\b[^>]*data-home-faq\b/g)||[]).length!==6)errors.push({file,reason:'Homepage menu, reading, or visible answer coverage differs'});
    const homeGraph=JSON.parse(source.match(/<script\b[^>]*data-site-schema[^>]*>([\s\S]*?)<\/script>/)?.[1]||'{}')['@graph']||[];
    for(const [id,count] of [['home-menu-list',8],['home-reading-list',18]]){
      const list=homeGraph.find(n=>n['@type']==='ItemList'&&n['@id']==='https://xn--3e0bl59bm0ad17a.com/#'+id);
      if(!list||list.numberOfItems!==count||list.itemListElement?.length!==count)errors.push({file,reason:'Homepage visible collection structured data differs'});
    }
    if(!source.includes('home-teaching-upgrade')||!source.includes('/assets/home-teaching.css')||['class-formats','school-exam','study-planner','learning-dialogue'].some(id=>!source.includes(`id="${id}"`)))errors.push({file,reason:'Reviewed teaching information sections missing'});
    if((source.match(/<tr\b[^>]*data-format-row\b/g)||[]).length!==8||!source.includes('data-planner-example'))errors.push({file,reason:'Teaching comparison or planner example missing'});
    const teachingPhotos=[...source.matchAll(/<figure\b[^>]*data-teaching-image[^>]*>([\s\S]*?)<\/figure>/g)];
    if(teachingPhotos.length!==4||teachingPhotos.some(m=>!m[1].includes('<figcaption>')))errors.push({file,reason:'Teaching photo coverage or source labels differ'});
    for(const photo of teachingPhotos){
      const src=photo[1].match(/src="\/(assets\/home-teaching\/[^"?]+)"/);
      if(!src||!manifest.files[src[1]])errors.push({file,reason:'Teaching photo missing from public manifest'});
    }
  }
  const curriculumLinks=(source.match(/data-curriculum-bridge=/g)||[]).length;
  curriculumBridges+=curriculumLinks;
  const requiresCurriculumLink=file.startsWith('전국학원/')||file.startsWith('과목별학원/')||file.startsWith('지점안내/')||['index.html','학습가이드/index.html','교육정보/index.html'].includes(file);
  if(curriculumLinks!==(requiresCurriculumLink?1:0))errors.push({file,reason:'Contextual curriculum discovery coverage differs'});
  if(requiresCurriculumLink&&!source.includes('/assets/curriculum.css'))errors.push({file,reason:'Curriculum discovery styles missing'});
  if(file.startsWith('학습커리큘럼/')){
    curriculumPages++;
    if(!source.includes('data-curriculum="2026-10-03"')||!source.includes('/assets/curriculum.css')||!source.includes('/assets/curriculum.js'))errors.push({file,reason:'Curriculum page template missing'});
    if(/편집\s*원칙/.test(source))errors.push({file,reason:'Excluded editorial statement returned'});
    if(source.includes('data-curriculum-kind="subject"')){
      curriculumSubjects++;
      if((source.match(/<article\b[^>]*data-level="(?:기초|표준|심화)"/g)||[]).length!==3||!source.includes('id="scope"')||!source.includes('id="sequence"')||!source.includes('id="check-task"')||!source.includes('id="school-check"')||!source.includes('id="sources"'))errors.push({file,reason:'Curriculum learning content incomplete'});
    }
    if(file==='학습커리큘럼/index.html'&&(source.match(/data-curriculum-card/g)||[]).length!==66)errors.push({file,reason:'Curriculum subject index differs'});
    if(file==='학습커리큘럼/고등선택과목/index.html'){
      curriculumElectives=(source.match(/data-elective-card/g)||[]).length;
      if(curriculumElectives!==29||!source.includes('2022 개정 교육과정')||!source.includes('고3은 2015 개정'))errors.push({file,reason:'Elective curriculum examples or cohort distinction missing'});
    }
  }
  if((source.match(/data-education-menu/g)||[]).length!==2)errors.push({file,reason:'Education information shared menu missing'});
  educationBridges+=(source.match(/data-education-bridge=/g)||[]).length;
  if(file.startsWith('교육정보/')){
    educationPages++;
    if(!/data-education-info="2026-10-(03|05)"/.test(source)||!source.includes('/assets/education-info.css')||!source.includes('/assets/education-info.js'))errors.push({file,reason:'Education information template missing'});
    if(/편집\s*원칙/.test(source))errors.push({file,reason:'Excluded editorial statement returned'});
    if(file!=='교육정보/index.html'){
      educationArticles++;
      const photos=[...source.matchAll(/<figure\b[^>]*data-education-image[^>]*>([\s\S]*?)<\/figure>/g)];
      educationImages+=photos.length;
      if(photos.length!==3||photos.some(m=>!m[1].includes('참고 이미지입니다.')))errors.push({file,reason:'Three disclosed education images required'});
      for(const photo of photos){
        const src=photo[1].match(/src="\/(assets\/education-info\/[^"?]+)"/);
        if(!src||!manifest.files[src[1]])errors.push({file,reason:'Education image missing from public manifest'});
      }
      if(!source.includes('id="example"')||!source.includes('id="sources"')||!source.includes('id="local-help"')||!source.includes('data-education-article'))errors.push({file,reason:'Education article sections missing'});
    }else if((source.match(/data-library-card/g)||[]).length!==128)errors.push({file,reason:'Expected 128 indexed educational articles'});
  }else if((source.match(/data-education-bridge=/g)||[]).length!==1)errors.push({file,reason:'Contextual education module missing'});
  if((source.match(/data-teacher-menu/g)||[]).length!==2)errors.push({file,reason:'Teacher directory shared menu missing'});
  const teacherLinks=[...source.matchAll(/data-teacher-bridge="([^"]+)"/g)];
  teacherBridges+=teacherLinks.length;
  if(teacherLinks.length>1)errors.push({file,reason:'Repeated contextual teacher link'});
  if(file.startsWith('선생님찾기/')){
    teacherPages++;
    const portraits=[...source.matchAll(/<img\b[^>]*src="(\/assets\/teacher-profiles\/[^"?]+)"[^>]*>/g)];
    const count=(source.match(/data-teacher-card/g)||[]).length;teacherCards+=count;
    if(!source.includes('data-teacher-directory="2026-10-02"')||!source.includes('/assets/teacher-directory.css')||!source.includes('/assets/teacher-directory.js'))errors.push({file,reason:'Teacher directory template missing'});
    if(count!==portraits.length||new Set(portraits.map(m=>m[1])).size!==portraits.length)errors.push({file,reason:'Missing or repeated teacher image'});
    if(count&&!source.includes('실제 교사 사진이 아닙니다.'))errors.push({file,reason:'Representative image disclosure missing'});
    if(portraits.some(m=>!manifest.files[m[1].slice(1)]||!m[0].includes('alt="교사 소개용 공용 이미지"')))errors.push({file,reason:'Teacher image missing or incorrectly identified'});
  }
  if(file.startsWith('학습가이드/')){
    learningGuides++;
    if(!source.includes('data-learning-guides="2026-10-02"')||!source.includes('/assets/learning-guides.css')||!source.includes('/assets/learning-guides.js'))
      errors.push({file,reason:'Reviewed learning-guide content or enhancement assets missing'});
    if(/편집\s*원칙/.test(source))errors.push({file,reason:'Excluded editorial statement returned'});
    if(file!=='학습가이드/index.html'){
      learningArticles++;
      if((source.match(/data-record-field/g)||[]).length!==4||!source.includes('id="sources"')||!source.includes('id="example"'))
        errors.push({file,reason:'Learning-guide example, sources or worksheet missing'});
      const worksheet=source.match(/href="(\/assets\/guide-worksheets\/[^"?]+\.txt)"/);
      if(!worksheet||!manifest.files[decodeURIComponent(worksheet[1]).slice(1)])errors.push({file,reason:'Worksheet missing from release manifest'});
    }
  }
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
if(learningGuides!==49||learningArticles!==48)errors.push({reason:'Reviewed learning-guide coverage changed',learningGuides,learningArticles});
if(teacherPages!==205||teacherCards!==1002)errors.push({reason:'Reviewed teacher coverage changed',teacherPages,teacherCards});
if(educationPages!==61||educationArticles!==60||educationImages!==180||educationBridges-curriculumPages!==10605)errors.push({reason:'Reviewed education coverage changed',educationPages,educationArticles,educationImages,educationBridges});
if(curriculumPages!==84||curriculumSubjects!==66||curriculumBridges!==10331||curriculumElectives!==29)errors.push({reason:'Reviewed curriculum coverage changed',curriculumPages,curriculumSubjects,curriculumBridges,curriculumElectives});
// This migration is intentionally explicit; new pages need reviewed coverage.
if(improved!==7791)errors.push({reason:'Expected all 7,791 reviewed pages to retain their migration marker',improved});
if(centerContent!==709||centerPages!==193||managementProfiles!==74||managementLinks!==516||commonPhotoBranches!==97)
  errors.push({reason:'Reviewed branch content coverage changed',centerContent,centerPages,managementProfiles,managementLinks,commonPhotoBranches});
if(visitPages!==3082||directions!==114||visitChildren!==2968||directionLinks!==1752||commonPhotoPages!==1472||centerPhotoPages!==1496)
  errors.push({reason:'Reviewed visiting information coverage changed',visitPages,directions,visitChildren,directionLinks,commonPhotoPages,centerPhotoPages});
errors.sort((a,b)=>(a.file||'').localeCompare(b.file||'')||a.reason.localeCompare(b.reason));
console.log(JSON.stringify({pages:pages.length,improved,centerContent,centerPages,managementProfiles,managementLinks,commonPhotoBranches,visitPages,directions,visitChildren,directionLinks,commonPhotoPages,centerPhotoPages,learningGuides,learningArticles,teacherPages,teacherCards,teacherBridges,educationPages,educationArticles,educationImages,educationBridges,curriculumPages,curriculumSubjects,curriculumBridges,curriculumElectives,errors:errors.slice(0,30),errorCount:errors.length}));
if(errors.length)process.exitCode=1;
