//! `bitagi monitor tick` (CT-P5-004-2c-1, B3-04, Claude track): one
//! read-only observation of the two loopback nodes and, when the request
//! names them, of a context-bound replay store and one Heart, with the
//! monitor's alarm states (FBO §7.4, §7.10, §7.11; A #258
//! issuecomment-6894736990). It is one-shot: the loop, the log file, the
//! edges (alarm start and clear) and the acknowledgement are CT-P5-004-2c-2's.
//! The result is one JSON object on stdout.
//!
//! What the tick reads, and in what order:
//!
//! 1. Each node's `getblockchaininfo` (chain label, Signet challenge, tip
//!    height and hash, `mediantime`) and its block at height 0. A node on
//!    another chain label, challenge or genesis than the substrate is
//!    `CONTEXT_MISMATCH`; a node that does not answer is `UNAVAILABLE`.
//!    Both are AL-0 (a), never a refusal: the monitor keeps observing. Such
//!    a node is not read again, and nothing of it is compared (no lag, no
//!    S14 reading).
//! 2. When both nodes are `READ`, each node's block at the S14 heights
//!    (`monitor_alarms::s14_heights`: genesis, H0 − 1, H0, the lower tip
//!    and the request's `critical_heights`, those both nodes reached), then
//!    each node's tip again. A tip that moved is read again, up to
//!    [`MAX_ATTEMPTS`] in all; after that the tick reports
//!    `TIP_RACE_NOT_SETTLED` and compares nothing.
//! 3. The host's UTC wall clock, once, after the node reads; the tip age is
//!    555-a's rule over both MTPs (`monitor_alarms::tip_age`).
//! 4. With a store: the store opened read-only and its snapshot read, and
//!    the request's own checks (a store of another context, an H0 other than
//!    the store's) made first, so they never depend on the nodes. Then,
//!    unless a node is on another context, the store judged as
//!    `replay status` judges it (`store_commands::established_or_unavailable`);
//!    anything but SYNCED is AL-0 (a) `STORE_NOT_SYNCED`. That judge reads
//!    both nodes again, after the clock read, so its agreed tip (and the
//!    Heart position on it) can be a later tip than step 1's: the result
//!    gives the judge's tip and attempts (`store.judge_tip`) and whether it
//!    is the tip both nodes gave in step 1 (`store.same_tip_as_node_reads`).
//!    Without a store: "store 없음" (`NONE`), not a failure, and no store is
//!    opened.
//! 5. With a `heart_ref`: the Heart's record in the CURRENT index of the
//!    SYNCED state and its countdown, as `heart countdown` computes it. A
//!    Heart named but not CURRENT (or not readable) is AL-0 (a)
//!    `HEART_NAMED_NOT_CURRENT`. With no `heart_ref` the store is never
//!    asked for a Heart, and AL-1 to AL-7, the countdown, READY and the W/L
//!    window are each `HEART_NOT_CURRENT` with `heart.failure` false.
//!
//! AL-8, AL-9 and AL-10 are `NOT_MEASURED` (`NO_CANDIDATE`,
//! `NO_CORE_REPORT`); AL-7 with a CURRENT Heart is `NOT_MEASURED`
//! (`NO_LEDGER_COUNTS`): this build reads no candidate, no core report and
//! no ledger. Their decision functions are `monitor_alarms`'. Every alarm
//! carries the two `B_detect` fields of FBO :282 (fault start to emission,
//! emission to acknowledgement), null here: the loop fills them on the host
//! UTC clock; `mono_ns` (the caller's monotonic reading, echoed) only
//! orders lines. No alarm holds anything; the tick writes nothing.
//!
//! Request (`BITAGI_CT_MONITOR_TICK_REQUEST_V1`, strict JSON, no unknown
//! member): `context_mode`, `substrate`, `deployment_id_internal`,
//! `loopback_ports` as the store commands take them; `store_path`, an
//! absolute path or null; `heart_ref`, as `heart get` takes it, or null
//! (a `heart_ref` needs a store); `first_effective_height` (H0, at least
//! 1); `critical_heights`, at most [`MAX_CRITICAL_HEIGHTS`] ascending
//! heights; `mono_ns`, an unsigned integer.
//!
//! Exit codes (A Q2c-13): 0 whenever there is an observation, whatever the
//! alarms; 2 an invalid request, a store bound to another context or one
//! the store open refuses as a request error (unreadable, too large, not a
//! regular file); 3 the request file missing; 4 an I/O failure (reading
//! the request file or the store path's entry, writing stdout); 5
//! credential material; 6 a Bitcoin mainnet substrate, before any node is
//! contacted. A store the open finds missing, in use or awaiting WAL
//! recovery, diverged, failing validation, written during the read, or
//! judged while a node names another genesis, is an observation (AL-0
//! (a)). Node settings are not verified (`CONTEXT_MODE`). Class T, release
//! authorization NONE.

use std::time::{Duration, SystemTime, UNIX_EPOCH};

use bitagi_bitcoin::BitcoinRpcRead;
use bitagi_bitcoin::preflight_rpc::{LocalChain, PreflightRpcError, PreflightRpcRead};
use bitagi_bitcoin::rpc_http::RpcSession;
use bitagi_core::HeartRef;
use bitagi_types::{SubstrateContext, SubstrateNetwork};
use serde_json::{Map, Value, json};

