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
        self.visible_rows = []
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

    def execute_script(self, script):
        self.read_script = script
        return self.visible_rows

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

    @staticmethod
    def bulk_row(number=1, status="Chưa ký số", selectable=True):
        return {"row_number": str(number), "name": f"Synthetic {number}",
                "masked_identifier": f"000*****{number:03d}",
                "status": status, "selectable": selectable}

    def test_preview_reads_first_five_pending_checkbox_rows_without_api_or_navigation(self):
        browser, driver = self.session()
        driver.visible_rows = [self.bulk_row(n) for n in range(1, 9)]
        browser.click_text = Mock()
        records = browser.scan_list_preview()
        self.assertEqual([r.row_number for r in records], [str(n) for n in range(1, 6)])
        self.assertTrue(all(r.status == "Chưa ký số" for r in records))
        self.assertEqual(driver.fetches, [])
        self.assertEqual(driver.visits, [])
        browser.click_text.assert_not_called()
        from kyso.workflow import BatchSigner
        token = Mock()
        with self.assertRaises(ValueError):
            BatchSigner(browser, token).run(records)
        token.handle.assert_not_called()

    def test_preview_opens_action_menu_then_bulk_picker_only(self):
        browser, driver = self.session()
        driver.execute_script = Mock(side_effect=[None, [self.bulk_row()]])
        browser.click_text = Mock()
        records = browser.scan_list_preview()
        self.assertEqual([call.args[0] for call in browser.click_text.call_args_list],
                         ["Hành động", "Ký nhiều file"])
        self.assertEqual(len(records), 1)
        self.assertEqual(driver.visits, [])
        self.assertEqual(driver.fetches, [])

    def test_preview_ignores_signed_and_disabled_rows(self):
        browser, driver = self.session()
        driver.visible_rows = [self.bulk_row(1, status="Đã ký số"),
                               self.bulk_row(2, selectable=False), self.bulk_row(3)]
        self.assertEqual([r.row_number for r in browser.scan_list_preview()], ["3"])

    def test_preview_rejects_malformed_or_duplicate_rows(self):
        for rows in ([], [self.bulk_row(), self.bulk_row()], [{"name": "missing status"}]):
            browser, driver = self.session()
            driver.visible_rows = rows
            with self.assertRaises(BrowserError):
                browser.scan_list_preview()
            self.assertEqual(driver.fetches, [])

    def test_preview_rejects_ambiguous_list_tabs_without_navigating(self):
        browser, driver = self.session()
        driver.urls["second"] = driver.urls["system"] + "?page=2"
        driver.switch_to.window("other")
        with self.assertRaisesRegex(BrowserError, "đúng tab"):
            browser.scan_list_preview()
        self.assertEqual(driver.current_window_handle, "other")
        self.assertEqual(driver.visits, [])

    def test_preview_prefers_selected_list_tab_over_previous_base(self):
        browser, driver = self.session()
        driver.urls["selected"] = driver.urls["system"] + "?page=2"
        driver.switch_to.window("selected")
        driver.visible_rows = [self.bulk_row()]
        self.assertEqual(len(browser.scan_list_preview()), 1)
        self.assertEqual(driver.current_window_handle, "selected")

    def test_preview_cancelled_before_read(self):
        browser, driver = self.session()
        stop = threading.Event()
        stop.set()
        with self.assertRaises(BrowserCancelled):
            browser.scan_list_preview(stop)
        self.assertFalse(hasattr(driver, "read_script"))

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

    def test_batch_limit_stops_at_100_without_fetching_later_pages(self):
        browser, driver = self.session([
            page([row(str(n)) for n in range(100)], pages=3),
        ])
        records = browser.scan_pending(limit=100)
        self.assertEqual([r.check_up_id for r in records], [str(n) for n in range(100)])
        self.assertEqual(len(driver.fetches), 1)

    def test_next_batch_restarts_page_one_and_excludes_previous_ids(self):
        browser, driver = self.session([
            page([row("old"), row("new")], pages=2),
            page([row("new"), row("next"), row("signed", status="signed")], pages=2),
        ])
        records = browser.scan_pending(limit=100, exclude_ids={"old"})
        self.assertEqual([r.check_up_id for r in records], ["new", "next"])
        self.assertIn("page_number=1", driver.fetches[0])

    def test_invalid_batch_limit_is_rejected_before_fetch(self):
        for limit in (0, -1, True, 1.5):
            browser, driver = self.session()
            with self.assertRaises(ValueError):
                browser.scan_pending(limit=limit)
            self.assertEqual(driver.fetches, [])

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

    def test_patient_form_must_match_scanned_name_before_signing(self):
        browser, driver = self.session()
        field = Mock()
        field.is_displayed.return_value = True
        values = {"placeholder": "NHẬP HỌ TÊN", "value": "  Nguyễn   Văn A "}
        field.get_attribute.side_effect = values.get
        driver.elements = [field]
        browser.wait_record_loaded(Record("a", "NGUYỄN VĂN A"), timeout=0)
        field.click.assert_not_called()
        for value in ("", "Nguyễn Văn B"):
            values["value"] = value
            with self.subTest(value=value), self.assertRaisesRegex(BrowserError, "chưa tải đúng"):
                browser.wait_record_loaded(Record("a", "Nguyễn Văn A"), timeout=0)

    def test_missing_or_ambiguous_patient_form_is_rejected(self):
        browser, driver = self.session()
        field = Mock()
        field.is_displayed.return_value = True
        field.get_attribute.side_effect = {"placeholder": "NHẬP HỌ TÊN", "value": "Test"}.get
        for fields in ([], [field, field]):
            driver.elements = fields
            with self.assertRaises(BrowserError):
                browser.wait_record_loaded(Record("a", "Test"), timeout=0)

    def test_cancel_before_patient_data_check(self):
        browser, driver = self.session()
        stop = threading.Event()
        stop.set()
        with self.assertRaises(BrowserCancelled):
            browser.wait_record_loaded(Record("a", "Test"), stop_event=stop)

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
