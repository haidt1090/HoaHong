import { app, BrowserWindow, protocol, net, dialog, Menu } from "electron";
import { readFile, mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { convertWord } from "../word-converter.js";
import { resolveAsset } from "./paths.js";

protocol.registerSchemesAsPrivileged([
  {
    scheme: "inbaocao",
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      corsEnabled: true,
      stream: true,
    },
  },
]);
app.setName("InBaoCao");
// Stable browser storage across app upgrades, installation folders and installer/portable builds.
app.setPath("userData", path.join(app.getPath("appData"), "InBaoCao"));
let window;
let converting = false;
const CSP =
  "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self' blob: data:; worker-src 'self' blob:; frame-src 'self' blob:; object-src 'self' blob:; base-uri 'none'; form-action 'none'";
const jsonError = (message, status = 400) =>
  Response.json({ error: message }, { status });
async function handleRequest(request) {
  const url = new URL(request.url);
  if (url.host !== "app") return new Response("Forbidden", { status: 403 });
  if (url.pathname === "/api/convert-docx") {
    if (request.method !== "POST")
      return jsonError("Phương thức không hợp lệ.", 405);
    if (converting)
      return jsonError("Đang chuyển một mẫu khác. Thử lại sau.", 429);
    let dir;
    converting = true;
    try {
      const length = Number(request.headers.get("content-length"));
      if (length > 26 * 1024 * 1024) return jsonError("Mẫu tối đa 25 MB.", 413);
      const form = await request.formData();
      const file = form.get("file");
      if (
        !file ||
        typeof file.arrayBuffer !== "function" ||
        !file.name.toLowerCase().endsWith(".docx")
      )
        return jsonError("Chọn tệp .docx.");
      if (file.size > 25 * 1024 * 1024)
        return jsonError("Mẫu tối đa 25 MB.", 413);
      dir = await mkdtemp(path.join(tmpdir(), "inbaocao-"));
      const input = path.join(dir, "template.docx");
      await writeFile(input, new Uint8Array(await file.arrayBuffer()));
      await convertWord(dir, input);
      return new Response(await readFile(path.join(dir, "template.pdf")), {
        headers: { "Content-Type": "application/pdf" },
      });
    } catch (error) {
      return jsonError(error.message, 422);
    } finally {
      if (dir) await rm(dir, { recursive: true, force: true });
      converting = false;
    }
  }
  if (request.method !== "GET")
    return new Response("Method not allowed", { status: 405 });
  const root = path.join(
    path.dirname(fileURLToPath(import.meta.url)),
    "..",
    "dist",
  );
  const target = resolveAsset(root, url.pathname);
  if (!target) return new Response("Forbidden", { status: 403 });
  try {
    const result = await net.fetch(pathToFileURL(target).href);
    const headers = new Headers(result.headers);
    headers.set("Content-Security-Policy", CSP);
    return new Response(result.body, { status: result.status, headers });
  } catch {
    return new Response("Not found", { status: 404 });
  }
}
function openWindow() {
  window = new BrowserWindow({
    width: 1440,
    height: 960,
    minWidth: 900,
    minHeight: 650,
    title: "InBaoCao",
    backgroundColor: "#f6f8fa",
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true,
    },
  });
  window.once("ready-to-show", () => window.show());
  window.webContents.on("will-navigate", (event, url) => {
    if (!url.startsWith("inbaocao://app/")) event.preventDefault();
  });
  window.webContents.setWindowOpenHandler(({ url }) =>
    url.startsWith("blob:inbaocao://app/")
      ? {
          action: "allow",
          overrideBrowserWindowOptions: {
            title: "InBaoCao · PDF để in",
            webPreferences: {
              nodeIntegration: false,
              contextIsolation: true,
              sandbox: true,
            },
          },
        }
      : { action: "deny" },
  );
  window.webContents.session.setPermissionRequestHandler(
    (_contents, _permission, callback) => callback(false),
  );
  window.loadURL("inbaocao://app/");
  window.on("closed", () => {
    window = null;
  });
}
if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on("second-instance", () => {
    if (window) {
      if (window.isMinimized()) window.restore();
      window.focus();
    }
  });
  app
    .whenReady()
    .then(() => {
      protocol.handle("inbaocao", handleRequest);
      Menu.setApplicationMenu(
        Menu.buildFromTemplate([
          {
            label: "Ứng dụng",
            submenu: [
              {
                label: "Thông tin InBaoCao",
                click: () =>
                  dialog.showMessageBox({
                    type: "info",
                    title: "InBaoCao",
                    message: `InBaoCao ${app.getVersion()}`,
                    detail:
                      "In sổ khám sức khỏe A3 hàng loạt. Kho mẫu lưu riêng trên máy này. Dùng Sao lưu kho mẫu để mang mẫu sang máy khác.",
                  }),
              },
              { type: "separator" },
              { role: "quit", label: "Thoát" },
            ],
          },
          {
            label: "Chỉnh sửa",
            submenu: [
              { role: "undo", label: "Hoàn tác" },
              { role: "redo", label: "Làm lại" },
              { type: "separator" },
              { role: "cut", label: "Cắt" },
              { role: "copy", label: "Sao chép" },
              { role: "paste", label: "Dán" },
              { role: "selectAll", label: "Chọn tất cả" },
            ],
          },
          {
            label: "Hiển thị",
            submenu: [
              { role: "resetZoom", label: "Kích thước mặc định" },
              { role: "zoomIn", label: "Phóng to" },
              { role: "zoomOut", label: "Thu nhỏ" },
              { role: "togglefullscreen", label: "Toàn màn hình" },
              ...(!app.isPackaged
                ? [{ role: "toggleDevTools", label: "Công cụ phát triển" }]
                : []),
            ],
          },
        ]),
      );
      openWindow();
      app.on("activate", () => {
        if (BrowserWindow.getAllWindows().length === 0) openWindow();
      });
    })
    .catch((error) => {
      dialog.showErrorBox("Không mở được InBaoCao", error.message);
      app.quit();
    });
  app.on("window-all-closed", () => {
    if (process.platform !== "darwin") app.quit();
  });
}
