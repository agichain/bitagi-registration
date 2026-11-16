// TEST_ONLY_PRIVATE_SCALAR_KNOWN -- DO_NOT_USE_FOR_VALUE OR MAINNET AUTHORITY.
//! CT-P3-044c-1d-3d-3c-rn-1: the launch host's accept path on two real
//! Regtest nodes (Bitcoin Core 31.1 as Node A, 30.3 as Node B; A #258
//! issuecomment-6244714789 (나), AGENTS.md Tier 3). Class T, Regtest only.
//!
//! `tools/claude_track_regtest_offline_export.py` runs these ignored
//! workers in the ordinary build, alternating with the offline stages of
//! `bitagi-signer/tests/launch_host_e2e_sign.rs`, all at tip H0 − 1:
//!
//! 1. `launch_describe_worker`: the pair's node configuration records
//!    (`common::record_set_for`, the debug-log paths the driver gives) and
//!    their set hash, which the host's descriptor binds and the offline
//!    charge stage builds its wallet and base on.
//! 2. `launch_sign_worker`: [`LaunchHost::init`] on the charged wallet,
//!    then production turns ([`LaunchHost::step_with_hand_offs`]) over the
//!    operator's candidate file: the execution checks (step 7's prevout
//!    reads on both nodes), a human signing authorization file for exactly
//!    the core's wait, the signing observation and `Sign`, which writes the
//!    hand-off to the outbox and records `SigningHandedOff`. It ends at
//!    `OfflineSignaturePending`.
//! 3. `launch_broadcast_worker`, after the offline stage signed the
//!    hand-off: the operator's E3d import (verified against both nodes'
//!    prevouts), then turns: the broadcast observation, `AdmitSignedFinal`
//!    (both nodes' `testmempoolaccept`), the prebroadcast checks, a human
//!    broadcast authorization file, and step 8, which hands the guarded
//!    bytes to the product transport ([`ProductTransport`], 1e-0) inside
//!    the wallet's export guard
//!    (`broadcast::BroadcastHandOff`) and records `Submitted`. It ends at
//!    `AwaitingInclusion`.
//!
//! CT-P3-044c-1d-3d-3c-rn-2 (A #258 issuecomment-6255049643 (iv),
//! -6255870804 Q-b15, -6262177277 1) runs the cases on a second pair and a
//! chain of its own, the charge built at H0 − 2 and the host turning at
//! H0 − 1, so step 8 reads an ancestry of two blocks. `launch_case_worker`
//! runs one phase of [`PHASES`] (and [`INCLUDED`]) per process, named by
//! `BITAGI_E3D3_PHASE`, after the driver changed the nodes for it. Phases 2
//! and 3 above are that table's first two rows: one turn loop serves all.
//! Each turn asserts its step's outcome as the host recorded it (a check
//! `Passed`, an admission's two answers, a submission's), that the human
//! authorization was recorded just before `Sign` and `Broadcast` (from the
//! host's journal, across processes), and 1d-3d-3c-2's paths (`steady`);
//! any other step, refusal or error is a FAIL.
//!
//! #503 (FD-CT-62) runs [`BOUND_PHASES`] with the same worker on a fifth
//! pair and chain, charged at H0 − 2: the sign phase, both nodes rejecting
//! the admission (the node stop raised, one counted failure at H0 − 1),
//! then at the same H0 − 1, with both nodes ready to admit, every act
//! refused at the core's per-tip bound (`FailedAttemptsAtTip`), across
//! turns and processes, with nothing written. The cases' chain has no
//! rejection: at K = 1 a rejected Opening cannot be admitted again at its
//! tip, and the Opening is admitted only at H0 − 1.
//!
//! The H0 − 1 prestate steps (`ComparePrestate`, `RecordInitialPrestate`;
//! CT-P3-044c-1 1d-3d-3d) are the host's own, as every other entry is:
//! nothing is seeded. The first `ComparePrestate` turn writes the host's
//! Rust receipt to the outbox and records nothing
//! (`PrestateComparisonPending`); the worker reports the receipt's name
//! (`prestate_receipt`) and ends there. The driver then makes the Python
//! receipt from its own reads of both nodes and compares the two with the
//! formats doc's `produce` and `compare --raw-block` commands as black
//! boxes, and runs the same phase again with the Python receipt and the
//! report (`BITAGI_E3D3_PRESTATE_RECEIPT`, `BITAGI_E3D3_PRESTATE_REPORT`),
//! which the host checks against its own reads and receipt, made again,
//! before it records the comparison and then the INITIAL_PRESTATE.
//!
//! #484 L0 (A #258 issuecomment-6366258674 §3 (나), -6378746779 §1; B's
//! draft -6377313784 §3 4) runs [`L0_PHASES`] on a fourth pair and chain,
//! charged at H0 − 2 and signed there: `launch_l0_worker`'s first phase
//! makes the host before the floor block exists
//! ([`LaunchHost::init_before_floor`]) and runs the pre-floor turns at
//! H0 − 2 to the Sign hand-off; after the offline signature and the
//! operator's import the next phase waits for the opening gate; after the
//! driver mined H0 − 1 the last phase anchors the floor and runs the H0 − 1
//! steps, with no Sign, to step 8. No L0 turn raises a lock or sees a
//! reorg, a pre-floor turn writes no replay store, and after each H0 − 1
//! turn the store's floor is the agreed H0 − 1 block.
//!
//! Step 8's transport is the product one, `bitagi_launch_transport`'s
//! [`RegtestTransport`] (CT-P3-044c-1 1e-0, A #258
//! issuecomment-6340181720), built for each hand-off on a read session of
//! its own (the public Class T fixture credential of `rpc_credentials.rs`)
//! and the send-only user the driver made for this run. It checks both
//! nodes before it sends, sends once to each and decides each node's
//! result by its `getmempoolentry` wtxid. It is called only by the host's
//! step 8, with a `GuardedRaw`; nothing else here submits.
//!
//! Output is `E3D3_STAGE_V1` lines: digests, heights, step names and
//! stable codes. No key, credential, port or path is printed. The
//! node-record signing scalar is the TEST_ONLY fixture of `common`.
#![cfg(unix)]

#[path = "support/answer_proxy.rs"]
mod answer_proxy;
mod common;

use answer_proxy::AnswerProxy;

use std::io::{Read as _, Write as _};
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};
use std::time::Duration;

use bitagi_bitcoin::DualNodeError;
use bitagi_bitcoin::network_context::NodeContextError;
use bitagi_bitcoin::preflight_rpc::{PreflightRpcRead, PrevoutView};
use bitagi_bitcoin::rpc_http::{HttpRpcClient, RpcSession};
use bitagi_bitcoin::{BitcoinRpcRead, substrate_context_hash};
use bitagi_launch::decision::{Outcome, Step, Verdict, Wait};
use bitagi_launch::facts::{AgreedTip, CheckOutcome, Entry, NodeAdmission, NodeSubmission, Record};
use bitagi_launch::reorg::AtLocal;
use bitagi_launch::with_reads::{ReadsCode, ReadsVerdict};
use bitagi_launch_host::act::{
    ActOutcome, AuthorityUnused, AuthorizationOutcome, HandOffs, NotYet,
};
use bitagi_launch_host::broadcast::{BroadcastHandOff, HandOffOutcome, TransportFailed};
use bitagi_launch_host::events::{Ack, AckSource, EventLines};
use bitagi_launch_host::finality::Marked;
use bitagi_launch_host::host_file::{HostFile, Seen};
use bitagi_launch_host::prestate::{PrestateComparison, PrestateHandOff, receipt_file_name};
use bitagi_launch_host::replay_compare::{ReplayComparison, ReplayHandOff, ReplayOutcome};
use bitagi_launch_host::turn::{TurnInputs, TurnReport};
use bitagi_launch_host::xd1::{AckLines, MAX_ACK_WAIT};
use bitagi_launch_host::{Floor, HOST_FILE, HostConfig, LaunchHost};
use bitagi_launch_transport::{RegtestTransport, SendCredential};
use bitagi_profile::{NetworkProfile, deployment_id};
use bitagi_signer::export_import::{
    VerifiedOfflineExport, decode_offline_export, verify_offline_export,
};
use bitagi_signer::export_wallet::import_offline_export;
use bitagi_types::{BitcoinInternalHash32, Bytes32, CoreHeight, SubstrateContext};
use bitagi_wallet::campaign_budget::{BudgetFreezeContext, CampaignBudget, admit_budget_record};
use bitagi_wallet::campaign_stop::{LockReason, StopCode};
use bitagi_wallet::reservations::{
    LedgerIdentity, OfflineImportOutcome, Origin, ReplayInput, ReservationLedger, SupportedContext,
};
use bitagi_wallet::{NodeAgreement, ObservedChainContext, ProofContext, SyncState};
use common::{H0, internal, node_record_set, regtest_genesis};

const LINE: &str = "E3D3_STAGE_V1";
/// Within `RpcSession::replay`'s bounds.
const RPC_CALLS: u32 = 20_000;
const RPC_TIME: Duration = Duration::from_secs(570);
/// More turns than either phase takes; a loop that does not end is a FAIL.
const MAX_TURNS: usize = 16;
/// The launch candidate's id (its bundle root, the operator's statement).
const LAUNCH_CANDIDATE: [u8; 32] = [0x0c; 32];
/// The retained signed-final record id the candidate file states.
const SIGNED_FINAL_RECORD: [u8; 32] = [0x0d; 32];
/// The digest of the operator's TDS 14.7 resolution record the resolution
/// file states (#440: Class T, a stand-in; the host reads only its digest).
const RESOLUTION_RECORD: [u8; 32] = [0x14; 32];
/// The human actors' references.
const SIGNING_ACTOR: [u8; 32] = [0xac; 32];
const BROADCAST_ACTOR: [u8; 32] = [0xad; 32];
/// The public Class T fixture credential (`rpc_credentials.rs`).
/// 1e-2a: the TEST_ONLY Class T TDS 6.7 procedure record whose digest the
/// procedure file names (no procedure is carried out on Regtest here).
const PROCEDURE_RECORD: &[u8] =
    b"TEST_ONLY Class T 1e-2a: TDS 6.7 procedure record, step 6 not performed (1D3 Q17)\n";

const AUTH_RECIPE: &[u8] = b"BITAGI/P3-008/PUBLIC-AUTH/V1";
const AUTH_USER: &str = "bitagi-class-t";

fn report(name: &str, value: &str) {
    let mut out = std::io::stdout().lock();
    writeln!(out, "{LINE}\t{name}\t{value}").unwrap();
    out.flush().unwrap();
}

/// 1e-2b-1: the event lines the driver asked for, if any. Lines go to a
/// new owner-only file (`BITAGI_E3D3_EVENT_LINES`), one per process. In
/// XD-1 mode (`BITAGI_E3D3_XD1_ACK`, a FIFO the driver writes) the host
/// waits after S2 for the driver's ack, at most `XD1_ACK_SECONDS`.
fn event_lines() -> Option<EventLines> {
    use std::os::unix::fs::OpenOptionsExt as _;
    let path = std::env::var_os("BITAGI_E3D3_EVENT_LINES")?;
    let file = std::fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(path)
        .expect("E3D3_EVENT_LINES");
    let Some(ack) = std::env::var_os("BITAGI_E3D3_XD1_ACK") else {
        return Some(EventLines::new(Box::new(file)));
    };
    let source = AckLines::spawn(Fifo(PathBuf::from(ack), None), XD1_ACK_WAIT);
    Some(EventLines::xd1(Box::new(file), Box::new(source)))
}

/// The ack FIFO, opened on the first read (on the ack reader's thread: an
/// open blocks until the driver opens its end).
struct Fifo(PathBuf, Option<std::fs::File>);

impl std::io::Read for Fifo {
    fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
        if self.1.is_none() {
            self.1 = Some(std::fs::File::open(&self.0)?);
        }
        self.1.as_mut().map_or(Ok(0), |f| f.read(buf))
    }
}

/// The host's bound on the ack wait in the smoke run.
const XD1_ACK_WAIT: Duration = Duration::from_secs(30);

/// XA2 (M4, FD-CT-62; A's XD-1 decisions of 2026-11-10, V3 §10): the
/// Founder's live broadcast decision, before the broadcast authorization
/// file is written (`write`, in the `None` arm of
/// `Wait::BroadcastAuthorityRequired`). `decision` is
/// `BITAGI_E3D3_XD1_DECISION`, a FIFO the driver sets only for the second
/// H0 − 1 process of a live-decision XD-1 run (`l0_broadcast`); unset,
/// `write` runs as before. Set, the worker reads that FIFO with
/// [`AckLines`], opened on the reader's first read as the ack [`Fifo`] is
/// (the driver opens its end only when it delivers), for the ack of the
/// sequence number of the `STEP_9_END` line in this process's event file
/// (`events`, `BITAGI_E3D3_EVENT_LINES`), the number the driver reads from
/// that line and acks only on the Founder's BROADCAST. Only `Acked` runs
/// `write`. Another number, a closed FIFO, any other line (`AckLines`
/// reads it as closed) or an event file without one `STEP_9_END` line
/// writes nothing: the phase ends at the wait, with no step 10 line. Each
/// wait is at most `bound`; one that times out is made again, with no
/// limit of the worker's own (the driver's run cap closes the FIFO, and
/// its supervisor bounds the process).
fn broadcast_decision(
    decision: Option<std::ffi::OsString>,
    events: Option<std::ffi::OsString>,
    bound: Duration,
    write: impl FnOnce() -> PathBuf,
) -> Option<PathBuf> {
    let Some(fifo) = decision else {
        return Some(write());
    };
    let seq = events
        .and_then(|path| std::fs::read(path).ok())
        .and_then(|lines| step_9_end_seq(&lines))?;
    let mut acks = AckLines::spawn(Fifo(PathBuf::from(fifo), None), bound);
    acked(&mut acks, seq).then(write)
}

/// Whether `source` acks `seq`, asked again while it times out.
fn acked(source: &mut impl AckSource, seq: u64) -> bool {
    loop {
        match source.ack(seq) {
            Ack::Acked => return true,
            Ack::OtherSequence | Ack::Closed => return false,
            Ack::TimedOut => {}
        }
    }
}

/// The sequence number of the one whole `XD1_LINE_V1 <seq> STEP_9_END`
/// line of an event file (`events.rs`); none for no such line or two.
fn step_9_end_seq(lines: &[u8]) -> Option<u64> {
    let mut found = lines.split_inclusive(|b| *b == b'\n').filter_map(|line| {
        let line = line.strip_suffix(b"\n")?.strip_prefix(b"XD1_LINE_V1 ")?;
        let digits = line.strip_suffix(b" STEP_9_END")?;
        if digits.first().is_none_or(|d| *d == b'0') || !digits.iter().all(u8::is_ascii_digit) {
            return None;
        }
        std::str::from_utf8(digits).ok()?.parse().ok()
    });
    let seq = found.next()?;
    found.next().is_none().then_some(seq)
}

/// XA2 (M4): the `l0_broadcast` process's event lines up to its
/// `STEP_9_END` (V3 §4: seq 17), as the driver's `EVENT_LINES` lists them.
const L0_TO_STEP_9_END: [&str; 17] = [
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
    "STEP_6_END",
    "STEP_7_START",
    "STEP_7_END",
    "STEP_8_START",
    "STEP_8_END",
    "STEP_9_START",
    "STEP_9_END",
];

/// `names` as one process's event lines, numbered from 1 (`events.rs`).
fn numbered(names: &[&str]) -> String {
    names
        .iter()
        .enumerate()
        .map(|(i, name)| format!("XD1_LINE_V1 {} {name}\n", i + 1))
        .collect()
}

/// A new TEST_ONLY directory for one gate cell.
fn gate_dir(cell: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!(
        "bitagi-e3d3-xd1-gate-{}-{cell}",
        std::process::id()
    ));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir(&dir).unwrap();
    dir
}

/// What the gate's reader reads once the driver has delivered
/// (`Decision.deliver`: `line` or nothing, then the FIFO closed), as a file
/// at the decision path in `dir`. No FIFO is made here (the worker starts
/// no process); the blocking open is the ack [`Fifo`]'s, and
/// `a_timed_out_decision_wait_is_made_again` gives the gate a pipe.
fn delivered(dir: &Path, line: Option<&[u8]>) -> std::ffi::OsString {
    let path = dir.join("xd1-decision.fifo");
    write_private(&path, line.unwrap_or_default());
    path.into_os_string()
}

/// The gate on a thread of its own, its `write` a TEST_ONLY stand-in file
/// in `dir`: what it returned, or `None` if it did not end within 30 s (a
/// FAIL, not a hang).
fn gate(
    dir: &Path,
    decision: Option<std::ffi::OsString>,
    events: Option<std::ffi::OsString>,
    bound: Duration,
) -> Option<Option<PathBuf>> {
    let file = dir.join("authority-broadcast.txt");
    let (done, result) = std::sync::mpsc::channel();
    std::thread::spawn(move || {
        let written = broadcast_decision(decision, events, bound, || {
            write_private(&file, b"TEST_ONLY stand-in broadcast authorization\n");
            file
        });
        let _ = done.send(written);
    });
    result.recv_timeout(Duration::from_secs(30)).ok()
}

/// Without `BITAGI_E3D3_XD1_DECISION` the file is written as before, and
/// nothing is read for it (no event file here).
#[test]
fn the_decision_gate_is_off_without_its_variable() {
    let dir = gate_dir("off");
    let file = dir.join("authority-broadcast.txt");
    for events in [None, Some(dir.join("absent").into_os_string())] {
        let _ = std::fs::remove_file(&file);
        assert_eq!(
            gate(&dir, None, events, MAX_ACK_WAIT),
            Some(Some(file.clone()))
        );
        assert_eq!(
            std::fs::read(&file).unwrap(),
            b"TEST_ONLY stand-in broadcast authorization\n"
        );
    }
    std::fs::remove_dir_all(&dir).unwrap();
}

/// The number is the `STEP_9_END` line's own, wherever it is, and only a
/// whole line of the writer's form counts, once.
#[test]
fn the_decision_is_for_step_9_ends_own_number() {
    assert_eq!(
        step_9_end_seq(numbered(&L0_TO_STEP_9_END).as_bytes()),
        Some(17)
    );
    let mut process = L0_TO_STEP_9_END.to_vec();
    process.extend(["STEP_10_START", "B_A_1", "B_B_1", "O_A ACCEPTED"]);
    assert_eq!(step_9_end_seq(numbered(&process).as_bytes()), Some(17));
    assert_eq!(
        step_9_end_seq(numbered(&L0_TO_STEP_9_END[12..]).as_bytes()),
        Some(5)
    );
    for bad in [
        &b""[..],
        numbered(&L0_TO_STEP_9_END[..16]).as_bytes(),
        b"XD1_LINE_V1 17 STEP_9_END",
        b"XD1_LINE_V1 017 STEP_9_END\n",
        b"XD1_LINE_V1 0 STEP_9_END\n",
        b"XD1_LINE_V1  STEP_9_END\n",
        b"XD1_LINE_V1 -17 STEP_9_END\n",
        b"XD1_LINE_V1 17 STEP_9_END \n",
        b"XD1_LINE_V1 17 STEP_9_START\n",
        b"XD1_LINE_V1 17 STEP_19_END\n",
        b"XD1_LINE_V2 17 STEP_9_END\n",
        b"XD1_LINE_V1 99999999999999999999 STEP_9_END\n",
        b"XD1_LINE_V1 17 STEP_9_END\nXD1_LINE_V1 18 STEP_9_END\n",
    ] {
        assert_eq!(step_9_end_seq(bad), None, "{bad:?}");
    }
}

/// The driver's `XD1_ACK_V1 <seq>` of the `STEP_9_END` line's number (the
/// Founder's BROADCAST) writes the file.
#[test]
fn the_ack_of_step_9_ends_number_writes_the_file() {
    for (cell, names, line) in [
        ("acked-17", &L0_TO_STEP_9_END[..], &b"XD1_ACK_V1 17\n"[..]),
        ("acked-5", &L0_TO_STEP_9_END[12..], b"XD1_ACK_V1 5\n"),
    ] {
        let dir = gate_dir(cell);
        let events = dir.join("lines.txt");
        write_private(&events, numbered(names).as_bytes());
        let fifo = delivered(&dir, Some(line));
        let file = dir.join("authority-broadcast.txt");
        assert_eq!(
            gate(
                &dir,
                Some(fifo),
                Some(events.into_os_string()),
                MAX_ACK_WAIT
            ),
            Some(Some(file.clone())),
            "{cell}"
        );
        assert!(file.exists(), "{cell}");
        std::fs::remove_dir_all(&dir).unwrap();
    }
}

/// Another number, the FIFO closed with no line (the Founder's REFUSE, a
/// closed console, the cap) or any other line writes nothing; the first
/// line decides.
#[test]
fn any_other_answer_writes_nothing() {
    let all = &L0_TO_STEP_9_END[..];
    for (cell, names, line) in [
        ("other-16", all, Some(&b"XD1_ACK_V1 16\n"[..])),
        ("other-18", all, Some(b"XD1_ACK_V1 18\n")),
        ("s2-number", all, Some(b"XD1_ACK_V1 1\n")),
        (
            "fixed-17",
            &L0_TO_STEP_9_END[12..],
            Some(b"XD1_ACK_V1 17\n"),
        ),
        ("other-first", all, Some(b"XD1_ACK_V1 16\nXD1_ACK_V1 17\n")),
        ("closed", all, None),
        ("word", all, Some(b"BROADCAST\n")),
        ("junk-first", all, Some(b"junk\nXD1_ACK_V1 17\n")),
        ("leading-zero", all, Some(b"XD1_ACK_V1 017\n")),
        ("no-newline", all, Some(b"XD1_ACK_V1 17")),
        (
            "console-line",
            all,
            Some(
                concat!(
                    "XD1_DECISION_V1 1 ",
                    "7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a7a",
                    " BROADCAST\n"
                )
                .as_bytes(),
            ),
        ),
    ] {
        let dir = gate_dir(cell);
        let events = dir.join("lines.txt");
        write_private(&events, numbered(names).as_bytes());
        let fifo = delivered(&dir, line);
        assert_eq!(
            gate(
                &dir,
                Some(fifo),
                Some(events.into_os_string()),
                MAX_ACK_WAIT
            ),
            Some(None),
            "{cell}"
        );
        assert!(!dir.join("authority-broadcast.txt").exists(), "{cell}");
        std::fs::remove_dir_all(&dir).unwrap();
    }
}

/// With the variable set, no event file or one without a `STEP_9_END`
/// line writes nothing, whatever the FIFO holds.
#[test]
fn no_step_9_end_line_writes_nothing() {
    let dir = gate_dir("no-step-9");
    let events = dir.join("lines.txt");
    write_private(&events, numbered(&L0_TO_STEP_9_END[..16]).as_bytes());
    let fifo = delivered(&dir, Some(b"XD1_ACK_V1 17\n"));
    for events in [None, Some(dir.join("absent")), Some(events)] {
        assert_eq!(
            gate(
                &dir,
                Some(fifo.clone()),
                events.map(PathBuf::into_os_string),
                MAX_ACK_WAIT
            ),
            Some(None)
        );
    }
    assert!(!dir.join("authority-broadcast.txt").exists());
    std::fs::remove_dir_all(&dir).unwrap();
}

/// `TimedOut` asks again, for the same number, with no limit of its own;
/// the first other answer decides. On a pipe, opened by its `/dev/fd` path
/// as the worker opens the FIFO's and written only after twenty waits of
/// the bound, the ack still writes the file.
#[test]
fn a_timed_out_decision_wait_is_made_again() {
    use std::os::fd::AsRawFd as _;
    struct Answers(Vec<Ack>, Vec<u64>);
    impl AckSource for Answers {
        fn ack(&mut self, seq: u64) -> Ack {
            self.1.push(seq);
            self.0.remove(0)
        }
    }
    let waits = |n| vec![Ack::TimedOut; n];
    for (answers, expected) in [
        ([waits(5), vec![Ack::Acked]].concat(), true),
        ([waits(3), vec![Ack::OtherSequence]].concat(), false),
        ([waits(2), vec![Ack::Closed]].concat(), false),
        (vec![Ack::Acked], true),
        (vec![Ack::OtherSequence], false),
        (vec![Ack::Closed], false),
    ] {
        let asks = answers.len();
        let mut source = Answers(answers, Vec::new());
        assert_eq!(acked(&mut source, 17), expected);
        assert_eq!(source.1, vec![17; asks]);
    }
    let dir = gate_dir("timed-out");
    let events = dir.join("lines.txt");
    write_private(&events, numbered(&L0_TO_STEP_9_END).as_bytes());
    let (read, mut write) = std::io::pipe().unwrap();
    let fifo = PathBuf::from(format!("/dev/fd/{}", read.as_raw_fd()));
    let after = Duration::from_millis(400);
    let started = std::time::Instant::now();
    std::thread::spawn(move || {
        std::thread::sleep(after);
        write.write_all(b"XD1_ACK_V1 17\n").unwrap();
    });
    let file = dir.join("authority-broadcast.txt");
    assert_eq!(
        gate(
            &dir,
            Some(fifo.into_os_string()),
            Some(events.into_os_string()),
            Duration::from_millis(20)
        ),
        Some(Some(file.clone()))
    );
    assert!(started.elapsed() >= after, "{:?}", started.elapsed());
    assert!(file.exists());
    drop(read);
    std::fs::remove_dir_all(&dir).unwrap();
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

fn unhex(text: &str) -> Vec<u8> {
    assert!(text.len().is_multiple_of(2), "E3D3_HEX");
    (0..text.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&text[i..i + 2], 16).expect("E3D3_HEX"))
        .collect()
}

fn unhex32(text: &str) -> [u8; 32] {
    unhex(text).try_into().expect("E3D3_HEX_LENGTH")
}

fn env(name: &str) -> String {
    std::env::var(format!("BITAGI_E3D3_{name}")).expect("E3D3_ENVIRONMENT")
}

fn ports() -> [u16; 2] {
    [env("NODE_A_PORT"), env("NODE_B_PORT")].map(|v| v.parse().expect("E3D3_PORT"))
}

/// The value of every `name=value` line `name` of `text`; it occurs once.
fn one<'a>(text: &'a str, name: &str) -> &'a str {
    let prefix = format!("{name}=");
    let found: Vec<&str> = text
        .lines()
        .filter_map(|l| l.strip_prefix(prefix.as_str()))
        .collect();
    assert_eq!(found.len(), 1, "E3D3_LINE {name}");
    found[0]
}

fn write_private(path: &Path, bytes: &[u8]) {
    std::fs::write(path, bytes).unwrap();
    std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o600)).unwrap();
}

