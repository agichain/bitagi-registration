//! TEST ONLY. Private-Signet replay store fixture for the P5-002 two-node
//! Signet check (scope (b): two Signet nodes, the replay and the watcher).
//! It follows the Regtest fixture `test_only_regtest_store_fixture`, whose
//! bytes it leaves alone.
//!
//! Usage: `test_only_signet_store_fixture <new-dir> <h0>
//! <h0-minus-1-hash-display> <genesis-display> <challenge-hex> <port-a>
//! <port-b>`. Before any node call it builds the PRIVATE_SIGNET substrate
//! from the given genesis and challenge: a Bitcoin mainnet genesis, any
//! genesis other than the Signet genesis every Signet shares, and the public
//! default Signet challenge are refused. Then each loopback node must report
//! `getblockchaininfo.chain` `signet` with exactly the given
//! `signet_challenge`, and the given genesis at height 0, and both must name
//! the given block at H0 - 1. Only then does it create `<new-dir>` (which
//! must be new) holding `profile.bin`, the 79-byte Profile
//! `NetworkProfile::build(genesis, H0)`; `store.sqlite3`, an empty replay
//! store at H0 - 1 bound to that Profile's deployment id and to the
//! substrate's `substrate_context_hash`, which carries the challenge (the
//! Profile does not); the Class T request envelopes `status.bin`,
//! `heart_list.bin`, `heart_get.bin`, `sync.bin` and `rewind.bin`; and
//! `heart_countdown_empty.json`, the `heart countdown` request for an absent
//! Heart. Every request names the network `PRIVATE_SIGNET`. It prints one
//! JSON summary line.
//!
//! `--follow <dir> <h0> <genesis-display> <challenge-hex> <port-a>
//! <port-b>` makes the same input and node checks, then makes one
//! `ActiveChainFollower::synchronize_synthetic` call on `<dir>/store.sqlite3`.
//! It applies blocks only when both nodes name the same tip, by height and
//! hash; while their tips differ, even with one node a block behind, the call
//! is refused (`FOLLOW_REFUSED`) and nothing is written. After a successful
//! call `bitagi replay status` reports SYNCED. The P5-002 driver calls it once
//! per poll. Each node's context is read from its own
//! `getblockchaininfo` and `getblockhash 0` answers, which are observations
//! and not node settings, so its JSON line says `replay_kind`
//! `SYNTHETIC_CONTEXT_UNVERIFIED_SETTINGS` (설정 미검증 synthetic-context
//! replay): never a verified replay or release evidence.
//!
//! Exit 0 on success; exit 2 with one line on stderr for any refusal. A
//! build refused after its directory was created removes that directory.
//!
//! Test data only, never operator state, and never a published Profile. It
//! is an example, so no release build of the CLI (`cargo build --release -p
//! bitagi-cli`) and no feature includes it. Its CONTROL cells, on fake
//! loopback nodes, are `tests/signet_store_fixture.rs`; no CI job runs it on
//! real nodes.
#![forbid(unsafe_code)]

use std::io::Write;
use std::path::Path;
use std::process::ExitCode;
use std::time::Duration;

use bitagi_bitcoin::network_context::{SyntheticContextRead, validate_synthetic_descriptor};
use bitagi_bitcoin::preflight_rpc::{LocalChain, PreflightRpcRead};
use bitagi_bitcoin::rpc_http::{HttpRpcClient, RpcSession};
use bitagi_bitcoin::{
    ActiveChainFollower, BitcoinRpcRead, NodeContextError, RpcBlockHeader, RpcReadError, SyncKind,
};
use bitagi_core::{
    CurrentAnchorIndex, DecodedCanonicalState, MinimalForwardState, StateValidationContext,
    decode_validated_canonical_state, encode_validated_canonical_state,
};
use bitagi_store::{SqliteStore, StoreContextBinding};
use bitagi_types::{
    BitcoinInternalHash32, Bytes32, CoreHeight, MAINNET_GENESIS_HASH_INTERNAL, SubstrateContext,
    SubstrateContextError,
};
use bitagi_wallet::{CommandArtifact, CommandKind};

