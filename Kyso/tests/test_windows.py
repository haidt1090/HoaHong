import io
import json
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from kyso import windows


CERT = windows.Certificate("A" * 40, "CN=Nguyen Van A, O=Clinic", "Nguyen Van A | 2030-01-01")


class Control:
    def __init__(self, name="", kind="Text", children=None, masked=False):
        self.name = name
        self.kind = kind
        self.children = children or []
        self.visible = True
        self.element_info = SimpleNamespace(element=SimpleNamespace(CurrentIsPassword=masked))
        self.entered = []
        self.invocations = 0
        self.selections = 0
        self.on_invoke = None

    def window_text(self):
        return self.name

    def descendants(self, control_type=None):
        return [child for child in self.children if child.kind == control_type]

    def is_visible(self):
        return self.visible

    def is_enabled(self):
        return True

    def set_edit_text(self, text):
        self.entered.append(text)

    def invoke(self):
        self.invocations += 1
        if self.on_invoke:
            self.on_invoke()

    def select(self):
        self.selections += 1


class Clock:
    def __init__(self):
        self.now = 0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class WindowsTests(unittest.TestCase):
    def test_certificate_json_singleton_and_duplicate_store_entries(self):
        row = {"thumbprint": "a" * 40, "subject": CERT.subject, "label": CERT.label}
        one = windows._parse_certificates("\ufeff" + json.dumps(row))
        both = windows._parse_certificates(json.dumps([row, row]))
        self.assertEqual(one, [CERT])
        self.assertEqual(both, one)
        self.assertEqual(windows._parse_certificates(""), [])

    def test_invalid_certificate_metadata_is_rejected(self):
        for raw in ('null', '123', '[{"thumbprint":"oops","subject":"x"}]'):
            with self.subTest(raw=raw), self.assertRaises(windows.TokenError):
                windows._parse_certificates(raw)

    def test_certificate_listing_uses_constant_script_and_does_not_export_private_keys(self):
        result = SimpleNamespace(returncode=0, stdout=b'[]')
        with patch.object(windows, "_require_windows"), patch.object(windows.subprocess, "run", return_value=result) as run:
            self.assertEqual(windows.list_certificates(), [])
        command = run.call_args.args[0]
        self.assertEqual(command[0], "powershell.exe")
        self.assertIn("-NonInteractive", command)
        self.assertIn("HasPrivateKey", command[-1])
        self.assertIn("ConvertTo-Json", command[-1])
        self.assertNotIn("Export-", command[-1])

    def test_chrome_starts_with_dedicated_profile_and_loopback(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_chrome = Path(directory) / "Google/Chrome/Application/chrome.exe"
            fake_chrome.parent.mkdir(parents=True)
            fake_chrome.write_bytes(b"")
            with patch.object(windows, "_require_windows"), \
                 patch.dict(os.environ, {"LOCALAPPDATA": directory}, clear=True), \
                 patch.object(windows, "_debugger_state", side_effect=["free", "chrome"]), \
                 patch.object(windows.subprocess, "Popen") as popen:
                windows.launch_chrome()
            args = popen.call_args.args[0]
            self.assertIn("--remote-debugging-address=127.0.0.1", args)
            self.assertIn("--remote-debugging-port=9222", args)
            self.assertIn(f"--user-data-dir={Path(directory) / 'KySoPython/ChromeProfile'}", args)
            self.assertEqual(args[-1], "https://admin.csdlksk.vn")

    def test_chrome_reuses_valid_endpoint_without_starting_process(self):
        with patch.object(windows, "_require_windows"), \
             patch.object(windows, "_debugger_state", return_value="chrome"), \
             patch.object(windows.subprocess, "Popen") as popen:
            windows.launch_chrome()
        popen.assert_not_called()

    def test_chrome_never_starts_on_occupied_non_chrome_port(self):
        with patch.object(windows, "_require_windows"), \
             patch.object(windows, "_debugger_state", return_value="occupied"), \
             patch.object(windows.subprocess, "Popen") as popen:
            with self.assertRaises(windows.TokenError):
                windows.launch_chrome()
        popen.assert_not_called()

    def test_debugger_metadata_rejects_remote_websocket(self):
        for host, expected in (("127.0.0.1", "chrome"), ("example.com", "occupied")):
            payload = json.dumps({"Browser": "Chrome/130", "webSocketDebuggerUrl": f"ws://{host}:9222/devtools/browser/abc"}).encode()
            opener = Mock()
            opener.open.return_value = io.BytesIO(payload)
            with patch.object(windows.socket, "create_connection"), \
                 patch.object(windows, "build_opener", return_value=opener):
                self.assertEqual(windows._debugger_state(9222), expected)

    def test_unrelated_window_titles_are_not_accepted(self):
        for title in ("My Windows Security settings", "Token Manager", "Chrome", "PIN", "Sign in"):
            self.assertIsNone(windows._dialog_kind(title))
        self.assertEqual(windows._dialog_kind("  WINDOWS SECURITY "), "security")
        self.assertEqual(windows._dialog_kind("Kiểm tra mã PIN"), "pin")

    def test_certificate_choice_rejects_duplicate_subjects(self):
        dialog = Control(children=[Control("Nguyen Van A", "ListItem"), Control("Nguyen Van A", "ListItem")])
        with self.assertRaises(windows.TokenError):
            windows._certificate_choice(dialog, CERT)
        item = Control("Nguyen Van A", "ListItem")
        self.assertIs(windows._certificate_choice(Control(children=[item]), CERT), item)
        self.assertIsNone(windows._certificate_choice(Control(children=[Control("Other", "ListItem")]), CERT))

    def test_pin_submitted_once_and_secret_not_logged(self):
        edit = Control(kind="Edit", masked=True)
        button = Control("Login", "Button")
        dialog = Control("Verify User PIN", children=[edit, button])
        button.on_invoke = lambda: setattr(dialog, "visible", False)
        desktop = Mock()
        desktop.windows.return_value = [dialog]
        logs = []
        clock = Clock()
        with patch.object(windows.time, "monotonic", clock.monotonic), patch.object(windows.time, "sleep", clock.sleep):
            windows.AutomatedTokenPrompt(log=logs.append)._handle_desktop(desktop, CERT, "secret-pin", threading.Event())
        self.assertEqual(edit.entered, ["secret-pin"])
        self.assertEqual(button.invocations, 1)
        self.assertNotIn("secret-pin", " ".join(logs))

    def test_stuck_or_rejected_pin_stops_without_retry(self):
        edit = Control(kind="Edit", masked=True)
        button = Control("Login", "Button")
        dialog = Control("Verify User PIN", children=[edit, button])
        desktop = Mock()
        desktop.windows.return_value = [dialog]
        clock = Clock()
        with patch.object(windows.time, "monotonic", clock.monotonic), patch.object(windows.time, "sleep", clock.sleep):
            with self.assertRaises(windows.TokenError):
                windows.AutomatedTokenPrompt(timeout=20)._handle_desktop(desktop, CERT, "bad-pin", threading.Event())
        self.assertEqual(button.invocations, 1)
        self.assertEqual(edit.entered, ["bad-pin"])

    def test_unmasked_edit_is_not_filled(self):
        edit = Control(kind="Edit", masked=False)
        dialog = Control("Verify User PIN", children=[edit, Control("Login", "Button")])
        desktop = Mock()
        desktop.windows.return_value = [dialog]
        with self.assertRaises(windows.TokenError):
            windows.AutomatedTokenPrompt()._handle_desktop(desktop, CERT, "pin", threading.Event())
        self.assertEqual(edit.entered, [])

    def test_generic_security_pin_requires_certificate_selection(self):
        edit = Control(kind="Edit", masked=True)
        dialog = Control("Windows Security", children=[edit, Control("OK", "Button")])
        desktop = Mock()
        desktop.windows.return_value = [dialog]
        with self.assertRaises(windows.TokenError):
            windows.AutomatedTokenPrompt()._handle_desktop(desktop, CERT, "pin", threading.Event())
        self.assertEqual(edit.entered, [])

    def test_stop_prevents_pin_submission(self):
        stop = threading.Event()
        stop.set()
        logs = []
        with self.assertRaises(windows.TokenError):
            windows.ManualTokenPrompt(logs.append).handle(None, "", stop)
        self.assertEqual(logs, [])


if __name__ == "__main__":
    unittest.main()


class DebuggerSocketRegressionTests(unittest.TestCase):
    def test_windows_timeout_on_unused_port_is_free(self):
        with patch.object(windows.socket, 'create_connection', side_effect=TimeoutError), \
             patch.object(windows.socket, 'socket') as factory:
            self.assertEqual(windows._debugger_state(9222), 'free')
        factory.return_value.__enter__.return_value.bind.assert_called_once_with(('127.0.0.1', 9222))

    def test_windows_10060_oserror_uses_ownership_probe(self):
        failure = OSError('timeout')
        failure.winerror = 10060
        with patch.object(windows.socket, 'create_connection', side_effect=failure), \
             patch.object(windows, '_port_after_timeout', return_value='free') as probe:
            self.assertEqual(windows._debugger_state(9222), 'free')
        probe.assert_called_once_with(9222)

    def test_timeout_does_not_treat_occupied_port_as_free(self):
        failure = OSError('in use')
        failure.winerror = 10048
        with patch.object(windows.socket, 'socket') as factory:
            factory.return_value.__enter__.return_value.bind.side_effect = failure
            self.assertEqual(windows._port_after_timeout(9222), 'unready')

    def test_permission_error_reports_windows_code(self):
        failure = PermissionError('blocked')
        failure.winerror = 10013
        with patch.object(windows.socket, 'create_connection', side_effect=failure):
            with self.assertRaisesRegex(windows.TokenError, '10013'):
                windows._debugger_state(9222)

    def test_http_startup_timeout_is_not_a_wrong_application(self):
        opener = Mock()
        opener.open.side_effect = TimeoutError
        with patch.object(windows.socket, 'create_connection'), patch.object(windows, 'build_opener', return_value=opener):
            self.assertEqual(windows._debugger_state(9222), 'unready')

    def test_real_unused_loopback_port(self):
        import socket
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        self.assertEqual(windows._debugger_state(port), 'free')

    def test_real_chrome_metadata_over_local_http(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({'Browser':'Chrome/156', 'webSocketDebuggerUrl':f'ws://127.0.0.1:{self.server.server_port}/devtools/browser/test'}).encode())
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1',0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            self.assertEqual(windows._debugger_state(server.server_port), 'chrome')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