/// The pair's records (`common::node_record_set`, for the versions both
/// nodes report and the debug-log paths the driver gives) and the
/// descriptor that binds them. Every host process makes them again.
fn descriptor(
    session: &RpcSession,
) -> (
    bitagi_bitcoin::node_configuration::NodeRecordSet,
    SubstrateContext,
) {
    let (a, b) = session.nodes();
    let versions = [
        a.network_info().expect("E3D3_NODE_INFO").version_u32,
        b.network_info().expect("E3D3_NODE_INFO").version_u32,
    ];
    assert_eq!(versions, [310_100, 300_300], "E3D3_NODE_VERSIONS");
    let versions = versions
        .map(|v| bitagi_bitcoin::SupportedNodeVersion::from_u32(v).expect("E3D3_NODE_VERSIONS"));
    let (log_a, log_b) = (env("NODE_A_LOG"), env("NODE_B_LOG"));
    let set = node_record_set(versions, [&log_a, &log_b]);
    let descriptor = SubstrateContext::regtest(internal(regtest_genesis()))
        .unwrap()
        .with_node_configuration_record(Bytes32::from_array(set.set_hash()))
        .unwrap();
    (set, descriptor)
}

/// Both nodes' answers to one read; they must agree.
fn agreed<T: PartialEq + std::fmt::Debug>(
    session: &RpcSession,
    read: impl Fn(&HttpRpcClient<'_>) -> T,
) -> T {
    let (a, b) = session.nodes();
    let (from_a, from_b) = (read(&a), read(&b));
    assert_eq!(from_a, from_b, "E3D3_NODES_DISAGREE");
    from_a
}

/// Phase 1 (module docs).
#[test]
#[ignore = "rn-1 Tier 3: run by tools/claude_track_regtest_offline_export.py"]
fn launch_describe_worker() {
    let session = RpcSession::replay(ports(), 64, Duration::from_secs(30)).expect("E3D3_RPC");
    let (_, descriptor) = descriptor(&session);
    // The read user (the product client's, whitelisted to its reads) may
    // not submit: each node answers HTTP 403 once it has read the method,
    // before the call runs.
    for port in ports() {
        let (status, _) = rpc(port, &fixture_authorization(), SEND_METHOD, "[\"00\"]");
        assert_eq!(status, Some(403), "E3D3_READ_USER_MAY_SUBMIT");
    }
    // 555-a (A #258 issuecomment-6533147267 condition 8): Core 31.1 and
    // 30.3 both give `getblockchaininfo`'s `mediantime`, and the same value
    // at the same best block, on a chain of height 11 or more. No state is
    // asserted: a fast-mined chain can be ahead of the clock.
    let (a, b) = session.nodes();
    let info = [a.blockchain_info(), b.blockchain_info()].map(|i| i.expect("E3D3_NODE_INFO"));
    assert_eq!(
        info[0].best_block_hash_internal, info[1].best_block_hash_internal,
        "E3D3_NODES_DISAGREE"
    );
    assert!(info[0].height_u64 >= 11, "E3D3_MTP_CHAIN_HEIGHT");
    assert!(
        info[0].median_time_u64.is_some() && info[0].median_time_u64 == info[1].median_time_u64,
        "E3D3_MTP"
    );
    report("descriptor", &hex(descriptor.canonical_bytes().as_bytes()));
    report("read_user_send_refused", "PASS");
    report("describe_stage", "PASS");
}

/// The launch directory's files and the host built on them.
struct Launch {
    dir: PathBuf,
    config: HostConfig,
    budget: CampaignBudget,
    base: String,
    public: String,
    session: RpcSession,
    /// CT-P5-001 D3a-1b: the sign base file and the launch candidate id
    /// this process acts for; `handoff/base.txt` and `LAUNCH_CANDIDATE`
    /// except in `launch_set_worker`.
    base_file: PathBuf,
    launch_id: [u8; 32],
    /// 1e-2b-1: this process's event lines (`BITAGI_E3D3_EVENT_LINES`),
    /// one writer across the host started per turn.
    events: std::cell::RefCell<Option<EventLines>>,
}

impl Launch {
    fn new() -> Self {
        let dir = PathBuf::from(env("LAUNCH"));
        assert!(dir.is_absolute() && dir.is_dir(), "E3D3_LAUNCH_DIR");
        let handoff = dir.join("handoff");
        let base = std::fs::read_to_string(handoff.join("base.txt")).expect("E3D3_BASE");
        let public = std::fs::read_to_string(handoff.join("launch.txt")).expect("E3D3_PUBLIC");
        let session = RpcSession::replay(ports(), RPC_CALLS, RPC_TIME).expect("E3D3_RPC");
        let (record_set, descriptor) = descriptor(&session);
        // The base is on this host's descriptor (so the set made again here
        // has the set hash the descriptor binds) and the nodes' chain.
        assert_eq!(
            one(&base, "descriptor"),
            hex(descriptor.canonical_bytes().as_bytes()),
            "E3D3_DESCRIPTOR"
        );
        let genesis = BitcoinInternalHash32::from_internal_bytes(regtest_genesis());
        let profile = NetworkProfile::parse(&unhex(one(&base, "profile")), genesis).unwrap();
        assert_eq!(profile.first_effective_height().value(), H0, "E3D3_H0");
        let context = ProofContext::new(
            substrate_context_hash(&descriptor),
            unhex32(one(&base, "custody_policy_hash")),
        );
        let supported = SupportedContext::new(profile, context).unwrap();
        // `common::v2_writer::wallet_on`'s identity values.
        let identity = LedgerIdentity::new([0x71; 32], 1, vec![supported], [0xa1; 32]).unwrap();
        let bytes = std::fs::read(handoff.join("budget.json")).expect("E3D3_BUDGET");
        let budget = admit_budget_record(
            Some(&bytes),
            bitagi_hash::sha256(&bytes),
            &BudgetFreezeContext {
                substrate: descriptor.network(),
                profile_sha256: *profile.profile_sha256().as_array(),
            },
        )
        .expect("E3D3_BUDGET");
        assert_eq!(
            hex(budget.sha256()),
            one(&base, "budget_record_sha256"),
            "E3D3_BUDGET"
        );
        let host = dir.join("host");
        let config = HostConfig {
            profile,
            descriptor,
            record_set,
            ledger_path: handoff.join("wallet.sqlite"),
            ledger_identity: identity,
            state_dir: host.join("state"),
            offhost_record_out: host.join("records").join("record-out.bin"),
            offhost_record_in: host.join("record-in.bin"),
            sign_outbox: Some(dir.join("outbox")),
            step6_outbox: None,
        };
        Self {
            dir,
            config,
            budget,
            base,
            public,
            session,
            base_file: handoff.join("base.txt"),
            launch_id: LAUNCH_CANDIDATE,
            events: std::cell::RefCell::new(event_lines()),
        }
    }

    fn host_dir(&self) -> PathBuf {
        self.dir.join("host")
    }

    fn wallet_candidate(&self) -> [u8; 32] {
        unhex32(one(&self.public, "wallet_candidate"))
    }

    fn approval_id(&self) -> [u8; 32] {
        unhex32(one(&self.public, "approval_id"))
    }

    fn instance(&self) -> [u8; 32] {
        ReservationLedger::open_read_only(&self.config.ledger_path, &self.config.ledger_identity)
            .unwrap()
            .wallet_instance_id()
            .unwrap()
    }

    /// The agreed tip of both nodes.
    fn tip(&self) -> (u64, [u8; 32]) {
        let height = agreed(&self.session, |n| n.get_block_count().unwrap());
        let hash = agreed(&self.session, |n| n.get_best_block_hash().unwrap());
        (height, hash)
    }

    /// The operator's candidate file, with the retained bytes once signed.
    fn write_candidates(&self, signed: Option<&VerifiedOfflineExport>) -> PathBuf {
        let p = &self.public;
        let (signed_hex, retained) = match signed {
            None => ("-".to_owned(), "-".to_owned()),
            Some(e) => (
                hex(e.raw_bytes()),
                [
                    hex(&SIGNED_FINAL_RECORD),
                    hex(e.raw_tx_sha256()),
                    hex(e.txid_internal()),
                    hex(e.wtxid_internal()),
                    hex(e.approval_id()),
                    hex(e.signing_authority_id()),
                ]
                .join(" "),
            ),
        };
        let line = [
            one(p, "wallet_candidate").to_owned(),
            hex(&LAUNCH_CANDIDATE),
            "opening".to_owned(),
            one(p, "approval_id").to_owned(),
            one(p, "approval_subject").to_owned(),
            one(p, "approval_session").to_owned(),
            one(p, "approval_actor").to_owned(),
            one(p, "reservation").to_owned(),
            hex(self.budget.sha256()),
            H0.to_string(),
            // The tip the charge was built on: H0 − 1 in rn-1, below it in
            // rn-2 (the base states the tip the host signs at instead).
            one(p, "constructed").to_owned(),
            "-".to_owned(),
            one(p, "unsigned").to_owned(),
            signed_hex,
            retained,
        ]
        .join(" ");
        let path = self.host_dir().join("candidates.txt");
        write_private(
            &path,
            format!("BITAGI-LAUNCH-HOST-CANDIDATES-V4\n{line}\n").as_bytes(),
        );
        path
    }

    /// Phase 2's start: the host files at H0 − 1, and the operator's copy
    /// of the generation-0 record. #484 L0: below H0 − 1 the floor block
    /// does not exist yet, so the host is made with U
    /// (`init_before_floor`).
    fn init(&self) {
        let host = self.host_dir();
        for (dir, mode) in [(host.join("state"), 0o700), (host.join("records"), 0o700)] {
            std::fs::create_dir(&dir).unwrap();
            std::fs::set_permissions(&dir, std::fs::Permissions::from_mode(mode)).unwrap();
        }
        if self.tip().0 < H0 - 1 {
            LaunchHost::init_before_floor(&self.config).expect("E3D3_HOST_INIT");
        } else {
            let (a, _) = self.session.nodes();
            let floor = a.get_block_hash(H0 - 1).expect("E3D3_FLOOR");
            LaunchHost::init(&self.config, internal(floor)).expect("E3D3_HOST_INIT");
        }
        self.present_latest_record();
    }

    /// #484 L0: the replay store's tip, read through a read-only handle
    /// (nothing is written).
    fn store_tip(&self) -> (u64, [u8; 32]) {
        let deployment = deployment_id(&self.config.profile);
        let store = bitagi_store::SqliteStore::open_read_only_for_context(
            self.config.state_dir.join(bitagi_launch_host::REPLAY_STORE),
            bitagi_store::StoreContextBinding::new(
                deployment,
                substrate_context_hash(&self.config.descriptor),
                self.config.descriptor.genesis_hash(),
            )
            .unwrap(),
        )
        .expect("E3D3_STORE");
        let snapshot = store.snapshot(deployment).expect("E3D3_STORE");
        (
            snapshot.as_of_height().value(),
            snapshot.as_of_block_hash().into_internal_bytes(),
        )
    }

    fn present_latest_record(&self) {
        std::fs::copy(
            &self.config.offhost_record_out,
            &self.config.offhost_record_in,
        )
        .unwrap();
    }

    /// One production turn by a freshly started host, as a restart does.
    fn turn(
        &self,
        candidates: &Path,
        authority: Option<&Path>,
        export: Option<&Path>,
        transport: Option<&mut ProductTransport>,
        comparison: Option<&PrestateComparison>,
    ) -> Result<TurnReport, bitagi_launch_host::HostError> {
        self.turn_with(candidates, authority, export, transport, comparison, || {
            self.procedure()
        })
    }

    /// [`Launch::turn`] with the procedure the operator presents made by
    /// `procedure`, at the same point of the turn: B-Q17c-2's release
    /// turn gives a V2 file with its step-6 documents.
    fn turn_with(
        &self,
        candidates: &Path,
        authority: Option<&Path>,
        export: Option<&Path>,
        transport: Option<&mut ProductTransport>,
        comparison: Option<&PrestateComparison>,
        procedure: impl FnOnce() -> Option<bitagi_launch_host::procedure::OperatorProcedure>,
    ) -> Result<TurnReport, bitagi_launch_host::HostError> {
        let entries = self
            .config
            .load_candidates(candidates)
            .expect("E3D3_CANDIDATES");
        let authority = authority.map(|p| self.config.load_authority(p).expect("E3D3_AUTHORITY"));
        let outbox = self.config.sign_outbox().expect("E3D3_OUTBOX");
        let base = self
            .config
            .load_sign_base(&self.base_file)
            .expect("E3D3_BASE");
        let export = export.map(|p| self.config.load_export(p).expect("E3D3_EXPORT"));
        let resolution = self.resolution();
        let procedure = procedure();
        let replay = replay_comparison(self);
        // 1e-2a: a start that refuses is the turn's result (`e_dead`).
        let mut host = LaunchHost::start(self.config.clone())?;
        if let Some(lines) = self.events.borrow_mut().take() {
            host.set_event_lines(lines);
        }
        // A session of its own per turn, as the host's phases open theirs
        // (1D3 `:1464-1468`): one session's call bound does not cover
        // several catch-up turns of the follower (B, Q-rn2-3).
        let session = RpcSession::replay(ports(), RPC_CALLS, RPC_TIME).expect("E3D3_RPC");
        let (a, b) = session.nodes();
        let mut hand_offs = HandOffs {
            sign_outbox: outbox.as_ref(),
            sign_base: Some(&base),
            export: export.as_ref(),
            transport: transport.map(|t| t as &mut bitagi_launch_host::broadcast::Transport<'_>),
            prestate: Some(PrestateHandOff {
                outbox: outbox.as_ref().expect("E3D3_OUTBOX"),
                comparison,
            }),
            // B-692b P2a: the replay comparison's outbox is the same.
            replay_comparison: Some(ReplayHandOff {
                outbox: outbox.as_ref().expect("E3D3_OUTBOX"),
                comparison: replay.as_ref(),
                refusal: None,
            }),
        };
        let report = host.step_with_hand_offs(
            &a,
            &b,
            &TurnInputs {
                budget: &self.budget,
                candidates: &entries,
                resolution: resolution.as_ref(),
                procedure: procedure.as_ref(),
                authority: authority.as_ref(),
            },
            &mut hand_offs,
        );
        *self.events.borrow_mut() = host.take_event_lines();
        drop(host);
        self.present_latest_record();
        report
    }

    /// Whether a line write failed in this process (reported, never a
    /// turn error).
    fn lines_failed(&self) -> bool {
        self.events
            .borrow()
            .as_ref()
            .is_some_and(EventLines::failed)
    }

    /// #440: while a CriticalHeight68 lock is open, the operator's TDS 14.7
    /// resolution file for that occurrence (Class T values), as the host
    /// reads it (`HostConfig::load_resolution`, the strict read since
    /// B-SR); otherwise none is presented.
    fn resolution(&self) -> Option<bitagi_launch_host::resolution::OperatorResolution> {
        let lock = ReservationLedger::open_read_only(
            &self.config.ledger_path,
            &self.config.ledger_identity,
        )
        .unwrap()
        .locks()
        .unwrap()
        .locks
        .into_iter()
        .find(|l| l.reason == LockReason::CriticalHeight68 && l.released.is_none())?;
        let path = self.host_dir().join("resolution.txt");
        write_private(
            &path,
            format!(
                "format=BITAGI-LAUNCH-HOST-RESOLUTION-V1\nresolution_sha256={}\nrebuilt_pair=-\nincident={}\nraised_event={}\n",
                hex(&RESOLUTION_RECORD),
                hex(&lock.incident_sha256),
                lock.raised_event
            )
            .as_bytes(),
        );
        Some(self.config.load_resolution(&path).expect("E3D3_RESOLUTION"))
    }

    /// 1e-2a: the operator's TDS 6.7 procedure file (#450 runbook §2), when
    /// one is in place (`write_procedure`; the driver removes it after its
    /// release), as the host reads it (`HostConfig::load_procedure`, the
    /// strict read since B-Q17b-2 Q6).
    fn procedure(&self) -> Option<bitagi_launch_host::procedure::OperatorProcedure> {
        let path = self.host_dir().join("procedure.txt");
        path.exists().then(|| {
            self.config
                .load_procedure(&path, None)
                .expect("E3D3_PROCEDURE")
        })
    }

    /// 1e-2a: the operator's copy of a reorg the hook raised (#450 runbook
    /// §2 item 1): the identity, the incident and the ancestor, in the
    /// procedure file's own lines. The host file does not hold them.
    fn save_reorg_copy(&self, seen: &bitagi_launch_host::hooks::ReorgSeen) {
        let ancestor = seen.ancestor.expect("E3D3_REORG_ANCESTOR");
        let at_local = match seen.identity.at_local {
            AtLocal::Agreed(hash) => hex(&hash),
            AtLocal::Below => "below".to_owned(),
        };
        let text = format!(
            "incident={}\nwatermark_event={}\nlocal_height={}\nlocal_hash={}\nagreed_at_local={at_local}\nancestor_height={}\nancestor_hash={}\n",
            hex(&seen.incident),
            ancestor.watermark_event,
            seen.identity.local.0,
            hex(&seen.identity.local.1),
            ancestor.height,
            hex(&ancestor.hash),
        );
        write_private(&self.host_dir().join("reorg-copy.txt"), text.as_bytes());
    }

    /// #471 E-B3 (Q8-ㄱ): the copy of the `Below` reorg E-B raised, which
    /// no turn reported (E-B ended `TipBelowReplayFloor`): its identity is
    /// the store's tip before it, the nodes' tip now (H0 − 1, X′), with no
    /// agreed hash, and its watermark is the ledger's. The file names the
    /// identity's local tip as the ancestor (#450 runbook §2).
    fn save_below_copy(&self) {
        let (height, hash) = self.tip();
        let identity = bitagi_launch::reorg::NonExtending {
            local: (height, hash),
            at_local: AtLocal::Below,
        };
        let watermark = reorg_watermark(self).expect("E3D3_BELOW_WATERMARK");
        assert_eq!(watermark.1, identity.incident(), "E3D3_BELOW_INCIDENT");
        let text = format!(
            "incident={}\nwatermark_event={}\nlocal_height={height}\nlocal_hash={}\nagreed_at_local=below\nancestor_height={height}\nancestor_hash={}\n",
            hex(&watermark.1),
            watermark.0,
            hex(&hash),
            hex(&hash),
        );
        write_private(&self.host_dir().join("reorg-copy.txt"), text.as_bytes());
    }

    /// 1e-2a: the procedure file from the saved copy (#450 runbook §2 items
    /// 2-3): a TEST_ONLY Class T procedure record's digest, step 6 not
    /// performed (1D3 Q17).
    fn write_procedure(&self) {
        self.write_procedure_with(PROCEDURE_RECORD);
    }

    /// D3a-2b-2a: `write_procedure` with the digest of `record` (the set worker's TEST_ONLY release
    /// record, `SET_RELEASE_RECORD`).
    fn write_procedure_with(&self, record: &[u8]) {
        let copy = std::fs::read_to_string(self.host_dir().join("reorg-copy.txt"))
            .expect("E3D3_REORG_COPY");
        let record = bitagi_hash::sha256(record);
        let text = format!(
            "format=BITAGI-LAUNCH-HOST-REORG-PROCEDURE-V1\nprocedure_sha256={}\n{copy}step6=not-performed\n",
            hex(&record)
        );
        write_private(&self.host_dir().join("procedure.txt"), text.as_bytes());
    }

    /// 1e-2a: the SHA-256 of the host file and of the replay store, each
    /// with its sidecars, to show a turn wrote neither (`e_below`).
    fn state_files(&self) -> [[u8; 32]; 2] {
        [HOST_FILE, bitagi_launch_host::REPLAY_STORE].map(|name| {
            let mut bytes = Vec::new();
            for suffix in ["", "-journal", "-wal", "-shm"] {
                let path = self.config.state_dir.join(format!("{name}{suffix}"));
                if let Ok(content) = std::fs::read(&path) {
                    bytes.extend_from_slice(suffix.as_bytes());
                    bytes.extend_from_slice(&content);
                }
            }
            bitagi_hash::sha256(&bytes)
        })
    }

    /// A signing authorization file for the wait on `checks_id`.
    fn signing_file(&self, checks_id: [u8; 32]) -> PathBuf {
        let text = format!(
            "schema=BITAGI_LAUNCH_HOST_SIGNING_AUTHORIZATION_V1\ndeployment_id={}\nwallet_instance_id={}\nwallet_candidate={}\nlaunch_candidate={}\nchecks_id={}\napproval_id={}\nauthority_actor={}\nend\n",
            hex(deployment_id(&self.config.profile).as_array()),
            hex(&self.instance()),
            hex(&self.wallet_candidate()),
            hex(&self.launch_id),
            hex(&checks_id),
            hex(&self.approval_id()),
            hex(&SIGNING_ACTOR),
        );
        let path = self.host_dir().join("authority-sign.txt");
        write_private(&path, text.as_bytes());
        path
    }

    /// A broadcast authorization file for the wait on `prebroadcast_id`,
    /// naming the export's bytes and receipt.
    fn broadcast_file(&self, prebroadcast_id: [u8; 32], e: &VerifiedOfflineExport) -> PathBuf {
        let text = format!(
            "schema=BITAGI_LAUNCH_HOST_BROADCAST_AUTHORIZATION_V1\ndeployment_id={}\nwallet_instance_id={}\nwallet_candidate={}\nlaunch_candidate={}\nprebroadcast_id={}\napproval_id={}\nsigning_authority_id={}\nauthority_actor={}\nraw_sha256={}\ntxid={}\nwtxid={}\nreservation={}\ndisplay_digest={}\nend\n",
            hex(deployment_id(&self.config.profile).as_array()),
            hex(&self.instance()),
            hex(&self.wallet_candidate()),
            hex(&self.launch_id),
            hex(&prebroadcast_id),
            hex(&self.approval_id()),
            hex(e.signing_authority_id()),
            hex(&BROADCAST_ACTOR),
            hex(e.raw_tx_sha256()),
            hex(e.txid_internal()),
            hex(e.wtxid_internal()),
            hex(e.reservation()),
            hex(e.display_digest()),
        );
        let path = self.host_dir().join("authority-broadcast.txt");
        write_private(&path, text.as_bytes());
        path
    }
}

/// The one candidate's verdict in `report`.
fn verdict(report: &TurnReport) -> ReadsVerdict {
    assert_eq!(report.decisions.len(), 1, "E3D3_DECISIONS");
    assert!(report.persisted.is_empty(), "E3D3_RAISED {report:?}");
    report.decisions[0].verdict
}

/// The act outcome of `report`, which must be the turn's act.
fn act(report: &TurnReport) -> ActOutcome {
    report.act.expect("E3D3_NO_ACT").outcome
}

/// The H0 − 1 prestate of this process: the outbox name of the Rust
/// receipt a `PrestateComparisonPending` turn wrote (`-` for none), and the
/// milliseconds its prestate turns took (the driver adds `produce` and
/// `compare` for the stage's wall clock).
fn report_prestate(done: &Done) {
    report(
        "prestate_receipt",
        &done.receipt.map_or_else(
            || done.replay_outbox.clone().unwrap_or_else(|| "-".to_owned()),
            |d| receipt_file_name(&d),
        ),
    );
    report("prestate_ms", &done.prestate_ms.to_string());
}

/// The steps the turns took, in order.
fn report_steps(steps: &[&str]) {
    report("steps", &steps.join(","));
}

/// The Python receipt and the report the driver made for this phase's
/// prestate comparison, read by the host's loader; `None` on a phase's
/// first run.
fn prestate_comparison(launch: &Launch) -> Option<PrestateComparison> {
    let receipt = std::env::var_os("BITAGI_E3D3_PRESTATE_RECEIPT");
    let report = std::env::var_os("BITAGI_E3D3_PRESTATE_REPORT");
    assert_eq!(receipt.is_some(), report.is_some(), "E3D3_PRESTATE_FILES");
    Some(
        launch
            .config
            .load_prestate_comparison(Path::new(&receipt?), Path::new(&report?))
            .expect("E3D3_PRESTATE_FILES"),
    )
}

/// B-692b P2a: the Python result and the `step6-compare` report the driver
/// made for this phase's replay comparison, and the outbox it was made
/// from, read by the host's loader; `None` on a phase's first run.
fn replay_comparison(launch: &Launch) -> Option<ReplayComparison> {
    let outbox = std::env::var("BITAGI_E3D3_REPLAY_OUTBOX").ok();
    let result = std::env::var_os("BITAGI_E3D3_REPLAY_RESULT");
    let report = std::env::var_os("BITAGI_E3D3_REPLAY_REPORT");
    assert!(
        outbox.is_some() == result.is_some() && result.is_some() == report.is_some(),
        "E3D3_REPLAY_FILES"
    );
    Some(
        launch
            .config
            .load_replay_comparison(&outbox?, Path::new(&result?), Path::new(&report?))
            .expect("E3D3_REPLAY_FILES"),
    )
}

/// The variant name of a journal record.
fn record_name(record: &Record) -> String {
    let text = format!("{record:?}");
    text.split([' ', '{', '(']).next().unwrap_or("").to_owned()
}

fn listing(dir: &Path) -> Vec<String> {
    let mut names: Vec<String> = std::fs::read_dir(dir)
        .unwrap()
        .map(|e| e.unwrap().file_name().into_string().unwrap())
        .collect();
    names.sort();
    names
}

/// The export the offline stage handed on, verified against both nodes'
/// prevouts of its input.
fn verified_export(launch: &Launch) -> (PathBuf, VerifiedOfflineExport) {
    let export_dir = launch.dir.join("export");
    let names = listing(&export_dir);
    assert_eq!(names.len(), 1, "E3D3_EXPORT");
    let path = export_dir.join(&names[0]);
    let bytes = std::fs::read(&path).unwrap();
    let decoded = decode_offline_export(&mut bytes.as_slice(), bytes.len() as u64).unwrap();
    let (txid, vout) = one(&launch.base, "prevout_outpoint")
        .split_once(':')
        .expect("E3D3_PREVOUT");
    let (txid, vout) = (unhex32(txid), vout.parse::<u32>().unwrap());
    let coin = |n: &HttpRpcClient<'_>| {
        let coin = n
            .txout(txid, vout, PrevoutView::ChainOnly)
            .unwrap()
            .expect("E3D3_PREVOUT_UNSPENT");
        vec![bitcoin::TxOut {
            value: bitcoin::Amount::from_sat(coin.value_sat_u64),
            script_pubkey: bitcoin::ScriptBuf::from_bytes(coin.script_pubkey_bytes),
        }]
    };
    let (a, b) = launch.session.nodes();
    let verified = verify_offline_export(&decoded, &launch.config.profile, &coin(&a), &coin(&b))
        .expect("E3D3_VERIFY");
    (path, verified)
}

/// The operator's import (E3d), before the launch turns: a scope at the
/// agreed tip, then `Recorded`.
fn import(launch: &Launch, verified: &VerifiedOfflineExport) {
    let (height, tip) = launch.tip();
    let mut ledger = ReservationLedger::open_expected(
        &launch.config.ledger_path,
        launch.config.ledger_identity.clone(),
        Origin::TrustedLocalRestart,
    )
    .unwrap();
    let scope = ledger
        .reconcile(&[ReplayInput {
            context: launch.config.ledger_identity.supported_contexts()[0].id(),
            chain: ObservedChainContext::from_class_t_assertion(
                CoreHeight::new(height),
                BitcoinInternalHash32::from_internal_bytes(tip),
                SyncState::Synchronized,
                NodeAgreement::Agreed,
                true,
            ),
            canonical_state: &[],
        }])
        .expect("E3D3_RECONCILE");
    let imported = import_offline_export(&mut ledger, &scope, verified).expect("E3D3_IMPORT");
    assert_eq!(imported.outcome(), OfflineImportOutcome::Recorded);
}

// ---------------------------------------------------------------- phases

/// What a phase reads of the offline stage.
#[derive(Clone, Copy, PartialEq, Eq)]
enum Export {
    /// Nothing: the candidate is unsigned.
    Unsigned,
    /// The export, verified against both nodes and imported first.
    Import,
    /// The export, verified against both nodes (imported earlier).
    Verified,
    /// The candidate file an earlier phase wrote: the export's input is
    /// spent in the chain, so it cannot be verified again.
    Stored,
}

/// One worker run (A #258 issuecomment-6255049643 (iv) for the rn-2
/// cases): what it starts with, what the nodes answer and where it ends.
/// The driver changes the nodes between runs; every turn's step is
/// asserted here and again by the driver.
struct Phase {
    name: &'static str,
    /// `LaunchHost::init` first.
    init: bool,
    export: Export,
    /// The tip both nodes agree on, or `None` where the driver made them
    /// differ.
    tip: Option<u64>,
    /// What every `AdmitSignedFinal` of the phase records, node A first.
    admitted: [NodeAdmission; 2],
    /// What step 8's submission gets, node A first.
    submitted: [NodeSubmission; 2],
    /// The stop the refusal that ends the phase raises, if any.
    raises: Option<StopCode>,
    /// The phase's one turn may instead be refused at the reads while the
    /// follower catches up (`LocalTipUnconfirmed`, `DEEP`).
    catch_up: bool,
    /// 1e-2a: every turn of the phase writes no journal entry and moves the
    /// ledger by exactly this many events (step 0's writer open, and a
    /// raise or a release).
    ledger: Option<u64>,
    /// The step that ends the phase.
    last: &'static str,
}

const ACCEPTED: [NodeAdmission; 2] = [NodeAdmission::Accepted, NodeAdmission::Accepted];
const SENT: [NodeSubmission; 2] = [NodeSubmission::Accepted, NodeSubmission::Accepted];
const NODE_STOP: Option<StopCode> = Some(StopCode::NodeUnavailableOrDisagreeing);

const PHASES: [Phase; 7] = [
    // rn-1: the accept path, construction at the tip.
    Phase {
        name: "sign",
        init: true,
        export: Export::Unsigned,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "OfflineSignaturePending",
    },
    Phase {
        name: "broadcast",
        init: false,
        export: Export::Import,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "AwaitingInclusion",
    },
    // rn-2: one chain, construction below the tip. Node B's P2P is off.
    Phase {
        name: "inactive",
        init: true,
        export: Export::Unsigned,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "HostError:NetworkInactive",
    },
    // Node B on its own H0 − 1 block: step 1's follower ends on the tip
    // disagreement, and the bracket, with no receipt, confirms it (#440;
    // A #258 issuecomment-6283589369 Q-440-4). Step 4 records the
    // disagreement at H0 − 1 and the core raises the CriticalHeight68 lock
    // with the node stop (FOL-04, R10); the turn acts on nothing.
    Phase {
        name: "disagree",
        init: false,
        export: Export::Unsigned,
        tip: None,
        admitted: ACCEPTED,
        submitted: SENT,
        raises: NODE_STOP,
        catch_up: false,
        ledger: None,
        last: "Refuse:CriticalHeightDisagreed",
    },
    // Both nodes back on one chain: the operator's resolution releases the
    // CriticalHeight68 lock first, and the node stop is cleared on the
    // run's fresh checks.
    Phase {
        name: "cases_sign",
        init: false,
        export: Export::Unsigned,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "OfflineSignaturePending",
    },
    // No delta: the import, admitted on both nodes, the broadcast
    // authorized. No stop is open (#503: the rejections are on a pair of
    // their own, `BOUND_PHASES`).
    Phase {
        name: "admit",
        init: false,
        export: Export::Import,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "BroadcastAuthorized",
    },
    // The delta on node B again: step 8 reaches node A's mempool only.
    Phase {
        name: "broadcast_one",
        init: false,
        export: Export::Verified,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: [NodeSubmission::Accepted, NodeSubmission::Rejected],
        raises: None,
        catch_up: false,
        ledger: None,
        last: "AwaitingInclusion",
    },
];

/// After the driver mined H0 with the transaction (EffectiveFacts, A #258
/// issuecomment-6341101080 Q-F5; table set before the first run,
/// 6255049643 (iv)): the store's birth of the transaction at H0 and the
/// spend scan's own inclusion are the core's effective facts, so the turn
/// decides `Done(Born { H0, at_opening })`; H0 is not yet deep enough, so
/// step 9 marks nothing.
const INCLUDED: Phase = Phase {
    name: "included",
    init: false,
    export: Export::Stored,
    tip: Some(H0),
    admitted: ACCEPTED,
    submitted: SENT,
    raises: None,
    catch_up: false,
    ledger: None,
    last: "Done:Born",
};

/// Blocks the driver mines above H0 before `DEEP`: more than
/// `MAX_ANCESTRY_BLOCKS` (4,096), step 9's depth.
const DEEP_BLOCKS: u64 = 4_100;
/// After the driver mined `DEEP_BLOCKS` above H0 (A #258
/// issuecomment-6262177277 1, B's item 11): the included transaction's block
/// is deeper than step 9's depth, both nodes agree and the store holds it.
/// Since EffectiveFacts (Q-F5, table set before the first run) the turn
/// decides `Done(Born { H0, at_opening })` and step 9 marks the candidate's
/// journal final at floor H0: the launch window closes (no `LaunchWindow`
/// hold) and the charge is settled. The follower catches up first: a
/// process's one turn is then refused at the reads (`LocalTipUnconfirmed`),
/// raising and writing nothing, and the driver runs the phase again (one
/// turn per process: one RPC session's bounds do not cover several catch-up
/// turns).
const DEEP: Phase = Phase {
    name: "deep",
    init: false,
    export: Export::Stored,
    tip: Some(H0 + DEEP_BLOCKS),
    admitted: ACCEPTED,
    submitted: SENT,
    raises: None,
    catch_up: true,
    ledger: None,
    last: "Done:Born",
};

/// 1e-2a (B #258 issuecomment-6338425291, A issuecomment-6340182163): the
/// E scenarios at the H0 − 1 floor, on a third pair and chain, the charge
/// built at H0 − 2 as rn-2's. Nothing is sent: no phase has a transport or
/// the send credential (`launch_e_worker` refuses one). The first phase
/// reaches the H0 − 1 prestate, which the host compares as in rn-1's sign
/// phase (1d-3d-3d: its first run ends at `PrestateComparisonPending`, the
/// driver compares and runs it again). The driver runs `e_sign_again`
/// and `e_admit_again` twice each, and changes the nodes before
/// `e_replaced` (X → X′ at H0 − 1), `e_below` (X′ invalidated: tip H0 − 2)
/// and `e_dead` (X′ reconsidered). #471: `e_release` releases the floor
/// replacement's Reorg67 ((a)), and `e_release_below` E-B's `Below` one on
/// the unchanged local tip (Q8-ㄱ); after each, a new run at X′ compares
/// X′'s prestate the same way (`e_reask`, `e_reask_below`; A #258
/// issuecomment-6392274893 §1) and goes on to the new run's broadcast
/// authorization wait, where E2″'s file is not used.
const E_PHASES: [Phase; 11] = [
    // E-0: the accept path to the offline signature, the H0 − 1
    // comparison first.
    Phase {
        name: "e_sign",
        init: true,
        export: Export::Unsigned,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "OfflineSignaturePending",
    },
    // E6a-1: a new process at the signature wait: nothing new.
    Phase {
        name: "e_sign_again",
        init: false,
        export: Export::Unsigned,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: Some(1),
        last: "OfflineSignaturePending",
    },
    // E2″: the import, then to step 8, which has no transport.
    Phase {
        name: "e_admit",
        init: false,
        export: Export::Import,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "NotYet:Transport",
    },
    // E6a-2: a new process at step 8 with no transport.
    Phase {
        name: "e_admit_again",
        init: false,
        export: Export::Verified,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: Some(1),
        last: "NotYet:Transport",
    },
    // E3′-1: X replaced by X′ at H0 − 1. The hook raises Reorg67 and binds
    // the ancestor (H0 − 1, X′); the core refuses on the lock.
    Phase {
        name: "e_replaced",
        init: false,
        export: Export::Verified,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: Some(2),
        last: "Refuse:Locked(Reorg67)",
    },
    // E3′-2 (#471 (a)): the procedure file from E3′-1's copy names the
    // floor's ancestor (H0 − 1, X′); the core releases the lock.
    Phase {
        name: "e_release",
        init: false,
        export: Export::Verified,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: Some(3),
        last: "ReleaseReorg67",
    },
    // E3′-3: the file removed; a new run at X′, which compares X′'s
    // prestate (first run pending), records it and goes to the broadcast
    // authorization wait. Its ledger count was one event a turn and its
    // last step `ComparePrestate` (c94d9ced, a host that did not perform
    // the comparison; A #258 issuecomment-6392274893 §1); its turns now
    // write journal entries.
    Phase {
        name: "e_reask",
        init: false,
        export: Export::Verified,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "BroadcastAuthorityRequired",
    },
    // E-B: the tip below the floor. The hook raises Reorg67 (Below), then
    // the follower ends with no ancestor.
    Phase {
        name: "e_below",
        init: false,
        export: Export::Verified,
        tip: Some(H0 - 2),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: Some(2),
        last: "HostError:Sync(TipBelowReplayFloor)",
    },
    // E-B2 (#471 Q8-ㄱ): X′ back; the start passes, the core refuses on the
    // open lock.
    Phase {
        name: "e_dead",
        init: false,
        export: Export::Verified,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: Some(1),
        last: "Refuse:Locked(Reorg67)",
    },
    // E-B3 (#471 Q8-ㄱ): the file names the identity's local tip
    // (H0 − 1, X′); the core releases the lock.
    Phase {
        name: "e_release_below",
        init: false,
        export: Export::Verified,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: Some(3),
        last: "ReleaseReorg67",
    },
    // E-B4: the file removed; a new run at X′ again (E-B's raise moved the
    // epoch), as E3′-3. Was as E3′-3's.
    Phase {
        name: "e_reask_below",
        init: false,
        export: Export::Verified,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "BroadcastAuthorityRequired",
    },
];

/// #484 L0 (module docs): the Sign hand-off in the signing window, on a
/// fourth pair and chain, the charge built and signed at H0 − 2. The first
/// phase makes the host with U (`Launch::init` below H0 − 1); the driver
/// mines H0 − 1 before the last, whose first run ends at the H0 − 1
/// comparison (1d-3d-3d), as rn-1's sign phase does.
const L0_PHASES: [Phase; 3] = [
    // The pre-floor turns at H0 − 2 to the hand-off.
    Phase {
        name: "l0_sign",
        init: true,
        export: Export::Unsigned,
        tip: Some(H0 - 2),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "OfflineSignaturePending",
    },
    // The operator's import at H0 − 2, then the wait for H0 − 1.
    Phase {
        name: "l0_wait",
        init: false,
        export: Export::Import,
        tip: Some(H0 - 2),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "SignedAwaitingOpeningGate",
    },
    // H0 − 1: the floor anchored, the prestate, then step 8; no Sign.
    Phase {
        name: "l0_broadcast",
        init: false,
        export: Export::Verified,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "AwaitingInclusion",
    },
];

/// #503 (FD-CT-62; the unit note's §7.3): the per-tip bound on real
/// nodes, on a fifth pair and chain, charged at H0 − 2 as rn-2's, the host
/// turning at H0 − 1. The Opening is admitted only at H0 − 1, so the
/// rejections that bound the candidate there cannot share the cases'
/// chain. `bound_sign` is rn-1's sign phase (no stop is open). In
/// `reject_both` both nodes reject the admission (a negative fee delta)
/// and the core raises the node stop: one counted failure at the tip,
/// `MAX_FAILED_ATTEMPTS_AT_TIP`. In `bounded` the driver took the deltas
/// back, so both nodes would admit the transaction, but at the same
/// H0 − 1 every act is refused (`FailedAttemptsAtTip`): no raise, no act,
/// the stop still open, and each of its `BOUND_TURNS` turns writes no
/// journal entry and moves the ledger by step 0's writer open only. The
/// driver runs it in more than one process.
const BOUND_PHASES: [Phase; 3] = [
    Phase {
        name: "bound_sign",
        init: true,
        export: Export::Unsigned,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "OfflineSignaturePending",
    },
    Phase {
        name: "reject_both",
        init: false,
        export: Export::Import,
        tip: Some(H0 - 1),
        admitted: [NodeAdmission::Rejected, NodeAdmission::Rejected],
        submitted: SENT,
        raises: NODE_STOP,
        catch_up: false,
        ledger: None,
        last: "Refuse:AdmissionRejected",
    },
    Phase {
        name: "bounded",
        init: false,
        export: Export::Verified,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: Some(1),
        last: "Refuse:FailedAttemptsAtTip",
    },
];

/// The turns one `bounded` process takes, each refused.
const BOUND_TURNS: usize = 3;

/// R2-b (e) (B #258 issuecomment-6354631934, A -6354752175 Q-R2b-3 (가)):
/// the literal R2 on real nodes, on a sixth pair and chain, charged at
/// H0 − 2 as rn-2's under a `CONTINUE_WITHIN_LIMITS` budget (the signer's
/// `launch_continue_charge_stage_worker`), the host turning at H0 − 1.
/// `r2b_sign` is rn-1's sign phase; `r2b_wait` is the import at H0 − 1 and
/// the run to its broadcast authorization wait, where no authorization is
/// written (nothing may be sent below H0). The driver then mines H0 with
/// no transaction: in `r2b_missed` the miss raises nothing under the
/// continue budget, the run starts again at H0 (its checks, admission and
/// prebroadcast checks), the operator authorizes the broadcast, and step 8
/// submits to both nodes (A8-M9's real-node kill: at H0 the ledger refuses a
/// reconcile with no state). The driver mines H0 + 1 with the transaction
/// (the gate is still H0): `r2b_included` is `Done(Born { H0 + 1,
/// at_opening: false })`. The table is the driver's `R2B_STEPS`, committed
/// before the first run.
const R2B_PHASES: [Phase; 4] = [
    Phase {
        name: "r2b_sign",
        init: true,
        export: Export::Unsigned,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "OfflineSignaturePending",
    },
    Phase {
        name: "r2b_wait",
        init: false,
        export: Export::Import,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "BroadcastAuthorityRequired",
    },
    Phase {
        name: "r2b_missed",
        init: false,
        export: Export::Verified,
        tip: Some(H0),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "AwaitingInclusion",
    },
    Phase {
        name: "r2b_included",
        init: false,
        export: Export::Stored,
        tip: Some(H0 + 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "Done:Born",
    },
];

/// 1e-2b-2a (B #258 issuecomment-6537897575 §3, A -6538196742 Q3, Q4, Q6):
/// the L0 chain past H0 − 1, run by `launch_l0_worker` after
/// `L0_PHASES`. The driver mines G = H0 with the transaction before
/// `l0_born` (E4-a: `Born { H0, at_opening: true }`, the opening block not
/// missed, no act); invalidates G on both nodes before `l0_reorged` (E9-a:
/// the hook raises Reorg67, local (H0, G) agreed below it, ancestor
/// (H0 − 1, X); the core refuses on the open lock); `l0_release` presents
/// the procedure file from that copy, step 6 not performed (A Q4);
/// `l0_waiting` (E9-b) has the transport while the transaction waits in
/// both mempools and hands nothing off; the driver mines a new H0 block
/// with the transaction before `l0_reborn` (E9-c: born again, the journal
/// kept). On every one of these turns the journal holds exactly one
/// `Submitted` and one `SigningHandedOff`. The table is the driver's
/// `L0T_STEPS`, committed before the first run.
const L0T_PHASES: [Phase; 5] = [
    Phase {
        name: "l0_born",
        init: false,
        export: Export::Stored,
        tip: Some(H0),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "Done:Born",
    },
    Phase {
        name: "l0_reorged",
        init: false,
        export: Export::Stored,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: Some(2),
        last: "Refuse:Locked(Reorg67)",
    },
    Phase {
        name: "l0_release",
        init: false,
        export: Export::Stored,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: Some(3),
        last: "ReleaseReorg67",
    },
    Phase {
        name: "l0_waiting",
        init: false,
        export: Export::Stored,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "AwaitingInclusion",
    },
    Phase {
        name: "l0_reborn",
        init: false,
        export: Export::Stored,
        tip: Some(H0),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "Done:Born",
    },
];

/// 1e-2b-2a's E8 variant (1E E8, T2-8): R2-b's charge under the continue
/// budget on a seventh pair and chain, run by `launch_case_worker`.
/// `e8_sign` is rn-1's sign phase; the host does not turn at H0 − 1 after
/// the signature: `e8_import` is the operator's import alone (dated
/// 2026-10-31: the harness's import cannot run above H0 − 1). The driver
/// mines H0 and the blocks to H0 + `E8_LATE` with no transaction:
/// `e8_late` makes new execution
/// checks, the admission on both nodes and a new `BroadcastAuthorized`
/// (R32) at that tip, then step 8 submits to both nodes; every decision
/// reports the opening block missed with no outcome. The driver mines the
/// next block with the transaction: `e8_included` is
/// `Born { H0 + E8_LATE + 1, at_opening: false }`. The table is the
/// driver's `E8_STEPS`, committed before the first run.
const E8_PHASES: [Phase; 4] = [
    Phase {
        name: "e8_sign",
        init: true,
        export: Export::Unsigned,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "OfflineSignaturePending",
    },
    // Dated 2026-10-31 (after the first run): the operator's import at
    // H0 − 1, no host turn (`run_phase`).
    Phase {
        name: "e8_import",
        init: false,
        export: Export::Import,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "Imported",
    },
    Phase {
        name: "e8_late",
        init: false,
        export: Export::Verified,
        tip: Some(H0 + E8_LATE),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "AwaitingInclusion",
    },
    Phase {
        name: "e8_included",
        init: false,
        export: Export::Stored,
        tip: Some(H0 + E8_LATE + 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "Done:Born",
    },
];

/// The blocks above H0 before `e8_late` (the driver's `E8_LATE`).
const E8_LATE: u64 = 1;

/// B-692a-RT (finding #692; unit note `2026-11-04_b-692a-rt.md`): B-692a's
/// late prestate path on real nodes, on a tenth pair and chain, run by
/// `launch_l0_worker`, charged at H0 − 2 under the continue budget.
/// `l0late_sign` and `l0late_wait` are L0's window phases (the host made
/// with U, the Sign at H0 − 2 with no prestate step, the operator's import
/// at H0 − 2). The host does not turn again while the driver mines H0 − 1
/// and H0 to H0 + `L0_LATE` with no transaction. In `l0late_broadcast` the
/// first run ends at the late `ComparePrestate` of block H0 − 1 (the Rust
/// receipt in the outbox, nothing recorded); the driver reads block H0 − 1
/// by its height on both nodes and compares; the second run records the
/// comparison and the INITIAL_PRESTATE at the run's tip, naming block
/// H0 − 1 (host journal tags 14 and 15), makes new checks, the admission
/// and a new authorization at that tip, and submits. The driver mines the
/// next block with the transaction: `l0late_included` is
/// `Born { H0 + L0_LATE + 1, at_opening: false }`, the two late rows read
/// back from the host file it opens. The table is the driver's
/// `L0LATE_STEPS`, committed before the first run.
const L0L_PHASES: [Phase; 4] = [
    Phase {
        name: "l0late_sign",
        init: true,
        export: Export::Unsigned,
        tip: Some(H0 - 2),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "OfflineSignaturePending",
    },
    Phase {
        name: "l0late_wait",
        init: false,
        export: Export::Import,
        tip: Some(H0 - 2),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "SignedAwaitingOpeningGate",
    },
    Phase {
        name: "l0late_broadcast",
        init: false,
        export: Export::Verified,
        tip: Some(H0 + L0_LATE),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "AwaitingInclusion",
    },
    Phase {
        name: "l0late_included",
        init: false,
        export: Export::Stored,
        tip: Some(H0 + L0_LATE + 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "Done:Born",
    },
];

/// The blocks above H0 before `l0late_broadcast` (the driver's `L0_LATE`).
/// Three, as the host cell C7 (`prestate_tests.rs`): block H0 − 1 is then
/// neither the tip nor the tip's parent, so a read of the tip, or of
/// height tip − 1, gives another block; and the first turn after the
/// window replays four blocks from U.
const L0_LATE: u64 = 3;

/// The births after H0 (their opening block missed).
const MISSED_BIRTHS: [&str; 3] = ["r2b_included", "e8_included", "l0late_included"];

/// The late phases (B-692a-RT): at and above H0.
fn l0_late(phase: &Phase) -> bool {
    L0L_PHASES[2..].iter().any(|p| p.name == phase.name)
}

/// The block a prestate step names: block H0 − 1 as both nodes give it by
/// its height. On the H0 − 1 path it is the run's tip; on B-692a-RT's late
/// path the tip is H0 + `L0_LATE`, above it.
fn check_prestate_block(launch: &Launch, phase: &Phase, block: AgreedTip) {
    assert_eq!(block.height, H0 - 1, "E3D3_PRESTATE_HEIGHT");
    let tip = launch.tip();
    if l0_late(phase) {
        let floor = agreed(&launch.session, |n| n.get_block_hash(H0 - 1).unwrap());
        assert_eq!(block.hash, floor, "E3D3_LATE_PRESTATE_BLOCK");
        assert_eq!(tip.0, H0 + L0_LATE, "E3D3_LATE_PRESTATE_TIP");
        assert_ne!(tip.1, block.hash, "E3D3_LATE_PRESTATE_TIP");
    } else {
        assert_eq!(tip, (block.height, block.hash), "E3D3_PRESTATE_TIP");
    }
}

/// B-692a-RT: the late comparison and INITIAL_PRESTATE, read back from the
/// host file this process opened: exactly one of each in the journal, both
/// made at the run's tip H0 + `L0_LATE` and naming block H0 − 1 read by the
/// entry's own node pair (so stored as tags 14 and 15: an entry whose block
/// is its tip keeps tags 1 and 2), the INITIAL naming the comparison. Read
/// through the records' text, as `record_name` does: no file in `tests/`
/// names the prestate records.
fn check_late_rows(launch: &Launch) {
    let floor = agreed(&launch.session, |n| n.get_block_hash(H0 - 1).unwrap());
    let rows: Vec<Entry> = journal(launch)
        .into_iter()
        .filter(|e| record_name(&e.record).contains("Prestate"))
        .collect();
    let names: Vec<String> = rows.iter().map(|e| record_name(&e.record)).collect();
    assert_eq!(
        names,
        ["PrestateCompared", "InitialPrestateRecorded"],
        "E3D3_LATE_ROWS"
    );
    for row in &rows {
        assert_eq!(row.at.height, H0 + L0_LATE, "E3D3_LATE_ROW_AT {row:?}");
        let block = AgreedTip {
            height: H0 - 1,
            hash: floor,
            node_pair: row.at.node_pair,
        };
        let text = format!("{:?}", row.record);
        assert!(
            text.contains(&format!("block: {block:?}")),
            "E3D3_LATE_ROW_BLOCK {text}"
        );
    }
    let initial = format!("{:?}", rows[1].record);
    assert!(
        initial.contains(&format!("comparison_id: {:?}", rows[0].id)),
        "E3D3_LATE_INITIAL_LINK {initial}"
    );
}

/// 1e-2b-2b (unit note `2026-11-01_1e-2b-2b.md` §2; A #258
/// issuecomment-6539879887): lost gates and reorged rungs, run by
/// `launch_lost_worker`. Every budget is `CONTINUE_WITHIN_LIMITS`. A
/// competitor (D2-1's generator, handed to D1's miner by the driver) is
/// born at G = H0 where P0 was not mined: P0's decision is
/// `Refuse(GateAdvanced)` with `Stale` reported (machine.rs `effective`
/// checks `stale` before a pending wait), and P0 mined later is
/// `IncludedNoEffect`. The tables are the driver's `E10_STEPS`, `E7_STEPS`
/// and `L0D_STEPS`, committed before the first run.
const fn lost(
    name: &'static str,
    init: bool,
    export: Export,
    tip: u64,
    ledger: Option<u64>,
    last: &'static str,
) -> Phase {
    Phase {
        name,
        init,
        export,
        tip: Some(tip),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger,
        last,
    }
}

/// §2.1 E10 then E10-s (the eighth pair).
const E10_PHASES: [Phase; 7] = [
    lost(
        "e10_sign",
        true,
        Export::Unsigned,
        H0 - 1,
        None,
        "OfflineSignaturePending",
    ),
    lost(
        "e10_broadcast",
        false,
        Export::Import,
        H0 - 1,
        None,
        "AwaitingInclusion",
    ),
    lost(
        "e10_lost",
        false,
        Export::Stored,
        H0,
        None,
        "Refuse:GateAdvanced",
    ),
    lost(
        "e10_included",
        false,
        Export::Stored,
        H0 + 1,
        None,
        "Done:IncludedNoEffect",
    ),
    lost(
        "e10s_reorged",
        false,
        Export::Stored,
        H0 - 1,
        Some(2),
        "Refuse:Locked(Reorg67)",
    ),
    lost(
        "e10s_release",
        false,
        Export::Stored,
        H0 - 1,
        Some(3),
        "ReleaseReorg67",
    ),
    lost(
        "e10s_same",
        false,
        Export::Stored,
        H0,
        None,
        "Done:IncludedNoEffect",
    ),
];

/// §2.2 E7 and E7b in one flow (the ninth pair). `e7_broadcast` reaches
/// node A through 1e-2b-1 L4's proxy (`BITAGI_E3D3_ANSWER_PROXY=A`).
const E7_PHASES: [Phase; 7] = [
    lost(
        "e7_sign",
        true,
        Export::Unsigned,
        H0 - 1,
        None,
        "OfflineSignaturePending",
    ),
    lost(
        "e7_broadcast",
        false,
        Export::Import,
        H0 - 1,
        None,
        "AwaitingInclusion",
    ),
    lost(
        "e7_reorged",
        false,
        Export::Stored,
        H0 - 1,
        Some(2),
        "Refuse:Locked(Reorg67)",
    ),
    lost(
        "e7_release",
        false,
        Export::Stored,
        H0 - 1,
        Some(3),
        "ReleaseReorg67",
    ),
    // Dated 2026-10-31 (after the first run): a new authorization asked.
    lost(
        "e7_waiting",
        false,
        Export::Stored,
        H0 - 1,
        None,
        "BroadcastAuthorityRequired",
    ),
    lost(
        "e7_lost",
        false,
        Export::Stored,
        H0,
        None,
        "Refuse:GateAdvanced",
    ),
    lost(
        "e7_included",
        false,
        Export::Stored,
        H0 + 1,
        None,
        "Done:IncludedNoEffect",
    ),
];

/// §2.3 E9-d (the L0 chain after `l0_reborn`).
const L0D_PHASES: [Phase; 3] = [
    lost(
        "l0_lost_reorged",
        false,
        Export::Stored,
        H0 - 1,
        Some(2),
        "Refuse:Locked(Reorg67)",
    ),
    lost(
        "l0_lost_release",
        false,
        Export::Stored,
        H0 - 1,
        Some(3),
        "ReleaseReorg67",
    ),
    lost(
        "l0_lost",
        false,
        Export::Stored,
        H0,
        None,
        "Refuse:GateAdvanced",
    ),
];

/// The 1e-2b-2b phases a turn of which is given the transport and the send
/// credential without reaching step 8: each must hand nothing off.
const LOST_TRANSPORTED: [&str; 4] = ["e10_lost", "e7_waiting", "e7_lost", "l0_lost"];

/// Round 4 (dated 2026-10-31, A #630 issuecomment-6548472857 P3-5): the
/// list, literally. The offline cells compare it with the driver's
/// `LOST_SENDING`, so the same name dropped from both (A7: `e7_waiting`)
/// would pass them; this cell runs without a node and fails on it.
#[test]
fn the_lost_transported_phases_are_pinned() {
    assert_eq!(
        LOST_TRANSPORTED,
        ["e10_lost", "e7_waiting", "e7_lost", "l0_lost"]
    );
}

/// B-692b P2a pre-PR (dated 2026-11-06): the phases whose first run ends at
/// `ReplayComparisonPending` with no send credential, the driver's
/// `REPLAY_PENDING` keys (the tool's cells compare the two).
const REPLAY_PHASES: [&str; 3] = ["r2b_missed", "e8_late", "l0late_broadcast"];

/// The list, literally (as `the_lost_transported_phases_are_pinned`).
#[test]
fn the_replay_pending_phases_are_pinned() {
    assert_eq!(REPLAY_PHASES, ["r2b_missed", "e8_late", "l0late_broadcast"]);
}

/// The 1e-2b-2b phase that reports the bytes step 8 handed off
/// (`raw_tx_hex`, Q-b5: the driver reads no mempool's bytes).
const LOST_KEEPS_BYTES: &str = "e7_broadcast";

fn lost_phase(name: &str) -> bool {
    E10_PHASES
        .iter()
        .chain(&E7_PHASES)
        .chain(&L0D_PHASES)
        .any(|p| p.name == name)
}

/// The report every decided turn of a 1e-2b-2b phase makes (the driver's
/// `LOST_REPORTS`): (opening block missed, reorged before inclusion).
fn lost_flags(name: &str) -> (bool, bool) {
    match name {
        "e10_lost" | "e10_included" | "e10s_same" | "l0_lost" => (true, false),
        "e7_reorged" | "e7_release" | "e7_waiting" => (false, true),
        "e7_lost" | "e7_included" => (true, true),
        _ => (false, false),
    }
}

/// The outcome a 1e-2b-2b phase's `Done` reports (`IncludedNoEffect`).
fn lost_included(name: &str) -> Option<Outcome> {
    match name {
        "e10_included" | "e7_included" => Some(Outcome::IncludedNoEffect { height: H0 + 1 }),
        "e10s_same" => Some(Outcome::IncludedNoEffect { height: H0 }),
        _ => None,
    }
}

/// A 1e-2b-2b report line: `missed=..;reorged=..;outcome=..`.
fn lost_report(report: &bitagi_launch::decision::Report) -> String {
    let outcome = match report.outcome {
        None => "-".to_owned(),
        Some(Outcome::Stale {
            target_gate_height,
            next_birth_height,
        }) => format!("Stale:{target_gate_height}:{next_birth_height}"),
        Some(Outcome::IncludedNoEffect { height }) => format!("IncludedNoEffect:{height}"),
        Some(Outcome::Born { height, at_opening }) => format!("Born:{height}:{at_opening}"),
        Some(Outcome::ProjectBornByOther { .. }) => "ProjectBornByOther".to_owned(),
        // BEAT-1: no BEAT candidate runs here.
        Some(
            beat @ (Outcome::BeatAccepted { .. }
            | Outcome::BeatIncludedNoEffect { .. }
            | Outcome::BeatAnchorSpent { .. }
            | Outcome::HeartTimedOut { .. }
            | Outcome::HeartMaxAge { .. }
            | Outcome::HeartBroken { .. }),
        ) => format!("{beat:?}"),
    };
    format!(
        "missed={};reorged={};outcome={outcome}",
        report.opening_block_missed, report.reorged_before_inclusion
    )
}

/// What a phase did.
struct Done {
    steps: Vec<&'static str>,
    /// The Rust receipt's SHA-256, when the phase ended at
    /// `PrestateComparisonPending`.
    receipt: Option<[u8; 32]>,
    /// B-692b P2a: the replay outbox's name, when the phase ended at
    /// `ReplayComparisonPending` (reported on the `prestate_receipt` line).
    replay_outbox: Option<String>,
    prestate_ms: u128,
    hand_offs: usize,
    raw_sha256: Option<[u8; 32]>,
    txid: Option<[u8; 32]>,
    turns: usize,
    /// 1e-2a: the ledger events the phase's turns made.
    ledger_events: u64,
    /// 1e-2b-1: the answers the proxy dropped, when it ran.
    answer_lost: Option<usize>,
    /// 1e-2b-1: a line write failed in this process.
    lines_failed: bool,
    /// 1e-2b-2b: the last decided turn's report (`lost_report`).
    report: Option<String>,
    /// 1e-2b-2b: the bytes step 8 handed off, for `LOST_KEEPS_BYTES` only.
    raw: Option<Vec<u8>>,
}

/// 1d-3d-3c-2's paths on every turn (A #258 issuecomment-6262177277 1):
/// step 0 passed (a turn that returns), no ledger or host-file rotation
/// ran or was held, no journal bound was met, no journal was final before
/// the turn, and step 9 marked nothing, but on `DEEP`'s `Done` turn
/// (EffectiveFacts, Q-F5; checked where the phase ends).
fn steady(turn: &TurnReport, phase: &Phase) {
    assert!(
        !turn.ledger_rotated && turn.rotation_held.is_none() && !turn.journal_full,
        "E3D3_ROTATION {turn:?}"
    );
    let deep_done = phase.name == DEEP.name
        && matches!(
            turn.decisions[..],
            [bitagi_launch_host::turn::CandidateReport {
                verdict: ReadsVerdict::Decided(Verdict::Done(_)),
                ..
            }]
        );
    assert!(
        (turn.marked_final.is_none() || deep_done) && turn.final_candidates.is_empty(),
        "E3D3_FINAL {turn:?}"
    );
}

/// The launch candidate's journal, read from the host file (no write).
fn journal(launch: &Launch) -> Vec<Entry> {
    HostFile::open(&launch.config.state_dir.join(HOST_FILE))
        .unwrap()
        .journal(&LAUNCH_CANDIDATE)
        .unwrap()
}

/// The journal entry `entry_id` of the launch candidate.
fn entry(launch: &Launch, entry_id: [u8; 32]) -> Record {
    journal(launch)
        .into_iter()
        .find(|e| e.id == entry_id)
        .expect("E3D3_ENTRY")
        .record
}

/// The ledger's next event: a turn that writes the ledger moves it.
fn next_event(launch: &Launch) -> u64 {
    ReservationLedger::inspect(&launch.config.ledger_path, &launch.config.ledger_identity)
        .unwrap()
        .next_event
}

/// The ledger's open stops, by code.
fn open_stops(launch: &Launch) -> Vec<StopCode> {
    ReservationLedger::open_read_only(&launch.config.ledger_path, &launch.config.ledger_identity)
        .unwrap()
        .campaign()
        .unwrap()
        .stops
        .iter()
        .filter(|s| s.cleared.is_none())
        .map(|s| s.code)
        .collect()
}

/// The ledger's open locks, by reason.
fn open_locks(launch: &Launch) -> Vec<LockReason> {
    ReservationLedger::open_read_only(&launch.config.ledger_path, &launch.config.ledger_identity)
        .unwrap()
        .locks()
        .unwrap()
        .locks
        .iter()
        .filter(|l| l.released.is_none())
        .map(|l| l.reason)
        .collect()
}

/// What a turn is checked against afterwards: the journal's length and
/// the ledger's next event before it.
#[derive(Clone, Copy)]
struct Before {
    journal: usize,
    event: u64,
    /// 1e-2a: the host file's and the replay store's digests.
    files: [[u8; 32]; 2],
    /// #471 (A P3 on #472): the ledger's reorg watermark, event and
    /// incident, as the host's start reads it.
    watermark: Option<(u64, [u8; 32])>,
}

/// The ledger's reorg watermark (event, incident), as `LaunchHost::start`
/// reads the history summary.
fn reorg_watermark(launch: &Launch) -> Option<(u64, [u8; 32])> {
    ReservationLedger::inspect(&launch.config.ledger_path, &launch.config.ledger_identity)
        .and_then(|i| i.history_summary())
        .unwrap()
        .reorg_watermark()
        .map(|w| (w.event, w.incident_sha256))
}

/// A turn that ended in a host error, or a catch-up refusal, wrote no
/// journal entry and left no stop or lock open, and its one ledger event
/// is step 0's writer open (the session the turn opened; 3c-2's
/// `TURN_EVENTS`: "writer open ... in step 0"), not a raise (self-review;
/// A #258 issuecomment-6279476947: a lock raised on step 1's path is
/// caught).
fn nothing_raised(launch: &Launch, before: Before) {
    assert_eq!(journal(launch).len(), before.journal, "E3D3_ERROR_WROTE");
    assert_eq!(next_event(launch), before.event + 1, "E3D3_ERROR_LEDGER");
    assert!(open_stops(launch).is_empty(), "E3D3_ERROR_RAISED");
    let locks = ReservationLedger::open_read_only(
        &launch.config.ledger_path,
        &launch.config.ledger_identity,
    )
    .unwrap()
    .locks()
    .unwrap();
    assert!(locks.first_open().is_none(), "E3D3_ERROR_LOCKED");
}

/// The names of the launch candidate's last `n` journal records, oldest
/// first: what the host recorded up to this turn's act, across processes.
fn last_records(launch: &Launch, n: usize) -> Vec<&'static str> {
    let journal = journal(launch);
    journal[journal.len().saturating_sub(n)..]
        .iter()
        .map(|e| match e.record {
            Record::SigningAuthorized { .. } => "SigningAuthorized",
            Record::SigningObserved { .. } => "SigningObserved",
            Record::BroadcastAuthorized { .. } => "BroadcastAuthorized",
            Record::SigningHandedOff { .. } => "SigningHandedOff",
            Record::Submitted { .. } => "Submitted",
            Record::SubmissionIntent { .. } => "SubmissionIntent",
            _ => "other",
        })
        .collect()
}

/// Runs `phase`'s turns (module docs). Every turn is a production turn by
/// a freshly started host; each step's outcome is asserted, and any other
/// step, refusal or error is a FAIL.
#[allow(clippy::too_many_lines)]
fn run_phase(phase: &Phase) -> Done {
    let launch = Launch::new();
    if let Some(height) = phase.tip {
        assert_eq!(launch.tip().0, height, "E3D3_TIP");
    }
    // A phase run again with the prestate comparison carries on from its
    // first run: the host files are already there.
    let comparison = prestate_comparison(&launch);
    // B-692b P2a: and so does one run again with the replay comparison.
    let replay_given = replay_comparison(&launch).is_some();
    if phase.init && comparison.is_none() && !replay_given {
        launch.init();
    }
    let host = launch.host_dir();
    let (candidates, export, verified) = match phase.export {
        Export::Unsigned => (launch.write_candidates(None), None, None),
        Export::Import | Export::Verified => {
            let (export, verified) = verified_export(&launch);
            assert_eq!(
                *verified.wallet_candidate(),
                launch.wallet_candidate(),
                "E3D3_ROW"
            );
            if phase.export == Export::Import {
                import(&launch, &verified);
            }
            (
                launch.write_candidates(Some(&verified)),
                Some(export),
                Some(verified),
            )
        }
        Export::Stored => (host.join("candidates.txt"), None, None),
    };
    // Only a phase that ends after step 8 gets the transport (and the send
    // credential it reads). B-692b P2a pre-PR (dated 2026-11-06): not a
    // replay phase's first run, which ends at `ReplayComparisonPending`
    // before step 8 and is given no send credential (the driver's
    // `replayed`); its run with the replay files gets it.
    let replay_pending = REPLAY_PHASES.contains(&phase.name) && !replay_given;
    let mut transport =
        (phase.last == "AwaitingInclusion" && !replay_pending).then(ProductTransport::new);
    // 1e-2b-2b: and the turns that must hand nothing off with it; the one
    // phase that reports the bytes keeps them.
    if LOST_TRANSPORTED.contains(&phase.name) {
        transport = Some(ProductTransport::new());
    }
    if let Some(t) = transport.as_mut() {
        t.keep = phase.name == LOST_KEEPS_BYTES;
    }
    // An authorization an earlier phase wrote is presented again, as an
    // operator's file stays in place.
    let mut authority =
        Some(host.join("authority-broadcast.txt")).filter(|p| verified.is_some() && p.exists());
    // 1e-2a: E3′-2 presents the procedure file the operator wrote from
    // E3′-1's copy; #471 E-B3 the one of E-B's `Below` reorg.
    if phase.name == "e_release_below" {
        launch.save_below_copy();
    }
    // 1e-2b-2a: `l0_release` presents the one from E9-a's copy.
    if phase.name == "e_release" || phase.name == "e_release_below" || phase.name == "l0_release" {
        launch.write_procedure();
    }
    // 1e-2b-2b: each release phase the one from its reorg's copy.
    if matches!(
        phase.name,
        "e10s_release" | "e7_release" | "l0_lost_release"
    ) {
        launch.write_procedure();
    }
    let mut report = None;
    let mut steps: Vec<&'static str> = Vec::new();
    let mut receipt = None;
    let mut replay_outbox = None;
    let mut prestate_ms = 0;
    let mut turns = 0;
    // XA2 (M4): the live decision gave no BROADCAST (`broadcast_decision`).
    let mut decision_refused = false;
    let first_event = next_event(&launch);
    // 1e-2b-2a's E8 (dated 2026-10-31, after the first run): the
    // operator's import at H0 − 1, with no host turn there. `import`
    // reconciles with no replay state, which the ledger refuses at a tip at
    // or above H0 (`StaleBranch`, the rule A8-M9 tests), so the harness
    // cannot import above H0 − 1.
    if phase.name == "e8_import" {
        return Done {
            steps: vec!["Imported"],
            receipt: None,
            replay_outbox: None,
            prestate_ms: 0,
            hand_offs: 0,
            raw_sha256: None,
            txid: verified.as_ref().map(|v| *v.txid_internal()),
            turns: 0,
            ledger_events: next_event(&launch) - first_event,
            answer_lost: None,
            lines_failed: launch.lines_failed(),
            report: None,
            raw: None,
        };
    }
    for _ in 0..MAX_TURNS {
        let before = Before {
            journal: journal(&launch).len(),
            event: next_event(&launch),
            files: launch.state_files(),
            watermark: reorg_watermark(&launch),
        };
        let started = std::time::Instant::now();
        let turn = launch.turn(
            &candidates,
            authority.as_deref(),
            export.as_deref(),
            transport.as_mut(),
            comparison.as_ref(),
        );
        let took = started.elapsed().as_millis();
        turns += 1;
        // No host-file rotation: no archived segment beside the live file
        // (`HostFile::rotate`; `TurnReport` has no field for it), whatever
        // the turn returned, the host errors included (Codex review on
        // #439).
        assert!(
            listing(&launch.config.state_dir)
                .iter()
                .all(|name| !name.contains("-segment-")),
            "E3D3_HOST_FILE_ROTATED"
        );
        // 1e-2a: a phase whose every turn writes no journal entry and moves
        // the ledger by its count, whatever the turn returned.
        if let Some(events) = phase.ledger {
            assert_eq!(
                journal(&launch).len(),
                before.journal,
                "E3D3_E_WROTE {turn:?}"
            );
            assert_eq!(
                next_event(&launch),
                before.event + events,
                "E3D3_E_LEDGER {turn:?}"
            );
        }
        let turn = match turn {
            Ok(turn) => turn,
            Err(bitagi_launch_host::HostError::Node(NodeContextError::NetworkInactive))
                if phase.last == "HostError:NetworkInactive" =>
            {
                nothing_raised(&launch, before);
                steps.push(phase.last);
                break;
            }
            // 1e-2a E-B: below the floor the hook raised Reorg67 (Below) and
            // the follower ended: that raise is the turn's only write (the
            // ledger count above), and the host file and the replay store
            // are as they were. #471 (A P3 on #472): the raise moved the
            // watermark to a new incident, so the open lock is this turn's
            // (E3′'s was released by E3′-2), not a count alone.
            Err(bitagi_launch_host::HostError::Sync(
                bitagi_bitcoin::SyncError::TipBelowReplayFloor,
            )) if phase.last == "HostError:Sync(TipBelowReplayFloor)" => {
                assert_eq!(launch.state_files(), before.files, "E3D3_E_BELOW_WROTE");
                assert_eq!(
                    open_locks(&launch),
                    [LockReason::Reorg67],
                    "E3D3_E_BELOW_LOCK"
                );
                assert!(open_stops(&launch).is_empty(), "E3D3_E_BELOW_STOP");
                let after = reorg_watermark(&launch).expect("E3D3_E_BELOW_WATERMARK");
                let before = before.watermark.expect("E3D3_E_BELOW_WATERMARK");
                assert!(
                    after.0 > before.0 && after.1 != before.1,
                    "E3D3_E_BELOW_WATERMARK {before:?} {after:?}"
                );
                steps.push(phase.last);
                break;
            }
            Err(e) => panic!("E3D3_TURN {} {e:?} after {steps:?}", phase.name),
        };
        steady(&turn, phase);
        // 1e-2b-2b: nothing persisted but a Reorg67 raise, no stop open, at
        // most one signature hand-off, authorization and submission, and
        // every decision's report as the phase's table says.
        if lost_phase(phase.name) {
            assert!(
                turn.persisted.is_empty() || phase.last == "Refuse:Locked(Reorg67)",
                "E3D3_LOST_RAISE {turn:?}"
            );
            assert!(open_stops(&launch).is_empty(), "E3D3_LOST_STOP {turn:?}");
            let names = last_records(&launch, usize::MAX);
            for name in ["SigningHandedOff", "BroadcastAuthorized", "Submitted"] {
                assert!(
                    names.iter().filter(|n| **n == name).count() <= 1,
                    "E3D3_LOST_{name} {turn:?}"
                );
            }
            for decision in &turn.decisions {
                assert_eq!(
                    (
                        decision.report.opening_block_missed,
                        decision.report.reorged_before_inclusion
                    ),
                    lost_flags(phase.name),
                    "E3D3_LOST_REPORT {turn:?}"
                );
                report = Some(lost_report(&decision.report));
            }
        }
        // R2-b: under the continue budget nothing is raised on any r2b turn,
        // and every decision at H0 reports the opening block missed (block
        // H0 holds no REGISTER) with no outcome yet.
        if R2B_PHASES.iter().any(|p| p.name == phase.name) {
            assert!(turn.persisted.is_empty(), "E3D3_R2B_RAISE {turn:?}");
            assert!(open_stops(&launch).is_empty(), "E3D3_R2B_STOP {turn:?}");
            if phase.name == "r2b_missed" {
                assert!(
                    matches!(
                        turn.decisions[..],
                        [bitagi_launch_host::turn::CandidateReport {
                            report: bitagi_launch::decision::Report {
                                opening_block_missed: true,
                                outcome: None,
                                ..
                            },
                            ..
                        }]
                    ),
                    "E3D3_R2B_MISSED {turn:?}"
                );
            }
        }
        // 1e-2b-2a: no L0T or late E8 turn raises a stop. On the L0 chain
        // past H0 − 1 (T2-11) the journal keeps exactly one `Submitted` and
        // one Sign hand-off, the opening block G held the transaction (never
        // missed), and no H0 − 1 block a submission was made at was reorged
        // away (X stays: no CN-01 mark). Only E9-a's turn sees a reorg.
        let l0t = L0T_PHASES.iter().any(|p| p.name == phase.name);
        if l0t || E8_PHASES[2..].iter().any(|p| p.name == phase.name) {
            assert!(turn.persisted.is_empty(), "E3D3_TIP_H0_RAISE {turn:?}");
            assert!(open_stops(&launch).is_empty(), "E3D3_TIP_H0_STOP {turn:?}");
        }
        if l0t {
            let names = last_records(&launch, usize::MAX);
            for (name, count) in [("Submitted", 1), ("SigningHandedOff", 1)] {
                assert_eq!(
                    names.iter().filter(|n| **n == name).count(),
                    count,
                    "E3D3_L0T_{name} {turn:?}"
                );
            }
            assert!(
                turn.decisions
                    .iter()
                    .all(|d| !d.report.opening_block_missed && !d.report.reorged_before_inclusion),
                "E3D3_L0T_REPORT {turn:?}"
            );
            if phase.name != "l0_reorged" {
                assert!(turn.reorg_seen.is_none(), "E3D3_L0T_REORG {turn:?}");
            }
            if phase.name != "l0_reorged" && phase.name != "l0_release" {
                assert!(open_locks(&launch).is_empty(), "E3D3_L0T_LOCK {turn:?}");
            }
        }
        // The E8 run at H0 + `E8_LATE`: the opening block missed, no outcome.
        if phase.name == "e8_late" {
            assert!(
                matches!(
                    turn.decisions[..],
                    [bitagi_launch_host::turn::CandidateReport {
                        report: bitagi_launch::decision::Report {
                            opening_block_missed: true,
                            outcome: None,
                            ..
                        },
                        ..
                    }]
                ),
                "E3D3_E8_MISSED {turn:?}"
            );
        }
        // #484 L0: no L0 turn raises a lock or sees a reorg. A pre-floor
        // turn (below H0 − 1) writes no replay store and signs at H0 − 2;
        // after an H0 − 1 turn the store's floor is the agreed block, so U
        // is not left (A's condition 2; F4 and F3 on real nodes).
        if L0_PHASES.iter().any(|p| p.name == phase.name) {
            assert!(turn.reorg_seen.is_none(), "E3D3_L0_REORG {turn:?}");
            assert!(open_locks(&launch).is_empty(), "E3D3_L0_LOCK {turn:?}");
            let (height, hash) = launch.tip();
            if height < H0 - 1 {
                assert_eq!(
                    launch.state_files()[1],
                    before.files[1],
                    "E3D3_L0_STORE_WROTE {turn:?}"
                );
                if let [
                    bitagi_launch_host::turn::CandidateReport {
                        verdict: ReadsVerdict::Decided(Verdict::Act(Step::Sign { at, .. })),
                        ..
                    },
                ] = turn.decisions[..]
                {
                    assert_eq!(at.height, H0 - 2, "E3D3_L0_SIGN_TIP");
                }
            } else {
                assert_eq!(launch.store_tip(), (height, hash), "E3D3_L0_FLOOR {turn:?}");
            }
        }
        // B-692a-RT: no turn of the late flow raises, opens a stop or a
        // lock, or sees a reorg. Below H0 − 1 (the window) it writes no
        // replay store and signs at H0 − 2; at and above H0 the store
        // followed the agreed tip from U (anchored at H0 − 1 by the first
        // turn after the window), and every decision reports the opening
        // block missed, with no outcome before the birth.
        if L0L_PHASES.iter().any(|p| p.name == phase.name) {
            assert!(turn.persisted.is_empty(), "E3D3_L0L_RAISE {turn:?}");
            assert!(open_stops(&launch).is_empty(), "E3D3_L0L_STOP {turn:?}");
            assert!(open_locks(&launch).is_empty(), "E3D3_L0L_LOCK {turn:?}");
            assert!(turn.reorg_seen.is_none(), "E3D3_L0L_REORG {turn:?}");
            let (height, hash) = launch.tip();
            if height < H0 - 1 {
                assert_eq!(
                    launch.state_files()[1],
                    before.files[1],
                    "E3D3_L0L_STORE_WROTE {turn:?}"
                );
                if let [
                    bitagi_launch_host::turn::CandidateReport {
                        verdict: ReadsVerdict::Decided(Verdict::Act(Step::Sign { at, .. })),
                        ..
                    },
                ] = turn.decisions[..]
                {
                    assert_eq!(at.height, H0 - 2, "E3D3_L0L_SIGN_TIP");
                }
            } else {
                assert!(height >= H0, "E3D3_L0L_TIP {turn:?}");
                assert_eq!(
                    launch.store_tip(),
                    (height, hash),
                    "E3D3_L0L_STORE {turn:?}"
                );
                assert!(
                    turn.decisions.iter().all(
                        |d| d.report.opening_block_missed && !d.report.reorged_before_inclusion
                    ),
                    "E3D3_L0L_MISSED {turn:?}"
                );
            }
            if phase.name == "l0late_broadcast" {
                assert!(
                    matches!(
                        turn.decisions[..],
                        [bitagi_launch_host::turn::CandidateReport {
                            report: bitagi_launch::decision::Report { outcome: None, .. },
                            ..
                        }]
                    ),
                    "E3D3_L0L_OUTCOME {turn:?}"
                );
            }
        }
        // #440 (A #258 issuecomment-6283589369 Q-440-4): step 1 refused on
        // the tip disagreement and the bracket confirmed it. The core
        // raised the CriticalHeight68 lock at H0 − 1 with the node stop;
        // nothing was acted on, authorized or released.
        if let Some(refused) = turn.step_one_refused {
            assert_eq!(
                phase.last, "Refuse:CriticalHeightDisagreed",
                "E3D3_STEP_ONE_REFUSED {turn:?}"
            );
            assert_eq!(
                refused,
                DualNodeError::TipHashDisagreement,
                "E3D3_STEP_ONE_REFUSED"
            );
            assert!(
                matches!(
                    turn.decisions[..],
                    [bitagi_launch_host::turn::CandidateReport {
                        verdict: ReadsVerdict::Refuse(bitagi_launch::with_reads::ReadsRefusal {
                            code: ReadsCode::CriticalHeightDisagreed { height },
                            ..
                        }),
                        ..
                    }] if height == H0 - 1
                ),
                "E3D3_UNEXPECTED_REFUSAL {turn:?}"
            );
            let raised: Vec<_> = turn.persisted.iter().map(|p| (p.stop, p.lock)).collect();
            assert_eq!(raised, [(phase.raises, true)], "E3D3_RAISE {turn:?}");
            assert!(
                turn.act.is_none()
                    && turn.authorization.is_none()
                    && turn.released.is_none()
                    && turn.marked_final.is_none(),
                "E3D3_ACT_ON_REFUSAL {turn:?}"
            );
            assert_eq!(journal(&launch).len(), before.journal, "E3D3_REFUSED_WROTE");
            // Step 0's writer open, the stop and the lock.
            assert_eq!(next_event(&launch), before.event + 3, "E3D3_REFUSED_LEDGER");
            assert_eq!(
                open_stops(&launch),
                phase.raises.into_iter().collect::<Vec<_>>(),
                "E3D3_RAISE_NOT_IN_LEDGER"
            );
            assert_eq!(
                open_locks(&launch),
                [LockReason::CriticalHeight68],
                "E3D3_LOCK_NOT_IN_LEDGER"
            );
            steps.push(phase.last);
            break;
        }
        // #440: the next phase's first turn, both nodes agreeing at H0 − 1
        // again, releases that lock on the operator's resolution file. #471
        // E3′-2 and E-B3: the procedure file releases the Reorg67 lock,
        // step 6 not performed, and the phase ends. Its decision is the
        // open lock's refusal, and it raises nothing.
        if let Some(released) = turn.released {
            let (reason, step6, step) = if phase.last == "ReleaseReorg67" {
                (
                    LockReason::Reorg67,
                    Some(bitagi_launch_host::procedure::Step6Status::NotPerformed),
                    "ReleaseReorg67",
                )
            } else {
                (
                    LockReason::CriticalHeight68,
                    None,
                    "ReleaseCriticalHeight68",
                )
            };
            assert_eq!(released.reason, reason, "E3D3_RELEASED {turn:?}");
            assert_eq!(released.step6, step6, "E3D3_RELEASED {turn:?}");
            assert!(
                matches!(
                    turn.decisions[..],
                    [bitagi_launch_host::turn::CandidateReport {
                        verdict: ReadsVerdict::Decided(Verdict::Refuse(
                            bitagi_launch::decision::Refusal {
                                code: bitagi_launch::decision::RefusalCode::Locked(r),
                                raise: bitagi_launch::decision::Raise {
                                    stop: None,
                                    lock: None
                                },
                            }
                        )),
                        ..
                    }] if r == reason
                ),
                "E3D3_RELEASED {turn:?}"
            );
            assert!(
                turn.persisted.is_empty() && turn.act.is_none() && turn.reorg_seen.is_none(),
                "E3D3_RELEASED {turn:?}"
            );
            assert!(open_locks(&launch).is_empty(), "E3D3_RELEASE_NOT_IN_LEDGER");
            steps.push(step);
            if step == phase.last {
                break;
            }
            continue;
        }
        assert_eq!(turn.decisions.len(), 1, "E3D3_DECISIONS");
        if let ReadsVerdict::Refuse(refusal) = turn.decisions[0].verdict {
            // Only `DEEP` may be refused at the reads, only while the
            // follower catches up, raising and writing nothing.
            assert!(
                phase.catch_up && refusal.code == ReadsCode::LocalTipUnconfirmed,
                "E3D3_UNEXPECTED_REFUSAL {turn:?} after {steps:?}"
            );
            assert!(
                turn.persisted.is_empty() && turn.act.is_none(),
                "E3D3_RAISE {turn:?}"
            );
            nothing_raised(&launch, before);
            steps.push("LocalTipUnconfirmed");
            break;
        }
        if let ReadsVerdict::Decided(Verdict::Refuse(refusal)) = turn.decisions[0].verdict {
            assert_eq!(
                format!("Refuse:{:?}", refusal.code),
                phase.last,
                "E3D3_UNEXPECTED_REFUSAL {turn:?} after {steps:?}"
            );
            let raised: Vec<_> = turn.persisted.iter().map(|p| (p.stop, p.lock)).collect();
            let expected: Vec<_> = phase
                .raises
                .map(|code| (Some(code), false))
                .into_iter()
                .collect();
            assert_eq!(raised, expected, "E3D3_RAISE {turn:?}");
            assert!(turn.act.is_none(), "E3D3_ACT_ON_REFUSAL {turn:?}");
            // 1e-2a E3′-1: the hook raised Reorg67 for X → X′ at H0 − 1 and
            // bound the ancestor (H0 − 1, X′); the operator keeps the copy.
            // #471 E-B2: the start passed with E-B's lock open and no
            // ancestor; no new reorg.
            if phase.name == "e_dead" {
                assert!(turn.reorg_seen.is_none(), "E3D3_REORG_AGAIN {turn:?}");
                assert_eq!(
                    open_locks(&launch),
                    [LockReason::Reorg67],
                    "E3D3_REORG_NOT_IN_LEDGER"
                );
            }
            // 1e-2b-1 L3: X -> X' after the send at H0 - 1. The hook
            // raised Reorg67, and the report marks the reorg before
            // inclusion (CN-01).
            if phase.name == "cn01" {
                let seen = turn.reorg_seen.expect("E3D3_REORG_SEEN");
                assert!(seen.raised, "E3D3_REORG_NOT_RAISED {seen:?}");
                assert!(
                    turn.decisions[0].report.reorged_before_inclusion,
                    "E3D3_CN01_NOT_MARKED {turn:?}"
                );
                assert_eq!(
                    open_locks(&launch),
                    [LockReason::Reorg67],
                    "E3D3_REORG_NOT_IN_LEDGER"
                );
            }
            // 1e-2b-2a E9-a: G invalidated on both nodes, the tip X at
            // H0 − 1 below the local tip (H0, G). The hook raised Reorg67
            // with no agreed block at the local height and bound the
            // ancestor (H0 − 1, X); the operator keeps the copy.
            if phase.name == "l0_reorged" {
                let seen = turn.reorg_seen.expect("E3D3_REORG_SEEN");
                let (height, hash) = launch.tip();
                assert!(seen.raised, "E3D3_REORG_NOT_RAISED {seen:?}");
                assert_eq!(height, H0 - 1, "E3D3_REORG_HEIGHT");
                assert_eq!(seen.identity.local.0, H0, "E3D3_REORG_LOCAL {seen:?}");
                assert_eq!(
                    seen.identity.at_local,
                    AtLocal::Below,
                    "E3D3_REORG_AT_LOCAL"
                );
                assert_eq!(
                    seen.ancestor.map(|a| (a.incident, a.height, a.hash)),
                    Some((seen.incident, H0 - 1, hash)),
                    "E3D3_REORG_ANCESTOR {seen:?}"
                );
                assert_eq!(
                    open_locks(&launch),
                    [LockReason::Reorg67],
                    "E3D3_REORG_NOT_IN_LEDGER"
                );
                launch.save_reorg_copy(&seen);
            }
            // 1e-2b-2b: the lost rows' reorgs. E10-s: G + 1 and G
            // invalidated, local (H0 + 1, G + 1) below the tip X; E9-d: G''
            // invalidated, local (H0, G'') below X; E7: X -> X', local
            // (H0 - 1, X) and X' agreed there. Each binds the ancestor at the
            // tip; the operator keeps the copy.
            if matches!(
                phase.name,
                "e10s_reorged" | "l0_lost_reorged" | "e7_reorged"
            ) {
                let seen = turn.reorg_seen.expect("E3D3_REORG_SEEN");
                let (height, hash) = launch.tip();
                assert!(seen.raised, "E3D3_REORG_NOT_RAISED {seen:?}");
                assert_eq!(height, H0 - 1, "E3D3_REORG_HEIGHT");
                let (local, at_local) = match phase.name {
                    "e10s_reorged" => (H0 + 1, AtLocal::Below),
                    "l0_lost_reorged" => (H0, AtLocal::Below),
                    _ => (H0 - 1, AtLocal::Agreed(hash)),
                };
                assert_eq!(seen.identity.local.0, local, "E3D3_REORG_LOCAL {seen:?}");
                assert_eq!(seen.identity.at_local, at_local, "E3D3_REORG_AT_LOCAL");
                assert_eq!(
                    seen.ancestor.map(|a| (a.incident, a.height, a.hash)),
                    Some((seen.incident, H0 - 1, hash)),
                    "E3D3_REORG_ANCESTOR {seen:?}"
                );
                assert_eq!(
                    open_locks(&launch),
                    [LockReason::Reorg67],
                    "E3D3_REORG_NOT_IN_LEDGER"
                );
                launch.save_reorg_copy(&seen);
            }
            // 1e-2b-2b E10, E7, E9-d: the gate lost to a competitor's birth
            // at G, P0 not mined: `Stale { G, next > G }`, not `Done`.
            if phase.last == "Refuse:GateAdvanced" {
                assert!(
                    matches!(
                        turn.decisions[0].report.outcome,
                        Some(Outcome::Stale { target_gate_height, next_birth_height })
                            if target_gate_height == H0 && next_birth_height > H0
                    ),
                    "E3D3_LOST_STALE {turn:?}"
                );
            }
            if phase.name == "e_replaced" {
                let seen = turn.reorg_seen.expect("E3D3_REORG_SEEN");
                let (height, hash) = launch.tip();
                assert!(seen.raised, "E3D3_REORG_NOT_RAISED {seen:?}");
                assert_eq!(height, H0 - 1, "E3D3_REORG_HEIGHT");
                assert_eq!(seen.identity.local.0, H0 - 1, "E3D3_REORG_LOCAL {seen:?}");
                assert_ne!(seen.identity.local.1, hash, "E3D3_REORG_LOCAL {seen:?}");
                assert_eq!(
                    seen.identity.at_local,
                    AtLocal::Agreed(hash),
                    "E3D3_REORG_AT_LOCAL"
                );
                assert_eq!(
                    seen.ancestor.map(|a| (a.incident, a.height, a.hash)),
                    Some((seen.incident, H0 - 1, hash)),
                    "E3D3_REORG_ANCESTOR {seen:?}"
                );
                assert_eq!(
                    open_locks(&launch),
                    [LockReason::Reorg67],
                    "E3D3_REORG_NOT_IN_LEDGER"
                );
                launch.save_reorg_copy(&seen);
            }
            // The raise is in the ledger, not only in the host's report.
            if let Some(code) = phase.raises {
                assert!(
                    open_stops(&launch).contains(&code),
                    "E3D3_RAISE_NOT_IN_LEDGER"
                );
            }
            // #503: at its bound, turn after turn, the stop `reject_both`
            // raised stays open and nothing is written (`phase.ledger`).
            if phase.name == "bounded" {
                assert_eq!(
                    open_stops(&launch),
                    NODE_STOP.into_iter().collect::<Vec<_>>(),
                    "E3D3_BOUND_STOP"
                );
                if turns < BOUND_TURNS {
                    continue;
                }
            }
            if phase.catch_up {
                // Deeper than step 9's depth, both nodes agreeing.
                let depth = launch.tip().0 - H0;
                assert!(
                    depth > bitagi_wallet::reservations::MAX_ANCESTRY_BLOCKS as u64,
                    "E3D3_DEPTH {depth}"
                );
            }
            steps.push(phase.last);
            break;
        }
        let calls = transport.as_ref().map_or(0, |t| t.calls);
        match verdict(&turn) {
            // 1d-3d-3d: the first comparison turn writes the Rust receipt
            // and records nothing; the phase ends for the driver's
            // comparison. With the comparison given, the host records it.
            // B-692a-RT: on the late path the block is H0 − 1 below the tip,
            // and the comparison entry is made at the tip.
            ReadsVerdict::Decided(Verdict::Act(Step::ComparePrestate { h0_minus_1 })) => {
                check_prestate_block(&launch, phase, h0_minus_1);
                prestate_ms += took;
                match act(&turn) {
                    ActOutcome::PrestateComparisonPending { receipt_sha256, .. } => {
                        assert!(comparison.is_none(), "E3D3_PRESTATE_NOT_TAKEN {turn:?}");
                        let outbox = launch.dir.join("outbox");
                        let bytes = std::fs::read(outbox.join(receipt_file_name(&receipt_sha256)))
                            .expect("E3D3_PRESTATE_RECEIPT");
                        assert_eq!(
                            bitagi_hash::sha256(&bytes),
                            receipt_sha256,
                            "E3D3_PRESTATE_RECEIPT"
                        );
                        receipt = Some(receipt_sha256);
                        steps.push("PrestateComparisonPending");
                        break;
                    }
                    ActOutcome::Recorded { entry_id } => {
                        assert!(comparison.is_some(), "E3D3_PRESTATE_NOT_GIVEN");
                        let record = entry(&launch, entry_id);
                        assert_eq!(
                            record_name(&record),
                            "PrestateCompared",
                            "E3D3_PRESTATE {turn:?}"
                        );
                        let made = journal(&launch)
                            .into_iter()
                            .find(|e| e.id == entry_id)
                            .expect("E3D3_PRESTATE_ENTRY");
                        assert_eq!(
                            (made.at.height, made.at.hash),
                            launch.tip(),
                            "E3D3_PRESTATE_AT {turn:?}"
                        );
                        steps.push("ComparePrestate");
                    }
                    other => panic!("E3D3_PRESTATE {other:?} after {steps:?}"),
                }
            }
            ReadsVerdict::Decided(Verdict::Act(Step::RecordInitialPrestate {
                at,
                prestate_sha256,
                ..
            })) => {
                // #471, a part of T2-4 (A #515 P3-11): the record is the
                // agreed block's (X′ after the floor replacement), and at
                // X′ its receipt is not X's, the journal's first.
                // B-692a-RT: on the late path block H0 − 1, below the tip.
                check_prestate_block(&launch, phase, at);
                if phase.name.starts_with("e_reask") {
                    // Read through the record's text, as `record_name`
                    // does: no file in `tests/` names the prestate records
                    // (`structure.rs`, `only_the_host_makes_the_prestate_records`).
                    let x = journal(&launch)
                        .into_iter()
                        .map(|e| format!("{:?}", e.record))
                        .find(|text| text.starts_with("InitialPrestateRecorded"))
                        .expect("E3D3_X_INITIAL_PRESTATE");
                    assert!(
                        x.contains("prestate_sha256: ["),
                        "E3D3_X_INITIAL_PRESTATE {x}"
                    );
                    assert!(
                        !x.contains(&format!("prestate_sha256: {prestate_sha256:?}")),
                        "E3D3_X_PRIME_RECEIPT {x}"
                    );
                }
                prestate_ms += took;
                let ActOutcome::Recorded { entry_id } = act(&turn) else {
                    panic!("E3D3_INITIAL_PRESTATE {turn:?}")
                };
                let record = entry(&launch, entry_id);
                assert_eq!(
                    record_name(&record),
                    "InitialPrestateRecorded",
                    "E3D3_INITIAL_PRESTATE"
                );
                steps.push("RecordInitialPrestate");
            }
            // B-692b P2a (finding #692): the REGISTER replay comparison at
            // tip >= H0. The first turn writes the host's outbox and records
            // nothing; the phase ends for the driver's `step6-compare`. With
            // its files given, the host records the link on its own MATCH.
            ReadsVerdict::Decided(Verdict::Act(Step::CompareReplay { from, through })) => {
                assert_eq!(from.height, H0 - 1, "E3D3_COMPARE_REPLAY_FROM");
                assert_eq!(
                    launch.tip(),
                    (through.height, through.hash),
                    "E3D3_COMPARE_REPLAY_TIP"
                );
                match act(&turn) {
                    ActOutcome::ReplayComparison(ReplayOutcome::Pending { .. }) => {
                        assert!(!replay_given, "E3D3_REPLAY_NOT_TAKEN {turn:?}");
                        assert_eq!(
                            journal(&launch).len(),
                            before.journal,
                            "E3D3_COMPARE_REPLAY_WROTE"
                        );
                        let names: Vec<String> = listing(&launch.dir.join("outbox"))
                            .into_iter()
                            .filter(|n| n.starts_with("replay-compare-"))
                            .collect();
                        assert_eq!(names.len(), 1, "E3D3_REPLAY_OUTBOX {names:?}");
                        replay_outbox = names.into_iter().next();
                        steps.push("ReplayComparisonPending");
                        break;
                    }
                    ActOutcome::Recorded { entry_id } => {
                        assert!(replay_given, "E3D3_REPLAY_NOT_GIVEN");
                        let made = journal(&launch)
                            .into_iter()
                            .find(|e| e.id == entry_id)
                            .expect("E3D3_REPLAY_ENTRY");
                        assert!(
                            matches!(made.record, Record::ReplayCompared { through: t, .. } if t == through),
                            "E3D3_REPLAY {made:?}"
                        );
                        assert_eq!(made.at, through, "E3D3_REPLAY_AT");
                        steps.push("CompareReplay");
                    }
                    other => panic!("E3D3_COMPARE_REPLAY {other:?} after {steps:?}"),
                }
            }
            // A check or an observation: what the turn recorded.
            ReadsVerdict::Decided(Verdict::Act(
                step @ (Step::RunExecutionChecks { .. }
                | Step::RecordSigningObservation { .. }
                | Step::RecordBroadcastObservation { .. }
                | Step::RunPrebroadcastChecks { .. }),
            )) => {
                let ActOutcome::Recorded { entry_id } = act(&turn) else {
                    panic!("{turn:?}")
                };
                let (name, recorded) = match (step, entry(&launch, entry_id)) {
                    (Step::RunExecutionChecks { .. }, Record::ExecutionChecks { outcome }) => {
                        ("RunExecutionChecks", outcome == CheckOutcome::Passed)
                    }
                    (
                        Step::RunPrebroadcastChecks { .. },
                        Record::PrebroadcastChecks { outcome, .. },
                    ) => ("RunPrebroadcastChecks", outcome == CheckOutcome::Passed),
                    (Step::RecordSigningObservation { .. }, Record::SigningObserved { .. }) => {
                        ("RecordSigningObservation", true)
                    }
                    (Step::RecordBroadcastObservation { .. }, Record::BroadcastObserved { .. }) => {
                        ("RecordBroadcastObservation", true)
                    }
                    _ => ("-", false),
                };
                assert!(recorded, "E3D3_RECORDED {turn:?}");
                steps.push(name);
            }
            ReadsVerdict::Decided(Verdict::Act(Step::ClearActionBlock {
                code,
                evidence_id,
                ..
            })) => {
                // The open stop of an earlier phase, cleared on this
                // phase's fresh checks.
                assert_eq!(Some(code), NODE_STOP, "E3D3_CLEARED_CODE");
                assert!(
                    matches!(
                        act(&turn),
                        ActOutcome::Cleared { code: c, evidence_id: e, .. }
                            if c == code && e == evidence_id
                    ),
                    "{turn:?}"
                );
                // Cleared in the ledger, not only in the host's report.
                assert!(
                    !open_stops(&launch).contains(&code),
                    "E3D3_CLEAR_NOT_IN_LEDGER"
                );
                steps.push("ClearActionBlock");
            }
            ReadsVerdict::Decided(Verdict::Act(Step::AdmitSignedFinal { .. })) => {
                let ActOutcome::Recorded { entry_id } = act(&turn) else {
                    panic!("{turn:?}")
                };
                let Record::Admitted { node_a, node_b, .. } = entry(&launch, entry_id) else {
                    panic!("E3D3_ADMITTED {turn:?}")
                };
                assert_eq!([node_a, node_b], phase.admitted, "E3D3_ADMISSION");
                steps.push("AdmitSignedFinal");
            }
            // The turn that records an authorization decided on the wait
            // before it (`TurnReport::authorization`).
            ReadsVerdict::Decided(Verdict::Wait(Wait::SigningAuthorityRequired {
                checks_id,
                ..
            })) => match turn.authorization {
                None => {
                    assert!(authority.is_none(), "E3D3_AUTHORITY_NOT_TAKEN {turn:?}");
                    authority = Some(launch.signing_file(checks_id));
                    steps.push("SigningAuthorityRequired");
                }
                Some(taken) => {
                    assert!(
                        matches!(taken.outcome, AuthorizationOutcome::Recorded { .. }),
                        "{turn:?}"
                    );
                    steps.push("SigningAuthorized");
                }
            },
            ReadsVerdict::Decided(Verdict::Wait(Wait::BroadcastAuthorityRequired {
                prebroadcast_id,
                ..
            })) => match turn.authorization {
                // #471 E3′-3 and E-B4: the new run at X′ waits for its own
                // authorization. E2″'s file, still in place, names X's
                // prebroadcast checks: it is not used and nothing is
                // written for it; the phase ends at the wait.
                // R2-b `r2b_wait`: at H0 − 1 the operator writes no
                // broadcast authorization; the phase ends at the wait.
                None if phase.name == "r2b_wait" => {
                    assert!(authority.is_none(), "E3D3_R2B_AUTHORITY");
                    assert!(turn.act.is_none(), "E3D3_R2B_AUTHORITY {turn:?}");
                    steps.push("BroadcastAuthorityRequired");
                }
                // 1e-2b-2b E7 (dated 2026-10-31, after the first run): at X'
                // the run asks for a new broadcast authorization; none is
                // given, so nothing is authorized or submitted under the old
                // one (Q22 main's answer).
                None if phase.name == "e7_waiting" => {
                    assert!(turn.act.is_none(), "E3D3_E7_AUTHORITY {turn:?}");
                    steps.push("BroadcastAuthorityRequired");
                }
                None if phase.last == "BroadcastAuthorityRequired" => {
                    assert!(authority.is_some(), "E3D3_E_NO_STALE_AUTHORITY");
                    assert_eq!(
                        turn.authority_unused,
                        Some(AuthorityUnused::OtherDecision),
                        "E3D3_E_STALE_AUTHORITY {turn:?}"
                    );
                    assert!(turn.act.is_none(), "E3D3_E_STALE_AUTHORITY {turn:?}");
                    assert_eq!(
                        journal(&launch).len(),
                        before.journal,
                        "E3D3_E_STALE_AUTHORITY"
                    );
                    assert!(open_locks(&launch).is_empty(), "E3D3_E_REASK_LOCKED");
                    steps.push("BroadcastAuthorityRequired");
                }
                None => {
                    assert!(authority.is_none(), "E3D3_AUTHORITY_NOT_TAKEN {turn:?}");
                    let verified = verified.as_ref().expect("E3D3_EXPORT");
                    // XA2 (M4): in a live-decision XD-1 run the file is
                    // written only on the Founder's BROADCAST; otherwise
                    // nothing is written and the phase ends at the wait,
                    // as `r2b_wait`'s (`broadcast_decision`).
                    authority = broadcast_decision(
                        std::env::var_os("BITAGI_E3D3_XD1_DECISION"),
                        std::env::var_os("BITAGI_E3D3_EVENT_LINES"),
                        MAX_ACK_WAIT,
                        || launch.broadcast_file(prebroadcast_id, verified),
                    );
                    steps.push("BroadcastAuthorityRequired");
                    if authority.is_none() {
                        decision_refused = true;
                        break;
                    }
                }
                Some(taken) => {
                    assert!(
                        matches!(taken.outcome, AuthorizationOutcome::Recorded { .. }),
                        "{turn:?}"
                    );
                    assert_eq!(calls, 0, "E3D3_HAND_OFF_BEFORE_AUTHORIZED");
                    steps.push("BroadcastAuthorized");
                }
            },
            ReadsVerdict::Decided(Verdict::Act(Step::Sign { .. })) => {
                // The human authorization was recorded just before, then
                // the observation (A #258 issuecomment-6262367082 P2-2): the
                // journal's last entries, the act's own last.
                assert_eq!(
                    last_records(&launch, 3),
                    ["SigningAuthorized", "SigningObserved", "SigningHandedOff"],
                    "E3D3_SIGN_BEFORE_AUTHORIZED {steps:?}"
                );
                assert!(
                    matches!(act(&turn), ActOutcome::SignHandedOff { .. }),
                    "{turn:?}"
                );
                steps.push("Sign");
            }
            // 1e-2a E2″ and E6a-2: step 8 with no transport hands off and
            // records nothing.
            ReadsVerdict::Decided(Verdict::Act(Step::Broadcast { .. }))
                if phase.last == "NotYet:Transport" =>
            {
                assert!(transport.is_none(), "E3D3_E_TRANSPORT");
                assert_eq!(
                    act(&turn),
                    ActOutcome::NotPerformed(NotYet::Transport),
                    "E3D3_E_SENT"
                );
                assert_eq!(journal(&launch).len(), before.journal, "E3D3_E_SENT");
                assert!(
                    !last_records(&launch, usize::MAX).contains(&"Submitted"),
                    "E3D3_E_SUBMITTED"
                );
                steps.push("NotYet:Transport");
            }
            ReadsVerdict::Decided(Verdict::Act(Step::Broadcast { .. })) => {
                // The authorization was recorded just before, in this
                // phase or the last; the act's own `Submitted` follows it
                // (read back below).
                // The host's own read before step 8 (its mempool log's last
                // row for the transaction): in neither node's mempool.
                let seen = HostFile::open(&launch.config.state_dir.join(HOST_FILE))
                    .unwrap()
                    .mempool_log()
                    .unwrap();
                let seen = seen.last().expect("E3D3_MEMPOOL_NOT_READ");
                assert_eq!(
                    [seen.node_a, seen.node_b],
                    [Seen::Absent, Seen::Absent],
                    "E3D3_MEMPOOL_BEFORE_STEP_8"
                );
                let ActOutcome::Submitted { entry_id, outcome } = act(&turn) else {
                    panic!("E3D3_NOT_SUBMITTED {turn:?}")
                };
                assert_eq!(
                    [outcome.node_a, outcome.node_b],
                    phase.submitted,
                    "E3D3_SUBMISSION"
                );
                // What step 8 recorded (A #258 issuecomment-6279476947): the
                // journal's last entry, both nodes' answers, after the
                // intent committed inside the guard (#473).
                let Record::Submitted { node_a, node_b, .. } = entry(&launch, entry_id) else {
                    panic!("E3D3_SUBMITTED {turn:?}")
                };
                assert_eq!([node_a, node_b], phase.submitted, "E3D3_SUBMITTED");
                assert_eq!(
                    last_records(&launch, 3),
                    ["BroadcastAuthorized", "SubmissionIntent", "Submitted"],
                    "E3D3_SUBMITTED_LAST"
                );
                steps.push("Broadcast");
            }
            ReadsVerdict::Decided(Verdict::Wait(Wait::OfflineSignaturePending { reservation })) => {
                assert_eq!(
                    hex(&reservation),
                    one(&launch.public, "reservation"),
                    "E3D3_RESERVATION"
                );
                // One hand-off in the outbox, beside the Rust receipt.
                let outbox = listing(&launch.dir.join("outbox"));
                assert_eq!(
                    outbox
                        .iter()
                        .filter(|n| n.starts_with("sign-input-"))
                        .count(),
                    1,
                    "E3D3_OUTBOX"
                );
                steps.push("OfflineSignaturePending");
            }
            ReadsVerdict::Decided(Verdict::Wait(Wait::AwaitingInclusion { txid })) => {
                // 1e-2b-1 L2, L5: a new process after the send hands
                // nothing off (it has the transport and the credential).
                // 1e-2b-2a E9-b: after G's reorg, while the transaction
                // waits in both mempools, the same.
                // 1e-2b-2b E7 (dated 2026-10-31, round 4, A #630
                // issuecomment-6548472857 P3-3): after X -> X' the table
                // stops `e7_waiting` at `BroadcastAuthorityRequired`, so a
                // wait for inclusion there is a regression; fail at once
                // rather than turn to MAX_TURNS.
                assert_ne!(
                    phase.name, "e7_waiting",
                    "E3D3_E7_AWAITING: e7_waiting reached AwaitingInclusion; \
                     the table says BroadcastAuthorityRequired (calls {calls})"
                );
                if B_PHASES.iter().any(|p| p.name == phase.name) || phase.name == "l0_waiting" {
                    assert_eq!(calls, 0, "E3D3_SENT_AGAIN");
                    steps.push("AwaitingInclusion");
                    if steps.last() == Some(&phase.last) {
                        break;
                    }
                    continue;
                }
                let verified = verified.as_ref().expect("E3D3_EXPORT");
                assert_eq!(txid, *verified.txid_internal(), "E3D3_TXID");
                assert_eq!(calls, 1, "E3D3_HAND_OFFS");
                let sent = transport.as_ref().and_then(|t| t.raw_sha256);
                assert_eq!(sent, Some(*verified.raw_tx_sha256()));
                // After `Submitted` the core decides this wait from the
                // record (`machine.rs` `broadcast`), and the host reads no
                // mempool for it: no split is reported, even with the
                // transaction in one node's mempool only (A #258
                // issuecomment-6279476947 M7; the driver reads the nodes).
                assert_eq!(turn.decisions[0].mempool_split, None, "E3D3_MEMPOOL_SPLIT");
                steps.push("AwaitingInclusion");
            }
            // EffectiveFacts (Q-F5): H0 mined with the transaction. The
            // phase's table names the outcome; a `Done` turn acts on nothing
            // and gave the core its facts.
            ReadsVerdict::Decided(Verdict::Done(outcome)) => {
                let name = match outcome {
                    Outcome::Born { .. } => "Done:Born",
                    Outcome::IncludedNoEffect { .. } => "Done:IncludedNoEffect",
                    Outcome::ProjectBornByOther { .. } => "Done:ProjectBornByOther",
                    Outcome::Stale { .. } => "Done:Stale",
                    // BEAT-1: no BEAT candidate runs here.
                    Outcome::BeatAccepted { .. }
                    | Outcome::BeatIncludedNoEffect { .. }
                    | Outcome::BeatAnchorSpent { .. }
                    | Outcome::HeartTimedOut { .. }
                    | Outcome::HeartMaxAge { .. }
                    | Outcome::HeartBroken { .. } => "Done:Beat",
                };
                assert_eq!(name, phase.last, "E3D3_UNEXPECTED {turn:?} after {steps:?}");
                // 1e-2b-2b: P0 mined after the competitor's birth (a later
                // block, or the same one after it): no effect, never
                // relabelled a birth.
                if let Some(included) = lost_included(phase.name) {
                    assert_eq!(outcome, included, "E3D3_LOST_INCLUDED {turn:?}");
                    assert_eq!(
                        turn.decisions[0].report.outcome,
                        Some(included),
                        "E3D3_LOST_REPORTED"
                    );
                    assert!(
                        turn.act.is_none()
                            && turn.authorization.is_none()
                            && turn.effective_held.is_none(),
                        "E3D3_LOST_DONE_ACT {turn:?}"
                    );
                    assert_eq!(turn.marked_final, None, "E3D3_FINAL {turn:?}");
                    steps.push(name);
                    break;
                }
                // R2-b: the continue holder's REGISTER in block H0 + 1, the
                // gate still H0 (block H0 was empty).
                // 1e-2b-2a's E8: born at the block after the late send.
                let born = match phase.name {
                    "r2b_included" => Outcome::Born {
                        height: H0 + 1,
                        at_opening: false,
                    },
                    "e8_included" => Outcome::Born {
                        height: H0 + E8_LATE + 1,
                        at_opening: false,
                    },
                    // B-692a-RT: born at the block after the late send.
                    "l0late_included" => Outcome::Born {
                        height: H0 + L0_LATE + 1,
                        at_opening: false,
                    },
                    _ => Outcome::Born {
                        height: H0,
                        at_opening: true,
                    },
                };
                assert_eq!(outcome, born, "E3D3_BORN {turn:?}");
                // A birth after H0 is one whose opening block was missed.
                assert_eq!(
                    turn.decisions[0].report.opening_block_missed,
                    MISSED_BIRTHS.contains(&phase.name),
                    "E3D3_BORN_MISSED {turn:?}"
                );
                // 1e-2b-2a E4-a and E9-c: `Done` writes nothing and the
                // journal stays in the host file (not archived, B10).
                if l0t {
                    assert_eq!(
                        journal(&launch).len(),
                        before.journal,
                        "E3D3_L0T_DONE_WROTE"
                    );
                    assert!(before.journal > 0, "E3D3_L0T_ARCHIVED");
                    assert!(turn.authorization.is_none(), "E3D3_L0T_DONE_ACT {turn:?}");
                }
                assert!(
                    turn.act.is_none() && turn.effective_held.is_none(),
                    "E3D3_DONE_ACT {turn:?}"
                );
                if phase.name == DEEP.name {
                    // Deeper than step 9's depth, both nodes agreeing: the
                    // journal is marked final at floor H0, and its charge
                    // is settled (its reservation is final).
                    let depth = launch.tip().0 - H0;
                    assert!(
                        depth > bitagi_wallet::reservations::MAX_ANCESTRY_BLOCKS as u64,
                        "E3D3_DEPTH {depth}"
                    );
                    let floor = Floor {
                        height: H0,
                        hash: agreed(&launch.session, |n| n.get_block_hash(H0).unwrap()),
                    };
                    assert!(
                        matches!(
                            turn.marked_final,
                            Some(Marked::Final { journals: 1, floor: f, .. }) if f == floor
                        ),
                        "E3D3_NOT_FINAL {turn:?}"
                    );
                    let finals = HostFile::open(&launch.config.state_dir.join(HOST_FILE))
                        .unwrap()
                        .final_reservations()
                        .unwrap();
                    assert_eq!(
                        finals.iter().map(|r| hex(r)).collect::<Vec<_>>(),
                        [one(&launch.public, "reservation")],
                        "E3D3_NOT_SETTLED"
                    );
                } else {
                    assert_eq!(turn.marked_final, None, "E3D3_FINAL {turn:?}");
                }
                steps.push(name);
            }
            // #484 L0: the window's import is retained (the hand-off
            // evidence), and the core waits for H0 − 1; nothing acted.
            ReadsVerdict::Decided(Verdict::Wait(Wait::SignedAwaitingOpeningGate {
                broadcast_from,
            })) => {
                assert_eq!(broadcast_from, H0 - 1, "E3D3_L0_GATE");
                assert!(
                    turn.act.is_none() && turn.authorization.is_none(),
                    "E3D3_L0_GATE {turn:?}"
                );
                steps.push("SignedAwaitingOpeningGate");
            }
            other => panic!("E3D3_UNEXPECTED {other:?} after {steps:?}"),
        }
        if steps.last() == Some(&phase.last) {
            break;
        }
    }
    assert!(
        decision_refused
            || steps.last() == Some(&phase.last)
            || steps.last() == Some(&"PrestateComparisonPending")
            || steps.last() == Some(&"ReplayComparisonPending")
            || (phase.catch_up && steps == ["LocalTipUnconfirmed"]),
        "E3D3_TURNS {steps:?}"
    );
    // 1e-2b-2a's E8 (T2-8, R32): the late run's checks, admission,
    // prebroadcast checks and authorization are each made once, all at
    // H0 + `E8_LATE`; no admission or authorization was made at H0 − 1
    // or reused from there (B-692b P2a: on the run after its replay
    // comparison).
    if phase.name == "e8_late" && steps.last() == Some(&phase.last) {
        for name in [
            "ExecutionChecks",
            "Admitted",
            "PrebroadcastChecks",
            "BroadcastAuthorized",
            "Submitted",
        ] {
            let heights: Vec<u64> = journal(&launch)
                .iter()
                .filter(|e| record_name(&e.record) == name)
                // The sign path's own checks at H0 − 1 are not this run's.
                .filter(|e| name != "ExecutionChecks" || e.at.height >= H0)
                .map(|e| e.at.height)
                .collect();
            assert_eq!(heights, [H0 + E8_LATE], "E3D3_E8_{name}");
        }
    }
    // B-692a-RT: the late run's checks, admission, prebroadcast checks,
    // authorization and submission are each made once, all at
    // H0 + `L0_LATE` (none at H0 − 2 but the sign path's own checks); after
    // it, and in the birth's new process, the two late prestate rows are
    // read back from the reopened host file.
    if phase.name == "l0late_broadcast" && steps.last() == Some(&phase.last) {
        for name in [
            "ExecutionChecks",
            "Admitted",
            "PrebroadcastChecks",
            "BroadcastAuthorized",
            "Submitted",
        ] {
            let heights: Vec<u64> = journal(&launch)
                .iter()
                .filter(|e| record_name(&e.record) == name)
                .filter(|e| name != "ExecutionChecks" || e.at.height >= H0)
                .map(|e| e.at.height)
                .collect();
            assert_eq!(heights, [H0 + L0_LATE], "E3D3_L0L_{name}");
        }
    }
    if (phase.name == "l0late_broadcast" && steps.last() == Some(&phase.last))
        || phase.name == "l0late_included"
    {
        check_late_rows(&launch);
    }
    Done {
        steps,
        receipt,
        replay_outbox,
        prestate_ms,
        hand_offs: transport.as_ref().map_or(0, |t| t.calls),
        raw_sha256: transport.as_ref().and_then(|t| t.raw_sha256),
        txid: verified.as_ref().map(|v| *v.txid_internal()),
        turns,
        ledger_events: next_event(&launch) - first_event,
        answer_lost: transport
            .as_ref()
            .and_then(|t| t.proxy.as_ref().map(AnswerProxy::dropped)),
        lines_failed: launch.lines_failed(),
        report,
        raw: transport.and_then(|t| t.raw),
    }
}

/// rn-1 phase 2 (module docs).
#[test]
#[ignore = "rn-1 Tier 3: run by tools/claude_track_regtest_offline_export.py"]
fn launch_sign_worker() {
    let done = run_phase(&PHASES[0]);
    report_steps(&done.steps);
    report_prestate(&done);
    report("sign_stage", "PASS");
}

/// rn-1 phase 3 (module docs).
#[test]
#[ignore = "rn-1 Tier 3: run by tools/claude_track_regtest_offline_export.py"]
fn launch_broadcast_worker() {
    let done = run_phase(&PHASES[1]);
    report_steps(&done.steps);
    report_prestate(&done);
    report(
        "raw_tx_sha256",
        &hex(&done.raw_sha256.expect("E3D3_HAND_OFFS")),
    );
    let mut display = done.txid.expect("E3D3_EXPORT");
    display.reverse();
    report("txid", &hex(&display));
    report("hand_offs", &done.hand_offs.to_string());
    report("broadcast_stage", "PASS");
}

/// rn-2, #503's bound pair (`BOUND_PHASES`) and R2-b's (`R2B_PHASES`): the phase
/// `BITAGI_E3D3_PHASE` names, after the driver changed the nodes for it
/// (module docs).
#[test]
#[ignore = "rn-2 Tier 3: run by tools/claude_track_regtest_offline_export.py"]
fn launch_case_worker() {
    let name = env("PHASE");
    let phase = PHASES[2..]
        .iter()
        .chain([&INCLUDED, &DEEP])
        .chain(&BOUND_PHASES)
        .chain(&R2B_PHASES)
        .chain(&E8_PHASES)
        .find(|p| p.name == name)
        .expect("E3D3_PHASE");
    let done = run_phase(phase);
    report("phase", phase.name);
    report_steps(&done.steps);
    report_prestate(&done);
    report("hand_offs", &done.hand_offs.to_string());
    report(
        "raw_tx_sha256",
        &done.raw_sha256.map_or_else(|| "-".to_owned(), |h| hex(&h)),
    );
    report("turns", &done.turns.to_string());
    if let Some(lost) = done.answer_lost {
        report("answer_lost", &lost.to_string());
    }
    report("case_stage", "PASS");
}

/// 1e-2b-1 (B #258 issuecomment-6341419417, A -6342681379): new processes
/// after rn-1's and rn-2's sends (L2, L5) and X -> X' after rn-1's (L3).
/// Each has the transport and the send credential, so a send again is a
/// hand-off.
const B_PHASES: [Phase; 3] = [
    Phase {
        name: "after_send",
        init: false,
        export: Export::Stored,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "AwaitingInclusion",
    },
    Phase {
        name: "cn01",
        init: false,
        export: Export::Stored,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: SENT,
        raises: None,
        catch_up: false,
        ledger: None,
        last: "Refuse:Locked(Reorg67)",
    },
    Phase {
        name: "after_send_one",
        init: false,
        export: Export::Stored,
        tip: Some(H0 - 1),
        admitted: ACCEPTED,
        submitted: [NodeSubmission::Accepted, NodeSubmission::Rejected],
        raises: None,
        catch_up: false,
        ledger: None,
        last: "AwaitingInclusion",
    },
];

/// 1e-2b-1: the phase `BITAGI_E3D3_PHASE` names (`B_PHASES`).
#[test]
#[ignore = "1e-2b-1 Tier 3: run by tools/claude_track_regtest_offline_export.py"]
fn launch_b_worker() {
    let name = env("PHASE");
    let phase = B_PHASES
        .iter()
        .find(|p| p.name == name)
        .expect("E3D3_PHASE");
    let done = run_phase(phase);
    report("phase", phase.name);
    report_steps(&done.steps);
    report("hand_offs", &done.hand_offs.to_string());
    report("lines_failed", &done.lines_failed.to_string());
    report("turns", &done.turns.to_string());
    report("b_stage", "PASS");
}

/// 1e-2a: the E phase `BITAGI_E3D3_PHASE` names (`E_PHASES`), after the
/// driver changed the nodes for it. No E phase has the send credential.
#[test]
#[ignore = "1e-2a Tier 3: run by tools/claude_track_regtest_offline_export.py"]
fn launch_e_worker() {
    assert!(
        std::env::var_os("BITAGI_E3D3_SEND_AUTH").is_none(),
        "E3D3_E_SEND_AUTH"
    );
    let name = env("PHASE");
    let phase = E_PHASES
        .iter()
        .find(|p| p.name == name)
        .expect("E3D3_PHASE");
    let done = run_phase(phase);
    assert_eq!(done.hand_offs, 0, "E3D3_E_HAND_OFF");
    report("phase", phase.name);
    report_steps(&done.steps);
    report_prestate(&done);
    report("hand_offs", &done.hand_offs.to_string());
    report("ledger_events", &done.ledger_events.to_string());
    report("turns", &done.turns.to_string());
    report("e_stage", "PASS");
}

/// #484 L0: the phase `BITAGI_E3D3_PHASE` names (`L0_PHASES`, `L0T_PHASES`,
/// B-692a-RT's `L0L_PHASES`), after the driver changed the nodes for it
/// (module docs).
#[test]
#[ignore = "#484 L0 Tier 3: run by tools/claude_track_regtest_offline_export.py"]
fn launch_l0_worker() {
    let name = env("PHASE");
    let phase = L0_PHASES
        .iter()
        .chain(&L0T_PHASES)
        .chain(&L0L_PHASES)
        .find(|p| p.name == name)
        .expect("E3D3_PHASE");
    let done = run_phase(phase);
    report("phase", phase.name);
    report_steps(&done.steps);
    report_prestate(&done);
    report("hand_offs", &done.hand_offs.to_string());
    report(
        "raw_tx_sha256",
        &done.raw_sha256.map_or_else(|| "-".to_owned(), |h| hex(&h)),
    );
    report("turns", &done.turns.to_string());
    report("l0_stage", "PASS");
}

/// 1e-2b-2b: the phase `BITAGI_E3D3_PHASE` names (`E10_PHASES`,
/// `E7_PHASES`, `L0D_PHASES`), after the driver changed the nodes for it.
/// Every line is reported, `-` where it does not apply.
#[test]
#[ignore = "1e-2b-2b Tier 3: run by tools/claude_track_regtest_offline_export.py"]
fn launch_lost_worker() {
    let name = env("PHASE");
    let phase = E10_PHASES
        .iter()
        .chain(&E7_PHASES)
        .chain(&L0D_PHASES)
        .find(|p| p.name == name)
        .expect("E3D3_PHASE");
    let done = run_phase(phase);
    // B's two named assertions (unit note §2.2). E7: lost with the mark,
    // then mined with no effect and the mark kept.
    if matches!(phase.name, "e7_lost" | "e7_included") {
        let expected = if phase.name == "e7_lost" {
            format!("missed=true;reorged=true;outcome=Stale:{H0}:")
        } else {
            format!(
                "missed=true;reorged=true;outcome=IncludedNoEffect:{}",
                H0 + 1
            )
        };
        assert!(
            done.report
                .as_deref()
                .is_some_and(|r| r.starts_with(&expected)),
            "E3D3_E7_REORGED_NO_EFFECT {:?}",
            done.report
        );
    }
    // E7b, "proxy drop + mark present" (B's pre-PR review P3-3,
    // 2026-10-31; the code name is kept): at `e7_broadcast` the proxy
    // dropped one answer of node A (its count only; the journal's
    // `Submitted` is `Accepted, Accepted`, the transport's read after the
    // drop finding P0 in node A's mempool); from `e7_reorged` on the
    // report's `reorged=true` (LOST_REPORTS' flag, repeated here); and no
    // hand-off after the broadcast. It does not show which answer set the
    // mark: step 8's `SubmissionIntent` marks it whatever the answers
    // (`phase_machine.rs` `node_bs_acceptance_alone_marks_a20` isolates
    // node B's answer).
    if phase.name.starts_with("e7_") && phase.name != "e7_sign" {
        let lost = phase.name != "e7_broadcast" || done.answer_lost == Some(1);
        let marked = matches!(phase.name, "e7_sign" | "e7_broadcast")
            || done
                .report
                .as_deref()
                .is_some_and(|r| r.contains(";reorged=true;"));
        let quiet = phase.name == "e7_broadcast" || done.hand_offs == 0;
        assert!(
            lost && marked && quiet,
            "E3D3_E7B_ANSWER_LOST_MARK (proxy drop + mark present) {:?}",
            done.report
        );
    }
    // From the broadcast on: exactly one `Submitted`, of the retained
    // transaction (1E `:902`), one authorization and one signature
    // hand-off (no second signature, T2-11).
    let submitted = if phase.name.ends_with("_sign") {
        "-".to_owned()
    } else {
        let records = journal(&Launch::new());
        let submitted: Vec<_> = records
            .iter()
            .filter_map(|e| match e.record {
                Record::Submitted {
                    txid,
                    node_a,
                    node_b,
                    ..
                } => Some((txid, node_a, node_b)),
                _ => None,
            })
            .collect();
        let [(txid, node_a, node_b)] = submitted[..] else {
            panic!("E3D3_LOST_SUBMITTED {}", submitted.len())
        };
        for name in ["BroadcastAuthorized", "SigningHandedOff"] {
            assert_eq!(
                records
                    .iter()
                    .filter(|e| record_name(&e.record) == name)
                    .count(),
                1,
                "E3D3_LOST_{name}"
            );
        }
        let mut display = txid;
        display.reverse();
        format!("{node_a:?},{node_b:?};txid={}", hex(&display))
    };
    report("phase", phase.name);
    report_steps(&done.steps);
    report_prestate(&done);
    report("hand_offs", &done.hand_offs.to_string());
    report(
        "raw_tx_sha256",
        &done.raw_sha256.map_or_else(|| "-".to_owned(), |h| hex(&h)),
    );
    report(
        "raw_tx_hex",
        &done.raw.as_deref().map_or_else(|| "-".to_owned(), hex),
    );
    report(
        "answer_lost",
        &done
            .answer_lost
            .map_or_else(|| "-".to_owned(), |n| n.to_string()),
    );
    report("submitted", &submitted);
    report("report", done.report.as_deref().unwrap_or("-"));
    report("turns", &done.turns.to_string());
    report("lost_stage", "PASS");
}

/// CT-P5-001 D1t: the leading variant names of a `Debug` text
/// (`Decided(Done(Born { .. }))` gives `Decided:Done:Born`): no field
/// value is reported.
fn variant_path(debug: &str) -> String {
    debug
        .split(['(', ' ', '{'])
        .take_while(|w| !w.is_empty() && w.chars().all(|c| c.is_ascii_alphanumeric() || c == '_'))
        .collect::<Vec<_>>()
        .join(":")
}

/// CT-P5-001 D1t (throughput): one production turn by a freshly started
/// host on the L0 launch the driver took to `Done:Born`, at whatever tip it
/// mined since, as a witness host turns once per block during the 4,096
/// wait. It measures and reports; it asserts no decision (the driver
/// checks the lines): the turn's decision as variant names, whether step 9
/// marked the journal final, the stops it raised, whether the ledger
/// rotated, the ledger events the turn made and its own milliseconds.
/// Nothing is sent: no transport.
#[test]
#[ignore = "CT-P5-001 D1t: run by tools/claude_track_ardr_throughput.py"]
fn launch_idle_worker() {
    let launch = Launch::new();
    let candidates = launch.host_dir().join("candidates.txt");
    let first_event = next_event(&launch);
    let started = std::time::Instant::now();
    let turn = launch
        .turn(&candidates, None, None, None, None)
        .expect("E3D3_TURN");
    let took = started.elapsed().as_millis();
    let decision = match &turn.decisions[..] {
        [one] => match &one.verdict {
            ReadsVerdict::Refuse(refusal) => {
                format!("Refuse:{}", variant_path(&format!("{:?}", refusal.code)))
            }
            verdict => variant_path(&format!("{verdict:?}")),
        },
        several => format!("Decisions:{}", several.len()),
    };
    report("tip", &launch.tip().0.to_string());
    report("decision", &decision);
    report(
        "marked_final",
        if turn.marked_final.is_some() {
            "1"
        } else {
            "0"
        },
    );
    report("persisted", &turn.persisted.len().to_string());
    report(
        "ledger_rotated",
        if turn.ledger_rotated { "1" } else { "0" },
    );
    report(
        "ledger_events",
        &(next_event(&launch) - first_event).to_string(),
    );
    report("turn_ms", &took.to_string());
    report("idle_stage", "PASS");
}

// ------------------------------------------------------------- transport

// ---------------------------------------------------------------- B-Q17c-2

/// B-Q17c-2 (1D3 Q17, FD-CT-62 line; A #258 issuecomment-6526114647): the
/// performed step-6 rows on the E phases' charge, run by
/// `tools/claude_track_regtest_reorg_step6.py`. One action per process
/// (`BITAGI_E3D3_STEP6_ACTION`), so the driver runs the step-6 tool
/// between them:
///
/// - `turn`: one production turn over the verified export, as an E phase
///   after the import does; a turn whose hook raised keeps the reorg's
///   identity (the operator's copy, #450 runbook §2 item 1);
/// - `below_identity`: E-B's `Below` identity, which no turn reported
///   (`save_below_copy`'s reading: the nodes' tip, no agreed hash);
/// - `abort`: the (나) row's reorg turn, a harness-inserted abort right
///   after the raise, NOT a production turn: the host's own hooks, wrapped
///   as `two_node_reorg.rs` wraps them, and `std::process::abort` after
///   `on_non_extending` returned, so no ancestor is bound and the store is
///   unchanged. The hook lives in this test file only;
/// - `export`: [`LaunchHost::export_step6`] into the step-6 outbox, a 0700
///   directory beside the launch directory's others and inside none;
/// - `facts`: the one `STEP6_FACTS <canonical JSON>` line for the tool's
///   `record --facts`, read from the ledger's watermark, the host file
///   (its ancestor and `record_log`), the store's rows and, for an
///   ancestor below H0 only, the export's start digest; read with no host
///   running;
/// - `release`: one production turn with the operator's procedure file V2
///   and its step-6 documents (`HostConfig::load_procedure`).
///
/// Each action reports its result (`Ok`, a host error's code, `RELEASED`)
/// and whether the Reorg67 lock is open. Nothing is sent: no transport,
/// no send credential.
fn step6_launch() -> Launch {
    let mut launch = Launch::new();
    launch.config.step6_outbox = Some(launch.dir.join("step6-outbox"));
    launch
}

fn step6_identity_path(launch: &Launch) -> PathBuf {
    launch.dir.join("step6-identity.txt")
}

fn save_step6_identity(launch: &Launch, identity: &bitagi_launch::reorg::NonExtending) {
    let at_local = match identity.at_local {
        AtLocal::Agreed(hash) => hex(&hash),
        AtLocal::Below => "below".to_owned(),
    };
    let text = format!(
        "local_height={}\nlocal_hash={}\nagreed_at_local={at_local}\n",
        identity.local.0,
        hex(&identity.local.1)
    );
    write_private(&step6_identity_path(launch), text.as_bytes());
}

fn load_step6_identity(launch: &Launch) -> bitagi_launch::reorg::NonExtending {
    let text = std::fs::read_to_string(step6_identity_path(launch)).expect("E3D3_STEP6_IDENTITY");
    let at_local = match one(&text, "agreed_at_local") {
        "below" => AtLocal::Below,
        hash => AtLocal::Agreed(unhex32(hash)),
    };
    bitagi_launch::reorg::NonExtending {
        local: (
            one(&text, "local_height")
                .parse()
                .expect("E3D3_STEP6_IDENTITY"),
            unhex32(one(&text, "local_hash")),
        ),
        at_local,
    }
}

fn reorg67_word(launch: &Launch) -> &'static str {
    if open_locks(launch).contains(&LockReason::Reorg67) {
        "OPEN"
    } else {
        "RELEASED"
    }
}

/// The candidate file with the verified export's retained bytes, the
/// export and the broadcast authorization an earlier phase wrote, as the
/// E phases after the import present them.
fn step6_inputs(launch: &Launch) -> (PathBuf, PathBuf, Option<PathBuf>) {
    let (export, verified) = verified_export(launch);
    assert_eq!(
        *verified.wallet_candidate(),
        launch.wallet_candidate(),
        "E3D3_ROW"
    );
    let candidates = launch.write_candidates(Some(&verified));
    let authority = Some(launch.host_dir().join("authority-broadcast.txt")).filter(|p| p.exists());
    (candidates, export, authority)
}

fn step6_turn(launch: &Launch) -> String {
    let (candidates, export, authority) = step6_inputs(launch);
    match launch.turn(&candidates, authority.as_deref(), Some(&export), None, None) {
        Ok(turn) => {
            if let Some(seen) = turn.reorg_seen.as_ref().filter(|s| s.raised) {
                save_step6_identity(launch, &seen.identity);
                report("reorg", "raised");
            } else {
                report("reorg", "none");
            }
            "Ok".to_owned()
        }
        Err(error) => {
            report("reorg", "none");
            error.to_string()
        }
    }
}

/// The (나) row's hooks: the host's own, with the process aborted right
/// after `on_non_extending` returned (`two_node_reorg.rs` `Stop::AfterRaise`).
struct AbortAfterRaise<'a, 'h> {
    inner: &'a mut bitagi_launch_host::HostHooks<'h>,
}

impl bitagi_bitcoin::FollowerHooks for AbortAfterRaise<'_, '_> {
    fn on_non_extending(
        &mut self,
        event: bitagi_bitcoin::NonExtending,
    ) -> Result<(), bitagi_bitcoin::HookRefused> {
        self.inner.on_non_extending(event)?;
        report("abort", "after-raise");
        std::process::abort();
    }

    fn on_ancestor(
        &mut self,
        height: CoreHeight,
        hash: BitcoinInternalHash32,
    ) -> Result<(), bitagi_bitcoin::HookRefused> {
        self.inner.on_ancestor(height, hash)
    }

    fn on_block(
        &mut self,
        height: CoreHeight,
        hash: BitcoinInternalHash32,
        block: &bitagi_bitcoin::AgreedRawBlock,
    ) -> Result<(), bitagi_bitcoin::HookRefused> {
        self.inner.on_block(height, hash, block)
    }
}

/// The (나) row's reorg turn (harness-inserted abort, not a production
/// turn). The identity is saved first: the store's tip and the nodes'
/// agreed block at its height. Never returns while the hook raises.
fn step6_abort(launch: &Launch) -> String {
    use bitagi_bitcoin::node_configuration::NodeRole;
    use bitagi_bitcoin::{ActiveChainFollower, verify_node};
    use bitagi_wallet::reservations::Origin;
    let config = &launch.config;
    let local = launch.store_tip();
    let (a, b) = launch.session.nodes();
    let at_local = agreed(&launch.session, |n| n.get_block_hash(local.0).unwrap());
    assert_ne!(at_local, local.1, "E3D3_STEP6_NOT_REPLACED");
    save_step6_identity(
        launch,
        &bitagi_launch::reorg::NonExtending {
            local,
            at_local: AtLocal::Agreed(at_local),
        },
    );
    // The production start, for its refusals in order; the run below opens
    // the same three files as the host does.
    if let Err(error) = LaunchHost::start(config.clone()) {
        return error.to_string();
    }
    let deployment = deployment_id(&config.profile);
    let mut ledger = ReservationLedger::open_expected(
        &config.ledger_path,
        config.ledger_identity.clone(),
        Origin::TrustedLocalRestart,
    )
    .unwrap();
    let mut host_file = HostFile::open(&config.state_dir.join(HOST_FILE)).unwrap();
    let mut store = bitagi_store::SqliteStore::open_for_context(
        config.state_dir.join(bitagi_launch_host::REPLAY_STORE),
        bitagi_store::StoreContextBinding::new(
            deployment,
            substrate_context_hash(&config.descriptor),
            config.descriptor.genesis_hash(),
        )
        .unwrap(),
    )
    .unwrap();
    let inspection =
        ReservationLedger::inspect(&config.ledger_path, &config.ledger_identity).unwrap();
    let summary = inspection.history_summary().unwrap();
    let epoch = inspection.next_event - 1;
    let a = verify_node(&config.descriptor, &a, NodeRole::A, &config.record_set).unwrap();
    let b = verify_node(&config.descriptor, &b, NodeRole::B, &config.record_set).unwrap();
    let mut hooks = bitagi_launch_host::HostHooks::new(
        &mut ledger,
        &mut host_file,
        H0,
        epoch,
        bitagi_launch_host::launch_history(&summary, inspection.rust_departed()),
    );
    let mut watch = AbortAfterRaise { inner: &mut hooks };
    match ActiveChainFollower::synchronize_verified(
        &a, &b, &mut store, deployment, &mut watch, None,
    ) {
        Ok(_) => "NO_REORG".to_owned(),
        Err(_) => "HOST_HOOK_REFUSED".to_owned(),
    }
}

fn step6_export(launch: &Launch) -> String {
    let identity = load_step6_identity(launch);
    let host = match LaunchHost::start(launch.config.clone()) {
        Ok(host) => host,
        Err(error) => return error.to_string(),
    };
    let (a, b) = launch.session.nodes();
    match host.export_step6(&a, &b, identity) {
        Ok(exported) => {
            report("export", &exported.name);
            "Ok".to_owned()
        }
        Err(error) => error.to_string(),
    }
}

/// The STEP6_FACTS line (the tool's `FACTS_KEYS`), from this process's own
/// reads, no host running: the identity the operator kept, the ledger's
/// watermark, the host file's ancestor for it (or the identity's local tip,
/// the unchanged tip), the store's rows and, below H0, the export's start
/// digest (the initial state recomputed, F §7). Step 7 is the first
/// `record_log` agreement as the host's `step7_agreement` takes it; with
/// none yet, the export tip and the watermark event stand in, and the
/// host's release turn writes the row and refuses with
/// HOST_STEP6_AGREEMENT_RECORDED_THIS_TURN (the driver's one retry).
fn step6_facts(launch: &Launch) -> String {
    use bitagi_bitcoin::critical_height::HeightAgreementRecord;
    let identity = load_step6_identity(launch);
    let (watermark_event, incident) = reorg_watermark(launch).expect("E3D3_STEP6_WATERMARK");
    assert_eq!(incident, identity.incident(), "E3D3_STEP6_INCIDENT");
    let host_file = HostFile::open(&launch.config.state_dir.join(HOST_FILE)).unwrap();
    let ancestor = host_file
        .state()
        .ancestor
        .filter(|a| a.watermark_event == watermark_event && a.incident == incident)
        .map_or(identity.local, |a| (a.height, a.hash));
    let log = host_file.record_log().unwrap();
    drop(host_file);
    let deployment = deployment_id(&launch.config.profile);
    let store = bitagi_store::SqliteStore::open_read_only_for_context(
        launch
            .config
            .state_dir
            .join(bitagi_launch_host::REPLAY_STORE),
        bitagi_store::StoreContextBinding::new(
            deployment,
            substrate_context_hash(&launch.config.descriptor),
            launch.config.descriptor.genesis_hash(),
        )
        .unwrap(),
    )
    .expect("E3D3_STORE");
    let snapshot = store.snapshot(deployment).expect("E3D3_STORE");
    let tip = snapshot.as_of_height().value();
    let row = |height: u64| {
        store
            .height_rows(deployment, CoreHeight::new(height))
            .expect("E3D3_STORE")
            .expect("E3D3_STEP6_ROW")
    };
    let h0_minus_1 = if tip >= H0 {
        row(H0).parent_hash().into_internal_bytes()
    } else {
        snapshot.as_of_block_hash().into_internal_bytes()
    };
    let hash_at = |height: u64| -> Option<[u8; 32]> {
        match height {
            h if h + 1 == H0 => Some(h0_minus_1),
            h if (H0..=tip).contains(&h) => Some(row(h).block_hash().into_internal_bytes()),
            _ => None,
        }
    };
    // The export's documents: T_e is the replacement manifest's last block
    // (H0 - 1 with none), as the host's release takes it from the record,
    // so a store that moved past T_e changes no fact.
    let name = std::env::var("BITAGI_E3D3_STEP6_EXPORT").expect("E3D3_STEP6_EXPORT");
    let side = launch
        .dir
        .join("step6-outbox")
        .join(name)
        .join("replacement");
    let read_side = |file: &str| -> serde_json::Value {
        serde_json::from_slice(&std::fs::read(side.join(file)).expect("E3D3_STEP6_EXPORT")).unwrap()
    };
    let t_e = read_side("manifest.json")["blocks"]
        .as_array()
        .expect("E3D3_STEP6_EXPORT")
        .last()
        .map_or(H0 - 1, |block| {
            block["height"].as_u64().expect("E3D3_STEP6_EXPORT")
        });
    assert!(t_e <= tip, "E3D3_STEP6_T_E");
    let restored = if ancestor.0 >= H0 {
        *row(ancestor.0).state_digest()
    } else {
        unhex32(
            read_side("rust_result.json")["start_state_digest"]
                .as_str()
                .expect("E3D3_STEP6_EXPORT"),
        )
    };
    let store_final = if t_e >= H0 {
        *row(t_e).state_digest()
    } else {
        restored
    };
    let agreement = log
        .iter()
        .filter(|e| e.epoch >= watermark_event && (ancestor.0..=t_e).contains(&e.height))
        .find_map(|e| {
            HeightAgreementRecord::from_canonical_bytes(&e.record)
                .ok()
                .filter(|r| {
                    r.height() == e.height && hash_at(e.height) == Some(r.block_hash_internal())
                })
                .map(|r| (e.height, r.block_hash_internal(), e.epoch))
        });
    report(
        "agreement",
        if agreement.is_some() {
            "recorded"
        } else {
            "none"
        },
    );
    let agreed = agreement.unwrap_or((t_e, hash_at(t_e).expect("E3D3_STEP6_TIP"), watermark_event));
    let at_local = match identity.at_local {
        AtLocal::Agreed(hash) => serde_json::Value::from(hex(&hash)),
        AtLocal::Below => serde_json::Value::from("below"),
    };
    let facts: std::collections::BTreeMap<&str, serde_json::Value> = [
        ("incident_sha256", hex(&incident).into()),
        ("watermark_event", watermark_event.into()),
        ("local_height", identity.local.0.into()),
        ("local_hash_internal", hex(&identity.local.1).into()),
        ("agreed_at_local_internal", at_local),
        ("ancestor_height", ancestor.0.into()),
        ("ancestor_hash_internal", hex(&ancestor.1).into()),
        (
            "restored_source",
            if t_e > ancestor.0 {
                "UNDO_ROW"
            } else {
                "SNAPSHOT"
            }
            .into(),
        ),
        (
            "reference_source",
            if ancestor.0 >= H0 {
                "STORE_BLOCK_ROW"
            } else {
                "INITIAL_RECOMPUTED"
            }
            .into(),
        ),
        ("restored_state_digest", hex(&restored).into()),
        ("store_final_state_digest", hex(&store_final).into()),
        ("agreed_tip_height", agreed.0.into()),
        ("agreed_tip_hash_internal", hex(&agreed.1).into()),
        ("agreement_event", agreed.2.into()),
        ("first_unavailable_height", serde_json::Value::Null),
        ("first_unavailable_hash_internal", serde_json::Value::Null),
    ]
    .into_iter()
    .collect();
    let line = format!("STEP6_FACTS {}", serde_json::to_string(&facts).unwrap());
    assert!(line.len() < 4096, "E3D3_STEP6_FACTS");
    let mut out = std::io::stdout().lock();
    writeln!(out, "{line}").unwrap();
    out.flush().unwrap();
    "Ok".to_owned()
}

fn step6_release(launch: &Launch) -> String {
    let documents = PathBuf::from(env("STEP6_DOCUMENTS"));
    let python = documents.join("python");
    let disconnected = python.join("disconnected_result.json");
    let paths = bitagi_launch_host::procedure::Step6DocumentPaths {
        record: documents.join("step6_record.json"),
        leg_record: documents.join("leg_record.json"),
        replacement_python_result: python.join("replacement_result.json"),
        replacement_report: python.join("replacement_report.json"),
        disconnected: disconnected
            .exists()
            .then(|| (disconnected, python.join("disconnected_report.json"))),
        // B-692 CF-2: the tool writes `NOT_APPLICABLE` step 8 only, so no
        // claims list (`tools/claude_track_reorg_step6.py` `step8_object`).
        claims_list: None,
    };
    let procedure = match launch
        .config
        .load_procedure(&documents.join("procedure.txt"), Some(&paths))
    {
        Ok(procedure) => procedure,
        Err(error) => return error.to_string(),
    };
    let (candidates, export, authority) = step6_inputs(launch);
    match launch.turn_with(
        &candidates,
        authority.as_deref(),
        Some(&export),
        None,
        None,
        || Some(procedure),
    ) {
        Ok(turn) => match turn.released {
            Some(released)
                if released.step6
                    == Some(bitagi_launch_host::procedure::Step6Status::Performed) =>
            {
                "RELEASED".to_owned()
            }
            _ => "NOT_RELEASED".to_owned(),
        },
        Err(error) => error.to_string(),
    }
}

/// B-Q17c-2: the action `BITAGI_E3D3_STEP6_ACTION` names (module docs of
/// `step6_launch`), after the driver changed the nodes for it.
#[test]
#[ignore = "B-Q17c-2 Tier 3: run by tools/claude_track_regtest_reorg_step6.py"]
fn launch_step6_worker() {
    assert!(
        std::env::var_os("BITAGI_E3D3_SEND_AUTH").is_none(),
        "E3D3_STEP6_SEND_AUTH"
    );
    let action = env("STEP6_ACTION");
    let launch = step6_launch();
    report("action", &action);
    let result = match action.as_str() {
        "turn" => step6_turn(&launch),
        "below_identity" => {
            let (height, hash) = launch.tip();
            let identity = bitagi_launch::reorg::NonExtending {
                local: (height, hash),
                at_local: AtLocal::Below,
            };
            let watermark = reorg_watermark(&launch).expect("E3D3_BELOW_WATERMARK");
            assert_eq!(watermark.1, identity.incident(), "E3D3_BELOW_INCIDENT");
            save_step6_identity(&launch, &identity);
            "Ok".to_owned()
        }
        "abort" => step6_abort(&launch),
        "export" => step6_export(&launch),
        "facts" => step6_facts(&launch),
        "release" => step6_release(&launch),
        _ => panic!("E3D3_STEP6_ACTION"),
    };
    report("result", &result);
    report("lock", reorg67_word(&launch));
    report("step6_stage", "PASS");
}

/// The submitting method, named once: the describe stage's HTTP 403 check
/// of the read user (the product transport names its own).
const SEND_METHOD: &str = "sendrawtransaction";

/// Step 8's transport: the product one (`bitagi_launch_transport`, 1e-0),
/// built for each hand-off on a read session of its own and the send-only
/// user the driver made for this run (module docs). It keeps the hand-off
/// count and the hash of the bytes it was shown, for the phase's report;
/// the bytes only for 1e-2b-2b's `LOST_KEEPS_BYTES` phase.
struct ProductTransport {
    /// The send-only user's name, and its password in an owner-only file
    /// already unlinked (never printed).
    user: String,
    secret: std::fs::File,
    calls: usize,
    raw_sha256: Option<[u8; 32]>,
    /// 1e-2b-2b: the bytes handed off, kept only when the phase reports
    /// them (`LOST_KEEPS_BYTES`, Q-b5).
    keep: bool,
    raw: Option<Vec<u8>>,
    /// 1e-2b-1 L4 (`BITAGI_E3D3_ANSWER_PROXY=A`): node A's port through the
    /// answer-dropping proxy, for the checks, the send and the read after.
    proxy: Option<AnswerProxy>,
}

impl ProductTransport {
    /// The send-only user from the driver. It may not read: each node
    /// answers HTTP 403 to its `getblockchaininfo` before the call runs
    /// (T5; the read user's refusal to send is the describe stage's).
    fn new() -> Self {
        let auth = env("SEND_AUTH");
        for port in ports() {
            let (status, _) = rpc(port, &base64(auth.as_bytes()), "getblockchaininfo", "[]");
            assert_eq!(status, Some(403), "E3D3_SEND_USER_MAY_READ");
        }
        let (user, password) = auth.split_once(':').expect("E3D3_SEND_AUTH");
        let proxy = match std::env::var("BITAGI_E3D3_ANSWER_PROXY").as_deref() {
            Ok("A") => Some(AnswerProxy::start(ports()[0])),
            Ok(_) => panic!("E3D3_ANSWER_PROXY"),
            Err(_) => None,
        };
        Self {
            user: user.to_owned(),
            secret: secret_file(password),
            calls: 0,
            raw_sha256: None,
            keep: false,
            raw: None,
            proxy,
        }
    }

    /// The password as the transport takes it: the file's descriptor,
    /// rewound. The file was opened once, before any hand-off (1e-0f, A
    /// #487 issuecomment-6378547674): no path is opened again under the
    /// guard.
    fn secret(&self) -> std::os::fd::OwnedFd {
        use std::io::Seek as _;
        (&self.secret)
            .rewind()
            .and_then(|()| self.secret.try_clone())
            .expect("E3D3_SEND_FILE")
            .into()
    }
}

/// An owner-only file holding `password`, unlinked before it is written,
/// so the path never names the password and nothing is left behind.
fn secret_file(password: &str) -> std::fs::File {
    use std::os::unix::fs::OpenOptionsExt as _;
    let path = std::env::temp_dir().join(format!("bitagi-e3d3-send-{}", std::process::id()));
    let mut file = std::fs::OpenOptions::new()
        .read(true)
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(&path)
        .expect("E3D3_SEND_FILE");
    std::fs::remove_file(&path).expect("E3D3_SEND_FILE");
    file.write_all(password.as_bytes()).expect("E3D3_SEND_FILE");
    file
}

impl BroadcastHandOff for ProductTransport {
    type Error = TransportFailed;
    fn hand_off(
        &mut self,
        raw: bitagi_wallet::reservations::GuardedRaw<'_>,
    ) -> Result<HandOffOutcome, TransportFailed> {
        self.calls += 1;
        self.raw_sha256 = Some(bitagi_hash::sha256(raw.as_bytes()));
        if self.keep {
            self.raw = Some(raw.as_bytes().to_vec());
        }
        let [a, b] = ports();
        let a = self.proxy.as_ref().map_or(a, AnswerProxy::port);
        let session = RpcSession::replay([a, b], 16, Duration::from_secs(60)).expect("E3D3_RPC");
        let send = SendCredential::from_fd(&self.user, self.secret()).expect("E3D3_SEND_AUTH");
        RegtestTransport::new(bitcoin::Network::Regtest, session, send)
            .expect("E3D3_TRANSPORT")
            .hand_off(raw)
    }
}

/// `Basic` authorization for the public fixture credential, the read user
/// the driver whitelists to the product client's reads.
fn fixture_authorization() -> String {
    let password = hex(&bitagi_hash::sha256(AUTH_RECIPE));
    base64(format!("{AUTH_USER}:{password}").as_bytes())
}

fn base64(bytes: &[u8]) -> String {
    const TABLE: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::new();
    for chunk in bytes.chunks(3) {
        let n = chunk
            .iter()
            .enumerate()
            .fold(0_u32, |n, (i, b)| n | (u32::from(*b) << (16 - 8 * i)));
        for i in 0..4 {
            if i <= chunk.len() {
                out.push(char::from(TABLE[((n >> (18 - 6 * i)) & 63) as usize]));
            } else {
                out.push('=');
            }
        }
    }
    out
}

/// One JSON-RPC call to the node at `port` as `authorization` (base64
/// `user:password`): the HTTP status, or `None` when it does not answer,
/// and the body. Only the two users' refusal checks call it.
fn rpc(port: u16, authorization: &str, method: &str, params: &str) -> (Option<u16>, String) {
    let body = format!(
        "{{\"jsonrpc\":\"1.0\",\"id\":\"rn-1\",\"method\":\"{method}\",\"params\":{params}}}"
    );
    let request = format!(
        "POST / HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Basic {authorization}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    let Ok(mut stream) = std::net::TcpStream::connect(("127.0.0.1", port)) else {
        return (None, String::new());
    };
    let timeout = Some(Duration::from_secs(60));
    if stream.set_read_timeout(timeout).is_err()
        || stream.set_write_timeout(timeout).is_err()
        || stream.write_all(request.as_bytes()).is_err()
    {
        return (None, String::new());
    }
    let mut response = String::new();
    if stream.take(1 << 20).read_to_string(&mut response).is_err() {
        return (None, String::new());
    }
    let status = response
        .strip_prefix("HTTP/1.1 ")
        .and_then(|rest| rest.get(..3))
        .and_then(|code| code.parse().ok());
    let body = response
        .split_once("\r\n\r\n")
        .map_or(String::new(), |(_, body)| body.to_owned());
    (status, body)
}

/// The base64 encoder against known vectors (RFC 4648 section 10).
#[test]
fn base64_vectors() {
    for (plain, encoded) in [
        ("", ""),
        ("f", "Zg=="),
        ("fo", "Zm8="),
        ("foo", "Zm9v"),
        ("foob", "Zm9vYg=="),
        ("fooba", "Zm9vYmE="),
        ("foobar", "Zm9vYmFy"),
    ] {
        assert_eq!(base64(plain.as_bytes()), encoded);
    }
}

/// The fixture credential is the driver's and the product's: the recipe and
/// user are the ones `rpc_credentials.rs` and the driver name.
#[test]
fn the_credential_is_the_public_fixture() {
    let product = std::fs::read_to_string(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../bitagi-bitcoin/src/rpc_credentials.rs"
    ))
    .unwrap();
    assert!(product.contains("b\"BITAGI/P3-008/PUBLIC-AUTH/V1\""));
    let driver = std::fs::read_to_string(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../tools/claude_track_regtest_offline_export.py"
    ))
    .unwrap();
    assert!(driver.contains("AUTH_RECIPE = \"BITAGI/P3-008/PUBLIC-AUTH/V1\""));
    assert!(driver.contains("AUTH_USER = \"-\".join((\"bitagi\", \"class\", \"t\"))"));
    assert_eq!(AUTH_USER, ["bitagi", "class", "t"].join("-"));
}

