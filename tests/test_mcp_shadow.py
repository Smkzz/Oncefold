from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from oncefold.identity import SideEffectClass
from oncefold.mcp_shadow import SHADOW_METADATA_KEY, MCPShadowProxy
from oncefold.protocol import DecisionState, InMemoryReceiptStore, ReceiptTrustPolicy


def test_shadow_adapter_forwards_equivalent_calls_and_compares_results() -> None:
    store = InMemoryReceiptStore()
    proxy = MCPShadowProxy(store, ReceiptTrustPolicy.for_producer("mcp-server", "private"))
    request: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "lookup",
            "arguments": {"q": "oncefold"},
            "_meta": {"idempotencyKey": "retry-1", "attestation": "external-proposal-field"},
        },
    }
    calls = 0

    def fake_tool(_: Mapping[str, Any]) -> Mapping[str, Any]:
        nonlocal calls
        calls += 1
        return {"result": {"content": [{"type": "text", "text": "same"}]}}

    first = proxy.forward(
        request,
        fake_tool,
        operation_version="tool-v1",
        trust_scope="tenant:one",
        side_effect_class=SideEffectClass.READ_ONLY,
        dependency_completeness=True,
    )
    second = proxy.forward(
        request,
        fake_tool,
        operation_version="tool-v1",
        trust_scope="tenant:one",
        side_effect_class=SideEffectClass.READ_ONLY,
        dependency_completeness=True,
    )
    assert calls == 2
    assert first.decision.state is DecisionState.UNKNOWN
    assert second.decision.state is DecisionState.REUSABLE_EXACT
    assert second.actual_result_matches_prior is True
    assert second.shadow_metadata[SHADOW_METADATA_KEY]["would_reuse"] is True
    assert request["params"]["_meta"]["idempotencyKey"] == "retry-1"

    changed = {**request, "params": {**request["params"], "arguments": {"q": "different"}}}
    third = proxy.forward(
        changed,
        fake_tool,
        operation_version="tool-v1",
        trust_scope="tenant:one",
        side_effect_class=SideEffectClass.READ_ONLY,
        dependency_completeness=True,
    )
    assert calls == 3
    assert third.decision.state is DecisionState.UNKNOWN


def test_shadow_adapter_does_not_emit_receipts_for_external_mutation() -> None:
    store = InMemoryReceiptStore()
    proxy = MCPShadowProxy(store)
    request = {"method": "tools/call", "params": {"name": "write", "arguments": {"x": "1"}}}
    result = proxy.forward(
        request,
        lambda _: {"result": {"ok": True}},
        operation_version="tool-v1",
        trust_scope="tenant:one",
        side_effect_class=SideEffectClass.EXTERNAL_MUTATION,
    )
    assert result.calls_executed == 1
    assert result.receipt is None
    assert result.decision.state is DecisionState.UNKNOWN
    assert result.shadow_metadata[SHADOW_METADATA_KEY]["receipt_digest"] is None


@pytest.mark.parametrize(
    "response",
    [
        {"isError": True, "content": [{"type": "text", "text": "tool failed"}]},
        {"result": {"isError": True, "content": [{"type": "text", "text": "tool failed"}]}},
        {"jsonrpc": "2.0", "id": 1, "error": {"code": -32603, "message": "tool failed"}},
        {"result": {"isError": "true"}},
        {"result": None},
    ],
)
def test_shadow_errors_do_not_become_reuse_evidence(response: Mapping[str, Any]) -> None:
    store = InMemoryReceiptStore()
    proxy = MCPShadowProxy(store, ReceiptTrustPolicy.for_producer("mcp-server", "private"))
    request = {"method": "tools/call", "params": {"name": "lookup", "arguments": {}}}
    calls = 0

    def failed_tool(_: Mapping[str, Any]) -> Mapping[str, Any]:
        nonlocal calls
        calls += 1
        return response

    for _ in range(2):
        observation = proxy.forward(
            request,
            failed_tool,
            operation_version="1",
            trust_scope="local",
            side_effect_class=SideEffectClass.READ_ONLY,
            dependency_completeness=True,
        )
        assert observation.calls_executed == 1
        assert observation.receipt is None
        assert observation.actual_result_digest is None
        assert observation.shadow_metadata[SHADOW_METADATA_KEY]["would_reuse"] is False
    assert calls == 2
