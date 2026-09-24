"""Gate reuse using independently configured current facts and actual result bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from oncefold import (
    ActionIdentity,
    DecisionState,
    InMemoryReceiptStore,
    ReceiptTrustPolicy,
    ReceiptVerifier,
    ReuseReceipt,
    SideEffectClass,
)
from oncefold.wire import load_json_object

# Demo-only local trust configuration, never inferred from an incoming receipt.
TRUSTED_PRODUCER = "generic-cli-producer"
TRUSTED_CACHE_SCOPE = "private"
TRUSTED_PROVENANCE = {"example": "producer"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--input", default="example-cli-input", help="independently observed input")
    parser.add_argument("--result", type=Path, help="defaults to <receipt stem>.result.txt")
    parser.add_argument("--action-output", type=Path, help="export current facts for the core CLI")
    args = parser.parse_args()
    result_path = args.result or args.receipt.with_suffix(".result.txt")

    try:
        # Reconstruct current facts from this consumer's configuration and input.
        # Copying receipt.action here would hide changes in the current request.
        action = ActionIdentity(
            operation_identity="example.cli.lookup",
            operation_version="1",
            input_digest=hashlib.sha256(args.input.encode("utf-8")).hexdigest(),
            trust_scope="example:public",
            side_effect_class=SideEffectClass.READ_ONLY,
            dependency_completeness=True,
        )
        receipt = ReuseReceipt.from_dict(load_json_object(args.receipt))
        with result_path.open("rb") as result_file:
            result_digest = hashlib.file_digest(result_file, "sha256").hexdigest()
        if args.action_output:
            for evidence_path in (args.receipt, result_path):
                if args.action_output.resolve() == evidence_path.resolve() or (
                    args.action_output.exists() and args.action_output.samefile(evidence_path)
                ):
                    raise ValueError("action output must not overwrite the receipt or result")
            args.action_output.parent.mkdir(parents=True, exist_ok=True)
            args.action_output.write_text(
                json.dumps(action.as_dict(), sort_keys=True, indent=2) + "\n", encoding="utf-8"
            )
        store = InMemoryReceiptStore()
        store.put(receipt)
        policy = ReceiptTrustPolicy.for_producer(
            TRUSTED_PRODUCER,
            TRUSTED_CACHE_SCOPE,
            required_provenance=TRUSTED_PROVENANCE,
        )
        decision = ReceiptVerifier(store, policy).evaluate(
            action, receipt, available_result_digest=result_digest
        )
    except (OSError, TypeError, ValueError, KeyError) as exc:
        print(
            json.dumps({"state": DecisionState.UNKNOWN.value, "reason": str(exc)}, sort_keys=True)
        )
        return 2
    print(json.dumps({"state": decision.state.value, "reason": decision.reason}, sort_keys=True))
    return 0 if decision.state is DecisionState.REUSABLE_EXACT else 1


if __name__ == "__main__":
    raise SystemExit(main())
