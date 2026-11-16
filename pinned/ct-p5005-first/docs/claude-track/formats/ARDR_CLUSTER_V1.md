# ARDR_CLUSTER_V1: the ARDR item-1 clustering tool's inputs, method and output

Status: D2-2 of the CT-P5-001 driver (A #258 issuecomment-6537782009 Q4, Q7 and section 3). The tool is
`tools/claude_track_ardr_cluster.py`; its tests are `tests/claude_track/test_ardr_cluster.py`. Run on the
Class T campaign, its output is Class T Regtest development evidence only.

The tool is built to run unchanged on a real node in Class E: it reads the node only, under an allowlist
of three read methods, needs no transaction index (the Class E reading node runs `txindex=0`), and nothing
in its method assumes TEST_ONLY material or Regtest. Whether the -2c
monitor uses it is decided in the -2c unit (A Q7).

The tool records; it never judges. A's judge computes the expected 4- and 15-report lists itself from the
frozen seed and inputs (045b 4.4 "Expected reports"); the two do not import each other (A Q4).

045b (`docs/claude-track/plans/CT-P3-045b_PREREGISTRATION_DRAFT_EN.md` sections 4.3 item 1 and 4.4) is a
draft input here. The freeze fixes the method bytes (link kinds, transitive closure, the shared-ancestry
boundary; A section 3); the tool takes the boundary and thresholds as inputs (045b 4.4: "fixed in the
frozen bytes, not by the CT-P5-001 driver"). When the freeze changes a rule this document states, this
document follows it in a new version.

## 1. Command

    claude_track_ardr_cluster.py --gates <file> --method <file> [--truth <file>] --out <new file>
        --chain <main|test|testnet4|signet|regtest> (--datadir <dir> | --rpccookiefile <file>)
        [--rpcconnect <host>] [--rpcport <port>] [--bitcoin-cli <path>]

The tool calls `bitcoin-cli -chain=<chain> -nogenerate -nonamed` with `-datadir` or `-rpccookiefile`;
bitcoin-cli reads the cookie itself. bitcoin-cli also reads the reading node's `bitcoin.conf`, and a
command-line option overrides the file: `-nogenerate` overrides a `generate=1` there, which would make
bitcoin-cli call `getnewaddress` (a wallet write) and `generatetoaddress` before the method; `-nonamed`
keeps the parameters positional. Both are accepted by the pinned Core 31.1 and 30.3 bitcoin-cli
(checked on the binaries whose SHA-256 `claude-track-launch-matrix.yml` pins). No credential is ever an argument: an argument that looks like one (`rpcpassword`,
`rpcuser`, `rpcauth`, `stdinrpcpass`, `password`) is refused before argument parsing (exit 5,
`CREDENTIAL_ARGUMENT`). Each input file is read once (a regular file, the final component not a symlink,
at most 16 MiB) as UTF-8 JSON with no float, no non-finite constant and no duplicate key. The output file
must not exist; it is never overwritten.

## 2. Node reads

The tool reads every block of the **window** [`floor_height`, tip], where tip is the node's height when
the run starts, as raw bytes, and holds the window's transactions in memory. No transaction index is
needed (B's D2-2 design answer). The only methods, with their exact parameter shapes, are checked before
any process starts (exit 5, `RPC_NOT_ALLOWED`, otherwise):

| Method | Parameters |
|---|---|
| `getblockchaininfo` | none (`chain` must equal `--chain`, else `CHAIN_MISMATCH`; `blocks` and `bestblockhash` give the tip) |
| `getblockhash` | a height (decimal, no leading zero) |
| `getblock` | a block hash (64 lowercase hex), `0` (raw bytes) |

No wallet, send, generate, block-submission, network or node-control method can be called. Each block's
header hash is recomputed and must be the hash asked for (`BLOCK_HASH_MISMATCH`), its merkle root must be
that of the recomputed txids (`MERKLE_MISMATCH`), and its bytes must parse exactly (`BLOCK_MALFORMED`).
The window must start at or below the tip (`FLOOR_ABOVE_TIP`) and hold at most `max_window_blocks`
blocks (`WINDOW_TOO_LARGE`, exit 2). The blocks read must form one chain from `floor_height` to the
`bestblockhash` that `getblockchaininfo` gave: for every height above `floor_height`, the block's
previous-block hash (header bytes 4 to 36, shown reversed as hex) must be the hash read at the height
below; the block read at the tip height must be that `bestblockhash` (also when `floor_height` is the tip);
and the tip height's hash is read again before and after the scan and must be that `bestblockhash` both
times (`REORG_DURING_SCAN`, exit 2 in each case). So a reorg that goes away and comes back during the scan
is refused, not mixed into the window. At most 2,000,000 transactions are held (`TX_BOUND`). A repeated
coinbase txid (BIP30 history) keeps the first; any other repeated txid is refused (`DUPLICATE_TXID`).
`getblockchaininfo`'s non-integer numbers are kept as text and never read.

## 3. Gate list (`BITAGI_CT_ARDR_GATES_V1`)

`{"schema": "BITAGI_CT_ARDR_GATES_V1", "gates": [...]}`, 1 to 100,000 items, each
`{"gate", "winner_txid", "project"}` and optionally `"block_hash"`:

- `gate`: an integer; the first is any value, every next one is the previous plus 1
  (`GATES_NOT_CONSECUTIVE`). A gate whose winner is not known is listed with `winner_txid` `null`.
- `winner_txid`: the gate's winning REGISTER (display hex), or `null`: **unknown control**. A txid may win
  one gate only (`DUPLICATE_WINNER`).
- `project`: `true` when the winner is the project's own REGISTER (never with a `null` winner).
- `block_hash`: when given, the winner must be in that block (`GATE_BLOCK_MISMATCH`).

Each winner must be in the window (`WINNER_NOT_IN_WINDOW`), inside the boundary (`WINNER_IN_BOUNDARY`:
not a coinbase, not an excluded txid) and REGISTER-shaped at `vout[1]` (`WINNER_NOT_REGISTER`, below). The tool does not replay Core: which REGISTER won a gate is the gate
list's statement (in Class T, the driver's raw log; A's judge replays the block bytes).

`WINNER_NOT_REGISTER` checks the shape of `vout[1]` only. The gate list is trusted for the REGISTER
carrier at `vout[0]` (its bytes are deployment-specific; the tool does not check them). Only the gate
winners' `vout[1]` are compared, so an output of a transaction that is not a listed winner never makes an
`ANCHOR_KEY` link.

## 4. Method file (`BITAGI_CT_ARDR_CLUSTER_METHOD_V1`)

    {"schema": "BITAGI_CT_ARDR_CLUSTER_METHOD_V1",
     "boundary": {"floor_height": <int>, "excluded_txids": [<txid>, ...]},
     "max_depth": <1..10000>,
     "max_window_blocks": <1..100000>,
     "thresholds": [<int>, ...]}

A PENDING marker anywhere (a string value starting with `PENDING`, as in `ARDR_RUN_V1.md` section 3) is
refused with exit 3 `METHOD_PENDING`. `thresholds` is strictly ascending (045b 4.4: 4 and 15).

**Shared-ancestry boundary** (045b 4.3 item 1: "the regtest funding source and the coinbase outputs common
to all wallets are excluded, since they would link every wallet"). A transaction is outside the boundary
when it is a coinbase (any coinbase), its txid is in `excluded_txids` (the funding source), or it is not
in the window (confirmed below `floor_height`). A transaction outside the boundary is neither an ancestor
nor walked past; each winner's output records how many distinct transactions its walk stopped at, by
kind (`boundary_stops`: `coinbase`, `excluded`, `outside_window`).

## 5. Method

Elements are the gates' winners. For each winner:

- **Ancestor set:** the winner itself and every transaction reached through inputs, breadth first, that
  is inside the boundary, up to `max_depth` hops. A transaction inside the boundary past the cap is left
  out and the winner's gate is listed in `walk_truncated`. When any walk was truncated, the output's
  top-level `incomplete` is `true` (else `false`), and the judge reads that report as **incomplete**: a
  link may be missing, so its reports and metrics are not a full record of the method. An `incomplete`
  report is not PASS: the judge counts that run as an exclusion with its reason (045b 10 % rule) and gives
  no judgement on it (A 6541483273 item 4).
- **Anchor key:** the 32-byte witness program of `vout[1]` when its scriptPubKey is exactly
  `0x51 0x20 <32 bytes>` (the Anchor predicate, SSoT 6.1; REGISTER `vout[1]`, SSoT 12 item 6).

**Links** (045b 4.3 item 1), one per pair of winning gates and kind:

- `ANCESTRY`: the two ancestor sets meet; `via` is the smallest shared txid.
- `ANCHOR_KEY`: the two Anchor keys are equal; `via` is the key.

**Link-based clusters:** the transitive closure of all links (union-find). A cluster's id is `L` followed
by its first gate number. **Ownership clusters** (only with ground truth): the winner's wallet's owner;
the id is the owner's name.

**Runs and reports** (045b 4.4), per clustering. The rules below are A's decisions on PR #616 (A
6541483273); A's judge and the 045b freeze use the same rules.

- **Project gates (reading (b), A 6541483273 item 2).** 045b 4.4 counts "consecutive gates won by one
  common-control cluster other than the project". Only the project's own gates (those marked `project`)
  are removed: a project gate is in no run and breaks every run. The other gates of a cluster that holds
  a project gate still form runs of that cluster and are reported like any other. `project_clusters`
  names the clusters that hold a project gate, and `project_cluster_other_gates` records their
  non-project winning gates: `gates`, and, with Class T truth, `not_project_owner`, those of them whose
  winner's owner is not an owner of a project gate's winner (`null` without truth).
- **Known clusters (R1).** For each cluster C, a run is a maximal interval of consecutive gates each won
  by C (not as a project gate) or of unknown control that holds at least one gate won by C. So an unknown
  gate never breaks a run and is counted in its length, as possibly C ("never as independent", 045b 4.3
  item 1 missing-data rule); two clusters' runs may share an unknown gate; a gate won by any other known
  cluster, or a project gate, ends the run.
- **Unknown-only runs (R3, A 6541483273 item 1).** In addition, every maximal interval of consecutive
  unknown gates is a run of the cluster `UNKNOWN` (possibly one controller; 045b 4.3 item 1: "counts as
  'unknown control', never as independent"). The thresholds are the same as for clusters; there is no
  other number. Any known gate, a project gate included, ends it. These gates may also count in a known
  cluster's run as above. No ownership cluster may be named `UNKNOWN` (`TRUTH_OWNERS`). A Class T campaign
  plants no unknown gate, so the judge's expected `UNKNOWN` list is empty; an `UNKNOWN` report there is a
  logging gap, and the judge counts that run as an exclusion with its reason (045b 10 % rule).

For each threshold T, every run of length at least T gives one report:

    {"cluster", "threshold": T, "trigger_gate", "first_gate", "last_gate", "length", "unknown_gates": [...]}

sorted by `trigger_gate`, then `cluster`. The trigger gate is the first gate at which the run holds T
gates and C has won at least one of them:

    trigger_gate = max(first_gate + T - 1, the run's first gate won by C)

So a run that starts with T or more unknown gates triggers at C's first win, never before it. For an
`UNKNOWN` run, `trigger_gate = first_gate + T - 1` and `unknown_gates` lists every gate of the run.

**Repeat-winner** (045b 4.5 "repeat-winner concentration"), per clustering: `known_gates`,
`unknown_gates`, `top_cluster_gates`, `top_clusters`, `longest_run` (the longest known-cluster run under
R1 with every winning gate counted as its cluster's, project gates included; `UNKNOWN` runs are not
counted).

## 6. Ground truth (`BITAGI_CT_ARDR_CLUSTER_TRUTH_V1`, Class T only)

    {"schema": "BITAGI_CT_ARDR_CLUSTER_TRUTH_V1",
     "winners": {<txid>: <wallet>, ...},
     "owners": {<wallet>: <owner>, ...},
     "planted_links": [{"kind": "ANCESTRY" | "ANCHOR_KEY", "wallets": [<wallet>, ...]}, ...]}

Every gate winner must be in `winners` (`TRUTH_WINNER_MISSING`). A planted link group joins wallets of one
owner (`TRUTH_LINK_ACROSS_OWNERS`; 045b 4.6: "No key is shared across owners"). `planted_links` are the
links actually placed on chain (shared funding ancestry inside the boundary, reused Anchor keys); the
generator states them.

**Metrics** (045b 4.3 item 1), over the wallets that won at least one gate, as exact fractions
`{"num", "den"}`. When `den` is 0 (no pairs to measure) the fraction is `{"num": 0, "den": 0,
"undefined": true}`; otherwise it has no `undefined` key. The judge reads an undefined fraction as having
no value: it is neither 1.0 nor 0, and that metric is NOT_ESTABLISHED for that run (A 6541483273 item
4). In 045b item 1's design (40 wallets, 10 owners) same-owner pairs always exist, so an undefined
fraction there is an input defect.

- D, the detected pairs: the tool's links lifted to wallets, closed transitively;
- P_L, the planted pairs (A accepted this rule, A 6541483273 item 3): each planted link group is first
  restricted to the winning wallets, then the restricted groups are closed transitively. A wallet that never wins cannot
  join two winning wallets: the tool sees only winners, so it could never detect a pair joined only
  through such a wallet (045b 4.6 makes this reachable: each wallet shares funding ancestry or its owner's Anchor key at random, and the other gates' winners are drawn among all 40 wallets, so a linked wallet may never win). Such a
  pair is in P_O but not in P_L, so it counts in `unlinkable_share`, not against `link_recall`. (The
  other reading, closing over all wallets and then restricting, would count it as a missed planted pair.)
- P_O, the same-owner pairs of winning wallets.
- `link_recall` = |D ∩ P_L| / |P_L|; `link_precision` = |D ∩ P_L| / |D|; `ownership_recall` =
  |D ∩ P_O| / |P_O|; `unlinkable_share` = |P_O − P_L| / |P_O| (a published limit, SSoT:2452).
- `missed_planted_pairs` (P_L − D) and `false_pairs` (D − P_L) list the pairs behind any value below 1.

045b 4.3 item 1 NO-GO is "link-based recall or precision below 1.0 on the Class T data"; the judge
decides it, not this tool.

## 7. Output (`BITAGI_CT_ARDR_CLUSTER_V1`)

One JSON object, ASCII, keys sorted, separators `,` and `:`, ending in one LF byte:

| Key | Value |
|---|---|
| `schema` | `BITAGI_CT_ARDR_CLUSTER_V1` |
| `labels` | `TOOL_RECORD_NOT_VERDICT`, `NODE_READ_ONLY` |
| `chain` | the node's chain |
| `window` | `floor_height`, `tip_height`, `tip_hash`, `blocks`, `transactions` (held from the window) |
| `inputs` | SHA-256 of the gate list, method and ground-truth files' bytes (`truth_sha256` `null` without one) |
| `method` | the method as read |
| `gates` | `count`, `first`, `last`, `unknown` and `project` gate numbers |
| `winners` | per winning gate: `gate`, `winner_txid`, `height`, `block_hash`, `anchor_key`, `ancestors_in_boundary`, `boundary_stops`, `link_cluster` |
| `walk_truncated` | gates whose walk stopped at `max_depth` |
| `incomplete` | `true` when `walk_truncated` is not empty, else `false` (section 5) |
| `links` | `{"kind", "gates": [a, b], "via"}`, by gate pair, ANCESTRY before ANCHOR_KEY |
| `link_based` | `clusters` (`id`, `gates`, `project`), `project_clusters`, `project_cluster_other_gates` (`gates`, `not_project_owner`), `reports` (threshold → list), `repeat_winner` |
| `ownership` | the same for ownership clusters, or `null` without ground truth |
| `metrics` | section 6, or `null` without ground truth |

The output is a function of the inputs and the node's chain (the window's blocks) only.

## 8. Exit codes

`0` output written (not a verdict) · `2` validation failure (including a window too large and a reorg
during the scan) · `3` missing prerequisite (an input file, `bitcoin-cli`, a failed or timed-out node call,
PENDING in the method, the output already existing) · `4` internal error (including an output that cannot
be written) · `5` security policy (optimized Python, a credential-like argument, a method or parameter
outside the allowlist).

The output file is created new (`open(..., 'x')`). If it cannot be created, that is exit 3: an existing
path is `OUTPUT_EXISTS`, any other failure (a missing parent directory, no permission) is
`OUTPUT_UNAVAILABLE`. Once the tool has created the file, a failed write, flush or close (for example
`ENOSPC`, `EFBIG`) is exit 4 `OUTPUT_WRITE_FAILED` (AGENTS.md section 12: a tool that cannot write its
output exits 4): the tool closes the stream, removes the partial file it created (only if the path still
names that file) and writes no report. A refusal prints one JSON line
`{"code", "exit", "result": "FAIL"}` with a fixed code; no input text, node message or path. The tool ends
through `tools/claude_track_exit.run`.
