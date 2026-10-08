/* Cobblers player guides: the shared script. Hand-written; every page links it in <head> so the saved theme applies
   before the first paint. Without JavaScript the html element keeps its `nojs` class: the page follows the system
   theme, hides the theme button, the section filter and the search box, and shows every section.

   1. the light / dark switch (#theme)
   2. the section filter: one <nav data-filter-nav> holding <button data-filter="KEY" aria-pressed>, one of them
      data-filter="all". Every element carrying data-section="KEY" is shown only while KEY (or "all") is chosen;
      anything without data-section is always shown. The choice is the page's #hash (#KEY; no hash is "all"), so a
      filter can be linked, and a link to an anchor inside a hidden section shows that section.
   3. the search box: <input data-search="SELECTOR"> hides every SELECTOR match whose data-name (or, without one, its
      text) does not contain what is typed; <span data-search-count> beside it says how many still match.
   tools/player_site.py filter_nav() and search_box() emit the markup, so no guide writes it twice. */
(function () {
  var d = document.documentElement;
  d.classList.remove('nojs');
  d.classList.add('js');
  try { var t = localStorage.getItem('cobblers-theme'); if (t) d.setAttribute('data-theme', t); } catch (e) {}

  function all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function theme() {
    var b = document.getElementById('theme');
    if (!b) return;
    b.addEventListener('click', function () {
      var cur = d.getAttribute('data-theme') ||
        (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
      var n = cur === 'dark' ? 'light' : 'dark';
      d.setAttribute('data-theme', n);
      try { localStorage.setItem('cobblers-theme', n); } catch (e) {}
    });
  }

  function filter() {
    var nav = document.querySelector('[data-filter-nav]');
    if (!nav) return;
    var btns = all('button[data-filter]', nav);
    var keys = btns.map(function (b) { return b.getAttribute('data-filter'); });
    var secs = all('[data-section]');
    function show(k) {
      if (keys.indexOf(k) < 0) k = 'all';
      secs.forEach(function (s) { s.hidden = k !== 'all' && s.getAttribute('data-section') !== k; });
      btns.forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-filter') === k)); });
      return k;
    }
    function fromHash() {
      var h = '';
      try { h = decodeURIComponent(location.hash.slice(1)); } catch (e) {}
      if (keys.indexOf(h) >= 0) { show(h); return; }
      var el = h && document.getElementById(h);
      var sec = el && el.closest('[data-section]');
      if (sec && sec.hidden) { show(sec.getAttribute('data-section')); el.scrollIntoView(); }
      else if (!h) show('all');
    }
    btns.forEach(function (b) {
      b.addEventListener('click', function () {
        var k = show(b.getAttribute('data-filter'));
        try { history.replaceState(null, '', k === 'all' ? location.pathname + location.search : '#' + k); }
        catch (e) {}
        if (nav.getBoundingClientRect().top < 0) nav.scrollIntoView();
      });
    });
    window.addEventListener('hashchange', fromHash);
    fromHash();
  }

  function search() {
    all('input[data-search]').forEach(function (q) {
      var rows = all(q.getAttribute('data-search'));
      var count = q.parentNode.querySelector('[data-search-count]');
      function run() {
        var t = q.value.trim().toLowerCase(), n = 0;
        rows.forEach(function (r) {
          var hit = !t || (r.getAttribute('data-name') || r.textContent).toLowerCase().indexOf(t) >= 0;
          r.classList.toggle('miss', !hit);
          if (hit) n++;
        });
        if (count) count.textContent = t ? n + (n === 1 ? ' entry matches' : ' entries match') : '';
      }
      q.addEventListener('input', run);
      run();
    });
  }

  document.addEventListener('DOMContentLoaded', function () { theme(); filter(); search(); });
})();
