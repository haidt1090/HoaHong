"""Telegram adapters with durable bot offsets and explicit connection status."""
import asyncio, json, queue, sqlite3, re
from pathlib import Path
from PySide6.QtCore import QThread, Signal

class BotAPIError(Exception):
    def __init__(self,code): self.code=code

def bot_error_text(exc):
    if isinstance(exc,BotAPIError):
        if exc.code==401: return 'Token bot không hợp lệ hoặc đã bị thu hồi. Kiểm tra token ở @BotFather.'
        if exc.code==409: return 'Bot đang có webhook hoặc một ứng dụng khác đang nhận cập nhật. Chỉ chạy một bản phần mềm cho bot này.'
        if exc.code==403: return 'Bot không có quyền truy cập. Kiểm tra bot còn trong nhóm và quyền nhận ảnh.'
        if exc.code==429: return 'Telegram đang giới hạn yêu cầu; đang chờ để thử lại.'
    return 'Lỗi mạng/nhận ảnh ('+type(exc).__name__+'). Đang tự thử lại.'

SUPPORTED={'image/jpeg' :'.jpg','image/png':'.png','image/webp':'.webp','image/bmp':'.bmp'}
def bot_media(message):
    if message.get('photo'):
        item=max(message['photo'],key=lambda p:p.get('file_size',p.get('width',0)*p.get('height',0)))
        return item['file_id'],'.jpg',item.get('file_size',0)
    doc=message.get('document',{})
    if doc.get('mime_type') in SUPPORTED:
        return doc['file_id'],SUPPORTED[doc['mime_type']],doc.get('file_size',0)
    return None

