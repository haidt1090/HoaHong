import json
import threading
import unittest
from unittest.mock import Mock

from kyso.browser import BrowserCancelled, BrowserError, ChromeSession, Record, xpath_literal


def page(rows, pages=1, success=True, status=200):
    return json.dumps({"httpStatus": status, "body": json.dumps({
        "header": {"success": success}, "data": {"total_pages": pages, "data": rows}
    })})


def row(identifier="1", name="Test", status="init"):
    return {"check_up_id": identifier, "full_name": name, "status": status}


class FakeSwitch:
    def __init__(self, driver):
        self.driver = driver

    def window(self, handle):
        if handle not in self.driver.urls:
            raise RuntimeError("no such tab")
        self.driver.current_window_handle = handle

    def new_window(self, kind):
        self.driver.urls["owned"] = "about:blank"
        self.window("owned")


class FakeDriver:
    def __init__(self, results=()):
        self.urls = {"other": "https://example.com", "system": "https://admin.csdlksk.vn/admin/operation/health-checkup"}
        self.current_window_handle = "other"
        self.switch_to = FakeSwitch(self)
        self.capabilities = {"browserName": "chrome"}
        self.results = iter(results)
        self.closed = []
        self.visits = []
        self.fetches = []
        self.elements = []
        self.service = Mock()
        self.command_executor = Mock()
        self.quit = Mock()

    @property
    def window_handles(self):
        return list(self.urls)

    @property
    def current_url(self):
        return self.urls[self.current_window_handle]

    def set_script_timeout(self, timeout):
        self.script_timeout = timeout

    def set_page_load_timeout(self, timeout):
        self.page_load_timeout = timeout

    def execute_async_script(self, script, path):
        self.fetches.append(path)
        return next(self.results)

    def get(self, url):
        self.urls[self.current_window_handle] = url
        self.visits.append(url)

    def close(self):
        self.closed.append(self.current_window_handle)
        del self.urls[self.current_window_handle]

    def find_elements(self, by, selector):
        self.last_selector = (by, selector)
        return self.elements


