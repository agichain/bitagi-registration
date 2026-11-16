#!/usr/bin/env python3
"""Shared standard-library utilities for BITAGI bootstrap verification."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PINS_PATH = ROOT / "canonical" / "D3_5_SOURCE_PINS.json"

EXIT_SUCCESS = 0
EXIT_VALIDATION = 2
EXIT_UNAVAILABLE = 3
EXIT_INTERNAL = 4
EXIT_SECURITY = 5
EXIT_RELEASE_REFUSAL = 6


def require_debug_mode() -> None:
    if not __debug__:
        print("ERROR: optimized Python execution is prohibited for release verification", file=sys.stderr)
        raise SystemExit(EXIT_RELEASE_REFUSAL)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text("utf-8"))


class SourceIdentityError(ValueError):
    """Bounded public failure identity; never includes input/exception text."""

    def __init__(self, code: str, path: str, *, exit_code: int = EXIT_VALIDATION,
                 observed: bytes | None = None) -> None:
        super().__init__(code)
        self.code, self.path, self.exit_code = code, path, exit_code
        self.observed_bytes = len(observed) if observed is not None else None
        self.observed_sha256 = sha256_bytes(observed) if observed is not None else None


def bounded_regular_bytes(path: Path, *, root: Path, limit: int) -> bytes:
    """Read one regular local object once, excluding links and reparse points."""
    rel = path.relative_to(root)
    for part in (root, *(root.joinpath(*rel.parts[:i]) for i in range(1, len(rel.parts) + 1))):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise OSError("nonregular input")
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
        raise OSError("nonregular or oversized input")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns):
            raise OSError("input changed")
        data = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    if len(data) > limit or len(data) != before.st_size or (
            opened.st_size, opened.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise OSError("input changed")
    return data


def sealed_root_payloads(root: Path, paths: Any,
                         overrides: dict[str, bytes | None] | None = None) -> dict[str, bytes | None]:
    payloads: dict[str, bytes | None] = {}
    for rel in paths:
        if overrides is not None and rel in overrides:
            payloads[rel] = overrides[rel]
            continue
        try:
            payloads[rel] = bounded_regular_bytes(root / rel, root=root, limit=1024 * 1024)
        except (OSError, ValueError):
            payloads[rel] = None
    return payloads


def load_pins() -> dict[str, Any]:
    # One owner for the already reviewed constants; no full verifier recursion.
    from verify_source_pins import ROOT_OF_TRUST_SHA256, EXPECTED_SOURCE_PINS, PINS_REL
    payloads = sealed_root_payloads(ROOT, ROOT_OF_TRUST_SHA256)
    for rel, expected in ROOT_OF_TRUST_SHA256.items():
        blob = payloads[rel]
        if blob is None:
            raise SourceIdentityError("SOURCE_ROOT_UNAVAILABLE", rel, exit_code=EXIT_UNAVAILABLE)
        if sha256_bytes(blob) != expected:
            raise SourceIdentityError("SOURCE_ROOT_MISMATCH", rel, observed=blob)
    # Parse the verified object, not a second read of PINS_PATH.
    pins = json.loads(payloads[PINS_REL])
    if {key: pins.get("protocol_identity", {}).get(key) for key in EXPECTED_SOURCE_PINS} != EXPECTED_SOURCE_PINS:
        raise SourceIdentityError("SOURCE_IDENTITY_MISMATCH", PINS_REL, observed=payloads[PINS_REL])
    return pins


def strict_json_bytes(blob: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(value: str) -> Any:
        raise ValueError("nonfinite JSON")

    return json.loads(blob.decode("utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite)


def read_json_input(path: Path, *, with_bytes: bool = False) -> Any:
    rel = path.relative_to(ROOT).as_posix()
    try:
        blob = bounded_regular_bytes(path, root=ROOT, limit=16 * 1024 * 1024)
    except (OSError, ValueError):
        raise SourceIdentityError("INPUT_UNAVAILABLE", rel, exit_code=EXIT_UNAVAILABLE) from None
    try:
        value = strict_json_bytes(blob)
        return (value, blob) if with_bytes else value
    except (ValueError, RecursionError):
        raise SourceIdentityError("INPUT_JSON_INVALID", rel, observed=blob) from None


def minimal_failure_evidence(tool: str, error: SourceIdentityError) -> dict[str, Any]:
    """Does not call any source loader; source failures are collectable once."""
    detail = {"code": error.code, "path": error.path,
              "observed_bytes": error.observed_bytes, "observed_sha256": error.observed_sha256}
    return {"schema_version": "1.0", "generated_at_utc": utc_now(), "tool": tool,
            "result": "FAIL", "exit_code": error.exit_code, "checks": [],
            "failures": [error.code], "failure_details": [detail],
            "source_pins": {"state": "UNVERIFIED"}, "current_action_authority": False,
            "active_source": {"state": "UNVERIFIED", "release_authorization": "NONE"}}


def source_pin_summary() -> dict[str, str]:
    p = load_pins()["protocol_identity"]
    return {
        "ssot_sha256": p["ssot_sha256"],
        "rules_hash": p["rules_hash"],
        "vectors_hash": p["vectors_hash"],
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def extract_between_whole_line_sentinels(blob: bytes, begin: bytes, end: bytes) -> bytes:
    begin_line = begin + b"\n"
    if blob.count(begin) != 1 or blob.count(end) != 1:
        raise ValueError("sentinels must each occur exactly once")
    if begin_line not in blob:
        raise ValueError("begin sentinel is not an exact LF-terminated whole line")
    start = blob.index(begin_line) + len(begin_line)
    stop = blob.index(end, start)
    if stop <= start:
        raise ValueError("invalid sentinel order")
    return blob[start:stop]


def evidence(tool: str, result: str, checks: list[dict[str, Any]], *, failures: list[Any] | None = None, notes: list[str] | None = None, extra: dict[str, Any] | None = None, structured_source_errors: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at_utc": utc_now(),
        "tool": tool,
        "tool_version": "1.0",
        "source_pins": source_pin_summary(),
        "result": result,
        "checks": checks,
        "failures": failures or [],
        "notes": notes or [],
    }
    if extra:
        out.update(extra)
    # This is the current execution context, not a claim that this tool tests R3
    # implementation conformance. Historical source_pins keep their old meaning.
    # The mandatory import/read deliberately fails closed if an adopted source
    # descriptor disappears; no fallback silently selects the old publication.
    from verify_active_source_identity import execution_source
    try:
        out["active_source"] = execution_source()
    except SourceIdentityError:
        raise
    except (OSError, ValueError, KeyError, TypeError):
        if not structured_source_errors:
            # Existing consumers retain the source loader's original exception.
            raise
        raise SourceIdentityError("ACTIVE_SOURCE_UNAVAILABLE_OR_INVALID",
                                  "docs/policy/ACTIVE_SOURCE_IDENTITY.json",
                                  exit_code=EXIT_UNAVAILABLE) from None
    return out


def source_bound_evidence(tool: str, result: str, checks: list[dict[str, Any]], *, failures: list[Any] | None = None, notes: list[str] | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Explicit structured-source boundary for the three current B2 consumers."""
    return evidence(tool, result, checks, failures=failures, notes=notes, extra=extra,
                    structured_source_errors=True)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8", newline="\n")


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def b_completion_source_identity() -> dict[str, Any]:
    """Source of the fixed P4-014/P4-015 historical completion edges only.

    Validate the full current V3 policy first, then require its exact, narrow
    applicability record before validating original V1 receipts. This never
    supplies current generic evidence or extends old tests to the new overlay.
    The snapshot loader additionally binds each original source descriptor.
    """
    from verify_active_source_identity import (R3_BASE_DESCRIPTOR_SHA, SCOPED_POLICY,
                                               execution_source)
    from launch_deliberation_policy import validate_current_context, historical_b_source
    sealed = source_pin_summary()
    try:
        current = execution_source()
        if current.get("schema_version") != "ACTIVE_SOURCE_CONTEXT_V3":
            raise ValueError("current overlay context required")
        registry_raw = bounded_regular_bytes(ROOT / SCOPED_POLICY, root=ROOT, limit=1024 * 1024)
        if sha256_bytes(registry_raw) != current["scoped_addenda"]["descriptor_sha256"]:
            raise ValueError("historical receipt scope registry identity")
        scope = strict_json_bytes(registry_raw)["historical_B_receipts"]
        if (type(scope) is not dict
                or set(scope) != {"scope", "current_overlay_still_validated",
                                  "extends_old_conformance_to_new_overlay", "old_descriptor_sha256"}
                or scope["scope"] != "P4-014_AND_P4-015_IMMUTABLE_ORIGINAL_SOURCE_CONTEXT_ONLY"
                or scope["current_overlay_still_validated"] is not True
                or scope["extends_old_conformance_to_new_overlay"] is not False
                or scope["old_descriptor_sha256"] != R3_BASE_DESCRIPTOR_SHA):
            raise ValueError("historical receipt scope is not the two original edges")
        validate_current_context(current)
        active = historical_b_source()
    except SourceIdentityError:
        raise
    except (OSError, ValueError, KeyError, TypeError):
        raise SourceIdentityError("ACTIVE_SOURCE_UNAVAILABLE_OR_INVALID",
                                  "docs/policy/ACTIVE_SOURCE_IDENTITY.json", exit_code=EXIT_UNAVAILABLE) from None
    return {"sealed": sealed, "active": active}