// ---------------------------------------------------------------- CT-P5-001 D3a-1b
// `launch_set_worker` is run by `tools/claude_track_ardr_l0.py` (the item-2 L0 seat's ladder), not by
// `tools/claude_track_regtest_offline_export.py`; its lines are checked by that tool's own cells
// (`tests/claude_track/test_ardr_l0.py`), as D1t's idle worker is. Class T Regtest development evidence
// only. From the D3a-0 spike (`claude/b-p5001-d3a0-ladder-spike`), reviewed in D3a-1b.

/// The set worker's phases (`SET_PHASES` in the L0 tool). D3a-2b-2a adds `set_reorged` and `set_release`
/// (item 4's REORG with the L0 seat, Class T Regtest only).
const SET_PHASES: [&str; 8] = [
    "set_sign",
    "set_wait",
    "set_ready",
    "set_send",
    "set_broadcast",
    "set_observe",
    "set_reorged",
    "set_release",
];
/// D3a-2b-2a (A #258 issuecomment-6557723699 Q4 (가)): `set_release` runs only when the operator's TEST_ONLY
/// release record `host/release-record.txt` (written by the L0 tool's `RELEASE_REORG67_TEST_ONLY` phase) is
/// exactly these bytes; the procedure file it presents carries this record's digest. No environment value
/// is added (the stages' one-input pin). Class T Regtest development evidence only; never a product path.
const SET_RELEASE_RECORD: &[u8] = b"TEST_ONLY Class T D3a-2b-2a: RELEASE_REORG67_TEST_ONLY, TDS 6.7 procedure record, step 6 not performed (1D3 Q17)\n";
/// 045b :537: a ladder ends after rung 7.
const MAX_SET_RUNGS: usize = 8;

