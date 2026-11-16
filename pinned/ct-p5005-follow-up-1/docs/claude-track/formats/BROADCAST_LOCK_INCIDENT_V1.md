# Broadcast-lock incident record, version 1 (`BITAGI_CT_BROADCAST_LOCK_INCIDENT_V1`), and its verifier

**2026-11-10 · Class T · protocol impact NONE · Claude plan, SELF_REVIEW**

```text
Status: NO PRODUCTION NETWORK ACTIVE · DO NOT ACTIVATE · Class P NO-GO · DO NOT GENESIS
release_authorization NONE. No approval, signing, broadcast or GO authority.
```

This page puts the frozen incident format in one place for the CT-P5-005 verifier. The format itself is
frozen 045b section 8.2 with its dated notes. This page restates it and adds no rule. The rules marked
"(Claude plan, A 2026-11-10)" are A's decisions I1–I7 and I3b. They are listed with their reasons in the
unit note `docs/claude-track/plans/notes/CT-P5-005_EN/2026-11-10_incident-v1-verifier.md`. If this page and
the frozen text ever differ, the frozen text holds.

- Tool: `tools/claude_track_incident_v1.py` (stdlib Python only, no network).
- Tests: `tests/claude_track/test_claude_track_incident_v1.py`.
- Sources, at main `78e6e06c16baa2f0bb0e2cd2b63fe064dcc7f8b3`:
  - "045b" = `docs/claude-track/plans/CT-P3-045b_PREREGISTRATION_DRAFT_EN.md`, frozen by the merge of
    PR #664. The relevant lines are section 8.2 `:847-896` with its dated notes, section 14.8 `:1128-1134`,
    section 14.19 item 5 `:1739-1743`, and R19-10 `:1838`.
  - "045a" = `docs/claude-track/plans/CT-P3-045a_CONFLICT_SET_AND_DISPOSITION_EN.md`. The relevant lines are
    the section 4.2 strict parse `:560-575` and the section 4.4 stop codes `:656-668`.
- Owner: A, as part of the CT-P5-005 unit (`docs/claude-track/plans/CT-P5_PHASE_PLAN_KO.md:142`). The
  verifier registers with the P5-005 follow-up registration.

## 1. Encoding

| Rule | Source |
|---|---|
| One UTF-8 JSON object, hashed as its exact bytes and never re-serialized | 045b:849-850 |
| No secret material, key, descriptor, RPC credential or signed mainnet transaction; a transaction is named by its txid | 045b:850-852 |
| Strict parse: no duplicate, unknown or missing keys; no `null`; no floats or exponents; no numeric strings; no trailing data; no value of another JSON type | 045b:849-850; 045a:570-572 |
| No BOM | 045a:562 |
| Every integer is `1 ≤ x ≤ 2^53 − 1`. Height 0 is refused (Claude plan, A 2026-11-10, I2) | 045a:572-573 |
| Hex is exactly 64 lowercase characters; `git_commit` is 40 | 045a:573; 045b:1134 |
| Enum strings match exactly | 045a:574 |
| At most 1 MiB per record file. This is a tool safety bound, not a format rule (Claude plan, A 2026-11-10, I7) | — |

The verifier's reading of these rules is as follows. JSON whitespace (space, tab, LF, CR) may come before and
after the object. Anything else after the object is trailing data. Key order is free. A string escape that
decodes to a field name is that field. None of this changes the identity, which is always the SHA-256 of the
exact bytes.

## 2. Fields

R = required. V2 = present in version 2 only. C = conditional, with the rule in the last column.

