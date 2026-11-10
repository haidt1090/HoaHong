"""Manually compile to native Windows code; no user data or secrets are bundled."""
import argparse,shutil,subprocess,sys,struct
from setup_environment import install_requirements
from pathlib import Path

def compiler_command(root):
    return [sys.executable,'-m','nuitka','--mode=standalone','--mingw64',
        '--enable-plugins=pyside6','--include-qt-plugins=sensible',
        '--windows-console-mode=disable','--output-filename=ChupAnh.exe',
        '--output-dir='+str(root/'build'/'nuitka'),
        '--include-package=telethon','--include-package=keyring.backends',
        '--include-module=keyring.backends.Windows','--include-module=win32print',
        '--include-module=win32timezone','--include-module=private_defaults',
        '--include-data-files='+str(root/'YEU_CAU.md')+'=YEU_CAU.md','--include-package-data=certifi',
        '--include-distribution-metadata=keyring',
        '--python-flag=no_docstrings','--python-flag=no_asserts','--lto=yes',
        '--assume-yes-for-downloads',str(root/'app.py')]

def main():
    parser=argparse.ArgumentParser(description='Dong goi native ChupAnh bang Nuitka (thu cong)')
    parser.add_argument('--skip-install',action='store_true'); args=parser.parse_args()
    if sys.platform!='win32': raise SystemExit('Dong goi chi chay tren Windows x64, khong build tu dong.')
    if sys.version_info[:2]!=(3,12) or struct.calcsize('P')!=8: raise SystemExit('Dung Python 3.12 x64 de dong goi; chay DONG_GOI.bat.')
    root=Path(__file__).resolve().parent
    if not args.skip_install:
        install_requirements(sys.executable,root)
    subprocess.run(compiler_command(root),cwd=root,check=True)
    candidates=list((root/'build'/'nuitka').glob('*.dist/ChupAnh.exe'))
    if not candidates: raise RuntimeError('Khong tim thay EXE sau bien dich Nuitka')
    source=max(candidates,key=lambda p:p.stat().st_mtime).parent
    folder=root/'dist'/'ChupAnh'
    if folder.is_symlink(): raise RuntimeError('Thu muc dau ra khong duoc la symbolic link')
    if folder.exists(): shutil.rmtree(folder)  # Only generated output, never LOCALAPPDATA.
    shutil.copytree(source,folder)
    report=root/'dist'/'smoke-report.json'
    subprocess.run([str(folder/'ChupAnh.exe'),'--smoke-test','--smoke-report',str(report)],cwd=root,check=True,timeout=120)
    shutil.copyfile(root/'README.md',folder/'HUONG_DAN.md')
    archive=shutil.make_archive(str(root/'dist'/'ChupAnh-Windows'),'zip',root_dir=root/'dist',base_dir='ChupAnh')
    print('Dong goi native thanh cong:',archive)
    print('Giai nen ca thu muc, mo ChupAnh.exe. Khong chi chep rieng EXE.')
    print('Nuitka lam kho trich ma hon; khong phai bao ve tuyet doi. Source public van doc duoc tren GitHub.')
if __name__=='__main__': main()
