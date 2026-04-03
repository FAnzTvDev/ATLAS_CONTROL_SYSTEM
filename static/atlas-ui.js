// ATLAS UI v30.6 — Extracted static JS
var _lastGenState = '';
setInterval(function(){
  fetch('/api/live-generations').then(function(r){return r.json()}).then(function(data){
    var state = JSON.stringify(data);
    if(state !== _lastGenState && _lastGenState !== ''){
      document.querySelectorAll('img[src*="/api/media"]').forEach(function(img){
        img.src = img.src.split('&_t=')[0] + '&_t=' + Date.now();
      });
    }
    _lastGenState = state;
  }).catch(function(){});
}, 3000);

// Lightbox
function atlasLightbox(src){
  var o = document.createElement('div');
  o.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.92);z-index:9999;display:flex;align-items:center;justify-content:center;cursor:pointer';
  o.innerHTML = '<img src="'+src+'" style="max-width:95%;max-height:90%;object-fit:contain;border-radius:8px"><div style="position:absolute;top:20px;right:30px;color:white;font-size:36px;cursor:pointer" onclick="this.parentElement.remove()">X</div>';
  o.onclick = function(e){if(e.target===o)o.remove()};
  document.body.appendChild(o);
}
setInterval(function(){
  document.querySelectorAll('.previs-card img, [class*=previs] img').forEach(function(img){
    if(!img.dataset.lb){img.dataset.lb='1';img.style.cursor='pointer';img.onclick=function(e){e.stopPropagation();atlasLightbox(img.src)}}
  });
},2000);

// Pulse CSS
var s=document.createElement('style');
s.textContent='@keyframes atlas-pulse{0%,100%{box-shadow:0 0 5px #0f8}50%{box-shadow:0 0 25px #0f8}}.atlas-generating{animation:atlas-pulse 1s infinite;opacity:.7}';
document.head.appendChild(s);
console.log('[ATLAS-UI] v30.6 loaded');