| Field | Type | Presence | Rule | Source |
|---|---|---|---|---|
| `schema` | string | R | `"BITAGI_CT_BROADCAST_LOCK_INCIDENT_V1"` | 045b:856 |
| `incident_id` | string | R | `INC-` followed by exactly 8 ASCII decimal digits. Version 1 and version 2 of one incident share it. It is unique within one deployment's set (see section 4) | 045b:857 |
| `record_version` | integer | R | `1` is the open record and `2` the release record | 045b:858 |
| `supersedes_sha256` | 64 hex | V2 | SHA-256 of the exact version-1 bytes | 045b:859, :889 |
| `release_class` | enum | R | `CLASS_T` \| `CLASS_E` | 045b:860 |
| `substrate` | enum | R | `REGTEST` \| `PRIVATE_SIGNET` \| `MAINNET` | 045b:861 |
| `profile_sha256` | 64 hex | R | the active Profile | 045b:862 |
| `trigger` | enum | R | `REORG_TDS_6_7` \| `CRITICAL_HEIGHT_DISAGREEMENT_TDS_6_8` \| `IMPORT_RESTORE_FAILURE_TDS_7_5` \| `PRESTATE_MISMATCH_FD_CT_03A` \| `RUST_PYTHON_MISMATCH_TIP_GE_H0`. The last is a §14.19 item 5 failure recorded at a run tip at or above H0. `PRESTATE_MISMATCH_FD_CT_03A` keeps the H0−1 comparison at tip H0−1 | 045b:863 and its 2026-11-04 note; :1739 |
| `stop_code` | enum | R | one of the 13 codes of 045a §4.4. With `PRESTATE_MISMATCH_FD_CT_03A` or `RUST_PYTHON_MISMATCH_TIP_GE_H0` it must be `STOP_DEFECT_DETECTED` or `STOP_PRESTATE_UNREPRODUCIBLE`. The other three triggers take any of the 13. TDS 7.5's `REPLAY_STATE_ERROR` is a return value, not a stop code (Claude plan, A 2026-11-10, I3) | 045b:864; 045a:656-668; 045b:883-884, :1742 |
| `detected_height` | integer | R | local committed tip height at detection | 045b:865 |
| `node_a_tip_hash`, `node_b_tip_hash` | 64 hex, internal byte order | R | tips observed at detection. V1 has no value for an unread tip, so an incident with an unread tip cannot be written in V1 (Claude plan, A 2026-11-10, I6) | 045b:866 |
| `fork_point_height` | integer | C | required with `REORG_TDS_6_7` and refused with every other trigger (Claude plan, A 2026-11-10, I4). With `step6=performed` it is `step2_common_ancestor.height` | 045b:867, :1129 |
| `state_digest_local`, `state_digest_reference` | 64 hex | C | the Rust and the Python digest at the compared height. Each may be omitted only when it was never produced. With `step6=performed` they are the Rust and Python `final_state_digest` of the replacement manifest | 045b:868, :1129 |
| `digest_absent_reason` | enum | C | present exactly when one or both digests are omitted. Values: `STATE_PARSE_FAILED` \| `DIGEST_RECONSTRUCTION_FAILED` \| `NO_COMPARISON_FOR_TRIGGER` \| `REFERENCE_DIVERGENCE_REFUSAL`. `REFERENCE_DIVERGENCE_REFUSAL` is accepted only with `RUST_PYTHON_MISMATCH_TIP_GE_H0` or `PRESTATE_MISMATCH_FD_CT_03A`. The other three are accepted with any trigger (Claude plan, A 2026-11-10, I3). `REFERENCE_DIVERGENCE_REFUSAL` also requires `state_digest_reference` to be omitted; `state_digest_local` may be present or omitted (Claude plan, A 2026-11-10, I3b) | 045b:869 and its 2026-11-04 note ("a divergence-family refusal that leaves no Python digest"); :1740 |
| `lock_applied` | boolean | R | must be `true` | 045b:870 |
| `affected_txids` | array of 64 hex | R | project candidates whose status may change. May be empty. For `RUST_PYTHON_MISMATCH_TIP_GE_H0`, version 1 lists every project REGISTER and BEAT whose decision tip or inclusion height is at or above the start of the failed comparison. Duplicates are refused and order is free (Claude plan, A 2026-11-10, I7) | 045b:871, :1741 |
| `release_evidence` | object | V2 | one member per condition the trigger requires (section 3) and no other member. Each member is "the 64-hex digest named for that condition (a tagged hash where the format names its tag)" | 045b:872, amended by :1128 |
| `released_at_height` | integer | V2 | | 045b:873 |
| `git_commit` | 40 lowercase hex | R | TDS §21.3 build identity | 045b:1134 |
| `build_id` | 64 lowercase hex | R | the RX-02 binary SHA-256 | 045b:1134 |
| `generated_at_utc` | integer seconds | R | | 045b:1134 |
| `affected_height` | integer | R | | 045b:1134 |
| `affected_block_hash` | 64 hex, internal byte order | R | "The P5-005 verifier requires them" | 045b:1134 |

