"""Local Word template library and portable backup, never store Excel patient lists."""

from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import json
import os
import shutil
import uuid
from .core import scan_tokens


def default_data_dir():
    base = (
        os.environ.get("APPDATA")
        or os.environ.get("XDG_DATA_HOME")
        or str(Path.home() / ".local/share")
    )
    return Path(base) / "InBaoCaoPython"


class Library:
    def __init__(self, root=None):
        self.root = Path(root) if root else default_data_dir()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "templates").mkdir(exist_ok=True)
        self.path = self.root / "library.json"
        if self.path.exists():
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if payload.get("format") != "inbaocao-word-v2":
                raise ValueError("Kho mẫu không đúng định dạng InBaoCao Python.")
            self.templates = payload["templates"]
        else:
            self.templates = []

    def save(self):
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {"format": "inbaocao-word-v2", "templates": self.templates},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        os.replace(temporary, self.path)

    def file(self, template):
        identifier = template["id"]
        uuid.UUID(identifier)
        return self.root / "templates" / f"{identifier}.docx"

    def add(self, filename, name=None):
        filename = Path(filename)
        if filename.suffix.lower() != ".docx":
            raise ValueError(
                "Hãy chọn mẫu Word .docx. File .doc cần lưu lại thành .docx."
            )
        if filename.stat().st_size > 25 * 1024 * 1024:
            raise ValueError("Mẫu Word tối đa 25 MB.")
        tokens = scan_tokens(filename)
        if not tokens:
            raise ValueError(
                "Mẫu chưa có keyword. Trong Word, chèn $hovaten, $gt, $ngaysinh… rồi lưu và nhập lại."
            )
        item = {
            "id": str(uuid.uuid4()),
            "name": (name or filename.stem).strip(),
            "tokens": tokens,
            "mapping": {},
            "constants": {},
        }
        shutil.copy2(filename, self.file(item))
        self.templates.append(item)
        self.save()
        return item

    def delete(self, item):
        self.templates = [t for t in self.templates if t["id"] != item["id"]]
        self.save()
        self.file(item).unlink(missing_ok=True)

    def backup(self, filename):
        with ZipFile(filename, "w", ZIP_DEFLATED) as archive:
            archive.writestr(
                "library.json",
                json.dumps(
                    {"format": "inbaocao-word-v2", "templates": self.templates},
                    ensure_ascii=False,
                ),
            )
            for item in self.templates:
                archive.write(self.file(item), f"templates/{item['id']}.docx")

    def restore(self, filename):
        """Read exact named members; never extract untrusted archive paths."""
        with ZipFile(filename) as archive:
            if sum(i.file_size for i in archive.infolist()) > 100 * 1024 * 1024:
                raise ValueError("Bản sao lưu giải nén vượt quá 100 MB.")
            data = json.loads(archive.read("library.json"))
            if data.get("format") != "inbaocao-word-v2" or not isinstance(
                data.get("templates"), list
            ):
                raise ValueError("Chỉ khôi phục ZIP kho mẫu Word của InBaoCao Python.")
            incoming = []
            for item in data["templates"]:
                old_id = str(uuid.UUID(item["id"]))
                contents = archive.read(f"templates/{old_id}.docx")
                if len(contents) > 25 * 1024 * 1024:
                    raise ValueError("Mẫu sao lưu vượt quá 25 MB.")
                if not isinstance(item.get("name"), str) or not item["name"].strip():
                    raise ValueError("Tên mẫu sao lưu không hợp lệ.")
                item = {**item, "id": str(uuid.uuid4())}
                for key in ["mapping", "constants"]:
                    if not isinstance(item.get(key, {}), dict) or any(
                        not isinstance(k, str) or not isinstance(v, str)
                        for k, v in item.get(key, {}).items()
                    ):
                        raise ValueError("Liên kết dữ liệu trong sao lưu không hợp lệ.")
                incoming.append((item, contents))
            written = []
            try:
                for item, contents in incoming:
                    self.file(item).write_bytes(contents)
                    written.append(self.file(item))
                    item["tokens"] = scan_tokens(self.file(item))
                previous = list(self.templates)
                self.templates.extend(item for item, _ in incoming)
                try:
                    self.save()
                except Exception:
                    self.templates = previous
                    raise
            except Exception:
                for p in written:
                    p.unlink(missing_ok=True)
                raise
            return len(incoming)
