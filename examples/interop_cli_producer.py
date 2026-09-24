"""Write a fixture tool result and a portable receipt for another process."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from oncefold import ActionIdentity, ReuseClass, ReuseReceipt, SideEffectClass


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="receipt JSON output path")
    parser.add_argument("--input", default="example-cli-input", help="observed lookup input")
    parser.add_argument("--value", default="cli-producer-result", help="fixture lookup result")
    parser.add_argument("--result-output", type=Path, help="defaults to <receipt stem>.result.txt")
    args = parser.parse_args()
    result_path = args.result_output or args.output.with_suffix(".result.txt")
    if args.output.resolve() == result_path.resolve() or (
        args.output.exists() and result_path.exists() and args.output.samefile(result_path)
    ):
        parser.error("receipt and result output paths must differ")

    action = ActionIdentity(
        operation_identity="example.cli.lookup",
        operation_version="1",
        input_digest=digest(args.input),
        trust_scope="example:public",
        side_effect_class=SideEffectClass.READ_ONLY,
        dependency_completeness=True,
    )
    receipt = ReuseReceipt(
        action=action,
        result_digest=digest(args.value),
        media_type="text/plain",
        producer_identity="generic-cli-producer",
        reuse_class=ReuseClass.EXACT,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        dependency_snapshot=(),
        provenance={"example": "producer"},
        trust_scope=action.trust_scope,
    )
    # Persist the exact UTF-8 bytes hashed above, without newline translation.
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_bytes(args.value.encode("utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt.as_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