/// The launch candidate id of conflict-set rung `k` (rung 0 is the L0 id).
fn set_launch_id(k: usize) -> [u8; 32] {
    assert!(k < MAX_SET_RUNGS, "E3D3_RUNG");
    if k == 0 {
        LAUNCH_CANDIDATE
    } else {
        [0x20 + u8::try_from(k).unwrap(); 32]
    }
}

/// The rung a launch candidate id names, if any.
fn set_rung_of(candidate: &[u8; 32]) -> Option<usize> {
    (0..MAX_SET_RUNGS).find(|j| set_launch_id(*j) == *candidate)
}

/// `BITAGI_E3D3_RUNG`: a rung index, decimal with no sign or leading zero, below `n`.
fn parse_rung(text: &str, n: usize) -> usize {
    assert!(
        !text.is_empty()
            && text.bytes().all(|b| b.is_ascii_digit())
            && (text == "0" || !text.starts_with('0')),
        "E3D3_RUNG"
    );
    let k: usize = text.parse().expect("E3D3_RUNG");
    assert!(k < n && n <= MAX_SET_RUNGS, "E3D3_RUNG");
    k
}

/// The number of rungs the set charge wrote (`launch-0.txt` … in `handoff/`, with no gap).
fn set_rungs(handoff: &Path) -> usize {
    let names = listing(handoff);
    let n = (0..=MAX_SET_RUNGS)
        .take_while(|k| names.contains(&format!("launch-{k}.txt")))
        .count();
    assert!((1..=MAX_SET_RUNGS).contains(&n), "E3D3_RUNGS");
    n
}