So the closed key set of a record depends on `record_version`, `trigger` and which digests were produced:

- Version 1 has none of `supersedes_sha256`, `release_evidence` and `released_at_height` (045b:887).
- Version 2 has all three (045b:888-889).
- `fork_point_height` is present only with `REORG_TDS_6_7`, and always there (I4).

## 3. Release evidence

A version 2 names exactly one of the allowed sets for its trigger, and for its stop code where the row is
keyed by one. Every listed member must be present. None may stand in for another, and no other member is
allowed (045b:875-876, :872, :894-895). "any" means the row is not keyed by stop code.

| `trigger` | stop code | members | Source |
|---|---|---|---|
| `REORG_TDS_6_7` | any | `REPLAY_AND_DIFFERENTIAL_PASS`, `NODE_AGREEMENT_RESTORED`, `PUBLIC_CLAIMS_RECLASSIFIED` | 045b:880 |
| `CRITICAL_HEIGHT_DISAGREEMENT_TDS_6_8` | any | `NODE_AGREEMENT_RESTORED`, `DISAGREEMENT_RESOLUTION_TDS_14_7`, `REPLAY_AND_DIFFERENTIAL_PASS` | 045b:881 |
| `IMPORT_RESTORE_FAILURE_TDS_7_5` | any | set (a): `REPLAY_AND_DIFFERENTIAL_PASS`, `NODE_AGREEMENT_RESTORED` | 045b:882 |
| `IMPORT_RESTORE_FAILURE_TDS_7_5` | any | set (b): `FRESH_IMPORT_TDS_7_5_PASS`, `NODE_AGREEMENT_RESTORED` | 045b:882 |
| `PRESTATE_MISMATCH_FD_CT_03A` | `STOP_DEFECT_DETECTED` | `DEFECT_FIXED_AND_VERIFIED` | 045b:883 |
| `PRESTATE_MISMATCH_FD_CT_03A` | `STOP_PRESTATE_UNREPRODUCIBLE` | `DEFECT_FIXED_AND_VERIFIED`, `TDS_14_8_PROCEDURE` | 045b:884 |
| `RUST_PYTHON_MISMATCH_TIP_GE_H0` | `STOP_DEFECT_DETECTED` | `DEFECT_FIXED_AND_VERIFIED`, `FIRST_DIFFERENCE_LOCATED`, `FULL_REPLAY_MATCH_FROM_INITIAL`, `PUBLIC_CLAIMS_RECLASSIFIED` | 045b:1742 |
| `RUST_PYTHON_MISMATCH_TIP_GE_H0` | `STOP_PRESTATE_UNREPRODUCIBLE` | `DEFECT_FIXED_AND_VERIFIED`, `TDS_14_8_PROCEDURE` | 045b:1742 |

IMPORT takes exactly one of (a) and (b). A record that names all three members, or `REPLAY_AND_DIFFERENTIAL_PASS`
with `FRESH_IMPORT_TDS_7_5_PASS`, is neither set and is refused (045b:882).

Facts the frozen text attaches to these rows. The verifier sees only the 64-hex values, so it does not check
any of them:

- With `step6=performed`, `REORG_TDS_6_7` maps as follows. `REPLAY_AND_DIFFERENTIAL_PASS` is the bundle digest
  `procedure_record_sha256`. `NODE_AGREEMENT_RESTORED` and `PUBLIC_CLAIMS_RECLASSIFIED` are the SHA-256 of the
  canonical bytes of `step7_node_agreement` and of `step8_public_claims`, where a `NOT_APPLICABLE` object is
  the latter's evidence (045b:1129; `REORG_STEP6_RECORD_V1.md` §8.4).
- A not-performed Reorg67 release has no `REPLAY_AND_DIFFERENTIAL_PASS`, so its incident cannot reach version 2
  (045b:1130).
- For `RUST_PYTHON_MISMATCH_TIP_GE_H0`, `PUBLIC_CLAIMS_RECLASSIFIED` is a `bitagi.claude_track.mismatch_claims.v1`
  list when Rust departed. Otherwise it is a `NOT_APPLICABLE` object with reason `PYTHON_DEPARTED` or
  `NO_PUBLIC_CLAIM_AT_OR_ABOVE_FIRST_DIFFERENCE`. B's code accepts the list's shape. Until that code merges, a
  release carrying a list is checked by hand (045b:1743 and its dated lines).
