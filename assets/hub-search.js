/* Progressive enhancement: every existing directory link remains in the HTML. */
(() => {
  'use strict';
  for (const directory of document.querySelectorAll('.subject-directory')) {
    const form = directory.querySelector('[data-hub-search]');
    if (!form) continue;
    const input = form.querySelector('input');
    const status = form.querySelector('[role="status"]');
    const normalize = (value) => value.normalize('NFC').toLocaleLowerCase('ko-KR').trim().replace(/\s+/g, ' ');
    const regions = Array.from(directory.querySelectorAll('.region-block')).map((region) => {
      const name = region.querySelector('.region-title h2').textContent;
      const districts = Array.from(region.querySelectorAll('.subject-district')).map((district) => ({
        element: district,
        links: Array.from(district.querySelectorAll('.subject-local-grid > a')).map((link) => ({
          element: link,
          text: normalize(`${name} ${district.querySelector('h3').textContent} ${link.textContent}`),
        })),
      }));
      return { element: region, districts };
    });
    const total = regions.reduce((sum, region) => sum + region.districts.reduce((n, district) => n + district.links.length, 0), 0);
    const update = () => {
      const words = normalize(input.value).split(' ').filter(Boolean);
      let count = 0;
      for (const region of regions) {
        let regionCount = 0;
        for (const district of region.districts) {
          let districtCount = 0;
          for (const link of district.links) {
            const visible = words.every((word) => link.text.includes(word));
            link.element.hidden = !visible;
            if (visible) districtCount += 1;
          }
          district.element.hidden = districtCount === 0;
          regionCount += districtCount;
        }
        region.element.hidden = regionCount === 0;
        count += regionCount;
      }
      for (const link of directory.querySelectorAll('.region-jump a')) {
        const region = regions.find((entry) => `#${entry.element.id}` === link.getAttribute('href'));
        link.hidden = Boolean(region?.element.hidden);
      }
      status.textContent = count ? `전체 ${total}개 동네 안내 중 ${count}개를 표시합니다.` : '검색 결과가 없습니다. 다른 지역명이나 동네명을 입력해 주세요.';
    };
    form.addEventListener('submit', (event) => event.preventDefault());
    input.addEventListener('input', update);
    form.addEventListener('reset', () => { input.value = ''; update(); input.focus(); });
    form.dataset.ready = 'true';
    update();
  }
})();
