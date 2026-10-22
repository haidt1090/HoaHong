import { test } from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { resolveAsset } from "./paths.js";
import { findSoffice } from "../word-converter.js";
test("desktop assets stay inside packaged dist directory", () => {
  const root = path.resolve("/tmp/app/dist");
  assert.equal(resolveAsset(root, "/"), path.join(root, "index.html"));
  assert.equal(
    resolveAsset(root, "/assets/main.js"),
    path.join(root, "assets/main.js"),
  );
  for (const p of ["/../secret", "/%2e%2e/secret", "/..%5csecret", "/%00"])
    assert.equal(resolveAsset(root, p), null);
});
test("explicit LibreOffice override is preserved", () => {
  assert.equal(
    findSoffice({ SOFFICE_BIN: "/custom/libreoffice" }, "win32"),
    "/custom/libreoffice",
  );
  assert.equal(findSoffice({}, "win32"), "soffice");
});
