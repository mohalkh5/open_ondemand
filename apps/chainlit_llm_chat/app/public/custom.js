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

  function clearChainlitThreadStorage() {
    try {
      Object.keys(localStorage).forEach(function (key) {
        var lower = key.toLowerCase();
        if (
          lower.indexOf("chainlit") !== -1 &&
          (lower.indexOf("thread") !== -1 || lower.indexOf("session") !== -1)
        ) {
          localStorage.removeItem(key);
        }
      });
      Object.keys(sessionStorage).forEach(function (key) {
        var lower = key.toLowerCase();
        if (lower.indexOf("chainlit") !== -1 && lower.indexOf("thread") !== -1) {
          sessionStorage.removeItem(key);
        }
      });
    } catch (_e) {
      /* ignore */
    }
  }

  function clickNewChat() {
    var selectors = [
      'button[aria-label="New Chat"]',
      'button[aria-label="New chat"]',
      'a[aria-label="New Chat"]',
      'a[aria-label="New chat"]',
      '[data-testid="new-chat-button"]',
      '[data-testid="new-chat"]',
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

  function startNewChat() {
    clearChainlitThreadStorage();
    if (clickNewChat()) {
      return;
    }
    // Fallback: reload app root so Chainlit starts a fresh thread/socket session.
    var path = window.location.pathname || "/";
    if (!path.endsWith("/")) {
      path += "/";
    }
    window.location.assign(path);
  }

  function handleCurcMessage(payload) {
    if (!payload || !payload.type) return;
    if (payload.type === "curc_copy_code" && payload.code) {
      copyToClipboard(payload.code);
    }
    if (payload.type === "curc_new_chat") {
      startNewChat();
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

  /** Hide attach-file controls (backup if config.toml upload flag is stale on server). */
  function hideAttachControls() {
    var selectors = [
      'button[aria-label="Attach files"]',
      'button[aria-label*="Attach file"]',
      "#upload-drop-input",
      'input[type="file"]',
    ];
    selectors.forEach(function (sel) {
      document.querySelectorAll(sel).forEach(function (el) {
        el.style.display = "none";
        el.setAttribute("disabled", "true");
        if (el.type === "file") {
          el.disabled = true;
        }
      });
    });
  }

  /** Hide human feedback buttons (thumbs up/down on assistant messages). */
  function hideFeedbackControls() {
    var selectors = [
      'button[aria-label="Helpful"]',
      'button[aria-label="Not helpful"]',
      'button[aria-label="Edit feedback"]',
    ];
    selectors.forEach(function (sel) {
      document.querySelectorAll(sel).forEach(function (el) {
        el.style.display = "none";
        el.setAttribute("disabled", "true");
        el.setAttribute("aria-hidden", "true");
      });
    });
  }

  function hideCurcDisabledControls() {
    hideAttachControls();
    hideFeedbackControls();
  }

  /** Canonical CURC welcome disclaimer (empty-state screen only). */
  function injectWelcomeNotice() {
    var screen = document.getElementById("welcome-screen");
    if (!screen || screen.querySelector("#curc-welcome-notice")) {
      return;
    }
    var textarea = screen.querySelector("textarea");
    if (!textarea) {
      return;
    }

    var notice = document.createElement("div");
    notice.id = "curc-welcome-notice";
    notice.className = "curc-welcome-notice";
    notice.innerHTML =
      '<p class="curc-welcome-title"><strong>CURC LLM Chat Interface</strong></p>' +
      '<blockquote><strong>Please note:</strong> This assistant was <strong>not</strong> trained on ' +
      '<a href="https://curc.readthedocs.io" target="_blank" rel="noopener noreferrer">' +
      "CU Research Computing (CURC) documentation</a>. " +
      "For this reason, information about CURC-specific clusters, software modules, " +
      "queues, filesystems, policies, or procedures, may be <strong>incorrect</strong>. " +
      "Always verify important details in the official documentation or with CURC support.</blockquote>";

    var composerRoot = textarea;
    while (composerRoot && composerRoot.parentElement !== screen) {
      composerRoot = composerRoot.parentElement;
    }
    if (composerRoot) {
      screen.insertBefore(notice, composerRoot);
    } else {
      screen.insertBefore(notice, textarea);
    }
  }

  function isDarkTheme() {
    var root = document.documentElement;
    if (root.classList.contains("dark")) {
      return true;
    }
    if (root.classList.contains("light")) {
      return false;
    }
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  /** Point the welcome logo at CURC branding (works with OOD root-path relative URLs). */
  function patchWelcomeLogo() {
    var screen = document.getElementById("welcome-screen");
    if (!screen) {
      return;
    }
    var img = screen.querySelector("img");
    if (!img) {
      return;
    }
    var theme = isDarkTheme() ? "dark" : "light";
    if (img.getAttribute("data-curc-logo-theme") === theme) {
      return;
    }
    var base = window.location.pathname.replace(/\/?$/, "");
    img.src = base + "/logo?theme=" + theme;
    img.alt = "CURC LLM Chat";
    img.setAttribute("data-curc-logo", "1");
    img.setAttribute("data-curc-logo-theme", theme);
    img.classList.add("curc-welcome-logo");
  }

  function refreshCurcUi() {
    hideCurcDisabledControls();
    patchWelcomeLogo();
    injectWelcomeNotice();
  }

  refreshCurcUi();
  var uiObserver = new MutationObserver(refreshCurcUi);
  uiObserver.observe(document.documentElement, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["class"],
  });
})();