class BrowserTests(unittest.TestCase):
    def session(self, results=()):
        driver = FakeDriver(results)
        browser = ChromeSession(driver=driver)
        browser.connect()
        return browser, driver

    def test_scan_snapshot_across_pages_and_deduplicates(self):
        browser, driver = self.session([
            page([row("one"), row("duplicate")], pages=2),
            page([row("duplicate"), row("two"), row("done", status="signed")], pages=2),
        ])
        records = browser.scan_pending()
        self.assertEqual([item.check_up_id for item in records], ["one", "duplicate", "two"])
        self.assertEqual(len(driver.fetches), 2)
        self.assertIn("page_number=1", driver.fetches[0])
        self.assertIn("page_number=2", driver.fetches[1])
        self.assertTrue(all(path.startswith("/api/checkup/health-examinations/all?") for path in driver.fetches))
        self.assertTrue(all("status=init" in path for path in driver.fetches))
        self.assertEqual(driver.closed, [])

    def test_empty_snapshot(self):
        browser, _ = self.session([page([], pages=0)])
        self.assertEqual(browser.scan_pending(), [])

    def test_authentication_failure_is_not_empty_results(self):
        browser, _ = self.session([page([], status=401)])
        with self.assertRaisesRegex(BrowserError, "401"):
            browser.scan_pending()

    def test_application_failure_is_not_empty_results(self):
        browser, _ = self.session([page([], success=False)])
        with self.assertRaisesRegex(BrowserError, "API"):
            browser.scan_pending()

    def test_invalid_response_shapes_fail(self):
        for data in ("not-json", "[]", json.dumps({"httpStatus": 200, "body": "{}"}), page([{"full_name": "missing id"}]), page([row()], pages=True)):
            with self.subTest(data=data):
                browser, _ = self.session([data])
                with self.assertRaises(BrowserError):
                    browser.scan_pending()

    def test_pending_record_requires_id(self):
        browser, _ = self.session([page([{"status": "init", "full_name": "A"}])])
        with self.assertRaisesRegex(BrowserError, "định danh"):
            browser.scan_pending()

    def test_page_count_change_requires_rescan(self):
        browser, _ = self.session([page([row()], pages=2), page([], pages=1)])
        with self.assertRaisesRegex(BrowserError, "thay đổi"):
            browser.scan_pending()

    def test_page_limit_fails_without_truncating(self):
        browser, driver = self.session([page([], pages=1001)])
        with self.assertRaisesRegex(BrowserError, "1000"):
            browser.scan_pending()
        self.assertEqual(len(driver.fetches), 1)

    def test_record_limit_fails_without_partial_return(self):
        browser, _ = self.session([page([row(str(n)) for n in range(3)])])
        browser.MAX_RECORDS = 2
        with self.assertRaisesRegex(BrowserError, "hơn 2"):
            browser.scan_pending()

    def test_stop_before_scan_makes_no_request(self):
        browser, driver = self.session()
        stop = threading.Event()
        stop.set()
        with self.assertRaises(BrowserCancelled):
            browser.scan_pending(stop)
        self.assertEqual(driver.fetches, [])

    def test_record_tab_is_cleaned_on_success_and_user_tabs_retained(self):
        browser, driver = self.session()
        with browser.open_record(Record("id/a?b")):
            self.assertEqual(driver.current_window_handle, "owned")
            self.assertTrue(driver.current_url.endswith("id%2Fa%3Fb"))
        self.assertEqual(driver.closed, ["owned"])
        self.assertEqual(set(driver.window_handles), {"other", "system"})
        self.assertEqual(driver.current_window_handle, "system")

    def test_completed_tab_is_kept_when_requested(self):
        browser, driver = self.session()
        browser.keep_completed_tabs = True
        with browser.open_record(Record("one")):
            pass
        self.assertEqual(driver.closed, [])
        self.assertEqual(set(driver.window_handles), {"other", "system", "owned"})
        self.assertEqual(driver.current_window_handle, "system")

    def test_constructor_accepts_keep_completed_tabs(self):
        driver = FakeDriver()
        browser = ChromeSession(driver=driver, keep_completed_tabs=True)
        browser.connect()
        with browser.open_record(Record("one")):
            pass
        self.assertEqual(driver.closed, [])
        self.assertIn("owned", driver.window_handles)

    def test_record_tab_is_preserved_on_workflow_failure(self):
        browser, driver = self.session()
        with self.assertRaisesRegex(RuntimeError, "failure"):
            with browser.open_record(Record("one")):
                raise RuntimeError("failure")
        self.assertEqual(driver.closed, [])
        self.assertIn("owned", driver.window_handles)
        self.assertEqual(driver.current_window_handle, "system")

    def test_login_redirect_cannot_reach_signing_actions(self):
        browser, driver = self.session()
        def redirect(_url):
            driver.urls[driver.current_window_handle] = "https://admin.csdlksk.vn/login?return=record"
        driver.get = redirect
        button = Mock()
        button.is_displayed.return_value = button.is_enabled.return_value = True
        driver.elements = [button]
        with self.assertRaisesRegex(BrowserError, "đúng hồ sơ"):
            with browser.open_record(Record("one")):
                browser.click_css('button[type="submit"]', timeout=0)
        button.click.assert_not_called()
        self.assertIn("owned", driver.window_handles)
        self.assertEqual(driver.closed, [])
        self.assertEqual(driver.current_window_handle, "system")

    def test_record_redirect_with_trailing_slash_and_query_is_allowed(self):
        browser, driver = self.session()
        original_get = driver.get
        driver.get = lambda url: original_get(url + "/?mode=view")
        with browser.open_record(Record("one")):
            self.assertTrue(driver.current_url.endswith("/one/?mode=view"))
        self.assertEqual(driver.closed, ["owned"])

    def test_new_tab_navigation_failure_keeps_preexisting_tabs(self):
        browser, driver = self.session()
        driver.get = Mock(side_effect=RuntimeError("navigation failed"))
        with self.assertRaisesRegex(RuntimeError, "navigation failed"):
            with browser.open_record(Record("one")):
                self.fail("body must not run")
        self.assertEqual(driver.closed, [])
        self.assertEqual(set(driver.window_handles), {"other", "system", "owned"})

    def test_disconnect_never_quits_attached_browser(self):
        browser, driver = self.session()
        browser.disconnect()
        driver.quit.assert_not_called()
        driver.command_executor.close.assert_called_once()
        driver.service.stop.assert_called_once()
        self.assertEqual(driver.closed, [])
        self.assertIsNone(browser.driver)

    def test_unrelated_tab_cannot_be_used_for_actions(self):
        browser, driver = self.session()
        driver.switch_to.window("other")
        with self.assertRaisesRegex(BrowserError, "chuyển khỏi"):
            browser.click_css("button", timeout=0)

    def test_no_matching_site_requires_user_login(self):
        driver = FakeDriver()
        driver.urls["system"] = "https://admin.csdlksk.vn/login"
        browser = ChromeSession(driver=driver)
        with self.assertRaisesRegex(BrowserError, "đăng nhập"):
            browser.connect()
        self.assertEqual(driver.current_window_handle, "other")

    def test_deceptive_host_is_not_same_origin(self):
        driver = FakeDriver()
        driver.urls["system"] = "https://admin.csdlksk.vn.evil.example/admin"
        with self.assertRaises(BrowserError):
            ChromeSession(driver=driver).connect()

    def test_debug_endpoint_is_loopback_only(self):
        for value in ("example.com:9222", "127.0.0.1", "127.0.0.1:9222/x", "name@127.0.0.1:9222", "127.0.0.1:99999"):
            with self.subTest(value=value), self.assertRaises(BrowserError):
                ChromeSession(debugger_address=value)

    def test_complete_waits_for_enabled_button_and_honors_stop(self):
        browser, driver = self.session()
        hidden = Mock()
        hidden.is_displayed.return_value = False
        disabled = Mock()
        disabled.is_displayed.return_value = True
        disabled.is_enabled.return_value = False
        ready = Mock()
        ready.is_displayed.return_value = ready.is_enabled.return_value = True
        driver.elements = [hidden, disabled, ready]
        browser.wait_complete(timeout=0)
        ready.click.assert_not_called()
        stop = threading.Event()
        stop.set()
        with self.assertRaises(BrowserCancelled):
            browser.wait_complete(stop_event=stop)

    def test_click_uses_native_click(self):
        browser, driver = self.session()
        element = Mock()
        element.is_displayed.return_value = element.is_enabled.return_value = True
        driver.elements = [element]
        browser.click_text('a\'b"c', timeout=0)
        self.assertIn('concat(', driver.last_selector[1])
        self.assertIn("self::a", driver.last_selector[1])
        element.click.assert_called_once()

    def test_ambiguous_buttons_are_not_clicked(self):
        browser, driver = self.session()
        buttons = [Mock(), Mock()]
        for button in buttons:
            button.is_displayed.return_value = True
            button.is_enabled.return_value = True
        driver.elements = buttons
        with self.assertRaisesRegex(BrowserError, "nhiều nút"):
            browser.click_css("button", timeout=0)
        for button in buttons:
            button.click.assert_not_called()

    def test_page_load_timeout_is_bounded(self):
        browser, driver = self.session()
        self.assertEqual(driver.page_load_timeout, 45)

    def test_disconnect_cleanup_failures_do_not_escape(self):
        browser, driver = self.session()
        driver.command_executor.close.side_effect = RuntimeError("transport")
        driver.service.stop.side_effect = RuntimeError("service")
        browser.disconnect()
        driver.service.stop.assert_called_once()
        self.assertIsNone(browser.driver)

    def test_cleanup_failure_does_not_hide_workflow_error(self):
        browser, driver = self.session()
        with self.assertRaisesRegex(RuntimeError, "primary failure"):
            with browser.open_record(Record("one")):
                driver.switch_to.window = Mock(side_effect=RuntimeError("cleanup"))
                raise RuntimeError("primary failure")
        self.assertEqual(driver.closed, [])

    def test_timeout_is_failure(self):
        browser, driver = self.session()
        driver.elements = []
        with self.assertRaisesRegex(BrowserError, "Không tìm thấy"):
            browser.wait_complete(timeout=0)

    def test_xpath_quote_literal(self):
        self.assertEqual(xpath_literal("a'b"), '"a\'b"')
        self.assertEqual(xpath_literal('a"b'), "'a\"b'")
        self.assertEqual(xpath_literal('a\'b"c'), "concat('a', \"'\", 'b\"c')")


if __name__ == "__main__":
    unittest.main()
