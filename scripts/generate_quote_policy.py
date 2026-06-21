#!/usr/bin/env python3
"""Generate the quote-admissibility policy text for every council surface.

One canonical manifest (``policies/quote-admissibility.v2.json``) is the single
source of truth. This generator renders that manifest into the four surfaces that
must state the policy:

1. the portable skill (``skills/religion-council/SKILL.md``, English);
2. the Claude skill (``.claude/skills/religion-council/SKILL.md``, Traditional Chinese);
3. & 4. the controller opening and follow-up prompts, via the generated Python module
   ``orchestrator/generated_quote_policy.py`` whose English constant is inserted into
   both prompts.

Usage::

    python scripts/generate_quote_policy.py            # write surfaces
    python scripts/generate_quote_policy.py --check     # fail if any surface is stale

The generator is deterministic and idempotent: output depends only on the manifest,
and Markdown is replaced between fixed BEGIN/END markers.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "policies" / "quote-admissibility.v2.json"

PORTABLE_SKILL = ROOT / "skills" / "religion-council" / "SKILL.md"
CLAUDE_SKILL = ROOT / ".claude" / "skills" / "religion-council" / "SKILL.md"
GENERATED_MODULE = ROOT / "orchestrator" / "generated_quote_policy.py"

GENERATED_BY = (
    "policies/quote-admissibility.v2.json by scripts/generate_quote_policy.py"
)


def load_manifest():
    with MANIFEST_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _marker(manifest):
    return manifest["generated_marker"]


def _begin(manifest):
    return "<!-- BEGIN GENERATED: {} -->".format(_marker(manifest))


def _end(manifest):
    return "<!-- END GENERATED: {} -->".format(_marker(manifest))


def _claim_marker_line(manifest, locale):
    parts = []
    for claim in manifest["claim_types"]:
        parts.append(
            "{} — {}".format(
                claim["aliases"][locale], claim["description"][locale]
            )
        )
    label = "Claim markers" if locale == "en" else "主張標記"
    return "{}: {}".format(label, "; ".join(parts))


def render_markdown_block(manifest, locale):
    """Render the generated Markdown block (without the surrounding markers)."""
    lines = []
    lines.append(
        "<!-- Generated from {}. Do not edit by hand. -->".format(GENERATED_BY)
    )
    lines.append("")
    if locale == "en":
        lines.append(
            "**Quote-admissibility policy (`{}`, instruction-enforced; "
            "not runtime-validated)**".format(_marker(manifest))
        )
    else:
        lines.append(
            "**引用可採性政策(`{}`,以指示約束,尚未在執行期驗證)**".format(
                _marker(manifest)
            )
        )
    lines.append("")
    lines.append(_claim_marker_line(manifest, locale))
    lines.append("")
    for index, rule in enumerate(manifest["rules"], start=1):
        lines.append("{}. {}".format(index, rule["text"][locale]))
    return "\n".join(lines)


def render_markdown_surface(manifest, locale):
    """Render the full marker-wrapped block for splicing into a Markdown file."""
    return "\n".join(
        [
            _begin(manifest),
            render_markdown_block(manifest, locale),
            _end(manifest),
        ]
    )


def render_english_policy_text(manifest):
    """Plain-text English policy block embedded into both controller prompts."""
    lines = []
    lines.append(
        "Quote-admissibility policy {} (instruction-enforced; not "
        "runtime-validated).".format(_marker(manifest))
    )
    lines.append(_claim_marker_line(manifest, "en"))
    lines.append("")
    for index, rule in enumerate(manifest["rules"], start=1):
        lines.append("{}. {}".format(index, rule["text"]["en"]))
    return "\n".join(lines)


def render_python_module(manifest):
    policy_text = render_english_policy_text(manifest)
    body = []
    body.append('"""Generated quote-admissibility policy. Do not edit by hand.')
    body.append("")
    body.append("Generated from {}.".format(GENERATED_BY))
    body.append('"""')
    body.append("")
    body.append("POLICY_ID = {!r}".format(manifest["policy_id"]))
    body.append("POLICY_VERSION = {!r}".format(manifest["policy_version"]))
    body.append("GENERATED_MARKER = {!r}".format(manifest["generated_marker"]))
    body.append("")
    body.append("QUOTE_ADMISSIBILITY_POLICY_EN = (")
    text_lines = policy_text.split("\n")
    for position, line in enumerate(text_lines):
        suffix = "\n" if position < len(text_lines) - 1 else ""
        body.append("    {!r}".format(line + suffix))
    body.append(")")
    return "\n".join(body) + "\n"


def splice_markdown(text, manifest, locale):
    begin = _begin(manifest)
    end = _end(manifest)
    if begin not in text or end not in text:
        raise SystemExit(
            "Markers {!r} / {!r} not found in the target file; add them once where "
            "the generated policy belongs.".format(begin, end)
        )
    head, _, rest = text.partition(begin)
    _, _, tail = rest.partition(end)
    return head + render_markdown_surface(manifest, locale) + tail


def planned_outputs(manifest):
    """Return a list of (path, desired_content) for every generated surface."""
    outputs = []
    outputs.append(
        (
            PORTABLE_SKILL,
            splice_markdown(
                PORTABLE_SKILL.read_text(encoding="utf-8"), manifest, "en"
            ),
        )
    )
    outputs.append(
        (
            CLAUDE_SKILL,
            splice_markdown(
                CLAUDE_SKILL.read_text(encoding="utf-8"), manifest, "zh-Hant"
            ),
        )
    )
    outputs.append((GENERATED_MODULE, render_python_module(manifest)))
    return outputs


def run(check):
    manifest = load_manifest()
    stale = []
    for path, desired in planned_outputs(manifest):
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == desired:
            continue
        stale.append(path)
        if not check:
            path.write_text(desired, encoding="utf-8")
    if check and stale:
        names = ", ".join(str(path.relative_to(ROOT)) for path in stale)
        sys.stderr.write(
            "Stale generated surfaces: {}\nRun: python scripts/generate_quote_policy.py\n".format(
                names
            )
        )
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if any generated surface is out of date.",
    )
    args = parser.parse_args()
    raise SystemExit(run(check=args.check))


if __name__ == "__main__":
    main()
