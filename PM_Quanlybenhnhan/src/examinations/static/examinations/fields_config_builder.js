"use strict";
/*
 * Dynamic field-builder for DepartmentTemplate.fields_config.
 *
 * Renders editable rows and keeps a hidden <textarea> JSON payload in sync so
 * the existing server-side validator (validate_fields_config) still applies.
 */
(function () {
  var FIELD_TYPES = [
    "text",
    "number",
    "select",
    "multi_select",
    "boolean",
    "date",
    "textarea",
    "computed",
  ];
  // Types that use the "options" column.
  var OPTION_TYPES = ["select", "multi_select"];

  // Convert a (Vietnamese) label into a snake_case ASCII key.
  function slugifyKey(label) {
    if (!label) return "";
    var s = label.toString().normalize("NFD");
    // Strip combining diacritical marks.
    s = s.replace(/[\u0300-\u036f]/g, "");
    // Vietnamese đ/Đ are not decomposed by NFD.
    s = s.replace(/đ/g, "d").replace(/Đ/g, "D");
    s = s.toLowerCase();
    // Non-alphanumeric → underscore, collapse repeats, trim edges.
    s = s.replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
    return s;
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (k) {
      if (k === "class") {
        node.className = attrs[k];
      } else if (k === "text") {
        node.textContent = attrs[k];
      } else {
        node.setAttribute(k, attrs[k]);
      }
    });
    (children || []).forEach(function (c) {
      node.appendChild(c);
    });
    return node;
  }

  function buildTypeSelect(value) {
    var select = el("select", { class: "fcb-input fcb-type" });
    FIELD_TYPES.forEach(function (t) {
      var opt = el("option", { value: t, text: t });
      if (t === value) opt.selected = true;
      select.appendChild(opt);
    });
    return select;
  }

  function textInput(cls, value, placeholder) {
    var input = el("input", {
      type: "text",
      class: "fcb-input " + cls,
    });
    if (value !== undefined && value !== null) input.value = value;
    if (placeholder) input.placeholder = placeholder;
    return input;
  }

  function numberInput(cls, value) {
    var input = el("input", { type: "number", step: "any", class: "fcb-input " + cls });
    if (value !== undefined && value !== null && value !== "") input.value = value;
    return input;
  }

  function checkbox(cls, checked) {
    var input = el("input", { type: "checkbox", class: cls });
    input.checked = !!checked;
    return input;
  }

  function buildRow(builder, field) {
    field = field || {};
    var normal = field.normal_range || {};

    var labelIn = textInput("fcb-label", field.label, "vd: Huyết sắc tố");
    var typeIn = buildTypeSelect(field.type || "text");
    var unitIn = textInput("fcb-unit", field.unit, "g/dL");
    var reqIn = checkbox("fcb-required", field.required);
    var minIn = numberInput("fcb-min", normal.min);
    var maxIn = numberInput("fcb-max", normal.max);
    var priceIn = numberInput("fcb-price", field.default_price);
    var catIn = textInput("fcb-category", field.test_category, "blood");
    var optionsVal = Array.isArray(field.options) ? field.options.join(", ") : "";
    var optionsIn = textInput("fcb-options", optionsVal, "A, B, C");

    var removeBtn = el("button", {
      type: "button",
      class: "fcb-remove button",
      text: "✕",
    });

    var row = el("tr", { class: "fcb-row" }, [
      el("td", {}, [labelIn]),
      el("td", {}, [typeIn]),
      el("td", {}, [unitIn]),
      el("td", { class: "fcb-center" }, [reqIn]),
      el("td", {}, [minIn]),
      el("td", {}, [maxIn]),
      el("td", {}, [priceIn]),
      el("td", {}, [catIn]),
      el("td", {}, [optionsIn]),
      el("td", { class: "fcb-center" }, [removeBtn]),
    ]);

    function toggleOptions() {
      var needsOptions = OPTION_TYPES.indexOf(typeIn.value) !== -1;
      optionsIn.disabled = !needsOptions;
      optionsIn.style.opacity = needsOptions ? "1" : "0.4";
    }
    toggleOptions();

    // Preserve an existing key (when editing) so stored data keeps its key.
    if (field.key) {
      row.dataset.originalKey = field.key;
    }

    row.addEventListener("input", function () {
      builder.sync();
    });
    row.addEventListener("change", function () {
      toggleOptions();
      builder.sync();
    });
    removeBtn.addEventListener("click", function () {
      row.parentNode.removeChild(row);
      builder.sync();
    });

    return row;
  }

  function collectRow(row, index) {
    function val(cls) {
      var node = row.querySelector("." + cls);
      return node ? node.value.trim() : "";
    }
    var field = {};
    var label = val("fcb-label");
    field.label = label;
    field.type = val("fcb-type");
    field.order = index + 1;

    // Key is derived from the label; an existing key (edit) is preserved.
    field.key = row.dataset.originalKey || slugifyKey(label);

    var unit = val("fcb-unit");
    if (unit) field.unit = unit;

    var reqNode = row.querySelector(".fcb-required");
    if (reqNode && reqNode.checked) field.required = true;

    var min = val("fcb-min");
    var max = val("fcb-max");
    if (min !== "" || max !== "") {
      field.normal_range = {};
      if (min !== "") field.normal_range.min = Number(min);
      if (max !== "") field.normal_range.max = Number(max);
    }

    var price = val("fcb-price");
    if (price !== "") field.default_price = Number(price);

    var category = val("fcb-category");
    if (category) field.test_category = category;

    var optionsNode = row.querySelector(".fcb-options");
    if (optionsNode && !optionsNode.disabled) {
      var raw = optionsNode.value
        .split(",")
        .map(function (s) {
          return s.trim();
        })
        .filter(function (s) {
          return s.length > 0;
        });
      if (raw.length) field.options = raw;
    }

    return field;
  }

  function Builder(container) {
    this.container = container;
    this.rowsBody = container.querySelector(".fcb-rows");
    this.textarea = container.querySelector(".fcb-json");
    this.errorBox = container.querySelector(".fcb-error");
    var self = this;

    var addBtn = container.querySelector(".fcb-add");
    addBtn.addEventListener("click", function () {
      self.rowsBody.appendChild(buildRow(self, {}));
      self.sync();
    });

    this.render();
  }

  Builder.prototype.render = function () {
    var initial = [];
    try {
      var parsed = JSON.parse(this.textarea.value || "[]");
      if (Array.isArray(parsed)) initial = parsed;
    } catch (e) {
      this.errorBox.textContent =
        "JSON hiện tại không hợp lệ, đã khởi tạo bảng trống.";
    }
    var self = this;
    initial.forEach(function (field) {
      self.rowsBody.appendChild(buildRow(self, field));
    });
    if (initial.length === 0) {
      this.rowsBody.appendChild(buildRow(this, {}));
    }
    this.sync();
  };

  Builder.prototype.sync = function () {
    var rows = this.rowsBody.querySelectorAll(".fcb-row");
    var data = [];
    var used = {};
    var missingLabel = false;
    Array.prototype.forEach.call(rows, function (row, index) {
      var field = collectRow(row, index);
      // Skip fully-empty rows so they don't fail validation.
      if (!field.label) return;

      var base = field.key;
      if (!base) {
        // Label has no ASCII/alphanumeric characters to slugify.
        base = "field_" + (index + 1);
        missingLabel = true;
      }
      // Ensure uniqueness by appending a numeric suffix when needed.
      var key = base;
      var n = 2;
      while (used[key]) {
        key = base + "_" + n;
        n += 1;
      }
      used[key] = true;
      field.key = key;

      data.push(field);
    });
    this.textarea.value = JSON.stringify(data, null, 2);
    this.errorBox.textContent = missingLabel
      ? "Có trường không tạo được mã từ nhãn; đã dùng mã tạm."
      : "";
  };

  function init() {
    var builders = document.querySelectorAll(".fields-config-builder");
    Array.prototype.forEach.call(builders, function (container) {
      if (container.dataset.fcbReady) return;
      container.dataset.fcbReady = "1";
      new Builder(container);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
