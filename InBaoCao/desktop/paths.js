import path from "node:path";
// Never let an app URL read arbitrary files on the machine.
export function resolveAsset(root, pathname) {
  let decoded;
  try {
    decoded = decodeURIComponent(pathname);
  } catch {
    return null;
  }
  if (decoded.includes("\0") || decoded.includes("\\")) return null;
  const target = path.resolve(
    root,
    "." + (decoded === "/" ? "/index.html" : decoded),
  );
  return target.startsWith(path.resolve(root) + path.sep) ? target : null;
}
