import importlib.util
import json
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "orchestrator"))

import corpus_metadata_enums  # noqa: E402
import policy_enums  # noqa: E402
import retrieval_evidence_adapter as adapter  # noqa: E402
from evidence_snapshot import EvidenceStore, canonical_bytes  # noqa: E402

PORTABLE_DIR = ROOT / "skills" / "religion-council"
CLAUDE_DIR = ROOT / ".claude" / "skills" / "religion-council"
BASELINE_PER_TRADITION = 7  # the S3 consistent baseline (also the post-enrichment median)

# The exact records S3 added, by (work, locator). Every one must carry a per-snippet
# provenance + rights-basis note (finding-3 fix). 13 public-domain-basis excerpts + 2 in-copyright
# Qur'an excerpts (馬堅) + 3 generated Sanskrit renderings = 18.
NEW_RECORDS = {
    "christianity": [("約翰福音", "1:1"), ("希伯來書", "11:1")],
    "islam": [("古蘭經", "1:1(開端章)"), ("古蘭經", "2:256")],
    "hinduism": [("廣林奧義書", "1.4.10"), ("薄伽梵歌", "2:48"), ("薄伽梵歌", "4:7")],
    "buddhism": [("雜阿含經", "(緣起法)"), ("法句經", "183")],
    "taoism": [("道德經", "48"), ("道德經", "58")],
    "confucianism": [("論語", "為政"), ("論語", "里仁")],
    "legalism": [("韓非子", "有度"), ("韓非子", "五蠹"), ("韓非子", "難三")],
    "mohism": [("墨子", "尚賢上"), ("墨子", "非樂上")],
}


def load_retriever(name, scripts_dir):
    path = scripts_dir / "scripts" / "retrieve.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def envelope(records):
    return {"contract_version": "religion-council/retrieval/v1", "records": records}


class CorpusCurationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retriever = load_retriever("retr_portable", PORTABLE_DIR)
        cls.by_tradition = {
            tradition: cls.retriever.parse_reference(tradition)
            for tradition in cls.retriever.TRADITIONS
        }
        cls.all_records = [r for records in cls.by_tradition.values() for r in records]

    # ---- balance / baseline (S3 exit criterion) -------------------------------------------
    def test_every_tradition_meets_the_baseline(self):
        for tradition, records in self.by_tradition.items():
            self.assertGreaterEqual(len(records), BASELINE_PER_TRADITION, tradition)

    def test_no_tradition_is_below_the_project_median(self):
        totals = sorted(len(r) for r in self.by_tradition.values())
        median = totals[len(totals) // 2]
        for tradition, records in self.by_tradition.items():
            self.assertGreaterEqual(len(records), median, tradition)

    # ---- record integrity -----------------------------------------------------------------
    def test_no_duplicate_records(self):
        seen = set()
        for r in self.all_records:
            key = (r["tradition"], r["work"], r["locator"], r["text"])
            self.assertNotIn(key, seen, key)
            seen.add(key)

    def test_text_is_nfc_and_lf_normalized(self):
        for r in self.all_records:
            text = r["text"]
            self.assertEqual(text, unicodedata.normalize("NFC", text), r["work"])
            self.assertNotIn("\r", text)
            self.assertTrue(text.strip(), r["work"])  # no empty/whitespace-only wording

    # ---- curated metadata (plan: enum + rights validation) --------------------------------
    def test_curated_records_pass_enum_and_rights_validation(self):
        curated = [
            r for r in self.all_records
            if any(r.get(f) is not None for f in ("representation_kind", "rendering_mode", "provenance", "rights"))
        ]
        self.assertTrue(curated)
        for r in curated:
            # representation_kind / rendering_mode are present only on renderings; check when present.
            if "representation_kind" in r:
                self.assertIn(r["representation_kind"], policy_enums.REPRESENTATION_KINDS, r["work"])
            if "rendering_mode" in r:
                self.assertIn(r["rendering_mode"], policy_enums.RENDERING_MODES, r["work"])
            # ADR 0008 witness/canon fields: enum-checked HERE (the portable retriever only
            # type-checks them, carried-not-trusted). `version` is a free-form source-edition string.
            for field, allowed in corpus_metadata_enums.SIDECAR_ENUM_FIELDS.items():
                if field in r:
                    self.assertIn(r[field], allowed, (r["work"], field))
            if "version" in r:
                self.assertTrue(isinstance(r["version"], str) and r["version"].strip(), r["work"])
            # Every curated record carries per-snippet provenance + a non-empty rights note.
            self.assertIsInstance(r.get("provenance"), dict, r["work"])
            self.assertTrue(isinstance(r.get("rights"), str) and r["rights"].strip(), r["work"])

    def test_every_new_record_carries_a_per_snippet_rights_basis(self):
        # Finding-3 fix: each S3 addition has per-record provenance + a rights note. This validates
        # that a rights BASIS is recorded and honestly scoped per snippet — NOT that legal clearance
        # is established (a test cannot do that): every note tells the reader to confirm before
        # redistribution, and every public-domain-basis note discloses it was not independently audited.
        seen = 0
        for tradition, keys in NEW_RECORDS.items():
            index = {(r["work"], r["locator"]): r for r in self.by_tradition[tradition]}
            for key in keys:
                seen += 1
                self.assertIn(key, index, (tradition, key))
                record = index[key]
                self.assertIsInstance(record.get("provenance"), dict, (tradition, key))
                self.assertTrue(record["provenance"], (tradition, key))
                rights = record.get("rights")
                self.assertTrue(isinstance(rights, str) and rights.strip(), (tradition, key))
                # Honest scoping: never claim cleared rights; always defer to redistribution review.
                self.assertIn("redistribution", rights.lower(), (tradition, key))
                # A public-domain-basis claim must disclose it was not independently audited.
                if "public domain" in rights.lower():
                    self.assertEqual(
                        record["provenance"].get("review"), "not-independently-audited", (tradition, key)
                    )
        self.assertEqual(seen, 18)

    def test_no_curated_record_is_labeled_edition_backed(self):
        # Curation principle: do NOT label snapshot/curated material as edition-backed.
        for r in self.all_records:
            self.assertNotEqual(r.get("representation_kind"), "edition-backed")
            self.assertNotIn("span_assurance_tier", r)  # the corpus never asserts a verified tier at rest

    def test_adr0008_witness_metadata_and_version_override(self):
        # Phase 1: the 道德經 (通行本 / 王弼) records carry disclosed textual-witness metadata, and the
        # sidecar `version` overrides the hardcoded placeholder with the source edition — resolving the
        # ADR 0006 drift honestly, without minting edition-backed assurance.
        daodejing = [r for r in self.all_records if r["work"] == "道德經"]
        self.assertTrue(daodejing)
        for r in daodejing:
            self.assertEqual(r["version"], "通行本")
            self.assertEqual(r["witness_kind"], "received")
            self.assertEqual(r["textual_witness"], "wang_bi")
            self.assertEqual(r["commentarial_lineage"], "wang_bi")
            self.assertEqual(r["corpus_family"], "daodejing")
            self.assertEqual(r["representation_kind"], "original-text")
        # Un-curated records keep the honest snapshot-label default — never a fabricated edition tag.
        self.assertTrue(any(r["version"] == "curated-reference-v0.1" for r in self.all_records))
        # The witness/canon enums live in the corpus-metadata policy, separate from admissibility, and
        # never admit an assurance value.
        self.assertIn("wang_bi", corpus_metadata_enums.TEXTUAL_WITNESSES)
        self.assertNotIn("edition-backed", corpus_metadata_enums.WITNESS_KINDS)

    # ---- span integrity + snapshot reproducibility ----------------------------------------
    def test_snapshot_roundtrip_and_full_span_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EvidenceStore(tmp)
            for r in self.all_records:
                aid, length = store.put_snapshot(r["text"])
                aid2, length2 = store.put_snapshot(r["text"])  # idempotent by content
                self.assertEqual((aid, length), (aid2, length2))
                blob = store.read_snapshot(aid)
                self.assertEqual(blob, canonical_bytes(r["text"]))
                self.assertEqual(blob[0:length].decode("utf-8"), unicodedata.normalize("NFC", r["text"]))

    def test_occurrence_ids_are_reproducible_across_runs(self):
        # File-based records carry origin hints -> corpus-stable scheme (ADR 0005), so two
        # adapt() runs over the same envelope mint identical occurrence ids (audit reproducible).
        # SCOPE: corpus-stable ids embed the absolute source_file path, so this reproducibility is
        # within the SAME checkout/path, not portable across relocated clones (ADR 0005 "Known
        # limitations"). The network-stable scheme has no such path dependency.
        for tradition in ("islam", "hinduism", "confucianism"):
            records = self.by_tradition[tradition]
            with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
                a = adapter.adapt(envelope(records), EvidenceStore(t1))
                b = adapter.adapt(envelope(records), EvidenceStore(t2))
            self.assertEqual([s.occurrence_id for s in a], [s.occurrence_id for s in b], tradition)
            self.assertTrue(all(s.occurrence_id_scheme == "occ/v1-corpus-stable" for s in a))

    def test_curated_presentation_is_carried_to_the_seed(self):
        # The B2/P1 value the enrichment serves: rights + representation reach the evidence seed.
        records = self.by_tradition["hinduism"]
        with tempfile.TemporaryDirectory() as tmp:
            seeds = adapter.adapt(envelope(records), EvidenceStore(tmp))
        idx = next(
            i for i, r in enumerate(records)
            if r["work"] == "廣林奧義書" and r["locator"] == "1.4.10"
        )
        seed = seeds[idx]
        self.assertEqual(seed.declared_representation_kind, "generated-rendering")
        self.assertEqual(seed.declared_rendering_mode, "meaning-rendering")
        self.assertTrue(seed.rights and seed.rights.strip())

    # ---- presentation sidecar parity (generator/retriever) --------------------------------
    def test_every_presentation_entry_resolves_to_a_record(self):
        # No orphan curation: each sidecar key must match an actually-parsed record.
        with (PORTABLE_DIR / "references" / "presentation.json").open(encoding="utf-8") as handle:
            data = json.load(handle)
        record_keys = {
            (t, r["work"], r["locator"]) for t, records in self.by_tradition.items() for r in records
        }
        for tradition, entries in data.items():
            if not isinstance(entries, list):
                continue  # the "_note" string
            for entry in entries:
                key = (tradition, entry["work"], entry["locator"])
                self.assertIn(key, record_keys, key)

    def test_both_reference_copies_parse_to_identical_records(self):
        # The dual-copy corpus must stay in sync (the enrichment touched both).
        claude = load_retriever("retr_claude", CLAUDE_DIR)
        for tradition in self.retriever.TRADITIONS:
            portable_rows = [
                (r["work"], r["locator"], r["text"]) for r in self.by_tradition[tradition]
            ]
            claude_rows = [
                (r["work"], r["locator"], r["text"]) for r in claude.parse_reference(tradition)
            ]
            self.assertEqual(portable_rows, claude_rows, tradition)

    def test_both_presentation_copies_are_byte_identical(self):
        portable = (PORTABLE_DIR / "references" / "presentation.json").read_bytes()
        claude = (CLAUDE_DIR / "references" / "presentation.json").read_bytes()
        self.assertEqual(portable, claude)


if __name__ == "__main__":
    unittest.main()
