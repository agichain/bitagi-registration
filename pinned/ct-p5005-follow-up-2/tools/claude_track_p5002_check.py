"""P5-002 endurance checker: the continuity proof, the S14 recount, the plan checks and the report (XA13, PR-1, PR-2a,
PR-2b).

Class T, private Signet, scope (b). The interface is docs/claude-track/formats/P5002_ENDURANCE_V1.md: this module
is built against that document, and its section 13 lists every name the VPS driver
(`tools/claude_track_p5002_driver.py`) and the hosted tool (`tools/claude_track_p5002_confirm.py`) use. Nothing
else here is an interface. The checker reads records and decides nothing by itself: the criteria are GOV072's
(at least `required_seconds` of continuous actual operation, S13) and TDS 6.8's (no critical-height disagreement,
S14), and follow-up registration 2 freezes these bytes.

  plan --mode M --attempt N --expected-head SHA --source-sha256 HEX --declaration NEW_FILE
       --bin-sha256 HEX --bitagi-sha256 HEX --fixture-sha256 HEX
       [--registration PATH --registration-sha256 HEX --s04-run-id ID] [--s04-dir DIR]
       [--duration-seconds D] [--sample-seconds S] [--block-seconds B] [--checkpoint-seconds C]
  attempt --records DIR --output NEW_FILE
  pilot-registration --commit SHA --output NEW_FILE

* `plan` (the hosted plan job) runs the plan checks of section 10 in their order on the `GITHUB_*` environment
  and writes `declaration.json`, which names the SHA-256 of the hosted build job's archive and of its two
  binaries (`binaries`). Since PR-2b both components are wired (`NOT_WIRED` is empty), so a CONFIRMATORY plan runs
  the registration checks; an EXPLORATORY plan runs from refs/heads/main with no registration, or from an attempt
  tag as the TEST_ONLY pilot (the XD-1 C2 analogue): it reads PILOT_REGISTRATION as merged on main, runs plan
  checks 6 to 9 against it, and is labelled and recorded EXPLORATORY only.
* The two components (PR-2b): the replay is B's TEST_ONLY Signet store fixture (`replay_build.json`, the driver's
  `--follow` rows in `replay.jsonl`; `replay_check()`), the monitor is `tools/claude_track_monitor.py run` over
  `bitagi monitor tick` (`monitor/request.json`, `monitor/monitor.jsonl`; `monitor_check()`, which reads the log
  with that tool's own `check_log`, imported when it is called). A read attempt passes the verdict only with both
  component checks PASS.
* Plan check 9 (PR-2a) is the S04 citation of a dispatch from an attempt tag: the cited rx02 main-push run, its
  record (the run's record artifact, else its record job's log, as `tools/claude_track_ardr_slices.py` reads it),
  and `s04_citation` of that record: `PASS_CLASS_T` and every subject's object id equal to the pinned commit's.
  The rule is copied from ARDR's `s04_run`, `s04_artifact_id`, `s04_job_id`, `s04_record_from_log`,
  `s04_record_bytes` and `s04_derive` (A's Q15: no ARDR module and no `tools/common.py` imported); the files are
  the ones the plan job's step "Read the cited S04 run" saved with GET requests, and nothing here makes a request.
* `attempt` reads one records directory locally and writes the attempt row of section 8.1 with the server anchors
  `NOT_CHECKED`: without the hosted listing no local read can give S13 `PASS`.
* `pilot-registration` writes the TEST_ONLY pilot file for A (A commits it on main naming the pilot's commit, then
  tags that commit and dispatches the EXPLORATORY pilot from the tag).
* The continuity rules (section 5) never sum two intervals: every gap or reset restarts the count, an interval
  lives in one sample chain that starts at 64 zeros, and the longest single interval is compared with
  `required_seconds`. `required_seconds()` reads that constant from `docs/policy/ACTIVE_VALIDATION_POLICY.json`
  itself (the file's pinned SHA-256 and its `signet` object), with no module of the Codex ledger imported and no
  ledger file read (CR-01), and only the hosted jobs call it (the VPS reads the value in the declaration).

Every command prints one line of canonical JSON on stdout (section 3) and never echoes input text, a label, a
file name or a path. Exit codes: 0 done; 2 validation; 3 unavailable; 4 internal; 5 security; 6 refusal
(optimized Python among them). No `assert` is a control. Stdlib only; nothing of ARDR or XD-1 is imported.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import time
import zipfile
import zlib

TOOLS = Path(__file__).resolve().parent

# ------------------------------------------------------------------------------------------ constants ----
FORMAT_DECLARATION = 'BITAGI_CT_P5002_DECLARATION_V1'
FORMAT_ENVIRONMENT = 'BITAGI_CT_P5002_ENVIRONMENT_V1'
FORMAT_MARKER = 'BITAGI_CT_P5002_MARKER_V1'
FORMAT_CHECKPOINT = 'BITAGI_CT_P5002_CHECKPOINT_V1'
FORMAT_FINAL = 'BITAGI_CT_P5002_FINAL_V1'
FORMAT_COMPONENTS = 'BITAGI_CT_P5002_COMPONENTS_V1'
FORMAT_SCOPE_FILE = 'BITAGI_CT_P5002_SCOPE_FILE_V1'
FORMAT_DISAGREEMENT = 'BITAGI_CT_P5002_S14_DISAGREEMENT_V1'
FORMAT_REPORT = 'BITAGI_CT_P5002_REPORT_V1'
OBSERVATION_SCHEMA = 'BITAGI_CT_OBSERVATION_LIST_V1'   # ct_preregistration_receipt.OBSERVATION_SCHEMA
OBSERVATION_PREFIX = 0      # OBS-0<attempt:07>; ARDR uses 1..8 and XD-1 uses 9 (A Q8)

# Section 1: each mode's labels (sorted), the bytes that refuse a record of that mode, and the fixed lines.
MODES = ('CONFIRMATORY', 'EXPLORATORY')
LABELS = {
    'CONFIRMATORY': ('CLASS_T', 'CONFIRMATORY', 'PRIVATE_SIGNET', 'SCOPE_B', 'TEST_ONLY'),
    'EXPLORATORY': ('CLASS_T', 'CLASS_T_DEVELOPMENT_EVIDENCE_NOT_S13', 'EXPLORATORY', 'PRIVATE_SIGNET', 'SCOPE_B',
                    'TEST_ONLY'),
}
SCALED_LABEL = 'EXPLORATORY_SCALED'
FORBIDDEN = {'CONFIRMATORY': (b'EXPLORATORY',), 'EXPLORATORY': (b'CONFIRMATORY',)}
SCALINGS = ('REGISTERED_CONSTANTS', 'EXPLORATORY_SCALED')
TRANSFERABILITY = ('Two nodes on one VPS, an OP_TRUE Signet challenge and scripted blocks do not transfer to the '
                   'mainnet hosts.')
SCOPE_B = ('P5-002 scope (b): two private Signet nodes, the replay and the watcher only; no launch host, no '
           'REGISTER or BEAT, no Signet H0-1 Rust/Python comparison.')
S14_NOT_COVERED = ('S14 heights not covered: every block containing a project REGISTER candidate; accepted '
                   'REGISTER height; every block containing a project BEAT candidate; accepted BEAT height. Not '
                   'counted from Regtest CI; open in P5-004 until a later Signet launch run under its own '
                   'registration.')
HOSTED_LIMITS = (
    'The final verification runs in the hosted report job of claude-track-p5002.yml, never on the VPS.',
    'It checks: the dispatched commit and, for a registered attempt, the registration and tag binding; the tree '
    'hash named by the plan job; the sample hash chain; the continuity rules recomputed from the raw samples; the '
    'S14 recount from the raw reads; labels; every counted attempt; the replay rows and the monitor log against the '
    'run\'s own reads; and the server times of the marker and the checkpoint artifacts.',
    'It can see: a job whose marker and checkpoints span less than the required seconds of GitHub server time; a '
    'missing, late or reordered checkpoint; a record that does not extend the checkpointed chain heads; a '
    'checkpoint whose committed sample is stale; sample clocks that do not follow server time from anchor to '
    'anchor; a VPS clock more than 300 s from server time at an anchor.',
    'It cannot see whether node answers, block hashes, uptime values, process ids, monotonic clock values, replay '
    'outputs and monitor logs are real: a hostile VPS holding the job\'s runtime token could upload a '
    'self-consistent fabricated record at the right server times, and the samples between two checkpoints are '
    'committed only by the later one.',
    'It cannot see whether the Signet blocks were made on the VPS by the two stated binaries, whether the VPS '
    'unpacked the tree it reports, or whether the VPS ran the binaries the hosted build job made.',
    'Start and end are bound to GitHub job server times and to the registration receipts.',
    'It cannot see a dispatch whose run was deleted, except that for a registered collection a run number missing '
    'between the first dispatch of the registration and the reporting run refuses the coverage. A run deleted '
    'before that first dispatch, or deleted together with every later run, leaves no gap: it is neither counted '
    'nor reported.',
    'It cannot know S14 for an attempt whose records are lost: the attempt is reported LOST with the largest '
    'disagreement count of its valid checkpoint files, and its critical reads after its last checkpoint are not '
    'known. A retry follows only after A records the investigated cause.',
    'Under a refused coverage it reads no record, a never-started run included, so the verdict is INCONCLUSIVE '
    'until the coverage is clean. A never-started run whose records artifact is missing or expired adds nothing '
    'to the verdict.',
    'The replay is a configuration-unverified synthetic-context replay of blocks with no project transaction, and '
    'the monitor\'s B_detect is not measured: no acknowledgement and no injected fault.',
)
ZERO_HASH = '0' * 64

# Section 2. required_seconds() returns GOV072's seconds as read from the policy file (POLICY_PATH, below).
NODES = ('a', 'b')
NODE_NAMES = {'a': 'SIGNET_NODE_A', 'b': 'SIGNET_NODE_B'}
NODE_VERSIONS = {'a': 310100, 'b': 300300}
BITCOIND_SHA256 = {'a': '986e63b3c8770f08d0059820ad3dd085d1ab9e1bea23946c243f858a06888a08',
                   'b': '30d4fa871a5447be1f57f195c3fd021c6fa44f920693aa4650e61769326edca8'}
PORTS = {'a': {'p2p': 38433, 'rpc': 38432}, 'b': {'p2p': 38443, 'rpc': 38442}}
PREMINE_CHUNK = 25
RPC_SECONDS = 20
SAMPLE_SECONDS, BLOCK_SECONDS, CHECKPOINT_SECONDS = 60, 600, 3600   # the registered base values
CLOCK_STEP_RECORD_SECONDS, CLOCK_STEP_GAP_SECONDS, ANCHOR_SLACK_SECONDS = 2, 60, 300   # never scaled
H0 = 200
SIGNET_CHALLENGE_HEX = '51'
MAX_ATTEMPTS = 3
MAX_CHECKPOINTS = 26
MAX_OBSERVATION_SECONDS = 96_000
MAX_SAMPLES = 16_000        # the samples up to the deadline: a samples.jsonl of that many lines fits LINES_LIMIT
# The EXPLORATORY scaling rule: each override's range (inclusive).
OVERRIDE_BOUNDS = {'duration_seconds': (60, 96_000), 'sample_seconds': (2, 60), 'block_seconds': (10, 600),
                   'checkpoint_seconds': (30, 3_700)}
CONSTANT_KEYS = ('required_seconds', 'sample_seconds', 'gap_seconds', 'clock_step_record_seconds',
                 'clock_step_gap_seconds', 'block_seconds', 'live_window_seconds', 'stop_margin_seconds',
                 'checkpoint_seconds', 'checkpoints', 'anchor_slack_seconds', 'h0', 'signet_challenge_hex',
                 'max_attempts')

COMPONENTS = ('monitor', 'replay')
# PR-2b: both components are wired. The guards that read this (plan check 4, COMPONENTS_NOT_WIRED) stay, dormant.
NOT_WIRED = ()
NOT_WIRED_STATE, WIRED_STATE = 'NOT_WIRED_PENDING_UNIT', 'WIRED'
# PR-2a: the S04 citation is plan check 9, so no plan check is missing. The guard in `plan` and its code
# S04_CITATION_NOT_WIRED stay (dormant while this is empty), so section 10's mechanism keeps its shape.
PLAN_CHECKS_NOT_WIRED = ()

MAIN_REF = 'refs/heads/main'
ATTEMPT_TAG = re.compile(r'refs/tags/ct-p5002-a[1-9][0-9]{0,2}')
TITLE = re.compile(r'p5002 (CONFIRMATORY|EXPLORATORY) attempt ([1-9][0-9]{0,2}) registration ([0-9a-f]{64}|none)')
WORKFLOW_PATH = '.github/workflows/claude-track-p5002.yml'
OBSERVE_JOB_NAME = 'P5-002 observe (VPS)'
MARKER_STEP_NAME = 'Upload the marker'       # the observe job's step that uploads p5002-started
FORMAT_DOC = 'docs/claude-track/formats/P5002_ENDURANCE_V1.md'
# The tag-path TEST_ONLY pilot (section 10; the XD-1 C2 analogue, `tools/claude_track_xd1_collect.py`): an
# EXPLORATORY dispatch from an attempt tag reads this file as merged on main, which must carry PILOT_LABEL, and runs
# plan checks 6 to 9 against it. A CONFIRMATORY plan refuses it by its path (anything under tests/) and by its label.
PILOT_REGISTRATION = 'tests/fixtures/p5002/P5002_PILOT_REGISTRATION_TEST_ONLY.json'
PILOT_LABEL = 'P5002_PILOT_REGISTRATION_TEST_ONLY_NEVER_A_REGISTRATION'
PILOT_NOTE = ('TEST_ONLY. Class T. Exercises the P5-002 registration read and the S04 citation for the EXPLORATORY '
              'pilot from an attempt tag; it is not a registration, and a registered attempt refuses it.')
# GOV072's policy file, read by required_seconds() alone (CR-01: no Codex ledger module or file is read for it).
POLICY_PATH = 'docs/policy/ACTIVE_VALIDATION_POLICY.json'
POLICY_SHA256 = 'e3068586e6b875604dab31d14731dc313d1b440fe7785fbc37fb044acdee7a07'
# The policy's `signet` object, exactly (the check GOV072's own policy reader makes of the same file).
POLICY_SIGNET = {'continuous_seconds': 86400, 'reset_restarts': True, 'unexplained_gap_restarts': True,
                 'actual_live_observation_required': True, 'other_exit_conditions_unchanged': True}
MONITOR_TOOL = 'tools/claude_track_monitor.py'
# PR-2b: the monitor loop and its log format, the two binaries' entry points (B's fixture example and the -2c-1 tick
# modules), and the files that pick their dependency versions and compiler; the format document stays last.
REGISTERED_PATHS = (
    'tools/claude_track_p5002_check.py', 'tools/claude_track_p5002_driver.py', 'tools/claude_track_p5002_confirm.py',
    'tools/claude_track_exit.py', POLICY_PATH, WORKFLOW_PATH, MONITOR_TOOL,
    'docs/claude-track/formats/MONITOR_LOG_V1.md', 'crates/bitagi-cli/examples/test_only_signet_store_fixture.rs',
    'crates/bitagi-cli/src/monitor_tick.rs', 'crates/bitagi-cli/src/monitor_alarms.rs', 'Cargo.lock',
    'rust-toolchain.toml', FORMAT_DOC)
ARTIFACTS = {'declaration': 'p5002-declaration', 'source': 'p5002-source', 'binaries': 'p5002-bin',
             'marker': 'p5002-started', 'checkpoint': 'p5002-checkpoint-', 'records': 'p5002-records'}
MEMBERS = ('declaration.json', 'environment.json', 'samples.jsonl', 'blocks.jsonl', 'critical_heights.jsonl',
           'components.json', 'replay_build.json', 'replay.jsonl', 'txs.jsonl', 'reserve_snapshots.jsonl',
           'final.json')
# The monitor's two files in p5002-records: not members (a missing or withheld log is a monitor check FAIL, not a
# lost attempt, because a separate process writes it), each read within its limit (LINES_LIMIT, SMALL_LIMIT).
MONITOR_FILES = ('monitor/request.json', 'monitor/monitor.jsonl')
SCOPE_FIELDS = {'txs.jsonl': ('attempt_id', 'tx_hex', 'broadcast_realtime_ns', 'first_seen_realtime_ns',
                              'inclusion_realtime_ns'),
                'reserve_snapshots.jsonl': ('realtime_ns', 'reserve_snapshot')}
SCOPE_STATE = 'NOT_APPLICABLE_SCOPE_B'
SMALL_LIMIT = 64 << 10
LINES_LIMIT = 16 << 20
ZIP_LIMIT = 256 << 20
FETCHED_LIMIT = 4 << 20
REGISTRATION_LIMIT = 1 << 20
REGISTERED_FILE_LIMIT = 16 << 20

BREAK_KINDS = ('FAILED_SAMPLE', 'CONTEXT', 'SAMPLE_GAP', 'CLOCK_STEP', 'SUSPEND', 'NODE_UPTIME', 'NODE_PID',
               'HEIGHT_DROP', 'BOOT_ID', 'SAMPLER_RESTART', 'CLOCK_DRIFT', 'NO_LIVE_BLOCK')
IDENTITY_CHECKS = ('ENVIRONMENT_BINDING', 'ENVIRONMENT_SOURCE', 'ENVIRONMENT_BINARY', 'ENVIRONMENT_BINARIES',
                   'ENVIRONMENT_CONTEXT', 'ENVIRONMENT_CLOCK', 'RECORDS_DECLARATION', 'CHALLENGE')
ANCHOR_RULES = ('SA1_JOB_ORDER', 'SA2_CLOCK_TIE', 'SA3_PREFIX', 'SA4_SPACING', 'SA5_ALL_PRESENT', 'SA6_SPAN',
                'SA7_SAMPLE_TIE')
S13_REASONS = ('IDENTITY', 'INTERVAL_SHORT', 'SERVER_ANCHOR', 'SERVER_ANCHOR_NOT_CHECKED')
UNREADABLE_CAUSES = ('DECLARATION_REFUSED', 'REGISTRATION_MISMATCH', 'LABELS_REFUSED', 'EVIDENCE_MISSING',
                     'COMPLETENESS_REFUSED', 'COMPONENTS_NOT_WIRED')
# Section 8.1: a counted attempt is read (COUNTED), reported without its records (LOST) or unreadable.
ATTEMPT_STATES = ('COUNTED', 'LOST', 'UNREADABLE')
LOST_REASON = 'RECORDS_LOST'        # a LOST attempt's S13 reason; its S14 result is LOST_S14
LOST_S14 = 'UNKNOWN'
# Section 8.3: the report's `coverage` is COVERAGE_OK or the code that refused the coverage (A's decision 5).
COVERAGE_OK = 'OK'
COVERAGE_CODES = ('OTHER_RUN_IN_PROGRESS', 'RUN_LIST_GAP', 'RUN_LIST_TITLE', 'MARKER_MISSING', 'ATTEMPT_OTHER_COMMIT',
                  'ATTEMPT_GAP', 'ATTEMPT_OVERLAP', 'ATTEMPTS_EXHAUSTED')
VERDICT_OPEN_REASONS = ('S13_NOT_YET_PASSED', 'S14_INCOMPLETE', 'COMPONENT_CHECK_FAILED')
# Section 6: what `missing` may hold besides `<kind>:<read>`.
S14_REPLACED, S14_NOT_ENVIRONMENT = 'REPLACED', 'GENESIS:NOT_ENVIRONMENT'
S14_FORK_UNDER_H0, S14_H0_NOT_PRODUCED = 'FORK_POINT:AT_OR_UNDER_H0', 'H0:NOT_PRODUCED_BLOCK'
CRITICAL_KINDS = ('GENESIS', 'H0_MINUS_1', 'H0')      # with FORK_POINT, the kinds of critical_heights.jsonl
CRITICAL_READS = ('FIRST', 'FINAL')
DAEMON_STATES = ('RUNNING', 'STOPPED', 'DEAD')
DAEMON_STOPS = ('STOP_RULE', 'DEADLINE')
STOP_REASONS = DAEMON_STOPS + ('FINISH', 'DAEMON_DEAD')
NODE_LOG_STATES = ('COPIED', 'WITHHELD_CREDENTIAL_SCAN', 'MISSING')
DAEMON_LOGS = ('out', 'err')        # final.json's daemon_logs: the daemon's own output and error output
# final.json's `monitor`: the log is copied whole or not at all (TOO_LARGE above LINES_LIMIT); `monitor.err` as a
# daemon log. `stop_reason` is the log's STOP `reason` (MONITOR_LOG_V1 section 4), read by the driver.
MONITOR_LOG_STATES = NODE_LOG_STATES + ('TOO_LARGE',)
MONITOR_STOPS = ('MAX_TICKS', 'SIGNAL_SIGTERM', 'SIGNAL_SIGINT', 'SIGNAL_SIGHUP', 'TICK_EXIT', 'LOG_WRITE_FAILED',
                 'INTERNAL_ERROR')
LIST_CUT = 1000             # the report keeps the first 1,000 breaks and clock steps
ENVIRONMENT_HOST = 'SELF_HOSTED_VPS'
ENVIRONMENT_CR21 = 'FD-CT-92 item 15 (2026-10-27)'

# The hosted build job's two binaries (PR-2b, A's decision 2): their names in the archive and in `<work>/bin/`, and
# the declaration's `binaries` (the archive's SHA-256 and each binary's).
BINARY_NAMES = {'bitagi': 'bitagi', 'fixture': 'test_only_signet_store_fixture'}
BINARIES_KEYS = ('archive_sha256', 'bitagi_sha256', 'fixture_sha256')
WORK_MARK = '<work>'                # how a copied log and a record name the VPS work directory

# The replay (PR-2b; A's decisions 7, 8): B's TEST_ONLY Signet store fixture
# (crates/bitagi-cli/examples/test_only_signet_store_fixture.rs). `start` builds the store once (its BUILD line),
# the daemon follows every `sample_seconds` and `finish` once more (each FOLLOW line). The line's keys and fixed
# values are the fixture's; `store_path` is checked by the driver and never recorded.
FORMAT_REPLAY_BUILD = 'BITAGI_CT_P5002_REPLAY_BUILD_V1'
REPLAY_LABEL = 'configuration-unverified synthetic-context replay'
FIXTURE_NAME = 'TEST_ONLY_PRIVATE_SIGNET_STORE_FIXTURE'
FIXTURE_NETWORK = 'PRIVATE_SIGNET'
FIXTURE_REPLAY_KIND = 'SYNTHETIC_CONTEXT_UNVERIFIED_SETTINGS'
FIXTURE_REPLAY_LABEL = '\uc124\uc815 \ubbf8\uac80\uc99d synthetic-context replay'     # B's REPLAY_LABEL
FIXTURE_UNVERIFIED = 'UNAVAILABLE'  # node_settings_verification
BUILD_KEYS = ('fixture', 'mode', 'network', 'node_settings_verification', 'genesis_hash_display',
              'signet_challenge_hex', 'substrate_context_hash', 'deployment_id_internal', 'profile_sha256',
              'first_effective_height', 'as_of_height', 'as_of_block_hash_display', 'store_path')
FOLLOW_KEYS = ('fixture', 'mode', 'replay_kind', 'replay_label', 'network', 'node_settings_verification',
               'substrate_context_hash', 'deployment_id_internal', 'sync_kind', 'ancestor_height',
               'disconnected_blocks', 'connected_blocks', 'replay_floor_reanchored', 'final_height',
               'final_hash_display', 'final_state_digest')
SYNC_KINDS = ('ALREADY_CURRENT', 'EXTENDED', 'REORGANIZED')
REPLAY_BUILD_RESULTS = ('BUILT', 'NOT_BUILT_S14_DISAGREEMENT', 'REFUSED', 'TIMEOUT', 'SPAWN_FAILED', 'OUTPUT_INVALID')
REPLAY_RESULTS = ('FOLLOWED', 'REFUSED', 'TIMEOUT', 'SPAWN_FAILED', 'OUTPUT_INVALID')
REPLAY_READS = ('POLL', 'FINAL')
# The code of the fixture's one stderr line (`test_only_signet_store_fixture: [node A: |node B: ]CODE: ...`);
# OTHER for a line without one (an RpcSession error has none). The text itself is never copied.
FIXTURE_REFUSALS = ('FOLLOW_REFUSED', 'STORE_REFUSED', 'STORE_MISSING', 'NODE_UNAVAILABLE', 'NODE_CHAIN_NOT_SIGNET',
                    'SIGNET_CHALLENGE_MISMATCH', 'NODE_GENESIS_MISMATCH', 'NODE_SUBSTRATE_REFUSED',
                    'H0_MINUS_1_UNAVAILABLE', 'H0_MINUS_1_DISAGREEMENT', 'H0_MINUS_1_NOT_GIVEN', 'GENESIS_NOT_SIGNET',
                    'DEFAULT_SIGNET_CHALLENGE_REFUSED', 'MAINNET_GENESIS_REFUSED', 'SUBSTRATE_REFUSED', 'OTHER')
FIXTURE_STDERR = re.compile(rb'test_only_signet_store_fixture: (?:node ([AB]): )?([A-Z][A-Z0-9_]{0,63}): [^\n]*\n?\Z')
FIXTURE_OUTPUT_LIMIT = 1 << 16      # the fixture's stdout or stderr that is read
REPLAY_CHECKS = ('REPLAY_BUILD', 'REPLAY_LABEL', 'REPLAY_CONTEXT', 'REPLAY_LAG', 'REPLAY_FINAL', 'REPLAY_CONSISTENT')
CHECK_RESULTS = ('PASS', 'FAIL', 'NOT_JUDGED')       # a component check; NOT_JUDGED when the store was not built

# The monitor (PR-2b; A's decisions 4, 5, 6): `tools/claude_track_monitor.py run` with the tick request of
# monitor_request() (no store, no Heart: -2c-1's P5-002 shape), polled every MONITOR_POLL_SECONDS, stopped by SIGTERM.
# Harness constants bound by the tool hashes, not registration constants (A's decision 10).
MONITOR_POLL_SECONDS, MONITOR_TICK_TIMEOUT_SECONDS = 120, 60
MONITOR_SPAN_SECONDS = 300          # checked TICKs at most this far apart in the longest interval (2 polls, a timeout)
MONITOR_LOG_FORMAT = 'docs/claude-track/formats/MONITOR_LOG_V1.md'
MONITOR_REQUEST_SCHEMA = 'BITAGI_CT_MONITOR_TICK_REQUEST_V1'
MONITOR_CONTEXT_MODE = 'CLASS_T_LOOPBACK_SETTINGS_UNVERIFIED'
# What START names, with the work directory written <work> (as finish copies the log)
MONITOR_PATHS = {'bitagi_path': WORK_MARK + '/bin/bitagi', 'request_path': WORK_MARK + '/monitor/request.json',
                 'log_path': WORK_MARK + '/monitor/monitor.jsonl'}
MONITOR_ALARMS = ('AL-0a', 'AL-0b', 'AL-1', 'AL-2', 'AL-3', 'AL-4', 'AL-5', 'AL-6', 'AL-7', 'AL-8', 'AL-9', 'AL-10')
MONITOR_COUNTDOWNS = ('HEART_NOT_CURRENT', 'MEASURED')
MONITOR_CHECKS = ('MONITOR_LOG', 'MONITOR_STOP', 'MONITOR_START', 'MONITOR_REQUEST', 'MONITOR_SPAN',
                  'MONITOR_ALARM_OUTPUT', 'MONITOR_COUNTDOWN_OUTPUT', 'MONITOR_CRITICAL_HEIGHTS')

# The S04 citation (plan check 9), copied from tools/claude_track_ardr_slices.py (S04_SCHEMA, S04_WORKFLOW_PATH,
# S04_JOB_NAME, S04_MEMBER, S04_LOG_LIMIT, S04_SOURCES, LOG_LINE, SHA_LINE; record format
# docs/claude-track/formats/S04_RECORD_V2.md). The cited run is a main push run of the rx02 workflow, matched on its
# `path`, never its display name; its record job uploads the record artifact `s04-record-v2-<run id>-<attempt>` and
# prints the record and its `sha256sum` line in its log. The six failures of s04_citation() are refusal codes of plan
# check 9.
S04_SCHEMA = 'bitagi.claude_track.s04_record.v2'
S04_PASS = 'PASS_CLASS_T'
S04_MAX_SUBJECTS = 4096
S04_FAILURES = ('S04_RECORD_JSON', 'S04_RECORD_SCHEMA', 'S04_NOT_PASS', 'S04_RECORD_COMMIT', 'S04_RECORD_RUN',
                'S04_SUBJECTS_CHANGED')
S04_WORKFLOW_PATH = '.github/workflows/claude-track-rx02.yml'
S04_JOB_NAME = 'S04 record v2 (leg set s04-legs-v1, this run only)'
S04_MEMBER = 's04_record_v2.json'
S04_ARTIFACT_PREFIX = 's04-record-v2-'      # + '<run id>-<run attempt>'
S04_SOURCES = ('ARTIFACT', 'JOB_LOG')
S04_RECORD_LIMIT = 1 << 20                  # the record artifact's zip and its member (ARDR's ZIP_LIMIT, JSON_LIMIT)
S04_LOG_LIMIT = 16 << 20
S04_LISTING_LIMIT = 100                     # one page of the artifact or jobs listing
# A job log line: the runner's timestamp, one space, the printed text; the record step's `sha256sum` line.
S04_LOG_LINE = re.compile(rb'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,9})?Z (.*)\Z', re.S)
S04_SHA_LINE = re.compile(rb'([0-9a-f]{64})  \S*/s04_record_v2\.json\Z')

EXIT_OK, EXIT_VALIDATION, EXIT_UNAVAILABLE, EXIT_INTERNAL, EXIT_SECURITY, EXIT_REFUSAL = 0, 2, 3, 4, 5, 6
# Section 10's table. COMPONENTS_NOT_WIRED is listed twice there: the plan's refusal (6) is the one held here, and
# an INCONCLUSIVE report line always exits EXIT_VALIDATION (output_line checks both).
REFUSALS = {code: exit_code for exit_code, codes in (
    (EXIT_VALIDATION, UNREADABLE_CAUSES + (
        'MODE', 'ATTEMPT_RANGE', 'SOURCE_SHA256', 'EXPLORATORY_INPUTS', 'OVERRIDE_RANGE', 'REGISTRATION_INPUTS',
        'REGISTRATION_PATH', 'REGISTRATION_NOT_ON_MAIN', 'REGISTRATION_SIZE', 'REGISTRATION_JSON',
        'REGISTRATION_P5002', 'DECLARATION_INVALID', 'RECORD_INVALID', 'CHECKPOINT_INDEX', 'LEFTOVER_PROCESS',
        'RUN_LIST_SHAPE', 'RUN_LIST_CHANGED', 'RUN_LIST_CAPPED', 'HEAD_SHA', 'CONTINUITY_INPUTS', 'OUTPUT_EXISTS',
        'BINARIES_SHA256')),
    (EXIT_UNAVAILABLE, (
        'GITHUB_IDS', 'MAIN_UNAVAILABLE', 'GIT_UNAVAILABLE', 'REGISTERED_FILE_MISSING', 'POLICY_UNAVAILABLE',
        'DECLARATION_MISSING', 'RECORDS_MISSING', 'NODE_BINARY_MISSING', 'NODE_NOT_READY', 'PEERS_NOT_CONNECTED',
        'PREMINE_FAILED', 'DAEMON_NOT_STARTED', 'DAEMON_STATE_MISSING', 'RUN_LIST_MISSING', 'RUN_LIST_JSON',
        'THIS_RUN_NOT_LISTED', 'ARTIFACT_LISTING', 'ARTIFACT_ZIP', 'JOBS_LISTING', 'INPUT_MISSING',
        'S04_RECORD_MISSING', 'S04_INPUT_MISSING', 'TOOL_BINARY_MISSING', 'REPLAY_BUILD_FAILED',
        'MONITOR_NOT_STARTED')),
    (EXIT_INTERNAL, ('INTERNAL_ERROR',)),
    (EXIT_SECURITY, ('MAINNET_REFUSED', 'CREDENTIAL_MATERIAL', 'PATH_NOT_REGULAR')),
    (EXIT_REFUSAL, (
        'OPTIMIZED_PYTHON', 'EVENT', 'RERUN', 'EXPECTED_HEAD', 'REF', 'OVERRIDE_REFUSED', 'COMPONENTS_NOT_WIRED',
        'S04_CITATION_NOT_WIRED', 'REGISTRATION_TEST_ONLY', 'NOT_ON_MAIN', 'REGISTRATION_SHA256_MISMATCH',
        'NOT_THE_PINNED_COMMIT', 'TOOL_SHA256_MISMATCH', 'REGISTRATION_CONSTANTS', 'REGISTRATION_FIXED_LINES',
        'DECLARATION_OTHER_RUN', 'SOURCE_MISMATCH', 'UNSUPPORTED_SIGNET_CONTEXT', 'OTHER_RUN_IN_PROGRESS',
        'RUN_NAME', 'RUN_LIST_GAP', 'RUN_LIST_TITLE', 'ATTEMPT_GAP', 'ATTEMPT_OVERLAP', 'ATTEMPT_OTHER_COMMIT',
        'ATTEMPT_NOT_NEXT', 'ATTEMPTS_EXHAUSTED', 'ARTIFACT_EXPIRED', 'ARTIFACT_DIGEST', 'MARKER_MISSING',
        'EARLIER_ATTEMPT_UNREADABLE', 'REPORT_ARTIFACT_PRESENT', 'PILOT_REGISTRATION', 'PILOT_REGISTRATION_LABEL',
        'S04_RUN_ID', 'S04_RUN_WORKFLOW', 'S04_RUN_EVENT', 'S04_RUN_BRANCH', 'S04_RUN_NOT_SUCCESS', 'S04_RUN_ATTEMPT',
        'S04_RUN_HEAD', 'S04_NOT_ON_PINNED_HISTORY', 'S04_ARTIFACT_LISTING', 'S04_ARTIFACT_ZIP', 'S04_JOB_NOT_LISTED',
        'S04_JOB_LOG_AMBIGUOUS', 'BINARY_MISMATCH') + S04_FAILURES),
) for code in codes}

TOOL_NAMES = ('p5002_check', 'p5002_driver', 'p5002_confirm')
RESULTS = ('DONE', 'REFUSED', 'INCONCLUSIVE', 'INTERNAL')
NS = 10**9
INT_MAX = 2**63 - 1
TIME_MAX = 253_402_300_799          # 9999-12-31T23:59:59Z, the last second the UTC text form holds
HEX40 = re.compile(r'[0-9a-f]{40}')
HEX64 = re.compile(r'[0-9a-f]{64}')
BOOT_ID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
CHAIN_NAME = re.compile(r'[a-z0-9]{1,16}')
CHALLENGE_HEX = re.compile(r'[0-9a-f]{0,1024}')
UTC = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z')
RUN_ID = re.compile(r'[1-9][0-9]{0,17}')
OUTPUT_TEXT = re.compile(r'[A-Za-z0-9_:-]{0,128}')
COMMAND_NAME = re.compile(r'[a-z][a-z0-9-]{0,31}')
GIT_SECONDS = 60

class Refusal(Exception):
    """A command ends with this closed code: `code`, and `exit_code` = REFUSALS[code]."""

    def __init__(self, code):
        if code not in REFUSALS:
            raise ValueError('refusal code')
        super().__init__(code)
        self.code = code
        self.exit_code = REFUSALS[code]


class Unreadable(Exception):
    """A counted attempt that cannot be read (section 8.1): `cause` is one of UNREADABLE_CAUSES."""

    def __init__(self, cause):
        if cause not in UNREADABLE_CAUSES:
            raise ValueError('unreadable cause')
        super().__init__(cause)
        self.cause = cause


class _Invalid(Exception):
    """A value outside section 4; the caller names the refusal."""


# ------------------------------------------------------------------------------- canonical serialization ----
def _plain(value, depth=0):
    """Objects, lists, strings, integers, booleans and null only: never a float."""
    if depth > 32:
        raise ValueError('not canonical: too deep')
    if value is None or type(value) in (bool, int, str):
        return
    if type(value) in (list, tuple):
        for item in value:
            _plain(item, depth + 1)
    elif type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError('not canonical: a key that is not a string')
            _plain(item, depth + 1)
    else:
        raise TypeError('not canonical: ' + type(value).__name__)


def canonical(value) -> bytes:
    """Section 4's serialization, with no newline."""
    _plain(value)
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def line(value: dict) -> bytes:
    return canonical(value) + b'\n'


