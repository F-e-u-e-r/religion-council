"""Immutable, content-addressed snapshot store for retrieval evidence (B1a).

Identity follows ADR 0003 §4:

    artifact_id = sha256( UTF-8( NFC( text-with-newlines-normalized-to-LF ) ) )

Newlines are normalized to LF *within* the text; no trailing newline is added or
stripped. Snapshot bytes and content-derived metadata are write-once (exclusive
create, compare-on-exists); the origins log is append-only. Nothing here decides
admissibility.
"""
import hashlib
import json
import unicodedata
from pathlib import Path


class EvidenceStoreError(RuntimeError):
    """Raised when an immutable snapshot would be overwritten with different bytes."""


def _newlines_to_lf(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def canonical_bytes(text):
    """Canonical snapshot bytes. Rejects non-str (no coercion); never trims/pads."""
    if not isinstance(text, str):
        raise TypeError("snapshot text must be str, got {}".format(type(text).__name__))
    return unicodedata.normalize("NFC", _newlines_to_lf(text)).encode("utf-8")


def artifact_id(text):
    return hashlib.sha256(canonical_bytes(text)).hexdigest()


def _write_once(path, data):
    """Create a file with bytes once; if it exists, require identical bytes.

    Uses exclusive create (``xb``) — never ``os.replace``/overwrite — so an existing
    immutable snapshot is preserved (ADR 0003 §4 rules 4-5).
    """
    try:
        with open(path, "xb") as handle:
            handle.write(data)
    except FileExistsError:
        if path.read_bytes() != data:
            raise EvidenceStoreError("immutable artifact would change: {}".format(path.name))


class EvidenceStore:
    """Write-once, content-addressed snapshot store rooted at a directory."""

    def __init__(self, store_dir):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def _origins_path(self):
        return self.store_dir / "origins.jsonl"

    def put_snapshot(self, text):
        """Ingest ``text`` as an immutable artifact; return ``(artifact_id, byte_length)``.

        Idempotent by content: re-ingesting identical bytes is a no-op accept. The
        sidecar ``<id>.meta.json`` carries content-derived fields only (no origin
        hints), so identical bytes arriving from different sources never conflict.
        """
        blob = canonical_bytes(text)
        aid = hashlib.sha256(blob).hexdigest()
        _write_once(self.store_dir / aid, blob)
        meta = {
            "artifact_id": aid,
            "sha256": aid,
            "byte_length": len(blob),
            "encoding": "utf-8",
            "normalization": "NFC",
            "newline": "LF",
        }
        meta_bytes = (json.dumps(meta, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        _write_once(self.store_dir / (aid + ".meta.json"), meta_bytes)
        return aid, len(blob)

    def read_snapshot(self, artifact_id):
        """Read an immutable snapshot's canonical bytes by id (B2 verification reads these).

        The stored bytes are already canonical (NFC + LF, UTF-8), so a span search canonicalizes
        only the needle. ``artifact_id`` must be a 64-hex digest — validated to keep it a pure
        filename (no path traversal). Raises :class:`EvidenceStoreError` if the snapshot is absent.
        """
        if not (isinstance(artifact_id, str) and len(artifact_id) == 64
                and all(c in "0123456789abcdef" for c in artifact_id)):
            raise EvidenceStoreError("invalid artifact_id: {!r}".format(artifact_id))
        path = self.store_dir / artifact_id
        if not path.is_file():
            raise EvidenceStoreError("snapshot not found: {}".format(artifact_id))
        return path.read_bytes()

    def append_origin(self, origin):
        """Append one origin observation. Append-only JSONL; duplicates are allowed.

        Origin hints (source_file/source_line/work/locator/...) are never part of
        artifact identity. Any future de-duplication is a *derived* index over this
        log, not a mutation of it.
        """
        line = json.dumps(origin, ensure_ascii=False, sort_keys=True) + "\n"
        with open(self._origins_path(), "a", encoding="utf-8") as handle:
            handle.write(line)
