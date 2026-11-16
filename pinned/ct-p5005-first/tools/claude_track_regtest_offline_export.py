#!/usr/bin/env python3
"""E3d-3: offline export, verify, import and guard on two Regtest nodes.

CT-P3-044a-2 E3d-3 (E3 design record §6 end to end items 1-4 and their
negatives; E3d-0 note Q12). Class T, Regtest only; development evidence,
not S17-PREP.

This driver starts two connected Regtest nodes (Bitcoin Core 31.1 as Node A,
30.3 as Node B), mines a coinbase to the TEST_ONLY fee key (scalar 9, by its
public output key) and the chain to tip H0 - 1, and reads the chain facts
from both nodes. It then runs two ignored Rust workers in turn, each in its
own build:

1. the offline stage, `crates/bitagi-signer/tests/offline_export_e2e_sign.rs`,
   in the offline build (`--cfg bitagi_offline_build`, feature
   `offline-ceremony`, which has no RPC client). It is given the chain facts
   in an input file, `chain-facts.txt` (its path is the only environment
   value the stage reads; its SHA-256 is printed and in the summary), charges the REGISTER in a wallet ledger, signs it with the
   offline binary and hands on exactly three files: the input file, the
   store's `<id>.export` and the wallet ledger;
2. the online stage, `crates/bitagi-signer/tests/two_node_offline_export.rs`,
   in the ordinary build. It reads only those three files and both nodes
   (the product read client), verifies and imports the export, and calls
   `testmempoolaccept` on both nodes only inside the export guard.

Only those three files pass between the stages: the driver checks the work
directory between them, and the offline stage removes its session root and
key files before it ends. After the online stage it checks that both
mempools are empty, the tip did not move and the funding coinbase output is
still unspent: these stages submit nothing (their label `NO_BROADCAST`).

CT-P3-044c-1d-3d-3c-rn-1 (A #258 issuecomment-6255049643) then runs a
third phase on the same nodes and tip, the launch host's accept path, with
labels of its own (`LAUNCH_LABELS`). Its online workers
(`crates/bitagi-launch-host/tests/two_node_launch_accept.rs`) alternate
with the offline build's (`crates/bitagi-signer/tests/launch_host_e2e_sign.rs`):

3. describe (online): the host's descriptor, bound to the pair's node
   configuration records, in hex; and that the read user may not submit
   (each node answers HTTP 403). The driver checks the descriptor's form
   and writes it, after E3d-3's chain facts, to `launch-facts.txt`, the
   launch offline stages' one environment value;
4. charge (offline): `launch/handoff/` gets exactly `BOUNDARIES["charge"]`;
5. sign (online): the host's init and turns through the execution checks, a
   signing authorization, the observation and `Sign`, which writes one
   hand-off to `launch/outbox/` (`BOUNDARIES["sign"]`);
6. sign (offline): the offline binary signs that hand-off; `launch/export/`
   gets exactly its export (`BOUNDARIES["export"]`). The stage writes and
   removes its own key files;
7. broadcast (online): the operator's import, then the host's turns through
   the observation, `AdmitSignedFinal`, the prebroadcast checks, a broadcast
   authorization and step 8, whose transport submits the guarded bytes to
   both nodes inside the wallet's export guard, then `AwaitingInclusion`.

CT-P3-044c-1d-3d-3c-rn-2 (A #258 issuecomment-6255049643 (iv),
-6255870804 Q-b15, -6262177277 1) then stops that pair and runs the launch
host's cases on a second pair and a chain of its own: the charge at
`CASE_CONSTRUCTION` (H0 - 2), below the tip the host turns at (H0 - 1), so
step 8 reads an ancestry of two blocks. Between the host worker's phases
(`launch_case_worker`, `CASE_STEPS`) the driver changes the nodes: node B's
P2P off (`NetworkInactive`), node B on its own H0 - 1 block (step 1's
follower ends on `TipHashDisagreement`, the bracket confirms it, and the
core raises the CriticalHeight68 lock with the node stop: #440), both back
on one chain (the operator's Class T resolution releases that lock, and the
node stop is cleared on the run's fresh checks), the import with no
fee delta (admitted, the broadcast authorized), a negative fee delta
(`prioritisetransaction`, which submits nothing) on node B before step 8
(submitted to node A only, `AwaitingInclusion`), and finally H0 mined with
the transaction (the store's birth is the core's effective fact: `Done`,
step 9 marks nothing yet), and then `DEEP_BLOCKS` more (`Done`, with H0's
block deeper than step 9's depth, after the follower catches up: step 9
marks the journal final).
`CASE_STEPS` was committed before the first run; another result is a FAIL
to investigate.

#484 L0 (A #258 issuecomment-6366258674 §3 (나), -6378746779 §1) then runs the Sign hand-off in the signing window on a fourth
pair and chain (`run_l0`, `L0_STEPS`): the charge and its base at
`CASE_CONSTRUCTION` (H0 - 2), where the host, made before the floor block
exists (`init_before_floor`), takes the pre-floor turns to `Sign`
(`launch_l0_worker`'s `l0_sign`); the offline stage signs that hand-off at
H0 - 2, the operator imports it and the host waits for the opening gate
(`l0_wait`); the driver mines H0 - 1, and `l0_broadcast` anchors the floor,
compares the prestate (its first run ends pending, as rn-1's sign phase)
and reaches step 8 with no Sign, its transport submitting to both nodes.
The outbox holds the one hand-off file after every phase.
1e-2b-2a (B #258 issuecomment-6537897575, A -6538196742 Q3, Q4, Q6) then
carries that chain past H0 - 1 (`L0T_STEPS`; no seventh pair): node A
mines G = H0 with the transaction (`l0_born`, run as XD-1 runs the host,
with an event line file and an ack FIFO: no line); both nodes invalidate
G and the transaction is back in both mempools (`l0_reorged`, the open
Reorg67 lock); the lock's release, step 6 not performed (`l0_release`);
a turn with the transport and the send credential while the transaction
waits (`l0_waiting`, no hand-off); node A mines a new H0 block with it
(`l0_reborn`, born again).

#503 (FD-CT-62; the unit note's section 7.3) then runs the per-tip bound
on a fifth pair and chain (`run_bounded`, `BOUND_STEPS`), charged at
H0 - 2 as rn-2's, with the case worker: `bound_sign` (rn-1's sign phase),
the offline signature, a negative fee delta on both nodes
(`AdmissionRejected`, the node stop raised: one counted failure at
H0 - 1), then the deltas taken back and `bounded` in `BOUND_RUNS`
processes of `BOUND_TURNS` turns each: at the same H0 - 1 every act is
refused (`FailedAttemptsAtTip`), raising nothing, writing no journal
entry, the stop still open. The rejections are not on the cases' chain:
at K = 1 a rejected admission is not redone at its tip, and the Opening
is admitted only at H0 - 1.

R2-b (CT-P3-044c-1, Class T; B #258 issuecomment-6354631934, A -6354752175)
then runs the literal R2 on a sixth pair and chain (`run_r2b`,
`R2B_STEPS`): charged at H0 - 2 as rn-2's, but under a
CONTINUE_WITHIN_LIMITS budget (`CONTINUE_CHARGE_WORKER`), with the case
worker: `r2b_sign` (rn-1's sign phase), the offline signature, `r2b_wait`
(the import at H0 - 1, to the broadcast authorization wait; no
authorization is written, nothing is sent), then H0 mined with no
transaction; in `r2b_missed` the miss raises nothing, the run starts again
at H0 and step 8 submits to both nodes (the send credential is this
phase's only); then node A mines H0 + 1 with the transaction and
`r2b_included` is born at H0 + 1, not at the opening.

1e-2b-2a's E8 variant then runs on a seventh pair and chain (`run_e8`,
`E8_STEPS`), charged as R2-b's: `e8_sign` (rn-1's sign phase) and the
offline signature and the operator's import (`e8_import`, no host turn),
then no host turn at H0 - 1; the driver mines H0 and H0 + 1 with no
transaction, and `e8_late` at H0 + 1 makes new
execution checks, the admission on both nodes and a new broadcast
authorization, and submits (its send credential is this pair's only);
node A mines H0 + 2 with the transaction and `e8_included` is born there,
with the opening block missed.

Steps 5 and 7 must report exactly `SIGN_STEPS` and `BROADCAST_STEPS`. The
two H0 - 1 prestate steps are the host's own (CT-P3-044c-1 1d-3d-3d; A #258
issuecomment-6340181340): a phase that reaches `ComparePrestate` (rn-1's
sign phase, rn-2's `cases_sign`, 1e-2a's E-0 `e_sign`, #471's X' re-asks
`e_reask` and `e_reask_below`, #484's `l0_broadcast` and #503's
`bound_sign` and R2-b's `r2b_sign`: eight comparisons) first ends at `PrestateComparisonPending`
(`PENDING_STEPS`), the host's Rust receipt in the outbox. The driver takes that one file out of the outbox, reads its own
inputs from both nodes (G the genesis, H the H0 - 1 hash, each node's tip,
B the raw H0 - 1 block, byte-equal from both; P the profile of the charge
stage's base), runs the formats doc's section 1.1 `produce` and section 1
`compare --raw-block` (`run_prestate`), and runs the phase again with the
Python receipt and the report, which the host checks against its own reads
before it records the comparison and the INITIAL_PRESTATE. Python boundary
(`claude_track_rx02_regtest_leg.py`'s): Python runs only as those two
documented command lines, judged by exit code; from the report the driver
reads only `result` and `raw_block_checked`, from a refusal line only
`refusal`; nothing under reference/python/ is opened or imported; Python
output is never edited, and the driver never writes the Python receipt
(only `produce` does, at a path that must not exist). The summary has each
comparison's three SHA-256s and the stage's wall clock (also in the job
summary under GitHub Actions). After every stage before
step 8 the driver checks that nothing was sent, and at every boundary that
no file under the work directory holds `private_scalar=`. After step 7 it
checks that both mempools hold exactly the candidate, that the candidate
alone spends the funding output, and that the tip did not move.

The nodes run with three RPC users, each whitelisted: the read user (the
public fixture, which the product read client uses) to the client's read
methods (`READ_METHODS`); a send-only user the driver makes for this run, to
the one submitting method, whose credential reaches only step 8's transport;
and the driver's own user, also made for this run, to `ALLOWED_RPCS`, whose
password stays in the driver's memory and reaches bitcoin-cli on its
standard input only. The cookie is whitelisted to no method (A #258
issuecomment-6262367082 P2-1: with `-rpcwhitelistdefault=0` an
unwhitelisted user may call every RPC, and a worker can find each node's
data directory), and the driver checks that each node refuses it (403)
before the run. No password is printed. Every worker's output and the
summary are scanned for ports, the users, credentials, the log and state
paths and the work directory (`scan_secrets`).

The driver itself mines only: it has no submit, broadcast or block-submit
step, and every node call it makes goes through `Node.call`, which refuses
any RPC outside `ALLOWED_RPCS` (pinned by
tests/claude_track/test_regtest_offline_export_tool.py). The only
submission in the run is the launch host's step 8 transport, in an ignored
test worker inside the wallet's export guard.

The offline stages' cfg comes only from `BITAGI_E3D3_OFFLINE_RUSTFLAGS`,
which must be exactly `--cfg bitagi_offline_build`; a `RUSTFLAGS` in the
driver's own environment is refused, so the online stages never get it.

No key, cookie, user name or port appears in the summary: the workers
authenticate with the public Class T fixture credential of
rpc_credentials.rs, given to each node as an rpcauth line with a fresh salt,
and bitcoin-cli uses the driver's own user.

Exit codes: 0 pass, 2 a check failed (a worker failed or ended early
included), 3 missing prerequisite (binaries, node start), 4 internal error.
Optimized Python (-O) is refused.
"""

from __future__ import annotations

import argparse
import decimal
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The compiled Regtest profile's H0 (tests/wallet/two_node_regtest_context.json,
# the v2_writer Profile): the pre-effective REGISTER locks at H0 - 1, so the
# chain is mined to that tip.
GATE = 1000
TIP_HEIGHT = GATE - 1
COINBASE_MATURITY = 100
# The x-only Taproot output key of TEST_ONLY scalar 9 (the fee key), with no
# script tree. Public; pinned against the signer's key binding by
# offline_export_e2e_sign.rs.
FUNDING_OUTPUT_KEY = "eceb0109085a0a3e3434faeab20e9d08e5b4fdc8538c438ba3e6748349d5f25f"
FUNDING_DESCRIPTOR = f"rawtr({FUNDING_OUTPUT_KEY})"
FUNDING_SCRIPT = "5120" + FUNDING_OUTPUT_KEY
FUNDING_HEIGHT = 1
NODE_VERSIONS = (310100, 300300)

OFFLINE_RUSTFLAGS = "--cfg bitagi_offline_build"
OFFLINE_FLAGS_VARIABLE = "BITAGI_E3D3_OFFLINE_RUSTFLAGS"
OFFLINE_WORKER = "offline_export_stage_worker"
ONLINE_WORKER = "online_export_stage_worker"
# rn-1: the launch host's workers, in the order they run, with their
# package, test target and build.
DESCRIBE_WORKER = "launch_describe_worker"
CHARGE_WORKER = "launch_charge_stage_worker"
HOST_SIGN_WORKER = "launch_sign_worker"
OFFLINE_SIGN_WORKER = "launch_sign_stage_worker"
HOST_BROADCAST_WORKER = "launch_broadcast_worker"
HOST_PACKAGE, HOST_TEST = "bitagi-launch-host", "two_node_launch_accept"
SIGNER_PACKAGE, LAUNCH_SIGNER_TEST = "bitagi-signer", "launch_host_e2e_sign"
STAGE = "E3D3_STAGE_V1"
STAGE_SECONDS = 1800
MAX_STAGE_LINE = 4096
MAX_OTHER_LINES = 2000

# The result lines each stage must print, in order (the values of the
# ones not ending in PASS are recorded in the summary).
OFFLINE_LINES = ["candidate_id", "raw_tx_sha256", "export_sha256", "wallet_candidate", "offline_stage"]
ONLINE_LINES = [
    "wallet_open",
    "N1_changed_export_refused",
    "item3_verify_import_recorded",
    "item1_wallet_construction_is_the_export",
    "N3_release_guard_revoked",
    "N4_repeat_already_recorded",
    "N5_changed_witness_refused_by_both_nodes",
    "item4_guarded_bytes_admitted_by_both_nodes",
    "N2_locked_guard_revoked",
    "txid",
    "admission_reads",
    "online_stage",
]
DESCRIBE_LINES = ["descriptor", "read_user_send_refused", "describe_stage"]
CHARGE_LINES = ["wallet_candidate", "reservation", "approval_id", "base_sha256", "budget_sha256", "charge_stage"]
HOST_SIGN_LINES = ["steps", "prestate_receipt", "prestate_ms", "sign_stage"]
OFFLINE_SIGN_LINES = ["candidate_id", "raw_tx_sha256", "txid", "export_sha256", "sign_stage"]
HOST_BROADCAST_LINES = ["steps", "prestate_receipt", "prestate_ms", "raw_tx_sha256", "txid", "hand_offs", "broadcast_stage"]
PASS_LINES = {
    "offline_stage",
    "online_stage",
    "describe_stage",
    "read_user_send_refused",
    "charge_stage",
    "sign_stage",
    "broadcast_stage",
} | set(ONLINE_LINES[:9])
ADMISSION_READS = "4"
# The launch host's steps, in order: each turn's decision and what it did.
# Every step is the host's own. A phase that reaches the H0 - 1 comparison
# first ends at `PENDING_STEPS` (the Rust receipt written), and the driver
# runs it again with the comparison (`run_prestate`).
SIGN_STEPS = ",".join(
    [
        "ComparePrestate",
        "RecordInitialPrestate",
        "RunExecutionChecks",
        "SigningAuthorityRequired",
        "SigningAuthorized",
        "RecordSigningObservation",
        "Sign",
        "OfflineSignaturePending",
    ]
)
BROADCAST_STEPS = ",".join(
    [
        "RecordBroadcastObservation",
        "AdmitSignedFinal",
        "RunPrebroadcastChecks",
        "BroadcastAuthorityRequired",
        "BroadcastAuthorized",
        "Broadcast",
        "AwaitingInclusion",
    ]
)
# The launch host's step 8 hands off once.
HAND_OFFS = "1"
# rn-2: the cases' charge height, below the tip the host turns at.
CASE_CONSTRUCTION = TIP_HEIGHT - 1
CASE_WORKER = "launch_case_worker"
CASE_LINES = ["phase", "steps", "prestate_receipt", "prestate_ms", "hand_offs", "raw_tx_sha256", "turns", "case_stage"]
# Each rn-2 phase's steps, in the order the driver runs them (module docs;
# A #258 issuecomment-6255049643 (iv): committed before the first run, in
# 68725282). #503 (the unit note's §7.3) moved "reject_both" to a pair of
# its own (`BOUND_STEPS`) and removed "reject_one": at K = 1 the rejected
# admission is not redone at its tip, and the Opening is admitted only at
# H0 - 1, so "admit" no longer clears a stop. #440 (A #258
# issuecomment-6283589369 Q-440-4) changed "disagree" and "cases_sign":
# step 1's tip disagreement now goes on to the bracket, which confirms it,
# and the core raises the CriticalHeight68 lock at H0 - 1 with the node stop
# (FOL-04), not the 2c `NodesDisagree` of 68725282; "cases_sign" releases
# that lock on the operator's resolution and clears the stop.
CASE_STEPS = {
    "inactive": "HostError:NetworkInactive",
    "disagree": "Refuse:CriticalHeightDisagreed",
    "cases_sign": ",".join(
        [
            "ComparePrestate",
            "RecordInitialPrestate",
            "RunExecutionChecks",
            "ClearActionBlock",
            "SigningAuthorityRequired",
            "SigningAuthorized",
            "RecordSigningObservation",
            "Sign",
            "OfflineSignaturePending",
        ]
    ),
    # #503: no stop is open; the import, then to the broadcast authorization.
    "admit": ",".join(
        [
            "RecordBroadcastObservation",
            "AdmitSignedFinal",
            "RunPrebroadcastChecks",
            "BroadcastAuthorityRequired",
            "BroadcastAuthorized",
        ]
    ),
    "broadcast_one": "Broadcast,AwaitingInclusion",
    # EffectiveFacts (A #258 issuecomment-6341101080 Q-F5; set before the
    # first run): the store's birth at H0 is the core's fact, `Done`.
    "included": "Done:Born",
    # B's item 11 (after the first runs; A #258 issuecomment-6262177277 1):
    # H0's block deeper than step 9's depth: `Done`, and step 9 marks the
    # journal final at floor H0.
    "deep": "Done:Born",
}
# Blocks mined above H0 before "deep" (the worker's `DEEP_BLOCKS`). Each
# "deep" process turns once; while the follower catches up that turn is
# refused at the reads (`DEEP_CATCH_UP`), raising nothing, and the driver
# runs it again, at most `DEEP_RUNS` times in all (four catch-up turns in the
# local runs; a range, not a count).
DEEP_BLOCKS = 4100
DEEP_CATCH_UP = "LocalTipUnconfirmed"
DEEP_RUNS = 8
# 1d-3d-3d: the phases whose first run ends at the H0 - 1 comparison, and
# what that run reports; the driver then compares and runs the phase again
# (whose steps are `CASE_STEPS`).
PENDING_STEPS = "PrestateComparisonPending"
CASE_PENDING = {"cases_sign": "ReleaseCriticalHeight68," + PENDING_STEPS}
CASE_HAND_OFFS = {"broadcast_one": "1"}
# The one phase that reaches step 8 and gets the send-only credential.
CASE_SENDING = ("broadcast_one",)
# #503 (module docs, the unit note's §7.3): the per-tip bound on a pair and
# chain of its own, with the case worker (`BOUND_PHASES`). "bound_sign" is
# rn-1's sign phase; in "reject_both" both nodes refuse the admission and
# the node stop is raised (one counted failure at H0 - 1); in "bounded" the
# deltas are taken back, and every act at the same H0 - 1 is refused,
# raising nothing, each process taking `BOUND_TURNS` turns, `BOUND_RUNS`
# processes.
BOUND_STEPS = {
    "bound_sign": SIGN_STEPS,
    "reject_both": "RecordBroadcastObservation,AdmitSignedFinal,Refuse:AdmissionRejected",
    "bounded": "Refuse:FailedAttemptsAtTip",
}
BOUND_PENDING = {"bound_sign": PENDING_STEPS}
BOUND_TURNS = "3"
BOUND_RUNS = 2
# R2-b (e) (B #258 issuecomment-6354631934, A -6354752175 Q-R2b-3 (가); the
# module docs): the literal R2 on a sixth pair and chain, charged at H0 - 2
# as rn-2's under a CONTINUE_WITHIN_LIMITS budget
# (`CONTINUE_CHARGE_WORKER`), with the case worker. Committed before the
# first r2b run, after the host test C1 (`r2b_tests.rs`) showed the H0
# run's steps; a run that differs is a FAIL to investigate, not a reason to
# change this table in the same change. "r2b_sign" is rn-1's sign phase;
# "r2b_wait" the import at H0 - 1, to the broadcast authorization wait,
# with no authorization written; the driver mines H0 with no transaction;
# "r2b_missed" raises nothing (the continue budget), starts the run again
# at H0 and submits to both nodes; the driver mines H0 + 1 with the
# transaction and "r2b_included" is `Done(Born { H0 + 1, at_opening:
# false })` (the worker asserts the height and `at_opening`).
CONTINUE_CHARGE_WORKER = "launch_continue_charge_stage_worker"
CONTINUE_POLICY = '"exact_height_miss":"CONTINUE_WITHIN_LIMITS"'
R2B_STEPS = {
    "r2b_sign": SIGN_STEPS,
    "r2b_wait": ",".join(BROADCAST_STEPS.split(",")[:4]),
    "r2b_missed": "CompareReplay,RunExecutionChecks," + BROADCAST_STEPS,  # B-692b P2a: the replay link first (REPLAY_PENDING)
    "r2b_included": "Done:Born",
}
R2B_PENDING = {"r2b_sign": PENDING_STEPS}
R2B_HAND_OFFS = {"r2b_missed": "1"}
# The one r2b phase that reaches step 8 and gets the send-only credential.
R2B_SENDING = ("r2b_missed",)
# The fee delta that makes a node refuse the candidate (below the minimum
# relay fee) and that the driver takes back: 1 BTC, in satoshis.
FEE_DELTA = 100_000_000
# 1d-3d-3d: the formats doc's two documented Python command lines the
# driver runs, and nothing else (`run_prestate`).
REFERENCE_DIR = ROOT / "reference" / "python"
PRESTATE_COMMANDS = {
    "produce": ("h0_prestate.py", "produce"),
    "compare": ("h0_prestate.py", "compare"),
}
PRESTATE_SECONDS = 300
# The formats doc's bounds: a receipt and a report at most 65,536 bytes, the
# profile text 4,096, the raw block text 8,000,001.
PRESTATE_FILE_LIMIT = 65_536
PROFILE_TEXT_LIMIT = 4096
RAW_TEXT_LIMIT = 8_000_001
RECEIPT_NAME = re.compile(r"h0-receipt-[0-9a-f]{64}\.json")
# 1e-2a (B #258 issuecomment-6338425291, A issuecomment-6340182163): the
# launch host's E scenarios at the H0 - 1 floor on a third pair and chain,
# with nothing sent. The charge is built at H0 - 2, as rn-2's; the host turns
# at H0 - 1 (block X). Each phase is one worker process, after the driver's
# node change for it (`run_e`). Committed before the first E run
# (A #258 issuecomment-6255049643 (iv)); a run that differs is a FAIL to
# investigate, not a reason to change this table in the same change.
E_WORKER = "launch_e_worker"
E_LINES = ["phase", "steps", "prestate_receipt", "prestate_ms", "hand_offs", "ledger_events", "turns", "e_stage"]
E_STEPS = {
    # E-0: the accept path to the offline signature, as rn-1's sign phase:
    # its first run ends at the H0 - 1 comparison (`E_PENDING`), its second
    # (with the comparison) starts with the host's own ComparePrestate and
    # RecordInitialPrestate (1d-3d-3d; #472 seeded both).
    "e_sign": SIGN_STEPS,
    # E6a-1 (run twice, each a new process): nothing new.
    "e_sign_again": "OfflineSignaturePending",
    # E2'': the import, then the turns to step 8, which has no transport.
    "e_admit": ",".join(
        [
            "RecordBroadcastObservation",
            "AdmitSignedFinal",
            "RunPrebroadcastChecks",
            "BroadcastAuthorityRequired",
            "BroadcastAuthorized",
            "NotYet:Transport",
        ]
    ),
    # E6a-2 (run twice): step 8 again without a transport.
    "e_admit_again": "NotYet:Transport",
    # E3'-1: X replaced by X' at H0 - 1 on both nodes. The hook raises
    # Reorg67 (at_local = X'), binds the ancestor (H0 - 1, X') and reanchors;
    # the core refuses on the open lock, raising nothing more; no act.
    "e_replaced": "Refuse:Locked(Reorg67)",
    # E3'-2 (#471 (a); re-tabled before its first run, A #258
    # issuecomment-6255049643 (iv)): the TDS 6.7 procedure file the worker
    # writes from E3'-1's copy names the floor's ancestor, (H0 - 1, X'), the
    # one the follower binds when X is the replay floor's own block; the core
    # releases it (`ReorgProcedureCompleted`, step 6 not performed).
    "e_release": "ReleaseReorg67",
    # E3'-3: the file removed; no lock, so step 1 again on X' (a new run:
    # nothing recorded at X is used, A Q4). Corrected before its first run on
    # this head (A #258 issuecomment-6392274893 §1; table before code, A
    # 6255049643 (iv)). Was "ComparePrestate" (#471 c94d9ced, a host that did
    # not perform the comparison); stale since 1d-3d-3d, whose host performs
    # it: the first run ends pending (`E_PENDING`), the driver compares and
    # the second run goes on (`machine.rs` `opening_gate`): the comparison,
    # INITIAL_PRESTATE, then `broadcast` for the retained import: fresh
    # checks, the observation, the admission and the prebroadcast checks.
    # Then the core waits for the new run's broadcast authorization; E2''s
    # file, still in place, names X's prebroadcast checks and is not used.
    # No Sign, no hand-off.
    "e_reask": ",".join(
        [
            "ComparePrestate",
            "RecordInitialPrestate",
            "RunExecutionChecks",
            "RecordBroadcastObservation",
            "AdmitSignedFinal",
            "RunPrebroadcastChecks",
            "BroadcastAuthorityRequired",
        ]
    ),
    # E-B: X' invalidated on both nodes, the tip H0 - 2: the hook raises
    # Reorg67 (Below, a new lock), then the follower ends below the replay
    # floor, with no ancestor.
    "e_below": "HostError:Sync(TipBelowReplayFloor)",
    # E-B2 (#471 Q8-ㄱ, Q-471-3): X' reconsidered; a new start passes with
    # the lock open and no ancestor, and the core refuses on the lock.
    "e_dead": "Refuse:Locked(Reorg67)",
    # E-B3 (#471 Q8-ㄱ): the procedure file names the identity's local tip,
    # (H0 - 1, X'), agreed_at_local below; the core releases it.
    "e_release_below": "ReleaseReorg67",
    # E-B4: the file removed; step 1 again on X', as E3'-3. E-B's raise
    # moved the ledger epoch past E3'-3's X' entries, so this is a new run
    # (`machine.rs` `current_run`, `ledger_epoch`). Corrected as E3'-3 and
    # for the same reason (was "ComparePrestate").
    "e_reask_below": ",".join(
        [
            "ComparePrestate",
            "RecordInitialPrestate",
            "RunExecutionChecks",
            "RecordBroadcastObservation",
            "AdmitSignedFinal",
            "RunPrebroadcastChecks",
            "BroadcastAuthorityRequired",
        ]
    ),
}
# Phases the driver runs more than once, each a new process with the nodes
# unchanged (E6a): every run reports the same.
E_RUNS = {"e_sign_again": 2, "e_admit_again": 2}
# 1d-3d-3d (A #258 issuecomment-6340181340, more conditions): nothing is
# seeded. #472 seeded the prestate in E-0 (twice); E-0 now compares it as
# rn-1's sign phase does: its first run ends at `PENDING_STEPS`, the driver
# compares (`run_prestate`) and runs it again. #471 (A #258
# issuecomment-6392274893 §1): after each release, E3'-3 and E-B4 compare
# X' the same way (was `{"e_sign": ...}` alone, before 1d-3d-3d met #471).
# This reaches E5's real-node shape (a new comparison on a replaced H0 - 1
# block) but does not close E5, E6b or T2-4 (1e-2a-2's).
E_PENDING = {"e_sign": PENDING_STEPS, "e_reask": PENDING_STEPS, "e_reask_below": PENDING_STEPS}
# Step 8 hands off nothing in any E phase.
E_HAND_OFFS: dict = {}
# No E phase gets the send credential or a transport.
E_SENDING = ()
# The ledger events each one-turn phase's turn makes (the worker reports the
# phase's total): step 0's writer open, and the raise or the release.
# E3'-3 and E-B4 left this table (each was "1", one refused turn) with
# their compared runs, which turn several times, as `e_sign`'s.
E_EVENTS = {
    "e_sign_again": "1",
    "e_admit_again": "1",
    "e_replaced": "2",
    # Step 0's writer open, then the release's reconcile and the release.
    "e_release": "3",
    "e_below": "2",
    "e_dead": "1",
    "e_release_below": "3",
}
# Rows that record behaviour that is open, not accepted, with the label's
# note. No E row since #471: the lock `OPEN_FLOOR_REPLACEMENT` marked is
# released by E3'-2, and the one `OPEN_1D3_Q8` marked (E-B's, left open
# through E-B2) by E-B3 (A #258 issuecomment-6342680714).
# Nor CN01 since A #258 issuecomment-6392274893 §1 7 (the note was kept
# for it at the EF merge, `e32c8d4e`).
E_OPEN: dict = {}
E_OPEN_NOTE: dict = {}
# 1e-2b-1 (B #258 issuecomment-6341419417, A -6342681379): the expected
# table, committed before the first run of its rows (A 6255049643 (iv)). A
# different result is a FAIL to investigate, never a reason to change this
# table in the same change. L0 (the retained path) is held for A's decision
# (B 6342816258): its row comes in a commit of its own, before its first run.
#
# The host's event lines (`XD1_LINE_V1 <seq> <NAME>`), per process, by
# phase. rn-1's first sign process is the XD-1 ack smoke (Q-B2): S2, the
# driver's ack of S2, then step 1's start. 1d-3d-3d's ComparePrestate takes
# two processes: the first writes the Rust receipt and ends ("sign"), the
# second is given the comparison ("sign_compared") and writes no second S2
# or STEP_1_START (B's choice (a), V1 EVENT_DUPLICATED). A process that
# writes nothing: [].
EVENT_LINES = {
    # L1 (and the ack smoke).
    "sign": ["S2", "STEP_1_START"],
    "sign_compared": [
        "STEP_1_END",
        "STEP_2_START",
        "STEP_2_END",
        "STEP_3_START",
        "STEP_3_END",
        "STEP_4_START",
        "STEP_4_END",
        "STEP_5_START",
        "STEP_5_END",
        "STEP_6_START",
    ],
    "broadcast": [
        "STEP_6_END",
        "STEP_7_START",
        "STEP_7_END",
        "STEP_8_START",
        "STEP_8_END",
        "STEP_9_START",
        "STEP_9_END",
        "STEP_10_START",
        "B_A_1",
        "B_B_1",
        "O_A ACCEPTED",
        "O_B ACCEPTED",
        "STEP_10_END",
    ],
    # L2, L3, L5: no line.
    "after_send": [],
    "cn01": [],
    "after_send_one": [],
    # L4: rn-2's step 8, node A's answer lost by the proxy, node B's
    # delta. The process starts at `Broadcast` (its authorization was the
    # "admit" phase's), so step 10 starts at the act.
    "broadcast_one": ["STEP_10_START", "B_A_1", "B_B_1", "O_A ACCEPTED", "O_B REJECTED", "STEP_10_END"],
}
# #484 L0 (`run_l0`; #495 P2-1, A issuecomment-6387756209 §2): no line
# below H0 - 1 (PROPOSAL-1). At H0 - 1 the first process is L1's "sign"
# (with no ack: L0 is no XD-1 ack smoke); the compared one goes on to
# step 10, its step 6 started by `RecordBroadcastObservation`, the reuse
# of the bytes signed in the window, not by a Sign. The run's chain is
# then L1's: each base line once.
EVENT_LINES["l0_sign"] = []
EVENT_LINES["l0_wait"] = []
EVENT_LINES["pending l0_broadcast"] = EVENT_LINES["sign"]
EVENT_LINES["l0_broadcast"] = EVENT_LINES["sign_compared"] + EVENT_LINES["broadcast"]
# The ack the driver writes for the smoke: S2's sequence number.
XD1_ACK_SEQ = {"sign": 1}
# 1e-2b-1's phases (`launch_b_worker`), their steps and hand-offs. L2 and
# L5 run twice (a new process each time, nodes unchanged), with the send
# credential: a regression that sends again is caught by its hand-off.
B_STEPS = {
    "after_send": "AwaitingInclusion",
    "cn01": "Refuse:Locked(Reorg67)",
    "after_send_one": "AwaitingInclusion",
}
B_RUNS = {"after_send": 2, "after_send_one": 2}
B_HAND_OFFS = {"after_send": "0", "cn01": "0", "after_send_one": "0"}
# L4: the answer the proxy lost (node A's), and what each node holds after.
ANSWER_LOST = {"broadcast_one": {"node": "A", "dropped": "1", "mempool": ("present", "absent")}}
# L2 and L5: the mempools after the send; L3 (Q-B7): both empty after X'.
MEMPOOLS = {
    "after_send": ("present", "present"),
    "after_send_one": ("present", "absent"),
    "cn01": ("absent", "absent"),
}
# L3 (CN-01 at H0 - 1): X -> X' after the rn-1 send. The hook raises
# Reorg67; the report marks the reorg before inclusion. The row records the
# raise only. It was labelled `OPEN_FLOOR_REPLACEMENT` ("the lock is not
# released"), stale since #471 (a): this lock, X -> X' on the floor block
# with the ancestor (H0 - 1, X'), is the one E3'-2 releases on real nodes
# (A #258 issuecomment-6392274893 §1 7).
CN01 = {"phase": "cn01", "reorged_before_inclusion": "true"}
# Labels of recorded behaviour that is not accepted. The stop before the
# record (Q-B5) is a host test's, not a real-node row's; its label
# OPEN_CN01_UNRECORDED_SUBMISSION is gone with #473's fix (I6: the host's
# SubmissionIntent keeps the CN-01 mark), so no note is left here.
B_OPEN: dict = {}
B_OPEN_NOTE: dict = {}
E_LABELS = [
    "CLASS_T",
    "REGTEST",
    "TEST_ONLY_PRIVATE_SCALAR_KNOWN",
    "CLASS_T_DEVELOPMENT_EVIDENCE_NOT_S17_PREP",
    "NOT_S04",
    "NO_BROADCAST",
    "H0_MINUS_1_PRESTATE_COMPARED_CLASS_T",
]
# #484 L0 (A #258 issuecomment-6366258674 §3 (나), -6378746779 §1; B's
# draft -6377313784 §3 4): the Sign hand-off in the signing window, on a
# fourth pair and chain. The charge is built at H0 - 2 and its base is for
# that tip (`sign_tip_lines`): the host is made before the floor block
# (`init_before_floor`) and signs at H0 - 2; the driver mines H0 - 1 only
# after the import, and the H0 - 1 turns compare the prestate and reach
# step 8 with no Sign. Committed before the first L0 run; a run that
# differs is a FAIL to investigate, not a reason to change this table in
# the same change.
L0_WORKER = "launch_l0_worker"
L0_LINES = ["phase", "steps", "prestate_receipt", "prestate_ms", "hand_offs", "raw_tx_sha256", "turns", "l0_stage"]
L0_STEPS = {
    # The pre-floor turns: SIGN_STEPS without the H0 - 1 prestate steps.
    "l0_sign": ",".join(SIGN_STEPS.split(",")[2:]),
    # The operator's import at H0 - 2: the core waits for H0 - 1.
    "l0_wait": "SignedAwaitingOpeningGate",
    # H0 - 1: the floor anchored (no Reorg67), the prestate compared, then
    # the broadcast path; no Sign.
    "l0_broadcast": ",".join(
        [
            "ComparePrestate",
            "RecordInitialPrestate",
            "RunExecutionChecks",
            *BROADCAST_STEPS.split(","),
        ]
    ),
}
L0_PENDING = {"l0_broadcast": PENDING_STEPS}
L0_HAND_OFFS = {"l0_broadcast": "1"}
# The one L0 phase that reaches step 8 and gets the send-only credential.
L0_SENDING = ("l0_broadcast",)
# 1e-2b-2a (B #258 issuecomment-6537897575 §3, A -6538196742 Q3, Q4, Q6;
# the unit note `2026-10-31_1e-2b-2a-tip-h0.md` §2): the L0 chain past
# H0 - 1, with the L0 worker, no seventh pair. Committed before the first
# run of these rows; a run that differs is a FAIL to investigate, not a
# reason to change this table in the same change.
L0T_STEPS = {
    # E4-a: node A mined G = H0 with the transaction, both mempools empty.
    # The worker asserts `Born { H0, at_opening: true }` with the opening
    # block not missed; no act, no authorization. The process is XD-1's
    # (an event line file and an ack FIFO): no line, so no ack is asked
    # (PROPOSAL-1, `tip + 1 == H0`).
    "l0_born": "Done:Born",
    # E9-a: both nodes invalidated G; the transaction is back in both
    # mempools. The hook raises Reorg67 for the local tip (H0, G), agreed
    # below it, ancestor (H0 - 1, X); the core refuses on the open lock.
    "l0_reorged": "Refuse:Locked(Reorg67)",
    # The release from the operator's copy, step 6 not performed (A Q4; the
    # performed release is #608's).
    "l0_release": "ReleaseReorg67",
    # E9-b: the file removed. While the transaction waits in both mempools,
    # a turn with the transport and the send credential hands nothing off.
    "l0_waiting": "AwaitingInclusion",
    # E9-c: node A mined a new H0 block with the transaction: born again,
    # the journal not archived, one `Submitted` and one Sign hand-off.
    "l0_reborn": "Done:Born",
}
L0T_HAND_OFFS: dict = {}
# The one L0T phase given the send credential (and the transport).
L0T_SENDING = ("l0_waiting",)
# The XD-1-style process (A Q3): the event line file and an ack FIFO the
# driver never writes. XD-1 itself still does not wait for `Done`.
L0T_XD1 = ("l0_born",)
# Each node's mempool for the transaction after each L0T phase.
L0T_MEMPOOLS = {
    "l0_born": ("absent", "absent"),
    "l0_reorged": ("present", "present"),
    "l0_release": ("present", "present"),
    "l0_waiting": ("present", "present"),
    "l0_reborn": ("absent", "absent"),
}
for _name in L0T_STEPS:
    EVENT_LINES[_name] = []
