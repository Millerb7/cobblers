/* Cobblers player guides: the shared light / dark switch. Hand-written; every page links it in <head> so the saved
   theme applies before the first paint. Without JavaScript the page follows the system setting and hides the button. */
(function () {
  var d = document.documentElement;
  d.classList.remove('nojs');
  d.classList.add('js');
  try { var t = localStorage.getItem('cobblers-theme'); if (t) d.setAttribute('data-theme', t); } catch (e) {}
  document.addEventListener('DOMContentLoaded', function () {
    var b = document.getElementById('theme');
    if (!b) return;
    b.addEventListener('click', function () {
      var cur = d.getAttribute('data-theme') ||
        (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
      var n = cur === 'dark' ? 'light' : 'dark';
      d.setAttribute('data-theme', n);
      try { localStorage.setItem('cobblers-theme', n); } catch (e) {}
    });
  });
})();
