import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import common
import publish as release
import reconstruct
import verify_assets as check

COMMIT = 'a' * 40
EXPECTED = {n: {'size': len(n), 'digest': 'sha256:' + hashlib.sha256(n.encode()).hexdigest()}
            for n in (common.APK, common.SOURCE, 'SHA256.json')}
MARKER = f'<!-- eidolon-preview source={common.SOURCE_COMMIT} -->'


class FakeGitHub:
    """Mock HTTP responses and state transitions, including lost upload responses."""
    def __init__(self):
        self.release = None
        self.assets = []
        self.mutations = []
        self.target = None
        self.stable = common.STABLE_BLOB
        self.latest = 700
        self.fail_upload = None
        self.lose_upload_response = False
        self.fail_publish = False
        self.lose_publish_response = False
        self.bad_upload_digest = False
        self.extra_releases = []
        self.models = [{'name': n, 'state': 'uploaded', **e} for n, e in common.REUSED_MODELS.items()]

    def seed(self, names=(), draft=True):
        self.release = {'id': 9001, 'tag_name': common.TAG, 'target_commitish': COMMIT,
                        'draft': draft, 'prerelease': True, 'body': MARKER,
                        'html_url': 'https://github.com/' + common.REPO + '/releases/tag/' + common.TAG}
        self.assets = [self.asset(n) for n in names]
        if not draft:
            self.target = COMMIT

    def asset(self, name):
        return {'id': 10000 + list(EXPECTED).index(name), 'name': name,
                'state': 'uploaded', **EXPECTED[name]}

    def pages(self, path):
        if path == release.PREFIX + '/releases':
            return copy.deepcopy(self.extra_releases + ([self.release] if self.release else []))
        if path == release.PREFIX + '/releases/9001/assets':
            return copy.deepcopy(self.assets)
        if path == release.PREFIX + '/releases/8001/assets':
            return copy.deepcopy(self.models)
        raise AssertionError('Unexpected list request: ' + path)

    def api(self, path, method='GET', body=None):
        if method != 'GET':
            self.mutations.append((method, path, copy.deepcopy(body)))
        if path == release.PREFIX and method == 'GET':
            return {'full_name': common.REPO, 'private': False, 'permissions': {'push': True}}
        if path == release.STABLE:
            return {'sha': self.stable}
        if path == release.LATEST:
            return {'id': self.latest}
        if path == release.PREFIX + '/releases/tags/' + common.BASE_TAG:
            return {'id': 8001, 'tag_name': common.BASE_TAG, 'draft': False}
        if path == release.PREFIX + '/git/matching-refs/tags/' + common.TAG:
            return [] if not self.target else [{'ref': 'refs/tags/' + common.TAG,
                                                'object': {'type': 'commit', 'sha': self.target}}]
        if path == release.PREFIX + '/releases' and method == 'POST':
            self.seed()
            self.release.update(body)
            return copy.deepcopy(self.release)
        if path.startswith(release.PREFIX + '/releases/assets/'):
            aid = int(path.rsplit('/', 1)[1])
            if method == 'GET':
                return copy.deepcopy(next(a for a in self.assets if a['id'] == aid))
            assert method == 'DELETE'
            self.assets = [a for a in self.assets if a['id'] != aid]
            return None
        if path == release.PREFIX + '/releases/9001':
            if method == 'PATCH':
                if self.fail_publish:
                    raise RuntimeError('HTTP 403')
                self.release.update(body)
                self.target = COMMIT
                if self.lose_publish_response:
                    self.lose_publish_response = False
                    raise RuntimeError('Connection lost after publish')
            return copy.deepcopy(self.release)
        raise AssertionError('Unexpected API call: ' + repr((path, method, body)))

    def upload(self, tag, path):
        assert tag == common.TAG
        self.mutations.append(('UPLOAD', path.name, None))
        if path.name == self.fail_upload:
            self.fail_upload = None
            raise RuntimeError('HTTP 502')
        item = self.asset(path.name)
        if self.bad_upload_digest:
            item['digest'] = 'sha256:' + '0' * 64
        self.assets.append(item)
        if self.lose_upload_response:
            self.lose_upload_response = False
            raise RuntimeError('Connection lost after accepted upload')


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeGitHub()

    def run_release(self):
        return release.publish(self.api, Path('/fake-staging'), EXPECTED, COMMIT, 'Notes')

    def test_new_release_then_idempotent_rerun(self):
        self.assertEqual(self.run_release()['status'], 'published-and-verified')
        self.assertFalse(self.api.release['draft'])
        self.assertEqual(len([m for m in self.api.mutations if m[0] == 'UPLOAD']), 3)
        create, finish = [m for m in self.api.mutations if m[0] in ('POST', 'PATCH')]
        self.assertTrue(create[2]['draft'])
        self.assertEqual(finish[2], {'draft': False, 'prerelease': True, 'make_latest': 'false'})
        count = len(self.api.mutations)
        self.run_release()
        self.assertEqual(len(self.api.mutations), count)

    def test_resume_partial_draft_only_uploads_missing(self):
        self.api.seed([common.APK])
        self.run_release()
        self.assertEqual({m[1] for m in self.api.mutations if m[0] == 'UPLOAD'}, {common.SOURCE, 'SHA256.json'})

    def test_upload_failure_remains_draft_and_reruns(self):
        self.api.fail_upload = common.APK
        with self.assertRaisesRegex(RuntimeError, '502'):
            self.run_release()
        self.assertTrue(self.api.release['draft'])
        self.assertEqual(len(self.api.assets), 1)
        self.run_release()
        self.assertEqual(len(self.api.assets), 3)

    def test_lost_upload_response_is_reconciled(self):
        self.api.lose_upload_response = True
        with self.assertRaises(RuntimeError):
            self.run_release()
        first = self.api.assets[0]['name']
        self.run_release()
        self.assertEqual(len([m for m in self.api.mutations if m[:2] == ('UPLOAD', first)]), 1)

    def test_empty_starter_is_repaired_only_in_draft(self):
        self.api.seed([common.APK])
        self.api.assets[0].update(state='starter', size=0, digest=None)
        self.run_release()
        self.assertEqual(len([m for m in self.api.mutations if m[0] == 'DELETE']), 1)

    def test_conflicting_asset_stops_before_any_upload(self):
        self.api.seed(['SHA256.json'])
        self.api.assets[0]['digest'] = 'sha256:wrong'
        with self.assertRaisesRegex(RuntimeError, 'Conflicting'):
            self.run_release()
        self.assertEqual(self.api.mutations, [])

    def test_missing_server_digest_fails_closed(self):
        self.api.seed([common.APK])
        self.api.assets[0].pop('digest')
        with self.assertRaises(RuntimeError):
            self.run_release()
        self.assertEqual(self.api.mutations, [])

    def test_nonempty_starter_is_not_deleted(self):
        self.api.seed([common.APK])
        self.api.assets[0]['state'] = 'starter'
        with self.assertRaises(RuntimeError):
            self.run_release()
        self.assertEqual(self.api.mutations, [])

    def test_published_incomplete_release_never_changes(self):
        self.api.seed([common.APK], draft=False)
        with self.assertRaisesRegex(RuntimeError, 'incomplete'):
            self.run_release()
        self.assertEqual(self.api.mutations, [])

    def test_published_starter_never_deleted(self):
        self.api.seed(EXPECTED, draft=False)
        self.api.assets[0].update(state='starter', size=0, digest=None)
        with self.assertRaises(RuntimeError):
            self.run_release()
        self.assertEqual(self.api.mutations, [])

    def test_duplicate_asset_fails(self):
        self.api.seed([common.APK])
        self.api.assets *= 2
        with self.assertRaisesRegex(RuntimeError, 'Duplicate'):
            self.run_release()
        self.assertEqual(self.api.mutations, [])

    def test_unknown_asset_fails(self):
        self.api.seed()
        self.api.assets.append({'name': 'old.apk'})
        with self.assertRaisesRegex(RuntimeError, 'Unexpected'):
            self.run_release()
        self.assertEqual(self.api.mutations, [])

    def test_reused_model_pack_missing_blocks_creation(self):
        self.api.models.pop()
        with self.assertRaisesRegex(RuntimeError, 'Reusable model asset missing'):
            self.run_release()
        self.assertEqual(self.api.mutations, [])

    def test_starter_replaced_by_other_actor_is_not_deleted(self):
        self.api.seed([common.APK])
        self.api.assets[0].update(state='starter', size=0, digest=None)
        api_call = self.api.api
        def changed(path, method='GET', body=None):
            if '/releases/assets/' in path and method == 'GET':
                return self.api.asset(common.APK)
            return api_call(path, method, body)
        self.api.api = changed
        with self.assertRaisesRegex(RuntimeError, 'Starter changed'):
            self.run_release()
        self.assertFalse(any(m[0] in ('DELETE', 'PATCH') for m in self.api.mutations))

    def test_duplicate_release_fails(self):
        self.api.seed()
        self.api.extra_releases.append(copy.deepcopy(self.api.release))
        with self.assertRaisesRegex(RuntimeError, 'Multiple'):
            self.run_release()
        self.assertEqual(self.api.mutations, [])

    def test_wrong_tag_commit_fails(self):
        self.api.target = 'b' * 40
        with self.assertRaisesRegex(RuntimeError, 'another commit'):
            self.run_release()
        self.assertEqual(self.api.mutations, [])

    def test_wrong_existing_release_provenance_fails(self):
        self.api.seed()
        self.api.release['body'] = 'Someone else\'s draft'
        with self.assertRaisesRegex(RuntimeError, 'provenance'):
            self.run_release()
        self.assertEqual(self.api.mutations, [])

    def test_wrong_target_commitish_fails(self):
        self.api.seed()
        self.api.release['target_commitish'] = 'main'
        with self.assertRaisesRegex(RuntimeError, 'different publication'):
            self.run_release()
        self.assertEqual(self.api.mutations, [])

    def test_stable_changed_fails_before_mutation(self):
        self.api.stable = 'changed'
        with self.assertRaisesRegex(RuntimeError, 'stable.json changed'):
            self.run_release()
        self.assertEqual(self.api.mutations, [])

    def test_stable_changes_during_upload_blocks_publish(self):
        upload = self.api.upload
        def changed(*args):
            upload(*args)
            self.api.stable = 'changed'
        self.api.upload = changed
        with self.assertRaisesRegex(RuntimeError, 'stable.json changed'):
            self.run_release()
        self.assertTrue(self.api.release['draft'])
        self.assertFalse(any(m[0] == 'PATCH' for m in self.api.mutations))

    def test_bad_uploaded_digest_blocks_publish(self):
        self.api.bad_upload_digest = True
        with self.assertRaisesRegex(RuntimeError, 'failed verification'):
            self.run_release()
        self.assertTrue(self.api.release['draft'])

    def test_publish_403_stops_then_can_retry(self):
        self.api.fail_publish = True
        with self.assertRaisesRegex(RuntimeError, '403'):
            self.run_release()
        self.assertTrue(self.api.release['draft'])
        self.api.fail_publish = False
        self.run_release()
        self.assertEqual(len([m for m in self.api.mutations if m[0] == 'UPLOAD']), 3)

    def test_lost_publish_response_rerun_is_read_only(self):
        self.api.lose_publish_response = True
        with self.assertRaises(RuntimeError):
            self.run_release()
        count = len(self.api.mutations)
        self.run_release()
        self.assertEqual(len(self.api.mutations), count)

    def test_latest_changed_after_publish_is_reported_as_failure(self):
        api_call = self.api.api
        def changed(path, method='GET', body=None):
            result = api_call(path, method, body)
            if method == 'PATCH':
                self.api.latest += 1
            return result
        self.api.api = changed
        with self.assertRaisesRegex(RuntimeError, 'Latest stable'):
            self.run_release()

    def test_pagination_reads_beyond_first_page(self):
        api = release.GitHub()
        with patch.object(api, 'api', side_effect=[[{'tag_name': 'old'}] * 100,
                                                 [{'tag_name': common.TAG, 'id': 123}]]) as call:
            self.assertEqual(release.find_release(api)['id'], 123)
            self.assertIn('page=2', call.call_args.args[0])

    def test_unauthorized_api_does_not_create_release(self):
        self.api.api = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('HTTP 401'))
        with self.assertRaisesRegex(RuntimeError, '401'):
            self.run_release()
        self.assertEqual(self.api.mutations, [])


