# ARDR_JUDGE_V1: A's ARDR judge and its judgement record

Status: J1, J2, J3, J4a and J5 of A's judge for CT-P5-001 (A #258 issuecomment-6557890079, "J1–J6" and decisions
1–14, with A #258 correction of decision 12; A's Q4 in issuecomment-6537782009). This is A's own tool. B may read it
but does not change it. Class T Regtest development evidence only. *2026-11-10 (J4b): and J4b, the judge workflow's wiring (section 27).* *2026-11-11 (045b :1090, section 29): and the record fields 045b :1090 asks for: the `verdict` block and the cause fields (section 29).*

- Tool: `tools/claude_track_ardr_judge.py` (stdlib Python only).
- Tests: `tests/claude_track/test_ardr_judge.py`; J4a's in `tests/claude_track/test_ardr_judge_item2.py`; J5's in
  `tests/claude_track/test_ardr_judge_item4.py`. *2026-11-10 (J4b): J4b's in `tests/claude_track/test_ardr_judge_workflow.py`.*
- J2's replay worker: `crates/bitagi-signer/tests/ardr_judge_replay.rs` (A's own file; section 17).
- Inputs it relies on: `ARDR_RUN_V1.md` (ARV1) sections 2, 3, 4, 6, 9, 11, 12, 13, 15, 16, 17 and 18;
  `ARDR_CLUSTER_V1.md` (CLV1) sections 5–7; 045b (`docs/claude-track/plans/CT-P3-045b_PREREGISTRATION_DRAFT_EN.md`)
  sections 4.3–4.6. J5 also: ARV1 sections 23–26 (:2065-2645 on this branch) and 045b :383, :407-425, :505-506, :524,
  :541-543, :1063-1084 (with the 2026-11-05 notes on :1068 and :1084), :1219-1220.

J1 judges item 1 only. J2 adds the Core replay of the block bytes (section 17) and lifts the J1 CONFIRMATORY
refusal as far as the inputs allow (section 3). J3 adds the pool run (section 19) and the 10% rule over the
registered N across dispatches, with the pool's Herfindahl index (section 20). J4a adds item 2 with the L0 project
seat (section 21) and the item-2 experiment: item 2's private win share, the E13 stratum and the section 4.5 rows
:498-:501 (section 22); A's J4a decisions are section 23. J5 adds item 4: one run of each of its four sub-scenarios
with the L0 project seat (section 24), the sub-scenario's experiment and item 4's outcome with the section 4.5 rows
:505-:506 (section 25); A's J5 decisions are section 26. *2026-11-10 (J4b): the judge workflow's ITEM2 and item-4 wiring, a listed dispatch that declared nothing (P3-2), the listing's `created` filter (P3-8) and what the :501 NO-GO needs are section 27.* *2026-11-10 (J4c): :501's NO-GO, judged from L0-501's `replaces_in_mempool`, is section 28.* *2026-11-11 (045b :1090, section 29): every record that states an outcome also carries `verdict` (`expected`, `observed`, `result`, `inconclusive_reason`), and the cause of a lost gate or unit is kept (`exclusions`, `unit_code`, `collection_code`); section 29.*

## 1. What the judge reads and what it does not

The judge reads only these:

- the raw log of one run (`BITAGI_CT_ARDR_RAW_V1`, ARV1 section 2);
- the policy file and the method policy file (ARV1 sections 3, 15 and 18);
- the 045b file;
- optionally the workflow's collection (ARV1 section 13) and the registration (ARV1 section 4);
- J3's `experiment` (section 20) reads the collections of the listed dispatches and the judge's own per-unit
  records, never a raw log or a driver line.

It recomputes these itself: the seed draws, the item-1 plan, the expected clusters, the expected 4- and
15-report lists, and the link metrics. It compares them with D2-2's own output, which the log carries in the
`CLUSTER_TOOL` line.

It runs one program besides itself: A's replay worker (section 17), as a subprocess with a fixed argv and no
shell. It never imports a driver module (`claude_track_ardr_*`), the slices collector or the offline export driver.
No driver module imports it. A test walks its imports to prove this (`ImportClosure`). Two tests import both the
judge and the driver: `DrawCrossCheck` compares 10,000 draws (A Q4), and J4a's `LadderCrossCheck`
(`test_ardr_judge_item2.py`) compares the judge's 045b :537 ladder with the bidders' `ladder` on a (p_0, b, i) grid,
its L0 p_0 with item 2's `l0_p0`, and its restated draft budget record with the L0 module's. J5's `Item4CrossCheck`
(`test_ardr_judge_item4.py`) is the third: the judge's item-4 seats, roles, fees, median, depth, turns and not-run list
against item 4's `plan_run(..., l0=True)` on a b × r grid, and its expected labels against `expected_l0_labels` and
`expected_reorg_labels` on every turn of a clean run of each sub-scenario.

The driver's claims are never facts for the judge. These lines are claims: `GATE_END` (`winner_txid`,
`wallet`, `block_hash`, `next_birth`), `CORE_REPLAY` (`born`), `GENERATED` (`ladder`), `BLOCK` (`height`,
`block_hash`) and `FUNDING_SENT` (`txid`). The judge derives each fact from the bytes. A claim that differs
is listed under `driver_claims` and changes no state. J5 adds these claims of an item-4 log: `ITEM4_LABELS` (`expected`,
`match`), `ITEM4_L0_LABEL_LINE` (`match`), `ITEM4_L0_OBSERVE` (its parsed copy of the host's lines, the turn, height
and tip), `ITEM4_L0_RELEASE`, `SELF_REGISTER`, `CENSOR_WINDOW`, `CENSOR_MEMPOOL`, `REORG`, `MINER_FILTER` (not read),
`GATE_END` (`born`, `winner`, `block_hash`) and `CORE_REPLAY` per chain (`FINAL`, `REPLACED`).

## 2. Command and exit codes

    claude_track_ardr_judge.py item1 --policy P --method-policy M --raw RAW.jsonl
        [--collection C.json] [--registration R] [--prereg 045b.md] --mode EXPLORATORY|CONFIRMATORY
        [--no-replay | --replay-bin BIN] [--d2-2-tool-at-commit FILE]

J3 (sections 19 and 20): *2026-11-10 (J4b, section 27): `experiment` also takes `--undeclared-run D` (repeatable); `run-query --mode M [--listed-after TIME]` prints the dispatch listing's query; `artifacts` and `unpack` take `--experiment` ITEM2 and the four item-4 names.*

    claude_track_ardr_judge.py pool --policy P --raw RAW.jsonl [--collection C.json] [--registration R]
        [--prereg 045b.md] --mode EXPLORATORY|CONFIRMATORY [--no-replay | --replay-bin BIN]
    claude_track_ardr_judge.py experiment --experiment ITEM1|POOL --policy P --mode EXPLORATORY|CONFIRMATORY
        [--registration R] [--prereg 045b.md] --collection C1.json [--collection C2.json ...]
        [--record R1.json ...] [--runs-listing D --main-history H [--listed-after TIME]]
    claude_track_ardr_judge.py run-pages --dir D

J4a (sections 21 and 22):

    claude_track_ardr_judge.py item2 --policy P --raw RAW.jsonl [--collection C.json] [--registration R]
        [--prereg 045b.md] --mode EXPLORATORY|CONFIRMATORY [--no-replay | --replay-bin BIN]
    claude_track_ardr_judge.py experiment --experiment ITEM2 ... (as above)

J5 (sections 24 and 25):

    claude_track_ardr_judge.py item4 --policy P --raw RAW.jsonl [--collection C.json] [--registration R]
        [--prereg 045b.md] --mode EXPLORATORY|CONFIRMATORY [--no-replay | --replay-bin BIN]
    claude_track_ardr_judge.py experiment
        --experiment ITEM4_SELF_DEALING|ITEM4_FEE_ASYMMETRY|ITEM4_CENSORSHIP|ITEM4_REORG ... (as above)
    claude_track_ardr_judge.py item4-outcome --mode EXPLORATORY|CONFIRMATORY [--record E1.json ...] [--prereg 045b.md]

`--prereg` defaults to the tree's 045b file. `--replay-bin` names the prebuilt replay worker (section 17); without
it the judge runs the worker through cargo. `--no-replay` (EXPLORATORY only) judges without the replay.
`--d2-2-tool-at-commit` names the D2-2 file's bytes at the judged run's commit (the workflow's `git show`, section
18): every `CLUSTER_TOOL.tool_sha256` must be their SHA-256, in any mode (`D2_2_TOOL_NOT_AT_RUN_COMMIT`, exit 6).

The judge prints exactly one line to stdout:

- the judgement record, canonical JSON (sorted keys, `,` and `:`, ASCII) and one LF, with exit 0; or
- one refusal line `{"code", "exit", "result": "FAIL"}` with that exit. *2026-11-11 (045b :1090, section 29): the refusal line is the command's status, not a verdict; its `result` `FAIL` is not a requirement verdict (section 29).*

The line ends in one LF on every platform. On a text stdout that would write CRLF (native Windows), the judge
sets it to write LF unchanged before it prints anything (#650, Desktop P3).

Exit codes (AGENTS.md section 12):

| Exit | Meaning |
|---|---|
| 0 | a judgement record was written, whatever its outcome (GO, NO_GO or NOT_ESTABLISHED) |
| 2 | validation failure: a malformed input or log |
| 3 | missing prerequisite: a file that cannot be read, a PENDING value in CONFIRMATORY, a CONFIRMATORY input that is not there (the replay, the collection, the registered D2-2 hash), a replay worker that does not run *2026-11-11 (045b :1090, section 29): a replay worker that runs past its time has its own code, `REPLAY_WORKER_TIMEOUT`, also exit 3* |
| 4 | internal error: the replay worker's answer does not follow section 17, or stdout cannot be written (`tools/claude_track_exit.run`) |
| 6 | binding refusal: a hash that does not match, a disagreeing collection, a CONFIRMATORY log in EXPLORATORY mode, `python -O` |

Exit 0 is not GO. The outcome is in the record's `outcome.result`. *2026-11-11 (045b :1090, section 29): the requirement verdict, the same fact in the words 045b :1090 asks for, is in `verdict.result`.*

Two choices differ from a neighbour tool:

- `python -O` is exit 6 (`OPTIMIZED_PYTHON`), as the driver and the collector refuse it; D2-2 uses 5.
- `RAW_LOG_GATES` is exit 2 here, a log the judge cannot read as ARV1 section 13 describes; the collector refuses
  the same shapes with exit 6.

## 3. Modes

- **CONFIRMATORY** (J2). The judge first runs the binding checks below. Then, in this order:
  - with `--no-replay` it refuses `REPLAY_NOT_BUILT`, exit 3 (J1 refused every CONFIRMATORY run so; J2 lifts it
    only when the replay runs);
  - without `--collection` it refuses `COLLECTION_REQUIRED`, exit 3;
  - it reads the registration's `d2_2_tool_sha256`: the SHA-256 of the bytes of
    `tools/claude_track_ardr_cluster.py` (the D2-2 file CONFIRMATORY runs, ARV1 section 18 :1496-1499) at the
    registered commit. Without the key it refuses `D2_2_TOOL_NOT_REGISTERED`, exit 3; a value that is not 64
    lowercase hex is `REGISTRATION_D2_2_TOOL`, exit 2. Every `CLUSTER_TOOL.tool_sha256` in the log must equal it
    (`D2_2_TOOL_SHA256`, exit 6).
  - **The key is A's decision** (A #258, J2 PR). ARV1 section 4 (B's document) names only `ardr_policy_sha256` today;
    it gains the `d2_2_tool_sha256` line at the 045b freeze PR (about 11-12). Until then a registration without the
    key is refused as above.
  - With `--d2-2-tool-at-commit` (the workflow path) the D2-2 file at the run's commit binds the same lines too
    (section 2); a match there does not lift the registration's check.
  - A CONFIRMATORY record is then made with the replay. One without the replay exists only when no gate is judged:
    `births` `NOT_REPLAYED_NO_JUDGED_GATE`, outcome NOT_ESTABLISHED (`NO_JUDGED_GATES`).
- **EXPLORATORY** judges the log with the replay (section 17): `births: REPLAYED`. With `--no-replay` it takes the
  birth of each gate from block G without replay (section 7) and says `births: UNVERIFIED_NO_REPLAY`. Either way
  the record carries the label `EXPLORATORY_NOT_A_VERDICT`.
  `--registration` is refused in this mode (`EXPLORATORY_REGISTRATION`). A log whose line 1 is CONFIRMATORY
  is refused in this mode (`LOG_MODE_MISMATCH`, exit 6): a confirmatory log gets only a confirmatory
  judgement.

## 4. Inputs and binding

**045b and the constants (decision 5).** The NO-GO thresholds are judge constants (`THRESHOLDS` in the tool).
Each entry cites one 045b line. At run time the judge reads the 045b file and checks that each entry's phrase
stands on its cited line (`PREREG_CITATION`, exit 6). The record carries the file's SHA-256 and the table.
The policy schema does not change. So a 045b edit that moves a cited line makes the judge refuse until A
updates the table. The table is the single source: the working constants (the report thresholds, the gate
count, the wallet and owner counts, the planted gates, the flag shares, the 10% limit, the recall and precision
minimum) are read from it, so the cited value is the value used. *2026-11-11 (045b :1090, section 29): this unit's constant, `VERDICT_MAPPING` (045b :1090), the mapping from an outcome to `verdict.result`, is not in the table below, which keeps its lines; section 29 gives it. (Nor are J5b's `ITEM4_MIN_TRANSITIONS`, `ITEM4_MIN_REACH` and `ITEM4_TRANSITION_UNREACHED`; section 25.)*

