/* Filters only: all teacher and branch links are rendered in static HTML. */
(() => {
  'use strict';
  const search=document.querySelector('#teacher-search');
  if(!search)return;
  const region=document.querySelector('#teacher-region');
  const focus=document.querySelector('#teacher-focus');
  const cards=[...document.querySelectorAll('#teacher-results [data-branch-card]')];
  const status=document.querySelector('#teacher-count');
  const more=document.querySelector('#teacher-more');
  const normal=text=>text.normalize('NFKC').toLocaleLowerCase('ko').replace(/\s+/g,'');
  let limit=24;
  const apply=()=>{
    const terms=search.value.trim().split(/\s+/).filter(Boolean).map(normal);
    let matches=0,profiles=0;
    for(const card of cards){
      const hit=(region.value==='all'||card.dataset.region===region.value)
        &&(focus.value==='all'||card.dataset.focus.split(' | ').includes(focus.value))
        &&terms.every(term=>normal(card.dataset.search).includes(term));
      card.hidden=!(hit&&matches<limit);
      if(hit){matches++;profiles+=Number(card.dataset.count);}
    }
    status.textContent=`${matches}개 지점 · 교사 소개 ${profiles.toLocaleString('ko-KR')}건 중 ${Math.min(matches,limit)}개 지점을 표시합니다.`;
    document.querySelector('#teacher-empty').hidden=matches!==0;
    more.parentElement.hidden=matches<=limit;
    more.textContent=`지점 ${Math.min(24,Math.max(0,matches-limit))}개 더 보기`;
  };
  const change=()=>{limit=24;apply();};
  const reset=()=>{search.value='';region.value='all';focus.value='all';change();};
  search.addEventListener('input',event=>{if(!event.isComposing)change();});
  search.addEventListener('compositionend',change);
  search.addEventListener('search',change);
  region.addEventListener('change',change);focus.addEventListener('change',change);
  document.querySelector('#teacher-reset').addEventListener('click',reset);
  document.querySelector('[data-teacher-reset]').addEventListener('click',()=>{reset();search.focus();});
  more.addEventListener('click',()=>{limit+=24;apply();});
  document.querySelector('[data-teacher-filter]').hidden=false;
  apply();
})();
