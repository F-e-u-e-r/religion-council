import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "orchestrator"))

import retrieval_evidence_adapter as adapter  # noqa: E402
from claim_protocol import SchemaRejection  # noqa: E402
from evidence_snapshot import EvidenceStore  # noqa: E402

NETWORK = "runtime-captured"


def envelope(records):
    return {"contract_version": "religion-council/retrieval/v1", "records": records}


def net_record(**overrides):
    """A network-backed record: NO source_file / source_line origin hints."""
    record = {
        "text": "克己復禮為仁",
        "tradition": "confucianism",
        "work": "論語",
        "locator": "顏淵",
        "evidence_type": "quotation",
        "verbatim": True,
        "topic": "仁與禮",
    }
    record.update(overrides)
    return record


class Fresh:
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.store = EvidenceStore(self.dir)
        return self

    def __exit__(self, *exc):
        self._tmp.cleanup()

    def snapshot_files(self):
        return [p for p in self.dir.iterdir() if len(p.name) == 64]


class SchemeSelectionTest(unittest.TestCase):
    def test_origin_hints_select_corpus_stable(self):
        record = net_record(source_file="/repo/x.md", source_line=10)
        self.assertEqual(
            adapter.occurrence_scheme(record, NETWORK), adapter.OCCURRENCE_SCHEME_CORPUS_STABLE
        )

    def test_network_origin_without_hints_selects_network_stable(self):
        self.assertEqual(
            adapter.occurrence_scheme(net_record(), NETWORK),
            adapter.OCCURRENCE_SCHEME_NETWORK_STABLE,
        )

    def test_non_network_without_hints_keeps_index_fallback(self):
        self.assertEqual(
            adapter.occurrence_scheme(net_record(), "bundled"),
            adapter.OCCURRENCE_SCHEME_INDEX_FALLBACK,
        )

    def test_stable_inputs_predicate(self):
        self.assertTrue(adapter.stable_occurrence_inputs_available(net_record()))  # work+locator
        self.assertTrue(
            adapter.stable_occurrence_inputs_available({"record_key": "k", "text": "x"})
        )
        self.assertTrue(
            adapter.stable_occurrence_inputs_available({"source_file": "f", "source_line": 1})
        )
        self.assertFalse(adapter.stable_occurrence_inputs_available({"text": "orphan"}))
        self.assertFalse(adapter.stable_occurrence_inputs_available({"work": "W", "text": "x"}))


class ReorderingInvarianceTest(unittest.TestCase):
    def test_network_id_is_independent_of_retrieval_order(self):
        a = net_record(text="alpha", work="W1", locator="L1")
        b = net_record(text="beta", work="W2", locator="L2")
        with Fresh() as f1, Fresh() as f2:
            order1 = adapter.adapt(envelope([a, b]), f1.store, acquisition_origin=NETWORK)
            order2 = adapter.adapt(envelope([b, a]), f2.store, acquisition_origin=NETWORK)
        occ_a_first = order1[0].occurrence_id  # 'a' at index 0
        occ_a_second = order2[1].occurrence_id  # 'a' at index 1
        self.assertEqual(occ_a_first, occ_a_second)  # same evidence -> same id across orderings
        self.assertEqual(order1[0].occurrence_id_scheme, adapter.OCCURRENCE_SCHEME_NETWORK_STABLE)

    def test_record_key_pins_identity_regardless_of_order(self):
        a = net_record(text="alpha", record_key="rk-A", work="W", locator="L")
        b = net_record(text="beta", record_key="rk-B", work="W", locator="L")
        with Fresh() as f1, Fresh() as f2:
            o1 = adapter.adapt(envelope([a, b]), f1.store, acquisition_origin=NETWORK)
            o2 = adapter.adapt(envelope([b, a]), f2.store, acquisition_origin=NETWORK)
        self.assertEqual(o1[0].occurrence_id, o2[1].occurrence_id)  # 'a' by its record_key
        self.assertNotEqual(o1[0].occurrence_id, o1[1].occurrence_id)  # distinct keys distinct ids

    def test_index_fallback_remains_order_scoped_for_non_network(self):
        # The legacy file-based stop-gap is preserved for NON-network acquisition.
        rec = net_record()
        with Fresh() as f:
            seeds = adapter.adapt(envelope([rec, dict(rec)]), f.store, acquisition_origin="bundled")
        self.assertEqual(seeds[0].occurrence_id_scheme, adapter.OCCURRENCE_SCHEME_INDEX_FALLBACK)
        self.assertNotEqual(seeds[0].occurrence_id, seeds[1].occurrence_id)  # index disambiguates


