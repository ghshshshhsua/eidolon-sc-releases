"""Continue the saved 1.4.3 byte-delta reconstruction, with pinned inputs."""
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from common import ROOT, REPO, BASE_TAG, BASE_FILES, TARGET_FILES, require, verify


def download_base(name, cache):
    require(name in BASE_FILES, 'Unknown baseline asset')
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / name
    if target.exists():
        verify(target, BASE_FILES[name])
        return target
    # A failed/interrupted transfer never becomes a reusable cache entry.
    part = target.with_suffix(target.suffix + '.partial')
    url = f'https://github.com/{REPO}/releases/download/{BASE_TAG}/{name}'
    subprocess.run(['curl', '--fail', '--location', '--proto', '=https',
                    '--proto-redir', '=https', '--retry', '3', '--connect-timeout', '30',
                    '--max-time', '1800', '--output', str(part), url], check=True)
    verify(part, BASE_FILES[name])
    part.replace(target)
    return target


def apply_delta(stream, output, literals, operations, base_size, target_size):
    for op, offset, length in operations:
        require(type(offset) is int and type(length) is int and offset >= 0 and length > 0,
                'Invalid delta range')
        require(output.tell() + length <= target_size, 'Delta exceeds target size')
        if op == 'L':
            require(offset + length <= len(literals), 'Literal outside payload')
            output.write(literals[offset:offset + length])
        else:
            require(op == 'C' and offset + length <= base_size, 'Copy outside baseline')
            stream.seek(offset)
            remaining = length
            while remaining:
                block = stream.read(min(remaining, 8 * 1024 * 1024))
                require(bool(block), 'Truncated baseline')
                output.write(block)
                remaining -= len(block)
    require(output.tell() == target_size, 'Incomplete delta output')


def reconstruct(root=ROOT, work=None, base_dir=None):
    root = Path(root)
    work = Path(work or tempfile.mkdtemp(prefix='eidolon-143-'))
    work.mkdir(parents=True, exist_ok=True)
    descriptor = json.loads((root / 'payload-descriptor.json').read_text())
    require(descriptor['size'] == 10311109 and descriptor['sha256'] ==
            'f106af8f710fd8b564fad60332e6cfd54679c9e9117efaaf1654651a506c198a',
            'Unexpected recovery payload')
    parts = descriptor['parts']
    require(len(parts) == 20 and [p['name'] for p in parts] ==
            [f'payload/part-{i:03d}.bin' for i in range(20)], 'Unexpected payload parts')
    # Fail before downloads or release API calls if the saved payload is not staged.
    for item in parts:
        verify(root / item['name'], item)
    payload = work / 'payload.zip'
    with payload.open('wb') as output:
        for item in parts:
            with (root / item['name']).open('rb') as stream:
                shutil.copyfileobj(stream, output)
    verify(payload, descriptor)
    staging = work / 'staging'
    require(not staging.exists() or not any(staging.iterdir()), 'Staging must be empty')
    staging.mkdir(exist_ok=True)
    cache = Path(base_dir) if base_dir else work / 'baseline'
    with zipfile.ZipFile(payload) as archive:
        require(len(archive.namelist()) == len(set(archive.namelist())), 'Duplicate payload entry')
        instructions = json.loads(archive.read('instructions.json'))
        targets = instructions['targets']
        require(len(targets) == 2 and {i['target']['name'] for i in targets} == set(TARGET_FILES),
                'Unexpected targets')
        for item in targets:
            base, target = item['base'], item['target']
            require(base['name'] in BASE_FILES and target['name'] in TARGET_FILES, 'Unknown asset')
            require(all(base[k] == v for k, v in BASE_FILES[base['name']].items()), 'Wrong base digest')
            require(all(target[k] == v for k, v in TARGET_FILES[target['name']].items()), 'Wrong target digest')
            require(base['url'] == f'https://github.com/{REPO}/releases/download/{BASE_TAG}/{base["name"]}',
                    'Unexpected baseline URL')
            source = download_base(base['name'], cache)
            literals = archive.read(item['literals'])
            result = staging / target['name']
            partial = result.with_suffix(result.suffix + '.partial')
            with source.open('rb') as stream, partial.open('wb') as output:
                apply_delta(stream, output, literals, item['operations'], base['size'], target['size'])
            verify(partial, target)
            partial.replace(result)
    shutil.copyfile(root / 'SHA256.json', staging / 'SHA256.json')
    return staging, cache


if __name__ == '__main__':
    print(reconstruct()[0])
