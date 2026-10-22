import { test } from "node:test";
import assert from "node:assert/strict";
import { autoMap, normalize, cellText, mappedValue, fields } from "./data.js";
test("maps all requested headers without accents or case sensitivity", () => {
  const headers = [
    "stt",
    "HO VA TEN",
    "gioi tinh",
    "ma nv",
    "ngay sinh",
    "cccd",
    "ngay cap cccd",
    "noi cap cccd",
    "dan toc",
    "noi o hien tai",
    "nghe nghiep",
    "CONG TY",
  ];
  const m = autoMap(headers);
  assert.equal(Object.values(m).filter(Boolean).length, 12);
  assert.equal(m.name, "HO VA TEN");
  assert.equal(m.workplace, "CONG TY");
  assert.equal(autoMap(["Họ tên"]).name, "Họ tên");
});
test("optional fields stay blank and manual constant works", () => {
  assert.equal(mappedValue({}, {}, "name"), "");
  assert.equal(
    mappedValue({}, {}, "workplace", { workplace: "Công ty A" }),
    "Công ty A",
  );
  assert.equal(
    mappedValue({ name: "Nguyễn An" }, { name: "name" }, "name"),
    "Nguyễn An",
  );
  assert.equal(fields.length, 12);
});
test("dates, formulas and rich text retain display values", () => {
  assert.equal(cellText(new Date("2001-02-03T00:00:00Z")), "03/02/2001");
  assert.equal(cellText({ formula: "1+1", result: 2 }), "2");
  assert.equal(
    cellText({ richText: [{ text: "Nguyễn " }, { text: "An" }] }),
    "Nguyễn An",
  );
  assert.equal(normalize("ĐẶNG Thị Ánh"), "dangthianh");
});