/// The network every request and summary names.
pub const NETWORK: &str = "PRIVATE_SIGNET";
/// The `--follow` line's replay kind: a synthetic-context replay whose node
/// settings are not verified.
pub const REPLAY_KIND: &str = "SYNTHETIC_CONTEXT_UNVERIFIED_SETTINGS";
/// The same, as the record words it (A #258 6894736990, Q-fx-1).
pub const REPLAY_LABEL: &str = "설정 미검증 synthetic-context replay";
/// The fixture's name in its summary lines.
pub const FIXTURE: &str = "TEST_ONLY_PRIVATE_SIGNET_STORE_FIXTURE";
/// The `--follow` read budget: within the replay session's own bounds, and
/// enough for one call's descent cap of blocks.
const FOLLOW_MAX_CALLS: u32 = 20_000;
const FOLLOW_DEADLINE: Duration = Duration::from_secs(300);

fn internal_from_display(text: &str) -> Option<[u8; 32]> {
    let mut bytes = bitagi_cli::decode_lower_hex(text).ok()?;
    bytes.reverse();
    bytes.try_into().ok()
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}

fn display(hash: [u8; 32]) -> String {
    let mut bytes = hash;
    bytes.reverse();
    hex(&bytes)
}

fn ports(port_a: &str, port_b: &str) -> Result<[u16; 2], String> {
    let ports = [
        port_a.parse().map_err(|_| "port a")?,
        port_b.parse().map_err(|_| "port b")?,
    ];
    if ports[0] == ports[1] {
        return Err("the two ports must name two nodes".into());
    }
    Ok(ports)
}

fn h0(text: &str) -> Result<u64, String> {
    let h0: u64 = text.parse().map_err(|_| "h0")?;
    if h0 < 2 {
        return Err("h0 must be at least 2".into());
    }
    Ok(h0)
}

/// The PRIVATE_SIGNET substrate of the given genesis and challenge, built
/// before any node call.
fn substrate(genesis_display: &str, challenge_hex: &str) -> Result<SubstrateContext, String> {
    let genesis = internal_from_display(genesis_display).ok_or("genesis")?;
    if genesis == MAINNET_GENESIS_HASH_INTERNAL {
        return Err("MAINNET_GENESIS_REFUSED: a Bitcoin mainnet genesis has no fixture".into());
    }
    let challenge = bitagi_cli::decode_lower_hex(challenge_hex).map_err(|_| "challenge hex")?;
    let substrate = SubstrateContext::private_signet(
        BitcoinInternalHash32::from_internal_bytes(genesis),
        &challenge,
    )
    .map_err(|error| match error {
        SubstrateContextError::DefaultSignetUnsupported => {
            "DEFAULT_SIGNET_CHALLENGE_REFUSED: the public default Signet is not a private Signet"
                .to_owned()
        }
        other => format!("SUBSTRATE_REFUSED: {other}"),
    })?;
    validate_synthetic_descriptor(substrate)
        .map_err(|_| "GENESIS_NOT_SIGNET: the genesis is not the Signet genesis")?;
    Ok(substrate)
}

/// The Profile at `h0` on the substrate's genesis, its deployment id, and
/// the store binding for that deployment on this substrate.
fn signet_context(
    substrate: SubstrateContext,
    h0: u64,
) -> Result<(bitagi_profile::NetworkProfile, Bytes32, StoreContextBinding), String> {
    let profile =
        bitagi_profile::NetworkProfile::build(substrate.genesis_hash(), CoreHeight::new(h0))
            .map_err(|error| format!("{error:?}"))?;
    let deployment = bitagi_profile::deployment_id(&profile);
    let binding = StoreContextBinding::new(
        deployment,
        bitagi_bitcoin::substrate_context_hash(&substrate),
        substrate.genesis_hash(),
    )
    .map_err(|error| format!("{error:?}"))?;
    Ok((profile, deployment, binding))
}

/// One node's substrate as it reports it: `getblockchaininfo` names a
/// Signet and its challenge, and `getblockhash 0` its genesis. An
/// observation, never the node's settings.
fn node_context<N: PreflightRpcRead + ?Sized>(node: &N) -> Result<SubstrateContext, String> {
    let info = node
        .blockchain_info()
        .map_err(|error| format!("NODE_UNAVAILABLE: {error:?}"))?;
    let (LocalChain::Signet, Some(challenge)) = (info.chain, info.signet_challenge) else {
        return Err(format!("NODE_CHAIN_NOT_SIGNET: {:?}", info.chain));
    };
    let genesis = node
        .get_block_hash(0)
        .map_err(|error| format!("NODE_UNAVAILABLE: {error:?}"))?;
    SubstrateContext::private_signet(
        BitcoinInternalHash32::from_internal_bytes(genesis),
        challenge.as_bytes(),
    )
    .map_err(|error| format!("NODE_SUBSTRATE_REFUSED: {error}"))
}

