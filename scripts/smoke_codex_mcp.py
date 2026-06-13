#!/usr/bin/env python3
"""Run an opt-in live create/reply smoke test against codex mcp-server."""

import argparse
import json
import os
from pathlib import Path
import shlex
import sys


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "orchestrator"))

from debate_controller import CodexMcpClient, ControllerError  # noqa: E402


OPENING_MARKER = "LIVE_CODEX_MCP_OK"
REPLY_MARKER = "LIVE_CODEX_REPLY_OK"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--codex-command",
        default=os.environ.get("CODEX_COMMAND", "codex mcp-server"),
        help="Command used to start the Codex MCP server.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args()

    client = CodexMcpClient(shlex.split(args.codex_command), ROOT)
    try:
        opening = client.call_tool(
            "codex",
            {
                "prompt": (
                    "This is a read-only connectivity smoke test. "
                    "Return exactly {} and no other text. Do not use tools."
                ).format(OPENING_MARKER),
                "cwd": str(ROOT),
                "sandbox": "read-only",
                "approval-policy": "never",
            },
            timeout=args.timeout_seconds,
        )
        if OPENING_MARKER not in opening["content"]:
            raise ControllerError("Opening response did not contain the expected marker.")

        reply = client.call_tool(
            "codex-reply",
            {
                "threadId": opening["thread_id"],
                "prompt": "Return exactly {} and no other text.".format(REPLY_MARKER),
            },
            timeout=args.timeout_seconds,
        )
        if reply["thread_id"] != opening["thread_id"]:
            raise ControllerError("codex-reply returned a different thread ID.")
        if REPLY_MARKER not in reply["content"]:
            raise ControllerError("Reply response did not contain the expected marker.")

        json.dump(
            {
                "status": "ok",
                "thread_id": opening["thread_id"],
                "opening_marker": True,
                "reply_marker": True,
                "thread_reused": True,
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
    finally:
        client.close()


if __name__ == "__main__":
    main()
