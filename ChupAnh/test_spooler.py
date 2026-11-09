import unittest
from spooler import WindowsSpooler,status_text,SpoolerUnavailable
class FakeAPI:
    def __init__(self):
        self.jobs=[]; self.commands=[]; self.closed=[]; self.device=0; self.fail_read=False; self.fail_command=False
    def OpenPrinter(self,name): return name
    def ClosePrinter(self,handle): self.closed.append(handle)
    def EnumJobs(self,handle,start,count,level):
        if self.fail_read: raise OSError('Offline RPC')
        return [dict(job) for job in self.jobs]
    def GetPrinter(self,handle,level): return {'Status':self.device}
    def SetJob(self,handle,identity,level,data,command):
        if self.fail_command: raise PermissionError('Denied')
        self.commands.append((handle,identity,level,data,command))
        for job in self.jobs:
            if job['JobId']==identity:
                if command==1: job['Status']=job.get('Status',0)|1
                elif command==2: job['Status']=job.get('Status',0)&~1
        if command==5: self.jobs=[job for job in self.jobs if job['JobId']!=identity]
class SpoolerTests(unittest.TestCase):
    def setUp(self):
        self.api=FakeAPI(); self.api.jobs=[{'JobId':71,'pDocument':'ChupAnh test','Status':0},{'JobId':72,'pDocument':'Other app','Status':0}]
        self.spool=WindowsSpooler(self.api)
    def test_cancel_calls_set_job_for_matching_id_and_document_only(self):
        result=self.spool.command('RICOH','ChupAnh test',71,'cancel')
        self.assertTrue(result['exists']); self.assertEqual(self.api.commands,[('RICOH',71,0,None,5)])
        self.assertEqual([job['JobId'] for job in self.api.jobs],[72]); self.assertEqual(self.api.closed,['RICOH'])
    def test_reused_or_wrong_id_is_never_cancelled(self):
        result=self.spool.command('RICOH','ChupAnh test',72,'cancel')
        self.assertFalse(result['exists']); self.assertEqual(self.api.commands,[])
    def test_pause_and_resume_go_to_windows(self):
        self.spool.command('RICOH','ChupAnh test',71,'pause'); self.spool.command('RICOH','ChupAnh test',71,'resume')
        self.assertEqual([call[-1] for call in self.api.commands],[1,2])
    def test_offline_queue_stays_present(self):
        self.api.device=0x80; info=self.spool.read('RICOH','ChupAnh test',71)
        self.assertTrue(info['exists']); self.assertIn('Offline',status_text(info)); self.assertIn('chưa hoàn tất',status_text(info))
    def test_read_errors_are_not_reported_as_empty_queue(self):
        self.api.fail_read=True
        with self.assertRaises(OSError): self.spool.read('RICOH','ChupAnh test',71)
        self.assertEqual(self.api.closed,['RICOH'])
    def test_permission_error_is_not_claimed_as_cancellation(self):
        self.api.fail_command=True
        with self.assertRaises(PermissionError): self.spool.command('RICOH','ChupAnh test',71,'cancel')
        self.assertEqual(len(self.api.jobs),2); self.assertEqual(self.api.closed,['RICOH'])
    def test_printed_flag_still_reports_job_in_queue(self):
        self.assertIn('còn trong hàng đợi',status_text({'status':0x80}))
if __name__=='__main__': unittest.main()
