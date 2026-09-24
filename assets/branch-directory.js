/* Progressive enhancement: every branch link is present in HTML without JavaScript. */
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
  const cards = [...document.querySelectorAll('[data-branch-card]')].map(element => ({ element, courses: JSON.parse(element.dataset.courses), text: element.dataset.search.replace(/\s/g, '').toLowerCase() }));
  function filter() {
    const words = search.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    let visible = 0;
    for (const item of cards) {
      const courseMatch = subject.value ? item.courses[subject.value] : Object.values(item.courses).flat();
      const match = words.every(word => item.text.includes(word)) && (!region?.value || item.element.dataset.region === region.value) && (!subject.value || Boolean(courseMatch?.length)) && (!grade.value || courseMatch?.includes(grade.value));
      item.element.hidden = !match;
      if (match) visible++;
    }
    const filtering = words.length || region?.value || subject.value || grade.value;
    for (const group of groups) {
      group.hidden = !group.querySelector('[data-branch-card]:not([hidden])');
      if (filtering && !group.hidden) group.open = true;
      if (!filtering) group.open = groups.length === 1 || group === groups[0];
    }
    count.textContent = `전체 ${cards.length}개 지점 중 ${visible}개 표시`;
    empty.hidden = visible !== 0;
  }
  form.addEventListener('submit', event => { event.preventDefault(); filter(); });
  form.addEventListener('input', filter);
  form.addEventListener('change', filter);
  form.addEventListener('reset', () => { requestAnimationFrame(filter); });
  filter();
})();