def line_sha256(raw_line: bytes) -> str:
    """The SHA-256 of one line without its newline (the line may be given with or without it)."""
    text = raw_line[:-1] if raw_line.endswith(b'\n') else raw_line
    if b'\n' in text:
        raise ValueError('more than one line')
    return hashlib.sha256(text).hexdigest()


def chain_head(raw: bytes) -> str:
    """The chain head of a whole samples.jsonl: the SHA-256 of its last complete line, ZERO_HASH when it has none.
    Bytes after the last newline (a line still being written) are not a line."""
    end = raw.rfind(b'\n')
    if end < 0:
        return ZERO_HASH
    return hashlib.sha256(raw[raw.rfind(b'\n', 0, end) + 1:end]).hexdigest()


def _no_duplicates(pairs):
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise _Invalid('DUPLICATE_KEY')
    return dict(pairs)


def _no_number(text):
    raise _Invalid('NUMBER')


def _parse(text: bytes):
    """Strict JSON: ASCII, no duplicate key, no float, no NaN or Infinity."""
    try:
        return json.loads(text.decode('ascii'), object_pairs_hook=_no_duplicates, parse_float=_no_number,
                          parse_constant=_no_number)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise _Invalid('JSON') from exc


def _loose_json(raw: bytes):
    """JSON that is not a record of section 4 (a registration, a cited S04 record): UTF-8, no duplicate key, no
    NaN or Infinity; a float is allowed."""
    return json.loads(raw.decode('utf-8'), object_pairs_hook=_no_duplicates, parse_constant=_no_number)


