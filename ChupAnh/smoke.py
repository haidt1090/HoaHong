"""Offline packaged-app check. The caller supplies an isolated temporary data folder."""
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QColor
from printing import create_printer,render

def run_smoke_test(window_type,base):
    import httpx,certifi,keyring
    from telethon.tl.types import InputPeerChat
    InputPeerChat(1); httpx.URL('https://api.telegram.org')
    if not Path(certifi.where()).is_file(): raise RuntimeError('Missing HTTPS CA bundle')
    if sys.platform=='win32':
        import win32print
        from keyring.backends import Windows
        if keyring.get_keyring().priority<1: raise RuntimeError('Missing Windows credential backend')
    window=window_type(); window.show(); QApplication.processEvents()
    window.timer.stop(); window.spool_timer.stop()
    try:
        if sys.platform=='win32' and not window.spooler.available: raise RuntimeError('Missing Windows spooler backend')
        image=QImage(300,400,QImage.Format.Format_RGB32); image.fill(QColor('blue'))
        path=Path(base)/'smoke.png'; image.save(str(path))
        if not window.enqueue(path,False): raise RuntimeError('Cannot load photo thumbnail')
        output=Path(base)/'smoke.pdf'; settings=window.snapshot()
        render(create_printer(settings,output),[path],settings)
        if output.stat().st_size<1000: raise RuntimeError('Invalid PDF output')
        return {'ok':True,'version':window.windowTitle(),'pdf_bytes':output.stat().st_size,
                'thumbnail':not window.list.item(0).icon().isNull(),'windows_spooler':window.spooler.available}
    finally: window.close(); QApplication.processEvents()
