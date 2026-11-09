import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QObject,Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication,QWidget,QLabel,QCheckBox,QListWidget
from connection_store import ConnectionStore
from telegram_ui import TelegramDialog

class Vault:
    def __init__(self): self.values={}
    def get_password(self,service,key): return self.values.get((service,key))
    def set_password(self,service,key,value): self.values[service,key]=value
    def delete_password(self,service,key): del self.values[service,key]
class StoreTests(unittest.TestCase):
    def test_save_restore_secret_is_not_in_config_and_forget(self):
        with tempfile.TemporaryDirectory() as d:
            vault=Vault(); store=ConnectionStore(d,vault)
            store.save('bot',{'token':'123:secret'},-123,'ChupAnh',True)
            text=store.path.read_text()
            self.assertNotIn('123:secret',text); self.assertNotIn('credentials',json.loads(text))
            restored=ConnectionStore(d,vault).load()
            self.assertEqual(restored['credentials']['token'],'123:secret')
            self.assertEqual(restored['group_id'],-123); self.assertTrue(restored['auto_connect'])
            store.forget(); self.assertIsNone(store.load()); self.assertEqual(vault.values,{})
    def test_account_credentials_and_opt_out(self):
        with tempfile.TemporaryDirectory() as d:
            store=ConnectionStore(d,Vault())
            store.save('account',{'api_id':'123','api_hash':'secret'},-1,'Test',False)
            self.assertFalse(store.load()['auto_connect'])
            self.assertNotIn('secret',store.path.read_text())
    def test_no_plaintext_fallback_if_vault_fails(self):
        class Broken(Vault):
            def set_password(self,*args): raise RuntimeError('unavailable')
        with tempfile.TemporaryDirectory() as d:
            store=ConnectionStore(d,Broken())
            with self.assertRaises(RuntimeError): store.save('bot',{'token':'123:secret'},-1,'Test')
            self.assertFalse(store.path.exists())

class Worker(QObject):
    status=Signal(str); groups=Signal(list); image=Signal(str); stage=Signal(str); finished=Signal()
    def __init__(self,mode,credentials,base,parent=None):
        super().__init__(parent); self.selected=None; self.known={}; self.commands=[]; self.started=False
    def command(self,name,value=None): self.commands.append((name,value))
    def start(self): self.started=True; self.stage.emit('ready')
class Owner(QWidget):
    def __init__(self):
        super().__init__(); self.auto=QCheckBox(); self.status=QLabel(); self.list=QListWidget(); self.received=[]
    def enqueue(self,path,auto,**kwargs): self.received.append((path,auto)); self.list.addItem(str(path)); return True

class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])
    def test_close_keeps_receiving_save_and_startup_select_before_polling(self):
        with tempfile.TemporaryDirectory() as d:
            store=ConnectionStore(d,Vault()); owner=Owner()
            with patch('telegram_ui.ConnectionStore',return_value=store),patch('telegram_ui.TelegramWorker',Worker):
                dialog=TelegramDialog(owner,d); dialog.token.setText('123:test'); dialog.connect_source()
                dialog.set_groups([(-123,'ChupAnh')]); dialog.select(); dialog.save_connection()
                worker=dialog.worker; event=QCloseEvent(); dialog.closeEvent(event)
                self.assertTrue(event.isAccepted()); self.assertTrue(dialog.active)
                self.assertNotIn(('stop',None),worker.commands)
                owner.auto.setChecked(True); worker.image.emit(str(Path(d)/'test.jpg'))
                self.assertEqual(owner.received,[(Path(d)/'test.jpg',True)])
                restarted=TelegramDialog(owner,d); restarted.restore_startup()
                self.assertTrue(restarted.worker.started); self.assertEqual(restarted.worker.selected,-123)
                self.assertTrue(owner.auto.isChecked())
                self.assertEqual(restarted.token.text(),'123:test')
                dialog.stop(); self.assertIn(('stop',None),worker.commands)
                self.assertFalse(owner.auto.isChecked())
                worker.finished.emit(); restarted.worker.finished.emit()
                dialog.close(); restarted.close(); owner.close()
    def test_startup_opt_out(self):
        with tempfile.TemporaryDirectory() as d:
            store=ConnectionStore(d,Vault()); store.save('bot',{'token':'123:test'},-1,'Test',False)
            with patch('telegram_ui.ConnectionStore',return_value=store),patch('telegram_ui.TelegramWorker',Worker):
                owner=Owner(); dialog=TelegramDialog(owner,d); dialog.restore_startup()
                self.assertIsNone(dialog.worker); dialog.close(); owner.close()
if __name__=='__main__': unittest.main()