def _one_line(raw, limit=SMALL_LIMIT) -> dict:
    """The object of a `.json` record: exactly one canonical line of at most `limit` bytes."""
    _need(type(raw) is bytes and len(raw) <= limit and raw.endswith(b'\n'))
    value = _parse(raw[:-1])
    _need(type(value) is dict and canonical(value) == raw[:-1])
    return value


def _lines(raw, limit=LINES_LIMIT) -> list[tuple[bytes, dict]]:
    """The lines of a `.jsonl` record (zero or more canonical lines and nothing else), each with its object."""
    _need(type(raw) is bytes and len(raw) <= limit)
    if not raw:
        return []
    _need(raw.endswith(b'\n'))
    rows = []
    for text in raw[:-1].split(b'\n'):
        value = _parse(text)
        _need(type(value) is dict and canonical(value) == text)
        rows.append((text, value))
    return rows


def _complete(raw: bytes) -> bytes:
    """The complete lines of a `.jsonl` record: bytes after the last newline (a line a killed writer left
    unfinished) are not a line."""
    return raw[:raw.rfind(b'\n') + 1]


def _same(left, right) -> bool:
    """Equal as canonical bytes (so true is never 1)."""
    try:
        return canonical(left) == canonical(right)
    except (TypeError, ValueError):
        return False


# --------------------------------------------------------------------------------------------- schemas ----
def _need(condition):
    if not condition:
        raise _Invalid('SCHEMA')


def _keys(value, keys):
    _need(type(value) is dict and set(value) == set(keys))


def _is_int(value, low=0, high=INT_MAX) -> bool:
    return type(value) is int and low <= value <= high


def _is_hash(value) -> bool:
    return type(value) is str and HEX64.fullmatch(value) is not None


def _is_sha(value) -> bool:
    return type(value) is str and HEX40.fullmatch(value) is not None


def _is_text(value, low=0, high=64) -> bool:
    return type(value) is str and low <= len(value) <= high


def _is_mode(value) -> bool:
    return type(value) is str and value in MODES


