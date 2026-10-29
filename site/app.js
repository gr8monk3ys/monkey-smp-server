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
  // own time and counts down the days, hours and minutes left, and once it has passed says the season is live.
  var launch = cfg.LAUNCH_AT ? new Date(cfg.LAUNCH_AT) : null;
  var countdown = document.getElementById("countdown");
  var counter = document.getElementById("counter");
  if (launch && !isNaN(launch) && countdown) {
    var launchLabel = document.getElementById("launch-label");
    var cells = counter ? counter.querySelectorAll(".cell") : [];
    var units = ["day", "hour", "minute"];
    var timer;
    // A digit that changes drops into its block (the .drop animation in style.css).
    var show = function (cell, n, unit) {
      var digits = cell.querySelector("i"), text = (n < 10 ? "0" : "") + n;
      cell.querySelector(".unit").textContent = unit + (n === 1 ? "" : "s");
      if (digits.textContent === text) return;
      digits.textContent = text;
      digits.classList.remove("drop");
      void digits.offsetWidth;
      digits.classList.add("drop");
    };
    var tick = function () {
      var left = launch - Date.now();
      if (left <= 0) {
        if (launchLabel) launchLabel.textContent = "Season I is live";
        if (counter) counter.hidden = true;
        countdown.textContent = "The server is open: copy the address below and join.";
        clearInterval(timer);
        return;
      }
      var minutes = Math.ceil(left / 60000);
      [Math.floor(minutes / 1440), Math.floor((minutes % 1440) / 60), minutes % 60].forEach(function (n, i) {
        if (cells[i]) show(cells[i], n, units[i]);
      });
    };
    countdown.textContent = "Your time: " + launch.toLocaleString(undefined, {
      weekday: "long", month: "long", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short"
    }) + ".";
    countdown.hidden = false;
    if (counter) counter.hidden = false;
    timer = setInterval(tick, 15000);
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

  // The blocks of a [data-place] list that start below the fold drop into place as they scroll into view, a
  // few at a time (.unplaced and .placed in style.css). The ones on screen at load are left alone, and so is
  // everything for visitors who asked for less motion. Printing shows them all.
  var places = document.querySelectorAll("[data-place]");
  if (places.length && !calm && "IntersectionObserver" in window) {
    var waiting = [];
    places.forEach(function (list) {
      Array.prototype.forEach.call(list.children, function (block) {
        if (block.getBoundingClientRect().top > window.innerHeight) {
          block.classList.add("unplaced");
          waiting.push(block);
        }
      });
    });
    var placer = new IntersectionObserver(function (entries) {
      var n = 0;
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var block = entry.target;
        placer.unobserve(block);
        setTimeout(function () {
          block.classList.remove("unplaced");
          block.classList.add("placed");
        }, Math.min(n++ * 60, 300));
      });
    }, { rootMargin: "0px 0px -8% 0px" });
    waiting.forEach(function (block) { placer.observe(block); });
    window.addEventListener("beforeprint", function () {
      waiting.forEach(function (block) { block.classList.remove("unplaced"); });
    });
  }

  // Copy puts the address on the clipboard; where the browser won't allow that, it selects the address so
  // the visitor can copy it themselves.
  var copy = document.getElementById("copy");
  if (copy && address) copy.addEventListener("click", function () {
    var say = function (word) {
      copy.textContent = word;
      setTimeout(function () { copy.textContent = "Copy"; }, 1600);
    };
    var select = function () {
      var range = document.createRange();
      range.selectNodeContents(address);
      var selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      say("Selected");
    };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(address.textContent).then(function () { say("Copied"); }, select);
    } else {
      select();
    }
  });
})();
