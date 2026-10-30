"""Opt-in real-browser smoke test against synthetic, loopback-only HTML/API.

Run with KYSO_BROWSER_SMOKE=1 and, when not on PATH,
KYSO_CHROMIUM_BINARY / KYSO_CHROMEDRIVER. It never contacts the live system,
uses no real identity or USB, and does not validate Windows token middleware.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import threading
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from kyso import browser as browser_module
from kyso import connection
from kyso.browser import BrowserError, ChromeSession
from kyso.windows import ManualTokenPrompt
from kyso.workflow import BatchSigner


@unittest.skipUnless(os.environ.get("KYSO_BROWSER_SMOKE") == "1", "opt-in local Chromium smoke")
class LocalBrowserSmoke(unittest.TestCase):
    def test_scan_then_original_signing_sequence_on_synthetic_pages(self):
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service

        receipts = []
        requests_seen = []
        receipts_ready = threading.Event()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format, *_args):
                pass

            def send(self, value, content_type="application/json"):
                body = value.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", content_type + "; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                parsed = urlsplit(self.path)
                requests_seen.append(parsed.path)
                if parsed.path == "/api/checkup/health-examinations/all":
                    query = parse_qs(parsed.query)
                    if query.get("status") != ["init"]:
                        self.send_error(400)
                        return
                    page = int(query.get("page_number", ["1"])[0])
                    rows = [{"check_up_id": f"fixture-{page}", "full_name": f"Synthetic {page}", "status": "init"}]
                    self.send(json.dumps({"header": {"success": True}, "data": {"total_pages": 2, "data": rows}}))
                    return
                if parsed.path.startswith("/admin/operation/health-checkup/"):
                    record_id = parsed.path.rsplit("/", 1)[-1]
                    # Every transition exposes exactly one actionable control.
                    # The anchor is intentional: the original app can use links.
                    self.send("""<!doctype html><html><meta charset="utf-8"><body>
<input placeholder="NHẬP HỌ TÊN" id="patient-name">
<button type="submit" onclick="throw new Error('Must not save the patient form')">Lưu thông tin</button>
<div id="stage"><button type="button" onclick="next(2)">Ký phiếu khám</button></div>
<script>
const id = RECORD_ID;
document.getElementById('patient-name').value = 'Synthetic ' + id.split('-').pop();
function next(n) {
 const stage = document.getElementById('stage');
 if (n === 2) stage.innerHTML = '<button aria-label="Chọn chữ ký để đặt vào PDF" onclick="next(3)">Đặt chữ ký</button>';
 if (n === 3) stage.innerHTML = '<a href="#" onclick="event.preventDefault();next(4)">Tạo chữ ký mới</a>';
 if (n === 4) stage.innerHTML = '<button onclick="next(5)">Save signature</button>';
 if (n === 5) stage.innerHTML = '<button onclick="next(6)">Sign with USB Token</button>';
 if (n === 6) stage.innerHTML = '<button onclick="receipt(this)">Complete</button>';
}
async function receipt(button) {
 button.disabled = true;
 await fetch('/receipt', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id})});
 document.getElementById('stage').textContent = 'Fixture đã nhận Complete';
}
</script></body></html>""".replace("RECORD_ID", json.dumps(record_id)), "text/html")
                    return
                self.send("<!doctype html><title>Synthetic system tab</title><p>Local fixture only</p>", "text/html")

            def do_POST(self):
                if self.path != "/receipt":
                    self.send_error(404)
                    return
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                receipts.append(data["id"])
                if len(receipts) == 2:
                    receipts_ready.set()
                self.send("{}")

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        target = f"http://127.0.0.1:{server.server_port}"
        options = webdriver.ChromeOptions()
        if os.environ.get("KYSO_CHROMIUM_BINARY"):
            options.binary_location = os.environ["KYSO_CHROMIUM_BINARY"]
        for argument in (
            "--headless=new", "--no-sandbox", "--disable-dev-shm-usage",
            "--no-proxy-server", "--disable-background-networking",
            "--no-first-run", "--disable-default-apps", "--disable-extensions",
            "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
        ):
            options.add_argument(argument)
        driver_path = os.environ.get("KYSO_CHROMEDRIVER")
        service = Service(executable_path=driver_path) if driver_path else Service()
        driver = None
        session = None
        original_origin = browser_module._origin

        def fixture_origin(value):
            parsed = urlsplit(value)
            # Relax HTTPS only for this exact test server; production remains
            # untouched and still rejects HTTP and arbitrary loopback endpoints.
            if (parsed.scheme == "http" and parsed.hostname == "127.0.0.1"
                    and parsed.port == server.server_port and parsed.username is None
                    and parsed.password is None):
                return parsed.scheme, parsed.hostname, parsed.port
            return original_origin(value)

        try:
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(45)
            driver.get(target + "/admin/operation/health-checkup")
            original_handle = driver.current_window_handle
            with patch.object(browser_module, "_origin", fixture_origin):
                # Exercise the production attachment path, not an injected driver.
                address = '127.0.0.1:' + driver.capabilities['goog:chromeOptions']['debuggerAddress'].rsplit(':', 1)[1]
                session = ChromeSession(base_url=target, debugger_address=address, keep_completed_tabs=True)
                with patch.object(connection.shutil, 'which', return_value=driver.service.path), \
                     patch.dict(os.environ, {'HTTP_PROXY':'http://127.0.0.1:9', 'HTTPS_PROXY':'http://127.0.0.1:9', 'NO_PROXY':''}):
                    session.connect()
                    self.assertEqual(os.environ['HTTP_PROXY'], 'http://127.0.0.1:9')
                records = session.scan_pending()
                self.assertEqual([record.check_up_id for record in records], ["fixture-1", "fixture-2"])
                result = BatchSigner(session, ManualTokenPrompt()).run(records)
                self.assertEqual(result.attempted, 2)
                self.assertEqual(result.completed_steps, 2)
                self.assertEqual(result.failed, 0, result.error)
                self.assertEqual(result.needs_review, [])
                self.assertTrue(receipts_ready.wait(5), "Synthetic server did not receive both Complete requests")
                self.assertEqual(receipts, ["fixture-1", "fixture-2"])
                self.assertEqual(len(driver.window_handles), 3)
                self.assertEqual(driver.current_window_handle, original_handle)
                self.assertEqual(requests_seen.count("/api/checkup/health-examinations/all"), 2)
                for handle in driver.window_handles:
                    driver.switch_to.window(handle)
                    self.assertTrue(driver.current_url.startswith(target + "/"))
                session.disconnect()
                self.assertEqual(len(driver.window_handles), 3, "Disconnect closed the external browser")
        finally:
            # This driver/browser was created exclusively by this test. Production
            # ChromeSession.disconnect never calls quit on an attached browser.
            if session is not None:
                session.disconnect()
            if driver is not None:
                driver.quit()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