class VerificationTests(unittest.TestCase):
    def test_signature_and_identity_parse(self):
        output = 'Signer #1 certificate SHA-256 digest: ' + common.SIGNER + '\n'
        badging = "package: name='local.eidolon.sc.android.preview' versionCode='143' versionName='1.4.3-preview.1'\n"
        with patch.object(check, 'command', side_effect=[output, badging]):
            self.assertEqual(check.apk_identity('fake.apk'), (common.PACKAGE, 143, common.VERSION))

    def test_wrong_or_multiple_signers_rejected(self):
        for signature in ['Signer #1 certificate SHA-256 digest: ' + '0' * 64,
                          'Signer #1 certificate SHA-256 digest: ' + common.SIGNER + '\n' +
                          'Signer #2 certificate SHA-256 digest: ' + common.SIGNER]:
            with self.subTest(signature=signature), patch.object(check, 'command', return_value=signature):
                with self.assertRaisesRegex(RuntimeError, 'signing certificate'):
                    check.apk_identity('fake.apk')

    def test_invalid_signature_command_fails(self):
        with patch.object(check, 'command', side_effect=subprocess.CalledProcessError(1, 'apksigner')):
            with self.assertRaises(subprocess.CalledProcessError):
                check.apk_identity('fake.apk')

    def test_debuggable_apk_rejected(self):
        signature = 'Signer #1 certificate SHA-256 digest: ' + common.SIGNER
        badging = "package: name='x' versionCode='1' versionName='1'\napplication-debuggable\n"
        with patch.object(check, 'command', side_effect=[signature, badging]):
            with self.assertRaisesRegex(RuntimeError, 'Debuggable'):
                check.apk_identity('fake.apk')

    def test_weights_rejected_and_public_corpus_allowed(self):
        with tempfile.TemporaryDirectory() as td, patch.object(check, 'MODEL_METADATA', {}):
            path = Path(td) / 'app.apk'
            for name in ['assets/judge/model.gguf', 'assets/neural/model.onnx',
                         'assets/neural/a.bin', 'assets/offline-asr/model.zip', 'assets/semantic.db']:
                with zipfile.ZipFile(path, 'w') as z:
                    z.writestr(name, b'test')
                with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, 'Bundled model'):
                    check.check_model_separation(path)
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('assets/corpus.db', b'public corpus')
                z.writestr('assets/neural/e5.spm', b'tokenizer')
            check.check_model_separation(path)

    def test_changed_model_metadata_rejected(self):
        with tempfile.TemporaryDirectory() as td, patch.object(check, 'MODEL_METADATA', {'judge/model.json': 'wrong'}):
            path = Path(td) / 'app.apk'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('assets/judge/model.json', '{}')
            with self.assertRaisesRegex(RuntimeError, 'Model metadata changed'):
                check.check_model_separation(path)

    def test_safe_zip_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'source.zip'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr('../key.jks', b'x')
            with zipfile.ZipFile(path) as z, self.assertRaisesRegex(RuntimeError, 'Unsafe'):
                check.safe_zip(z)

    def test_delta_bounds_and_exact_length(self):
        output = io.BytesIO()
        reconstruct.apply_delta(io.BytesIO(b'abcdef'), output, b'XY', [('C', 1, 3), ('L', 0, 2)], 6, 5)
        self.assertEqual(output.getvalue(), b'bcdXY')
        for ops, size in [([('C', 5, 2)], 2), ([('L', 0, 4)], 4), ([('C', -1, 1)], 1),
                          ([('X', 0, 1)], 1), ([('C', 0, 2)], 1), ([('L', 0, 1)], 2)]:
            with self.subTest(ops=ops, size=size), self.assertRaises(RuntimeError):
                reconstruct.apply_delta(io.BytesIO(b'abcdef'), io.BytesIO(), b'XY', ops, 6, size)

    def test_guards_survive_optimized_python(self):
        proc = subprocess.run([sys.executable, '-O', '-c',
                               'from common import require; require(False, "blocked")'],
                              cwd=common.ROOT, capture_output=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn(b'blocked', proc.stderr)

    def test_default_verify_only_does_not_call_github(self):
        with patch.object(release, 'reconstruct', return_value=('staging', 'base')), \
             patch.object(release, 'verify_assets', return_value=EXPECTED), \
             patch.object(release, 'GitHub') as api, patch('sys.stdout', new_callable=io.StringIO) as output:
            self.assertEqual(release.main([]), 0)
            api.assert_not_called()
            self.assertFalse(json.loads(output.getvalue())['published'])

    def test_failed_local_validation_exits_one_before_github(self):
        env = {'GITHUB_REPOSITORY': common.REPO, 'GITHUB_REF': 'refs/heads/' + common.BRANCH,
               'GITHUB_SHA': COMMIT, 'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GH_TOKEN': 'fake-token'}
        with patch.dict(os.environ, env), patch.object(release, 'reconstruct', return_value=('s', 'b')), \
             patch.object(release, 'verify_assets', side_effect=RuntimeError('bad signature')), \
             patch.object(release, 'GitHub') as api, patch('sys.stderr', new_callable=io.StringIO):
            self.assertEqual(release.main(['--publish']), 1)
            api.assert_not_called()

    def test_missing_payload_exits_one(self):
        with patch.object(release, 'reconstruct', side_effect=RuntimeError('Missing payload')), \
             patch('sys.stderr', new_callable=io.StringIO):
            self.assertEqual(release.main([]), 1)

    def test_remote_api_failure_exits_one(self):
        env = {'GITHUB_REPOSITORY': common.REPO, 'GITHUB_REF': 'refs/heads/' + common.BRANCH,
               'GITHUB_SHA': COMMIT, 'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GH_TOKEN': 'fake-token'}
        with patch.dict(os.environ, env), patch.object(release, 'reconstruct', return_value=('s', 'b')), \
             patch.object(release, 'verify_assets', return_value=EXPECTED), \
             patch.object(release, 'publish', side_effect=RuntimeError('HTTP 403')), \
             patch('sys.stderr', new_callable=io.StringIO):
            self.assertEqual(release.main(['--publish']), 1)

    def test_push_event_cannot_publish(self):
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': common.REPO,
                                    'GITHUB_REF': 'refs/heads/' + common.BRANCH,
                                    'GITHUB_EVENT_NAME': 'push'}), \
             patch.object(release, 'reconstruct') as reconstruct_call, \
             patch('sys.stderr', new_callable=io.StringIO):
            self.assertEqual(release.main(['--publish']), 1)
            reconstruct_call.assert_not_called()


if __name__ == '__main__':
    unittest.main()