/// Both nodes report the selected substrate.
fn check_nodes<N: PreflightRpcRead + ?Sized>(
    nodes: [&N; 2],
    selected: SubstrateContext,
) -> Result<(), String> {
    for (name, node) in ["A", "B"].into_iter().zip(nodes) {
        let observed = node_context(node).map_err(|error| format!("node {name}: {error}"))?;
        if observed.signet_challenge_bytes() != selected.signet_challenge_bytes() {
            return Err(format!(
                "node {name}: SIGNET_CHALLENGE_MISMATCH: the node reports another challenge"
            ));
        }
        if observed.genesis_hash() != selected.genesis_hash() {
            return Err(format!(
                "node {name}: NODE_GENESIS_MISMATCH: the node reports another genesis"
            ));
        }
    }
    Ok(())
}

/// A loopback node whose synthetic context is read from its own answers at
/// each call, so a node that changes Signet during a follow is refused.
struct ObservedSignetNode<'a>(HttpRpcClient<'a>);

impl BitcoinRpcRead for ObservedSignetNode<'_> {
    fn get_block_count(&self) -> Result<u64, RpcReadError> {
        self.0.get_block_count()
    }
    fn get_best_block_hash(&self) -> Result<[u8; 32], RpcReadError> {
        self.0.get_best_block_hash()
    }
    fn get_block_hash(&self, height_u64: u64) -> Result<[u8; 32], RpcReadError> {
        self.0.get_block_hash(height_u64)
    }
    fn get_block_header(&self, hash_internal: [u8; 32]) -> Result<RpcBlockHeader, RpcReadError> {
        self.0.get_block_header(hash_internal)
    }
    fn get_block_hex(&self, hash_internal: [u8; 32]) -> Result<String, RpcReadError> {
        self.0.get_block_hex(hash_internal)
    }
}

impl SyntheticContextRead for ObservedSignetNode<'_> {
    fn synthetic_context(&self) -> Result<SubstrateContext, NodeContextError> {
        node_context(&self.0).map_err(|_| NodeContextError::ReadUnavailable)
    }
}

/// The empty state at H0 - 1 whose as-of block is `as_of`.
fn initial_state(
    deployment: Bytes32,
    h0: u64,
    as_of: BitcoinInternalHash32,
) -> Result<DecodedCanonicalState, String> {
    let first = CoreHeight::new(h0);
    let state = MinimalForwardState::new(first, CurrentAnchorIndex::new());
    let encoded = encode_validated_canonical_state(
        StateValidationContext::new(deployment, first, CoreHeight::new(h0 - 1), as_of, as_of),
        &state,
    )
    .map_err(|error| format!("{error:?}"))?;
    decode_validated_canonical_state(deployment, first, as_of, encoded.bytes())
        .map_err(|error| format!("{error:?}"))
}

fn write(path: &Path, bytes: &[u8]) -> Result<(), String> {
    std::fs::write(path, bytes).map_err(|error| error.to_string())
}

/// Creates `directory`, which must be new, and fills it with `fill`. When
/// `fill` fails, the directory this call created is removed again, so a
/// refused build leaves no half-built directory behind; an existing path is
/// refused before anything is written or removed.
pub fn in_new_directory<T>(
    directory: &Path,
    fill: impl FnOnce(&Path) -> Result<T, String>,
) -> Result<T, String> {
    std::fs::create_dir(directory).map_err(|error| format!("new directory: {error}"))?;
    fill(directory).inspect_err(|_| {
        let _ = std::fs::remove_dir_all(directory);
    })
}

