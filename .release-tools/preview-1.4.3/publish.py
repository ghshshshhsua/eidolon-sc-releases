"""Verify first, resume a tag-scoped draft, then publish a non-latest prerelease."""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from common import ROOT, REPO, BRANCH, TAG, SOURCE_COMMIT, STABLE_BLOB, BASE_TAG, REUSED_MODELS, require
from reconstruct import reconstruct
from verify_assets import verify_assets

PREFIX = 'repos/' + REPO
STABLE = PREFIX + '/contents/updates/stable.json?ref=main'
LATEST = PREFIX + '/releases/latest'


class GitHub:
    def call(self, *args, input_text=None):
        result = subprocess.run(['gh', *args], input=input_text, text=True,
                                capture_output=True, env=dict(os.environ, GH_PROMPT_DISABLED='1'))
        require(result.returncode == 0, 'GitHub command failed: ' + result.stderr.strip())
        return result.stdout

    def api(self, path, method='GET', body=None):
        args = ['api', path, '--method', method, '-H', 'Accept: application/vnd.github+json',
                '-H', 'X-GitHub-Api-Version: 2022-11-28']
        if body is not None:
            args += ['--input', '-']
        raw = self.call(*args, input_text=None if body is None else json.dumps(body))
        return json.loads(raw) if raw.strip() else None

    def pages(self, path):
        results = []
        for page in range(1, 1001):
            items = self.api(f'{path}?per_page=100&page={page}')
            require(isinstance(items, list), 'Expected paginated list')
            results.extend(items)
            if len(items) < 100:
                return results
        raise RuntimeError('Pagination limit reached; refusing incomplete discovery')

    def upload(self, tag, path):
        # No --clobber: conflicting assets must never be overwritten.
        self.call('release', 'upload', tag, str(path), '--repo', REPO)


def find_release(api):
    matches = [r for r in api.pages(PREFIX + '/releases') if r['tag_name'] == TAG]
    require(len(matches) <= 1, 'Multiple matching releases')
    return matches[0] if matches else None


def tag_target(api):
    refs = api.api(PREFIX + '/git/matching-refs/tags/' + TAG)
    refs = [r for r in refs if r['ref'] == 'refs/tags/' + TAG]
    require(len(refs) <= 1, 'Ambiguous tag')
    if not refs:
        return None
    obj = refs[0]['object']
    for _ in range(5):
        if obj['type'] == 'commit':
            return obj['sha']
        require(obj['type'] == 'tag', 'Tag does not resolve to commit')
        obj = api.api(PREFIX + '/git/tags/' + obj['sha'])['object']
    raise RuntimeError('Tag chain too deep')


def guard_channels(api, latest_id):
    require(api.api(STABLE)['sha'] == STABLE_BLOB, 'main/updates/stable.json changed; stopped')
    require(api.api(LATEST)['id'] == latest_id, 'Latest stable release changed; stopped')


def assets_by_name(api, release):
    rows = api.pages(f'{PREFIX}/releases/{release["id"]}/assets')
    require(len({r['name'] for r in rows}) == len(rows), 'Duplicate remote asset names')
    return {r['name']: r for r in rows}


def check_release(release, commit):
    require(release['tag_name'] == TAG and release['prerelease'] is True, 'Wrong release identity/type')
    require(release['target_commitish'] == commit, 'Release belongs to a different publication commit')


def matches(asset, expected):
    return asset.get('state') == 'uploaded' and all(asset.get(k) == v for k, v in expected.items())


def check_reused_models(api):
    baseline = api.api(PREFIX + '/releases/tags/' + BASE_TAG)
    require(baseline['tag_name'] == BASE_TAG and not baseline['draft'], 'Missing published model baseline')
    assets = assets_by_name(api, baseline)
    for name, expected in REUSED_MODELS.items():
        require(matches(assets.get(name, {}), expected), 'Reusable model asset missing/changed: ' + name)


