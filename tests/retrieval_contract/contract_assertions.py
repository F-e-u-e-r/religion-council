"""Shared retrieval-contract conformance battery (ADR 0006 §5).

`test_contract_portable.py` and `test_contract_project.py` each subclass
:class:`RetrievalContractMixin` together with ``unittest.TestCase``, so the *identical*
battery runs against both retrievers. The battery has two halves matching ADR 0006 §2:

* **retriever-level** — assertions over each retriever's *live* envelope (the real curated
  corpus): envelope shape + version, required record fields, NFC/LF-canonical text, capability
  metadata, determinism, provenance/rights preservation, and (portable only) stdlib-only imports;
* **identity-level** — assertions over the shared fixtures fed through the real B1 adapter +
  ``EvidenceStore`` (the downstream both retrievers share): deterministic ids, duplicate-text
  distinctness vs. correct collapse, NFC/LF identity stability, fail-closed on underspecified
  dynamic acquisition, and the empty-envelope / malformed-record contracts.

Identity is minted by the *adapter*, never by a retriever (ADR 0006 §2), so the identity-level
checks belong to the contract floor every conforming envelope relies on; running them under each
retriever's test module makes each module a self-contained conformance report.
"""
import ast
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "orchestrator"))

import retrieval_evidence_adapter as adapter  # noqa: E402
from claim_protocol import SchemaRejection  # noqa: E402
from evidence_snapshot import EvidenceStore, canonical_bytes  # noqa: E402

CONTRACT_VERSION = "religion-council/retrieval/v1"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
PORTABLE_RETRIEVER = ROOT / "skills" / "religion-council" / "scripts" / "retrieve.py"


def load_module_from_path(name, path):
    """Import a Python module by file path (used to load retrievers that are not installed)."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# Required record fields a conforming envelope must carry (ADR 0006 §2 / docs/CORPUS.md).
REQUIRED_RECORD_FIELDS = (
    "text",
    "tradition",
    "school",
    "work",
    "locator",
    "language",
    "version",
    "category",
    "label",
)
KNOWN_RETRIEVER_KINDS = frozenset(
    {"portable-file", "project-file", "project-index", "project-service"}
)
# Queries chosen to exercise several traditions deterministically.
SAMPLE_QUERIES = ("人生意義", "仁", "空")

STDLIB_DIR = os.path.realpath(os.path.dirname(os.__file__))


def load_fixture(name):
    with (FIXTURES / name / "envelope.json").open(encoding="utf-8") as handle:
        return json.load(handle)


class FreshStore:
    """A throwaway content-addressed store (mirrors tests/test_stable_occurrence_identity.Fresh)."""

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.store = EvidenceStore(self.dir)
        return self

    def __exit__(self, *exc):
        self._tmp.cleanup()

    def snapshot_files(self):
        return [p for p in self.dir.iterdir() if len(p.name) == 64]


def imported_top_level_modules(path):
    """Top-level module names imported by the Python source at ``path`` (a relative import
    is reported as a dotted sentinel so the stdlib check rejects it)."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                names.add("." * node.level)  # relative import -> never stdlib
            elif node.module:
                names.add(node.module.split(".")[0])
    return names


def is_stdlib_module(name):
    """True iff ``name`` resolves to a standard-library (or built-in) module.

    Version-portable (no ``sys.stdlib_module_names``, which is 3.10+): a module is stdlib if it is
    built-in/frozen, or its origin file lives under the stdlib directory and not under
    ``site-packages``. Project modules (under the repo) and third-party packages are rejected.
    """
    if name.startswith("."):
        return False
    if name in sys.builtin_module_names:
        return True
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, ValueError):
        return False
    if spec is None or spec.origin is None:
        return False
    if spec.origin in ("built-in", "frozen"):
        return True
    origin = os.path.realpath(spec.origin)
    if os.sep + "site-packages" + os.sep in origin:
        return False
    return origin.startswith(STDLIB_DIR + os.sep)


