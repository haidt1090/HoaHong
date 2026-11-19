/*
 * Report template editor (Sprint 9a).
 *
 * A dependency-free code editor for Django-template HTML:
 *   - syntax highlighting (HTML tags/attrs/strings/comments + Django tags)
 *   - line numbers
 *   - variable picker that inserts tokens at the caret
 *   - live preview against sample or real data
 *
 * Technique: a transparent <textarea> sits on top of a highlighted <pre>.
 * The textarea keeps native editing/undo/IME behaviour; the <pre> underneath
 * supplies the colour. Both share identical font metrics and scroll together.
 */
(function () {
  "use strict";

  function escapeHtml(text) {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  /**
   * Tokenize with a single alternation pass so we never highlight inside an
   * already-consumed region (which is what causes nested-markup corruption).
   * Order matters: Django tags win over HTML so {% if x > 1 %} stays intact.
   */
  var PATTERN = new RegExp(
    [
      "(\\{#[\\s\\S]*?#\\})", // 1 django comment
      "(\\{%[\\s\\S]*?%\\})", // 2 django block tag
      "(\\{\\{[\\s\\S]*?\\}\\})", // 3 django variable
      "(<!--[\\s\\S]*?-->)", // 4 html comment
      "(<[^>]*>)", // 5 html tag
    ].join("|"),
    "g"
  );

  var TAG_INNER = /(=)|("[^"]*"|'[^']*')|([A-Za-z_:][-A-Za-z0-9_:.]*)/g;

  function highlightHtmlTag(tag) {
    // tag includes the angle brackets.
    var out = "";
    var last = 0;
    var seenName = false;
    var m;
    TAG_INNER.lastIndex = 0;
    while ((m = TAG_INNER.exec(tag)) !== null) {
      out += escapeHtml(tag.slice(last, m.index));
      if (m[2]) {
        out += '<span class="tok-string">' + escapeHtml(m[2]) + "</span>";
      } else if (m[3]) {
        if (!seenName) {
          out += '<span class="tok-tag">' + escapeHtml(m[3]) + "</span>";
          seenName = true;
        } else {
          out += '<span class="tok-attr">' + escapeHtml(m[3]) + "</span>";
        }
      } else {
        out += escapeHtml(m[0]);
      }
      last = m.index + m[0].length;
    }
    out += escapeHtml(tag.slice(last));
    return out;
  }

  function highlight(source) {
    var out = "";
    var last = 0;
    var m;
    PATTERN.lastIndex = 0;
    while ((m = PATTERN.exec(source)) !== null) {
      out += escapeHtml(source.slice(last, m.index));
      if (m[1]) {
        out += '<span class="tok-dj-cmt">' + escapeHtml(m[1]) + "</span>";
      } else if (m[2]) {
        out += '<span class="tok-dj-block">' + escapeHtml(m[2]) + "</span>";
      } else if (m[3]) {
        out += '<span class="tok-dj-var">' + escapeHtml(m[3]) + "</span>";
      } else if (m[4]) {
        out += '<span class="tok-comment">' + escapeHtml(m[4]) + "</span>";
      } else if (m[5]) {
        out += highlightHtmlTag(m[5]);
      }
      last = m.index + m[0].length;
    }
    out += escapeHtml(source.slice(last));
    // Trailing newline keeps the last line visible in the <pre>.
    return out + "\n";
  }

  function getCookie(name) {
    var match = document.cookie.match(
      new RegExp("(^|;\\s*)" + name + "=([^;]*)")
    );
    return match ? decodeURIComponent(match[2]) : "";
  }

  function Editor(root) {
    this.root = root;
    this.textarea = root.querySelector("[data-source]");
    this.highlightEl = root.querySelector("[data-highlight]");
    this.gutter = root.querySelector("[data-gutter]");
    this.varsPanel = root.querySelector("[data-vars]");
    this.varList = root.querySelector("[data-var-list]");
    this.varSearch = root.querySelector("[data-var-search]");
    this.status = root.querySelector("[data-status]");
    this.previewBox = root.querySelector("[data-preview]");
    this.previewFrame = root.querySelector("[data-preview-frame]");
    this.previewKind = root.dataset.previewKind || "";

    try {
      this.groups = JSON.parse(root.dataset.variables || "[]");
    } catch (e) {
      this.groups = [];
    }

    this.bind();
    this.render();
    this.renderVariables("");
  }

  Editor.prototype.bind = function () {
    var self = this;

    this.textarea.addEventListener("input", function () {
      self.render();
    });
    this.textarea.addEventListener("scroll", function () {
      self.highlightEl.scrollTop = self.textarea.scrollTop;
      self.highlightEl.scrollLeft = self.textarea.scrollLeft;
      self.gutter.scrollTop = self.textarea.scrollTop;
    });

    // Tab inserts two spaces instead of leaving the field.
    this.textarea.addEventListener("keydown", function (event) {
      if (event.key !== "Tab" || event.ctrlKey || event.altKey) return;
      event.preventDefault();
      self.insert("  ");
    });

    this.root.addEventListener("click", function (event) {
      var button = event.target.closest("[data-action]");
      if (!button) return;
      var action = button.dataset.action;
      if (action === "toggle-vars") {
        var hidden = self.varsPanel.hasAttribute("hidden");
        self.varsPanel.toggleAttribute("hidden", !hidden);
        button.setAttribute("aria-pressed", hidden ? "true" : "false");
      } else if (action === "preview") {
        self.preview();
      } else if (action === "close-preview") {
        self.previewBox.setAttribute("hidden", "");
      } else if (action === "wrap-loop") {
        self.wrapLoop();
      }
    });

    if (this.varSearch) {
      this.varSearch.addEventListener("input", function () {
        self.renderVariables(self.varSearch.value.trim().toLowerCase());
      });
    }
  };

  Editor.prototype.render = function () {
    var value = this.textarea.value;
    this.highlightEl.innerHTML = highlight(value);
    var lines = value.split("\n").length;
    var gutter = "";
    for (var i = 1; i <= lines; i++) gutter += i + "\n";
    this.gutter.textContent = gutter;
    // Grow the textarea with the content so long templates stay usable.
    this.textarea.style.height = "auto";
    var target = Math.max(320, this.textarea.scrollHeight);
    this.textarea.style.height = target + "px";
    this.highlightEl.style.height = target + "px";
  };

  Editor.prototype.insert = function (text) {
    var ta = this.textarea;
    var start = ta.selectionStart;
    var end = ta.selectionEnd;
    ta.focus();
    // execCommand keeps the native undo stack intact where supported.
    var ok = false;
    try {
      ok = document.execCommand("insertText", false, text);
    } catch (e) {
      ok = false;
    }
    if (!ok) {
      ta.value = ta.value.slice(0, start) + text + ta.value.slice(end);
      ta.selectionStart = ta.selectionEnd = start + text.length;
    }
    this.render();
  };

  Editor.prototype.wrapLoop = function () {
    var ta = this.textarea;
    var selected = ta.value.slice(ta.selectionStart, ta.selectionEnd);
    var inner = selected || "  <td>{{ field.label }}</td>\n  <td>{{ field.value }}</td>";
    this.insert("{% for field in fields %}\n" + inner + "\n{% endfor %}");
  };

  Editor.prototype.renderVariables = function (query) {
    var self = this;
    this.varList.innerHTML = "";
    this.groups.forEach(function (group) {
      var matches = group.variables.filter(function (v) {
        if (!query) return true;
        return (
          v.label.toLowerCase().indexOf(query) !== -1 ||
          v.token.toLowerCase().indexOf(query) !== -1
        );
      });
      if (!matches.length) return;

      var heading = document.createElement("div");
      heading.className = "rt-editor__var-group";
      heading.textContent = group.group;
      self.varList.appendChild(heading);

      matches.forEach(function (variable) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "rt-editor__var";
        var label = document.createElement("b");
        label.textContent = variable.label;
        var code = document.createElement("code");
        code.textContent = variable.token;
        button.appendChild(label);
        button.appendChild(code);
        button.addEventListener("click", function () {
          self.insert(variable.token);
        });
        self.varList.appendChild(button);
      });
    });
  };

  Editor.prototype.setStatus = function (message, isError) {
    this.status.textContent = message || "";
    this.status.classList.toggle("is-error", Boolean(isError));
  };

  Editor.prototype.preview = function () {
    var self = this;
    var objectId = this.root.dataset.objectId || readObjectIdFromUrl();
    if (!objectId) {
      this.setStatus("Lưu template trước khi xem trước.", true);
      return;
    }

    var base =
      this.previewKind === "department"
        ? "/api/department-report-templates/"
        : "/api/report-templates/";
    var payload = { output_format: "html", limit: 3 };
    if (this.previewKind === "department") {
      payload.body_html = this.textarea.value;
    } else if (this.textarea.name === "body_html") {
      payload.body_html = this.textarea.value;
    }

    this.setStatus("Đang tạo bản xem trước…", false);

    fetch(base + objectId + "/preview/", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
      },
      body: JSON.stringify(payload),
    })
      .then(function (response) {
        return response.text().then(function (body) {
          return { ok: response.ok, body: body };
        });
      })
      .then(function (result) {
        if (!result.ok) {
          var message = result.body;
          try {
            message = JSON.parse(result.body).error || message;
          } catch (e) {
            /* keep raw body */
          }
          self.setStatus(message, true);
          return;
        }
        self.setStatus("", false);
        self.previewBox.removeAttribute("hidden");
        self.previewFrame.srcdoc = result.body;
      })
      .catch(function (error) {
        self.setStatus("Lỗi kết nối: " + error.message, true);
      });
  };

  function readObjectIdFromUrl() {
    // /admin/reports/reporttemplate/<uuid>/change/
    var match = window.location.pathname.match(
      /\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\//i
    );
    return match ? match[1] : "";
  }

  function init(scope) {
    (scope || document)
      .querySelectorAll("[data-editor-root]")
      .forEach(function (root) {
        if (root.dataset.ready === "1") return;
        root.dataset.ready = "1";
        new Editor(root);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      init(document);
    });
  } else {
    init(document);
  }

  // Re-init editors inside dynamically added admin inlines.
  document.addEventListener("formset:added", function (event) {
    init(event.target);
  });
})();
