"""Read ordinary downloaded images; never decode Zalo's private cache."""
import os
from pathlib import Path
EXTENSIONS={'.jpg','.jpeg','.png','.webp','.bmp'}
def inventory(folder,recursive=False):
    result={}; stack=[Path(folder)]
    while stack:
        current=stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink(): continue
                        if recursive and entry.is_dir(follow_symlinks=False): stack.append(Path(entry.path))
                        elif Path(entry.name).suffix.lower() in EXTENSIONS and entry.is_file(follow_symlinks=False):
                            stat=entry.stat(follow_symlinks=False)
                            if stat.st_size: result[entry.path]=(stat.st_size,stat.st_mtime_ns)
                    except OSError: continue
        except OSError: continue
    return result
class FolderTracker:
    def __init__(self): self.previous={}; self.baseline={}
    def reset(self): self.previous={}; self.baseline={}
    def arm(self,snapshot): self.baseline=dict(snapshot)
    def update(self,snapshot):
        ready=[(Path(path), self.baseline.get(path)!=stamp)
               for path,stamp in snapshot.items() if self.previous.get(path)==stamp]
        self.previous=dict(snapshot)
        return ready
