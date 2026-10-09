"""Deployment-owned rollback floor, independent of the site database/backup."""
import fcntl
import hashlib
import json
import os
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path

import frappe

CLOCK_TOLERANCE = 60  # seconds; effective authorization time never goes backwards
COUNTERS = ("highest_license_version", "highest_accepted_iat", "highest_trusted_time")


@contextmanager
def protected_state(installation_id, *, online=False):
    configured = frappe.conf.get("celesta_license_state_path")
    if not isinstance(configured, str) or not Path(configured).is_absolute():
        raise ValueError("Configure an absolute protected license state path")
    path = Path(configured)
    sites_path = getattr(frappe.local, "sites_path", None)
    if sites_path and path.resolve().is_relative_to(Path(sites_path).resolve()):
        raise ValueError("License state must be outside the sites directory and site backups")
    # Deployment creates a private directory outside site backups; never auto-reset it.
    directory = path.parent.stat()
    if directory.st_uid != os.geteuid() or stat.S_IMODE(directory.st_mode) != 0o700:
        raise ValueError("License state directory must be owned by the service user and mode 0700")
    fd = os.open(str(path) + ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            state_fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            if not online:
                raise ValueError("Online verification is required to initialize protected state")
            state = dict.fromkeys(COUNTERS, 0)
            state["installation_id"] = installation_id
            state.update(license_id=None, retired_license_ids=[])
        else:
            with os.fdopen(state_fd) as stream:
                info = os.fstat(stream.fileno())
                if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
                    raise ValueError("Unsafe license state permissions")
                state = json.load(stream)
        if (not isinstance(state, dict) or not installation_id
                or state.get("installation_id") != installation_id
                or any(type(state.get(k)) is not int or state[k] < 0 for k in COUNTERS)):
            raise ValueError("Invalid protected license state or installation binding")
        yield state
        # Atomic replacement plus fsync persists the floor across process/OS restarts.
        tmp_fd, tmp_name = tempfile.mkstemp(prefix=".license-", dir=path.parent)
        try:
            with os.fdopen(tmp_fd, "w") as stream:
                json.dump(state, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp_name, path)
            directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
    finally:
        os.close(fd)


def transition_context(installation_id):
    """Read identity from deployment state, never editable DB metadata."""
    with protected_state(installation_id, online=True) as state:
        return state.get("license_id")


def verify_protected(token, public_keys, installation_id, now, previous_issued=0, *, offline=False,
                     transition_nonce=None):
    from retail.licensing.signature import verify_response

    with protected_state(installation_id, online=not offline) as state:
        claims = verify_response(token, public_keys, installation_id, now, authenticate_only=True)
        trusted = state["highest_trusted_time"]
        effective_now = max(now, trusted)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        current = state.get("license_id")
        retired = state.get("retired_license_ids", [])
        if (current is not None and (not isinstance(current, str) or not current)
                or not isinstance(retired, list) or any(not isinstance(x, str) for x in retired)):
            raise ValueError("Invalid protected identity state")
        # Upgrade legacy floors only using the exact previously authenticated token.
        if "license_id" not in state and state.get("last_token_hash") != token_hash:
            raise ValueError("Verify the previously accepted token before upgrading protected identity state")
        if "license_id" in state and current is None and offline:
            raise ValueError("Online verification required to bind initial identity")
        replacement = current is not None and current != claims["license_id"]
        if claims["license_id"] in retired:
            raise ValueError("Retired license identity")
        if replacement:
            # Renewal/key regeneration retain the unique central identity. Never
            # reset the version floor, even for a signed legacy transition.
            raise ValueError("License identity change is not supported; renew the existing Customer License")
        if claims["iat"] < max(previous_issued, state["highest_accepted_iat"]):
            raise ValueError("License issued time rollback")
        if claims["license_version"] < state["highest_license_version"]:
            raise ValueError("License version rollback")
        state["license_id"] = claims["license_id"]
        state["retired_license_ids"] = retired
        state["highest_license_version"] = claims["license_version"]
        state["highest_accepted_iat"] = claims["iat"]
        state["highest_trusted_time"] = max(trusted, claims["iat"], int(now))
        state["last_token_hash"] = token_hash
        # Denials must occur AFTER the context manager durably writes the floors.
        clock_rollback = now + CLOCK_TOLERANCE < trusted
    if clock_rollback:
        raise ValueError("Local clock moved behind protected trusted time")
    return verify_response(token, public_keys, installation_id, effective_now,
                           previous_issued, offline=offline)