/// A decision's verdict without its values: `Done:<outcome>`, `Refuse:<code>`, `Wait:<wait>`,
/// `Act:<step>`, or `Reads:<code>` (a refusal at the reads).
fn set_verdict(verdict: &ReadsVerdict) -> String {
    let name = |text: String| text.split([' ', '{', '(']).next().unwrap_or("").to_owned();
    match verdict {
        ReadsVerdict::Decided(Verdict::Done(outcome)) => {
            format!("Done:{}", set_outcome(Some(*outcome)))
        }
        ReadsVerdict::Decided(Verdict::Refuse(r)) => format!("Refuse:{:?}", r.code),
        ReadsVerdict::Decided(Verdict::Wait(w)) => format!("Wait:{}", name(format!("{w:?}"))),
        ReadsVerdict::Decided(Verdict::Act(s)) => format!("Act:{}", name(format!("{s:?}"))),
        ReadsVerdict::Refuse(r) => format!("Reads:{}", name(format!("{r:?}"))),
    }
}

/// A report's outcome: `Born@<h>` (`+opening` at H0), `IncludedNoEffect@<h>`,
/// `ProjectBornByOther@<birth height>`, `Stale@<target>><next birth>`, or `-`.
fn set_outcome(outcome: Option<Outcome>) -> String {
    match outcome {
        None => "-".to_owned(),
        Some(Outcome::Born { height, at_opening }) => {
            format!("Born@{height}{}", if at_opening { "+opening" } else { "" })
        }
        Some(Outcome::IncludedNoEffect { height }) => format!("IncludedNoEffect@{height}"),
        Some(Outcome::ProjectBornByOther { birth }) => {
            format!("ProjectBornByOther@{}", birth.height)
        }
        Some(Outcome::Stale {
            target_gate_height,
            next_birth_height,
        }) => format!("Stale@{target_gate_height}>{next_birth_height}"),
        // BEAT-1: no BEAT candidate runs here.
        Some(
            beat @ (Outcome::BeatAccepted { .. }
            | Outcome::BeatIncludedNoEffect { .. }
            | Outcome::BeatAnchorSpent { .. }
            | Outcome::HeartTimedOut { .. }
            | Outcome::HeartMaxAge { .. }
            | Outcome::HeartBroken { .. }),
        ) => format!("{beat:?}"),
    }
}

