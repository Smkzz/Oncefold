from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
from dataclasses import replace
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

from oncefold import ActionIdentity, DecisionState, ReuseClass, ReuseReceipt
from oncefold.wire import load_json_object

ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONUTF8": "1"}


def run_python(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=cwd,
        env=ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=30,
    )


def producer(receipt: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return run_python(
        str(ROOT / "examples/interop_cli_producer.py"), str(receipt), *args, cwd=receipt.parent
    )


def consumer(receipt: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return run_python(
        str(ROOT / "examples/interop_consumer.py"), str(receipt), *args, cwd=receipt.parent
    )


@pytest.fixture
def receipt_path(tmp_path: Path) -> Path:
    receipt = tmp_path / "receipt.json"
    result = producer(receipt)
    assert result.returncode == 0, result.stderr
    return receipt


def test_readme_quickstart_output_and_artifacts(receipt_path: Path) -> None:
    action_path = receipt_path.parent / "current-action.json"
    result = consumer(receipt_path, "--action-output", str(action_path))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    expected = re.search(r"<!-- quickstart-output -->\s*```json\n(.*?)\n```", readme, re.S)
    assert expected is not None
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected.group(1)
    receipt = ReuseReceipt.from_dict(load_json_object(receipt_path))
    action = ActionIdentity.from_dict(load_json_object(action_path))
    assert action.digest == receipt.action.digest
    result_bytes = receipt_path.with_suffix(".result.txt").read_bytes()
    assert result_bytes == b"cli-producer-result"
    assert hashlib.sha256(result_bytes).hexdigest() == receipt.result_digest


def test_consumer_does_not_trust_embedded_action(receipt_path: Path) -> None:
    receipt = ReuseReceipt.from_dict(load_json_object(receipt_path))
    changed_action = replace(receipt.action, operation_version="changed")
    # Valid, self-consistent evidence for a different action must still be stale.
    changed_receipt = replace(receipt, action=changed_action)
    receipt_path.write_text(json.dumps(changed_receipt.as_dict()), encoding="utf-8")
    action_path = receipt_path.parent / "independent-action.json"
    result = consumer(receipt_path, "--action-output", str(action_path))
    assert result.returncode == 1
    assert json.loads(result.stdout)["state"] == "STALE"
    current = ActionIdentity.from_dict(load_json_object(action_path))
    assert current.operation_version == "1"
    assert current.digest != changed_action.digest


def test_changed_input_is_stale(receipt_path: Path) -> None:
    result = consumer(receipt_path, "--input", "changed-input")
    assert result.returncode == 1
    assert json.loads(result.stdout) == {
        "reason": "action identity mismatch",
        "state": "STALE",
    }


def test_changed_result_fails_closed(receipt_path: Path) -> None:
    receipt_path.with_suffix(".result.txt").write_bytes(b"different result")
    result = consumer(receipt_path)
    assert result.returncode == 1
    assert json.loads(result.stdout) == {"reason": "result digest mismatch", "state": "UNKNOWN"}


@pytest.mark.parametrize("failure", ["producer", "cache_scope", "provenance"])
def test_receipt_cannot_supply_its_own_trust_policy(receipt_path: Path, failure: str) -> None:
    receipt = ReuseReceipt.from_dict(load_json_object(receipt_path))
    if failure == "producer":
        receipt = replace(receipt, producer_identity="untrusted-producer")
    elif failure == "cache_scope":
        receipt = replace(receipt, cache_scope="untrusted-scope")
    else:
        receipt = replace(receipt, provenance={})
    receipt_path.write_text(json.dumps(receipt.as_dict()), encoding="utf-8")
    result = consumer(receipt_path)
    assert result.returncode == 1
    assert json.loads(result.stdout)["state"] == "UNKNOWN"


@pytest.mark.parametrize("failure", ["missing_receipt", "missing_result", "malformed_receipt"])
def test_consumer_input_errors_exit_two(receipt_path: Path, failure: str) -> None:
    if failure == "missing_receipt":
        receipt_path.unlink()
    elif failure == "missing_result":
        receipt_path.with_suffix(".result.txt").unlink()
    else:
        receipt_path.write_text('{"broken":', encoding="utf-8")
    result = consumer(receipt_path)
    assert result.returncode == 2
    assert json.loads(result.stdout)["state"] == "UNKNOWN"
    assert "Traceback" not in result.stderr


def test_custom_paths_and_utf8_result(tmp_path: Path) -> None:
    receipt = tmp_path / "custom receipt.json"
    result_path = tmp_path / "separate result.txt"
    value = "caf\u00e9\nsecond line"
    produced = producer(
        receipt, "--input", "request-A", "--value", value, "--result-output", str(result_path)
    )
    assert produced.returncode == 0, produced.stderr
    assert result_path.read_bytes() == value.encode("utf-8")
    result = consumer(receipt, "--input", "request-A", "--result", str(result_path))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["state"] == "REUSABLE_EXACT"


def test_producer_rejects_colliding_outputs(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.json"
    result = producer(receipt, "--result-output", str(receipt))
    assert result.returncode == 2
    assert not receipt.exists()


@pytest.mark.parametrize("target", ["receipt", "result"])
def test_action_export_cannot_overwrite_evidence(receipt_path: Path, target: str) -> None:
    output = receipt_path if target == "receipt" else receipt_path.with_suffix(".result.txt")
    original = output.read_bytes()
    result = consumer(receipt_path, "--action-output", str(output))
    assert result.returncode == 2
    assert output.read_bytes() == original
    assert json.loads(result.stdout)["state"] == "UNKNOWN"


@pytest.mark.parametrize("command", ["check", "verify", "inspect"])
@pytest.mark.parametrize("state", list(DecisionState))
def test_documented_cli_state_exit_matrix(
    receipt_path: Path, command: str, state: DecisionState
) -> None:
    action_path = receipt_path.parent / "current-action.json"
    assert consumer(receipt_path, "--action-output", str(action_path)).returncode == 0
    action = ActionIdentity.from_dict(load_json_object(action_path))
    receipt = ReuseReceipt.from_dict(load_json_object(receipt_path))
    if state is DecisionState.REQUIRES_VALIDATION:
        receipt = replace(receipt, reuse_class=ReuseClass.VERIFIED)
    elif state is DecisionState.ADVISORY_ONLY:
        receipt = replace(receipt, reuse_class=ReuseClass.ADVISORY)
    elif state is DecisionState.REVOKED:
        receipt = replace(receipt, revocation_ref="example:revoked")
    elif state is DecisionState.STALE:
        action = replace(action, operation_version="changed")
    elif state is DecisionState.SCOPE_MISMATCH:
        action = replace(action, trust_scope="different-scope")
    elif state is DecisionState.UNSAFE:
        receipt = replace(receipt, reuse_class=ReuseClass.UNSAFE)
    elif state is DecisionState.UNKNOWN:
        receipt = replace(receipt, producer_identity="untrusted-producer")
    receipt_path.write_text(json.dumps(receipt.as_dict()), encoding="utf-8")
    action_path.write_text(json.dumps(action.as_dict()), encoding="utf-8")
    result = run_python(
        "-m",
        "oncefold",
        command,
        str(receipt_path),
        "--action",
        str(action_path),
        "--result-digest",
        hashlib.sha256(receipt_path.with_suffix(".result.txt").read_bytes()).hexdigest(),
        "--trusted-producer",
        "generic-cli-producer",
        "--trusted-cache-scope",
        "private",
        "--require-provenance",
        "example=producer",
        cwd=receipt_path.parent,
    )
    expected_code = 0 if command == "inspect" or state is DecisionState.REUSABLE_EXACT else 1
    assert result.returncode == expected_code, result.stderr or result.stdout
    assert json.loads(result.stdout)["state"] == state.value
    row = next(
        line
        for line in (ROOT / "README.md").read_text(encoding="utf-8").splitlines()
        if line.startswith(f"| `{state.value}` |")
    )
    gate_code, inspect_code = [int(value.strip()) for value in row.split("|")[-3:-1]]
    assert (gate_code, inspect_code) == (0 if state is DecisionState.REUSABLE_EXACT else 1, 0)


@pytest.mark.parametrize("command", ["check", "verify", "inspect"])
def test_cli_parse_failure_overrides_state_table(receipt_path: Path, command: str) -> None:
    action_path = receipt_path.parent / "current-action.json"
    assert consumer(receipt_path, "--action-output", str(action_path)).returncode == 0
    receipt_path.write_text("not JSON", encoding="utf-8")
    result = run_python(
        "-m",
        "oncefold",
        command,
        str(receipt_path),
        "--action",
        str(action_path),
        cwd=receipt_path.parent,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["state"] == "UNKNOWN"


@pytest.mark.parametrize("command", ["check", "verify"])
def test_cli_requires_independent_action(receipt_path: Path, command: str) -> None:
    result = run_python("-m", "oncefold", command, str(receipt_path), cwd=receipt_path.parent)
    assert result.returncode == 2
    assert "--action" in result.stderr


def test_readme_badges_match_package_metadata() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"version-{project['version']}-" in readme
    assert project["requires-python"] == ">=3.11"
    assert "python-3.11%2B-" in readme
    assert project["license"] == "Apache-2.0"
    assert "license-Apache--2.0-" in readme
    assert project["dependencies"] == []
    assert project["urls"]["Repository"] == "https://github.com/Smkzz/Oncefold"


@pytest.mark.parametrize("document", ["README.md", "examples/README.md"])
def test_documentation_relative_links_exist(document: str) -> None:
    source = ROOT / document
    for target in re.findall(r"\]\(([^)]+)\)", source.read_text(encoding="utf-8")):
        url = urlsplit(target)
        if url.scheme or not url.path:
            continue
        destination = source.parent / unquote(url.path)
        assert destination.exists(), f"{document}: {target}"


def test_producer_rejects_hardlinked_outputs(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_bytes(b"existing evidence")
    alias = tmp_path / "result.txt"
    try:
        os.link(receipt, alias)
    except OSError as exc:
        pytest.skip(f"filesystem does not support hard links: {exc}")
    result = producer(receipt, "--result-output", str(alias))
    assert result.returncode == 2
    assert receipt.read_bytes() == b"existing evidence"


@pytest.mark.parametrize("target", ["receipt", "result"])
def test_action_export_cannot_overwrite_hardlinked_evidence(
    receipt_path: Path, target: str
) -> None:
    evidence = receipt_path if target == "receipt" else receipt_path.with_suffix(".result.txt")
    original = evidence.read_bytes()
    alias = receipt_path.parent / "action-alias.json"
    try:
        os.link(evidence, alias)
    except OSError as exc:
        pytest.skip(f"filesystem does not support hard links: {exc}")
    result = consumer(receipt_path, "--action-output", str(alias))
    assert result.returncode == 2
    assert evidence.read_bytes() == original
    assert json.loads(result.stdout)["state"] == "UNKNOWN"
