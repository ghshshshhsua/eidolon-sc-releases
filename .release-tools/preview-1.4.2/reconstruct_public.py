from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import io
import json
import shutil
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
PUBLIC = [
    {'name':'Eidolon-SC-Android-1.4.1.apk','size':2016418850,'sha256':'0d74da40356f0c0d3d007486cff62337f62e4e80c72895be2809f4017b11cd27'},
    {'name':'Eidolon-SC-1.4.1-corresponding-source.zip','size':1768326670,'sha256':'6886bb3c523203a2488781768dacddff447f3d2cf7a158f20ef1c1d9cd7d1cbf'},
]
PREFIX = 'https://github.com/ghshshshhsua/eidolon-sc-releases/releases/download/v1.4.1/'

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def check(path, spec):
    assert path.stat().st_size == spec['size'] and sha(path) == spec['sha256'], path.name

def reconstruct():
    staging = ROOT / 'staging'
    staging.mkdir(exist_ok=True)
    bases = ROOT / 'public-base'
    bases.mkdir(exist_ok=True)
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    assert manifest['repository'] == 'ghshshshhsua/eidolon-sc-releases'
    assert manifest['tag'] == 'v1.4.2-preview.1'
    assert manifest['sourceCommit'] == '91ce558753904756eea471717f8afb8e990a3167'
    def download(spec):
        path = bases / spec['name']
        if path.exists():
            check(path, spec)
            return
        print('Downloading public base ' + spec['name'], flush=True)
        temp = path.with_suffix(path.suffix + '.downloading')
        with urllib.request.urlopen(PREFIX + spec['name'], timeout=120) as response, temp.open('wb') as out:
            shutil.copyfileobj(response, out, 8 * 1024 * 1024)
        check(temp, spec)
        temp.replace(path)
        print('Verified public base ' + spec['name'], flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(download, PUBLIC))
    descriptor = json.loads((ROOT / 'payload-descriptor.json').read_text())
    payload = ROOT / 'public-publication-payload.zip'
    if not payload.exists():
        with payload.open('wb') as out:
            for part in descriptor['parts']:
                assert Path(part['name']).name == part['name']
                p = ROOT / 'payload' / part['name']
                check(p, part)
                with p.open('rb') as src:
                    shutil.copyfileobj(src, out)
    check(payload, descriptor)
    with zipfile.ZipFile(payload) as z:
        instructions = json.loads(z.read('instructions.json'))
        literals = z.read('apk-literals.bin')
        source_overlay = z.read('source-overlay.zip')
    meta = json.loads((ROOT / 'files/preview-apk.json').read_text())
    assert instructions['apkSha256'] == meta['sha256']
    apk = staging / meta['file']
    with (bases / PUBLIC[0]['name']).open('rb') as base, apk.open('wb') as out:
        for op in instructions['operations']:
            if op[0] == 'L':
                chunk = literals[op[1]:op[1]+op[2]]
                assert len(chunk) == op[2]
                out.write(chunk)
            else:
                assert op[0] == 'C'
                base.seek(op[1])
                remaining = op[2]
                h = hashlib.sha256()
                while remaining:
                    chunk = base.read(min(remaining, 8 * 1024 * 1024))
                    assert chunk
                    out.write(chunk)
                    h.update(chunk)
                    remaining -= len(chunk)
                assert h.hexdigest() == op[3], op[4]
    check(apk, meta)
    print('Reconstructed APK matches original signed preview SHA-256', flush=True)
    source_path = staging / 'Eidolon-SC-1.4.2-preview.1-corresponding-source.zip'
    removed = set(instructions['removedSourcePaths'])
    with zipfile.ZipFile(bases / PUBLIC[1]['name']) as original, zipfile.ZipFile(io.BytesIO(source_overlay)) as overlay, zipfile.ZipFile(source_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as out:
        changed = {i.filename:i for i in overlay.infolist()}
        added = set()
        for info in original.infolist():
            name = info.filename
            assert not name.startswith('/') and '..' not in Path(name).parts
            if name in removed:
                continue
            if name in changed:
                out.writestr(changed[name], overlay.read(name))
                added.add(name)
            else:
                with original.open(info) as src, out.open(info, 'w', force_zip64=info.file_size >= 2**31) as dst:
                    shutil.copyfileobj(src, dst, 8 * 1024 * 1024)
        for name in sorted(set(changed) - added):
            assert not name.startswith('/') and '..' not in Path(name).parts
            out.writestr(changed[name], overlay.read(name))
    with zipfile.ZipFile(source_path) as source:
        entries = {i.filename:[i.file_size,i.CRC] for i in source.infolist()}
        assert entries == instructions['sourceEntries']
        assert len(entries) == len(source.infolist())
        assert 'LICENSE' in entries
        assert not any(n.lower().endswith(('.p12','.jks','.keystore')) for n in entries)
        prefix = 'work/android-app/app/src/main/assets/'
        def read(name): return json.loads(source.read(prefix + name))
        judge, neural, speech, index = (read(n) for n in ('judge/model.json','neural/manifest.json','offline-asr/manifest.json','semantic-index.json'))
        groups = {'judge':{'judge/'+judge['file']:judge},'retrieval':{**{'neural/'+k:v for k,v in neural['files'].items()},'semantic.db':index},'speech':{'offline-asr/model.zip':speech}}
        licenses_prefix = 'work/android-app/licenses/'
        licenses = sorted(n for n in entries if n.startswith(licenses_prefix) and '/' not in n[len(licenses_prefix):] and not n.endswith('/'))
        assert licenses
        for group, files in groups.items():
            identity = hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()[:12]
            output = staging / ('eidolon-models-'+group+'-'+identity+'.zip')
            with zipfile.ZipFile(output,'w',zipfile.ZIP_STORED,allowZip64=True) as archive:
                def add(name, member, spec=None):
                    info = zipfile.ZipInfo(name,(2020,1,1,0,0,0))
                    info.external_attr = 0o644 << 16
                    h = hashlib.sha256(); size = 0
                    with archive.open(info,'w',force_zip64=True) as target, source.open(member) as data:
                        for block in iter(lambda:data.read(8*1024*1024),b''):
                            h.update(block);size += len(block);target.write(block)
                    if spec:
                        assert size == spec['bytes'] and h.hexdigest() == spec['sha256'],name
                for name,spec in sorted(files.items()): add(name,prefix+name,spec)
                for member in licenses: add('licenses/'+member[len(licenses_prefix):],member)
                add('licenses/VOSK.txt',prefix+'offline-asr/LICENSE-VOSK.txt')
                archive.writestr(zipfile.ZipInfo('NOTICE.txt',(2020,1,1,0,0,0)),'Eidolon SC optional model pack. See included licenses. No chats, API keys or application data included.\n')
            spec = next(g for g in json.loads((ROOT/'files/release-resources.json').read_text())['files'] if g['file']==output.name)
            check(output,spec)
            print('Verified model pack '+output.name,flush=True)
    expected_names = {meta['file'],source_path.name} | {g['file'] for g in json.loads((ROOT/'files/release-resources.json').read_text())['files'] if 'models-' in g['file']}
    assert len(expected_names) == 5
    assets=[]
    for name in sorted(expected_names):
        p=staging/name
        assert p.stat().st_size < 2**31
        assets.append({'name':name,'size':p.stat().st_size,'sha256':sha(p)})
    result={'version':meta['version'],'sourceCommit':meta['sourceCommit'],'package':meta['package'],'signerSha256':meta['signerSha256'],'files':assets}
    (staging/'SHA256.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('All release assets reconstructed and verified',flush=True)

if __name__=='__main__':
    reconstruct()