- `FULL_REPLAY_MATCH_FROM_INITIAL` is the (ii) chain, whose digest B-692b fixes. The `TDS_14_8_PROCEDURE`
  full replay comparison is the same chain (045b:1742).

## 4. Set rules

One verifier invocation checks one deployment's record set, given as a directory. Every entry of the
directory is a record (Claude plan, A 2026-11-10, I5).

| Rule | Source |
|---|---|
| Every record in a set has the same `release_class`, `substrate` and `profile_sha256` | Claude plan, A 2026-11-10, I5 (045b:857 "unique per deployment") |
| An incident's state is the state of its highest `record_version` | 045b:886-887 |
| Version 1 opens the lock. A valid version 2 closes that incident | 045b:887-890 |
| Broadcast stays refused while any `incident_id` has no valid version 2 | 045b:890-891 |
| At most one version 1 per `incident_id` | Claude plan, A 2026-11-10, I5 |
| A version 2 is refused if its `supersedes_sha256` is not the SHA-256 of that incident's exact version-1 bytes | 045b:891-892 |
| A version 2 is refused if any repeated field differs. Version 2 repeats every version-1 field unchanged except `record_version`, including `git_commit`, `build_id`, `generated_at_utc`, `affected_height` and `affected_block_hash` (Claude plan, A 2026-11-10, I1). The release record's own build and time are not fields; the release-evidence digests bind them | 045b:888, :892; :1134 |
| A version 2 is refused if a second version 2 exists for the same incident | 045b:893 |
| A version 2 is refused if its `release_evidence` members are not exactly one allowed set (section 3) | 045b:894-895 |
| Both versions are kept as exact bytes. Nothing is rewritten | 045b:895-896 |
| At most 10,000 files per set. This is a tool safety bound, not a format rule (Claude plan, A 2026-11-10, I7) | — |

The verifier reads these rules as follows:

- A version 2 with no version 1 in the set is refused, because its `supersedes_sha256` cannot be the hash of
  "that incident's version 1" (045b:891-892).
- "Unchanged" means the same JSON value. A field that version 1 omits must also be omitted in version 2, and
  `affected_txids` keeps its order.
- A version 2 that changes `release_class`, `substrate` or `profile_sha256` breaks the I5 deployment rule
  first, and the verifier reports it under that rule.

## 5. What the verifier checks and what it cannot

It checks every rule in sections 1–4 for which the record itself carries the evidence. It cannot check the
following:

- Whether a `release_evidence` value is the evidence its member names. This covers the step-6 procedure
  record, the step-7 and step-8 bytes, the claims list or `NOT_APPLICABLE` object, the (i) record and the
  (ii) chain. The verifier sees only digests.
- Whether `affected_txids` is complete, for example the mismatch trigger's list of every REGISTER and BEAT at
  or above the start of the failed comparison (045b:1741).
- Whether `generated_at_utc` and the heights are true, and how they relate to each other. 045b states no
  relation (I4).
- Whether the trigger is the right one, for example `PRESTATE_MISMATCH_FD_CT_03A` at tip H0−1 against
  `RUST_PYTHON_MISMATCH_TIP_GE_H0` at a tip at or above H0 (045b:1739).
- Whether every lock was recorded. The record set is caller-supplied, so an empty set refuses nothing. The
  lock itself does not depend on the record (I6).
- Who produced the record. The producers are B's code.

## 6. Commands

```text
python3 tools/claude_track_incident_v1.py check-record FILE
python3 tools/claude_track_incident_v1.py check-set DIR
```

`check-record` applies the per-record rules (sections 1–3). `check-set` applies them to every entry of DIR
in byte-sorted name order, then the set rules (section 4) (Claude plan, A 2026-11-10, I9). Any subdirectory,
link or other non-regular entry is refused, never skipped.

The checks run in a fixed order:

