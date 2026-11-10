"""Photo placement in millimetres; negative gaps make neighbouring photos overlap."""
import math
PAPERS={'A4':(210,297),'A5':(148,210),'A6':(105,148)}
PHOTOS={'3 × 4 cm':(30,40),'4 × 6 cm':(40,60)}

def grid_slots(paper,photo,margin=7,gap=3,*,gap_x=None,gap_y=None):
    width,height=PAPERS[paper]; pw,ph=PHOTOS[photo]
    gx=float(gap if gap_x is None else gap_x); gy=float(gap if gap_y is None else gap_y); margin=float(margin)
    if not all(math.isfinite(value) for value in (margin,gx,gy)): raise ValueError('Thông số bố trí không hợp lệ')
    if margin<0 or pw+gx<1 or ph+gy<1: raise ValueError('Khoảng cách chồng ảnh quá lớn hoặc lề không hợp lệ')
    if width-2*margin<pw or height-2*margin<ph: raise ValueError('Ảnh không vừa giấy với lề đang chọn')
    cols=math.floor((width-2*margin-pw)/(pw+gx)+1e-9)+1
    rows=math.floor((height-2*margin-ph)/(ph+gy)+1e-9)+1
    return [(margin+c*(pw+gx),margin+r*(ph+gy),pw,ph) for r in range(rows) for c in range(cols)]

def validate_count(count):
    if not isinstance(count,int) or not 1<=count<=999: raise ValueError('Số lượng phải từ 1 đến 999')

def pages(paper,photo,count,margin=7,gap=3):
    validate_count(count); slots=grid_slots(paper,photo,margin,gap)
    return [slots[:min(len(slots),count-i)] for i in range(0,count,len(slots))]

def batch_pages(paper,photo,requests,margin=7,gap_x=3,gap_y=3):
    slots=grid_slots(paper,photo,margin,gap_x=gap_x,gap_y=gap_y); page=[]
    for path,count in requests:
        validate_count(count)
        for _ in range(count):
            page.append((path,slots[len(page)]))
            if len(page)==len(slots): yield page; page=[]
    if page: yield page

def layout_kwargs(settings):
    return {'margin':settings.get('margin_mm',7),'gap_x':settings.get('gap_x_mm',3),'gap_y':settings.get('gap_y_mm',3)}