/// D3a-2b-2a: the reorg the turn's hook raised or acknowledged, `-` when none:
/// `raised:<true|false>;local:<h>:<hash>;at_local:<hash|below>;ancestor:<h>:<hash>` (`-` for no ancestor),
/// hashes in internal byte order (the procedure file's form).
fn set_reorg(seen: Option<&bitagi_launch_host::hooks::ReorgSeen>) -> String {
    let Some(seen) = seen else {
        return "-".to_owned();
    };
    let at_local = match seen.identity.at_local {
        AtLocal::Agreed(hash) => hex(&hash),
        AtLocal::Below => "below".to_owned(),
    };
    let ancestor = seen.ancestor.map_or_else(
        || "-".to_owned(),
        |a| format!("{}:{}", a.height, hex(&a.hash)),
    );
    format!(
        "raised:{};local:{}:{};at_local:{at_local};ancestor:{ancestor}",
        seen.raised,
        seen.identity.local.0,
        hex(&seen.identity.local.1)
    )
}

/// D3a-1b / D3a-2b-1: a report's flags, `opening_block_missed:<true|false>,reorged_before_inclusion:<true|false>`
/// (decision.rs `Report`; the item-4 tool parses exactly this form).
fn set_flags(report: &bitagi_launch::decision::Report) -> String {
    format!(
        "opening_block_missed:{},reorged_before_inclusion:{}",
        report.opening_block_missed, report.reorged_before_inclusion
    )
}

