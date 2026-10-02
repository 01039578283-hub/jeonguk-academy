/* Progressive enhancement only. No form submissions, storage or network calls. */
(() => {
  'use strict';
  const initialize = () => {
    if (!document.body.classList.contains('learning-guides')) return;
    const normal = value => value.normalize('NFKC').toLocaleLowerCase('ko').replace(/\s+/g, '');
    const search = document.querySelector('#guide-search');
    if (search) {
      const audience = document.querySelector('#guide-audience');
      const buttons = [...document.querySelectorAll('[data-topic]')];
      const cards = [...document.querySelectorAll('#guide-results [data-guide-card]')];
      const groups = [...document.querySelectorAll('[data-guide-group]')];
      const status = document.querySelector('#guide-count');
      let topic = 'all';
      const apply = () => {
        const terms = search.value.trim().split(/\s+/).filter(Boolean).map(normal);
        let count = 0;
        for (const card of cards) {
          const match = (topic === 'all' || card.dataset.category === topic)
            && (audience.value === 'all' || card.dataset.audience.split(' ').includes(audience.value))
            && terms.every(term => normal(card.dataset.search).includes(term));
          card.hidden = !match;
          if (match) count++;
        }
        for (const group of groups) {
          const visible = [...group.querySelectorAll('[data-guide-card]')].filter(card => !card.hidden).length;
          group.hidden = visible === 0;
          group.querySelector('[data-group-count]').textContent = `${visible}개`;
        }
        for (const button of buttons) button.setAttribute('aria-pressed', String(button.dataset.topic === topic));
        document.querySelector('#guide-empty').hidden = count !== 0;
        status.textContent = `${count}개 가이드를 볼 수 있습니다.`;
      };
      const reset = () => { search.value = ''; audience.value = 'all'; topic = 'all'; apply(); };
      search.addEventListener('input', event => { if (!event.isComposing) apply(); });
      search.addEventListener('compositionend', apply);
      search.addEventListener('search', apply);
      audience.addEventListener('change', apply);
      for (const button of buttons) button.addEventListener('click', () => { topic = button.dataset.topic; apply(); });
      document.querySelector('#guide-reset').addEventListener('click', reset);
      document.querySelector('[data-reset]').addEventListener('click', () => { reset(); search.focus(); });
      document.querySelector('.lg-finder').classList.add('lg-enhanced');
      apply();
    }
    for (const record of document.querySelectorAll('[data-record]')) {
      const fields = [...record.querySelectorAll('[data-record-field]')];
      const date = record.querySelector('[data-record-date]');
      const save = record.querySelector('[data-save-record]');
      const status = record.querySelector('.lg-record-status');
      const printRecord = record.querySelector('.lg-print-record');
      const checkedItems = () => [...document.querySelectorAll('[data-check]:checked')].map(input => input.nextElementSibling.textContent.trim());
      const content = () => [
        `전국학원 학습가이드 | ${record.dataset.title}`,
        document.querySelector('link[rel="canonical"]').href,
        '', `작성 날짜: ${date.value || '미작성'}`, '',
        ...fields.flatMap(field => [`${field.dataset.label}:`, field.value.trim() || '(미작성)', '']),
        '시작 전 확인한 항목:', ...checkedItems().map(item => `✓ ${item}`),
      ].join('\n').replace(/\r\n?/g, '\n').replace(/\n/g, '\r\n');
      const update = () => {
        const filled = fields.some(field => field.value.trim());
        save.disabled = !filled;
        status.textContent = filled ? '작성 중입니다. 페이지를 떠나기 전에 TXT로 저장하세요.' : '한 항목 이상 적으면 저장할 수 있습니다.';
        printRecord.textContent = content();
      };
      fields.forEach(field => field.addEventListener('input', update));
      date.addEventListener('input', update);
      document.querySelectorAll('[data-check]').forEach(input => input.addEventListener('change', update));
      save.addEventListener('click', () => {
        if (!fields.some(field => field.value.trim())) return;
        try {
          const blob = new Blob(['\uFEFF', content()], {type: 'text/plain;charset=utf-8'});
          const url = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = `${record.dataset.slug}-${date.value || '실천기록'}.txt`;
          document.body.appendChild(link); link.click(); link.remove();
          window.setTimeout(() => URL.revokeObjectURL(url), 30000);
          status.textContent = 'TXT 다운로드를 요청했습니다. 브라우저의 다운로드 목록을 확인하세요.';
        } catch {
          status.textContent = '파일을 저장하지 못했습니다. 작성 내용을 복사하거나 인쇄 기능을 이용하세요.';
        }
      });
      record.querySelector('[data-print]').addEventListener('click', () => { printRecord.textContent = content(); window.print(); });
      // beforeprint also supports the browser's own print command.
      window.addEventListener('beforeprint', () => { printRecord.textContent = content(); });
      update();
    }
    document.querySelectorAll('[data-js-only]').forEach(element => { element.hidden = false; });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize, {once: true});
  else initialize();
})();
