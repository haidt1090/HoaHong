import { cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const destination = path.join(root, ".desktop-package");
await rm(destination, { recursive: true, force: true });
await mkdir(destination);
for (const name of ["dist", "desktop", "word-converter.js"])
  await cp(path.join(root, name), path.join(destination, name), {
    recursive: true,
    filter: (source) => !source.endsWith(".test.js"),
  });
const metadata = JSON.parse(
  await readFile(path.join(root, "package.json"), "utf8"),
);
const packaged = Object.fromEntries(
  [
    "name",
    "version",
    "description",
    "author",
    "type",
    "main",
    "repository",
  ].map((key) => [key, metadata[key]]),
);
await writeFile(
  path.join(destination, "package.json"),
  JSON.stringify(packaged, null, 2) + "\n",
);
console.log(
  "Desktop staging prepared: built UI + desktop runtime, without development dependencies or health records.",
);