1. Every record's format, from the parse through sections 2 and 3's member names (exit 2).
2. The set's structure: one deployment, then at most one version 1 per incident (exit 2).
3. The version-2 refusals, incident by incident in `incident_id` order: a second version 2, a version 2 with
   no version 1, `supersedes_sha256`, the repeated fields in section 2's order, then the release set (exit 6).
4. The broadcast state.

## 7. Result line

The verifier writes one JSON line to stdout, with sorted keys. It never echoes input text: it writes only
codes, field names from section 2, an entry's 0-based index in byte-sorted name order (`file_index`), and an
`incident_id` that has already passed its pattern.

- `check-record` pass: `result` `RECORD_VALID`, `record_sha256`, `incident_id`, `record_version`,
  `trigger`, `stop_code`, `exit` 0.
- `check-set` pass: `result` `SET_VALID`, `broadcast_allowed`, `code` (`BROADCAST_ALLOWED` or
  `INCIDENT_OPEN`), `record_count`, `incident_count`, `open_count`, `released_count`, `deployment` (when the
  set is not empty), and `incidents`. `incidents` lists one entry per incident in `incident_id` order, each
  with `incident_id`, `state` (`OPEN` or `RELEASED`), `trigger`, `stop_code`, `v1_sha256`, and `v2_sha256`
  when the state is `RELEASED`. The exit is 0 when `broadcast_allowed` is true and 6 when it is false, so a
  shell `&&` never treats an open incident as a pass.
- Failure: `result` `FAIL`, `code`, `exit`, and where it applies `field`, `file_index` and `incident_id`. A
  `check-set` failure also carries `broadcast_allowed` false.

The exit codes follow AGENTS.md section 12: 0 pass, 2 malformed record or set, 3 missing or unreadable input,
4 internal error, 6 refusal. Exit 4 also covers output that cannot be written (`tools/claude_track_exit.run`).
Optimized Python (`-O`) is refused with exit 6.

## 8. Verifier codes

