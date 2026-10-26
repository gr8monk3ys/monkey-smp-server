// Fills links from config.js and wires the copy button. The pages read fine without it: tools/site_links.py
// writes the same links into the HTML.
(function () {
  var cfg = window.REALMS || {};

  var address = document.getElementById("address");
  if (cfg.ADDRESS && address) address.textContent = cfg.ADDRESS;

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

  // Text that is true only once the store is open (data-store="open"), and what it says until then ("soon").
  document.querySelectorAll("[data-store]").forEach(function (el) {
    el.hidden = (el.getAttribute("data-store") === "open") !== Boolean(cfg.STORE_URL);
  });

  // The season launch (LAUNCH_AT): site_links.py wrote it out in Pacific and Eastern; this adds the visitor's
  // own time and how long is left, and once it has passed says the season is live.
  var launch = cfg.LAUNCH_AT ? new Date(cfg.LAUNCH_AT) : null;
  var countdown = document.getElementById("countdown");
  if (launch && !isNaN(launch) && countdown) {
    var launchLabel = document.getElementById("launch-label");
    var yourTime = launch.toLocaleString(undefined, {
      weekday: "long", month: "long", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short"
    });
    var plural = function (n, word) { return n + " " + word + (n === 1 ? "" : "s"); };
    var timer;
    var tick = function () {
      var left = launch - Date.now();
      if (left <= 0) {
        if (launchLabel) launchLabel.textContent = "Season I is live";
        countdown.textContent = "The server is open: copy the address below and join.";
        clearInterval(timer);
        return;
      }
      var minutes = Math.ceil(left / 60000);
      var days = Math.floor(minutes / 1440), hours = Math.floor((minutes % 1440) / 60), mins = minutes % 60;
      // The two largest units, leaving out a zero ("3 days", not "3 days, 0 hours").
      var parts = (days ? [[days, "day"], [hours, "hour"]] : [[hours, "hour"], [mins, "minute"]])
        .filter(function (p, i) { return p[0] || (i === 1 && !days && !hours); })
        .map(function (p) { return plural(p[0], p[1]); });
      countdown.textContent = "Starts in " + parts.join(", ") + ". Your time: " + yourTime + ".";
    };
    countdown.hidden = false;
    timer = setInterval(tick, 30000);
    tick();
  }

  // The trailer plays muted while it's on screen, unless the visitor asked for less motion or less data.
  var trailer = document.getElementById("trailer");
  var calm = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var saveData = navigator.connection && navigator.connection.saveData;
  if (trailer && !calm && !saveData && "IntersectionObserver" in window) {
    // A pause the visitor made sticks; the pause event fires later, so the flag is cleared there.
    var userPaused = false, autoPause = false;
    trailer.addEventListener("pause", function () {
      if (autoPause) autoPause = false; else userPaused = true;
    });
    new IntersectionObserver(function (entries) {
      var on = entries[0].isIntersecting;
      if (on && trailer.paused && !userPaused) {
        trailer.play().catch(function () {});
      } else if (!on && !trailer.paused) {
        autoPause = true;
        trailer.pause();
      }
    }, { threshold: 0.5 }).observe(trailer);
  }

  var copy = document.getElementById("copy");
  if (copy) copy.addEventListener("click", function () {
    var text = address.textContent;
    var done = function () {
      copy.textContent = "Copied";
      setTimeout(function () { copy.textContent = "Copy"; }, 1600);
    };
    if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, function () {});
  });
})();
