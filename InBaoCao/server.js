import express from "express";
import multer from "multer";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";
const app = express();
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 25 * 1024 * 1024, files: 1 },
});
let converting = false;
function convert(dir, input) {
  return new Promise((resolve, reject) => {
    const child = spawn(
      process.env.SOFFICE_BIN || "soffice",
      [
        "-env:UserInstallation=file://" + dir + "/profile",
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        dir,
        input,
      ],
      { stdio: "ignore" },
    );
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      reject(
        Error("Chuyển Word quá thời gian. Hãy xuất PDF từ Word rồi nhập lại."),
      );
    }, 90000);
    child.on("error", () => {
      clearTimeout(timer);
      reject(
        Error(
          "Máy chủ chưa có LibreOffice. Hãy xuất Word thành PDF rồi nhập lại.",
        ),
      );
    });
    child.on("exit", (code) => {
      clearTimeout(timer);
      code === 0
        ? resolve()
        : reject(
            Error("Không chuyển được Word. Hãy xuất PDF từ Word rồi nhập lại."),
          );
    });
  });
}
app.post("/api/convert-docx", upload.single("file"), async (req, res) => {
  let dir;
  if (converting)
    return res
      .status(429)
      .json({ error: "Đang chuyển một mẫu khác. Thử lại sau." });
  if (!req.file || !req.file.originalname.toLowerCase().endsWith(".docx"))
    return res.status(400).json({ error: "Chọn tệp .docx." });
  converting = true;
  try {
    dir = await mkdtemp(path.join(tmpdir(), "inbaocao-"));
    const { writeFile } = await import("node:fs/promises");
    const input = path.join(dir, "template.docx");
    await writeFile(input, req.file.buffer);
    await convert(dir, input);
    const pdf = await readFile(path.join(dir, "template.pdf"));
    res.type("application/pdf").send(pdf);
  } catch (e) {
    res.status(422).json({ error: e.message });
  } finally {
    if (dir) await rm(dir, { recursive: true, force: true });
    converting = false;
  }
});
app.use((error, req, res, next) => {
  res
    .status(400)
    .json({
      error:
        error.code === "LIMIT_FILE_SIZE"
          ? "Mẫu tối đa 25 MB."
          : "Không đọc được tệp gửi lên.",
    });
});
if (process.argv.includes("--dev")) {
  const { createServer } = await import("vite");
  const vite = await createServer({
    server: { middlewareMode: true },
    appType: "spa",
  });
  app.use(vite.middlewares);
} else {
  app.use(express.static(path.resolve("dist")));
  app.get("/{*path}", (req, res) =>
    res.sendFile(path.resolve("dist/index.html")),
  );
}
const port = Number(process.env.PORT) || 5173;
app.listen(port, "0.0.0.0", () =>
  console.log(`InBaoCao đang chạy trên cổng ${port}`),
);
