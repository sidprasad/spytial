// Open any link to the in-browser Playground in a new tab/window, so readers
// don't lose their place in the docs (and don't reload Pyodide on back-nav).
(function () {
  function mark() {
    document.querySelectorAll("a[href]").forEach(function (a) {
      var href = a.getAttribute("href") || "";
      if (/(^|\/)playground\/(index\.html)?($|[?#])/.test(href)) {
        a.target = "_blank";
        a.rel = "noopener";
      }
    });
  }
  // Material exposes `document$`; fall back to a plain load listener.
  if (typeof window.document$ !== "undefined" && window.document$.subscribe) {
    window.document$.subscribe(mark);
  } else {
    document.addEventListener("DOMContentLoaded", mark);
  }
})();
