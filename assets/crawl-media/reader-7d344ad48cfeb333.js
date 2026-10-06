(() => {
  'use strict';
  if (!window.HTMLDialogElement) return;
  let dialog, view, picture, title, toggle, previous;
  function create() {
    dialog = document.createElement('dialog');
    dialog.className = 'crawl-zoom';
    dialog.setAttribute('aria-labelledby', 'crawl-zoom-title');
    dialog.innerHTML = '<header><strong id="crawl-zoom-title"></strong><button type="button" data-zoom-size aria-pressed="false">원본 크기</button><button type="button" data-zoom-close autofocus>닫기</button></header><p class="crawl-zoom-help">원본 크기로 확대하면 좌우·위아래로 이동하며 읽을 수 있습니다.</p><div class="crawl-zoom-view" tabindex="0" aria-label="확대 이미지 이동 영역"><img alt=""></div>';
    document.body.append(dialog);
    view = dialog.querySelector('.crawl-zoom-view'); picture = view.querySelector('img');
    title = dialog.querySelector('strong'); toggle = dialog.querySelector('[data-zoom-size]');
    dialog.querySelector('[data-zoom-close]').addEventListener('click', () => dialog.close());
    toggle.addEventListener('click', () => {
      const natural = dialog.classList.toggle('is-natural');
      toggle.textContent = natural ? '화면 너비에 맞추기' : '원본 크기';
      toggle.setAttribute('aria-pressed', String(natural));
    });
    dialog.addEventListener('close', () => {
      document.documentElement.classList.remove('crawl-zoom-open');
      picture.removeAttribute('src'); previous?.focus({preventScroll:true});
    });
    dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  }
  document.addEventListener('click', event => {
    const link = event.target.closest('a[data-image-zoom]');
    if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault(); if (!dialog) create(); previous = link;
    const original = link.querySelector('img');
    title.textContent = original?.alt || '이미지 확대'; picture.alt = title.textContent;
    dialog.classList.remove('is-natural'); toggle.textContent = '원본 크기'; toggle.setAttribute('aria-pressed','false');
    picture.src = link.href; document.documentElement.classList.add('crawl-zoom-open');
    dialog.showModal(); view.scrollTo(0,0);
  });
})();