def _completion_git(arguments: list[str], *, deadline: float, limit: int) -> bytes:
    """Finite local Git read; neither a shell nor any record-supplied command."""
    import subprocess
    import threading
    import time
    if time.monotonic() >= deadline:
        raise ValueError("COMPLETION_SNAPSHOT_TIMEOUT")
    buffers = [bytearray(), bytearray()]
    exceeded = threading.Event()
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    with subprocess.Popen(["git", "--no-replace-objects", "-C", str(ROOT), *arguments],
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=environment,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)) as process:
        def capture(stream: Any, buffer: bytearray, bound: int) -> None:
            try:
                while chunk := os.read(stream.fileno(), 8192):
                    remaining = bound - len(buffer)
                    buffer.extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        exceeded.set()
                        process.kill()
                        break
            except OSError:
                exceeded.set()
            finally:
                stream.close()
        threads = [threading.Thread(target=capture, args=(stream, buffer, bound), daemon=True)
                   for stream, buffer, bound in zip((process.stdout, process.stderr), buffers, (limit, 65536))]
        for thread in threads:
            thread.start()
        timed_out = False
        try:
            process.wait(timeout=max(0.001, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            process.wait(timeout=2)
        for thread in threads:
            thread.join(timeout=1)
        if timed_out or exceeded.is_set() or any(t.is_alive() for t in threads) or process.returncode:
            raise ValueError("COMPLETION_SNAPSHOT_GIT_UNAVAILABLE")
    return bytes(buffers[0])


def b_completion_snapshot_context(producer_id: str, code_commit: str, *, deadline: float) -> dict[str, Any]:
    """Select the two owned predecessor plans from their original regular Git tree.

    The records never select executable commands or expected hashes. A later
    consumer may change tools; that does not relabel its predecessor's old run.
    """
    import ast
    import re
    import shlex
    from verify_founder_approval import task_contract_sha256
    from evidence_record import EDGE_SPECS
    if producer_id not in {"P4-014", "P4-015"} or not isinstance(code_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", code_commit):
        raise ValueError("COMPLETION_SNAPSHOT_IDENTITY")
    edge = next(row for row in EDGE_SPECS if row["producer"] == producer_id)
    git = lambda args, limit=16 * 1024 * 1024: _completion_git(args, deadline=deadline, limit=limit)
    if Path(git(["rev-parse", "--show-toplevel"], 8192).decode("utf-8").strip()).resolve() != ROOT.resolve():
        raise ValueError("COMPLETION_SNAPSHOT_REPOSITORY")
    git(["cat-file", "-e", code_commit + "^{commit}"], 1024)
    git(["merge-base", "--is-ancestor", code_commit, "HEAD"], 1024)
    tree = git(["ls-tree", "-r", "-z", code_commit], 4 * 1024 * 1024)
    entries: dict[str, tuple[bytes, bytes]] = {}
    for row in tree.split(b"\0"):
        if not row:
            continue
        meta, name = row.split(b"\t", 1)
        mode, kind, oid = meta.split()
        entries[name.decode("utf-8")] = (mode, oid) if kind == b"blob" else (b"", oid)
    originals: dict[str, bytes] = {}
    def original(path: str) -> bytes:
        if path not in originals:
            if entries.get(path, (None,))[0] not in (b"100644", b"100755"):
                raise ValueError("COMPLETION_SNAPSHOT_REGULAR_BLOB_REQUIRED")
            originals[path] = git(["cat-file", "blob", entries[path][1].decode("ascii")])
            if len(originals) > 64 or sum(map(len, originals.values())) > 64 * 1024 * 1024:
                raise ValueError("COMPLETION_SNAPSHOT_BOUND")
        return originals[path]

    backlog = strict_json_bytes(original("BACKLOG.json"))
    rows = [task for task in backlog["tasks"] if task.get("id") == producer_id]
    if len(rows) != 1 or rows[0].get("status") not in {"IN_PROGRESS", "DONE"}:
        raise ValueError("COMPLETION_SNAPSHOT_TASK_NOT_STARTED")
    task = rows[0]
    current = read_json_input(ROOT / "BACKLOG.json")
    current_rows = [row for row in current["tasks"] if row.get("id") == producer_id]
    if len(current_rows) != 1 or task_contract_sha256(task) != task_contract_sha256(current_rows[0]):
        raise ValueError("COMPLETION_SNAPSHOT_CURRENT_CONTRACT_MISMATCH")
    fixed = ["MANIFEST.sha256", "REQUIREMENTS.json", "canonical/D3_5_SOURCE_PINS.json",
             "canonical/AGENTS.md", "docs/policy/ACTIVE_SOURCE_IDENTITY.json",
             "docs/policy/ACTIVE_DEVELOPMENT_POLICY.json", "specs/BITAGI_SSOT_D3_5_R3_A2_FINAL_EN.md",
             "tools/verify_active_source_identity.py", "tools/verify_development_policy.py",
             "tools/verify_workflow_policy.py",
             "tools/verify_ci.py", "tools/check_no_secrets.py", "tools/generate_manifest.py",
             "tools/verify_package.py", "tools/verify_diff_scope.py", ".github/workflows/bootstrap.yml"]
    for path in fixed + [task["task_document_path"]]:
        original(path)
    for path in task["allowed_files"]:
        if path.startswith(("tools/", "tests/", "schemas/")):
            if any(character in path for character in "*?[\\:"):
                raise ValueError("COMPLETION_SNAPSHOT_EXACT_INPUT_REQUIRED")
            original(path)
    source = b_completion_source_identity()
    from verify_source_pins import ROOT_OF_TRUST_SHA256
    for path, expected in ROOT_OF_TRUST_SHA256.items():
        if sha256_bytes(original(path)) != expected:
            raise ValueError("COMPLETION_SNAPSHOT_SEALED_SOURCE")
    # The scoped source above is the original R3 V1 identity. A later snapshot
    # containing the current augmented descriptor cannot reuse this legacy
    # route; it must refuse instead of relabeling new execution as an old run.
    if (sha256_bytes(original("docs/policy/ACTIVE_SOURCE_IDENTITY.json")) != source["active"]["descriptor_sha256"]
            or sha256_bytes(original("specs/BITAGI_SSOT_D3_5_R3_A2_FINAL_EN.md")) != source["active"]["ssot_sha256"]):
        raise ValueError("COMPLETION_SNAPSHOT_ACTIVE_SOURCE")
    control_modules = ({"test_standalone_source_identity.py": ["B2-C01"],
                        "test_backlog_input_errors.py": ["B2-C02"],
                        "test_direct_approval_provenance.py": ["B2-C03", "B2-C04"],
                        "test_current_evidence_binding.py": ["B2-C04", "B2-C05", "B2-C06"]}
                       if producer_id == "P4-014" else
                       {"test_file_inclusion_boundary.py": ["B3-C01", "B3-C04"],
                        "test_worktree_visibility.py": ["B3-C03"],
                        "test_task_path_boundary.py": ["B3-C02"]})
    plan = []
    for number, command in enumerate(task["acceptance_commands"], 1):
        argv = shlex.split(command)
        if not argv or argv[0] != "python3" or any(ord(c) < 32 for arg in argv for c in arg):
            raise ValueError("COMPLETION_SNAPSHOT_COMMAND")
        row = {"run_id": f"ACCEPTANCE_{number:02d}", "logical_command": argv, "role": "ACCEPTANCE",
               "expected_exit_code": 0, "expected_result": "PASS", "environment_class": "WINDOWS_LOCAL_CLASS_T",
               "control_ids": [], "output_kind": "JSON_RESULT"}
        if len(argv) > 1 and argv[1].startswith("tools/"):
            row["expected_tool"] = ("verify_p3_006_signer.py" if "--signer-regression" in argv
                                    else "verify_workflow_policy.py" if argv[1] == "tools/verify_development_policy.py"
                                    else argv[1].removeprefix("tools/"))
        if argv[1:7] == ["-B", "-m", "unittest", "discover", "-s", "tests/governance"] and len(argv) == 9 and argv[7] == "-p":
            name = argv[8]
            parsed = ast.parse(original("tests/governance/" + name))
            methods = [node for item in parsed.body if isinstance(item, ast.ClassDef)
                       for node in item.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")]
            if not methods or len(methods) > 512:
                raise ValueError("COMPLETION_SNAPSHOT_TEST_INVENTORY")
            row.update(output_kind="UNITTEST", test_count=len(methods), control_ids=control_modules.get(name, []))
        elif argv == ["python3", "tools/generate_manifest.py"]:
            row.update(output_kind="MANIFEST", manifest_file_count=len(original("MANIFEST.sha256").splitlines()))
        elif argv == ["python3", "tools/bootstrap_self_test.py", "--no-write"]:
            parsed = ast.parse(original("tools/bootstrap_self_test.py"))
            assignments = [node.value for node in parsed.body if isinstance(node, ast.Assign)
                           and any(isinstance(target, ast.Name) and target.id == "COMMANDS" for target in node.targets)]
            if len(assignments) != 1:
                raise ValueError("COMPLETION_SNAPSHOT_BOOTSTRAP_PLAN")
            row.update(output_kind="BOOTSTRAP", bootstrap_command_ids=[item[0] for item in ast.literal_eval(assignments[0])])
        plan.append(row)
    if not plan or len(plan) > 64 or set(cid for row in plan for cid in row["control_ids"]) != set(edge["required_controls"]):
        raise ValueError("COMPLETION_SNAPSHOT_CONTROL_COVERAGE")
    inputs = [{"path": path, "sha256": sha256_bytes(blob), "bytes": len(blob)} for path, blob in sorted(originals.items())]
    return {"producer_task_id": producer_id, "producer_code_commit": code_commit,
            "producer_contract_sha256": task_contract_sha256(task), "producer_task_state_at_run": task["status"],
            "expected_source_identity": source, "input_artifacts": inputs,
            "approved_run_plan": plan, "required_control_ids": list(edge["required_controls"])}
