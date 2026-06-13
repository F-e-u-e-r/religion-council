#!/usr/bin/env python3
import json
import sys
import threading
import time


write_lock = threading.Lock()
state_lock = threading.Lock()
thread_counter = 0
failed_once = set()


def send(message):
    with write_lock:
        sys.stdout.write(json.dumps(message, separators=(",", ":")) + "\n")
        sys.stdout.flush()


def tool_result(request_id, thread_id, content):
    send(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "structuredContent": {
                    "threadId": thread_id,
                    "content": content,
                },
                "content": [{"type": "text", "text": content}],
            },
        }
    )


def handle(message):
    global thread_counter
    method = message.get("method")
    request_id = message.get("id")
    if method == "initialize":
        send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "fake-codex", "version": "0.1"},
                },
            }
        )
    elif method == "tools/list":
        send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {"name": "codex", "inputSchema": {"type": "object"}},
                        {"name": "codex-reply", "inputSchema": {"type": "object"}},
                    ]
                },
            }
        )
    elif method == "tools/call":
        params = message["params"]
        name = params["name"]
        arguments = params["arguments"]
        time.sleep(0.005)
        if name == "codex":
            panelist_id = arguments["prompt"].split("Panelist ID: ", 1)[1].splitlines()[0]
            with state_lock:
                should_fail = (
                    "Force one failure" in arguments["prompt"]
                    and panelist_id == "panelist_30"
                    and panelist_id not in failed_once
                )
                if should_fail:
                    failed_once.add(panelist_id)
                else:
                    thread_counter += 1
                    thread_id = "thread-{:03d}".format(thread_counter)
            if should_fail:
                send(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "isError": True,
                            "content": [{"type": "text", "text": "forced failure"}],
                        },
                    }
                )
                return
            content = "opening:" + panelist_id
            tool_result(request_id, thread_id, content)
        elif name == "codex-reply":
            thread_id = arguments["threadId"]
            tool_result(request_id, thread_id, "followup:" + thread_id)
    elif request_id is not None:
        send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": "method not found"},
            }
        )


for raw_line in sys.stdin:
    raw_line = raw_line.strip()
    if not raw_line:
        continue
    incoming = json.loads(raw_line)
    if incoming.get("method") == "tools/call":
        threading.Thread(target=handle, args=(incoming,), daemon=True).start()
    else:
        handle(incoming)