/// Builds the fixture directory; returns the summary line.
fn run_build(arguments: &[String]) -> Result<String, String> {
    let [
        directory,
        h0_text,
        as_of_hash,
        genesis,
        challenge,
        port_a,
        port_b,
    ] = arguments
    else {
        return Err(
            "usage: test_only_signet_store_fixture <new-dir> <h0> <h0-minus-1-hash-display> \
             <genesis-display> <challenge-hex> <port-a> <port-b>"
                .into(),
        );
    };
    let h0 = h0(h0_text)?;
    let as_of = internal_from_display(as_of_hash).ok_or("as-of hash")?;
    let ports = ports(port_a, port_b)?;
    // Before any node call: mainnet, the default Signet and a non-Signet
    // genesis are refused here.
    let substrate = substrate(genesis, challenge)?;
    let (profile, deployment, binding) = signet_context(substrate, h0)?;
    let session = RpcSession::preflight(ports).map_err(|error| format!("{error:?}"))?;
    let (node_a, node_b) = session.nodes();
    check_nodes([&node_a, &node_b], substrate)?;
    let floor = [&node_a, &node_b].map(|node| node.get_block_hash(h0 - 1));
    let [Ok(floor_a), Ok(floor_b)] = floor else {
        return Err("H0_MINUS_1_UNAVAILABLE: a node names no block at H0 - 1".into());
    };
    if floor_a != floor_b {
        return Err("H0_MINUS_1_DISAGREEMENT: the nodes name two blocks at H0 - 1".into());
    }
    if floor_a != as_of {
        return Err("H0_MINUS_1_NOT_GIVEN: the nodes name another block at H0 - 1".into());
    }
    let as_of = BitcoinInternalHash32::from_internal_bytes(as_of);
    let first = CoreHeight::new(h0);
    let initial = initial_state(deployment, h0, as_of)?;
    in_new_directory(Path::new(directory), |directory| {
        write(&directory.join("profile.bin"), profile.as_bytes())?;
        let store_path = directory.join("store.sqlite3");
        let mut store = SqliteStore::open(&store_path).map_err(|error| format!("{error:?}"))?;
        store
            .initialize_contextual(binding, first, as_of, &initial)
            .map_err(|error| format!("{error:?}"))?;
        drop(store);
        let store_path = std::fs::canonicalize(&store_path).map_err(|error| error.to_string())?;
        let base = |schema: &str| {
            serde_json::json!({
                "schema": schema,
                "context_mode": "CLASS_T_LOOPBACK_SETTINGS_UNVERIFIED",
                "substrate": {
                    "network": NETWORK,
                    "genesis_hash_display": genesis,
                    "signet_challenge_hex": challenge,
                },
                "deployment_id_internal": hex(deployment.as_array()),
                "store_path": store_path.to_str(),
                "loopback_ports": ports,
            })
        };
        let heart_ref = serde_json::json!({
            "deployment_id_internal": hex(deployment.as_array()),
            "register_txid_display": hex(&[0x81; 32]),
        });
        let mut countdown = base("BITAGI_CT_HEART_COUNTDOWN_REQUEST_V1");
        countdown["heart_ref"] = heart_ref.clone();
        write(
            &directory.join("heart_countdown_empty.json"),
            &serde_json::to_vec(&countdown).map_err(|error| error.to_string())?,
        )?;
        let mut heart_get = base("BITAGI_CT_HEART_GET_REQUEST_V1");
        heart_get["heart_ref"] = heart_ref;
        for (name, kind, request) in [
            (
                "status.bin",
                CommandKind::ReplayStatus,
                base("BITAGI_CT_REPLAY_STATUS_REQUEST_V1"),
            ),
            (
                "heart_list.bin",
                CommandKind::HeartList,
                base("BITAGI_CT_HEART_LIST_REQUEST_V1"),
            ),
            ("heart_get.bin", CommandKind::HeartGet, heart_get),
            (
                "sync.bin",
                CommandKind::ReplaySync,
                base("BITAGI_CT_REPLAY_SYNC_REQUEST_V1"),
            ),
            (
                "rewind.bin",
                CommandKind::ReplayRewind,
                base("BITAGI_CT_REPLAY_REWIND_REQUEST_V1"),
            ),
        ] {
            let payload = serde_json::to_vec(&request).map_err(|error| error.to_string())?;
            let envelope = CommandArtifact::new(kind, &payload)
                .and_then(|artifact| artifact.encode())
                .map_err(|error| error.to_string())?;
            write(&directory.join(name), &envelope)?;
        }
        Ok(serde_json::json!({
            "fixture": FIXTURE,
            "mode": "BUILD",
            "network": NETWORK,
            "node_settings_verification": "UNAVAILABLE",
            "genesis_hash_display": genesis,
            "signet_challenge_hex": challenge,
            "substrate_context_hash": hex(&binding.substrate_context_hash()),
            "deployment_id_internal": hex(deployment.as_array()),
            "profile_sha256": hex(profile.profile_sha256().as_array()),
            "first_effective_height": h0,
            "as_of_height": h0 - 1,
            "as_of_block_hash_display": display(*as_of.as_internal_bytes()),
            "store_path": store_path.to_str(),
        })
        .to_string())
    })
}

