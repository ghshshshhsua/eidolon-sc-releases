"""Read-only checks on the actual signed APK and corresponding source."""
import json
import re
import subprocess
import zipfile
from pathlib import Path, PurePosixPath
from common import (ROOT, VERSION, SOURCE_REPO, SOURCE_COMMIT, PACKAGE, SIGNER,
                    APK, SOURCE, BASE_APK, BASE_FILES, TARGET_FILES,
                    SOURCE_BLOBS, MODEL_METADATA, require, verify, sha, blob_sha)


def command(*args):
    result = subprocess.run(args, text=True, capture_output=True, check=True)
    return result.stdout


def apk_identity(path):
    signature = command('apksigner', 'verify', '--verbose', '--print-certs', str(path))
    signers = re.findall(r'^Signer #\d+ certificate SHA-256 digest: ([0-9a-fA-F]{64})$',
                         signature, re.M)
    require([x.lower() for x in signers] == [SIGNER], 'Wrong/multiple APK signing certificate(s)')
    badging = command('aapt2', 'dump', 'badging', str(path))
    match = re.search(r"^package: name='([^']+)' versionCode='(\d+)' versionName='([^']+)'", badging, re.M)
    require(match is not None, 'Cannot read APK package/version')
    require(not re.search(r'^application-debuggable\b', badging, re.M), 'Debuggable APK')
    package, code, version = match.groups()
    return package, int(code), version


def safe_zip(archive):
    names = archive.namelist()
    require(len(names) == len(set(names)), 'Duplicate ZIP entry')
    for name in names:
        require('\\' not in name and not name.startswith('/') and
                '..' not in PurePosixPath(name).parts, 'Unsafe ZIP path')
    return names


def check_model_separation(apk):
    with zipfile.ZipFile(apk) as archive:
        names = safe_zip(archive)
        forbidden = [n for n in names if n.startswith('assets/') and (
            n.lower().endswith(('.gguf', '.onnx', '.bin', '.safetensors', '.pt', '.pth')) or
            n in ('assets/offline-asr/model.zip', 'assets/semantic.db'))]
        require(not forbidden, 'Bundled model weights/index: ' + ', '.join(forbidden))
        # The public corpus DB and SentencePiece vocabularies intentionally remain.
        for name, digest in MODEL_METADATA.items():
            require(blob_sha(archive.read('assets/' + name)) == digest,
                    'Model metadata changed: ' + name)


def check_source(path):
    with zipfile.ZipFile(path) as archive:
        names = safe_zip(archive)
        require('LICENSE' in names and 'build-dependencies.json' in names, 'Incomplete source archive')
        for name, digest in SOURCE_BLOBS.items():
            require(blob_sha(archive.read(name)) == digest, 'Wrong pinned source: ' + name)
        require(archive.testzip() is None, 'Source ZIP CRC error')


def verify_assets(staging, baseline):
    staging, baseline = Path(staging), Path(baseline)
    require({p.name for p in staging.iterdir()} == {*TARGET_FILES, 'SHA256.json'},
            'Unexpected/missing staged assets')
    manifest = json.loads((staging / 'SHA256.json').read_text())
    expected_identity = {'version': VERSION, 'sourceRepository': SOURCE_REPO,
                         'sourceCommit': SOURCE_COMMIT, 'package': PACKAGE,
                         'versionCode': 143, 'signerSha256': SIGNER}
    require(all(manifest.get(k) == v for k, v in expected_identity.items()), 'Wrong manifest identity')
    entries = manifest['files']
    require(len(entries) == 2 and {e['name'] for e in entries} == set(TARGET_FILES), 'Wrong manifest files')
    for entry in entries:
        require(all(entry[k] == v for k, v in TARGET_FILES[entry['name']].items()), 'Unpinned asset')
        verify(staging / entry['name'], entry)
    verify(baseline / BASE_APK, BASE_FILES[BASE_APK])
    require(apk_identity(baseline / BASE_APK) == (PACKAGE, 142, '1.4.2-preview.1'),
            'Unexpected published baseline identity')
    require(apk_identity(staging / APK) == (PACKAGE, 143, VERSION), 'Wrong preview identity/version')
    # Both calls above cryptographically verify signatures and require the same pinned certificate.
    command('zipalign', '-c', '-P', '16', '4', str(staging / APK))
    check_model_separation(staging / APK)
    check_source(staging / SOURCE)
    return {p.name: {'size': p.stat().st_size, 'digest': 'sha256:' + sha(p)} for p in staging.iterdir()}