del _name
# 1e-2b-2a's E8 variant (1E E8, T2-8; B #258 issuecomment-6537897575 §3):
# R2-b's flow on a seventh pair and chain, charged under the continue
# budget, with no host turn at H0 - 1 after the signature. The driver
# mines H0 to H0 + `E8_LATE` with no transaction; `e8_late` at
# H0 + `E8_LATE` makes new execution checks, the admission on both nodes
# and a new `BroadcastAuthorized` (R32), and submits; node A mines the next
# block with the transaction and `e8_included` is
# `Born { H0 + E8_LATE + 1, at_opening: false }` with the opening block
# missed (the worker). Both later phases run with an event line file: no
# line above H0 - 1. Committed before the first run, as `L0T_STEPS`.
E8_LATE = 1
E8_STEPS = {
    "e8_sign": SIGN_STEPS,
    # Dated 2026-10-31, after the first run (unit note §2.2): the
    # operator's import at H0 - 1, with no host turn. The worker's import
    # reconciles with no replay state, which the ledger refuses at a tip at
    # or above H0 (`E3D3_RECONCILE: StaleBranch` at H0 + 1), so "e8_late"
    # no longer imports.
    "e8_import": "Imported",
    "e8_late": "CompareReplay,RunExecutionChecks," + BROADCAST_STEPS,  # B-692b P2a: the replay link first (REPLAY_PENDING)
    "e8_included": "Done:Born",
}
E8_PENDING = {"e8_sign": PENDING_STEPS}
E8_HAND_OFFS = {"e8_late": "1"}
E8_SENDING = ("e8_late",)
E8_LINES = ("e8_late", "e8_included")
EVENT_LINES["e8_late"] = []
EVENT_LINES["e8_included"] = []

# 1e-2b-2b (CT-P3-044c-1; unit note `2026-11-01_1e-2b-2b.md`; B #258
# issuecomment-6539695866, A -6539879887 Q-b1-Q-b8, B -6539888340): lost
# gates and reorged rungs, Class T Regtest. Only `run_e10` (an eighth pair),
# `run_e7` (a ninth) and `run_l0`'s opt-in `rows_2b` (the L0 chain) use
# these; with them off every other phase, RPC list and chain is as before.
#
# D1's miner process (`claude_track_ardr_driver.MinerProcess`, Q-b4 B1)
# runs on node A of those pairs under its own user, whitelisted for exactly
# D1's `MINER_RPCS` (passed in: D1 imports this module). The driver's user
# keeps `ALLOWED_RPCS`: no submit RPC. The miner's own word for bytes handed
# to it privately is `PRIVATE`; the log's mark is `THIRD_PARTY` (A
# 6538196742 §2, dated 2026-10-31), a template transaction's `TEMPLATE`.
MINER_USER = "bitagi-rn1-mine"
MINER_POLICY = "ITEM2_DEFAULT"
MINER_MARKS = {"TEMPLATE": "TEMPLATE", "PRIVATE": "THIRD_PARTY"}
# The competitor's funding: block 2's coinbase to P2WSH(OP_TRUE), spent by
# D2-1's `funding_tx` (handed privately to the miner, block H0 - 2) to the
# COMPETITOR wallet C00's fee script.
COMPETITOR_SOURCE_HEIGHT = 2
COMPETITOR = ("COMPETITOR", "C00", "COMPETITOR_C00_ANCHOR_H000")
# The generator's TEST_ONLY policy seed (D2-1's draft key rule): a fixed
# public label's digest, never a wallet seed.
COMPETITOR_SEED = hashlib.sha256(b"BITAGI/CT-P3-044C1/1E-2B-2B/COMPETITOR/TEST_ONLY/V1").digest()
COMPETITOR_RUN = 0
# The competitor's fee: this many times P0's fee per vbyte at least (its
# ancestor feerate above P0's: E10-s's block order, checked in `order`).
COMPETITOR_FEE_FACTOR = 2
# `getblocktemplate` caches its template for about 5 s at an unchanged tip
# (unit note §0, measured on both pins): after a fee delta the driver
# waits this long before the miner asks.
TEMPLATE_SECONDS = 6.0
LOST_WORKER = "launch_lost_worker"
LOST_LINES = [
    "phase",
    "steps",
    "prestate_receipt",
    "prestate_ms",
    "hand_offs",
    "raw_tx_sha256",
    "raw_tx_hex",
    "answer_lost",
    "submitted",
    "report",
    "turns",
    "lost_stage",
]
RELEASE_STEPS = "ReleaseReorg67"
# §2.1 (eighth pair). Committed with the note's table, before the first
# real-node run of these rows.
E10_STEPS = {
    "e10_sign": SIGN_STEPS,
    "e10_broadcast": BROADCAST_STEPS,
    # E10: the miner mined G with the competitor and without P0 (its delta
    # at node A); P0 waits in both mempools. Stale is checked before a
    # pending wait (machine.rs `effective`): refused, nothing handed off.
    "e10_lost": "Refuse:GateAdvanced",
    # The delta taken back; the miner mined G + 1 with P0 from the template.
    "e10_included": "Done:IncludedNoEffect",
    # E10-s: G + 1 and G invalidated on both nodes, both back on X.
    "e10s_reorged": "Refuse:Locked(Reorg67)",
    "e10s_release": RELEASE_STEPS,
    # The miner mined G'' from the template: the competitor before P0.
    "e10s_same": "Done:IncludedNoEffect",
}
# §2.2 (ninth pair): E7 and E7b in one flow.
E7_STEPS = {
    "e7_sign": SIGN_STEPS,
    # E7b: node A's answer through L4's proxy (one dropped), node B called.
    "e7_broadcast": BROADCAST_STEPS,
    # X -> X' on both nodes, P0 not in X' (its delta at node A).
    "e7_reorged": "Refuse:Locked(Reorg67)",
    "e7_release": RELEASE_STEPS,
    # No submission under the old authorization (Q22 main's answer). Dated
    # 2026-10-31 (after the first E7 run; the note's table said
    # `AwaitingInclusion`): after the comparison at X' the run admits again
    # and asks for a new broadcast authorization, which is not given.
    "e7_waiting": "ComparePrestate,RecordInitialPrestate,RunExecutionChecks," + ",".join(BROADCAST_STEPS.split(",")[:4]),
    "e7_lost": "Refuse:GateAdvanced",
    # P0's bytes (e7_broadcast's `raw_tx_hex`) handed privately to the
    # miner: G' + 1.
    "e7_included": "Done:IncludedNoEffect",
}
# §2.3 (the L0 chain after `l0_reborn`, `run_l0(rows_2b=True)`).
L0D_STEPS = {
    "l0_lost_reorged": "Refuse:Locked(Reorg67)",
    "l0_lost_release": RELEASE_STEPS,
    # E9-d: the winner changed by a reorg after it won.
    "l0_lost": "Refuse:GateAdvanced",
}
# Dated 2026-10-31 (after the first E7 run): X' is a new H0 - 1 block, so
# `e7_waiting`'s first run ends at the comparison (as 1e-2a's `e_reask`);
# its run with the comparison is the table's `AwaitingInclusion`.
LOST_PENDING = {"e10_sign": PENDING_STEPS, "e7_sign": PENDING_STEPS, "e7_waiting": PENDING_STEPS}
LOST_HAND_OFFS = {"e10_broadcast": "1", "e7_broadcast": "1"}
# The phases given the transport and the send credential: the broadcasts,
# and the turns that must hand nothing off with them.
LOST_SENDING = ("e10_broadcast", "e10_lost", "e7_broadcast", "e7_waiting", "e7_lost", "l0_lost")
# E7b: node A's answer dropped by the proxy (1e-2b-1 L4's).
LOST_ANSWER = {"e7_broadcast": "1"}
# The one phase whose worker reports the bytes step 8 handed off
# (`raw_tx_hex`, Q-b5), for `e7_included`'s private hand-off.
LOST_RAW_HEX = ("e7_broadcast",)
# Each phase's worker report (its last decided turn; a release turn decides
# the open lock's refusal, so it reports too):
# `missed`, `reorged` and the outcome. `Stale:G:>G` is `Stale { G, next }`
# with next above G.
STALE = f"Stale:{GATE}:>{GATE}"
LOST_REPORTS = {
    "e10_sign": "missed=false;reorged=false;outcome=-",
    "e10_broadcast": "missed=false;reorged=false;outcome=-",
    "e10_lost": f"missed=true;reorged=false;outcome={STALE}",
    "e10_included": f"missed=true;reorged=false;outcome=IncludedNoEffect:{GATE + 1}",
    "e10s_reorged": "missed=false;reorged=false;outcome=-",
    "e10s_release": "missed=false;reorged=false;outcome=-",
    "e10s_same": f"missed=true;reorged=false;outcome=IncludedNoEffect:{GATE}",
    "e7_sign": "missed=false;reorged=false;outcome=-",
    "e7_broadcast": "missed=false;reorged=false;outcome=-",
    "e7_reorged": "missed=false;reorged=true;outcome=-",
    "e7_release": "missed=false;reorged=true;outcome=-",
    "e7_waiting": "missed=false;reorged=true;outcome=-",
    "e7_lost": f"missed=true;reorged=true;outcome={STALE}",
    "e7_included": f"missed=true;reorged=true;outcome=IncludedNoEffect:{GATE + 1}",
    "l0_lost_reorged": "missed=false;reorged=false;outcome=-",
    "l0_lost_release": "missed=false;reorged=false;outcome=-",
    "l0_lost": f"missed=true;reorged=false;outcome={STALE}",
}
# Each node's mempool for P0 after each phase (node A, node B).
LOST_MEMPOOLS = {
    "e10_broadcast": ("present", "present"),
    "e10_lost": ("present", "present"),
    "e10_included": ("absent", "absent"),
    "e10s_reorged": ("present", "present"),
    "e10s_release": ("present", "present"),
    "e10s_same": ("absent", "absent"),
    "e7_broadcast": ("present", "present"),
    # X -> X': P0 is not final for X's height, so both nodes drop it (as
    # 1e-2b-1 L3's `cn01`); the miner gets its bytes privately later.
    "e7_reorged": ("absent", "absent"),
    "e7_release": ("absent", "absent"),
    "e7_waiting": ("absent", "absent"),
    "e7_lost": ("absent", "absent"),
    "e7_included": ("absent", "absent"),
    "l0_lost_reorged": ("present", "present"),
    "l0_lost_release": ("present", "present"),
    "l0_lost": ("present", "present"),
}
# The tip height each phase turns at.
LOST_TIPS = {
    **{name: TIP_HEIGHT for name in ("e10_sign", "e10_broadcast", "e10s_reorged", "e10s_release",
                                     "e7_sign", "e7_broadcast", "e7_reorged", "e7_release", "e7_waiting",
                                     "l0_lost_reorged", "l0_lost_release")},
    **{name: GATE for name in ("e10_lost", "e10s_same", "e7_lost", "l0_lost")},
    **{name: GATE + 1 for name in ("e10_included", "e7_included")},
}
# What the worker reports of the journal's `Submitted` answers after each
# phase from the broadcast on (node A, node B): `-` before it.
# E7b: node A's answer was dropped after node A took the transaction; the
# transport's read after it finds it there (1e-2b-1 L4's `broadcast_one`),
# so both answers are `Accepted` (reading of the note's "answer lost",
# 2026-10-31: `NodeSubmission` has no lost answer; the proxy's count is).
LOST_SUBMITTED = {name: ("-" if name.endswith("_sign") else "Accepted,Accepted") for name in LOST_REPORTS}
# The files that cross each boundary of the launch phase: the stage that
# writes them, the stage that reads them, the directory, and their names
# (`<candidate>` and `<entry>` are 64 lower-case hex digits).
BOUNDARIES = {
    "charge": ("offline", "online", "handoff", ["base.txt", "budget.json", "launch.txt", "wallet.sqlite"]),
    "sign": ("online", "offline", "outbox", ["sign-input-<entry>.txt"]),
    "export": ("offline", "online", "export", ["<candidate>.export"]),
}
# The descriptor the describe stage hands on: a version 2 Regtest
# descriptor (`SubstrateContext::canonical_bytes`, 174 + 32 bytes), tag
# `BGSUBCTX`, version 2, network byte 1 (Regtest), the genesis at 13..45.
DESCRIPTOR_BYTES = 206
DESCRIPTOR_TAG = b"BGSUBCTX"
# The product read client's methods (`Method::name` in rpc_http.rs; the
# keepalive driver's list), to which the read user is whitelisted.
READ_METHODS = (
    "getblockcount",
    "getbestblockhash",
    "getblockhash",
    "getblockheader",
    "getblock",
    "getnetworkinfo",
    "getblockchaininfo",
    "getdeploymentinfo",
    "gettxout",
    "testmempoolaccept",
    "estimatesmartfee",
    "getblockstats",
    "getmempoolentry",
    "getrawtransaction",
    "getindexinfo",
    "getrpcinfo",
)
# The send-only user's one method, named only to whitelist it; the driver
# never calls it (`Node.raw` refuses it, it is not in `ALLOWED_RPCS`).
SEND_USER = "bitagi-rn1-send"
SEND_WHITELIST = "sendrawtransaction"
# The driver's own user, whitelisted to `ALLOWED_RPCS`; and the cookie's
# user, whitelisted to nothing.
ADMIN_USER = "bitagi-rn1-driver"
COOKIE_USER = "__cookie__"

# Every RPC the driver may make. No submit or broadcast RPC
# (sendrawtransaction, submitpackage, submitblock, generateblock) and no
# admission read: the online stage makes those, inside the guard.
ALLOWED_RPCS = frozenset(
    {
        "addnode",
        "generatetodescriptor",
        "getbestblockhash",
        "getblock",
        "getblockchaininfo",
        "getblockcount",
        "getblockhash",
        "getconnectioncount",
        "getdescriptorinfo",
        "getmempoolentry",
        "getmempoolinfo",
        "getnetworkinfo",
        "gettxout",
        "gettxspendingprevout",
        # rn-2's node changes: none submits (A #258
        # issuecomment-6255049643 (ii), (iv)).
        "invalidateblock",
        "prioritisetransaction",
        "reconsiderblock",
        "setnetworkactive",
        "stop",
    }
)
# The read-only RPCs a caller may add for the driver's own user, by name
# (`Node`/`Pair` `extra_rpcs`; A #258 issuecomment-6423146186): 1e-4b-1's
# XD-1 driver decodes the candidate's bytes on both nodes. Nothing that
# writes, mines or sets policy. Without `extra_rpcs` every node is as before.
EXTRA_RPCS = frozenset({"decoderawtransaction"})

