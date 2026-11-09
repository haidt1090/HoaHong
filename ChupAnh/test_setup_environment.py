import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import setup_environment as setup
class EnvironmentTests(unittest.TestCase):
    def test_rejects_newer_or_32bit_python_before_install(self):
        for info in [(3,15,64),(3,14,64),(3,12,32)]:
            with self.assertRaises(RuntimeError): setup.require_supported(info)
        setup.require_supported((3,12,64))
    def test_wrong_old_environment_is_preserved_not_deleted(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); old=root/'.venv'; (old/'Scripts').mkdir(parents=True)
            (old/'Scripts'/'python.exe').write_bytes(b'old'); (old/'keep.txt').write_text('keep')
            def create(folder):
                (folder/'Scripts').mkdir(parents=True); (folder/'Scripts'/'python.exe').write_bytes(b'new')
            with patch.object(setup,'python_info',side_effect=[(3,15,64),(3,12,64)]),patch.object(setup.venv.EnvBuilder,'create',side_effect=create):
                result=setup.ensure_environment(root,'.venv')
            backups=list(root.glob('.venv-old-*')); self.assertEqual(len(backups),1)
            self.assertEqual((backups[0]/'keep.txt').read_text(),'keep'); self.assertEqual(result.read_bytes(),b'new')
    def test_install_keeps_full_requirements_but_forbids_zstandard_source_build(self):
        with patch.object(setup,'python_info',return_value=(3,12,64)),patch.object(setup.subprocess,'run') as run:
            setup.install_requirements(Path('python.exe'),Path('project'))
        commands=[call.args[0] for call in run.call_args_list]
        install=next(command for command in commands if '-r' in command)
        self.assertIn('--only-binary=zstandard,pywin32',install)
        self.assertEqual(install[-1],str(Path('project')/'requirements.txt'))
if __name__=='__main__': unittest.main()
