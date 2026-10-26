/* Only public branch/course context is carried to the existing Google form. */
(() => {
 'use strict';
 const params=new URLSearchParams(location.search);
 const setOption=(node,value)=>{if(node&&[...node.options].some(o=>o.value===value))node.value=value;};
 function courseMessage(courses,conditional,grade,subject){
  if(!grade||!subject)return '학생의 학년과 희망 과목을 고르면 자료에 안내된 범위를 확인할 수 있습니다. 시간표·잔여 자리·확정 교육비는 상담에서 확인해 주세요.';
  if(courses[subject]?.includes(grade))return `안내 자료에는 ${grade} ${subject} 수강 범위가 포함되어 있습니다. 현재 개설 시간·담당 선생님·교육비는 별도 확인이 필요합니다.`;
  const note=conditional[subject];
  if(note?.grades.includes(grade))return `조건 확인 필요: ${note.note}`;
  return `현재 안내 자료에서는 ${grade} ${subject} 수강 범위가 확인되지 않습니다. 개설 여부를 상담에서 문의해 주세요.`;
 }
 const branchForm=document.querySelector('[data-journey-branch]');
 if(branchForm){
  const g=branchForm.elements.grade,s=branchForm.elements.subject;
  setOption(g,params.get('grade'));setOption(s,params.get('subject'));
  const status=branchForm.querySelector('[data-journey-status]');
  const courses=JSON.parse(branchForm.dataset.courses),conditional=JSON.parse(branchForm.dataset.unconfirmed);
  const update=()=>{status.textContent=courseMessage(courses,conditional,g.value,s.value);};
  branchForm.addEventListener('change',update);update();
 }
 const panel=document.querySelector('[data-journey-contact]');
 if(!panel)return;
 const b=panel.querySelector('#consult-branch'),g=panel.querySelector('#consult-grade'),s=panel.querySelector('#consult-subject');
 setOption(b,params.get('branch'));setOption(g,params.get('grade'));setOption(s,params.get('subject'));
 const status=panel.querySelector('[data-journey-status]'),summary=panel.querySelector('[data-journey-summary]'),detail=panel.querySelector('[data-journey-detail]');
 const links=[...document.querySelectorAll('[data-consult-open]')];
 const base="https://docs.google.com/forms/d/e/1FAIpQLSdb2oE5Qk5YS0TfYDxyV1w-IOTkhkjOCmmpAKTI9FmqpVj6Yg/viewform";
 function update(){
  const option=b.selectedOptions[0],courses=JSON.parse(option.dataset.courses||'{}'),conditional=JSON.parse(option.dataset.unconfirmed||'{}');
  const url=new URL(base);url.searchParams.set('usp','pp_url');
  if(b.value)url.searchParams.set('entry.288740305',b.value);
  const selected=[g.value,s.value].filter(Boolean).join(' / ');
  if(selected)url.searchParams.set('entry.1461737477',selected);
  for(const link of links)link.href=url.href;
  summary.textContent=b.value?`${b.value} · ${option.dataset.address}`:'아직 지점을 정하지 않았다면 신청서에 희망 지역을 적어 주세요.';
  detail.hidden=!b.value;
  if(b.value){detail.href=option.dataset.path;detail.textContent=b.value+' 주소·수강 조건 다시 보기';}else detail.removeAttribute('href');
  status.textContent=b.value?courseMessage(courses,conditional,g.value,s.value):'희망 지점을 선택하면 주소와 자료상 수강 범위를 함께 확인할 수 있습니다.';
 }
 panel.addEventListener('change',update);update();
})();