use crate::command_io::{CommandError, NON_CLAIMS, lower_hex};
use crate::heart_countdown::heart_countdown;
use crate::heart_countdown_command::{countdown_json, heart_ref_json};
use crate::monitor_alarms::{
    AGING_SECS, CLOCK_AHEAD_SECS, HeartPosition, HeightRole, STALE_SECS, TipAge, TipState,
    al1_beat_due, al2_ready_lost, al3_escalation, al4_late, al5_brink, al6_no_timely_block, ready,
    s14, s14_heights, tip_age, window, window_label,
};
use crate::request::{array, decode_request, member, object, only_members, refuse};
use crate::store_commands::{
    Standing, StoreRequest, absolute_path, confirm_unchanged, context_json, context_members,
    established_or_unavailable, heart_ref, loopback_ports, open_store, snapshot_json,
};

pub const COMMAND_NAME: &str = "monitor tick";
pub const REQUEST_SCHEMA: &str = "BITAGI_CT_MONITOR_TICK_REQUEST_V1";
pub const RESULT_SCHEMA: &str = "BITAGI_CT_MONITOR_TICK_RESULT_V1";
/// The largest request [`run`] parses: the CLI's input-file bound.
pub const MAX_REQUEST_BYTES: usize = bitagi_wallet::MAX_COMMAND_ARTIFACT_BYTES;
/// The most critical heights one request names.
pub const MAX_CRITICAL_HEIGHTS: usize = 16;
/// Node read attempts while a tip moves, the first included.
pub const MAX_ATTEMPTS: u32 = 3;
const RETRY_PAUSE: Duration = Duration::from_millis(200);
const MEMBERS: [&str; 10] = [
    "schema",
    "context_mode",
    "substrate",
    "deployment_id_internal",
    "store_path",
    "loopback_ports",
    "heart_ref",
    "first_effective_height",
    "critical_heights",
    "mono_ns",
];

/// One tick against the nodes, store and Heart the request names, at the
/// host's UTC wall clock.
pub fn run(payload: &[u8]) -> Result<Value, CommandError> {
    tick(payload, host_clock)
}

/// The host's UTC wall clock in whole seconds since the UNIX epoch; none
/// when it is before the epoch. The only clock this command reads.
fn host_clock() -> Option<u64> {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .ok()
        .map(|since| since.as_secs())
}

/// The checked request.
struct Request {
    substrate: SubstrateContext,
    context: Value,
    ports: [u16; 2],
    store: Option<StoreRequest>,
    heart: Option<HeartRef>,
    h0: u64,
    critical: Vec<u64>,
    mono_ns: u64,
}

fn unsigned(value: &Value, path: &'static str) -> Result<u64, CommandError> {
    value
        .as_u64()
        .ok_or(refuse("NOT_AN_UNSIGNED_INTEGER", path))
}

fn parse(payload: &[u8]) -> Result<Request, CommandError> {
    if payload.len() > MAX_REQUEST_BYTES {
        return Err(refuse("INPUT_BYTES_LIMIT", "payload"));
    }
    let request = decode_request(payload, REQUEST_SCHEMA)?;
    let top = object(&request, "payload")?;
    only_members(top, &MEMBERS, "payload")?;
    // A mainnet substrate is exit 6 here, before any node is reached.
    let (substrate, binding) = context_members(top)?;
    let store_path = match member(top, "store_path", "store_path")? {
        Value::Null => None,
        Value::String(path) => Some(absolute_path(path)?),
        _ => return Err(refuse("NOT_A_STRING", "store_path")),
    };
    let ports = loopback_ports(top)?;
    let store = store_path.map(|path| StoreRequest::from_parts(substrate, binding, path, ports));
    let heart = match (member(top, "heart_ref", "heart_ref")?, &store) {
        (Value::Null, _) => None,
        (_, None) => return Err(refuse("HEART_REF_NEEDS_STORE", "heart_ref")),
        (_, Some(store)) => Some(heart_ref(top, store)?),
    };
    let h0 = unsigned(
        member(top, "first_effective_height", "first_effective_height")?,
        "first_effective_height",
    )?;
    if h0 == 0 {
        return Err(refuse("RANGE", "first_effective_height"));
    }
    let critical = critical_heights(top)?;
    let mono_ns = unsigned(member(top, "mono_ns", "mono_ns")?, "mono_ns")?;
    Ok(Request {
        substrate,
        context: context_json(substrate, binding),
        ports,
        store,
        heart,
        h0,
        critical,
        mono_ns,
    })
}

fn critical_heights(top: &Map<String, Value>) -> Result<Vec<u64>, CommandError> {
    const PATH: &str = "critical_heights";
    let heights = array(member(top, PATH, PATH)?, PATH)?;
    if heights.len() > MAX_CRITICAL_HEIGHTS {
        return Err(refuse("TOO_MANY", PATH));
    }
    let heights = heights
        .iter()
        .map(|height| unsigned(height, PATH))
        .collect::<Result<Vec<_>, _>>()?;
    if heights.windows(2).any(|pair| pair[0] >= pair[1]) {
        return Err(refuse("NOT_ASCENDING", PATH));
    }
    Ok(heights)
}

// ------------------------------------------------------------ node reads

/// How one node answered.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum NodeStatus {
    Read,
    Unavailable,
    ContextMismatch,
}

impl NodeStatus {
    const fn label(self) -> &'static str {
        match self {
            Self::Read => "READ",
            Self::Unavailable => "UNAVAILABLE",
            Self::ContextMismatch => "CONTEXT_MISMATCH",
        }
    }
}

