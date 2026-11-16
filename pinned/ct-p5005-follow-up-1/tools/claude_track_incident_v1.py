#!/usr/bin/env python3
"""CT-P5-005: broadcast-lock incident record V1 verifier (BITAGI_CT_BROADCAST_LOCK_INCIDENT_V1).

The format is frozen 045b section 8.2 (docs/claude-track/plans/CT-P3-045b_PREREGISTRATION_DRAFT_EN.md:847-896)
with its dated notes, the section 14.8 lines :1128-1134 and the section 14.19 item 5 incident bullets
:1739-1743, read with A's decisions I1-I9 of 2026-11-10 (unit note
docs/claude-track/plans/notes/CT-P5-005_EN/2026-11-10_incident-v1-verifier.md). The consolidated tables are in
docs/claude-track/formats/BROADCAST_LOCK_INCIDENT_V1.md. R19-10 (045b:1838) names this tool: it accepts
RUST_PYTHON_MISMATCH_TIP_GE_H0, REFERENCE_DIVERGENCE_REFUSAL and the two release rows of :1742.

Commands:

- `check-record FILE`: one record, the per-record rules.
- `check-set DIR`: every entry of DIR is one record of one deployment's record set (I5); the per-record rules,
  then the set rules of 045b:886-896. Each incident is reported OPEN or RELEASED, and `broadcast_allowed` is
  false while any incident is OPEN (045b:890-891; I9).
- `crosswalk --note PATH`: the D4 crosswalk note's Table A (the 13 SSoT:2847 fields) and Table B (the Class E
  subset of SSoT:2849's 23 criteria) must equal this tool's SSOT_2847_FIELDS and SSOT_2849_CLASS_E_SUBSET, row
  by row and in order, with the note's two counts lines ("The P5-005 verifier carries the same tables",
  045b:1148; A's decision F7 on #258, 2026-11-12). It reads no record.

Per record (each read once as exact bytes, at most RECORD_LIMIT bytes, I7):

- strict parse as 045a section 4.2 (CT-P3-045a_CONFLICT_SET_AND_DISPOSITION_EN.md:560-575): UTF-8 with no BOM; one
  JSON object with JSON whitespace around it and nothing else after it; no duplicate, unknown or missing keys;
  no null; no floats or exponents; no numeric strings or booleans where integers go; every integer
  1 <= x <= 2^53 - 1 (I2: height 0 is refused); hex exactly 64 lowercase characters (git_commit 40);
  enum strings exact;
- the closed key set depends on record_version and trigger: version 1 has none of supersedes_sha256,
  release_evidence and released_at_height, version 2 has all three (045b:859, :872-873, :887-889);
  fork_point_height is required with REORG_TDS_6_7 and refused otherwise (045b:867, :1129; I4);
  digest_absent_reason is present exactly when a state digest is omitted (045b:868-869);
- lock_applied is true (045b:870); incident_id is `INC-` and 8 ASCII digits (045b:857); the five build and
  affected-block fields are required (045b:1134);
- stop_code is one of the 13 codes of 045a section 4.4 (045a:656-668); PRESTATE_MISMATCH_FD_CT_03A and
  RUST_PYTHON_MISMATCH_TIP_GE_H0 take only STOP_DEFECT_DETECTED or STOP_PRESTATE_UNREPRODUCIBLE (I3);
  REFERENCE_DIVERGENCE_REFUSAL goes only with those two triggers (I3) and only with state_digest_reference
  omitted (I3b; 045b:869's note, "a divergence-family refusal that leaves no Python digest");
- affected_txids: lowercase 64-hex, no duplicate (I7), order free, may be empty (045b:871);
- release_evidence (version 2): member names from the release table, each value lowercase 64-hex (045b:872 as
  amended by :1128), and the names exactly one allowed set for (trigger, stop_code) (045b:878-884, :1742,
  :894-895).

Per set (one invocation, one deployment, I5): at most MAX_SET_FILES entries, each a regular file (I7); every
record shares release_class, substrate and profile_sha256 (DEPLOYMENT_MIXED); per incident_id at most one
version 1; a version 2 is refused when it has no version 1, when a second version 2 exists, when its
supersedes_sha256 is not the SHA-256 of the exact version-1 bytes, or when any repeated field differs from
version 1 (each field is compared, presence included; equal means the same JSON value, so affected_txids
keeps its order) (045b:888-895; I1).

What it cannot check: whether a digest is the evidence its member names (a release_evidence value, a claims
list behind PUBLIC_CLAIMS_RECLASSIFIED, a procedure record), whether affected_txids is complete, whether the
heights are consistent with each other (045b states no relation; I4), and whether every lock was recorded:
the record set is caller-supplied.

Output: one JSON line on stdout, sorted keys. A failure names a code, and where it helps a field name from
the closed field list, the 0-based index of the entry in byte-sorted name order (check-set), or a validated
incident_id. Input text is never echoed.

Exit codes (AGENTS.md section 12): 0 valid record, or valid set with broadcast allowed, or a crosswalk note
that matches the tables; 2 malformed record or set, or a crosswalk note that differs; 3 missing or
unreadable input; 4 internal error (also when stdout or stderr cannot be written:
tools/claude_track_exit.run); 6 a version 2 refused under 045b:891-895, or a valid set with an OPEN incident
(code INCIDENT_OPEN: broadcast refused). Optimized Python (-O) is refused.

Class T development tool. It grants no approval, signing, broadcast or release authority.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any, Iterable, Iterator, Mapping, Sequence

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).absolute().parent))
from common import (  # noqa: E402
    EXIT_INTERNAL, EXIT_RELEASE_REFUSAL, EXIT_SUCCESS, EXIT_UNAVAILABLE, EXIT_VALIDATION,
    bounded_regular_bytes, require_debug_mode, sha256_bytes,
)

SCHEMA = "BITAGI_CT_BROADCAST_LOCK_INCIDENT_V1"
RECORD_LIMIT = 1024 * 1024        # I7: tool safety bound per record file
MAX_SET_FILES = 10_000            # I7: tool safety bound per set
MIN_INTEGER = 1                   # 045a:572; I2
MAX_INTEGER = 2**53 - 1           # 045a:572-573
MAX_INTEGER_DIGITS = 20           # parse bound; any longer literal is above MAX_INTEGER

RELEASE_CLASSES = ("CLASS_T", "CLASS_E")                              # 045b:860
SUBSTRATES = ("REGTEST", "PRIVATE_SIGNET", "MAINNET")                 # 045b:861
REORG = "REORG_TDS_6_7"
CRITICAL = "CRITICAL_HEIGHT_DISAGREEMENT_TDS_6_8"
IMPORT = "IMPORT_RESTORE_FAILURE_TDS_7_5"
PRESTATE = "PRESTATE_MISMATCH_FD_CT_03A"
MISMATCH = "RUST_PYTHON_MISMATCH_TIP_GE_H0"
TRIGGERS = (REORG, CRITICAL, IMPORT, PRESTATE, MISMATCH)              # 045b:863 and its note; :1739

DEFECT = "STOP_DEFECT_DETECTED"
UNREPRODUCIBLE = "STOP_PRESTATE_UNREPRODUCIBLE"
# 045a section 4.4, the closed set, in table order (045a:656-668; I3). A test compares it with the table rows.
STOP_CODES = (
    "STOP_GATE_ATTEMPTS_EXHAUSTED", "STOP_RELEASED_CANDIDATES_EXHAUSTED", "STOP_FEE_EXPOSURE_CAP",
    "STOP_PRINCIPAL_EXPOSURE_CAP", "STOP_EXACT_HEIGHT_MISSED", DEFECT, "STOP_SUSPECTED_KEY_COMPROMISE",
    "STOP_BUDGET_RECORD_MISMATCH", "BLOCK_NODE_UNAVAILABLE_OR_DISAGREEING", "BLOCK_STALE_OR_CHANGED_FACTS",
    UNREPRODUCIBLE, "STOP_BEAT_COUNT_EXHAUSTED", "STOP_BEAT_REPLACEMENTS_EXHAUSTED",
)
# I3: the two triggers whose release rows are keyed by stop code (045b:883-884, :1742).
STOP_CODES_FOR_TRIGGER = {PRESTATE: (DEFECT, UNREPRODUCIBLE), MISMATCH: (DEFECT, UNREPRODUCIBLE)}

DIVERGENCE_REASON = "REFERENCE_DIVERGENCE_REFUSAL"
DIGEST_ABSENT_REASONS = ("STATE_PARSE_FAILED", "DIGEST_RECONSTRUCTION_FAILED", "NO_COMPARISON_FOR_TRIGGER",
                         DIVERGENCE_REASON)                            # 045b:869 and its note; :1740
DIVERGENCE_REASON_TRIGGERS = (MISMATCH, PRESTATE)                     # I3

REPLAY = "REPLAY_AND_DIFFERENTIAL_PASS"
AGREEMENT = "NODE_AGREEMENT_RESTORED"
CLAIMS = "PUBLIC_CLAIMS_RECLASSIFIED"
RESOLUTION = "DISAGREEMENT_RESOLUTION_TDS_14_7"
FRESH_IMPORT = "FRESH_IMPORT_TDS_7_5_PASS"
FIXED = "DEFECT_FIXED_AND_VERIFIED"
PROCEDURE_14_8 = "TDS_14_8_PROCEDURE"
FIRST_DIFFERENCE = "FIRST_DIFFERENCE_LOCATED"
FULL_REPLAY = "FULL_REPLAY_MATCH_FROM_INITIAL"
RELEASE_MEMBERS = (REPLAY, AGREEMENT, CLAIMS, RESOLUTION, FRESH_IMPORT, FIXED, PROCEDURE_14_8, FIRST_DIFFERENCE,
                   FULL_REPLAY)
# The allowed release_evidence member sets: key (trigger, stop_code), or (trigger, None) for any stop code.
# "Exactly one of the sets": a release names one whole set and nothing else (045b:875-876, :894-895).
RELEASE_SETS: dict[tuple[str, str | None], tuple[frozenset[str], ...]] = {
    (REORG, None): (frozenset({REPLAY, AGREEMENT, CLAIMS}),),                                    # 045b:880
    (CRITICAL, None): (frozenset({AGREEMENT, RESOLUTION, REPLAY}),),                             # 045b:881
    (IMPORT, None): (frozenset({REPLAY, AGREEMENT}), frozenset({FRESH_IMPORT, AGREEMENT})),      # 045b:882 (a), (b)
    (PRESTATE, DEFECT): (frozenset({FIXED}),),                                                   # 045b:883
    (PRESTATE, UNREPRODUCIBLE): (frozenset({FIXED, PROCEDURE_14_8}),),                           # 045b:884
    (MISMATCH, DEFECT): (frozenset({FIXED, FIRST_DIFFERENCE, FULL_REPLAY, CLAIMS}),),            # 045b:1742
    (MISMATCH, UNREPRODUCIBLE): (frozenset({FIXED, PROCEDURE_14_8}),),                           # 045b:1742
}

# Fields in 045b table order (045b:856-873), then the five of 045b:1134.
FIELD_ORDER = (
    "schema", "incident_id", "record_version", "supersedes_sha256", "release_class", "substrate",
    "profile_sha256", "trigger", "stop_code", "detected_height", "node_a_tip_hash", "node_b_tip_hash",
    "fork_point_height", "state_digest_local", "state_digest_reference", "digest_absent_reason", "lock_applied",
    "affected_txids", "release_evidence", "released_at_height", "git_commit", "build_id", "generated_at_utc",
    "affected_height", "affected_block_hash",
)
RELEASE_FIELDS = ("supersedes_sha256", "release_evidence", "released_at_height")   # version 2 only
FORK_FIELD = "fork_point_height"
DIGEST_FIELDS = ("state_digest_local", "state_digest_reference")
REASON_FIELD = "digest_absent_reason"
CONDITIONAL_FIELDS = (*RELEASE_FIELDS, FORK_FIELD, *DIGEST_FIELDS, REASON_FIELD)
REQUIRED_FIELDS = tuple(field for field in FIELD_ORDER if field not in CONDITIONAL_FIELDS)
# Every field a version 2 repeats from version 1 (045b:888): all but record_version and the release fields.
REPEATED_FIELDS = tuple(field for field in FIELD_ORDER if field != "record_version" and field not in RELEASE_FIELDS)
DEPLOYMENT_FIELDS = ("release_class", "substrate", "profile_sha256")                # I5
HEIGHT_FIELDS = ("detected_height", "fork_point_height", "released_at_height", "affected_height")
HEX64_FIELDS = ("supersedes_sha256", "profile_sha256", "node_a_tip_hash", "node_b_tip_hash", "state_digest_local",
                "state_digest_reference", "build_id", "affected_block_hash")

_HEX64 = re.compile(r"[0-9a-f]{64}")
_HEX40 = re.compile(r"[0-9a-f]{40}")
_INCIDENT_ID = re.compile(r"INC-[0-9]{8}")
_JSON_WHITESPACE = " \t\n\r"

# The SSoT:2847 field crosswalk and the Class E subset table of SSoT:2849's 23 criteria, as Tables A and B of the
# pinned D4 crosswalk note write them (045b:1148, "The P5-005 verifier carries the same tables";
# preregistration/CT_P5_005_EVALUATION_POLICY_V1_FIRST.md:81-85; A's decision F7 on #258, 2026-11-12). Each name
# is the note's verbatim cell, in table order. The source stays ASCII, so U+2026, U+2192 and U+2264 are
# written as \u escapes. `crosswalk --note PATH` checks a note against these tables.
CROSSWALK_NOTE = "docs/claude-track/plans/notes/CT-P3-045b_PREREGISTRATION_DRAFT_EN/2026-11-09_d4-crosswalk.md"
NOTE_LIMIT = 1024 * 1024          # tool safety bound for the note file
DEFINED, VALUE_AT_FREEZE = "DEFINED", "VALUE_AT_FREEZE"
SSOT_2847_FIELDS = (                                                   # Table A, rows 1-13
    ("release class and launch/recognition path", DEFINED),
    ("target and actual population requirements", DEFINED),
    ("observation horizon and block-count convention", DEFINED),
    ("metrics and units", DEFINED),
    ("numerical thresholds", VALUE_AT_FREEZE),
    ("fault intensity", VALUE_AT_FREEZE),
    ("fee-trace dataset", VALUE_AT_FREEZE),
    ("sampling and percentile method", VALUE_AT_FREEZE),
    ("exclusion and missing-data rules", DEFINED),
    ("censoring", DEFINED),
    ("stopping rules", DEFINED),
    ("scope-change process", DEFINED),
    ("accountable approvers", VALUE_AT_FREEZE),
)
# MEASURED_PARTIAL: measured in Class T for ages up to 10,080 only and not claimed above (045b:1148's FD-CT-104
# note and :1584, in force per :1014). The note qualifies age-specific survival in its status cell and abandoned
# births in its basis cell; its counts line names both. Every measured row is Class T and never a Class P claim.
MEASURED, MEASURED_PARTIAL, NOT_CLAIMED = "MEASURED", "MEASURED_PARTIAL", "NOT_CLAIMED"
SSOT_2849_CLASS_E_SUBSET = (                                           # Table B, rows 1-23
    ("mean \u2026 active-chain block-weight share", NOT_CLAIMED),
    ("p95 \u2026 active-chain block-weight share", NOT_CLAIMED),
    ("p99 \u2026 active-chain block-weight share", NOT_CLAIMED),
    ("maximum active-chain block-weight share", NOT_CLAIMED),
    ("separate submission \u2026 measures", MEASURED),
    ("\u2026 disconnected-workload measures", NOT_CLAIMED),
    ("candidate/realized-loss amplification", NOT_CLAIMED),
    ("repeat-winner \u2026 concentration", MEASURED),
    ("mining-pool \u2026 concentration", MEASURED),
    ("common-control concentration", MEASURED),
    ("abandoned births", MEASURED_PARTIAL),
    ("age-specific survival", MEASURED_PARTIAL),
    ("population realization", MEASURED),
    ("heartbeat-age and deadlines", NOT_CLAIMED),
    ("scheduling/recovery peaks", NOT_CLAIMED),
    ("relay acceptance", MEASURED),
    ("fee runway", NOT_CLAIMED),
    ("UTXO residue", NOT_CLAIMED),
    ("wallet-caused `BROKEN`", NOT_CLAIMED),
    ("replay cost", NOT_CLAIMED),
    ("reorganization recovery", MEASURED),
    ("consumer freshness/expiry failures", NOT_CLAIMED),
    ("independent implementation disagreement", MEASURED),
)
# The note's header rows, exactly.
CROSSWALK_A_HEADER = ("#", "SSoT field (verbatim)",
                      "Where it is defined (`file:line`; base line \u2192 amending line)", "Status", "Note")
CROSSWALK_B_HEADER = ("SSoT criterion (verbatim, SSoT:2849)",
                      "measured (045b line, Class T) / not claimed / NOT_ESTABLISHED", "Basis line")
# A Table B status cell opens with a status phrase: its leading **bold** run, or else the whole cell. A phrase
# allows these statuses. "measured" allows MEASURED_PARTIAL because the note marks abandoned births partial outside
# its status cell; the counts line then names the MEASURED_PARTIAL rows exactly (_crosswalk_counts_b).
CROSSWALK_B_PHRASES = {
    "measured": (MEASURED, MEASURED_PARTIAL),
    "measured for ages \u2264 10,080": (MEASURED_PARTIAL,),
    "not claimed": (NOT_CLAIMED,),
}
PARTIAL_QUALIFIER = "for ages up to 10,080 only"
_HEADING = re.compile(r"#{1,6} ")
_SEPARATOR_CELL = re.compile(r":?-{3,}:?")
_CELL_SPLIT = re.compile(r"(?<!\\)\|")

# Every code this tool emits, with its exit code. The format note lists the same table.
CODES = {
    "INPUT_UNAVAILABLE": EXIT_UNAVAILABLE,
    "RECORD_OVERSIZED": EXIT_VALIDATION,
    "RECORD_BOM": EXIT_VALIDATION,
    "RECORD_NOT_UTF8": EXIT_VALIDATION,
    "JSON_INVALID": EXIT_VALIDATION,
    "JSON_DUPLICATE_KEY": EXIT_VALIDATION,
    "JSON_NUMBER_NOT_INTEGER": EXIT_VALIDATION,
    "JSON_INTEGER_TOO_LARGE": EXIT_VALIDATION,
    "JSON_TRAILING_DATA": EXIT_VALIDATION,
    "JSON_NULL": EXIT_VALIDATION,
    "RECORD_NOT_OBJECT": EXIT_VALIDATION,
    "KEY_UNKNOWN": EXIT_VALIDATION,
    "KEY_MISSING": EXIT_VALIDATION,
    "SCHEMA_INVALID": EXIT_VALIDATION,
    "INCIDENT_ID_INVALID": EXIT_VALIDATION,
    "RECORD_VERSION_INVALID": EXIT_VALIDATION,
    "TYPE_INVALID": EXIT_VALIDATION,
    "ENUM_INVALID": EXIT_VALIDATION,
    "STOP_CODE_UNKNOWN": EXIT_VALIDATION,
    "HEX_INVALID": EXIT_VALIDATION,
    "HEIGHT_OUT_OF_RANGE": EXIT_VALIDATION,
    "INTEGER_OUT_OF_RANGE": EXIT_VALIDATION,
    "LOCK_NOT_APPLIED": EXIT_VALIDATION,
    "TXID_DUPLICATE": EXIT_VALIDATION,
    "V1_RELEASE_FIELD": EXIT_VALIDATION,
    "V2_RELEASE_FIELD_MISSING": EXIT_VALIDATION,
    "FORK_POINT_MISSING": EXIT_VALIDATION,
    "FORK_POINT_NOT_ALLOWED": EXIT_VALIDATION,
    "DIGEST_ABSENT_WITHOUT_REASON": EXIT_VALIDATION,
    "REASON_WITHOUT_ABSENT_DIGEST": EXIT_VALIDATION,
    "STOP_CODE_NOT_FOR_TRIGGER": EXIT_VALIDATION,
    "REASON_NOT_FOR_TRIGGER": EXIT_VALIDATION,
    "REASON_DIGEST_MISMATCH": EXIT_VALIDATION,
    "RELEASE_MEMBER_UNKNOWN": EXIT_VALIDATION,
    "SET_TOO_MANY_FILES": EXIT_VALIDATION,
    "SET_ENTRY_NOT_REGULAR": EXIT_VALIDATION,
    "DEPLOYMENT_MIXED": EXIT_VALIDATION,
    "V1_DUPLICATE": EXIT_VALIDATION,
    "RELEASE_EVIDENCE_SET": EXIT_RELEASE_REFUSAL,
    "V2_WITHOUT_V1": EXIT_RELEASE_REFUSAL,
    "V2_DUPLICATE": EXIT_RELEASE_REFUSAL,
    "SUPERSEDES_MISMATCH": EXIT_RELEASE_REFUSAL,
    "V2_FIELD_CHANGED": EXIT_RELEASE_REFUSAL,
    "INCIDENT_OPEN": EXIT_RELEASE_REFUSAL,
    "CROSSWALK_NOTE_OVERSIZED": EXIT_VALIDATION,
    "CROSSWALK_NOTE_NOT_UTF8": EXIT_VALIDATION,
    "CROSSWALK_TABLE_MISSING": EXIT_VALIDATION,
    "CROSSWALK_TABLE_MALFORMED": EXIT_VALIDATION,
    "CROSSWALK_ROW_COUNT": EXIT_VALIDATION,
    "CROSSWALK_NAME_MISMATCH": EXIT_VALIDATION,
    "CROSSWALK_STATUS_MISMATCH": EXIT_VALIDATION,
    "CROSSWALK_COUNTS_MISMATCH": EXIT_VALIDATION,
    "INTERNAL_ERROR": EXIT_INTERNAL,
}


class Outcome(Exception):
    """A typed failure. `code` is a stable identifier; `field` is a name from FIELD_ORDER; `file_index` and
    `incident_id` (validated) place it in a set; `table` ("A" or "B") and `row` (1-based data row) place a
    crosswalk refusal. No input text is carried."""

    def __init__(self, code: str, *, field: str | None = None, incident_id: str | None = None,
                 table: str | None = None, row: int | None = None) -> None:
        super().__init__(code)
        self.code, self.exit_code = code, CODES[code]
        self.field, self.incident_id = field, incident_id
        self.table, self.row = table, row
        self.file_index: int | None = None

    def report(self) -> dict[str, Any]:
        out: dict[str, Any] = {"result": "FAIL", "code": self.code, "exit": self.exit_code}
        if self.field is not None:
            out["field"] = self.field
        if self.file_index is not None:
            out["file_index"] = self.file_index
        if self.incident_id is not None:
            out["incident_id"] = self.incident_id
        if self.table is not None:
            out["table"] = self.table
        if self.row is not None:
            out["row"] = self.row
        return out


class _JsonRefusal(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise _JsonRefusal("JSON_DUPLICATE_KEY")
        result[key] = value
    return result


def _no_float(_text: str) -> Any:
    raise _JsonRefusal("JSON_NUMBER_NOT_INTEGER")


def _bounded_int(text: str) -> int:
    if len(text) > MAX_INTEGER_DIGITS:
        raise _JsonRefusal("JSON_INTEGER_TOO_LARGE")
    return int(text)


def _no_constant(_text: str) -> Any:
    raise _JsonRefusal("JSON_INVALID")    # NaN, Infinity, -Infinity are not JSON


_DECODER = json.JSONDecoder(object_pairs_hook=_pairs, parse_float=_no_float, parse_int=_bounded_int,
                            parse_constant=_no_constant)


def _skip_whitespace(text: str, index: int) -> int:
    while index < len(text) and text[index] in _JSON_WHITESPACE:
        index += 1
    return index


def strict_parse(blob: bytes) -> dict[str, Any]:
    """045a section 4.2 strict parse of one record's exact bytes; a dict with no null anywhere."""
    if len(blob) > RECORD_LIMIT:
        raise Outcome("RECORD_OVERSIZED")
    if blob.startswith(b"\xef\xbb\xbf"):
        raise Outcome("RECORD_BOM")
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError:
        raise Outcome("RECORD_NOT_UTF8") from None
    try:
        value, end = _DECODER.raw_decode(text, _skip_whitespace(text, 0))
    except _JsonRefusal as refusal:
        raise Outcome(refusal.code) from None
    except (ValueError, RecursionError):
        raise Outcome("JSON_INVALID") from None
    if _skip_whitespace(text, end) != len(text):
        raise Outcome("JSON_TRAILING_DATA")
    if not isinstance(value, dict):
        raise Outcome("RECORD_NOT_OBJECT")
    stack: list[Any] = [value]
    while stack:
        item = stack.pop()
        if item is None:
            raise Outcome("JSON_NULL")
        if isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return value


