import json
from pathlib import Path
import tempfile
import unittest
import publish


class PublicationContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = {'GITHUB_REPOSITORY': publish.REPO,
                    'GITHUB_REF': 'refs/heads/' + publish.BRANCH,
                    'GITHUB_EVENT_NAME': 'push', 'GH_TOKEN': 'test-token'}
        (self.root / 'publish-request.json').write_text(json.dumps(publish.PUSH_REQUEST))

    def test_authorized_push(self):
        publish.publication_context(self.env, self.root)

    def test_manual_dispatch_retained(self):
        self.env['GITHUB_EVENT_NAME'] = 'workflow_dispatch'
        (self.root / 'publish-request.json').unlink()
        publish.publication_context(self.env, self.root)

    def test_wrong_context_stops(self):
        for key, value in [('GITHUB_REPOSITORY', 'other/repo'),
                           ('GITHUB_REF', 'refs/heads/main'),
                           ('GITHUB_EVENT_NAME', 'pull_request'),
                           ('GH_TOKEN', '')]:
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                publish.publication_context(dict(self.env, **{key: value}), self.root)

    def test_missing_request_stops(self):
        (self.root / 'publish-request.json').unlink()
        with self.assertRaises(RuntimeError):
            publish.publication_context(self.env, self.root)

    def test_changed_identity_stops(self):
        for key in publish.PUSH_REQUEST:
            request = dict(publish.PUSH_REQUEST, **{key: 'wrong'})
            (self.root / 'publish-request.json').write_text(json.dumps(request))
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                publish.publication_context(self.env, self.root)
