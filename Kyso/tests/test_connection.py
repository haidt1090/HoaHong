import io
import json
import unittest
from unittest.mock import Mock, patch
from kyso import connection


class ConnectionTests(unittest.TestCase):
    def test_reads_version_without_proxy(self):
        opener = Mock()
        opener.open.return_value = io.BytesIO(json.dumps({'Browser':'Chrome/156.0.8078.47'}).encode())
        with patch.object(connection, 'ProxyHandler') as handler, patch.object(connection, 'build_opener', return_value=opener):
            self.assertEqual(connection.chrome_version('127.0.0.1:9222'), '156.0.8078.47')
        handler.assert_called_once_with({})

    def test_invalid_endpoint_rejected(self):
        opener = Mock()
        opener.open.return_value = io.BytesIO(b'{"Browser":"Other/1"}')
        with patch.object(connection, 'build_opener', return_value=opener):
            with self.assertRaises(connection.ConnectionSetupError):
                connection.chrome_version('127.0.0.1:9222')

    def test_matching_local_driver_works_without_manager(self):
        with patch.object(connection.shutil, 'which', return_value='local-driver'), \
             patch.object(connection, 'driver_version', return_value='156.0.1.2'), \
             patch('selenium.webdriver.common.selenium_manager.SeleniumManager') as manager:
            self.assertEqual(connection.resolve_driver('156.0.3.4', lambda _: None), 'local-driver')
        manager.assert_not_called()

    def test_wrong_path_driver_does_not_override_running_chrome_version(self):
        with patch.object(connection.shutil, 'which', return_value='old-driver'), \
             patch.object(connection, 'driver_version', side_effect=['120.0.1.2', '156.0.3.4']), \
             patch('selenium.webdriver.common.selenium_manager.SeleniumManager') as manager:
            manager.return_value.binary_paths.return_value = {'driver_path':'right-driver'}
            self.assertEqual(connection.resolve_driver('156.0.3.4', lambda _: None), 'right-driver')
        args = manager.return_value.binary_paths.call_args.args[0]
        self.assertEqual(args[args.index('--browser-version')+1], '156.0.3.4')
        self.assertIn('--skip-driver-in-path', args)
        self.assertIn('--avoid-browser-download', args)

    def test_manager_failure_shows_real_diagnostic(self):
        with patch.object(connection.shutil, 'which', return_value=None), \
             patch('selenium.webdriver.common.selenium_manager.SeleniumManager') as manager:
            manager.return_value.binary_paths.side_effect = RuntimeError('download failed: DNS blocked')
            with self.assertRaisesRegex(connection.ConnectionSetupError, 'DNS blocked'):
                connection.resolve_driver('156.0.1.2', lambda _: None)

    def test_attach_uses_explicit_service_and_local_proxy_bypass(self):
        with patch.object(connection, 'chrome_version', return_value='156.0.1.2'), \
             patch.object(connection, 'resolve_driver', return_value='driver'), \
             patch('selenium.webdriver.Chrome') as chrome:
            connection.attach('127.0.0.1:9222', lambda _:None)
        opts = chrome.call_args.kwargs['options']
        self.assertEqual(opts.debugger_address, '127.0.0.1:9222')
        self.assertTrue(opts._ignore_local_proxy)
        self.assertNotIn('detach', opts.experimental_options)
        self.assertEqual(chrome.call_args.kwargs['service'].path, 'driver')

    def test_attach_failure_retains_driver_mismatch_detail(self):
        with patch.object(connection, 'chrome_version', return_value='156.0.1.2'), \
             patch.object(connection, 'resolve_driver', return_value='driver'), \
             patch('selenium.webdriver.chrome.service.Service') as service, \
             patch('selenium.webdriver.Chrome', side_effect=RuntimeError('only supports Chrome version 120')):
            with self.assertRaisesRegex(connection.ConnectionSetupError, 'only supports Chrome version 120'):
                connection.attach('127.0.0.1:9222', lambda _:None)
        service.return_value.stop.assert_called_once()

    def test_diagnostic_redacts_credentials_and_tokens(self):
        text = connection.safe_error(RuntimeError('download https://name:secret@proxy.test/path?token=private'))
        self.assertNotIn('secret',text)
        self.assertNotIn('private',text)
