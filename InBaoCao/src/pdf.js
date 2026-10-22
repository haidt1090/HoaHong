import { PDFDocument, rgb } from "pdf-lib";
import fontkit from "@pdf-lib/fontkit";
import * as pdfjs from "pdfjs-dist";
import worker from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { mappedValue } from "./data";
pdfjs.GlobalWorkerOptions.workerSrc = worker;
export async function importBackground(file) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  if (
    file.type === "application/pdf" ||
    file.name.toLowerCase().endsWith(".pdf")
  ) {
    const task = pdfjs.getDocument({
      data: bytes.slice(),
      isEvalSupported: false,
    });
    const doc = await task.promise;
    const pages = [];
    try {
      for (let i = 1; i <= doc.numPages; i++) {
        const page = await doc.getPage(i);
        const viewport = page.getViewport({ scale: 1.4 });
        const canvas = document.createElement("canvas");
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        await page.render({ canvasContext: canvas.getContext("2d"), viewport })
          .promise;
        pages.push({
          image: canvas.toDataURL("image/png"),
          landscape: viewport.width > viewport.height,
        });
      }
    } finally {
      await task.destroy();
    }
    const pdfData = await new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(r.result);
      r.onerror = reject;
      r.readAsDataURL(new Blob([bytes], { type: "application/pdf" }));
    });
    return { pages, pdfData };
  }
  if (!["image/png", "image/jpeg"].includes(file.type))
    throw Error("Chọn mẫu PDF, PNG hoặc JPG.");
  const image = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
  const img = new Image();
  img.src = image;
  await img.decode();
  return { pages: [{ image, landscape: img.width > img.height }] };
}
export async function makePDF(
  template,
  rows,
  mapping,
  constants,
  onProgress = () => {},
) {
  if (!template?.pages?.length) throw Error("Chưa có mẫu in.");
  const doc = await PDFDocument.create();
  doc.registerFontkit(fontkit);
  const response = await fetch("/fonts/DejaVuSans.ttf");
  if (!response.ok) throw Error("Không tải được font tiếng Việt.");
  const font = await doc.embedFont(await response.arrayBuffer(), {
    subset: true,
  });
  let vectorPages = null;
  if (template.pdfData) {
    const source = await PDFDocument.load(template.pdfData);
    for (const p of source.getPages()) {
      if (!p.node.Contents())
        p.drawRectangle({
          x: 0,
          y: 0,
          width: p.getWidth(),
          height: p.getHeight(),
          color: rgb(1, 1, 1),
        });
    }
    vectorPages = await doc.embedPages(source.getPages());
  }
  const backgrounds =
    vectorPages ||
    (await Promise.all(
      template.pages.map((p) =>
        p.image.startsWith("data:image/jpeg")
          ? doc.embedJpg(p.image)
          : doc.embedPng(p.image),
      ),
    ));
  for (let index = 0; index < rows.length; index++) {
    for (let p = 0; p < template.pages.length; p++) {
      const landscape = template.pages[p].landscape;
      const width = landscape ? 1190.55 : 841.89,
        height = landscape ? 841.89 : 1190.55;
      const page = doc.addPage([width, height]);
      if (vectorPages)
        page.drawPage(vectorPages[p], { x: 0, y: 0, width, height });
      else page.drawImage(backgrounds[p], { x: 0, y: 0, width, height });
      for (const slot of template.slots.filter((s) => s.page === p)) {
        const text = mappedValue(
          rows[index],
          mapping,
          slot.field,
          constants,
        ).replace(/[\r\n\t]/g, " ");
        const available = Math.max(15, (slot.width || 0.35) * width);
        let size = Number(slot.size) || 12;
        const textWidth = font.widthOfTextAtSize(text, size);
        if (textWidth > available)
          size = Math.max(4, (size * available) / textWidth);
        if (slot.mask !== false)
          page.drawRectangle({
            x: slot.x * width,
            y: height - slot.y * height - size * 1.25,
            width: available,
            height: size * 1.25,
            color: rgb(1, 1, 1),
          });
        if (!text) continue;
        page.drawText(text, {
          x: slot.x * width,
          y: height - slot.y * height - size,
          size,
          font,
          color: rgb(0, 0, 0),
        });
      }
    }
    onProgress(index + 1, rows.length);
    if (index % 10 === 0) await new Promise((r) => setTimeout(r, 0));
  }
  return new Blob([await doc.save()], { type: "application/pdf" });
}
