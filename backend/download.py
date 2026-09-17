"""Bounded concurrent range download for the official archive's slow connections."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import urllib.request

def download_ranges(url, destination, progress):
    request=urllib.request.Request(url,method='HEAD',headers={'User-Agent':'BrainControlledFly/1.0'})
    with urllib.request.urlopen(request,timeout=45) as response:
        total=int(response.headers.get('Content-Length',0))
        ranges=response.headers.get('Accept-Ranges','')=='bytes'
    if not ranges or total<1024*1024:
        return False
    part_dir=Path(str(destination)+'.parts')
    part_dir.mkdir(parents=True,exist_ok=True)
    chunk_size=128*1024
    jobs=[(i,start,min(total-1,start+chunk_size-1)) for i,start in enumerate(range(0,total,chunk_size))]
    def fetch(job):
        index,start,end=job;path=part_dir/str(index)
        # A chunk file is committed only after its response and length validate.
        if path.exists() and path.stat().st_size==end-start+1:
            return
        for attempt in range(3):
            try:
                req=urllib.request.Request(url,headers={'Range':f'bytes={start}-{end}','User-Agent':'BrainControlledFly/1.0'})
                with urllib.request.urlopen(req,timeout=45) as response:
                    if response.status!=206 or response.headers.get('Content-Range')!=f'bytes {start}-{end}/{total}':
                        raise RuntimeError('Server returned an invalid byte range')
                    data=response.read()
                if len(data)!=end-start+1: raise RuntimeError('Incomplete download chunk')
                temporary=path.with_suffix('.tmp');temporary.write_bytes(data);temporary.replace(path)
                return
            except Exception:
                if attempt==2: raise
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures=[pool.submit(fetch,job) for job in jobs]
        for completed,future in enumerate(as_completed(futures),1):
            future.result()
            if completed%12==0 or completed==len(jobs):
                progress(f'Downloading {destination.stem}: {completed/len(jobs):.0%} / {total/1e6:.1f} MB')
    with destination.open('wb') as output:
        for i,_,_ in jobs:output.write((part_dir/str(i)).read_bytes())
    # Remove only our numbered chunks after a complete assembly.
    for i,_,_ in jobs:(part_dir/str(i)).unlink()
    part_dir.rmdir()
    return True
