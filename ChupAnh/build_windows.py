"""Build a portable Windows folder and ZIP; no credentials or user photos included."""
import argparse,shutil,subprocess,sys
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description='Dong goi ChupAnh thanh Windows EXE')
    parser.add_argument('--skip-install',action='store_true')
    args=parser.parse_args()
    if sys.platform!='win32': raise SystemExit('Can chay dong goi tren Windows. Hoac tai ban EXE tu GitHub Releases.')
    root=Path(__file__).resolve().parent
    if not args.skip_install:
        subprocess.run([sys.executable,'-m','pip','install','-r',str(root/'requirements-build.txt')],cwd=root,check=True)
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--windowed',
        '--name','ChupAnh','--distpath',str(root/'dist'),'--workpath',str(root/'build'/'pyinstaller'),
        '--specpath',str(root/'build'),'--collect-submodules','telethon','--collect-submodules','keyring.backends',
        '--copy-metadata','keyring','--hidden-import','keyring.backends.Windows',
        '--hidden-import','win32print','--hidden-import','win32timezone',str(root/'app.py')]
    subprocess.run(command,cwd=root,check=True)
    folder=root/'dist'/'ChupAnh'; exe=folder/'ChupAnh.exe'
    if not exe.is_file(): raise RuntimeError('Khong tim thay EXE sau dong goi')
    report=root/'dist'/'smoke-report.json'
    subprocess.run([str(exe),'--smoke-test','--smoke-report',str(report)],cwd=root,check=True,timeout=120)
    shutil.copyfile(root/'README.md',folder/'HUONG_DAN.md')
    archive=shutil.make_archive(str(root/'dist'/'ChupAnh-Windows'),'zip',root_dir=root/'dist',base_dir='ChupAnh')
    print('Dong goi thanh cong:',archive)
    print('Giai nen toan bo ZIP, mo ChupAnh/ChupAnh.exe. Giu thu muc _internal di kem.')
if __name__=='__main__': main()
