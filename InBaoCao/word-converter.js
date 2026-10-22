import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

export function findSoffice(env = process.env, platform = process.platform) {
  if (env.SOFFICE_BIN) return env.SOFFICE_BIN;
  if (platform === "win32") {
    for (const root of [
      env.ProgramW6432,
      env.ProgramFiles,
      env["ProgramFiles(x86)"],
    ].filter(Boolean)) {
      const executable = path.join(
        root,
        "LibreOffice",
        "program",
        "soffice.exe",
      );
      if (existsSync(executable)) return executable;
    }
  }
  if (
    platform === "darwin" &&
    existsSync("/Applications/LibreOffice.app/Contents/MacOS/soffice")
  )
    return "/Applications/LibreOffice.app/Contents/MacOS/soffice";
  return "soffice";
}

export function convertWord(dir, input) {
  return new Promise((resolve, reject) => {
    const child = spawn(
      findSoffice(),
      [
        "-env:UserInstallation=" +
          pathToFileURL(path.join(dir, "profile")).href,
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        dir,
        input,
      ],
      { stdio: "ignore", windowsHide: true },
    );
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      child.kill("SIGKILL");
    }, 90000);
    child.once("error", () => {
      clearTimeout(timer);
      reject(
        new Error(
          "Chưa tìm thấy LibreOffice. Cài LibreOffice hoặc xuất Word thành PDF rồi nhập lại.",
        ),
      );
    });
    child.once("close", (code) => {
      clearTimeout(timer);
      if (timedOut)
        reject(
          new Error(
            "Chuyển Word quá thời gian. Hãy xuất PDF từ Word rồi nhập lại.",
          ),
        );
      else if (code === 0) resolve();
      else
        reject(
          new Error(
            "Không chuyển được Word. Hãy xuất PDF từ Word rồi nhập lại.",
          ),
        );
    });
  });
}
