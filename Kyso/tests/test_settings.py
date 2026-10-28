from dataclasses import asdict
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from kyso.settings import AppSettings, SettingsError, load_settings, save_settings


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "config" / "settings.json"

    def test_missing_file_has_safe_defaults(self):
        self.assertEqual(load_settings(self.path), AppSettings())

    def test_roundtrip_preserves_only_nonsecret_fields(self):
        settings = AppSettings(certificate_thumbprint="A" * 40, automatic_pin=True)
        save_settings(settings, self.path)
        self.assertEqual(load_settings(self.path), settings)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(set(data), {"debugger_address", "base_url", "certificate_thumbprint", "automatic_pin"})
        self.assertEqual(list(self.path.parent.glob(".settings-*.tmp")), [])

    def test_cannot_load_pin_or_unknown_fields(self):
        self.path.parent.mkdir()
        for key in ["pin", "password", "cookies", "unexpected"]:
            with self.subTest(key=key):
                self.path.write_text(json.dumps({key: "do-not-retain"}), encoding="utf-8")
                with self.assertRaises(SettingsError):
                    load_settings(self.path)

    def test_rejects_remote_debug_or_unexpected_web_origin(self):
        for address in ["0.0.0.0:9222", "example.com:9222", "127.0.0.1:0", "127.0.0.1:65536", 9222]:
            with self.subTest(address=address):
                with self.assertRaises(SettingsError):
                    AppSettings(debugger_address=address)
        for url in ["http://admin.csdlksk.vn", "https://admin.csdlksk.vn.evil.test", "https://admin.csdlksk.vn/path", None]:
            with self.subTest(url=url):
                with self.assertRaises(SettingsError):
                    AppSettings(base_url=url)

    def test_rejects_wrong_field_types_and_corrupt_json(self):
        with self.assertRaises(SettingsError):
            AppSettings(automatic_pin="true")
        with self.assertRaises(SettingsError):
            AppSettings(certificate_thumbprint="bad")
        self.path.parent.mkdir()
        for text in ["[]", "null", "broken", '{"automatic_pin": 1}']:
            self.path.write_text(text, encoding="utf-8")
            with self.assertRaises(SettingsError):
                load_settings(self.path)

    def test_failed_atomic_replace_preserves_old_config_and_cleans_temporary(self):
        original = AppSettings()
        save_settings(original, self.path)
        with patch("kyso.settings.os.replace", side_effect=OSError("read-only")):
            with self.assertRaises(SettingsError):
                save_settings(AppSettings(automatic_pin=True), self.path)
        self.assertEqual(load_settings(self.path), original)
        self.assertEqual(list(self.path.parent.glob(".settings-*.tmp")), [])

    def test_save_rejects_arbitrary_dict(self):
        with self.assertRaises(SettingsError):
            save_settings({"pin": "secret"}, self.path)
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
