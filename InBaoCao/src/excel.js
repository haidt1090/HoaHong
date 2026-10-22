import ExcelJS from "exceljs";
import { autoMap, cellText, normalize } from "./data";
export async function loadWorkbook(file) {
  const book = new ExcelJS.Workbook();
  await book.xlsx.load(await file.arrayBuffer());
  return book;
}
export function guessHeader(sheet) {
  let best = 1,
    score = -1;
  for (let i = 1; i <= Math.min(sheet.rowCount, 40); i++) {
    const values = sheet.getRow(i).values.slice(1).map(cellText);
    const map = autoMap(values);
    let s = Object.values(map).filter(Boolean).length;
    if (values.some((v) => normalize(v) === "stt")) s += 2;
    if (s > score) {
      score = s;
      best = i;
    }
  }
  return best;
}
export function readSheet(sheet, headerRow) {
  const headers = [],
    columns = [];
  const row = sheet.getRow(headerRow);
  const seen = new Set();
  row.eachCell((cell, col) => {
    const text = cellText(cell.value).trim();
    if (!text) return;
    let header = text;
    while (seen.has(header)) header += " (trùng)";
    seen.add(header);
    headers.push(header);
    columns.push([col, header]);
  });
  const rows = [];
  for (let i = headerRow + 1; i <= sheet.rowCount; i++) {
    const r = sheet.getRow(i),
      item = {};
    for (const [col, h] of columns) {
      const c = r.getCell(col);
      item[h] =
        c.value instanceof Date
          ? cellText(c.value)
          : c.text || cellText(c.value);
    }
    if (Object.values(item).some((v) => String(v).trim())) rows.push(item);
  }
  return { headers, rows };
}
