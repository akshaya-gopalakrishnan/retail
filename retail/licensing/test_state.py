import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from retail.licensing import state
from retail.licensing import test_signature


class TestProtectedState(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state.json"
        config = patch.object(state.frappe, "conf", {"celesta_license_state_path": str(self.path)})
        config.start()
        self.addCleanup(config.stop)
        self.fixture = test_signature.TestSignature()
        self.fixture.setUp()

    def verify(self, now=1001, offline=False):
        return state.verify_protected(self.fixture.token(), self.fixture.keys, "installation-1", now, offline=offline)

    def test_bootstrap_permissions_and_no_secret(self):
        with self.assertRaises(ValueError):
            self.verify(offline=True)
        self.verify()
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved['highest_license_version'], 1)
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)
        self.assertNotIn(self.fixture.token(), self.path.read_text())
        self.assertNotIn('license_key', saved)

    def test_progression_tolerance_rollback_restart(self):
        self.verify()
        self.verify(2000, offline=True)
        self.verify(1950, offline=True)
        self.assertEqual(json.loads(self.path.read_text())['highest_trusted_time'], 2000)
        # A fresh module/process reads the disk floor, without an in-memory cache.
        import importlib
        importlib.reload(state)
        with self.assertRaises(ValueError):
            self.verify(1939, offline=True)
        self.verify(2100, offline=True)

    def test_restored_older_version_and_iat_newer_accepted(self):
        self.verify()
        self.fixture.claims.update(license_version=2, iat=1100, nbf=1100, exp=87500)
        self.verify(1101)
        self.fixture.claims['license_version'] = 1
        with self.assertRaises(ValueError):
            self.verify(1102, offline=True)
        self.fixture.claims.update(license_version=2, iat=1000, nbf=1000, exp=87400)
        with self.assertRaises(ValueError):
            self.verify(1102, offline=True)
        self.fixture.claims.update(license_version=3, iat=1200, nbf=1200, exp=87600)
        self.verify(1201)

    def test_corruption_binding_and_missing_configuration_fail_closed(self):
        self.verify()
        self.path.write_text('{}')
        with self.assertRaises(ValueError):
            self.verify()
        self.path.unlink()
        self.verify()
        with self.assertRaises(ValueError):
            with state.protected_state('other', online=True):
                pass
        with patch.object(state.frappe, 'conf', {}):
            with self.assertRaises(ValueError):
                self.verify()

    def test_denial_advances_floor_and_rejects_prior_active_token(self):
        self.verify()
        original = self.fixture.token()
        self.fixture.claims.update(license_version=2)
        self.fixture.claims['rules']['status'] = 'Revoked'
        self.fixture.claims['exp'] = 1000
        self.verify()
        with self.assertRaises(ValueError):
            state.verify_protected(original, self.fixture.keys, 'installation-1', 1001, offline=True)

    def test_site_backup_paths_and_symlink_aliases_rejected(self):
        with patch.object(state.frappe.local, "sites_path", self.directory.name, create=True):
            with self.assertRaisesRegex(ValueError, "outside the sites"):
                self.verify()
            with tempfile.TemporaryDirectory() as elsewhere:
                alias = Path(elsewhere) / "site-alias"
                alias.symlink_to(self.directory.name, target_is_directory=True)
                with patch.dict(state.frappe.conf, {"celesta_license_state_path": str(alias / "state.json")}):
                    with self.assertRaisesRegex(ValueError, "outside the sites"):
                        self.verify()
        self.assertFalse(self.path.exists())

    def test_identity_change_never_resets_any_floor_even_with_signed_transition(self):
        self.fixture.claims['license_version'] = 5
        self.verify()
        before = self.path.read_bytes()
        for version in (1, 6):
            self.fixture.claims.update(license_id='CL-2', license_version=version, iat=1100, nbf=1100, exp=87500)
            self.fixture.claims['transition'] = {
                'from': 'CL-1', 'to': 'CL-2', 'installation_id': 'installation-1',
                'nonce': 'fresh-request', 'iat': 1100, 'version': version}
            for offline in (False, True):
                with self.assertRaisesRegex(ValueError, "identity change"):
                    state.verify_protected(self.fixture.token(), self.fixture.keys, 'installation-1', 1101,
                                           offline=offline, transition_nonce='fresh-request')
                self.assertEqual(self.path.read_bytes(), before)

    def test_same_identity_renewal_preserves_floors_and_rejects_old_token(self):
        self.fixture.claims['license_version'] = 5
        self.verify()
        old = self.fixture.token()
        before = json.loads(self.path.read_text())
        self.fixture.claims.update(license_version=6, iat=1100, nbf=1100, exp=87500)
        self.verify(1101)
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved['license_id'], 'CL-1')
        self.assertEqual(saved['retired_license_ids'], [])
        for counter in state.COUNTERS:
            self.assertGreaterEqual(saved[counter], before[counter])
        for offline in (False, True):
            with self.assertRaises(ValueError):
                state.verify_protected(old, self.fixture.keys, 'installation-1', 1102, offline=offline)
        self.assertEqual(json.loads(self.path.read_text()), saved)

    def test_expired_authentic_token_persists_time_before_denial(self):
        self.verify()
        with self.assertRaises(ValueError):
            self.verify(87401, offline=True)
        self.assertEqual(json.loads(self.path.read_text())['highest_trusted_time'], 87401)
        for now in (87399, 1001):
            with self.assertRaises(ValueError):
                self.verify(now, offline=True)
        self.assertEqual(json.loads(self.path.read_text())['highest_trusted_time'], 87401)

    def test_inactive_and_future_authentic_tokens_persist_floors(self):
        self.verify()
        for version, status in enumerate(('Revoked', 'Suspended', 'NotYetActive'), 2):
            self.fixture.claims.update(license_version=version, exp=1000)
            self.fixture.claims['rules']['status'] = status
            with self.assertRaises(ValueError):
                self.verify(1200 + version, offline=True)
            saved = json.loads(self.path.read_text())
            self.assertEqual(saved['highest_license_version'], version)
            self.assertEqual(saved['highest_trusted_time'], 1200 + version)
        self.fixture.claims.update(license_version=5, iat=2000, nbf=2000, exp=88400)
        self.fixture.claims['rules']['status'] = 'Active'
        with self.assertRaises(ValueError):
            self.verify(1300, offline=True)
        self.assertEqual(json.loads(self.path.read_text())['highest_trusted_time'], 2000)

    def test_untrusted_malformed_and_tampered_tokens_never_advance_state(self):
        self.verify()
        before = self.path.read_bytes()
        token = self.fixture.token()
        for bad, keys in ((token[:-8] + 'AAAAAAAA', self.fixture.keys), ('malformed', self.fixture.keys),
                          (token, [])):
            with self.assertRaises(Exception):
                state.verify_protected(bad, keys, 'installation-1', 90000, offline=True)
            self.assertEqual(self.path.read_bytes(), before)
        self.fixture.claims['rules']['allowed_users'] = 'malformed'
        with self.assertRaises(ValueError):
            self.verify(90000, offline=True)
        self.assertEqual(self.path.read_bytes(), before)

    def test_legacy_identity_upgrade_preserves_floors(self):
        self.verify()
        saved = json.loads(self.path.read_text())
        del saved['license_id']
        del saved['retired_license_ids']
        self.path.write_text(json.dumps(saved))
        self.fixture.claims['license_id'] = 'forged-change'
        with self.assertRaises(ValueError):
            self.verify()
        self.fixture.claims['license_id'] = 'CL-1'
        self.verify(offline=True)
        self.assertEqual(json.loads(self.path.read_text())['license_id'], 'CL-1')
