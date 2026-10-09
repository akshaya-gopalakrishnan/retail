#!/usr/bin/env python3
"""Publish a packaged release to R2. Requires AWS CLI and bucket-scoped credentials.

Credentials are read by AWS CLI from its environment/profile, never arguments.
Upload data first and the activation manifest last. Existing releases are retained.
"""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


def commands(directory, bucket, account):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / "manifest.json").read_text())
    release = manifest["release"]
    if directory.name != release or not re.fullmatch(r"[a-f0-9]{24}", release):
        raise ValueError("Invalid release directory")
    if not re.fullmatch(r"[a-fA-F0-9]{32}", account):
        raise ValueError("Expected Cloudflare's 32-character account ID")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket):
        raise ValueError("Invalid bucket name")
    actual_files = {"/" + source.relative_to(directory).as_posix()
                    for source in (directory / "assets").rglob("*") if source.is_file()}
    if actual_files != set(manifest["files"]):
        raise ValueError("Release contains missing or unlisted files")
    for path, digest in manifest["files"].items():
        source = directory / path.lstrip("/")
        if not source.resolve().is_relative_to(directory) or hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Asset integrity check failed: {path}")
    endpoint = f"https://{account}.r2.cloudflarestorage.com"
    destination = f"s3://{bucket}/{release}"
    common = ["--endpoint-url", endpoint, "--region", "auto"]
    return [
        ["aws", "s3", "sync", str(directory / "assets"), destination + "/assets",
         "--cache-control", "public,max-age=31536000,immutable", *common],
        ["aws", "s3", "cp", str(directory / "manifest.json"), destination + "/manifest.json",
         "--content-type", "application/json", "--cache-control", "public,max-age=31536000,immutable", *common],
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--upload", action="store_true", help="Upload; otherwise print the plan only")
    args = parser.parse_args()
    for command in commands(args.directory, args.bucket, args.account_id):
        if args.upload:
            subprocess.run(command, check=True)
        else:
            print(json.dumps(command))
