// Fills links from config.js and wires the copy button. The page reads fine without it.
(function () {
  var cfg = window.REALMS || {};

  if (cfg.ADDRESS) document.getElementById("address").textContent = cfg.ADDRESS;

  // A link whose URL isn't set yet points at the Discord and says so.
  document.querySelectorAll("[data-link]").forEach(function (a) {
    var url = cfg[a.getAttribute("data-link")];
    if (url) {
      a.href = url;
      if (/^https?:/.test(url)) a.rel = "noopener";
    } else if (cfg.DISCORD_INVITE && a.getAttribute("data-link") !== "DISCORD_INVITE") {
      a.href = cfg.DISCORD_INVITE;
      a.title = "Coming soon: ask in the Discord";
    }
  });

  var copy = document.getElementById("copy");
  copy.addEventListener("click", function () {
    var text = document.getElementById("address").textContent;
    var done = function () {
      copy.textContent = "Copied";
      setTimeout(function () { copy.textContent = "Copy"; }, 1600);
    };
    if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, function () {});
  });
})();
