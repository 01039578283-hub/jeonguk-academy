/* Progressive enhancement; all article links and regional hubs exist in HTML. */
(() => {
  'use strict';
  const form = document.querySelector('[data-library-filters]');
  if (form) {
    const cards = [...document.querySelectorAll('[data-library-card]')];
    const search = document.getElementById('ei-search');
    const topic = document.getElementById('ei-topic');
    const kind = document.getElementById('ei-kind');
    const more = document.getElementById('ei-more');
    const status = document.getElementById('ei-result-count');
    const empty = document.getElementById('ei-empty');
    let limit = 12;
    const normalize = value => value.normalize('NFKC').toLowerCase().replace(/\s+/g, '');
    const filter = () => {
      const needle = normalize(search.value.trim());
      const matches = cards.filter(card =>
        (topic.value === 'all' || card.dataset.topic === topic.value) &&
        (kind.value === 'all' || card.dataset.kind === kind.value) &&
        normalize(card.dataset.search).includes(needle));
      const visible = new Set(matches.slice(0, limit));
      for (const card of cards) card.hidden = !visible.has(card);
      status.textContent = `조건에 맞는 글 ${matches.length}편 · ${visible.size}편 표시`;
      empty.hidden = matches.length > 0;
      more.hidden = matches.length <= limit;
      more.textContent = `글 더 보기 (${Math.max(0, matches.length - limit)}편 남음)`;
    };
    const fromUrl = () => {
      const value = new URL(window.location.href).searchParams.get('topic');
      topic.value = [...topic.options].some(o => o.value === value) ? value : 'all';
      limit = 12; filter();
    };
    const syncUrl = () => {
      const url = new URL(window.location.href);
      if (topic.value === 'all') url.searchParams.delete('topic');
      else url.searchParams.set('topic', topic.value);
      window.history.replaceState(null, '', url);
    };
    form.hidden = false;
    form.addEventListener('submit', e => e.preventDefault());
    for (const control of [search, topic, kind]) control.addEventListener(control === search ? 'input' : 'change', () => {
      limit = 12; filter(); syncUrl();
    });
    form.addEventListener('reset', () => {
      // Explicit assignment avoids depending on the browser's reset event order.
      search.value = ''; topic.value = 'all'; kind.value = 'all'; limit = 12;
      filter(); syncUrl();
    });
    document.querySelector('[data-library-reset]').addEventListener('click', () => {
      form.reset(); search.focus();
    });
    more.addEventListener('click', () => {
      const previous = new Set(cards.filter(c => !c.hidden));
      limit += 12; filter();
      cards.find(c => !c.hidden && !previous.has(c))?.querySelector('a')?.focus();
    });
    for (const link of document.querySelectorAll('[data-topic-link]')) link.addEventListener('click', e => {
      // Preserve ordinary modified-click navigation.
      if (e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;
      e.preventDefault(); topic.value = link.dataset.topicLink; search.value = ''; kind.value = 'all';
      limit = 12; filter(); syncUrl();
      document.getElementById('library').scrollIntoView({block:'start'}); search.focus({preventScroll:true});
    });
    window.addEventListener('popstate', fromUrl);
    fromUrl();
  }

  const locationForm = document.querySelector('[data-location-form]');
  if (locationForm) {
    const branches = JSON.parse(document.getElementById('ei-locations').textContent);
    const region = document.getElementById('ei-region');
    const branch = document.getElementById('ei-branch');
    const output = document.getElementById('ei-location-result');
    const neighborhoodLink = () => {
      const option = region.selectedOptions[0];
      return link(`${option.dataset.neighborhoodLabel} 동네 페이지 보기`, option.dataset.neighborhoodHref);
    };
    const link = (label, path) => {
      const a = document.createElement('a'); a.textContent = label; a.href = path; return a;
    };
    const regionalResult = () => {
      output.replaceChildren();
      if (!region.value) return;
      const p = document.createElement('p');
      const matches = branches.filter(b => b.region === region.value);
      p.textContent = matches.length ? `${region.value} 지역에서 지점을 선택하면 해당 지점과 연결된 동네 안내를 볼 수 있습니다.` : '이 지역의 지점 정보는 전체 지점 안내에서 확인해 주세요. 동네별 안내도 살펴볼 수 있습니다.';
      const nav = document.createElement('nav'); nav.setAttribute('aria-label','선택 지역 안내');
      nav.append(neighborhoodLink());
      if (matches.length) nav.append(link(`${region.value} 지점 페이지 보기`, `/지점안내/${region.value}/`));
      output.append(p, nav);
    };
    region.addEventListener('change', () => {
      const matches = branches.filter(b => b.region === region.value);
      branch.replaceChildren(new Option(matches.length ? '지점을 선택하세요' : '선택할 지점이 없습니다', ''));
      for (const b of matches) branch.append(new Option(b.name, b.sitePath));
      branch.disabled = matches.length === 0; regionalResult();
    });
    branch.addEventListener('change', () => {
      const selected = branches.find(b => b.sitePath === branch.value && b.region === region.value);
      if (!selected) { regionalResult(); return; }
      const title = document.createElement('h3'); title.textContent = selected.name;
      const address = document.createElement('p'); address.textContent = selected.address;
      const nav = document.createElement('nav'); nav.setAttribute('aria-label', `${selected.name} 및 동네 안내`);
      nav.append(link(`${selected.name} 지점 정보 보기`, selected.sitePath));
      for (const n of selected.neighborhoods) nav.append(link(`${n.name} 동네 정보 보기`, n.path));
      if (!selected.neighborhoods.length) nav.append(neighborhoodLink());
      output.replaceChildren(title, address, nav);
    });
    locationForm.hidden = false;
  }
})();
