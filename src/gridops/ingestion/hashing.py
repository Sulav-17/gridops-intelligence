"""Content hashing helpers for source payload evidence."""

from pathlib import Path


def sha256_bytes(payload: bytes) -> str:
    """Return the lowercase SHA-256 hex digest for payload bytes."""

    import hashlib

    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 hex digest for a file."""

    import hashlib

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()