class RetrievalContractMixin:
    """The shared battery. Concrete subclasses (with ``unittest.TestCase``) provide the retriever."""

    # Subclasses override:
    STDLIB_ONLY = False
    EXPECTED_RETRIEVER_KIND = None

    def load_retriever(self):
        raise NotImplementedError

    def retriever_source_path(self):
        """Path to the retriever's source file (for the stdlib-only import check)."""
        return None

    def setUp(self):
        super().setUp()
        self.retriever = self.load_retriever()

    # ----- helpers -----

    def _live_envelopes(self):
        envelopes = []
        for tradition in sorted(self.retriever.TRADITIONS):
            for query in SAMPLE_QUERIES:
                envelopes.append(self.retriever.retrieve_envelope(tradition, query, 3))
        return envelopes

    def _assert_text_canonical(self, text):
        # canonical_bytes = UTF-8(NFC(LF(text))); already-canonical text round-trips unchanged.
        self.assertEqual(
            canonical_bytes(text).decode("utf-8"),
            text,
            "retriever emitted non-canonical (NFC/LF) text: {!r}".format(text),
        )

    def _assert_envelope_conforms(self, envelope):
        self.assertIsInstance(envelope, dict)
        self.assertEqual(envelope.get("contract_version"), CONTRACT_VERSION)
        self.assertIsInstance(envelope.get("records"), list)
        for record in envelope["records"]:
            self.assertIsInstance(record, dict)
            for field in REQUIRED_RECORD_FIELDS:
                self.assertIn(field, record, "missing required field {!r}".format(field))
                self.assertIsInstance(record[field], str)
                self.assertTrue(record[field].strip(), "empty required field {!r}".format(field))
            self._assert_text_canonical(record["text"])

    # ----- retriever-level -----

    def test_envelope_shape_and_version(self):
        for envelope in self._live_envelopes():
            self.assertIsInstance(envelope, dict)
            self.assertEqual(envelope.get("contract_version"), CONTRACT_VERSION)
            self.assertIsInstance(envelope.get("records"), list)
            # Valid, ensure_ascii=False-serializable JSON that round-trips.
            self.assertEqual(json.loads(json.dumps(envelope, ensure_ascii=False)), envelope)

    def test_required_record_fields_present_and_typed(self):
        for envelope in self._live_envelopes():
            for record in envelope["records"]:
                self.assertIsInstance(record, dict)
                for field in REQUIRED_RECORD_FIELDS:
                    self.assertIn(field, record, "missing required field {!r}".format(field))
                    self.assertIsInstance(record[field], str)
                    self.assertTrue(record[field].strip(), "empty {!r}".format(field))

    def test_text_is_canonical_nfc_lf(self):
        for envelope in self._live_envelopes():
            for record in envelope["records"]:
                self._assert_text_canonical(record["text"])

    def test_optional_fields_well_typed_when_present(self):
        for envelope in self._live_envelopes():
            for record in envelope["records"]:
                if "evidence_type" in record:
                    self.assertIn(record["evidence_type"], ("quotation", "source-bound-summary"))
                if "verbatim" in record:
                    self.assertIsInstance(record["verbatim"], bool)
                if "provenance" in record:
                    self.assertIsInstance(record["provenance"], dict)
                    self.assertTrue(record["provenance"])
                for field in ("representation_kind", "rendering_mode", "rights", "topic"):
                    if field in record:
                        self.assertIsInstance(record[field], str)

    def test_capabilities_block(self):
        caps = self.retriever.capabilities()
        self.assertIsInstance(caps, dict)
        self.assertEqual(caps["contract_version"], CONTRACT_VERSION)
        self.assertIn(caps["retriever_kind"], KNOWN_RETRIEVER_KINDS)
        if self.EXPECTED_RETRIEVER_KIND is not None:
            self.assertEqual(caps["retriever_kind"], self.EXPECTED_RETRIEVER_KIND)
        self.assertIsInstance(caps["supports_stable_occurrence_identity"], bool)
        self.assertIsInstance(caps["supports_network_acquisition"], bool)
        # ADR 0006 §3: network acquisition implies stable occurrence identity.
        if caps["supports_network_acquisition"]:
            self.assertTrue(caps["supports_stable_occurrence_identity"])

    def test_capabilities_contract_version_matches_envelope(self):
        caps = self.retriever.capabilities()
        envelope = self.retriever.retrieve_envelope("buddhism", "空", 1)
        self.assertEqual(caps["contract_version"], envelope["contract_version"])

    def test_output_is_deterministic(self):
        for tradition in sorted(self.retriever.TRADITIONS):
            first = self.retriever.retrieve_envelope(tradition, "人生意義", 3)
            second = self.retriever.retrieve_envelope(tradition, "人生意義", 3)
            self.assertEqual(first, second)

    def test_live_envelope_mints_stable_corpus_identity(self):
        # The file-based retriever supplies source_file + source_line, so the adapter mints
        # order-independent occ/v1-corpus-stable ids: identical across two fresh stores.
        for tradition in sorted(self.retriever.TRADITIONS):
            envelope = self.retriever.retrieve_envelope(tradition, "人生意義", 3)
            with FreshStore() as one, FreshStore() as two:
                seeds_one = adapter.adapt(envelope, one.store)
                seeds_two = adapter.adapt(envelope, two.store)
            self.assertEqual(
                [s.occurrence_id for s in seeds_one],
                [s.occurrence_id for s in seeds_two],
            )
            for seed in seeds_one:
                self.assertEqual(
                    seed.occurrence_id_scheme, adapter.OCCURRENCE_SCHEME_CORPUS_STABLE
                )

    def test_curated_provenance_and_rights_survive_into_seed(self):
        curated = None
        for tradition in sorted(self.retriever.TRADITIONS):
            for record in self.retriever.parse_reference(tradition):
                if record.get("provenance") and record.get("rights"):
                    curated = record
                    break
            if curated is not None:
                break
        self.assertIsNotNone(curated, "expected at least one curated record in the corpus")
        envelope = {"contract_version": CONTRACT_VERSION, "records": [curated]}
        with FreshStore() as fresh:
            seeds = adapter.adapt(envelope, fresh.store)
        self.assertEqual(seeds[0].provenance, curated["provenance"])
        self.assertEqual(seeds[0].rights, curated["rights"])

    def test_imports_are_stdlib_only(self):
        if not self.STDLIB_ONLY:
            self.skipTest("stdlib-only invariant applies to the portable retriever (ADR 0006 §4.4)")
        path = self.retriever_source_path()
        self.assertIsNotNone(path, "portable retriever must expose its source path")
        offenders = sorted(
            name for name in imported_top_level_modules(path) if not is_stdlib_module(name)
        )
        self.assertEqual(
            offenders, [], "portable retriever imports non-stdlib modules: {}".format(offenders)
        )

    # ----- identity-level (shared fixtures through the real adapter) -----

    def test_fixture_basic_corpus_conforms_and_is_deterministic(self):
        envelope = load_fixture("basic_corpus")
        self._assert_envelope_conforms(envelope)
        with FreshStore() as one, FreshStore() as two:
            seeds_one = adapter.adapt(envelope, one.store)
            seeds_two = adapter.adapt(envelope, two.store)
        self.assertEqual(
            [s.occurrence_id for s in seeds_one], [s.occurrence_id for s in seeds_two]
        )
        # Two distinct file-based occurrences (distinct locators/lines) stay distinct.
        self.assertEqual(len({s.occurrence_id for s in seeds_one}), len(seeds_one))

    def test_fixture_duplicate_text_distinct_but_same_locator_collapses(self):
        envelope = load_fixture("duplicate_text")
        self._assert_envelope_conforms(envelope)
        with FreshStore() as fresh:
            seeds = adapter.adapt(envelope, fresh.store)
        # All three records are the same bytes -> exactly one artifact.
        self.assertEqual(len({s.artifact_id for s in seeds}), 1)
        # Records 0 and 2 share every stable input -> one occurrence (correct collapse, ADR 0005 §5);
        # record 1 at a different locator stays distinct.
        self.assertEqual(seeds[0].occurrence_id, seeds[2].occurrence_id)
        self.assertNotEqual(seeds[0].occurrence_id, seeds[1].occurrence_id)
        self.assertEqual(len({s.occurrence_id for s in seeds}), 2)

    def test_fixture_unicode_normalization_is_identity_stable(self):
        envelope = load_fixture("unicode_normalization")
        with FreshStore() as fresh:
            seeds = adapter.adapt(envelope, fresh.store)
            # Records differ only by NFC/NFD and CRLF/LF -> one canonical snapshot on disk.
            self.assertEqual(len(fresh.snapshot_files()), 1)
        self.assertEqual(len({s.artifact_id for s in seeds}), 1)
        self.assertEqual(len({s.occurrence_id for s in seeds}), 1)

    def test_fixture_missing_metadata_still_binds_without_provenance(self):
        envelope = load_fixture("missing_metadata")
        self._assert_envelope_conforms(envelope)
        with FreshStore() as fresh:
            seeds = adapter.adapt(envelope, fresh.store)
        self.assertTrue(seeds)
        for seed in seeds:
            self.assertIsNone(seed.provenance)
            self.assertIsNone(seed.rights)
            self.assertIsNone(seed.declared_representation_kind)

    def test_fixture_dynamic_identity_required_fails_closed(self):
        envelope = load_fixture("dynamic_identity_required")
        with FreshStore() as fresh:
            with self.assertRaises(adapter.StableIdentityError):
                adapter.adapt(envelope, fresh.store, acquisition_origin="runtime-captured")
            # Preflight rejection: nothing persisted, before any claim binding.
            self.assertEqual(fresh.snapshot_files(), [])
            self.assertFalse((fresh.dir / "origins.jsonl").exists())

    def test_dynamic_with_record_key_binds_network_stable_and_reorder_invariant(self):
        # The escape hatch: the same underspecified dynamic records become bindable the moment a
        # stable record_key is supplied — order-independently (ADR 0005 §1 network-stable).
        records = load_fixture("dynamic_identity_required")["records"]
        keyed = [dict(record, record_key="rk-{}".format(i)) for i, record in enumerate(records)]
        forward = {"contract_version": CONTRACT_VERSION, "records": keyed}
        reverse = {"contract_version": CONTRACT_VERSION, "records": list(reversed(keyed))}
        with FreshStore() as one, FreshStore() as two:
            seeds_forward = adapter.adapt(forward, one.store, acquisition_origin="runtime-captured")
            seeds_reverse = adapter.adapt(reverse, two.store, acquisition_origin="runtime-captured")
        self.assertEqual(seeds_forward[0].occurrence_id, seeds_reverse[-1].occurrence_id)
        for seed in seeds_forward:
            self.assertEqual(
                seed.occurrence_id_scheme, adapter.OCCURRENCE_SCHEME_NETWORK_STABLE
            )

    def test_fixture_no_result_is_valid_empty_envelope(self):
        envelope = load_fixture("no_result")
        self.assertEqual(envelope["contract_version"], CONTRACT_VERSION)
        self.assertEqual(envelope["records"], [])
        with FreshStore() as fresh:
            seeds = adapter.adapt(envelope, fresh.store)
        self.assertEqual(seeds, [])

    def test_malformed_record_fails_predictably(self):
        # Malformed corpus data fails as a schema rejection, never a silent drop (ADR 0006 §5).
        envelope = {
            "contract_version": CONTRACT_VERSION,
            "records": [{"work": "W", "locator": "L"}],  # no text
        }
        with FreshStore() as fresh:
            with self.assertRaises(SchemaRejection):
                adapter.adapt(envelope, fresh.store)
