import base64
import hashlib
import json
import unittest

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from retail.licensing.signature import verify_response


class TestSignature(unittest.TestCase):
    def setUp(self):
        self.key = Ed25519PrivateKey.generate()
        raw = self.key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.keys = [base64.b64encode(raw).decode()]
        self.header = dict(alg="EdDSA", typ="JWT", kid=hashlib.sha256(raw).hexdigest()[:16])
        self.claims = dict(iss="celesta_license", aud="celesta_retail", sub="installation-1",
                           license_id="CL-1", license_version=1, iat=1000, nbf=1000, exp=87400,
                           rules=dict(status="Active", allowed_users=5, max_devices=2,
                                      max_sessions_per_user=1, device_restriction_enabled=True,
                                      expiry_date=None, offline_grace_days=1))

    def token(self):
        def enc(value):
            return base64.urlsafe_b64encode(value).rstrip(b"=").decode()
        body = ".".join(enc(json.dumps(part).encode()) for part in (self.header, self.claims))
        return body + "." + enc(self.key.sign(body.encode()))

    def check(self, **kwargs):
        return verify_response(self.token(), self.keys, "installation-1", 1001, **kwargs)

    def test_valid_signature(self):
        self.assertEqual(self.check()["rules"]["allowed_users"], 5)

    def test_tampering(self):
        head, body, signature = self.token().split(".")
        changed = base64.urlsafe_b64encode(b'{"rules":{"allowed_users":999}}').rstrip(b"=").decode()
        with self.assertRaises(InvalidSignature):
            verify_response(f"{head}.{changed}.{signature}", self.keys, "installation-1", 1001)

    def test_scope_algorithm_and_times(self):
        for field, value in (("sub", "other"), ("iss", "other"), ("aud", "other"),
                             ("iat", 1), ("nbf", 2000), ("exp", 999999), ("iat", True)):
            with self.subTest(field=field, value=value):
                old = self.claims[field]
                self.claims[field] = value
                with self.assertRaises(ValueError):
                    self.check()
                self.claims[field] = old
        self.header["alg"] = "none"
        with self.assertRaises(ValueError):
            self.check()

    def test_reject_rollback_and_untrusted_key(self):
        with self.assertRaises(ValueError):
            self.check(previous_issued=1002)
        with self.assertRaises(ValueError):
            verify_response(self.token(), [], "installation-1", 1001)

    def test_signed_denial_and_zero_grace_can_update_display(self):
        for status in ("Revoked", "Suspended", "Expired", "NotYetActive"):
            self.claims["rules"].update(status=status, offline_grace_days=0)
            self.claims["exp"] = 1000
            self.assertEqual(self.check()["rules"]["status"], status)

    def test_version_and_active_zero_grace_rejected(self):
        for value in (None, 0, -1, True, '1'):
            self.claims['license_version'] = value
            with self.assertRaises(ValueError):
                self.check()
        self.claims['license_version'] = 1
        self.claims['rules']['offline_grace_days'] = 0
        self.claims['exp'] = 1000
        with self.assertRaises(ValueError):
            self.check()
