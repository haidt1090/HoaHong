"""Read/control only this app's identified Windows spool jobs; never purge a printer."""
import sys

class SpoolerUnavailable(RuntimeError): pass
class WindowsSpooler:
    def __init__(self,api=None):
        self.api=api
        if api is None and sys.platform=='win32':
            try:
                import win32print
                self.api=win32print
            except ImportError: pass
        self.available=self.api is not None
    def _open(self,printer):
        if not self.available: raise SpoolerUnavailable('Cần Windows và pywin32; chạy lại CAI_DAT.bat.')
        return self.api.OpenPrinter(printer)
    def read(self,printer,document,job_id=None):
        handle=self._open(printer)
        try:
            jobs=self.api.EnumJobs(handle,0,9999,1)
            matches=[job for job in jobs if job.get('pDocument')==document and (job_id is None or job.get('JobId')==job_id)]
            if not matches: return {'exists':False,'job_id':job_id}
            job=matches[0]
            try:
                device=self.api.GetPrinter(handle,2); printer_status=device.get('Status',0)
                if device.get('Attributes',0)&0x400: printer_status|=0x80
            except Exception: printer_status=0
            return {'exists':True,'job_id':job['JobId'],'status':job.get('Status',0),
                    'text':job.get('pStatus') or '', 'printer_status':printer_status,
                    'pages':job.get('TotalPages',0),'printed':job.get('PagesPrinted',0)}
        finally: self.api.ClosePrinter(handle)
    def find_job_id(self,printer,document):
        info=self.read(printer,document)
        return info.get('job_id') if info['exists'] else None
    def command(self,printer,document,job_id,action):
        codes={'pause':1,'resume':2,'cancel':5}  # JOB_CONTROL_PAUSE, RESUME, DELETE
        if action not in codes: raise ValueError('Lệnh hàng đợi không hợp lệ')
        handle=self._open(printer)
        try:
            # Verify both job ID and unique document name: IDs may be reused by Windows.
            matches=[job for job in self.api.EnumJobs(handle,0,9999,1)
                     if job.get('pDocument')==document and (job_id is None or job.get('JobId')==job_id)]
            if not matches: return {'exists':False,'job_id':job_id}
            identified=matches[0]['JobId']
            self.api.SetJob(handle,identified,0,None,codes[action])
            return {'exists':True,'job_id':identified,'action':action}
        finally: self.api.ClosePrinter(handle)

def status_text(info):
    status=info.get('status',0); device=info.get('printer_status',0)
    if status&0x104: return 'Windows đang xóa lệnh — chưa hoàn tất'
    if device&0x80 or status&0x20: return 'Tạm dừng; máy in Offline — chưa hoàn tất' if status&0x1 else 'Máy in Offline — chưa hoàn tất'
    if status&0x1: return 'Đã tạm dừng tại máy in'
    if device&0x10 or status&0x40: return 'Hết giấy — chưa hoàn tất'
    if status&(0x2|0x200|0x400) or device&(0x2|0x100000|0x400000): return 'Máy in báo lỗi — chưa hoàn tất'
    if status&0x10: return 'Windows đang in'
    if status&0x8: return 'Windows đang nhận dữ liệu'
    if status&(0x80|0x1000): return 'Đã gửi/in — còn trong hàng đợi'
    return 'Còn trong hàng đợi Windows — chưa hoàn tất'
