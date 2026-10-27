import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
from reconstruct_public import reconstruct
import sys
import traceback

ROOT = Path(__file__).resolve().parent
GH = Path(shutil.which('gh') or '/usr/bin/gh')
REPO = 'ghshshshhsua/eidolon-sc-releases'
TAG = 'v1.4.2-preview.1'
STAGING = ROOT / 'staging'
ENV = dict(os.environ, GH_PROMPT_DISABLED='1')

def gh(*args, check=True):
    p = subprocess.run([str(GH), *args], env=ENV, capture_output=True, text=True)
    if check and p.returncode:
        raise RuntimeError(p.stderr.strip())
    return p

def api(path):
    return json.loads(gh('api', path).stdout)

def find_release():
    # Draft tags are not published Git refs: look up drafts in the release list.
    matches = [r for r in api('repos/' + REPO + '/releases?per_page=100') if r['tag_name'] == TAG]
    if len(matches) > 1:
        canonical = [r for r in matches if r['id'] == 425099036]
        assert len(canonical) == 1, 'Ambiguous release drafts'
        others = [r for r in matches if r['id'] != 425099036]
        assert all(r['id'] == 425100494 and r['draft'] and not r['assets'] for r in others), 'Unexpected duplicate release content'
        return canonical[0]
    return matches[0] if matches else None

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def run():
    manifest = json.loads((STAGING / 'SHA256.json').read_text())
    entries = manifest['files']
    names = {e['name'] for e in entries} | {'SHA256.json'}
    assert len(entries) == 5
    assert names == {p.name for p in STAGING.iterdir() if p.is_file() and not p.name.startswith('.')}
    assert not any(any(s in n.lower() for s in ('private', 'keystore', '.p12', '.jks')) for n in names)
    for e in entries:
        p = STAGING / e['name']
        assert p.stat().st_size == e['size'] and sha(p) == e['sha256'], e['name']
    expected = {e['name']: {'size': e['size'], 'digest': 'sha256:' + e['sha256']} for e in entries}
    expected['SHA256.json'] = {'size': (STAGING / 'SHA256.json').stat().st_size, 'digest': 'sha256:' + sha(STAGING / 'SHA256.json')}
    assert os.environ.get('GITHUB_REPOSITORY') == REPO, 'Unexpected repository context'
    assert os.environ.get('GITHUB_REF') == 'refs/heads/codex/publish-1.4.2-preview', 'Unexpected branch context'
    repo = api('repos/' + REPO)
    print('Repository checks: ' + json.dumps({'full_name': repo.get('full_name'), 'private': repo.get('private'), 'permissions': repo.get('permissions')}), flush=True)
    assert repo['full_name'] == REPO and not repo['private'], 'Repository identity or visibility check failed'
    # Installation tokens use contents permissions, not collaborator-role flags.
    # GitHub enforces contents:write on the release mutation endpoints.
    stable_before = api('repos/' + REPO + '/contents/updates/stable.json')['sha']
    release = find_release()
    assert release is not None, 'Preview draft disappeared before upload'
    assert release['tag_name'] == TAG and release['prerelease']
    uploaded = {a['name']: a for a in release['assets']}
    assert not (set(uploaded) - set(expected)), 'Unexpected existing assets; stopped.'
    for name, exp in expected.items():
        if name in uploaded:
            assert uploaded[name]['size'] == exp['size'] and uploaded[name]['digest'] == exp['digest'], 'Existing asset mismatch: ' + name
            continue
        assert release['draft'], 'Published release is incomplete; stopped without modifying it.'
        print('Uploading ' + name, flush=True)
        gh('release', 'upload', TAG, str(STAGING / name), '--repo', REPO)
        print('Uploaded ' + name, flush=True)
    release = api(f'repos/{REPO}/releases/{release["id"]}')
    assets = {a['name']: a for a in release['assets']}
    assert set(assets) == set(expected)
    for name, exp in expected.items():
        assert assets[name]['state'] == 'uploaded'
        assert assets[name]['size'] == exp['size'] and assets[name]['digest'] == exp['digest'], name
    assert api('repos/' + REPO + '/contents/updates/stable.json')['sha'] == stable_before
    if release['draft']:
        print('All six assets verified; publishing prerelease', flush=True)
        payload = ROOT / 'publish-request.json'
        payload.write_text(json.dumps({'draft': False, 'prerelease': True, 'make_latest': 'false'}))
        gh('api', f'repos/{REPO}/releases/{release["id"]}', '--method', 'PATCH', '--input', str(payload))
    result = api(f'repos/{REPO}/releases/{release["id"]}')
    assert not result['draft'] and result['prerelease']
    assert api('repos/' + REPO + '/contents/updates/stable.json')['sha'] == stable_before
    public = {'url': result['html_url'], 'tag': result['tag_name'], 'prerelease': result['prerelease'], 'assets': [{k: a[k] for k in ('name', 'size', 'digest', 'browser_download_url')} for a in result['assets']]}
    (ROOT / 'published-result.json').write_text(json.dumps(public, ensure_ascii=False, indent=2))
    print(json.dumps(public, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    try:
        context = api('repos/' + REPO)
        print('Publication context: ' + json.dumps({'repository': os.environ.get('GITHUB_REPOSITORY'), 'ref': os.environ.get('GITHUB_REF'), 'permissions': context.get('permissions')}), flush=True)
        assert context['full_name'] == REPO and not context['private'], 'Unexpected repository target'
        assert os.environ.get('GITHUB_REPOSITORY') == REPO
        assert os.environ.get('GITHUB_REF') == 'refs/heads/codex/publish-1.4.2-preview'
        existing = find_release()
        if existing is None:
            gh('release', 'create', TAG, '--repo', REPO, '--draft', '--prerelease', '--latest=false', '--target', context['default_branch'], '--title', 'Eidolon SC · Android 1.4.2-preview.1 独立测试版', '--notes-file', str(ROOT / 'RELEASE-NOTES.md'))
            existing = find_release()
        assert existing is not None and existing['prerelease'], 'Preview release is unavailable'
        print('Using preview release ' + str(existing['id']), flush=True)
        reconstruct()
        run()
        # Remove only the empty duplicate created by this publication attempt.
        leftovers = [r for r in api('repos/' + REPO + '/releases?per_page=100') if r['id'] == 425100494]
        for duplicate in leftovers:
            assert duplicate['tag_name'] == TAG and duplicate['draft'] and not duplicate['assets']
            assert duplicate['author']['login'] == 'github-actions[bot]'
            gh('api', f'repos/{REPO}/releases/425100494', '--method', 'DELETE')
            print('Removed empty duplicate publication draft', flush=True)
    except Exception as exc:
        location = traceback.extract_tb(exc.__traceback__)[-1]
        print('Publication stopped: ' + type(exc).__name__ + ': ' + str(exc) + ' at ' + str(location.lineno), file=sys.stderr)
        sys.exit(1)
