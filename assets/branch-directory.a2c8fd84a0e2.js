/* Every branch link and course note exists in the initial HTML. */
(() => {
  'use strict';
  const form = document.querySelector('[data-branch-filter]');
  if (!form) return;
  const search = form.querySelector('#branch-search');
  const region = form.querySelector('#branch-region');
  const subject = form.querySelector('#branch-subject');
  const grade = form.querySelector('#branch-grade');
  const count = document.querySelector('[data-branch-count]');
  const empty = document.querySelector('[data-branch-empty]');
  const groups = [...document.querySelectorAll('[data-region-group]')];
  const cards = [...document.querySelectorAll('[data-branch-card]')].map(element => ({
    element,
    courses: JSON.parse(element.dataset.courses),
    confirmation: JSON.parse(element.dataset.unconfirmedCourses || '{}'),
    text: element.dataset.search.replace(/\s/g, '').toLowerCase()
  }));
  function filter() {
    const words = search.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    let visible = 0;
    let needsConfirmation = 0;
    for (const item of cards) {
      const known = subject.value ? (item.courses[subject.value] || []) : Object.values(item.courses).flat();
      const conditional = subject.value ? (item.confirmation[subject.value]?.grades || []) : Object.values(item.confirmation).flatMap(value => value.grades);
      const knownMatch = (!subject.value || known.length > 0) && (!grade.value || known.includes(grade.value));
      const conditionalMatch = conditional.length > 0 && (!grade.value || conditional.includes(grade.value));
      const match = words.every(word => item.text.includes(word)) && (!region?.value || item.element.dataset.region === region.value) && (knownMatch || conditionalMatch);
      item.element.hidden = !match;
      const destination=item.element.querySelector('h3 a');
      if(destination){
        const url=new URL(destination.getAttribute('href'),location.origin);
        for(const [key,value] of [['grade',grade.value],['subject',subject.value]]){
          if(value)url.searchParams.set(key,value);else url.searchParams.delete(key);
        }
        destination.href=url.pathname+url.search;
      }
      const conditionalOnly = match && !knownMatch && conditionalMatch;
      const note = item.element.querySelector('[data-course-confirmation]');
      if (note) note.dataset.matchedConfirmation = String(conditionalOnly);
      if (match) visible++;
      if (conditionalOnly) needsConfirmation++;
    }
    const filtering = words.length || region?.value || subject.value || grade.value;
    for (const group of groups) {
      group.hidden = !group.querySelector('[data-branch-card]:not([hidden])');
      if (filtering && !group.hidden) group.open = true;
      if (!filtering) group.open = groups.length === 1 || group === groups[0];
    }
    count.textContent = `전체 ${cards.length}개 지점 중 ${visible}개 표시` + (needsConfirmation ? ` · 조건 확인 필요 ${needsConfirmation}개` : '');
    empty.hidden = visible !== 0;
  }
  form.addEventListener('submit', event => { event.preventDefault(); filter(); });
  form.addEventListener('input', filter);
  form.addEventListener('change', filter);
  form.addEventListener('reset', () => { requestAnimationFrame(filter); });
  const params = new URLSearchParams(location.search);
  for (const [name, control] of [['region',region],['subject',subject],['grade',grade]]) {
    const value=params.get(name);
    if(control && [...control.options].some(option=>option.value===value)) control.value=value;
  }
  if(params.has('q')) search.value=params.get('q').slice(0,120);
  filter();
})();
