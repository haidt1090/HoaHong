import tempfile,unittest
from pathlib import Path
from folder_source import inventory,FolderTracker
class FolderTests(unittest.TestCase):
    def test_existing_new_partial_and_changed(self):
        tracker=FolderTracker(); old={'old.jpg':(20,1)}
        tracker.arm(old)
        self.assertEqual(tracker.update(old),[])
        self.assertEqual(tracker.update(old),[(Path('old.jpg'),False)])
        partial={**old,'new.jpg':(5,2)}
        tracker.update(partial)
        complete={**old,'new.jpg':(40,3)}
        self.assertFalse(any(p.name=='new.jpg' for p,_ in tracker.update(complete)))
        self.assertIn((Path('new.jpg'),True),tracker.update(complete))
    def test_recursive_and_filters(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); (p/'child').mkdir()
            (p/'x.jpg').write_bytes(b'fake'); (p/'child'/'y.PNG').write_bytes(b'fake')
            (p/'download.part').write_bytes(b'incomplete'); (p/'empty.jpg').touch()
            self.assertEqual(len(inventory(d)),1)
            self.assertEqual(len(inventory(d,True)),2)
    def test_source_reset(self):
        tracker=FolderTracker(); snapshot={'x.jpg':(2,2)}
        tracker.update(snapshot); tracker.arm(snapshot); tracker.reset()
        self.assertEqual(tracker.update(snapshot),[])
if __name__=='__main__': unittest.main()
