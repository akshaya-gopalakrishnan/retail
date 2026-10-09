#!/usr/bin/env python3
"""Package public assets for a versioned R2 release; never uploads or changes DNS."""

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

EXTENSIONS = {".js", ".css", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2", ".ttf", ".eot", ".mp3", ".ogg", ".wav"}


def package(bench, output, origin):
    bench, output = Path(bench).resolve(), Path(output).resolve()
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/") or parsed.query or parsed.fragment or parsed.username:
        raise ValueError("CDN origin must be an HTTPS hostname, without a path or credentials")
    bundles = json.loads((bench / "sites/assets/assets.json").read_text())
    rtl = bench / "sites/assets/assets-rtl.json"
    if rtl.exists():
        bundles.update(json.loads(rtl.read_text()))
    assets = {}
    for app in (bench / "sites/apps.txt").read_text().splitlines():
        if not app:
            continue
        public = (bench / "apps" / app / app / "public").resolve()
        for source in public.rglob("*"):
            if not source.is_file() or source.suffix.lower() not in EXTENSIONS:
                continue
            relative = source.relative_to(public)
            if any(part.startswith(".") or part == "node_modules" for part in relative.parts):
                continue
            if not source.resolve().is_relative_to(public):
                continue
            assets[f"/assets/{app}/{relative.as_posix()}"] = source.read_bytes()
    for path in bundles.values():
        if path not in assets:
            raise ValueError(f"Missing bundle: {path}; rebuild all installed apps first")
    fingerprint = hashlib.sha256()
    fingerprint.update(json.dumps(bundles, sort_keys=True).encode())
    for path, content in sorted(assets.items()):
        fingerprint.update(path.encode() + b"\0" + hashlib.sha256(content).digest())
    release = fingerprint.hexdigest()[:24]
    destination = output / release
    if destination.exists():
        raise ValueError("Release directory already exists; use a fresh output directory")
    base = origin.rstrip("/") + "/" + release
    manifest = {"release": release, "bundles": bundles, "files": {}}
    for path, content in sorted(assets.items()):
        target = destination / path.lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.suffix == ".css":
            # Preserve absolute /assets references on the shared asset origin.
            content = re.sub(rb"([\"'(])(/assets/)", lambda m: m[1] + base.encode() + m[2], content)
        target.write_bytes(content)
        manifest["files"][path] = hashlib.sha256(content).hexdigest()
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return destination, base


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", default=str(Path(__file__).resolve().parents[3]))
    parser.add_argument("--output", required=True)
    parser.add_argument("--origin", required=True)
    args = parser.parse_args()
    directory, base = package(args.bench, args.output, args.origin)
    print(json.dumps({"directory": str(directory), "retail_cdn_url": base,
                      "retail_cdn_manifest": str(directory / "manifest.json")}, indent=2))