| Code | Exit | Meaning |
|---|---|---|
| `INPUT_UNAVAILABLE` | 3 | FILE or DIR absent, unreadable, a link or (on Windows) a reparse point such as a junction, or of the wrong kind. A DIR that is a link or reparse point is refused before any entry is listed, so an empty one is refused too (2026-11-10, Desktop P3 on #764) |
| `RECORD_OVERSIZED` | 2 | a record file over 1 MiB (I7) |
| `RECORD_BOM` | 2 | UTF-8 BOM |
| `RECORD_NOT_UTF8` | 2 | not UTF-8 |
| `JSON_INVALID` | 2 | not JSON, including `NaN`, `Infinity` and leading zeros |
| `JSON_DUPLICATE_KEY` | 2 | a key repeated in any object |
| `JSON_NUMBER_NOT_INTEGER` | 2 | a fraction or an exponent |
| `JSON_INTEGER_TOO_LARGE` | 2 | an integer literal over 20 characters |
| `JSON_TRAILING_DATA` | 2 | anything but JSON whitespace after the object |
| `JSON_NULL` | 2 | `null` anywhere |
| `RECORD_NOT_OBJECT` | 2 | the top-level value is not an object |
| `KEY_UNKNOWN` | 2 | a key outside section 2 (its name is not echoed) |
| `KEY_MISSING` | 2 | a required key is absent (`field`) |
| `SCHEMA_INVALID` | 2 | `schema` is not the exact string |
| `INCIDENT_ID_INVALID` | 2 | not `INC-` and 8 ASCII digits |
| `RECORD_VERSION_INVALID` | 2 | an integer other than 1 or 2 |
| `TYPE_INVALID` | 2 | wrong JSON type: a string, boolean, array or object where an integer goes, a non-boolean `lock_applied`, a non-array `affected_txids`, a non-object `release_evidence` (`field`) |
| `ENUM_INVALID` | 2 | `release_class`, `substrate`, `trigger` or `digest_absent_reason` outside its list (`field`) |
| `STOP_CODE_UNKNOWN` | 2 | not one of the 13 045a §4.4 codes |
| `HEX_INVALID` | 2 | not lowercase 64-hex (40 for `git_commit`), including an `affected_txids` entry or a `release_evidence` value (`field`) |
| `HEIGHT_OUT_OF_RANGE` | 2 | a height outside 1 … 2^53 − 1 (I2) (`field`) |
| `INTEGER_OUT_OF_RANGE` | 2 | `generated_at_utc` outside 1 … 2^53 − 1 (`field`) |
| `LOCK_NOT_APPLIED` | 2 | `lock_applied` is `false` |
| `TXID_DUPLICATE` | 2 | a txid listed twice (I7) |
| `V1_RELEASE_FIELD` | 2 | a version 1 with a release field (`field`) |
| `V2_RELEASE_FIELD_MISSING` | 2 | a version 2 without a release field (`field`) |
| `FORK_POINT_MISSING` | 2 | `REORG_TDS_6_7` without `fork_point_height` (I4) |
| `FORK_POINT_NOT_ALLOWED` | 2 | `fork_point_height` with another trigger (I4) |
| `DIGEST_ABSENT_WITHOUT_REASON` | 2 | a digest omitted and no `digest_absent_reason` |
| `REASON_WITHOUT_ABSENT_DIGEST` | 2 | `digest_absent_reason` with both digests present |
| `STOP_CODE_NOT_FOR_TRIGGER` | 2 | PRESTATE or the mismatch trigger with a code other than the two of its rows (I3) |
| `REASON_NOT_FOR_TRIGGER` | 2 | `REFERENCE_DIVERGENCE_REFUSAL` with another trigger (I3) |
| `REASON_DIGEST_MISMATCH` | 2 | `REFERENCE_DIVERGENCE_REFUSAL` with `state_digest_reference` present (I3b) |
| `RELEASE_MEMBER_UNKNOWN` | 2 | a `release_evidence` member name not in section 3 |
| `SET_TOO_MANY_FILES` | 2 | more than 10,000 entries (I7) |
| `SET_ENTRY_NOT_REGULAR` | 2 | a set entry that is not a regular file |
| `DEPLOYMENT_MIXED` | 2 | a record's `release_class`, `substrate` or `profile_sha256` differs from the set's first (I5) |
| `V1_DUPLICATE` | 2 | a second version 1 for one `incident_id` (I5) |
| `RELEASE_EVIDENCE_SET` | 6 | the members are not exactly one allowed set (045b:894-895) |
| `V2_WITHOUT_V1` | 6 | a version 2 with no version 1 in the set |
| `V2_DUPLICATE` | 6 | a second version 2 (045b:893) |
| `SUPERSEDES_MISMATCH` | 6 | `supersedes_sha256` is not the SHA-256 of the exact version-1 bytes (045b:891-892) |
| `V2_FIELD_CHANGED` | 6 | a repeated field differs from version 1 (045b:892; I1) (`field`) |
| `INCIDENT_OPEN` | 6 | the set is valid and an incident is OPEN: broadcast refused (045b:890-891) |
| `INTERNAL_ERROR` | 4 | any other failure inside the tool |

## 9. Crosswalk tables and the `crosswalk` command (added 2026-11-12, A, decision F7 on #258)

Frozen 045b:1148 (freeze condition 9) says "The P5-005 verifier carries the same tables". The tables are the
SSoT:2847 crosswalk of 13 fields and the Class E subset table of SSoT:2849's 23 criteria. The pinned D4
crosswalk note
`docs/claude-track/plans/notes/CT-P3-045b_PREREGISTRATION_DRAFT_EN/2026-11-09_d4-crosswalk.md` holds them as
its Table A and Table B. The first registration carries them by that reference, and the verifier-side copy goes
with this verifier in the follow-up registration that carries it
(`docs/claude-track/preregistration/CT_P5_005_EVALUATION_POLICY_V1_FIRST.md:81-85`). This section adds no rule
to the incident format, and sections 1–8 are unchanged.

The tool holds two constant tables, copied from the note in table order:

- `SSOT_2847_FIELDS`: the 13 field names of Table A, each with its status, `DEFINED` (fields 1–4 and 9–12) or
  `VALUE_AT_FREEZE` (fields 5–8 and 13).
- `SSOT_2849_CLASS_E_SUBSET`: the 23 criteria of Table B, each with `MEASURED`, `MEASURED_PARTIAL` or
  `NOT_CLAIMED`. `MEASURED_PARTIAL` marks abandoned births and age-specific survival, which are measured in
  Class T for ages up to 10,080 only and are not claimed above that (045b:1148's FD-CT-104 note, :1584). No
  measured row is a Class P claim (045b:363-365).

```text
python3 tools/claude_track_incident_v1.py crosswalk --note PATH
```

`crosswalk` reads one note (at most 1 MiB, a regular file and not a link) and checks the following, in this
order. Table A comes first and Table B second.

1. Each table is found. Its section starts at the single heading line that begins `## Table A:` or
   `## Table B:` and ends at the next heading of any level (`#` to `######` and a space). The table is the
   first run of lines in the section that start with `|`. It has exactly the note's header row, then a
   separator row, then the data rows. Every line has a leading and a trailing pipe, cells are split at
   unescaped pipes (`\|` stays inside a cell), and every row has as many cells as the header. Table A's `#` column reads
   1 to 13 in order. A second such heading, or a second run of pipe lines in the section, is refused.
2. Table A has 13 data rows and Table B has 23.
3. Row by row and in order, the name cell equals the tool's name exactly. Only the surrounding spaces of a
   cell are stripped, and there is no other normalization.
4. Row by row, the status matches. A Table A status cell equals the tool's status once one surrounding pair
   of `**` bold markers is removed. A Table B status cell opens with a status phrase, which is its leading
   `**bold**` run or else the whole cell. The phrase `measured` allows `MEASURED` and `MEASURED_PARTIAL`.
   The phrase `measured for ages ≤ 10,080` allows only `MEASURED_PARTIAL`, and `not claimed` allows only
   `NOT_CLAIMED`. Any other phrase is refused.
5. Each section has exactly one line that starts `Counts:` after its table; a line before the table does not
   count. Table A's line is
   `Counts: DEFINED 8 (fields 1, 2, 3, 4, 9, 10, 11, 12); VALUE_AT_FREEZE 5 (fields 5, 6, 7, 8, 13).`, either
   alone or followed by a space and more text. Table B's line is exactly
   `Counts: with the FD-CT-104 note of 045b:1148 in force, 10 measured (abandoned births and age-specific
   survival for ages up to 10,080 only) and 13 not claimed.`, with nothing after it (wording made exact
   2026-11-13, P3 on #833; until then the tool also accepted a tail on Table B's line). The parenthesis names
   the `MEASURED_PARTIAL` rows in table order, so the split between `MEASURED` and `MEASURED_PARTIAL` is
   checked here. The note marks abandoned births partial in its basis cell and counts line, not in its status cell.

On a pass the result line has `result` `DONE`, `note_sha256` (the SHA-256 of the exact note bytes),
`ssot_2847` (`rows`, `defined`, `value_at_freeze`), `ssot_2849` (`rows`, `measured` with the partial rows
included, `measured_partial`, `not_claimed`) and `exit` 0. A failure carries `result` `FAIL`, `code`, `exit`,
and where it applies `table` (`A` or `B`) and `row` (the 1-based data row). No note text is echoed. The
command does not check the other cells of either table (the "where defined" lines, notes and basis lines),
and it does not check that the note is the pinned one. The registration pins the note's bytes.

| Code | Exit | Meaning |
|---|---|---|
| `CROSSWALK_NOTE_OVERSIZED` | 2 | the note is over 1 MiB |
| `CROSSWALK_NOTE_NOT_UTF8` | 2 | the note is not UTF-8 |
| `CROSSWALK_TABLE_MISSING` | 2 | no `## Table A:` or `## Table B:` heading, or no table in its section (`table`) |
| `CROSSWALK_TABLE_MALFORMED` | 2 | the table is not shaped as step 1 says (`table`, and `row` where it applies) |
| `CROSSWALK_ROW_COUNT` | 2 | not 13 (A) or 23 (B) data rows (`table`) |
| `CROSSWALK_NAME_MISMATCH` | 2 | a field or criterion name differs from the tool's at that row (`table`, `row`) |
| `CROSSWALK_STATUS_MISMATCH` | 2 | a status differs from the tool's, or an unknown Table B phrase (`table`, `row`) |
| `CROSSWALK_COUNTS_MISMATCH` | 2 | the counts line is missing, repeated, or differs from the tool's table (`table`) |

A missing or unreadable note, or one that is a link, is `INPUT_UNAVAILABLE` (exit 3), as in section 8.
`check-record` and `check-set` are unchanged.
