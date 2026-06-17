import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "orchestrator"))

import claim_binding as cb  # noqa: E402
import policy_enums  # noqa: E402
import retrieval_evidence_adapter as adapter  # noqa: E402
from evidence_snapshot import EvidenceStore  # noqa: E402


def load_retriever():
    path = ROOT / "skills" / "religion-council" / "scripts" / "retrieve.py"
    spec = importlib.util.spec_from_file_location("religion_retrieve_a1", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RETRIEVE = load_retriever()


def islam_envelope():
    records = RETRIEVE.parse_reference("islam")
    return {"contract_version": "religion-council/retrieval/v1", "records": records}, records


class SidecarEnumValidityTest(unittest.TestCase):
    def test_curated_presentation_values_are_valid_policy_enums(self):
        # Curation typo guard: every sidecar representation_kind / rendering_mode must be a real
        # policy enum member (retrieve.py carries the strings; the policy is the source of truth).
        with RETRIEVE.PRESENTATION_FILE.open(encoding="utf-8") as handle:
            sidecar = json.load(handle)
        seen = 0
        for tradition, entries in sidecar.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if "representation_kind" in entry:
                    self.assertIn(entry["representation_kind"], policy_enums.REPRESENTATION_KINDS)
                    seen += 1
                if "rendering_mode" in entry:
                    self.assertIn(entry["rendering_mode"], policy_enums.RENDERING_MODES)
        self.assertGreater(seen, 0)  # the sidecar actually curates something


class PipelineCarryThroughTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = EvidenceStore(self.tmp.name)

    def test_adapter_carries_curated_presentation_onto_seed(self):
        envelope, _ = islam_envelope()
        seeds = adapter.adapt(envelope, self.store)
        rendering = next(s for s in seeds if s.work == "古蘭經" and s.locator == "51:56")
        self.assertEqual(rendering.declared_representation_kind, "published-translation")
        self.assertEqual(rendering.declared_rendering_mode, "meaning-rendering")
        self.assertEqual(rendering.provenance["translator"], "馬堅")
        self.assertIn("copyright", rendering.rights)
        # an uncurated occurrence carries none
        summary = next(s for s in seeds if s.declared_evidence_type == "source-bound-summary")
        self.assertIsNone(summary.declared_representation_kind)
        self.assertIsNone(summary.declared_rendering_mode)

    def test_catalog_carries_presentation_and_marks_rendering(self):
        envelope, records = islam_envelope()
        seeds = adapter.adapt(envelope, self.store)
        catalog = cb.EvidenceCatalog.from_seeds_and_records(seeds, records)
        rendering = next(s for s in catalog.seeds if s.locator == "51:56")
        self.assertEqual(rendering.representation_kind, "published-translation")
        self.assertEqual(rendering.rendering_mode, "meaning-rendering")
        self.assertEqual(rendering.provenance["translator"], "馬堅")
        # the prompt listing flags the rendering so a panelist won't treat it as the original
        line = next(
            l for l in catalog.render_for_prompt().splitlines() if "51:56" in l
        )
        self.assertIn("meaning-rendering", line)
        self.assertIn("published-translation", line)

    def test_catalog_state_round_trip_preserves_presentation(self):
        envelope, records = islam_envelope()
        seeds = adapter.adapt(envelope, self.store)
        catalog = cb.EvidenceCatalog.from_seeds_and_records(seeds, records)
        rebuilt = cb.EvidenceCatalog.from_state(json.loads(json.dumps(catalog.to_state())))
        rendering = next(s for s in rebuilt.seeds if s.locator == "51:56")
        self.assertEqual(rendering.rendering_mode, "meaning-rendering")
        self.assertEqual(rendering.representation_kind, "published-translation")

    def test_uncurated_tradition_has_no_marker(self):
        records = RETRIEVE.parse_reference("confucianism")
        envelope = {"contract_version": "religion-council/retrieval/v1", "records": records}
        seeds = adapter.adapt(envelope, self.store)
        catalog = cb.EvidenceCatalog.from_seeds_and_records(seeds, records)
        self.assertTrue(all(s.rendering_mode is None for s in catalog.seeds))
        rendered = catalog.render_for_prompt()
        self.assertNotIn("meaning-rendering", rendered)


if __name__ == "__main__":
    unittest.main()
