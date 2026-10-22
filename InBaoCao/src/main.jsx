import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { get, set } from "idb-keyval";
import {
  Printer,
  FileSpreadsheet,
  LayoutTemplate,
  Plus,
  Upload,
  ArrowRight,
  Check,
  ChevronLeft,
  ChevronRight,
  Trash2,
  Settings2,
  Download,
  FileText,
  ShieldCheck,
  X,
  Link2,
  Search,
  RotateCcw,
} from "lucide-react";
import { fields, autoMap, mappedValue } from "./data";
import { loadWorkbook, guessHeader, readSheet } from "./excel";
import { importBackground, makePDF } from "./pdf";
import "./style.css";
const storeKey = "inbaocao-templates-v1";
function Icon({ as: Icon, ...props }) {
  return <Icon size={19} strokeWidth={1.8} {...props} />;
}
function App() {
  const [tab, setTab] = useState("print"),
    [templates, setTemplates] = useState([]),
    [loaded, setLoaded] = useState(false),
    [templateId, setTemplateId] = useState(""),
    [editing, setEditing] = useState(false),
    [page, setPage] = useState(0),
    [placeField, setPlaceField] = useState("name"),
    [activeSlot, setActiveSlot] = useState(null);
  const [book, setBook] = useState(null),
    [sheetName, setSheetName] = useState(""),
    [headerRow, setHeaderRow] = useState(1),
    [filename, setFilename] = useState(""),
    [headers, setHeaders] = useState([]),
    [rows, setRows] = useState([]),
    [mapping, setMapping] = useState({}),
    [constants, setConstants] = useState({}),
    [selected, setSelected] = useState(new Set()),
    [query, setQuery] = useState(""),
    [previewIndex, setPreviewIndex] = useState(0);
  const [busy, setBusy] = useState(""),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [showMapping, setShowMapping] = useState(false),
    [pdfUrl, setPdfUrl] = useState(""),
    [pdfName, setPdfName] = useState("");
  const excelRef = useRef(),
    templateRef = useRef(),
    pdfRef = useRef();
  const template = templates.find((t) => t.id === templateId),
    slot = template?.slots.find((s) => s.id === activeSlot),
    current = rows[previewIndex] || {};
  useEffect(() => {
    get(storeKey)
      .then((t) => {
        if (t?.length) {
          setTemplates(t);
          setTemplateId(t[0].id);
        }
      })
      .catch(() => setError("Không đọc được kho mẫu trong trình duyệt."))
      .finally(() => setLoaded(true));
  }, []);
  useEffect(() => {
    if (loaded)
      set(storeKey, templates).catch(() =>
        setError("Không lưu được mẫu: bộ nhớ trình duyệt đầy hoặc bị chặn."),
      );
  }, [templates, loaded]);
  useEffect(
    () => () => {
      if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    },
    [pdfUrl],
  );
  useEffect(() => {
    setPdfUrl("");
  }, [rows, mapping, constants, template]);
  function updateTemplate(changes) {
    setTemplates((ts) =>
      ts.map((t) => (t.id === templateId ? { ...t, ...changes } : t)),
    );
  }
  function updateSlot(changes) {
    updateTemplate({
      slots: template.slots.map((s) =>
        s.id === activeSlot ? { ...s, ...changes } : s,
      ),
    });
  }
  async function run(work) {
    setError("");
    try {
      await work();
    } catch (e) {
      setError(e.message || "Có lỗi xảy ra. Vui lòng thử lại.");
    } finally {
      setBusy("");
    }
  }
  async function importTemplate(file) {
    if (!file) return;
    await run(async () => {
      if (file.size > 25 * 1024 * 1024) throw Error("Mẫu tối đa 25 MB.");
      setBusy("Đang đọc mẫu…");
      let input = file;
      if (file.name.toLowerCase().endsWith(".docx")) {
        setBusy("Đang chuyển Word sang PDF…");
        const form = new FormData();
        form.append("file", file);
        const response = await fetch("/api/convert-docx", {
          method: "POST",
          body: form,
        });
        if (!response.ok) {
          const e = await response.json();
          throw Error(e.error);
        }
        input = new File([await response.blob()], "template.pdf", {
          type: "application/pdf",
        });
      }
      const background = await importBackground(input);
      const t = {
        id: crypto.randomUUID(),
        name: file.name.replace(/\.[^.]+$/, ""),
        ...background,
        slots: [],
        created: new Date().toISOString(),
      };
      setTemplates((ts) => [...ts, t]);
      setTemplateId(t.id);
      setPage(0);
      setEditing(true);
      setTab("templates");
      setActiveSlot(null);
      setNotice(
        "Đã nhập mẫu. Chọn trường bên phải rồi bấm vào vị trí cần điền trên giấy.",
      );
    });
  }
  async function importExcel(file) {
    if (!file) return;
    await run(async () => {
      setBusy("Đang đọc danh sách Excel…");
      const b = await loadWorkbook(file);
      if (!b.worksheets.length) throw Error("Excel không có trang tính.");
      setBook(b);
      setFilename(file.name);
      chooseSheet(b, b.worksheets[0].name);
      setNotice(
        "Đã đọc Excel và tự liên kết các cột nhận diện được. Bạn có thể chỉnh lại liên kết.",
      );
    });
  }
  function chooseSheet(b, name) {
    const sheet = b.getWorksheet(name);
    const h = guessHeader(sheet);
    setSheetName(name);
    applySheet(sheet, h);
  }
  function applySheet(sheet, h) {
    setHeaderRow(h);
    const data = readSheet(sheet, h);
    setRows(data.rows);
    setHeaders(data.headers);
    setMapping(autoMap(data.headers));
    setSelected(new Set(data.rows.map((_, i) => i)));
    setPreviewIndex(0);
    setQuery("");
  }
  async function blankTemplate() {
    await run(async () => {
      setBusy("Đang tạo mẫu…");
      const canvas = document.createElement("canvas");
      canvas.width = 1191;
      canvas.height = 1684;
      const c = canvas.getContext("2d");
      c.fillStyle = "white";
      c.fillRect(0, 0, 1191, 1684);
      c.fillStyle = "#111";
      c.textAlign = "center";
      c.font = "bold 25px Arial";
      c.fillText("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", 595, 80);
      c.font = "20px Arial";
      c.fillText("Độc lập – Tự do – Hạnh phúc", 595, 115);
      c.font = "bold 34px Arial";
      c.fillText("SỔ KHÁM SỨC KHỎE", 595, 205);
      c.font = "18px Arial";
      c.fillText("MẪU MINH HỌA · KHỔ A3", 595, 245);
      c.textAlign = "left";
      const slots = fields.map((f, i) => {
        const y = 340 + i * 76;
        c.font = "21px Arial";
        const labelWidth = c.measureText(f.label + ":").width;
        if (labelWidth > 355) c.font = `${(21 * 355) / labelWidth}px Arial`;
        c.fillText(f.label + ":", 75, y);
        c.strokeStyle = "#d9dee7";
        c.beginPath();
        c.moveTo(75, y + 36);
        c.lineTo(1115, y + 36);
        c.stroke();
        return {
          id: crypto.randomUUID(),
          field: f.id,
          page: 0,
          x: 0.38,
          y: (y - 22) / 1684,
          width: 0.53,
          size: 13,
          mask: true,
        };
      });
      c.font = "italic 17px Arial";
      c.fillStyle = "#777";
      c.fillText(
        "Mẫu minh họa, không thay thế biểu mẫu khám sức khỏe theo quy định.",
        75,
        1550,
      );
      const t = {
        id: crypto.randomUUID(),
        name: "Sổ khám sức khỏe · Mẫu minh họa",
        pages: [{ image: canvas.toDataURL("image/png"), landscape: false }],
        slots,
        created: new Date().toISOString(),
      };
      setTemplates((ts) => [...ts, t]);
      setTemplateId(t.id);
      setPage(0);
      setTab("templates");
      setEditing(true);
      setNotice("Đã tạo mẫu minh họa A3 có sẵn 12 vị trí dữ liệu.");
    });
  }
  async function exportPDF(onlyOne = false) {
    await run(async () => {
      if (!template) throw Error("Hãy chọn mẫu in.");
      if (!template.slots.length)
        throw Error(
          "Mẫu chưa có vị trí dữ liệu. Hãy vào Kho mẫu để đặt các trường.",
        );
      const chosen = onlyOne
        ? [rows[previewIndex]]
        : rows.filter((_, i) => selected.has(i));
      if (!chosen.length || !chosen[0])
        throw Error("Hãy chọn ít nhất một người khám.");
      setBusy("Đang tạo PDF…");
      const blob = await makePDF(
        template,
        chosen,
        mapping,
        constants,
        (n, total) => setBusy(`Đang tạo PDF ${n}/${total} người…`),
      );
      if (pdfUrl) URL.revokeObjectURL(pdfUrl);
      setPdfUrl(URL.createObjectURL(blob));
      setPdfName(
        `InBaoCao-${onlyOne ? "xem-thu" : chosen.length + "-nguoi"}.pdf`,
      );
      setNotice(
        `Đã tạo ${chosen.length * template.pages.length} trang A3. Mở PDF để kiểm tra trước khi in.`,
      );
    });
  }
  function position(event) {
    if (!editing || !template) return;
    const box = event.currentTarget.getBoundingClientRect();
    const x = Math.min(
        0.96,
        Math.max(0, (event.clientX - box.left) / box.width),
      ),
      y = Math.min(0.96, Math.max(0, (event.clientY - box.top) / box.height));
    const s = {
      id: crypto.randomUUID(),
      field: placeField,
      page,
      x,
      y,
      width: Math.min(0.3, 1 - x),
      size: 12,
      mask: true,
    };
    updateTemplate({ slots: [...template.slots, s] });
    setActiveSlot(s.id);
  }
  async function backup() {
    const blob = new Blob([JSON.stringify({ version: 1, templates })], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "InBaoCao-kho-mau.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function restore(file) {
    await run(async () => {
      const data = JSON.parse(await file.text());
      if (data.version !== 1 || !Array.isArray(data.templates))
        throw Error("Tệp sao lưu không hợp lệ.");
      for (const t of data.templates) {
        if (
          !t.name ||
          !Array.isArray(t.pages) ||
          !t.pages.length ||
          !Array.isArray(t.slots) ||
          t.slots.some(
            (s) =>
              !fields.some((f) => f.id === s.field) ||
              !Number.isInteger(s.page) ||
              s.page < 0 ||
              s.page >= t.pages.length ||
              ![s.x, s.y, s.width, s.size].every(Number.isFinite),
          ) ||
          t.pages.some((p) => !/^data:image\/(png|jpeg);base64,/.test(p.image))
        )
          throw Error("Mẫu sao lưu không hợp lệ.");
      }
      const imported = data.templates.map((t) => ({
        ...t,
        id: crypto.randomUUID(),
      }));
      setTemplates((ts) => [...ts, ...imported]);
      if (imported.length) setTemplateId(imported[0].id);
      setPage(0);
      setNotice(`Đã khôi phục ${imported.length} mẫu.`);
    });
  }
  const filtered = rows
    .map((r, i) => ({ r, i }))
    .filter(({ r }) =>
      Object.values(r).some((v) =>
        String(v).toLowerCase().includes(query.toLowerCase()),
      ),
    );
  const selectedCount = selected.size,
    linked = Object.values(mapping).filter(Boolean).length;
  return (
    <div className="app">
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="InBaoCao">
          <span className="brand-mark">
            <Printer size={25} />
          </span>
          <span>
            InBaoCao<small>QUẢN LÝ IN ẤN</small>
          </span>
        </a>
        <div className="workspace-label">KHÔNG GIAN LÀM VIỆC</div>
        <button
          className={"nav " + (tab === "print" ? "active" : "")}
          onClick={() => {
            setTab("print");
            setEditing(false);
          }}
        >
          <Icon as={Printer} />
          In sổ sức khỏe
        </button>
        <button
          className={"nav " + (tab === "templates" ? "active" : "")}
          onClick={() => setTab("templates")}
        >
          <Icon as={LayoutTemplate} />
          Kho mẫu in<span className="count">{templates.length}</span>
        </button>
        <div className="sidebar-bottom">
          <div className="privacy-icon">
            <ShieldCheck size={22} />
          </div>
          <strong>Dữ liệu của bạn, riêng tư</strong>
          <p>
            Excel được xử lý trên trình duyệt. Mẫu Word được chuyển đổi trên máy
            chủ và xóa sau khi xử lý.
          </p>
          <div className="user">
            <span>HH</span>
            <div>
              Hoa Hồng<small>Không gian nội bộ</small>
            </div>
            <span className="online" />
          </div>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <span>
            Không gian làm việc <ChevronRight size={14} />{" "}
            <b>{tab === "print" ? "In sổ sức khỏe" : "Kho mẫu in"}</b>
          </span>
          <span className="local-badge">
            <span />
            Lưu mẫu trên thiết bị
          </span>
        </header>
        <div className="content">
          <div className="heading">
            <div>
              <div className="eyebrow">
                INBAOCAO /{" "}
                {tab === "print" ? "IN HÀNG LOẠT" : "QUẢN LÝ BIỂU MẪU"}
              </div>
              <h1>{tab === "print" ? "In sổ khám sức khỏe" : "Kho mẫu in"}</h1>
              <p>
                {tab === "print"
                  ? "Từ danh sách Excel đến sổ khám hoàn chỉnh, chỉ trong vài bước."
                  : "Lưu mẫu của bạn, đặt vị trí dữ liệu và sử dụng cho nhiều đợt khám."}
              </p>
            </div>
            <button
              className="button secondary"
              onClick={() => templateRef.current.click()}
            >
              <Plus size={18} />
              Thêm mẫu mới
            </button>
          </div>
          <input
            ref={excelRef}
            type="file"
            hidden
            accept=".xlsx"
            onChange={(e) => {
              importExcel(e.target.files[0]);
              e.target.value = "";
            }}
          />
          <input
            ref={templateRef}
            type="file"
            hidden
            accept=".pdf,.docx,.png,.jpg,.jpeg"
            onChange={(e) => {
              importTemplate(e.target.files[0]);
              e.target.value = "";
            }}
          />
          {error && (
            <div className="alert error" role="alert">
              {error}
              <button onClick={() => setError("")} aria-label="Đóng lỗi">
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div className="alert notice" role="status">
              <Check size={17} />
              {notice}
              <button onClick={() => setNotice("")} aria-label="Đóng thông báo">
                <X size={16} />
              </button>
            </div>
          )}
          {busy && (
            <div className="alert" role="status">
              <span className="spinner" />
              {busy}
            </div>
          )}
          {tab === "print" ? (
            <>
              <div className="steps">
                {[
                  [
                    "01",
                    "Nhập danh sách",
                    "Chọn tệp Excel của bạn",
                    !!rows.length,
                  ],
                  [
                    "02",
                    "Chọn mẫu & liên kết",
                    "Tự động ghép dữ liệu",
                    !!template,
                  ],
                  ["03", "Kiểm tra & in", "Xuất PDF khổ A3", !!pdfUrl],
                ].map(([n, title, desc, done]) => (
                  <div className={"step " + (done ? "done" : "")} key={n}>
                    <span className="step-no">
                      {done ? <Check size={18} /> : n}
                    </span>
                    <div>
                      <strong>{title}</strong>
                      <small>{desc}</small>
                    </div>
                  </div>
                ))}
              </div>
              <div className="setup-grid">
                <section className="card">
                  <div className="card-title">
                    <span className="icon-tile green">
                      <FileSpreadsheet size={21} />
                    </span>
                    <div>
                      <h2>1. Danh sách người khám</h2>
                      <p>Nhập dữ liệu từ tệp Excel</p>
                    </div>
                    {rows.length > 0 && (
                      <span className="pill">{rows.length} người</span>
                    )}
                  </div>
                  <button
                    className={"dropzone " + (filename ? "uploaded" : "")}
                    onClick={() => excelRef.current.click()}
                    disabled={!!busy || !loaded}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      if (!busy && loaded) importExcel(e.dataTransfer.files[0]);
                    }}
                  >
                    <span className="upload-icon">
                      <Upload size={24} />
                    </span>
                    <strong>
                      {filename || "Chọn hoặc kéo thả tệp Excel vào đây"}
                    </strong>
                    <span>
                      {filename
                        ? "Bấm để thay đổi danh sách"
                        : "Hỗ trợ .xlsx · Không giới hạn cột thông tin"}
                    </span>
                    <span className="file-chip">
                      {filename ? "Đã nhập thành công" : "Chọn tệp Excel"}{" "}
                      <ArrowRight size={14} />
                    </span>
                  </button>
                  {book && (
                    <div className="sheet-controls">
                      <label>
                        Trang tính
                        <select
                          value={sheetName}
                          onChange={(e) => chooseSheet(book, e.target.value)}
                        >
                          {book.worksheets.map((s) => (
                            <option key={s.name}>{s.name}</option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Dòng tiêu đề
                        <input
                          type="number"
                          min="1"
                          max={book.getWorksheet(sheetName).rowCount || 1}
                          value={headerRow}
                          onChange={(e) => {
                            const n = Number(e.target.value);
                            if (
                              n >= 1 &&
                              n <= book.getWorksheet(sheetName).rowCount
                            )
                              applySheet(book.getWorksheet(sheetName), n);
                          }}
                        />
                      </label>
                    </div>
                  )}
                </section>
                <section className="card">
                  <div className="card-title">
                    <span className="icon-tile purple">
                      <LayoutTemplate size={21} />
                    </span>
                    <div>
                      <h2>2. Mẫu sổ khám sức khỏe</h2>
                      <p>Chọn mẫu áp dụng cho danh sách</p>
                    </div>
                    <span className="pill neutral">A3</span>
                  </div>
                  <label className="label">
                    Mẫu in
                    <select
                      className="template-select"
                      value={templateId}
                      onChange={(e) => {
                        setTemplateId(e.target.value);
                        setPage(0);
                      }}
                    >
                      <option value="">Chọn mẫu từ kho mẫu của bạn</option>
                      {templates.map((t) => (
                        <option value={t.id} key={t.id}>
                          {t.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  {template ? (
                    <div className="template-summary">
                      <div className="mini-page">
                        <FileText size={28} />
                      </div>
                      <div>
                        <strong>{template.name}</strong>
                        <p>
                          {template.pages.length} trang ·{" "}
                          {template.slots.length} vị trí dữ liệu
                        </p>
                        <button
                          className="text-button"
                          onClick={() => {
                            setTab("templates");
                            setEditing(true);
                          }}
                        >
                          Chỉnh vị trí trên mẫu <ArrowRight size={14} />
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="template-empty">
                      <FileText size={34} />
                      <p>
                        Chưa chọn mẫu? Nhập mẫu riêng hoặc
                        <br />
                        thử mẫu minh họa có sẵn.
                      </p>
                      <button
                        className="text-button"
                        onClick={blankTemplate}
                        disabled={!!busy}
                      >
                        Tạo mẫu minh họa A3 <ArrowRight size={14} />
                      </button>
                    </div>
                  )}
                  <div className="mapping-bar">
                    <span>
                      <Link2 size={17} />
                      {rows.length
                        ? `${linked}/${fields.length} trường đã liên kết`
                        : "Liên kết dữ liệu linh hoạt"}
                    </span>
                    <button
                      className="text-button"
                      onClick={() => setShowMapping(!showMapping)}
                    >
                      <Settings2 size={15} />
                      {showMapping ? "Thu gọn" : "Thiết lập"}
                    </button>
                  </div>
                </section>
              </div>
              {showMapping && (
                <section className="card mapping-panel">
                  <div className="section-title">
                    <div>
                      <h2>Liên kết cột Excel với trường trên mẫu</h2>
                      <p>
                        Không phân biệt hoa thường, dấu tiếng Việt hoặc dấu (*).
                        Trường không có dữ liệu sẽ để trống.
                      </p>
                    </div>
                    <button
                      className="button secondary"
                      onClick={() => setMapping(autoMap(headers))}
                    >
                      <RotateCcw size={15} />
                      Tự liên kết lại
                    </button>
                  </div>
                  <div className="mapping-grid">
                    {fields.map((f) => (
                      <label key={f.id}>
                        {f.label}
                        <select
                          value={mapping[f.id] || ""}
                          onChange={(e) =>
                            setMapping({ ...mapping, [f.id]: e.target.value })
                          }
                        >
                          <option value="">
                            Để trống / dùng giá trị chung
                          </option>
                          {headers.map((h) => (
                            <option key={h} value={h}>
                              {h}
                            </option>
                          ))}
                        </select>
                        {!mapping[f.id] && (
                          <input
                            placeholder="Giá trị chung (không bắt buộc)"
                            value={constants[f.id] || ""}
                            onChange={(e) =>
                              setConstants({
                                ...constants,
                                [f.id]: e.target.value,
                              })
                            }
                          />
                        )}
                      </label>
                    ))}
                  </div>
                </section>
              )}
              <section className="card table-card">
                <div className="section-title">
                  <div>
                    <h2>
                      Danh sách in{" "}
                      <span className="heading-count">{rows.length}</span>
                    </h2>
                    <p>
                      {rows.length
                        ? `Đã chọn ${selectedCount} người · Bấm vào tên để xem dữ liệu trên mẫu`
                        : "Dữ liệu người khám sẽ xuất hiện tại đây sau khi nhập Excel"}
                    </p>
                  </div>
                  <div className="search">
                    <Search size={17} />
                    <input
                      placeholder="Tìm trong danh sách…"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  </div>
                </div>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>
                          <input
                            aria-label="Chọn tất cả kết quả"
                            type="checkbox"
                            checked={
                              !!filtered.length &&
                              filtered.every(({ i }) => selected.has(i))
                            }
                            onChange={(e) => {
                              const next = new Set(selected);
                              filtered.forEach(({ i }) =>
                                e.target.checked ? next.add(i) : next.delete(i),
                              );
                              setSelected(next);
                            }}
                          />
                        </th>
                        <th>STT</th>
                        <th>HỌ VÀ TÊN</th>
                        <th>GIỚI TÍNH</th>
                        <th>NGÀY SINH</th>
                        <th>MÃ NHÂN VIÊN</th>
                        <th>SỐ CCCD</th>
                        <th>TRẠNG THÁI</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.slice(0, 300).map(({ r, i }) => (
                        <tr
                          key={i}
                          className={previewIndex === i ? "current" : ""}
                        >
                          <td>
                            <input
                              aria-label={`Chọn người ${i + 1}`}
                              type="checkbox"
                              checked={selected.has(i)}
                              onChange={(e) => {
                                const next = new Set(selected);
                                e.target.checked ? next.add(i) : next.delete(i);
                                setSelected(next);
                              }}
                            />
                          </td>
                          <td>{mappedValue(r, mapping, "number") || i + 1}</td>
                          <td>
                            <button
                              className="name-button"
                              onClick={() => {
                                setPreviewIndex(i);
                                document
                                  .getElementById("preview")
                                  ?.scrollIntoView({ behavior: "smooth" });
                              }}
                            >
                              {mappedValue(r, mapping, "name") ||
                                "(Chưa liên kết họ tên)"}
                            </button>
                          </td>
                          <td>{mappedValue(r, mapping, "gender")}</td>
                          <td>{mappedValue(r, mapping, "birth")}</td>
                          <td>{mappedValue(r, mapping, "employee")}</td>
                          <td>{mappedValue(r, mapping, "identity")}</td>
                          <td>
                            <span className="status-dot" />
                            {selected.has(i) ? "Đã chọn" : "Bỏ qua"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {!rows.length && (
                  <div className="empty-table">
                    <span>
                      <FileSpreadsheet size={28} />
                    </span>
                    <h3>Danh sách đang chờ bạn</h3>
                    <p>Thêm tệp Excel để bắt đầu chuẩn bị sổ khám sức khỏe.</p>
                    <button
                      className="text-button"
                      onClick={() => excelRef.current.click()}
                    >
                      Nhập danh sách đầu tiên <ArrowRight size={14} />
                    </button>
                  </div>
                )}
                {rows.length > 0 && (
                  <div className="table-footer">
                    Hiển thị {Math.min(filtered.length, 300)}/{filtered.length}{" "}
                    kết quả · Tất cả {selectedCount} người đã chọn sẽ được xuất,
                    kể cả ngoài bảng.
                  </div>
                )}
              </section>
              <div className="print-footer">
                <div>
                  <span className="icon-tile green">
                    <Printer size={21} />
                  </span>
                  <div>
                    <strong>
                      {selectedCount
                        ? `${selectedCount} sổ khám sẵn sàng chuẩn bị`
                        : "Sẵn sàng cho đợt khám tiếp theo"}
                    </strong>
                    <p>PDF khổ A3 · Kiểm tra trước khi gửi máy in</p>
                  </div>
                </div>
                <div className="actions">
                  <button
                    className="button secondary"
                    disabled={!!busy || !rows.length || !template}
                    onClick={() => exportPDF(true)}
                  >
                    Xuất thử 1 người
                  </button>
                  <button
                    className="button primary"
                    disabled={!!busy || !selectedCount || !template}
                    onClick={() => exportPDF()}
                  >
                    <Printer size={18} />
                    Tạo PDF hàng loạt <ArrowRight size={17} />
                  </button>
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="template-tools">
                <button
                  className="button secondary"
                  onClick={blankTemplate}
                  disabled={!!busy}
                >
                  <Plus size={16} />
                  Mẫu minh họa A3
                </button>
                <button
                  className="button secondary"
                  onClick={backup}
                  disabled={!templates.length}
                >
                  <Download size={16} />
                  Sao lưu kho mẫu
                </button>
                <label className="button secondary">
                  <Upload size={16} />
                  Khôi phục mẫu
                  <input
                    hidden
                    type="file"
                    accept=".json"
                    onChange={(e) => {
                      if (e.target.files[0]) restore(e.target.files[0]);
                      e.target.value = "";
                    }}
                  />
                </label>
              </div>
              <div className="template-cards">
                {templates.map((t) => (
                  <button
                    key={t.id}
                    className={
                      "template-card " + (templateId === t.id ? "chosen" : "")
                    }
                    onClick={() => {
                      setTemplateId(t.id);
                      setPage(0);
                      setEditing(true);
                      setActiveSlot(null);
                    }}
                  >
                    <div
                      className="thumbnail"
                      style={{ backgroundImage: `url("${t.pages[0].image}")` }}
                    />
                    <div>
                      <strong>{t.name}</strong>
                      <p>
                        A3 · {t.pages.length} trang · {t.slots.length} vị trí
                      </p>
                    </div>
                    <span className="radio">
                      {templateId === t.id && <Check size={14} />}
                    </span>
                  </button>
                ))}
              </div>
              {!templates.length && (
                <div className="card big-empty">
                  <LayoutTemplate size={40} />
                  <h2>Kho mẫu đầu tiên của bạn</h2>
                  <p>
                    Nhập Word, PDF hoặc ảnh, đặt tên và bố trí các trường dữ
                    liệu.
                  </p>
                  <button
                    className="button primary"
                    onClick={() => templateRef.current.click()}
                  >
                    <Plus size={18} />
                    Nhập mẫu
                  </button>
                </div>
              )}
              {template && (
                <section className="card">
                  <div className="section-title">
                    <label className="label">
                      Tên mẫu
                      <input
                        value={template.name}
                        onChange={(e) =>
                          updateTemplate({ name: e.target.value })
                        }
                      />
                    </label>
                    <button
                      className="button danger"
                      onClick={() => {
                        if (window.confirm(`Xóa mẫu “${template.name}”?`)) {
                          setTemplates((ts) =>
                            ts.filter((t) => t.id !== templateId),
                          );
                          setTemplateId("");
                        }
                      }}
                    >
                      <Trash2 size={16} />
                      Xóa mẫu
                    </button>
                  </div>
                  <p className="hint">
                    Chọn trường rồi bấm lên giấy để đặt vị trí. Một trường có
                    thể đặt nhiều lần. Bấm nhãn đã đặt để chỉnh hoặc xóa. Mẫu
                    lưu trong trình duyệt này; hãy sao lưu để dùng ở máy khác.
                  </p>
                  <div className="alert notice">
                    Mẫu có sẵn dữ liệu người khác: che hoặc xóa toàn bộ dữ liệu
                    cũ, mã vạch và chữ ký trước khi dùng. Ô dữ liệu có tùy chọn
                    nền trắng để che nội dung ngay bên dưới.
                  </div>
                </section>
              )}
            </>
          )}
          {template && (
            <section className="card preview-section" id="preview">
              <div className="section-title">
                <div>
                  <h2>
                    {tab === "templates"
                      ? "Thiết kế vị trí dữ liệu"
                      : "Xem trước trên mẫu"}
                  </h2>
                  <p>
                    {tab === "templates"
                      ? "Bản in A3 · Vị trí được giữ lại cho các lần in sau"
                      : "Chọn một người trong danh sách để kiểm tra dữ liệu"}
                  </p>
                </div>
                <div className="pager">
                  <button
                    aria-label="Trang trước"
                    disabled={!page}
                    onClick={() => setPage(page - 1)}
                  >
                    <ChevronLeft size={17} />
                  </button>
                  Trang {page + 1}/{template.pages.length}
                  <button
                    aria-label="Trang sau"
                    disabled={page === template.pages.length - 1}
                    onClick={() => setPage(page + 1)}
                  >
                    <ChevronRight size={17} />
                  </button>
                </div>
              </div>
              <div className="editor-layout">
                <div className="paper-area">
                  <div
                    className={"paper " + (editing ? "editable" : "")}
                    onClick={position}
                  >
                    <img
                      src={template.pages[page].image}
                      alt={`Mẫu trang ${page + 1}`}
                      draggable="false"
                    />
                    {template.slots
                      .filter((s) => s.page === page)
                      .map((s) => (
                        <button
                          key={s.id}
                          className={
                            "field-slot " +
                            (activeSlot === s.id && editing ? "selected" : "") +
                            " " +
                            (editing ? "editing" : "")
                          }
                          style={{
                            left: s.x * 100 + "%",
                            top: s.y * 100 + "%",
                            width: (s.width || 0.35) * 100 + "%",
                            fontSize: `${((Number(s.size) || 12) / (template.pages[page].landscape ? 1190.55 : 841.89)) * 100}cqw`,
                            background: s.mask ? "white" : "transparent",
                          }}
                          onClick={(e) => {
                            e.stopPropagation();
                            if (editing) setActiveSlot(s.id);
                          }}
                          title={fields.find((f) => f.id === s.field)?.label}
                        >
                          {mappedValue(current, mapping, s.field, constants) ||
                            (editing
                              ? `{${fields.find((f) => f.id === s.field)?.label}}`
                              : "")}
                        </button>
                      ))}
                  </div>
                </div>
                <aside className="editor-panel">
                  {tab === "templates" ? (
                    <>
                      <h3>
                        <Settings2 size={17} />
                        Đặt trường lên mẫu
                      </h3>
                      <label>
                        Trường cần thêm
                        <select
                          value={placeField}
                          onChange={(e) => setPlaceField(e.target.value)}
                        >
                          {fields.map((f) => (
                            <option value={f.id} key={f.id}>
                              {f.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <p className="hint">
                        Bấm trên trang bên trái để đặt trường đã chọn.
                      </p>
                      <label>
                        Chiều giấy
                        <select
                          value={
                            template.pages[page].landscape
                              ? "landscape"
                              : "portrait"
                          }
                          onChange={(e) =>
                            updateTemplate({
                              pages: template.pages.map((p, i) =>
                                i === page
                                  ? {
                                      ...p,
                                      landscape: e.target.value === "landscape",
                                    }
                                  : p,
                              ),
                            })
                          }
                        >
                          <option value="portrait">
                            A3 dọc (297 × 420 mm)
                          </option>
                          <option value="landscape">
                            A3 ngang (420 × 297 mm)
                          </option>
                        </select>
                      </label>
                      {slot && (
                        <div className="slot-settings">
                          <h3>Vị trí đang chọn</h3>
                          <label>
                            Trường
                            <select
                              value={slot.field}
                              onChange={(e) =>
                                updateSlot({ field: e.target.value })
                              }
                            >
                              {fields.map((f) => (
                                <option key={f.id} value={f.id}>
                                  {f.label}
                                </option>
                              ))}
                            </select>
                          </label>
                          <div className="two-col">
                            {[
                              ["x", "Trái (%)"],
                              ["y", "Trên (%)"],
                              ["width", "Rộng (%)"],
                            ].map(([key, title]) => (
                              <label key={key}>
                                {title}
                                <input
                                  type="number"
                                  min="0"
                                  max="100"
                                  step="0.1"
                                  value={Math.round(slot[key] * 1000) / 10}
                                  onChange={(e) =>
                                    updateSlot({
                                      [key]: Math.max(
                                        0,
                                        Math.min(
                                          1,
                                          Number(e.target.value) / 100,
                                        ),
                                      ),
                                    })
                                  }
                                />
                              </label>
                            ))}
                            <label>
                              Cỡ chữ (pt)
                              <input
                                type="number"
                                min="4"
                                max="50"
                                value={slot.size}
                                onChange={(e) =>
                                  updateSlot({
                                    size: Math.max(
                                      4,
                                      Math.min(50, Number(e.target.value)),
                                    ),
                                  })
                                }
                              />
                            </label>
                          </div>
                          <label className="check-label">
                            <input
                              type="checkbox"
                              checked={slot.mask !== false}
                              onChange={(e) =>
                                updateSlot({ mask: e.target.checked })
                              }
                            />
                            Nền trắng (chỉ che trực quan)
                          </label>
                          <button
                            className="button danger"
                            onClick={() => {
                              updateTemplate({
                                slots: template.slots.filter(
                                  (s) => s.id !== activeSlot,
                                ),
                              });
                              setActiveSlot(null);
                            }}
                          >
                            <Trash2 size={15} />
                            Xóa vị trí này
                          </button>
                        </div>
                      )}
                    </>
                  ) : (
                    <>
                      <h3>
                        <FileText size={17} />
                        Dữ liệu đang xem
                      </h3>
                      {rows.length > 0 && (
                        <select
                          aria-label="Người xem trước"
                          value={previewIndex}
                          onChange={(e) =>
                            setPreviewIndex(Number(e.target.value))
                          }
                        >
                          {rows.map((r, i) => (
                            <option value={i} key={i}>
                              {i + 1}.{" "}
                              {mappedValue(r, mapping, "name") || "Chưa có tên"}
                            </option>
                          ))}
                        </select>
                      )}
                      <dl>
                        {fields.map((f) => (
                          <div key={f.id}>
                            <dt>{f.label}</dt>
                            <dd>
                              {mappedValue(current, mapping, f.id, constants) ||
                                "—"}
                            </dd>
                          </div>
                        ))}
                      </dl>
                      <button
                        className="text-button"
                        onClick={() => {
                          setShowMapping(true);
                          window.scrollTo({ top: 300, behavior: "smooth" });
                        }}
                      >
                        Chỉnh liên kết dữ liệu <ArrowRight size={14} />
                      </button>
                    </>
                  )}
                </aside>
              </div>
            </section>
          )}
          {pdfUrl && (
            <section className="card pdf-result">
              <div className="section-title">
                <div>
                  <h2>
                    <Check size={19} />
                    PDF đã sẵn sàng
                  </h2>
                  <p>
                    Chọn giấy A3, tỷ lệ 100% / kích thước thực. Với mẫu nhiều
                    trang, chọn in hai mặt theo máy in.
                  </p>
                </div>
                <a className="button primary" href={pdfUrl} download={pdfName}>
                  <Download size={17} />
                  Tải PDF
                </a>
              </div>
              <div className="actions">
                <a
                  className="button secondary"
                  href={pdfUrl}
                  target="_blank"
                  rel="noreferrer"
                >
                  Mở PDF để in
                </a>
                <button
                  className="button secondary"
                  onClick={() => {
                    try {
                      pdfRef.current.contentWindow.focus();
                      pdfRef.current.contentWindow.print();
                    } catch {
                      setNotice(
                        "Hãy mở PDF ở thẻ mới và dùng lệnh In của trình duyệt.",
                      );
                    }
                  }}
                >
                  <Printer size={17} />
                  In PDF
                </button>
              </div>
              <iframe ref={pdfRef} title="PDF sổ khám sức khỏe" src={pdfUrl} />
            </section>
          )}
          <footer className="bottom-note">
            <ShieldCheck size={15} /> Không lưu danh sách người khám lên máy chủ
            · InBaoCao v1.0
          </footer>
        </div>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")).render(<App />);
