import asyncio,sqlite3,tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch
import httpx
from telegram_source import TelegramWorker,bot_media

class MediaTests(unittest.TestCase):
    def test_largest_photo(self):
        self.assertEqual(bot_media({'photo':[{'file_id':'small','file_size':10},{'file_id':'large','file_size':50}]}),('large','.jpg',50))
    def test_documents(self):
        self.assertEqual(bot_media({'document':{'file_id':'x','mime_type':'image/png'}}),('x','.png',0))
        self.assertIsNone(bot_media({'document':{'file_id':'x','mime_type':'application/pdf'}}))
    def test_bot_download_selected_group_and_deduplicate(self):
        with tempfile.TemporaryDirectory() as d:
            worker=TelegramWorker('bot',{'token':'123:fake_token'},d)
            worker.db=sqlite3.connect(':memory:'); worker.db.execute('CREATE TABLE received (key TEXT PRIMARY KEY)')
            worker.selected=-1001
            counters={'polls':0,'downloads':0}; offsets=[]
            def message(chat_id,message_id):
                return {'message_id':message_id,'chat':{'id':chat_id,'type':'supergroup','title':'Test'},'photo':[{'file_id':'pic','file_size':3}]}
            def handler(request):
                path=request.url.path
                if path.endswith('getMe'): return httpx.Response(200,json={'ok':True,'result':{'id':123,'username':'pkhoahongbot'}})
                if path.endswith('getWebhookInfo'): return httpx.Response(200,json={'ok':True,'result':{'url':''}})
                if path.endswith('getUpdates'):
                    counters['polls']+=1; offsets.append(json.loads(request.content)['offset'])
                    if counters['polls']==1:
                        updates=[{'update_id':1,'message':message(-1001,10)}, {'update_id':2,'message':message(-1002,11)}, {'update_id':3,'message':message(-1001,10)}]
                    else: worker.stopping=True; updates=[]
                    return httpx.Response(200,json={'ok':True,'result':updates})
                if path.endswith('getFile'): return httpx.Response(200,json={'ok':True,'result':{'file_path':'photos/test.jpg'}})
                if '/file/' in path:
                    counters['downloads']+=1; return httpx.Response(200,content=b'img')
                raise AssertionError(path)
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
            with patch('httpx.AsyncClient',return_value=client): asyncio.run(worker.bot())
            files=list(Path(d).rglob('*.jpg'))
            self.assertEqual(len(files),1); self.assertEqual(files[0].read_bytes(),b'img')
            self.assertEqual(counters['downloads'],1)
            self.assertEqual(offsets,[0,4])
            self.assertEqual(worker.db.execute('SELECT offset FROM bot_offsets WHERE bot=?',('123',)).fetchone()[0],4)
            self.assertEqual(list(Path(d).rglob('*.part')),[])
            worker.db.close()

class AccountTests(unittest.TestCase):
    def test_login_code_2fa_group_selection_and_download(self):
        from types import SimpleNamespace
        from telethon import errors
        with tempfile.TemporaryDirectory() as d:
            worker=TelegramWorker('account',{'api_id':'123','api_hash':'test'},d)
            worker.db=sqlite3.connect(':memory:'); worker.db.execute('CREATE TABLE received (key TEXT PRIMARY KEY)')
            calls=[]
            class Client:
                def __init__(self,*args): self.handler=None; self.driver=None
                async def connect(self): pass
                async def disconnect(self):
                    if self.driver: await self.driver
                    calls.append('disconnect')
                async def is_user_authorized(self): return False
                async def send_code_request(self,phone): calls.append('phone')
                async def sign_in(self,**kwargs):
                    if 'code' in kwargs: calls.append('code'); raise errors.SessionPasswordNeededError(request=None)
                    calls.append('password')
                async def get_me(self): return SimpleNamespace(id=99)
                async def iter_dialogs(self):
                    yield SimpleNamespace(is_group=True,entity='entity',name='Ảnh')
                def add_event_handler(self,handler,event): self.handler=handler
                async def download_media(self,message,file):
                    Path(file).write_bytes(b'image'); calls.append('download')
            client=Client()
            def stage(value):
                if value=='phone': worker.command('phone','+84000000000')
                elif value=='code': worker.command('code','12345')
                elif value=='password': worker.command('password','fake')
                elif value=='ready':
                    worker.command('select',-1001)
                    async def drive():
                        while worker.selected is None: await asyncio.sleep(.01)
                        event=SimpleNamespace(chat_id=-1001,message=SimpleNamespace(photo=True,id=5,file=SimpleNamespace(size=5)))
                        await client.handler(event); await client.handler(event)
                        event.chat_id=-1002; await client.handler(event)
                        worker.command('stop')
                    client.driver=asyncio.create_task(drive())
            worker.stage.connect(stage)
            with patch('telethon.TelegramClient',return_value=client),patch('telethon.utils.get_peer_id',return_value=-1001): asyncio.run(worker.account())
            self.assertEqual(calls,['phone','code','password','download','disconnect'])
            self.assertEqual(len(list(Path(d).rglob('*.jpg'))),1)
            worker.db.close()

if __name__=='__main__': unittest.main()

