import os,tempfile,unittest,time
from concurrent.futures import Future
import printing
from spooler import WindowsSpooler
from test_spooler import FakeAPI
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PySide6.QtCore import QObject,Signal,Qt
from PySide6.QtGui import QImage,QColor
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtPdf import QPdfDocument
with patch.dict(os.environ,{'LOCALAPPDATA':tempfile.gettempdir()}):
    import app as application
from connection_store import ConnectionStore
from test_connection import Vault

class FakePrintWorker(QObject):
    finished=Signal(); progress=Signal(int,int,str); spool_job=Signal(int)
    def __init__(self,paths,settings,parent=None):
        super().__init__(parent); self.paths=list(paths); self.settings=dict(settings); self.error=None; self.started=False; self.cancelled=False; self.paused=False
    def start(self): self.started=True
    def pause(self): self.paused=True
    def resume(self): self.paused=False
    def cancel(self): self.cancelled=True

class ImmediatePool:
    def submit(self,fn,*args):
        future=Future()
        try: future.set_result(fn(*args))
        except Exception as exc: future.set_exception(exc)
        return future
    def shutdown(self,*args,**kwargs): pass

class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.qt=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.base=Path(self.temp.name); self.vault=Vault()
        self.patches=[patch.object(application,'BASE',self.base),
            patch('telegram_ui.ConnectionStore',side_effect=lambda base:ConnectionStore(base,self.vault)),
            patch.object(application.QPrinterInfo,'availablePrinters',return_value=[SimpleNamespace(printerName=lambda:'Test printer')]),
            patch.object(application,'PrintWorker',FakePrintWorker),
            patch.object(application,'NativePrintJob',FakePrintWorker),
            patch.object(application,'WindowsSpooler',return_value=SimpleNamespace(available=False))]
        for p in self.patches: p.start()
        self.windows=[]; self.window=self.new_window()
    def new_window(self):
        window=application.Window(); self.windows.append(window); self.qt.processEvents(); window.timer.stop(); window.spool_timer.stop(); return window
    def photo(self,name,color):
        path=self.base/name; image=QImage(300,400,QImage.Format.Format_RGB32); image.fill(QColor(color)); image.save(str(path)); return path
    def finish_print(self,window,error=None):
        if window.print_worker:
            window.print_worker.error=error; window.print_worker.finished.emit(); self.qt.processEvents(); self.qt.processEvents()
    def tearDown(self):
        for w in self.windows:
            if w.print_worker: self.finish_print(w)
            if not w.closed: w.close()
        self.qt.processEvents()
        import shiboken6
        for window in self.windows:
            if shiboken6.isValid(window): shiboken6.delete(window)
        self.windows.clear(); self.window=None; self.qt.processEvents()
        for p in reversed(self.patches): p.stop()
        self.temp.cleanup()
    def test_thumbnails_checkbox_batch_selection_and_manual_print(self):
        w=self.window
        for name,color in [('one.jpg','blue'),('two.jpg','red')]: self.assertTrue(w.enqueue(self.photo(name,color),False))
        self.assertFalse(w.list.item(0).icon().isNull()); self.assertEqual(w.list.item(0).text(),'two.jpg')
        w.check_all(True); self.assertEqual(len(w.selected_entries()),2)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes): w.manual()
        self.qt.processEvents(); self.assertTrue(w.print_worker.started); self.assertEqual(len(w.print_worker.paths),2)
        self.finish_print(w); self.assertEqual(w.db.execute("SELECT COUNT(*) FROM jobs WHERE state='submitted'").fetchone()[0],2)
        w.check_all(False)
        with self.assertRaises(ValueError): w.selected_entries()
    def test_auto_receiving_prints_without_confirmation_and_no_duplicate(self):
        w=self.window; w.auto.setChecked(True); path=self.photo('auto.png','green')
        with patch.object(QMessageBox,'question',side_effect=AssertionError('Auto must not ask for confirmation')):
            w.enqueue(path,True); self.qt.processEvents()
            self.assertTrue(w.print_worker.started); self.assertEqual(w.print_worker.paths,[path])
            w.enqueue(path,True); self.assertEqual(len(w.print_queue),0)
            self.finish_print(w)
        self.assertEqual(w.db.execute('SELECT state FROM jobs').fetchone()[0],'submitted')
    def test_add_files_also_prints_immediately_when_auto_enabled(self):
        w=self.window; path=self.photo('import.png','purple'); w.auto.setChecked(True)
        with patch.object(application.QFileDialog,'getOpenFileNames',return_value=([str(path)],'')):
            w.add_files()
        self.qt.processEvents(); self.assertIsNotNone(w.print_worker); self.assertEqual(w.print_worker.paths,[path]); self.finish_print(w)
    def test_old_photo_does_not_auto_print_when_auto_is_enabled(self):
        w=self.window; path=self.photo('old.png','yellow'); w.enqueue(path,False)
        w.auto.setChecked(True); self.qt.processEvents(); self.assertIsNone(w.print_worker)
    def test_new_photo_keeps_existing_manual_selection(self):
        w=self.window; w.enqueue(self.photo('one.png','blue'),False); w.check_all(True)
        w.telegram_dialog.active=True; w.telegram_dialog.receive(str(self.photo('two.png','red')))
        self.assertEqual([path.name for path,_ in w.selected_entries()],['one.png'])
    def test_save_and_restore_print_settings_and_auto(self):
        w=self.window; w.paper.setCurrentText('A6'); w.photo.setCurrentText('4 × 6 cm'); w.count.setValue(7)
        w.auto.setChecked(True); w.save_settings(); w.close()
        restored=self.new_window()
        self.assertEqual(restored.paper.currentText(),'A6'); self.assertEqual(restored.photo.currentText(),'4 × 6 cm')
        self.assertEqual(restored.count.value(),7); self.assertEqual(restored.printer.currentText(),'Test printer')
        self.assertTrue(restored.auto.isChecked())
    def test_library_is_restored_without_auto_printing_old_images(self):
        w=self.window; w.enqueue(self.photo('old.png','orange'),False); w.auto.setChecked(True); w.save_settings(); w.close()
        restored=self.new_window(); self.assertEqual(restored.list.count(),1); self.assertTrue(restored.auto.isChecked())
        self.assertIsNone(restored.print_worker)
    def test_multi_image_pdf_shares_page(self):
        w=self.window; paths=[self.photo('one.png','red'),self.photo('two.png','blue')]
        settings=w.snapshot(); settings.update(paper='A5',count=4)
        output=self.base/'batch.pdf'
        application.render(application.create_printer(settings,output),paths,settings)
        document=QPdfDocument(); document.load(str(output))
        self.assertEqual(document.pageCount(),1)
        self.assertAlmostEqual(document.pagePointSize(0).width(),148*72/25.4,delta=1)
        document.close()
    def test_auto_queue_cancellation_and_snapshot(self):
        w=self.window; w.auto.setChecked(True); w.count.setValue(3); w.enqueue(self.photo('one.png','red'),True)
        self.qt.processEvents(); self.assertEqual(w.print_worker.settings['count'],3)
        w.count.setValue(6); w.enqueue(self.photo('two.png','blue'),True)
        self.assertEqual(w.print_queue[0]['settings']['count'],6)
        w.auto.setChecked(False); self.assertEqual(len(w.print_queue),0)
        self.assertTrue(w.print_worker.started); self.finish_print(w)
        states=[r[0] for r in w.db.execute('SELECT state FROM jobs')]
        self.assertCountEqual(states,['submitted','cancelled'])
    def test_print_failure_stops_auto_and_marks_review(self):
        w=self.window; w.auto.setChecked(True); w.enqueue(self.photo('one.png','red'),True); self.qt.processEvents()
        self.finish_print(w,error='Printer unavailable')
        self.assertFalse(w.auto.isChecked()); self.assertIn('Printer unavailable',w.status.text())
        self.assertEqual(w.db.execute('SELECT state FROM jobs').fetchone()[0],'review')
    def test_stale_queue_is_recovered_and_manual_reprint_is_allowed(self):
        w=self.window; path=self.photo('old.png','orange'); w.enqueue(path,False)
        digest=next(iter(w.pending)); w.db.execute('INSERT INTO jobs VALUES (?,?,?)',(digest,'sending',str(path))); w.db.commit(); w.close()
        restored=self.new_window(); self.assertEqual(restored.recovered,1)
        self.assertEqual(restored.db.execute('SELECT state FROM jobs').fetchone()[0],'review')
        restored.send_batch([(path,digest)]); self.qt.processEvents()
        self.assertIsNotNone(restored.print_worker); self.finish_print(restored)
    def test_busy_photo_is_skipped_but_other_photos_can_print(self):
        w=self.window; one=self.photo('one.png','red'); two=self.photo('two.png','blue')
        w.enqueue(one,False); w.enqueue(two,False); entries=[(Path(path),digest) for digest,path in w.pending.items()]
        w.send_batch(entries[:1]); self.qt.processEvents()
        w.send_batch(entries)
        self.assertEqual(len(w.print_queue),1); self.assertEqual(len(w.print_queue[0]['entries']),1)
        self.assertEqual(w.print_queue[0]['entries'][0][0],two)
        self.finish_print(w); self.finish_print(w)
    def test_clicking_same_busy_photo_again_does_not_throw(self):
        w=self.window; path=self.photo('one.png','red'); w.enqueue(path,False)
        entry=(path,next(iter(w.pending))); w.send_batch([entry]); self.qt.processEvents()
        w.send_batch([entry]); self.assertEqual(len(w.print_queue),0)
        self.assertIn('không xếp thêm bản trùng',w.status.text()); self.finish_print(w)
    def test_manual_can_reprint_submitted_image_when_auto_is_off(self):
        w=self.window; w.enqueue(self.photo('again.png','red'),False); w.check_all(True)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):
            for _ in range(2):
                w.manual(); self.qt.processEvents(); self.assertIsNotNone(w.print_worker); self.finish_print(w)
        self.assertFalse(w.auto.isChecked()); self.assertEqual(w.queue_table.topLevelItemCount(),2)
    def test_manual_microsoft_pdf_real_export_never_uses_native_driver(self):
        w=self.window; w.printer.addItem('Microsoft Print to PDF'); w.printer.setCurrentText('Microsoft Print to PDF')
        w.enqueue(self.photo('one.png','red'),False); w.enqueue(self.photo('two.png','blue'),False); w.check_all(True)
        output=self.base/'ảnh thử.pdf'
        with patch.object(application,'PrintWorker',printing.PrintWorker),patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes),patch.object(application.QFileDialog,'getSaveFileName',return_value=(str(output),'')),patch.object(printing.QPrinterInfo,'printerInfo',side_effect=AssertionError('Must not use a native PDF driver')):
            w.manual(); self.qt.processEvents(); worker=w.print_worker; self.assertIsNotNone(worker)
            self.assertTrue(worker.wait(10000)); self.assertIsNone(worker.error); self.qt.processEvents(); self.qt.processEvents()
        self.assertIsNone(w.print_worker); self.assertTrue(output.exists())
        pdf=QPdfDocument(); pdf.load(str(output)); self.assertEqual(pdf.pageCount(),1); pdf.close()
        self.assertEqual(w.db.execute('SELECT COUNT(*) FROM jobs WHERE state=?',('exported',)).fetchone()[0],2)
        run=next(iter(w.run_data.values())); self.assertEqual(run['state'],'exported'); self.assertEqual(run['done'],8)
    def test_cancel_manual_pdf_does_not_reserve_or_lock_photo(self):
        w=self.window; w.printer.setCurrentText(application.PDF_PRINTER); w.enqueue(self.photo('one.png','red'),False); w.check_all(True)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes),patch.object(application.QFileDialog,'getSaveFileName',return_value=('','')):
            w.manual()
        self.assertEqual(len(w.print_queue),0); self.assertIsNone(w.print_worker)
        self.assertEqual(w.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],0)
        self.assertEqual(w.queue_table.topLevelItemCount(),0)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes),patch.object(application.QFileDialog,'getSaveFileName',return_value=(str(self.base/'retry.pdf'),'')):
            w.manual(); self.qt.processEvents(); self.assertIsNotNone(w.print_worker); self.finish_print(w)
    def test_explicit_pdf_export_without_available_physical_printer(self):
        w=self.window; w.printer.setCurrentIndex(-1); w.enqueue(self.photo('one.png','blue'),False); w.check_all(True)
        with patch.object(application.QFileDialog,'getSaveFileName',return_value=(str(self.base/'export.pdf'),'')):
            w.pdf(); self.qt.processEvents()
        self.assertEqual(w.print_worker.settings['pdf_output'],str(self.base/'export.pdf')); self.finish_print(w)
    def test_automatic_pdf_chooses_file_without_any_dialog(self):
        w=self.window; w.printer.setCurrentText(application.PDF_PRINTER); w.auto.setChecked(True)
        with patch.object(application.QFileDialog,'getSaveFileName',side_effect=AssertionError('Auto must not open a save dialog')):
            w.enqueue(self.photo('auto.png','green'),True); self.qt.processEvents()
        self.assertTrue(Path(w.print_worker.settings['pdf_output']).is_relative_to(Path(w.pdf_folder.text())))
        self.finish_print(w)
    def test_no_selection_does_not_start_manual_print(self):
        w=self.window
        with patch.object(w,'error') as error: w.manual(); error.assert_called_once()
        self.assertIsNone(w.print_worker); self.assertEqual(w.queue_table.topLevelItemCount(),0)
    def test_progress_pause_resume_cancel_and_clear(self):
        w=self.window; w.enqueue(self.photo('one.png','red'),False); w.check_all(True)
        w.send_batch(w.selected_entries(),pdf_output=str(self.base/'progress.pdf')); self.qt.processEvents()
        worker=w.print_worker; worker.progress.emit(2,4,str(self.base/'one.png')); self.qt.processEvents()
        self.assertEqual(w.queue_table.topLevelItem(0).text(2),'2/4'); self.assertEqual(w.queue_table.topLevelItem(0).text(1),'one.png')
        w.pause_printing(); self.assertTrue(worker.paused); self.assertTrue(w.queue_paused)
        w.resume_printing(); self.assertFalse(worker.paused); self.assertFalse(w.queue_paused)
        w.clear_progress(); self.assertEqual(w.queue_table.topLevelItemCount(),1)
        w.cancel_selected_print(); self.assertTrue(worker.cancelled); self.finish_print(w)
        self.assertEqual(next(iter(w.run_data.values()))['state'],'cancelled')
        w.clear_progress(); self.assertEqual(w.queue_table.topLevelItemCount(),0); self.assertEqual(w.list.count(),1)
    def test_paused_queue_does_not_start_until_resume(self):
        w=self.window; w.enqueue(self.photo('one.png','blue'),False); w.check_all(True); w.pause_printing()
        w.send_batch(w.selected_entries()); self.qt.processEvents(); self.assertIsNone(w.print_worker)
        self.assertEqual(len(w.print_queue),1); w.resume_printing(); self.assertIsNotNone(w.print_worker); self.finish_print(w)
    def use_spooler(self,w,api):
        w.spooler=WindowsSpooler(api); w.spool_pool.shutdown(wait=False); w.spool_command_pool.shutdown(wait=False)
        w.spool_pool=ImmediatePool(); w.spool_command_pool=ImmediatePool()
    def spool_job(self):
        w=self.window; api=FakeAPI(); api.device=0x80; self.use_spooler(w,api)
        path=self.photo('offline.png','blue'); w.enqueue(path,False); entry=(path,next(iter(w.pending)))
        w.send_batch([entry]); self.qt.processEvents(); job=w.current_print_job
        api.jobs=[{'JobId':71,'pDocument':job['settings']['document'],'Status':0}]
        w.print_worker.spool_job.emit(71); self.qt.processEvents(); self.finish_print(w)
        return w,api,job
    def test_offline_spool_job_is_not_finished_and_cancel_calls_windows(self):
        w,api,job=self.spool_job(); w.poll_spooler(); w.poll_spooler()
        self.assertIn(job['id'],w.spool_jobs); self.assertEqual(w.run_data[job['id']]['state'],'spool_wait')
        self.assertIn('Offline',w.run_items[job['id']].text(3))
        w.cancel_selected_print(); self.assertEqual(api.commands[-1],('Test printer',71,0,None,5))
        self.assertNotEqual(w.run_data[job['id']]['state'],'cancelled')
        for _ in range(3): w.poll_spooler()
        self.assertNotIn(job['id'],w.spool_jobs); self.assertEqual(w.run_data[job['id']]['state'],'cancelled')
    def test_spool_query_error_never_claims_completion(self):
        w,api,job=self.spool_job(); api.fail_read=True
        w.poll_spooler(); w.poll_spooler()
        self.assertEqual(w.run_data[job['id']]['state'],'spool_error'); self.assertIn(job['id'],w.spool_jobs)
        self.assertIn(job['entries'][0][1],w.active_digests())
    def test_pause_resume_calls_windows_for_pending_spool_job(self):
        w,api,job=self.spool_job(); w.pause_printing(); w.resume_printing()
        self.assertEqual([call[-1] for call in api.commands],[1,2])
    def test_clear_progress_keeps_offline_spool_job(self):
        w,api,job=self.spool_job(); w.clear_progress()
        self.assertIn(job['id'],w.run_data); self.assertEqual(w.queue_table.topLevelItemCount(),1)
    def test_reopen_restores_pending_windows_job_and_can_cancel_it(self):
        w,api,job=self.spool_job(); w.close()
        with patch.object(application,'WindowsSpooler',return_value=WindowsSpooler(api)):
            restored=self.new_window()
        self.use_spooler(restored,api)
        self.assertIn(job['id'],restored.spool_jobs)
        restored.cancel_selected_print(); self.assertEqual(api.commands[-1][-1],5)
        for _ in range(3): restored.poll_spooler()
        self.assertNotIn(job['id'],restored.spool_jobs)
    def test_present_printed_flag_is_not_complete_until_queue_removes_job(self):
        w,api,job=self.spool_job(); api.jobs[0]['Status']=0x80; api.device=0
        w.poll_spooler(); w.poll_spooler()
        self.assertEqual(w.run_data[job['id']]['state'],'spool_wait'); self.assertIn(job['id'],w.spool_jobs)
        api.jobs=[]
        for _ in range(3): w.poll_spooler()
        self.assertEqual(w.run_data[job['id']]['state'],'completed'); self.assertNotIn(job['id'],w.spool_jobs)
        self.assertNotIn(job['entries'][0][1],w.active_digests())
    def test_windows_cancel_denied_remains_pending_and_reports_error(self):
        w,api,job=self.spool_job(); api.fail_command=True; w.cancel_selected_print()
        for _ in range(3): w.poll_spooler()
        self.assertIn(job['id'],w.spool_jobs); self.assertEqual(w.run_data[job['id']]['state'],'spool_error')
        self.assertIn('PermissionError',w.run_items[job['id']].text(3)); self.assertEqual(len(api.jobs),1)
    def test_gallery_retains_only_100_newest_records(self):
        w=self.window
        for index in range(101): w.enqueue(self.photo(f'{index}.png',f'#{index:06x}'),False,added=float(index))
        self.assertEqual(w.list.count(),100); self.assertEqual(w.list.item(0).text(),'100.png')
        self.assertEqual(w.list.item(99).text(),'1.png')
        self.assertEqual(w.db.execute('SELECT COUNT(*) FROM images').fetchone()[0],100)
        self.assertEqual(len(w.pending),100); self.assertTrue((self.base/'0.png').is_file())
    def test_older_restoration_cannot_push_live_photo_down(self):
        w=self.window
        w.enqueue(self.photo('old1.png','red'),False,added=1)
        w.enqueue(self.photo('new.png','blue'),False,added=3)
        w.enqueue(self.photo('old2.png','green'),False,added=2)
        self.assertEqual([w.list.item(i).text() for i in range(3)],['new.png','old2.png','old1.png'])
        w.close(); restored=self.new_window()
        self.assertEqual([restored.list.item(i).text() for i in range(3)],['new.png','old2.png','old1.png'])
    def test_clear_gallery_keeps_files_active_print_and_allows_manual_reimport(self):
        w=self.window; path=self.photo('clear.png','red'); w.enqueue(path,False); w.check_all(True)
        w.send_batch(w.selected_entries(),pdf_output=str(self.base/'clear.pdf')); self.qt.processEvents()
        w.clear_gallery(); self.assertEqual(w.list.count(),0); self.assertTrue(path.exists())
        self.assertIsNotNone(w.print_worker); self.assertEqual(w.db.execute('SELECT state FROM jobs').fetchone()[0],'sending')
        w.enqueue(path,False); self.assertEqual(w.list.count(),0)
        self.finish_print(w)
        with patch.object(application.QFileDialog,'getOpenFileNames',return_value=([str(path)],'')): w.add_files()
        self.assertEqual(w.list.count(),1)
    def test_clear_stays_empty_after_restart(self):
        w=self.window; path=self.photo('clear.png','blue'); w.enqueue(path,False); w.clear_gallery(); w.close()
        restored=self.new_window(); self.assertEqual(restored.list.count(),0)
        restored.enqueue(path,False); self.assertEqual(restored.list.count(),0); self.assertTrue(path.exists())
    def test_alt_digit_shortcuts_print_latest_without_changing_selection(self):
        from PySide6.QtTest import QTest
        w=self.window; old=self.photo('old.png','red'); new=self.photo('new.png','blue')
        w.enqueue(old,False); w.enqueue(new,False); w.list.item(1).setCheckState(Qt.CheckState.Checked)
        w.show(); w.activateWindow(); w.list.setFocus(); self.qt.processEvents()
        with patch.object(QMessageBox,'question',side_effect=AssertionError('Normal hotkey must print immediately')):
            QTest.keyClick(w.list,Qt.Key.Key_1,Qt.KeyboardModifier.AltModifier); self.qt.processEvents()
            self.assertIsNotNone(w.print_worker); self.assertEqual(w.print_worker.paths,[new]); self.finish_print(w)
            QTest.keyClick(w.list,Qt.Key.Key_2,Qt.KeyboardModifier.AltModifier); self.qt.processEvents()
            self.assertEqual(w.print_worker.paths,[old]); self.finish_print(w)
        self.assertEqual([path for path,_ in w.selected_entries()],[old])
    def test_alt_a_only_prints_new_unsubmitted_images(self):
        w=self.window
        for name,color in [('done.png','red'),('new1.png','blue'),('review.png','green'),('new2.png','yellow')]: w.enqueue(self.photo(name,color),False)
        identities={Path(path).name:identity for identity,path in w.pending.items()}
        w.db.execute('INSERT INTO jobs VALUES (?,?,?)',(identities['done.png'],'submitted',str(self.base/'done.png')))
        w.db.execute('INSERT INTO jobs VALUES (?,?,?)',(identities['review.png'],'review',str(self.base/'review.png'))); w.db.commit()
        with patch.object(QMessageBox,'question',side_effect=AssertionError('Alt+A must not ask about already-reviewed photos')):
            w.print_all_new(); self.qt.processEvents()
        self.assertEqual([path.name for path in w.print_worker.paths],['new2.png','new1.png'])
        w.print_all_new(); self.assertEqual(len(w.print_queue),0); self.assertIn('Không có ảnh mới',w.status.text()); self.finish_print(w)
    def test_missing_hotkey_position_does_not_print(self):
        w=self.window; w.print_latest(9); self.assertIsNone(w.print_worker); self.assertIn('thứ 9',w.status.text())
    def test_telegram_resend_same_bytes_creates_new_card_and_auto_job(self):
        w=self.window; first=self.photo('10.jpg','red'); second=self.base/'11.jpg'; second.write_bytes(first.read_bytes())
        w.telegram_dialog.active=True; w.auto.setChecked(True)
        w.telegram_dialog.receive(str(first)); self.qt.processEvents(); w.telegram_dialog.receive(str(second)); self.qt.processEvents()
        self.assertEqual(w.list.count(),2); self.assertEqual(w.list.item(0).text(),'11.jpg')
        self.assertEqual(len(w.print_queue),1); self.assertEqual(w.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],2)
        w.telegram_dialog.receive(str(second)); self.assertEqual(w.list.count(),2); self.assertEqual(len(w.print_queue),1)
        self.finish_print(w); self.finish_print(w); w.close()
        restored=self.new_window(); self.assertEqual(restored.list.count(),2)
        self.assertEqual([restored.list.item(i).text() for i in range(2)],['11.jpg','10.jpg'])
    def test_clear_all_progress_deletes_finished_history_beyond_visible_limit(self):
        w=self.window
        for index in range(120):
            w.db.execute('INSERT INTO print_runs VALUES (?,?,?,?,?,?,?,?,?,?,?)',(f'old-{index}',float(index),'old','exported',4,4,'photo.jpg','PDF','out.pdf','old-doc',None))
        w.db.execute('INSERT INTO print_runs VALUES (?,?,?,?,?,?,?,?,?,?,?)',('hold',999.,'pending','spool_wait',4,4,'photo.jpg','RICOH','','hold-doc',71)); w.db.commit()
        w.clear_progress()
        self.assertEqual(w.db.execute('SELECT id FROM print_runs').fetchall(),[('hold',)])
    def test_folder_scan_does_not_duplicate_a_live_telegram_path(self):
        w=self.window; path=self.photo('10.jpg','red'); w.telegram_dialog.active=True
        w.telegram_dialog.receive(str(path)); self.assertEqual(w.list.count(),1)
        w.enqueue(path,False); self.assertEqual(w.list.count(),1)
    def test_manual_print_never_asks_confirmation_even_for_review(self):
        w=self.window; one=self.photo('review.png','red'); two=self.photo('new.png','blue')
        w.enqueue(one,False); w.enqueue(two,False); w.check_all(True)
        identity=next(identity for identity,path in w.pending.items() if Path(path)==one)
        w.db.execute('INSERT INTO jobs VALUES (?,?,?)',(identity,'review',str(one))); w.db.commit()
        with patch.object(QMessageBox,'question',side_effect=AssertionError('Manual printing must not ask Yes/No')):
            w.manual(); self.qt.processEvents()
        self.assertIsNotNone(w.print_worker); self.assertEqual(len(w.print_worker.paths),2); self.finish_print(w)
if __name__=='__main__': unittest.main()
