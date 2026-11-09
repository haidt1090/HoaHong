"""One complete Python 3.12 x64 environment for running or manually compiling."""
import argparse,json,struct,subprocess,sys,venv,uuid
from datetime import datetime
from pathlib import Path

def python_info(executable):
    result=subprocess.run([str(executable),'-c','import sys,struct,json; print(json.dumps([sys.version_info.major,sys.version_info.minor,struct.calcsize("P")*8]))'],check=True,capture_output=True,text=True)
    return tuple(json.loads(result.stdout.strip()))

def require_supported(info):
    if tuple(info)!=(3,12,64):
        raise RuntimeError('Can Python 3.12 x64. Cai ban 64-bit tu python.org; khong can cai Visual C++ chi de chay phan mem.')

def ensure_environment(root,target):
    if target not in ('.venv','.build-venv'): raise ValueError('Thu muc moi truong khong hop le')
    folder=Path(root)/target; executable=folder/'Scripts'/'python.exe'
    valid=False
    if executable.is_file():
        try: valid=python_info(executable)==(3,12,64)
        except (OSError,ValueError,subprocess.SubprocessError): pass
    if not valid:
        if folder.exists():
            backup=folder.with_name(target+'-old-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
            folder.rename(backup); print('Da giu moi truong cu tai:',backup)
        venv.EnvBuilder(with_pip=True).create(folder)
    require_supported(python_info(executable))
    return executable

def install_requirements(executable,root):
    require_supported(python_info(executable))
    subprocess.run([str(executable),'-m','pip','install','--upgrade','pip'],cwd=root,check=True)
    # A missing wheel is an actionable install error, never a surprise MSVC build.
    subprocess.run([str(executable),'-m','pip','install','--prefer-binary','--only-binary=zstandard,pywin32','-r',str(Path(root)/'requirements.txt')],cwd=root,check=True)
    subprocess.run([str(executable),'-m','pip','check'],cwd=root,check=True)
    subprocess.run([str(executable),'-c','import zstandard,win32print; from nuitka.Version import getNuitkaVersion; print("zstandard wheel:",zstandard.__version__,"| Nuitka:",getNuitkaVersion())'],cwd=root,check=True)

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--target',choices=['.venv','.build-venv'],default='.venv'); args=parser.parse_args()
    try:
        if sys.platform!='win32': raise RuntimeError('Bo cai moi truong nay danh cho Windows x64.')
        require_supported((*sys.version_info[:2],struct.calcsize('P')*8))
        root=Path(__file__).resolve().parent; executable=ensure_environment(root,args.target)
        install_requirements(executable,root)
        print('Da cai DU thu vien chay va dong goi. Chua bien dich ung dung hay tao EXE.')
        return 0
    except Exception as exc:
        print('Cai moi truong that bai:',exc)
        print('Thoat ung dung truoc khi cai lai. Du lieu va ket noi tai LOCALAPPDATA khong bi xoa.')
        return 1
if __name__=='__main__': sys.exit(main())
