import { test, expect } from "@playwright/test";
import ExcelJS from "exceljs";
import { PDFDocument } from "pdf-lib";
async function excel() {
  const book = new ExcelJS.Workbook();
  const s = book.addWorksheet("Danh sách");
  s.addRow(["DANH SÁCH KIỂM THỬ"]);
  s.addRow([]);
  s.addRow([
    "STT",
    "HỌ VÀ TÊN (*)",
    "Giới tính",
    "Mã NV",
    "Ngày sinh",
    "Số CCCD",
    "Ngày cấp",
    "Nơi cấp",
    "Dân tộc",
    "Nơi ở hiện tại",
    "Nghề nghiệp",
    "Công ty(*)",
  ]);
  s.addRow([
    1,
    "Nguyễn Thị Ánh",
    "Nữ",
    "NV001",
    "03/02/2001",
    "001234567890",
    "01/01/2025",
    "Bộ Công an",
    "Kinh",
    "Hà Nội",
    "Kế toán",
    "Công ty thử nghiệm",
  ]);
  s.addRow([
    2,
    "Đặng Văn Bình",
    "Nam",
    "NV002",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
  ]);
  return {
    name: "kiem-thu.xlsx",
    mimeType:
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    buffer: Buffer.from(await book.xlsx.writeBuffer()),
  };
}
async function readPDF(page) {
  const href = await page
    .getByRole("link", { name: "Tải PDF", exact: true })
    .getAttribute("href");
  const bytes = await page.evaluate(
    async (url) =>
      Array.from(new Uint8Array(await (await fetch(url)).arrayBuffer())),
    href,
  );
  return PDFDocument.load(new Uint8Array(bytes));
}
test("Excel → automatic/manual mapping → selected batch A3 PDF → persistence", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page.getByRole("button", { name: /Tạo mẫu minh họa A3/ }).click();
  await expect(
    page.getByText("Đã tạo mẫu minh họa A3 có sẵn 12 vị trí dữ liệu."),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "In sổ sức khỏe", exact: true })
    .click();
  await page.locator('input[accept=".xlsx"]').setInputFiles(await excel());
  await expect(page.locator("tbody tr")).toHaveCount(2);
  await expect(page.getByLabel("Dòng tiêu đề")).toHaveValue("3");
  await page.getByRole("button", { name: "Thiết lập", exact: true }).click();
  await expect(page.locator(".mapping-grid select").nth(1)).toHaveValue(
    "HỌ VÀ TÊN (*)",
  );
  await expect(page.locator(".mapping-grid select").nth(5)).toHaveValue(
    "Số CCCD",
  );
  await page.locator(".mapping-grid select").nth(11).selectOption("");
  await page
    .locator(".mapping-grid label")
    .last()
    .locator("input")
    .fill("Cơ quan chung");
  await expect(page.locator(".editor-panel dd").last()).toHaveText(
    "Cơ quan chung",
  );
  await page
    .getByRole("checkbox", { name: "Chọn người 2", exact: true })
    .uncheck();
  await page.getByRole("button", { name: /Tạo PDF hàng loạt/ }).click();
  await expect(
    page.getByRole("heading", { name: "PDF đã sẵn sàng" }),
  ).toBeVisible();
  const pdf = await readPDF(page);
  expect(pdf.getPageCount()).toBe(1);
  expect(pdf.getPage(0).getWidth()).toBeCloseTo(841.89, 1);
  expect(pdf.getPage(0).getHeight()).toBeCloseTo(1190.55, 1);
  // Changing the source invalidates the old PDF to prevent printing a stale batch.
  await page
    .locator(".mapping-grid label")
    .last()
    .locator("input")
    .fill("Đơn vị mới");
  await expect(
    page.getByRole("heading", { name: "PDF đã sẵn sàng" }),
  ).toHaveCount(0);
  await page.reload();
  await page.getByRole("button", { name: /Kho mẫu in/ }).click();
  await expect(page.locator(".template-card")).toHaveCount(1);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});
test("multi-page PDF template, placement, all selected people and A3 landscape", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const source = await PDFDocument.create();
  source.addPage([1190.55, 841.89]);
  source.addPage([1190.55, 841.89]);
  await page.goto("/");
  await page
    .locator('input[accept=".pdf,.docx,.png,.jpg,.jpeg"]')
    .setInputFiles({
      name: "Mẫu hai trang.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from(await source.save()),
    });
  await expect(
    page.getByText(
      "Đã nhập mẫu. Chọn trường bên phải rồi bấm vào vị trí cần điền trên giấy.",
    ),
  ).toBeVisible();
  await page.locator(".paper").click({ position: { x: 100, y: 100 } });
  await expect(page.locator(".field-slot")).toHaveCount(1);
  await page.getByRole("button", { name: "Trang sau", exact: true }).click();
  await page.locator(".paper").click({ position: { x: 150, y: 150 } });
  await page
    .getByRole("button", { name: "In sổ sức khỏe", exact: true })
    .click();
  await page.locator('input[accept=".xlsx"]').setInputFiles(await excel());
  await expect(page.locator("tbody tr")).toHaveCount(2);
  await page.getByRole("button", { name: /Tạo PDF hàng loạt/ }).click();
  await expect(
    page.getByRole("heading", { name: "PDF đã sẵn sàng" }),
  ).toBeVisible();
  const pdf = await readPDF(page);
  expect(pdf.getPageCount()).toBe(4);
  expect(pdf.getPage(0).getWidth()).toBeCloseTo(1190.55, 1);
  expect(pdf.getPage(0).getHeight()).toBeCloseTo(841.89, 1);
  expect(errors).toEqual([]);
});
