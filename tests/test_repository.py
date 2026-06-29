import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


class RepositoryValidationTest(unittest.TestCase):
    def test_release_version_is_v0130(self):
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), "v0.13.0")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("version-v0.13.0", readme)
        controller = (ROOT / "orchestrator" / "debate_controller.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('CONTROLLER_VERSION = "0.13.0"', controller)

    def test_markdown_relative_links_exist(self):
        missing = []
        for path in ROOT.rglob("*.md"):
            if ".git" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            for target in MARKDOWN_LINK_RE.findall(text):
                target = target.strip("<>")
                if (
                    not target
                    or target.startswith("#")
                    or "://" in target
                    or target.startswith("mailto:")
                ):
                    continue
                relative = target.split("#", 1)[0]
                if relative and not (path.parent / relative).exists():
                    missing.append("{} -> {}".format(path.relative_to(ROOT), target))
        self.assertEqual(missing, [])

    def test_no_unresolved_public_placeholders(self):
        forbidden = ("<your-fork-url>", "TODO:", "FIXME:")
        failures = []
        for name in ("README.md", "INSTALL.md", "docs/ORCHESTRATION.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            for value in forbidden:
                if value in text:
                    failures.append("{} contains {}".format(name, value))
        self.assertEqual(failures, [])

    def test_roster_counts_and_unique_ids(self):
        expectations = {
            "orchestrator/panelists/religion-8.json": 8,
            "orchestrator/panelists/thirty-member-example.json": 30,
        }
        for relative, expected in expectations.items():
            data = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            panelists = data["panelists"]
            ids = [item["id"] for item in panelists]
            self.assertEqual(len(panelists), expected, relative)
            self.assertEqual(len(ids), len(set(ids)), relative)

    def test_claude_agent_roster_is_one_moderator_plus_36_voices(self):
        paths = sorted((ROOT / ".claude" / "agents").glob("council-*.md"))
        self.assertEqual(len(paths), 37)
        self.assertEqual(sum(path.name == "council-moderator.md" for path in paths), 1)
        names = []
        for path in paths:
            match = FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
            self.assertIsNotNone(match, path)
            name_line = next(
                line for line in match.group(1).splitlines() if line.startswith("name:")
            )
            name = name_line.split(":", 1)[1].strip()
            self.assertEqual(path.stem, name)
            names.append(name)
        self.assertEqual(len(names), len(set(names)))

    def test_moderator_can_complete_the_strict_finalization_workflow(self):
        moderator = ROOT / ".claude" / "agents" / "council-moderator.md"
        text = moderator.read_text(encoding="utf-8")
        match = FRONTMATTER_RE.match(text)
        self.assertIsNotNone(match)
        self.assertIn(
            "mcp__religion-council-controller__debate_finalize", match.group(1)
        )
        self.assertIn("`assurance_footer`", text)

    def test_portable_skill_frontmatter_and_references(self):
        skill = ROOT / "skills" / "religion-council" / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        match = FRONTMATTER_RE.match(text)
        self.assertIsNotNone(match)
        keys = {
            line.split(":", 1)[0].strip()
            for line in match.group(1).splitlines()
            if ":" in line
        }
        self.assertEqual(keys, {"name", "description"})
        self.assertIn("name: religion-council", match.group(1))
        references = set(re.findall(r"`(references/[^`]+\.md)`", text))
        self.assertEqual(len(references), 16)
        for relative in references:
            self.assertTrue((skill.parent / relative).is_file(), relative)

    def test_reference_bodies_match_between_distributions(self):
        portable = ROOT / "skills" / "religion-council" / "references"
        claude = ROOT / ".claude" / "skills" / "religion-council" / "references"
        portable_names = sorted(path.name for path in portable.glob("*.md"))
        claude_names = sorted(path.name for path in claude.glob("*.md"))
        self.assertEqual(portable_names, claude_names)
        for name in portable_names:
            portable_body = (portable / name).read_text(encoding="utf-8").split(
                "## 引用紀律", 1
            )[0]
            claude_body = (claude / name).read_text(encoding="utf-8").split(
                "## 引用紀律", 1
            )[0]
            self.assertEqual(portable_body, claude_body, name)

    def test_project_mcp_registration(self):
        config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
        server = config["mcpServers"]["religion-council-controller"]
        self.assertEqual(server["type"], "stdio")
        self.assertIn("debate_controller.py", " ".join(server["args"]))


if __name__ == "__main__":
    unittest.main()
