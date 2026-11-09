"""Physical photo placement; all dimensions are millimetres."""
import math
PAPERS = {'A4': (210,297), 'A5': (148,210), 'A6': (105,148)}
PHOTOS = {'3 × 4 cm': (30,40), '4 × 6 cm': (40,60)}
def pages(paper, photo, count, margin=7, gap=3):
    if not 1 <= count <= 999:
        raise ValueError('Số lượng phải từ 1 đến 999')
    w,h = PAPERS[paper]; pw,ph = PHOTOS[photo]
    cols = math.floor((w-2*margin+gap)/(pw+gap))
    rows = math.floor((h-2*margin+gap)/(ph+gap))
    if cols < 1 or rows < 1:
        raise ValueError('Ảnh không vừa giấy')
    slots = [(margin+c*(pw+gap), margin+r*(ph+gap), pw,ph)
             for r in range(rows) for c in range(cols)]
    return [slots[:min(len(slots), count-i)] for i in range(0,count,len(slots))]
