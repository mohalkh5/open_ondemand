/**
 * CURC Chainlit UI helpers (loaded via config.toml custom_js).
 * - curc_new_chat: click the built-in New Chat control when possible
 * - curc_copy_code: copy text to the clipboard
 */
(function () {
  function parsePayload(raw) {
    if (!raw) return null;
    if (typeof raw === "object") return raw;
    try {
      return JSON.parse(raw);
    } catch (_e) {
      return null;
    }
  }

  function copyToClipboard(text) {
    if (!text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).catch(function () {});
      return;
    }
    var el = document.createElement("textarea");
    el.value = text;
    document.body.appendChild(el);
    el.select();
    try {
      document.execCommand("copy");
    } catch (_e) {
      /* ignore */
    }
    document.body.removeChild(el);
  }

  function clickNewChat() {
    var selectors = [
      'button[aria-label="New Chat"]',
      'button[aria-label="New chat"]',
      'a[aria-label="New Chat"]',
      'a[aria-label="New chat"]',
    ];
    for (var i = 0; i < selectors.length; i++) {
      var el = document.querySelector(selectors[i]);
      if (el) {
        el.click();
        return true;
      }
    }
    var buttons = document.querySelectorAll("button");
    for (var j = 0; j < buttons.length; j++) {
      var label = (buttons[j].textContent || "").trim().toLowerCase();
      if (label === "new chat" || label.indexOf("new chat") === 0) {
        buttons[j].click();
        return true;
      }
    }
    return false;
  }

  function handleCurcMessage(payload) {
    if (!payload || !payload.type) return;
    if (payload.type === "curc_copy_code" && payload.code) {
      copyToClipboard(payload.code);
    }
    if (payload.type === "curc_new_chat") {
      clickNewChat();
    }
  }

  window.addEventListener("message", function (event) {
    var payload = parsePayload(event.data);
    handleCurcMessage(payload);
  });

  // Chainlit may deliver parent window messages on this hook when embedded.
  window.addEventListener("chainlit-window-message", function (event) {
    var payload = parsePayload(event.detail);
    handleCurcMessage(payload);
  });
})();
