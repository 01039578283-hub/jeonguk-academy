/* All learning content and destinations are rendered in the HTML. */
(() => {
  'use strict';
  const init = () => {
    const filter = document.querySelector('[data-curriculum-filter]');
    if (filter) {
      const grade = document.getElementById('ci-grade');
      const subject = document.getElementById('ci-subject');
      const search = document.getElementById('ci-search');
      const cards = Array.from(document.querySelectorAll('[data-curriculum-card]'));
      const status = document.getElementById('ci-count');
      const empty = document.getElementById('ci-empty');
      const more = document.getElementById('ci-more');
      let limit = 12;
      let matching = cards;
      const clean = value => value.toLocaleLowerCase('ko-KR').replace(/\s+/g, ' ').trim();
      const params = new URLSearchParams(window.location.search);
      for (const [input, key] of [[grade, 'grade'], [subject, 'subject']]) {
        const candidate = params.get(key);
        if (Array.from(input.options).some(option => option.value === candidate)) input.value = candidate;
      }
      search.value = (params.get('q') || '').slice(0, 120);
      const updateURL = () => {
        const url = new URL(window.location.href);
        for (const [key, value] of [['grade', grade.value], ['subject', subject.value], ['q', search.value.trim()]]) {
          if (value && value !== 'all') url.searchParams.set(key, value);
          else url.searchParams.delete(key);
        }
        window.history.replaceState(null, '', url);
      };
      const render = () => {
        const terms = clean(search.value).split(' ').filter(Boolean);
        matching = cards.filter(card =>
          (grade.value === 'all' || card.dataset.grade === grade.value) &&
          (subject.value === 'all' || card.dataset.subject === subject.value) &&
          terms.every(term => clean(card.dataset.search).includes(term)));
        const visible = new Set(matching.slice(0, limit));
        for (const card of cards) card.hidden = !visible.has(card);
        status.textContent = `조건에 맞는 안내 ${matching.length}개 · ${visible.size}개 표시`;
        empty.hidden = matching.length > 0;
        more.hidden = matching.length <= limit;
        more.textContent = `안내 더 보기 (${Math.max(0, matching.length - limit)}개 남음)`;
      };
      const change = () => { limit = 12; render(); updateURL(); };
      filter.addEventListener('submit', event => event.preventDefault());
      filter.addEventListener('input', change);
      filter.addEventListener('change', change);
      // Native reset values become available after the reset event completes.
      filter.addEventListener('reset', () => setTimeout(change, 0));
      document.querySelector('[data-curriculum-reset]').addEventListener('click', () => { filter.reset(); search.focus(); });
      more.addEventListener('click', () => {
        const firstNew = matching[limit];
        limit += 12;
        render();
        firstNew?.querySelector('a')?.focus();
      });
      render();
      filter.hidden = false;
    }
    const levelFilter = document.querySelector('[data-level-filter]');
    if (levelFilter) {
      const school = document.getElementById('ci-school-level');
      const subject = document.getElementById('ci-level-subject');
      const groups = Array.from(document.querySelectorAll('[data-level-group]'));
      const update = () => {
        let count = 0;
        for (const group of groups) {
          group.hidden = !((school.value === 'all' || group.dataset.school === school.value) && (subject.value === 'all' || group.dataset.subject === subject.value));
          if (!group.hidden) count++;
        }
        document.querySelector('[data-level-count]').textContent = `학교급·과목별 비교 ${count}개`;
      };
      levelFilter.addEventListener('submit', event => event.preventDefault());
      levelFilter.addEventListener('change', update);
      levelFilter.addEventListener('reset', () => setTimeout(update, 0));
      levelFilter.hidden = false;
      update();
    }
    const electiveFilter = document.querySelector('[data-elective-filter]');
    if (electiveFilter) {
      const subject = document.getElementById('ci-elective-subject');
      const type = document.getElementById('ci-elective-type');
      const cards = Array.from(document.querySelectorAll('[data-elective-card]'));
      const update = () => {
        let count = 0;
        for (const card of cards) {
          card.hidden = !((subject.value === 'all' || card.dataset.subject === subject.value) && (type.value === 'all' || card.dataset.type === type.value));
          if (!card.hidden) count++;
        }
        document.querySelector('[data-elective-count]').textContent = `조건에 맞는 과목 예시 ${count}개`;
        document.querySelector('[data-elective-empty]').hidden = count > 0;
      };
      electiveFilter.addEventListener('submit', event => event.preventDefault());
      electiveFilter.addEventListener('change', update);
      electiveFilter.addEventListener('reset', () => setTimeout(update, 0));
      electiveFilter.hidden = false;
      update();
    }
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true});
  else init();
})();
