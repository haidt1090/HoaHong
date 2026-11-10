"""Named, editable paper/photo format presets; never stores image paths or credentials."""
import json,math
from pathlib import Path
from layout import grid_slots,layout_kwargs,validate_count
FORMAT_KEYS=('paper','photo','count','margin_mm','gap_x_mm','gap_y_mm')
DEFAULT_GEOMETRY={'margin_mm':7.,'gap_x_mm':3.,'gap_y_mm':3.}

def clean_format(settings):
    result={'paper':settings['paper'],'photo':settings['photo'],'count':int(settings.get('count',4))}
    result.update({key:float(settings.get(key,default)) for key,default in DEFAULT_GEOMETRY.items()})
    validate_count(result['count']); grid_slots(result['paper'],result['photo'],**layout_kwargs(result))
    return result

class FormatStore:
    def __init__(self,base): self.path=Path(base)/'print-formats.json'
    def load(self):
        try:
            payload=json.loads(self.path.read_text(encoding='utf-8')); result={}
            for name,value in payload.items():
                try: result[str(name)]=clean_format(value)
                except (ValueError,TypeError,KeyError): continue
            return result
        except (OSError,ValueError,AttributeError): return {}
    def save(self,name,settings):
        name=name.strip()
        if not name: raise ValueError('Nhập tên mẫu trước khi lưu')
        formats=self.load(); formats[name]=clean_format(settings)
        self.path.parent.mkdir(parents=True,exist_ok=True); temporary=self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(formats,ensure_ascii=False,indent=2),encoding='utf-8'); temporary.replace(self.path)
