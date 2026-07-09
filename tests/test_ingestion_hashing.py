"""Tests for ingestion hashing utilities."""

from pathlib import Path

from gridops.ingestion.hashing import sha256_bytes, sha256_file


def test_sha256_bytes_returns_expected_hex_digest() -> None:
    """Payload hashes are deterministic SHA-256 hex digests."""

    assert sha256_bytes(b"gridops") == (
        "cebf832b96b7354ea84ea2bcf71c5068900906fa7bf4581043070ba0b56f0633"
    )


def test_sha256_file_matches_payload_hash(tmp_path: Path) -> None:
    """File hashing uses the same SHA-256 contract as byte hashing."""

    payload = b"source payload"
    path = tmp_path / "payload.csv"
    path.write_bytes(payload)

    assert sha256_file(path) == sha256_bytes(payload)