def _derive(required, sample, block, checkpoint):
    """The fourteen effective constants from the four base values by section 2's formulas; None outside its
    bounds."""
    values = dict(duration_seconds=required, sample_seconds=sample, block_seconds=block, checkpoint_seconds=checkpoint)
    for name, value in values.items():
        low, high = OVERRIDE_BOUNDS[name]
        if type(value) is not int or not low <= value <= high:
            return None
    if block < sample or checkpoint < sample:
        return None
    margin = 10 * sample
    checkpoints = -(-(required + margin) // checkpoint) + 1
    if checkpoints > MAX_CHECKPOINTS or checkpoints * checkpoint > MAX_OBSERVATION_SECONDS:
        return None
    if checkpoints * checkpoint > MAX_SAMPLES * sample:     # more samples by the deadline than LINES_LIMIT holds
        return None
    return {'required_seconds': required, 'sample_seconds': sample, 'gap_seconds': 3 * sample,
            'clock_step_record_seconds': CLOCK_STEP_RECORD_SECONDS, 'clock_step_gap_seconds': CLOCK_STEP_GAP_SECONDS,
            'block_seconds': block, 'live_window_seconds': 3 * block, 'stop_margin_seconds': margin,
            'checkpoint_seconds': checkpoint, 'checkpoints': checkpoints,
            'anchor_slack_seconds': ANCHOR_SLACK_SECONDS, 'h0': H0, 'signet_challenge_hex': SIGNET_CHALLENGE_HEX,
            'max_attempts': MAX_ATTEMPTS}


def _check_constants(constants, scaling):
    _keys(constants, CONSTANT_KEYS)
    derived = _derive(constants['required_seconds'], constants['sample_seconds'], constants['block_seconds'],
                      constants['checkpoint_seconds'])
    _need(derived is not None and _same(constants, derived))
    if scaling == SCALINGS[0]:
        _need((constants['sample_seconds'], constants['block_seconds'], constants['checkpoint_seconds'])
              == (SAMPLE_SECONDS, BLOCK_SECONDS, CHECKPOINT_SECONDS))


def _check_citation(value):
    """The declaration's `s04_citation` (plan check 9's result)."""
    _keys(value, ('record_sha256', 'record_source', 's04_run_attempt', 's04_head_sha', 'subjects'))
    _need(_is_hash(value['record_sha256']) and type(value['record_source']) is str
          and value['record_source'] in S04_SOURCES)
    _need(_is_int(value['s04_run_attempt'], 1, 999) and _is_sha(value['s04_head_sha'])
          and _is_int(value['subjects'], 1, S04_MAX_SUBJECTS))


def _check_binaries(value):
    """The declaration's `binaries`: the hosted build job's archive and its two binaries, 64 hex each."""
    _keys(value, BINARIES_KEYS)
    _need(all(_is_hash(item) for item in value.values()))


def _check_declaration(value):
    _keys(value, ('format', 'mode', 'attempt', 'head_sha', 'ref', 'run_id', 'run_attempt', 'registration_sha256',
                  's04_run_id', 's04_citation', 'source_sha256', 'binaries', 'scaling', 'constants', 'labels'))
    _need(value['format'] == FORMAT_DECLARATION and _is_mode(value['mode']))
    confirmatory = value['mode'] == 'CONFIRMATORY'
    _need(_is_int(value['attempt'], 1, MAX_ATTEMPTS if confirmatory else 1))
    _need(_is_sha(value['head_sha']) and _is_int(value['run_id'], 1) and _is_int(value['run_attempt'], 1, 1))
    ref = value['ref']
    # a dispatch from an attempt tag is cited (CONFIRMATORY, or the EXPLORATORY pilot); EXPLORATORY also from main
    tagged = type(ref) is str and ATTEMPT_TAG.fullmatch(ref) is not None
    _need(tagged or (not confirmatory and ref == MAIN_REF))
    # an EXPLORATORY declaration names no registration, the pilot's TEST_ONLY file included (XD-1 C2)
    _need(_is_hash(value['registration_sha256']) if confirmatory else value['registration_sha256'] is None)
    if tagged:
        _need(_is_int(value['s04_run_id'], 1))
        _check_citation(value['s04_citation'])
    else:
        _need(value['s04_run_id'] is None and value['s04_citation'] is None)
    _need(_is_hash(value['source_sha256']))
    _check_binaries(value['binaries'])
    scaling = value['scaling']
    _need(type(scaling) is str and scaling in SCALINGS and not (confirmatory and scaling != SCALINGS[0]))
    _check_constants(value['constants'], scaling)
    _need(_same(value['labels'], labels_for(value['mode'], scaling == SCALINGS[1])))


def _check_environment(value):
    _keys(value, ('format', 'mode', 'attempt', 'head_sha', 'run_id', 'source_sha256', 'nodes', 'binaries',
                  'signet_challenge_hex', 'genesis_hash', 'h0', 'boot_id', 'clock', 'host', 'start_monotonic_ns',
                  'start_realtime_ns', 'labels', 'transferability', 'scope_b', 's14_not_covered'))
    _need(value['format'] == FORMAT_ENVIRONMENT and _is_mode(value['mode']))
    _need(_is_int(value['attempt'], 1, MAX_ATTEMPTS) and _is_sha(value['head_sha']) and _is_int(value['run_id'], 1))
    _need(_is_hash(value['source_sha256']) and _is_hash(value['genesis_hash']) and _is_int(value['h0']))
    _keys(value['nodes'], NODES)
    for key in NODES:
        node = value['nodes'][key]
        _keys(node, ('name', 'version', 'bitcoind_sha256', 'args', 'p2p_port', 'rpc_port'))
        _need(node['name'] == NODE_NAMES[key] and _is_int(node['version']) and _is_hash(node['bitcoind_sha256']))
        _need(type(node['args']) is list and len(node['args']) <= 64
              and all(_is_text(arg, 1, 512) for arg in node['args']))
        _need(_is_int(node['p2p_port'], 1, 65535) and _is_int(node['rpc_port'], 1, 65535))
    # the two binaries' SHA-256 as the VPS computed them (S1b); ENVIRONMENT_BINARIES compares them
    _keys(value['binaries'], BINARY_NAMES)
    _need(all(_is_hash(item) for item in value['binaries'].values()))
    challenge = value['signet_challenge_hex']
    _need(type(challenge) is str and CHALLENGE_HEX.fullmatch(challenge) is not None)
    _need(type(value['boot_id']) is str and BOOT_ID.fullmatch(value['boot_id']) is not None)
    _keys(value['clock'], ('source', 'ntp_synchronized'))
    synchronized = value['clock']['ntp_synchronized']
    # an empty source is a valid record of a clocksource that could not be read; ENVIRONMENT_CLOCK then fails
    _need(_is_text(value['clock']['source'], 0, 32) and (synchronized is None or type(synchronized) is bool))
    host = value['host']
    _keys(host, ('nproc', 'mem_total_kb', 'disk_free_kb', 'kernel', 'python', 'runner_name'))
    _need(all(_is_int(host[key]) for key in ('nproc', 'mem_total_kb', 'disk_free_kb')))
    _need(_is_text(host['kernel']) and _is_text(host['python']) and _is_text(host['runner_name'], 0, 128))
    _need(_is_int(value['start_monotonic_ns']) and _is_int(value['start_realtime_ns']))
    labels = value['labels']
    _need(type(labels) is list and len(labels) <= 16 and all(_is_text(label, 1) for label in labels))
    _need(all(_is_text(value[key], 0, 512) for key in ('transferability', 'scope_b', 's14_not_covered')))


def _check_marker(value):
    _keys(value, ('format', 'mode', 'attempt', 'head_sha', 'run_id', 'run_attempt', 'registration_sha256', 'seq',
                  'head_sha256', 'monotonic_ns', 'realtime_ns'))
    _need(value['format'] == FORMAT_MARKER and _is_mode(value['mode']))
    confirmatory = value['mode'] == 'CONFIRMATORY'
    _need(_is_int(value['attempt'], 1, MAX_ATTEMPTS if confirmatory else 1) and _is_sha(value['head_sha']))
    _need(_is_int(value['run_id'], 1) and _is_int(value['run_attempt'], 1, 1))
    registration = value['registration_sha256']
    _need(_is_hash(registration) if confirmatory else registration is None)
    _need(_is_int(value['seq'], 0, 0) and _is_hash(value['head_sha256']))
    _need(_is_int(value['monotonic_ns']) and _is_int(value['realtime_ns']))


def _check_checkpoint(value):
    _keys(value, ('format', 'run_id', 'attempt', 'index', 'due_monotonic_ns', 'monotonic_ns', 'realtime_ns', 'seq',
                  'head_sha256', 'daemon_state', 'stop_reason', 'blocks', 'critical_reads', 's14_disagreements',
                  'current_interval_seconds'))
    _need(value['format'] == FORMAT_CHECKPOINT and _is_int(value['run_id'], 1))
    _need(_is_int(value['attempt'], 1, MAX_ATTEMPTS) and _is_int(value['index'], 1, MAX_CHECKPOINTS))
    _need(all(_is_int(value[key]) for key in ('due_monotonic_ns', 'monotonic_ns', 'realtime_ns', 'seq', 'blocks',
                                              'critical_reads', 's14_disagreements')))
    _need(_is_hash(value['head_sha256']))
    state, stop = value['daemon_state'], value['stop_reason']
    _need(type(state) is str and state in DAEMON_STATES)
    _need(type(stop) is str and stop in DAEMON_STOPS if state == 'STOPPED' else stop is None)
    _need(value['current_interval_seconds'] is None or _is_int(value['current_interval_seconds']))


def _check_final(value):
    _keys(value, ('format', 'run_id', 'attempt', 'stop_reason', 'samples', 'head_sha256', 'monotonic_ns',
                  'realtime_ns', 'challenge_final', 'nodes_stopped', 'leftover_processes', 'node_logs',
                  'daemon_logs', 'monitor', 'replay_store_sha256', 'vps_summary', 'fleet_scale'))
    _need(value['format'] == FORMAT_FINAL and _is_int(value['run_id'], 1))
    _need(_is_int(value['attempt'], 1, MAX_ATTEMPTS))
    _need(type(value['stop_reason']) is str and value['stop_reason'] in STOP_REASONS)
    _need(_is_int(value['samples']) and _is_hash(value['head_sha256']))
    _need(_is_int(value['monotonic_ns']) and _is_int(value['realtime_ns']) and _is_int(value['leftover_processes']))
    for key in ('challenge_final', 'nodes_stopped', 'node_logs'):
        _keys(value[key], NODES)
    for key in NODES:
        challenge = value['challenge_final'][key]
        _need(challenge is None or (type(challenge) is str and CHALLENGE_HEX.fullmatch(challenge) is not None))
        _need(type(value['nodes_stopped'][key]) is bool)
        _need(type(value['node_logs'][key]) is str and value['node_logs'][key] in NODE_LOG_STATES)
    _keys(value['daemon_logs'], DAEMON_LOGS)
    _need(all(type(state) is str and state in NODE_LOG_STATES for state in value['daemon_logs'].values()))
    monitor = value['monitor']
    _keys(monitor, ('log', 'err', 'exit', 'stop_reason'))
    _need(type(monitor['log']) is str and monitor['log'] in MONITOR_LOG_STATES)
    _need(type(monitor['err']) is str and monitor['err'] in NODE_LOG_STATES)
    _need(monitor['exit'] is None or _is_int(monitor['exit'], 0, 255))
    _need(monitor['stop_reason'] is None or (type(monitor['stop_reason']) is str
                                             and monitor['stop_reason'] in MONITOR_STOPS))
    _keys(value['replay_store_sha256'], ('profile', 'store'))
    _need(all(item is None or _is_hash(item) for item in value['replay_store_sha256'].values()))
    summary = value['vps_summary']
    _keys(summary, ('longest_interval_seconds', 'breaks', 's14_disagreements'))
    _need(summary['longest_interval_seconds'] is None or _is_int(summary['longest_interval_seconds']))
    _need(_is_int(summary['breaks']) and _is_int(summary['s14_disagreements']))
    _need(value['fleet_scale'] == 'NOT_MEASURED')


def _check_components(value):
    _keys(value, ('components', 'format'))
    _need(value['format'] == FORMAT_COMPONENTS)
    _keys(value['components'], COMPONENTS)
    _need(all(type(state) is str and state in (NOT_WIRED_STATE, WIRED_STATE)
              for state in value['components'].values()))


def _check_build_line(line):
    """replay_build.json's `line`: the fixture's BUILD summary without `store_path`, its keys closed and typed (the
    values replay_check() compares are not fixed here)."""
    _keys(line, BUILD_KEYS[:-1])
    _need(all(type(line[key]) is str and 1 <= len(line[key]) <= 128 for key in (
        'fixture', 'mode', 'network', 'node_settings_verification')))
    _need(all(_is_hash(line[key]) for key in ('genesis_hash_display', 'substrate_context_hash',
                                             'deployment_id_internal', 'profile_sha256', 'as_of_block_hash_display')))
    _need(type(line['signet_challenge_hex']) is str and CHALLENGE_HEX.fullmatch(line['signet_challenge_hex']))
    _need(_is_int(line['first_effective_height']) and _is_int(line['as_of_height']))


def _check_follow_line(line):
    """A FOLLOWED row's `line`: the fixture's FOLLOW summary, its keys closed and typed (the labels and the context
    are compared by replay_check(), so a record that names others is a REPLAY_* FAIL, not an unreadable one)."""
    _keys(line, FOLLOW_KEYS)
    _need(all(type(line[key]) is str and 1 <= len(line[key]) <= 128 for key in (
        'fixture', 'mode', 'replay_kind', 'replay_label', 'network', 'node_settings_verification')))
    _need(all(_is_hash(line[key]) for key in ('substrate_context_hash', 'deployment_id_internal', 'final_hash_display',
                                             'final_state_digest')))
    _need(type(line['sync_kind']) is str and line['sync_kind'] in SYNC_KINDS)
    _need(all(_is_int(line[key]) for key in ('ancestor_height', 'disconnected_blocks', 'connected_blocks',
                                            'final_height')))
    _need(type(line['replay_floor_reanchored']) is bool)


def _check_replay_build(value):
    _keys(value, ('format', 'run_id', 'attempt', 'result', 'exit', 'refusal', 'started_monotonic_ns',
                  'ended_monotonic_ns', 'line', 'label'))
    _need(value['format'] == FORMAT_REPLAY_BUILD and _is_int(value['run_id'], 1))
    _need(_is_int(value['attempt'], 1, MAX_ATTEMPTS) and value['label'] == REPLAY_LABEL)
    result = value['result']
    _need(type(result) is str and result in REPLAY_BUILD_RESULTS)
    times = (value['started_monotonic_ns'], value['ended_monotonic_ns'])
    if result == 'NOT_BUILT_S14_DISAGREEMENT':      # the H0_MINUS_1 / FIRST read disagreed: nothing was run
        _need(times == (None, None) and value['exit'] is None and value['refusal'] is None and value['line'] is None)
        return
    _need(all(_is_int(item) for item in times) and times[0] <= times[1])
    _need(value['exit'] is None if result in ('TIMEOUT', 'SPAWN_FAILED') else _is_int(value['exit'], 0, 255))
    _need(value['exit'] != 0 if result == 'REFUSED' else value['exit'] in (None, 0))
    refusal = value['refusal']
    _need(type(refusal) is str and refusal in FIXTURE_REFUSALS if result == 'REFUSED' else refusal is None)
    if result == 'BUILT':
        _check_build_line(value['line'])
    else:
        _need(value['line'] is None)


def _check_replay_rows(rows):
    _need(type(rows) is list)
    final = False
    for index, row in enumerate(rows):
        _keys(row, ('n', 'read', 'started_monotonic_ns', 'started_realtime_ns', 'ended_monotonic_ns', 'exit', 'result',
                    'refusal', 'refusal_node', 'line'))
        _need(_is_int(row['n'], index, index) and type(row['read']) is str and row['read'] in REPLAY_READS)
        _need(not final)                            # the one FINAL row is the last
        final = row['read'] == 'FINAL'
        _need(all(_is_int(row[key]) for key in ('started_monotonic_ns', 'started_realtime_ns', 'ended_monotonic_ns')))
        _need(row['started_monotonic_ns'] <= row['ended_monotonic_ns'])
        result = row['result']
        _need(type(result) is str and result in REPLAY_RESULTS)
        _need(row['exit'] is None if result in ('TIMEOUT', 'SPAWN_FAILED') else _is_int(row['exit'], 0, 255))
        _need(row['exit'] != 0 if result == 'REFUSED' else row['exit'] in (None, 0))
        if result == 'REFUSED':
            _need(type(row['refusal']) is str and row['refusal'] in FIXTURE_REFUSALS)
            _need(row['refusal_node'] in (None, 'A', 'B'))
        else:
            _need(row['refusal'] is None and row['refusal_node'] is None)
        if result == 'FOLLOWED':
            _check_follow_line(row['line'])
        else:
            _need(row['line'] is None)


def _check_block_rows(rows):
    _need(type(rows) is list)
    interval = False
    for index, row in enumerate(rows):
        _keys(row, ('n', 'phase', 'height', 'hash', 'producer', 'tries', 'produced_monotonic_ns',
                    'produced_realtime_ns', 'seen_other_monotonic_ns', 'seen_other_realtime_ns'))
        _need(_is_int(row['n'], index, index) and type(row['phase']) is str and row['phase'] in ('PREMINE', 'INTERVAL'))
        interval = interval or row['phase'] == 'INTERVAL'
        # heights 1..h0 - 1 are the pre-mine's, and no pre-mine row follows a row of the observation
        _need(_is_int(row['height'], H0) if interval else _is_int(row['height'], 1, H0 - 1))
        _need((row['phase'] == 'INTERVAL') == interval)
        _need(_is_hash(row['hash']) and type(row['producer']) is str and row['producer'] in NODES)
        _need(_is_int(row['tries'], 1))
        _need(_is_int(row['produced_monotonic_ns']) and _is_int(row['produced_realtime_ns']))
        seen = (row['seen_other_monotonic_ns'], row['seen_other_realtime_ns'])
        _need(seen == (None, None) or all(_is_int(x) for x in seen))


def _check_critical_row(row, index):
    _keys(row, ('n', 'kind', 'read', 'height', 'hash_a', 'hash_b', 'agree', 'seq', 'node', 'monotonic_ns',
                'realtime_ns'))
    _need(_is_int(row['n'], index, index) and type(row['kind']) is str and type(row['read']) is str)
    if row['kind'] == 'FORK_POINT':
        _need(row['read'] == 'EVENT' and _is_int(row['seq']) and type(row['node']) is str and row['node'] in NODES)
    else:
        _need(row['kind'] in CRITICAL_KINDS and row['read'] in CRITICAL_READS)
        _need(row['seq'] is None and row['node'] is None)
    _need(_is_int(row['height']) and _is_hash(row['hash_a']) and _is_hash(row['hash_b']))
    # `agree` is the comparison itself, so a row cannot claim agreement over two different hashes
    _need(type(row['agree']) is bool and row['agree'] == (row['hash_a'] == row['hash_b']))
    _need(_is_int(row['monotonic_ns']) and _is_int(row['realtime_ns']))


def _check_critical_rows(rows):
    _need(type(rows) is list)
    for index, row in enumerate(rows):
        _check_critical_row(row, index)


def _check_sample(value, seq, prev_sha256):
    _keys(value, ('seq', 'prev_sha256', 'monotonic_ns', 'boottime_ns', 'realtime_ns', 'boot_id', 'sampler_pid',
                  'nodes'))
    _need(_is_int(value['seq'], seq, seq) and _is_hash(value['prev_sha256']) and value['prev_sha256'] == prev_sha256)
    _need(all(_is_int(value[key]) for key in ('monotonic_ns', 'boottime_ns', 'realtime_ns')))
    _need(type(value['boot_id']) is str and BOOT_ID.fullmatch(value['boot_id']) is not None)
    _need(_is_int(value['sampler_pid'], 1))
    _keys(value['nodes'], NODES)
    for key in NODES:
        node = value['nodes'][key]
        _keys(node, ('ok', 'pid', 'uptime', 'chain', 'blocks', 'bestblockhash', 'mediantime', 'signet_challenge',
                     'genesis_hash', 'connections', 'networkactive', 'mempool_size'))
        _need(type(node['ok']) is bool)
        if not node['ok']:
            _need(all(item is None for name, item in node.items() if name != 'ok'))
            continue
        _need(_is_int(node['pid'], 1) and all(_is_int(node[name]) for name in (
            'uptime', 'blocks', 'mediantime', 'connections', 'mempool_size')))
        _need(type(node['chain']) is str and CHAIN_NAME.fullmatch(node['chain']) is not None)
        _need(_is_hash(node['bestblockhash']) and _is_hash(node['genesis_hash']))
        _need(type(node['signet_challenge']) is str and CHALLENGE_HEX.fullmatch(node['signet_challenge']) is not None)
        _need(type(node['networkactive']) is bool)


def _check_samples(rows):
    _need(type(rows) is list)
    previous = ZERO_HASH
    for index, row in enumerate(rows):
        _check_sample(row, index, previous)
        previous = hashlib.sha256(canonical(row)).hexdigest()


def _check_scope_file(name):
    def check(value):
        _need(_same(value, _scope_value(name)))
    return check


_RECORD_CHECKS = {
    'declaration.json': _check_declaration, 'environment.json': _check_environment, 'marker.json': _check_marker,
    'checkpoint.json': _check_checkpoint, 'final.json': _check_final, 'components.json': _check_components,
    'blocks.jsonl': _check_block_rows, 'critical_heights.jsonl': _check_critical_rows,
    'samples.jsonl': _check_samples, 'replay_build.json': _check_replay_build, 'replay.jsonl': _check_replay_rows,
    'txs.jsonl': _check_scope_file('txs.jsonl'),
    'reserve_snapshots.jsonl': _check_scope_file('reserve_snapshots.jsonl'),
}


def validate_record(name: str, value) -> None:
    """Section 4's schema of one record. `name` is a member of MEMBERS, 'marker.json' or 'checkpoint.json';
    `value` is the parsed object, or the list of rows of blocks.jsonl, critical_heights.jsonl, replay.jsonl or
    samples.jsonl (the samples are also chained). RECORD_INVALID."""
    if name not in _RECORD_CHECKS:
        raise ValueError('record name')
    try:
        _plain(value)
        _RECORD_CHECKS[name](value)
    except (_Invalid, TypeError, ValueError):
        raise Refusal('RECORD_INVALID') from None


def validate_sample(value: dict, seq: int, prev_sha256: str) -> None:
    """One sample line's schema, its `seq` and its `prev_sha256` (the chain). RECORD_INVALID."""
    try:
        _plain(value)
        _check_sample(value, seq, prev_sha256)
    except (_Invalid, TypeError, ValueError):
        raise Refusal('RECORD_INVALID') from None


def _chain(raw) -> tuple[list[dict], list[str]]:
    """The samples of a whole samples.jsonl and each line's SHA-256: every line canonical, `seq` its index from 0,
    `prev_sha256` the hash of the line before it (64 zeros for line 0)."""
    samples, hashes, previous = [], [], ZERO_HASH
    for index, (text, value) in enumerate(_lines(raw)):
        _check_sample(value, index, previous)
        previous = hashlib.sha256(text).hexdigest()
        samples.append(value)
        hashes.append(previous)
    return samples, hashes


def read_samples(raw: bytes) -> list[dict]:
    """Every line of a samples.jsonl, validated and chained: a broken hash, a reordered, duplicated or missing
    `seq`, a line that is not canonical or a partial last line is RECORD_INVALID."""
    try:
        return _chain(raw)[0]
    except _Invalid:
        raise Refusal('RECORD_INVALID') from None


# ---------------------------------------------------------------------------------------------- files ----
def _read_file(path, limit):
    """The bytes of a regular file that is not a link, at most `limit` + 1 of them; None when absent.
    PATH_NOT_REGULAR for a link or anything that is not a regular file."""
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode):
        raise Refusal('PATH_NOT_REGULAR')
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0))
    except FileNotFoundError:
        return None
    except OSError:
        raise Refusal('PATH_NOT_REGULAR') from None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise Refusal('PATH_NOT_REGULAR')
        chunks, size = [], 0
        while size <= limit:
            chunk = os.read(fd, min(1 << 20, limit + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
    finally:
        os.close(fd)
    return b''.join(chunks)


def _write_new(path, raw: bytes) -> None:
    """A new file, never over another: OUTPUT_EXISTS for a regular file there, PATH_NOT_REGULAR for a link or
    anything else."""
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        info = None
    if info is not None:
        raise Refusal('OUTPUT_EXISTS' if stat.S_ISREG(info.st_mode) else 'PATH_NOT_REGULAR')
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    except FileExistsError:
        raise Refusal('OUTPUT_EXISTS') from None
    try:
        try:
            view = memoryview(raw)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        try:   # no partial output is left behind
            os.unlink(path)
        except OSError:
            pass
        raise


def read_declaration(path: Path) -> dict:
    """The declaration of section 4.1 from a file: DECLARATION_MISSING when absent, DECLARATION_INVALID when it is
    not one canonical line of that schema, PATH_NOT_REGULAR for a link."""
    raw = _read_file(path, SMALL_LIMIT)
    if raw is None:
        raise Refusal('DECLARATION_MISSING')
    try:
        value = _one_line(raw)
        _check_declaration(value)
    except _Invalid:
        raise Refusal('DECLARATION_INVALID') from None
    return value


# ------------------------------------------------------------------------------------ output and policy ----
def _closed(value, depth=0) -> bool:
    """A value an output line may hold: a closed code, an integer, a boolean, a hex digest, null, or a short
    list of them."""
    if value is None or type(value) in (bool, int):
        return True
    if type(value) is str:
        return OUTPUT_TEXT.fullmatch(value) is not None
    return type(value) in (list, tuple) and depth == 0 and len(value) <= 4096 and all(
        _closed(item, 1) for item in value)


def output_line(tool: str, command: str, result: str, exit_code: int, code: str | None = None, **keys) -> bytes:
    """The one stdout line of a command (section 3), with its newline. DONE carries the command's keys, exit 0 and
    no code; REFUSED a code of REFUSALS with that code's exit; INCONCLUSIVE one of the six causes with exit 2 and,
    for the report, `coverage`; INTERNAL is INTERNAL_ERROR with exit 4. Anything else is a ValueError: the line
    never holds input text."""
    if tool not in TOOL_NAMES or result not in RESULTS:
        raise ValueError('output line')
    if command is not None and (type(command) is not str or COMMAND_NAME.fullmatch(command) is None):
        raise ValueError('output line: command')
    if result == 'DONE':
        consistent = code is None and exit_code == EXIT_OK
    elif result == 'INTERNAL':
        consistent = code == 'INTERNAL_ERROR' and exit_code == EXIT_INTERNAL
    elif result == 'INCONCLUSIVE':
        consistent = type(code) is str and code in UNREADABLE_CAUSES and exit_code == EXIT_VALIDATION
    else:
        consistent = (type(code) is str and code in REFUSALS and code != 'INTERNAL_ERROR'
                      and exit_code == REFUSALS[code])
    if type(exit_code) is not int or not consistent:
        raise ValueError('output line: code and exit')
    value = {'command': command, 'exit': exit_code, 'result': result, 'tool': tool}
    if 'coverage' in keys and keys['coverage'] not in (COVERAGE_OK,) + COVERAGE_CODES:
        raise ValueError('output line: coverage')
    if result == 'DONE':
        if set(keys) & set(value) or 'code' in keys or not all(_closed(item) for item in keys.values()):
            raise ValueError('output line: keys')
        value.update(keys)
    else:
        # only the report's INCONCLUSIVE line carries a key besides its code: `coverage` (section 3)
        if set(keys) - ({'coverage'} if result == 'INCONCLUSIVE' else set()):
            raise ValueError('output line: keys on a line that is not DONE')
        value['code'] = code
        value.update(keys)
    return line(value)


def required_seconds(root: Path | None = None) -> int:
    """GOV072's continuous seconds, read from docs/policy/ACTIVE_VALIDATION_POLICY.json of `root` (this checkout
    when None): a regular file that is not a link, at most SMALL_LIMIT bytes, of SHA-256 POLICY_SHA256, strict
    UTF-8 JSON with no duplicate key, whose `signet` object is POLICY_SIGNET as canonical bytes. Returns that
    object's `continuous_seconds` as read. No Codex ledger module or file is read (CR-01). Hosted jobs only.
    POLICY_UNAVAILABLE."""
    root = TOOLS.parent if root is None else Path(root)
    try:
        raw = _read_file(root / POLICY_PATH, SMALL_LIMIT)
        _need(type(raw) is bytes and len(raw) <= SMALL_LIMIT)
        _need(hashlib.sha256(raw).hexdigest() == POLICY_SHA256)
        policy = _loose_json(raw)
        _need(type(policy) is dict and _same(policy.get('signet'), POLICY_SIGNET))
    except (Refusal, _Invalid, UnicodeDecodeError, ValueError, RecursionError, OSError):
        raise Refusal('POLICY_UNAVAILABLE') from None
    return policy['signet']['continuous_seconds']


def effective_constants(overrides: dict | None, required: int) -> dict:
    """The fourteen effective constants (section 2). `overrides` holds any of duration_seconds, sample_seconds,
    block_seconds and checkpoint_seconds (a None value is absent); `required` is required_seconds()'s value.
    OVERRIDE_RANGE when a value is outside its range or the formulas' bounds."""
    if type(required) is not int:
        raise ValueError('required')
    given = {name: value for name, value in (overrides or {}).items() if value is not None}
    if set(given) - set(OVERRIDE_BOUNDS):
        raise ValueError('override name')
    derived = _derive(given.get('duration_seconds', required), given.get('sample_seconds', SAMPLE_SECONDS),
                      given.get('block_seconds', BLOCK_SECONDS), given.get('checkpoint_seconds', CHECKPOINT_SECONDS))
    if derived is None:
        raise Refusal('OVERRIDE_RANGE')
    return derived


def registered_constants(required: int) -> dict:
    """The registration block's `constants`: the unscaled effective constants and the two node pins."""
    return dict(effective_constants(None, required), node_versions=dict(NODE_VERSIONS),
                bitcoind_sha256=dict(BITCOIND_SHA256))


def labels_for(mode: str, scaled: bool) -> list[str]:
    """The mode's label list, sorted; EXPLORATORY_SCALED is added for a scaled EXPLORATORY dispatch only."""
    if mode not in MODES or type(scaled) is not bool or (scaled and mode != 'EXPLORATORY'):
        raise ValueError('labels')
    return sorted(LABELS[mode] + ((SCALED_LABEL,) if scaled else ()))


# ----------------------------------------------------------------------------------------- continuity ----
def _good(sample, challenge, genesis_hash) -> bool:
    return all(node['ok'] and node['chain'] == 'signet' and node['signet_challenge'] == challenge
               and node['genesis_hash'] == genesis_hash for node in sample['nodes'].values())


def _break_kinds(sample, previous, good, constants, forks) -> list[str]:
    """The break kinds of section 5 that hold at `sample`, CLOCK_DRIFT and NO_LIVE_BLOCK apart, in BREAK_KINDS
    order."""
    kinds = []
    nodes = sample['nodes']
    if not all(nodes[key]['ok'] for key in NODES):
        kinds.append('FAILED_SAMPLE')
    elif not good:
        kinds.append('CONTEXT')
    if previous is None:
        return kinds
    mono = sample['monotonic_ns'] - previous['monotonic_ns']
    if mono > constants['gap_seconds'] * NS:
        kinds.append('SAMPLE_GAP')
    if abs((sample['realtime_ns'] - previous['realtime_ns']) - mono) > constants['clock_step_gap_seconds'] * NS:
        kinds.append('CLOCK_STEP')
    # the boot-time clock counts suspended time and the monotonic clock does not: the machine was suspended
    if (sample['boottime_ns'] - previous['boottime_ns']) - mono > constants['clock_step_record_seconds'] * NS:
        kinds.append('SUSPEND')
    both = [key for key in NODES if nodes[key]['ok'] and previous['nodes'][key]['ok']]
    if any(nodes[key]['uptime'] < previous['nodes'][key]['uptime'] for key in both):
        kinds.append('NODE_UPTIME')
    if any(nodes[key]['pid'] != previous['nodes'][key]['pid'] for key in both):
        kinds.append('NODE_PID')
    if any(nodes[key]['blocks'] < previous['nodes'][key]['blocks'] and (sample['seq'], key) not in forks
           for key in both):
        kinds.append('HEIGHT_DROP')
    if sample['boot_id'] != previous['boot_id']:
        kinds.append('BOOT_ID')
    if sample['sampler_pid'] != previous['sampler_pid'] or mono <= 0:
        kinds.append('SAMPLER_RESTART')
    return kinds


def intervals(samples: list[dict], fork_rows: list[dict], constants: dict, genesis_hash: str) -> dict:
    """Section 5 over the samples in `seq` order: the qualifying intervals, the breaks and the recorded clock
    steps. Every break restarts the count from zero: an interval is one maximal run of good samples with no break
    between them, a wall clock that stays within `clock_step_gap_seconds` of the monotonic clock as they stood at
    its first sample, and a block witness at most `live_window_seconds` apart; two intervals are never summed.
    `longest` is the longest interval (the earliest on a tie) and `current` the one holding the last sample (the
    stopping rule reads it); both are None when there is none. Lengths are nanoseconds of the monotonic clock."""
    challenge = constants['signet_challenge_hex']
    record_ns = constants['clock_step_record_seconds'] * NS
    step_gap_ns = constants['clock_step_gap_seconds'] * NS
    live_ns = constants['live_window_seconds'] * NS
    forks = {(row['seq'], row['node']) for row in fork_rows if row.get('kind', 'FORK_POINT') == 'FORK_POINT'}
    found, breaks, steps = [], [], []
    # current: [first sample, last sample, witness_ns, witness_height, the first sample's realtime - monotonic]
    current = previous = None

    def close(kind):
        first, last = current[0], current[1]
        found.append({'first_seq': first['seq'], 'last_seq': last['seq'],
                      'monotonic_ns': last['monotonic_ns'] - first['monotonic_ns'], 'ended_by': kind})

    def opened(sample):
        return [sample, sample, sample['monotonic_ns'], min(sample['nodes'][key]['blocks'] for key in NODES),
                sample['realtime_ns'] - sample['monotonic_ns']]

    for sample in samples:
        good = _good(sample, challenge, genesis_hash)
        kinds = _break_kinds(sample, previous, good, constants, forks)
        if previous is not None:
            step = abs((sample['realtime_ns'] - previous['realtime_ns'])
                       - (sample['monotonic_ns'] - previous['monotonic_ns']))
            if record_ns <= step <= step_gap_ns:
                steps.append({'seq': sample['seq'], 'step_ns': step})
        if kinds:
            breaks.extend({'seq': sample['seq'], 'kind': kind} for kind in kinds)
            if current is not None:
                close(kinds[0])
            current = opened(sample) if good else None
        elif current is None:
            current = opened(sample)
        elif abs(sample['realtime_ns'] - sample['monotonic_ns'] - current[4]) > step_gap_ns:
            # steps that each stay within the bound have added up since the interval's first sample
            breaks.append({'seq': sample['seq'], 'kind': 'CLOCK_DRIFT'})
            close('CLOCK_DRIFT')
            current = opened(sample)
        elif sample['monotonic_ns'] - current[2] > live_ns:
            breaks.append({'seq': sample['seq'], 'kind': 'NO_LIVE_BLOCK'})
            close('NO_LIVE_BLOCK')
            current = opened(sample)
        else:
            current[1] = sample
            a, b = sample['nodes']['a'], sample['nodes']['b']
            if a['bestblockhash'] == b['bestblockhash'] and min(a['blocks'], b['blocks']) > current[3]:
                current[2], current[3] = sample['monotonic_ns'], min(a['blocks'], b['blocks'])
        previous = sample
    last = None
    if current is not None:
        close(None)
        last = found[-1]
    longest = None
    for interval in found:
        if longest is None or interval['monotonic_ns'] > longest['monotonic_ns']:
            longest = interval
    return {'intervals': found, 'breaks': breaks, 'clock_steps': steps, 'longest': longest, 'current': last}


# ------------------------------------------------------------------------------------------------ S14 ----
def s14_table(rows: list[dict], h0: int, genesis_hash: str | None = None, blocks: list[dict] | None = None) -> dict:
    """Section 6 over every critical read: `disagreements` counts the rows with `agree` false; FAIL with one or
    more; PASS with none and exactly one FIRST and one FINAL read of GENESIS, H0_MINUS_1 and H0, each at its
    height, the FINAL read showing the block of the FIRST, (with `genesis_hash`, the environment's) every
    GENESIS read showing that hash, no fork point at or under `h0`, and (with `blocks`, the rows of
    blocks.jsonl) the H0 / FIRST read showing the block the producer recorded at `h0`; INCOMPLETE otherwise.
    `missing` lists `<kind>:<read>` for a read that is not there once, `<kind>:REPLACED` for a block both nodes
    agreed on at each read that is not the same block at both reads, `GENESIS:NOT_ENVIRONMENT`,
    `H0:NOT_PRODUCED_BLOCK` and `FORK_POINT:AT_OR_UNDER_H0`. A row whose two hashes differ is a disagreement
    (FAIL) and is not compared further. The row of section 8.1's `s14` without `challenge` and `not_covered`."""
    heights = dict(zip(CRITICAL_KINDS, (0, h0 - 1, h0)))
    disagreements = sum(1 for row in rows if not row['agree'])
    covered, missing = [], []
    for kind in CRITICAL_KINDS:
        entry = {'kind': kind, 'height': heights[kind]}
        single = {}
        for read in CRITICAL_READS:
            reads = [row for row in rows if row['kind'] == kind and row['read'] == read]
            entry[read.lower() + '_agree'] = all(row['agree'] for row in reads) if reads else None
            if len(reads) != 1 or reads[0]['height'] != heights[kind]:
                missing.append(f'{kind}:{read}')
            elif reads[0]['agree']:
                single[read] = reads[0]['hash_a']
        if len(single) == len(CRITICAL_READS) and single['FIRST'] != single['FINAL']:
            missing.append(f'{kind}:{S14_REPLACED}')    # the chain under a critical height was rewritten
        if kind == 'GENESIS' and genesis_hash is not None and any(
                row['agree'] and row['hash_a'] != genesis_hash for row in rows if row['kind'] == kind):
            missing.append(S14_NOT_ENVIRONMENT)
        # the block both nodes agreed on at H0 is the one the producer recorded there, exactly once
        if kind == 'H0' and blocks is not None and 'FIRST' in single and (
                [row['hash'] for row in blocks if row['height'] == h0] != [single['FIRST']]):
            missing.append(S14_H0_NOT_PRODUCED)
        covered.append(entry)
    forks = [{'height': row['height'], 'agree': row['agree'], 'seq': row['seq'], 'node': row['node']}
             for row in rows if row['kind'] == 'FORK_POINT']
    if any(row['height'] <= h0 for row in forks):      # a rewrite that reached a critical height never passes
        missing.append(S14_FORK_UNDER_H0)
    result = 'FAIL' if disagreements else 'INCOMPLETE' if missing else 'PASS'
    return {'result': result, 'reads': len(rows), 'disagreements': disagreements, 'covered': covered,
            'fork_points': forks, 'missing': missing, 'report_cutoffs': 'NONE_IN_RUN'}


# ------------------------------------------------------------------------------- registration and plan ----
def _git(root, *args):
    try:
        return subprocess.run(['git', '-C', str(root), *args], capture_output=True, timeout=GIT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise Refusal('GIT_UNAVAILABLE') from None


def _canonical_path(path) -> bool:
    """A canonical relative repository path: `a/b/c`, no leading `/` or `./`, no `.`, `..` or empty part, no
    backslash, colon or control character (XD-1 V3 section 8)."""
    return (type(path) is str and bool(path) and '\\' not in path and ':' not in path
            and all(' ' <= char <= '~' for char in path)
            and all(part not in ('', '.', '..') for part in path.split('/')))


def _registration_bytes(path: str, root) -> bytes:
    """The registration as merged on main: the blob `refs/remotes/origin/main:<path>`, at most 1 MiB."""
    name = f'refs/remotes/origin/main:{path}'
    kind = _git(root, 'cat-file', '-t', name)
    if kind.returncode != 0 or kind.stdout.strip() != b'blob':
        raise Refusal('REGISTRATION_NOT_ON_MAIN')
    size = _git(root, 'cat-file', '-s', name)
    if size.returncode != 0 or not size.stdout.strip().isdigit():
        raise Refusal('GIT_UNAVAILABLE')
    if int(size.stdout.strip()) > REGISTRATION_LIMIT:
        raise Refusal('REGISTRATION_SIZE')
    blob = _git(root, 'cat-file', 'blob', name)
    if blob.returncode != 0:
        raise Refusal('GIT_UNAVAILABLE')
    return blob.stdout


def check_registration(blob: bytes, sha256: str, head: str, required: int, root: Path | None = None,
                       pilot: bool = False) -> dict:
    """Section 10's registration block, in the order of plan checks 7 and 8: the bytes' SHA-256 is the input; the
    file holds PILOT_LABEL exactly when `pilot` (the TEST_ONLY pilot from an attempt tag, whose `label` is then that
    text: PILOT_REGISTRATION_LABEL; a registration that holds it is REGISTRATION_TEST_ONLY, so the pilot file never
    counts, XD-1 C2); the `p5002` block's key set is closed; its pinned commit is `head`; its `tool_sha256` names
    exactly REGISTERED_PATHS with the SHA-256 of each file of this checkout; its `constants` are
    registered_constants() and its `fixed_lines` the two lines of section 1. Returns the block. The file is UTF-8
    JSON with no duplicate key; its other keys are not read (they may hold any JSON), and the block itself holds no
    float."""
    root = TOOLS.parent if root is None else Path(root)
    if type(pilot) is not bool:
        raise ValueError('pilot')
    if type(blob) is not bytes or hashlib.sha256(blob).hexdigest() != sha256:
        raise Refusal('REGISTRATION_SHA256_MISMATCH')
    if (PILOT_LABEL.encode('ascii') in blob) != pilot:
        raise Refusal('PILOT_REGISTRATION_LABEL' if pilot else 'REGISTRATION_TEST_ONLY')
    try:
        value = _loose_json(blob)
        _need(type(value) is dict)
    except (_Invalid, UnicodeDecodeError, ValueError, RecursionError):
        raise Refusal('REGISTRATION_JSON') from None
    if pilot and value.get('label') != PILOT_LABEL:
        raise Refusal('PILOT_REGISTRATION_LABEL')
    block = value.get('p5002')
    try:
        _plain(block)
        _keys(block, ('pinned_commit', 'tool_sha256', 'constants', 'fixed_lines'))
        _need(_is_sha(block['pinned_commit']))
        _keys(block['tool_sha256'], REGISTERED_PATHS)
        _need(all(_is_hash(item) for item in block['tool_sha256'].values()))
        _need(type(block['constants']) is dict and type(block['fixed_lines']) is dict)
    except (_Invalid, TypeError, ValueError):
        raise Refusal('REGISTRATION_P5002') from None
    if block['pinned_commit'] != head:
        raise Refusal('NOT_THE_PINNED_COMMIT')
    files = {path: _read_file(root / path, REGISTERED_FILE_LIMIT) for path in REGISTERED_PATHS}
    if any(raw is None for raw in files.values()):       # every file is there before any hash is compared
        raise Refusal('REGISTERED_FILE_MISSING')
    if any(hashlib.sha256(raw).hexdigest() != block['tool_sha256'][path] for path, raw in files.items()):
        raise Refusal('TOOL_SHA256_MISMATCH')
    if not _same(block['constants'], registered_constants(required)):
        raise Refusal('REGISTRATION_CONSTANTS')
    if not _same(block['fixed_lines'], {'scope_b': SCOPE_B, 's14_not_covered': S14_NOT_COVERED}):
        raise Refusal('REGISTRATION_FIXED_LINES')
    return block


def _on_main(root, commit: str) -> None:
    """`commit` is on refs/remotes/origin/main's first-parent chain: MAIN_UNAVAILABLE, NOT_ON_MAIN."""
    if _git(root, 'rev-parse', '--verify', '--quiet', 'refs/remotes/origin/main').returncode != 0:
        raise Refusal('MAIN_UNAVAILABLE')
    chain = _git(root, 'rev-list', '--first-parent', 'refs/remotes/origin/main')
    if chain.returncode != 0:
        raise Refusal('MAIN_UNAVAILABLE')
    if commit.encode('ascii') not in chain.stdout.split():
        raise Refusal('NOT_ON_MAIN')


def plan(mode: str, attempt: int, expected_head: str, source_sha256: str, registration: str | None,
         registration_sha256: str | None, s04_run_id: int | None, overrides: dict | None, environ,
         root: Path | None = None, s04_dir: Path | None = None, binaries: dict | None = None) -> dict:
    """The plan checks of section 10 in their order (the first that fails refuses), then the declaration of
    section 4.1. `environ` is the job's environment (the GITHUB_* values); `root` the checkout; `s04_dir` the
    folder the step "Read the cited S04 run" saved its answers in (read only by a dispatch from an attempt tag);
    `binaries` the hosted build job's three SHA-256 values ({'archive_sha256', 'bitagi_sha256', 'fixture_sha256'};
    BINARIES_SHA256 when it is absent or malformed, with the inputs of check 2)."""
    root = TOOLS.parent if root is None else Path(root)
    # 1. the dispatch
    if environ.get('GITHUB_EVENT_NAME') != 'workflow_dispatch':
        raise Refusal('EVENT')
    if environ.get('GITHUB_RUN_ATTEMPT') != '1':
        raise Refusal('RERUN')
    run_id, head = environ.get('GITHUB_RUN_ID', ''), environ.get('GITHUB_SHA', '')
    if RUN_ID.fullmatch(run_id) is None or HEX40.fullmatch(head) is None:
        raise Refusal('GITHUB_IDS')
    if head != expected_head:
        raise Refusal('EXPECTED_HEAD')
    # 2. the inputs every mode has
    if not _is_mode(mode):
        raise Refusal('MODE')
    confirmatory = mode == 'CONFIRMATORY'
    if not _is_int(attempt, 1, MAX_ATTEMPTS if confirmatory else 1):
        raise Refusal('ATTEMPT_RANGE')
    if not _is_hash(source_sha256):
        raise Refusal('SOURCE_SHA256')
    try:
        _check_binaries(binaries)
    except _Invalid:
        raise Refusal('BINARIES_SHA256') from None
    required = required_seconds(root)
    given = {name: value for name, value in (overrides or {}).items() if value is not None}
    ref = environ.get('GITHUB_REF', '')
    tagged = ATTEMPT_TAG.fullmatch(ref) is not None     # a cited dispatch: plan checks 6 to 9 run
    if not confirmatory:
        # 3. EXPLORATORY: from main with no registration, or the TEST_ONLY pilot from an attempt tag; the scaling
        # rule either way
        if ref != MAIN_REF and not tagged:
            raise Refusal('REF')
        if not tagged:
            if registration is not None or registration_sha256 is not None or s04_run_id is not None:
                raise Refusal('EXPLORATORY_INPUTS')
        elif not (registration == PILOT_REGISTRATION and _is_hash(registration_sha256) and _is_int(s04_run_id, 1)):
            raise Refusal('PILOT_REGISTRATION')
        constants = effective_constants(given, required)
    else:
        # 4. CONFIRMATORY: the registered constants only; refused while a component or a plan check is not wired
        if given:
            raise Refusal('OVERRIDE_REFUSED')
        if NOT_WIRED:
            raise Refusal('COMPONENTS_NOT_WIRED')
        if PLAN_CHECKS_NOT_WIRED:
            raise Refusal('S04_CITATION_NOT_WIRED')
        # 5. the pinned attempt tag and the registration inputs
        if not tagged:
            raise Refusal('REF')
        if not (type(registration) is str and registration and _is_hash(registration_sha256)
                and _is_int(s04_run_id, 1)):
            raise Refusal('REGISTRATION_INPUTS')
        if not _canonical_path(registration):
            raise Refusal('REGISTRATION_PATH')
        if PurePosixPath(registration).parts[0] == 'tests':
            raise Refusal('REGISTRATION_TEST_ONLY')
        constants = effective_constants(None, required)
    citation = None
    if tagged:
        # 6. the head is on main's first-parent chain
        _on_main(root, head)
        # 7, 8. the registration as merged on main (the pilot's TEST_ONLY file for EXPLORATORY), this checkout
        check_registration(_registration_bytes(registration, root), registration_sha256, head, required, root,
                           pilot=not confirmatory)
        # 9. the S04 citation, from the files the read step saved
        if s04_dir is None:
            raise Refusal('S04_INPUT_MISSING')
        citation = s04_cite(Path(s04_dir), s04_run_id, head, root)
    scaled = bool(given)
    return {'format': FORMAT_DECLARATION, 'mode': mode, 'attempt': attempt, 'head_sha': head, 'ref': ref,
            'run_id': int(run_id), 'run_attempt': 1,
            'registration_sha256': registration_sha256 if confirmatory else None,
            's04_run_id': s04_run_id if tagged else None, 's04_citation': citation,
            'source_sha256': source_sha256, 'binaries': dict(binaries),
            'scaling': SCALINGS[1] if scaled else SCALINGS[0],
            'constants': constants, 'labels': labels_for(mode, scaled)}


def s04_citation(record_raw: bytes, run_id: int, run_attempt: int, run_head_sha: str, subject_oid) -> str | None:
    """The S04 citation rule (STEP-48), copied from `s04_derive`: the cited S04 record v2 is `PASS_CLASS_T`, it
    was judged by that main-push run attempt on that run's head commit, and every subject's object id in it equals
    the pinned commit's. `run_id`, `run_attempt` and `run_head_sha` are the cited run's, as the Actions API
    answered; `subject_oid(path)` gives the pinned commit's object id of a subject path (`git rev-parse
    <pinned>:<path>`), or None when it has none. No subject's bytes are read. Returns None when the citation holds,
    else the first failure, a label of S04_FAILURES (plan check 9 refuses with it)."""
    if not (_is_int(run_id, 1) and _is_int(run_attempt, 1, 999) and _is_sha(run_head_sha)):
        raise ValueError('cited run')
    try:
        record = _loose_json(record_raw)
    except (_Invalid, UnicodeDecodeError, ValueError, RecursionError):
        return 'S04_RECORD_JSON'
    if type(record) is not dict or record.get('schema') != S04_SCHEMA:
        return 'S04_RECORD_SCHEMA'
    if record.get('s04') != S04_PASS:
        return 'S04_NOT_PASS'
    if record.get('commit') != run_head_sha:
        return 'S04_RECORD_COMMIT'
    fields = record.get('run')
    if not (type(fields) is dict and fields.get('event') == 'push' and fields.get('ref') == MAIN_REF
            and fields.get('run_id') == str(run_id) and fields.get('run_attempt') == str(run_attempt)
            and fields.get('commit') == run_head_sha):
        return 'S04_RECORD_RUN'
    oids = record.get('subject_oids')
    if type(oids) is not dict or not 0 < len(oids) <= S04_MAX_SUBJECTS:
        return 'S04_RECORD_SCHEMA'
    for subject, oid in sorted(oids.items()):
        if not _is_sha(oid):
            return 'S04_RECORD_SCHEMA'
        if subject_oid(subject) != oid:
            return 'S04_SUBJECTS_CHANGED'
    return None


def _s04_saved(folder: Path, name: str, limit: int):
    """A file the read step saved in `folder`: at most `limit` + 1 of its bytes (a regular file that is not a link,
    PATH_NOT_REGULAR otherwise); None when it is absent."""
    try:
        return _read_file(folder / name, limit)
    except NotADirectoryError:
        return None


def _s04_answer(folder: Path, name: str):
    """A saved Actions API answer (`run.json`, `artifacts.json`, `jobs.json`): its JSON value, or None when it is
    not UTF-8 JSON with no duplicate key (the caller refuses with its own code). S04_INPUT_MISSING when it is absent
    or over FETCHED_LIMIT."""
    raw = _s04_saved(folder, name, FETCHED_LIMIT)
    if raw is None or len(raw) > FETCHED_LIMIT:
        raise Refusal('S04_INPUT_MISSING')
    try:
        return _loose_json(raw)
    except (_Invalid, UnicodeDecodeError, ValueError, RecursionError):
        return None


def s04_run(folder: Path, run_id: int, head: str, root: Path | None = None) -> dict:
    """Plan check 9, the cited run, from `run.json` (the Actions API's answer for `run_id`; ARDR's `s04_run`): its
    `id` is `run_id`, its `path` the rx02 workflow's, its `event` `push`, its `head_branch` `main`, `completed` with
    the conclusion `success`, its `run_attempt` 1..999, and its `head_sha` 40 hex on `head`'s first-parent history
    (ancestor or equal), so the record was judged on a commit the pinned commit descends from. Returns
    {'run_attempt', 'head_sha'}; each failure is its code (S04_RUN_ID ... S04_NOT_ON_PINNED_HISTORY)."""
    if not (_is_int(run_id, 1) and _is_sha(head)):
        raise ValueError('cited run')
    root = TOOLS.parent if root is None else Path(root)
    run = _s04_answer(Path(folder), 'run.json')
    run = run if type(run) is dict else {}
    if not _same(run.get('id'), run_id):
        raise Refusal('S04_RUN_ID')
    if run.get('path') != S04_WORKFLOW_PATH:
        raise Refusal('S04_RUN_WORKFLOW')
    if run.get('event') != 'push':
        raise Refusal('S04_RUN_EVENT')
    if run.get('head_branch') != 'main':
        raise Refusal('S04_RUN_BRANCH')
    if run.get('status') != 'completed' or run.get('conclusion') != 'success':
        raise Refusal('S04_RUN_NOT_SUCCESS')
    attempt = run.get('run_attempt')
    if not _is_int(attempt, 1, 999):
        raise Refusal('S04_RUN_ATTEMPT')
    cited = run.get('head_sha')
    if not _is_sha(cited):
        raise Refusal('S04_RUN_HEAD')
    chain = _git(root, 'rev-list', '--first-parent', head)
    if chain.returncode != 0:
        raise Refusal('GIT_UNAVAILABLE')
    if cited.encode('ascii') not in chain.stdout.split():
        raise Refusal('S04_NOT_ON_PINNED_HISTORY')
    return {'run_attempt': attempt, 'head_sha': cited}


def s04_artifact_id(folder: Path, run_id: int, run_attempt: int) -> int | None:
    """The cited run attempt's record artifact in `artifacts.json` (the run's listing filtered by the exact name
    `s04-record-v2-<run id>-<attempt>`; ARDR's `s04_artifact_id`): its id when it is listed once and not expired;
    None when it is not listed or has expired (the record job's log is read instead). A listing that is not one
    page of that name only, holds it twice or gives no positive integer id is S04_ARTIFACT_LISTING."""
    if not (_is_int(run_id, 1) and _is_int(run_attempt, 1, 999)):
        raise ValueError('cited run')
    name = f'{S04_ARTIFACT_PREFIX}{run_id}-{run_attempt}'
    listing = _s04_answer(Path(folder), 'artifacts.json')
    items = listing.get('artifacts') if type(listing) is dict else None
    if not (type(items) is list and _same(listing.get('total_count'), len(items)) and len(items) <= 1
            and all(type(item) is dict and item.get('name') == name for item in items)):
        raise Refusal('S04_ARTIFACT_LISTING')
    if not items or items[0].get('expired') is not False:
        return None
    if not _is_int(items[0].get('id'), 1):
        raise Refusal('S04_ARTIFACT_LISTING')
    return items[0]['id']


def s04_job_id(folder: Path, run_id: int, run_attempt: int) -> int:
    """The record job of the cited run attempt in `jobs.json` (that attempt's jobs listing, one page; ARDR's
    `s04_job_id` and `jobs_of`): every listed job is of that run attempt and named once, and S04_JOB_NAME is listed
    with a positive integer id. Anything else is S04_JOB_NOT_LISTED."""
    if not (_is_int(run_id, 1) and _is_int(run_attempt, 1, 999)):
        raise ValueError('cited run')
    listing = _s04_answer(Path(folder), 'jobs.json')
    jobs = listing.get('jobs') if type(listing) is dict else None
    if not (type(jobs) is list and _same(listing.get('total_count'), len(jobs)) and len(jobs) <= S04_LISTING_LIMIT
            and all(type(job) is dict and type(job.get('name')) is str and _same(job.get('run_id'), run_id)
                    and _same(job.get('run_attempt'), run_attempt) for job in jobs)
            and len({job['name'] for job in jobs}) == len(jobs)):
        raise Refusal('S04_JOB_NOT_LISTED')
    named = [job for job in jobs if job['name'] == S04_JOB_NAME]
    if not (named and _is_int(named[0].get('id'), 1)):
        raise Refusal('S04_JOB_NOT_LISTED')
    return named[0]['id']


def _s04_zip_record(raw: bytes) -> bytes:
    """The one member `s04_record_v2.json` of the record artifact's zip, at most S04_RECORD_LIMIT bytes (ARDR's
    `zip_single`); any other shape is S04_ARTIFACT_ZIP."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            if not (len(infos) == 1 and infos[0].filename == S04_MEMBER and infos[0].file_size <= S04_RECORD_LIMIT):
                raise Refusal('S04_ARTIFACT_ZIP')
            with archive.open(infos[0]) as member:
                blob = member.read(S04_RECORD_LIMIT + 1)
    except (zipfile.BadZipFile, zipfile.LargeZipFile, zlib.error, OSError, EOFError, NotImplementedError,
            RuntimeError, ValueError):
        raise Refusal('S04_ARTIFACT_ZIP') from None
    if len(blob) > S04_RECORD_LIMIT:
        raise Refusal('S04_ARTIFACT_ZIP')
    return blob


def _s04_log_record(blob: bytes) -> bytes:
    """The record bytes the record job printed (`cat` of the one-line record), checked against the `sha256sum`
    line the same step printed right after it (ARDR's `s04_record_from_log`): exactly one printed record line
    (S04_JOB_LOG_AMBIGUOUS for more; S04_RECORD_MISSING for none, or without that hash line)."""
    lines = [text[:-1] if text.endswith(b'\r') else text for text in blob.split(b'\n')]
    texts = [match.group(1) if match else None for match in map(S04_LOG_LINE.match, lines)]
    found = []
    for index, text in enumerate(texts):
        if text is None or not text.startswith(b'{'):
            continue
        try:
            value = _loose_json(text)
        except (_Invalid, UnicodeDecodeError, ValueError, RecursionError):
            continue
        if type(value) is dict and value.get('schema') == S04_SCHEMA:
            found.append(index)
    if len(found) > 1:
        raise Refusal('S04_JOB_LOG_AMBIGUOUS')
    if not found:
        raise Refusal('S04_RECORD_MISSING')
    raw = texts[found[0]] + b'\n'
    after = texts[found[0] + 1] if found[0] + 1 < len(texts) else None
    sha = S04_SHA_LINE.match(after) if after is not None else None
    if sha is None or sha.group(1).decode('ascii') != hashlib.sha256(raw).hexdigest():
        raise Refusal('S04_RECORD_MISSING')
    return raw


def _s04_record(folder: Path, run_id: int, run_attempt: int) -> tuple[bytes, str]:
    """The record's bytes and their source (ARDR's `s04_record_bytes`). The artifact wins: when it is listed and
    not expired its zip is the record and the log is not read (a zip that was not saved is S04_RECORD_MISSING,
    never a fallback). Only an artifact that is not listed or has expired falls back to the record job's log."""
    if s04_artifact_id(folder, run_id, run_attempt) is not None:
        raw = _s04_saved(folder, 'record.zip', S04_RECORD_LIMIT)
        if raw is None:
            raise Refusal('S04_RECORD_MISSING')
        if len(raw) > S04_RECORD_LIMIT:
            raise Refusal('S04_ARTIFACT_ZIP')
        return _s04_zip_record(raw), S04_SOURCES[0]
    s04_job_id(folder, run_id, run_attempt)
    blob = _s04_saved(folder, 'job.log', S04_LOG_LIMIT)
    if blob is None or len(blob) > S04_LOG_LIMIT:
        raise Refusal('S04_RECORD_MISSING')
    return _s04_log_record(blob), S04_SOURCES[1]


def s04_cite(folder: Path, run_id: int, head: str, root: Path | None = None) -> dict:
    """Plan check 9 from the files the step "Read the cited S04 run" saved in `folder` (no request is made here;
    ARDR's `s04_derive`): the cited run (s04_run), its record (the artifact, else the record job's log), and
    s04_citation() of that record with each subject's object id at `head` (`git rev-parse --verify --quiet
    <head>:<path>`; no subject's bytes are read). Each failure refuses with its code. Returns the declaration's
    `s04_citation`: {'record_sha256', 'record_source', 's04_run_attempt', 's04_head_sha', 'subjects'}."""
    root = TOOLS.parent if root is None else Path(root)
    folder = Path(folder)
    run = s04_run(folder, run_id, head, root)
    raw, source = _s04_record(folder, run_id, run['run_attempt'])

    def subject_oid(path):
        if type(path) is not str or not path or '\0' in path:
            return None
        done = _git(root, 'rev-parse', '--verify', '--quiet', f'{head}:{path}')
        return done.stdout.decode('ascii', 'replace').strip() if done.returncode == 0 else None

    failure = s04_citation(raw, run_id, run['run_attempt'], run['head_sha'], subject_oid)
    if failure is not None:
        raise Refusal(failure)
    return {'record_sha256': hashlib.sha256(raw).hexdigest(), 'record_source': source,
            's04_run_attempt': run['run_attempt'], 's04_head_sha': run['head_sha'],
            'subjects': len(_loose_json(raw)['subject_oids'])}


def pilot_registration(commit: str, required: int, root: Path | None = None) -> dict:
    """The TEST_ONLY pilot registration for PILOT_REGISTRATION (section 10): PILOT_LABEL, PILOT_NOTE and a `p5002`
    block whose pinned commit is `commit` (on main's first-parent chain: MAIN_UNAVAILABLE, NOT_ON_MAIN), whose
    `tool_sha256` is the SHA-256 of each REGISTERED_PATHS file at that commit (REGISTERED_FILE_MISSING), and whose
    `constants` and `fixed_lines` are the ones plan check 8 compares. A commits it on main after `commit`, tags
    `commit` and dispatches the EXPLORATORY pilot from that tag. It is never a registration: a CONFIRMATORY plan
    refuses it by its path and by its label. PILOT_REGISTRATION for a `commit` that is not 40 hex."""
    root = TOOLS.parent if root is None else Path(root)
    if not _is_sha(commit):
        raise Refusal('PILOT_REGISTRATION')
    _on_main(root, commit)
    tools = {}
    for path in REGISTERED_PATHS:
        name = f'{commit}:{path}'
        kind = _git(root, 'cat-file', '-t', name)
        if kind.returncode != 0 or kind.stdout.strip() != b'blob':
            raise Refusal('REGISTERED_FILE_MISSING')
        blob = _git(root, 'cat-file', 'blob', name)
        if blob.returncode != 0:
            raise Refusal('GIT_UNAVAILABLE')
        tools[path] = hashlib.sha256(blob.stdout).hexdigest()
    return {'label': PILOT_LABEL, 'note': PILOT_NOTE,
            'p5002': {'pinned_commit': commit, 'tool_sha256': tools, 'constants': registered_constants(required),
                      'fixed_lines': {'scope_b': SCOPE_B, 's14_not_covered': S14_NOT_COVERED}}}


# ------------------------------------------------------------------------------------ record builders ----
def marker(declaration: dict, head_sha256: str, monotonic_ns: int, realtime_ns: int) -> dict:
    """marker.json's value (anchor 0): the declaration's binding and the chain head after sample 0."""
    value = {'format': FORMAT_MARKER, 'seq': 0, 'head_sha256': head_sha256, 'monotonic_ns': monotonic_ns,
             'realtime_ns': realtime_ns}
    value.update((key, declaration[key]) for key in ('mode', 'attempt', 'head_sha', 'run_id', 'run_attempt',
                                                     'registration_sha256'))
    validate_record('marker.json', value)
    return value


def components() -> dict:
    """components.json's value: each component WIRED, or NOT_WIRED_PENDING_UNIT while NOT_WIRED lists it."""
    return {'format': FORMAT_COMPONENTS,
            'components': {name: NOT_WIRED_STATE if name in NOT_WIRED else WIRED_STATE for name in COMPONENTS}}


def _scope_value(name: str) -> dict:
    if name not in SCOPE_FIELDS:
        raise ValueError('scope file')
    return {'fields': list(SCOPE_FIELDS[name]), 'file': name, 'format': FORMAT_SCOPE_FILE, 'rows': 0,
            'state': SCOPE_STATE}


def scope_file(name: str) -> bytes:
    """The one line of txs.jsonl or reserve_snapshots.jsonl: zero rows, NOT_APPLICABLE_SCOPE_B."""
    return line(_scope_value(name))


def disagreement(run_id: int, attempt: int, row: dict) -> dict:
    """An incidents/ file's value for one critical read whose `agree` is false."""
    try:
        _plain(row)
        _check_critical_row(row, row.get('n') if type(row) is dict else None)
        _need(row['agree'] is False and _is_int(run_id, 1) and _is_int(attempt, 1, MAX_ATTEMPTS))
    except (_Invalid, TypeError):
        raise ValueError('disagreement') from None
    return {'format': FORMAT_DISAGREEMENT, 'run_id': run_id, 'attempt': attempt, 'row': dict(row),
            'effect': 'BROADCAST_LOCK_NO_GO'}


# --------------------------------------------------------------------------------- the two components ----
def fixture_line(raw: bytes, mode: str) -> dict | None:
    """The fixture's summary on stdout for `mode` (`BUILD` or `FOLLOW`): exactly one LF-ended line of strict UTF-8
    JSON (no duplicate key, no float) holding an object with exactly that mode's keys (BUILD_KEYS, FOLLOW_KEYS),
    each of its type, and the fixed values (`fixture`, `mode`, `network`, `node_settings_verification`; FOLLOW also
    `replay_kind` and `replay_label`). None for anything else (the driver's OUTPUT_INVALID). A BUILD object keeps
    its `store_path` here; the driver checks it and leaves it out of the record."""
    if mode not in ('BUILD', 'FOLLOW'):
        raise ValueError('fixture mode')
    if type(raw) is not bytes or len(raw) > FIXTURE_OUTPUT_LIMIT or not raw.endswith(b'\n') or raw.count(b'\n') != 1:
        return None
    try:
        value = json.loads(raw[:-1].decode('utf-8'), object_pairs_hook=_no_duplicates, parse_float=_no_number,
                           parse_constant=_no_number)
        _plain(value)
        fixed = {'fixture': FIXTURE_NAME, 'mode': mode, 'network': FIXTURE_NETWORK,
                 'node_settings_verification': FIXTURE_UNVERIFIED}
        if mode == 'BUILD':
            _keys(value, BUILD_KEYS)
            _need(type(value['store_path']) is str and 1 <= len(value['store_path']) <= 4096)
            _check_build_line({key: item for key, item in value.items() if key != 'store_path'})
        else:
            _check_follow_line(value)
            fixed.update(replay_kind=FIXTURE_REPLAY_KIND, replay_label=FIXTURE_REPLAY_LABEL)
        _need(all(value[key] == item for key, item in fixed.items()))
    except (_Invalid, UnicodeDecodeError, ValueError, RecursionError, TypeError):
        return None
    return value


def fixture_refusal(raw: bytes) -> tuple[str, str | None]:
    """(the code, the node `A` or `B` or None) of the fixture's one stderr line: a code of FIXTURE_REFUSALS, or
    OTHER for any other text (an RpcSession error has no code). Nothing of the text is returned."""
    match = FIXTURE_STDERR.fullmatch(raw) if type(raw) is bytes and len(raw) <= FIXTURE_OUTPUT_LIMIT else None
    if match is None:
        return 'OTHER', None
    code = match.group(2).decode('ascii')
    node = None if match.group(1) is None else match.group(1).decode('ascii')
    return (code if code in FIXTURE_REFUSALS[:-1] else 'OTHER'), node


def monitor_request(genesis_hash: str, signet_challenge_hex: str, deployment_id_internal: str, h0: int) -> dict:
    """monitor/request.json's value: the tick request template the monitor loop is given (-2c-1's
    BITAGI_CT_MONITOR_TICK_REQUEST_V1 in its P5-002 shape: both nodes on their RPC ports, no store, no Heart, the
    critical heights 0, h0 - 1 and h0; `mono_ns` 0, which the loop replaces at each tick)."""
    if not (_is_hash(genesis_hash) and type(signet_challenge_hex) is str
            and CHALLENGE_HEX.fullmatch(signet_challenge_hex) and _is_hash(deployment_id_internal)
            and _is_int(h0, 2)):
        raise ValueError('monitor request')
    return {'schema': MONITOR_REQUEST_SCHEMA, 'context_mode': MONITOR_CONTEXT_MODE,
            'substrate': {'network': FIXTURE_NETWORK, 'genesis_hash_display': genesis_hash,
                          'signet_challenge_hex': signet_challenge_hex},
            'deployment_id_internal': deployment_id_internal, 'store_path': None,
            'loopback_ports': [PORTS[key]['rpc'] for key in NODES], 'heart_ref': None,
            'first_effective_height': h0, 'critical_heights': [0, h0 - 1, h0], 'mono_ns': 0}


def replay_check(build: dict, rows: list[dict], blocks: list[dict], critical: list[dict], genesis_hash: str,
                 constants: dict, window: tuple[int, int] | None) -> dict:
    """The replay's component check (section 8.1): `result` PASS or FAIL with the codes of REPLAY_CHECKS that fail,
    in that order, or NOT_JUDGED when the store was not built because the H0_MINUS_1 / FIRST read disagreed (S14 is
    FAIL then). `build` is replay_build.json, `rows` replay.jsonl's rows, `blocks` and `critical` the rows of
    blocks.jsonl and critical_heights.jsonl, `window` the longest interval's first and last sample `monotonic_ns`
    (None: REPLAY_LAG is not judged). Reported, not judged: the count of each result, REORGANIZED follows and
    re-anchored floors (A's decision 8)."""
    followed = [row for row in rows if row['result'] == 'FOLLOWED']
    finals = [row for row in rows if row['read'] == 'FINAL']
    value = {'build': build['result'], 'rows': len(rows),
             'results': {result: sum(1 for row in rows if row['result'] == result) for result in REPLAY_RESULTS},
             'reorganized': sum(1 for row in followed if row['line']['sync_kind'] == 'REORGANIZED'),
             'reanchored': sum(1 for row in followed if row['line']['replay_floor_reanchored']),
             'final_height': finals[0]['line']['final_height'] if finals and finals[0]['line'] else None}
    if build['result'] == 'NOT_BUILT_S14_DISAGREEMENT':
        return dict(value, result=CHECK_RESULTS[2], failed=[])
    failed = set()
    h0, line = constants['h0'], build['line']
    floor = [row for row in critical if row['kind'] == 'H0_MINUS_1' and row['read'] == 'FIRST']
    if build['result'] != 'BUILT' or not (
            len(floor) == 1 and floor[0]['agree'] and line['fixture'] == FIXTURE_NAME and line['mode'] == 'BUILD'
            and line['network'] == FIXTURE_NETWORK and line['node_settings_verification'] == FIXTURE_UNVERIFIED
            and line['genesis_hash_display'] == genesis_hash
            and line['signet_challenge_hex'] == constants['signet_challenge_hex']
            and line['first_effective_height'] == h0 and line['as_of_height'] == h0 - 1
            and line['as_of_block_hash_display'] == floor[0]['hash_a']):
        failed.add('REPLAY_BUILD')
    fixed = {'fixture': FIXTURE_NAME, 'mode': 'FOLLOW', 'replay_kind': FIXTURE_REPLAY_KIND,
             'replay_label': FIXTURE_REPLAY_LABEL, 'network': FIXTURE_NETWORK,
             'node_settings_verification': FIXTURE_UNVERIFIED}
    if any(row['line'][key] != item for row in followed for key, item in fixed.items()):
        failed.add('REPLAY_LABEL')
    if any(line is None or row['line'][key] != line[key] for row in followed
           for key in ('substrate_context_hash', 'deployment_id_internal')):
        failed.add('REPLAY_CONTEXT')
    live_ns = constants['live_window_seconds'] * NS
    if window is not None:
        first, last = window
        for block in blocks:
            seen = block['seen_other_monotonic_ns']
            # a block seen on both nodes inside the interval, more than the live window before its last sample
            if block['phase'] != 'INTERVAL' or seen is None or seen < first or last - seen <= live_ns:
                continue
            if not any(row['ended_monotonic_ns'] - seen <= live_ns and row['line']['final_height'] >= block['height']
                       for row in followed):
                failed.add('REPLAY_LAG')
                break
    if blocks and blocks[-1]['seen_other_monotonic_ns'] is not None:
        last_block = blocks[-1]
        if not (len(finals) == 1 and finals[0]['result'] == 'FOLLOWED'
                and finals[0]['line']['final_height'] == last_block['height']
                and finals[0]['line']['final_hash_display'] == last_block['hash']):
            failed.add('REPLAY_FINAL')
    digests = {}
    for row in followed:
        if digests.setdefault(row['line']['final_hash_display'], row['line']['final_state_digest']) != (
                row['line']['final_state_digest']):
            failed.add('REPLAY_CONSISTENT')
    return dict(value, result=CHECK_RESULTS[1] if failed else CHECK_RESULTS[0],
                failed=[code for code in REPLAY_CHECKS if code in failed])


def _monitor_tool():
    """tools/claude_track_monitor.py, imported only when a monitor log is read (its own check_log is the reading
    rule; the VPS tree holds the tool because the driver runs it)."""
    import claude_track_monitor
    return claude_track_monitor


def monitor_check(log_raw: bytes | None, request_raw: bytes | None, final: dict, declaration: dict,
                  environment: dict, build: dict, critical: list[dict], window: tuple[int, int] | None) -> dict:
    """The monitor's component check (section 8.1): `result` PASS or FAIL with the codes of MONITOR_CHECKS that fail,
    in that order (a log that is not COPIED or not a valid MONITOR_LOG_V1 log fails MONITOR_LOG and nothing else is
    read), or NOT_JUDGED when the store was not built (no monitor was started: its request needs the build's
    deployment id). `log_raw` and `request_raw` are the bytes of monitor/monitor.jsonl and monitor/request.json (None
    when absent); `window` as replay_check()'s (None: MONITOR_SPAN is not judged). `unequal` counts the
    CRITICAL_HEIGHT lines whose `equal` is not true: attempt_row() adds them to S14's disagreements (A's decision
    4). The rest is reported, not judged."""
    value = dict.fromkeys(('lines', 'ticks', 'checked_ticks', 'failed_ticks', 'alarm_starts', 'gaps_at_seq',
                           'suspends_at_seq', 'clock_steps_at_seq', 'open_alarms', 'unequal'))
    if build['result'] == 'NOT_BUILT_S14_DISAGREEMENT':
        return dict(value, result=CHECK_RESULTS[2], failed=[])
    tool = _monitor_tool()
    summary = tool.check_log(log_raw) if type(log_raw) is bytes and len(log_raw) <= LINES_LIMIT else None
    if final['monitor']['log'] != 'COPIED' or summary is None or not summary['valid']:
        return dict(value, result=CHECK_RESULTS[1], failed=['MONITOR_LOG'])
    rows = [tool.loads(text) for text in log_raw.split(b'\n')[:-1]]      # check_log read each of them
    failed = set()
    start, stop = rows[0], rows[-1]
    if stop['kind'] != 'STOP' or stop.get('reason') != 'SIGNAL_SIGTERM' or not _same(stop.get('exit'), 0):
        failed.add('MONITOR_STOP')
    try:
        tool_sha256 = hashlib.sha256((TOOLS / Path(MONITOR_TOOL).name).read_bytes()).hexdigest()
    except OSError:
        tool_sha256 = None
    started = {'format': MONITOR_LOG_FORMAT, 'tool_sha256': tool_sha256,
               'bitagi_sha256': declaration['binaries']['bitagi_sha256'], **MONITOR_PATHS,
               'poll_s': MONITOR_POLL_SECONDS, 'tick_timeout_s': MONITOR_TICK_TIMEOUT_SECONDS, 'max_ticks': None,
               'ack_input': None, 'mark_input': None}
    if tool_sha256 is None or any(not _same(start.get(key), item) for key, item in started.items()):
        failed.add('MONITOR_START')
    h0 = declaration['constants']['h0']
    request = None
    if build['result'] == 'BUILT':
        request = line(monitor_request(environment['genesis_hash'], declaration['constants']['signet_challenge_hex'],
                                       build['line']['deployment_id_internal'], h0))
    if (request is None or request_raw != request
            or not _same(start.get('request_sha256'), hashlib.sha256(request).hexdigest())):
        failed.add('MONITOR_REQUEST')
    ticks = [row for row in rows if row['kind'] == 'TICK']
    checked = [row for row in ticks if row.get('tick_error') is None and type(row.get('tick')) is dict]
    if window is not None:
        first, last = window
        points = [first, *(row['mono_ns'] for row in checked if first <= row['mono_ns'] <= last), last]
        if any(later - earlier > MONITOR_SPAN_SECONDS * NS for earlier, later in zip(points, points[1:])):
            failed.add('MONITOR_SPAN')

    def alarm_ids(row):
        alarms = row['tick'].get('alarms')
        if type(alarms) is not list or not all(type(item) is dict and type(item.get('id')) is str for item in alarms):
            return None
        return sorted(item['id'] for item in alarms)

    if not checked or any(alarm_ids(row) != sorted(MONITOR_ALARMS) for row in checked):
        failed.add('MONITOR_ALARM_OUTPUT')
    if not checked or any(type(row.get('countdown_status')) is not str
                          or row['countdown_status'] not in MONITOR_COUNTDOWNS for row in checked):
        failed.add('MONITOR_COUNTDOWN_OUTPUT')
    marks = [row for row in rows if row['kind'] == 'CRITICAL_HEIGHT']
    heights = dict(zip(CRITICAL_KINDS, (0, h0 - 1, h0)))
    for kind, height in heights.items():
        reads = [row for row in critical if row['kind'] == kind and row['read'] == 'FIRST']
        found = [row for row in marks if _same(row.get('height'), height)]
        if len(reads) != 1 or len(found) != 1 or found[0].get('hash_a_display') != reads[0]['hash_a']:
            failed.add('MONITOR_CRITICAL_HEIGHTS')
    if len(marks) != len(heights):
        failed.add('MONITOR_CRITICAL_HEIGHTS')
    starts = {}
    for item in summary['alarm_starts']:
        if type(item.get('alarm_id')) is str:
            starts[item['alarm_id']] = starts.get(item['alarm_id'], 0) + 1
    value.update(lines=summary['lines'], ticks=len(ticks), checked_ticks=len(checked),
                 failed_ticks=len(ticks) - len(checked), alarm_starts=starts,
                 gaps_at_seq=summary['gaps_at_seq'][:LIST_CUT], suspends_at_seq=summary['suspends_at_seq'][:LIST_CUT],
                 clock_steps_at_seq=summary['clock_steps_at_seq'][:LIST_CUT],
                 open_alarms=len(stop['open_alarms']) if stop['kind'] == 'STOP' and type(
                     stop.get('open_alarms')) is list else None,
                 unequal=sum(1 for row in marks if row.get('equal') is not True))
    return dict(value, result=CHECK_RESULTS[1] if failed else CHECK_RESULTS[0],
                failed=[code for code in MONITOR_CHECKS if code in failed])


# ---------------------------------------------------------------------------------------- attempt row ----
def _label_pairs(pairs):
    if [key for key, _ in pairs].count('labels') > 1:
        raise ValueError('ambiguous labels')
    return dict(pairs)


def _labels_of(raw):
    """A record's `labels`, read leniently (as XD-1 reads them), so a record that fails its schema for another
    reason still has its labels checked; None when they cannot be read."""
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_label_pairs)
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None
    labels = value.get('labels') if type(value) is dict else None
    if type(labels) is not list or not all(type(label) is str for label in labels):
        return None
    return labels


def _anchor(entry, name):
    """(the anchor file's value, its artifact's created_at) of one `server['anchors']` entry; None when the entry,
    its time or its file is not valid."""
    if type(entry) not in (tuple, list) or len(entry) != 2:
        return None
    raw, created = entry
    if not _is_int(created, 1, TIME_MAX):
        return None
    try:
        value = _one_line(raw)
        _RECORD_CHECKS[name](value)
    except _Invalid:
        return None
    return value, created


def _utc(seconds: int) -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(seconds))


def _server_anchors(server, declaration, samples, hashes, longest) -> tuple[dict, int | None]:
    """Section 7: the rules SA1..SA7 over the marker and checkpoint artifacts' server times. Returns the row's
    `anchors` and the largest value SA7's part 4 compared with its bound (None when it compared none)."""
    constants = declaration['constants']
    count, slack = constants['checkpoints'], constants['anchor_slack_seconds']
    tie = constants['gap_seconds'] + slack      # SA7: how far a committed sample may lie from its anchor
    given = server['anchors']
    valid = {}
    for k in range(count + 1):
        got = _anchor(given.get(k), 'marker.json' if k == 0 else 'checkpoint.json')
        if got is not None:
            valid[k] = got
    failed = set()
    if set(given) != set(range(count + 1)) or len(valid) != count + 1:
        failed.add('SA5_ALL_PRESENT')
    if 0 not in valid or server['job_started_at'] > valid[0][1]:
        failed.add('SA1_JOB_ORDER')
    previous_seq = None
    committed = {}      # k: the sample anchor k commits, when its `seq` is a line of the final samples.jsonl
    for k in sorted(valid):
        value, created = valid[k]
        if abs(value['realtime_ns'] // NS - created) > slack:
            failed.add('SA2_CLOCK_TIE')
        seq = value['seq']
        if seq < len(samples):                  # a `seq` that is no line of the file is SA3's
            sample = committed[k] = samples[seq]
            if k == 0 or value['daemon_state'] == 'RUNNING':
                # SA7: a running sampler's anchor commits a sample taken shortly before it, on both clocks
                if not (0 <= value['monotonic_ns'] - sample['monotonic_ns'] <= tie * NS
                        and abs(value['realtime_ns'] - sample['realtime_ns']) <= tie * NS):
                    failed.add('SA7_SAMPLE_TIE')
            elif seq != len(samples) - 1:
                failed.add('SA7_SAMPLE_TIE')    # an ended daemon's anchor commits the last sample
        if not (seq < len(hashes) and hashes[seq] == value['head_sha256']):
            failed.add('SA3_PREFIX')
        if previous_seq is not None and seq < previous_seq:
            failed.add('SA3_PREFIX')
        previous_seq = seq
        if (value['run_id'], value['attempt']) != (declaration['run_id'], declaration['attempt']) or (
                k > 0 and value['index'] != k):
            failed.add('SA3_PREFIX')
        if k - 1 in valid and not 0 <= created - valid[k - 1][1] <= constants['checkpoint_seconds'] + slack:
            failed.add('SA4_SPACING')    # late, or uploaded before the anchor it follows
    # SA7: sample 0 was taken inside the observe job, at or before the marker (no inherited or backdated chain)
    first_second = samples[0]['realtime_ns'] // NS if samples else None
    if first_second is None or first_second < server['job_started_at'] - slack or (
            0 in valid and first_second > valid[0][1] + slack):
        failed.add('SA7_SAMPLE_TIE')
    span = skew = None
    if longest is not None:
        before = [k for k in sorted(valid) if valid[k][0]['seq'] <= longest['first_seq']]
        after = [k for k in sorted(valid) if valid[k][0]['seq'] >= longest['last_seq']]
        if before and after:
            a, b = before[-1], after[0]
            span = valid[b][1] - valid[a][1]
            # SA7: between the anchors that bracket the longest interval, the committed samples' monotonic
            # clock follows server time (SA6 alone bounds the interval from above only)
            for k in sorted(valid):
                if a < k <= b and a in committed and k in committed:
                    apart = abs((committed[k]['monotonic_ns'] - committed[a]['monotonic_ns']) // NS
                                - (valid[k][1] - valid[a][1]))
                    skew = apart if skew is None else max(skew, apart)
                    if apart > tie:
                        failed.add('SA7_SAMPLE_TIE')
    if span is None or span < constants['required_seconds']:
        failed.add('SA6_SPAN')
    anchors = {'result': 'FAIL' if failed else 'PASS', 'failed': [rule for rule in ANCHOR_RULES if rule in failed],
               'server_span_seconds': span, 'present': sorted(k for k in given if type(k) is int)}
    return anchors, skew


def _blocks_summary(rows, h0) -> dict:
    premine = [row for row in rows if row['phase'] == 'PREMINE']
    interval = [row for row in rows if row['phase'] == 'INTERVAL']
    ordered = ([row['height'] for row in premine] == list(range(1, h0))
               and all(row['producer'] == NODES[(row['height'] - 1) // PREMINE_CHUNK % 2] for row in premine)
               and all(row['height'] == h0 + n and row['producer'] == NODES[n % 2] for n, row in enumerate(interval)))
    return {'premine': len(premine), 'interval': len(interval),
            'first_height': rows[0]['height'] if rows else None, 'last_height': rows[-1]['height'] if rows else None,
            'alternation_ok': ordered}


def _listing_values(row: dict, listed, server) -> dict:
    """The row with the dispatch's listing values and the observe job's server start (null for a local read)."""
    if listed is not None:
        created, runners = listed['created_at'], listed['runner_labels']
        if not (type(created) is str and UTC.fullmatch(created) is not None and type(runners) in (list, tuple)
                and all(_is_text(label, 1, 128) for label in runners)):
            raise ValueError('listed')
        row.update(created_at=created, runner_labels=sorted(runners))
    if server is not None:
        row.update(started_at=_utc(server['job_started_at']), start_time_utc=server['job_started_at'])
    return row


def _lost_row(declaration: dict, listed, server: dict) -> dict:
    """Section 8.1's LOST row: a counted attempt whose declaration and marker are valid and whose records are
    missing, expired or invalid. S13 is FAIL (RECORDS_LOST) and S14 is UNKNOWN; `checkpoint_s14_disagreements` is
    the largest `s14_disagreements` over its valid checkpoint files (`checkpoints_read` names them; None when it
    has none). An attempt with no observe job start, or a CONFIRMATORY one while a component is not wired, stays
    unreadable."""
    if not _is_int(server.get('job_started_at'), 1, TIME_MAX):
        raise Unreadable('COMPLETENESS_REFUSED')
    if declaration['mode'] == 'CONFIRMATORY' and NOT_WIRED:
        raise Unreadable('COMPONENTS_NOT_WIRED')
    counts = {}
    for k, entry in server['anchors'].items():
        got = _anchor(entry, 'checkpoint.json') if _is_int(k, 1, MAX_CHECKPOINTS) else None
        if got is not None:
            counts[k] = got[0]['s14_disagreements']
    row = {'attempt': declaration['attempt'], 'run_id': declaration['run_id'],
           'run_attempt': declaration['run_attempt'], 'created_at': None, 'started_at': None,
           'start_time_utc': None, 'runner_labels': None, 'state': ATTEMPT_STATES[1],
           'scaling': declaration['scaling'],
           's13': {'result': 'FAIL', 'reason': LOST_REASON,
                   'required_seconds': declaration['constants']['required_seconds']},
           's14': {'result': LOST_S14}, 'checkpoints_read': sorted(counts),
           'checkpoint_s14_disagreements': max(counts.values()) if counts else None}
    return _listing_values(row, listed, server)


def attempt_row(declaration_raw: bytes, members: dict, listed: dict | None, server: dict | None) -> dict:
    """The attempt row of section 8.1, or Unreadable with the first cause that holds, in the order of
    UNREADABLE_CAUSES. `declaration_raw` is the declaration (the p5002-declaration artifact's bytes; for the
    `attempt` command the records' own); `members` maps each member of MEMBERS found to its bytes, and each file of
    MONITOR_FILES found (not members: a missing one fails the monitor check); `listed` is
    {'run_id', 'created_at', 'head_sha', 'mode', 'attempt', 'registration_sha256', 'runner_labels'} of the
    dispatch; `server` is {'job_started_at': seconds, 'anchors': {k: (file bytes, created_at in seconds)}}. With
    `listed`, a CONFIRMATORY declaration's constants must be the registered ones (required_seconds() is read, so
    only a hosted job passes `listed`). With `server` None the anchors are NOT_CHECKED and S13 cannot be PASS.
    Records that are missing or invalid are EVIDENCE_MISSING for a local read; with `server` (the hosted report)
    the attempt is not unreadable for them: its row has the state LOST."""
    # DECLARATION_REFUSED: the declaration and the marker are valid and this run's
    try:
        declaration = _one_line(declaration_raw)
        _check_declaration(declaration)
    except _Invalid:
        raise Unreadable('DECLARATION_REFUSED') from None
    mode, constants = declaration['mode'], declaration['constants']
    registration = declaration['registration_sha256']
    if listed is not None:
        if any(not _same(declaration[key], listed[key]) for key in ('run_id', 'head_sha', 'mode', 'attempt')):
            raise Unreadable('DECLARATION_REFUSED')
        if mode == 'CONFIRMATORY' and not _same(constants, effective_constants(None, required_seconds())):
            raise Unreadable('DECLARATION_REFUSED')
        registration = listed['registration_sha256']
    anchor_raws, marker_value = [], None
    if server is not None:
        if type(server.get('anchors')) is not dict:
            raise ValueError('server anchors')
        anchor_raws = [entry[0] for entry in server['anchors'].values()
                       if type(entry) in (tuple, list) and entry and type(entry[0]) is bytes]
        got = _anchor(server['anchors'].get(0), 'marker.json')
        if got is None or any(not _same(got[0][key], declaration[key]) for key in (
                'mode', 'attempt', 'head_sha', 'run_id', 'run_attempt')):
            raise Unreadable('DECLARATION_REFUSED')
        marker_value = got[0]
    # REGISTRATION_MISMATCH: the declaration and the marker name the dispatch's registration
    if not _same(declaration['registration_sha256'], registration) or (
            marker_value is not None and not _same(marker_value['registration_sha256'], registration)):
        raise Unreadable('REGISTRATION_MISMATCH')
    # LABELS_REFUSED: no byte of the other mode anywhere; the labels are exactly the declaration's
    found = {name: members[name] for name in MEMBERS if name in members}
    monitor_files = {name: members[name] for name in MONITOR_FILES if name in members}
    if any(type(raw) is not bytes for raw in [*found.values(), *monitor_files.values()]):
        raise TypeError('member bytes')
    if any(word in raw for raw in [declaration_raw, *anchor_raws, *found.values(), *monitor_files.values()]
           for word in FORBIDDEN[mode]):
        raise Unreadable('LABELS_REFUSED')
    for name in ('declaration.json', 'environment.json'):
        if name in found and _labels_of(found[name]) != declaration['labels']:
            raise Unreadable('LABELS_REFUSED')
    # EVIDENCE_MISSING: the eleven members, each within its limit, canonical, of its schema; the hash chain
    try:
        _need(len(found) == len(MEMBERS))
        _check_declaration(_one_line(found['declaration.json']))
        environment, final, parts = (_one_line(found[name]) for name in (
            'environment.json', 'final.json', 'components.json'))
        _check_environment(environment)
        _check_final(final)
        _check_components(parts)
        for name in SCOPE_FIELDS:
            _need(found[name] == scope_file(name))
        # a line a killed writer left unfinished is not a line (final.json states the complete lines' count)
        samples, hashes = _chain(_complete(found['samples.jsonl']))
        blocks = [value for _, value in _lines(_complete(found['blocks.jsonl']))]
        _check_block_rows(blocks)
        critical = [value for _, value in _lines(_complete(found['critical_heights.jsonl']))]
        _check_critical_rows(critical)
        build = _one_line(found['replay_build.json'])
        _check_replay_build(build)
        follows = [value for _, value in _lines(_complete(found['replay.jsonl']))]
        _check_replay_rows(follows)
        # final.json is this attempt's and describes the final samples.jsonl
        _need((final['run_id'], final['attempt']) == (declaration['run_id'], declaration['attempt']))
        _need(final['samples'] == len(samples) and final['head_sha256'] == (hashes[-1] if hashes else ZERO_HASH))
    except _Invalid:
        if server is None:      # a local read has no marker and no checkpoint artifact to report the attempt by
            raise Unreadable('EVIDENCE_MISSING') from None
        return _lost_row(declaration, listed, server)
    # COMPLETENESS_REFUSED: the observe job's server start
    if server is not None and not _is_int(server.get('job_started_at'), 1, TIME_MAX):
        raise Unreadable('COMPLETENESS_REFUSED')
    # COMPONENTS_NOT_WIRED: a CONFIRMATORY attempt needs every component wired, in the record and in this checker
    if mode == 'CONFIRMATORY' and (NOT_WIRED or any(state != WIRED_STATE for state in parts['components'].values())):
        raise Unreadable('COMPONENTS_NOT_WIRED')

    result = intervals(samples, [row for row in critical if row['kind'] == 'FORK_POINT'], constants,
                       environment['genesis_hash'])
    longest = result['longest']
    table = s14_table(critical, constants['h0'], environment['genesis_hash'], blocks)
    challenge_ok = (all(final['challenge_final'][key] == constants['signet_challenge_hex'] for key in NODES)
                    and not any(item['kind'] == 'CONTEXT' for item in result['breaks']))
    nodes = environment['nodes']
    identity = {
        'ENVIRONMENT_BINDING': all(_same(environment[key], declaration[key]) for key in (
            'mode', 'attempt', 'head_sha', 'run_id')),
        'ENVIRONMENT_SOURCE': environment['source_sha256'] == declaration['source_sha256'],
        'ENVIRONMENT_BINARY': all(nodes[key]['version'] == NODE_VERSIONS[key]
                                  and nodes[key]['bitcoind_sha256'] == BITCOIND_SHA256[key] for key in NODES),
        # the two binaries the VPS hashed (S1b) are the ones the hosted build job made (the declaration's)
        'ENVIRONMENT_BINARIES': _same(environment['binaries'], {
            key: declaration['binaries'][key + '_sha256'] for key in BINARY_NAMES}),
        'ENVIRONMENT_CONTEXT': (environment['signet_challenge_hex'] == constants['signet_challenge_hex']
                                and environment['h0'] == constants['h0'] and environment['scope_b'] == SCOPE_B
                                and environment['s14_not_covered'] == S14_NOT_COVERED
                                and environment['transferability'] == TRANSFERABILITY),
        # a registered attempt also needs a clock the host reports as NTP-synchronized
        'ENVIRONMENT_CLOCK': (bool(environment['clock']['source']) and bool(samples)
                              and samples[0]['boot_id'] == environment['boot_id']
                              and (mode != 'CONFIRMATORY' or environment['clock']['ntp_synchronized'] is True)),
        'RECORDS_DECLARATION': found['declaration.json'] == declaration_raw,
        'CHALLENGE': challenge_ok,
    }
    failed_identity = [name for name in IDENTITY_CHECKS if not identity[name]]
    skew = None
    if server is None:
        anchors = {'result': 'NOT_CHECKED', 'failed': [], 'server_span_seconds': None, 'present': []}
    else:
        anchors, skew = _server_anchors(server, declaration, samples, hashes, longest)
    # the observed margins (never judged): how far the wall clock moved from the monotonic clock inside the
    # longest interval, as the cumulative clock rule measures it, and SA7's largest anchor-to-anchor skew
    drift = None
    if longest is not None:
        inside = samples[longest['first_seq']:longest['last_seq'] + 1]
        offset = inside[0]['realtime_ns'] - inside[0]['monotonic_ns']
        drift = max(abs(item['realtime_ns'] - item['monotonic_ns'] - offset) for item in inside)
    met = longest is not None and longest['monotonic_ns'] >= constants['required_seconds'] * NS
    applies = {'IDENTITY': bool(failed_identity), 'INTERVAL_SHORT': not met,
               'SERVER_ANCHOR': anchors['result'] == 'FAIL',
               'SERVER_ANCHOR_NOT_CHECKED': anchors['result'] == 'NOT_CHECKED'}
    reason = next((name for name in S13_REASONS if applies[name]), None)    # the first that applies; None is PASS
    s13 = {'result': 'PASS' if reason is None else 'FAIL', 'reason': reason,
           'required_seconds': constants['required_seconds'], 'samples': len(samples),
           'intervals': len(result['intervals']),
           'longest': None if longest is None else dict(longest, seconds=longest['monotonic_ns'] // NS),
           'breaks': result['breaks'][:LIST_CUT], 'clock_steps': result['clock_steps'][:LIST_CUT],
           'identity': failed_identity, 'anchors': anchors,
           'margins': {'clock_drift_max_ns': drift, 'anchor_skew_max_seconds': skew}}
    window = None if longest is None else (samples[longest['first_seq']]['monotonic_ns'],
                                           samples[longest['last_seq']]['monotonic_ns'])
    checks = {'monitor': monitor_check(monitor_files.get(MONITOR_FILES[1]), monitor_files.get(MONITOR_FILES[0]),
                                       final, declaration, environment, build, critical, window),
              'replay': replay_check(build, follows, blocks, critical, environment['genesis_hash'], constants,
                                     window)}
    # A's decision 4: a critical height the monitor read with two hashes is a disagreement of S14 too
    unequal = checks['monitor']['unequal'] or 0
    table = dict(table, disagreements=table['disagreements'] + unequal, monitor_disagreements=unequal,
                 result='FAIL' if unequal else table['result'])
    s14 = dict(table, challenge='PASS' if challenge_ok else 'FAIL', not_covered=S14_NOT_COVERED)
    row = {'attempt': declaration['attempt'], 'run_id': declaration['run_id'],
           'run_attempt': declaration['run_attempt'], 'created_at': None, 'started_at': None,
           'start_time_utc': None, 'runner_labels': None, 'state': ATTEMPT_STATES[0],
           'scaling': declaration['scaling'], 'stop_reason': final['stop_reason'],
           # bytes after the last newline of samples.jsonl (a line a killed writer left unfinished) were not read
           'samples_partial_last_line': _complete(found['samples.jsonl']) != found['samples.jsonl'],
           's13': s13, 's14': s14, 'components': parts['components'], 'component_checks': checks,
           'blocks': _blocks_summary(blocks, constants['h0'])}
    return _listing_values(row, listed, server)


# ------------------------------------------------------------------------------------------ collection ----
def critical_disagreements(raw: bytes) -> int | None:
    """The rows with `agree` false in the complete lines of a critical_heights.jsonl (a dispatch that never
    started may have read a critical height before it failed: section 8.3); None when the bytes are not that
    record."""
    try:
        rows = [value for _, value in _lines(_complete(raw))]
        _check_critical_rows(rows)
    except _Invalid:
        return None
    return sum(1 for row in rows if not row['agree'])


def verdict(attempts: list[dict], constants: dict, never_started: list[dict] | None = None,
            coverage: str = COVERAGE_OK) -> dict:
    """Section 8.2's verdict over the counted attempts in attempt order (read rows, LOST rows and UNREADABLE
    entries); the first rule that holds decides. Each attempt stands alone: no interval of one is added to
    another's. A disagreement a never-started dispatch read before it failed (`never_started` entries'
    `s14_disagreements`), or one a LOST attempt's checkpoint counted, is final as one of a read attempt is; a
    refused `coverage` is INCONCLUSIVE. A LOST attempt counts toward `max_attempts` and never passes."""
    read = [entry for entry in attempts if entry.get('state') == ATTEMPT_STATES[0]]
    lost = [entry for entry in attempts if entry.get('state') == ATTEMPT_STATES[1]]
    unreadable = [entry for entry in attempts if entry.get('state') == ATTEMPT_STATES[2]]
    if len(read) + len(lost) + len(unreadable) != len(attempts) or any(
            e['cause'] not in UNREADABLE_CAUSES for e in unreadable):
        raise ValueError('attempts')
    if coverage not in (COVERAGE_OK,) + COVERAGE_CODES:
        raise ValueError('coverage')
    early = [entry.get('s14_disagreements') for entry in never_started or []]
    kept = [entry['checkpoint_s14_disagreements'] for entry in lost]
    if any(not (count is None or _is_int(count)) for count in early + kept):
        raise ValueError('a disagreement count')
    early, kept = sum(count or 0 for count in early), sum(count or 0 for count in kept)
    if any(row['s13']['required_seconds'] != constants['required_seconds'] for row in read + lost):
        raise ValueError('an attempt judged against another required_seconds')
    expected = {'s13': 'LONGEST_QUALIFYING_INTERVAL_GE_REQUIRED_SECONDS',
                'required_seconds': constants['required_seconds'], 's14': 'CRITICAL_HEIGHT_DISAGREEMENTS_EQ_0',
                'components': 'ALL_WIRED_AND_CHECKED', 'max_attempts': constants['max_attempts'],
                'stitching': 'NONE_EACH_ATTEMPT_ALONE'}

    def checked(row):       # both component checks PASS (A's decision 3)
        return all(row['component_checks'][name]['result'] == CHECK_RESULTS[0] for name in COMPONENTS)

    gates = [row for row in read if row['s13']['result'] == 'PASS' and row['s14']['result'] == 'PASS']
    passing = [row['attempt'] for row in gates if checked(row)]
    observed = {'counted_attempts': len(attempts),
                's13': [None if e['state'] == ATTEMPT_STATES[2] else e['s13']['result'] for e in attempts],
                's14': [None if e['state'] == ATTEMPT_STATES[2] else e['s14']['result'] for e in attempts],
                'components': [{name: e['component_checks'][name]['result'] for name in COMPONENTS}
                               if e['state'] == ATTEMPT_STATES[0] else None for e in attempts],
                's14_disagreements': sum(row['s14']['disagreements'] for row in read) + kept + early,
                'passing_attempt': None, 'lost_attempts': [row['attempt'] for row in lost]}
    if early or kept or any(row['s14']['result'] == 'FAIL' for row in read):
        result, reason = 'FAIL', 'NO_GO_S14_DISAGREEMENT'
    elif unreadable or coverage != COVERAGE_OK:
        result, reason = 'INCONCLUSIVE', unreadable[0]['cause'] if unreadable else 'COMPLETENESS_REFUSED'
    elif passing:
        result, reason = 'PASS', None
        observed['passing_attempt'] = passing[0]
    elif len(attempts) >= constants['max_attempts']:
        result, reason = 'FAIL', 'ATTEMPTS_EXHAUSTED'
    elif gates:
        result, reason = 'OPEN', VERDICT_OPEN_REASONS[2]     # S13 and S14 passed and a component check did not
    elif any(row['s13']['result'] == 'PASS' and row['s14']['result'] == 'INCOMPLETE' for row in read):
        result, reason = 'OPEN', VERDICT_OPEN_REASONS[1]     # S13 passed and S14 is INCOMPLETE
    else:
        result, reason = 'OPEN', VERDICT_OPEN_REASONS[0]
    return {'expected': expected, 'observed': observed, 'result': result, 'reason': reason}


def collection_report(mode: str, registration_sha256: str | None, head_sha: str, attempts: list[dict],
                      never_started: list[dict], result: dict | None, constants: dict | None,
                      coverage: str = COVERAGE_OK) -> bytes:
    """The collection report of section 8.2, one canonical line: every counted attempt in attempt order (read or
    unreadable, none erased), the verdict (`result`: verdict()'s value, None for EXPLORATORY), `coverage` (OK, or
    the code that refused the coverage of section 8.3), the capture list, the environment row and what hosted
    verification cannot see."""
    if mode not in MODES or not _is_sha(head_sha) or not (registration_sha256 is None or _is_hash(registration_sha256)):
        raise ValueError('collection report')
    if coverage not in (COVERAGE_OK,) + COVERAGE_CODES:
        raise ValueError('collection report: coverage')
    if (mode == 'CONFIRMATORY') != (registration_sha256 is not None) or (mode == 'CONFIRMATORY') != (
            type(result) is dict) or (mode == 'EXPLORATORY' and result is not None):
        raise ValueError('collection report: mode')
    read = [entry for entry in attempts if entry.get('state') in ATTEMPT_STATES[:2]]      # read or LOST
    scaled = mode == 'EXPLORATORY' and any(row['scaling'] == SCALINGS[1] for row in read)
    environment = {'host': ENVIRONMENT_HOST, 'cr21': ENVIRONMENT_CR21, 'node_versions': dict(NODE_VERSIONS),
                   'same_host_nodes': True,
                   'runner_labels': sorted({label for row in read for label in row['runner_labels'] or []})}
    capture = {'tx_hex': SCOPE_STATE, 'tx_times': SCOPE_STATE, 'reserve_snapshots': SCOPE_STATE,
               'block_times': 'RECORDED', 'outage_intervals': 'RECORDED',
               'monitor_logs': NOT_WIRED_STATE if 'monitor' in NOT_WIRED else 'RECORDED',
               'fleet_scale': 'NOT_MEASURED'}
    return line({'format': FORMAT_REPORT, 'mode': mode, 'registration_sha256': registration_sha256,
                 'head_sha': head_sha, 'labels': labels_for(mode, scaled), 'transferability': TRANSFERABILITY,
                 'scope_b': SCOPE_B, 's14_not_covered': S14_NOT_COVERED, 'constants': constants,
                 'attempts': attempts, 'never_started': never_started, 'verdict': result,
                 'coverage': coverage, 'capture_list': capture, 'environment': environment, 'hosted_limits': list(HOSTED_LIMITS)})


def observation_list(starts: dict[int, int], registration_sha256: str) -> bytes:
    """Section 9: the observation list in ct_preregistration_receipt's V1 shape, one entry per counted attempt in
    attempt order (`starts` maps attempts 1..k to the observe job's server `started_at` in integer seconds)."""
    if not _is_hash(registration_sha256) or not starts or sorted(starts) != list(range(1, len(starts) + 1)) or (
            len(starts) > MAX_ATTEMPTS):
        raise ValueError('observation list')
    items = []
    for attempt in sorted(starts):
        if not _is_int(starts[attempt], 1, 2**53 - 1):
            raise ValueError('start_time_utc')
        items.append({'observation_id': 'OBS-%d%07d' % (OBSERVATION_PREFIX, attempt),
                      'registration_sha256': registration_sha256, 'start_time_utc': starts[attempt]})
    return line({'schema': OBSERVATION_SCHEMA, 'observations': items})


# ------------------------------------------------------------------------------------------- commands ----
def _digits(text: str) -> int:
    if re.fullmatch(r'[0-9]{1,18}', text) is None:
        raise argparse.ArgumentTypeError('an integer')
    return int(text)


def _optional_digits(text: str):
    return None if text == '' else _digits(text)


def _optional_text(text: str):
    return None if text == '' else text


def parser():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest='command', required=True)
    q = sub.add_parser('plan')
    q.add_argument('--mode', required=True)
    q.add_argument('--attempt', required=True, type=_digits)
    q.add_argument('--expected-head', required=True)
    q.add_argument('--source-sha256', required=True)
    q.add_argument('--declaration', required=True)
    q.add_argument('--registration', type=_optional_text)
    q.add_argument('--registration-sha256', type=_optional_text)
    q.add_argument('--s04-run-id', type=_optional_digits)
    q.add_argument('--s04-dir', type=_optional_text)
    for name in ('--bin-sha256', '--bitagi-sha256', '--fixture-sha256'):
        q.add_argument(name, type=_optional_text)
    for name in OVERRIDE_BOUNDS:
        q.add_argument('--' + name.replace('_', '-'), type=_optional_digits)
    q = sub.add_parser('attempt')
    q.add_argument('--records', required=True)
    q.add_argument('--output', required=True)
    q = sub.add_parser('pilot-registration')
    q.add_argument('--commit', required=True)
    q.add_argument('--output', required=True)
    return p


def _plan_command(args) -> dict:
    overrides = {name: getattr(args, name) for name in OVERRIDE_BOUNDS}
    binaries = {'archive_sha256': args.bin_sha256, 'bitagi_sha256': args.bitagi_sha256,
                'fixture_sha256': args.fixture_sha256}
    declaration = plan(args.mode, args.attempt, args.expected_head, args.source_sha256, args.registration,
                       args.registration_sha256, args.s04_run_id, overrides, os.environ,
                       s04_dir=None if args.s04_dir is None else Path(args.s04_dir), binaries=binaries)
    raw = line(declaration)
    _write_new(args.declaration, raw)
    return {'attempt': declaration['attempt'], 'mode': declaration['mode'], 'scaling': declaration['scaling'],
            'checkpoints': declaration['constants']['checkpoints'],
            'declaration_sha256': hashlib.sha256(raw).hexdigest()}


def _attempt_command(args) -> dict:
    records = Path(args.records)
    try:
        info = os.lstat(records)
    except FileNotFoundError:
        raise Refusal('RECORDS_MISSING') from None
    if stat.S_ISLNK(info.st_mode):
        raise Refusal('PATH_NOT_REGULAR')
    if not stat.S_ISDIR(info.st_mode):
        raise Refusal('RECORDS_MISSING')
    read_declaration(records / 'declaration.json')
    members = {}
    for name in MEMBERS + MONITOR_FILES:
        raw = _read_file(records / name, LINES_LIMIT if name.endswith('.jsonl') else SMALL_LIMIT)
        if raw is not None:
            members[name] = raw
    try:
        row = attempt_row(members['declaration.json'], members, None, None)
    except Unreadable as unreadable:
        # a local read names its own codes where it has them; any other cause is the report's INCONCLUSIVE
        local = {'DECLARATION_REFUSED': 'DECLARATION_INVALID', 'EVIDENCE_MISSING': 'RECORD_INVALID'}
        if unreadable.cause in local:
            raise Refusal(local[unreadable.cause]) from None
        raise
    raw = line(row)
    _write_new(args.output, raw)
    longest = row['s13']['longest']
    return {'s13': row['s13']['result'], 's14': row['s14']['result'],
            'longest_interval_seconds': None if longest is None else longest['seconds'],
            'disagreements': row['s14']['disagreements'], 'row_sha256': hashlib.sha256(raw).hexdigest()}


def _pilot_registration_command(args) -> dict:
    """The TEST_ONLY pilot file for A, one canonical line (section 10); its SHA-256 is the pilot dispatch's
    `registration_sha256` once A has committed these bytes on main."""
    raw = line(pilot_registration(args.commit, required_seconds()))
    _write_new(args.output, raw)
    return {'registration_sha256': hashlib.sha256(raw).hexdigest()}


COMMANDS = {'plan': _plan_command, 'attempt': _attempt_command, 'pilot-registration': _pilot_registration_command}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    tool = TOOL_NAMES[0]

    def emit(command, result, exit_code, code=None, **keys) -> int:
        sys.stdout.write(output_line(tool, command, result, exit_code, code, **keys).decode('ascii'))
        return exit_code

    if not __debug__:   # before anything else, argparse included
        return emit(argv[0] if argv and argv[0] in COMMANDS else None, 'REFUSED', EXIT_REFUSAL, 'OPTIMIZED_PYTHON')
    args = parser().parse_args(argv)
    try:
        keys = COMMANDS[args.command](args)
    except Refusal as refusal:
        return emit(args.command, 'REFUSED', refusal.exit_code, refusal.code)
    except Unreadable as unreadable:
        return emit(args.command, 'INCONCLUSIVE', EXIT_VALIDATION, unreadable.cause)
    except Exception:   # noqa: BLE001 - one closed line; no text of the failure is printed
        return emit(args.command, 'INTERNAL', EXIT_INTERNAL, 'INTERNAL_ERROR')
    return emit(args.command, 'DONE', EXIT_OK, **keys)


if __name__ == '__main__':
    import claude_track_exit
    claude_track_exit.run(main)