fn sync_kind(kind: SyncKind) -> &'static str {
    match kind {
        SyncKind::AlreadyCurrent => "ALREADY_CURRENT",
        SyncKind::Extended => "EXTENDED",
        SyncKind::Reorganized => "REORGANIZED",
    }
}

/// One synthetic follow step of an existing fixture store; returns the
/// summary line.
fn run_follow(arguments: &[String]) -> Result<String, String> {
    let [directory, h0_text, genesis, challenge, port_a, port_b] = arguments else {
        return Err(
            "usage: test_only_signet_store_fixture --follow <dir> <h0> <genesis-display> \
             <challenge-hex> <port-a> <port-b>"
                .into(),
        );
    };
    let h0 = h0(h0_text)?;
    let ports = ports(port_a, port_b)?;
    // Before any node call, as for a build.
    let substrate = substrate(genesis, challenge)?;
    let (_, deployment, binding) = signet_context(substrate, h0)?;
    let store_path = Path::new(directory).join("store.sqlite3");
    match std::fs::symlink_metadata(&store_path) {
        Ok(entry) if entry.is_file() => {}
        _ => return Err("STORE_MISSING: <dir>/store.sqlite3 is not a regular file".into()),
    }
    let session = RpcSession::replay(ports, FOLLOW_MAX_CALLS, FOLLOW_DEADLINE)
        .map_err(|error| format!("{error:?}"))?;
    let (node_a, node_b) = session.nodes();
    check_nodes([&node_a, &node_b], substrate)?;
    let (node_a, node_b) = (ObservedSignetNode(node_a), ObservedSignetNode(node_b));
    let mut store = SqliteStore::open_for_context(&store_path, binding)
        .map_err(|error| format!("STORE_REFUSED: {error:?}"))?;
    let receipt = ActiveChainFollower::new(&node_a, &node_b)
        .synchronize_synthetic(&mut store, deployment, substrate)
        .map_err(|error| format!("FOLLOW_REFUSED: {error}"))?;
    drop(store);
    Ok(serde_json::json!({
        "fixture": FIXTURE,
        "mode": "FOLLOW",
        "replay_kind": REPLAY_KIND,
        "replay_label": REPLAY_LABEL,
        "network": NETWORK,
        "node_settings_verification": "UNAVAILABLE",
        "substrate_context_hash": hex(&binding.substrate_context_hash()),
        "deployment_id_internal": hex(deployment.as_array()),
        "sync_kind": sync_kind(receipt.kind()),
        "ancestor_height": receipt.ancestor_height().value(),
        "disconnected_blocks": receipt.disconnected_blocks(),
        "connected_blocks": receipt.connected_blocks(),
        "replay_floor_reanchored": receipt.replay_floor_reanchored(),
        "final_height": receipt.final_height().value(),
        "final_hash_display": display(*receipt.final_hash().as_internal_bytes()),
        "final_state_digest": hex(&receipt.final_state_digest()),
    })
    .to_string())
}

/// The fixture's run: the summary line, or the refusal.
pub fn run(arguments: &[String]) -> Result<String, String> {
    match arguments.split_first() {
        Some((mode, rest)) if mode == "--follow" => run_follow(rest),
        _ => run_build(arguments),
    }
}

/// The process's work: the summary line on `stdout` and exit 0, or one
/// refusal line on `stderr` and exit 2.
pub fn main_with(arguments: &[String], stdout: &mut dyn Write, stderr: &mut dyn Write) -> u8 {
    match run(arguments) {
        Ok(line) if writeln!(stdout, "{line}").is_ok() => 0,
        Ok(_) => 2,
        Err(error) => {
            let _ = writeln!(stderr, "test_only_signet_store_fixture: {error}");
            2
        }
    }
}

fn main() -> ExitCode {
    let arguments = std::env::args().skip(1).collect::<Vec<_>>();
    ExitCode::from(main_with(
        &arguments,
        &mut std::io::stdout(),
        &mut std::io::stderr(),
    ))
}