# Each phase's labels: E3d-3's stages submit nothing; the launch phase's
# one submission is step 8's Regtest transport, and its H0 - 1 prestate is
# compared (Class T Regtest; not S04 or S17-PREP evidence).
E3D3_LABELS = [
    "CLASS_T",
    "REGTEST",
    "TEST_ONLY_PRIVATE_SCALAR_KNOWN",
    "CLASS_T_DEVELOPMENT_EVIDENCE_NOT_S17_PREP",
    "NO_BROADCAST",
]
LAUNCH_LABELS = [
    "CLASS_T",
    "REGTEST",
    "TEST_ONLY_PRIVATE_SCALAR_KNOWN",
    "CLASS_T_DEVELOPMENT_EVIDENCE_NOT_S17_PREP",
    "NOT_S04",
    "REGTEST_STEP8_TRANSPORT_ONLY",
    "H0_MINUS_1_PRESTATE_COMPARED_CLASS_T",
]

# The public fixture recipe and user of rpc_credentials.rs; not a secret.
AUTH_RECIPE = "BITAGI/P3-008/PUBLIC-AUTH/V1"
AUTH_USER = "-".join(("bitagi", "class", "t"))


class RunUser:
    """A user made for this run (the send-only user, the driver's own): a
    fresh password, given to the nodes as an rpcauth line with a fresh
    salt. The send-only user's credential goes to step 8's transport only;
    the driver's stays in its memory. Never printed."""

    def __init__(self, user: str):
        self.user = user
        self.password = secrets.token_hex(32)
        self.salt = secrets.token_hex(16)
        self.digest = hmac.new(self.salt.encode("ascii"), self.password.encode("ascii"), hashlib.sha256).hexdigest()

    def line(self) -> str:
        return f"{self.user}:{self.salt}${self.digest}"

    def auth(self) -> str:
        return f"{self.user}:{self.password}"

    def needles(self) -> list[str]:
        return [self.user, self.password, self.salt, self.digest]


class Prerequisite(Exception):
    pass


class Mismatch(Exception):
    pass


