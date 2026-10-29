"""Pinned release identity. No signing keys, credentials or model weights."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = 'ghshshshhsua/eidolon-sc-releases'
BRANCH = 'codex/publish-1.4.3-preview'
VERSION = '1.4.3-preview.1'
TAG = 'v' + VERSION
SOURCE_REPO = 'ghshshshhsua/eidolon-sc-client'
SOURCE_COMMIT = '4b70b8c62bbcfe2d5e6a86b42d352cd7e10a4321'
PACKAGE = 'local.eidolon.sc.android.preview'
SIGNER = '4c7ab53572c7ecc4b76517edf404a834bc955bd0b8bf9d5296a868e6045b1c31'
STABLE_BLOB = '64876f05ff3a4fc2d0549c17bfdca66412716185'
APK = 'Eidolon-SC-Android-' + VERSION + '.apk'
SOURCE = 'Eidolon-SC-' + VERSION + '-corresponding-source.zip'
BASE_TAG = 'v1.4.2-preview.1'
BASE_APK = 'Eidolon-SC-Android-1.4.2-preview.1.apk'
BASE_FILES = {
    BASE_APK: {'size': 269372329, 'sha256': 'ae1bf28c57f5d317e0e3e08331323440b07e3aab99c1b41bc47017427afff23b'},
    'Eidolon-SC-1.4.2-preview.1-corresponding-source.zip': {'size': 1768381253, 'sha256': '34d2a6b96708580094ec3cef53ef89d4c43fef5a306248eedae02a215e451add'},
}
TARGET_FILES = {
    APK: {'size': 269854671, 'sha256': 'fafd23b85ff76c66e35d4da1df6e49f27add08371e4a435b1496ded1af86db3e'},
    SOURCE: {'size': 1772827825, 'sha256': '6932d713e1811e976e08e3e7f03749cd479bdab8712510537a96e7f03cebfc15'},
}
SOURCE_BLOBS = {
    'work/android-app/web/src/dataPackage.ts': 'abd8fe9dc436ec2dd96f0144be25c40ed4c32726',
    'work/android-app/app/build.gradle': 'fbc63647d0371adce9827b36254d4c28c646c75c',
    'work/android-app/UPSTREAM-1.4.3.md': 'b9ef3e32668f8399386039de4625e6a365443ff8',
    'work/test-upstream-integration.cjs': 'b0aa0eb41827e1523e910e0165f1e802341c134b',
    'work/android-app/web/src/update-check.mjs': '395b6f8a4aa8b6d2f5f6bef87dbb15b4951e5012',
}
MODEL_METADATA = {
    'judge/model.json': '36a99d61ce4bc724d1287be01a01de7f9cef344a',
    'neural/manifest.json': 'daf2e09df08ada5a4d1e886d871106c74a1752b7',
    'offline-asr/manifest.json': '55c13ec8f7ab100d6e36a7a95b9017933799cf77',
    'semantic-index.json': '6c6dd2fc82b7ca596c9df4950959057673532954',
}
REUSED_MODELS = {
    'eidolon-models-judge-b3f7bd777fbd.zip': {'size': 1359320739, 'digest': 'sha256:4b3763bb1b24bf0187dde4105fbe4f7f2b58ff551f3e8a09e964636487ab3b4b'},
    'eidolon-models-retrieval-5d7233bc58fc.zip': {'size': 345156307, 'digest': 'sha256:ae2c513ff98e621290ddaa3e65b55d3f8deaba07a4cdccfe65e4a431f457baa6'},
    'eidolon-models-speech-59c5055a3322.zip': {'size': 43939707, 'digest': 'sha256:e63a9b25236399b7003501d5e078841759d998f84708b1c5ed6136ab1731b63f'},
}


def require(condition, message):
    # Explicit exceptions: python -O must never disable a release gate.
    if not condition:
        raise RuntimeError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def blob_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def verify(path, entry):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), f'Missing/unsafe file: {path.name}')
    require(path.stat().st_size == entry['size'] and sha(path) == entry['sha256'],
            f'Size/SHA-256 mismatch: {path.name}')