/// One node's tip read.
#[derive(Debug, Clone, PartialEq, Eq)]
struct NodeTip {
    height: u64,
    hash: [u8; 32],
    mtp: Option<u64>,
    chain: LocalChain,
    challenge: Option<Vec<u8>>,
    genesis: [u8; 32],
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct NodeRead {
    status: NodeStatus,
    tip: Option<NodeTip>,
}

const UNAVAILABLE: NodeRead = NodeRead {
    status: NodeStatus::Unavailable,
    tip: None,
};

fn read_tip<N: PreflightRpcRead + ?Sized>(node: &N, substrate: SubstrateContext) -> NodeRead {
    let info = match node.blockchain_info() {
        Ok(info) => info,
        // A chain label this build does not know, or a Signet without its
        // challenge.
        Err(PreflightRpcError::ContextMismatch) => {
            return NodeRead {
                status: NodeStatus::ContextMismatch,
                tip: None,
            };
        }
        Err(_) => return UNAVAILABLE,
    };
    let Ok(genesis) = node.get_block_hash(0) else {
        return UNAVAILABLE;
    };
    let challenge = info
        .signet_challenge
        .map(|challenge| challenge.as_bytes().to_vec());
    let chain_matches = match substrate.network() {
        SubstrateNetwork::Regtest => info.chain == LocalChain::Regtest,
        SubstrateNetwork::PrivateSignet => {
            info.chain == LocalChain::Signet
                && challenge.as_deref() == substrate.signet_challenge_bytes()
        }
        SubstrateNetwork::Mainnet => false,
    };
    let status = if chain_matches && genesis == *substrate.genesis_hash().as_internal_bytes() {
        NodeStatus::Read
    } else {
        NodeStatus::ContextMismatch
    };
    NodeRead {
        status,
        tip: Some(NodeTip {
            height: info.height_u64,
            hash: info.best_block_hash_internal,
            mtp: info.median_time_u64,
            chain: info.chain,
            challenge,
            genesis,
        }),
    }
}

/// One node's block at `height`, from its tip read where it is the tip.
fn hash_at<N: BitcoinRpcRead + ?Sized>(node: &N, tip: &NodeTip, height: u64) -> Option<[u8; 32]> {
    match height {
        0 => Some(tip.genesis),
        _ if height == tip.height => Some(tip.hash),
        _ => node.get_block_hash(height).ok(),
    }
}

/// One compared height: its roles and Node A's and Node B's block there.
#[derive(Debug, Clone, PartialEq, Eq)]
struct Compared {
    height: u64,
    roles: Vec<HeightRole>,
    a: [u8; 32],
    b: [u8; 32],
}

/// What the node reads gave.
#[derive(Debug, Clone, PartialEq, Eq)]
struct Observed {
    nodes: [NodeRead; 2],
    compared: Vec<Compared>,
    race: bool,
    attempts: u32,
}

enum Attempt {
    Done(Observed),
    Moved([NodeRead; 2]),
}

fn observe_nodes<A: PreflightRpcRead + ?Sized, B: PreflightRpcRead + ?Sized>(
    node_a: &A,
    node_b: &B,
    substrate: SubstrateContext,
    h0: u64,
    critical: &[u64],
    pause: Duration,
) -> Observed {
    let mut last = [UNAVAILABLE, UNAVAILABLE];
    for attempt in 1..=MAX_ATTEMPTS {
        if attempt > 1 {
            std::thread::sleep(pause);
        }
        match observe_once(node_a, node_b, substrate, h0, critical) {
            Attempt::Done(observed) => {
                return Observed {
                    attempts: attempt,
                    ..observed
                };
            }
            Attempt::Moved(nodes) => last = nodes,
        }
    }
    Observed {
        nodes: last,
        compared: Vec::new(),
        race: true,
        attempts: MAX_ATTEMPTS,
    }
}

fn observe_once<A: PreflightRpcRead + ?Sized, B: PreflightRpcRead + ?Sized>(
    node_a: &A,
    node_b: &B,
    substrate: SubstrateContext,
    h0: u64,
    critical: &[u64],
) -> Attempt {
    let mut nodes = [read_tip(node_a, substrate), read_tip(node_b, substrate)];
    // A node that is not READ (unavailable, or on another context) is not
    // read again: nothing of it is compared.
    let (Some(tip_a), Some(tip_b), [NodeStatus::Read, NodeStatus::Read]) = (
        nodes[0].tip.clone(),
        nodes[1].tip.clone(),
        [nodes[0].status, nodes[1].status],
    ) else {
        return Attempt::Done(Observed {
            nodes,
            compared: Vec::new(),
            race: false,
            attempts: 0,
        });
    };
    let mut compared = Vec::new();
    let mut failed = [false, false];
    for (height, roles) in s14_heights(h0, tip_a.height.min(tip_b.height), critical) {
        let a = hash_at(node_a, &tip_a, height);
        let b = hash_at(node_b, &tip_b, height);
        failed[0] |= a.is_none();
        failed[1] |= b.is_none();
        if let (Some(a), Some(b)) = (a, b) {
            compared.push(Compared {
                height,
                roles,
                a,
                b,
            });
        }
    }
    // Each tip once more: no comparison outlives a tip change.
    let mut moved = false;
    for (index, (tip, read)) in [
        (&tip_a, node_a.get_best_block_hash()),
        (&tip_b, node_b.get_best_block_hash()),
    ]
    .into_iter()
    .enumerate()
    {
        match read {
            Ok(hash) if hash == tip.hash && !failed[index] => {}
            Ok(hash) if hash != tip.hash => moved = true,
            // The same tip, and a height read it should have answered
            // failed; or no answer to the tip read.
            _ => nodes[index] = UNAVAILABLE,
        }
    }
    if moved {
        return Attempt::Moved(nodes);
    }
    if nodes.iter().any(|node| node.tip.is_none()) {
        compared.clear();
    }
    Attempt::Done(Observed {
        nodes,
        compared,
        race: false,
        attempts: 0,
    })
}

// ------------------------------------------------------------ the store

/// How the store stands, when one is named.
#[derive(Debug, Clone, PartialEq, Eq)]
enum StoreState {
    None,
    Synced,
    Syncing(u64),
    /// No standing: why (an open, node or judgement outcome).
    Unavailable(&'static str),
}

impl StoreState {
    const fn label(&self) -> &'static str {
        match self {
            Self::None => "NONE",
            Self::Synced => "SYNCED",
            Self::Syncing(_) => "SYNCING",
            Self::Unavailable(_) => "UNAVAILABLE",
        }
    }
}

/// The store's reading and, for a Heart, its CURRENT position.
struct StoreReading {
    state: StoreState,
    snapshot: Option<Value>,
    /// The store judge's own agreed tip (height, hash) and attempts.
    judge_tip: Option<(u64, [u8; 32], u32)>,
    heart: HeartReading,
}

#[derive(Debug, Clone, PartialEq, Eq)]
enum HeartReading {
    NotConfigured,
    NotCurrent(&'static str),
    Current {
        position: HeartPosition,
        countdown: Value,
    },
}

/// An outcome of the store open or judgement that is an observation, not a
/// refusal: its reason. A refusal of the request itself stays one.
fn observed_store_failure(error: CommandError) -> Option<&'static str> {
    match error {
        CommandError::ChainUnavailable(reason) => Some(reason),
        CommandError::InputMissing(_) => Some("STORE_MISSING"),
        CommandError::ReplayStateError => Some("REPLAY_STATE_ERROR"),
        CommandError::Request { code, .. } if code == "NODE_CONTEXT_MISMATCH" => Some(code),
        _ => None,
    }
}

fn read_store(
    store_request: &StoreRequest,
    heart: Option<HeartRef>,
    h0: u64,
    nodes_usable: bool,
) -> Result<StoreReading, CommandError> {
    let unavailable = |reason, snapshot| StoreReading {
        state: StoreState::Unavailable(reason),
        snapshot,
        judge_tip: None,
        heart: match heart {
            Some(_) => HeartReading::NotCurrent("STORE_NOT_SYNCED"),
            None => HeartReading::NotConfigured,
        },
    };
    let store = match open_store(store_request) {
        Ok(store) => store,
        Err(error) => {
            return observed_store_failure(error)
                .map(|reason| unavailable(reason, None))
                .ok_or(error);
        }
    };
    // The request's own checks come before anything that depends on the
    // nodes, so a bad request is exit 2 on every tick.
    let Ok(snapshot) = store.snapshot_for_context(store_request.binding()) else {
        return Ok(unavailable("REPLAY_STATE_ERROR", None));
    };
    if snapshot.first_effective_height().value() != h0 {
        return Err(refuse(
            "FIRST_EFFECTIVE_HEIGHT_MISMATCH",
            "first_effective_height",
        ));
    }
    // A node on another context would make the store judge refuse.
    if !nodes_usable {
        return Ok(unavailable(
            "NODE_CONTEXT_MISMATCH",
            Some(snapshot_json(&snapshot)),
        ));
    }
    let judged = match established_or_unavailable(store_request, &store) {
        Ok(judged) => judged,
        Err(error) => {
            return observed_store_failure(error)
                .map(|reason| unavailable(reason, Some(snapshot_json(&snapshot))))
                .ok_or(error);
        }
    };
    let state = match judged.standing {
        Standing::Synced => StoreState::Synced,
        Standing::Behind(blocks) => StoreState::Syncing(blocks),
        // Not reached: `established_or_unavailable` returns a diverged store as an `Err`.
        Standing::Diverged => StoreState::Unavailable("STORE_DIVERGED"),
    };
    let heart = match heart {
        None => HeartReading::NotConfigured,
        Some(_) if state != StoreState::Synced => HeartReading::NotCurrent("STORE_NOT_SYNCED"),
        Some(heart) => current_heart(store_request, &judged, heart),
    };
    // No reading outlives a writer that appeared meanwhile.
    if confirm_unchanged(&store).is_err() {
        return Ok(unavailable("STORE_CHANGED_DURING_READ", None));
    }
    Ok(StoreReading {
        state,
        snapshot: Some(snapshot_json(&judged.snapshot)),
        judge_tip: Some((
            judged.view.tip.height_u64,
            judged.view.tip.block_hash_internal,
            judged.view.attempts,
        )),
        heart,
    })
}

/// The Heart's CURRENT record and countdown at the SYNCED state, as
/// `heart countdown` reads them.
fn current_heart(
    store_request: &StoreRequest,
    judged: &crate::store_commands::Judged,
    heart: HeartRef,
) -> HeartReading {
    let Some(state) = judged.state.as_ref() else {
        return HeartReading::NotCurrent("REPLAY_STATE_ERROR");
    };
    let as_of_height = state.identity().as_of_height();
    if as_of_height.value() != judged.view.tip.height_u64 {
        return HeartReading::NotCurrent("REPLAY_STATE_ERROR");
    }
    let deployment = store_request.deployment();
    let Some((_, record)) = state
        .state()
        .current_anchor_index()
        .iter()
        .find(|(_, record)| record.heart_ref(deployment) == heart)
    else {
        return HeartReading::NotCurrent("HEART_NOT_CURRENT");
    };
    let Ok(countdown) = heart_countdown(record, as_of_height) else {
        return HeartReading::NotCurrent("REPLAY_STATE_ERROR");
    };
    HeartReading::Current {
        position: HeartPosition {
            birth_height: countdown.birth_height().value(),
            anchor_height: countdown.current_anchor_height().value(),
            last_valid_beat_height: countdown.last_valid_beat_height().value(),
            last_timely_beat_height: countdown.last_timely_beat_height().value(),
            tip: as_of_height.value(),
        },
        countdown: countdown_json(countdown),
    }
}

// ------------------------------------------------------------ the tick

fn tick(payload: &[u8], clock: impl FnOnce() -> Option<u64>) -> Result<Value, CommandError> {
    let request = parse(payload)?;
    let session = RpcSession::preflight(request.ports)
        .map_err(|_| refuse("LOOPBACK_SESSION", "loopback_ports"))?;
    let (node_a, node_b) = session.nodes();
    let observed = observe_nodes(
        &node_a,
        &node_b,
        request.substrate,
        request.h0,
        &request.critical,
        RETRY_PAUSE,
    );
    drop(session);
    let now = clock();
    let mtp = observed.nodes.clone().map(|node| match node.status {
        NodeStatus::Read => node.tip.and_then(|tip| tip.mtp),
        _ => None,
    });
    let age = tip_age(mtp, now);
    let nodes_usable = !observed
        .nodes
        .iter()
        .any(|node| node.status == NodeStatus::ContextMismatch);
    let store = match &request.store {
        None => StoreReading {
            state: StoreState::None,
            snapshot: None,
            judge_tip: None,
            heart: HeartReading::NotConfigured,
        },
        Some(store_request) => read_store(store_request, request.heart, request.h0, nodes_usable)?,
    };
    Ok(document(&request, &observed, now, age, &store))
}

/// A hash in display order.
fn display(hash: &[u8; 32]) -> String {
    let mut bytes = *hash;
    bytes.reverse();
    lower_hex(&bytes)
}

/// RFC 3339 UTC, whole seconds, of `secs` since the UNIX epoch (the civil
/// calendar of days since 1970-01-01).
fn rfc3339(secs: u64) -> String {
    let days = secs / 86_400;
    let rest = secs % 86_400;
    // Shifted to a year that starts on 1 March, 0000-03-01 = day 0.
    let shifted = days + 719_468;
    let era = shifted / 146_097;
    let day_of_era = shifted % 146_097;
    let year_of_era =
        (day_of_era - day_of_era / 1_460 + day_of_era / 36_524 - day_of_era / 146_096) / 365;
    let day_of_year = day_of_era - (365 * year_of_era + year_of_era / 4 - year_of_era / 100);
    let month_index = (5 * day_of_year + 2) / 153;
    let day = day_of_year - (153 * month_index + 2) / 5 + 1;
    let month = if month_index < 10 {
        month_index + 3
    } else {
        month_index - 9
    };
    let year = year_of_era + era * 400 + u64::from(month <= 2);
    format!(
        "{year:04}-{month:02}-{day:02}T{:02}:{:02}:{:02}Z",
        rest / 3_600,
        rest % 3_600 / 60,
        rest % 60
    )
}

/// A value the Heart decides, or why there is none.
fn valued(heart: &HeartReading, value: impl FnOnce(&HeartPosition) -> Value) -> Value {
    match heart {
        HeartReading::Current { position, .. } => {
            json!({"status": "MEASURED", "value": value(position)})
        }
        _ => json!({"status": "HEART_NOT_CURRENT", "value": null}),
    }
}

/// The two `B_detect` fields of FBO :282, for the loop to fill on the
/// host UTC clock.
fn b_detect() -> Value {
    json!({
        "clock": "HOST_UTC_WALL_CLOCK",
        "fault_start_utc": null,
        "emission_utc": null,
        "acknowledgment_utc": null,
        "fault_to_emission_s": null,
        "emission_to_acknowledgment_s": null,
        "status": "UNMEASURED",
    })
}

fn alarm(id: &str, name: &str, raised: bool, sub_kinds: Vec<Value>) -> Value {
    json!({
        "id": id,
        "name": name,
        "status": "MEASURED",
        "raised": raised,
        "reason": null,
        "sub_kinds": sub_kinds,
        "b_detect": b_detect(),
    })
}

fn unmeasured(id: &str, name: &str, status: &str, reason: &str) -> Value {
    json!({
        "id": id,
        "name": name,
        "status": status,
        "raised": null,
        "reason": reason,
        "sub_kinds": [],
        "b_detect": b_detect(),
    })
}

/// AL-0 (a)'s sub-kinds: nodes, S14, store and a named Heart.
fn al0a_sub_kinds(observed: &Observed, store: &StoreReading) -> Vec<Value> {
    let mut kinds = Vec::new();
    for (name, node) in ["A", "B"].into_iter().zip(&observed.nodes) {
        match node.status {
            NodeStatus::Read => {}
            NodeStatus::Unavailable => {
                kinds.push(json!({"kind": "NODE_UNAVAILABLE", "node": name}));
            }
            NodeStatus::ContextMismatch => {
                kinds.push(json!({"kind": "NODE_CONTEXT_MISMATCH", "node": name}));
            }
        }
    }
    if observed.race {
        kinds.push(json!({"kind": "TIP_RACE_NOT_SETTLED", "attempts": observed.attempts}));
    } else if observed
        .nodes
        .iter()
        .all(|node| node.status == NodeStatus::Read)
        && let (Some(a), Some(b)) = (&observed.nodes[0].tip, &observed.nodes[1].tip)
    {
        let pairs: Vec<_> = observed
            .compared
            .iter()
            .map(|compared| (compared.height, compared.a, compared.b))
            .collect();
        let reading = s14([a.height, b.height], &pairs);
        if reading.lag > 0 {
            kinds.push(json!({
                "kind": "NODES_LAG",
                "lag": reading.lag,
                "behind": if a.height < b.height { "A" } else { "B" },
            }));
        }
        if !reading.mismatches.is_empty() {
            kinds.push(json!({"kind": "S14_HASH_MISMATCH", "heights": reading.mismatches}));
        }
    }
    match &store.state {
        StoreState::None | StoreState::Synced => {}
        state => kinds.push(json!({
            "kind": "STORE_NOT_SYNCED",
            "standing": state.label(),
            "reason": match state {
                StoreState::Unavailable(reason) => Some(*reason),
                _ => None,
            },
        })),
    }
    if let HeartReading::NotCurrent(reason) = store.heart {
        kinds.push(json!({"kind": "HEART_NAMED_NOT_CURRENT", "reason": reason}));
    }
    kinds
}

/// AL-0 (b) (B's default): judged on node agreement; a store that is not
/// synced is AL-0 (a) and does not hide a stale tip. Its one sub-kind is
/// the tip age state's name as it stands (`TIP_STALE`, `TIP_TIMES_UNREAD`
/// and so on), so a stale tip and an unread one differ (A, fix round 2).
fn al0b_alarm(nodes_agree: bool, age: TipAge) -> Value {
    if !nodes_agree {
        return unmeasured("AL-0b", "UNKNOWN_TIP", "NOT_MEASURED", "NODES_NOT_AGREED");
    }
    let raised = age.state.raises_al0b();
    alarm(
        "AL-0b",
        "UNKNOWN_TIP",
        raised,
        if raised {
            vec![json!({"kind": age.state.code()})]
        } else {
            Vec::new()
        },
    )
}

fn heart_alarms(heart: &HeartReading, agreed_tip_clear: bool) -> (Vec<Value>, Value) {
    const NAMES: [(&str, &str); 7] = [
        ("AL-1", "BEAT_DUE"),
        ("AL-2", "READY_LOST"),
        ("AL-3", "ESCALATION"),
        ("AL-4", "LATE"),
        ("AL-5", "BRINK"),
        ("AL-6", "NO_TIMELY_BLOCK"),
        ("AL-7", "CAP_HEADROOM"),
    ];
    let HeartReading::Current { position, .. } = heart else {
        let alarms = NAMES
            .iter()
            .map(|(id, name)| unmeasured(id, name, "HEART_NOT_CURRENT", "HEART_NOT_CURRENT"))
            .collect();
        return (
            alarms,
            json!({"status": "HEART_NOT_CURRENT", "value": null}),
        );
    };
    let Some(d) = position.d() else {
        let alarms = NAMES
            .iter()
            .map(|(id, name)| unmeasured(id, name, "NOT_MEASURED", "HEIGHT_RANGE"))
            .collect();
        return (alarms, json!({"status": "NOT_MEASURED", "value": null}));
    };
    let raised = [
        al1_beat_due(position),
        al2_ready_lost(d),
        al3_escalation(position),
        al4_late(d),
        al5_brink(d),
        al6_no_timely_block(d),
    ];
    let mut alarms: Vec<Value> = NAMES
        .iter()
        .zip(raised)
        .map(|((id, name), raised)| alarm(id, name, raised, Vec::new()))
        .collect();
    alarms.push(unmeasured(
        NAMES[6].0,
        NAMES[6].1,
        "NOT_MEASURED",
        "NO_LEDGER_COUNTS",
    ));
    let ready = json!({"status": "MEASURED", "value": ready(agreed_tip_clear, d)});
    (alarms, ready)
}

fn node_json(name: &str, node: &NodeRead) -> Value {
    let tip = node.tip.as_ref();
    json!({
        "node": name,
        "status": node.status.label(),
        "chain": tip.map(|tip| match tip.chain {
            LocalChain::Regtest => "regtest",
            LocalChain::Signet => "signet",
            LocalChain::Main => "main",
        }),
        "signet_challenge_hex": tip.and_then(|tip| tip.challenge.as_deref().map(lower_hex)),
        "genesis_hash_display": tip.map(|tip| display(&tip.genesis)),
        "tip_height": tip.map(|tip| tip.height),
        "tip_hash_display": tip.map(|tip| display(&tip.hash)),
        "median_time_past_s": tip.and_then(|tip| tip.mtp),
    })
}

fn document(
    request: &Request,
    observed: &Observed,
    now: Option<u64>,
    age: TipAge,
    store: &StoreReading,
) -> Value {
    let al0a = al0a_sub_kinds(observed, store);
    let nodes_agree = !al0a.iter().any(|kind| {
        matches!(
            kind["kind"].as_str(),
            Some(
                "NODE_UNAVAILABLE"
                    | "NODE_CONTEXT_MISMATCH"
                    | "TIP_RACE_NOT_SETTLED"
                    | "NODES_LAG"
                    | "S14_HASH_MISMATCH"
            )
        )
    });
    let al0b = al0b_alarm(nodes_agree, age);
    let al0b_raised = al0b["raised"] == json!(true);
    let mut alarms = vec![alarm(
        "AL-0a",
        "UNKNOWN_NODES_OR_STORE",
        !al0a.is_empty(),
        al0a.clone(),
    )];
    alarms.push(al0b);
    let (heart_alarms, ready) = heart_alarms(&store.heart, al0a.is_empty() && !al0b_raised);
    alarms.extend(heart_alarms);
    alarms.push(unmeasured(
        "AL-8",
        "FEE_CAP",
        "NOT_MEASURED",
        "NO_CANDIDATE",
    ));
    alarms.push(unmeasured(
        "AL-9",
        "COMPARISON_LAG",
        "NOT_MEASURED",
        "NO_CORE_REPORT",
    ));
    alarms.push(unmeasured(
        "AL-10",
        "COMPARISON_LAG_WIDE",
        "NOT_MEASURED",
        "NO_CORE_REPORT",
    ));
    let reached: Vec<Value> = observed
        .compared
        .iter()
        .filter(|compared| compared.roles.contains(&HeightRole::Critical))
        .map(|compared| {
            json!({
                "height": compared.height,
                "hash_a_display": display(&compared.a),
                "hash_b_display": display(&compared.b),
                "equal": compared.a == compared.b,
            })
        })
        .collect();
    let pending: Vec<u64> = request
        .critical
        .iter()
        .copied()
        .filter(|height| {
            !observed.compared.iter().any(|compared| {
                compared.height == *height && compared.roles.contains(&HeightRole::Critical)
            })
        })
        .collect();
    let heart = match (&request.heart, &store.heart) {
        (None, _) => json!({
            "configured": false,
            "heart_ref": null,
            "status": "HEART_NOT_CURRENT",
            "reason": "NO_HEART_NAMED",
            "failure": false,
        }),
        (Some(heart), HeartReading::Current { .. }) => json!({
            "configured": true,
            "heart_ref": heart_ref_json(*heart),
            "status": "CURRENT",
            "reason": null,
            "failure": false,
        }),
        (Some(heart), reading) => json!({
            "configured": true,
            "heart_ref": heart_ref_json(*heart),
            "status": "HEART_NOT_CURRENT",
            "reason": match reading {
                HeartReading::NotCurrent(reason) => Some(*reason),
                _ => None,
            },
            "failure": true,
        }),
    };
    let notices: Vec<&str> = if age.state == TipState::Aging {
        vec![TipState::Aging.code()]
    } else {
        Vec::new()
    };
    json!({
        "schema": RESULT_SCHEMA,
        "command": COMMAND_NAME,
        "release_class": "T",
        "release_authorization": "NONE",
        "result": "MONITOR_TICK",
        "context": request.context,
        "clock": {
            "source": "HOST_UTC_WALL_CLOCK",
            "utc": now.map(rfc3339),
            "utc_unix_s": now,
            "mono_ns": request.mono_ns,
            "mono_ns_use": "ORDERING_ONLY",
        },
        "first_effective_height": request.h0,
        "nodes": [node_json("A", &observed.nodes[0]), node_json("B", &observed.nodes[1])],
        "observation_attempts": observed.attempts,
        "compared_heights": observed.compared.iter().map(|compared| json!({
            "height": compared.height,
            "roles": compared.roles.iter().map(|role| role.label()).collect::<Vec<_>>(),
            "hash_a_display": display(&compared.a),
            "hash_b_display": display(&compared.b),
            "equal": compared.a == compared.b,
        })).collect::<Vec<_>>(),
        "critical_heights": {"reached": reached, "pending": pending},
        "tip_age": {
            "rule": "555-a",
            "state": age.state.code(),
            "age_s": age.age_s,
            "aging_secs": AGING_SECS,
            "stale_secs": STALE_SECS,
            "clock_ahead_secs": CLOCK_AHEAD_SECS,
        },
        "store": {
            "configured": request.store.is_some(),
            "standing": store.state.label(),
            "reason": match store.state {
                StoreState::None => Some("NO_STORE_NAMED"),
                StoreState::Unavailable(reason) => Some(reason),
                _ => None,
            },
            "behind_blocks": match store.state {
                StoreState::Synced => Some(0),
                StoreState::Syncing(blocks) => Some(blocks),
                _ => None,
            },
            "snapshot": store.snapshot,
            "judge_tip": store.judge_tip.map(|(height, hash, attempts)| json!({
                "tip_height": height,
                "tip_hash_display": display(&hash),
                "observation_attempts": attempts,
            })),
            "same_tip_as_node_reads": store.judge_tip.map(|(height, hash, _)| {
                observed.nodes.iter().all(|node| {
                    node.status == NodeStatus::Read
                        && node.tip.as_ref().is_some_and(|tip| (tip.height, tip.hash) == (height, hash))
                })
            }),
        },
        "heart": heart,
        "countdown": match &store.heart {
            HeartReading::Current { countdown, .. } => json!({"status": "MEASURED", "value": countdown}),
            _ => json!({"status": "HEART_NOT_CURRENT", "value": null}),
        },
        "window": valued(&store.heart, |position| {
            json!(window(position).map(window_label))
        }),
        "ready": ready,
        "alarms": alarms,
        "notices": notices,
        "non_claims": NON_CLAIMS,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rfc3339_of_known_instants() {
        assert_eq!(rfc3339(0), "1970-01-01T00:00:00Z");
        assert_eq!(rfc3339(94_694_399), "1972-12-31T23:59:59Z");
        assert_eq!(rfc3339(951_868_799), "2000-02-29T23:59:59Z");
        assert_eq!(rfc3339(1_794_748_080), "2026-11-15T13:08:00Z");
        assert_eq!(rfc3339(4_107_542_400), "2100-03-01T00:00:00Z");
    }

    /// AL-0 (b) stands for every tip age state but fresh and aging, and its
    /// one sub-kind is the state's name verbatim, so "stale" and "unread"
    /// differ (A, fix round 2, item 7). `TIP_CLOCK_UNREADABLE` (a host clock
    /// before the epoch) has no live cell: this is its cell. Without node
    /// agreement AL-0 (b) is not measured, whatever the age.
    #[test]
    fn al0b_carries_each_tip_state_name_verbatim() {
        let raised = [
            (TipState::Stale, "TIP_STALE"),
            (TipState::TimesDisagree, "TIP_TIMES_DISAGREE"),
            (TipState::TimesUnread, "TIP_TIMES_UNREAD"),
            (TipState::ClockBehind, "TIP_CLOCK_BEHIND"),
            (TipState::ClockUnreadable, "TIP_CLOCK_UNREADABLE"),
        ];
        for (state, name) in raised {
            let al0b = al0b_alarm(true, TipAge { state, age_s: None });
            assert_eq!(al0b["status"], "MEASURED", "{name}");
            assert_eq!(al0b["raised"], true, "{name}");
            assert_eq!(al0b["sub_kinds"], json!([{"kind": name}]), "{name}");
        }
        assert_eq!(
            tip_age([Some(1), Some(1)], None).state,
            TipState::ClockUnreadable
        );
        for state in [TipState::Fresh, TipState::Aging] {
            let al0b = al0b_alarm(
                true,
                TipAge {
                    state,
                    age_s: Some(0),
                },
            );
            assert_eq!(al0b["raised"], false);
            assert_eq!(al0b["sub_kinds"], json!([]));
        }
        let al0b = al0b_alarm(
            false,
            TipAge {
                state: TipState::Stale,
                age_s: None,
            },
        );
        assert_eq!(
            (&al0b["status"], &al0b["raised"], &al0b["reason"]),
            (
                &json!("NOT_MEASURED"),
                &Value::Null,
                &json!("NODES_NOT_AGREED")
            )
        );
    }

    /// Which store open and judgement outcomes are an observation (exit 0,
    /// AL-0 (a) with the reason) and which stay a refusal with their exit
    /// (A, fix round 2, P3-1). The live cells are in `tests/monitor_tick.rs`.
    #[test]
    fn observed_store_failure_splits_observations_from_refusals() {
        for (error, reason) in [
            (CommandError::InputMissing("store_path"), "STORE_MISSING"),
            (
                CommandError::ChainUnavailable("STORE_IN_USE"),
                "STORE_IN_USE",
            ),
            (
                CommandError::ChainUnavailable("STORE_WAL_RECOVERY_REQUIRED"),
                "STORE_WAL_RECOVERY_REQUIRED",
            ),
            (
                CommandError::ChainUnavailable("STORE_DIVERGED"),
                "STORE_DIVERGED",
            ),
            (CommandError::ReplayStateError, "REPLAY_STATE_ERROR"),
            (
                refuse("NODE_CONTEXT_MISMATCH", "loopback_ports"),
                "NODE_CONTEXT_MISMATCH",
            ),
        ] {
            assert_eq!(observed_store_failure(error), Some(reason), "{reason}");
        }
        for (error, exit) in [
            (refuse("STORE_CONTEXT_MISMATCH", "store_path"), 2),
            (refuse("STORE_UNREADABLE", "store_path"), 2),
            (refuse("STORE_TOO_LARGE", "store_path"), 2),
            (refuse("INPUT_NOT_A_REGULAR_FILE", "store_path"), 2),
            (refuse("LOOPBACK_SESSION", "loopback_ports"), 2),
            (CommandError::InputIo("store_path"), 4),
        ] {
            assert_eq!(observed_store_failure(error), None, "{error}");
            assert_eq!(error.exit_code(), exit, "{error}");
        }
    }

    /// The tick reads the OS clock once, in `host_clock`, after the node
    /// reads; no other clock seam exists. Read at run time.
    #[test]
    fn the_host_clock_is_read_once_after_the_node_reads() {
        let source =
            std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/src/monitor_tick.rs"))
                .unwrap();
        let code = source.split("#[cfg(test)]").next().unwrap();
        assert_eq!(code.matches("SystemTime::now()").count(), 1);
        assert_eq!(code.matches("tick(payload, host_clock)").count(), 1);
        let body = &code[code.find("fn tick(").unwrap()..];
        let observe = body.find("observe_nodes(").unwrap();
        let clock = body.find("clock()").unwrap();
        assert!(observe < clock, "the clock is read before the node reads");
    }
}