def publish(api, staging, expected, commit, notes):
    """Only called after real artifact verification. Injectable API enables offline failure tests."""
    require(re.fullmatch(r'[0-9a-f]{40}', commit) is not None, 'Expected exact publication commit')
    repo = api.api(PREFIX)
    require(repo['full_name'] == REPO and repo['private'] is False, 'Wrong public release repository')
    # Repository role flags are not the contents scope of an Actions installation token.
    # The release API enforces that scope; every failed request still stops publication.
    latest_id = api.api(LATEST)['id']
    guard_channels(api, latest_id)
    check_reused_models(api)
    target = tag_target(api)
    require(target is None or target == commit, 'Existing tag points to another commit')
    release = find_release(api)
    marker = f'<!-- eidolon-preview source={SOURCE_COMMIT} -->'
    if release is None:
        release = api.api(PREFIX + '/releases', 'POST', {
            'tag_name': TAG, 'target_commitish': commit,
            'name': 'Eidolon SC · Android 1.4.3-preview.1',
            'body': notes.rstrip() + '\n\n' + marker + '\n',
            'draft': True, 'prerelease': True, 'make_latest': 'false',
        })
    check_release(release, commit)
    require(marker in release.get('body', ''), 'Unrecognized draft/release provenance')
    uploaded = assets_by_name(api, release)
    require(set(uploaded) <= set(expected), 'Unexpected remote assets; refusing to modify release')
    # Preflight every asset before changing anything in an existing draft.
    repairable = set()
    for name, asset in uploaded.items():
        if matches(asset, expected[name]):
            continue
        if release['draft'] and asset.get('state') == 'starter' and asset.get('size') == 0 and not asset.get('digest'):
            repairable.add(name)
        else:
            raise RuntimeError('Conflicting/unverified remote asset: ' + name)
    require(release['draft'] or set(uploaded) == set(expected), 'Published release is incomplete')
    if not release['draft']:
        require(tag_target(api) == commit, 'Published tag does not match publication commit')
    for name in sorted(expected):
        if name in uploaded and name not in repairable:
            continue
        # A previous 502 can leave an empty starter. Only that draft-owned object is removable.
        current = api.api(f'{PREFIX}/releases/{release["id"]}')
        check_release(current, commit)
        require(current['draft'], 'Release became public during upload; stopped')
        guard_channels(api, latest_id)
        if name in repairable:
            fresh = api.api(f'{PREFIX}/releases/assets/{uploaded[name]["id"]}')
            require(fresh.get('name') == name and fresh.get('state') == 'starter' and
                    fresh.get('size') == 0 and not fresh.get('digest'),
                    'Starter changed during verification; rerun without deleting it')
            api.api(f'{PREFIX}/releases/assets/{uploaded[name]["id"]}', 'DELETE')
        api.upload(TAG, Path(staging) / name)
        # Even a CLI success is insufficient without server size/digest/state verification.
        actual = assets_by_name(api, release).get(name, {})
        require(matches(actual, expected[name]), 'Uploaded asset failed verification: ' + name)
    release = api.api(f'{PREFIX}/releases/{release["id"]}')
    check_release(release, commit)
    actual = assets_by_name(api, release)
    require(set(actual) == set(expected) and all(matches(actual[n], e) for n, e in expected.items()),
            'Incomplete or mismatched final assets')
    guard_channels(api, latest_id)
    target = tag_target(api)
    require(target is None or target == commit, 'Tag moved during upload')
    if release['draft']:
        api.api(f'{PREFIX}/releases/{release["id"]}', 'PATCH', {
            'draft': False, 'prerelease': True, 'make_latest': 'false',
        })
    final = api.api(f'{PREFIX}/releases/{release["id"]}')
    check_release(final, commit)
    require(not final['draft'] and tag_target(api) == commit, 'Release publication not confirmed')
    final_assets = assets_by_name(api, final)
    require(set(final_assets) == set(expected) and all(matches(final_assets[n], e) for n, e in expected.items()),
            'Published assets changed')
    guard_channels(api, latest_id)
    return {'status': 'published-and-verified', 'url': final['html_url'], 'assets': sorted(expected)}


PUSH_REQUEST = {
    'repository': REPO,
    'version': '1.4.3-preview.1',
    'sourceCommit': SOURCE_COMMIT,
    'payloadSha256': 'f106af8f710fd8b564fad60332e6cfd54679c9e9117efaaf1654651a506c198a',
    'mode': 'publish',
}


def publication_context(env, root=ROOT):
    require(env.get('GITHUB_REPOSITORY') == REPO, 'Wrong workflow repository')
    require(env.get('GITHUB_REF') == 'refs/heads/' + BRANCH, 'Wrong workflow branch')
    event = env.get('GITHUB_EVENT_NAME')
    require(event in ('workflow_dispatch', 'push'), 'Unsupported publication event')
    if event == 'push':
        request = Path(root) / 'publish-request.json'
        require(request.is_file() and not request.is_symlink(), 'Missing publication request')
        require(json.loads(request.read_text()) == PUSH_REQUEST, 'Unexpected publication request')
    require(bool(env.get('GH_TOKEN')), 'Missing release token')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish', action='store_true', help='Actually publish after all checks (default: verify only)')
    parser.add_argument('--staging', type=Path, help='Existing exact signed assets; otherwise reconstruct saved payload')
    parser.add_argument('--baseline-dir', type=Path, help='Directory holding the pinned previous APK')
    args = parser.parse_args(argv)
    try:
        if args.publish:
            publication_context(os.environ)
        if args.staging:
            require(args.baseline_dir is not None, '--baseline-dir required with --staging')
            staging, baseline = args.staging, args.baseline_dir
        else:
            staging, baseline = reconstruct(base_dir=args.baseline_dir)
        expected = verify_assets(staging, baseline)
        if args.publish:
            result = publish(GitHub(), staging, expected, os.environ.get('GITHUB_SHA', ''),
                             (ROOT / 'RELEASE-NOTES.md').read_text())
        else:
            result = {'status': 'verified-only', 'published': False, 'sourceCommit': SOURCE_COMMIT,
                      'assets': expected}
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print('Release stopped: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

