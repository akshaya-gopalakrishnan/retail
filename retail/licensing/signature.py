"""Verify central Ed25519 responses using deployment-pinned public keys."""
import base64
import hashlib
import json
from datetime import date

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


RULE_FIELDS = ("status", "allowed_users", "max_devices", "max_sessions_per_user",
               "device_restriction_enabled", "expiry_date", "offline_grace_days")


def _decode(value):
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)


def verify_response(token, public_keys, installation_id, now, previous_issued=0, *, offline=False, authenticate_only=False):
    """Validate a fresh live response, including signed inactive states.

    This is NOT an offline authorization predicate: inactive and expired licenses
    must still replace local display data after an authenticated live check.
    """
    if not isinstance(token, str) or len(token) > 16384:
        raise ValueError("Invalid token")
    head, body, sig = token.split(".")
    header = json.loads(_decode(head))
    if not isinstance(header, dict) or header.get("alg") != "EdDSA" or header.get("typ") != "JWT" or header.get("crit"):
        raise ValueError("Unsupported token header")
    keys = [base64.b64decode(key, validate=True) for key in public_keys]
    key = next((key for key in keys if hashlib.sha256(key).hexdigest()[:16] == header.get("kid")), None)
    if key is None:
        raise ValueError("Untrusted signing key")
    Ed25519PublicKey.from_public_bytes(key).verify(_decode(sig), f"{head}.{body}".encode("ascii"))
    claims = json.loads(_decode(body))
    if not isinstance(claims, dict):
        raise ValueError("Invalid claims")
    if not isinstance(installation_id, str) or not installation_id:
        raise ValueError("Missing installation identity")
    if (claims.get("iss"), claims.get("aud"), claims.get("sub")) != (
        "celesta_license", "celesta_retail", installation_id
    ):
        raise ValueError("Wrong token scope")
    if type(claims.get("license_version")) is not int or claims["license_version"] < 1:
        raise ValueError("Invalid license version")
    for field in ("iat", "nbf", "exp"):
        if type(claims.get(field)) is not int:
            raise ValueError("Invalid time claim")
    issued = claims["iat"]
    if not authenticate_only and ((not offline and not now - 300 <= issued <= now + 60) or issued < previous_issued):
        raise ValueError("Stale response or clock rollback")
    if claims["nbf"] != issued or (not authenticate_only and claims["nbf"] > now + 60):
        raise ValueError("Invalid validity start")
    if not isinstance(claims.get("license_id"), str) or not claims["license_id"]:
        raise ValueError("Missing license identity")
    rules = claims["rules"]
    if not isinstance(rules, dict):
        raise ValueError("Invalid rules")
    if rules.get("status") not in ("Active", "Suspended", "Expired", "Revoked", "NotYetActive"):
        raise ValueError("Invalid license status")
    for field in ("allowed_users", "max_devices", "max_sessions_per_user", "offline_grace_days"):
        if type(rules.get(field)) is not int or rules[field] < 0:
            raise ValueError("Invalid license limit")
    if rules["status"] == "Active" and rules["offline_grace_days"] < 1:
        raise ValueError("Active licenses require positive offline grace")
    if type(rules.get("device_restriction_enabled")) is not bool:
        raise ValueError("Invalid device restriction")
    if rules.get("expiry_date") is not None:
        date.fromisoformat(rules["expiry_date"])
    if claims["exp"] > issued + rules["offline_grace_days"] * 86400:
        raise ValueError("Invalid offline deadline")
    if rules["status"] != "Active" and claims["exp"] > issued:
        raise ValueError("Inactive license grants offline validity")
    if rules["status"] == "Active" and claims["exp"] < issued:
        raise ValueError("Active response already expired")
    if "customer_name" in rules and not isinstance(rules["customer_name"], str):
        raise ValueError("Invalid customer name")
    if not authenticate_only and offline and (rules["status"] != "Active" or not issued <= now < claims["exp"]):
        raise ValueError("License is not locally valid")
    return claims
