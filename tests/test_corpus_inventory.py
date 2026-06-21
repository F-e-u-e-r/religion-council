import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CorpusInventoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inv = load_script(
            "corpus_inventory_under_test", ROOT / "scripts" / "corpus_inventory.py"
        )
        cls.inventory = cls.inv.build_inventory()

    def test_inventory_is_deterministic(self):
        self.assertEqual(self.inv.build_inventory(), self.inv.build_inventory())

    def test_all_traditions_reported_separately(self):
        retriever = self.inv.load_retriever()
        self.assertEqual(
            set(self.inventory["traditions"]), set(retriever.TRADITIONS)
        )
        self.assertEqual(len(self.inventory["traditions"]), 8)

    def test_overall_is_the_sum_of_traditions(self):
        traditions = self.inventory["traditions"].values()
        for field in ("total", "quotation", "source_bound_summary", "with_provenance", "invalid"):
            self.assertEqual(
                self.inventory["overall"][field],
                sum(stats[field] for stats in traditions),
                field,
            )

    def test_quotation_plus_summary_never_exceeds_total(self):
        for tradition, stats in self.inventory["traditions"].items():
            self.assertLessEqual(
                stats["quotation"] + stats["source_bound_summary"], stats["total"], tradition
            )

    def test_distribution_buckets_sum_to_total(self):
        for tradition, stats in self.inventory["traditions"].items():
            self.assertEqual(sum(stats["by_representation_kind"].values()), stats["total"], tradition)
            self.assertEqual(sum(stats["by_curation_tier"].values()), stats["total"], tradition)

    def test_inventory_uses_the_portable_retriever_records(self):
        # Parity by construction: the inventory's per-tradition total equals the retriever's
        # parse_reference record count, so the inventory cannot drift from what retrieval sees.
        retriever = self.inv.load_retriever()
        for tradition in retriever.TRADITIONS:
            self.assertEqual(
                self.inventory["traditions"][tradition]["total"],
                len(retriever.parse_reference(tradition)),
                tradition,
            )

    def test_enum_sets_match_policy_enums(self):
        # The inventory reads enum ids straight from the manifest; assert they equal the
        # orchestrator's derived frozensets so validation can never silently diverge.
        sys.path.insert(0, str(ROOT / "orchestrator"))
        try:
            import policy_enums  # noqa: PLC0415
        finally:
            sys.path.pop(0)
        enums = self.inv.load_policy_enums()
        self.assertEqual(enums["representation_kinds"], policy_enums.REPRESENTATION_KINDS)
        self.assertEqual(enums["rendering_modes"], policy_enums.RENDERING_MODES)

    def test_current_corpus_has_no_invalid_records(self):
        self.assertEqual(self.inventory["invalid_records"], [])
        self.assertEqual(self.inventory["overall"]["invalid"], 0)

    def test_check_mode_passes_on_clean_corpus(self):
        self.assertEqual(self.inv.main(["--check"]), 0)

    def test_validator_flags_enum_violation(self):
        enums = self.inv.load_policy_enums()
        bad = {
            "text": "x", "tradition": "islam", "work": "W", "locator": "1:1",
            "representation_kind": "bogus-kind", "rights": "ok",
        }
        self.assertIn("representation-kind-not-in-enum", self.inv._validate(bad, enums))

    def test_validator_flags_curated_presentation_without_rights(self):
        # Mirrors the renderer rights gate: presentation metadata requires a rights note.
        enums = self.inv.load_policy_enums()
        bad = {
            "text": "x", "tradition": "islam", "work": "W", "locator": "1:1",
            "representation_kind": "published-translation", "rendering_mode": "meaning-rendering",
        }
        reasons = self.inv._validate(bad, enums)
        self.assertIn("curated-presentation-without-rights", reasons)

    def test_validator_passes_a_well_formed_enriched_record(self):
        enums = self.inv.load_policy_enums()
        good = {
            "text": "x", "tradition": "islam", "work": "古蘭經", "locator": "51:56",
            "representation_kind": "published-translation", "rendering_mode": "meaning-rendering",
            "provenance": {"translator": "馬堅"}, "rights": "short excerpt; confirm licensing",
        }
        self.assertEqual(self.inv._validate(good, enums), [])

    def test_check_mode_fails_when_a_record_is_invalid(self):
        # Inject a malformed presentation entry via the sidecar and confirm --check reports it.
        retriever = self.inv.load_retriever()
        sample = retriever.parse_reference("confucianism")[0]
        key = ("confucianism", sample["work"], sample["locator"])
        original = dict(retriever.PRESENTATION)
        retriever.PRESENTATION[key] = {
            "work": sample["work"],
            "locator": sample["locator"],
            "representation_kind": "published-translation",  # curated presentation...
            # ...but no rights -> renderer rights gate violation -> invalid.
        }
        try:
            enums = self.inv.load_policy_enums()
            inventory = self.inv.build_inventory(retriever=retriever, enums=enums)
        finally:
            retriever.PRESENTATION.clear()
            retriever.PRESENTATION.update(original)
        self.assertTrue(inventory["invalid_records"])
        self.assertTrue(
            any("curated-presentation-without-rights" in e["reasons"] for e in inventory["invalid_records"])
        )

    def test_json_and_text_formats_render(self):
        import io
        from contextlib import redirect_stdout

        for fmt in ("text", "json"):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                self.assertEqual(self.inv.main(["--format", fmt]), 0)
            self.assertTrue(buffer.getvalue().strip())
        # JSON form must be machine-parseable and round-trip the overall total.
        import json

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.inv.main(["--format", "json"])
        parsed = json.loads(buffer.getvalue())
        self.assertEqual(parsed["overall"]["total"], self.inventory["overall"]["total"])


if __name__ == "__main__":
    unittest.main()
