import unittest
from layout import pages,PAPERS,PHOTOS
class LayoutTests(unittest.TestCase):
    def test_dimensions_and_count(self):
        for paper,(w,h) in PAPERS.items():
            for photo,(pw,ph) in PHOTOS.items():
                result=pages(paper,photo,37)
                self.assertEqual(sum(map(len,result)),37)
                for page in result:
                    for x,y,a,b in page:
                        self.assertEqual((a,b),(pw,ph))
                        self.assertLessEqual(x+a,w-7+1e-6)
                        self.assertLessEqual(y+b,h-7+1e-6)
    def test_invalid_count(self):
        for n in (0,-1,1000):
            with self.assertRaises(ValueError): pages('A5','3 × 4 cm',n)
if __name__=='__main__': unittest.main()