def auth_line() -> str:
    """`<user>:<salt>$<hmac>` for the public fixture credential."""
    fixture = hashlib.sha256(AUTH_RECIPE.encode("ascii")).hexdigest()
    salt = secrets.token_hex(16)
    digest = hmac.new(salt.encode("ascii"), fixture.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{AUTH_USER}:{salt}${digest}"


def free_port() -> int:
    """One port through `draw_ports` (#682, defined near the end): never a
    port this process has handed out before."""
    return draw_ports(1)[0]


def rpc_method(args: tuple[str, ...]) -> str:
    """The RPC a bitcoin-cli argument list names: its first argument that
    is not an option."""
    for arg in args:
        if not arg.startswith("-"):
            return arg
    raise Mismatch("RPC_WITHOUT_METHOD")


# tools-cli-text (#498): the methods this driver calls whose answer is a
# bare string. bitcoin-cli prints it without quotes, and a hash's digits
# can read as a JSON number, so it is never parsed. `getblock` at
# verbosity 0 is the block's hex, and is text too.
TEXT_METHODS = frozenset({"getbestblockhash", "getblockhash", "stop"})


def cli_result(args: tuple[str, ...], text: str):
    """bitcoin-cli's answer to `args`: the text for a `TEXT_METHODS` call,
    `None` for a null result (printed as nothing), and otherwise JSON, amounts as
    `Decimal`.
    Any other answer that is not JSON raises (`JSONDecodeError`, or `InvalidOperation` for an exponent
    `Decimal` refuses): a broken
    answer to a number or object call is refused where it is read, never
    passed on as text."""
    method, *params = args[next(i for i, a in enumerate(args) if not a.startswith("-")):]
    if method in TEXT_METHODS or (method == "getblock" and params[1:2] == ["0"]):
        return text
    if not text:
        return None
    return json.loads(text, parse_float=decimal.Decimal)


class Node:
    # Added to `ALLOWED_RPCS` for this node's driver user: a subset of
    # `EXTRA_RPCS`, none by default.
    extra_rpcs: frozenset = frozenset()

    # 1e-2b-2b (Q-b4 B1): an optional miner user for D1's miner process,
    # whitelisted for exactly the RPC set its caller passes (D1's
    # `MINER_RPCS`); none by default. The driver's own user never gets it.
    miner_user: RunUser | None = None
    miner_rpcs: frozenset = frozenset()

    def __init__(self, label: str, bindir: Path, datadir: Path, rpcport: int, send: RunUser, admin: RunUser,
                 extra_rpcs: frozenset = frozenset(), miner: RunUser | None = None,
                 miner_rpcs: frozenset = frozenset(), port: int | None = None):
        extra = frozenset(extra_rpcs)
        if not extra <= EXTRA_RPCS:
            raise Prerequisite(f"{label}: RPCs outside EXTRA_RPCS: {','.join(sorted(extra - EXTRA_RPCS))}")
        if (miner is None) != (not miner_rpcs):
            raise Prerequisite(f"{label}: a miner user needs its RPC set, and only it")
        self.extra_rpcs = extra
        self.miner_user = miner
        self.miner_rpcs = frozenset(miner_rpcs)
        self.label = label
        self.send = send
        self.admin = admin
        self.bitcoind = bindir / "bitcoind"
        self.cli = bindir / "bitcoin-cli"
        self.datadir = datadir
        self.port = port or free_port()   # #682: a pair passes its drawn ports
        self.rpcport = rpcport
        self.process: subprocess.Popen | None = None

    @property
    def log_path(self) -> str:
        """The default Regtest debug-log path under the node's data
        directory (the host worker's node records name its digest)."""
        return str(self.datadir / "regtest" / "debug.log")

    def start(self) -> None:
        for binary in (self.bitcoind, self.cli):
            if not binary.is_file():
                raise Prerequisite(f"{self.label}: missing {binary.name}")
        self.datadir.mkdir(parents=True, exist_ok=False)
        self.process = subprocess.Popen(
            [
                str(self.bitcoind),
                "-regtest",
                f"-datadir={self.datadir}",
                f"-port={self.port}",
                f"-rpcport={self.rpcport}",
                "-bind=127.0.0.1",
                "-rpcbind=127.0.0.1",
                "-rpcallowip=127.0.0.1",
                "-" + "rpc" + "auth=" + auth_line(),
                "-" + "rpc" + "auth=" + self.send.line(),
                "-" + "rpc" + "auth=" + self.admin.line(),
                # The read user may call the client's reads only; the
                # send-only user the one submitting method; the driver's
                # user `ALLOWED_RPCS`; the cookie nothing.
                "-rpcwhitelist=" + AUTH_USER + ":" + ",".join(READ_METHODS),
                "-rpcwhitelist=" + self.send.user + ":" + SEND_WHITELIST,
                "-rpcwhitelist=" + self.admin.user + ":" + ",".join(sorted(ALLOWED_RPCS | self.extra_rpcs)),
                "-rpcwhitelist=" + COOKIE_USER + ":",
                *self.miner_lines(),
                "-rpcwhitelistdefault=0",
                "-disablewallet=1",
                "-listen=1",
                "-server=1",
                "-discover=0",
                "-dnsseed=0",
                "-fixedseeds=0",
                "-printtoconsole=0",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        wait_started(self, self.label.upper())   # #682: the first call, `-rpcwait`

    def miner_lines(self) -> list[str]:
        """The miner user's rpcauth and whitelist lines: none without one."""
        if self.miner_user is None:
            return []
        return [
            "-" + "rpc" + "auth=" + self.miner_user.line(),
            "-rpcwhitelist=" + self.miner_user.user + ":" + ",".join(sorted(self.miner_rpcs)),
        ]

    def stop(self) -> None:
        if self.process is None:
            return
        try:   # #682 (WR682 P3-3): an exited node (a failed start) is only reaped: no `stop` RPC to its port
            self.process.poll() is None and self.call("stop")
            self.process.wait(timeout=60)
        except Exception:  # cleanup only; the result is already decided
            self.process.kill()
            self.process.wait(timeout=30)
        self.process = None

    def raw(self, *args: str, cookie: bool = False) -> subprocess.CompletedProcess:
        """bitcoin-cli as the driver's user, its password on standard
        input; or, for `cookie_refused` only, with the node's cookie."""
        if rpc_method(args) not in ALLOWED_RPCS | self.extra_rpcs:
            raise Mismatch(f"RPC_NOT_ALLOWED {rpc_method(args)}")
        user = [] if cookie else [f"-rpcuser={self.admin.user}", "-stdinrpcpass"]
        return subprocess.run(
            [str(self.cli), "-regtest", f"-datadir={self.datadir}", f"-rpcport={self.rpcport}", *user, *args],
            input=None if cookie else self.admin.password + "\n",
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )

    def cookie_refused(self) -> None:
        """The node refuses a read made with its cookie (whitelisted to
        nothing): HTTP 403."""
        done = self.raw("getblockchaininfo", cookie=True)
        if done.returncode == 0 or "403" not in done.stderr:
            raise Mismatch(f"{self.label}: the cookie is not refused")

    def call(self, *args: str):
        done = self.raw(*args)
        if done.returncode != 0:
            raise Prerequisite(f"{self.label}: {rpc_method(args)} failed: {done.stderr.strip()[:200]}")
        return cli_result(args, done.stdout.strip())

    def height(self) -> int:
        return int(self.call("getblockcount"))

    def best(self) -> str:
        return self.call("getbestblockhash")


def wait_for(condition, what: str, seconds: float = 120.0) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.25)
    raise Prerequisite(f"timed out waiting for {what}")


class Pair:
    """Node A and Node B on one fresh chain, connected."""

    def __init__(self, node_a: Path, node_b: Path, work: Path, send: RunUser, admin: RunUser,
                 extra_rpcs: frozenset = frozenset(), miner: RunUser | None = None,
                 miner_rpcs: frozenset = frozenset()):
        # 1e-2b-2b: only node A gets the miner user, when one is given.
        self.a = Node("A", node_a, work / "a", (ports := draw_ports(4))[0], send, admin, extra_rpcs, miner, miner_rpcs, port=ports[1])
        self.b = Node("B", node_b, work / "b", ports[2], send, admin, extra_rpcs, port=ports[3])   # #682: one draw

    def start(self) -> None:
        self.a.start()
        self.b.start()
        for node in self.both():
            node.cookie_refused()
        self.b.call("addnode", f"127.0.0.1:{self.a.port}", "onetry")
        wait_for(lambda: self.a.call("getconnectioncount") >= 1, "the two nodes to connect")

    def stop(self) -> None:
        self.b.stop()
        self.a.stop()

    def both(self) -> tuple[Node, Node]:
        return (self.a, self.b)

    def agreed(self, height: int) -> str:
        """Both nodes at `height` with one best hash."""
        wait_for(lambda: self.a.height() == height and self.b.height() == height, f"both nodes at {height}", 300.0)
        hashes = {node.best() for node in self.both()}
        if len(hashes) != 1:
            raise Mismatch(f"nodes disagree at height {height}")
        return hashes.pop()

    def mine(self, descriptor: str, blocks: int) -> str:
        start = self.a.height()
        self.a.call("generatetodescriptor", str(blocks), descriptor)
        return self.agreed(start + blocks)

    # rn-2's node changes (module docs). Each waits until it holds.

    def isolate_b(self) -> None:
        """Node B's P2P off."""
        self.b.call("setnetworkactive", "false")
        wait_for(lambda: self.a.call("getconnectioncount") == 0, "node B to leave")

    def fork_b(self, descriptor: str) -> tuple[str, str]:
        """Node B, isolated, on its own block at the tip's height:
        returns (the agreed tip, node B's)."""
        tip = self.b.best()
        self.b.call("invalidateblock", tip)
        self.b.call("generatetodescriptor", "1", descriptor)
        wait_for(lambda: self.b.height() == TIP_HEIGHT and self.b.best() != tip, "node B's own block")
        self.b.call("setnetworkactive", "true")
        return tip, self.b.best()

    def join_b(self, tip: str, own: str | None = None) -> None:
        """Node B back on `tip` (off its own block `own`), connected."""
        if own is not None:
            self.b.call("invalidateblock", own)
            self.b.call("reconsiderblock", tip)
        self.b.call("setnetworkactive", "true")
        self.b.call("addnode", f"127.0.0.1:{self.a.port}", "onetry")
        wait_for(lambda: self.a.call("getconnectioncount") >= 1, "the two nodes to connect")
        if {node.best() for node in self.both()} != {tip}:
            raise Mismatch("node B is not back on the tip")

    def fee_delta(self, node: "Node", txid: str, delta: int) -> None:
        """A fee delta on `txid` at `node` (the transaction need not be
        known): submits nothing."""
        node.call("prioritisetransaction", txid, "0", str(delta))

    # 1e-2a's node changes (module docs). Each waits until it holds.

    def replace_tip(self, descriptor: str) -> tuple[str, str]:
        """X -> X' at the tip's height: both nodes invalidate the agreed tip
        X, node A mines X' to `descriptor` (another coinbase), and both agree
        on it. Returns (X, X')."""
        tip = self.agreed(TIP_HEIGHT)
        for node in self.both():
            node.call("invalidateblock", tip)
        self.a.call("generatetodescriptor", "1", descriptor)
        replaced = self.agreed(TIP_HEIGHT)
        if replaced == tip:
            raise Mismatch("the tip was not replaced")
        return tip, replaced

    def lower_tip(self) -> str:
        """Both nodes invalidate the agreed tip: they agree one block lower.
        Returns that block."""
        tip = self.agreed(TIP_HEIGHT)
        for node in self.both():
            node.call("invalidateblock", tip)
        return self.agreed(TIP_HEIGHT - 1)

    # 1e-2b-2a's node change.

    def drop_block(self, block: str, height: int) -> str:
        """Both nodes invalidate `block`, the agreed tip at `height`: they
        agree on its parent. Returns the parent."""
        if self.agreed(height) != block:
            raise Mismatch("the block to drop is not the agreed tip")
        for node in self.both():
            node.call("invalidateblock", block)
        return self.agreed(height - 1)

    def restore_tip(self, tip: str) -> None:
        """Both nodes reconsider `tip` and agree on it again."""
        for node in self.both():
            node.call("reconsiderblock", tip)
        if self.agreed(TIP_HEIGHT) != tip:
            raise Mismatch("the tip was not restored")


def internal(display_hex: str) -> str:
    """A hash in internal byte order from Core's display order."""
    return bytes.fromhex(display_hex)[::-1].hex()


def sats(btc: decimal.Decimal) -> int:
    value = btc * 100_000_000
    if value != value.to_integral_value():
        raise Mismatch("VALUE_NOT_WHOLE_SATS")
    return int(value)


def chain_facts(pair: Pair, tip: str, height: int = TIP_HEIGHT) -> tuple[str, dict]:
    """The chain facts both nodes agree on, as the offline stage reads
    them (the lines of `chain-facts.txt`), and the funding coinbase output."""
    a, b = pair.both()
    genesis = {node.call("getblockhash", "0") for node in (a, b)}
    if len(genesis) != 1:
        raise Mismatch("GENESIS_DISAGREES")
    block = a.call("getblock", a.call("getblockhash", str(FUNDING_HEIGHT)), "2")
    coinbase = block["tx"][0]
    outputs = [o for o in coinbase["vout"] if o["scriptPubKey"]["hex"] == FUNDING_SCRIPT]
    if len(outputs) != 1:
        raise Mismatch("FUNDING_OUTPUT")
    vout = outputs[0]["n"]
    coins = [node.call("gettxout", coinbase["txid"], str(vout), "false") for node in (a, b)]
    if coins[0] != coins[1] or not coins[0] or not coins[0]["coinbase"]:
        raise Mismatch("FUNDING_COIN")
    if coins[0]["confirmations"] < COINBASE_MATURITY or coins[0]["scriptPubKey"]["hex"] != FUNDING_SCRIPT:
        raise Mismatch("FUNDING_COIN")
    funding = {"txid": coinbase["txid"], "vout": vout, "value_sat": sats(coins[0]["value"])}
    text = "".join(
        f"{line}\n"
        for line in [
            f"genesis={internal(genesis.pop())}",
            f"tip_height={height}",
            f"tip_hash={internal(tip)}",
            f"fee_txid={internal(coinbase['txid'])}",
            f"fee_vout={vout}",
            f"fee_value={funding['value_sat']}",
            f"fee_height={FUNDING_HEIGHT}",
        ]
    )
    return text, funding


def stage_lines(stdout: bytes, worker: str) -> list[tuple[str, str]]:
    """The worker's `E3D3_STAGE_V1` lines, bounded. libtest may print a
    line after its own `test <name> ... ` prefix."""
    result = []
    other = 0
    for line in stdout.split(b"\n"):
        if len(line) > MAX_STAGE_LINE:
            raise Mismatch("STAGE_LINE_BOUND")
        text = line.decode("ascii", errors="replace")
        at = text.find(STAGE + "\t")
        if at < 0:
            other += 1
            if other > MAX_OTHER_LINES:
                raise Mismatch("WORKER_OUTPUT_BOUND")
            continue
        if at and not text[:at].startswith(f"test {worker} ... "):
            raise Mismatch("STAGE_LINE_PREFIX")
        fields = text[at:].split("\t")
        if len(fields) != 3:
            raise Mismatch("STAGE_FIELDS")
        result.append((fields[1], fields[2]))
    return result


def check_stage(lines: list[tuple[str, str]], expected: list[str]) -> dict:
    """The stage printed exactly `expected`, in order, each PASS line as
    PASS; returns the values."""
    names = [name for name, _ in lines]
    if names != expected:
        raise Mismatch(f"stage lines {names}, expected {expected}")
    for name, value in lines:
        if name in PASS_LINES and value != "PASS":
            raise Mismatch(f"{name} {value}")
    return dict(lines)


def scan_secrets(text: str, needles: tuple[str, ...] = (), ports: tuple[int, ...] = ()) -> list[str]:
    """Credential, cookie, user name, endpoint host or port in the text,
    and any of `needles` (the send-only user's credential, the log and
    state paths, the work directory). A port counts only as a whole
    number, not inside hex. Moved from the launch-restart driver
    (`scan_secrets`) with `needles` added (A #258 issuecomment-6255049643)."""
    fixture = hashlib.sha256(AUTH_RECIPE.encode("ascii")).hexdigest()
    found = []
    for needle in (AUTH_USER, fixture, "rpcauth", "rpcpassword", "rpcuser", "cookie", "127.0.0.1", "localhost"):
        if needle in text:
            found.append(f"output contains a forbidden token ({needle[:4]}...)")
    for needle in needles:
        # Also as json.dumps writes it (#615): a path with a backslash, quote
        # or non-ASCII character is escaped in a JSON summary or row file.
        if needle and (needle in text or json.dumps(needle)[1:-1] in text):
            found.append("output contains a run secret or path")
    for port in ports:
        if re.search(rf"(?<![0-9A-Za-z]){port}(?![0-9A-Za-z])", text):
            found.append("output contains a port")
    return found


class Secrets:
    """What no worker output or summary may contain: `scan_secrets`'s
    tokens, these needles and these ports."""

    def __init__(self, needles: tuple[str, ...] = (), ports: tuple[int, ...] = ()):
        self.needles = needles
        self.ports = ports

    def check(self, text: str, what: str) -> None:
        found = scan_secrets(text, self.needles, self.ports)
        if found:
            raise Mismatch(f"{what}: {found[0]}")


def run_stage(
    command: list[str], env: dict, worker: str, expected: list[str], seconds: int = STAGE_SECONDS, secrets_: Secrets | None = None
) -> dict:
    """Runs one worker to its end. A nonzero exit, a timeout or a missing
    or extra result line is a FAIL (exit 2): the worker ended during the
    test (N6). A passing worker's output is scanned (`Secrets`)."""
    try:
        done = subprocess.run(command, env=env, cwd=ROOT, capture_output=True, timeout=seconds, check=False)
    except subprocess.TimeoutExpired:
        raise Mismatch(f"{worker} timed out") from None
    lines = stage_lines(done.stdout, worker)
    if done.returncode != 0:
        # A failing worker's stderr is relayed only when the scan finds
        # nothing in it (Codex review on #431: a panic may carry a
        # credential, a port or a path).
        # The whole of it is scanned, then cut (A #258
        # issuecomment-6262367082: a needle across the cut).
        stderr = done.stderr.decode("utf-8", errors="replace")
        found = [] if secrets_ is None else scan_secrets(stderr, secrets_.needles, secrets_.ports)
        sys.stderr.write("(the worker's standard error is withheld: the secret scan matched it)\n" if found else stderr[-4000:])
        raise Mismatch(f"{worker} ended with exit {done.returncode} after {[n for n, _ in lines]}")
    if secrets_ is not None:
        for stream in (done.stdout, done.stderr):
            secrets_.check(stream.decode("utf-8", errors="replace"), worker)
    return check_stage(lines, expected)


def worker_command(cargo: str, test: str, worker: str, features: list[str], package: str = "bitagi-signer") -> list[str]:
    return [
        cargo, "test", "--locked", "-q", "-p", package, *features, "--test", test, "--",
        "--exact", worker, "--ignored", "--nocapture", "--test-threads=1",
    ]


def listing(path: Path) -> list[str]:
    return sorted(entry.name for entry in path.iterdir())


def check_handoff(stage_dir: Path, candidate: str) -> Path:
    """Between the stages: only `handoff/` with the three files."""
    if listing(stage_dir) != ["handoff"]:
        raise Mismatch(f"STAGE_DIR {listing(stage_dir)}")
    handoff = stage_dir / "handoff"
    if listing(handoff) != sorted([f"{candidate}.export", "input.txt", "wallet.sqlite"]):
        raise Mismatch(f"HANDOFF {listing(handoff)}")
    return handoff


def check_nothing_sent(pair: Pair, tip: str, funding: dict, txid: str | None, height: int = TIP_HEIGHT) -> None:
    """Both mempools empty, the tip unmoved and the funding output unspent
    (mempool included), so nothing was submitted."""
    for node in pair.both():
        if node.call("getmempoolinfo")["size"] != 0:
            raise Mismatch(f"{node.label}: mempool not empty")
        if node.height() != height or node.best() != tip:
            raise Mismatch(f"{node.label}: tip moved")
        if not node.call("gettxout", funding["txid"], str(funding["vout"]), "true"):
            raise Mismatch(f"{node.label}: funding output spent")
        if txid is not None:
            done = node.raw("getmempoolentry", txid)
            if done.returncode == 0 or "error code: -5" not in done.stderr:
                raise Mismatch(f"{node.label}: the export transaction is known")


def check_submitted(
    pair: Pair, tip: str, funding: dict, txid: str, nodes: tuple | None = None, height: int = TIP_HEIGHT
) -> None:
    """After the launch host's step 8: both mempools (or those of `nodes`)
    hold exactly `txid`, `txid` alone spends the funding output (in the
    mempool; the chain still has it unspent), and the tip did not move."""
    outpoint = json.dumps([{"txid": funding["txid"], "vout": funding["vout"]}], separators=(",", ":"))
    for node in nodes or pair.both():
        if node.call("getmempoolinfo")["size"] != 1:
            raise Mismatch(f"{node.label}: mempool is not the one transaction")
        if node.height() != height or node.best() != tip:
            raise Mismatch(f"{node.label}: tip moved")
        if node.raw("getmempoolentry", txid).returncode != 0:
            raise Mismatch(f"{node.label}: the launch transaction is not in its mempool")
        if node.call("gettxout", funding["txid"], str(funding["vout"]), "true"):
            raise Mismatch(f"{node.label}: funding output not spent in the mempool")
        if not node.call("gettxout", funding["txid"], str(funding["vout"]), "false"):
            raise Mismatch(f"{node.label}: funding output spent in the chain")
        spending = node.call("gettxspendingprevout", outpoint)
        if [entry.get("spendingtxid") for entry in spending] != [txid]:
            raise Mismatch(f"{node.label}: the funding output's spender is not the launch transaction")


def sign_tip_lines(tip: str, height: int = TIP_HEIGHT) -> str:
    """The launch facts' last two lines: the tip the host signs at, H0 - 1
    (#484 L0: H0 - 2; the charge stage writes the base for it)."""
    return f"sign_tip_height={height}\nsign_tip_hash={internal(tip)}\n"


def check_boundary(launch: Path, name: str, values: dict) -> None:
    """The boundary `name` (`BOUNDARIES`): its directory holds exactly its
    files, `<...>` filled from `values` (each 64 lower-case hex digits)."""
    _, _, directory, names = BOUNDARIES[name]
    expected = []
    for item in names:
        for key, value in values.items():
            if not re.fullmatch(r"[0-9a-f]{64}", value):
                raise Mismatch(f"{name}: {key} is not a digest")
            item = item.replace(f"<{key}>", value)
        if "<" in item:
            raise Mismatch(f"{name}: unfilled {item}")
        expected.append(item)
    if listing(launch / directory) != sorted(expected):
        raise Mismatch(f"LAUNCH_{name.upper()} {listing(launch / directory)}")


def scan_key_material(work: Path) -> None:
    """No file under `work` holds a key file's scalar line."""
    needle = b"private_" + b"scalar="
    for path in sorted(work.rglob("*")):
        if path.is_file() and not path.is_symlink() and needle in path.read_bytes():
            raise Mismatch("a key file's scalar line is left in the work directory")


def check_descriptor(text: str, genesis_internal: str) -> str:
    """The describe stage's descriptor: one line of lower-case hex, a
    version 2 Regtest descriptor (`DESCRIPTOR_BYTES`, `DESCRIPTOR_TAG`,
    version 2, network byte 1) of the nodes' genesis."""
    if not re.fullmatch(r"[0-9a-f]+", text) or len(text) != 2 * DESCRIPTOR_BYTES:
        raise Mismatch("DESCRIPTOR_FORM")
    raw = bytes.fromhex(text)
    if raw[:8] != DESCRIPTOR_TAG or raw[8] != 2 or raw[9] != 1 or raw[13:45].hex() != genesis_internal:
        raise Mismatch("DESCRIPTOR_FORM")
    return text


def check_listing(path: Path, expected: list[str], what: str) -> None:
    if listing(path) != sorted(expected):
        raise Mismatch(f"{what} {listing(path)}")


def private(path: Path) -> Path:
    path.mkdir(mode=0o700)
    path.chmod(0o700)
    return path


# 1e-2b-1: the host's event lines and the B phases' worker.
B_WORKER = "launch_b_worker"
B_LINES = ["phase", "steps", "hand_offs", "lines_failed", "turns", "b_stage"]
EVENT_NAMES = frozenset(
    ["S2", "B_A_1", "B_B_1"]
    + [f"STEP_{k}_{end}" for k in range(1, 11) for end in ("START", "END")]
    + [f"O_{n} {o}" for n in "AB" for o in ("ACCEPTED", "REJECTED", "TIMED_OUT")]
)
MAX_EVENT_FILE = 4096
ACK_SECONDS = 120.0


def event_names(path: Path, secrets_: Secrets | None) -> list[str]:
    """The names of the event line file at `path`: each line
    `XD1_LINE_V1 <seq> <NAME>[ <OUTCOME>]`, seq from 1 in order, the name
    from the closed set; the file scanned like a worker's output."""
    data = path.read_bytes()
    if len(data) > MAX_EVENT_FILE:
        raise Mismatch(f"{path.name}: event lines too long")
    text = data.decode("ascii")
    if secrets_ is not None:
        secrets_.check(text, path.name)
    if text and not text.endswith("\n"):
        raise Mismatch(f"{path.name}: an unterminated event line")
    names = []
    # LF only: `splitlines` would take CR, VT and the other line ends too.
    for i, line in enumerate(text.split("\n")[:-1]):
        prefix = f"XD1_LINE_V1 {i + 1} "
        if not line.startswith(prefix) or line[len(prefix):] not in EVENT_NAMES:
            raise Mismatch(f"{path.name}: event line {i + 1} malformed")
        names.append(line[len(prefix):])
    return names


class Acker(threading.Thread):
    """XD-1 ack smoke (Q-B2): waits for the S2 line in the event file, then
    writes `XD1_ACK_V1 <seq>` to the FIFO the worker reads. Keeps the names
    written when it acked (only S2: T2-12)."""

    def __init__(self, lines: Path, fifo: Path, seq: int):
        super().__init__(daemon=True)
        self.lines, self.fifo, self.seq = lines, fifo, seq
        self.at_ack: list[str] | None = None

    def run(self) -> None:
        deadline = time.monotonic() + ACK_SECONDS
        while time.monotonic() < deadline:
            if self.lines.exists() and f"XD1_LINE_V1 {self.seq} S2\n" in self.lines.read_text(encoding="ascii"):
                break
            time.sleep(0.05)
        else:
            return
        while time.monotonic() < deadline:
            try:
                fd = os.open(self.fifo, os.O_WRONLY | os.O_NONBLOCK)
            except OSError:
                time.sleep(0.05)
                continue
            self.at_ack = event_names(self.lines, None)
            os.write(fd, f"XD1_ACK_V1 {self.seq}\n".encode("ascii"))
            os.close(fd)
            return


# bitcoin-cli's answer when the node's mempool lacks the transaction (RPC
# error -5, exit code 5; seen on Core 31.1 and 30.3).
NOT_IN_MEMPOOL = ["error code: -5", "error message:", "Transaction not in mempool"]


def mempools(pair: Pair, txid: str) -> tuple[str, str]:
    """Each node's mempool for `txid`: "present" or "absent". Present on
    both: the same wtxid. "absent" is only the node's own not-in-mempool
    answer; any other failed read (no connection, refused credentials, a
    node still warming up) is a Prerequisite, never an absence (Desktop P2
    on #494, r4366744128)."""
    states, wtxids = [], set()
    for node in pair.both():
        done = node.raw("getmempoolentry", txid)
        if done.returncode == 5 and done.stderr.splitlines() == NOT_IN_MEMPOOL:
            states.append("absent")
            continue
        if done.returncode != 0:
            raise Prerequisite(f"{node.label}: getmempoolentry failed: {done.stderr.strip()[:200]}")
        wtxids.add(json.loads(done.stdout)["wtxid"])
        states.append("present")
    if len(wtxids) > 1:
        raise Mismatch("the nodes hold different wtxids")
    return tuple(states)


def b_phase(host, env: dict, work: Path, name: str, secrets_: Secrets) -> dict:
    """1e-2b-1's phase `name` (`launch_b_worker`), `B_RUNS` new processes,
    each with its own event line file; every run reports the same."""
    runs = []
    for i in range(B_RUNS.get(name, 1)):
        stage_env = dict(env)
        stage_env["BITAGI_E3D3_PHASE"] = name
        lines = work / f"lines-{name}-{i}.txt"
        stage_env["BITAGI_E3D3_EVENT_LINES"] = str(lines.resolve())
        got = host(B_WORKER, B_LINES, stage_env)
        if (got["phase"], got["steps"], got["hand_offs"], got["lines_failed"]) != (name, B_STEPS[name], B_HAND_OFFS[name], "false"):
            raise Mismatch(f"{name}: {got}")
        if event_names(lines, secrets_) != EVENT_LINES[name]:
            raise Mismatch(f"{name} event lines {event_names(lines, None)}")
        runs.append(got)
    if any(run != runs[0] for run in runs[1:]):
        raise Mismatch(f"{name}: a new process reported otherwise")
    return runs[0]


def refusal_line(stderr: str) -> str | None:
    """The `refusal` value of the first JSON line of a documented Python
    command's standard error that has it as a string (formats doc refusal
    line); other keys are ignored."""
    for line in stderr.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict) and isinstance(value.get("refusal"), str):
            return value["refusal"][:200]
    return None


def run_reference(name: str, args: list[str]) -> tuple[int, str | None]:
    """Runs one documented Python command (`PRESTATE_COMMANDS`) as a black
    box; returns its exit code and its refusal line's `refusal`."""
    script, subcommand = PRESTATE_COMMANDS[name]
    try:
        done = subprocess.run(
            [sys.executable, "-B", str(REFERENCE_DIR / script), subcommand, *args],
            cwd=ROOT,
            capture_output=True,
            timeout=PRESTATE_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise Mismatch(f"PRESTATE_{name.upper()}_TIMEOUT") from None
    return done.returncode, refusal_line(done.stderr.decode("utf-8", errors="replace"))


def read_report(path: Path) -> dict:
    """The comparison report: a regular file within the formats doc's bound,
    one JSON object."""
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > PRESTATE_FILE_LIMIT:
            raise Mismatch("PRESTATE_REPORT")
        value = json.loads(path.read_bytes())
    except (OSError, ValueError):
        raise Mismatch("PRESTATE_REPORT") from None
    if not isinstance(value, dict):
        raise Mismatch("PRESTATE_REPORT")
    return value


def prestate_inputs(pair: Pair, height: int, tip_height: int | None = None, tip_hash: str | None = None) -> tuple[str, str, str]:
    """G, H and B as both nodes give them, never one side's: the genesis, the hash at `height` and its raw block, byte-equal; both best
    blocks one hash, the run tip's: the block at `height`, or with `tip_height` above it `tip_hash`, the hash mined (B-692a-RT)."""
    a, b = pair.both()
    genesis, hashes = ({node.call("getblockhash", str(h)) for node in (a, b)} for h in (0, height))
    bests = {node.best() for node in (a, b)}
    tips = hashes if tip_height in (None, height) else {tip_hash}
    for bad, reason in zip((len(genesis) != 1, len(hashes) != 1, len(bests) != 1, bests != tips), PRESTATE_REFUSALS):
        if bad:
            raise Mismatch(reason)
    if len(raw := {node.call("getblock", next(iter(hashes)), "0") for node in (a, b)}) != 1:
        raise Mismatch(PRESTATE_RAW_DISAGREE)
    return genesis.pop(), hashes.pop(), raw.pop()


def write_text(path: Path, text: str, limit: int, reason: str) -> bytes:
    """One lowercase hex line and one LF (formats doc section 1.1), written
    new."""
    data = (text + "\n").encode("ascii")
    if not re.fullmatch(r"(?:[0-9a-f]{2})+", text) or len(data) > limit:
        raise Mismatch(reason)
    with open(path, "xb") as handle:
        handle.write(data)
    return data


def base_profile(launch: Path) -> str:
    """P: the profile the charge stage's base states, the host's profile."""
    base = (launch / "handoff" / "base.txt").read_text(encoding="ascii")
    found = [line.removeprefix("profile=") for line in base.splitlines() if line.startswith("profile=")]
    if len(found) != 1:
        raise Mismatch("PRESTATE_PROFILE")
    return found[0]


def run_prestate(pair: Pair, launch: Path, directory: Path, receipt_name: str, height: int = TIP_HEIGHT, tip_height=None, tip_hash=None) -> dict:
    """1d-3d-3d (module docs): takes the host's Rust receipt out of the
    outbox, makes the Python receipt from the driver's own reads with
    `produce` and compares the two with `compare --raw-block`. Exit 0 and a
    MATCH report with `raw_block_checked` pass; any other result is a FAIL.
    Returns the files for the phase's second run, their SHA-256s and the
    two commands' seconds (B-692a-RT: `tip_height`, `tip_hash`, `prestate_inputs`)."""
    if not RECEIPT_NAME.fullmatch(receipt_name):
        raise Mismatch("PRESTATE_RECEIPT_NAME")
    private(directory)
    rust = directory / "rust-receipt.json"
    held = launch / "outbox" / receipt_name
    if held.is_symlink() or not held.is_file() or held.stat().st_size > PRESTATE_FILE_LIMIT:
        raise Mismatch("PRESTATE_RUST_RECEIPT")
    held.rename(rust)
    # The file is the one its name names (B P3-4 on #477).
    if hashlib.sha256(rust.read_bytes()).hexdigest() != receipt_name.removeprefix("h0-receipt-").removesuffix(".json"):
        raise Mismatch("PRESTATE_RUST_RECEIPT")
    genesis, tip, raw = prestate_inputs(pair, height, tip_height, tip_hash)
    inputs = private(directory / "inputs")
    write_text(inputs / "profile.hex", base_profile(launch), PROFILE_TEXT_LIMIT, "PRESTATE_PROFILE")
    write_text(inputs / "h0_minus_1.hex", raw, RAW_TEXT_LIMIT, "PRESTATE_RAW_BLOCK")
    python = directory / "python-receipt.json"
    report = directory / "report.json"
    started = time.monotonic()
    code, refusal = run_reference(
        "produce",
        [
            "--network", "regtest", "--profile", str(inputs / "profile.hex"), "--chain-genesis-hash", genesis,
            "--h0-minus-1-block-hash", tip, "--raw-block", str(inputs / "h0_minus_1.hex"), "--output", str(python),
        ],
    )
    produced = time.monotonic()
    if code != 0 or not python.is_file():
        raise Mismatch(f"PRESTATE_PRODUCE exit {code} {refusal}")
    code, refusal = run_reference(
        "compare",
        [
            "--python-receipt", str(python), "--other-receipt", str(rust), "--raw-block",
            str(inputs / "h0_minus_1.hex"), "--output", str(report),
        ],
    )
    compared = time.monotonic()
    if code != 0:
        raise Mismatch(f"PRESTATE_COMPARE exit {code} {refusal}")
    result = read_report(report)
    if result.get("result") != "MATCH" or result.get("raw_block_checked") is not True:
        raise Mismatch("PRESTATE_REPORT_NOT_MATCH")
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()  # noqa: E731
    return {
        "env": {"BITAGI_E3D3_PRESTATE_RECEIPT": str(python.resolve()), "BITAGI_E3D3_PRESTATE_REPORT": str(report.resolve())},
        "rust_receipt_sha256": digest(rust),
        "python_receipt_sha256": digest(python),
        "report_sha256": digest(report),
        "produce_ms": round((produced - started) * 1000),
        "compare_ms": round((compared - produced) * 1000),
    }


def prestate_summary(name: str, pending: dict, compared: dict, done: dict) -> dict:
    """One comparison's record: the phase it ends, the three SHA-256s and
    the H0 - 1 stage's wall clock (the host's prestate turns of both runs,
    `produce` and `compare`), also written to the job summary under GitHub
    Actions."""
    record = {"phase": name}
    record.update({key: value for key, value in compared.items() if key != "env"})
    record["host_turns_ms"] = int(pending["prestate_ms"]) + int(done["prestate_ms"])
    record["stage_ms"] = record["host_turns_ms"] + record["produce_ms"] + record["compare_ms"]
    job_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if job_summary:
        with open(job_summary, "a", encoding="utf-8") as handle:
            handle.write(
                f"- H0-1 comparison `{name}`: Rust receipt `{record['rust_receipt_sha256']}`, "
                f"Python receipt `{record['python_receipt_sha256']}`, report `{record['report_sha256']}`, "
                f"stage {record['stage_ms']} ms\n"
            )
    return record


def run_launch(
    pair: Pair, work: Path, chain: str, tip: str, funding: dict, cargo: str, offline_env: dict, online_env: dict, send: RunUser, secrets_: Secrets
) -> dict:
    """Steps 3-7 (module docs): the launch host's accept path. `chain` is
    the chain facts text; `offline_env` and `online_env` are each build's
    environment without stage values."""
    summary: dict = {"labels": LAUNCH_LABELS}
    online = dict(online_env)
    online.update(
        {
            "BITAGI_E3D3_NODE_A_PORT": str(pair.a.rpcport),
            "BITAGI_E3D3_NODE_B_PORT": str(pair.b.rpcport),
            "BITAGI_E3D3_NODE_A_LOG": pair.a.log_path,
            "BITAGI_E3D3_NODE_B_LOG": pair.b.log_path,
        }
    )
    genesis = chain.split("\n", 1)[0].removeprefix("genesis=")

    def host(worker: str, lines: list[str], env: dict) -> dict:
        command = worker_command(cargo, HOST_TEST, worker, [], HOST_PACKAGE)
        return run_stage(command, env, worker, lines, secrets_=secrets_)

    def signer(worker: str, lines: list[str], env: dict) -> dict:
        command = worker_command(cargo, LAUNCH_SIGNER_TEST, worker, ["--features", "offline-ceremony"], SIGNER_PACKAGE)
        return run_stage(command, env, worker, lines, secrets_=secrets_)

    described = host(DESCRIBE_WORKER, DESCRIBE_LINES, online)
    descriptor = check_descriptor(described["descriptor"], genesis)
    summary["descriptor_sha256"] = hashlib.sha256(bytes.fromhex(descriptor)).hexdigest()
    check_nothing_sent(pair, tip, funding, None)

    launch = private(work / "launch")
    for name in ("handoff", "outbox", "export", "host"):
        private(launch / name)
    facts = work / "launch-facts.txt"
    facts.write_text(chain + f"descriptor={descriptor}\n" + sign_tip_lines(tip), encoding="ascii", newline="")
    facts.chmod(0o600)
    tmp = private(work / "launch-tmp")
    offline = dict(offline_env)
    offline.update({"BITAGI_E3D3_LAUNCH_FILE": str(facts.resolve()), "TMPDIR": str(tmp.resolve())})
    online["BITAGI_E3D3_LAUNCH"] = str(launch.resolve())
    try:
        summary["charge_stage"] = signer(CHARGE_WORKER, CHARGE_LINES, offline)
        check_boundary(launch, "charge", {})
        scan_key_material(work)
        check_nothing_sent(pair, tip, funding, None)

        # 1e-2b-1: the event lines and the XD-1 ack smoke are the first
        # process's, which writes S2 (1d-3d-3d: it ends at the comparison).
        sign_env = dict(online)
        sign_lines = work / "lines-sign.txt"
        fifo = work / "ack-sign.fifo"
        os.mkfifo(fifo, 0o600)
        sign_env["BITAGI_E3D3_EVENT_LINES"] = str(sign_lines.resolve())
        sign_env["BITAGI_E3D3_XD1_ACK"] = str(fifo.resolve())
        acker = Acker(sign_lines, fifo, XD1_ACK_SEQ["sign"])
        acker.start()
        pending = host(HOST_SIGN_WORKER, HOST_SIGN_LINES, sign_env)
        acker.join(5)
        fifo.unlink()
        if acker.at_ack != ["S2"]:
            raise Mismatch(f"ack smoke: lines at the ack {acker.at_ack}")
        if event_names(sign_lines, secrets_) != EVENT_LINES["sign"]:
            raise Mismatch(f"sign event lines {event_names(sign_lines, None)}")
        summary["xd1_ack_smoke"] = "PASS"
        if pending["steps"] != PENDING_STEPS:
            raise Mismatch(f"sign steps {pending['steps']}")
        check_nothing_sent(pair, tip, funding, None)
        compared = run_prestate(pair, launch, private(work / "prestate") / "sign", pending["prestate_receipt"])
        signed_lines = work / "lines-sign-compared.txt"
        signed = host(HOST_SIGN_WORKER, HOST_SIGN_LINES, {**online, **compared["env"], "BITAGI_E3D3_EVENT_LINES": str(signed_lines.resolve())})
        if event_names(signed_lines, secrets_) != EVENT_LINES["sign_compared"]:
            raise Mismatch(f"compared sign event lines {event_names(signed_lines, None)}")
        if signed["steps"] != SIGN_STEPS or signed["prestate_receipt"] != "-":
            raise Mismatch(f"sign steps {signed['steps']}")
        summary["prestate_comparisons"] = [prestate_summary("sign", pending, compared, signed)]
        summary["host_sign_stage"] = signed
        outbox = listing(launch / "outbox")
        entry = outbox[0].removeprefix("sign-input-").removesuffix(".txt") if len(outbox) == 1 else "-"
        check_boundary(launch, "sign", {"entry": entry})
        scan_key_material(work)
        check_nothing_sent(pair, tip, funding, None)

        try:
            exported = signer(OFFLINE_SIGN_WORKER, OFFLINE_SIGN_LINES, offline)
        except BaseException:
            # A worker that failed may leave its session root and the
            # TEST_ONLY key files: remove them.
            shutil.rmtree(launch / "offline", ignore_errors=True)
            raise
        summary["offline_sign_stage"] = exported
        check_listing(launch, ["export", "handoff", "host", "outbox"], "LAUNCH_DIR")
        check_boundary(launch, "export", {"candidate": exported["candidate_id"]})
        scan_key_material(work)
        check_nothing_sent(pair, tip, funding, None)
    finally:
        # Nothing of the offline stages but their handed-on files stays for
        # the online stage: not their scratch files, not the facts file.
        shutil.rmtree(tmp)
        facts.unlink()

    broadcast_env = dict(online)
    broadcast_env["BITAGI_E3D3_SEND_AUTH"] = send.auth()
    broadcast_lines = work / "lines-broadcast.txt"
    broadcast_env["BITAGI_E3D3_EVENT_LINES"] = str(broadcast_lines.resolve())
    broadcast = host(HOST_BROADCAST_WORKER, HOST_BROADCAST_LINES, broadcast_env)
    if event_names(broadcast_lines, secrets_) != EVENT_LINES["broadcast"]:
        raise Mismatch(f"broadcast event lines {event_names(broadcast_lines, None)}")
    if broadcast["steps"] != BROADCAST_STEPS or (broadcast["prestate_receipt"], broadcast["prestate_ms"]) != ("-", "0"):
        raise Mismatch(f"broadcast steps {broadcast['steps']}")
    if broadcast["hand_offs"] != HAND_OFFS:
        raise Mismatch(f"hand-offs {broadcast['hand_offs']}")
    # The bytes step 8 handed off are the offline signature's export.
    if broadcast["raw_tx_sha256"] != exported["raw_tx_sha256"]:
        raise Mismatch("the broadcast bytes are not the offline export's")
    summary["host_broadcast_stage"] = broadcast
    check_submitted(pair, tip, funding, broadcast["txid"])
    summary["submitted_by_step_8_only"] = "PASS"
    summary["event_lines"] = "PASS"
    # 1e-2b-1 L2: new processes, nodes unchanged, the credential given.
    txid = broadcast["txid"]
    for name in ("after_send", "cn01"):
        if name == "cn01":
            # L3: X -> X' at H0 - 1 on both nodes (1e-2a's helper).
            replaced = pair.replace_tip(pair.a.call("getdescriptorinfo", "raw(51)")["descriptor"])
            summary["cn01_tips"] = {"x": replaced[0], "x_replaced": replaced[1]}
        summary[f"phase_{name}"] = b_phase(host, broadcast_env, work, name, secrets_)
        if mempools(pair, txid) != MEMPOOLS[name]:
            raise Mismatch(f"{name}: mempools {mempools(pair, txid)}")
    summary["phase_cn01"] = dict(summary["phase_cn01"], reorged_before_inclusion=CN01["reorged_before_inclusion"])
    return summary


def check_ancestors(work: Path) -> None:
    """The offline binary refuses a session root below a group- or
    world-writable directory; say so before any node starts."""
    for ancestor in work.parents:
        if ancestor.exists() and ancestor.stat().st_mode & 0o022:
            raise Prerequisite(f"{ancestor} is group- or world-writable; choose another --work")


def run_secrets(work: Path, pairs: tuple[Pair, ...], send: RunUser, admin: RunUser) -> Secrets:
    """What no output of this run may hold: both run users' credentials,
    the work directory, every node's log path and ports, and the host
    state paths."""
    nodes = [node for pair in pairs for node in pair.both()]
    return Secrets(
        tuple(send.needles() + admin.needles())
        + (str(work), str(work.resolve()))
        + tuple(node.log_path for node in nodes)
        + tuple(str(work / name / "host" / "state") for name in ("launch", "cases/launch", "e/launch", "l0/launch", "bounded/launch", "r2b/launch", "e8/launch", "l0late/launch")),
        tuple(port for node in nodes for port in (node.rpcport, node.port)),
    )


def run_cases(
    pair: Pair, work: Path, cargo: str, offline_env: dict, online_env: dict, send: RunUser, secrets_: Secrets
) -> dict:
    """rn-2 (module docs): the launch host's cases on `pair`'s own chain.
    `offline_env` and `online_env` are each build's environment without
    stage values."""
    summary: dict = {"labels": LAUNCH_LABELS, "construction_height": CASE_CONSTRUCTION}
    funding_descriptor = pair.a.call("getdescriptorinfo", FUNDING_DESCRIPTOR)["descriptor"]
    constructed = pair.mine(funding_descriptor, CASE_CONSTRUCTION)
    chain, funding = chain_facts(pair, constructed, CASE_CONSTRUCTION)
    summary["funding"] = funding
    online = dict(online_env)
    online.update(
        {
            "BITAGI_E3D3_NODE_A_PORT": str(pair.a.rpcport),
            "BITAGI_E3D3_NODE_B_PORT": str(pair.b.rpcport),
            "BITAGI_E3D3_NODE_A_LOG": pair.a.log_path,
            "BITAGI_E3D3_NODE_B_LOG": pair.b.log_path,
        }
    )
    genesis = chain.split("\n", 1)[0].removeprefix("genesis=")

    def host(worker: str, lines: list[str], env: dict) -> dict:
        command = worker_command(cargo, HOST_TEST, worker, [], HOST_PACKAGE)
        return run_stage(command, env, worker, lines, secrets_=secrets_)

    def signer(worker: str, lines: list[str], env: dict) -> dict:
        command = worker_command(cargo, LAUNCH_SIGNER_TEST, worker, ["--features", "offline-ceremony"], SIGNER_PACKAGE)
        return run_stage(command, env, worker, lines, secrets_=secrets_)

    def phase(name: str, env: dict, catching_up: bool = False) -> dict:
        stage_env = dict(env)
        stage_env["BITAGI_E3D3_PHASE"] = name
        if name in CASE_SENDING:
            stage_env["BITAGI_E3D3_SEND_AUTH"] = send.auth()
        pending = None
        if name in CASE_PENDING:
            # The first run ends at the H0 - 1 comparison (1d-3d-3d).
            pending = host(CASE_WORKER, CASE_LINES, stage_env)
            if (pending["phase"], pending["steps"], pending["hand_offs"]) != (name, CASE_PENDING[name], "0"):
                raise Mismatch(f"{name}: steps {pending['steps']}")
            compared = run_prestate(pair, launch, prestate_dir / name, pending["prestate_receipt"])
            stage_env.update(compared["env"])
        lines = CASE_LINES
        if name in ANSWER_LOST:
            # 1e-2b-1 L4: node A's answer lost by the proxy; the process's
            # event lines.
            stage_env["BITAGI_E3D3_ANSWER_PROXY"] = ANSWER_LOST[name]["node"]
            stage_env["BITAGI_E3D3_EVENT_LINES"] = str((work / f"lines-{name}.txt").resolve())
            lines = CASE_LINES[:-1] + ["answer_lost", CASE_LINES[-1]]
        got = host(CASE_WORKER, lines, stage_env)
        if name in ANSWER_LOST:
            if got["answer_lost"] != ANSWER_LOST[name]["dropped"]:
                raise Mismatch(f"{name}: answers lost {got['answer_lost']}")
            names = event_names(work / f"lines-{name}.txt", secrets_)
            if names != EVENT_LINES[name]:
                raise Mismatch(f"{name} event lines {names}")
        steps = (CASE_STEPS[name], DEEP_CATCH_UP) if catching_up else (CASE_STEPS[name],)
        expected = (name, "-", CASE_HAND_OFFS.get(name, "0"))
        if (got["phase"], got["prestate_receipt"], got["hand_offs"]) != expected or got["steps"] not in steps:
            raise Mismatch(f"{name}: steps {got['steps']}")
        if pending is not None:
            summary.setdefault("prestate_comparisons", []).append(prestate_summary(name, pending, compared, got))
        elif got["prestate_ms"] != "0":
            raise Mismatch(f"{name}: a prestate turn without a comparison")
        # Bytes only where step 8 handed some off.
        if name not in CASE_HAND_OFFS and got["raw_tx_sha256"] != "-":
            raise Mismatch(f"{name}: bytes without a hand-off")
        summary[f"phase_{name}"] = got
        return got

    described = host(DESCRIBE_WORKER, DESCRIBE_LINES, online)
    descriptor = check_descriptor(described["descriptor"], genesis)
    summary["descriptor_sha256"] = hashlib.sha256(bytes.fromhex(descriptor)).hexdigest()
    check_nothing_sent(pair, constructed, funding, None, CASE_CONSTRUCTION)
    # The host turns, and signs, one block above the charge's facts; the
    # charge stage writes the base for that tip (`sign_tip_lines`).
    tip = pair.mine(funding_descriptor, 1)

    # The offline stages find `launch/` beside their facts file.
    root = private(work / "cases")
    launch = private(root / "launch")
    prestate_dir = private(root / "prestate")
    for name in ("handoff", "outbox", "export", "host"):
        private(launch / name)
    facts = root / "launch-facts.txt"
    facts.write_text(chain + f"descriptor={descriptor}\n" + sign_tip_lines(tip), encoding="ascii", newline="")
    facts.chmod(0o600)
    tmp = private(root / "launch-tmp")
    offline = dict(offline_env)
    offline.update({"BITAGI_E3D3_LAUNCH_FILE": str(facts.resolve()), "TMPDIR": str(tmp.resolve())})
    online["BITAGI_E3D3_LAUNCH"] = str(launch.resolve())
    try:
        summary["charge_stage"] = signer(CHARGE_WORKER, CHARGE_LINES, offline)
        check_boundary(launch, "charge", {})
        scan_key_material(work)
        check_nothing_sent(pair, tip, funding, None)

        pair.isolate_b()
        phase("inactive", online)
        own = pair.fork_b(pair.a.call("getdescriptorinfo", "raw(51)")["descriptor"])
        phase("disagree", online)
        pair.join_b(tip, own[1])
        check_nothing_sent(pair, tip, funding, None)
        phase("cases_sign", online)
        outbox = listing(launch / "outbox")
        entry = outbox[0].removeprefix("sign-input-").removesuffix(".txt") if len(outbox) == 1 else "-"
        check_boundary(launch, "sign", {"entry": entry})
        scan_key_material(work)
        check_nothing_sent(pair, tip, funding, None)

        try:
            exported = signer(OFFLINE_SIGN_WORKER, OFFLINE_SIGN_LINES, offline)
        except BaseException:
            shutil.rmtree(launch / "offline", ignore_errors=True)
            raise
        summary["offline_sign_stage"] = exported
        check_listing(launch, ["export", "handoff", "host", "outbox"], "CASES_DIR")
        check_boundary(launch, "export", {"candidate": exported["candidate_id"]})
        scan_key_material(work)
        check_nothing_sent(pair, tip, funding, None)
    finally:
        shutil.rmtree(tmp)
        facts.unlink()

    txid = exported["txid"]
    if not re.fullmatch(r"[0-9a-f]{64}", txid):
        raise Mismatch("the export's txid is not a digest")
    phase("admit", online)
    check_nothing_sent(pair, tip, funding, txid)
    pair.fee_delta(pair.b, txid, -FEE_DELTA)
    sent = phase("broadcast_one", online)
    if sent["raw_tx_sha256"] != exported["raw_tx_sha256"]:
        raise Mismatch("the broadcast bytes are not the offline export's")
    # Node A's mempool holds the transaction; node B, whose delta refuses
    # it, holds nothing.
    check_submitted(pair, tip, funding, txid, (pair.a,))
    if pair.b.call("getmempoolinfo")["size"] != 0:
        raise Mismatch("B: mempool not empty")
    summary["submitted_to_node_a_only"] = "PASS"
    if mempools(pair, txid) != ANSWER_LOST["broadcast_one"]["mempool"]:
        raise Mismatch("broadcast_one: mempools")
    summary["answer_lost"] = dict(ANSWER_LOST["broadcast_one"], mempool=list(ANSWER_LOST["broadcast_one"]["mempool"]))
    # 1e-2b-1 L5: new processes after the one-node send, credential given.
    send_env = dict(online)
    send_env["BITAGI_E3D3_SEND_AUTH"] = send.auth()
    summary["phase_after_send_one"] = b_phase(host, send_env, work, "after_send_one", secrets_)
    if mempools(pair, txid) != MEMPOOLS["after_send_one"]:
        raise Mismatch("after_send_one: mempools")

    # H0, mined by node A with the transaction; both nodes agree.
    pair.mine(funding_descriptor, 1)
    for node in pair.both():
        block = node.call("getblock", node.best(), "1")
        if txid not in block["tx"] or node.call("getmempoolinfo")["size"] != 0:
            raise Mismatch(f"{node.label}: the transaction is not in H0's block")
        if node.call("gettxout", funding["txid"], str(funding["vout"]), "false"):
            raise Mismatch(f"{node.label}: funding output not spent in the chain")
    phase("included", online)
    # Step 9's depth: H0's block more than 4,096 below the tip.
    pair.mine(funding_descriptor, DEEP_BLOCKS)
    for runs in range(1, DEEP_RUNS + 1):
        if phase("deep", online, catching_up=True)["steps"] == CASE_STEPS["deep"]:
            break
    else:
        raise Mismatch("deep: the follower did not catch up")
    summary["deep_catch_up_turns"] = runs - 1
    if len(summary.get("prestate_comparisons", [])) != len(CASE_PENDING):
        raise Mismatch("CASE_PENDING: not every H0 - 1 comparison ran")
    return summary


def run_bounded(pair: Pair, work: Path, cargo: str, offline_env: dict, online_env: dict, secrets_: Secrets) -> dict:
    """#503 (module docs, `BOUND_STEPS`): the per-tip bound on `pair`'s own
    chain, charged at H0 - 2 as rn-2's, the host turning at H0 - 1.
    `offline_env` and `online_env` are each build's environment without
    stage values. No phase reaches step 8 or gets the send credential."""
    summary: dict = {"labels": LAUNCH_LABELS, "construction_height": CASE_CONSTRUCTION}
    funding_descriptor = pair.a.call("getdescriptorinfo", FUNDING_DESCRIPTOR)["descriptor"]
    constructed = pair.mine(funding_descriptor, CASE_CONSTRUCTION)
    chain, funding = chain_facts(pair, constructed, CASE_CONSTRUCTION)
    summary["funding"] = funding
    online = dict(online_env)
    online.update(
        {
            "BITAGI_E3D3_NODE_A_PORT": str(pair.a.rpcport),
            "BITAGI_E3D3_NODE_B_PORT": str(pair.b.rpcport),
            "BITAGI_E3D3_NODE_A_LOG": pair.a.log_path,
            "BITAGI_E3D3_NODE_B_LOG": pair.b.log_path,
        }
    )
    genesis = chain.split("\n", 1)[0].removeprefix("genesis=")

    def host(worker: str, lines: list[str], env: dict) -> dict:
        command = worker_command(cargo, HOST_TEST, worker, [], HOST_PACKAGE)
        return run_stage(command, env, worker, lines, secrets_=secrets_)

    def signer(worker: str, lines: list[str], env: dict) -> dict:
        command = worker_command(cargo, LAUNCH_SIGNER_TEST, worker, ["--features", "offline-ceremony"], SIGNER_PACKAGE)
        return run_stage(command, env, worker, lines, secrets_=secrets_)

    def phase(name: str) -> dict:
        stage_env = dict(online)
        stage_env["BITAGI_E3D3_PHASE"] = name
        pending = None
        if name in BOUND_PENDING:
            # The first run ends at the H0 - 1 comparison (1d-3d-3d).
            pending = host(CASE_WORKER, CASE_LINES, stage_env)
            if (pending["phase"], pending["steps"], pending["hand_offs"]) != (name, BOUND_PENDING[name], "0"):
                raise Mismatch(f"{name}: steps {pending['steps']}")
            compared = run_prestate(pair, launch, prestate_dir / name, pending["prestate_receipt"])
            stage_env.update(compared["env"])
        got = host(CASE_WORKER, CASE_LINES, stage_env)
        expected = (name, BOUND_STEPS[name], "-", "0", "-")
        if (got["phase"], got["steps"], got["prestate_receipt"], got["hand_offs"], got["raw_tx_sha256"]) != expected:
            raise Mismatch(f"{name}: steps {got['steps']}")
        if name == "bounded" and got["turns"] != BOUND_TURNS:
            raise Mismatch(f"bounded: turns {got['turns']}")
        if pending is not None:
            summary.setdefault("prestate_comparisons", []).append(prestate_summary(name, pending, compared, got))
        elif got["prestate_ms"] != "0":
            raise Mismatch(f"{name}: a prestate turn without a comparison")
        summary.setdefault(f"phase_{name}", []).append(got)
        return got

    described = host(DESCRIBE_WORKER, DESCRIBE_LINES, online)
    descriptor = check_descriptor(described["descriptor"], genesis)
    summary["descriptor_sha256"] = hashlib.sha256(bytes.fromhex(descriptor)).hexdigest()
    check_nothing_sent(pair, constructed, funding, None, CASE_CONSTRUCTION)
    tip = pair.mine(funding_descriptor, 1)

    root = private(work / "bounded")
    launch = private(root / "launch")
    prestate_dir = private(root / "prestate")
    for name in ("handoff", "outbox", "export", "host"):
        private(launch / name)
    facts = root / "launch-facts.txt"
    facts.write_text(chain + f"descriptor={descriptor}\n" + sign_tip_lines(tip), encoding="ascii", newline="")
    facts.chmod(0o600)
    tmp = private(root / "launch-tmp")
    offline = dict(offline_env)
    offline.update({"BITAGI_E3D3_LAUNCH_FILE": str(facts.resolve()), "TMPDIR": str(tmp.resolve())})
    online["BITAGI_E3D3_LAUNCH"] = str(launch.resolve())
    try:
        summary["charge_stage"] = signer(CHARGE_WORKER, CHARGE_LINES, offline)
        check_boundary(launch, "charge", {})
        scan_key_material(work)
        check_nothing_sent(pair, tip, funding, None)
        phase("bound_sign")
        outbox = listing(launch / "outbox")
        entry = outbox[0].removeprefix("sign-input-").removesuffix(".txt") if len(outbox) == 1 else "-"
        check_boundary(launch, "sign", {"entry": entry})
        scan_key_material(work)
        check_nothing_sent(pair, tip, funding, None)

        try:
            exported = signer(OFFLINE_SIGN_WORKER, OFFLINE_SIGN_LINES, offline)
        except BaseException:
            shutil.rmtree(launch / "offline", ignore_errors=True)
            raise
        summary["offline_sign_stage"] = exported
        check_listing(launch, ["export", "handoff", "host", "outbox"], "BOUNDED_DIR")
        check_boundary(launch, "export", {"candidate": exported["candidate_id"]})
        scan_key_material(work)
        check_nothing_sent(pair, tip, funding, None)
    finally:
        shutil.rmtree(tmp)
        facts.unlink()

    txid = exported["txid"]
    if not re.fullmatch(r"[0-9a-f]{64}", txid):
        raise Mismatch("the export's txid is not a digest")
    for node in pair.both():
        pair.fee_delta(node, txid, -FEE_DELTA)
    phase("reject_both")
    check_nothing_sent(pair, tip, funding, txid)
    # Both nodes would admit the transaction again; the tip is the same.
    for node in pair.both():
        pair.fee_delta(node, txid, FEE_DELTA)
    for _ in range(BOUND_RUNS):
        phase("bounded")
        check_nothing_sent(pair, tip, funding, txid)
    if len(summary.get("prestate_comparisons", [])) != len(BOUND_PENDING):
        raise Mismatch("BOUND_PENDING: not every H0 - 1 comparison ran")
    return summary


def run_r2b(pair: Pair, work: Path, cargo: str, offline_env: dict, online_env: dict, send: RunUser, secrets_: Secrets) -> dict:
    """R2-b (module docs, `R2B_STEPS`): the continue holder on `pair`'s own
    chain, charged at H0 - 2 under a CONTINUE_WITHIN_LIMITS budget, the
    host turning at H0 - 1, then at H0 (no transaction in its block) and at
    H0 + 1 (the transaction in its block). `offline_env` and `online_env`
    are each build's environment without stage values. Only "r2b_missed"
    gets the send credential."""
    summary: dict = {"labels": LAUNCH_LABELS, "construction_height": CASE_CONSTRUCTION}
    funding_descriptor = pair.a.call("getdescriptorinfo", FUNDING_DESCRIPTOR)["descriptor"]
    constructed = pair.mine(funding_descriptor, CASE_CONSTRUCTION)
    chain, funding = chain_facts(pair, constructed, CASE_CONSTRUCTION)
    summary["funding"] = funding
    online = dict(online_env)
    online.update(
        {
            "BITAGI_E3D3_NODE_A_PORT": str(pair.a.rpcport),
            "BITAGI_E3D3_NODE_B_PORT": str(pair.b.rpcport),
            "BITAGI_E3D3_NODE_A_LOG": pair.a.log_path,
            "BITAGI_E3D3_NODE_B_LOG": pair.b.log_path,
        }
    )
    genesis = chain.split("\n", 1)[0].removeprefix("genesis=")

    def host(worker: str, lines: list[str], env: dict) -> dict:
        command = worker_command(cargo, HOST_TEST, worker, [], HOST_PACKAGE)
        return run_stage(command, env, worker, lines, secrets_=secrets_)

    def signer(worker: str, lines: list[str], env: dict) -> dict:
        command = worker_command(cargo, LAUNCH_SIGNER_TEST, worker, ["--features", "offline-ceremony"], SIGNER_PACKAGE)
        return run_stage(command, env, worker, lines, secrets_=secrets_)

    def phase(name: str) -> dict:
        stage_env = dict(online)
        stage_env["BITAGI_E3D3_PHASE"] = name
        if name in R2B_SENDING:
            stage_env["BITAGI_E3D3_SEND_AUTH"] = send.auth()
        pending = None
        if name in R2B_PENDING:
            # The first run ends at the H0 - 1 comparison (1d-3d-3d).
            pending = host(CASE_WORKER, CASE_LINES, stage_env)
            if (pending["phase"], pending["steps"], pending["hand_offs"]) != (name, R2B_PENDING[name], "0"):
                raise Mismatch(f"{name}: steps {pending['steps']}")
            compared = run_prestate(pair, launch, prestate_dir / name, pending["prestate_receipt"])
            stage_env.update(compared["env"])
        got = replayed(name, lambda _, env: host(CASE_WORKER, CASE_LINES, env), stage_env, launch, root, summary, secrets_)
        expected = (name, R2B_STEPS[name], "-", R2B_HAND_OFFS.get(name, "0"))
        if (got["phase"], got["steps"], got["prestate_receipt"], got["hand_offs"]) != expected:
            raise Mismatch(f"{name}: steps {got['steps']}")
        if pending is not None:
            summary.setdefault("prestate_comparisons", []).append(prestate_summary(name, pending, compared, got))
        elif got["prestate_ms"] != "0":
            raise Mismatch(f"{name}: a prestate turn without a comparison")
        # Bytes only where step 8 handed some off.
        if name not in R2B_HAND_OFFS and got["raw_tx_sha256"] != "-":
            raise Mismatch(f"{name}: bytes without a hand-off")
        summary[f"phase_{name}"] = got
        return got

    described = host(DESCRIBE_WORKER, DESCRIBE_LINES, online)
    descriptor = check_descriptor(described["descriptor"], genesis)
    summary["descriptor_sha256"] = hashlib.sha256(bytes.fromhex(descriptor)).hexdigest()
    check_nothing_sent(pair, constructed, funding, None, CASE_CONSTRUCTION)
    tip = pair.mine(funding_descriptor, 1)

    root = private(work / "r2b")
    launch = private(root / "launch")
    prestate_dir = private(root / "prestate")
    for name in ("handoff", "outbox", "export", "host"):
        private(launch / name)
    facts = root / "launch-facts.txt"
    facts.write_text(chain + f"descriptor={descriptor}\n" + sign_tip_lines(tip), encoding="ascii", newline="")
    facts.chmod(0o600)
    tmp = private(root / "launch-tmp")
    offline = dict(offline_env)
    offline.update({"BITAGI_E3D3_LAUNCH_FILE": str(facts.resolve()), "TMPDIR": str(tmp.resolve())})
    online["BITAGI_E3D3_LAUNCH"] = str(launch.resolve())
    try:
        summary["charge_stage"] = signer(CONTINUE_CHARGE_WORKER, CHARGE_LINES, offline)
        check_boundary(launch, "charge", {})
        # The budget the host is handed continues within limits on a miss.
        if (launch / "handoff" / "budget.json").read_text(encoding="ascii").count(CONTINUE_POLICY) != 1:
            raise Mismatch("r2b: the budget does not continue within limits")
        scan_key_material(work)
        check_nothing_sent(pair, tip, funding, None)
        phase("r2b_sign")
        outbox = listing(launch / "outbox")
        entry = outbox[0].removeprefix("sign-input-").removesuffix(".txt") if len(outbox) == 1 else "-"
        check_boundary(launch, "sign", {"entry": entry})
        scan_key_material(work)
        check_nothing_sent(pair, tip, funding, None)

        try:
            exported = signer(OFFLINE_SIGN_WORKER, OFFLINE_SIGN_LINES, offline)
        except BaseException:
            shutil.rmtree(launch / "offline", ignore_errors=True)
            raise
        summary["offline_sign_stage"] = exported
        check_listing(launch, ["export", "handoff", "host", "outbox"], "R2B_DIR")
        check_boundary(launch, "export", {"candidate": exported["candidate_id"]})
        scan_key_material(work)
        check_nothing_sent(pair, tip, funding, None)
    finally:
        shutil.rmtree(tmp)
        facts.unlink()

    txid = exported["txid"]
    if not re.fullmatch(r"[0-9a-f]{64}", txid):
        raise Mismatch("the export's txid is not a digest")
    phase("r2b_wait")
    check_nothing_sent(pair, tip, funding, txid)
    # H0 with no transaction: nothing was sent, so its block holds none.
    h0 = pair.mine(funding_descriptor, 1)
    check_nothing_sent(pair, h0, funding, txid, GATE)
    sent = phase("r2b_missed")
    if sent["raw_tx_sha256"] != exported["raw_tx_sha256"]:
        raise Mismatch("the broadcast bytes are not the offline export's")
    check_submitted(pair, h0, funding, txid, height=GATE)
    summary["submitted_at_h0"] = "PASS"
    # H0 + 1, mined by node A with the transaction; both nodes agree.
    pair.mine(funding_descriptor, 1)
    for node in pair.both():
        block = node.call("getblock", node.best(), "1")
        if txid not in block["tx"] or node.call("getmempoolinfo")["size"] != 0:
            raise Mismatch(f"{node.label}: the transaction is not in H0 + 1's block")
        if node.call("gettxout", funding["txid"], str(funding["vout"]), "false"):
            raise Mismatch(f"{node.label}: funding output not spent in the chain")
    phase("r2b_included")
    if len(summary.get("prestate_comparisons", [])) != len(R2B_PENDING):
        raise Mismatch("R2B_PENDING: not every H0 - 1 comparison ran")
    return summary


def run_e8(pair: Pair, work: Path, cargo: str, offline_env: dict, online_env: dict, send: RunUser, secrets_: Secrets) -> dict:
    """1e-2b-2a's E8 variant (module docs, `E8_STEPS`): R2-b's charge on
    `pair`'s own chain, the host signing at H0 - 1 and not turning there
    again; then at H0 + `E8_LATE` (no transaction in H0's block or after)
    the import and a broadcast on new checks, admission and authorization,
    and at the next block (the transaction in it) the birth. Only "e8_late"
    gets the send credential; it and "e8_included" write no event line."""
    summary: dict = {"labels": LAUNCH_LABELS, "construction_height": CASE_CONSTRUCTION}
    funding_descriptor = pair.a.call("getdescriptorinfo", FUNDING_DESCRIPTOR)["descriptor"]
    constructed = pair.mine(funding_descriptor, CASE_CONSTRUCTION)
    chain, funding = chain_facts(pair, constructed, CASE_CONSTRUCTION)
    summary["funding"] = funding
    online = dict(online_env)
    online.update(
        {
            "BITAGI_E3D3_NODE_A_PORT": str(pair.a.rpcport),
            "BITAGI_E3D3_NODE_B_PORT": str(pair.b.rpcport),
            "BITAGI_E3D3_NODE_A_LOG": pair.a.log_path,
            "BITAGI_E3D3_NODE_B_LOG": pair.b.log_path,
        }
    )
    genesis = chain.split("\n", 1)[0].removeprefix("genesis=")

    def host(worker: str, lines: list[str], env: dict) -> dict:
        command = worker_command(cargo, HOST_TEST, worker, [], HOST_PACKAGE)
        return run_stage(command, env, worker, lines, secrets_=secrets_)

    def signer(worker: str, lines: list[str], env: dict) -> dict:
        command = worker_command(cargo, LAUNCH_SIGNER_TEST, worker, ["--features", "offline-ceremony"], SIGNER_PACKAGE)
        return run_stage(command, env, worker, lines, secrets_=secrets_)

    def phase(name: str) -> dict:
        stage_env = dict(online)
        stage_env["BITAGI_E3D3_PHASE"] = name
        if name in E8_SENDING:
            stage_env["BITAGI_E3D3_SEND_AUTH"] = send.auth()
        pending = None
        if name in E8_PENDING:
            # The first run ends at the H0 - 1 comparison (1d-3d-3d).
            pending = host(CASE_WORKER, CASE_LINES, stage_env)
            if (pending["phase"], pending["steps"], pending["hand_offs"]) != (name, E8_PENDING[name], "0"):
                raise Mismatch(f"{name}: steps {pending['steps']}")
            compared = run_prestate(pair, launch, prestate_dir / name, pending["prestate_receipt"])
            stage_env.update(compared["env"])
        lines = None
        if name in E8_LINES:
            lines = work / f"lines-{name}.txt"
            stage_env["BITAGI_E3D3_EVENT_LINES"] = str(lines.resolve())
        got = replayed(name, lambda _, env: host(CASE_WORKER, CASE_LINES, env), stage_env, launch, root, summary, secrets_)
        if lines is not None and event_names(lines, secrets_) != EVENT_LINES[name]:
            raise Mismatch(f"{name} event lines {event_names(lines, None)}")
        expected = (name, E8_STEPS[name], "-", E8_HAND_OFFS.get(name, "0"))
        if (got["phase"], got["steps"], got["prestate_receipt"], got["hand_offs"]) != expected:
            raise Mismatch(f"{name}: steps {got['steps']}")
        if pending is not None:
            summary.setdefault("prestate_comparisons", []).append(prestate_summary(name, pending, compared, got))
        elif got["prestate_ms"] != "0":
            raise Mismatch(f"{name}: a prestate turn without a comparison")
        # Bytes only where step 8 handed some off.
        if name not in E8_HAND_OFFS and got["raw_tx_sha256"] != "-":
            raise Mismatch(f"{name}: bytes without a hand-off")
        summary[f"phase_{name}"] = got
        return got

    described = host(DESCRIBE_WORKER, DESCRIBE_LINES, online)
    descriptor = check_descriptor(described["descriptor"], genesis)
    summary["descriptor_sha256"] = hashlib.sha256(bytes.fromhex(descriptor)).hexdigest()
    check_nothing_sent(pair, constructed, funding, None, CASE_CONSTRUCTION)
    tip = pair.mine(funding_descriptor, 1)

    root = private(work / "e8")
    launch = private(root / "launch")
    prestate_dir = private(root / "prestate")
    for name in ("handoff", "outbox", "export", "host"):
        private(launch / name)
    facts = root / "launch-facts.txt"
    facts.write_text(chain + f"descriptor={descriptor}\n" + sign_tip_lines(tip), encoding="ascii", newline="")
    facts.chmod(0o600)
    tmp = private(root / "launch-tmp")
    offline = dict(offline_env)
    offline.update({"BITAGI_E3D3_LAUNCH_FILE": str(facts.resolve()), "TMPDIR": str(tmp.resolve())})
    online["BITAGI_E3D3_LAUNCH"] = str(launch.resolve())
    try:
        summary["charge_stage"] = signer(CONTINUE_CHARGE_WORKER, CHARGE_LINES, offline)
        check_boundary(launch, "charge", {})
        # The budget the host is handed continues within limits on a miss.
        if (launch / "handoff" / "budget.json").read_text(encoding="ascii").count(CONTINUE_POLICY) != 1:
            raise Mismatch("e8: the budget does not continue within limits")
        scan_key_material(work)
        check_nothing_sent(pair, tip, funding, None)
        phase("e8_sign")
        outbox = listing(launch / "outbox")
        entry = outbox[0].removeprefix("sign-input-").removesuffix(".txt") if len(outbox) == 1 else "-"
        check_boundary(launch, "sign", {"entry": entry})
        scan_key_material(work)
        check_nothing_sent(pair, tip, funding, None)

        try:
            exported = signer(OFFLINE_SIGN_WORKER, OFFLINE_SIGN_LINES, offline)
        except BaseException:
            shutil.rmtree(launch / "offline", ignore_errors=True)
            raise
        summary["offline_sign_stage"] = exported
        check_listing(launch, ["export", "handoff", "host", "outbox"], "E8_DIR")
        check_boundary(launch, "export", {"candidate": exported["candidate_id"]})
        scan_key_material(work)
        check_nothing_sent(pair, tip, funding, None)
    finally:
        shutil.rmtree(tmp)
        facts.unlink()

    txid = exported["txid"]
    if not re.fullmatch(r"[0-9a-f]{64}", txid):
        raise Mismatch("the export's txid is not a digest")
    # The operator's import, no host turn.
    phase("e8_import")
    check_nothing_sent(pair, tip, funding, txid)
    # No host turn at H0 - 1 after the signature: H0 and the blocks to
    # H0 + E8_LATE with no transaction, nothing sent.
    late = pair.mine(funding_descriptor, 1 + E8_LATE)
    check_nothing_sent(pair, late, funding, txid, GATE + E8_LATE)
    sent = phase("e8_late")
    if sent["raw_tx_sha256"] != exported["raw_tx_sha256"]:
        raise Mismatch("the broadcast bytes are not the offline export's")
    check_submitted(pair, late, funding, txid, height=GATE + E8_LATE)
    summary["submitted_late"] = "PASS"
    # The next block, mined by node A with the transaction; both agree.
    pair.mine(funding_descriptor, 1)
    for node in pair.both():
        block = node.call("getblock", node.best(), "1")
        if txid not in block["tx"] or node.call("getmempoolinfo")["size"] != 0:
            raise Mismatch(f"{node.label}: the transaction is not in the late block")
        if node.call("gettxout", funding["txid"], str(funding["vout"]), "false"):
            raise Mismatch(f"{node.label}: funding output not spent in the chain")
    phase("e8_included")
    if len(summary.get("prestate_comparisons", [])) != len(E8_PENDING):
        raise Mismatch("E8_PENDING: not every H0 - 1 comparison ran")
    summary["event_lines"] = "PASS"
    return summary


def check_procedure(path: Path, replaced: tuple[str, str], below: bool = False) -> None:
    """The procedure file the E3'-2 worker wrote from its copy of the
    reorg (#450 runbook §2), against the driver's own reads: the replaced
    tip X at H0 - 1 is the identity's local block, X' the agreed one and the
    ancestor's; step 6 not performed. With `below` (#471 E-B3, Q8-ㄱ): E-B's
    reorg, whose local block is X', with no agreed hash, and whose ancestor
    is that local block itself."""
    old, new = replaced
    fields = dict(line.split("=", 1) for line in path.read_text(encoding="ascii").splitlines())
    expected = {
        "format": "BITAGI-LAUNCH-HOST-REORG-PROCEDURE-V1",
        "local_height": str(TIP_HEIGHT),
        "local_hash": internal(new if below else old),
        "agreed_at_local": "below" if below else internal(new),
        "ancestor_height": str(TIP_HEIGHT),
        "ancestor_hash": internal(new),
        "step6": "not-performed",
    }
    if {key: fields.get(key) for key in expected} != expected:
        raise Mismatch("the procedure file is not the replaced tip's")
    for key in ("procedure_sha256", "incident"):
        if not re.fullmatch(r"[0-9a-f]{64}", fields.get(key, "")):
            raise Mismatch(f"the procedure file's {key}")
    if not re.fullmatch(r"[1-9][0-9]*", fields.get("watermark_event", "")):
        raise Mismatch("the procedure file's watermark_event")


def run_e(pair: Pair, work: Path, cargo: str, offline_env: dict, online_env: dict, secrets_: Secrets) -> dict:
    """1e-2a (module docs): the launch host's E scenarios at the H0 - 1
    floor on `pair`'s own chain, with nothing sent. `offline_env` and
    `online_env` are each build's environment without stage values."""
    summary: dict = {"labels": E_LABELS, "construction_height": CASE_CONSTRUCTION, "open_rows": E_OPEN_NOTE}
    funding_descriptor = pair.a.call("getdescriptorinfo", FUNDING_DESCRIPTOR)["descriptor"]
    constructed = pair.mine(funding_descriptor, CASE_CONSTRUCTION)
    chain, funding = chain_facts(pair, constructed, CASE_CONSTRUCTION)
    summary["funding"] = funding
    online = dict(online_env)
    online.update(
        {
            "BITAGI_E3D3_NODE_A_PORT": str(pair.a.rpcport),
            "BITAGI_E3D3_NODE_B_PORT": str(pair.b.rpcport),
            "BITAGI_E3D3_NODE_A_LOG": pair.a.log_path,
            "BITAGI_E3D3_NODE_B_LOG": pair.b.log_path,
        }
    )
    genesis = chain.split("\n", 1)[0].removeprefix("genesis=")

    def host(worker: str, lines: list[str], env: dict) -> dict:
        command = worker_command(cargo, HOST_TEST, worker, [], HOST_PACKAGE)
        return run_stage(command, env, worker, lines, secrets_=secrets_)

    def signer(worker: str, lines: list[str], env: dict) -> dict:
        command = worker_command(cargo, LAUNCH_SIGNER_TEST, worker, ["--features", "offline-ceremony"], SIGNER_PACKAGE)
        return run_stage(command, env, worker, lines, secrets_=secrets_)

    def phase(name: str, tip: str, txid: str | None, height: int = TIP_HEIGHT) -> dict:
        stage_env = dict(online)
        stage_env["BITAGI_E3D3_PHASE"] = name
        if name in E_SENDING:
            raise Mismatch(f"{name}: an E phase with the send credential")
        pending = None
        if name in E_PENDING:
            # The first run ends at the H0 - 1 comparison (1d-3d-3d), as
            # rn-1's sign phase.
            pending = host(E_WORKER, E_LINES, stage_env)
            if (pending["phase"], pending["steps"], pending["hand_offs"]) != (name, E_PENDING[name], "0"):
                raise Mismatch(f"{name}: steps {pending['steps']}")
            check_nothing_sent(pair, tip, funding, txid, height)
            compared = run_prestate(pair, launch, prestate_dir / name, pending["prestate_receipt"], height)
            stage_env.update(compared["env"])
        runs = [host(E_WORKER, E_LINES, stage_env) for _ in range(E_RUNS.get(name, 1))]
        got = runs[0]
        expected = (name, E_STEPS[name], "-", E_HAND_OFFS.get(name, "0"))
        if (got["phase"], got["steps"], got["prestate_receipt"], got["hand_offs"]) != expected:
            raise Mismatch(f"{name}: steps {got['steps']}")
        if pending is not None:
            summary.setdefault("prestate_comparisons", []).append(prestate_summary(name, pending, compared, got))
        elif got["prestate_ms"] != "0":
            raise Mismatch(f"{name}: a prestate turn without a comparison")
        if name in E_EVENTS and got["ledger_events"] != E_EVENTS[name]:
            raise Mismatch(f"{name}: ledger events {got['ledger_events']}")
        # E6a: a new process with the nodes unchanged reports the same.
        if any(run != got for run in runs[1:]):
            raise Mismatch(f"{name}: a restart reported otherwise")
        # Every E phase: both mempools empty, the funding output unspent and
        # the tip the driver left (A's condition).
        check_nothing_sent(pair, tip, funding, txid, height)
        if name in E_OPEN:
            got = dict(got, label=E_OPEN[name])
        summary[f"phase_{name}"] = got
        return got

    described = host(DESCRIBE_WORKER, DESCRIBE_LINES, online)
    descriptor = check_descriptor(described["descriptor"], genesis)
    summary["descriptor_sha256"] = hashlib.sha256(bytes.fromhex(descriptor)).hexdigest()
    check_nothing_sent(pair, constructed, funding, None, CASE_CONSTRUCTION)
    tip = pair.mine(funding_descriptor, 1)

    root = private(work / "e")
    launch = private(root / "launch")
    prestate_dir = private(root / "prestate")
    for name in ("handoff", "outbox", "export", "host"):
        private(launch / name)
    facts = root / "launch-facts.txt"
    facts.write_text(chain + f"descriptor={descriptor}\n" + sign_tip_lines(tip), encoding="ascii", newline="")
    facts.chmod(0o600)
    tmp = private(root / "launch-tmp")
    offline = dict(offline_env)
    offline.update({"BITAGI_E3D3_LAUNCH_FILE": str(facts.resolve()), "TMPDIR": str(tmp.resolve())})
    online["BITAGI_E3D3_LAUNCH"] = str(launch.resolve())
    try:
        summary["charge_stage"] = signer(CHARGE_WORKER, CHARGE_LINES, offline)
        check_boundary(launch, "charge", {})
        scan_key_material(work)
        check_nothing_sent(pair, tip, funding, None)
        phase("e_sign", tip, None)
        outbox = listing(launch / "outbox")
        entry = outbox[0].removeprefix("sign-input-").removesuffix(".txt") if len(outbox) == 1 else "-"
        check_boundary(launch, "sign", {"entry": entry})
        phase("e_sign_again", tip, None)
        check_boundary(launch, "sign", {"entry": entry})
        scan_key_material(work)
        try:
            exported = signer(OFFLINE_SIGN_WORKER, OFFLINE_SIGN_LINES, offline)
        except BaseException:
            shutil.rmtree(launch / "offline", ignore_errors=True)
            raise
        summary["offline_sign_stage"] = exported
        check_listing(launch, ["export", "handoff", "host", "outbox"], "E_DIR")
        check_boundary(launch, "export", {"candidate": exported["candidate_id"]})
        scan_key_material(work)
        check_nothing_sent(pair, tip, funding, None)
    finally:
        shutil.rmtree(tmp)
        facts.unlink()

    txid = exported["txid"]
    if not re.fullmatch(r"[0-9a-f]{64}", txid):
        raise Mismatch("the export's txid is not a digest")
    phase("e_admit", tip, txid)
    phase("e_admit_again", tip, txid)
    replaced = pair.replace_tip(pair.a.call("getdescriptorinfo", "raw(51)")["descriptor"])
    phase("e_replaced", replaced[1], txid)
    phase("e_release", replaced[1], txid)
    procedure = launch / "host" / "procedure.txt"
    check_procedure(procedure, replaced)
    # Released, the operator removes the file (#450 runbook §2 5: a file
    # left in place is refused at every turn).
    procedure.unlink()
    phase("e_reask", replaced[1], txid)
    check_boundary(launch, "sign", {"entry": entry})
    lowered = pair.lower_tip()
    phase("e_below", lowered, txid, TIP_HEIGHT - 1)
    pair.restore_tip(replaced[1])
    phase("e_dead", replaced[1], txid)
    # #471 E-B3 and E-B4 (Q8-ㄱ): the file of E-B's reorg names the unchanged
    # local tip; released, it is removed.
    phase("e_release_below", replaced[1], txid)
    check_procedure(procedure, replaced, below=True)
    procedure.unlink()
    phase("e_reask_below", replaced[1], txid)
    check_boundary(launch, "sign", {"entry": entry})
    summary["tips"] = {"x": replaced[0], "x_replaced": replaced[1], "below": lowered}
    if len(summary.get("prestate_comparisons", [])) != len(E_PENDING):
        raise Mismatch("E_PENDING: not every H0 - 1 comparison ran")
    summary["nothing_sent"] = "PASS"
    return summary


def run_l0(pair: Pair, work: Path, cargo: str, offline_env: dict, online_env: dict, send: RunUser, secrets_: Secrets,
           rows_2b: bool = False) -> dict:
    """#484 L0 (module docs, `L0_STEPS`): the Sign hand-off at H0 - 2 on
    `pair`'s own chain, then step 8 at H0 - 1. `offline_env` and
    `online_env` are each build's environment without stage values. The
    outbox's one hand-off file is checked after each host phase: the H0 - 1
    turns write no second one. Each host process's event lines are
    `EVENT_LINES`' for its phase (#495 P2-1).

    1e-2b-2b (opt-in, `rows_2b`; node A of `pair` has the miner user): the
    chain is §1's (the competitor funded at H0 - 2 by D1's miner), the
    charge `CONTINUE_CHARGE_WORKER` (Q-b6), and after `l0_reborn` E9-d
    (`L0D_STEPS`). Without it every call is as before."""
    summary: dict = {"labels": LAUNCH_LABELS, "construction_height": CASE_CONSTRUCTION}
    funding_descriptor = pair.a.call("getdescriptorinfo", FUNDING_DESCRIPTOR)["descriptor"]
    if rows_2b:
        miner = PairMiner(pair)
        try:
            summary_2b = rows_2b_l0(pair, work, cargo, offline_env, online_env, send, secrets_, miner, summary, funding_descriptor)
        finally:
            miner.stop()
        return summary_2b
    constructed = pair.mine(funding_descriptor, CASE_CONSTRUCTION)
    return l0_chain(pair, work, cargo, offline_env, online_env, send, secrets_, summary, funding_descriptor, constructed, CHARGE_WORKER)


def rows_2b_l0(pair: Pair, work: Path, cargo: str, offline_env: dict, online_env: dict, send: RunUser, secrets_: Secrets,
               miner: "PairMiner", summary: dict, funding_descriptor: str) -> dict:
    """`run_l0(rows_2b=True)`: §1's chain, the continue charge, L0's rows,
    then E9-d (§2.3)."""
    competitor = Competitor(cargo, work / "l0-generator")
    constructed = construct_2b(pair, miner, competitor)
    hand = {}
    summary = l0_chain(pair, work, cargo, offline_env, online_env, send, secrets_, summary, funding_descriptor, constructed,
                       CONTINUE_CHARGE_WORKER, hand)
    context, tip, reborn = hand["context"], summary["tips"]["floor"], summary["tips"]["g_again"]
    if (context.launch / "handoff" / "budget.json").read_text(encoding="ascii").count(CONTINUE_POLICY) != 1:
        raise Mismatch("l0: the budget does not continue within limits")
    # E9-d: P0 out of node A's template; G'' dropped on both nodes.
    context.delta(-FEE_DELTA)
    if pair.drop_block(reborn, GATE) != tip:
        raise Mismatch("the nodes are not back on the floor block")
    context.phase("l0_lost_reorged")
    context.release("l0_lost_release", (GATE, reborn), "below", (TIP_HEIGHT, tip))
    rung = competitor.rung(tip, competitor_fee(pair, context.txid, competitor.bidders.CANDIDATE_VSIZE))
    summary["competitor"] = {k: rung[k] for k in ("txid", "fee", "vsize", "raw_sha256")}
    lost = miner.block((rung["hex"],))
    check_order(lost, [(rung["txid"], "THIRD_PARTY")], "l0_lost")
    context.phase("l0_lost")
    summary["tips"]["g_lost"] = lost["hash"]
    summary["miner_blocks"] = miner.blocks
    summary["labels"] = LAUNCH_LABELS + ["THIRD_PARTY_COMPETITOR_TEST_ONLY"]
    return summary


def l0_chain(pair: Pair, work: Path, cargo: str, offline_env: dict, online_env: dict, send: RunUser, secrets_: Secrets,
             summary: dict, funding_descriptor: str, constructed: str, charge_worker: str, hand: dict | None = None) -> dict:
    """`run_l0`'s rows on the chain built to `constructed` (H0 - 2), the
    charge by `charge_worker`. `hand`, when given, gets the 1e-2b-2b
    context for the rows after `l0_reborn`."""
    chain, funding = chain_facts(pair, constructed, CASE_CONSTRUCTION)
    summary["funding"] = funding
    online = dict(online_env)
    online.update(
        {
            "BITAGI_E3D3_NODE_A_PORT": str(pair.a.rpcport),
            "BITAGI_E3D3_NODE_B_PORT": str(pair.b.rpcport),
            "BITAGI_E3D3_NODE_A_LOG": pair.a.log_path,
            "BITAGI_E3D3_NODE_B_LOG": pair.b.log_path,
        }
    )
    genesis = chain.split("\n", 1)[0].removeprefix("genesis=")
    # The sign phase's one hand-off (its outbox name), once it is there.
    entry = "-"

    def host(worker: str, lines: list[str], env: dict) -> dict:
        command = worker_command(cargo, HOST_TEST, worker, [], HOST_PACKAGE)
        return run_stage(command, env, worker, lines, secrets_=secrets_)

    def signer(worker: str, lines: list[str], env: dict) -> dict:
        command = worker_command(cargo, LAUNCH_SIGNER_TEST, worker, ["--features", "offline-ceremony"], SIGNER_PACKAGE)
        return run_stage(command, env, worker, lines, secrets_=secrets_)

    def l0_host(key: str, env: dict) -> dict:
        # Each process its own event line file, its names `EVENT_LINES[key]`.
        lines = work / f"lines-{key.replace(' ', '-')}.txt"
        env = {**env, "BITAGI_E3D3_EVENT_LINES": str(lines.resolve())}
        fifo = None
        if key in L0T_XD1:
            # As XD-1 runs the host (1e-2b-2a, A Q3): an ack FIFO the driver
            # never writes. A turn that wrote S2 would wait on it.
            fifo = work / f"xd1-ack-{key}.fifo"
            os.mkfifo(fifo, 0o600)
            env["BITAGI_E3D3_XD1_ACK"] = str(fifo.resolve())
        try:
            got = host(L0_WORKER, L0_LINES, env)
        finally:
            # Gone after the phase, also when the worker fails (B's P3-2).
            if fifo is not None:
                fifo.unlink()
        if event_names(lines, secrets_) != EVENT_LINES[key]:
            raise Mismatch(f"{key} event lines {event_names(lines, None)}")
        return got

    def phase(name: str, tip: str, txid: str | None, height: int) -> dict:
        nonlocal entry
        stage_env = dict(online)
        stage_env["BITAGI_E3D3_PHASE"] = name
        if name in L0_SENDING:
            stage_env["BITAGI_E3D3_SEND_AUTH"] = send.auth()
        pending = None
        if name in L0_PENDING:
            # The first run ends at the H0 - 1 comparison (1d-3d-3d).
            pending = l0_host("pending " + name, stage_env)
            if (pending["phase"], pending["steps"], pending["hand_offs"]) != (name, L0_PENDING[name], "0"):
                raise Mismatch(f"{name}: steps {pending['steps']}")
            check_nothing_sent(pair, tip, funding, txid, height)
            compared = run_prestate(pair, launch, prestate_dir / name, pending["prestate_receipt"], height)
            stage_env.update(compared["env"])
        got = l0_host(name, stage_env)
        expected = (name, L0_STEPS[name], "-", L0_HAND_OFFS.get(name, "0"))
        if (got["phase"], got["steps"], got["prestate_receipt"], got["hand_offs"]) != expected:
            raise Mismatch(f"{name}: steps {got['steps']}")
        if pending is not None:
            summary.setdefault("prestate_comparisons", []).append(prestate_summary(name, pending, compared, got))
        elif got["prestate_ms"] != "0":
            raise Mismatch(f"{name}: a prestate turn without a comparison")
        # Bytes only where step 8 handed some off.
        if name not in L0_HAND_OFFS and got["raw_tx_sha256"] != "-":
            raise Mismatch(f"{name}: bytes without a hand-off")
        # The one Sign hand-off, written in the window, is the outbox's
        # only file after every phase.
        if name == "l0_sign":
            outbox = listing(launch / "outbox")
            entry = outbox[0].removeprefix("sign-input-").removesuffix(".txt") if len(outbox) == 1 else "-"
        check_boundary(launch, "sign", {"entry": entry})
        # Nothing sent before step 8, at the tip the driver left.
        if name not in L0_SENDING:
            check_nothing_sent(pair, tip, funding, txid, height)
        summary[f"phase_{name}"] = got
        return got

    described = host(DESCRIBE_WORKER, DESCRIBE_LINES, online)
    descriptor = check_descriptor(described["descriptor"], genesis)
    summary["descriptor_sha256"] = hashlib.sha256(bytes.fromhex(descriptor)).hexdigest()
    check_nothing_sent(pair, constructed, funding, None, CASE_CONSTRUCTION)

    root = private(work / "l0")
    launch = private(root / "launch")
    prestate_dir = private(root / "prestate")
    for name in ("handoff", "outbox", "export", "host"):
        private(launch / name)
    facts = root / "launch-facts.txt"
    # The host signs at the charge's own tip, H0 - 2.
    facts.write_text(chain + f"descriptor={descriptor}\n" + sign_tip_lines(constructed, CASE_CONSTRUCTION), encoding="ascii", newline="")
    facts.chmod(0o600)
    tmp = private(root / "launch-tmp")
    offline = dict(offline_env)
    offline.update({"BITAGI_E3D3_LAUNCH_FILE": str(facts.resolve()), "TMPDIR": str(tmp.resolve())})
    online["BITAGI_E3D3_LAUNCH"] = str(launch.resolve())
    try:
        summary["charge_stage"] = signer(charge_worker, CHARGE_LINES, offline)
        check_boundary(launch, "charge", {})
        scan_key_material(work)
        check_nothing_sent(pair, constructed, funding, None, CASE_CONSTRUCTION)
        if listing(launch / "outbox"):
            raise Mismatch("L0_OUTBOX")
        phase("l0_sign", constructed, None, CASE_CONSTRUCTION)
        scan_key_material(work)

        try:
            exported = signer(OFFLINE_SIGN_WORKER, OFFLINE_SIGN_LINES, offline)
        except BaseException:
            shutil.rmtree(launch / "offline", ignore_errors=True)
            raise
        summary["offline_sign_stage"] = exported
        check_listing(launch, ["export", "handoff", "host", "outbox"], "L0_DIR")
        check_boundary(launch, "export", {"candidate": exported["candidate_id"]})
        check_boundary(launch, "sign", {"entry": entry})
        scan_key_material(work)
        check_nothing_sent(pair, constructed, funding, None, CASE_CONSTRUCTION)
    finally:
        shutil.rmtree(tmp)
        facts.unlink()

    txid = exported["txid"]
    if not re.fullmatch(r"[0-9a-f]{64}", txid):
        raise Mismatch("the export's txid is not a digest")
    phase("l0_wait", constructed, txid, CASE_CONSTRUCTION)
    # The floor block, H0 - 1.
    tip = pair.mine(funding_descriptor, 1)
    check_nothing_sent(pair, tip, funding, txid)
    sent = phase("l0_broadcast", tip, txid, TIP_HEIGHT)
    if sent["raw_tx_sha256"] != exported["raw_tx_sha256"]:
        raise Mismatch("the broadcast bytes are not the offline export's")
    check_submitted(pair, tip, funding, txid)
    summary["submitted_by_step_8_only"] = "PASS"
    summary["tips"] = {"signed_at": constructed, "floor": tip}
    if len(summary.get("prestate_comparisons", [])) != len(L0_PENDING):
        raise Mismatch("L0_PENDING: not every H0 - 1 comparison ran")

    # 1e-2b-2a (`L0T_STEPS`): the same chain past H0 - 1.
    def l0t(name: str, height: int) -> dict:
        stage_env = dict(online)
        stage_env["BITAGI_E3D3_PHASE"] = name
        if name in L0T_SENDING:
            stage_env["BITAGI_E3D3_SEND_AUTH"] = send.auth()
        got = l0_host(name, stage_env)
        expected = (name, L0T_STEPS[name], "-", "0", "-", "0")
        if (got["phase"], got["steps"], got["prestate_receipt"], got["hand_offs"], got["raw_tx_sha256"], got["prestate_ms"]) != expected:
            raise Mismatch(f"{name}: steps {got['steps']}")
        for node in pair.both():
            if node.height() != height:
                raise Mismatch(f"{node.label}: {name}: tip moved")
        if mempools(pair, txid) != L0T_MEMPOOLS[name]:
            raise Mismatch(f"{name}: mempools {mempools(pair, txid)}")
        check_boundary(launch, "sign", {"entry": entry})
        summary[f"phase_{name}"] = got
        return got

    def holds(block: str) -> None:
        # Both nodes on `block` at H0, the transaction in it, both mempools
        # empty and the funding output spent in the chain.
        if pair.agreed(GATE) != block:
            raise Mismatch("the nodes are not on the H0 block mined")
        for node in pair.both():
            if txid not in node.call("getblock", block, "1")["tx"] or node.call("getmempoolinfo")["size"] != 0:
                raise Mismatch(f"{node.label}: the transaction is not in H0's block")
            if node.call("gettxout", funding["txid"], str(funding["vout"]), "false"):
                raise Mismatch(f"{node.label}: funding output not spent in the chain")

    # E4-a: G = H0 with the transaction.
    g = pair.mine(funding_descriptor, 1)
    holds(g)
    l0t("l0_born", GATE)
    # E9-a: G invalidated on both nodes; the floor block is the tip again.
    if pair.drop_block(g, GATE) != tip:
        raise Mismatch("the nodes are not back on the floor block")
    l0t("l0_reorged", TIP_HEIGHT)
    l0t("l0_release", TIP_HEIGHT)
    procedure = launch / "host" / "procedure.txt"
    check_l0t_procedure(procedure, g, tip)
    # Released, the operator removes the file (#450 runbook §2 5).
    procedure.unlink()
    # E9-b and E9-c.
    l0t("l0_waiting", TIP_HEIGHT)
    # Another coinbase, as `replace_tip`: mined to the funding descriptor
    # again within the same second, the block would be G itself, which both
    # nodes hold invalid.
    reborn = pair.mine(pair.a.call("getdescriptorinfo", "raw(51)")["descriptor"], 1)
    if reborn == g:
        raise Mismatch("the H0 block was not mined again")
    holds(reborn)
    l0t("l0_reborn", GATE)
    summary["tips"].update({"g": g, "g_again": reborn})
    summary["event_lines"] = "PASS"
    if hand is not None:
        context = LostContext(pair, work, cargo, online, launch, prestate_dir, send, secrets_, summary)
        context.entry, context.txid = entry, txid
        hand["context"] = context
    return summary


def check_l0t_procedure(path: Path, g: str, floor: str) -> None:
    """The procedure file `l0_release`'s worker wrote from its copy of E9-a's
    reorg, against the driver's own reads: the local tip (H0, G), no agreed
    block at that height, the ancestor (H0 - 1, the floor block); step 6 not
    performed."""
    fields = dict(line.split("=", 1) for line in path.read_text(encoding="ascii").splitlines())
    expected = {
        "format": "BITAGI-LAUNCH-HOST-REORG-PROCEDURE-V1",
        "local_height": str(GATE),
        "local_hash": internal(g),
        "agreed_at_local": "below",
        "ancestor_height": str(TIP_HEIGHT),
        "ancestor_hash": internal(floor),
        "step6": "not-performed",
    }
    if {key: fields.get(key) for key in expected} != expected:
        raise Mismatch("the procedure file is not G's")
    for key in ("procedure_sha256", "incident"):
        if not re.fullmatch(r"[0-9a-f]{64}", fields.get(key, "")):
            raise Mismatch(f"the procedure file's {key}")
    if not re.fullmatch(r"[1-9][0-9]*", fields.get("watermark_event", "")):
        raise Mismatch("the procedure file's watermark_event")


# ------------------------------------------------------------- 1e-2b-2b

LOST_STEPS = {**E10_STEPS, **E7_STEPS, **L0D_STEPS}


# B-692a-RT (finding #692; A #702 issuecomment-6632892704, the LATENT row
# `B-692a-RT` of the B-692a note §4; unit note `2026-11-04_b-692a-rt.md`):
# B-692a's late prestate path on a tenth pair and chain, with the L0
# worker, charged under the continue budget (an H0 miss raises nothing).
# The window phases are L0's (the Sign at H0 - 2 with no prestate step);
# the driver then mines H0 - 1 and H0 to H0 + `L0_LATE` with no host turn
# and no transaction; `l0late_broadcast` at H0 + `L0_LATE` compares block
# H0 - 1 late (its first run ends at `PrestateComparisonPending`), records
# both prestate entries at that tip, makes new checks, the admission and
# authorization there, and submits; node A mines the next block with the
# transaction and `l0late_included` is
# `Born { H0 + L0_LATE + 1, at_opening: false }`, the late rows read back
# from the reopened host file. No process of the flow writes an event line.
# Three blocks above H0, as the host cell C7: block H0 - 1 is then neither
# the tip nor its parent. The driver reads block H0 - 1 by its height, both
# nodes at the run's tip, the hash it mined (`prestate_inputs` with
# `tip_height` and `tip_hash`), and
# compares with the same two commands. Defined after `l0_chain`, so the
# lines `claude_track_ardr_l0.py` pins in this file stay where they are.
# Committed before the first run; a run that differs is a FAIL to
# investigate, not a reason to change this table in the same change.
L0_LATE = 3
L0LATE_STEPS = {
    "l0late_sign": L0_STEPS["l0_sign"],
    "l0late_wait": L0_STEPS["l0_wait"],
    # The late comparison and INITIAL_PRESTATE end the replay pending run
    # (REPLAY_PENDING, B-692b P2a); this run: the link, new checks, then the
    # broadcast path; no Sign.
    "l0late_broadcast": "CompareReplay," + ",".join(L0_STEPS["l0_broadcast"].split(",")[2:]),
    "l0late_included": "Done:Born",
}
# Dated 2026-11-04, after the first local run on Core 31.1 and 30.3 (the
# unit note §1): the first turn after the window, at H0 + `L0_LATE`, is
# refused once with no effective facts (the spend scan not at the receipt:
# its backfill ran on the store's floor (H0 - 1, U) before the follower
# anchored it), raising and writing nothing; the next turn asks the late
# comparison.
# B-708 (2026-11-05, finding #708 fixed in the host): that turn now
# backfills again after the follower anchors the floor, so it asks the late
# comparison; a scan-behind refusal in the pending run is a Mismatch (was
# "Refuse:EffectiveFactsMissing," + PENDING_STEPS).
L0LATE_PENDING = {"l0late_broadcast": PENDING_STEPS}
L0LATE_HAND_OFFS = {"l0late_broadcast": "1"}
L0LATE_SENDING = ("l0late_broadcast",)
for _name in (*L0LATE_STEPS, *("pending " + n for n in L0LATE_PENDING)):
    EVENT_LINES[_name] = []
del _name

# B-692a-RT: one refusal for each input the two nodes give differently,
# or a tip that is not the run's.
PRESTATE_GENESIS_DISAGREE = "PRESTATE_NODES_DISAGREE"
PRESTATE_HASH_DISAGREE = "PRESTATE_NODES_DISAGREE:H0_MINUS_1_HASH"
PRESTATE_BEST_DISAGREE = "PRESTATE_NODES_DISAGREE:BEST"
PRESTATE_BEST_NOT_TIP = "PRESTATE_BEST_NOT_RUN_TIP"
PRESTATE_RAW_DISAGREE = "PRESTATE_NODES_DISAGREE:RAW_BLOCK"
PRESTATE_REFUSALS = (PRESTATE_GENESIS_DISAGREE, PRESTATE_HASH_DISAGREE, PRESTATE_BEST_DISAGREE, PRESTATE_BEST_NOT_TIP)


# B-692b P2a (finding #692; A #258 issuecomment-6664483166, B -6664523315):
# the phases whose first run (the late one's second) stops at the REGISTER
# gate's `CompareReplay` with the host's outbox `replay-compare-...`
# (`ReplayComparisonPending`; the worker names it on its `prestate_receipt`
# line). The driver moves that directory out of the outbox, runs the formats
# doc section 8 `step6-compare` as a black box on it, and runs the phase
# again with the Python result and the report; the host records the link
# only on its own MATCH. A MISMATCH or a refusal is a FAIL here. These runs
# are Class T development evidence before B-692b P3, not gate evidence
# (Q-b692-8 (c)).
# Dated 2026-11-08 (B-692b P3c-1, finding #692; A #258
# issuecomment-6723103119 §2 condition 4): the host now records a MISMATCH
# (tag 19), a store-state difference (tag 20) and a Python defect refusal
# (tag 21), and the next turn raises a stop that stays until the release
# path (Q-p3-11) exists. This driver still never hands one on: a non-zero
# `step6-compare` or a report other than MATCH is a FAIL before the next
# run, so no phase here expects a step after a MISMATCH.
REPLAY_PENDING = {
    "r2b_missed": "ReplayComparisonPending",
    "e8_late": "ReplayComparisonPending",
    "l0late_broadcast": "ComparePrestate,RecordInitialPrestate,ReplayComparisonPending",
}
REPLAY_NAME = re.compile(r"replay-compare-[0-9]+-[0-9a-f]{64}-[0-9]+-[0-9a-f]{64}-[0-9]+")
PRESTATE_COMMANDS["step6-compare"] = ("real_block_compare.py", "step6-compare")
# The formats doc's bounds: the Python result 64 MiB, the report 4 MiB.
REPLAY_RESULT_LIMIT = 64 << 20
REPLAY_REPORT_LIMIT = 4 << 20
EVENT_LINES["replay l0late_broadcast"] = []
EVENT_LINES["replay e8_late"] = []


def run_replay(launch: Path, directory: Path, name: str) -> dict:
    """Moves the host's outbox `name` out of the outbox into `directory`
    and runs `step6-compare` on it (`M`, `P` and `E` the host's files);
    exit 0 and a MATCH report pass, anything else is a FAIL. The Python
    output is handed on as written: only its path. Returns the environment
    of the phase's next run and the three SHA-256s."""
    if not REPLAY_NAME.fullmatch(name):
        raise Mismatch("REPLAY_OUTBOX_NAME")
    private(directory)
    held = launch / "outbox" / name
    if held.is_symlink() or not held.is_dir():
        raise Mismatch("REPLAY_OUTBOX")
    inputs = directory / name
    held.rename(inputs)
    out = private(directory / "out")
    python, report = out / "python-result.json", out / "report.json"
    started = time.monotonic()
    code, refusal = run_reference(
        "step6-compare",
        [
            "--manifest", str(inputs / "manifest.json"), "--profile", str(inputs / "profile.hex"),
            "--external", str(inputs / "rust_result.json"), "--python-output", str(python), "--output", str(report),
        ],
    )
    took = time.monotonic() - started
    if code != 0:
        raise Mismatch(f"REPLAY_COMPARE exit {code} {refusal}")
    for path, limit in ((python, REPLAY_RESULT_LIMIT), (report, REPLAY_REPORT_LIMIT)):
        if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
            raise Mismatch("REPLAY_REPORT")
    try:
        result = json.loads(report.read_bytes())
    except ValueError:
        raise Mismatch("REPLAY_REPORT") from None
    if not isinstance(result, dict) or result.get("result") != "MATCH":
        raise Mismatch("REPLAY_REPORT_NOT_MATCH")
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()  # noqa: E731
    return {
        "env": {
            "BITAGI_E3D3_REPLAY_OUTBOX": name,
            "BITAGI_E3D3_REPLAY_RESULT": str(python.resolve()),
            "BITAGI_E3D3_REPLAY_REPORT": str(report.resolve()),
        },
        "manifest_sha256": digest(inputs / "manifest.json"),
        "python_result_sha256": digest(python),
        "report_sha256": digest(report),
        "compare_ms": round(took * 1000),
    }


def replayed(name: str, run, env: dict, launch: Path, root: Path, summary: dict, secrets_: Secrets) -> dict:
    """The phase `name`'s run by `run(label, env)`; for a `REPLAY_PENDING`
    phase first a run that must end there (its own event line file when the
    phase has one, with no line; no send credential: it ends before step
    8), the comparison (`run_replay`), then the run with its files."""
    if name not in REPLAY_PENDING:
        return run(name, env)
    first = dict(env)
    first.pop("BITAGI_E3D3_SEND_AUTH", None)
    lines = None
    if "BITAGI_E3D3_EVENT_LINES" in first:
        lines = Path(first["BITAGI_E3D3_EVENT_LINES"]).with_name(f"lines-replay-{name}.txt")
        first["BITAGI_E3D3_EVENT_LINES"] = str(lines.resolve())
    pending = run("replay " + name, first)
    if (pending["phase"], pending["steps"], pending["hand_offs"]) != (name, REPLAY_PENDING[name], "0"):
        raise Mismatch(f"{name}: replay pending steps {pending['steps']}")
    if lines is not None and event_names(lines, secrets_) != EVENT_LINES["replay " + name]:
        raise Mismatch(f"replay {name} event lines {event_names(lines, None)}")
    compared = run_replay(launch, private(root / "replay") / name, pending["prestate_receipt"])
    second = dict(env)
    second.update(compared["env"])
    got = run(name, second)
    record = {"phase": name}
    record.update({key: value for key, value in compared.items() if key != "env"})
    summary.setdefault("replay_comparisons", []).append(record)
    return got


def run_l0_late(pair: Pair, work: Path, cargo: str, offline_env: dict, online_env: dict, send: RunUser,
                secrets_: Secrets) -> dict:
    """B-692a-RT (the comment above `L0_LATE`, `L0LATE_STEPS`): L0's window on `pair`'s own
    chain under the continue budget, the Sign at H0 - 2 and the import
    there; no host turn while the driver mines H0 - 1 and H0 to
    H0 + `L0_LATE` with no transaction; at that tip the late comparison of
    block H0 - 1, read by its height, both nodes at the mined tip's hash
    (`run_prestate` with `tip_height` and `tip_hash`),
    and step 8; the birth at the next block. Every host process has an event
    line file and writes no line. The outbox's one hand-off file is checked
    after each host phase."""
    summary: dict = {"labels": LAUNCH_LABELS, "construction_height": CASE_CONSTRUCTION, "late": L0_LATE}
    funding_descriptor = pair.a.call("getdescriptorinfo", FUNDING_DESCRIPTOR)["descriptor"]
    constructed = pair.mine(funding_descriptor, CASE_CONSTRUCTION)
    chain, funding = chain_facts(pair, constructed, CASE_CONSTRUCTION)
    summary["funding"] = funding
    online = dict(online_env)
    online.update(
        {
            "BITAGI_E3D3_NODE_A_PORT": str(pair.a.rpcport),
            "BITAGI_E3D3_NODE_B_PORT": str(pair.b.rpcport),
            "BITAGI_E3D3_NODE_A_LOG": pair.a.log_path,
            "BITAGI_E3D3_NODE_B_LOG": pair.b.log_path,
        }
    )
    genesis = chain.split("\n", 1)[0].removeprefix("genesis=")
    # The sign phase's one hand-off (its outbox name), once it is there.
    entry = "-"

    def host(worker: str, lines: list[str], env: dict) -> dict:
        command = worker_command(cargo, HOST_TEST, worker, [], HOST_PACKAGE)
        return run_stage(command, env, worker, lines, secrets_=secrets_)

    def signer(worker: str, lines: list[str], env: dict) -> dict:
        command = worker_command(cargo, LAUNCH_SIGNER_TEST, worker, ["--features", "offline-ceremony"], SIGNER_PACKAGE)
        return run_stage(command, env, worker, lines, secrets_=secrets_)

    def late_host(key: str, env: dict) -> dict:
        # Each process its own event line file, its names `EVENT_LINES[key]`
        # (none: nothing at H0 - 2, nothing above H0 - 1).
        lines = work / f"lines-{key.replace(' ', '-')}.txt"
        got = host(L0_WORKER, L0_LINES, {**env, "BITAGI_E3D3_EVENT_LINES": str(lines.resolve())})
        if event_names(lines, secrets_) != EVENT_LINES[key]:
            raise Mismatch(f"{key} event lines {event_names(lines, None)}")
        return got

    def phase(name: str, tip: str, txid: str | None, height: int) -> dict:
        nonlocal entry
        stage_env = dict(online)
        stage_env["BITAGI_E3D3_PHASE"] = name
        if name in L0LATE_SENDING:
            stage_env["BITAGI_E3D3_SEND_AUTH"] = send.auth()
        pending = None
        if name in L0LATE_PENDING:
            # The first run ends at the late comparison (B-692a): the Rust
            # receipt of block H0 - 1 in the outbox, at the tip `height`.
            pending = late_host("pending " + name, stage_env)
            if (pending["phase"], pending["steps"], pending["hand_offs"]) != (name, L0LATE_PENDING[name], "0"):
                raise Mismatch(f"{name}: steps {pending['steps']}")
            check_nothing_sent(pair, tip, funding, txid, height)
            compared = run_prestate(pair, launch, prestate_dir / name, pending["prestate_receipt"], TIP_HEIGHT, height, tip)
            stage_env.update(compared["env"])
        got = replayed(name, late_host, stage_env, launch, root, summary, secrets_)
        expected = (name, L0LATE_STEPS[name], "-", L0LATE_HAND_OFFS.get(name, "0"))
        if (got["phase"], got["steps"], got["prestate_receipt"], got["hand_offs"]) != expected:
            raise Mismatch(f"{name}: steps {got['steps']}")
        if pending is not None:
            summary.setdefault("prestate_comparisons", []).append(prestate_summary(name, pending, compared, got))
        elif got["prestate_ms"] != "0":
            raise Mismatch(f"{name}: a prestate turn without a comparison")
        # Bytes only where step 8 handed some off.
        if name not in L0LATE_HAND_OFFS and got["raw_tx_sha256"] != "-":
            raise Mismatch(f"{name}: bytes without a hand-off")
        # The one Sign hand-off, written in the window, is the outbox's
        # only file after every phase.
        if name == "l0late_sign":
            outbox = listing(launch / "outbox")
            entry = outbox[0].removeprefix("sign-input-").removesuffix(".txt") if len(outbox) == 1 else "-"
        check_boundary(launch, "sign", {"entry": entry})
        # Nothing sent before step 8, at the tip the driver left.
        if name not in L0LATE_SENDING and name != "l0late_included":
            check_nothing_sent(pair, tip, funding, txid, height)
        summary[f"phase_{name}"] = got
        return got

    described = host(DESCRIBE_WORKER, DESCRIBE_LINES, online)
    descriptor = check_descriptor(described["descriptor"], genesis)
    summary["descriptor_sha256"] = hashlib.sha256(bytes.fromhex(descriptor)).hexdigest()
    check_nothing_sent(pair, constructed, funding, None, CASE_CONSTRUCTION)

    root = private(work / "l0late")
    launch = private(root / "launch")
    prestate_dir = private(root / "prestate")
    for name in ("handoff", "outbox", "export", "host"):
        private(launch / name)
    facts = root / "launch-facts.txt"
    # The host signs at the charge's own tip, H0 - 2 (L0's window).
    facts.write_text(chain + f"descriptor={descriptor}\n" + sign_tip_lines(constructed, CASE_CONSTRUCTION), encoding="ascii", newline="")
    facts.chmod(0o600)
    tmp = private(root / "launch-tmp")
    offline = dict(offline_env)
    offline.update({"BITAGI_E3D3_LAUNCH_FILE": str(facts.resolve()), "TMPDIR": str(tmp.resolve())})
    online["BITAGI_E3D3_LAUNCH"] = str(launch.resolve())
    try:
        summary["charge_stage"] = signer(CONTINUE_CHARGE_WORKER, CHARGE_LINES, offline)
        check_boundary(launch, "charge", {})
        # The budget the host is handed continues within limits on a miss.
        if (launch / "handoff" / "budget.json").read_text(encoding="ascii").count(CONTINUE_POLICY) != 1:
            raise Mismatch("l0late: the budget does not continue within limits")
        scan_key_material(work)
        check_nothing_sent(pair, constructed, funding, None, CASE_CONSTRUCTION)
        if listing(launch / "outbox"):
            raise Mismatch("L0LATE_OUTBOX")
        phase("l0late_sign", constructed, None, CASE_CONSTRUCTION)
        scan_key_material(work)

        try:
            exported = signer(OFFLINE_SIGN_WORKER, OFFLINE_SIGN_LINES, offline)
        except BaseException:
            shutil.rmtree(launch / "offline", ignore_errors=True)
            raise
        summary["offline_sign_stage"] = exported
        check_listing(launch, ["export", "handoff", "host", "outbox"], "L0LATE_DIR")
        check_boundary(launch, "export", {"candidate": exported["candidate_id"]})
        check_boundary(launch, "sign", {"entry": entry})
        scan_key_material(work)
        check_nothing_sent(pair, constructed, funding, None, CASE_CONSTRUCTION)
    finally:
        shutil.rmtree(tmp)
        facts.unlink()

    txid = exported["txid"]
    if not re.fullmatch(r"[0-9a-f]{64}", txid):
        raise Mismatch("the export's txid is not a digest")
    phase("l0late_wait", constructed, txid, CASE_CONSTRUCTION)
    # No host turn at H0 - 1 or H0: the floor block, H0 and the blocks to
    # H0 + L0_LATE, no transaction, nothing sent.
    late = pair.mine(funding_descriptor, 2 + L0_LATE)
    check_nothing_sent(pair, late, funding, txid, GATE + L0_LATE)
    sent = phase("l0late_broadcast", late, txid, GATE + L0_LATE)
    if sent["raw_tx_sha256"] != exported["raw_tx_sha256"]:
        raise Mismatch("the broadcast bytes are not the offline export's")
    check_submitted(pair, late, funding, txid, height=GATE + L0_LATE)
    summary["submitted_late"] = "PASS"
    # The next block, mined by node A with the transaction; both agree.
    born = pair.mine(funding_descriptor, 1)
    for node in pair.both():
        block = node.call("getblock", node.best(), "1")
        if txid not in block["tx"] or node.call("getmempoolinfo")["size"] != 0:
            raise Mismatch(f"{node.label}: the transaction is not in the late block")
        if node.call("gettxout", funding["txid"], str(funding["vout"]), "false"):
            raise Mismatch(f"{node.label}: funding output not spent in the chain")
    phase("l0late_included", born, txid, GATE + L0_LATE + 1)
    if len(summary.get("prestate_comparisons", [])) != len(L0LATE_PENDING):
        raise Mismatch("L0LATE_PENDING: not every late comparison ran")
    summary["tips"] = {"signed_at": constructed, "late": late, "born": born}
    summary["event_lines"] = "PASS"
    return summary


def ardr_modules():
    """D1's driver and D2-1's bidders, imported only when a 1e-2b-2b pair
    runs. Both import this module; run as a script it is `__main__`, so
    they are handed this one module (its `Mismatch` and `Prerequisite`)."""
    this = sys.modules.get(__name__)
    if this is not None:
        sys.modules.setdefault("claude_track_regtest_offline_export", this)
    if str(Path(__file__).resolve().parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
    import claude_track_ardr_bidders as bidders
    import claude_track_ardr_driver as ardr

    return ardr, bidders


class PairMiner:
    """D1's miner process on node A of a 1e-2b-2b pair (Q-b4 B1). Each
    block: both nodes on it, and each transaction's mark."""

    def __init__(self, pair: Pair):
        self.ardr, _ = ardr_modules()
        if pair.a.miner_user is None or pair.a.miner_rpcs != self.ardr.MINER_RPCS:
            raise Prerequisite("node A has no miner user for exactly MINER_RPCS")
        self.pair = pair
        self.process = self.ardr.MinerProcess(pair.a, MINER_POLICY)
        self.blocks: list[dict] = []

    def block(self, private: tuple[str, ...] = ()) -> dict:
        start = self.pair.a.height()
        try:
            for raw in private:
                self.process.add_private(raw)
            built = self.process.build_block()
        except self.ardr.Refusal as error:
            raise Mismatch(f"the miner refused: {error.code}") from None
        if built["submit_result"] is not None:
            raise Mismatch(f"the node refused the miner's block: {str(built['submit_result'])[:80]}")
        if self.pair.agreed(start + 1) != built["block_hash"]:
            raise Mismatch("the nodes are not on the miner's block")
        order = []
        for entry in built["order"]:
            if entry["source"] not in MINER_MARKS:
                raise Mismatch(f"the miner's source {entry['source']}")
            order.append({"txid": entry["txid"], "mark": MINER_MARKS[entry["source"]], "fee": entry["fee"], "vsize": entry["vsize"]})
        record = {"height": int(built["height"]), "hash": built["block_hash"], "order": order}
        self.blocks.append(record)
        return record

    def stop(self) -> None:
        self.process.stop()


class Competitor:
    """The COMPETITOR wallet C00 of D2-1's generator (the one generator):
    its funding and its rung at a gate, TEST_ONLY keys from a public seed."""

    def __init__(self, cargo: str, work: Path):
        self.ardr, self.bidders = ardr_modules()
        self.worker = self.bidders.Worker(cargo, COMPETITOR_SEED, COMPETITOR_RUN, GATE, private(work))
        self.funding: dict | None = None

    def guarded(self, what, *args):
        try:
            return what(*args)
        except self.ardr.Refusal as error:
            raise Mismatch(f"the generator refused: {error.code}") from None

    def funding_raw(self, prevout: tuple[str, int], value: int) -> bytes:
        keys = self.guarded(self.worker.keys, [COMPETITOR])
        script = bytes.fromhex(keys[COMPETITOR[1]]["fee_script"])
        return self.guarded(self.bidders.funding_tx, prevout, value, [(self.bidders.FUNDING_VALUE, script)])

    def rung(self, tip: str, fee: int) -> dict:
        built = self.guarded(self.worker.build, COMPETITOR[0], COMPETITOR[1], GATE, (TIP_HEIGHT, tip), self.funding,
                          COMPETITOR[2], [fee], None)
        if len(built) != 1 or built[0]["gate"] != GATE or built[0]["fee"] != fee:
            raise Mismatch("the generator's rung")
        return built[0]


def secrets_2b(secrets_: Secrets, work: Path, pairs: tuple[Pair, ...], miners: tuple[RunUser, ...]) -> Secrets:
    """`run_secrets`' set with the 1e-2b-2b pairs' log paths and ports, the
    miner users' credentials and the eighth and ninth pairs' host state."""
    nodes = [node for pair in pairs for node in pair.both()]
    return Secrets(
        secrets_.needles
        + tuple(n for user in miners for n in user.needles())
        + tuple(node.log_path for node in nodes)
        + tuple(str(work / name / "launch" / "host" / "state") for name in ("e10", "e7")),
        secrets_.ports + tuple(port for node in nodes for port in (node.rpcport, node.port)),
    )


def construct_2b(pair: Pair, miner: PairMiner, competitor: Competitor) -> str:
    """§1's chain to H0 - 2: block 1 to the funding descriptor, block 2 to
    P2WSH(OP_TRUE), the blocks to H0 - 3 to the funding descriptor, then
    block H0 - 2 from the miner with the competitor's funding transaction
    handed privately (`THIRD_PARTY`). Returns block H0 - 2."""
    funding_descriptor = pair.a.call("getdescriptorinfo", FUNDING_DESCRIPTOR)["descriptor"]
    payout = pair.a.call("getdescriptorinfo", f"raw({competitor.ardr.PAYOUT_SCRIPT.hex()})")["descriptor"]
    pair.mine(funding_descriptor, FUNDING_HEIGHT)
    pair.mine(payout, COMPETITOR_SOURCE_HEIGHT - FUNDING_HEIGHT)
    pair.mine(funding_descriptor, CASE_CONSTRUCTION - 1 - COMPETITOR_SOURCE_HEIGHT)
    source = pair.a.call("getblock", pair.a.call("getblockhash", str(COMPETITOR_SOURCE_HEIGHT)), "2")["tx"][0]
    if source["vout"][0]["scriptPubKey"]["hex"] != competitor.ardr.PAYOUT_SCRIPT.hex():
        raise Mismatch("the competitor's source output")
    raw = competitor.funding_raw((source["txid"], 0), sats(source["vout"][0]["value"]))
    txid = competitor.ardr.Tx(raw).txid
    block = miner.block((raw.hex(),))
    marks = [(entry["txid"], entry["mark"], entry["fee"]) for entry in block["order"]]
    if block["height"] != CASE_CONSTRUCTION or marks != [(txid, "THIRD_PARTY", competitor.bidders.FUNDING_FEE)]:
        raise Mismatch("block H0 - 2 is not the competitor's funding alone")
    for node in pair.both():
        if node.call("getmempoolinfo")["size"] != 0 or not node.call("gettxout", txid, "0", "false"):
            raise Mismatch(f"{node.label}: the competitor's funding is not confirmed")
    competitor.funding = {"txid": txid, "vout": 0, "value": competitor.bidders.FUNDING_VALUE, "height": CASE_CONSTRUCTION}
    return block["hash"]


def competitor_fee(pair: Pair, txid: str, vsize: int) -> int:
    """`COMPETITOR_FEE_FACTOR` times P0's fee per vbyte (node A's entry) at
    `vsize`, rounded up: the competitor's ancestor feerate above P0's."""
    entry = pair.a.call("getmempoolentry", txid)
    fee, size = sats(entry["fees"]["base"]), int(entry["vsize"])
    return -(-COMPETITOR_FEE_FACTOR * fee * vsize // size) + 1


def check_report(name: str, report: str) -> None:
    """The worker's report for `name` against `LOST_REPORTS`."""
    expected = LOST_REPORTS[name]
    if expected.endswith(STALE):
        prefix = expected.removesuffix(STALE)
        got = re.fullmatch(re.escape(prefix) + rf"Stale:{GATE}:([1-9][0-9]*)", report)
        if got is None or int(got.group(1)) <= GATE:
            raise Mismatch(f"{name}: report {report}")
        return
    if report != expected:
        raise Mismatch(f"{name}: report {report}")


def check_reorg_procedure(path: Path, local: tuple[int, str], at_local: str, ancestor: tuple[int, str]) -> None:
    """A release phase's procedure file (the worker wrote it from its copy of
    the reorg), against the driver's own reads; step 6 not performed."""
    fields = dict(line.split("=", 1) for line in path.read_text(encoding="ascii").splitlines())
    expected = {
        "format": "BITAGI-LAUNCH-HOST-REORG-PROCEDURE-V1",
        "local_height": str(local[0]),
        "local_hash": internal(local[1]),
        "agreed_at_local": at_local,
        "ancestor_height": str(ancestor[0]),
        "ancestor_hash": internal(ancestor[1]),
        "step6": "not-performed",
    }
    if {key: fields.get(key) for key in expected} != expected:
        raise Mismatch(f"the procedure file is not the reorg's: {sorted(k for k in expected if fields.get(k) != expected[k])}")
    for key in ("procedure_sha256", "incident"):
        if not re.fullmatch(r"[0-9a-f]{64}", fields.get(key, "")):
            raise Mismatch(f"the procedure file's {key}")
    if not re.fullmatch(r"[1-9][0-9]*", fields.get("watermark_event", "")):
        raise Mismatch("the procedure file's watermark_event")


class LostContext:
    """One 1e-2b-2b launch: its pair, host files and the phase runner."""

    def __init__(self, pair: Pair, work: Path, cargo: str, online: dict, launch: Path, prestate_dir: Path,
                 send: RunUser, secrets_: Secrets, summary: dict):
        self.pair, self.work, self.cargo, self.online, self.launch = pair, work, cargo, online, launch
        self.prestate_dir, self.send, self.secrets, self.summary = prestate_dir, send, secrets_, summary
        self.entry = "-"
        self.txid: str | None = None
        # The bytes step 8 handed off, from the worker's report (E7's).
        self.last_hex = "-"

    def phase(self, name: str) -> dict:
        stage_env = dict(self.online)
        stage_env["BITAGI_E3D3_PHASE"] = name
        if name in LOST_SENDING:
            stage_env["BITAGI_E3D3_SEND_AUTH"] = self.send.auth()
        if name in LOST_ANSWER:
            stage_env["BITAGI_E3D3_ANSWER_PROXY"] = "A"
        command = worker_command(self.cargo, HOST_TEST, LOST_WORKER, [], HOST_PACKAGE)
        secrets_ = self.secrets

        def host(env: dict) -> dict:
            return run_stage(command, env, LOST_WORKER, LOST_LINES, secrets_=secrets_)

        pending = None
        if name in LOST_PENDING:
            # The first run ends at the H0 - 1 comparison (1d-3d-3d).
            pending = host(stage_env)
            if (pending["phase"], pending["steps"], pending["hand_offs"]) != (name, LOST_PENDING[name], "0"):
                raise Mismatch(f"{name}: steps {pending['steps']}")
            compared = run_prestate(self.pair, self.launch, self.prestate_dir / name, pending["prestate_receipt"])
            stage_env.update(compared["env"])
        got = host(stage_env)
        submitted = LOST_SUBMITTED[name] if LOST_SUBMITTED[name] == "-" else f"{LOST_SUBMITTED[name]};txid={self.txid}"
        expected = (name, LOST_STEPS[name], "-", LOST_HAND_OFFS.get(name, "0"), LOST_ANSWER.get(name, "-"), submitted)
        if (got["phase"], got["steps"], got["prestate_receipt"], got["hand_offs"], got["answer_lost"], got["submitted"]) != expected:
            raise Mismatch(f"{name}: {[got[k] for k in ('steps', 'hand_offs', 'answer_lost', 'submitted')]}")
        if pending is not None:
            self.summary.setdefault("prestate_comparisons", []).append(prestate_summary(name, pending, compared, got))
        elif got["prestate_ms"] != "0":
            raise Mismatch(f"{name}: a prestate turn without a comparison")
        check_report(name, got["report"])
        # Bytes only where step 8 handed some off; their hex beside their
        # hash (Q-b5: the driver reads no mempool's bytes).
        if name in LOST_RAW_HEX:
            if not re.fullmatch(r"(?:[0-9a-f]{2})+", got["raw_tx_hex"]):
                raise Mismatch(f"{name}: no raw_tx_hex")
            if hashlib.sha256(bytes.fromhex(got["raw_tx_hex"])).hexdigest() != got["raw_tx_sha256"]:
                raise Mismatch(f"{name}: raw_tx_hex is not the bytes handed off")
            self.last_hex = got["raw_tx_hex"]
        elif got["raw_tx_hex"] != "-":
            raise Mismatch(f"{name}: raw_tx_hex outside {LOST_RAW_HEX}")
        if name not in LOST_HAND_OFFS and got["raw_tx_sha256"] != "-":
            raise Mismatch(f"{name}: bytes without a hand-off")
        for node in self.pair.both():
            if node.height() != LOST_TIPS[name]:
                raise Mismatch(f"{node.label}: {name}: tip moved")
        if self.txid is not None and name in LOST_MEMPOOLS and mempools(self.pair, self.txid) != LOST_MEMPOOLS[name]:
            raise Mismatch(f"{name}: mempools {mempools(self.pair, self.txid)}")
        if name.endswith("_sign"):
            outbox = listing(self.launch / "outbox")
            self.entry = outbox[0].removeprefix("sign-input-").removesuffix(".txt") if len(outbox) == 1 else "-"
        check_boundary(self.launch, "sign", {"entry": self.entry})
        self.summary[f"phase_{name}"] = {k: v for k, v in got.items() if k != "raw_tx_hex"}
        return got

    def release(self, name: str, local: tuple[int, str], at_local: str, ancestor: tuple[int, str]) -> None:
        """The release phase, its procedure file checked, then removed (#450
        runbook §2 5)."""
        self.phase(name)
        procedure = self.launch / "host" / "procedure.txt"
        check_reorg_procedure(procedure, local, at_local, ancestor)
        procedure.unlink()

    def delta(self, delta: int) -> None:
        """P0's fee delta at node A (the miner's node), then the template's
        cache out (unit note §0)."""
        self.pair.fee_delta(self.pair.a, self.txid, delta)
        time.sleep(TEMPLATE_SECONDS)


def lost_launch(pair: Pair, work: Path, name: str, cargo: str, offline_env: dict, online_env: dict, send: RunUser,
                secrets_: Secrets, miner: PairMiner, competitor: Competitor, summary: dict) -> tuple[LostContext, str]:
    """A 1e-2b-2b pair to step 8 at X = H0 - 1: §1's construction, the
    describe stage, X, the charge under the continue budget, `<name>_sign`
    (the H0 - 1 comparison first), the offline signature and
    `<name>_broadcast` (the import and step 8). Returns the context and X."""
    constructed = construct_2b(pair, miner, competitor)
    chain, funding = chain_facts(pair, constructed, CASE_CONSTRUCTION)
    summary["funding"] = funding
    online = dict(online_env)
    online.update(
        {
            "BITAGI_E3D3_NODE_A_PORT": str(pair.a.rpcport),
            "BITAGI_E3D3_NODE_B_PORT": str(pair.b.rpcport),
            "BITAGI_E3D3_NODE_A_LOG": pair.a.log_path,
            "BITAGI_E3D3_NODE_B_LOG": pair.b.log_path,
        }
    )
    genesis = chain.split("\n", 1)[0].removeprefix("genesis=")
    described = run_stage(worker_command(cargo, HOST_TEST, DESCRIBE_WORKER, [], HOST_PACKAGE), online, DESCRIBE_WORKER,
                          DESCRIBE_LINES, secrets_=secrets_)
    descriptor = check_descriptor(described["descriptor"], genesis)
    summary["descriptor_sha256"] = hashlib.sha256(bytes.fromhex(descriptor)).hexdigest()
    check_nothing_sent(pair, constructed, funding, None, CASE_CONSTRUCTION)
    tip = pair.mine(pair.a.call("getdescriptorinfo", FUNDING_DESCRIPTOR)["descriptor"], 1)

    root = private(work / name)
    launch = private(root / "launch")
    for part in ("handoff", "outbox", "export", "host"):
        private(launch / part)
    context = LostContext(pair, work, cargo, online, launch, private(root / "prestate"), send, secrets_, summary)
    facts = root / "launch-facts.txt"
    facts.write_text(chain + f"descriptor={descriptor}\n" + sign_tip_lines(tip), encoding="ascii", newline="")
    facts.chmod(0o600)
    tmp = private(root / "launch-tmp")
    offline = dict(offline_env)
    offline.update({"BITAGI_E3D3_LAUNCH_FILE": str(facts.resolve()), "TMPDIR": str(tmp.resolve())})
    online["BITAGI_E3D3_LAUNCH"] = str(launch.resolve())

    def signer(worker: str, lines: list[str]) -> dict:
        command = worker_command(cargo, LAUNCH_SIGNER_TEST, worker, ["--features", "offline-ceremony"], SIGNER_PACKAGE)
        return run_stage(command, offline, worker, lines, secrets_=secrets_)

    try:
        summary["charge_stage"] = signer(CONTINUE_CHARGE_WORKER, CHARGE_LINES)
        check_boundary(launch, "charge", {})
        if (launch / "handoff" / "budget.json").read_text(encoding="ascii").count(CONTINUE_POLICY) != 1:
            raise Mismatch(f"{name}: the budget does not continue within limits")
        scan_key_material(work)
        check_nothing_sent(pair, tip, funding, None)
        context.phase(f"{name}_sign")
        scan_key_material(work)
        check_nothing_sent(pair, tip, funding, None)
        try:
            exported = signer(OFFLINE_SIGN_WORKER, OFFLINE_SIGN_LINES)
        except BaseException:
            shutil.rmtree(launch / "offline", ignore_errors=True)
            raise
        summary["offline_sign_stage"] = exported
        check_listing(launch, ["export", "handoff", "host", "outbox"], f"{name.upper()}_DIR")
        check_boundary(launch, "export", {"candidate": exported["candidate_id"]})
        scan_key_material(work)
        check_nothing_sent(pair, tip, funding, None)
    finally:
        shutil.rmtree(tmp)
        facts.unlink()
    txid = exported["txid"]
    if not re.fullmatch(r"[0-9a-f]{64}", txid):
        raise Mismatch("the export's txid is not a digest")
    context.txid = txid
    sent = context.phase(f"{name}_broadcast")
    if sent["raw_tx_sha256"] != exported["raw_tx_sha256"]:
        raise Mismatch("the broadcast bytes are not the offline export's")
    check_submitted(pair, tip, funding, txid)
    return context, tip


def check_order(block: dict, expected: list[tuple[str, str]], what: str) -> None:
    """A miner block's transactions, in order, with their marks."""
    if [(entry["txid"], entry["mark"]) for entry in block["order"]] != expected:
        raise Mismatch(f"{what}: block order {[(e['txid'][:8], e['mark']) for e in block['order']]}")


def run_e10(pair: Pair, work: Path, cargo: str, offline_env: dict, online_env: dict, send: RunUser, secrets_: Secrets) -> dict:
    """§2.1: E10 (a lost gate, P0 later) then E10-s (the same block, the
    competitor first) on `pair`, the miner on node A."""
    summary: dict = {"labels": LAUNCH_LABELS + ["THIRD_PARTY_COMPETITOR_TEST_ONLY"], "construction_height": CASE_CONSTRUCTION}
    miner = PairMiner(pair)
    try:
        competitor = Competitor(cargo, work / "e10-generator")
        context, tip = lost_launch(pair, work, "e10", cargo, offline_env, online_env, send, secrets_, miner, competitor, summary)
        txid = context.txid
        # E10: P0 out of node A's template; the competitor built at X and
        # handed to the miner; G.
        context.delta(-FEE_DELTA)
        rung = competitor.rung(tip, competitor_fee(pair, txid, competitor.bidders.CANDIDATE_VSIZE))
        summary["competitor"] = {k: rung[k] for k in ("txid", "fee", "vsize", "raw_sha256")}
        g = miner.block((rung["hex"],))
        check_order(g, [(rung["txid"], "THIRD_PARTY")], "e10_lost")
        context.phase("e10_lost")
        # The delta taken back: G + 1 with P0 from the template.
        context.delta(FEE_DELTA)
        g1 = miner.block()
        check_order(g1, [(txid, "TEMPLATE")], "e10_included")
        context.phase("e10_included")
        # E10-s: G + 1 and G dropped; both transactions back in both mempools.
        pair.drop_block(g1["hash"], GATE + 1)
        if pair.drop_block(g["hash"], GATE) != tip:
            raise Mismatch("the nodes are not back on X")
        if mempools(pair, rung["txid"]) != ("present", "present"):
            raise Mismatch("e10s: the competitor is not back in both mempools")
        context.phase("e10s_reorged")
        context.release("e10s_release", (GATE + 1, g1["hash"]), "below", (TIP_HEIGHT, tip))
        # G'' from the template: the competitor (the higher ancestor
        # feerate) before P0.
        time.sleep(TEMPLATE_SECONDS)
        same = miner.block()
        check_order(same, [(rung["txid"], "TEMPLATE"), (txid, "TEMPLATE")], "e10s_same")
        if same["hash"] == g["hash"]:
            raise Mismatch("G was not mined again")
        context.phase("e10s_same")
        summary["tips"] = {"x": tip, "g": g["hash"], "g_plus_1": g1["hash"], "g_again": same["hash"]}
        summary["miner_blocks"] = miner.blocks
    finally:
        miner.stop()
    return summary


def run_e7(pair: Pair, work: Path, cargo: str, offline_env: dict, online_env: dict, send: RunUser, secrets_: Secrets) -> dict:
    """§2.2: E7 and E7b in one flow on `pair`, the miner on node A."""
    summary: dict = {"labels": LAUNCH_LABELS + ["THIRD_PARTY_COMPETITOR_TEST_ONLY"], "construction_height": CASE_CONSTRUCTION}
    miner = PairMiner(pair)
    try:
        competitor = Competitor(cargo, work / "e7-generator")
        context, tip = lost_launch(pair, work, "e7", cargo, offline_env, online_env, send, secrets_, miner, competitor, summary)
        txid = context.txid
        p0_hex = context.last_hex
        # The competitor's fee from P0's entry while P0 is in node A's mempool.
        fee = competitor_fee(pair, txid, competitor.bidders.CANDIDATE_VSIZE)
        # X -> X' (another coinbase); P0 leaves both mempools (non-final at
        # H0 - 2's next block; 1e-2b-1 L3's cn01). Dated 2026-10-31 (after
        # the first E7 run): no fee delta, unlike the note's table: P0 is in
        # no mempool to keep out of X' or G', and with the delta node A's
        # re-admission at X' is `Rejected`.
        x, replaced = pair.replace_tip(pair.a.call("getdescriptorinfo", "raw(51)")["descriptor"])
        context.phase("e7_reorged")
        context.release("e7_release", (TIP_HEIGHT, x), internal(replaced), (TIP_HEIGHT, replaced))
        context.phase("e7_waiting")
        rung = competitor.rung(replaced, fee)
        summary["competitor"] = {k: rung[k] for k in ("txid", "fee", "vsize", "raw_sha256")}
        g = miner.block((rung["hex"],))
        check_order(g, [(rung["txid"], "THIRD_PARTY")], "e7_lost")
        context.phase("e7_lost")
        # P0's bytes, as step 8 handed them off, to the miner: G' + 1.
        g1 = miner.block((p0_hex,))
        check_order(g1, [(txid, "THIRD_PARTY")], "e7_included")
        context.phase("e7_included")
        summary["tips"] = {"x": x, "x_replaced": replaced, "g": g["hash"], "g_plus_1": g1["hash"]}
        summary["miner_blocks"] = miner.blocks
    finally:
        miner.stop()
    return summary


# Stage values the driver sets for one stage only.
STAGE_VALUES = ("BITAGI_E3D3_CHAIN_FILE", "TMPDIR")


def run(node_a: Path, node_b: Path, work: Path, cargo: str, offline_target: Path, online_target: Path) -> dict:
    if "RUSTFLAGS" in os.environ:
        raise Prerequisite("RUSTFLAGS is set; the offline stage's cfg comes only from " + OFFLINE_FLAGS_VARIABLE)
    if os.environ.get(OFFLINE_FLAGS_VARIABLE) != OFFLINE_RUSTFLAGS:
        raise Prerequisite(f"{OFFLINE_FLAGS_VARIABLE} must be exactly {OFFLINE_RUSTFLAGS!r}")
    check_ancestors(work)
    work.mkdir(parents=True, exist_ok=False)
    work.chmod(0o700)
    stage_dir = (work / "stage").resolve()
    stage_dir.mkdir(mode=0o700)
    offline_tmp = (work / "offline-tmp").resolve()
    offline_tmp.mkdir(mode=0o700)
    summary: dict = {"e3d3_labels": E3D3_LABELS, "gate": GATE, "tip_height": TIP_HEIGHT}
    send, admin = RunUser(SEND_USER), RunUser(ADMIN_USER)
    pair = Pair(node_a, node_b, work / "nodes", send, admin)
    cases = Pair(node_a, node_b, work / "cases-nodes", send, admin)
    e_pair = Pair(node_a, node_b, work / "e-nodes", send, admin)
    # 1e-2b-2b: D1's miner user on node A of the L0, eighth and ninth
    # pairs, for exactly D1's `MINER_RPCS` (Q-b4 B1).
    miner_rpcs = ardr_modules()[0].MINER_RPCS
    miners = tuple(RunUser(MINER_USER) for _ in range(3))
    l0_pair = Pair(node_a, node_b, work / "l0-nodes", send, admin, miner=miners[0], miner_rpcs=miner_rpcs)
    bound_pair = Pair(node_a, node_b, work / "bounded-nodes", send, admin)
    r2b_pair = Pair(node_a, node_b, work / "r2b-nodes", send, admin)
    e8_pair = Pair(node_a, node_b, work / "e8-nodes", send, admin)
    l0late_pair = Pair(node_a, node_b, work / "l0late-nodes", send, admin)
    e10_pair = Pair(node_a, node_b, work / "e10-nodes", send, admin, miner=miners[1], miner_rpcs=miner_rpcs)
    e7_pair = Pair(node_a, node_b, work / "e7-nodes", send, admin, miner=miners[2], miner_rpcs=miner_rpcs)
    secrets_ = run_secrets(work, (pair, cases, e_pair, l0_pair, bound_pair, r2b_pair, e8_pair, l0late_pair), send, admin)
    secrets_ = secrets_2b(secrets_, work, (e10_pair, e7_pair), miners)
    try:
        pair.start()
        summary["default_credential_refused"] = "PASS"
        versions = tuple(node.call("getnetworkinfo")["version"] for node in pair.both())
        if versions != NODE_VERSIONS:
            raise Prerequisite(f"node versions {versions}, expected {NODE_VERSIONS}")
        summary["node_versions"] = {"A": versions[0], "B": versions[1]}
        descriptor = pair.a.call("getdescriptorinfo", FUNDING_DESCRIPTOR)["descriptor"]
        tip = pair.mine(descriptor, TIP_HEIGHT)
        chain, funding = chain_facts(pair, tip)
        summary["funding"] = funding
        summary["tip_hash"] = tip
        facts = work / "chain-facts.txt"
        facts.write_text(chain, encoding="ascii", newline="")
        facts.chmod(0o600)
        summary["chain_facts_sha256"] = hashlib.sha256(chain.encode("ascii")).hexdigest()
        print(f"chain-facts.txt sha256 {summary['chain_facts_sha256']}", flush=True)

        base = {k: v for k, v in os.environ.items() if k != OFFLINE_FLAGS_VARIABLE}
        offline_env = dict(base)
        offline_env.update(
            {
                "RUSTFLAGS": OFFLINE_RUSTFLAGS,
                "CARGO_TARGET_DIR": str(offline_target),
                "BITAGI_E3D3_CHAIN_FILE": str(facts.resolve()),
                # The test helpers' scratch ledgers (`common::path`) go
                # here, and are removed with it after the stage.
                "TMPDIR": str(offline_tmp),
            }
        )
        try:
            offline = run_stage(
                worker_command(cargo, "offline_export_e2e_sign", OFFLINE_WORKER, ["--features", "offline-ceremony"]),
                offline_env,
                OFFLINE_WORKER,
                OFFLINE_LINES,
                secrets_=secrets_,
            )
        except BaseException:
            # A worker that failed may leave its session root and the
            # TEST_ONLY key files: remove them.
            shutil.rmtree(stage_dir / "offline", ignore_errors=True)
            raise
        finally:
            # Nothing of the offline stage but `handoff/` stays for the
            # online stage: not its scratch files, not the chain facts.
            shutil.rmtree(offline_tmp)
            facts.unlink()
        summary["offline_stage"] = offline
        if listing(work) != ["nodes", "stage"]:
            raise Mismatch(f"WORK_DIR {listing(work)}")
        handoff = check_handoff(stage_dir, offline["candidate_id"])
        check_nothing_sent(pair, tip, funding, None)

        online_env = dict(base)
        online_env["CARGO_TARGET_DIR"] = str(online_target)
        base_online = dict(online_env)
        online_env.update(
            {
                "CARGO_TARGET_DIR": str(online_target),
                "BITAGI_E3D3_HANDOFF": str(handoff),
                "BITAGI_E3D3_NODE_A_PORT": str(pair.a.rpcport),
                "BITAGI_E3D3_NODE_B_PORT": str(pair.b.rpcport),
            }
        )
        online = run_stage(
            worker_command(cargo, "two_node_offline_export", ONLINE_WORKER, []),
            online_env,
            ONLINE_WORKER,
            ONLINE_LINES,
            secrets_=secrets_,
        )
        if online["admission_reads"] != ADMISSION_READS:
            raise Mismatch(f"admission reads {online['admission_reads']}")
        summary["online_stage"] = online
        check_nothing_sent(pair, tip, funding, internal(online["txid"]))
        summary["nothing_sent"] = "PASS"
        summary["launch_host"] = run_launch(
            pair,
            work,
            chain,
            tip,
            funding,
            cargo,
            {k: v for k, v in offline_env.items() if k not in STAGE_VALUES},
            base_online,
            send,
            secrets_,
        )
    finally:
        pair.stop()
    try:
        cases.start()
        summary["launch_cases"] = run_cases(
            cases,
            work,
            cargo,
            {k: v for k, v in offline_env.items() if k not in STAGE_VALUES},
            base_online,
            send,
            secrets_,
        )
    finally:
        cases.stop()
    try:
        e_pair.start()
        summary["launch_e"] = run_e(
            e_pair,
            work,
            cargo,
            {k: v for k, v in offline_env.items() if k not in STAGE_VALUES},
            base_online,
            secrets_,
        )
    finally:
        e_pair.stop()
    try:
        l0_pair.start()
        started = time.monotonic()
        summary["launch_l0"] = run_l0(
            l0_pair,
            work,
            cargo,
            {k: v for k, v in offline_env.items() if k not in STAGE_VALUES},
            base_online,
            send,
            secrets_,
            rows_2b=True,
        )
        summary["launch_l0"]["pair_seconds"] = round(time.monotonic() - started)
    finally:
        l0_pair.stop()
    try:
        bound_pair.start()
        summary["launch_bounded"] = run_bounded(
            bound_pair,
            work,
            cargo,
            {k: v for k, v in offline_env.items() if k not in STAGE_VALUES},
            base_online,
            secrets_,
        )
    finally:
        bound_pair.stop()
    try:
        r2b_pair.start()
        started = time.monotonic()
        summary["launch_r2b"] = run_r2b(
            r2b_pair,
            work,
            cargo,
            {k: v for k, v in offline_env.items() if k not in STAGE_VALUES},
            base_online,
            send,
            secrets_,
        )
        summary["launch_r2b"]["pair_seconds"] = round(time.monotonic() - started)
    finally:
        r2b_pair.stop()
    try:
        e8_pair.start()
        started = time.monotonic()
        summary["launch_e8"] = run_e8(
            e8_pair,
            work,
            cargo,
            {k: v for k, v in offline_env.items() if k not in STAGE_VALUES},
            base_online,
            send,
            secrets_,
        )
        summary["launch_e8"]["pair_seconds"] = round(time.monotonic() - started)
    finally:
        e8_pair.stop()
    # B-692a-RT: the late prestate path on a tenth pair.
    try:
        l0late_pair.start()
        started = time.monotonic()
        summary["launch_l0_late"] = run_l0_late(
            l0late_pair,
            work,
            cargo,
            {k: v for k, v in offline_env.items() if k not in STAGE_VALUES},
            base_online,
            send,
            secrets_,
        )
        summary["launch_l0_late"]["pair_seconds"] = round(time.monotonic() - started)
    finally:
        l0late_pair.stop()
    # 1e-2b-2b: E10 and E10-s on an eighth pair, E7 and E7b on a ninth.
    for key, two_b, runner in (("launch_e10", e10_pair, run_e10), ("launch_e7", e7_pair, run_e7)):
        try:
            two_b.start()
            started = time.monotonic()
            summary[key] = runner(
                two_b,
                work,
                cargo,
                {k: v for k, v in offline_env.items() if k not in STAGE_VALUES},
                base_online,
                send,
                secrets_,
            )
            summary[key]["pair_seconds"] = round(time.monotonic() - started)
        finally:
            two_b.stop()
    summary["result"] = "PASS"
    secrets_.check(json.dumps(summary, sort_keys=True, default=str), "summary")
    return summary


# ---------------------------------------------------------------------------
# #682: one port draw per topology, and a node that exited instead of
# coming up.

# #682: every port this process has handed out (the latest 1024). A port the
# kernel offers again while an earlier node may still need it is redrawn.
ISSUED_PORTS: list[int] = []
ISSUED_KEPT = 1024
# Core's init errors for a listener it could not open: the P2P "Unable to
# bind to <addr> on this computer" and the RPC "Unable to bind any endpoint
# for RPC server".
BIND_FAILURE = b"Unable to bind"
START_GRACE = 10.0   # seconds a node whose first call failed gets to exit
LOG_TAIL = 64 * 1024


def draw_ports(count: int, source=socket.socket) -> list[int]:
    """#682: `count` distinct loopback ports for one topology. Every socket
    is held until all are drawn, so the kernel cannot offer one port twice;
    a port already drawn here, or handed out earlier by this process, is
    redrawn, never used (its socket stays held to the end). The ports are
    recorded, then all sockets are released together."""
    held: list = []
    ports: list[int] = []
    try:
        while len(ports) < count:
            if len(held) >= count + 64:
                raise Prerequisite("PORT_DRAW")
            sock = source()
            held.append(sock)
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            if port in ports or port in ISSUED_PORTS:
                continue
            ports.append(port)
        ISSUED_PORTS.extend(ports)   # recorded while still held: a concurrent draw cannot return them (A F2)
        del ISSUED_PORTS[:-ISSUED_KEPT]
    finally:
        for sock in held:
            sock.close()
    return ports


def start_failure(process, log_path: str, role: str, grace: float = 0.0) -> str | None:
    """#682: why a node's first call failed, when the node's own process has
    exited (waiting up to `grace` seconds for it to): `PORT_COLLISION <role>`
    when its debug log's tail holds Core's bind failure, else `NODE_EXITED
    <role>`. `None` while it still runs (a slow node: its own error stands).
    Code words only: no path, port or log text."""
    if process is None:
        return None
    try:
        if grace:
            process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        return None
    if process.poll() is None:
        return None
    try:
        with open(log_path, "rb") as log:
            log.seek(0, os.SEEK_END)
            log.seek(max(0, log.tell() - LOG_TAIL))
            tail = log.read(LOG_TAIL)
    except OSError:
        tail = b""
    return f"PORT_COLLISION {role}" if BIND_FAILURE in tail else f"NODE_EXITED {role}"


def wait_started(node, role: str) -> None:
    """#682: the node's first call, `-rpcwait` up to 120 s (through the
    node's own `call`). If it fails and the node's own process has exited,
    the failure is named for that (see `start_failure`); otherwise the
    call's own error is raised unchanged."""
    try:
        node.call("-rpcwait", "-rpcwaittimeout=120", "getblockchaininfo")
    except Prerequisite:
        code = start_failure(node.process, node.log_path, role, START_GRACE)
        if code is None:
            raise
        raise Prerequisite(code) from None


def main(argv: list[str] | None = None) -> int:
    if not __debug__:
        print("FAIL: optimized Python (-O) strips the checks", file=sys.stderr)
        return 4
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--node-a", type=Path, required=True, help="bin directory of Core 31.1")
    parser.add_argument("--node-b", type=Path, required=True, help="bin directory of Core 30.3")
    parser.add_argument("--work", type=Path, required=True, help="a new directory for this run")
    parser.add_argument("--cargo", default="cargo")
    parser.add_argument("--offline-target", type=Path, default=ROOT / "target/offline-build")
    parser.add_argument("--online-target", type=Path, default=ROOT / "target")
    args = parser.parse_args(argv)
    try:
        summary = run(
            args.node_a.resolve(),
            args.node_b.resolve(),
            args.work.resolve(),
            args.cargo,
            args.offline_target.resolve(),
            args.online_target.resolve(),
        )
    except Mismatch as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2
    except Prerequisite as error:
        print(f"PREREQUISITE: {error}", file=sys.stderr)
        return 3
    except Exception as error:  # an internal error is not a pass
        print(f"INTERNAL: {type(error).__name__}", file=sys.stderr)
        return 4
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    print("PASS: E3d-3 offline export, verify, import and guard, and the launch host's accept path, on two Regtest nodes")
    return 0


if __name__ == "__main__":
    import claude_track_exit
    claude_track_exit.run(main)
