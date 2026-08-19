#!/usr/bin/env python3
"""Download a Docker Registry image as a resumable OCI image layout.

This is intended for very large WebArena-Verified site images. ``docker pull``
restarts an interrupted layer, while this helper persists partial blobs and
continues them with HTTP Range requests. The completed directory can be loaded
with ``tar -C OUTPUT -cf - oci-layout index.json blobs | docker load``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import requests


REGISTRY = "https://registry-1.docker.io"
AUTH = "https://auth.docker.io/token"
MANIFEST_ACCEPT = "application/vnd.docker.distribution.manifest.v2+json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="Docker Hub repository, e.g. owner/image")
    parser.add_argument("--tag", default="latest")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--chunk-mib", type=int, default=8)
    parser.add_argument("--retries", type=int, default=100)
    return parser.parse_args()


def _token(session: requests.Session, repository: str) -> str:
    response = session.get(
        AUTH,
        params={
            "service": "registry.docker.io",
            "scope": f"repository:{repository}:pull",
        },
        timeout=60,
    )
    response.raise_for_status()
    return str(response.json()["token"])


def _sha256(path: Path, chunk_size: int) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(chunk_size):
            digest.update(block)
    return digest.hexdigest()


def _download_blob(
    session: requests.Session,
    repository: str,
    descriptor: dict[str, Any],
    output: Path,
    *,
    chunk_size: int,
    retries: int,
) -> None:
    digest = str(descriptor["digest"])
    algorithm, expected_hash = digest.split(":", 1)
    if algorithm != "sha256":
        raise ValueError(f"unsupported digest: {digest}")
    expected_size = int(descriptor["size"])
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.stat().st_size > expected_size:
        output.unlink()

    attempt = 0
    while not output.exists() or output.stat().st_size < expected_size:
        offset = output.stat().st_size if output.exists() else 0
        headers = {"Authorization": f"Bearer {_token(session, repository)}"}
        # Bound every request to one persisted chunk. Some HTTP proxies keep a
        # multi-gigabyte Registry response half-open after transferring data;
        # short ranges turn that failure mode into cheap, resumable requests.
        range_end = min(expected_size - 1, offset + chunk_size - 1)
        headers["Range"] = f"bytes={offset}-{range_end}"
        try:
            with session.get(
                f"{REGISTRY}/v2/{repository}/blobs/{digest}",
                headers=headers,
                stream=True,
                timeout=(60, 180),
            ) as response:
                response.raise_for_status()
                if response.status_code != 206:
                    raise RuntimeError(
                        f"registry ignored resume offset {offset}: HTTP {response.status_code}"
                    )
                mode = "ab" if offset else "wb"
                with output.open(mode) as stream:
                    for block in response.iter_content(chunk_size=chunk_size):
                        if block:
                            stream.write(block)
            attempt = 0
        except (requests.RequestException, OSError, RuntimeError) as error:
            attempt += 1
            if attempt > retries:
                raise RuntimeError(f"failed downloading {digest}") from error
            completed = output.stat().st_size if output.exists() else 0
            print(
                f"retry={attempt} blob={expected_hash[:12]} "
                f"completed={completed}/{expected_size} error={error}",
                flush=True,
            )
            time.sleep(min(30, 2 * attempt))

    actual_size = output.stat().st_size
    if actual_size != expected_size:
        raise RuntimeError(f"size mismatch for {digest}: {actual_size} != {expected_size}")
    actual_hash = _sha256(output, chunk_size)
    if actual_hash != expected_hash:
        raise RuntimeError(f"digest mismatch for {digest}: sha256:{actual_hash}")
    print(f"verified blob={expected_hash} bytes={expected_size}", flush=True)


def main() -> int:
    args = parse_args()
    repository = args.image.removeprefix("docker.io/").removeprefix("library/")
    output = args.output.resolve()
    blobs = output / "blobs" / "sha256"
    blobs.mkdir(parents=True, exist_ok=True)
    session = requests.Session()

    token = _token(session, repository)
    response = session.get(
        f"{REGISTRY}/v2/{repository}/manifests/{args.tag}",
        headers={"Authorization": f"Bearer {token}", "Accept": MANIFEST_ACCEPT},
        timeout=60,
    )
    response.raise_for_status()
    manifest_bytes = response.content
    manifest = response.json()
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    (blobs / manifest_hash).write_bytes(manifest_bytes)

    descriptors = [manifest["config"], *manifest["layers"]]
    for descriptor in descriptors:
        digest_hash = str(descriptor["digest"]).split(":", 1)[1]
        _download_blob(
            session,
            repository,
            descriptor,
            blobs / digest_hash,
            chunk_size=args.chunk_mib * 1024 * 1024,
            retries=args.retries,
        )

    (output / "oci-layout").write_text(
        json.dumps({"imageLayoutVersion": "1.0.0"}) + "\n", encoding="utf-8"
    )
    index = {
        "schemaVersion": 2,
        "manifests": [
            {
                "mediaType": manifest.get("mediaType", MANIFEST_ACCEPT),
                "digest": f"sha256:{manifest_hash}",
                "size": len(manifest_bytes),
                "annotations": {
                    "org.opencontainers.image.ref.name": (
                        f"docker.io/{repository}:{args.tag}"
                    )
                },
            }
        ],
    }
    (output / "index.json").write_text(
        json.dumps(index, indent=2) + "\n", encoding="utf-8"
    )
    print(f"OCI image layout ready: {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