/// The wallet's CT-P3-045a section 2.2 counters, one line (the L0 tool parses exactly this form).
fn set_counters(counters: &bitagi_wallet::release_budget::BudgetCounters) -> String {
    format!(
        "released={};gate_attempts={};fee_exposure_sat={};principal_exposure_sat={}",
        counters.released_register_candidates(),
        counters.gate_attempts(),
        counters.fee_exposure_sat(),
        counters.principal_exposure_sat()
    )
}

/// Every export in `launch/export/` verified against both nodes' chain-only prevout of `base`'s input,
/// by the wallet candidate it is for (`launch/export/` holds only exports the driver wrote).
fn set_exports(launch: &Launch) -> Vec<(PathBuf, VerifiedOfflineExport)> {
    let (txid, vout) = one(&launch.base, "prevout_outpoint")
        .split_once(':')
        .expect("E3D3_PREVOUT");
    let (txid, vout) = (unhex32(txid), vout.parse::<u32>().unwrap());
    let coin = |n: &HttpRpcClient<'_>| {
        let coin = n
            .txout(txid, vout, PrevoutView::ChainOnly)
            .unwrap()
            .expect("E3D3_PREVOUT_UNSPENT");
        vec![bitcoin::TxOut {
            value: bitcoin::Amount::from_sat(coin.value_sat_u64),
            script_pubkey: bitcoin::ScriptBuf::from_bytes(coin.script_pubkey_bytes),
        }]
    };
    let (a, b) = launch.session.nodes();
    let (coin_a, coin_b) = (coin(&a), coin(&b));
    let dir = launch.dir.join("export");
    listing(&dir)
        .into_iter()
        .map(|name| {
            let path = dir.join(&name);
            let bytes = std::fs::read(&path).unwrap();
            let decoded = decode_offline_export(&mut bytes.as_slice(), bytes.len() as u64).unwrap();
            let verified =
                verify_offline_export(&decoded, &launch.config.profile, &coin_a, &coin_b)
                    .expect("E3D3_VERIFY");
            (path, verified)
        })
        .collect()
}