| Constant | Value | 045b line |
|---|---|---|
| `ITEM1_LINK_RECALL_MIN`, `ITEM1_LINK_PRECISION_MIN` | 1 | 380 |
| `ITEM1_REPORT_THRESHOLDS` | 4, 15 | 434 |
| `ITEM1_GATES` | 200 | 521 |
| `ITEM1_WALLETS_OWNERS` | 40, 10 | 531 |
| `ITEM1_PLANTED_GATES` | 100–119 | 532 |
| `ITEM1_ANCESTRY_SHARE`, `ITEM1_KEY_REUSE_SHARE` | value below 30 of 100 | 553, 554 |
| `ITEM1_EXCLUSION_UNIT` | the gate | 546 |
| `EXCLUSION_LIMIT` | more than 1/10 | 572 |
| `ITEM2_PRIVATE_WIN_SHARE_MAX` | 1/2 (J4) | 381 |
| `MINED_LOSING_SHARE_MAX` | 25/100 (J4) | 499 |
| `POOL_HHI_MAX` | 1/2 (J3) | 504 |
| `ITEM3_ZERO_BEAT_GATES` | 15 (J6) | 435 |
| `POOL_RUNS_GATES` | 50 runs of 4 gates (J3) | 545 |
| `POOL_PRODUCER_DRAW` | n = 100: A below 50, B below 80, else C (J3) | 560 |
| `POOL_EXCLUSION_UNIT` | the gate (J3; decision 6: the line defines the run) | 546 |
| `ITEM1_RUNS` | 1 (J3) | 546 |
| `FIXED_N` | the registered N (J3) | 571 |
| `DISPATCHED_ONCE` | each unit once (J3) | 577 |
| `ITEM2_RUNS`, `ITEM2_EXCLUSION_UNIT` | 200 runs; the run (J4a) | 546 |
| `ITEM2_COMPLETED`, `ITEM2_QUALIFYING`, `ITEM2_STRATUM_LIMIT` | OBSERVED; r = 0, 2, …, 98; more than 5 of 50 (J4a, E13) | 1218 |
| `ITEM2_GATE_INTERVAL` | n = 1,200, t_G = value + 1 s (J4a) | 559 |
| `ITEM2_RUNG_SECONDS`, `ITEM2_LADDER` | 60 s; v 213, rung 7 the last, cap 4b (J4a) | 537 |
| `ITEM2_EXCLUSION_CODES`, `ITEM2_G_LATE_SECONDS` | the four item-2 codes in order; 1 s (J4a) | 1050 |
| `ITEM2_WINNER_BY_TXID` | the winner by txid, never Anchor key (J4a, F9; 045b :1220 as corrected by Reviewer bundle 20, `cc351920`: item 2 by txid, item 4 also by the funding outpoint) | 1220 |
| `CANDIDATES_EXACT` | observed equals predicted in every gate (J4a) | 498 |
| `L0_LOSING_FEE_PER_ATTEMPT_MAX` | 500000/24, `source` DRAFT (J4a) *2026-11-10 (A): `source` FROZEN; the freeze wrote the value (045b A2 :1176, section 14.21 :1899; decision 4)* | 500 |
| `L0_LOSING_FEE_DRAFT` | 500000/24, the draft value (J4a) *2026-11-10 (A): the frozen value, :1176's "stays (500,000 / 24" (FD-CT-102); the name is kept* | 1176 |
| `L0_MAX_FEE_PER_CANDIDATE_DRAFT` | 100,000 sat (J4a) *2026-11-10 (A): 30,000 sat, frozen (045b A1 :1175, FD-CT-102; the Class T record `7d0a7a35…`, section 14.21 :1898-1899); the name is kept* | 1175 |
| `L0_P0_RULE`, `L0_MAX_GATE_ATTEMPTS`, `L0_FEE_EXACT` | `CEIL_2_5_B`; 24; f_k on every rung (J4a) *2026-11-10 (A): `L0_MAX_GATE_ATTEMPTS` cites :1053's freeze line (the frozen policy's `max_gate_attempts` 24)* *2026-11-12 (A, FD-CT-133, section 30): `L0_P0_RULE` is `MAX_P0_TWO_RUNGS`; the row still cites :1053, the value it replaces (`amends`)* | 1053 |
| `L0_CHARGED_NOT_RELEASED` | not released rungs (J4a) | 1055 |
| `ITEM2_L0_SEAT` | seat 1 (J4a, F2) | 1219 |
| `ITEM2_L0_H0` | 1000 (J4a) | 1054 |
| `ROW_NOT_MEASURED` | a row not measured is NOT_ESTABLISHED (J4a) | 1061 |
| `PERCENTILE_NEAREST_RANK` | nearest rank (J4a) | 565 |
| `ITEM4_MISLABEL_NOGO`, `ITEM4_NOT_RUN` | any judged label that differs is NO-GO; a sub-scenario not run is NOT_ESTABLISHED (J5) | 383 |
| `ITEM4_LABEL_TABLE` | the table of :415, :416, :419 (J5) | 410 |
| `ITEM4_LOST_NOT_MINED`, `ITEM4_E10S` | `Stale` with the opening missed, not Done; P0 `Done:IncludedNoEffect` in G (J5) | 415, 419 |
| `ITEM4_TURNS`, `ITEM4_LABEL_INCLUDED`, `ITEM4_LABEL_LOST`, `ITEM4_LABEL_UNRELEASED`, `ITEM4_FLAGS`, `ITEM4_NEXT_BIRTH`, `ITEM4_MISLABEL_FIELDS` | the three sub-scenarios' turns and labels, every rung, the four judged fields, the next birth from the judge's replay (J5; A's Q2 line, the 2026-11-05 note) | 1068 |
| `ITEM4_E9D_BORN`, `ITEM4_E9D_OTHERS`, `ITEM4_E9D_LOCKED`, `ITEM4_E9D_STALE`, `ITEM4_E9D_FLAGS`, `ITEM4_LABEL_LINE`, `ITEM4_RELEASE_STEP`, `ITEM4_MISS` | E9-d: `Done:Born` and `Done:ProjectBornByOther` at G and G + 1, the locked pair, the STALE turn, the flags before and from the replacement tip, the label line with its release step, CONTINUE_WITHIN_LIMITS only (J5) | 1068 |
| `ITEM4_RUNS` | 50 runs per sub-scenario (J5) | 524 |
| `ITEM4_EXCLUSION_UNIT`, `ITEM4_SUBSCENARIO_LIMIT`, `ITEM4_LABEL_CHECK_JUDGED`, `ITEM4_LABEL_JUDGED_RUN`, `ITEM4_PARTIAL_RUN`, `ITEM4_ORDER` | the run; more than 5 of 50 (or no judged run) is not run; the driver's own label-check runs judged; a label-judged run; a partial run's evidence; NO-GO first (J5; A's Q1/Q4 line, the 2026-11-05 note) | 1084 |
| `ITEM4_SELF_FEE`, `ITEM4_SELF_BELOW_HONEST`, `ITEM4_SELF_FEE_FLOOR_B` | 600 sat; strictly below every honest rung 0 in G; b ≥ 1127 (J5) *2026-11-12 (section 30): `ITEM4_SELF_FEE_FLOOR_B` is b ≥ 1058 with FD-CT-133's p_0 (`amends` 1127)* | 1065 |
| `ITEM4_ASYM_FACTOR` | 10, `source` DRAFT until F15 (J5, A's Q11) *2026-11-10 (A): F15 is item 4's follow-up registration (045b :1078's and :1198's dated lines); `source` stays DRAFT* | 541 |
| `ITEM4_ASYM_SEATS_MEDIAN`, `ITEM4_ASYM_DRAW` | S0 asymmetric, S1 L0, S2-S4 drawn, the nearest-rank p50; `BID_FEE_2` … `BID_FEE_4`, n = 3b + 1 (J5) | 1078, 1076 |
| `ITEM4_ASYM_FEE_CAP`, `ITEM4_COMPETITOR_FEE`, `ITEM4_CENSOR_WINDOW`, `ITEM4_WINNER_READDED` | 90,000 sat; 2 × f_0 + 1; G … G + 143, lifted at G + 144; by txid or funding outpoint (J5) | 1079 |
| `ITEM4_REORG_DEPTH`, `ITEM4_REORG_REPLACEMENT` | depth 1 for even r, 2 for odd r; d + 1 replacement blocks (J5) | 1070 |
| `ITEM4_NOT_RUN_LIST`, `ITEM4_E7_NOT_RUN`, `ITEM4_RELEASE_CLASS_T_RUN` | the not-run cases; E7 in every L0 run; "the release is a Class T test step" (J5) | 1067, 1066 |
| `ITEM4_RELEASE_CLASS_T_ROW`, `ITEM4_RELEASE_MARK` | "release: Class T test step"; the mark in the raw log (J5) | 1069 |
| `ITEM4_L0_SEAT`, `ITEM4_WINNER_BY_OUTPOINT` | the project seat S1 / S0 by scenario; winners by txid and funding outpoint (J5) | 1219, 1220 |
| `ITEM4_H0` | 1000 (J5) | 1054 |
| `ITEM4_ROW_505`, `ITEM4_ROW_506` | the rows take item 4's outcome (J5) | 505, 506 |
| `ITEM4_MINED_LOSING_REPORTED`, `ITEM4_LEDGER_C` | item 4's mined-losing figures reported only; Ledger C is the replaced branch (J5, A's Q12) | 536, 1061 |

J4a's lines at 1050 and above are the 045b freeze draft's (sections 14.4 and 14.15, branch `claude/a-045b-freeze`;
A's J4a decision 1): on a 045b without them the judge refuses `PREREG_CITATION`. *2026-11-10 (A): #664 merged them to main (`317ecbf5`), with the frozen files in `docs/claude-track/preregistration/`; 045b kept its line numbers.*
J5's :1068 and :1084 rows cite the notes dated 2026-11-05 at the end of those lines (#664 head `f090ca9b`): a 045b without them is refused the same way. *2026-11-10 (A, J5 after the freeze): main `317ecbf5` holds them with the same text. The freeze left item 4's own values DRAFT: they are fixed by item 4's follow-up registration (045b :1079, :1198, :1260), and the item-4 `l0_seat` keys come with item 4's follow-up policy (:1053's dated line), so no item-4 constant changes; the L0 seat's frozen values (30,000 sat, 500000/24, the Class T record) reach item 4 through item 2's L0 checks.*

**Policy.** The judge reads the policy as bytes (at most 1 MiB, no duplicate key, no float). It checks the
closed key set, the seed and the `ITEM1` entry (ARV1 sections 3 and 18). Without `params` an EXPLORATORY
run takes ARV1's DRAFT params (b 3,000, H0 110, 200 gates). CONFIRMATORY needs params, 200 gates, a count,
a declared method policy and no PENDING value.

**Method policy.** Its SHA-256 must be the one the policy names (`METHOD_POLICY_SHA256`, exit 6). A PENDING
value takes ARV1's DRAFT value in EXPLORATORY. Its thresholds must be 045b's 4 and 15
(`METHOD_THRESHOLDS`).

**Registration** (CONFIRMATORY only; ARV1 section 4 placeholder). It must list the policy SHA-256 and the
method policy SHA-256. The raw log's first line must be CONFIRMATORY and carry the registration's SHA-256.

**Raw log.** The judge reads the log once, in order:

- at most 256 MiB, one line at most 32 MiB, a regular file, not a symlink; every input is opened without
  blocking, so a FIFO or a device is refused (`_NOT_REGULAR`) instead of waited on;
- each line one ASCII JSON object ending in LF, with no duplicate key;
- the fields the judge reads have their JSON types: integers, strings, lists of integers, and booleans only as
  `true` or `false` (never `0`, `1` or `0.0`). A float in a line the judge reads is refused. A float is accepted
  only in node answers the judge does not read (for example `TESTMEMPOOLACCEPT`). The code is the line's
  family: `RAW_LOG_GATES` (gate lines, `PREFIX_START`, `RUN_END`), `RAW_LOG_CLUSTER`, `RAW_LOG_FUNDING`,
  `RAW_LOG_BLOCK`, else `RAW_LOG_TYPES`;
- `RUN_END` has `status` `DONE` or `FAILED`, and a FAILED one has a `phase` of ARV1 section 16 (`GATES`,
  `POST_GATES`, `CLUSTER`, `END`); else `RAW_LOG_GATES`;
- every line has the section 2 envelope, `schema` `BITAGI_CT_ARDR_RAW_V1`, `seq` 1, 2, 3 … with no gap or repeat,
  and the same mode, evidence status, policy hash, registration hash and labels as line 1 (J5: except the `labels` of
  `L0_LABELS`, `ITEM4_LABELS` and `ITEM4_L0_OBSERVE`, which is the line's own field: the driver's `RawLog.write` puts
  the line's fields after the header, so their host labels replace the envelope's; ARV1 section 2 :75-80 says so since B-J5Z);
- line 1 is `RUN_START`; the policy hash is the policy file's (exit 6); `unit` is ITEM1 with one run index;
- only item-1 events are accepted (`RAW_LOG_EVENT` otherwise); `RUN_START` and `BIDDERS` appear once;
- no line follows `RUN_END`, whether it parses or not (`RAW_LOG_AFTER_END`; ARV1 section 13 :722-724: the
  driver writes `RUN_END` last, so a line after it is never a kill's leftover);
- a line that does not parse is refused (`RAW_LOG_JSON`), except the last one before any `RUN_END`. A cut last
  line marks the log truncated, and the unit is EXCLUDED `RAW_LOG_TRUNCATED` (ARV1 section 13 :630-633).

## 5. The seed draw

The draw is ARV1 section 6 and 045b 4.6: `D = SHA-256(seed ‖ e ‖ 0x00 ‖ u32be(r) ‖ label ‖ 0x00 ‖ u32be(k))`.
`x` is the first 8 bytes of D as a big-endian u64. `x mod n` is accepted only when `x < floor(2^64 / n) × n`.
Otherwise the draw retries with `k + 1`.

There is no 2^20 cap: k runs up to 2^32 − 1 (decision 13). The driver caps it at 2^20 (`DRAW_TRIES`). The two
can differ only past 2^20 retries, which has probability below 2^−(2^20).

## 6. The item-1 plan

The plan comes from the policy's seed, run index r and `gates_per_run`:

- `OWNER_W<ii>` (n = 10) gives wallet `W<ii>` the owner `O<value>`.
- `ANCESTRY_W<ii>` below 30 sets the ancestry flag. `KEY_REUSE_W<ii>` below 30 sets the key-reuse flag.
- The planted owner has the most wallets; on a tie, the lowest owner index wins. Its wallet count is m.
- Gate 100 + j goes to the planted owner's wallet j mod m, in ascending wallet order, with no draw. Every
  other gate draws `WINNER_G<ggg>` (n = 40) and goes to `W<value>`.
- **Heart number h** (decision 3): the number of the wallet's earlier wins in this run, in gate order, from 0.
- **Anchor label.** A reusing wallet carries its owner's base key `SYNTHETIC_<base>_ANCHOR_H000` in every gate.
  `<base>` is the owner's lowest-indexed wallet. Any other wallet carries `SYNTHETIC_<w>_ANCHOR_H<hhh>`. So the
  base wallet's h = 0 gate also carries the base key.
- **Funding.** A flagged wallet's `(wallet, gate)` output is in its owner's OWNER transaction. Any other
  output is in the FAN_OUT.
- Rung 0 pays `ceil(b × 213 / 1000)` (ARV1 section 16).

## 7. Bytes, chain and births

**Parser.** The judge parses each accepted `BLOCK`'s `block_hex` and each `FUNDING_SENT`'s `hex` itself:

- segwit aware; the txid hashes the serialization without witness;
- canonical varints only; no trailing byte; a superfluous witness is refused;
- the merkle root is recomputed; the first transaction is the only coinbase;
- the height is the coinbase's BIP34 push (OP_1–OP_16, or a minimal push).

The judge does not check proof of work.

**Chain.** The chain starts at the last accepted block and goes back by previous-block hash to height 1. Each
height must be its parent's plus one. Accepted blocks off this chain are counted as `stale_blocks`.

**Funding.** `FUNDING_SENT.outputs` names `[wallet, gate]` for output 0, 1, 2 … of its transaction, in output
order (ARV1 section 12). These are run-level layout problems (`funding_problems`):

- not exactly one FAN_OUT;
- a funding transaction that is not on the chain below H0;
- an OWNER transaction whose one input is not a FAN_OUT output;
- a repeated label, or a label outside the run's wallets and gates;
- funding scripts whose equality does not follow the wallets (one fee key per wallet).

**One OWNER transaction per owner** (A's J1 review; ARV1 section 9 :339-340 rejects one per gate).
Each owner's ancestry-flagged `(wallet, gate)` outputs must all be in one OWNER transaction. These transactions
must be exactly the OWNER lines, one per owner with a flagged seat. Else the run field `OWNER_SPLIT`.

**ANCESTRY on chain** (A's J1 review; 045b:380 measures the links actually placed). The judge reads the
gate-level ANCESTRY groups from the bytes: births that spend outputs of one funding transaction other than the
excluded FAN_OUT. They must equal the plan's ANCESTRY groups (section 10). Else the run field
`ANCESTRY_ON_CHAIN`. So a layout that places no shared ancestor gives NOT_ESTABLISHED, never a GO on links that
are not on chain and never a NO-GO that blames D2-2.

**Births in block G.** The gate height G comes from `GATE_START`; the replay (section 17) verifies it.
G0 must be H0, and later heights must increase. In block G, exactly one transaction must spend a labelled
funding output. It must have one input, and that input must be the planned `(wallet, gate)` output. That output
must be spent nowhere else on the chain. This transaction is the REGISTER the judge found in block G. With the
replay it must also be the one Heart the Core bore there (section 17); with `--no-replay` it is the gate's birth
for the record unverified.

**Anchor keys** (equality only: stdlib has no secp256k1). `vout[1]` must be `0x51 0x20 <32 bytes>`. Gates with
one planned label must have one program. Gates with different labels must have different programs.

## 8. Gate accounting (decision 11)

The judge re-derives the unit and gate states from the log alone, with the rules of ARV1 section 13 ("Gate
states") and section 16:

- **RUN_END DONE.** The gates that ended are OBSERVED. A deadline stop (`deadline_reached`, `gates_not_started`)
  leaves gates k … end NOT_STARTED `DEADLINE_REACHED`. The stop must be proved from the log: `RUN_START` has a
  `deadline`, every `GATE_START` is before `clock_ns`, and the line after the last `GATE_END` is at or after
  it. The log must hold exactly one `CLUSTER_TOOL` with `prefix` false over gates 0 … k − 1, exit 0, with
  output.
- **RUN_END FAILED, prefix OK** (the prefix rule). This needs phase `GATES`, `cluster_prefix` `OK`,
  `cluster_failed` false, `failed_gate` g, one `PREFIX_START`, and after it one prefix `CLUSTER_TOOL`. Both
  must name gates 0 … g − 1. Then those gates are OBSERVED (`PREFIX`), gate g is EXCLUDED, and the rest are
  NOT_STARTED.
- **Any other end** (no `RUN_END`, a prefix `FAILED` or `NOT_RUN`, a later phase, a cut log). Every started
  gate is EXCLUDED with the death cause, and the rest are NOT_STARTED.
- **A unit killed after RUN_END DONE** (ARV1 section 13, P3-5). Only the collection shows this: it says
  EXCLUDED. The judge then takes EXCLUDED with the collection's code.

With `--collection`, the collection's unit state, gate states and counts must equal the judge's. Otherwise the
judge refuses with `COLLECTION_DISAGREES`, exit 6. The collection is unauthenticated derived data.

**The 10% rule** (045b:546, :572; A Q2). Missing and EXCLUDED gates add up. More than a tenth of the run's gates
(more than 20 of 200) makes item 1 NOT_ESTABLISHED. J1 counts one run. J3 counts the whole registered N
(section 20).

## 9. Plan-vs-bytes fields (decision 4)

A judged gate whose bytes differ from the plan becomes EXCLUDED `JUDGE_PLAN_MISMATCH:<field>`. The first field
that fails names it, and the gate lists all its fields in `mismatches`. It counts under the 10% rule. It is a
driver defect, not NO-GO.

- **Gate fields:** `height`, `bidders` (the `BIDDERS` seat), `funding` (membership), `block_g`, `winner`,
  `register_shape`, `fee`, `d2_2_winner` (the gate row D2-2 was given), `anchor_key`, and with the replay
  (section 17) `replay_birth`, `replay_next_birth`, `replay_other_birth`.
- **Run fields** (they exclude every judged gate): `params`, `miner_policy`, `bidders_sha256`, `bidders_list`,
  `funding_layout`, `OWNER_SPLIT`, `ANCESTRY_ON_CHAIN` (section 7), `d2_2_inputs`, `d2_2_method`, `d2_2_truth`.

The run-field checks:

- `bidders_sha256` is the SHA-256 of the canonical `BIDDERS.bidders` and equals `RUN_START`'s.
- `d2_2_inputs`: the three documents in `CLUSTER_TOOL.inputs`, hashed as the converter writes them (sorted
  keys, indent 1, LF; ARV1 section 15), must be the ones D2-2's output names.
- `d2_2_method`: that method document must hold the method policy's values and the FAN_OUT txid as the one
  excluded txid.
- `d2_2_truth`: the truth must give each born txid its planned wallet and every wallet its owner.

**J1 rule (A accepted it on review of J1).** The expected lists depend on the whole gate sequence D2-2 judged. If any judged
gate is EXCLUDED here, the report and metric comparison is not evaluated
(`COMPARISON_NOT_EVALUATED:JUDGE_PLAN_MISMATCH`), and the outcome is NOT_ESTABLISHED. A plan mismatch therefore
never gives NO-GO and never gives GO.

## 10. Expected clusters and reports

Clusters are computed over the judged gates: 0 … N − 1, or the prefix or deadline gates (decision 12).

- **Ownership:** the gate's cluster is its planned winner's owner (`O<n>`).
- **Link-based, at gate level (decision 3):** the transitive closure of the planted on-chain links. The
  cluster id is `L<first gate>`.
  - ANCESTRY joins every gate won by an ancestry-flagged wallet of one owner. These gates spend that owner's
    one OWNER transaction. One flagged wallet that wins twice also joins its own two gates.
  - ANCHOR_KEY joins every gate that carries one Anchor label. So it joins all gates of the owner's reusing
    wallets and the base wallet's h = 0 gate.
- **Reports (CLV1 section 5):** R1 runs per cluster and R3 `UNKNOWN` runs. Item 1 has no unknown gate, so
  `UNKNOWN` is expected to be empty. A project gate breaks every run (reading (b)). Each run of length at
  least T gives one report, with `trigger_gate = max(first_gate + T − 1, the run's first gate won by C)`. The
  lists are sorted by (`trigger_gate`, `cluster`). T is 4 and 15.
- **Comparison key** (decision 3): (clustering, cluster id, threshold, trigger_gate).
  - A report that is expected but absent is `missing`. One that is present but not expected is `extra`.
  - A missing and an extra report with the same clustering, cluster and threshold pair up as `wrong_gate`,
    with `late` true when the reported gate is later.
  - `first_gate`, `last_gate`, `length`, `unknown_gates` and the list order are diagnostics only.
- **Repeat-winner** (045b 4.5): known and unknown gates, the top cluster's gates and the longest run. A project
  gate counts as its cluster's here (CLV1 :162-165), though it breaks every report run. The judge compares them
  with D2-2's `repeat_winner`. This is reported, not judged.
- **D2-2's own consistency** (CLV1 section 7). `incomplete` must be true exactly when `walk_truncated` is not
  empty. Every report's `unknown_gates` must be in `gates.unknown`. `gates.project` must be empty (item 1 has no
  project gate). Else the output is `D2_2_OUTPUT_MALFORMED:<part>`.

## 11. Metrics (CLV1 section 6; 045b:392-405)

All metrics are over the wallets that won a judged gate.

- **D:** D2-2's own `links`, lifted to wallets, closed.
- **P_L:** the planted groups, restricted to winning wallets, then closed. An ANCESTRY group is an owner's
  flagged winners. An ANCHOR_KEY group is the winners whose gates carry one label.
- **P_O:** same-owner pairs.

The judge reports `link_recall`, `link_precision`, `ownership_recall` and `unlinkable_share` as exact
fractions, and the missed and false pairs. D2-2's own `metrics` are compared as a diagnostic only.

**A 0/0 metric** (045b:400-405; A #258 6558883776 correction of decision 12). A fraction with denominator 0 is neither 1
nor 0. That metric alone is NOT_ESTABLISHED for the run (`METRIC_UNDEFINED:<metric>`). It excludes no gate.
The report comparison and the other metric are still evaluated. `comparison.metric_status` gives `MET`,
`BELOW_1` or `NOT_ESTABLISHED` for each of `link_recall` and `link_precision`.

- P_L empty makes recall 0/0. By the item-1 design (40 wallets, 10 owners) this is an input defect.
- D empty with P_L not empty makes recall 0 of |P_L|, which is below 1 and so NO-GO, and precision 0/0,
  which is NOT_ESTABLISHED. The outcome is NO_GO (section 12).

## 12. Outcome

1. **Run excluded** (decision 12 as corrected; CLV1 sections 5 and 6). Any of these makes every judged gate
   EXCLUDED with its code:
   - D2-2's `incomplete` is true (`D2_2_INCOMPLETE`);
   - D2-2 lists a gate as unknown control (`D2_2_UNKNOWN_GATES`; CLV1 section 3 :71-72 for its meaning, :146-148:
     a Class T campaign plants none, so one is a logging gap);
   - D2-2 gave an `UNKNOWN` report (`D2_2_UNKNOWN_REPORT`).
   Then the comparison is not evaluated, and item 1 is NOT_ESTABLISHED. A 0/0 metric does not exclude the run
   (section 11).
2. **NO_GO** only from an evaluated comparison. These conditions count:
   - a missing, extra or wrong-gate report;
   - a defined `link_recall` or `link_precision` below 1;
   - a D2-2 output that cannot be read as CLV1 section 7 (`D2_2_OUTPUT_MALFORMED:<part>`; its reports cannot be
     compared, so they are missing).
3. **NOT_ESTABLISHED** for any of these:
   - the 10% rule (`TEN_PERCENT_RULE`);
   - no judged gate (`NO_JUDGED_GATES`);
   - a run exclusion;
   - a comparison not evaluated;
   - a 0/0 `link_recall` or `link_precision` (`METRIC_UNDEFINED:<metric>`).
4. Otherwise **GO**.

NO_GO comes first, then NOT_ESTABLISHED, then GO. So a defect found on judged gates is NO_GO even when the
10% rule also holds (for example a prefix stop at g = 150 with a wrong report).

## 13. The record (`BITAGI_CT_ARDR_JUDGEMENT_V1`)

The record is one canonical JSON line. A 200-gate run's record is about 96 KB (95,777 bytes for the test file's
200-gate Core-shaped run). The judge workflow prints it and its `sha256sum` line in the job log and also uploads
the same bytes as the `ardr-judgements` artifact (section 18), so the log line is not the only copy.

| Key | Value |
|---|---|
| `schema`, `labels` | the schema; `CLASS_T`, `REGTEST`, `JUDGE_RECORD`, `J2_ITEM1_ONLY`, and `EXPLORATORY_NOT_A_VERDICT` outside CONFIRMATORY |
| `item`, `mode`, `evidence_status` | `ITEM1`; the judge's mode; the same. A CONFIRMATORY record needs a registration with `d2_2_tool_sha256` (section 3) and the replay: one without the replay exists only as `births` `NOT_REPLAYED_NO_JUDGED_GATE`, whose outcome is NOT_ESTABLISHED (`NO_JUDGED_GATES`) |
| `log_mode`, `log_evidence_status` | the raw log's line-1 values |
| `births` | `REPLAYED`; `NOT_REPLAYED_NO_JUDGED_GATE` (the replay was asked for and no gate is judged, so it did not run); `UNVERIFIED_NO_REPLAY` (`--no-replay`) |
| `replay` | null unless `REPLAYED`: `first_height` (H0), `last_height` (the tip), `rows`, `calls`, `poststate_sha256`, `birth_count`, `births` (the first 100 `{height, txid}`), `outside_judged_gates` (the first 100 births at a height that is no judged gate's G, `{height, born}`) |
| `judge` | `unit` `J2`, `tool_sha256` (this file's bytes) |
| `inputs` | the SHA-256 of the policy, method policy, raw log and collection; the raw log's bytes and lines; `prereg_045b` `{path, sha256}`; the raw log's `registration_sha256`; the method fields that took DRAFT values; `d2_2_tool_sha256`, the judged `CLUSTER_TOOL` line's `tool_sha256` (null without one); `d2_2_tool_registered_sha256` (CONFIRMATORY: the registration's `d2_2_tool_sha256`; else null); `d2_2_tool_at_run_commit_sha256` (the SHA-256 of `--d2-2-tool-at-commit`, the D2-2 file at the run's commit; null without it) |
| `thresholds` | the constant table: `name`, `item`, `value`, `cite` (`045b:<line>`) |
| `unit`, `params` | experiment, run, the policy's registered run count; `b`, `H0`, `gates_per_run`, `source` (`POLICY` or `DRAFT`) |
| `plan` | `plan_sha256`, the planted owner and m, base wallets, rung-0 fee, per wallet its draws and flags, per gate `wallet`, `source`, `draw`, `heart`, `anchor_label`, `funding` |
| `run_shape` | unit state, `RUN_END` status, phase, death cause, failed gate, prefix outcome, `prefix`, `deadline_reached`, `truncated`, judged gate count, chain tip, stale and rejected blocks, `funding_problems`, `run_mismatches` *2026-11-11 (045b :1090, section 29): and `collection_code`, the collection's code of the unit (null without a collection; shown only)* |
| `gates` | per gate `gate`, `state`, `code`, `observation_id`, planned `wallet`, `born_txid`, `height`, `next_birth` (the Core's next birth after block G; null without the replay), `mismatches` |
| `gate_counts` | `gates`, `observed`, `excluded`, `missing`, `missing_or_excluded`, `over_10_percent` |
| `expected` | link groups, link clusters, both report lists, both repeat-winner counts, planted pairs (or null without judged gates) |
| `comparison` | `evaluated`, `not_evaluated_reason`, `metrics`, `metric_status`, `reports` (`missing`, `extra`, `wrong_gate`, `field_differences`, `order_agrees`), `repeat_winner`, `diagnostics` |
| `driver_claims` | `count` and the first 100 disagreements (`event`, `seq`, `field`, `claimed`, `derived`) |
| `outcome` | `result` (`GO`, `NO_GO`, `NOT_ESTABLISHED`), `nogo`, `not_established` *2026-11-11 (045b :1090, section 29): and, beside it, `verdict`: `expected`, `observed`, `result` (`PASS`, `FAIL`, `INCONCLUSIVE`), `inconclusive_reason`* |

## 14. Refusal codes

| Code | Exit | When |
|---|---|---|
| `OPTIMIZED_PYTHON` | 6 | run under `python -O` |
| `PREREG_UNAVAILABLE`, `POLICY_UNAVAILABLE`, `METHOD_POLICY_UNAVAILABLE`, `REGISTRATION_UNAVAILABLE`, `COLLECTION_UNAVAILABLE`, `RAW_LOG_UNAVAILABLE` | 3 | the file cannot be opened |
| `PREREG_NOT_REGULAR`, `POLICY_NOT_REGULAR`, `METHOD_POLICY_NOT_REGULAR`, `REGISTRATION_NOT_REGULAR`, `COLLECTION_NOT_REGULAR`, `RAW_LOG_NOT_REGULAR` | 2 | a symlink or not a regular file (a FIFO included) |
| `PREREG_SIZE`, `POLICY_SIZE`, `METHOD_POLICY_SIZE`, `REGISTRATION_SIZE`, `COLLECTION_SIZE`, `RAW_LOG_SIZE` | 2 | over its bound (045b 4 MiB, policy files and registration 1 MiB, collection 64 MiB, raw log 256 MiB or 4,000,000 lines) |
| `POLICY_JSON`, `METHOD_POLICY_JSON`, `REGISTRATION_JSON`, `COLLECTION_JSON` | 2 | not one JSON object (or a duplicate key or a float) |
| `PREREG_CITATION` | 6 | a constant's phrase is not on its cited 045b line |
| `POLICY_SHAPE`, `POLICY_SEED`, `POLICY_ITEM1`, `POLICY_PARAMS`, `POLICY_METHOD_POLICY` | 2 | the policy's keys, seed, ITEM1 entry, params or `method_policy` are malformed |
| `POLICY_MINER_EXPERIMENT` | 2 | ITEM1's miner policy is not `ITEM1_WINNER_ONLY` (J3: POOL's is not `POOL_50_30_20`) |
| `POLICY_POOL` | 2 | J3: no POOL entry, or one with keys other than `miner_policy` and `params` |
| `POLICY_POOL_RUNS`, `POLICY_POOL_GATES` | 2 | J3, CONFIRMATORY: a POOL count other than 50 or `gates_per_run` other than 4 (045b :545) |
| `POLICY_ITEM1_RUNS` | 2 | J3 `experiment`, CONFIRMATORY: an ITEM1 count other than 1 (045b :546) |
| `POLICY_ITEM1_GATES` | 2 | CONFIRMATORY with `gates_per_run` other than 200 |
| `POLICY_ITEM2` | 2 | J4a: no ITEM2 entry, or one with keys other than `miner_policy`, `params` and `l0_seat` |
| `POLICY_ITEM2_GATES`, `POLICY_ITEM2_H0` | 2 | J4a: ITEM2 `gates_per_run` other than 1; an H0 below 107 (045b :1054, ARV1 :1587), or (CONFIRMATORY, or a policy with a non-PENDING `l0_seat`) other than 1000 (045b :1054) |
| `POLICY_ITEM2_RUNS` | 2 | J4a `experiment`, CONFIRMATORY: an ITEM2 count other than 200 (045b :546) |
| `POLICY_L0_SEAT`, `POLICY_L0_SEAT_PRIVATE` | 2 | J4a: `experiments.ITEM2.l0_seat` not ARV1 section 26's shape (each value PENDING or of its kind, `seat` 0-4); seat 0. J5: `experiments.ITEM4_<S>.l0_seat` not the item-4 shape (no `seat` key) |
| `POLICY_L0_VALUES` | 2 | J4a, CONFIRMATORY: `l0_seat` with a seat other than 1, a `p0_rule` other than `CEIL_2_5_B` or `max_gate_attempts` other than 24 (045b :1053, :1219); J5: an item-4 key also with an `exact_height_miss` other than `CONTINUE_WITHIN_LIMITS` (045b :1068) *2026-11-10 (A, J4a verification round): also an `exact_height_miss` other than `CONTINUE_WITHIN_LIMITS` or a `budget_sha256` other than the frozen record's `7d0a7a35…` (045b :1053's dated line, section 14.21 :1898-1901; the driver refuses the STOP_CAMPAIGN twin in CONFIRMATORY)* *2026-11-10 (A, J5 after the freeze): an item-4 key too: `budget_sha256` other than `7d0a7a35…` (045b section 14.21 :1898, the Class T record of the ARDR L0 seat; the driver refuses another, ARV1 section 26 :2557-2558)* *2026-11-12 (A, FD-CT-133, section 30): the `p0_rule` wanted is `MAX_P0_TWO_RUNGS`; `CEIL_2_5_B` is refused* |
| `L0_P0_NO_TWO_RUNGS` | 2 | *2026-11-12 (section 30)*: no p_0 from 2b has a two-rung :537 ladder at i = 0 (b 1-3) |
| `L0_P0_INPUT` | 2 | *2026-11-12 (section 30)*: the b given to `l0_p0` is not a positive int |
| `L0_FREEZE_PENDING` | 3 | J4a, CONFIRMATORY: an ITEM2 (J5: or item-4) policy without `l0_seat` |
| `POLICY_PENDING`, `SEED_PENDING`, `POLICY_PARAMS_PENDING` | 3 | a PENDING value (any in CONFIRMATORY; the seed or params in any mode) |
| `POLICY_COUNT_UNSET`, `POLICY_PARAMS_UNSET`, `METHOD_POLICY_NOT_DECLARED` | 3 | CONFIRMATORY without the experiment's count or params (ITEM1, and J3's POOL in `pool` and `experiment`), or without ITEM1's method policy *2026-11-10 (A, J5b; A's Q3 on #719): J4a's item-2 and J5's item-4 commands (`item2`, `item4`, `experiment`) also refuse a CONFIRMATORY policy that is not complete, as the driver's `load_policy` does: an experiment without a count (the driver's POLICY_COUNT_UNSET, exit 3) or a count that is not an int 1 .. 2^32-1 (the driver's `check_policy_shape` POLICY_COUNTS, exit 2: the judge has no such code and keeps its own for that count, POLICY_COUNT_UNSET, exit 3); 2026-11-10 (J5b verification round): so is a `counts` key that is not an experiment, POLICY_COUNTS's other half (POLICY_COUNT_UNSET, exit 3). A PENDING value anywhere stays POLICY_PENDING (exit 3, `policy_head`).* |
| `METHOD_POLICY_SHAPE`, `METHOD_POLICY_BOUND` | 2 | the method policy's keys or a value out of ARV1 section 15's bounds |
| `METHOD_POLICY_SHA256` | 6 | the method policy is not the file the policy names |
| `METHOD_POLICY_PENDING` | 3 | a PENDING method value in CONFIRMATORY |
| `METHOD_THRESHOLDS` | 2 | the thresholds are not 045b's 4 and 15 |
| `EXPLORATORY_REGISTRATION` | 2 | `--registration` in EXPLORATORY |
| `REGISTRATION_MISSING` | 3 | CONFIRMATORY without `--registration` |
| `COLLECTION_REQUIRED` | 3 | CONFIRMATORY without `--collection` (J2) |
| `D2_2_TOOL_NOT_REGISTERED` | 3 | CONFIRMATORY: the registration has no `d2_2_tool_sha256` (section 3) |
| `REGISTRATION_D2_2_TOOL` | 2 | CONFIRMATORY: the registration's `d2_2_tool_sha256` is not 64 lowercase hex |
| `D2_2_TOOL_SHA256` | 6 | CONFIRMATORY: a `CLUSTER_TOOL` line's `tool_sha256` is not the registered one |
| `D2_2_TOOL_NOT_AT_RUN_COMMIT` | 6 | with `--d2-2-tool-at-commit`: a `CLUSTER_TOOL` line's `tool_sha256` is not the SHA-256 of the D2-2 file at the run's commit |
| `D2_2_FILE_UNAVAILABLE` | 3 | the `--d2-2-tool-at-commit` file cannot be opened |
| `D2_2_FILE_NOT_REGULAR`, `D2_2_FILE_SIZE` | 2 | that file is not a regular file, or is over 4 MiB |
| `REGISTRATION_SHAPE` | 2 | no non-empty `ardr_policy_sha256` list *2026-11-12 (section 30): or an `experiments` key that is not a non-empty list of strings* |
| `EXPERIMENT_NOT_REGISTERED` | 6 | *2026-11-12 (A, FD-CT-133, section 30)*: CONFIRMATORY, the registration names its `experiments` and not the one judged |
| `POLICY_NOT_REGISTERED`, `METHOD_POLICY_NOT_REGISTERED` | 6 | the registration does not list that SHA-256 |
| `RAW_LOG_NOT_CONFIRMATORY` | 6 | CONFIRMATORY with a log that is not |
| `REGISTRATION_BYTES_CHANGED` | 6 | the log's `registration_sha256` is not the registration file's |
| `LOG_MODE_MISMATCH` | 6 | EXPLORATORY with a log whose line 1 is CONFIRMATORY |
| `REPLAY_NOT_BUILT` | 3 | CONFIRMATORY with `--no-replay`, after every binding check passed |
| `REPLAY_OPTIONS` | 2 | `--no-replay` and `--replay-bin` together |
| `REPLAY_REQUEST_SIZE` | 2 | one worker request over 12 MiB (a block and its prestate) |
| `REPLAY_REFUSED` | 2 | the worker refused the bytes (its code goes to stderr; section 17) |
| `REPLAY_WORKER_FAILED`, `REPLAY_WORKER_TIMEOUT` | 3 | the worker could not start, ended non-zero, ran past 1,800 s or wrote no answer *2026-11-11 (045b :1090, section 29): `REPLAY_WORKER_TIMEOUT`: the worker ran past 1,800 s, split from `REPLAY_WORKER_FAILED`, which keeps the other three* |
| `REPLAY_ANSWER` | 4 | the worker's answer does not follow section 17 |
| `RAW_LOG_POLICY_SHA256` | 6 | the log names another policy |
| `RAW_LOG_LINE_SIZE` | 2 | a line over 32 MiB |
| `RAW_LOG_JSON` | 2 | a line before the last that does not parse (or the only line) |
| `RAW_LOG_EMPTY` | 2 | no line |
| `RAW_LOG_ENVELOPE`, `RAW_LOG_SCHEMA`, `RAW_LOG_SEQ`, `RAW_LOG_MODE` | 2 | a missing envelope key or another envelope than line 1; another schema; a `seq` gap or repeat; an unknown mode |
| `RAW_LOG_START`, `RAW_LOG_DUPLICATE_EVENT`, `RAW_LOG_AFTER_END`, `RAW_LOG_EVENT` | 2 | line 1 not `RUN_START`; a second `RUN_START` or `BIDDERS`; any line after `RUN_END`, parsed or not; an event outside item 1's (J3, a pool log: also `CLUSTER_TOOL` or `PREFIX_START`) |
| `RAW_LOG_UNIT`, `RAW_LOG_EXPERIMENT` | 2 | a malformed `unit` or another run; another experiment (`item1` reads ITEM1 logs, `pool` POOL logs) |
| `RAW_LOG_BLOCK`, `RAW_LOG_BLOCK_DUPLICATE`, `BLOCK_CHAIN` | 2 | block bytes or `BLOCK` fields that do not parse or have the wrong type (J3, a pool log: also a `BLOCK` without a string `producer`); one accepted block twice; no chain from the last block to height 1 |
| `RAW_LOG_FUNDING` | 2 | funding bytes or `FUNDING_SENT` fields (`outputs` included) that do not parse or have the wrong type |
| `RAW_LOG_GATES` | 2 | gate lines not in order or with a wrongly typed field (J3, a pool log: a `GATE_END` without `producer_tags`, a list of strings), a `RUN_END` with another status, phase or field type or outside section 16's table, or a deadline stop the log does not prove |
| `RAW_LOG_CLUSTER` | 2 | a DONE run without its one `CLUSTER_TOOL`, a wrongly typed field (a `tool_sha256` that is not 64 hex included), or output bytes that do not match its SHA-256 and length |
| `RAW_LOG_TYPES` | 2 | a wrongly typed or missing field, or a float, in `RUN_START`, `BIDDERS`, `CORE_REPLAY` or `GENERATED` (J3, a pool log: also `DRAW`'s `label`, `value`, `k`, `producer`) |
| `RAW_LOG_ITEM2` | 2 | J4a: a wrongly typed or missing field of an item-2 line (`SCHEDULE`, `RELEASE`, `PUBLIC_SENT`, `PRIVATE_HANDOFF`, `PRIVATE_REPLACE`, `RELEASE_MEMPOOLS`, `REPLACED_RUNG_MISSING`, `G_TIMING`, `TEMPLATE`, an EXCLUDED `GATE_END` or `RUN_END`), handed-off bytes that do not parse, a `RELEASE` seat other than S0-S4, a `schedule_source` other than the two, or `RUN_END` EXCLUDED without its `GATE_END` |
| `RAW_LOG_L0` | 2 | J4a: a wrongly typed or missing field of an L0 line (ARV1 :1969-1983) or of an L0 `RELEASE`; L0 lines in a run without the L0 seat; an L0 `RELEASE` of another seat (or a seat's release not by L0); an EXPLORATORY seat other than 1-4; the L0 seat with H0 other than 1000 (045b :1054; ARV1 section 22 `ITEM2_L0_H0`) |
| `RAW_LOG_L0_SEAT` | 6 | J4a, CONFIRMATORY: the log's `RUN_START.l0_seat` is not the policy's (`PENDING_FREEZE` included). 2026-11-10 (B-FZ-a): also an EXPLORATORY `POLICY_VALUE` log whose seat is not the policy key's |
| `RAW_LOG_L0_SOURCE` | 6 | J4a: `l0_seat_source` or `budget_source` is not the mode's (#667 P3-1: `REGISTERED_POLICY` only in CONFIRMATORY). 2026-11-10 (B-FZ-a #756): outside CONFIRMATORY `POLICY_VALUE` is taken only on both lines, with `budget_sha256` and no `budget_draft`, from a policy whose `l0_seat` has no PENDING value (section 21). *2026-11-10 (A, J4a verification round): and only from a policy `--policy-l0-seat` takes (complete: no PENDING value anywhere, every experiment counted; the key's `p0_rule` `CEIL_2_5_B`, `max_gate_attempts` 24, `budget_sha256` the product's record for its `exact_height_miss`, ARV1 section 26 :2557-2558). `L0_BUDGET.policy_compare` is `EQUAL` with `policy_budget_sha256` in a run on the policy's values, else `NO_POLICY_VALUE` (or absent, an EXPLORATORY log from before B-FZ-a) without it (ARV1 :2570-2571)* *2026-11-10 (A, Desktop P3 on #669): complete also means every count is an int 1 .. 2^32-1, as the producer's shape check (`check_policy_shape`, POLICY_COUNTS) requires; a null, 0 or non-integer count is not complete (`RAW_LOG_L0_SOURCE`).* *2026-11-10 (A, J5b verification round): nor is a policy with a `counts` key that is not an experiment, the shape check's other half (`check_policy_shape` POLICY_COUNTS, every mode).* *2026-11-10 (A, J5): an item-4 RUN_START has no `l0_seat_source`, so an item-4 log says `POLICY_VALUE` on `L0_LAUNCH_START.budget_source` alone, with the same policy-side conditions (section 24)* |
| `RAW_LOG_SCHEDULE_OVERRIDE` | 6 | J4a, CONFIRMATORY: a log with `schedule_source` `DRAFT_OVERRIDE` |
| `L0_BUDGET_SHA256` | 6 | J4a, CONFIRMATORY: a logged `budget_sha256` (L0_LAUNCH_START, L0_SET_CHARGED, L0_BUDGET) is not the policy's. 2026-11-10 (B-FZ-a): the same in an EXPLORATORY `POLICY_VALUE` log. *2026-11-10 (A, J4a verification round): `L0_BUDGET.policy_budget_sha256` is one of the logged digests* |
| `POLICY_ITEM4` | 2 | J5: no entry for the log's item-4 experiment, or one with keys other than `miner_policy`, `params` and `l0_seat` |
| `POLICY_ITEM4_GATES`, `POLICY_ITEM4_H0` | 2 | J5: `gates_per_run` other than 1; H0 below 107, or (CONFIRMATORY, or a policy with a non-PENDING `l0_seat`) other than 1000 (045b :1054) |
| `POLICY_ITEM4_SELF_FEE` | 2 | J5: ITEM4_SELF_DEALING params whose project rung 0 (⌈2.5 b⌉ at 213 vB) pays 600 sat or less (b < 1127; 045b :1065) *2026-11-12 (section 30): the project rung 0 is FD-CT-133's p_0 at 213 vB, so b < 1058* |
| `POLICY_ITEM4_RUNS` | 2 | J5 `experiment`, CONFIRMATORY: an item-4 count other than 50 (045b :524) |
| `RAW_LOG_ITEM4` | 2 | J5: a wrongly typed or missing field of an item-4 line (section 24's table), handed-off bytes that do not parse, a `RELEASE` seat outside the plan's, `RUN_START.scenario` not the log's experiment or `project_seat` neither `L0_PROJECT` nor `PROJECT_STANDIN`, a scenario's own line in another scenario's log, `REPLACED_RUNG_MISSING` in an L0 log, an `ITEM4_L0_OBSERVE` not standing between its turn's `L0_TURN` and the next, or `RUN_END` EXCLUDED without its `GATE_END` |
| `RAW_LOG_ITEM4_LABELS` | 2 | J5: a turn the driver accepted (its `ITEM4_L0_OBSERVE` is there) whose raw `labels` or `flags` line is not one well-formed entry per rung of the set (a turn the driver did not accept with such a line is judged a mislabel, section 24) |
| `RAW_LOG_ITEM4_STANDIN` | 6 | J5, CONFIRMATORY: a log whose project seat is the stand-in (ARV1 :2076-2077; A's Q7) |
| `RAW_LOG_RELEASE_MARK` | 6 | J5: a release step (an `ITEM4_L0_RELEASE` line or a `set_release` turn) outside ITEM4_REORG; CONFIRMATORY ITEM4_REORG: a mark present (an `ITEM4_L0_OBSERVE.procedure.mark`, the planned release turn's `ITEM4_L0_OBSERVE`, an `ITEM4_L0_RELEASE.step`) that is not `RELEASE_REORG67_TEST_ONLY`, a run past its release turn without the release turn's mark, or past the STALE turn's checks (DONE or an `ITEM4_L0_LABEL_LINE`) without exactly one such step (045b :1069; A's Q10 and the J5 check's P2-1) |
| `ITEM4_RECORD_DUPLICATE` | 2 | J5 `item4-outcome`: two records of one sub-scenario |
| `COLLECTION_RUN` | 6 | workflow `unpack` (J3 check P3-4): the collection's own `run` is not this dispatch (run id, attempt 1, the run's head) |
| `COLLECTION_SHAPE`, `COLLECTION_UNIT` | 2 | not a V2 collection (for `unpack`, also a unit's `slice_record_sha256` that is neither null nor 64 lowercase hex, #655; for J3's `experiment`, any field section 20 reads: the experiment, the run id, the registration hash, each unit's key, state, code and gate rows, a unit listed twice; for J5, an item-4 unit without `exit`, or with one neither null nor an integer); not exactly one entry for this unit *2026-11-11 (finding #788, section 28): for J3's `experiment`, also an ITEM2 unit without `exit`, or with one neither null nor an integer.* |
| `COLLECTION_DISAGREES` | 6 | its unit state, gate states or counts are not the judge's |
| `COLLECTION_MODE` | 6 | J3 `experiment`: a collection of another mode than the judge's |
| `COLLECTION_DUPLICATE`, `RUN_DECLARED` | 2 | J3 `experiment`: two collections of one dispatch run *2026-11-10 (J4b): or one run given twice, by collection or `--undeclared-run`; `RUN_DECLARED`: an `--undeclared-run` whose saved listing names a declaration, collection or slice artifact (such a run is given by its collection; section 27)* |
| `COLLECTION_REGISTRATION` | 6 | J3 `experiment`: a collection's `registration_sha256` is not the registration file's (null outside CONFIRMATORY) |
| `RECORD_UNAVAILABLE` | 3 | J3 `experiment`: a `--record` file cannot be opened |
| `RECORD_NOT_REGULAR`, `RECORD_SIZE`, `RECORD_JSON` | 2 | J3 `experiment`: that file is not a regular file, is over 16 MiB, or is not one JSON object |
| `RECORD_SHAPE` | 2 | J3 `experiment`: not this experiment's per-unit judgement record (unit, gate rows, a pool gate's producer, outcome); J5 `item4-outcome`: not an item-4 experiment record, or one whose result disagrees with its lists (section 25) *2026-11-11 (045b :1090, section 29): J3 `experiment` (every experiment): also a per-unit record of this judge file without `verdict`, or whose `verdict.result` is not the mapping of its `outcome.result`; it is the last record check, so a record another judge file made stays `RECORD_TOOL`* |
| `RECORD_TOOL` | 6 | J3 `experiment` (J5: and `item4-outcome`): a record another judge file made (`judge.tool_sha256`) |
| `RECORD_BINDING` | 6 | J3 `experiment`: a record of another mode, policy or registration, or not made with the collection of the dispatch that started its unit; J5 `item4-outcome`: records of another mode or 045b file, or of two policies or registrations |
| `RECORD_DUPLICATE` | 2 | J3 `experiment`: two records of one unit |
| `RECORD_DISAGREES` | 6 | J3 `experiment`: a record's gate states do not follow its collection's (section 20) |
| `RECORD_MISSING` | 3 | J3 `experiment`: a started unit with an OBSERVED gate in its collection and no record; J5: also an item-4 unit with no record whose code is a driver label-check code or whose `exit` is not null (section 25) *2026-11-11 (finding #788, section 28): also an ITEM2 unit with no record whose `exit` is not null* |
| `UNIT_DISPATCHED_TWICE` | 6 | J3 `experiment`: one unit started (not BEFORE_START) in two listed dispatches (045b :577-580) |
| `UNIT_NOT_REGISTERED` | 6 | J3 `experiment`: a started unit at or above the registered N (045b :571) |
| `REGISTERED_N_SIZE` | 2 | J3 `experiment`: the registered N times the gates per run is above 100,000 |
| `RUN_LIST_REQUIRED` | 3 | J3 `experiment`: CONFIRMATORY without `--runs-listing`, `--main-history` and `--listed-after`; a listing without `--main-history`; `--listed-after` or `--main-history` without a listing *2026-11-10 (J4b): also `--undeclared-run` without `--runs-listing` and `--main-history`, and `run-query` in CONFIRMATORY without `--listed-after`* |
| `RUN_LIST_BOUND` | 2 | J3 `experiment`: `--listed-after` is not an ISO 8601 time with its offset *2026-11-10 (J4b): also `run-query`'s, or one with no UTC date two days before it* |
| `RUN_LIST_SHAPE` | 2 | J3 `run-pages`, `experiment`: page 1's `total_count` is not a count (a later page's that differs is `RUN_LIST_CHANGED`), or a run's `id`, `display_title`, `status`, `event`, `path`, `head_branch`, `head_sha` or `created_at` is missing or of another type |
| `RUN_LIST_CAPPED` | 3 | J3 `run-pages`, `experiment`: the listing says 1,000 runs or more (GitHub's cap for a filtered listing) *2026-11-10 (J4b): a CONFIRMATORY listing holds only the runs created from two days before the bound (`run-query`, section 27)* |
| `RUN_LIST_CHANGED` | 3 | J3 `experiment`: the pages disagree on the total, a page but the last is not full, or a run is listed twice (the listing moved while it was read) |
| `RUN_LIST_DISAGREES` | 6 | J3 `experiment`: a listed run is not in the listing as a completed run of the experiment on the judge's main history, or (with `--listed-after`) was created before the bound |
| `RUN_LIST_TITLE` | 6 | J3 `experiment`: a `workflow_dispatch` run on main of `claude-track-ardr.yml` whose name is not one of the campaign's (`ardr CONFIRMATORY\|EXPLORATORY <experiment>`, `ardr RECOLLECT <experiment> …`, a known experiment) |
| `RUN_LIST_INCOMPLETE` | 6 | J3 `experiment`: a run of the experiment created at or after the bound (completed or not) is not listed (section 20; its ids go to stderr) |
| `DRAW_SEED`, `DRAW_LABEL`, `DRAW_RANGE`, `DRAW_EXHAUSTED` | 4 | internal: a draw called out of range |
| `RUN_IDS` | 2 | workflow `run-ids` (and `artifacts`, `unpack`): not 1 to 20 distinct run ids of digits without a leading zero; J3 `experiment`: more than 20 collections *2026-11-10 (J4b): more than 20 collections and `--undeclared-run` runs together* |
| `FETCHED_UNAVAILABLE` | 3 | workflow: a saved API answer (`run.json`, `artifacts.json`, J3's `runs-<page>.json`) or a zip's JSON member cannot be opened |
| `FETCHED_NOT_REGULAR`, `FETCHED_SIZE`, `FETCHED_JSON` | 2 | workflow: that file is not a regular file, is over 64 MiB, or is not one JSON object |
| `RUN_NOT_JUDGEABLE` | 6 | workflow: the run is not a completed first-attempt `workflow_dispatch` run of `claude-track-ardr.yml` on main named `ardr <mode> <experiment>` (ITEM1 by default; J3: `--experiment`), with a 40-hex head *2026-11-10 (J4b): E is also ITEM2 or an item-4 name; a run that declared nothing may be a later attempt in CONFIRMATORY only (section 27)* |
| `RUN_NOT_ON_MAIN_HISTORY` | 6 | workflow: the run's head is not on the first-parent history of the judge's own commit (section 18) |
| `MAIN_HISTORY_UNAVAILABLE` | 3 | workflow: the `--main-history` file cannot be opened |
| `MAIN_HISTORY_NOT_REGULAR`, `MAIN_HISTORY_SIZE`, `MAIN_HISTORY_SHAPE` | 2 | workflow: that file is not a regular file, is over 64 MiB, or is not one 40-hex commit per LF-terminated line |
| `ARTIFACT_LISTING`, `RUN_JOBS_LISTING` | 3 | workflow: the listing is not one page of fewer than 100, or names an artifact of another run, an expired one, a malformed digest, or a needed name twice *2026-11-10 (J4b): `RUN_JOBS_LISTING`: the attempt-1 jobs listing (`jobs.json`) of a run that declared nothing is not one page of every job (`total_count`, at most 100), each of this run's attempt 1, each name once, with its steps (section 27)* |
| `RUN_COLLECTION_MISSING` | 3 | workflow: no `ardr-declaration` or no `ardr-collection` (a recollected run is not read yet, section 15) *2026-11-10 (J4b): a run with no declaration, collection or slice artifact is accepted only when its attempt-1 jobs listing shows the plan job failed or is not listed and no other job ran a step; else this code (section 27)* |
| `ARTIFACT_MISSING` | 3 | workflow: a needed zip was not downloaded |
| `ARTIFACT_DIGEST` | 6 | workflow: a zip's SHA-256 is not the `sha256:` digest the listing gives it |
| `ARTIFACT_ZIP` | 2 | workflow: a zip that does not open, holds another member or a member twice, or is over its bound |
| `RUN_DECLARATION` | 6 | workflow: the declaration is not this run's V2 declaration of the experiment (ITEM1 by default) in this mode at the run's head, or (ITEM1) has no method policy in CONFIRMATORY, or (POOL) names one *2026-11-10 (J4b): ITEM2 and the item-4 experiments name none, as POOL* |
| `OUTPUT_EXISTS` | 3 | workflow: `unpack --out` exists |
| `SLICE_RECORD_SHA256` | 6 | workflow: a slice record is not the one the collection's `slice_record_sha256` names, or names other units |
| `RAW_LOG_MISSING` | 3 | workflow: a raw log the slice record names is not in the slice zip |
| `RAW_LOG_SHA256` | 6 | workflow: a raw log's SHA-256 is not the slice record's `raw_log_sha256` |

## 15. What J1, J2 and J3 do and do not do

- **J2 (done here):** A's own replay harness (section 17: the product decoder and `apply_block_transition`). It
  gives the born Hearts, `next_birth` and so the gate heights, and lifts J1's CONFIRMATORY refusal when the
  replay runs. In CONFIRMATORY it requires `--collection` and binds every `CLUSTER_TOOL` line's `tool_sha256` to
  the registration's `d2_2_tool_sha256` (A's decision, section 3); in the workflow, in any mode, also to the D2-2
  file at the run's commit. J2 also adds the main-only judge workflow that prints the record and its SHA-256
  (section 18).
- **Later, an A ask to B:** run the judge (EXPLORATORY) on the campaign's ITEM1 PR smoke. It changes B's
  `claude-track-ardr.yml`, so J2 leaves it out (agreed with A).
- **J3 (done here):** the pool run (section 19: the judge's own tag reader, block G read from the bytes, the
  producer draw) and the experiment's judgement (section 20: the 10% rule over the registered N across the listed
  dispatches, and the pool's Herfindahl index). The slice records' `raw_log_sha256` binds each log to its
  collection (`unpack`, section 18).
- **J3 check, fix round (A's decisions on the non-author check of `e78b6157`, 2026-11-02):** the run list is
  checked against the workflow's own dispatch listing (`RUN_LIST_INCOMPLETE`, section 20), and `unpack` binds the
  collection to its run (`COLLECTION_RUN`).
- **J3 re-check, fix round (A's decisions on the re-check of `3bb6724e`, 2026-11-02):** the CONFIRMATORY bound is
  anchored on the first commit that introduced the registration's bytes and binds the listed runs too (section 20);
  the run names are checked (`RUN_LIST_TITLE`); the workflow refuses a re-run attempt.
- **Not in J3:** a `RECOLLECT` run's recollection (`RUN_COLLECTION_MISSING` still refuses a run without a
  collection; it fails closed, A's decision). A dispatch of the experiment after the bound with no declaration or
  no collection keeps failing closed (A's decision P3-2 on the re-check, section 16). *2026-11-10 (J4b): a dispatch that declared nothing is accepted on its attempt-1 jobs listing (section 27); RECOLLECT still fails closed.*
- **J4a (done here):** item 2 with the L0 seat (section 21) and the item-2 experiment with the section 4.5 rows
  (section 22), A's J4a decisions (section 23).
- **J4b:** the judge workflow's ITEM2 wiring (the `experiment` input, `unpack` and `RUN_DECLARATION` for ITEM2,
  sections 18 and 20); collection-less dispatches accepted only with the attempt-1 jobs listing (section 16, P3-2);
  `created>=<bound>` in the CONFIRMATORY listing (section 16, P3-8); RECOLLECT (section 16, Q6); A's POOL funding
  decision (section 16, Q8); the :501 NO-GO, which needs `replaces_in_mempool` on `L0_RUNG_TEST` (not logged yet);
  the minimum transition list (045b :1279) once A writes it (J4a records the per-run facts it needs). *2026-11-10 (A): written; 045b :1279's dated line names `plans/CT-P5-001_INVENTORY_EN.md` section 2.* *2026-11-10 (A, J5b): item 4's gate is built in J5b (sections 24 and 25); the list binds no item-2 run (the inventory's scope rule), so none is J4b's.* *2026-11-10 (J4b, section 27): built: the ITEM2 wiring and, by the same generalization, the item-4 sub-scenarios' (the `experiment` input, `unpack` and `RUN_DECLARATION`, the per-unit command); P3-2 (`unpack` and `experiment --undeclared-run` on the attempt-1 jobs listing); P3-8 (`run-query`'s `created` filter). Left as they are: RECOLLECT (Q6, fails closed) and POOL's funding (Q8, reported; no real EXPLORATORY POOL log has shown its structural problems empty). Not built: the :501 NO-GO, which needs an L0 log change before the registration pins the code (A's decision; section 27).* *2026-11-10 (J4c, section 28): the :501 NO-GO is built.*
- **J5 (done here):** item 4 (sections 24 and 25), A's J5 decisions (section 26).
- **Not in J5:** the judge workflow's ITEM4 wiring (`unpack`, `RUN_DECLARATION`, the `experiment` input), which rides
  on J4b's generalization (A's Q16); the minimum transition list's gate (045b :1279): J5 records the transitions each
  run reaches (A's Q13); a control-row log (A's Q8: its 145 turns are `l0_turns`, no pairing); E7 (045b :1066). *2026-11-10 (A, J5 after the freeze): 045b :1279's dated line (frozen) reads its "J4 item" as each experiment's judge stage, item 4 in J5, and names the list (`plans/CT-P5-001_INVENTORY_EN.md` section 2, TR-1 to TR-6 for item 4). That gate is not built here; it waits on A's decision, and J5 still reports the transitions each run reaches.* *2026-11-10 (A, J5b; A's Q1 on #719): the gate is in J5b, not "not in J5": each run reports the listed transitions it reaches (`min_transitions`, section 24) and the item-4 experiment makes a sub-scenario with one not reached NOT_ESTABLISHED, `TRANSITION_NOT_REACHED` (section 25).* *2026-11-10 (J4b): the ITEM4 wiring is built in J4b (section 27); `item4-outcome` stays a separate call over the four sub-scenarios' experiment records.*
- **J6:** item 3.
- Neither J1 nor J2 checks proof of work: the product decoder does not, and regtest work is trivial. The 144-block
  birth spacing is checked through the Core's `next_birth` (section 17).
- J2 replays only the final chain. An item-4 reorg run's replaced branch is replayed by J5 (sections 17 and 24).

## 16. Review decisions and a driver disagreement since fixed

A decided these points on review of J1:

- **The J1 rule in section 9** is kept. A plan mismatch makes the comparison not evaluated.
- **The outcome order in section 12** is kept. A NO-GO found on judged gates stands even when the 10% rule
  holds.
- **A 0/0 metric** is metric-level, not a run exclusion (045b:400-405; A #258 6558883776 correction of decision 12;
  section 11).

- **Round 2 of the review** added: one OWNER transaction per owner and ANCESTRY read from the chain (section 7);
  any line after `RUN_END` refused and a CONFIRMATORY log refused in EXPLORATORY mode (sections 3 and 4); strict
  field types; D2-2's own consistency and `D2_2_UNKNOWN_GATES` (sections 10 and 12); the constants read from the
  table (section 4).

**A's decisions on the J3 non-author check** (of `e78b6157`, 2026-11-02):

- **POOL's outcome order (Q1).** When the 10% rule holds and the index is above 1/2, the pool experiment is
  NOT_ESTABLISHED, not NO_GO (section 20). Reason: 045b :571-574 applies the 10% rule to every row; the index is a
  statistic of the gates judged, which more than 10% missing can bias either way; item 1's NO-GOs are deterministic
  defects found on judged gates, so section 12 keeps NO_GO first there; both outcomes are non-GO.
- **The gate is POOL's exclusion unit (Q2, decision 6).** `POOL_EXCLUSION_UNIT` cites 045b :546 for now, whose text
  defines the pool run ("a run of 4 gates"). The gate unit becomes a 045b freeze line in A's freeze PR. For POOL,
  decision 6 supersedes ARDR_RUN_V1 :176-177 ("run for item 4 and the pool run"); B corrects ARV1 (this judge does not
  edit it).
- **A unit started twice (Q4).** `UNIT_DISPATCHED_TWICE` stays a refusal. If it ever fires, the fallback is to count
  that unit's gates EXCLUDED (045b :579-580), never to pick one dispatch's observation.
- **Decision 4 for POOL's funding (Q8).** The pool run's funding layout is reported (`run_shape.funding_problems`),
  not an exclusion, until a real EXPLORATORY POOL log shows its structural `funding_problems` empty; then A decides
  in J4. *2026-11-10 (J4b): no real EXPLORATORY POOL log has shown that yet; the layout stays reported (section 27).*
- **RECOLLECT (Q6)** is not in J3 and fails closed; Q3 (tag precedence) and Q7 (EXPLORATORY N) stay as built. *2026-11-10 (J4b): unchanged, still not read (section 27).*
- **Non-canonical varints (P3-5, note only).** The judge's coinbase reader refuses a non-canonical varint where the
  collector's reader takes it, so a pool block with one gives `COLLECTION_DISAGREES` or `RAW_LOG_BLOCK` (fails
  closed).

**A's decisions on the J3 re-check** (of `3bb6724e`, 2026-11-02):

- **The CONFIRMATORY bound (P2-A).** The bound is the committer time of the first commit, on the judge's history,
  that introduced the registration's exact bytes (section 20); a listed run created before it is refused. A
  committer date is not authenticated: the registration's own timestamp receipt is the real time anchor, out of
  J3's scope (a 045b line).
- **Dispatches that hold no collection (P3-2).** A CONFIRMATORY dispatch of the experiment created after the bound
  with no declaration or no collection (one the concurrency group replaced before it started, one refused at its
  plan, one cancelled, or a re-run attempt) keeps failing closed: left out it is `RUN_LIST_INCOMPLETE`, listed it is
  `RUN_COLLECTION_MISSING` or `RUN_NOT_JUDGEABLE`. J4 will accept such a run only when its attempt-1 jobs listing
  shows the plan failed and no slice job ran a step (B's `prior_declaration` rule, ARV1 section 13 D-1). The same
  holds for EXPLORATORY dispatches after the first listed run. *2026-11-10 (J4b, section 27): built, for CONFIRMATORY and EXPLORATORY: a listed run with no declaration, collection or slice artifact counts as listed (`unpack`, `experiment --undeclared-run`) when its attempt-1 jobs listing shows the plan job failed or is not listed and no other job ran a step (B's rule read over every job, not only the slice jobs); a later attempt in CONFIRMATORY only, whose plan refuses every attempt but the first.*
- **The listing's cap (P3-8, note only).** The 1,000-run cap counts every `claude-track-ardr.yml` dispatch on main,
  of any experiment. A CONFIRMATORY listing could add `created=>=<bound>` to the query later (J4); no code now. *2026-11-10 (J4b, section 27): built: the CONFIRMATORY listing asks only for runs created on or after the UTC date two days before the bound (`run-query`); the judge applies the exact bound as before.*

**The `FUNDING_SENT.outputs` disagreement (finding #647) is gone** (2026-11-01, B's PR #649, main `a50869fc`):
the three writers now list `[wallet, gate]` in vout order (ARV1 section 12). The test
`Refusals.test_funding_outputs_not_in_output_order` stays as a guard against the sorted shape.

## 17. The Core replay (J2)

A #258 6557890079 decision 1: the judge replays with its own harness, so a change to B's bidder worker never
changes the judge. Both call the same product Core.

**Worker.** `crates/bitagi-signer/tests/ardr_judge_replay.rs`, the ignored test `ardr_judge_replay_worker`. It
reads the request file named by `BITAGI_ARDR_JUDGE_REPLAY_REQUEST` (at most 12 MiB) and writes a new answer file
named by `BITAGI_ARDR_JUDGE_REPLAY_ANSWER`. It reads no node, no store and no key. Per block it uses the product:

- `bitagi_bitcoin::decode_raw_block` and `recompute_and_verify_block_identities` (decode, txids, merkle root);
- the header hash as `bitagi_h0_receipt::checked_block` takes it (double SHA-256 of the 80 header bytes);
- the Stage-1 projection the product builds (`into_core_transactions`, `crates/bitagi-bitcoin/src/follower.rs`
  :919-960 and `crates/bitagi-h0-receipt/src/real_block.rs` :194-224);
- `bitagi_core::apply_block_transition` with the context the product builds (`real_block.rs` :378-393), and
  `encode_validated_canonical_state` for the poststate;
- the regtest Profile from `NetworkProfile::build_for_network(Regtest, H0)`; no other network is accepted.

The born Hearts are the transition's `AcceptedRegister` events, as txids in display order. The worker also checks
that the coinbase starts with the BIP34 push of the block's height (`bip34_prefix`, restated from
`crates/bitagi-h0-receipt/src/lib.rs` :180-202). It does not check proof of work.

**Request** (one LF per line, fields split by one tab):

    ARDR_JUDGE_REPLAY_REQUEST_V1
    PROFILE   regtest   <H0>
    PRESTATE  -  |  <canonical state hex>
    BLOCK     <height>  <raw block hex>        (1 to 4,096 lines, consecutive heights, each block on the one before)
    END       <number of BLOCK lines>

Numbers are canonical decimals and hex is lowercase. `PRESTATE -` is the Core 19.5 initial state as of H0 − 1,
so it is accepted only when the first block is H0; a state's as-of block must be the first block's parent and
its as-of height the height before. The Core replays no block below H0.

**Answer:**

    ARDR_JUDGE_REPLAY_ANSWER_V1
    ROW        <height> <block hash> <born txids, comma-separated | -> <next birth> <poststate SHA-256>
    POSTSTATE  <last height> <last block hash> <poststate hex>
    END        <number of ROW lines>

or the head and `REFUSED <code>`, one of `REQUEST_SIZE`, `REQUEST_LINES`, `REQUEST_HEAD`, `REQUEST_PROFILE`,
`PROFILE_NETWORK`, `PROFILE_H0`, `REQUEST_PRESTATE`, `REQUEST_HEX`, `REQUEST_HEIGHT`, `REQUEST_LINE`,
`REQUEST_BLOCKS`, `REQUEST_END`, `HEIGHT_SEQUENCE`, `BELOW_H0`, `BLOCK_DECODE`, `BLOCK_IDENTITY`, `BLOCK_CHAIN`,
`COINBASE_HEIGHT`, `STATE_REQUIRED`, `PRESTATE_DECODE`, `PRESTATE_HEIGHT`, `CORE_TRANSITION`,
`STATE_ENCODING`. Only an I/O failure makes the worker panic.

**The judge's side.**

- **Chain.** The final chain of section 7 (from the last accepted `BLOCK` back by previous-block hash), from H0 to
  the tip. Blocks off it are not replayed, except (J5) an item-4 reorg run's replaced branch: a second request, again
  `PRESTATE -`, over that branch's blocks H0 … H0 + d − 1 (block G as the run mined it and its descendants by
  previous-block hash; section 24). Both chains start at H0, so neither needs a prestate.
- **Calls.** `cargo test --locked -q -p bitagi-signer --test ardr_judge_replay -- --exact
  ardr_judge_replay_worker --ignored --test-threads=1`, or `<BIN> -q --exact ardr_judge_replay_worker --ignored
  --test-threads=1` with `--replay-bin BIN`. No shell. The request and the answer live in a new private
  directory; the worker's own output goes to stderr only; 1,800 s per call. *2026-11-11 (045b :1090, section 29): a call past that time is refused `REPLAY_WORKER_TIMEOUT` (exit 3), apart from `REPLAY_WORKER_FAILED`.*
- **Chunks.** At most 3 MiB of block hex or 4,096 blocks per request (one larger block goes alone), as B's
  campaign chunks its own (ARV1 section 14). Each request after the first starts on the last one's `POSTSTATE`.
- **Answer.** One `ROW` per block sent, in order, at its height, with the hash the judge computed; born txids that
  are transactions of that block, each once; `POSTSTATE` of the last block whose SHA-256 is the last row's; `END`.
  Else `REPLAY_ANSWER`, exit 4.
- **No judged gate.** The replay checks the judged gates only, so it does not run when none is judged
  (`births` `NOT_REPLAYED_NO_JUDGED_GATE`).

**Per judged gate** (gate fields of section 9; the first that fails names the exclusion):

- `replay_birth`: the Core did not bear exactly one Heart at G, or that Heart is not the REGISTER the judge
  found in block G (section 7);
- `replay_next_birth`: for gate k ≥ 1, G_k is not the Core's next birth after block G_{k−1} (gate 0: G_0 = H0, the
  initial next birth, J1's `height`);
- `replay_other_birth`: the Core bore a Heart at a height that is no judged gate's G, from G_0 up to the height
  before the first started gate that is not judged (else the tip). It is charged to the judged gate whose
  interval holds it. Births above that range (a failed gate's own) exclude nothing; the record lists every birth
  outside the judged gates' heights.

**Driver claims.** With the replay, each `CORE_REPLAY` line's `born`, `next_birth` and `state_sha256` are
compared with the replay's row at its height (driver claims only).

## 18. The judge workflow (J2)

A #258 6557890079 decision 2: the judge runs in its own main-only workflow,
`.github/workflows/claude-track-ardr-judge.yml`, which A dispatches after the window. It prints each judgement record
and its SHA-256 in the job log, because A's session reads job logs but cannot download artifacts. Its static
checks are `tests/claude_track/test_ardr_judge_workflow.py`. It is not a required check.

**Inputs.** `run_ids` (comma-separated `claude-track-ardr` dispatch runs of the experiment, at most 20),
`experiment` (J3: `ITEM1` or `POOL`, the experiment those runs dispatched), `mode` (`EXPLORATORY` or
`CONFIRMATORY`: the mode those runs were dispatched in and the judge's mode) and `registration` (a file of the
dispatched commit, CONFIRMATORY only; empty otherwise). *2026-11-10 (J4b): `experiment` also ITEM2, ITEM4_SELF_DEALING, ITEM4_FEE_ASYMMETRY, ITEM4_CENSORSHIP or ITEM4_REORG (section 27).*

**Permissions.** `contents: read` and `actions: read`, nothing else. Only one step holds the job's token, and it
makes GET requests only.

**Steps.**

1. Refuse any ref but `refs/heads/main` and any attempt but the first (`GITHUB_RUN_ATTEMPT` 1, as the campaign's
   plan job; J3 re-check P3-3); check out the dispatched commit with full history and without persisted
   credentials; verify the head.
2. Check the inputs before the token step: the mode is one of the two (a shell `case`, before it is written to
   `GITHUB_ENV`); `run-ids`; the registration is a blob of this commit in CONFIRMATORY and empty in EXPLORATORY.
   Save `git rev-list --first-parent "$GITHUB_SHA"` (this commit's first-parent history) for `--main-history`.
3. Install the pinned Rust toolchain and build the replay worker once (`cargo test --locked --no-run -p
   bitagi-signer --test ardr_judge_replay`), as the campaign's slice job builds the bidder worker. Every judge
   call runs that binary (`--replay-bin`).
4. Run `RealReplay` (section 17's worker on the judge's own Core-shaped run); a skip fails the step
   (`if grep -q skipped …; then exit 1; fi`: a `!` pipeline never stops a `set -e` script). Every multi-line step
   starts with `set -euo pipefail`.
5. The token step. Per run, in a new directory: `GET actions/runs/<id>` and `GET actions/runs/<id>/artifacts`
   (one page of 100), checked by `artifacts`, then each named zip with `GET actions/artifacts/<artifact id>/zip`.
   `gh api` follows the zip's redirect and writes the bytes to a file; no API answer and no URL is printed. The
   tool's own line (ids and digests, or a refusal) goes to the log through stderr, as do `run-ids`' and
   `unpack`'s, so the log says which code stopped which run. *2026-11-10 (J4b): a run with nothing to download also gets `GET actions/runs/<id>/attempts/1/jobs?per_page=100` (section 27).*
6. Per run, `unpack` binds and extracts the zips, then the judge runs per unit with a raw log (`item1`, or J3's
   `pool` for POOL, with the built worker), and the step prints each record and its `sha256sum` line. The policy
   and (ITEM1) the method policy are read with `git show` at the run's own commit (the declaration's paths); an
   EXPLORATORY run whose policy declares no method policy takes
   `tests/claude_track/ardr_exploratory_item1_method_policy_draft.json` of that same commit, as its driver took the
   DRAFT values. The D2-2 file `tools/claude_track_ardr_cluster.py` is read the same way and passed as
   `--d2-2-tool-at-commit`, so every record, EXPLORATORY too, says which D2-2 code ran (A #258, J2 PR). The step
   prints each run's count of units with a raw log. Every unit is judged; the step fails at the end if any judge
   call refused, a listed run gives no unit (`NO_JUDGED_UNITS run <id>`), or a record's `unit.run` is not the unit
   judged (`RECORD_UNIT_MISMATCH run <id> unit <n>`); these two messages go to stderr. J3: after every run the
   step runs `experiment` (section 20) over every listed run's collection and every unit record that was judged
   (a refused unit's record is left out, so its unit is `RECORD_MISSING` unless its collection has no OBSERVED
   gate), with the first listed run's policy, the saved dispatch listing, the main history and, in CONFIRMATORY,
   `--listed-after` the bound below, and prints that record (`experiment-<experiment>.json`) and
   its `sha256sum` line; a refusal there fails the step too. With an experiment (the J3 workflow always has one,
   A's Q9 decision), a listed run with no unit to judge is a notice, `NO_JUDGED_UNITS run <id> (notice: ...)`, not
   a failure, since the experiment's judgement counts its units (as missing or EXCLUDED); without one it still
   fails the step. *2026-11-10 (J4b): ITEM2 units are judged by `item2` and item-4 units by `item4`, with pool's arguments; a run that `unpack` accepted as declaring nothing reads nothing at its commit and goes to `experiment` as `--undeclared-run`; the experiment's policy is the first declared run's, and with none the step fails (`NO_DECLARED_RUN`, stderr; section 27).* *2026-11-11 (finding #788, section 28): an ITEM2 unit whose record is left out is `RECORD_MISSING` also when its collection state is EXCLUDED and its `exit` is not null (its driver ran).*
7. Upload the records as `ardr-judgements` (always).

**`run-ids --run-ids TEXT`.** 1 to 20 distinct run ids of digits without a leading zero (`RUN_IDS`). J3 keeps 20:
ITEM1 is one unit and POOL 50 units of 4 gates (200 observations, one dispatch under the campaign's 400-observation
budget), so 20 leaves room for re-dispatching BEFORE_START units; an experiment with more completed dispatches
cannot be listed whole and fails closed (`RUN_LIST_INCOMPLETE`). *2026-11-10 (J4b): ITEM2's 200 runs and an item-4 sub-scenario's 50 fit one dispatch each; a run that declared nothing counts toward the 20.*

**J3: the dispatch listing.** The token step also saves, after the runs' own reads and into a fresh directory, every
page of `GET actions/workflows/claude-track-ardr.yml/runs?event=workflow_dispatch&branch=main&per_page=100&page=N`
(page 1, then 2 … the count `run-pages --dir D` gives: at most 10, since a total of 1,000 or more is refused,
`RUN_LIST_CAPPED`). The Check-the-inputs step computes, in CONFIRMATORY, the bound `--listed-after`: the earliest
committer time among the commits of the dispatched history that changed the presence of the registration's exact
bytes, `blob=$(git rev-parse "HEAD:<registration>")` and `git log --format='%ct %cI' --find-object="$blob"
"$GITHUB_SHA" | sort -n | awk 'NR == 1 {print $2}'`, refusing an empty answer. It is the minimum, not the last line
of git's date order: with skewed committer dates a merged side branch that adds and removes a copy of the bytes
could otherwise move the bound later and leave early runs out (J3 delta re-check P3-1). A later revert to the same
bytes, a re-add, a rename or such a branch can only lower it, which is stricter (`RegistrationBound` runs both
cases on a repository); a PR merged by merge commit keeps its branch commit's committer date, a squash merge makes
a new commit with its own. The bound may carry any offset and is compared as a time (`instant`). *2026-11-10 (J4b): the query is `run-query`'s, computed in the Check-the-inputs step before the token: in CONFIRMATORY it adds `&created=%3E%3D<the UTC date two days before the bound>` (section 27).*

**`artifacts --dir D --run-id ID --mode M [--experiment E] --main-history H`.** `D/run.json` must be a completed,
first-attempt `workflow_dispatch` run of `claude-track-ardr.yml` on main named `ardr M E` (E is ITEM1 unless J3's
`--experiment POOL` is given), with a 40-hex `head_sha`
(`RUN_NOT_JUDGEABLE`). A `head_branch` of `main` is not proof that the run ran main's commit: a dispatch on a tag
named `main` lists the same way (as B's collector notes for recollections, `tools/claude_track_ardr_slices.py`
in `prior_recollection`'s paragraph on a tag named `main`). So the run's `head_sha` must also be on the first-parent history of the judge's own commit, which
the workflow runs only from `refs/heads/main`: one of the lines of H, the workflow's `git rev-list --first-parent
"$GITHUB_SHA"` (ancestor or equal; `RUN_NOT_ON_MAIN_HISTORY`, exit 6), as the collector's S04 rule binds its run
(`S04_NOT_ON_SLICE_HISTORY`, `slices.py`, in `s04_run`). A head reachable only through a merge's second parent is
refused. This binds the run to main only while main takes changes by merge commit alone: a fast-forward push or
a rebase merge (GitHub's rebase merge, which main's ruleset allows today, adds each rewritten commit to main's
first-parent line) puts commits main never pointed at on its first-parent history, so a dispatch on a tag `main`
at one of them would pass. A tag ruleset refusing `refs/tags/main` (a repository setting, the Founder's) closes
that gap. H must be one 40-hex commit per LF-terminated line, at least one (`MAIN_HISTORY_SHAPE`).
`D/artifacts.json` must be one page of fewer than 100 artifacts, each of this run (`workflow_run.id`), not
expired, with a `sha256:` digest or none, and name `ardr-declaration`, `ardr-collection` and each `ardr-slice-<n>`
at most once (`ARTIFACT_LISTING`; without the declaration or the collection `RUN_COLLECTION_MISSING`). It prints
the downloads as `<file stem>:<artifact id>`. *2026-11-10 (J4b): E may be ITEM2 or an item-4 name. A listing with no declaration, collection or slice artifact is a run that declared nothing: no download, `declared` false (else true); it may be a later attempt in CONFIRMATORY only (section 27).*

**`unpack --dir D --run-id ID --mode M [--experiment E] --main-history H --out O`.** It repeats `artifacts`'
checks, then:

- each downloaded zip's SHA-256 equals the listing's digest (`ARTIFACT_DIGEST`);
- `declaration.zip` holds `declaration.json` only: V2, experiment E, mode M, `run` `{run_id ID, run_attempt 1,
  commit}` equal to the run's head, a policy path, slices, and for ITEM1 a method policy path in CONFIRMATORY, for
  POOL none (`RUN_DECLARATION`); *2026-11-10 (J4b): ITEM2 and item 4 none, as POOL.*
- `collection.zip` holds `collection.json` only, a V2 collection whose units are objects, each with a
  `slice_record_sha256` that is null (or absent) or 64 lowercase hex (`COLLECTION_SHAPE`, exit 2, #655), and whose
  own `run` is this dispatch: run id ID, attempt 1, the run's head (`COLLECTION_RUN`, exit 6; J3 check P3-4);
- for each declared slice whose units the collection binds to a slice record (`slice_record_sha256`),
  `slice-<n>.zip` holds `slice-record.json` with that SHA-256 and naming exactly the slice's units
  (`SLICE_RECORD_SHA256`), and each raw log the record names (`raw_log_sha256` not null) as `raw-<run>.jsonl`
  (`RAW_LOG_MISSING`) with that SHA-256 (`RAW_LOG_SHA256`). A slice zip may hold only those members (a
  `slice-record.json.tmp` leftover is skipped, ARV1 section 13), each within its bound (`ARTIFACT_ZIP`);
- a slice with no collected record (its job never started or was lost) gives no raw log: its gates are the
  collection's, and J3 counts them.

It writes `O/declaration.json`, `O/collection.json` and `O/raw-<run>.jsonl` into the new directory O
(`OUTPUT_EXISTS`) and prints `{run_id, commit, policy_path, method_policy_path, units}`. *2026-11-10 (J4b): it prints `declared` too; for a run that declared nothing it checks `D/jobs.json` instead (section 27), makes O empty and prints `declared` false, no policy and no unit.*

**Not in J2 or J3.** A run whose collect job failed has no collection; its `RECOLLECT` run's recollection is not read
yet (`RUN_COLLECTION_MISSING`). J2 judged each run alone; J3's `experiment` (section 20) adds the 10% rule over the
registered N across the listed runs. *2026-11-10 (J4b): still not read.*

## 19. The pool run (J3)

A #258 6557890079, the J3 row (the judge's own tag parser and the Herfindahl index) and decisions 4, 5, 6 and 11.
045b :504 (Herfindahl index above 0.5; a block without a recorded producer is excluded and counted), :544-545 (50
runs of 4 gates, one public synthetic seat at feerate `b`, a producer tag in the coinbase, the index computed once
over all pool gates, per-run values descriptive only), :560 (the `PRODUCER_H<height>` draw). ARV1 sections 6, 13
(POOL gate states), 16 ("Which gates count", POOL), 17 and 18.

**Command.** `pool` reads one POOL raw log as section 4 reads an ITEM1 log, with the pool events (`CLUSTER_TOOL` and
`PREFIX_START` are refused, `RAW_LOG_EVENT`) and three typed pool fields: every `BLOCK` names a string `producer`,
every `DRAW` its `label`, `value`, `k` and `producer`, every `GATE_END` its `producer_tags`, a list of strings.
It needs no method policy and no D2-2. CONFIRMATORY binds as section 3 (registration, the log's policy and
registration hashes, the replay, the collection), without the method-policy and D2-2 checks.

**Policy** (`parse_pool_policy`). The `POOL` entry holds `miner_policy` `POOL_50_30_20` and optionally `params`
(ARV1 section 18), nothing else (`POLICY_POOL`; a `method_policy` there is `POLICY_METHOD_POLICY`). Without params
an EXPLORATORY run takes ARV1's DRAFT params (b 3,000, H0 110, 4 gates). CONFIRMATORY needs the count and params,
and 045b's 50 runs of 4 gates (`POLICY_POOL_RUNS`, `POLICY_POOL_GATES`, :545).

**The plan.** Gate g's seat is one PUBLIC SYNTHETIC seat, wallet `W<g mod 40>` (ARV1 section 17, DEFAULT), whose
REGISTER spends the `(W<g mod 40>, g)` funding output and pays rung 0, `ceil(b × 213 / 1000)`. The producer of the
block at height h is the draw `PRODUCER_H<h>` (experiment `POOL`, the run index, n = 100): A below 50, B below 80,
else C. The implied shares are 50/30/20, whose index is the 0.38 of :504.

**Gate states** (decision 11; the collection's rule, ARV1 section 13):

- `RUN_END DONE` (and the collection does not say the unit was killed after it): gates 0 … k − 1 OBSERVED
  (`DONE`), a deadline stop's gates NOT_STARTED `DEADLINE_REACHED` (as section 8).
- Any other run (`RUN_END FAILED` in any phase, no `RUN_END`, a cut log, a unit killed after `RUN_END DONE`): a
  gate with `GATE_END` that `excluded_gates` does not list is OBSERVED (`REBUILT_FROM_LOG`) when the collection's
  rebuild rule holds for it, from the lines before its `GATE_END` only: exactly one `BLOCK` line with the
  `GATE_END`'s `block_hash`, at its `height`, named by no earlier `GATE_END`, whose coinbase tags (read from its
  `block_hex` the way the collector reads a coinbase) equal the `GATE_END`'s `producer_tags` (`[]` too), and
  exactly one `DRAW` `PRODUCER_H<height>` line whose `producer` is the `BLOCK`'s. Any other started gate is
  EXCLUDED with the death cause; a gate never started is NOT_STARTED. A cut log so counts to its last whole
  `GATE_END`.
- These lines are driver claims. The rule only re-derives the collection's state, which `--collection` must equal
  (`COLLECTION_DISAGREES`). The judged gates (the OBSERVED ones) need not be a prefix: a pool gate counts by itself.

**Reading the tag** (`script_tags`, `coinbase_tags`; ARV1 section 17). The coinbase scriptSig is split into its data
pushes in order: `OP_0` (an empty push), `OP_PUSHBYTES_1`–`75`, `OP_PUSHDATA1`/`2`/`4` with their little-endian
lengths; any other opcode carries no data and is skipped. A tag is a push of exactly the 21 bytes
`BITAGI_ARDR_PRODUCER_` and one of `A`, `B`, `C`. A push that runs past the script's end makes it unreadable. For
the collection's rule the coinbase is read as the collector reads it: the header, a transaction count of at least
one, the version, the segwit marker and flag when present (the driver's coinbase of a block with witnesses), exactly
one input, its scriptSig.

**Per judged gate** (from the bytes; the first field that fails names the exclusion, section 9's convention):

| Field | Fails when |
|---|---|
| `height` | G (GATE_START) is not GATE_END's, or G0 is not H0, or G is not above the gate before's (which started first) |
| `bidders` | the BIDDERS seat of the gate is not one PUBLIC SYNTHETIC seat of `W<g mod 40>` |
| `block_g`, `winner` | as section 7: no block at G on the final chain; not exactly one transaction there spends a labelled funding output, the seat's, with one input, spent nowhere else |
| `fee` | the REGISTER does not pay rung 0 |
| `producer` | block G carries exactly one tag, and it is not the drawn producer of G (decision 4) |
| `replay_birth`, `replay_next_birth`, `replay_other_birth` | with the replay (section 17): the Core did not bear exactly the REGISTER found at G; G is not the Core's next birth after block G of gate g − 1; a birth at a height that is no started gate's G lies in this gate's interval [G, the next started gate's G) |

Run fields (they exclude every judged gate): `params`, `miner_policy` (`POOL_50_30_20`), `bidders_sha256`,
`bidders_list`. The funding layout is not judged here (ARV1 section 16: the pool judgement needs block G and its
tags only); its problems are reported in `run_shape.funding_problems` (decision 4 for POOL, as A amended it: section
16).

A judged gate with a field becomes EXCLUDED `JUDGE_PLAN_MISMATCH:<field>`. A judged gate whose block G does not carry
exactly one tag (none, two, or an unreadable scriptSig) becomes EXCLUDED `PRODUCER_MISSING` (045b :504, :545:
excluded and counted). Both count under the 10% rule. A filler block's tag is not judged.

**Driver claims.** `GATE_END`'s `winner_txid`, `wallet`, `block_hash` and `producer_tags`, each `DRAW`
`PRODUCER_H<h>`'s `value`, `k` and `producer` against the judge's own draw, `CORE_REPLAY` and `GENERATED` (as
item 1) are listed under `driver_claims` and change no state.

**The record** (`BITAGI_CT_ARDR_JUDGEMENT_V1`, `item` `POOL`). As section 13, with labels `CLASS_T`, `REGTEST`,
`JUDGE_RECORD`, `J3_POOL_RUN` (and `EXPLORATORY_NOT_A_VERDICT` outside CONFIRMATORY), `judge.unit` `J3`, and:

| Key | Value |
|---|---|
| `plan` | `rung0_fee`, `seats` (`{gate, wallet}`) |
| `gates` | per gate `gate`, `state`, `code`, `observation_id` (`OBS-8<run:07>-G<gate:03>`), `wallet`, `height` and `block_hash` (block G as read, null when not judged or not on the chain), `born_txid`, `next_birth`, `producer_tags`, `drawn_producer` (`{producer, value, k}`), `producer` (an OBSERVED gate's one tag, else null), `mismatches` |
| `producers` | the run's counts per producer, `gates`, `herfindahl` (an exact fraction), `scope` `RUN_DESCRIPTION_NOT_JUDGED` |
| `outcome` | `result` `NOT_A_VERDICT_PER_RUN` (045b :545: per-run values are descriptive only), empty `nogo` and `not_established` *2026-11-11 (045b :1090, section 29): and `verdict` with `result` `NOT_A_VERDICT_PER_RUN` and the other three keys null; `run_shape` has `collection_code`* |

## 20. The experiment's judgement across dispatches (J3)

A #258 6557890079 decisions 6 (POOL's 10% is counted by gate: more than 20 of 200) and 7 (a unit not dispatched when
the window closes counts as missing). 045b :571-572 (fixed N, no early stopping; exclusions above 10% of an
experiment's runs make it NOT_ESTABLISHED), :577-580 (each unit is dispatched once; only a unit whose slice record
shows it never started may be dispatched again).

**Command.** `experiment --experiment ITEM1|POOL` reads the policy (as `item1` or `pool` do), each listed dispatch's
collection (`--collection`, one per run, at most 20) and this judge's record of each unit with a raw log
(`--record`). It reads no raw log. With `--runs-listing` it checks the run list (below; CONFIRMATORY needs it).
CONFIRMATORY needs the registration, which must list the policy, and every
collection and record must carry its SHA-256 (`COLLECTION_REGISTRATION`, `RECORD_BINDING`); ITEM1's count must be
045b's one run (`POLICY_ITEM1_RUNS`, :546). *2026-11-10 (J4b): `--undeclared-run D` (repeatable; with the listing and the history) adds a listed run that declared nothing, re-checked from `D/run.json`, `D/artifacts.json` and `D/jobs.json`; at most 20 runs in all (section 27).*

**Collections** (read strictly, #655): V2, this experiment, the judge's mode (`COLLECTION_MODE`), a run id of digits,
a registration hash that is null or 64 lowercase hex; per unit its `{experiment, run, gate, cohort}` key (each unit
once), its state (BEFORE_START, OBSERVED or EXCLUDED), its code, and, unless BEFORE_START, one row per gate
(`gate`, a state of OBSERVED, EXCLUDED or NOT_STARTED, `code`). Two collections of one run are
`COLLECTION_DUPLICATE`.

**Records** (read strictly): this judge's per-unit record of this experiment (`RECORD_SHAPE`), made by this judge
file (`judge.tool_sha256`, `RECORD_TOOL`), in this mode, with this policy, and with the collection of the dispatch
that started its unit (`inputs.collection_sha256`, `RECORD_BINDING`); one per unit (`RECORD_DUPLICATE`). A pool
record's OBSERVED gates each name their producer.

**The registered N.** N is the policy's count for the experiment; an EXPLORATORY policy without one takes the
listed units (0 … the highest + 1) and says `registered.source` `UNITS_LISTED`. N times the gates per run is at
most 100,000 (`REGISTERED_N_SIZE`; 045b's experiments have 200 gates). A unit started (not BEFORE_START) in
two listed dispatches is refused (`UNIT_DISPATCHED_TWICE`, :577-580); a started unit at or above N is refused
(`UNIT_NOT_REGISTERED`, :571).

**Per unit 0 … N − 1:**

- started in a listed dispatch, with a record: the record's gate states, which must follow the collection's (the
  same state, or a collection OBSERVED gate the judge EXCLUDED; else `RECORD_DISAGREES`);
- started, without a record: the collection's gate states, only when none is OBSERVED (a unit with no raw log, such
  as a lost slice's, `SLICE_RECORD_MISSING`); else `RECORD_MISSING`; *2026-11-11 (finding #788, section 28): for ITEM2 the collection's state stands only when the unit's `exit` is null too (its driver did not end under the slice tool: never started, a lost slice, or interrupted); otherwise `RECORD_MISSING`.*
- BEFORE_START in every listed dispatch, or in none: every gate NOT_STARTED (`BEFORE_START`, `NOT_DISPATCHED`),
  missing (decision 7).

**The run list** (A's decision P2-1 on the J3 check). Without it, a dispatch left out of the list would count its
units as missing and drop its judged gates from the index: the checker turned a NO_GO (814/1600) into a GO
(614/1296) so, inside the 10% budget. A run of the experiment is a `workflow_dispatch` run of `claude-track-ardr.yml`
on main named exactly `ardr <mode> <experiment>` whose head is on the judge's first-parent main history (a tag
`main` elsewhere is not one). From the saved listing (`--runs-listing D`, `runs-<page>.json`, read before any set is
built: `RUN_LIST_SHAPE`, `RUN_LIST_CAPPED`, `RUN_LIST_CHANGED`):

- every `workflow_dispatch` run on main of `claude-track-ardr.yml` carries one of the campaign's run names (its
  `run-name`: `ardr CONFIRMATORY|EXPLORATORY <experiment>`, `ardr RECOLLECT <experiment> …`, a known experiment),
  else `RUN_LIST_TITLE`: the judge reads the listing only as the campaign writes it;
- each listed run (each collection's `run.run_id`) must be such a run and completed (`RUN_LIST_DISAGREES`);
- every such run created at or after the bound, completed or not, must be listed (`RUN_LIST_INCOMPLETE`, exit 6; a
  run still in progress cannot be judged yet, so it fails closed too);
- the bound is `--listed-after` (CONFIRMATORY: the committer time of the first commit that introduced the
  registration's bytes, section 18, required with the listing and the history, `RUN_LIST_REQUIRED`), else
  (EXPLORATORY) the first listed run's creation: an exploratory tally may start where A chooses but may not skip a
  run after it. With `--listed-after` a listed run created before the bound is refused (`RUN_LIST_DISAGREES`): the
  judged runs are exactly the experiment's runs at or after the bound, and a bound set too late refuses instead of
  selecting (A's decision P2-A on the re-check);
- runs of another experiment, mode or workflow, of another branch, at a head off the history, or created before the
  bound are not the experiment's: they need not be listed (a listed one is refused as above);
- `--listed-after` or `--main-history` without a listing is refused (`RUN_LIST_REQUIRED`). *2026-11-10 (J4b): the listed runs include each `--undeclared-run`; in CONFIRMATORY the saved listing holds only the runs created from two days before the bound (section 27).*

The record's `inputs.run_list` gives `listing_runs`, `experiment_runs`, `bound`, `bound_source` (`LISTED_AFTER` or
`FIRST_LISTED_RUN`) and `checked_runs`; it is null when no listing was given (EXPLORATORY only).

**The 10% rule.** The gate is the unit (decision 6; :546 defines the pool run as 4 gates). Over the N × gates per
run gates, missing and EXCLUDED gates add up; more than a tenth (`EXCLUSION_LIMIT`, :572) gives
`TEN_PERCENT_RULE`. No OBSERVED gate gives `NO_JUDGED_GATES`.

**POOL.** The Herfindahl index is computed once over the producers of every OBSERVED pool gate of every unit (:545),
as the exact fraction Σ n_p² / N². Above 1/2 (strictly, `POOL_HHI_MAX`, :504) it is `POOL_HHI_ABOVE_MAX`. The
outcome is NOT_ESTABLISHED when the 10% rule or `NO_JUDGED_GATES` holds (:571-572: such an experiment is not
established, and the index is a statistic of the gates judged), else NO_GO when the index is above 1/2, else GO.
The index is reported either way.

**ITEM1.** Each record's `nogo` and `not_established` reasons are the experiment's, except the run's own
`TEN_PERCENT_RULE`, which the experiment's 10% rule replaces. The outcome follows section 12's order: NO_GO, then
NOT_ESTABLISHED, then GO.

**The record** (`BITAGI_CT_ARDR_EXPERIMENT_JUDGEMENT_V1`), one canonical JSON line:

| Key | Value |
|---|---|
| `schema`, `labels` | the schema; `CLASS_T`, `REGTEST`, `JUDGE_RECORD`, `J3_EXPERIMENT`, and `EXPLORATORY_NOT_A_VERDICT` outside CONFIRMATORY |
| `experiment`, `mode`, `evidence_status`, `judge` | `ITEM1` or `POOL`; the judge's mode; the same; `{unit J3, tool_sha256}` |
| `inputs` | `policy_sha256`, `prereg_045b`, `registration_sha256`, `run_list` (above, or null), `collections` (`{run_id, sha256}`), `records` (`{run, sha256}`) *2026-11-10 (J4b): and `undeclared_runs` (`{run_id, run_sha256, artifacts_sha256, jobs_sha256}`; empty when none)* |
| `thresholds` | the constant table (section 4) |
| `registered` | `runs` (N), `source` (`POLICY` or `UNITS_LISTED`), `gates_per_run`, `gates`, `params_source` |
| `units` | per unit `run`, `dispatch_run_id`, `unit_state` (the collection's, or `BEFORE_START`, `NOT_DISPATCHED`), `source` (`RECORD`, `COLLECTION`, `NONE`), `observed`, `excluded`, `missing`, `result` (the record's) *2026-11-11 (045b :1090, section 29): and `unit_code`, the collection's code of the unit from the dispatch that started it (null when no listed dispatch started it, or when that collection gives it none; the code of a `BEFORE_START` listing is not copied and stays in the collections `inputs.collections` names; shown only)* |
| `gate_counts` | as section 13, over every registered gate *2026-11-11 (045b :1090, section 29): beside it `exclusions`: `{by_code}` for ITEM1 and POOL, the code of every gate that is not OBSERVED, over the same rows; null for ITEM2 and item 4* |
| `pool` | POOL: `counts`, `gates`, `herfindahl`, `herfindahl_max`, `above_max`; ITEM1: null |
| `outcome` | `result` (`GO`, `NO_GO`, `NOT_ESTABLISHED`), `nogo`, `not_established` *2026-11-11 (045b :1090, section 29): and, beside it, `verdict` (`result` `PASS`, `FAIL` or `INCONCLUSIVE`)* |

## 21. One item-2 run (J4a)

A's J4a plan and A's decisions on it (section 23). 045b :381 (item 2), :535-540 (bidders, the project seat, the
release schedule and fees, the clock and the presence check, the qualifying sample), :546 (the run is the unit),
:556-559 (the draws), :1050-1055 (section 14.4: the item-2 codes, rung 0 at four nodes, the L0 seat's draw, fees and
H0, rungs charged and not released), :1218-1220 (section 14.15: E13, F2, F9). ARV1 sections 7, 12, 13, 20, 22 and 26.

**Command.** `item2` reads one ITEM2 raw log as section 4 reads an ITEM1 log, with the item-2 events (ARV1 :82-95,
sections 12 and 16, section 20's `SCHEDULE`, `REPLACED_RUNG_MISSING`, `PRIVATE_REPLACE`, `RELEASE`,
`RELEASE_MEMPOOLS`, `G_TIMING`, and section 22's L0 lines; `CLUSTER_TOOL` and `PREFIX_START` are `RAW_LOG_EVENT`),
a run index below 200 (`RAW_LOG_UNIT`), and the typed fields it reads (`RAW_LOG_TYPES`, `RAW_LOG_GATES`,
`RAW_LOG_ITEM2`, `RAW_LOG_L0`). A float anywhere in the line is refused for `RUN_START`, `BIDDERS`, `DRAW`,
`BLOCK`, `FUNDING_SENT`, `GATE_START`, `GATE_END`, `RUN_END`, `CORE_REPLAY`, `GENERATED`, `SCHEDULE`, `RELEASE`,
`PUBLIC_SENT`, `PRIVATE_HANDOFF`, `PRIVATE_REPLACE`, `RELEASE_MEMPOOLS`, `G_TIMING`, `L0_FUNDING_BLOCK`,
`L0_LAUNCH_START`, `L0_SET_CHARGED`, `L0_READY`, `L0_ADMISSION`, `L0_BUDGET`, `L0_RELAY`, `L0_LABELS`,
`L0_BUDGET_COUNTERS` and `MEMPOOL` (its `node` and `txids`, read for the private hold). It is accepted in `TEMPLATE` (a getblocktemplate answer), `REPLACED_RUNG_MISSING`
(`waited_seconds`) and `L0_RUNG_TEST` (testmempoolaccept answers), whose typed fields only are checked, and in the
lines the judge does not read (`BLOCK_ACCEPTED`, `TESTMEMPOOLACCEPT`, `LADDER_EMPTY`, `GATE_NO_BID`,
`L0_TURN`, `L0_LAUNCH_END`, `L0_STOP_FAILED`). At most one `RUN_START`, `BIDDERS`, `SCHEDULE`,
`L0_LAUNCH_START`, `L0_SET_CHARGED`, `L0_READY`, `L0_BUDGET` and L0 funding block (`RAW_LOG_DUPLICATE_EVENT`). It
needs no method policy and no D2-2. CONFIRMATORY binds as section 3 without the method-policy and D2-2 checks
(registration, the log's hashes, the replay, the collection), and also: the policy's `l0_seat` (below), the log's
seat the policy's (`RAW_LOG_L0_SEAT`), no schedule override (`RAW_LOG_SCHEDULE_OVERRIDE`) and every logged
`budget_sha256` the policy's (`L0_BUDGET_SHA256`).

**Policy** (`parse_item2_policy`). The `ITEM2` entry holds `miner_policy` `ITEM2_DEFAULT`, `params` and optionally
`l0_seat`, nothing else (`POLICY_ITEM2`). Params are needed in every mode (`POLICY_PARAMS_UNSET`, exit 3: without
them the driver runs D1's smoke, which has no gate, so the PR-smoke policy's runs are refused, as `SEED_PENDING`
refuses them first), with one gate per run (`POLICY_ITEM2_GATES`) and H0 at least 107 (`POLICY_ITEM2_H0`; 045b :1054, ARV1 :1587). `l0_seat`
has ARV1 section 26's shape (`POLICY_L0_SEAT`, `POLICY_L0_SEAT_PRIVATE`). CONFIRMATORY needs the count, the key
(`L0_FREEZE_PENDING`), 045b's seat 1, `CEIL_2_5_B` and 24 attempts (`POLICY_L0_VALUES`) and H0 1000; a policy with a
non-PENDING key needs H0 1000 in any mode (`POLICY_ITEM2_H0`). *2026-11-10 (A, J4a verification round): the CONFIRMATORY key's `exact_height_miss` and `budget_sha256` are the frozen ones too, `CONTINUE_WITHIN_LIMITS` and `7d0a7a35…` (045b :1053's dated line, section 14.21 :1898-1901; `POLICY_L0_VALUES`).* *2026-11-10 (A, J5b; A's Q3 on #719): CONFIRMATORY also needs the policy complete (every experiment counted, each count an int 1 .. 2^32-1, every `counts` key an experiment (J5b verification round); `POLICY_COUNT_UNSET`, exit 3; a PENDING value anywhere stays `POLICY_PENDING`), as the driver's `load_policy`.*

**The L0 seat and its sources** (A's J4a decision 6; #667 P3-1). The seat is `RUN_START.l0_seat`. CONFIRMATORY: the
policy's seat with `l0_seat_source` `REGISTERED_POLICY`. EXPLORATORY: a seat 1-4 with `DRAFT_PARAMETER`, or
`PENDING_FREEZE` (no seat) with `PENDING_FREEZE`; another seat is `RAW_LOG_L0`. `L0_LAUNCH_START.budget_source` is
`REGISTERED_POLICY` with `budget_sha256` (and no `budget_draft`) in CONFIRMATORY, else `BUDGET_DRAFT` with
`budget_draft` (and no `budget_sha256`). A label not the mode's is `RAW_LOG_L0_SOURCE` (exit 6). L0 lines without the
seat, and the seat with H0 other than 1000, are `RAW_LOG_L0`. *2026-11-10 (A; B-FZ-a #756, ARV1 section 26 :2563-2571, A #756 6742106624): outside CONFIRMATORY a run on the policy's `l0_seat` values (the L0 CLI's `--policy-l0-seat`, 045b F3 command :1224) labels both lines `POLICY_VALUE`. The judge takes it only as a pair, `RUN_START.l0_seat_source` and `L0_LAUNCH_START.budget_source` both `POLICY_VALUE` with `budget_sha256` and no `budget_draft`, from a policy whose `l0_seat` holds no PENDING value (`RAW_LOG_L0_SOURCE` otherwise), on that key's seat (`RAW_LOG_L0_SEAT`), with every logged `budget_sha256` the key's (`L0_BUDGET_SHA256`) and the key's `exact_height_miss` expected (`l0_budget`), as CONFIRMATORY binds the registered key. `REGISTERED_POLICY` stays CONFIRMATORY's only; `POLICY_VALUE` in CONFIRMATORY is `RAW_LOG_L0_SOURCE`. Such a record is still EXPLORATORY (`EXPLORATORY_NOT_A_VERDICT`).* *2026-11-10 (A, J4a verification round): `POLICY_VALUE` also needs a policy the L0 CLI's `--policy-l0-seat` would load and take before any node: no PENDING value anywhere, every experiment counted, and a key with `p0_rule` `CEIL_2_5_B`, `max_gate_attempts` 24 and the product's record digest for its `exact_height_miss` (ARV1 section 26 :2557-2558; `RAW_LOG_L0_SOURCE`). `L0_BUDGET.policy_compare` must say `EQUAL`, with `policy_budget_sha256` the key's digest, in CONFIRMATORY and in a `POLICY_VALUE` run, and `NO_POLICY_VALUE` (or be absent) otherwise (ARV1 :2570-2571).* *2026-11-10 (A, Desktop P3 on #669): complete also means every count is an int 1 .. 2^32-1, as the producer's shape check (`check_policy_shape`, POLICY_COUNTS) requires; a null, 0 or non-integer count is not complete (`RAW_LOG_L0_SOURCE`).* *2026-11-10 (A, J5b verification round): nor is a policy with a `counts` key that is not an experiment, the shape check's other half (`check_policy_shape` POLICY_COUNTS, every mode).*

**The plan, recomputed** (no driver import). Seats S0-S4 with wallets W00-W04, S0 PRIVATE on even r, the L0 seat
`L0_PROJECT` / `L0` / PUBLIC. Fee draws: r = 0, 2, …, 98 draw `PRIVATE_FEE` (n = b + 1) and `PUBLIC_FEE_j` (n = 4b − p
+ 1); other runs `BID_FEE_j` (n = 3b + 1); the L0 seat draws nothing (045b :1052). t_G = `GATE_INTERVAL` (n = 1,200) +
1 s; with `schedule_source` `DRAFT_OVERRIDE` (EXPLORATORY only) RUN_START's t_G and spacing, recorded. The rungs
released: k with 60 k < t_G, at most rung 7. Every ladder by 045b :537 with i the larger of `SCHEDULE.increments`
(Node A's and Node B's), v 213, the L0 seat's at p_0 = ⌈2.5 b⌉. The rounds and the predicted count (the rungs released
strictly before t_G, summed over seats). The order constraint is reported as a property of the draws (`order_holds`).

**Bytes and attribution.** The chain is section 7's, with block 1 from `L0_FUNDING_BLOCK` when the seat is there.
Each synthetic seat's outpoint is its `[W0j, r]` label in `FUNDING_SENT` (the item-1 layout F9 keeps); the L0 seat's
is the one output of block 1's coinbase paying `funding_script`. Layout problems are `run_shape.funding_problems`,
reported, never an exclusion (A's J4a decision 7). Each handed-off synthetic rung's bytes (`PUBLIC_SENT`,
`PRIVATE_HANDOFF` for rung 0, `PRIVATE_REPLACE` after, which must replace the seat's rung before) must spend exactly
its seat's outpoint and pay its ladder's f_k at vsize 213. The candidates in G are block G's transactions that spend a
seat outpoint, each one input, a released rung of its seat, one per seat; their fee is the outpoint's value less the
outputs, their weight 3 × base + total size, vsize ⌈weight / 4⌉. **The winner** is the Core's one birth at G on the
replayed chain (section 17), attributed to the seat whose outpoint it spends, never by Anchor key or by `GATE_END`
(045b :1220); with `--no-replay` (EXPLORATORY) it is the first candidate in G's order (045b :421-423), `births`
`UNVERIFIED_NO_REPLAY`. The replay runs whenever block G is on the chain.

**Observed candidates** (045b :498): a handed-off public synthetic rung whose txid is in the relay's mempool in a
`RELEASE_MEMPOOLS` line after its `RELEASE`; a private rung the miner process took (its hand-off line); an L0 rung with
`L0_RELAY.at_relay` true or in a relay list taken at or after its `sent_ns` (compared by the lines' `t_ns`, one clock:
L0 writes its `RELEASE` lines after the driver's own steps, so a later step's list comes before them in the log). A
rung logged but not handed off is not observed. Rungs charged and not released are not released rungs (045b :1055).

**Every mined rung attributed, in the REGISTER form** (J4a check P1-1; Desktop r4443064942). Only a candidate of the
REGISTER form counts as a mined REGISTER (`candidates_in_g`, `mined_losing` and the fees of :499 and :500). A block-G transaction whose txid is a released rung (or a rung
`L0_READY` names) must be that seat's candidate, read through its funding outpoint; else `rung_bytes`. With an
`L0_FUNDING_*` problem and an L0 rung in G, also `l0_attempt`: the attribution needs the L0 funding outpoint.

**Unit state** (decision 11; as the collection derives it). One `GATE_START` and at most one `GATE_END`, both of gate
r with `OBS-2<r:07>`. `RUN_END` DONE after `GATE_END` OBSERVED is OBSERVED (unless the collection says the unit was
killed after it: EXCLUDED with the collection's code); `RUN_END` EXCLUDED (its `GATE_END` EXCLUDED with the same
code), `RUN_END` FAILED (phase SETUP, GATE or END), no `RUN_END` or a cut log are EXCLUDED. With `--collection` the
collection's unit state must be the judge's (`COLLECTION_DISAGREES`); a run-level unit has `gates` null
(`COLLECTION_SHAPE`).

**The item-2 code, re-derived** (045b :538, :1050), one per gate in order: `RELEASE_NOT_IN_TEMPLATE` (a seat's last
released rung, by log order, not in the transactions of the `TEMPLATE` line block G was built from, or the private
one not in its private set), `RELEASE_AFTER_G` (a `RELEASE.sent_ns` at or after t0 + t_G, t0 the `t_ns` of block
G − 1's `BLOCK` line), `G_LATE` (`TEMPLATE(G).t_ns` − (t0 + t_G) of 1 s or more); without block G,
`REPLACED_RUNG_NOT_IN_MEMPOOL` when `REPLACED_RUNG_MISSING` is logged. The code's seats are the missing, late or
missing-rung seats. Only a missing `TEMPLATE(G)` or block G − 1 stops the derivation; a plan mismatch found first (a
`release` timing one included) does not, and the code still wins for the run (Codex r4445199350).

**A run the driver ended OBSERVED** becomes EXCLUDED, in this order: with the re-derived item-2 code; else
`JUDGE_PLAN_MISMATCH:<field>` (decision 4) with the first field of the list below; else `MEMPOOL_LOG_INCOMPLETE` when the
relay log is not complete (045b :498: a gate without a complete mempool log is excluded and counted). The relay log is
matched by position: each release step k has its own `RELEASE_MEMPOOLS` line of that k, after step k's synthetic
`RELEASE` lines and the step before's line, before any later step's `RELEASE` and L0's first `RELEASE`; with L0 rungs
released, one more line of L0's last k after L0's last `RELEASE` (J4a check P2-2: L0's line never stands for a step's).
A driver item-2 code the judge does not reproduce stays, goes to `driver_claims`, and the observation's
`code_reproduced` is false (true for every other state and code; section 22 and section 23's J4a review decision).

| Field | Fails when |
|---|---|
| `params`, `miner_policy`, `bidders_sha256` | as section 9 (`ITEM2_DEFAULT`) |
| `bidders` | `BIDDERS.bidders` is not the plan's list, or `RUN_START`'s `private_present` / `order_constrained` not the run's |
| `fee_draws` | `BIDDERS`' feerates or draws (`label`, `n`, `k`, `value`, `feerate`) are not the judge's |
| `schedule` | RUN_START's t_G, spacing or released ks, or `SCHEDULE`'s `increment`, `rounds`, t_G, spacing or `l0_seat`, are not the judge's; a release on another path than its seat's |
| `ladder` | a synthetic seat's `SCHEDULE` ladder is not the judge's |
| `height` | `GATE_START` (or `GATE_END`) is not at H0 |
| `block_g` | no block at G on the chain for an OBSERVED run, or no candidate in it |
| `rung_bytes` | a handed-off synthetic rung's bytes as above, or its hand-off line out of its step's window: after its `RELEASE` (Desktop r4445653922), or before step k − 1's `RELEASE` lines and relay snapshot (step 0: before block G − 1's `BLOCK` line; Desktop r4446892062); a hand-off line no `RELEASE` pairs with (Desktop r4448008178: only a release's validated hand-off starts or ends a private hold or counts as taken); a candidate in G with more than one input, not a released rung of its seat, a second one of a seat, or not of the REGISTER form (Desktop r4443064942: output 0 the exact carrier of `crates/bitagi-wire` `construct_register_carrier` for the run's Regtest deployment id and target height G, value 0; output 1 an Anchor script); a released or L0-charged rung in G that is not its seat's candidate (P1-1) |
| `private_exposure` | a held private rung (from its `PRIVATE_HANDOFF` / `PRIVATE_REPLACE` to its replacement or the block that holds it) in a `RELEASE_MEMPOOLS` list or a `MEMPOOL` line (Desktop r4443056837: the driver stops such a run, `PRIVATE_IN_MEMPOOL`, RUN_END FAILED, and never writes the snapshot, so no item-2 code applies) |
| `presence`, `timing` | no `TEMPLATE` line before block G; no block G − 1, or `TEMPLATE(G).t_ns` before t0 + t_G (block G early: the driver did not run the frozen interval, 045b :537-538; no item-2 code, Codex r4442135911) |
| `release` | a rung k ≥ 1 is logged `due_ns` other than t0 + k × the rung spacing (60 s), or sent (`sent_ns`) before it (J4a check P3-2, Desktop r4443056830). Timing only: the released (seat, k) pairs against the plan's rounds are reported per gate (`gate.release_pairs`: planned, released, missing, extra, repeated) and reach :498 only through its count (A's P3-2 split, section 23) |
| `l0_fee` | the judge's L0 ladder (at most 8 rungs, each at most the draft 100,000 sat; *2026-11-10 (A): the frozen 30,000 sat, 045b A1 :1175*) is not `L0_LAUNCH_START.fee` (`b`, `p0`, `i`, `v` 213, `k` 0, `f_k`, `ladder`, `increments` = SCHEDULE's), `SCHEDULE`'s L0 ladder, `L0_SET_CHARGED`'s `fees`, every rung's `fee_sat`, `wallet_fee_sat`, `wallet_vsize` and charge base, each released rung's `L0_ADMISSION` (one per rung: `computed`, the wallet row, the charge base, both nodes `in_mempool` with f_k and 213) and L0 `RELEASE` `fee` / `vsize`, or the L0 rung read from block G's bytes (045b :1053; the driver's `L0_FEE_MISMATCH`) |
| `l0_attempt` | `L0_LAUNCH_START` missing, or its seat, kind, attempt 1, attempt id `L0ATT-OBS-2<r:07>-01` or H0 1000 differs; `L0_SET_CHARGED` / `L0_READY` missing or of another attempt; `L0_READY` not one txid per rung, or not `L0_SET_CHARGED`'s txid of each k (Desktop r4443056821: one txid per k from the charge to the release); an `L0_ADMISSION`, `L0_BUDGET`, `L0_LABELS`, `L0_BUDGET_COUNTERS` or `L0_RUNG_TEST` row of another attempt id (Desktop r4445659421, r4446892881; such a rung test never enters :501's refusal count); the attempt's `L0_RUNG_TEST` rows not one per charged rung k ≥ 1 with that rung's `L0_SET_CHARGED` txid (a duplicate, a k outside the set or another txid; Desktop r4448015560; only the first valid row of each k is counted at :501); an `L0_FUNDING_*` problem with an L0 rung in G; an L0 release not rungs 0, 1, … in order, not the charged rung's txid, or of another attempt *2026-11-11 (finding #788, section 28): in an item-2 run also an `L0_RUNG_TEST` row whose `when` is neither `BEFORE_RELEASE` nor `CHARGED_NOT_RELEASED_BEFORE_G`. The row counted at :501 is the first row of each rung k ≥ 1 of the judge's ladder whose txid is any charged txid of that rung; a row that is not counted is no longer silent there (`rung_tests_unresolved`)* |
| `l0_budget` | EXPLORATORY `budget_draft` not the draft record (ARV1 section 22 "Budget"); `L0_BUDGET` missing, its four fields not the draft's, its digest not `L0_SET_CHARGED`'s, its threshold not `500000/24`; `exact_height_miss` not the policy's (EXPLORATORY: `CONTINUE_WITHIN_LIMITS`) in `L0_LAUNCH_START`, `L0_BUDGET` or `L0_LABELS`; the wallet's last `gate_attempts` above 24. *2026-11-10 (A): the record is the L0 module's `BUDGET_DRAFT`, since B-FZ-p (#759) four fields of the frozen Class T record with status `FROZEN_TEST_ONLY` (045b :1898-1899); `budget_draft` is checked in a `BUDGET_DRAFT` run only, and a `POLICY_VALUE` run expects the policy's `exact_height_miss` (section 21)* |
| `replay_birth`, `replay_other_birth` | with the replay: not exactly one birth at G, or it is no candidate of G (zero births with candidates in G included); a birth at another height |

**Reported, not judged.** `L0_LABELS` beside the judge's in-G and born k (A's J4a decision 8); the L0 seat's charged
and not released rungs (count, fee sum, ks), `L0_BUDGET.product`, the wallet's counters and every `L0_RUNG_TEST`
answer (`allowed` per node); the funding problems (decision 7). *2026-11-11 (finding #788, section 28): `gate.l0.rung_tests` holds the answers of the counted lines; a line that is not counted is not listed, and it is counted in `rung_tests_unresolved` when a node's answer on it is open.*

**Driver claims.** `GATE_END`'s `born` and `winner` (with the replay; without it they are listed in
`gate.unverified_claims`, never compared with the unverified first candidate, and `CORE_REPLAY`'s `born` is not
compared either), `predicted_candidates`, `observed_candidates`, `block_hash` and an item-2 `code` the judge does not
reproduce; `SCHEDULE.predicted_candidates`; the `GATE_INTERVAL` `DRAW`'s `value` and
`k`; `CORE_REPLAY` (as section 17); `FUNDING_SENT.txid`; `BLOCK`'s height and hash.

**The record** (`BITAGI_CT_ARDR_JUDGEMENT_V1`, `item` `ITEM2`), as section 19's with labels `CLASS_T`, `REGTEST`,
`JUDGE_RECORD`, `J4A_ITEM2_RUN` (and `EXPLORATORY_NOT_A_VERDICT` outside CONFIRMATORY), `judge.unit` `J4A`, and:

| Key | Value |
|---|---|
| `plan` | condition, qualifying, `order_holds`, the seat and its source, the bidders, feerates and draws, the `GATE_INTERVAL` draw, `schedule_source`, t_G, spacing, released ks, increments and i, ladders, rounds, predicted count |
| `run_shape` | the log-derived unit state and code, `RUN_END` status and phase, `truncated`, `killed`, chain tip, stale and rejected blocks, `funding_problems` *2026-11-11 (045b :1090, section 29): and `collection_code`* |
| `gate` | block G's height and hash, the re-derived code and its seats, the timing (t0, due, template time, lag), misses, late seats, each seat's last released rung, the releases, the observed txids, `mempool_log_complete`, the candidates in G (seat, path, kind, k, txid, position, weight, vsize, fee), the winner and its source (`REPLAY` or `FIRST_IN_BLOCK_ORDER`), the L0 facts |
| `observation` | the row `experiment` reads: `observation_id`, `state`, `code`, `code_source` (`LOG` or `JUDGE`), `code_reproduced`, `code_seats`, `condition`, `qualifying`, `l0_seat`, `winner` (`seat`, `path`, `kind`, `txid`), `predicted_candidates`, `observed_candidates`, `private_observed`, `candidates_in_g`, `mined_losing`, `losing_weight_wu`, `losing_fee_sat`, `l0` (`attempted`, `in_g`, `born`, `mined_losing`, `losing_fee_sat`, `losing_weight_wu`; null without the seat), `traffic` (`handed_off`, `replacements`, `cancellations` 0, `l0_replacements`, `l0_rung_tests_refused`), `mismatches` *2026-11-10 (J4c, section 28): `traffic` also holds `rung_refusals_501`, `rung_refusals_501_undecided` and `rung_tests_before_release`.* *2026-11-11 (finding #788, section 28): each entry of `rung_refusals_501_undecided` also holds `why` (`REPLACES_UNKNOWN` or `ITEM5_UNKNOWN`), and `traffic` also holds `rung_tests_unresolved`.* |
| `outcome` | `NOT_A_VERDICT_PER_RUN`, empty `nogo` and `not_established` (as POOL) *2026-11-11 (045b :1090, section 29): and `verdict`, as POOL* |

## 22. The item-2 experiment (J4a)

`experiment --experiment ITEM2` reads the policy (as `item2`), the listed dispatches' collections and the `item2`
records, as section 20 does, with one observation per unit: a collection's ITEM2 unit has `gates` null and its state
is its one row's; a record's row is its `observation` (`RECORD_SHAPE`), whose `observation_id` must be its unit's
run, `OBS-2<unit.run:07>` (`RECORD_SHAPE`; Desktop r4446911576: a copy of another run's record with only `unit.run`
changed is refused). CONFIRMATORY needs 045b's 200 runs
(`POLICY_ITEM2_RUNS`). A unit not dispatched or BEFORE_START is missing (decision 7). Statistics use OBSERVED runs
only (E13).

**The rules that gate the statistics.** The 10% rule: missing and EXCLUDED runs above a tenth of N
(`TEN_PERCENT_RULE`; 21 of 200), for every row. The E13 stratum: of the qualifying runs (r = 0, 2, …, 98, fixed by run
index), missing and EXCLUDED above 5 of 50 (`QUALIFYING_STRATUM_RULE`; the same 1/10 of the stratum below N = 200),
for the :381 row only, the one statistic over the qualifying sample (045b :1218 amends :381 and :540).

**The rows** (A's J4a decision 2: a statistic row is NOT_ESTABLISHED before NO_GO, as POOL; a defect row is NO_GO
first, as item 1). Item 2's own outcome, the record's `outcome`, is the :381 row's; each row carries its own in
`item2.rows`.

| Row | Measure | NO_GO | NOT_ESTABLISHED |
|---|---|---|---|
| :381 (statistic) | private-seat (SYNTHETIC PRIVATE) winners over the OBSERVED qualifying runs, an exact fraction | above 1/2, strictly (`ITEM2_PRIVATE_WIN_SHARE_ABOVE_MAX`) | `TEN_PERCENT_RULE`, `QUALIFYING_STRATUM_RULE`, `NO_JUDGED_GATES` (no OBSERVED qualifying run), `DRIVER_EXCLUSION_UNREPRODUCED` (a qualifying run's record with `code_reproduced` false, whatever the stratum count) |
| :498 (defect) | per OBSERVED run, and per run EXCLUDED only by `release` timing (its one mismatch, no item-2 gate code) with a complete mempool log, observed against predicted; the observed mean, nearest-rank p95 and max and the predicted mean over the OBSERVED runs; `RELEASE_NOT_IN_TEMPLATE` runs left out and counted | any compared run with observed ≠ predicted (`CANDIDATES_DIFFER`) | `TEN_PERCENT_RULE`, `NO_JUDGED_GATES` |
| :499 (statistic) | mined losing candidates (all seats) and their share of mined REGISTERs; the project share: OBSERVED runs with an L0 attempt whose L0 rung in G was not born, over those runs (A's J4a decision 3); the share over every started L0 run beside it | project share above 25/100, strictly (`MINED_LOSING_SHARE_ABOVE_MAX`) | `TEN_PERCENT_RULE`, `NOT_MEASURED` (no OBSERVED L0 run; 045b :499 "not reported"); not the E13 stratum (A's clarification of decision 2, section 23) |
| :500 (statistic) | total and per-gate losing weight (WU) and fee (sat); the project's losing fee per attempted gate (exact), and over every started L0 run beside it | above 500000/24 (`LOSING_FEE_PER_ATTEMPT_ABOVE_MAX`; `source` DRAFT until the freeze line writes the value, A's J4a decision 4, cross-checked per run with `L0_BUDGET.product`, field `l0_budget`; *2026-11-10 (A): written, `source` FROZEN, 045b A2 :1176 and section 14.21 :1899*) | as :499 |
| :501 (reported) | replacements (handed-off rungs k ≥ 1; L0's with both nodes `in_mempool`), cancellations 0, per gate and as a share of handed-off rungs; the project's own; the `L0_RUNG_TEST` refusals of every started run's record | none in J4a (J4b, A's J4a decision 7) *2026-11-10 (J4b): none yet; judging it needs an L0 log change, A's decision (section 27)* *2026-11-10 (J4c, section 28): a defect row; any project rung refused before its release by Node A or B with `replaces_in_mempool` true, meeting item 5, in any run's record (`PROJECT_REPLACEMENT_REFUSED`)* | none (`REPORTED_NOT_JUDGED`) *2026-11-10 (J4c): `TEN_PERCENT_RULE`, `RUNG_TEST_REPLACES_UNKNOWN`, `NOT_MEASURED`* *2026-11-11 (finding #788, section 28): and `RUNG_TEST_ITEM5_UNKNOWN`, for a refused rung whose item 5 the judge cannot establish, and `RUNG_TEST_UNRESOLVED`, for a rung-test line the judge cannot resolve* |

**Reported beside them.** The win share by path (PRIVATE, PUBLIC, L0, NONE) per condition (order-constrained, other
even, odd); the private-order-flow share (the private rungs observed over all observed candidates of the OBSERVED
private-present runs, A's J4a decision 5); the exclusions by condition (EXCLUDED and missing), by code, by seat, and
the L0 seat's on a line of its own (045b :1050); the driver exclusions the judge did not reproduce, by condition
(`driver_exclusions_unreproduced`).

**The record** (`BITAGI_CT_ARDR_EXPERIMENT_JUDGEMENT_V1`) is section 20's, with labels `CLASS_T`, `REGTEST`,
`JUDGE_RECORD`, `J4A_ITEM2_EXPERIMENT`, `judge.unit` `J4A`, `registered.gates_per_run` 1, and `item2`: `stratum`
(`runs`, `missing_or_excluded`, `limit`, `over_limit`), `missing_or_excluded`, `over_10_percent`, `rows` (above, each
with `result`, `nogo`, `not_established` and its figures), `win_share_by_path`, `driver_exclusions_unreproduced`,
`private_order_flow_share`, `exclusions`. Every other experiment's record has `item2` null. *2026-11-11 (045b :1090, section 29): each row of `item2.rows` also carries its own `verdict`, and the record's `verdict` is the :381 row's, as `outcome` is; the record's top-level `exclusions` is null (item 2's tally is `item2.exclusions`).*

## 23. A's decisions on the J4a plan (2026-11-02)

1. **Citation base.** J4a cites the 045b freeze-draft lines (#664). Its branch stacks on `claude/a-045b-freeze`; its
   PR targets that branch until #664 merges as the "decided lines" PR, then retargets main. If #664 cannot merge
   first, J4a drops the E13 and F2 citations to J4b.
2. **Outcome order per row.** :381, :499, :500: NOT_ESTABLISHED (the 10% rule and the E13 stratum) before NO_GO, as
   POOL. :498 (and :501 when judged): NO_GO first, as item 1. Item 2's own outcome is the :381 row's.
3. **The project's attempted gates** (:499, :500) are the OBSERVED L0 runs; the all-started figure is reported beside.
4. **The :500 threshold** is a judge constant from the freeze line that writes it; until then DRAFT 500000/24 with
   `source: DRAFT`, cross-checked against `L0_BUDGET.product`. *2026-11-10 (A): the freeze wrote it (045b A2 :1176: 500,000 / 24 stays, FD-CT-102; section 14.21 :1899): 500000/24 with `source: FROZEN`.*
5. **The private-order-flow share** is the private share of observed candidate traffic, reported, not judged.
6. **EXPLORATORY seat:** seats 1-4 accepted (DRAFT_PARAMETER) and recorded; CONFIRMATORY only seat 1, from the
   policy key. *2026-11-10 (A): an EXPLORATORY `POLICY_VALUE` run takes the policy key's seat (B-FZ-a; section 21).*
7. **Item-2 funding problems** are reported (a run field), not an exclusion, until a real EXPLORATORY ITEM2 log shows
   structural `funding_problems` empty (as POOL Q8); then A decides. Winners are attributed by outpoint and txid only,
   never by Anchor key (F9). The :501 NO-GO waits for `replaces_in_mempool` (J4b); J4a reports :501. *2026-11-10 (J4b): not built; section 27 says what it needs.* *2026-11-10 (J4c): built; section 28.*
8. **L0 labels** are reported, not judged.
9. **Real log.** J4a merges on synthetic fixtures with a LATENT: the first real check is an item-2 L0 raw log from B
   (local or the `ardr-l0-real-nodes` job) before the 11-10 runs. No local Core build by the J4a builder.

Readings the plan left open, taken here and accepted by A (2026-11-02): an ITEM2 policy's H0 below 107 is
`POLICY_ITEM2_H0` (ARV1 section 20's `ITEM2_MIN_H0`, :1587-1592, and 045b :1054's "Item 2's lowest H0 is 107"), and an
EXPLORATORY log with an L0 seat must have H0 1000 (`RAW_LOG_L0`; 045b :1054, ARV1 section 22's `ITEM2_L0_H0`). A
missing release-step mempool line is `MEMPOOL_LOG_INCOMPLETE` (045b :498), and the funding layout is not a mismatch
field (decision 7). `POLICY_L0_VALUES` is exit 2 on purpose, a policy refusal before any log is read; the driver's
`L0_POLICY_P0_RULE` and `L0_POLICY_ATTEMPTS` (exit 6) belong to another tool. The replay runs whenever block G
exists.

- **A clarification 2026-11-02 of decision 2.** The E13 qualifying stratum (more than 5 of the 50 qualifying runs
  missing or EXCLUDED) gates only the :381 private-win-share row, because that statistic is computed over the
  qualifying sample (045b section 14.15 E13 amends :381 and :540 only). Rows :499 and :500 are computed over the
  attempted gates (decision 3); their NOT_ESTABLISHED rule is the item-level 10% rule plus their own section 4.5
  rule ("not reported": no attempted gate, `NOT_MEASURED`). Each row keeps NOT_ESTABLISHED before NO_GO.
- **A decision 2026-11-02 (J4a review).** Each observation carries `code_reproduced`: false when the log's exclusion
  is an item-2 gate code (045b :1050) the judge does not re-derive from the log. The experiment reports their count by
  condition; one in the qualifying stratum (r = 0, 2, …, 98) makes :381 NOT_ESTABLISHED
  (`DRIVER_EXCLUSION_UNREPRODUCED`) whatever the stratum count; elsewhere they are reported only.
- **A decision 2026-11-02 (J4a round 2, P3-2 split).** The released (seat, k) pairs against the plan's rounds (a
  planned rung not released, one released twice, an extra one) are not an exclusion field: they are reported per gate
  (`release_pairs`) and reach :498 only through the existing observed-against-predicted count, with no new NO-GO
  trigger. Field `release` keeps the timing checks only (a rung k ≥ 1 due at t0 + 60 k and not sent before it). A run
  EXCLUDED only by `release` timing whose mempool log is complete still reaches :498's count comparison. Reason: 045b
  :498 (FD-CT-92 row 8) names a release defect as the NO-GO, and that row excludes only gates without a complete
  mempool log; excluding a run for a wrong release-pair set would turn a preregistered NO-GO into an exclusion.
- **Desktop r4445653922 and r4445659421 (A: VALID, 2026-11-02).** The driver writes a rung's hand-off line
  (`PUBLIC_SENT`, `PRIVATE_HANDOFF`, `PRIVATE_REPLACE`), then its `RELEASE`, then the step's snapshot. A hand-off line
  after its `RELEASE` is `rung_bytes`, a plan mismatch (the run EXCLUDED and counted), not a refusal: it is the class
  of a `RELEASE` whose bytes are not handed off as the driver hands them (a missing or wrong hand-off line is already
  `rung_bytes`), the record still shows the run, and it is never OBSERVED; it also keeps a moved line from starting a
  private rung's hold after the snapshot that exposes it (`private_exposure`). Every L0 row the driver writes with
  `self.attempt` (`L0_ADMISSION`, `L0_BUDGET`, `L0_LABELS`, `L0_BUDGET_COUNTERS`, beside `L0_SET_CHARGED`, `L0_READY`
  and the L0 `RELEASE`) must name the attempt judged, else `l0_attempt`.
- **Desktop r4446892062 and r4446892881 (A: VALID, 2026-11-02).** The hand-off window has a lower bound too: the
  driver writes step k's hand-offs only after step k − 1's `RELEASE` lines and relay snapshot (step 0's after block
  G − 1), so a hand-off line before them is `rung_bytes`, the same class; it keeps a moved `PRIVATE_REPLACE` from
  ending a private rung's hold before the snapshot that exposes it. `L0_RUNG_TEST` rows must name the attempt
  judged too (`l0_attempt`), and a row of another attempt never enters :501's refusal count.
- **Desktop r4448008178 and r4448015560 (2026-11-02).** The driver writes every hand-off line right before its
  `RELEASE` (item 2's `_release`, the only caller of the bidders' `hand_off` in an item-2 run; a fault-injected test
  rung logs a `RELEASE` without a hand-off, never the reverse), so no item-2 log legitimately holds an unpaired
  `PUBLIC_SENT`, `PRIVATE_HANDOFF` or `PRIVATE_REPLACE`: one is `rung_bytes`, and only a release's validated hand-off
  starts or ends a private hold. The attempt's `L0_RUNG_TEST` rows are one per charged rung k ≥ 1 (ARV1 section 22)
  with its charged txid; anything else is `l0_attempt` (the class of the other L0 rows that do not belong to the
  attempt's set), and :501 counts one valid row per k.
- **Notes from the J4a review (2026-11-02).** The :500 threshold and the `l0_budget` draft constants
  (`L0_LOSING_FEE_PER_ATTEMPT_MAX`, `L0_LOSING_FEE_DRAFT`, `L0_MAX_FEE_PER_CANDIDATE_DRAFT`, `L0_BUDGET_DRAFT`) change
  with the freeze line that writes the Q1 values (decision 4). The F3 command's path (045b section 14.15 F3: the
  Python API in EXPLORATORY with the policy's digest) logs `budget_source` `REGISTERED_POLICY` outside CONFIRMATORY;
  the judge refuses it (`RAW_LOG_L0_SOURCE`) until B's freeze unit gives that path its own label (#667 P3-1). *2026-11-10 (A): both done. The 045b freeze (#664, `317ecbf5`) wrote the Q1 values: `L0_MAX_FEE_PER_CANDIDATE_DRAFT` 30,000 sat (was 100,000; A1 :1175, FD-CT-102), `L0_LOSING_FEE_DRAFT` 500000/24 (A2 :1176), `L0_LOSING_FEE_PER_ATTEMPT_MAX` 500000/24 with `source` FROZEN, and `L0_BUDGET_DRAFT` the L0 module's B-FZ-p record (status `FROZEN_TEST_ONLY`, the four fields of the Class T record `7d0a7a35…`, section 14.21 :1898-1899); the names are kept. B-FZ-a (#756) gave the path the label `POLICY_VALUE`, which the judge takes outside CONFIRMATORY as section 21 binds it; `REGISTERED_POLICY` outside CONFIRMATORY stays `RAW_LOG_L0_SOURCE`. The ARV1 line citations in this file were moved to main's lines on the same date (B-713, B-J5F, B-J5Z, B-FZ-a and B-FZ-p inserted lines there; the cited text is unchanged).*

## 24. One item-4 run (J5)

A's J5 plan and A's decisions on it (section 26). 045b :383 (item 4), :407-425 (the label table), :524 (50 runs),
:541-543 (the fixed inputs), :1063-1084 (section 14.4 "Item 4" and "Units and stopping", with the 2026-11-05 notes on
:1068 and :1084), :1219-1220 (F2, F9). ARV1 sections 22-26 (:1745-2645 on this branch).

**Command.** `item4` reads one raw log of `ITEM4_SELF_DEALING`, `ITEM4_FEE_ASYMMETRY`, `ITEM4_CENSORSHIP` or
`ITEM4_REORG`; the experiment is read from the log's first line (A's Q6; another is `RAW_LOG_EXPERIMENT`). It reads
the log as section 4 reads an ITEM1 log, with the item-4 events (ARV1 sections 22-25; `DRAW`, `L0_LABELS`,
`RELEASE_MEMPOOLS`, `G_TIMING`, `PRIVATE_REPLACE`, `CLUSTER_TOOL` and `PREFIX_START` are `RAW_LOG_EVENT`), a run index
below 50 (`RAW_LOG_UNIT`), and the typed fields of the table below (`RAW_LOG_ITEM4`, `RAW_LOG_L0`, `RAW_LOG_GATES`,
`RAW_LOG_TYPES`, `RAW_LOG_BLOCK`, `RAW_LOG_FUNDING`). A float is refused anywhere in those lines except `TEMPLATE`,
`REPLACED_RUNG_MISSING`, `L0_RUNG_TEST` and `MINER_FILTER`. At most one `SCHEDULE`, `SCENARIO_NOT_RUN`,
`ASYMMETRIC_BID`, `SELF_REGISTER`, `CENSOR_WINDOW`, `CENSOR_MEMPOOL`, `REORG`, `ITEM4_L0_RELEASE`, `ITEM4_L0_LABEL_LINE`
and L0 singleton (`RAW_LOG_DUPLICATE_EVENT`); a scenario's own line in another scenario's log is `RAW_LOG_ITEM4`, a
release step outside ITEM4_REORG `RAW_LOG_RELEASE_MARK`.

| Event | Fields read |
|---|---|
| `RUN_START` | `gates` [r], `params`, `miner_policy`, `bidders_sha256`, `scenario`, `depth`, `roles`, `fees`, `project_seat`, `self_fee`, `self_fee_rule` |
| `BIDDERS` | `bidders`, `bidders_sha256`, `draws` (`e`, `r`, `label`, `n`, `k`, `value`, `feerate`), `feerates` |
| `SCENARIO_NOT_RUN` | `not_run` (`scenario`, `case`, `label`, `reason`) |
| `SCHEDULE` | `increment`, `increments`, `ladders`, `after_g`, `rule`; with L0 `l0_seat`, `l0_release_ks` |
| `RELEASE`, `PUBLIC_SENT`, `PRIVATE_HANDOFF` | as section 21 (no `due_ns` needed); L0's `RELEASE` `sent_by`, `fee`, `vsize`, `attempt_id` |
| `TEMPLATE`, `BLOCK`, `BLOCK_ACCEPTED`, `MEMPOOL` | the template block G was built from; every block's bytes; the acceptance before a turn; the snapshots before each block |
| `ASYMMETRIC_BID`, `SELF_REGISTER`, `CENSOR_WINDOW`, `CENSOR_MEMPOOL`, `REORG` | ASYMMETRIC_BID is compared with the plan; the others are claims |
| `L0_TURN` | `attempt_id`, `worker`, `lines` (every value a string), `start_ns`, `end_ns`: the set worker's raw `labels`, `flags`, `reorg`, `released`, `phase`, `prestate_receipt`, `budget_counters` |
| `ITEM4_L0_OBSERVE`, `ITEM4_LABELS`, `ITEM4_L0_RELEASE`, `ITEM4_L0_LABEL_LINE` | the driver's copies and judgements: claims (the release turn's `procedure.mark` and `ITEM4_L0_RELEASE.step` are CONFIRMATORY's mark) |
| `CORE_REPLAY` | `height`, `born`, `next_birth`, `chain` (`FINAL`, `REPLACED`) |
| the L0 lines | as section 21 |

**Policy** (`parse_item4_policy`). The experiment's entry holds its pinned `miner_policy` (`ITEM4_SELF_FIRST_ZERO_FEE`,
`ITEM2_DEFAULT`, `ITEM4_CENSOR_144`, `ITEM4_REORG_REPLACE`; `POLICY_MINER_EXPERIMENT`), `params` in every mode
(`POLICY_PARAMS_UNSET`) and optionally `l0_seat`, nothing else (`POLICY_ITEM4`); one gate per run
(`POLICY_ITEM4_GATES`), H0 at least 107 (`POLICY_ITEM4_H0`), and for self dealing a project rung 0 above 600 sat
(`POLICY_ITEM4_SELF_FEE`, b ≥ 1127, 045b :1065). `l0_seat` has the item-4 shape: `p0_rule`, `max_gate_attempts`,
`exact_height_miss`, `budget_sha256`, no `seat` (`POLICY_L0_SEAT`). CONFIRMATORY needs the count, the key
(`L0_FREEZE_PENDING`) with `CEIL_2_5_B`, 24 attempts and `CONTINUE_WITHIN_LIMITS` (`POLICY_L0_VALUES`; 045b :1068: any
other value has no expected labels) and H0 1000; a non-PENDING key needs H0 1000 in any mode. *2026-11-10 (A, after the freeze): the CONFIRMATORY key's `budget_sha256` is the frozen Class T L0 record's, `7d0a7a35…` (045b section 14.21 :1898; ARV1 section 26 :2557-2558: the driver's `confirmatory_l0_seat` refuses another before any node), as item 2's (section 21); `complete` as item 2's.* *2026-11-10 (A, J5b; A's Q3 and Q4 on #719): CONFIRMATORY also needs the policy complete, as item 2's (section 21; `POLICY_COUNT_UNSET`). The `7d0a7a35…` pin is the first registration's record; item 4 registers in the follow-up registration (045b :317-320), and if that policy names another budget record the pin moves with it. Nothing changes before.*

**Binding.** CONFIRMATORY binds as section 21 (the registration, the log's hashes, the replay, the collection, the
budget source and digest), and also: the project seat is `L0_PROJECT` (`RAW_LOG_ITEM4_STANDIN`, exit 6: the stand-in
never runs CONFIRMATORY, ARV1 :2076-2077, A's Q7), and in a reorg run the release mark (045b :1069; A's Q10 and A's
decision on the J5 check, P2-1; `RAW_LOG_RELEASE_MARK`, exit 6). The release turn is found by its position in the
planned turns (the `RELEASE` turn), never by the phase a line claims. Every mark present is `RELEASE_REORG67_TEST_ONLY`:
each `ITEM4_L0_OBSERVE.procedure.mark`, the release turn's `ITEM4_L0_OBSERVE` (with or without a `procedure`) and each
`ITEM4_L0_RELEASE.step`. When the run went past the release turn (a later turn is in the log, or RUN_END is DONE), the
release turn's `ITEM4_L0_OBSERVE` carries that `procedure.mark`. When it went past the STALE turn's checks (RUN_END
DONE, or an `ITEM4_L0_LABEL_LINE` in the log), the log also holds exactly one `ITEM4_L0_RELEASE`, with that `step`:
ARV1 section 25 writes `ITEM4_L0_RELEASE` after the STALE turn and its checks and the label line after it, so a run
stopped inside the STALE turn has none. A run the driver stopped inside the release turn (before its
`ITEM4_L0_OBSERVE`, e.g. `L0_RELEASE_NOT_REORG67`) has no mark to show and is judged. `labels_judged.release_mark` is
`MARKED` or `STOPPED_BEFORE_THE_MARK` (null outside CONFIRMATORY ITEM4_REORG). In EXPLORATORY a stand-in log
(`PROJECT_STANDIN`, no L0 line: `RAW_LOG_L0` otherwise) is judged for its mechanics; its labels are
`NOT_APPLICABLE_STANDIN` and it is never label-judged. *2026-11-10 (A, after B-FZ-a #756; ARV1 section 26 :2563-2571): an EXPLORATORY L0 run on the policy's key labels its budget `POLICY_VALUE` (the L0 module's `budget_fields`; no CLI writes it for item 4, the L0 CLI runs ITEM2 only). An item-4 RUN_START has no `l0_seat_source`, so `L0_LAUNCH_START.budget_source` alone says it (`l0_policy_valued`). The judge takes it as section 21 does for item 2: the policy complete and its key present, `CEIL_2_5_B`, 24 attempts and `budget_sha256` the product's record for the key's `exact_height_miss` (`RAW_LOG_L0_SOURCE`, exit 6, otherwise); `budget_sha256` and no `budget_draft` on the launch, `L0_BUDGET.policy_compare` `EQUAL` with `policy_budget_sha256`, every logged digest the key's (`L0_BUDGET_SHA256`); the key's `exact_height_miss` is the run's, and anything but `CONTINUE_WITHIN_LIMITS` is `l0_budget` (045b :1068). `REGISTERED_POLICY` outside CONFIRMATORY stays `RAW_LOG_L0_SOURCE`.*

**The plan, recomputed** (no driver import; every value from a constant of section 4).

| Item | Rule |
|---|---|
| seats | self dealing S0 `SELF` (W00, PRIVATE), S1 the project; fee asymmetry S0 `ASYMMETRIC` (W00), S1 the project, S2-S4 `HONEST` (W02-W04); censorship and reorg S0 the project, S1 `COMPETITOR` (C00). The project is `L0_PROJECT` / `L0` / PUBLIC, or the stand-in SYNTHETIC W01 PUBLIC (045b :1078, :1219) |
| fees | f_0 = ⌈p_0 × 213 / 1000⌉ with p_0 = ⌈2.5 b⌉ (the L0 ladder's rung 0, 045b :537); self 600 sat; competitor 2 f_0 + 1; asymmetric one rung of ⌈10 × median × 213 / 1000⌉ (above 90,000 sat: `fees`); honest ⌈p × 213 / 1000⌉ (045b :1065, :1079) |
| draws | `BID_FEE_2` … `BID_FEE_4` of `ITEM4_FEE_ASYMMETRY`, n = 3b + 1, feerate b + value; the median is the nearest-rank p50 of [p_0, the draws] (045b :541, :565, :1076, :1078) |
| ladders | i = the larger of `SCHEDULE.increments`; the L0 seat's 045b :537 ladder; a censorship stand-in's first two rungs |
| depth, turns | d = 1 for even r, 2 for odd r (045b :1070). Turns: G (self dealing, fee asymmetry); G, G + 143, G + 144 (censorship); G (and G + 1 at d = 2) on the replaced branch, then `REORGED` (`set_reorged`), `RELEASE` (`set_release`) and `STALE` at G + d (045b :1068) |
| not run | censorship `DONE_BORN_LATE_NOT_AT_OPENING`; self dealing `ITEM4_SELF_ZERO_FEE_REGISTER`; then `E7_REORG_BEFORE_INCLUSION` in an L0 run, `L0_PROJECT_SEAT` in a stand-in run (045b :1066-1067; compared by scenario and case, A's Q17) |

**Bytes, branches and attribution.** The FINAL chain is section 7's. Block G as the run mined it is the first block
the log wrote at H0 on FINAL's G − 1 (`block_g` when FINAL has no block at H0 in a whole run, or G holds no
candidate). In a reorg run the replaced branch is that block and its descendants up to
H0 + d − 1 by previous-block hash, those not on FINAL. Seats' outpoints are section 21's (the competitor's `[C00, r]`
label too). The candidates in a block (H0 and above, both branches) are its transactions that spend a seat outpoint,
with fee, vsize and weight from the bytes; each must be a known rung of its seat (its `RELEASE`, or for L0 `L0_READY`),
one input, one per seat, of the REGISTER form (`rung_bytes`). The project's set is L0's `L0_READY` txids and its funding
outpoint (stand-in: its released rungs and outpoint); a block's project transactions are those txids or any spend of
the outpoint, whatever the txid (045b :1079, :1220).

**The exclusion code, re-derived:** `RELEASE_NOT_IN_TEMPLATE` (a seat's last rung released before block G not in G's
template, or the self rung not in its private set), then (stand-in) `REPLACED_RUNG_NOT_IN_MEMPOOL` when
`REPLACED_RUNG_MISSING` is logged (045b names no item-4 code; ARV1 section 23). A missing template is `presence`.

**The replay.** FINAL from H0 (section 17), and in a reorg run that has reorged the replaced branch as a second request.
`replay_birth`: on FINAL, exactly one birth at G and it is a candidate of G; `replay_other_birth`: no other birth;
`replay_replaced`: the replaced branch's births are exactly L0's rung 0 at G; `winner`: the birth's seat role is the
scenario's adversary (`SELF`, `ASYMMETRIC`, `COMPETITOR`; A's Q3: a project win is the driver's defect, never a
mislabel). A reorg run that stopped before its reorg has FINAL equal to G's branch, and its FINAL winner is not checked.
With `--no-replay` (EXPLORATORY) the winner is G's first candidate and the labels' next birth the driver's
`CORE_REPLAY` of the turn's chain (`labels_judged.next_birth_source` `CORE_REPLAY_UNVERIFIED`; A's Q14).

**Mechanics** (each a plan field, so a driver or harness defect: decision 4). A run is *whole* when its RUN_END is
DONE or, with L0, every planned turn is in the log (A's decision on the J5 check, P3-3: a run the driver failed on its
own label check after its last turn has written every line). The absence checks (a line or block missing, a tip short
of the plan's, the plan's set of releases exactly) apply to a whole run; a run stopped partway keeps every other check.

- Self dealing: block G's first transaction is S0's handed-off rung 0 (`self_first`), at 600 sat from the bytes
  (`fees`), its feerate strictly below every other seat's last released rung in G, each of which G holds
  (`self_first`); the self rung in no `MEMPOOL` snapshot between its hand-off and block G (`private_exposure`).
- Fee asymmetry: `ASYMMETRIC_BID`'s `seat`, `median`, `factor`, `feerate`, `fee`, `honest_feerates`,
  `project_configured_p0`, `project_seat` (and with L0 `project_p0_sources`, `project_sent.k`, `source` and
  `fee_source`) the plan's (`asymmetric`; missing in a whole run too); `project_sent`'s fee, vsize and txid L0's rung 0
  read from block G (`l0_fee`; stand-in: its fee and txid, `asymmetric`).
- Censorship: no project transaction in G … G + 143; G + 144 holds the project's last released rung (L0's rung 0; the
  stand-in's rung 1); the FINAL tip no higher than G + 144, and G + 144 in a whole run (`censor_window`). L0's rung 0 in
  Node A's and Node B's `MEMPOOL` snapshot before each block G + 1 … G + 144 (`censor_mempool`). No L0 `RELEASE` after
  block G (`release`).
- Reorg: `RUN_START.depth` d (`reorg_depth`); the replaced G holds the project's rung 0 alone of its set; once reorged
  (or in a whole run) the replaced branch is H0 … H0 + d − 1, no other stale block, the FINAL tip H0 + d
  (`reorg_replaced`); no replacement block H0 … H0 + d holds a project transaction (`reorg_readded`); TEMPLATE(G′)
  offers the competitor's rung 0 (`reorg_offered`); the REORGED turn's raw `reorg` line is exactly
  `raised:true;local:<H0+d−1>:<replaced tip>;at_local:<FINAL block at H0+d−1>;ancestor:<H0−1>:<its hash>`, hashes in
  internal byte order, and the RELEASE and STALE turns' lines are `-` (`reorg_seen`; A's Q9: a plan field until 045b
  states it).
- Every scenario: `SCHEDULE` (`schedule`; a synthetic ladder `fees`, L0's `l0_fee`), `RUN_START.fees`, `self_fee` and
  `self_fee_rule` (`fees`), the releases (`release`: a path other than its seat's, a release before block G − 1, a
  before-G release after block G or an after-G one, the reorg's competitor and the stand-in's censorship rung 1, before
  it, a (seat, k) twice or not the plan's, and in a whole run the plan's set exactly), the hand-off bytes as section 21
  (`rung_bytes`; another fee `fees`), and J4a's L0 checks with this run's attempt id `L0ATT-OBS-<e><r:07>-01`
  (`l0_fee`, `l0_attempt`, `l0_budget`), plus: L0 releases rung 0 only, and rung 0 in a whole run (`l0_attempt`);
  every `L0_RUNG_TEST` of the attempt `CHARGED_NOT_RELEASED_BEFORE_G` (`l0_attempt`); every `ITEM4_L0_OBSERVE`,
  `L0_TURN` and `ITEM4_L0_RELEASE` of the attempt (`l0_attempt`); `exact_height_miss` `CONTINUE_WITHIN_LIMITS`
  (EXPLORATORY: the draft's) in every `ITEM4_LABELS` (`l0_budget`).

**The host's labels** (045b :1068 and its note; A's Q2: judged in all four sub-scenarios).

- *The turns.* A turn is a `launch_set_worker` `L0_TURN` of an observing phase (`set_observe`, `set_reorged`,
  `set_release`) whose run ended the turn (`prestate_receipt` `-`), in log order; its tip is the last accepted block the
  log wrote before it. The j-th planned turn is the j-th turn: its tip must be the planned branch's block at its height,
  its phase the planned one, and a `BLOCK_ACCEPTED` of that block must stand between the block and the turn with a
  `t_ns` not after the turn's `start_ns`; else `l0_turns` and the turn is not judged. An extra turn, or (RUN_END DONE)
  a missing one, is `l0_turns`. The j-th `ITEM4_L0_OBSERVE` must stand between the j-th turn and the next
  (`RAW_LOG_ITEM4`); its turn, height, tip, phase, labels, flags and `released` are claims.
- *The raw lines.* `labels` is `r<j>=<verdict>/<outcome>` and `flags` `r<j>=opening_block_missed:<b>,
  reorged_before_inclusion:<b>`, each rung of the set (`L0_READY`'s count) once, read by rung name; in a reorg run
  `reorg` is `-` or `raised:<b>;local:<h>:<hash>;at_local:<hash or below>;ancestor:<- or h:hash>` and `released` `-`
  or `reason:<r>;step6:<s>` (ARV1 section 25). A's decisions on the J5 check (P2-2) and its re-check (P2): a turn whose
  stage did not complete (its `done` line is not `yes`) or that lacks one of these lines has no raw evidence and is not
  judged (`RAW_LINE_ABSENT`). A line of 045b's label line that is there but not in its form is a wrong-form label, so
  the turn is judged and does not match (`RAW_LINE_MALFORMED`, `malformed` names the lines; 045b :383 and :1068's
  note), NO-GO evidence under a clean plan: `labels` and `flags` in every sub-scenario, `released` in a reorg run only
  (:1068 names the release step there; in the other three sub-scenarios `released` is not judged at all). The `reorg`
  line is not part of 045b's label line (A's Q9): a malformed one, in any sub-scenario, is a wrong one, plan field
  `reorg_seen`. A `labels` or `flags` line that does not parse in a turn the driver accepted (its `ITEM4_L0_OBSERVE` is
  there, so the driver parsed it) is a log that contradicts itself: `RAW_LOG_ITEM4_LABELS`.
- *Expected, per rung* (the case from the bytes, A's Q3). On the turn's branch up to its height: a rung the replay found
  born is `Done:Born@<H0>+opening` / `Born@<H0>+opening` and the set's other rungs `Done:ProjectBornByOther@<H0>` /
  `ProjectBornByOther@<H0>`, flags false and false (before the replacement tip); else a rung a block holds is
  `Done:IncludedNoEffect@<its height>` / `IncludedNoEffect@<its height>`; else the outcome is `Stale@<H0>><next birth>`
  and the verdict `Refuse:Locked(Reorg67)` at REORGED and RELEASE, `Refuse:GateAdvanced` when released, else
  `Wait:OfflineSignaturePending`. Every rung not born: `opening_block_missed` true, `reorged_before_inclusion` false.
  The next birth is the replay's at the turn's height on its branch. So a clean self-dealing or fee-asymmetry run
  expects rung 0 `Done:IncludedNoEffect@1000` and rung k ≥ 1 `Wait:OfflineSignaturePending`; censorship rung 0
  `Refuse:GateAdvanced` at G and G + 143, `Done:IncludedNoEffect@1144` at G + 144; a reorg run E9-d's chain.
- *Host-format tokens* (A's decision on the J5 check, P3-5). Some strings the judge compares are ARV1 section 24's host
  rendering, not 045b text: `@<H0>+opening` after `Done:Born` and `Born` (045b :1068's note writes `Done:Born`), the
  outcome `ProjectBornByOther@<H0>` (the note writes the verdict `Done:ProjectBornByOther@<H0>`) and the released
  string `reason:Reorg67;step6:Some(NotPerformed)` (045b :1068: the `RELEASE_REORG67_TEST_ONLY` phase, step 6 not
  performed). Every expected value they carry cites 045b: a rung's case, its heights, the flags, the next birth and the
  release step (:1068 and its 2026-11-05 note, :1069; the constants of section 4).
- *Judged.* A turn is judged when it is the planned turn, its lines are there and a replay row covers every height up
  to its own (`NEXT_BIRTH_UNKNOWN`; a turn with a malformed line is judged without one). Each rung's verdict, outcome
  and both flags are compared; any one that differs is a mislabel, and so is a malformed line (045b :1068's note,
  :383). The next birth is read at the turn's own height (the :1068 note). In a reorg run each turn's raw `released`
  line is part of the label line: `reason:Reorg67;step6:Some(NotPerformed)` after RELEASE, `-` at every other turn
  (045b :1068: every step is kept; a dropped, moved or other release step is a mismatch). `labels_judged.label_line`
  composes rung 0's line with the release step, observed and expected. A driver turn structure that differs (a turn
  missing or added) is `l0_turns`, not a mislabel.

**Classification** (A's Q1, 045b :1084's note). The unit state stays the collection's (decision 11). A run the driver
ended OBSERVED becomes EXCLUDED with the re-derived code, else `JUDGE_PLAN_MISMATCH:<field>` in this order: `params`,
`miner_policy`, `bidders_sha256`, `bidders`, `fee_draws`, `fees`, `asymmetric`, `not_run`, `schedule`, `height`,
`block_g`, `presence`, `rung_bytes`, `release`, `private_exposure`, `self_first`, `censor_window`, `censor_mempool`,
`reorg_depth`, `reorg_replaced`, `reorg_readded`, `reorg_offered`, `reorg_seen`, `l0_turns`, `l0_fee`, `l0_budget`,
`l0_attempt`, `replay_birth`, `replay_replaced`, `replay_other_birth`, `winner`. With no plan field and no re-derived
code, an L0 run is:

- **label-judged** when every planned turn is judged, whatever its RUN_END (a run the driver failed on its own label
  check, `ITEM4_LABEL_MISMATCH` or `L0_RELEASE_NOT_REORG67`, included), matching or not;
- **NO-GO evidence** when a judged turn mismatches, also when the run stopped partway;
- otherwise neither (a stopped run with every judged turn matching, or a run with a plan field: an exclusion).

`code_reproduced` is false when the log's code is a driver mechanics code (`ITEM4_CENSOR_LEAK`,
`ITEM4_CENSOR_NOT_LIFTED`, `ITEM4_CENSOR_END`, `ITEM4_WINNER_READDED`, `ITEM4_SELF_NOT_FIRST`,
`ITEM4_SELF_FEE_NOT_LOWEST`, `ITEM4_TEMPLATE_STALE`, `ITEM4_REPLACED_NOT_WINNER`, `ITEM4_WINNER_STILL_BORN`,
`ITEM4_L0_CENSORED_LEFT_MEMPOOL`, `ITEM4_L0_NOT_IN_G`, `ITEM4_L0_REORG_SEEN`, and `L0_REORG_LINE` by `reorg_seen`)
the judge's fields do not reproduce, an exclusion code it does not re-derive, or a driver label-check code or
host-form code (`ITEM4_L0_FLAGS`, `L0_LABELS`) with no mismatch the judge finds (A's Q1 sub-decision: a judged matching
run, the driver's defect, `driver_label_check.reproduced` false, reported).

**Reported, not judged.** The project born on FINAL (the win-rate numerator) and the winner; mined REGISTERs that
created no Heart (count, weight, fee), all seats and L0, Ledger A (the FINAL chain from H0) and Ledger C (the replaced
branch; 045b :1061); a reorg run's replaced winner (depth, whether L0's rung 0 was born on the replaced branch and not
on FINAL, the STALE turn's rung-0 label as the label line's end state); the release class (a reorg run whose RELEASE
turn's release step matches: `CLASS_T_TEST_STEP`, "the release is a Class T test step", 045b :1067); the transitions
the judged turns' host labels reach (`DONE_BORN`, `PROJECT_BORN_BY_OTHER`, `STALE_OPENING_MISSED`,
`INCLUDED_NO_EFFECT`, `REORG67_LOCK`, `REORG67_RELEASE_CLASS_T`, `GATE_ADVANCED`, `OFFLINE_SIGNATURE_PENDING`; A's Q13);
the not-run cases; the funding problems; the driver's label disagreements per turn.

**The minimum transitions** (J5b, 2026-11-10; A's Q1 on #719; 045b :1279, frozen, and its dated line; the CT-P5-001
inventory section 2, TR-1 to TR-6 for item 4). The run reports which transitions of its sub-scenario's list it reaches
(`observation.min_transitions`, TR ids in the list's order); it cannot see the other runs, so the experiment counts
them (section 25). A transition counts only in its sub-scenario and at the planned turn the inventory lists, and only
with the judge's own replay (with `--no-replay`, and in a stand-in run, none is reached). A rung shows a transition
when its turn is judged and its raw label (the set worker's `L0_TURN` lines, the labels `ITEM4_L0_OBSERVE` copies)
matches the label derived from the bytes and the replay; a reached transition with a wrong label is NO-GO evidence as
before, and NO_GO stays first (section 25). The lines the inventory names are read as below; E7 is not required.

| TR | Sub-scenario, turn | Evidence the judge reads |
|---|---|---|
| TR-1 `Done:Born` | ITEM4_REORG, G | rung 0 `Done:Born@<H0>+opening`, matching; the replaced branch's replay gives exactly that birth (no `replay_replaced`) |
| TR-2 `Stale`, `opening_block_missed` true | ITEM4_CENSORSHIP, G or G + 143; ITEM4_REORG, STALE | rung 0 `Stale@<H0>><next birth>` (the replay's next birth) with the flag true, matching |
| TR-3 `IncludedNoEffect` | ITEM4_SELF_DEALING and ITEM4_FEE_ASYMMETRY, G; ITEM4_CENSORSHIP, G + 144 | rung 0 `IncludedNoEffect@<G or G + 144>`, matching (the height where the bytes hold P0's rung 0) |
| TR-4 E10-s | ITEM4_SELF_DEALING, G | TR-3's line; block G's first transaction the self REGISTER, from its bytes; `SELF_REGISTER` with `index` 0, `height` H0 and G's `block_hash`; the competitor born in G: the judge's replay bears exactly that self REGISTER at G (no `replay_birth`) *(2026-11-10, J5b verification round)* |
| TR-5 Reorg67 lock | ITEM4_REORG, REORGED and RELEASE | every rung `Refuse:Locked(Reorg67)`, matching, at both turns; both branches replayed; the REORGED turn's raw `reorg` line the reorg the bytes show (no `reorg_seen`); `REORG` with the run's `depth` and the replaced G as `invalidated` |
| TR-6 Class T release, then `Stale` | ITEM4_REORG, RELEASE and STALE | the RELEASE turn's raw `released` line `reason:Reorg67;step6:Some(NotPerformed)` (`release_class`); one `ITEM4_L0_RELEASE` with `step` `RELEASE_REORG67_TEST_ONLY`, that `released`, a `procedure_sha256` and `chains`; the release turn's `ITEM4_L0_OBSERVE.procedure.mark` `RELEASE_REORG67_TEST_ONLY`; the STALE turn's rung 0 `Stale@…`, matching |

**The record** (`BITAGI_CT_ARDR_JUDGEMENT_V1`, `item` the experiment), labels `CLASS_T`, `REGTEST`, `JUDGE_RECORD`,
`J5_ITEM4_RUN` (and `EXPLORATORY_NOT_A_VERDICT` outside CONFIRMATORY), `judge.unit` `J5`, `replay` (FINAL) and
`replay_replaced`, and:

| Key | Value |
|---|---|
| `plan` | scenario, run, depth, the project seat and kind, seats, bidders, fees, p_0, f_0, draws, feerates, the asymmetric plan (median, factor and its `source` DRAFT, feerate, fee, `cap_exceeded`), `after_g`, increments and i, ladders, released ks, turns, the not-run list, the censor window |
| `run_shape` | the log's unit state and code, RUN_END status and phase, truncated, killed, chain tip, stale blocks, the replaced branch's heights, other stale blocks, rejected blocks, `funding_problems` *2026-11-11 (045b :1090, section 29): and `collection_code`* |
| `gate` | block G's height and hash, the re-derived code and seats, misses, each seat's last released rung, the releases, the candidates in G, the winner and its source, the scenario facts (`self`, `asymmetric`, `censor`), `reorg`, the L0 facts (section 21's) |
| `labels_judged` | `source` (`RAW_WORKER_LINES` or `NOT_APPLICABLE_STANDIN`), `next_birth_source` (`REPLAY`, `CORE_REPLAY_UNVERIFIED` with `--no-replay`, `CORE_REPLAY_UNVERIFIED_NOT_REPLAYED` when a replay was asked for but FINAL has no block G), `release_mark`, per planned turn `turn`, `phase`, `height`, `branch`, `block_hash`, `judged`, `reason` (`NOT_REACHED`, `NOT_THE_PLANNED_TURN`, `RAW_LINE_ABSENT`, `NEXT_BIRTH_UNKNOWN`, `RAW_LINE_MALFORMED` on a judged turn), `malformed`, per rung `{k, observed, expected, match, differs}`, `released` (reorg), `match`; `label_line`; `release`; `judged_turns`; `complete` |
| `observation` | the row `experiment` reads: `observation_id`, `scenario`, `state`, `code`, `code_source`, `code_reproduced`, `code_seats`, `depth`, `project_seat`, `labels` (`JUDGED`, `NOT_APPLICABLE_STANDIN`), `label_judged`, `label_mismatch`, `nogo_evidence`, `complete`, `judged_turns`, `planned_turns`, `mismatch_turns`, `driver_label_check`, `driver_label_disagreements`, `project_born`, `winner`, `mined_losing` (`A`, `C`, `l0_A`, `l0_C`), `replaced_winner`, `release_class`, `not_run`, `transitions`, `mismatches`; *2026-11-10 (A, J5b)*: `min_transitions` (the listed TR ids the run reaches, below) |
| `outcome` | `NOT_A_VERDICT_PER_RUN`, empty `nogo` and `not_established` *2026-11-11 (045b :1090, section 29): and `verdict`, as POOL; the expected and observed labels are per rung, in `labels_judged`* |

## 25. The item-4 experiments and item 4 (J5)

`experiment --experiment ITEM4_<S>` reads the policy (as `item4`), the listed dispatches' collections and the `item4`
records, as section 22 does: a unit has `gates` null, a record's row is its `observation` (`RECORD_SHAPE`, with
`OBS-<e><unit.run:07>`, the observation's `scenario` the experiment, a run below 50, no NO-GO evidence without a
mismatch, and no plan field in a label-judged or NO-GO-evidence row). CONFIRMATORY needs 045b's 50 runs
(`POLICY_ITEM4_RUNS`). A unit not dispatched or BEFORE_START is missing (decision 7). The unit state is the
collection's (a label-judged FAILED run is EXCLUDED there and in its record: no `RECORD_DISAGREES`).

A started unit with no record is refused `RECORD_MISSING` (exit 3) when its collection state is OBSERVED, its code is
a driver label-check code (`ITEM4_LABEL_MISMATCH`, `L0_RELEASE_NOT_REORG67`) or its `exit` is not null (its driver
ran, so the slice holds its raw log; ARV1 section 13). Such a run is judged from its raw log and is never an exclusion
on the collection's word (045b :1084's note; A's decision on the J5 check, P1-1). Only a started unit whose driver
never ran stands on its collection. An item-4 unit always carries `exit`, null or an integer (`COLLECTION_SHAPE` when
it is missing or of another type; A's re-check, P3-3). A per-run refusal (for example a raw log cut by a kill,
`RAW_LOG_JSON`) therefore blocks its sub-scenario's `experiment` with `RECORD_MISSING` by design (fail closed); A then
reads that log and either re-runs the judge after a tool fix or opens a finding for the driver (A's re-check, P3-4).

**The sub-scenario's outcome** (045b :383, :524, :1084 and its note; A's Q4, Q5).

| Rule | Result |
|---|---|
| a run that is NO-GO evidence (label-judged with a mismatch, or stopped partway after a judged turn mismatched) | NO_GO `ITEM4_MISLABEL` |
| runs that are neither label-judged nor NO-GO evidence (missing, EXCLUDED, an OBSERVED stand-in or one whose turns could not all be judged) above 5 of 50 (the same share of another N) | NOT_ESTABLISHED `TEN_PERCENT_RULE` (the sub-scenario is not run) |
| no label-judged run | NOT_ESTABLISHED `NO_JUDGED_GATES` (not run) |
| (J5b) a transition the inventory lists for the sub-scenario that no label-judged run reaches (045b :1279 and its dated line) | NOT_ESTABLISHED `TRANSITION_NOT_REACHED` (`item4.min_transitions.unreached` names the TR ids) |
| order | NO_GO before NOT_ESTABLISHED (a deterministic tooling defect, as item 1's order, :1086) |

A label-judged run counts as judged whether its labels match or not; it is never an exclusion (A's Q1).

The minimum transitions (J5b, 2026-11-10; A's Q1 on #719) are counted here, per sub-scenario over its label-judged
runs, because only `experiment` sees every run; `item4` reports one run's reach (section 24). Each listed TR needs one
reach (`ITEM4_MIN_REACH`), from any one run; no run needs all of them, and a run that is not label-judged adds none.
The rule binds item 4 only, per sub-scenario; items 1 and 2 and the pool take none (the inventory's scope rule). With
no judged run every TR is unreached, so `TRANSITION_NOT_REACHED` stands beside `NO_JUDGED_GATES`; `item4-outcome`
carries it as `TRANSITION_NOT_REACHED:<S>`.

**Reported beside it** (never judged; A's Q12, 045b :536): the project win rate over the judged runs and over every
started run; mined losing count, weight and fee by ledger (all seats, L0) over the judged runs; a reorg sub-scenario's
replaced winners by depth (runs, replaced, the label line's end states) and the row label "release: Class T test step"
(045b :1069); the not-run cases; the transitions reached (runs per transition); the driver exclusions the judge did not
reproduce; the driver label-check disagreements; the stand-in runs; the exclusions by code.

**The record** is section 20's with labels `CLASS_T`, `REGTEST`, `JUDGE_RECORD`, `J5_ITEM4_EXPERIMENT`, `judge.unit`
`J5`, `registered.gates_per_run` 1, `gate_counts` null (J3's generic gate count would contradict the `item4` block's
own count; A's decision on the J5 check, P3-2), `item2` null and `item4`: `scenario`, `runs`, `judged`,
`nogo_evidence_runs`, `nogo_evidence_partial_runs`, `missing_or_excluded`, `limit`, `over_10_percent`,
`label_mismatch_runs`, `label_judged_failed_runs`, `win_rate`, `mined_losing`, `replaced_winners`, `release_label`,
`not_run`, `transitions`, `driver_exclusions_unreproduced`, `driver_label_disagreements`, `standin_runs`, `exclusions`,
`outcome`. Every other experiment's record has `item4` null. *2026-11-10 (A, J5b): `item4` also holds `min_transitions` (`required`, `reach` per TR, `min_reach`, `unreached`, `source`).* *2026-11-11 (045b :1090, section 29): the record also carries `verdict`, a view of the `item4` block; its top-level `exclusions` is null (`item4.exclusions` is the tally).*

**`item4-outcome`** reads up to four `experiment` records of the item-4 sub-scenarios (`RECORD_SHAPE` otherwise, and
also when a record's result disagrees with its own lists: NO_GO without a `nogo` code or a `nogo` code without NO_GO,
NOT_ESTABLISHED without a `not_established` code, GO with one, or `item4.nogo_evidence_runs` absent, or not empty
outside NO_GO; A's decision on the J5 check, P3-1). They
must be this judge file's (`RECORD_TOOL`), of the judge's mode and of the 045b file it reads now, and share one policy
and registration (`RECORD_BINDING`); two of one sub-scenario are `ITEM4_RECORD_DUPLICATE`. Item 4 is NO_GO when a
sub-scenario is NO_GO (`ITEM4_MISLABEL:<S>`); else NOT_ESTABLISHED when one is NOT_ESTABLISHED (`<code>:<S>`) or has no
record (`NOT_RUN:<S>`, 045b :383 "any of the four sub-scenarios not run"); else GO. Neither order can give GO while a
sub-scenario is missing. The record `BITAGI_CT_ARDR_ITEM4_JUDGEMENT_V1` has labels `CLASS_T`, `REGTEST`,
`JUDGE_RECORD`, `J5_ITEM4_OUTCOME` (and `EXPLORATORY_NOT_A_VERDICT`), `judge.unit` `J5`, `inputs` (the records'
SHA-256 by sub-scenario, the shared policy and registration, the 045b file), `thresholds`, `scenarios` (per
sub-scenario `present`, `result`, `nogo`, `not_established`), `rows` (:505 and :506 take item 4's outcome, :506 with the
reorg sub-scenario's replaced winners and release label; :499 and :500 `REPORTED_NOT_JUDGED` with each record's mined
losing figures) and `outcome`. *2026-11-11 (045b :1090, section 29): and `verdict`, which the rows :505 and :506 carry too.*

## 26. A's decisions on the J5 plan (2026-11-05)

A #258 issuecomment-6656311995 (A's J5 decisions Q1-Q17 and requests B1-B4), with A's 2026-11-05 update: the 045b
lines for Q2 and Q1/Q4 are notes on :1068 and :1084 (#664 head `f090ca9b`), and Q2 is judged.

1. **Q1.** The unit state stays the collection's; the labels are judged apart from it from the set worker's raw lines.
   A run whose planned turns are all judged, with no plan mismatch, is label-judged, matching or not, never an
   exclusion; a run that stopped partway is NO-GO evidence when a judged turn already mismatches, else EXCLUDED. A
   driver `match` false over host lines equal to 045b is a judged matching run, reported as the driver's defect (A opens
   a finding). The driver change that would write such a run OBSERVED is a later optional B unit.
2. **Q2.** The three sub-scenarios' verdicts, k ≥ 1 rungs and the E10-s `opening_block_missed` are judged, citing
   045b :1068's 2026-11-05 note.
3. **Q3.** The expected case is chosen from the bytes (where P0 sits, the replay's birth, the turn's branch); plan field
   `winner` requires the born seat's role to be the scenario's adversary.
4. **Q4.** The 10% rule per sub-scenario (more than 5 of 50); over it, or with no judged run, the sub-scenario is not
   run and item 4 NOT_ESTABLISHED (045b :1084's note).
5. **Q5.** NO_GO before NOT_ESTABLISHED inside a sub-scenario.
6. **Q6.** `item4`, `experiment --experiment ITEM4_<S>`, `item4-outcome`.
7. **Q7.** Stand-in logs in EXPLORATORY only (`NOT_APPLICABLE_STANDIN`); CONFIRMATORY `RAW_LOG_ITEM4_STANDIN` (exit 6).
8. **Q8.** Control-row logs are not judged yet (their turns are `l0_turns`); B3's `RUN_START.l0_control` is optional;
   no pairing.
9. **Q9.** The REORGED turn's `reorg` line is plan field `reorg_seen` until 045b states it; the `released` value is
   judged (045b :1068).
10. **Q10.** The existing fields are CONFIRMATORY's release mark (`ITEM4_L0_RELEASE.step`,
    `ITEM4_L0_OBSERVE.procedure.mark`), else `RAW_LOG_RELEASE_MARK` (exit 6); B confirms them in the lift unit (B1).
11. **Q11.** `ITEM4_ASYM_FACTOR` 10 cites :541, `source` DRAFT until F15.
12. **Q12.** Item 4's mined-losing figures are reported only, under (ㄱ) and (ㄷ); (ㄷ)'s "every ladder" is item 2's.
13. **Q13.** Each run records the transitions it reaches; the gate waits for J4b's mechanism. *2026-11-10 (A, J5b; A's Q1 on #719): the gate is J5b's (045b :1279's frozen dated line makes it item 4's judge stage): per sub-scenario in `experiment` (section 25), each run reporting `min_transitions` (section 24).*
14. **Q14.** `--no-replay` (EXPLORATORY): the next birth from `CORE_REPLAY`, `UNVERIFIED_NO_REPLAY`; CONFIRMATORY
    refuses it (`REPLAY_NOT_BUILT`).
15. **Q15.** The first real-log cell is LATENT (`RealItem4Logs`, skipped unless `BITAGI_ARDR_ITEM4_REAL_LOGS` names a
    folder of B's logs, B4).
16. **Q16.** No workflow wiring in J5; J4b owns the generalization.
17. **Q17.** A `SCENARIO_NOT_RUN` list other than 045b :1066-1067's is plan field `not_run`.

Readings the plan left open, as A settled them on the J5 check (2026-11-05, P1-P3). The release mark is required
whenever the run went past the planned release turn (a later turn or RUN_END DONE), and every mark present must be
`RELEASE_REORG67_TEST_ONLY`, so a CONFIRMATORY reorg run the driver stopped inside the release turn
(`L0_RELEASE_NOT_REORG67`) is judged, not refused, while one that went on without its mark is refused. The
`ITEM4_L0_RELEASE` step is required from the point the driver writes it (after the STALE turn's checks: RUN_END DONE
or an `ITEM4_L0_LABEL_LINE`), not from the STALE turn itself, which narrows A's wording to the ARV1 section 25 order
(the re-check found it acceptable; its optional tightening is left as is). A line of 045b's label line that is there
but not in its form is a mislabel (the turn is judged and does not match): `labels` and `flags` in every sub-scenario,
`released` in a reorg run only (A's re-check, P2). A malformed `reorg` line is a wrong one, plan field `reorg_seen`, in
every sub-scenario (as Q9). Only an absent line, or a stage that did not complete, leaves the turn unjudged. A run
that is not whole (section 24: neither DONE nor with every planned turn) is not given absence fields but keeps every
contradiction field, so its NO-GO evidence needs the same clean plan as a whole run. An item-4 unit the driver ran, or
ended on its own label check, needs its record (`RECORD_MISSING`; a per-run refusal blocks the sub-scenario until A
acts, section 25). An `L0_LABELS`, `ITEM4_LABELS` or `ITEM4_L0_OBSERVE` line's own `labels` stands in the envelope's,
and no other event's does (ARV1 section 2 :75-80, since B-J5Z; J4a's `L0_LABELS` lines had the same latent refusal).
One reading is kept from the plan and flagged for A: a `labels` or `flags` line that does not parse in a turn the
driver accepted stays `RAW_LOG_ITEM4_LABELS` (the driver parsed it, so the log contradicts itself).

## 27. The judge workflow's ITEM2 and item-4 wiring, dispatches that declared nothing, the listing filter (J4b)

2026-11-10. A's J4b scope (section 15): sections 16 (P3-2, P3-8, Q6, Q8), 18 and 20; ARV1 section 13 (D-1); 045b
:571-580 (fixed N, each unit dispatched once) and :501. Tests: `tests/claude_track/test_ardr_judge_workflow.py`
(WorkflowFile's J4b cells, JudgeStepPlumbing, UndeclaredReads, Item2Reads, Item4Reads, Item2Unpacked,
UndeclaredExperiment, RunQuery).

**Experiments.** The judge workflow's `experiment` input takes ITEM1, POOL, ITEM2, ITEM4_SELF_DEALING,
ITEM4_FEE_ASYMMETRY, ITEM4_CENSORSHIP and ITEM4_REORG (`WORKFLOW_EXPERIMENTS`; `artifacts` and `unpack` take the same
`--experiment` values). The Check-the-inputs step's `case` gives each its per-unit command, `item1`, `pool`, `item2` or
`item4`, and refuses anything else (`EXPERIMENT_NOT_A_CHOICE`). Only an ITEM1 declaration names a method policy (the
collector's `check_declaration`); POOL, ITEM2 and item-4 declarations name none (`RUN_DECLARATION`). Every unit but an
ITEM1 one is judged with POOL's line (the policy at the run's commit, the raw log, the run's collection, the mode, the
registration in CONFIRMATORY, the built worker), ITEM1 keeping its method policy and D2-2 file; then `experiment
--experiment <E>` runs over every listed run (sections 20, 22 and 25). The item-4 wiring is that same line (A's Q16):
`item4` reads the sub-scenario from the raw log, whose collection entry must be the dispatch's (`COLLECTION_UNIT`
otherwise). `item4-outcome` is not in the workflow: one judge dispatch judges one experiment, so item 4's outcome is a
separate call over the four sub-scenarios' experiment records (this judge file's, `RECORD_TOOL`).

**A listed dispatch that declared nothing** (section 16 P3-2; B's `prior_declaration` rule, ARV1 section 13 D-1).
A run whose artifact listing names no `ardr-declaration`, no `ardr-collection` and no `ardr-slice-<n>` declared
nothing: `artifacts` gives no download and `declared` false, and the token step saves its attempt-1 jobs listing
(`GET actions/runs/<id>/attempts/1/jobs?per_page=100`, `jobs.json`). `unpack` accepts such a run only when that listing

- is one page of every job (`total_count`, at most 100), each of this run (an integer `run_id`) and of attempt 1, each
  name once, each with its steps (else `RUN_JOBS_LISTING`, exit 3);
- shows the plan job (`ARDR dispatch plan (main only, slice budget, re-dispatch rule)`, which a test pins to the
  campaign file) not listed, or completed with a conclusion other than success;
- shows no other job with a step that may have run: any step but one queued, pending, waiting or completed skipped
  (the collector's `step_ran`), whatever the job's name or `started_at`.

Otherwise the run is `RUN_COLLECTION_MISSING` (exit 3), as before. The rule is the collector's read over every job, not
only the slice jobs: a unit runs only inside a slice job, which needs the plan, and the collect job runs only after a
successful plan, so in such a run every other job is skipped or never started, and a renamed job cannot slip through.
Like the collector's, it relies on artifacts not being deleted (an expired one is listed and refused,
`ARTIFACT_LISTING`; a deleted one is not listed). An accepted run makes the new `--out` directory empty and prints
`declared` false, no policy and no unit. The judge step then reads nothing at its commit and passes its folder to
`experiment` as `--undeclared-run`, which re-checks it from `run.json`, `artifacts.json` and `jobs.json` (`artifacts`'
run checks, the listing, the jobs listing; `RUN_DECLARED`, exit 2, when the listing names a declaration, collection or
slice artifact), counts it as a listed run in the run-list check (section 20: completed, of the experiment, on main's
history, and in CONFIRMATORY at or after the bound) and adds no unit: its units are those of no dispatch, missing
(decision 7). `--undeclared-run` needs the listing and the history (`RUN_LIST_REQUIRED`); one run given twice, by
collection or as `--undeclared-run`, is `COLLECTION_DUPLICATE`; collections and such runs are at most 20 together
(`RUN_IDS`). The record's `inputs.undeclared_runs` lists each with the SHA-256 of its three files. Such a run is the
first attempt, or a later attempt in CONFIRMATORY only: the campaign's plan refuses every CONFIRMATORY attempt but the
first before it uploads a declaration (`RUN_ATTEMPT_NOT_FIRST`), so no later attempt can observe and attempt 1's jobs
speak for the run; an EXPLORATORY later attempt could plan and observe, and only a deleted declaration would hide it
(`RUN_NOT_JUDGEABLE`). A run with a declaration and no collection (its collect job failed) is RECOLLECT's and stays
`RUN_COLLECTION_MISSING` (Q6). The experiment's policy is the first declared run's; with no declared run the judge
step fails (`NO_DECLARED_RUN`, stderr).

**The listing's `created` filter** (section 16 P3-8). The dispatch listing's query is `run-query`'s, computed in the
Check-the-inputs step before the token: `event=workflow_dispatch&branch=main&per_page=100`, and with a bound
(CONFIRMATORY requires one) `&created=%3E%3D<YYYY-MM-DD>`, the UTC date two days before the bound. GitHub's 1,000-run cap
(`RUN_LIST_CAPPED`) then counts the runs created from that date, not every dispatch since the workflow began. The filter
is a margin only: read at its day's start or end in any time zone from UTC-12 to UTC+14, its cut stays before the bound,
and `experiment` applies the exact bound to the saved runs as before (`RUN_LIST_INCOMPLETE`, `RUN_LIST_DISAGREES`).
EXPLORATORY's bound is the first listed run's creation, unknown before the listing is read, so its query has no filter.

**Not changed in J4b.** RECOLLECT (Q6): a recollected run is still not read (`RUN_COLLECTION_MISSING`, fail closed).
POOL's funding (Q8): reported, not an exclusion; no real EXPLORATORY POOL log has shown its structural
`funding_problems` empty, so A's decision has no input yet. The minimum transition list binds no item-2 run (section
15). ITEM3 has no judge (J6).

**The :501 NO-GO: what it needs (investigated, not built).** 045b :501's threshold is "any project replacement refused
by Node A/B `testmempoolaccept` despite meeting 045a §1.3 item 5" (the fee step, 045a :130-135). Line numbers below are
main `3ac1c20b`'s.

1. Judging it from the log needs an L0 log change. `L0_RUNG_TEST` (ARV1 :1980; `tools/claude_track_ardr_l0.py`
   `_rung_test` :1127-1148) holds each node's answer but no field saying the rung it replaces was in that node's
   mempool when the node answered; item 2's synthetic `TESTMEMPOOLACCEPT` has one (`replaces_in_mempool`, ARV1 :1661;
   `tools/claude_track_ardr_item2.py` :759-760). Without it a refused replacement (the NO-GO) cannot be told from a
   test whose predecessor was not there. `when` `BEFORE_RELEASE` is documented as "rung k − 1 in both mempools" (ARV1
   :2307), and the L0 seat checks that right before the test (`_unsent(self.floor_hash, replaces)`, :1106-1108,
   `L0_FUNDING_SPENDER`), but in the log it is a driver claim, not a fact. `CHARGED_NOT_RELEASED_BEFORE_G` tests a
   rung whose predecessor was never released (it would replace the last released rung, not rung k − 1), and the code
   checks only that both tips are G − 1.
2. The refusal :501 names is not kept either. A released rung refused by `testmempoolaccept` is then sent; its step 8
   fails (the rung is in neither mempool, `L0_RUNG_NOT_IN_MEMPOOL`, or the send stage's own error), the L0 thread
   stops, and `L0Seat.finish` re-raises that error (`self._raise()`, :664) before it writes any `L0_RUNG_TEST` line
   (:675). The run ends FAILED (EXCLUDED, counted under the 10% rule) without the answer. A NO-GO needs both:
   `replaces_in_mempool` per node on `L0_RUNG_TEST`, and the rung tests written on an attempt that fails.
3. The fee-step half is judged today: the judge recomputes the L0 ladder from `p_0`, `b`, `i` (the larger of the nodes'
   `incrementalfee`, `SCHEDULE.increments`) and 213 vB and checks it everywhere (`l0_fee`, section 21); 045b :537's
   ladder meets item 5 by construction.
4. 045b does not make :501 part of item 2's verdict: item 2's outcome is the :381 row (045b :381; section 22; A's J4a
   decision 2). :501 is a section 4.5 row with its own NO-GO; every such row is measured and reported, "a row not
   measured makes the ARDR NOT_ESTABLISHED" (045b :489-492), and no row may stay discretionary after collection
   (:508-511). Its own NOT_ESTABLISHED cell is "not reported".
5. If it stays `REPORTED_NOT_JUDGED`, item 2's CONFIRMATORY outcome (the :381 row) does not change, and the record says
   :501 was measured but not judged. The ARDR then cannot state the :501 row as passed (045b :490-491, SSoT:2851;
   CT-P7-001 refuses a NOT_ESTABLISHED item, 045b :355-357): unless A records another reading, that row is not
   established for the ARDR. A decides before the registration, since a driver or L0 change after it needs a new
   registration.

## 28. The :501 NO-GO from the rung tests (J4c)

2026-11-10. Builds what section 27 found missing, once L0-501 (ARDR_RUN_V1's addition to section 22, at the end of
that file) logged it: each node's `replaces_in_mempool` on `L0_RUNG_TEST`, and a failed attempt's rung tests. Placed at
the end of this file so that every line above keeps its number; the places above that describe :501 carry a dated
pointer here. Tests: `tests/claude_track/test_ardr_judge_item2.py` (Row501, and Item2Experiment's :501 cells) and
`tests/claude_track/test_ardr_judge_item4.py` (`test_l0_facts_without_501_lists`). *2026-11-11 (finding #788): amended at the places marked below and by the parts after "Not changed" at the end of this section, which also name the cells.*

**The reading.** 045b :501's NO-GO is "any project replacement refused by Node A/B `testmempoolaccept` despite meeting
045a §1.3 item 5". Per run, among the attempt's counted rung tests (section 21's rule: rows of the judged attempt
only, the first valid row of each charged k ≥ 1, with that rung's charged txid), a rung k is a NO-GO rung when

- its `when` is `BEFORE_RELEASE` (a `CHARGED_NOT_RELEASED_BEFORE_G` test is not a replacement the attempt made: the
  rung was never sent, and what it would replace is the last released rung, not k − 1; it is ignored here); *2026-11-11 (finding #788): ignored only when rung k has no `RELEASE` line. Such a line of a rung that has one, and a line whose `when` is neither of the two values, are read at the end of this section ("Lines the judge cannot resolve").*
- it meets item 5, read from the judge's own values and never from the absence of `l0_fee` (an attempt that FAILED at
  step 8 has no `RELEASE` lines, so `l0_fee` is set in exactly the runs this row is for): the judge's L0 ladder
  (section 21) equals `L0_LAUNCH_START.fee.ladder`, whose `increments` are `SCHEDULE`'s; `L0_SET_CHARGED.fees` is that
  ladder and the attempt's one charged row of k has `wallet_fee_sat` f_k and `wallet_vsize` 213; and f_k − f_(k−1) is
  at least max(1, ⌈i × 213 / 1000⌉), the step of 045b :537 with i the larger logged `incrementalfee`; *2026-11-11 (finding #788): this condition holds two questions, whether the judge can establish item 5 from its own values (the equalities) and whether item 5 is then met (the step). The end of this section tells "item 5 not met" from "item 5 not establishable by the judge". The equalities also cover rung k − 1: its one charged row and, where the log holds it, each node's fee in its `L0_ADMISSION`.*
- and Node A or Node B (either) answered `allowed` false with `replaces_in_mempool` true: the rung it replaces was in
  that node's mempool when the node refused it. *2026-11-11 (finding #788): section 21's rule in the parenthesis above reads "the first row of each rung k ≥ 1 of the judge's ladder, of the judged attempt, whose txid is a charged txid of that rung" (any charged row of the rung), and a line that is not counted is no longer silent: the end of this section.*

A refusal (`allowed` false) under the first two conditions whose node has no `replaces_in_mempool` bool (missing, null
or another type) cannot be told from a test with nothing to replace: that rung is undecided. A refusal with the field
false is neither (that node had no predecessor; reported in `rung_tests_refused` only). An untested rung (`nodes`
null) has no `allowed` and enters neither list: no test is no refusal evidence (A's decision on J4c), and it is no
measurement either. *2026-11-11 (finding #788): a `BEFORE_RELEASE` refusal of a rung whose item 5 the judge cannot establish is undecided too, with `replaces_in_mempool` true or with no bool there. A node answer without a bool `allowed` on a tested line (`nodes` not null) is not an acceptance: unless that node's `replaces_in_mempool` is false, the line is unresolved (the end of this section; its one exception is a counted `CHARGED_NOT_RELEASED_BEFORE_G` line of a rung without a `RELEASE` line, in an attempt that has L0 `RELEASE` lines).*

**Per run (`item2`).** `gate.l0` gains `rung_refusals_501` (the NO-GO rungs) and `rung_refusals_501_undecided`, each a
list of `{k, roles}` (`roles` the nodes, `A` before `B`, in k order of the log); `observation.traffic` carries both
lists beside `l0_rung_tests_refused`, empty without the L0 seat, and `rung_tests_before_release`: the counted
`BEFORE_RELEASE` tests with at least one node's answer (0 without the seat). The run's state, its fields and `rung_tests_refused`
are unchanged; reading `allowed` excludes nothing. Every run with an L0 attempt is judged this way, FAILED and EXCLUDED
included: `item2` builds the L0 facts and the observation for every run it reads, and the judge workflow judges every
unit with a raw log (section 27), so a FAILED attempt's record reaches the experiment. A unit without a record (no raw
log) has no rung test to read. Item 4 reads its L0 facts through the same function but has no `BEFORE_RELEASE` test
(section 24); its records are as before (the two lists are item 2's only). *2026-11-11 (finding #788): an entry of `rung_refusals_501_undecided` is `{k, roles, why}`. `why` is `REPLACES_UNKNOWN` for the rung above (item 5 met, no `replaces_in_mempool` bool) and `ITEM5_UNKNOWN` for a refused rung whose item 5 the judge cannot establish (`roles` the nodes that refused with the field true or with no bool). An entry of `rung_refusals_501` stays `{k, roles}`. `gate.l0` and `observation.traffic` also hold `rung_tests_unresolved`, the number of rung-test lines the judge cannot resolve. A unit without a record is no longer the same as one without a raw log: `experiment` needs the record of an ITEM2 unit whose driver ran.*

**The row (`experiment --experiment ITEM2`).** :501 becomes a defect row (NO_GO first, as :498; A's J4a decision 2),
summed over every unit with a record whatever its state: NO_GO `PROJECT_REPLACEMENT_REFUSED` with any NO-GO rung;
otherwise NOT_ESTABLISHED with `TEN_PERCENT_RULE` (as the other rows), `RUNG_TEST_REPLACES_UNKNOWN` with any
undecided rung, and `NOT_MEASURED` (:499's code) when no record holds a counted `BEFORE_RELEASE` test (A's decision on
J4c: no replacement traffic was measured, and 045b :489-492 makes an unmeasured row NOT_ESTABLISHED; the sum is
`project_rung_tests_before_release`); otherwise GO. The reported figures stay as they were (replacements, cancellations 0, per gate, share
of handed-off rungs, the project's replacements, `project_rung_tests_refused_all_started`), and the row adds
`project_replacements_refused` and `rung_tests_replaces_unknown` (each entry `{k, roles, run}`, at most 100 shown)
with their counts. An `item2` record's two lists are read strictly (`RECORD_SHAPE`: a list of objects with exactly `k`
1-7 once and `roles` `[A]`, `[B]` or `[A, B]`; `rung_tests_before_release` an integer ≥ 0). Item 2's outcome stays the :381 row's (045b :381). *2026-11-11 (finding #788): the undecided rungs whose `why` is `ITEM5_UNKNOWN` have their own code and list. NOT_ESTABLISHED is also `RUNG_TEST_ITEM5_UNKNOWN` with any such rung, listed after `RUNG_TEST_REPLACES_UNKNOWN`; that code and `rung_tests_replaces_unknown` are for the `REPLACES_UNKNOWN` rungs only, and both codes may appear together. The row adds `rung_tests_item5_unknown` (at most 100 shown) and `rung_tests_item5_unknown_count`; an entry of either undecided list is `{k, roles, why, run}`. NOT_ESTABLISHED is also `RUNG_TEST_UNRESOLVED` when the sum of the records' `rung_tests_unresolved`, the row's `rung_tests_unresolved_count`, is above 0; it is listed after the two undecided codes and before `NOT_MEASURED`. `RECORD_SHAPE` reads an entry of `rung_refusals_501_undecided` as exactly `k`, `roles` and `why` (one of the two values), an entry of `rung_refusals_501` as before, and `rung_tests_unresolved` as an integer ≥ 0.*

**Not changed.** The threshold table (`thresholds`) gains no :501 entry: the row has no number, and every record,
item 4's included, lists that table, so an entry would change item 4's records. An attempt whose rung tests are not in the log (section
27's cases that remain: a failure after the error check, item 2 failing before `finish`) is read as it is: its counted
tests are those logged, and `l0_attempt` already flags a missing rung test.

**Item 5 not met, and item 5 not establishable by the judge (finding #788).** 2026-11-11. The reading above says "it
meets item 5" once. A rung can fail that condition in two different ways, and they are not the same case:

- **Item 5 not establishable by the judge.** Item 5 compares f_k with f_(k−1), so the judge needs both as values of
  its own. It has them only when all of this holds: the attempt has an `L0_LAUNCH_START` whose `fee.ladder` is the
  judge's ladder and whose `fee.increments` are `SCHEDULE`'s; `L0_SET_CHARGED.fees` is that ladder; rung k and rung
  k − 1 each have exactly one charged row, with the ladder's fee as `wallet_fee_sat` and 213 as `wallet_vsize`; and
  the log holds exactly one `L0_ADMISSION` of rung k − 1, in which each node's `fee` is f_(k−1) (the driver writes
  the released rungs' admissions before the rung tests, in a failed attempt too: ARDR_RUN_V1 section 22). If one of
  them fails, the judge can say neither that item 5 is met nor that it is not; without that admission, or with two,
  it has no single node-reported fee of the predecessor. No other value is read for item 5: a charge base one sat off, for example, is `l0_fee` and
  leaves item 5 established.
- **Item 5 not met.** Every one of them holds and f_k − f_(k−1) is below the step. On the judge's ladder this does
  not happen: `item2_ladder` (045b :537) puts every rung k ≥ 1 at least max(1, ⌈i × 213 / 1000⌉) above rung k − 1,
  with the same i and 213 vB the step is taken from. The comparison restates the formula and stays as a check. A rung
  exactly one step above its predecessor meets item 5.

A counted `BEFORE_RELEASE` rung test that Node A or B refused (`allowed` false) is read as follows. Each cell is per
refusing node, and a rung's entry in a list names the nodes of its cells; one rung can be in both lists.

| Item 5 of the rung | `replaces_in_mempool` true | no `replaces_in_mempool` bool | `replaces_in_mempool` false |
|---|---|---|---|
| met | NO-GO rung (`rung_refusals_501`) | undecided, `why` `REPLACES_UNKNOWN` | neither list |
| not establishable by the judge | undecided, `why` `ITEM5_UNKNOWN` (new) | undecided, `why` `ITEM5_UNKNOWN` (new) | neither list |
| not met | neither list | neither list | neither list |

Before this amendment the two undecided cells of the middle row were "neither list". The refusal was dropped, the run
was EXCLUDED on `l0_fee` and counted once under the 10% rule, and with enough clean runs the row read GO with a
refusal on record (Reviewer RV-184 on #778: `L0_SET_CHARGED.rungs[1].wallet_fee_sat` one sat above the ladder, rung 1
refused by both nodes with rung 0 in their mempools, 199 clean runs). A's decisions on the finding:

- **Undecided, not dropped and not NO-GO.** Such a refusal is evidence the judge cannot weigh. It is not a NO-GO rung:
  045b :501's NO-GO is a refusal "despite meeting 045a §1.3 item 5", and that is what the judge cannot say of it.
- **Both unknown.** When the node also has no `replaces_in_mempool` bool, item 5 and the predecessor are both unknown.
  The reading above already makes "item 5 met, predecessor unknown" undecided, and two unknowns must not read as
  healthy, so this refusal is undecided too. Its `why` is `ITEM5_UNKNOWN` as well: the entry names every node that
  refused with the field true or with no bool, A before B, and does not say which of them lacked the field.
- **No predecessor.** A refusal with `replaces_in_mempool` false stays in neither list whatever item 5 is: that node
  had nothing to replace, so it refused no replacement.
- **The cause is named.** Each entry of `rung_refusals_501_undecided` is `{k, roles, why}`, with `why`
  `REPLACES_UNKNOWN` (item 5 met, no `replaces_in_mempool` bool) or `ITEM5_UNKNOWN` (item 5 not establishable by the
  judge). The row has a code and a list for each: `RUNG_TEST_REPLACES_UNKNOWN` with `rung_tests_replaces_unknown`, as
  before, and `RUNG_TEST_ITEM5_UNKNOWN` with `rung_tests_item5_unknown` and `rung_tests_item5_unknown_count`. One code
  for both would send the reader of an `ITEM5_UNKNOWN` rung to `replaces_in_mempool`, which may be known there. The
  second list is every undecided entry that is not in the first, so no entry can fall between the two.
- **The predecessor** (the non-author review). Until then only rung k's charged row was read, so a refusal of rung k
  was a NO-GO rung even when rung k − 1 had been charged, or admitted by a node, at another fee than the ladder's:
  the mirror of the Reviewer's case, where the nodes may be right to refuse. Rung k − 1's charged row and its
  one admission are now part of "establishable" (the first bullet above), and such a refusal is `ITEM5_UNKNOWN`.

**Lines the judge cannot resolve (finding #788, A's decisions on the non-author review, 2026-11-11).** A rung-test
line that the counting rule did not count, or that carried another `when`, or a node answer without a bool `allowed`,
was silent: no entry and no measurement, so with enough clean runs the row read GO with a refusal in the raw log.
That is the finding's own shape, and it is closed the same way, fail closed.

- **The counting rule** (section 21) reads: the first `L0_RUNG_TEST` row of each rung k ≥ 1 of the judge's ladder, of
  the judged attempt, whose txid is a charged txid of that rung. Any charged row of the rung will do, so two charged
  rows of one rung give the same lists in either order (item 5 is then not establishable; the mismatches can differ
  by `l0_attempt`). The charged txids are those of the log's one `L0_SET_CHARGED` line, also when that line names
  another attempt (`l0_attempt`). Only a counted line is listed in `gate.l0.rung_tests`, counts in
  `rung_tests_refused`, can enter a list and can be a measurement.
- **An open answer.** A node's answer on a line is open when the line was tested (`nodes` not null), the node did not
  answer `allowed` true, and its `replaces_in_mempool` is not false. An untested rung (`nodes` null) has no answer,
  as before; a node without the predecessor in its mempool refused no replacement. A line without the `nodes` key is
  not ARDR_RUN_V1's untested line (section 22 gives `nodes` as the answers or null): it is a tested line with no
  answer, so both nodes' answers on it are open.
- **An unresolved line** is a line with an open answer that is (a) not counted: a row of another attempt, a second
  row of a rung, a k that is not a rung ≥ 1 of the judge's ladder (the launch may have charged more rungs than the
  judge's ladder has), or a txid that is no charged txid of its rung (an attempt without `L0_SET_CHARGED` has none);
  or (b) of a `when` that is neither `BEFORE_RELEASE` nor `CHARGED_NOT_RELEASED_BEFORE_G` (ARDR_RUN_V1 section 22
  has these two); or (c) a `CHARGED_NOT_RELEASED_BEFORE_G` line of a rung that has a `RELEASE` line, which the
  judge's own releases contradict, or of an attempt that has no L0 `RELEASE` line at all: without any the judge
  cannot tell a held rung from a released one; or (d) a counted `BEFORE_RELEASE` line, when the open answer has no
  bool `allowed` (not an acceptance: ARDR_RUN_V1 section 22 makes it the driver's `MISMATCH L0_RUNG_TEST`). In (a)
  to (c) a refusal is an open answer too.
- **The one exception** is a counted `CHARGED_NOT_RELEASED_BEFORE_G` line of a rung without a `RELEASE` line, in an
  attempt that has L0 `RELEASE` lines: it tests no replacement the attempt made and is no evidence, as before. The
  exception is read fail closed (A's decision on the second review round). A line the judge does not count it cannot
  tie to a rung, so that label on it proves nothing and the line is (a). And in an attempt without any L0 `RELEASE`
  line a refused line with that label read GO; it is (c) now. A correct driver writes no such label in an attempt
  that failed at step 8 (its finish stops before the held rungs' tests), but a finish that fails after the rung
  tests, on the budget checks, leaves genuine held-rung lines and no `RELEASE` line: a held rung's line with an open
  answer is then unresolved as well. That is the stricter side, and the unit is EXCLUDED either way.
- **Per run** `gate.l0` and `observation.traffic` hold `rung_tests_unresolved`, the number of such lines (0 without
  the L0 seat; `RECORD_SHAPE`: an integer ≥ 0). A line of (a) to (c) enters neither list and is no measurement. A
  line of (d) stays a counted `BEFORE_RELEASE` test: the node that did answer measures and can put the rung in a
  list, and the line is unresolved besides (one line can give a NO-GO rung and an unresolved line).
- **The row** sums it over every unit with a record (`rung_tests_unresolved_count`). With a sum above 0 it is
  NOT_ESTABLISHED with `RUNG_TEST_UNRESOLVED`, listed after `RUNG_TEST_ITEM5_UNKNOWN` and before `NOT_MEASURED`;
  NO_GO is still first, with the code listed.
- **The unit.** In an item-2 run a `when` outside the two values is `l0_attempt` (item 4 checks its one value,
  section 24), and every line of (a) was `l0_attempt` already, so those units are EXCLUDED and count under the 10%
  rule. (c) and (d) add no mismatch: the unit keeps its state, and the row carries the result.

**What else the row relies on (the same review).**

- **The record of a unit whose driver ran.** `experiment` refuses `RECORD_MISSING` for an ITEM2 unit that has no
  record and whose collection entry's `exit` is not null (its driver ran, so the slice holds its raw log; ARDR_RUN_V1
  section 13), as it does for item 4 (section 25). A FAILED attempt is EXCLUDED in its collection, and its rung tests
  reach this row only through its record. A unit with `exit` null still stands on its collection: its driver did not
  end under the slice tool (it never started, the slice record was lost, or the unit was interrupted,
  `RUN_INTERRUPTED`). Such a unit may have been observed in part, but it has no raw log in the collection, so its
  rung tests do not reach this row; the unit counts under the 10% rule. `exit` itself must be present, and null or
  an integer (`COLLECTION_SHAPE`, section 14, as for item 4): a missing key is not "null". So a judge refusal of the
  raw log of a unit whose driver ran blocks the experiment until A acts, as for item 4.
- **Where the result is.** The row's result is carried only in `item2.rows['501']`. The experiment record's `outcome`
  and the command's exit code are the :381 row's by design (section 22), so they can read GO beside a :501 NO_GO or
  NOT_ESTABLISHED. Whoever assembles the ARDR takes each section 4.5 row from `item2.rows`.
- **What counts as a measurement.** A counted `BEFORE_RELEASE` test of a rung whose item 5 is not establishable
  still counts in `rung_tests_before_release` when a node answered, so such tests alone make the row measured.
- **The unit of an undecided rung.** Reading the answers changes no state and no code. A run with a rung whose item 5
  is not establishable carries `l0_fee` among its mismatches (`l0_attempt` when the launch line is missing), so it is
  not OBSERVED. Its code is `JUDGE_PLAN_MISMATCH:` with the first mismatched field in section 21's order, which can
  be another one (`schedule`, when `SCHEDULE`'s increments are the ones that differ), or the log's own code when the
  driver did not end the run OBSERVED (a FAILED attempt).

**The frozen rule for these cases (045b; the statement finding #788 asks for).** The frozen missing-data rule does
not ask for more than NOT_ESTABLISHED; it asks for less. NO-GO cannot be affirmed under :501's own wording, "any
project replacement refused by Node A/B `testmempoolaccept` despite meeting 045a §1.3 item 5, which is a
ladder-design defect". Each kind leaves one part of that sentence open: for an `ITEM5_UNKNOWN` rung the judge cannot
say "despite meeting 045a §1.3 item 5" on values of its own; for a `REPLACES_UNKNOWN` rung item 5 is met and it
cannot say "replacement"; for a line of (d) it cannot say "refused"; and for a line of (a) to (c) it cannot say that
the line is a test of a replacement the judged attempt made. :1043 treats a plan mismatch the same way: the run "is
EXCLUDED with `JUDGE_PLAN_MISMATCH:<field>`. It counts under the 10% rule and is reported as a driver defect, not as
NO-GO; A opens a finding." (:1043 names block bytes that differ from the frozen plan, ladder fees among them;
`l0_fee` is this judge's field for that rule, section 21, and it is also set from the logged launch, charge and
admission. The finding it asks for is A's to open; the judge reports the entries.) What the frozen rule does ask is
exclusion and the count: :501's missing-data cell is "as above", that is :498's "a gate without a complete mempool
log is excluded and counted"; by :1053 a wallet row, charge base or node fee that differs from the computed f_k
"fails the run (`L0_FEE_MISMATCH`)"; and by :572-574 "exclusions above 10% of an experiment's runs make that
experiment NOT_ESTABLISHED". A unit that is EXCLUDED on `l0_fee` or `l0_attempt` keeps exactly that. The row's
NOT_ESTABLISHED on a single such refusal is this judge's stricter reading. It rests on :490-492, "Class E must not
mark absent evidence as satisfied (SSoT:2851), so every row is measured and reported; a row not measured makes the
ARDR NOT_ESTABLISHED": a refusal the judge cannot weigh is absent evidence for that rung, and the row is not read as
satisfied over it. This holds where the unit stays OBSERVED as well (an answer without the field or without a bool
`allowed`, a mislabelled line); 045b has no missing-data clause for a node's answer, so there the row's result rests
on :490-492 alone.

**Not changed by finding #788.** The other cells of the table; an untested rung; the threshold table; the entries of
`rung_refusals_501` (`{k, roles}`). Section 14 gains no code (the row's codes are not refusal codes); its
`RECORD_MISSING` and `COLLECTION_SHAPE` rows have a dated note each. Item 4's records are as before, with one
exception that follows from the counting rule: in a run with two charged rows of one rung (`l0_fee` already)
`gate.l0.rung_tests` lists the line that names either row's txid, and `rung_tests_refused` counts its refusals.

**The cells** (`tests/claude_track/test_ardr_judge_item2.py`, Row501). The table: `test_observed_run`,
`test_failed_attempt_refused_with_predecessor`, `test_failed_attempt_field_missing`,
`test_failed_attempt_predecessor_absent`, `test_item5_exact_step`, `test_refusal_with_item5_not_establishable`,
`test_item5_not_establishable_other_ways`, `test_item5_needs_the_predecessor`, `test_two_charged_rows_either_order`,
`test_item5_not_establishable_keeps_the_rest`, `test_item5_not_met`. Lines the judge cannot resolve:
`test_uncounted_refusal_is_unresolved`, `test_uncounted_line_answers`,
`test_foreign_and_duplicate_lines_not_counted`, `test_rung_test_when`, `test_charged_not_released_ignored`,
`test_node_answer_without_a_bool_allowed`, `test_untested_rung_is_no_evidence`. The row and the record:
`test_undecided_kinds_in_the_row`, `test_unresolved_in_the_row`, `test_undecided_entry_never_between_the_lists`,
`test_result_is_carried_in_the_row_only`, `test_unit_whose_driver_ran_needs_its_record`,
`test_no_replacement_traffic_not_measured`, `test_record_shape`. Item 4's exception:
`test_item4_two_charged_rows`.

## 29. The requirement verdict and the cause kept (045b :1090)

2026-11-11. 045b line 1090 (section 14.4, frozen; it amends the confirmatory record formats of its sections 4 and 5,
and names the assurance application table's :241, V-01 and V-03) asks three things of the ARDR judge record before
its first CONFIRMATORY verdict: fields named `expected` and `observed`, so that "observed REFUSED, required PASS" can
be written; a value `INCONCLUSIVE`, so that a timeout "is not folded into FAIL or PARTIAL"; and that "A mapping that
folds values keeps the cause." Its dated line of 2026-11-09 says that no format had these fields at the freeze and
that each adds them before its first CONFIRMATORY verdict. The judge carries them from this unit on (A's decisions
of 2026-11-11). 045b is not edited. This section is at the end of the file so that every line above keeps its number;
the places above that describe a record carry a dated pointer here.

No outcome changes. For every input, `outcome`, each row's `result`, every gate and unit state, every count and every
other field are what they were; the new keys are made afterwards, from the finished values.

**The block.** Every record that states an outcome also carries

    "verdict": {"expected": {...} | null, "observed": {...} | null,
                "result": "PASS" | "FAIL" | "INCONCLUSIVE" | "NOT_A_VERDICT_PER_RUN",
                "inconclusive_reason": null | [code, ...]}

- The four keys are those of the XD-1 collection report's `verdict` (`XD1_EVENT_CHAIN_V3.md`), so the two record
  families 045b :1090 names have one shape. One difference: XD-1's `inconclusive_reason` is one string. Here it is a
  list, since an ARDR outcome can have several causes at once.
- `result` is the image of the finished `outcome.result` under one constant mapping, applied last: `GO` gives `PASS`,
  `NO_GO` gives `FAIL`, `NOT_ESTABLISHED` gives `INCONCLUSIVE`, and `NOT_A_VERDICT_PER_RUN` stays
  `NOT_A_VERDICT_PER_RUN`. Nothing else decides it. There is no other value: no `result` is `PARTIAL`, and the judge
  writes no key or value `PARTIAL` of its own. (A cause field below copies a collection's text as the collection
  gives it, so a collection code of that word would show there; no collector writes one.)
- The mapping is a constant of the judge's table (section 4), `VERDICT_MAPPING`, item `ALL`. It cites 045b :1090 by
  the phrase "carries `expected` and `observed` fields", so a 045b whose line 1090 does not carry that phrase is
  refused (`PREREG_CITATION`, exit 6), as for every cited constant. Every record lists it under `thresholds`.
- `inconclusive_reason` is the `not_established` list of the outcome (or row) the block stands beside when `result`
  is `INCONCLUSIVE`, and null otherwise. The causes of a `FAIL` are that outcome's `nogo` codes, as before.
- `expected` is the registered criterion: from the constant table, and where the table below says so from the
  policy's N (`registered.runs`), decision 3 (`EQUAL_TO_EXPECTED_LISTS`), 045b :501 (no refused replacement) or item
  4's list of sub-scenarios. `observed` is what the judge measured: each figure restates a finished field of the
  record, named in the table below. A value the judge did not measure is null, or a fraction in its `undefined` form
  (0/0). It is never a copy of the expected value.
- The block is made in EXPLORATORY and in CONFIRMATORY alike. Outside CONFIRMATORY the record's label
  `EXPLORATORY_NOT_A_VERDICT` qualifies it, as it qualifies `outcome`. (XD-1 differs: its `verdict` is null in
  EXPLORATORY.)
- The block is a view. No state, count or outcome is computed from it.

**Where it sits and what it holds.**

| Record | The block | `expected` | `observed` |
|---|---|---|---|
| `item1` (section 13) | top-level `verdict` | `reports` `EQUAL_TO_EXPECTED_LISTS` (the lists are the record's `expected.reports`; decision 3), `link_recall_min` and `link_precision_min` 1/1 (045b :380), `exclusion_limit` 1/10 (:572) | `evaluated`, `not_evaluated_reason`; `reports` (`missing`, `extra`, `wrong_gate`, as counts), `link_recall` and `link_precision`, each null when the comparison was not evaluated; `gates`, `missing_or_excluded`. A `FAIL` beside `evaluated` false is a D2-2 output that cannot be read (`D2_2_OUTPUT_MALFORMED:<part>`, section 12): its figures are null, and its cause is in `outcome.nogo` |
| `experiment`, ITEM1 (section 20) | top-level `verdict` | item 1's criterion, and `runs`: `registered.runs`, the registered N (without one, in EXPLORATORY, the listed units, as `registered.source` `UNITS_LISTED` says) | `run_results` (`{run, result}` per registered run, in run order; `result` is that run's own record's `outcome.result`, `GO`, `NO_GO` or `NOT_ESTABLISHED`, null without a record), `gates`, `missing_or_excluded` |
| `experiment`, POOL (section 20) | top-level `verdict` | `herfindahl_max` 1/2 (:504), `exclusion_limit` | `herfindahl` (the record's `pool.herfindahl`; `undefined` with no judged gate), `gates`, `judged_gates`, `missing_or_excluded` |
| `experiment`, ITEM2 (section 22) | `verdict` in each `item2.rows[<row>]`; the top-level `verdict` is the :381 row's, as `outcome` is | each with `exclusion_limit`. :381 `private_win_share_max` 1/2, `stratum_limit` 5/50; :498 `candidates` `OBSERVED_EQUALS_PREDICTED`; :499 `project_share_max` 25/100; :500 `project_fee_per_attempt_max` 500000/24; :501 `project_replacements_refused` 0 | :381 `private_win_share`, `qualifying_observed`; :498 `compared` (the release-timing runs it reads included, section 22), `differ_count` (null when no run was compared); :499 `project_share`, `project_attempted_gates`; :500 `project_fee_per_attempt`; :501 `project_replacements_refused` (the count of decided refusals, so a lower bound while `undecided` or `unresolved` is not 0; null when no counted test was measured and none refused), `rung_tests_before_release`, `undecided`, `unresolved`. The lost-run counts that `exclusion_limit` and `stratum_limit` bound are not in the block: they are `item2.missing_or_excluded` and `item2.stratum` |
| `pool`, `item2`, `item4`: one run (sections 19, 21, 24) | top-level `verdict` with `result` `NOT_A_VERDICT_PER_RUN` | null | null |
| `experiment`, `ITEM4_<S>` (section 25) | top-level `verdict` | `mislabel_nogo` `ANY_JUDGED_LABEL_DIFFERS` (:383), `subscenario_limit` 5/50 (:1084), `min_transitions` and `min_reach` (:1279) | `judged_runs`, `matching_runs` (null with no label-judged run), `differing_runs` (the runs with NO-GO evidence, a stopped run's included; null when no run is label-judged and none carries NO-GO evidence), `missing_or_excluded`, `unreached_transitions` |
| `item4-outcome` (section 25) | top-level `verdict`, and the same block in `rows.505` and `rows.506` | `mislabel_nogo`, `sub_scenarios` (the four names) | `sub_scenarios`: each one's `outcome.result` (`GO`, `NO_GO`, `NOT_ESTABLISHED`), null without a record (not run) |

An ITEM1 run's `result` in `run_results` is its own record's, and so holds that run's own 10% rule, which the
experiment replaces by its own (section 20). With more than one registered run (EXPLORATORY only: CONFIRMATORY
registers one), a run that is `NOT_ESTABLISHED` only for its own 10% rule does not make the experiment so, and the
block can say `PASS` beside that run's `NOT_ESTABLISHED`.

Item 2's five rows are not folded into one verdict: 045b states no such rule. So the top-level block of an ITEM2
record can say `PASS` beside any of the rows :498 to :501 that says `FAIL` or `INCONCLUSIVE`, as `outcome` can
(section 28, "Where the result is"). It holds the :381 row's `expected`, `observed` and `result`. Its
`inconclusive_reason` is the record's own `outcome.not_established`: the row's codes as `outcome` lists them, sorted.
Row :498 keeps its older key `observed` (the distribution: mean, p95, max) beside the new block. The rows :499 and
:500 of `item4-outcome` are `REPORTED_NOT_JUDGED` and carry no block.

A per-run record of the pool, item 2 or item 4 states no verdict (045b :545; sections 19, 21 and 24), so its block
has no criterion and no figures. Its expected and observed sides are per observation, under the names they already
have:

- a pool gate: `drawn_producer` (the judge's own draw) beside `producer_tags` and `producer` (read from block G);
- an item-2 run: `observation.predicted_candidates` beside `observed_candidates`; and each node's answer on an L0 rung
  test in `gate.l0.rung_tests`, `allowed` true, false or null, a product reaction kept as an observation apart from
  any verdict;
- an item-4 run: `labels_judged`, where each rung is `{k, observed, expected, match, differs}` and the release line
  and the label line are `{observed, expected, match}`. "Observed `Refuse:Locked(Reorg67)`, expected the same, match"
  is 045b :1090's "observed REFUSED, required PASS".

**Three words on three levels.** No state is added.

| Level | Word | Field | Meaning | Cause |
|---|---|---|---|---|
| one observation (a gate; a run of item 2 or item 4) | excluded, missing | `state` `EXCLUDED`, `NOT_STARTED` | the observation gives no judged value. It is never a pass, and never NO-GO evidence by itself. It counts under the 10% rule (045b :546, :571-574) | `code`; and `run_shape.collection_code`, `units[].unit_code`, `exclusions.by_code` (below) |
| an item, an experiment, a section 4.5 row | NOT_ESTABLISHED | `outcome.result`, a row's `result` | 045b's word (:371-372, :571-574): neither GO nor NO-GO can be stated | `not_established` |
| the requirement verdict | INCONCLUSIVE | `verdict.result` | the same fact in the words 045b :1090 asks for. A block is INCONCLUSIVE exactly when the outcome beside it is NOT_ESTABLISHED | `inconclusive_reason`, the same codes |

A timeout is therefore an excluded or missing observation with its code. It reaches a verdict only through a frozen
rule over lost or unmeasured observations (the 10% rule, `NO_JUDGED_GATES`, item 2's `QUALIFYING_STRATUM_RULE`,
`NOT_MEASURED`, section 28's codes for row :501, item 4's `TRANSITION_NOT_REACHED` and `item4-outcome`'s
`NOT_RUN:<S>`), and then as INCONCLUSIVE with the rule's code, never as FAIL; the observation's own code stays in the
tally and in `unit_code` (below). NO_GO, and so FAIL, needs evidence on judged observations, as before (sections 12,
20, 22, 25 and 28). Section 12's order stands: a defect found on judged gates is NO_GO, so FAIL, also when the 10%
rule holds, and `outcome.not_established` still lists the rule.

**The cause kept.** Before this unit, two folds lost a cause that this unit keeps. A unit the slice killed at its
time limit before `RUN_END`, its last line whole, is `UNIT_TIMEOUT` in its collection, but its judged record read
`RUN_END_MISSING` and did not copy the collection's code. And the ITEM1 and POOL experiment records held the counts of
the lost gates, but no codes. Three fields keep them:

- `run_shape.collection_code` (every per-run record): the collection's `code` of the judged unit, the text as the
  collection gives it, also when it is no code word; null without a collection, or when that code is not text. It is
  a claim, like the other collection data (section 8). It is shown only: no state or count reads it, and the gate
  codes are what they were. For a unit killed before `RUN_END` that has a per-run record they are the log-derived
  code; for a unit killed after `RUN_END` `DONE` (section 8) they are the collection's code as a code word, or
  `UNIT_TIMEOUT` when it is none.
- `units[].unit_code` (the experiment record): the collection's code of the unit, as given, from the dispatch that
  started it; null for a unit no listed dispatch started (`BEFORE_START` everywhere, or `NOT_DISPATCHED`), or whose
  collection gives it no code. It is shown only and feeds no count.
- `exclusions` (the experiment record, top level): for ITEM1 and POOL `{"by_code": {code: count}}`, the code of every
  registered gate that is not `OBSERVED`, tallied over the very rows `gate_counts` counts. So the tally sums to
  `gate_counts.missing_or_excluded`. Each gate counts under the code of the row that gave its state (section 20): the
  record's gate row for a unit with a record, the collection's gate row for a unit that stands on its collection. So
  one tally can hold both vocabularies for one kind of event: a killed unit judged from its record under
  `RUN_END_MISSING`, one standing on its collection under `UNIT_TIMEOUT`. A gate of a unit no dispatch started counts
  under `BEFORE_START` or `NOT_DISPATCHED`, and a gate without a code (absent, null or empty) under `NONE`. These
  three are the judge's own keys, in one namespace with the collections' codes: a collection row whose code is one of
  those words counts under the same key. The tally is null for ITEM2 and item 4, which have their own tallies
  (`item2.exclusions`, `item4.exclusions`).

So a unit killed at its limit before `RUN_END`, its last line whole, and judged from its record shows `UNIT_TIMEOUT`
as its `unit_code` and its `collection_code`, while its gates keep the log-derived `RUN_END_MISSING`, which is the one
the tally counts. The two are never added together. Two causes stay outside the judge's record, on purpose. When the
kill cut the last line of the raw log, the collection itself says `RAW_LOG_TRUNCATED` (ARDR_RUN_V1 section 13), and so
do the gate codes, `collection_code`, `unit_code` and the tally: no field of the judge's record says that the unit was
killed at its limit, and the collection's `exit` 4 is a hint only (a driver that ends 4 on a cut log gives the same).
And a unit that is `BEFORE_START` in every listed dispatch has, in each collection, the code of the reason it never
started (a slice refusal's code, `SLICE_NOT_STARTED`, `SLICE_UNITS_NOT_RUN`), which can differ per dispatch. It is not
copied (`unit_code` is null and the tally says `BEFORE_START`); it is read from the collections that
`inputs.collections` names by SHA-256.

**A refusal line is not a verdict.** `{"code", "exit", "result": "FAIL"}` (section 2) is the command's status. Its
`result` `FAIL` is the refusal line's fixed word (section 2), and its exit code is AGENTS.md section 12's; it is not a
requirement verdict and not in the mapping. A refusal means that no record was made. A consumer reads "no record" as
INCONCLUSIVE with the refusal code as the cause, never as FAIL and never as PASS. The judge's own replay worker running
past its 1,800 s is such a cause. It has its own code now, `REPLAY_WORKER_TIMEOUT` (exit 3), split from
`REPLAY_WORKER_FAILED` (the worker could not start, ended non-zero or wrote no answer), as the driver keeps
`PREREQUISITE WORKER_TIMEOUT` apart.

**Folding into another vocabulary.** A consumer that folds `INCONCLUSIVE` into another vocabulary (for one, the gate
status bundle's `PASS`, `FAIL`, `PARTIAL`, `NOT_APPLICABLE`) carries `inconclusive_reason` with it, and where there is
no record, the refusal code. When a reason is a rule over lost observations (`TEN_PERCENT_RULE`, `NO_JUDGED_GATES`,
`QUALIFYING_STRATUM_RULE`), it also carries those observations' own codes: the tally (`exclusions.by_code`; for ITEM2
`item2.exclusions.by_code`; for item 4 `item4.exclusions`) and the `unit_code` of every unit that is not `OBSERVED`.
An ITEM2 record is folded row by row, each `item2.rows[<row>].verdict`; its top-level block is the :381 row's alone
(section 28). A fold does not erase the cause (045b :1090: "A mapping that folds values keeps the cause"). No such
mapping document exists yet; this paragraph binds the one that is written.

**Read back.** `experiment` refuses (`RECORD_SHAPE`, exit 2) a per-unit record that has no `verdict`, or whose
`verdict.result` is not the mapping of its `outcome.result`. It is `experiment`'s last check of the records it is
given: every older check (`RECORD_TOOL`, `RECORD_BINDING`, `UNIT_DISPATCHED_TWICE`, `RECORD_DUPLICATE`,
`RECORD_MISSING`, `RECORD_DISAGREES`) comes first and refuses what it refused before this unit. So a record another
judge file made stays `RECORD_TOOL` (exit 6), every record made before this unit (none has a `verdict`) included, and
the refusal of a missing or wrong block applies to a record of this judge file. Only `result` is read back:
`experiment` computes nothing from a unit's `verdict` (it reads each unit's `outcome`, as before), and the unit
record is bound by its SHA-256 in `inputs.records`. `item4-outcome` reads each sub-scenario record's `outcome` and
does not read its `verdict` back.

**Not changed.** Every outcome, result, state, code and count; the refusal codes, but for the one split and the
read-back check; section 12's order; the three rules that read evidence inside an excluded run (row :498's
release-timing runs, row :501's records whatever their state, item 4's judged turns of a stopped run); the judge
workflow, which prints and uploads the record and reads no field of it but `unit.run` (`RECORD_UNIT_MISMATCH`). Every
record gains one `thresholds` entry, `VERDICT_MAPPING`.

**The cells.** `tests/claude_track/test_ardr_judge.py` holds every record that a cell of the judge test modules makes
in-process to this section's invariant (`check_verdict`, on the six commands that write a record; the records that the
two `test_command_line` cells make through a child process are checked by those cells, and the records of the workflow
module's bash steps are not checked): the block beside each stated outcome with exactly its mapping, no `PARTIAL`, a
reason list only with INCONCLUSIVE and then the outcome's own codes, figures that restate the record's own finished
fields (`check_figures`: so never the criterion's value, null where the judge did not measure, a whole count), the ITEM1
and POOL tally summing to `gate_counts.missing_or_excluded`, and the cause fields in their places; and the two places
that state an outcome a second time with no block of their own (an item-4 experiment's `item4.outcome`, each
sub-scenario's result in the `item4-outcome` record) equal the outcome they copy. `VerdictInvariant` tests that check
itself. The mapping and its citation: `VerdictMapping`. Item 1: `VerdictItem1` (also the codes a unit killed at its
limit gives), `Reported.test_late_report`, `Reported.test_link_miss`, `ExperimentItem1.test_verdict_and_causes`,
`test_go_and_nogo_follow_the_run`, `test_n13_nogo_first_with_the_10_percent`, `test_the_10_percent_is_the_experiments`,
`test_the_tally_keeps_the_whole_code`. The pool and the cause fields: `VerdictPool`,
`Experiment.test_redispatch_after_before_start_counts_once`. Both modes:
`ConfirmatoryReplay.test_verdict_is_the_same_in_both_modes`, `PoolReplay.test_confirmatory_pool_record`,
`ExperimentItem1.test_a_confirmatory_experiment_carries_the_same_block`,
`VerdictPool.test_a_confirmatory_experiment_carries_the_same_block`. The worker's timeout:
`WorkerProcess.test_timeout_has_its_own_code`. The read-back check: `Experiment.test_malformed_collections_and_records`,
`Experiment.test_read_back_is_the_last_record_check`, `ExperimentItem1.test_read_back_of_every_pair`. Item 2
(`test_ardr_judge_item2.py`): `Item2Experiment.test_verdict_per_row`, `test_read_back_of_an_item2_record`,
`test_row_498_figures`, `test_row_501_figures`, `test_a_confirmatory_experiment_carries_the_same_blocks`,
`Item2Confirmatory.test_clean`, `Row501.test_verdict_of_a_line_the_judge_cannot_resolve`,
`Item2EndToEnd.test_records_from_item2`, `Item2EndToEnd.test_a_run_killed_at_its_limit`. Item 4
(`test_ardr_judge_item4.py`): `Item4Experiment.test_verdict_of_a_sub_scenario`, `test_read_back_of_an_item4_record`,
`Item4Outcome.test_verdict_of_item_4`, `Item4EndToEnd.test_records_feed_experiment`,
`Item4EndToEnd.test_a_run_killed_at_its_limit`.

## 30. L0's p_0 after FD-CT-133, the experiments a registration covers, and the CONFIRMATORY record cell

*Dated section 2026-11-12 (A; FD-CT-133, finding #807, A's design issuecomment-6810795838 and answers
issuecomment-6811277603; B4-80's unit in the same train). The judge is A's, so a Reviewer reads it before its MERGE-GO
(card B5). Class T Regtest only. Not a GO.*

**The p_0 rule.** FD-CT-133 replaces 045b :1053's `p_0 = ⌈2.5 × b⌉` (`CEIL_2_5_B`) for the L0 seat with
`MAX_P0_TWO_RUNGS`: the largest integer p_0 ≥ 2b whose 045b :537 ladder at i = 0 (v = 213) has two rungs. From 2b up
r_2 ≥ 4.5b, so no rung 2 fits, and f_1 never falls as p_0 rises, so this is the last p_0 whose rung 1 fits under the 4b
cap; its rung 1 is the cap fee floor(4b·v/1000). b = 3000 gives 8000 and [1704, 2556]; b = 6000 gives 16,000 and
[3408, 5112]. `l0_p0(b)` is the judge's own binary search over its own `item2_ladder` (not the bidders' code; the cross
check `test_ardr_judge_item2.LadderCrossCheck` compares the two for b 4 to 3199 and both refusals). A b with no
two-rung p_0 from 2b (b 1-3) is `L0_P0_NO_TWO_RUNGS`; a b that is not a positive int is `L0_P0_INPUT` (exit 2 both).

- Frozen 045b is not edited. The constant table's `L0_P0_RULE` row now holds `MAX_P0_TWO_RUNGS` and still cites 045b
  :1053 by its phrase, as the value it replaces: the row carries `amends` {`value`: `CEIL_2_5_B`, `by`: `FD-CT-133`},
  and every record's `thresholds` entry for it carries the same `amends` object. A 045b whose line 1053 lacks the phrase
  is still `PREREG_CITATION`.
- `ITEM4_SELF_FEE_FLOOR_B` follows the same p_0 (one source for items 2 and 4, design section 5): the self REGISTER's
  600 sat is strictly below the project's rung 0 from b = 1058 (b 1057 gives 600), so the row holds 1058 with `amends`
  {1127, FD-CT-133}, citing :1065's phrase as before. `POLICY_ITEM4_SELF_FEE` reads `l0_p0`, so it moves with it.
- A CONFIRMATORY `l0_seat` (item 2 or item 4) must carry `p0_rule` `MAX_P0_TWO_RUNGS` (`POLICY_L0_VALUES`
  otherwise); the frozen first policy's ITEM2 seat (`CEIL_2_5_B`) is refused by that rule, which is why the first
  registration leaves ITEM2 out (below). `RAW_LOG_L0_SOURCE`'s `p0_rule` comparison reads the same constant.
- Earlier sections' `CEIL_2_5_B`, ⌈2.5 b⌉, 7500 and b ≥ 1127 (sections 4, 21, 24 and the J4a and J5 rows) read
  `MAX_P0_TWO_RUNGS`, FD-CT-133's p_0, 8000 and b ≥ 1058 from this section on; their words are kept.
- Not added: a judge check that the run's L0 ladder at its logged i has two rungs. The driver refuses a run whose ladder
  is not two rungs ending at the cap fee before any L0 charge, signing or broadcast (`ITEM2_L0_LADDER_NOT_TWO_RUNGS`,
  ARV1's 2026-11-12 section; it is checked in `L0Seat.start`, after the run's Regtest funding and setup, Desktop
  r4546050104), and the judge compares the logged ladder with its own, as before. At b = 3000 the step reaches rung 1 only
  at i = 3,996 to 4,000 sat/kvB, where rung 1 is exactly one step above rung 0; finding #788's item-5 cells now use
  those increments (the step check is otherwise unchanged).

**The experiments a registration covers.** The driver refuses a CONFIRMATORY run of an experiment that a registration
naming its `experiments` leaves out (`EXPERIMENT_NOT_REGISTERED`, exit 6; ARV1's 2026-11-12 addition to section 4).
The judge now applies the same rule (D4's note section 6 left it to A):

- `registered_experiment(registration, experiment)`: a registration without the key reads as before; a key that is
  not a non-empty list of strings is `REGISTRATION_SHAPE`; an experiment not in it is `EXPERIMENT_NOT_REGISTERED`.
- Where: `item1`, `pool`, `item2`, `item4` (the log's scenario) and `experiment`, in CONFIRMATORY. Each checks once
  before it reads the policy (`covering_registration`, so the first registration's ITEM2 is refused for its coverage
  and not as `POLICY_L0_VALUES`), and again on the registration bytes it binds (`registered_log`, and the `experiment`
  command's registration step). With no `--registration`, the first check is skipped and `REGISTRATION_MISSING` stays
  where it was.
- The P5-005 registration tool's judge probe reads `parse_registration` and `registered_d2_2_sha256`, both unchanged.

**The CONFIRMATORY record cell (the Reviewer's RV-193 P3, M17).** `test_ardr_judge_item2.Item2Experiment.
test_confirmatory_unit_whose_driver_ran_needs_its_record`: in CONFIRMATORY as in EXPLORATORY, an ITEM2 unit whose
driver ran (`exit` an int) and has no record is `RECORD_MISSING` (exit 3), and a lost slice (`exit` null) stands on its
collection. The code at the rule is unchanged; the cell kills the mutant that turns the rule off in CONFIRMATORY.

**Not changed.** Every outcome, row, state and count rule; the :537 ladder function; the frozen 045b and the frozen
first policy; the record's shape but for `amends` on the two amended `thresholds` entries; the judge workflow. The
judge's tests that used ⌈2.5 b⌉ values now use FD-CT-133's (`test_ardr_judge_item2`, `test_ardr_judge_item4`;
the test specs re-derive the rule from 4b down, not by the judge's search).
