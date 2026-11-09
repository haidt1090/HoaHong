import asyncio,tempfile,unittest
from types import SimpleNamespace
from unittest.mock import patch
import httpx
from telegram_access import allowed_bot,allowed_account,phone_fingerprint
from telegram_source import TelegramWorker
class AccessTests(unittest.TestCase):
    def test_exact_bot_username_only(self):
        self.assertTrue(allowed_bot({'username':'PKHoaHongBot'}))
        for user in [{},{'username':'otherbot'},{'username':'pkhoahongbot_fake'},{'username':None}]: self.assertFalse(allowed_bot(user))
    def test_exact_account_only(self):
        with patch('telegram_access.ACCOUNT_FINGERPRINT',phone_fingerprint('84900000000')):
            for phone in ['+84900000000','84900000000','0900000000','+84 900 000 000']: self.assertTrue(allowed_account(phone))
            for phone in [None,'','+84900000001','0900000001']: self.assertFalse(allowed_account(phone))
    def test_other_bot_is_denied_before_updates_or_download(self):
        with tempfile.TemporaryDirectory() as d:
            worker=TelegramWorker('bot',{'token':'123:fake'},d); calls=[]; stages=[]
            worker.stage.connect(stages.append)
            def handler(request):
                calls.append(request.url.path)
                return httpx.Response(200,json={'ok':True,'result':{'id':123,'username':'otherbot'}})
            import sqlite3
            worker.db=sqlite3.connect(':memory:')
            with patch('httpx.AsyncClient',return_value=httpx.AsyncClient(transport=httpx.MockTransport(handler))): asyncio.run(worker.bot())
            self.assertEqual(len(calls),1); self.assertTrue(calls[0].endswith('getMe'))
            self.assertEqual(stages,['error']); self.assertFalse(worker.access_verified); worker.db.close()
    def test_wrong_saved_account_disconnects_before_listing_groups(self):
        with tempfile.TemporaryDirectory() as d:
            worker=TelegramWorker('account',{'api_id':'123','api_hash':'fake'},d); calls=[]; stages=[]
            worker.stage.connect(stages.append)
            class Client:
                async def connect(self): calls.append('connect')
                async def disconnect(self): calls.append('disconnect')
                async def is_user_authorized(self): return True
                def add_event_handler(self,*args): pass
                async def get_me(self): return SimpleNamespace(id=1,phone='84900000000')
                def iter_dialogs(self): raise AssertionError('Must not list groups for a denied account')
            with patch('telethon.TelegramClient',return_value=Client()): asyncio.run(worker.account())
            self.assertEqual(calls,['connect','disconnect']); self.assertEqual(stages,['error']); self.assertFalse(worker.access_verified)
    def test_unapproved_input_phone_does_not_request_login_code(self):
        with tempfile.TemporaryDirectory() as d:
            worker=TelegramWorker('account',{'api_id':'123','api_hash':'fake'},d); calls=[]; stages=[]
            class Client:
                async def connect(self): pass
                async def disconnect(self): calls.append('disconnect')
                async def is_user_authorized(self): return False
                def add_event_handler(self,*args): pass
                async def send_code_request(self,*args): raise AssertionError('Must not send a code to another phone')
            def stage(value):
                stages.append(value)
                if len(stages)==1:
                    worker.command('phone','+84900000000'); worker.command('stop')
            worker.stage.connect(stage)
            with patch('telethon.TelegramClient',return_value=Client()): asyncio.run(worker.account())
            self.assertEqual(calls,['disconnect']); self.assertNotIn('code',stages); self.assertFalse(worker.access_verified)
if __name__=='__main__': unittest.main()
