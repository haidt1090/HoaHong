export const fields = [
  ["number", "Số", ["STT", "Số"]],
  ["name", "Họ và tên", ["Họ tên", "HỌ VÀ TÊN"]],
  ["gender", "Giới tính", ["Giới tính"]],
  ["employee", "Mã nhân viên", ["Mã NV", "Mã nhân viên"]],
  ["birth", "Sinh Ngày", ["NGÀY SINH", "Sinh ngày"]],
  [
    "identity",
    "Số CMND/CCCD /Hộ chiếu/định danh CD",
    ["CCCD", "Số CCCD", "CMND", "Hộ chiếu", "định danh CD"],
  ],
  ["issued", "Cấp ngày", ["Ngày cấp CCCD", "Ngày cấp", "Cấp ngày"]],
  ["issuer", "Tại", ["Nơi cấp CCCD", "Nơi cấp"]],
  ["ethnicity", "Dân tộc", ["Dân tộc"]],
  ["address", "Nơi ở hiện tại", ["Nơi ở hiện tại"]],
  ["job", "Nghề nghiệp", ["Nghề nghiệp"]],
  [
    "workplace",
    "Nơi công tác, học tập",
    [
      "Nơi công tác, học tập",
      "Nơi công tác",
      "Công ty",
      "Đơn vị",
      "Nơi làm việc",
    ],
  ],
].map(([id, label, aliases]) => ({ id, label, aliases }));
export const normalize = (value) =>
  String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[đĐ]/g, "d")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
export function autoMap(headers) {
  return Object.fromEntries(
    fields.map((f) => [
      f.id,
      headers.find((h) =>
        [f.label, ...f.aliases].some((a) => normalize(a) === normalize(h)),
      ) || "",
    ]),
  );
}
export function cellText(value) {
  if (value == null) return "";
  if (value instanceof Date)
    return `${String(value.getUTCDate()).padStart(2, "0")}/${String(value.getUTCMonth() + 1).padStart(2, "0")}/${value.getUTCFullYear()}`;
  if (typeof value === "object") {
    if ("result" in value) return cellText(value.result);
    if (value.richText) return value.richText.map((t) => t.text).join("");
    if ("text" in value) return value.text;
    return "";
  }
  return String(value);
}
export function mappedValue(row, mapping, id, constants = {}) {
  return mapping[id] ? cellText(row[mapping[id]]) : constants[id] || "";
}