def _hex(value: Any, field: str, pattern: re.Pattern[str] = _HEX64) -> None:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise Outcome("HEX_INVALID", field=field)


def _integer(value: Any, field: str) -> int:
    # bool is an int subclass; strings, floats and null never reach here as int.
    if type(value) is not int:
        raise Outcome("TYPE_INVALID", field=field)
    if not MIN_INTEGER <= value <= MAX_INTEGER:
        raise Outcome("HEIGHT_OUT_OF_RANGE" if field in HEIGHT_FIELDS else "INTEGER_OUT_OF_RANGE", field=field)
    return value


def _enum(value: Any, allowed: Sequence[str], field: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise Outcome("ENUM_INVALID", field=field)
    return value


def _check_value(field: str, value: Any) -> None:
    """One field's own rule (045b:856-873, :1134; 045a:570-575; I2, I7)."""
    if field == "incident_id":
        if not isinstance(value, str) or _INCIDENT_ID.fullmatch(value) is None:
            raise Outcome("INCIDENT_ID_INVALID")
    elif field == "release_class":
        _enum(value, RELEASE_CLASSES, field)
    elif field == "substrate":
        _enum(value, SUBSTRATES, field)
    elif field == "stop_code":
        if not isinstance(value, str) or value not in STOP_CODES:
            raise Outcome("STOP_CODE_UNKNOWN")
    elif field == "digest_absent_reason":
        _enum(value, DIGEST_ABSENT_REASONS, field)
    elif field in HEX64_FIELDS:
        _hex(value, field)
    elif field == "git_commit":
        _hex(value, field, _HEX40)
    elif field in HEIGHT_FIELDS or field == "generated_at_utc":
        _integer(value, field)
    elif field == "lock_applied":
        if type(value) is not bool:
            raise Outcome("TYPE_INVALID", field=field)
        if value is not True:
            raise Outcome("LOCK_NOT_APPLIED")
    elif field == "affected_txids":
        if not isinstance(value, list):
            raise Outcome("TYPE_INVALID", field=field)
        for txid in value:
            _hex(txid, field)
        if len(set(value)) != len(value):
            raise Outcome("TXID_DUPLICATE")
    elif field == "release_evidence":
        if not isinstance(value, dict):
            raise Outcome("TYPE_INVALID", field=field)
        if any(name not in RELEASE_MEMBERS for name in value):
            raise Outcome("RELEASE_MEMBER_UNKNOWN")
        for digest in value.values():
            _hex(digest, field)
    else:   # schema, record_version and trigger are checked before the key-set rules
        raise Outcome("INTERNAL_ERROR")


def check_record(record: Mapping[str, Any]) -> None:
    """The per-record format rules (exit 2). The release-set rule (exit 6) is release_set_check."""
    if any(key not in FIELD_ORDER for key in record):
        raise Outcome("KEY_UNKNOWN")
    if "schema" not in record:
        raise Outcome("KEY_MISSING", field="schema")
    if record["schema"] != SCHEMA or not isinstance(record["schema"], str):
        raise Outcome("SCHEMA_INVALID")
    for field in REQUIRED_FIELDS:
        if field not in record:
            raise Outcome("KEY_MISSING", field=field)
    version = record["record_version"]
    if type(version) is not int:
        raise Outcome("TYPE_INVALID", field="record_version")
    if version not in (1, 2):
        raise Outcome("RECORD_VERSION_INVALID")
    trigger = _enum(record["trigger"], TRIGGERS, "trigger")
    # The closed key set for (record_version, trigger) and the digest/reason coupling.
    for field in RELEASE_FIELDS:
        if version == 1 and field in record:
            raise Outcome("V1_RELEASE_FIELD", field=field)
        if version == 2 and field not in record:
            raise Outcome("V2_RELEASE_FIELD_MISSING", field=field)
    if trigger == REORG and FORK_FIELD not in record:
        raise Outcome("FORK_POINT_MISSING")
    if trigger != REORG and FORK_FIELD in record:
        raise Outcome("FORK_POINT_NOT_ALLOWED")
    digest_omitted = any(field not in record for field in DIGEST_FIELDS)
    if digest_omitted and REASON_FIELD not in record:
        raise Outcome("DIGEST_ABSENT_WITHOUT_REASON")
    if not digest_omitted and REASON_FIELD in record:
        raise Outcome("REASON_WITHOUT_ABSENT_DIGEST")
    for field in FIELD_ORDER:
        if field in record and field not in ("schema", "record_version", "trigger"):
            _check_value(field, record[field])
    # I3: stop codes for the two stop-code-keyed triggers; the divergence reason for its two triggers.
    # I3b: the divergence reason names the omitted Python digest; the local digest may be present or omitted.
    allowed_codes = STOP_CODES_FOR_TRIGGER.get(trigger)
    if allowed_codes is not None and record["stop_code"] not in allowed_codes:
        raise Outcome("STOP_CODE_NOT_FOR_TRIGGER")
    if record.get(REASON_FIELD) == DIVERGENCE_REASON and trigger not in DIVERGENCE_REASON_TRIGGERS:
        raise Outcome("REASON_NOT_FOR_TRIGGER")
    if record.get(REASON_FIELD) == DIVERGENCE_REASON and "state_digest_reference" in record:
        raise Outcome("REASON_DIGEST_MISMATCH")


def allowed_release_sets(trigger: str, stop_code: str) -> tuple[frozenset[str], ...]:
    """The member sets 045b allows for this trigger and stop code (empty when none)."""
    return RELEASE_SETS.get((trigger, stop_code)) or RELEASE_SETS.get((trigger, None)) or ()


def release_set_check(record: Mapping[str, Any]) -> None:
    """A version 2's members are exactly one allowed set (045b:894-895), or it is refused (exit 6)."""
    if record["record_version"] != 2:
        return
    members = frozenset(record["release_evidence"])
    if members not in allowed_release_sets(record["trigger"], record["stop_code"]):
        raise Outcome("RELEASE_EVIDENCE_SET", field="release_evidence")


def _canonical(value: Any) -> str:
    """Type-exact comparison form of a checked value (true is not 1)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


class Checked:
    """What the set rules need from one checked record; the record's bytes are not kept."""

    __slots__ = ("index", "sha256", "incident_id", "version", "trigger", "stop_code", "deployment",
                 "supersedes", "members", "repeated")

    def __init__(self, index: int, blob: bytes, record: Mapping[str, Any]) -> None:
        self.index, self.sha256 = index, sha256_bytes(blob)
        self.incident_id, self.version = record["incident_id"], record["record_version"]
        self.trigger, self.stop_code = record["trigger"], record["stop_code"]
        self.deployment = tuple(record[field] for field in DEPLOYMENT_FIELDS)
        self.supersedes = record.get("supersedes_sha256")
        self.members = frozenset(record["release_evidence"]) if self.version == 2 else frozenset()
        # One entry per repeated field: absent, or the canonical form of its value (I1: all fields, :1134's too).
        self.repeated = tuple((field, _canonical(record[field]) if field in record else None)
                              for field in REPEATED_FIELDS)


def validate_record(blob: bytes) -> dict[str, Any]:
    """check-record: a summary of one valid record, or raise Outcome."""
    record = strict_parse(blob)
    check_record(record)
    release_set_check(record)
    return {"result": "RECORD_VALID", "record_sha256": sha256_bytes(blob), "incident_id": record["incident_id"],
            "record_version": record["record_version"], "trigger": record["trigger"],
            "stop_code": record["stop_code"]}


def _set_refusal(code: str, item: Checked, field: str | None = None) -> Outcome:
    outcome = Outcome(code, field=field, incident_id=item.incident_id)
    outcome.file_index = item.index
    return outcome


def validate_set(blobs: Iterable[bytes]) -> dict[str, Any]:
    """check-set over the records in byte-sorted name order: a summary, or raise Outcome.

    Every record's format first (exit 2), then the set's structure (exit 2), then the version-2 refusals of
    045b:891-895 (exit 6), and last the broadcast state."""
    checked: list[Checked] = []
    for index, blob in enumerate(blobs):
        try:
            record = strict_parse(blob)
            check_record(record)
        except Outcome as outcome:
            outcome.file_index = index
            raise
        checked.append(Checked(index, blob, record))
    if checked:
        deployment = checked[0].deployment
        for item in checked:
            if item.deployment != deployment:
                raise _set_refusal("DEPLOYMENT_MIXED", item)
    incidents: dict[str, dict[int, list[Checked]]] = {}
    for item in checked:
        incidents.setdefault(item.incident_id, {1: [], 2: []})[item.version].append(item)
    for incident_id in sorted(incidents):
        if len(incidents[incident_id][1]) > 1:
            raise _set_refusal("V1_DUPLICATE", incidents[incident_id][1][1])
    report: list[dict[str, Any]] = []
    for incident_id in sorted(incidents):
        opens, releases = incidents[incident_id][1], incidents[incident_id][2]
        if len(releases) > 1:
            raise _set_refusal("V2_DUPLICATE", releases[1])
        if releases and not opens:
            raise _set_refusal("V2_WITHOUT_V1", releases[0])
        entry = {"incident_id": incident_id, "trigger": opens[0].trigger, "stop_code": opens[0].stop_code,
                 "v1_sha256": opens[0].sha256, "state": "OPEN"}
        if releases:
            open_record, release = opens[0], releases[0]
            if release.supersedes != open_record.sha256:
                raise _set_refusal("SUPERSEDES_MISMATCH", release, "supersedes_sha256")
            for (field, before), (_, after) in zip(open_record.repeated, release.repeated):
                if before != after:
                    raise _set_refusal("V2_FIELD_CHANGED", release, field)
            if release.members not in allowed_release_sets(release.trigger, release.stop_code):
                raise _set_refusal("RELEASE_EVIDENCE_SET", release, "release_evidence")
            entry.update(state="RELEASED", v2_sha256=release.sha256)
        report.append(entry)
    open_count = sum(1 for entry in report if entry["state"] == "OPEN")
    summary: dict[str, Any] = {
        "result": "SET_VALID",
        "code": "INCIDENT_OPEN" if open_count else "BROADCAST_ALLOWED",
        "broadcast_allowed": open_count == 0,
        "record_count": len(checked),
        "incident_count": len(report),
        "open_count": open_count,
        "released_count": len(report) - open_count,
        "incidents": report,
    }
    if checked:
        summary["deployment"] = dict(zip(DEPLOYMENT_FIELDS, checked[0].deployment))
    return summary


def _read_file(path: Path, root: Path, limit: int | None = None, oversized: str = "RECORD_OVERSIZED") -> bytes:
    """One bounded read. A regular file over `limit` (RECORD_LIMIT unless given) is malformed (exit 2, code
    `oversized`); an absent, unreadable, linked or non-regular one is unavailable (exit 3)."""
    bound = RECORD_LIMIT if limit is None else limit
    try:
        info = path.lstat()
    except OSError:
        raise Outcome("INPUT_UNAVAILABLE") from None
    if stat.S_ISREG(info.st_mode) and info.st_size > bound:
        raise Outcome(oversized)
    try:
        return bounded_regular_bytes(path, root=root, limit=bound)
    except (OSError, ValueError):
        raise Outcome("INPUT_UNAVAILABLE") from None


def read_set(directory: Path) -> Iterator[bytes]:
    """The set's records in byte-sorted name order, read one at a time. Every entry is a record: a
    subdirectory, link or other non-regular entry is refused, never skipped."""
    root = directory.absolute()
    try:
        info = root.lstat()
    except OSError:
        raise Outcome("INPUT_UNAVAILABLE") from None
    # The set directory itself may be no link and no Windows reparse point (a junction lstat()s as a directory, and
    # an empty one would otherwise pass with no entry read; Desktop P3 on #764, r4522241280).
    if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise Outcome("INPUT_UNAVAILABLE")
    names: list[str] = []
    try:
        with os.scandir(root) as entries:
            for entry in entries:
                names.append(entry.name)
                if len(names) > MAX_SET_FILES:
                    raise Outcome("SET_TOO_MANY_FILES")
    except OSError:
        raise Outcome("INPUT_UNAVAILABLE") from None
    names.sort(key=os.fsencode)

    def records() -> Iterator[bytes]:
        for index, name in enumerate(names):
            path = root / name
            try:
                try:
                    entry_info = path.lstat()
                except OSError:
                    raise Outcome("INPUT_UNAVAILABLE") from None
                if not stat.S_ISREG(entry_info.st_mode):
                    raise Outcome("SET_ENTRY_NOT_REGULAR")
                blob = _read_file(path, root)
            except Outcome as outcome:
                outcome.file_index = index
                raise
            yield blob

    return records()


def _table_cells(line: str, table: str, row: int | None) -> list[str]:
    """One markdown table line: a leading and a trailing pipe, cells split at unescaped pipes, each cell with its
    surrounding spaces stripped and nothing else changed."""
    body = line.rstrip(" ")
    if len(body) < 2 or not body.endswith("|"):
        raise Outcome("CROSSWALK_TABLE_MALFORMED", table=table, row=row)
    return [cell.strip(" ") for cell in _CELL_SPLIT.split(body[1:-1])]


def _note_table(lines: Sequence[str], table: str, header: Sequence[str],
                size: int) -> tuple[list[list[str]], list[str]]:
    """Table `table` of the note: its data rows as cells, and the section's lines that start "Counts:" after it.

    The section runs from the one heading line that starts `## Table <table>:` to the next heading. Its first run
    of lines that start with a pipe is the table: the exact header row, a separator row, then the data rows."""
    starts = [index for index, line in enumerate(lines) if line.startswith(f"## Table {table}:")]
    if not starts:
        raise Outcome("CROSSWALK_TABLE_MISSING", table=table)
    if len(starts) > 1:
        raise Outcome("CROSSWALK_TABLE_MALFORMED", table=table)
    end = next((index for index in range(starts[0] + 1, len(lines)) if _HEADING.match(lines[index])), len(lines))
    section = lines[starts[0] + 1:end]
    piped = [index for index, line in enumerate(section) if line.startswith("|")]
    if not piped:
        raise Outcome("CROSSWALK_TABLE_MISSING", table=table)
    first = last = piped[0]
    while last + 1 < len(section) and section[last + 1].startswith("|"):
        last += 1
    if piped[-1] != last or last - first < 1:     # a second table in the section, or no separator row
        raise Outcome("CROSSWALK_TABLE_MALFORMED", table=table)
    if _table_cells(section[first], table, None) != list(header):
        raise Outcome("CROSSWALK_TABLE_MALFORMED", table=table)
    separator = _table_cells(section[first + 1], table, None)
    if len(separator) != len(header) or not all(_SEPARATOR_CELL.fullmatch(cell) for cell in separator):
        raise Outcome("CROSSWALK_TABLE_MALFORMED", table=table)
    rows: list[list[str]] = []
    for number, line in enumerate(section[first + 2:last + 1], 1):
        cells = _table_cells(line, table, number)
        if len(cells) != len(header):
            raise Outcome("CROSSWALK_TABLE_MALFORMED", table=table, row=number)
        rows.append(cells)
    if len(rows) != size:
        raise Outcome("CROSSWALK_ROW_COUNT", table=table)
    return rows, [line for line in section[last + 1:] if line.startswith("Counts:")]


def _status_word(cell: str) -> str:
    """Table A: the cell, without a surrounding pair of `**` bold markers."""
    if len(cell) > 4 and cell.startswith("**") and cell.endswith("**"):
        return cell[2:-2]
    return cell


def _status_phrase(cell: str) -> str | None:
    """Table B: the cell's leading **bold** run, or else the whole cell. None when the bold run is not closed, or
    is followed by anything but the end of the cell, a colon or a comma."""
    if not cell.startswith("**"):
        return cell
    end = cell.find("**", 2)
    if end < 0 or cell[end + 2:end + 3] not in ("", ":", ","):
        return None
    return cell[2:end]


def _count(table: Sequence[tuple[str, str]], *statuses: str) -> int:
    return sum(1 for _, status in table if status in statuses)


def _crosswalk_counts_a() -> str:
    """Table A's counts line as the tool's table gives it (the note's line may go on after it)."""
    def rows(status: str) -> str:
        return ", ".join(str(number) for number, (_, value) in enumerate(SSOT_2847_FIELDS, 1) if value == status)
    return (f"Counts: DEFINED {_count(SSOT_2847_FIELDS, DEFINED)} (fields {rows(DEFINED)}); VALUE_AT_FREEZE "
            f"{_count(SSOT_2847_FIELDS, VALUE_AT_FREEZE)} (fields {rows(VALUE_AT_FREEZE)}).")


def _crosswalk_counts_b() -> str:
    """Table B's counts line as the tool's table gives it: the measured count includes the MEASURED_PARTIAL rows,
    which the parenthesis names in table order with the age qualifier."""
    partial = " and ".join(name for name, status in SSOT_2849_CLASS_E_SUBSET if status == MEASURED_PARTIAL)
    return (f"Counts: with the FD-CT-104 note of 045b:1148 in force, "
            f"{_count(SSOT_2849_CLASS_E_SUBSET, MEASURED, MEASURED_PARTIAL)} measured ({partial} {PARTIAL_QUALIFIER})"
            f" and {_count(SSOT_2849_CLASS_E_SUBSET, NOT_CLAIMED)} not claimed.")


def _counts_check(found: Sequence[str], expected: str, table: str, tail: bool) -> None:
    """Exactly one counts line, equal to `expected`; with `tail` (Table A), `expected` followed by a space and more
    text is also accepted. Table B's line must be the whole sentence."""
    if len(found) != 1:
        raise Outcome("CROSSWALK_COUNTS_MISMATCH", table=table)
    if not (found[0] == expected or (tail and found[0].startswith(expected + " "))):
        raise Outcome("CROSSWALK_COUNTS_MISMATCH", table=table)


def check_crosswalk(blob: bytes) -> dict[str, Any]:
    """crosswalk: the note's Tables A and B equal SSOT_2847_FIELDS and SSOT_2849_CLASS_E_SUBSET, row by row and
    in order, and its two counts lines agree; a summary, or raise Outcome (exit 2)."""
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError:
        raise Outcome("CROSSWALK_NOTE_NOT_UTF8") from None
    lines = [line[:-1] if line.endswith("\r") else line for line in text.split("\n")]
    rows, counts = _note_table(lines, "A", CROSSWALK_A_HEADER, len(SSOT_2847_FIELDS))
    for number, (cells, (name, status)) in enumerate(zip(rows, SSOT_2847_FIELDS), 1):
        if cells[0] != str(number):
            raise Outcome("CROSSWALK_TABLE_MALFORMED", table="A", row=number)
        if cells[1] != name:
            raise Outcome("CROSSWALK_NAME_MISMATCH", table="A", row=number)
        if _status_word(cells[3]) != status:
            raise Outcome("CROSSWALK_STATUS_MISMATCH", table="A", row=number)
    _counts_check(counts, _crosswalk_counts_a(), "A", tail=True)
    rows, counts = _note_table(lines, "B", CROSSWALK_B_HEADER, len(SSOT_2849_CLASS_E_SUBSET))
    for number, (cells, (name, status)) in enumerate(zip(rows, SSOT_2849_CLASS_E_SUBSET), 1):
        if cells[0] != name:
            raise Outcome("CROSSWALK_NAME_MISMATCH", table="B", row=number)
        if status not in CROSSWALK_B_PHRASES.get(_status_phrase(cells[1]), ()):
            raise Outcome("CROSSWALK_STATUS_MISMATCH", table="B", row=number)
    _counts_check(counts, _crosswalk_counts_b(), "B", tail=False)
    return {
        "result": "DONE",
        "note_sha256": sha256_bytes(blob),
        "ssot_2847": {"rows": len(SSOT_2847_FIELDS), "defined": _count(SSOT_2847_FIELDS, DEFINED),
                      "value_at_freeze": _count(SSOT_2847_FIELDS, VALUE_AT_FREEZE)},
        "ssot_2849": {"rows": len(SSOT_2849_CLASS_E_SUBSET),
                      "measured": _count(SSOT_2849_CLASS_E_SUBSET, MEASURED, MEASURED_PARTIAL),
                      "measured_partial": _count(SSOT_2849_CLASS_E_SUBSET, MEASURED_PARTIAL),
                      "not_claimed": _count(SSOT_2849_CLASS_E_SUBSET, NOT_CLAIMED)},
    }


def main(argv: Sequence[str] | None = None) -> int:
    require_debug_mode()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    record_parser = commands.add_parser("check-record", help="check one incident record")
    record_parser.add_argument("file", type=Path)
    set_parser = commands.add_parser("check-set", help="check one deployment's record set (a directory)")
    set_parser.add_argument("directory", type=Path)
    crosswalk_parser = commands.add_parser("crosswalk", help="check the D4 crosswalk note against the tool's tables")
    crosswalk_parser.add_argument("--note", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        try:
            if args.command == "check-record":
                path = args.file.absolute()
                summary = validate_record(_read_file(path, path.parent))
            elif args.command == "crosswalk":
                path = args.note.absolute()
                summary = check_crosswalk(_read_file(path, path.parent, NOTE_LIMIT, "CROSSWALK_NOTE_OVERSIZED"))
            else:
                summary = validate_set(read_set(args.directory))
        except Outcome:
            raise
        except Exception:  # noqa: BLE001 - mapped to a bounded internal error
            raise Outcome("INTERNAL_ERROR") from None
    except Outcome as outcome:
        report = outcome.report()
        if args.command == "check-set":
            report["broadcast_allowed"] = False
        print(json.dumps(report, sort_keys=True))
        return outcome.exit_code
    code = EXIT_RELEASE_REFUSAL if summary.get("broadcast_allowed") is False else EXIT_SUCCESS
    print(json.dumps({**summary, "exit": code}, sort_keys=True))
    return code


if __name__ == "__main__":
    import claude_track_exit
    claude_track_exit.run(main)
