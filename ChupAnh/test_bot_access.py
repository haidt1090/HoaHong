import asyncio,sqlite3,tempfile,unittest
from unittest.mock import patch
import httpx
from telegram_access import allowed_bot
from telegram_source import TelegramWorker
class BotAccessTests(unittest.TestCase):
    def test_exact_username_only(self):
        self.assertTrue(allowed_bot({'username':'PKHoaHongBot'}))
        for value in [None,'otherbot','pkhoahongbot_fake']: self.assertFalse(allowed_bot({'username':value}))
    def test_rejected_bot_cannot_poll_messages(self):
        with tempfile.TemporaryDirectory() as d:
            worker=TelegramWorker('bot',{'token':'123:fake'},d); calls=[]; stages=[]
            worker.stage.connect(stages.append); worker.db=sqlite3.connect(':memory:')
            def handler(request):
                calls.append(request.url.path)
                return httpx.Response(200,json={'ok':True,'result':{'id':123,'username':'otherbot'}})
            with patch('httpx.AsyncClient',return_value=httpx.AsyncClient(transport=httpx.MockTransport(handler))): asyncio.run(worker.bot())
            self.assertEqual(len(calls),1); self.assertTrue(calls[0].endswith('getMe')); self.assertEqual(stages,['error']); worker.db.close()
if __name__=='__main__': unittest.main()
