import { _electron as electron, expect } from "@playwright/test";
import { PDFDocument } from "pdf-lib";
import ExcelJS from "exceljs";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

const config = await mkdtemp(path.join(tmpdir(), "inbaocao-desktop-test-"));
const application = await electron.launch({
  args: [...(process.platform === "linux" ? ["--no-sandbox"] : []), "."],
  env: {
    ...process.env,
    XDG_CONFIG_HOME: config,
    XDG_CACHE_HOME: path.join(config, "cache"),
    APPDATA: config,
  },
});
try {
  const page = await application.firstWindow();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await expect(
    page.getByRole("heading", { name: "In sổ khám sức khỏe", exact: true }),
  ).toBeVisible();
  const source = await PDFDocument.create();
  source.addPage([1190.55, 841.89]);
  source.addPage([1190.55, 841.89]);
  await page
    .locator('input[accept=".pdf,.docx,.png,.jpg,.jpeg"]')
    .setInputFiles({
      name: "Mẫu thử desktop.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from(await source.save()),
    });
  await expect(
    page.getByText(
      "Đã nhập mẫu. Chọn trường bên phải rồi bấm vào vị trí cần điền trên giấy.",
    ),
  ).toBeVisible({ timeout: 30000 });
  await page.locator(".paper").click({ position: { x: 100, y: 100 } });
  await page.getByRole("button", { name: "Trang sau", exact: true }).click();
  await page.locator(".paper").click({ position: { x: 120, y: 120 } });
  await page
    .getByRole("button", { name: "In sổ sức khỏe", exact: true })
    .click();
  const book = new ExcelJS.Workbook();
  const sheet = book.addWorksheet("Thử");
  sheet.addRow(["STT", "HO VA TEN", "CCCD"]);
  sheet.addRow([1, "Nguyễn Thị Ánh", "001234567890"]);
  sheet.addRow([2, "Đặng Văn Bình", "002345678901"]);
  await page
    .locator('input[accept=".xlsx"]')
    .setInputFiles({
      name: "desktop.xlsx",
      mimeType:
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      buffer: Buffer.from(await book.xlsx.writeBuffer()),
    });
  await expect(page.locator("tbody tr")).toHaveCount(2);
  await page.getByRole("button", { name: /Tạo PDF hàng loạt/ }).click();
  await expect(
    page.getByRole("heading", { name: "PDF đã sẵn sàng" }),
  ).toBeVisible({ timeout: 30000 });
  const url = await page
    .getByRole("link", { name: "Tải PDF", exact: true })
    .getAttribute("href");
  const bytes = await page.evaluate(
    async (url) =>
      Array.from(new Uint8Array(await (await fetch(url)).arrayBuffer())),
    url,
  );
  const output = await PDFDocument.load(new Uint8Array(bytes));
  if (output.getPageCount() !== 4) throw Error("Expected 4 A3 pages");
  const fontResponse = await page.evaluate(async () => ({
    ok: (await fetch("/fonts/DejaVuSans.ttf")).ok,
  }));
  if (!fontResponse.ok) throw Error("Desktop font failed");
  await page.reload();
  await page.getByRole("button", { name: /Kho mẫu in/ }).click();
  await expect(page.locator(".template-card")).toHaveCount(1);
  if (errors.length) throw Error(errors.join("\n"));
  console.log(
    "PASS desktop custom protocol, PDF worker, Excel, Vietnamese font, 4-page A3 batch, IndexedDB persistence",
  );
} finally {
  await application.close();
  await rm(config, { recursive: true, force: true });
}