class FailClosedTest(unittest.TestCase):
    def test_network_record_without_stable_inputs_fails_closed(self):
        orphan = {"text": "orphan wording", "evidence_type": "quotation", "verbatim": True}
        with Fresh() as f:
            with self.assertRaises(adapter.StableIdentityError):
                adapter.adapt(envelope([orphan]), f.store, acquisition_origin=NETWORK)
            self.assertEqual(f.snapshot_files(), [])  # nothing persisted (preflight, before binding)
            self.assertFalse((f.dir / "origins.jsonl").exists())

    def test_one_orphan_aborts_whole_network_envelope(self):
        good = net_record()
        orphan = {"text": "orphan", "evidence_type": "quotation", "verbatim": True}
        with Fresh() as f:
            with self.assertRaises(adapter.StableIdentityError):
                adapter.adapt(envelope([good, orphan]), f.store, acquisition_origin=NETWORK)
            self.assertEqual(f.snapshot_files(), [])  # atomic: the good record is not persisted

    def test_stable_identity_error_is_a_schema_rejection(self):
        # So the controller's existing `except SchemaRejection` fails closed at start().
        self.assertTrue(issubclass(adapter.StableIdentityError, SchemaRejection))

    def test_network_record_with_origin_hints_is_allowed(self):
        # A network backend that DOES supply stable hints uses the corpus-stable scheme.
        rec = net_record(source_file="/snap/x", source_line=3)
        with Fresh() as f:
            seeds = adapter.adapt(envelope([rec]), f.store, acquisition_origin=NETWORK)
        self.assertEqual(seeds[0].occurrence_id_scheme, adapter.OCCURRENCE_SCHEME_CORPUS_STABLE)

    def test_degenerate_origin_hints_do_not_bypass_fail_closed(self):
        # Regression: empty source_file / zero source_line are NOT real origin hints, so a
        # network record carrying them (and no other stable input) must still fail closed and
        # persist nothing — it must not mint a corpus-stable id.
        for bad in (
            {"text": "orphan", "source_file": "", "source_line": 0},
            {"text": "orphan", "source_file": "   ", "source_line": 5},
            {"text": "orphan", "source_file": "/x", "source_line": 0},
            {"text": "orphan", "source_file": "/x", "source_line": True},
        ):
            with self.subTest(bad=bad), Fresh() as f:
                with self.assertRaises(adapter.StableIdentityError):
                    adapter.adapt(envelope([bad]), f.store, acquisition_origin=NETWORK)
                self.assertEqual(f.snapshot_files(), [])
                self.assertFalse((f.dir / "origins.jsonl").exists())

    def test_degenerate_hints_with_work_locator_use_network_stable(self):
        # Degenerate hints + a real (work, locator) is still stable, but via the network scheme,
        # never corpus-stable (which would otherwise be order-dependent on bogus line numbers).
        rec = net_record(source_file="", source_line=0)  # work/locator come from net_record
        self.assertEqual(
            adapter.occurrence_scheme(rec, NETWORK), adapter.OCCURRENCE_SCHEME_NETWORK_STABLE
        )
        with Fresh() as f:
            seeds = adapter.adapt(envelope([rec]), f.store, acquisition_origin=NETWORK)
        self.assertEqual(seeds[0].occurrence_id_scheme, adapter.OCCURRENCE_SCHEME_NETWORK_STABLE)


class CollisionResistanceTest(unittest.TestCase):
    def test_same_bytes_different_locator_do_not_collide(self):
        with Fresh() as f:
            seeds = adapter.adapt(
                envelope([net_record(locator="顏淵"), net_record(locator="里仁")]),
                f.store,
                acquisition_origin=NETWORK,
            )
        self.assertEqual(len({s.artifact_id for s in seeds}), 1)  # one artifact (same bytes)
        self.assertEqual(len({s.occurrence_id for s in seeds}), 2)  # two occurrences

    def test_same_bytes_same_locator_collapse_to_one_identity(self):
        # Identical bytes at the identical (work, locator) ARE the same occurrence — collapsing
        # them is correct, not a collision bug.
        with Fresh() as f:
            seeds = adapter.adapt(
                envelope([net_record(), net_record()]), f.store, acquisition_origin=NETWORK
            )
        self.assertEqual(seeds[0].occurrence_id, seeds[1].occurrence_id)

    def test_different_bytes_same_locator_do_not_collide(self):
        with Fresh() as f:
            seeds = adapter.adapt(
                envelope([net_record(text="one"), net_record(text="two")]),
                f.store,
                acquisition_origin=NETWORK,
            )
        self.assertNotEqual(seeds[0].occurrence_id, seeds[1].occurrence_id)


class ReproducibilityTest(unittest.TestCase):
    def test_network_ids_are_reproducible_across_runs(self):
        rec = net_record(work="W", locator="L")
        with Fresh() as f1, Fresh() as f2:
            one = adapter.adapt(envelope([rec]), f1.store, acquisition_origin=NETWORK)[0]
            two = adapter.adapt(envelope([rec]), f2.store, acquisition_origin=NETWORK)[0]
        self.assertEqual(one.occurrence_id, two.occurrence_id)  # persisted audit reproducible

    def test_scheme_is_recorded_in_origins_log(self):
        with Fresh() as f:
            adapter.adapt(envelope([net_record()]), f.store, acquisition_origin=NETWORK)
            origins = (f.dir / "origins.jsonl").read_text(encoding="utf-8")
        self.assertIn(adapter.OCCURRENCE_SCHEME_NETWORK_STABLE, origins)


if __name__ == "__main__":
    unittest.main()
