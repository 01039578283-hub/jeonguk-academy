/* One visible map per section; source codes stay in reusable branch frames. */
(()=>{
  const frames=[...document.querySelectorAll('iframe[data-kakao-map-frame]')];
  const active=new WeakSet();
  const sendActivation=frame=>frame.contentWindow?.postMessage({type:'wawa:kakao-map-activate'},location.origin);
  const activate=frame=>{active.add(frame);sendActivation(frame)};
  const measure=frame=>frame.contentWindow?.postMessage({type:'wawa:kakao-map-measure'},location.origin);
  addEventListener('message',event=>{
    if(event.origin!==location.origin||!['wawa:kakao-map-ready','wawa:kakao-map-size'].includes(event.data?.type))return;
    const frame=frames.find(item=>item.contentWindow===event.source);
    if(!frame||String(event.data.timestamp)!==frame.dataset.mapTimestamp)return;
    if(event.data.type==='wawa:kakao-map-ready'){if(active.has(frame))sendActivation(frame);return}
    if(event.data.type!=='wawa:kakao-map-size')return;
    const height=Number(event.data.height);
    if(Number.isFinite(height)&&height>=360&&height<=4000)frame.style.height=Math.ceil(height+4)+'px';
  });
  // Keep real iframe URLs in HTML; only execute the provider when the map approaches.
  const observer='IntersectionObserver' in window?new IntersectionObserver(entries=>{
    for(const entry of entries)if(entry.isIntersecting){activate(entry.target);observer.unobserve(entry.target)}
  },{rootMargin:'600px 0px'}):null;
  frames.forEach(frame=>{frame.addEventListener('load',()=>{measure(frame);if(active.has(frame))sendActivation(frame)});if(observer)observer.observe(frame);else activate(frame)});
  document.querySelectorAll('[data-kakao-map-picker]').forEach(picker=>{
    const showSelected=()=>{
      const section=picker.closest('[data-kakao-directions]'),option=picker.selectedOptions[0],frame=section.querySelector('iframe');
      if(!option||!option.value.startsWith('/assets/kakao-maps/'))return;
      frame.dataset.mapTimestamp=option.dataset.timestamp;
      frame.title=option.dataset.branch+' 카카오맵 위치 안내';
      frame.style.height=(option.dataset.height||'1000')+'px';frame.src=option.value;
      section.querySelector('[data-map-branch-name]').textContent=option.dataset.branch;
      section.querySelector('[data-map-address]').textContent=option.dataset.address;
      section.querySelector('[data-map-branch-link]').href=option.dataset.branchUrl+'#kakao-directions';
      activate(frame);
    };
    picker.addEventListener('change',showSelected);
    // A selection may be restored or changed before this deferred script arrives.
    const frame=picker.closest('[data-kakao-directions]').querySelector('iframe');
    if(picker.value!==frame.getAttribute('src'))showSelected();
  });
})();
