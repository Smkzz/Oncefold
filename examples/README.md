# Examples

Start with the [complete quickstart](../README.md#quickstart-producer--receipt-file--consumer)
for clone, installation, expected output, and a negative control.
These examples need an installed Oncefold package but no agent SDK, API key,
network service, cache, or execution authority.

## In-memory Python API

```sh
python examples/basic.py
```

This constructs and evaluates a fixture in memory. It is an API illustration,
not verification of an independently observed live tool call.

## Separate producer and consumer processes

```sh
python examples/interop_cli_producer.py .tmp/quickstart/receipt.json
python examples/interop_consumer.py .tmp/quickstart/receipt.json --action-output .tmp/quickstart/current-action.json
```

The producer writes a portable receipt and `receipt.result.txt` beside it. The
consumer hashes the actual result bytes, constructs its current action from its
own configuration and `--input`, and evaluates the receipt under its fixed local
trust policy. `--action-output` optionally exports those current facts for the
core CLI. It never copies the receipt's action or trust configuration.

Expected output and exit code 0:

```json
{"reason": "identity and dependencies match", "state": "REUSABLE_EXACT"}
```

### Custom fixture inputs and paths

```sh
python examples/interop_cli_producer.py .tmp/custom/receipt.json --input request-A --value result-A --result-output .tmp/custom/result.txt
python examples/interop_consumer.py .tmp/custom/receipt.json --input request-A --result .tmp/custom/result.txt
python examples/interop_consumer.py .tmp/custom/receipt.json --input request-B --result .tmp/custom/result.txt
```

The matching consumer exits 0 with `REUSABLE_EXACT`. The last command exits 1
with `STALE` and reason `action identity mismatch`. Changing result bytes yields
`UNKNOWN` and exit 1. Missing files or malformed receipts yield `UNKNOWN` and
exit 2. Use `--help` on either script for the argument reference.

The producer's `--value` is a **supplied fixture lookup result**, not a result
computed or authenticated by Oncefold. Its fixed timestamp makes the artifact
reproducible; no external dependency discovery or wall-clock freshness check is
performed. The `READ_ONLY` class describes the represented lookup, not the local
file writes used to transport the example artifacts.

The local consumer admits only `generic-cli-producer`, cache scope `private`,
and provenance `example=producer`. These labels are not cryptographic proof of
origin. Configure real producer admission, authenticated transport, observed
dependencies, scope, freshness, and revocation state outside an incoming receipt
before considering a real integration. This example uses a fresh in-memory
store, not an external revocation source or a shared cache.

The scripts overwrite their selected output artifacts. Use a dedicated output
directory; generated `.tmp/` files are ignored by Git. The consumer refuses to
export its current action over the receipt or result, and the producer refuses
to use the same path for receipt and result outputs.

The optional MCP shadow adapter is documented in
[MCP interoperability](../docs/MCP_INTEROP.md).
