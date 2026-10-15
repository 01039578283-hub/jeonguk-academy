/* One visible map per section; source codes stay in reusable branch frames. */
(()=>{
  const frames=[...document.querySelectorAll('iframe[data-kakao-map-frame]')];
  const measure=frame=>frame.contentWindow?.postMessage({type:'wawa:kakao-map-measure'},location.origin);
  addEventListener('message',event=>{
    if(event.origin!==location.origin||event.data?.type!=='wawa:kakao-map-size')return;
    const frame=frames.find(item=>item.contentWindow===event.source);
    if(!frame||String(event.data.timestamp)!==frame.dataset.mapTimestamp)return;
    const height=Number(event.data.height);
    if(Number.isFinite(height)&&height>=360&&height<=4000)frame.style.height=Math.ceil(height+4)+'px';
  });
  frames.forEach(frame=>{frame.addEventListener('load',()=>measure(frame));measure(frame)});
  document.querySelectorAll('[data-kakao-map-picker]').forEach(picker=>{
    const showSelected=()=>{
      const section=picker.closest('[data-kakao-directions]'),option=picker.selectedOptions[0],frame=section.querySelector('iframe');
      if(!option||!option.value.startsWith('/assets/kakao-maps/'))return;
      frame.dataset.mapTimestamp=option.dataset.timestamp;
      frame.title=option.dataset.branch+' 카카오맵 위치와 교통 안내';
      frame.style.height=(option.dataset.height||'1000')+'px';frame.src=option.value;
      section.querySelector('[data-map-branch-name]').textContent=option.dataset.branch;
      section.querySelector('[data-map-address]').textContent=option.dataset.address;
      section.querySelector('[data-map-branch-link]').href=option.dataset.branchUrl+'#kakao-directions';
      section.querySelector('[data-map-place-link]').href=option.dataset.placeUrl;
    };
    picker.addEventListener('change',showSelected);
    // A selection may be restored or changed before this deferred script arrives.
    const frame=picker.closest('[data-kakao-directions]').querySelector('iframe');
    if(picker.value!==frame.getAttribute('src'))showSelected();
  });
})();
