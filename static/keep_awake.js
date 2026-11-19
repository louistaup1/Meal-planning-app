/*
  "Keep screen on" for recipe pages.

  Uses the browser's Screen Wake Lock feature: while it's on, the iPad won't dim or lock
  by itself. It switches off when you press the lock button, leave the page or tap the
  button again. Your choice is remembered on this device, and switched back on when you
  come back to a recipe screen.
*/
(function () {
  var button = document.getElementById("keep-awake");
  if (!button) { return; }
  var help = document.getElementById("keep-awake-help");
  var STORAGE_KEY = "pantry-chef-keep-screen-on";
  var lock = null;

  function wanted() {
    try { return localStorage.getItem(STORAGE_KEY) === "yes"; } catch (e) { return false; }
  }
  function remember(on) {
    try { localStorage.setItem(STORAGE_KEY, on ? "yes" : "no"); } catch (e) { /* not saved: fine */ }
  }
  function show(on) {
    button.classList.toggle("is-on", on);
    button.setAttribute("aria-pressed", on ? "true" : "false");
    button.textContent = on ? "🔆 Screen stays on (tap to stop)" : "🔅 Keep screen on";
  }

  // Older iPads (before iPadOS 16.4) don't have this feature.
  if (!("wakeLock" in navigator)) {
    button.disabled = true;
    help.hidden = false;
    return;
  }

  function switchOn() {
    navigator.wakeLock.request("screen").then(function (newLock) {
      lock = newLock;
      show(true);
      // The browser lets go when you leave the page; show that it's off.
      lock.addEventListener("release", function () { lock = null; show(false); });
    }).catch(function () {
      show(false);
      help.hidden = false;
    });
  }

  function switchOff() {
    if (lock) { lock.release(); }
    lock = null;
    show(false);
  }

  button.addEventListener("click", function () {
    if (lock) {
      remember(false);
      switchOff();
    } else {
      remember(true);
      switchOn();
    }
  });

  // Coming back to the page (after switching apps or unlocking): switch on again if you wanted it.
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible" && wanted() && !lock) { switchOn(); }
  });

  show(false);
  if (wanted()) { switchOn(); }
})();