class TelegramWorker(QThread):
    status=Signal(str); groups=Signal(list); image=Signal(str); stage=Signal(str)
    def __init__(self,mode,credentials,base,parent=None):
        super().__init__(parent); self.mode=mode; self.credentials=credentials
        self.base=Path(base); self.commands=queue.Queue(); self.selected=None
        self.stopping=False; self.identity=''; self.known={}
    def command(self,name,value=None): self.commands.put((name,value))
    def run(self):
        self.db=sqlite3.connect(self.base/'telegram.sqlite')
        self.db.execute('CREATE TABLE IF NOT EXISTS received (key TEXT PRIMARY KEY)'); self.db.commit()
        try: asyncio.run(self.bot() if self.mode=='bot' else self.account())
        except Exception as exc:
            # Never expose URLs, phone numbers, tokens or access hashes in exceptions.
            self.status.emit('Kết nối đã dừng ('+type(exc).__name__+'). Kiểm tra thông tin đăng nhập và mạng.'); self.stage.emit('error')
        finally: self.db.close(); self.credentials.clear()
    def seen(self,key): return self.db.execute('SELECT 1 FROM received WHERE key=?',(key,)).fetchone() is not None
    def commit(self,key):
        self.db.execute('INSERT OR IGNORE INTO received VALUES (?)',(key,)); self.db.commit()
    def target(self,chat,message,ext):
        folder=self.base/'telegram-images'/self.mode/str(self.identity)/str(chat)
        folder.mkdir(parents=True,exist_ok=True)
        return folder/(str(message)+ext)
    def publish(self,temporary,dest,key,chat):
        temporary.replace(dest); self.commit(key)
        if self.selected==chat and not self.stopping: self.image.emit(str(dest))
    def remember(self,chat_id,title):
        if self.known.get(chat_id)!=title:
            self.known[chat_id]=title
            self.groups.emit([(i,t) for i,t in self.known.items()])
    def drain(self):
        while not self.commands.empty():
            name,value=self.commands.get_nowait()
            if name=='stop': self.stopping=True
            elif name=='select':
                self.selected=value
                self.status.emit('Đang nhận ảnh mới từ nhóm ID '+str(value))
    async def bot(self):
        import httpx
        token=self.credentials['token'].strip()
        if not re.fullmatch(r'\d+:[A-Za-z0-9_-]+',token): raise ValueError('token')
        async with httpx.AsyncClient(timeout=20) as client:
            async def api(method,**data):
                r=await client.post('https://api.telegram.org/bot'+token+'/'+method,json=data)
                payload=r.json()
                if not payload.get('ok'): raise BotAPIError(payload.get('error_code',r.status_code))
                return payload['result']
            self.db.execute('CREATE TABLE IF NOT EXISTS bot_offsets (bot TEXT PRIMARY KEY, offset INTEGER)')
            while not self.stopping:
                self.drain()
                if self.stopping: return
                try:
                    me=await api('getMe'); self.identity=str(me['id'])
                    webhook=await api('getWebhookInfo')
                    if webhook.get('url'):
                        self.status.emit('Bot đang dùng webhook. Tắt webhook ở dịch vụ đang dùng hoặc tạo bot riêng; phần mềm không tự xóa webhook.')
                        self.stage.emit('error'); return
                    break
                except Exception as exc:
                    self.status.emit(bot_error_text(exc))
                    if isinstance(exc,BotAPIError) and exc.code in (401,403): self.stage.emit('error'); return
                    await asyncio.sleep(3)
            if self.stopping: return
            self.stage.emit('ready')
            if self.known: self.groups.emit(list(self.known.items()))
            if self.selected is not None: self.status.emit('Đã khôi phục: đang nhận ảnh từ nhóm ID '+str(self.selected))
            else: self.status.emit('Bot đã kết nối. Gửi tin nhắn trong nhóm, chọn nhóm rồi bấm Nhận ảnh từ nhóm.')
            if not me.get('can_read_all_group_messages',False):
                self.status.emit('Bot còn bật Group Privacy: để nhận ảnh thông thường, tắt privacy ở @BotFather rồi thêm lại bot, hoặc cấp quyền quản trị trong nhóm.')
            row=self.db.execute('SELECT offset FROM bot_offsets WHERE bot=?',(self.identity,)).fetchone()
            offset=row[0] if row else 0
            while not self.stopping:
                self.drain()
                if self.stopping: break
                try:
                    updates=await api('getUpdates',offset=offset,timeout=5,allowed_updates=['message','my_chat_member'])
                    for update in updates:
                        self.drain()
                        if self.stopping: break
                        message=update.get('message',{}); chat=message.get('chat') or update.get('my_chat_member',{}).get('chat',{})
                        chat_id=chat.get('id')
                        if chat.get('type') in ('group','supergroup'): self.remember(chat_id,chat.get('title',str(chat_id)))
                        media=bot_media(message)
                        if media and self.selected==chat_id and not self.stopping:
                            file_id,ext,size=media; key=f'bot:{self.identity}:{chat_id}:{message["message_id"]}'
                            if not self.seen(key):
                                if size>20*1024*1024:
                                    self.status.emit('Bỏ qua ảnh lớn hơn giới hạn tải 20 MB của Bot API.'); self.commit(key)
                                else:
                                    info=await api('getFile',file_id=file_id)
                                    file_path=info['file_path']
                                    if '..' in file_path.split('/') or file_path.startswith('/'): raise ValueError('file_path')
                                    dest=self.target(chat_id,message['message_id'],ext); temporary=dest.with_suffix('.part')
                                    try:
                                        async with client.stream('GET','https://api.telegram.org/file/bot'+token+'/'+file_path) as response:
                                            response.raise_for_status(); total=0
                                            with temporary.open('wb') as output:
                                                async for chunk in response.aiter_bytes():
                                                    total+=len(chunk)
                                                    if total>20*1024*1024: raise ValueError('size')
                                                    output.write(chunk)
                                        self.publish(temporary,dest,key,chat_id)
                                    finally: temporary.unlink(missing_ok=True)
                        offset=update['update_id']+1
                        self.db.execute('INSERT OR REPLACE INTO bot_offsets VALUES (?,?)',(self.identity,offset)); self.db.commit()
                except Exception as exc:
                    self.status.emit(bot_error_text(exc))
                    if isinstance(exc,BotAPIError) and exc.code==401: self.stage.emit('error'); return
                    await asyncio.sleep(3)
    async def account(self):
        from telethon import TelegramClient,events,errors,utils
        api_id=int(self.credentials['api_id']); api_hash=self.credentials['api_hash'].strip()
        client=TelegramClient(str(self.base/'telegram-account'),api_id,api_hash)
        await client.connect()
        async def download(event):
            chat_id=event.chat_id
            if self.selected!=chat_id or self.stopping: return
            message=event.message
            if message.photo: ext='.jpg'
            elif message.document and message.document.mime_type in SUPPORTED: ext=SUPPORTED[message.document.mime_type]
            else: return
            key=f'account:{self.identity}:{chat_id}:{message.id}'
            if self.seen(key): return
            if message.file and message.file.size and message.file.size>50*1024*1024:
                self.status.emit('Bỏ qua tệp ảnh lớn hơn 50 MB.'); return
            dest=self.target(chat_id,message.id,ext); temporary=dest.with_suffix('.part')
            try:
                await client.download_media(message,file=str(temporary))
                if temporary.exists(): self.publish(temporary,dest,key,chat_id)
            except Exception as exc:
                self.status.emit('Không tải được một ảnh ('+type(exc).__name__+').')
            finally: temporary.unlink(missing_ok=True)
        client.add_event_handler(download,events.NewMessage())
        async def ready():
            self.identity=str((await client.get_me()).id)
            async for dialog in client.iter_dialogs():
                if dialog.is_group: self.known[utils.get_peer_id(dialog.entity)]=dialog.name
            self.groups.emit(list(self.known.items())); self.stage.emit('ready')
            self.status.emit('Đang nhận ảnh từ nhóm ID '+str(self.selected) if self.selected is not None else 'Đã đăng nhập. Chọn nhóm rồi bấm Nhận ảnh từ nhóm.')
        try:
            authorized=await client.is_user_authorized()
            if authorized: await ready()
            else: self.stage.emit('phone')
            while not self.stopping:
                while not self.commands.empty():
                    name,value=self.commands.get_nowait()
                    try:
                        if name=='stop': self.stopping=True
                        elif name=='select' and authorized: self.selected=value; self.status.emit('Đang nhận ảnh mới từ nhóm ID '+str(value))
                        elif name=='phone' and not authorized:
                            phone=value.strip(); await client.send_code_request(phone); self.stage.emit('code')
                        elif name=='code' and not authorized:
                            try: await client.sign_in(phone=phone,code=value.strip())
                            except errors.SessionPasswordNeededError: self.stage.emit('password'); continue
                            authorized=True; await ready()
                        elif name=='password' and not authorized:
                            await client.sign_in(password=value); authorized=True; await ready()
                        elif name=='refresh' and authorized: await ready()
                    except errors.FloodWaitError as exc: self.status.emit('Telegram yêu cầu chờ '+str(exc.seconds)+' giây trước khi thử lại.')
                    except Exception as exc: self.status.emit('Chưa thực hiện được ('+type(exc).__name__+'). Kiểm tra lại và thử lại.')
                await asyncio.sleep(.15)
        finally:
            await client.disconnect()
