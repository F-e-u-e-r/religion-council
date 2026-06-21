#!/usr/bin/env python3
import json
import sys
import threading
import time

write_lock = threading.Lock()
state_lock = threading.Lock()
thread_counter = 0
failed_once = set()
# Per-thread B1b structured scenario, so the repair turn (a codex-reply) knows whether
# this thread should succeed on repair or stay malformed and be dropped.
thread_scenario = {}


# B1b structured claim blocks (only emitted when the prompt carries the claim/v1 contract).
VALID_BLOCK = (
    "\n<<<CLAIM_PROTOCOL_V1>>>\n"
    '{"protocol_version":"religion-council/claim/v1",'
    '"claims":[{"claim_id":"c1","claim_type":"text","text":"克己復禮為仁"}],'
    '"edges":[{"claim_id":"c1","evidence_seed_id":"S1",'
    '"evidentiary_role":"primary-source","evidence_type":"quotation"}]}\n'
    "<<<END_CLAIM_PROTOCOL_V1>>>\n"
)
# Invalid claim_type "opinion" -> validate_claim_payload raises SchemaRejection.
MALFORMED_BLOCK = (
    "\n<<<CLAIM_PROTOCOL_V1>>>\n"
    '{"protocol_version":"religion-council/claim/v1",'
    '"claims":[{"claim_id":"c1","claim_type":"opinion","text":"x"}],"edges":[]}\n'
    "<<<END_CLAIM_PROTOCOL_V1>>>\n"
)


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
        prompt = arguments.get("prompt", "")
        structured = "religion-council/claim/v1" in prompt
        time.sleep(0.005)
        if name == "codex":
            panelist_id = prompt.split("Panelist ID: ", 1)[1].splitlines()[0]
            scenario = "ok"
            with state_lock:
                should_fail = (
                    "Force one failure" in prompt
                    and panelist_id == "panelist_30"
                    and panelist_id not in failed_once
                )
                if should_fail:
                    failed_once.add(panelist_id)
                else:
                    thread_counter += 1
                    thread_id = "thread-{:03d}".format(thread_counter)
                    if structured and panelist_id == "panelist_30":
                        if "STRUCTURED_DROP" in prompt:
                            scenario = "drop"
                        elif "STRUCTURED_REPAIR" in prompt:
                            scenario = "repair"
                    thread_scenario[thread_id] = scenario
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
            if structured:
                content += MALFORMED_BLOCK if scenario in ("drop", "repair") else VALID_BLOCK
            tool_result(request_id, thread_id, content)
        elif name == "codex-reply":
            thread_id = arguments["threadId"]
            is_repair = "rejected at the schema level" in prompt
            if is_repair:
                with state_lock:
                    scenario = thread_scenario.get(thread_id, "ok")
                if scenario == "drop":
                    # Still malformed on repair -> controller drops the payload, keeps prose.
                    tool_result(request_id, thread_id, "repair-attempt:" + thread_id + MALFORMED_BLOCK)
                else:
                    tool_result(request_id, thread_id, "repaired:" + thread_id + VALID_BLOCK)
            else:
                content = "followup:" + thread_id
                if structured:
                    content += VALID_BLOCK
                tool_result(request_id, thread_id, content)
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
