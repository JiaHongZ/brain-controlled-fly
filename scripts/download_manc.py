"""Download the official Janelia MANC v1.0 release, verify publisher MD5 hashes."""
from pathlib import Path
import sys
import json
import hashlib
import base64
import urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.download import download_ranges

ROOT=Path(__file__).resolve().parents[1]
BUCKET='https://storage.googleapis.com/flyem-manc-exports/'
KEYS={
    'traced-neurons.csv':'v1.0/manc-traced-adjacencies-v1.0/traced-neurons.csv',
    'traced-connections.csv':'v1.0/manc-traced-adjacencies-v1.0/traced-connections.csv',
    'neuron-properties.feather':'v1.0/manc-v1.0-neuron-properties.feather',
    'README.txt':'v1.0/manc-traced-adjacencies-v1.0/README',
}

def download(progress=print):
    folder=ROOT/'data/manc/raw';folder.mkdir(parents=True,exist_ok=True)
    with urllib.request.urlopen('https://storage.googleapis.com/storage/v1/b/flyem-manc-exports/o?maxResults=1000',timeout=60) as r:
        listing=json.load(r)
    objects={o['name']:o for o in listing['items']}
    def get(item):
        name,key=item;obj=objects[key];path=folder/name
        def valid():return path.exists() and path.stat().st_size==int(obj['size']) and base64.b64encode(hashlib.md5(path.read_bytes()).digest()).decode()==obj['md5Hash']
        if not valid():
            temp=path.with_suffix(path.suffix+'.download')
            progress('Downloading official MANC: '+name)
            if not download_ranges(BUCKET+key,temp,progress):
                with urllib.request.urlopen(BUCKET+key,timeout=60) as response:
                    temp.write_bytes(response.read())
            temp.replace(path)
            if not valid():raise RuntimeError('Publisher checksum mismatch: '+name)
        progress('MANC verified: '+name)
        return name,dict(url=BUCKET+key,bytes=path.stat().st_size,publisher_md5_base64=obj['md5Hash'],
                         sha256=hashlib.sha256(path.read_bytes()).hexdigest(),generation=obj['generation'])
    with ThreadPoolExecutor(max_workers=3) as pool:files=dict(pool.map(get,KEYS.items()))
    provenance=dict(dataset='Male Adult Nerve Cord (MANC)',version='v1.0',
                    official_landing_page='https://www.janelia.org/project-team/flyem/manc-connectome',
                    modality='Electron microscopy reconstruction; directed chemical synapse counts',
                    files=files)
    (folder.parent/'source_manifest.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    return folder

if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    download()