/// CT-P5-001 D3a-1b (Class T Regtest development evidence only; from the D3a-0 spike): one phase for
/// rung `BITAGI_E3D3_RUNG` of the L0 seat's conflict set, all of whose rungs the signer's
/// `launch_set_charge_stage_worker` charged, on the operator's candidate file of every rung. A rung above
/// this one that is not signed yet carries no approval reservation: the core refuses it `OfflineCharged`
/// and raises nothing. A signed rung above this one is not imported yet and carries no bytes: it waits
/// for its signature (`OfflineSignaturePending`) and acts on nothing. Each rung's export, once the
/// driver wrote it to `launch/export/`, is found by its wallet candidate.
///
/// - `set_sign`: turns to the Sign hand-off (`OfflineSignaturePending`), or to the H0 − 1 prestate
///   comparison (`PrestateComparisonPending`) on a run without it. Rung 0 at H0 − 2 makes the host with U
///   (`Launch::init`, as L0's `l0_sign`).
/// - `set_wait`: rung 0's export imported below H0 − 1, then turns to `SignedAwaitingOpeningGate`.
///   Every rung is signed below H0 − 1 (`set_sign`): the set charge wrote every rung's base for the tip
///   it was made at, and the host signs only at a base's own tip.
/// - `set_ready`: at H0 − 1, this rung's export imported, then turns to the broadcast authority
///   (`BroadcastAuthorityRequired`), no transport (the H0 − 1 comparison first, as above); the
///   operator's broadcast authorization is written then and not presented.
/// - `set_send`: this rung's imported export to step 8, with the product transport (the H0 − 1
///   comparison first when it has not run; the authorization `set_ready` wrote presented from the
///   first turn); it ends on the turn whose act submitted this rung.
/// - `set_broadcast`: this rung's export imported, then to step 8 and `AwaitingInclusion`, with the
///   product transport.
/// - `set_observe`: one turn, no transport, on the candidate file the last phase wrote (after G every
///   input is spent in the chain, so no export verifies again).
///
/// Every turn's decision for every rung and its act are reported, with the host's own `Admitted` and
/// `Submitted` records, the last turn's verdict and report outcome per rung (`labels`) and the wallet's
/// counters. Only a host error or the turn limit fails here; the driver judges the rest.
#[test]
#[ignore = "CT-P5-001 D3a-1b Tier 3: run by tools/claude_track_ardr_l0.py"]
fn launch_set_worker() {
    let name = env("PHASE");
    assert!(SET_PHASES.contains(&name.as_str()), "E3D3_PHASE");
    let mut launch = Launch::new();
    let handoff = launch.dir.join("handoff");
    let n = set_rungs(&handoff);
    let k = parse_rung(&env("RUNG"), n);
    launch.public = std::fs::read_to_string(handoff.join(format!("launch-{k}.txt"))).unwrap();
    launch.base = std::fs::read_to_string(handoff.join(format!("base-{k}.txt"))).unwrap();
    launch.base_file = handoff.join(format!("base-{k}.txt"));
    launch.launch_id = set_launch_id(k);
    let comparison = prestate_comparison(&launch);
    if name == "set_sign"
        && k == 0
        && comparison.is_none()
        && !launch.host_dir().join("state").exists()
    {
        launch.init();
    }
    let publics: Vec<String> = (0..n)
        .map(|j| std::fs::read_to_string(handoff.join(format!("launch-{j}.txt"))).unwrap())
        .collect();
    // D3a-2b-2a: `set_reorged` and `set_release` are one turn each on the candidate file as it is, as
    // `set_observe` (after G every input is spent in the chain).
    let observe = matches!(name.as_str(), "set_observe" | "set_reorged" | "set_release");
    // (가): the release phase needs the TEST_ONLY release record, then presents the TEST_ONLY Class T procedure file
    // made from `set_reorged`'s copy of the reorg (step 6 not performed).
    if name == "set_release" {
        let record = std::fs::read(launch.host_dir().join("release-record.txt"))
            .expect("E3D3_RELEASE_TEST_ONLY");
        assert_eq!(record, SET_RELEASE_RECORD, "E3D3_RELEASE_TEST_ONLY");
        launch.write_procedure_with(&record);
    }
    let mut exports: Vec<Option<(PathBuf, VerifiedOfflineExport)>> = (0..n).map(|_| None).collect();
    if !observe {
        for (path, verified) in set_exports(&launch) {
            let j = publics
                .iter()
                .position(|p| one(p, "wallet_candidate") == hex(verified.wallet_candidate()))
                .expect("E3D3_EXPORT_ROW");
            assert!(exports[j].is_none(), "E3D3_EXPORT_TWICE");
            exports[j] = Some((path, verified));
        }
    }
    // The export is imported once: on the phase's first run (a run with the comparison carries on).
    let imports =
        matches!(name.as_str(), "set_wait" | "set_ready" | "set_broadcast") && comparison.is_none();
    let sends = matches!(name.as_str(), "set_send" | "set_broadcast");
    if imports || sends || name == "set_ready" {
        let (_, verified) = exports[k].as_ref().expect("E3D3_EXPORT");
        assert_eq!(
            hex(verified.wallet_candidate()),
            one(&launch.public, "wallet_candidate"),
            "E3D3_ROW"
        );
        if imports {
            import(&launch, verified);
        }
    }
    let mut lines = Vec::new();
    for (j, p) in publics.iter().enumerate() {
        // A rung's approval reservation is given once it is this one or below it, or signed (the host
        // holds its Sign hand-off); its bytes once it is this one or below it (imported: the ledger row
        // holds their hash, `candidates::bind`). A signed rung above this one, not imported, waits
        // for its signature (`OfflineSignaturePending`) and acts on nothing.
        let given = j <= k || exports[j].is_some();
        let (signed_hex, retained) = match exports[j].as_ref().filter(|_| j <= k) {
            None => ("-".to_owned(), "-".to_owned()),
            Some((_, e)) => (
                hex(e.raw_bytes()),
                [
                    hex(&[0x0d + u8::try_from(j).unwrap() * 0x10; 32]),
                    hex(e.raw_tx_sha256()),
                    hex(e.txid_internal()),
                    hex(e.wtxid_internal()),
                    hex(e.approval_id()),
                    hex(e.signing_authority_id()),
                ]
                .join(" "),
            ),
        };
        lines.push(
            [
                one(p, "wallet_candidate").to_owned(),
                hex(&set_launch_id(j)),
                "opening".to_owned(),
                one(p, "approval_id").to_owned(),
                one(p, "approval_subject").to_owned(),
                one(p, "approval_session").to_owned(),
                one(p, "approval_actor").to_owned(),
                if given {
                    one(p, "reservation").to_owned()
                } else {
                    "-".to_owned()
                },
                hex(launch.budget.sha256()),
                H0.to_string(),
                one(p, "constructed").to_owned(),
                "-".to_owned(),
                one(p, "unsigned").to_owned(),
                signed_hex,
                retained,
            ]
            .join(" "),
        );
    }
    let candidates = launch.host_dir().join("candidates.txt");
    if !observe {
        write_private(
            &candidates,
            format!("BITAGI-LAUNCH-HOST-CANDIDATES-V4\n{}\n", lines.join("\n")).as_bytes(),
        );
    }
    let mut transport = sends.then(ProductTransport::new);
    let export_path = exports[k].as_ref().map(|(p, _)| p.clone());
    // `set_send` presents the broadcast authorization `set_ready` wrote for this rung, as an
    // operator's file stays in place; any other phase starts with none.
    let written = launch.host_dir().join("authority-broadcast.txt");
    let mut authority: Option<PathBuf> = (name == "set_send"
        && std::fs::read_to_string(&written).is_ok_and(|text| {
            text.lines()
                .any(|l| l == format!("launch_candidate={}", hex(&set_launch_id(k))))
        }))
    .then_some(written);
    let mut turns = Vec::new();
    let mut receipt = "-".to_owned();
    let mut done = false;
    let mut labels = String::new();
    let mut flags = String::new();
    let mut reorg = "-".to_owned();
    let mut released = "-".to_owned();
    let mut admitted: Vec<String> = Vec::new();
    let mut submitted: Vec<String> = Vec::new();
    let started_all = std::time::Instant::now();
    for _ in 0..32 {
        let started = std::time::Instant::now();
        let turn = launch
            .turn(
                &candidates,
                authority.as_deref(),
                export_path.as_deref(),
                transport.as_mut(),
                comparison.as_ref(),
            )
            .unwrap_or_else(|e| panic!("E3D3_TURN {name} {e:?} after {turns:?}"));
        let took = started.elapsed().as_millis();
        let rung =
            |c: &[u8; 32]| set_rung_of(c).map_or_else(|| "r?".to_owned(), |j| format!("r{j}"));
        let mut row: Vec<String> = turn
            .decisions
            .iter()
            .map(|d| format!("{}:{}", rung(&d.candidate), set_verdict(&d.verdict)))
            .collect();
        labels = turn
            .decisions
            .iter()
            .map(|d| {
                format!(
                    "{}={}/{}",
                    rung(&d.candidate),
                    set_verdict(&d.verdict),
                    set_outcome(d.report.outcome)
                )
            })
            .collect::<Vec<_>>()
            .join(";");
        // D3a-2b-1: the report's two flags per rung, as the core set them (the driver logs them, never
        // computes them).
        flags = turn
            .decisions
            .iter()
            .map(|d| format!("{}={}", rung(&d.candidate), set_flags(&d.report)))
            .collect::<Vec<_>>()
            .join(";");
        // D3a-2b-2a: the reorg the hook saw and the lock the procedure file released, as the host
        // reported them.
        reorg = set_reorg(turn.reorg_seen.as_ref());
        released = turn.released.as_ref().map_or_else(
            || "-".to_owned(),
            |r| format!("reason:{:?};step6:{:?}", r.reason, r.step6),
        );
        if name == "set_reorged" {
            let seen = turn.reorg_seen.as_ref().expect("E3D3_REORG_SEEN");
            assert!(seen.raised, "E3D3_REORG_NOT_RAISED {seen:?}");
            assert!(seen.ancestor.is_some(), "E3D3_REORG_ANCESTOR {seen:?}");
            assert_eq!(
                open_locks(&launch),
                [LockReason::Reorg67],
                "E3D3_REORG_NOT_IN_LEDGER"
            );
            launch.save_reorg_copy(seen);
        }
        if name == "set_release" {
            let r = turn.released.as_ref().expect("E3D3_NOT_RELEASED");
            assert_eq!(r.reason, LockReason::Reorg67, "E3D3_RELEASED {turn:?}");
            assert_eq!(
                r.step6,
                Some(bitagi_launch_host::procedure::Step6Status::NotPerformed),
                "E3D3_RELEASED {turn:?}"
            );
            assert!(open_locks(&launch).is_empty(), "E3D3_LOCK_STILL_OPEN");
        }
        if let Some(a) = &turn.act {
            let outcome = format!("{:?}", a.outcome);
            row.push(format!(
                "act:{}:{}",
                rung(&a.candidate),
                outcome.split([' ', '{', '(']).next().unwrap_or("")
            ));
            // The host's own admission (both nodes' `testmempoolaccept` of the exact rung) and
            // submission, as its journal records them.
            if let ActOutcome::Recorded { entry_id } | ActOutcome::Submitted { entry_id, .. } =
                a.outcome
            {
                let record = HostFile::open(&launch.config.state_dir.join(HOST_FILE))
                    .unwrap()
                    .journal(&a.candidate)
                    .unwrap()
                    .into_iter()
                    .find(|e| e.id == entry_id)
                    .map(|e| e.record);
                match record {
                    Some(Record::Admitted { node_a, node_b, .. }) => {
                        admitted.push(format!("{}:{node_a:?}/{node_b:?}", rung(&a.candidate)));
                    }
                    Some(Record::Submitted { node_a, node_b, .. }) => {
                        submitted.push(format!("{}:{node_a:?}/{node_b:?}", rung(&a.candidate)));
                    }
                    _ => {}
                }
            }
        }
        if !turn.persisted.is_empty() {
            row.push(format!("raised:{:?}", turn.persisted));
        }
        if let Some(t) = &turn.authorization {
            row.push(
                format!("authz:{:?}", t.outcome)
                    .split(' ')
                    .next()
                    .unwrap()
                    .to_owned(),
            );
        }
        row.push(format!("{took}ms"));
        turns.push(row.join("|"));
        let mine = turn
            .decisions
            .iter()
            .find(|d| d.candidate == set_launch_id(k))
            .expect("E3D3_RUNG_DECISION");
        match mine.verdict {
            _ if observe => done = true,
            // The H0 − 1 comparison of any rung ends the run: the driver compares the receipt.
            _ if matches!(
                turn.act.as_ref().map(|a| &a.outcome),
                Some(ActOutcome::PrestateComparisonPending { .. })
            ) =>
            {
                if let ActOutcome::PrestateComparisonPending { receipt_sha256, .. } = act(&turn) {
                    receipt = receipt_file_name(&receipt_sha256);
                }
                done = true;
            }
            ReadsVerdict::Decided(Verdict::Wait(Wait::SigningAuthorityRequired {
                checks_id,
                ..
            })) if turn.authorization.is_none() => {
                authority = Some(launch.signing_file(checks_id));
            }
            ReadsVerdict::Decided(Verdict::Wait(Wait::BroadcastAuthorityRequired {
                prebroadcast_id,
                ..
            })) if turn.authorization.is_none() && sends => {
                let (_, verified) = exports[k].as_ref().expect("E3D3_EXPORT");
                authority = Some(launch.broadcast_file(prebroadcast_id, verified));
            }
            ReadsVerdict::Decided(Verdict::Wait(Wait::OfflineSignaturePending { .. }))
                if name == "set_sign" =>
            {
                done = true;
            }
            ReadsVerdict::Decided(Verdict::Wait(Wait::SignedAwaitingOpeningGate { .. }))
                if name == "set_wait" =>
            {
                done = true;
            }
            // The operator writes the broadcast authorization now and presents it only with the
            // transport, at the rung's release time (`set_send`).
            ReadsVerdict::Decided(Verdict::Wait(Wait::BroadcastAuthorityRequired {
                prebroadcast_id,
                ..
            })) if name == "set_ready" => {
                let (_, verified) = exports[k].as_ref().expect("E3D3_EXPORT");
                launch.broadcast_file(prebroadcast_id, verified);
                done = true;
            }
            // Step 8 handed this rung off: the release is done.
            _ if sends
                && turn.act.as_ref().is_some_and(|a| {
                    a.candidate == set_launch_id(k)
                        && matches!(a.outcome, ActOutcome::Submitted { .. })
                }) =>
            {
                done = true;
            }
            ReadsVerdict::Decided(Verdict::Wait(Wait::AwaitingInclusion { .. })) if sends => {
                done = true;
            }
            ReadsVerdict::Decided(Verdict::Refuse(_) | Verdict::Done(_))
            | ReadsVerdict::Refuse(_) => {
                done = true;
            }
            _ => {}
        }
        if done {
            break;
        }
    }
    // The wallet's CT-P3-045a section 2.2 counters after this phase.
    let mut ledger = ReservationLedger::open_expected(
        &launch.config.ledger_path,
        launch.config.ledger_identity.clone(),
        Origin::TrustedLocalRestart,
    )
    .unwrap();
    let counters =
        bitagi_wallet::release_budget::budget_counters(&mut ledger).expect("E3D3_COUNTERS");
    drop(ledger);
    report("phase", &name);
    report("rung", &k.to_string());
    report("rungs", &n.to_string());
    report("done", if done { "yes" } else { "no" });
    report("prestate_receipt", &receipt);
    report("turns", &turns.len().to_string());
    report("turn_log", &turns.join(" ; "));
    report("labels", &labels);
    report("flags", &flags);
    report("reorg", &reorg);
    report("released", &released);
    report("admitted", &admitted.join(" ; "));
    report("submitted", &submitted.join(" ; "));
    report(
        "hand_offs",
        &transport.as_ref().map_or(0, |t| t.calls).to_string(),
    );
    report(
        "raw_tx_sha256",
        &transport
            .as_ref()
            .and_then(|t| t.raw_sha256)
            .map_or_else(|| "-".to_owned(), |h| hex(&h)),
    );
    report("budget_counters", &set_counters(&counters));
    report("ms", &started_all.elapsed().as_millis().to_string());
    report("set_stage", "PASS");
}

/// D3a-1b: the set worker's input parsing and line forms (no node).
#[test]
fn set_worker_inputs() {
    use std::panic::catch_unwind;
    assert_eq!(set_launch_id(0), LAUNCH_CANDIDATE);
    let ids: Vec<[u8; 32]> = (0..MAX_SET_RUNGS).map(set_launch_id).collect();
    for (j, id) in ids.iter().enumerate() {
        assert_eq!(set_rung_of(id), Some(j));
        assert_eq!(ids.iter().filter(|other| *other == id).count(), 1);
    }
    assert_eq!(set_rung_of(&[0x77; 32]), None);
    assert!(catch_unwind(|| set_launch_id(MAX_SET_RUNGS)).is_err());
    assert_eq!(parse_rung("0", 2), 0);
    assert_eq!(parse_rung("1", 2), 1);
    assert_eq!(parse_rung("7", 8), 7);
    for (bad, n) in [
        ("2", 2),
        ("", 2),
        ("01", 2),
        ("+1", 2),
        ("1 ", 2),
        ("-1", 2),
        ("0", 9),
    ] {
        assert!(catch_unwind(|| parse_rung(bad, n)).is_err(), "{bad:?} {n}");
    }
    assert_eq!(set_outcome(None), "-");
    assert_eq!(
        set_outcome(Some(Outcome::Born {
            height: 1000,
            at_opening: true
        })),
        "Born@1000+opening"
    );
    assert_eq!(
        set_outcome(Some(Outcome::IncludedNoEffect { height: 1000 })),
        "IncludedNoEffect@1000"
    );
    assert_eq!(
        set_outcome(Some(Outcome::Stale {
            target_gate_height: 1000,
            next_birth_height: 1004
        })),
        "Stale@1000>1004"
    );
    assert_eq!(
        set_flags(&bitagi_launch::decision::Report {
            opening_block_missed: true,
            ..Default::default()
        }),
        "opening_block_missed:true,reorged_before_inclusion:false"
    );
    assert_eq!(
        set_flags(&bitagi_launch::decision::Report {
            reorged_before_inclusion: true,
            ..Default::default()
        }),
        "opening_block_missed:false,reorged_before_inclusion:true"
    );
    assert_eq!(
        SET_PHASES,
        [
            "set_sign",
            "set_wait",
            "set_ready",
            "set_send",
            "set_broadcast",
            "set_observe",
            "set_reorged",
            "set_release"
        ]
    );
    assert!(
        SET_RELEASE_RECORD.starts_with(b"TEST_ONLY Class T D3a-2b-2a: RELEASE_REORG67_TEST_ONLY, ")
    );
    assert!(PROCEDURE_RECORD.starts_with(b"TEST_ONLY Class T "));
    assert_eq!(set_reorg(None), "-");
    let seen = bitagi_launch_host::hooks::ReorgSeen {
        identity: bitagi_launch::reorg::NonExtending {
            local: (1000, [0x11; 32]),
            at_local: AtLocal::Agreed([0x22; 32]),
        },
        incident: [0x33; 32],
        raised: true,
        ancestor: None,
    };
    assert_eq!(
        set_reorg(Some(&seen)),
        format!(
            "raised:true;local:1000:{};at_local:{};ancestor:-",
            hex(&[0x11; 32]),
            hex(&[0x22; 32])
        )
    );
}

/// D3a-1b: the host signs a set rung only at its base's own tip. The set charge writes every rung's base for
/// the tip it was made at (H0 − 2), and a base for one tip is refused at another (`complete`'s
/// `SignInputMismatch(TipHeight)` / `TipHash`, crates/bitagi-launch-host/src/sign_input.rs). So every rung is
/// signed below H0 − 1 (`set_sign` before G − 1); signing rung k after G − 1 would be refused.
#[test]
fn set_base_tip_is_the_sign_tip() {
    use bitagi_launch_host::candidates::ApprovalStatement;
    use bitagi_launch_host::sign_input::{
        AuthorityLines, ChargeFacts, HostFacts, SignLine, complete,
    };
    let fixture = include_str!("fixtures/sign_input_base_v4.txt");
    let approval = ApprovalStatement {
        subject_digest: [0x5a; 32],
        session: unhex32(one(fixture, "approval_session")),
        actor: unhex32(one(fixture, "approval_actor")),
    };
    let approval_id = approval.approval_id();
    let base: String = fixture
        .lines()
        .map(|l| match l.strip_prefix("approval_id=") {
            Some(_) => format!("approval_id={}\n", hex(&approval_id)),
            None => format!("{l}\n"),
        })
        .collect();
    let height: u64 = one(&base, "tip_height").parse().unwrap();
    let hash = unhex32(one(&base, "tip_hash"));
    let facts = |height: u64, hash: [u8; 32]| HostFacts {
        tip: AgreedTip {
            height,
            hash,
            node_pair: [0x31; 32],
        },
        budget_record_sha256: unhex32(one(&base, "budget_record_sha256")),
        fee_policy_sha256: unhex32(one(&base, "fee_policy_id")),
        charge: ChargeFacts {
            ledger_id: unhex32(one(&base, "offline_reservation_wallet_ledger_id")),
            candidate: unhex32(one(&base, "offline_reservation_wallet_candidate")),
            budget_record_sha256: unhex32(one(&base, "budget_record_sha256")),
            sequence: one(&base, "offline_reservation_charge_sequence")
                .parse()
                .unwrap(),
            reservation: unhex32(one(&base, "offline_reservation")),
        },
        approval,
        approval_id,
    };
    let authority = AuthorityLines {
        session: [0xa1; 32],
        actor: [0xa2; 32],
        id: [0xa3; 32],
    };
    assert!(complete(base.as_bytes(), &facts(height, hash), &authority).is_ok());
    assert!(matches!(
        complete(base.as_bytes(), &facts(height + 1, [0x99; 32]), &authority),
        Err(bitagi_launch_host::HostError::SignInputMismatch(
            SignLine::TipHeight
        ))
    ));
    assert!(matches!(
        complete(base.as_bytes(), &facts(height, [0x99; 32]), &authority),
        Err(bitagi_launch_host::HostError::SignInputMismatch(
            SignLine::TipHash
        ))
    ));
}
