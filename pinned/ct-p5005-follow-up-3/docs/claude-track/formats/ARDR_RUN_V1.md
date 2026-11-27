# ARDR_RUN_V1: the CT-P5-001 driver's raw log, policy file and seed draw

Status: D1 of the CT-P5-001 driver (A #258 issuecomment-6537782009 Q3, Q6, Q9 and section 4; B
-6537801599 defaults (a)-(d)). Class T Regtest development evidence only. The tool is
`tools/claude_track_ardr_driver.py`; its tests are `tests/claude_track/test_ardr_driver.py`.

The driver records; it never judges. A's judge (a separate tool, A's unit) reads the raw log and the
frozen policy, recomputes the draws, and replays the logged block bytes. The two do not import each
other.

045b (`docs/claude-track/plans/CT-P3-045b_PREREGISTRATION_DRAFT_EN.md` sections 4.3-4.6) is a draft
input here, not frozen bytes. When the freeze changes a rule this document cites, this document follows
it in a new version. *Dated line 2026-11-10 (B, FZ-6, F5; C27 pointer: 045b :1194's dated line "A, freeze verification C27"; A #664 issuecomment-6746599499): after the 045b freeze (#664, main `317ecbf5`) this file follows it with same-line pointers from its DRAFT and PENDING_FREEZE marks to the frozen 045b, not with a new file: no rule here changes, and no line moves (045b cites this file by line, 045b :1903). The C27 pointers, each citing both sources: :295 to 045b :1221 (F13, the key rule; its log label is flipped at bidders :64 (dated line here at :462)); :374 and :378 to 045b :1140 (F11, `b` a multiple of 250); :402 to 045b :1140 and :1901 (section 14.21, the frozen ARDR policy values); :1337 to 045b :1083 (an item-1 job that dies at gate g); :1415 to 045b :1901 and :545 (the pool run gates); :1459 to 045b :1901; :1597, :1763 and :1930 to 045b :1219 (F2, the item-2 L0 seat S1) and :1194 (the F3 L0 policy keys row); :1770 to 045b :1052 (the L0 seat takes no `BID_FEE` draw); :2561 to 045b :1194 and :1901. FZ-6 fix round 1 adds the two "A decides at the freeze" marks that 045b's C28 ruling settled: :1494 and :1727 to 045b :1903 (its dated line "A, freeze verification C28"). :2118's DRAFT (item 4's `p_0` rule) keeps no pointer: item 4's L0 keys come with its follow-up policy (045b :1194). Whether A wants a separate V2 file instead is asked in the FZ-6 note.*

## 1. Topology

Every run starts four fresh Regtest nodes, each in its own new data directory under the run's `--work`
directory (mode 0700):

| Role | Core | Binaries | Driver user's whitelist (exactly) | Other users |
|---|---|---|---|---|
| `miner` | 31.1 | `--node-a` | `getbestblockhash`, `getblockchaininfo`, `getnetworkinfo`, `getrawmempool`, `stop` | the miner process's user: exactly `getblocktemplate`, `submitblock`, `gettxout` |
| `relay` | 31.1 | `--node-a` | those five, `addnode`, `getconnectioncount`, `sendrawtransaction` (public bidders) | none |
| `A` | 31.1 | `--node-a` | those five, `addnode`, `testmempoolaccept` | none |
| `B` | 30.3 | `--node-b` | those five, `addnode`, `testmempoolaccept` | none |

`relay` connects to `miner`; `A` and `B` connect to `relay`. The driver checks each node's version
(`getnetworkinfo`) against this table before the first block.

Credentials. Each node has its own driver user (`oe.RunUser`, a fresh password per run), so a credential
reaches one node only. The node object is `claude_track_regtest_offline_export.Node`, started by
`RoleNode` with its own `rpcauth` and `rpcwhitelist` arguments (`oe.Node.start` and `oe.ALLOWED_RPCS`
are not used, so oe's other callers are unchanged): each user is whitelisted for exactly its set in the
table above, `-rpcwhitelistdefault=1` (a user without a whitelist line could call nothing), and the cookie is whitelisted to nothing and stays in its data
directory; the driver never reads it into a log. There is no send-only user and no fixture read user.
The node refuses anything else with HTTP 403; `RoleNode` also refuses a call outside the set before
`bitcoin-cli` starts. No credential on any node can call `generatetodescriptor`, `generateblock`,
`invalidateblock`, `prioritisetransaction` or `setnetworkactive`; only the relay's driver user can call
`sendrawtransaction`. One exception (D3a-2a, section 23): in an `ITEM4_REORG` run only, the miner node's
driver user is whitelisted for its set above plus `invalidateblock` (`Topology(reorg=True)`); no other
user, node or experiment gets it, and no credential gets `reconsiderblock`.

The miner process is a separate operating-system process (`claude_track_ardr_driver.py miner`). It gets
its own user's credential on the miner node on standard input, and nothing else: not the miner node's
driver user, no other node's credential, no relay access. Its RPC set is `MINER_RPCS` =
{`getblocktemplate`, `submitblock`, `gettxout`}, enforced by the node's whitelist and in the process
before any call. It never calls `sendrawtransaction`, `generateblock` or
`generatetodescriptor`; every block of the run, setup blocks included, is built from a template.

## 2. Raw log

One JSON Lines file per run (`--out`, a new file), ASCII, each line one JSON object ending in one LF
byte. Keys are sorted, separators are `,` and `:`. A line that would hold a run secret (any node user's
password, salt or digest, or the work directory path) is refused before it is written (exit 5).
`--work` must be an absolute path and no such value may be shorter than 8 characters (section 21).
The check looks for each such value both as written and in the JSON-escaped form the line uses
(backslash, quote and non-ASCII characters escaped), in keys as well as values; a refused line adds
nothing to the file and does not use up a `seq` number.

Every line carries:

| Key | Value |
|---|---|
| `schema` | `BITAGI_CT_ARDR_RAW_V1` |
| `seq` | 1, 2, 3, … in write order |
| `t_ns` | the run clock (section 5) at the event |
| `event` | below |
| `mode` | `CONFIRMATORY`, `EXPLORATORY` or `PR_SMOKE` |
| `evidence_status` | `CONFIRMATORY` in CONFIRMATORY mode, otherwise `EXPLORATORY` |
| `policy_sha256` | SHA-256 of the policy file's exact bytes |
| `registration_sha256` | SHA-256 of the registration file's bytes (CONFIRMATORY), else `null` |
| `labels` | `CLASS_T`, `REGTEST`, `TEST_ONLY_OP_TRUE_OUTPUTS`, `CLASS_T_DEVELOPMENT_EVIDENCE_NOT_S17_PREP`, `DRIVER_RECORD_NOT_VERDICT` |
| `unit` | section 4 |

Three event kinds carry their own `labels` field, the rung labels (per rung `verdict` and `outcome`, and in
`ITEM4_LABELS` the two flags too):
`L0_LABELS` (section 20), `ITEM4_LABELS` and `ITEM4_L0_OBSERVE` (section 24). In those lines it replaces the
envelope `labels` above, because `RawLog.write` (`tools/claude_track_ardr_driver.py:1327-1328`) writes an
event's fields after the envelope. So the line's `labels` is the rung labels, and the envelope's labels are
not on that line (B-J5Z, 2026-11-05, A #258 issuecomment-6660854606 B5; the field keeps its name for now).

Events (D1):

| `event` | Extra keys |
|---|---|
| `RUN_START` | `observation_start` (section 5), `miner_policy`, `node_versions` |
| `DRAW` | `e`, `r`, `label`, `k` (the try that was accepted), `value`, and for `GATE_INTERVAL` `t_gate_seconds` and `applied` (D1's smoke records the draw but does not wait for it) |
| `MEMPOOL` | `node`, `txids` (sorted `getrawmempool`), `before_block` |
| `TEMPLATE` | `template` (the `getblocktemplate` answer as received), `private_set` (every private transaction the miner held when it asked: `txid`, `hex`); `t_ns` is the miner process's clock reading when it asked |
| `BLOCK` | `height`, `block_hex` (the full submitted bytes), `block_hash`, `coinbase_txid`, `coinbase_value`, `miner_policy`, `order` (each included transaction: `txid`, `source` `PRIVATE` or `TEMPLATE`, `fee`, `vsize`), `cut`, `dropped`, `private_unresolved`, `submit_result` (`null` = accepted), `interval_seconds` (whole seconds since the previous submit, rounded up; `null` for the first); `t_ns` is the submit time |
| `BLOCK_ACCEPTED` | `block_hash`, `nodes` (every node whose best block is it) |
| `TESTMEMPOOLACCEPT` | `node` (`A` or `B`), `txid`, `result` |
| `PUBLIC_SENT` | `node` (`relay`), `txid`, `hex`, `answer` |
| `PRIVATE_HANDOFF` | `txid`, `hex` (given to the miner process only) |
| `RUN_END` | `status`, the run summary |

The driver keeps the run's held private set (every private txid handed to the miner process and not yet
in an accepted block) across all blocks of the run. Before each block it snapshots all four mempools and
stops the run (exit 2, `PRIVATE_IN_MEMPOOL`) if a held txid is in any of them. The miner process refuses
a template that holds one of its held private txids (exit 2, `PRIVATE_IN_TEMPLATE`) before it builds or
submits a block. A block that not all four nodes accept within 120 s stops the run (exit 2,
`BLOCK_NOT_ACCEPTED`). This is a guard on the driver's own
invariant, not a verdict: the judge checks the same thing from the `MEMPOOL` and `BLOCK` lines.

The judge can see from the bytes alone which transactions a block holds and in which order, so it does
not rely on `order`.

Slice records, the collection and the observation list are section 13 (D4).

## 3. Policy file (`BITAGI_CT_ARDR_POLICY_V1`)

One JSON object, read once as bytes (at most 1 MiB, duplicate keys and non-finite numbers refused).
Its SHA-256 is the `policy_sha256` of every log line. Keys (closed set):

| Key | Value |
|---|---|
| `schema` | `BITAGI_CT_ARDR_POLICY_V1` |
| `seed` | 64 lowercase hex characters (32 bytes), or a PENDING marker |
| `counts` | object: experiment name → run count (integer, 1 ≤ count < 2^32) or a PENDING marker; in CONFIRMATORY every experiment named in `experiments` needs one (section 3 modes) |
| `experiments` | object: experiment name → `{"miner_policy": <name>}` |
| `bidders` | list (D2 defines its items) or a PENDING marker |
| `thresholds` | optional object (D2/A define it); may hold PENDING markers |

Experiment names: `ITEM1`, `ITEM2`, `ITEM3`, `ITEM4_SELF_DEALING`, `ITEM4_FEE_ASYMMETRY`,
`ITEM4_CENSORSHIP`, `ITEM4_REORG`, `POOL`.

Miner policy names: `ITEM2_DEFAULT` is built (section 7). `ITEM1_WINNER_ONLY`,
`ITEM4_SELF_FIRST_ZERO_FEE`, `ITEM4_CENSOR_144`, `ITEM4_REORG_REPLACE` and `POOL_50_30_20` are reserved
for D2/D3a and refused with `MINER_POLICY_NOT_BUILT` (exit 3); any other name is refused with
`MINER_POLICY_UNKNOWN` (exit 2).

PENDING marker: any JSON string value, at any depth, that starts with `PENDING` (for example
`"PENDING"` or `"PENDING Q7"`).

Modes:

- `CONFIRMATORY` needs `--registration` and `--registration-sha256`. The driver checks, in this order:
  the registration file's SHA-256 equals `--registration-sha256`, else exit 6
  `REGISTRATION_BYTES_CHANGED`; the policy file's SHA-256 is one the registration binds, else exit 6
  `POLICY_NOT_REGISTERED`; no PENDING marker is left, else exit 3 `POLICY_PENDING`; then the shape
  (exit 2); every experiment named in `experiments` (so the run's experiment) has a count in `counts`,
  else exit 3 `POLICY_COUNT_UNSET` (045b 4.6: "a frozen policy with any count unset is refused"); then
  the experiment's miner policy. So the freeze fills: `seed`, a count for each experiment it lists,
  `bidders`, every `thresholds` value, and no PENDING marker anywhere. The refusals have the shape of
  `tools/ct_preregistration_receipt.py`'s different-hash refusal: one JSON line
  `{"code": …, "exit": 6, "result": "FAIL"}`. D1 builds no confirmatory campaign: a CONFIRMATORY `run`
  that passes these checks ends with exit 3 `CONFIRMATORY_CAMPAIGN_NOT_BUILT` before any node starts.
  A CONFIRMATORY run also needs `--started-at`.
- `EXPLORATORY` and `PR_SMOKE` accept a draft policy (PENDING markers allowed), refuse registration
  arguments (exit 2), and mark every line `evidence_status` `EXPLORATORY`. The judge leaves those
  logs out of every confirmatory verdict.

## 4. Registration (D1 placeholder)

The registration is the CT-P5-005 evaluation policy, which binds the policy files' hashes; it is not the
policy file (A #258 -6537782009 Q6; `CT-P5_PHASE_PLAN_KO.md:115-116`). Its format belongs to A's P5-005
unit. Until that unit names it, the driver reads the registration as a JSON object and takes one key,
`ardr_policy_sha256`: a non-empty list of lowercase hex SHA-256 values. Any other key is ignored. When
A's format is fixed, the driver's read follows it. *Note 2026-11-02 (045b freeze draft 1; checklist S21): the registration also carries `d2_2_tool_sha256` (A #258 issuecomment-6561758412); see the addition to section 4 at the end of this file. The list's shape is set at the 045b freeze.*

## 5. Clock and unit identifiers

Clock: one monotonic clock per run, Python `time.monotonic_ns()` (CLOCK_MONOTONIC), as in
`XD1_EVENT_CHAIN_V2.md:132`. The driver and the miner process run on one host and read the same clock,
so their stamps are comparable; nothing in the log uses wall time except `observation_start`. Every
measured duration is in whole seconds, rounded up (045b 4.6): `ceil(ns / 10^9)`.

Observation start (`RUN_START` `observation_start`): `{"source": "GITHUB_JOB_STARTED_AT", "utc": …}`
from `--started-at`, the GitHub job's server time `started_at`; the receipt's "strictly earlier than the
first observation" (045b 3.2) is compared with this time, not with the monotonic clock. Without
`--started-at` (local EXPLORATORY or PR_SMOKE runs) it is `{"source": "LOCAL_EXPLORATORY", "utc": …}`
from the host clock.

Unit identifiers (`unit` on every line): `{"experiment", "run", "gate", "cohort"}`; `gate` and `cohort`
are `null` where the unit does not use them. They let the freeze choose the unit of a run and of an
exclusion per experiment (A's default: gate for items 1 and 2, cohort for item 3, run for item 4 and
the pool run). *Dated line 2026-11-25 (B, B4-09, FD-CT-67; 045b :1085, judge decision 6 in #258 issuecomment-6557890079, Claude decision #258 issuecomment-6567369540; WORK_TABLE B4-09 and READ-19): for the pool the exclusion unit is the gate, not the run. The pool's "a run of 4 gates" defines its run unit only, and its 10% rule counts gates, more than 20 of its 200 gates (045b :1085); item 4's unit stays the run (045b :1084). 045b :1085 and the phase plan's 17.9 line (`CT-P5_PHASE_PLAN_KO.md:563`) cite this sentence as `:169`. See the addition at the end of this file (2026-11-25, B-B1 and B4-09).*

## 6. Seed draw

Draw `k` of choice `label` in run `r` of experiment `e`:

    D = SHA-256(seed ‖ e ‖ 0x00 ‖ u32be(r) ‖ label ‖ 0x00 ‖ u32be(k))

`e` and `label` are the exact ASCII strings of 045b 4.6's draw table; `k` starts at 0 for every choice.
An integer uniform in `[0, n)` takes `x` = the first 8 bytes of `D` as a big-endian `u64` and accepts
`x mod n` only when `x < floor(2^64 / n) × n`; otherwise it retries with `k + 1`.

Labels the driver accepts: `ITEM1`: `OWNER_W00`-`OWNER_W39`, `ANCESTRY_W00`-`ANCESTRY_W39`,
`KEY_REUSE_W00`-`KEY_REUSE_W39`, `WINNER_G000`-`WINNER_G099` and `WINNER_G120`-`WINNER_G199`;
`ITEM2`: `BID_FEE_0`-`BID_FEE_4`, `PRIVATE_FEE`, `PUBLIC_FEE_1`-`PUBLIC_FEE_4`, `GATE_INTERVAL`;
`POOL`: `PRODUCER_H` followed by the height in decimal without leading zeros. `t_G` = the
`GATE_INTERVAL` value (`n` = 1,200) + 1 seconds.

Each label is bound to the draw table's `n`: `OWNER_W` 10, `ANCESTRY_W` 100, `KEY_REUSE_W` 100,
`WINNER_G` 40, `GATE_INTERVAL` 1,200, `PRODUCER_H` 100; any other `n` for them is refused (exit 2,
`DRAW_N`). The `ITEM2` fee labels' `n` depends on `b` and `p`, so the caller gives it. `r` and `n` must be
integers (a JSON or Python boolean is refused, `DRAW_RANGE`).

Test vectors, seed = bytes 0x00, 0x01, …, 0x1f
(`000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f`). These values are computed by the
driver (and recomputed with plain `hashlib` in its test); A compares them with its own independent
implementation and 10,000 draws in its D1 integration check:

| `e` | `r` | `label` | `n` | first 8 bytes of D at k = 0 | value | k |
|---|---|---|---|---|---|---|
| `ITEM2` | 0 | `GATE_INTERVAL` | 1200 | `1f75e2e8b0b704bc` | 332 (`t_G` = 333 s) | 0 |
| `ITEM2` | 7 | `GATE_INTERVAL` | 1200 | `10f2d003473f515c` | 956 | 0 |
| `ITEM1` | 0 | `OWNER_W00` | 10 | `e50aa48e1d05760c` | 4 | 0 |
| `ITEM1` | 3 | `WINNER_G120` | 40 | `b6a4dffe187cfff3` | 19 | 0 |
| `POOL` | 0 | `PRODUCER_H105` | 100 | `bdec8d2c069d526d` | 9 | 0 |
| `ITEM2` | 1 | `BID_FEE_0` | 3001 | `7cefee403c1f7972` | 1695 | 0 |
| `ITEM2` | 2 | `BID_FEE_0` | 2^63 + 1 | `c03b56574191c1a1` (rejected), then `3b3f2436e15d5c60` at k = 1 | 4269170789898345568 | 1 |

The last row is a rejection example (`BID_FEE_0`'s `n` is the caller's; 2^63 + 1 makes a rejection
likely), not a value a campaign uses. The command
`claude_track_ardr_driver.py draw --seed <hex> --experiment <e> --run <r> --label <label> --n <n>`
prints `value` and `k`.

## 7. Miner policy `ITEM2_DEFAULT`

045b 4.3 item 2 and A Q3: ancestor feerate descending, ties by txid, parents before children, cut at the
weight cap. The name `ITEM2_DEFAULT` is the identity of exactly the rule set below, so the freeze can
bind it by name; any other rule (for example skipping a package that does not fit instead of ending the
selection, or a different tie order) is a new variant name, never a change under this one. Exactly:

1. The candidates are the template's transactions (fee and parents from the template) and the private
   set (fee = inputs − outputs, input values from the candidates or `gettxout` on confirmed outputs; a
   private transaction whose input value cannot be found is left out and listed in
   `private_unresolved`, and so is every private transaction that spends one left out, to a fixpoint).
   A template holding a private txid is refused (`PRIVATE_IN_TEMPLATE`). A candidate whose parent is
   not a candidate is refused (`MINER_PARENT_MISSING`).
2. Repeat while candidates remain: for each remaining candidate take its package (itself and its
   remaining ancestors). Pick the package with the highest feerate, fees over vsizes (vsize = ceil(weight
   / 4)), compared exactly by cross-multiplication; a tie goes to the smaller txid (display hex,
   ascending).
3. If a package member spends an outpoint a selected transaction already spends, or one another member of
   the same package spends, those members and their descendants are dropped (`dropped`), and step 2
   repeats.
4. If the package's weight would take the block past the budget (the template's `weightlimit` − 4,000
   weight units for the header, counts and coinbase), selection ends: the package and every remaining
   candidate are `cut`. A smaller package after it is not tried.
5. Otherwise the package is appended parents first; among members whose parents are placed, the smaller
   txid first.

The coinbase has the BIP34 height (`CScript() << height`: `OP_1`…`OP_16` for heights 1-16, otherwise
the minimal little-endian push with a 0x00 sign byte when the top bit is set; the test checks it, the
merkle root and the commitment against Core 31.1 Regtest blocks), an 8-byte extranonce push, one P2WSH(OP_TRUE)
output of subsidy plus the included fees (subsidy = template `coinbasevalue` − template fees), and, when
an included transaction has a witness, the BIP141 commitment output and a 32-byte zero witness. Header:
template `version`, `previousblockhash`, `curtime` and `bits`; the first nonce meeting the target.

Not checked by the miner (D1): the block sigop cost (template transactions are within it; a private
set is small), and a private transaction's own validity, which `submitblock` decides. The ordering
recomputes every package each round (quadratic in the candidates).

## 8. Exit codes

`0` run done (`result` `DONE`; not a verdict) · `2` validation failure · `3` missing prerequisite
(including PENDING in CONFIRMATORY, a reserved miner policy, missing registration or `--started-at`) ·
`4` internal error · `5` a run secret would enter the log · `6` registration or policy hash refusal.
A refusal prints one JSON line with a fixed `code` (for a node failure: `PREREQUISITE` or `MISMATCH` and
the message's leading code words only, for example `PREREQUISITE NODE_VERSION B` or
`PREREQUISITE RPC_FAILED MINER`; never a node's stderr, a path or a user name). A refusal inside the miner
process crosses to the driver with its exit code: its `code` is `MINER` and the miner process's code (for
example `MINER PRIVATE_IN_TEMPLATE`, exit 2; `MINER PREREQUISITE RPC_FAILED MINER`, exit 3;
`MINER POW_NOT_FOUND`, exit 4). A node call or a worker call past its time limit is a missing
prerequisite (exit 3; section 21), not an internal error.
The tool ends through `tools/claude_track_exit.run`.

## 9. Synthetic-bidder / competitor generator (D2-1)

Status: D2-1 of the CT-P5-001 driver (A #258 -6537782009 Q2, section 4 row D2; A -6538196742 1E Q15).
Class T Regtest development evidence only. The tool is `tools/claude_track_ardr_bidders.py`; the
generator is the ignored Rust worker `crates/bitagi-signer/tests/ardr_bidder_generator.rs`
(`worker::ardr_bidder_worker`); the tests are `tests/claude_track/test_ardr_bidders.py` and the
worker file's own cells.

There is one generator for both sets. Every REGISTER is built, signed and released through the
product path of the 1e-1 launch-matrix worker (`prepare_register_construction`, `rp::begin_register`,
`finalize_candidate`, the inherited `Fixture::sign`), with fresh ledgers (wallet, signer, proof) for
each set, wallet and gate. Rung k ≥ 1 is the product replacement of rung k − 1: the same funding
outpoint, `CandidateOrigin::ReplacementOf`, the same lineage. A gate at H0 uses the pre-effective
context; a later gate uses the effective-final context with the canonical state at G − 1. Every
REGISTER has lock G − 1 and sequence 0xfffffffd.

| Set | Wallet ids | Key labels | Ledger identities | Marks |
|---|---|---|---|---|
| `SYNTHETIC` | `W00`-`W39` | `SYNTHETIC_<w>_FEE`, `SYNTHETIC_<w>_ANCHOR_H<hhh>` | `ARDR_TEST_ONLY_SYNTHETIC_<w>_G<gate>_V1\|WALLET` (and `\|SIGNER`, `\|PROOF`) | `SYNTHETIC`, `TEST_ONLY` |
| `COMPETITOR` | `C00`-`C09` | `COMPETITOR_<c>_FEE`, `COMPETITOR_<c>_ANCHOR_H<hhh>` | `ARDR_TEST_ONLY_COMPETITOR_<c>_G<gate>_V1\|…` | `COMPETITOR`, `TEST_ONLY` |

The worker refuses a label of the other set. 1e-2b-2b's E7 and E10 competitor uses the `COMPETITOR`
set.

**Key rule (DRAFT, PENDING_FREEZE).** The freeze sets the seed-to-key rule (A -6537782009 section 3). *Dated line 2026-11-10 (B, FZ-6, C27 pointer; sources 045b :1194's C27 dated line and A #664 issuecomment-6746599499): frozen as written, 045b :1221 (F13: this DRAFT key rule, `TEST_ONLY_KEY` reserved, the key-set labels apart from the draw labels). Its log label, the ground truth's `labels` entry at bidders :64, is `KEY_RULE_FROZEN_045B_F13` since FZ-6 (was `KEY_RULE_DRAFT_PENDING_FREEZE`; 045b :1221, a label change only; A #258 issuecomment-6738933506; the name accepted by A #258 issuecomment-6757790020), section 12 (:462).*
Until then, the scalar of a key with label `L` in run `r` is the first

    D = SHA-256(seed ‖ "TEST_ONLY_KEY" ‖ 0x00 ‖ u32be(r) ‖ L ‖ 0x00 ‖ u32be(k)),  k = 0, 1, …

that is a valid secp256k1 secret key. This is the section 6 digest form. `TEST_ONLY_KEY` is not an
experiment name of the 045b draw table, so a key digest never equals a draw digest. The key object is
the inherited fixture helper's (`public_key`/`tweaked` in `crates/bitagi-signer/tests/common/two_node.rs`;
`OfflineKey::import_offline`, `BackupMode::TestOnlyRehearsal`, the BIP341 output key). Only the scalar
source differs: the inherited `scalar(n)` holds one byte. The worker never writes a scalar out.
The fee key pays the funding and the change. The Anchor key is the successor (Anchor) key of
the REGISTER: 045b 4.6's `item 1 Anchor keys`.

**Item 1 ownership.** These use section 6 draws in experiment `ITEM1`, run `r`:

- `OWNER_W<ii>` (n = 10) gives wallet `W<ii>`'s owner `O<value>`;
- `ANCESTRY_W<ii>` < 30 means the wallet shares funding ancestry inside its owner;
- `KEY_REUSE_W<ii>` < 30 means the wallet uses the owner's base key for every Anchor.

The base key is `SYNTHETIC_<base>_ANCHOR_H000`, where `<base>` is the owner's lowest-indexed wallet. A
wallet that does not reuse it uses `SYNTHETIC_<w>_ANCHOR_H<h>` for its Heart number `h`. The planted
owner is the owner with the most wallets, the lowest index on ties.

**Funding** (045b :351, 4.3 item 1: "the regtest funding source and the coinbase outputs common to all
wallets are excluded"). The funding is placed **once per run, before the run's first gate**, for every
seat of every gate in the bidder list (`funding_layout`, `build_funding`). Each seat of each gate has its
own funding output, one per `(wallet, gate)`:

1. One common **fan-out** spends the first coinbase output (height 1, mature at tip `SETUP_BLOCKS`; a
   TEST_ONLY P2WSH(OP_TRUE) output). It pays every unflagged SYNTHETIC wallet and every competitor
   directly, one output (`FUNDING_VALUE` to the wallet's fee key) per gate the wallet bids in, and one
   P2WSH(OP_TRUE) output per owner that has an ancestry-flagged SYNTHETIC wallet anywhere in the run.
   The fan-out is the Regtest funding source: its txid is the ground truth's `excluded_txids`, outside
   the boundary.
2. Per such owner, **one owner funding transaction** (non-coinbase, inside the boundary) spends that
   output and pays each of the owner's ancestry-flagged wallets **one output per gate the wallet bids
   in** (DEFAULT: separate outputs, not one per-wallet output that later gates chain from; a chain would
   put the wallet's earlier REGISTER between the owner transaction and the later one).

The fan-out is mined first, then the owner funding transactions, both through the relay, both before the
first gate. A REGISTER in gate g spends its `(wallet, g)` output. So one owner transaction is the parent
of every REGISTER of that owner's flagged wallets in every gate of the run: when two of them win
different gates, the two winners share that ancestor inside the boundary, and the planted ANCESTRY link
reaches two winners (D2-2's P_L restricts planted groups to winners before closing them, section 12).
Funding per gate instead (one owner transaction per gate) could never do that, because each gate has
one winner. Every seat is funded from the one fan-out, so a run needs only one mature output.

**Funding bound** (`MAX_FUNDING_OUTPUTS` = 1,000; round 3). A bidder list with more than 1,000 seats over
all its gates is refused when it is read, before any node starts (`FUNDING_TOO_LARGE`, exit 2). 1,000 is
045b 4.6's item 1 run: 200 gates × 5 seats. The fee stays the fixed `FUNDING_FEE` (10,000 sat); the
bound, not a vsize-scaled fee, keeps the fan-out standard. The arithmetic: each seat is at most one
fan-out output, so the fan-out has at most 1,001 outputs (with the change), each 43 bytes (8 value, 1
length, a 34-byte P2TR or P2WSH script). Its stripped size is 4 (version) + 1 + 41 (the input) + 3 (the
output count) + 1,001 × 43 + 4 (locktime) = 43,096 bytes, and its witness (marker, flag, one stack item
`OP_TRUE`) is 5 bytes. So its weight is 43,096 × 4 + 5 = 172,389 WU (43,098 vB), under the 400,000 WU
standard limit with a factor of 2.3 to spare, and 10,000 sat over 43,098 vB is 232 sat/kvB, over the
100 sat/kvB default `minrelaytxfee` of Core 31.1 and 30.3 (`bitcoind -help-debug`) by the same factor.
An owner funding transaction has fewer outputs than the fan-out. Without the bound, at about 2,320
outputs the fan-out reaches 100,000 vB, so both the 400,000 WU standard weight and (at 10,000 sat) the
100 sat/kvB minimum relay fee, and the run would fail with a raw `sendrawtransaction` error after its
nodes started.

**Gates of a run.** The cell runs every gate of the bidder list in order: the first at H0, each next one
at the Core replay's next birth height (H0 + 144 after the gate's birth). The gate numbers are
consecutive in list order (section 11). Every block from H0 on is replayed (section 10, BIRTH) for the
canonical state a later gate's BUILD needs. A gate where bids exist and the Core replay of block G shows
no birth or more than one is refused (`GATE_BORN_COUNT`, exit 2), and so is a birth that is not one of
the gate's rung-0 txids (`GATE_BORN_UNKNOWN`, exit 2): D2-2 takes exactly one `winner_txid` per gate,
so such a gate is never written as a `BID` row (`gate_row`; round 3).

**Rung fees** (045b 4.6 `item 2 release schedule`). `p_0` is `b` + the `BID_FEE_j` value (n = 3b + 1).
The fees are:

- `f_0 = ceil(p_0 v / 1000)`;
- `r_k = ceil(p_0 3^k / 2^k)`;
- `j` is the seat index in the bidder list (section 11): seat j draws `BID_FEE_j`;
- `f_k = max(ceil(r_k v / 1000), f_(k−1) + max(1, ceil(i v / 1000)))`.

The ladder ends before the first rung with `f_k × 1000 > 4b × v`, or after rung 7. When that first
rung is rung 0, the ladder is **empty** (DEFAULT, PENDING_FREEZE for A and the freeze): the seat bids *Dated line 2026-11-10 (B, FZ-6, C27 pointer; sources 045b :1194's C27 dated line and A #664 issuecomment-6746599499): 045b :1140 (F11) froze `b` as a multiple of 250 sat/kvB, so that no ladder is empty at v = 213 vB (the alternative at :391-392).*
nothing in that gate, the raw log records `LADDER_EMPTY` for it, and the gate continues
(`gate_bids`: the per-seat draw, ladder and bid-or-LADDER_EMPTY step).

**A gate where every seat's ladder is empty** (DEFAULT for A, PENDING_FREEZE; round 3). Such a gate *Dated line 2026-11-10 (B, FZ-6, C27 pointer; sources 045b :1194's C27 dated line and A #664 issuecomment-6746599499): under 045b :1140 (F11) no ladder is empty, so a CONFIRMATORY run, whose `b` the driver checks before any node (`POLICY_B_NOT_MULTIPLE_OF_250`, section 18), never reaches this refusal; EXPLORATORY keeps it.*
would have no REGISTER and no winner, and D2-2's gate list has no encoding for it: `winner_txid` `null`
means unknown control, and under A's #616 -6541483273 R3 an unknown gate counts toward a run's length
and an unknown-only run is reported as UNKNOWN, so no-bid gates between same-cluster wins would lengthen
a run and four in a row would give a false report. Whether a ladder is empty depends only on rung 0, so
only on `BID_FEE_j` (seed, run, j, b), not on `i`; so it is known before any node starts. The cell
therefore refuses the run before any node starts, and before any output file exists, when some gate
has no seat with a non-empty ladder (`plan_gates`; `RUN_GATE_NO_BID_G<gate>`, exit 2, naming the
first such gate). One empty seat in a gate where another seat bids is not refused: that seat logs
`LADDER_EMPTY` and the gate runs. The in-run `GATE_NO_BID` check stays as a defence and is unreachable
from a plan that passed `plan_gates`: the raw log records `GATE_NO_BID` and the run is refused
(`GATE_NO_BID`, exit 2) before block G is mined; no ground-truth row is written for it. An empty ladder
happens only through rounding, when `b` is not a multiple of 250 at v = 213 and `p_0` is within a few
sat/kvB of 4b (b = 3,001: `p_0` ∈ 12,001-12,004). The alternative for the freeze is `b % 250 == 0`, which
makes an empty ladder, and so this refusal, impossible (*2026-11-10, B-FZ-p round 2: 045b F11 (on #664) took it; a [Dated line 2026-11-10 (B, FZ-6): the date 2026-11-10 of this B-FZ-p line is UTC 2026-11-09, A #759 issuecomment-6749449323, F3; F11 is 045b :1140 on main since #664.]
CONFIRMATORY policy whose run's `b` is not a multiple of 250 is refused before any node,
`POLICY_B_NOT_MULTIPLE_OF_250`, section 18*). `i` is the larger of Node A's and Node B's
`getnetworkinfo` `incrementalfee` (sat/kvB; Node A's alone before D3a-2b-1, section 24). `v` is `CANDIDATE_VSIZE` = 213 vB, the measured vsize of
the product REGISTER shape: one P2TR key-path input, then the carrier, Anchor and change outputs. Every
built rung is checked against it (`CANDIDATE_VSIZE`, exit 2).

With `p_0 ≤ 4b`, `r_4 ≥ 1.5^4 b > 4b`, so the cap ends every ladder by rung 3, and the rung-7 bound
does not bind. The product fixture's fee floor is 2,000 sat/kvB over its declared 1,200 WU, which is
600 sat. So a campaign's `b` must keep `f_0 ≥ 600` (`b ≥ 2,813` at v = 213; 2,812 gives 599). The D2-1 cell uses
b = 3,000 (DRAFT; the freeze sets `b`). *Dated line 2026-11-10 (B, FZ-6, C27 pointer; sources 045b :1194's C27 dated line and A #664 issuecomment-6746599499): the freeze set `b` = 6,000 for every experiment (045b :1901, section 14.21) and F11 (045b :1140).*

## 10. Worker lines

Request (ASCII, LF), one file per call:

    ARDR_BIDDERS_REQUEST_V1
    SEED <seed hex> <run> <H0>
    KEYS <set> <wallet> <anchor label>
    BUILD <set> <wallet> <gate> <tip height> <tip hash> <funding txid> <vout> <value> <funding height> <anchor label> <fee,fee,…> <canonical state hex | ->
    BIRTH <height> <block hex> <prestate hex | ->

Fields are tab-separated. Answer: `ARDR_BIDDERS_ANSWER_V1`, then for each request line:

- KEYS: `KEY <set> <wallet> <anchor label> <fee script> <anchor script>`;
- BUILD: one `RUNG <set> <wallet> <gate> <k> <fee> <txid> <vsize> <raw sha256> <ledger id> <candidate id> <lineage> <raw hex>` line per rung;
- BIRTH: `BIRTH <height> <born txids, comma-separated | -> <next birth> <poststate hex>`.

BIRTH is the pure Core replay (`bitagi_core::apply_block_transition`) of the exact block bytes on the
prestate. An empty prestate below H0 means next birth H0. A born Heart is an `AcceptedRegister`
event. Its txid is the REGISTER's.

## 11. Bidder list (`BITAGI_CT_ARDR_BIDDERS_V1`)

A JSON document that lists who bids in each contested gate. Its keys are a closed set:

    {"schema": "BITAGI_CT_ARDR_BIDDERS_V1",
     "gates": [{"gate": <int>, "seats": [{"seat": <str>, "kind": <kind>, "wallet": <id>, "path": <path>}]}]}

- `kind` is `SYNTHETIC` (wallet `W00`-`W39`), `COMPETITOR` (wallet `C00`-`C09`) or `L0_PROJECT`.
- `L0_PROJECT` is the project seat. It is refused with exit 3, `L0_PROJECT_SEAT_NOT_BUILT`, except in
  item 2's DRAFT L0 seat (section 22, D3a-1a: `parse_bidders(l0=True)`), where a gate may hold one
  `L0_PROJECT` seat, `PUBLIC`, wallet `L0` (`BIDDERS_L0_SEAT` otherwise).
- `path` is `PUBLIC` or `PRIVATE`.

A gate has 1-5 seats (`BIDDERS_GATE`): the 045b 4.6 draw table has `BID_FEE_0`-`BID_FEE_4`, and seat
j draws `BID_FEE_j`. It has at most one `PRIVATE` seat (`BIDDERS_TWO_PRIVATE`), and that seat is seat 0
(`BIDDERS_PRIVATE_NOT_FIRST`; 045b 4.6: bidder 0 is the private bidder when present). It has no repeated
seat or wallet (`BIDDERS_SEAT_DUPLICATE`), and no repeated gate (`BIDDERS_GATE_DUPLICATE`). The gate
numbers are consecutive in list order: `gates[k].gate == gates[0].gate + k`
(`BIDDERS_GATES_NOT_CONSECUTIVE`; the cell runs list order, and D2-2's gates input refuses
non-consecutive gates, `GATES_NOT_CONSECUTIVE`). The list holds at most 1,000 seats over all its gates
(`FUNDING_TOO_LARGE`, section 9). Other shape faults are exit 2. Every refusal is one JSON line, as in
section 8 (`check-bidders`), and is made when the list is read, before any node starts; `cell()` reads
a list it is handed again, so a list built in code is checked the same way.

The policy file's `bidders` key (section 3) is unchanged by D2-1. D2-3 decides whether the campaigns
carry the bidder list in it or bind the list's SHA-256 next to it.

Hand-off: a `PUBLIC` seat's rung goes to the relay node with `sendrawtransaction` (`PUBLIC_SENT`). A
`PRIVATE` seat's rung goes only to D1's miner process (`PRIVATE_HANDOFF`) and into the run's held
private set (section 2). A private rung is never given to `sendrawtransaction`. `PRIVATE_HANDOFF`
carries the seat's `kind` (`SYNTHETIC` or `COMPETITOR`). The `THIRD_PARTY` mark of A -6538196742 Q15 is
not a D2-1 mark: it marks third-party bundles fed to the miner, which is 1e-2b-2b's E7 re-feed.

## 12. Ground truth (`BITAGI_CT_ARDR_GROUND_TRUTH_V1`) and new raw-log events

The ground-truth file is written by D2-1 for D2-2's clustering tool. It is one JSON document with
sorted keys, ASCII, ending in exactly one LF, and is written only as a new file. Keys:

- `schema`, `labels`; *Dated line 2026-11-10 (B, FZ-6 fix round 1; 045b :1221, F13; A #258 issuecomment-6738933506; the name accepted by A #258 issuecomment-6757790020): the key-rule label in `labels` is `KEY_RULE_FROZEN_045B_F13` (was `KEY_RULE_DRAFT_PENDING_FREEZE`; `tools/claude_track_ardr_bidders.py:64`); a label change only, the key rule (section 9, :295) is unchanged.*
- `seed_sha256` (the seed itself is never written), `run`, `boundary`, `planted_owner`;
- `excluded_txids`: the common fan-out funding transactions that fund every wallet, for the clustering
  method's excluded set (besides the coinbase outputs); empty when there is none;
- `wallet_to_owner`: wallet → owner;
- `winners`: winning REGISTER txid → wallet, over every gate of the run;
- `gates`: one row per gate of the run, in order, with consecutive gate numbers: `gate` (the bidder
  list's number), `height`, `status` (always `BID`: a run with a gate without a bid is refused, section
  9) and `born` (exactly one REGISTER txid, the gate's winner; section 9, `GATE_BORN_COUNT`);
- `owners`: per owner, `wallets` and `base_wallet`;
- `wallets`: per wallet `owner`, `shares_ancestry`, `reuses_base_key`, the three draw values, `set`,
  `funding_txids` and `anchor_label_h0`. `funding_txids` maps each gate the wallet bids in (its number as
  a string) to the txid of that `(wallet, gate)` funding output; `{}` when the wallet does not bid;
- `competitors`: `set` `COMPETITOR`, `owner` `COMPETITOR_<c>` (each competitor is its own owner; no
  shared owner joins two competitors), `funding_txids` (as for `wallets`);
- `link_groups`: planted groups, each `{"kind": "ANCESTRY" | "ANCHOR_KEY", "owner", "wallets", …}`, each
  with at least two wallets of one owner. An ANCESTRY group is derived from the funding actually placed,
  not from the plan flags, over the whole run: the distinct wallets with a funding output, in any gate,
  of one shared transaction that is not in `excluded_txids`. It carries `funding_txids`, exactly one
  txid: that owner funding transaction, the parent of each member's funding outputs (section 9), and at
  least two distinct wallets. Only groups placed on chain are written; a shared
  funding txid across owners or over an unflagged wallet is refused (`GROUND_TRUTH_ANCESTRY`, exit 2).
  An ANCHOR_KEY group carries the `anchor_label` of the shared key. On chain it is the REGISTER's
  vout[1] P2TR program `0x51 0x20 <32>`;
- `links`: the same groups as pairs, `ancestry` and `anchor_key`.

An ANCHOR_KEY link is on chain only once both of its wallets' REGISTERs are; D2-3 records which links
are placed.

**Projection to D2-2's `BITAGI_CT_ARDR_CLUSTER_TRUTH_V1`.** D2-2's clustering tool
(`tools/claude_track_ardr_cluster.py`, `ARDR_CLUSTER_V1.md` section 6) reads a different shape. As it
stands at 36e1e62e (`claude/b-p5001-d2-cluster`, PR #616) it is:

<!-- CLUSTER_TRUTH_V1 shape at 36e1e62e -->

    {"schema": "BITAGI_CT_ARDR_CLUSTER_TRUTH_V1", "winners": {"<txid>": "<wallet>", ...}, "owners": {"<wallet>": "<owner>", ...}, "planted_links": [{"kind": "ANCESTRY", "wallets": ["<wallet>", ...]}, ...]}

The projection GROUND_TRUTH_V1 → CLUSTER_TRUTH_V1, field by field (`cluster_truth_projection` in the
tool):

| CLUSTER_TRUTH_V1 | From GROUND_TRUTH_V1 |
|---|---|
| `schema` | the constant `BITAGI_CT_ARDR_CLUSTER_TRUTH_V1` |
| `winners` | `winners` as is (winning REGISTER txid → wallet) |
| `owners` | wallet → owner: `wallet_to_owner` (the 40 synthetic wallets), plus each `competitors` key → its `owner` (`COMPETITOR_<c>`) |
| `planted_links` | one `{"kind", "wallets"}` per `link_groups` entry, in order (the `owner`, `funding_txids` and `anchor_label` fields are dropped) |

Note the name clash: GROUND_TRUTH_V1's `owners` is owner → wallets; CLUSTER_TRUTH_V1's `owners` is
wallet → owner (GROUND_TRUTH_V1's `wallet_to_owner`). The other GROUND_TRUTH_V1 fields have no
CLUSTER_TRUTH_V1 field; `excluded_txids` goes to D2-2's own input as `boundary.excluded_txids`. D2-1 does
not import D2-2 or write its file.

D2-2's P_L rule (at 36e1e62e, section 6, DEFAULT for A): each planted link group is **first restricted to
the winning wallets, then** the restricted groups are closed transitively. So a planted link counts only
when at least two of its wallets win. With the run-wide funding of section 9 an ANCESTRY group spans the
gates, and D2-1's unit cell `RunFunding` shows a planted ANCESTRY group whose two wallets win two gates
(the restricted group has 2 members, so P_L holds that pair). D2-3 adds the converter and a cross-tool
cell with at least 2 winners per planted link, so that `link_recall` and `link_precision` are 1, not 0/0.

New raw-log events (section 2 shape):

| `event` | Extra keys |
|---|---|
| `FUNDING_SENT` | `node`, `txid`, `hex`, `stage` (`FAN_OUT` or `OWNER`), `wallets` it pays, `outputs` (`[wallet, gate]` per output, in output order: `outputs[i]` is vout i of `txid`; the fan-out's owner outputs and each transaction's change output come after the listed ones and are not listed), their `kinds` (in the order of `outputs`); `wallets` is the sorted set of the listed wallets |
| `LADDER_EMPTY` | `seat`, `kind`, `feerate` (`p_0`): the seat bids nothing in this gate |
| `GATE_NO_BID` | `gate`, `seats`: every seat's ladder was empty; a defence only, unreachable from a plan that passed `plan_gates`, and the run is then refused (section 9) |
| `GENERATED` | `seat`, `ladder` (the fees), `rungs` (each rung without its hex) |
| `CORE_REPLAY` | `height`, `born`, `next_birth` |

`PUBLIC_SENT` and `PRIVATE_HANDOFF` also carry `seat` and `kind`. The setup blocks, `FUNDING_SENT` and
their blocks belong to the run (`unit.gate` `null`); every later line belongs to its gate.

## 13. Workflow, slices and collection (D4)

Status: D4 of the CT-P5-001 driver (A #258 issuecomment-6537782009 section 1, Q5, Q6, Q9, section 3 and
section 4 row D4; -6539879887 section 3). The workflow is `.github/workflows/claude-track-ardr.yml`, the
tool `tools/claude_track_ardr_slices.py`, its tests `tests/claude_track/test_ardr_workflow.py`. Class T
Regtest development evidence only. This section was added on 2026-10-31 in place of D1's slice-record
placeholder; sections 1-8 are unchanged.

**Unit.** A unit is `(experiment, run index)`, the `unit` of section 5 with `gate` and `cohort` `null`: the
driver runs, and the re-dispatch rule counts, one unit at a time. **U3 (2026-11-01, A #258 6549827052 and
#634 check 6551127840):** an ITEM1 or POOL unit holds `gates_per_run` observations, one per gate, with the
campaign's gate id `OBS-<e><run:07>-G<gate:03>` (section 16); any other unit is one observation with the
run id `OBS-<e><run:07>`. The cohort unit (D3) is not built.

**Run name.** The workflow's `run-name` is `ardr <mode> <experiment>` for a dispatch (`ardr PR smoke <ref>`
for a pull request); the server lists it as the run's `display_title`, and the re-dispatch check chooses the
earlier runs to read by it. A collect-only recovery dispatch (mode `RECOLLECT`, D4-2 below) is named
`ardr RECOLLECT <experiment> <recollect_run_id>`.

**Who dispatches.** Only A dispatches, from `main`, first attempt only (Q5; the VPS preparation section
3.6 rule). Inputs: `experiment`, `mode` (`CONFIRMATORY` or `EXPLORATORY`), `unit_first`, `unit_last` (at
most 400 observations, U3: units for a run-level experiment, units × `gates_per_run` for ITEM1 and POOL),
`units_per_slice`, `unit_minutes`, `policy` (a path in the dispatched commit), and for
CONFIRMATORY `registration`, `registration_sha256` (Q6) and `s04_run_id` (the run id of the cited
`claude-track-rx02` main push run; an EXPLORATORY dispatch ignores it and its declaration says so). Mode
`RECOLLECT` with `recollect_run_id` is the collect-only recovery (D4-2, "Collect-only recovery" below); it
reads none of the unit, policy or registration inputs and runs only its `recollect` job; the dispatch must still
fill the inputs the form requires (`unit_first`, `unit_last`, `units_per_slice`, `unit_minutes`, `policy`), which
it ignores (A check 6547983257). A pull request runs the PR smoke
instead: one unit, `ITEM2` run 0, driver mode `PR_SMOKE` (EXPLORATORY), the draft policy
`tests/claude_track/ardr_pr_smoke_policy_draft.json`, through the same `plan`, `slice` and `collect`
commands, plus the driver's and the campaign's RealNodes tests on the same Core 31.1 and 30.3 binaries
(none may skip; the campaign's ITEM1 cell runs the tree's own D2-2, never `BITAGI_ARDR_CLUSTER_TOOL`; D2-3a
round 2, P3-C). The PR-smoke and slice jobs set `CARGO_INCREMENTAL=0` job-wide, so every unit reuses the
worker build's artifacts (round 2, P3-B).

**Declaration (`BITAGI_CT_ARDR_DECLARATION_V2`, artifact `ardr-declaration`; V2 since U3).** Written by `plan`:
`experiment`, `mode`, `evidence_status`, `units` `{first, last}`, `units_per_slice`, `unit_minutes`,
`slices` (each `{slice, first, last}`, numbered from 1, consecutive), `policy_path`, `registration_path`,
`registration_sha256` (CONFIRMATORY only), `s04_run_id` (CONFIRMATORY: the input, digits; else `null`),
`s04_run_id_input` (`CITED`; EXPLORATORY: `IGNORED_EXPLORATORY` when one was given, else `NOT_GIVEN`), `run`
`{run_id, run_attempt, commit}`, `observations_per_unit` (ITEM1, POOL: the policy's
`experiments.<E>.params.gates_per_run`, 1 … 200, or the driver's DRAFT 200 / 4 for an EXPLORATORY policy
without params; else 1), `method_policy` (ITEM1: the policy's `experiments.ITEM1.method_policy`
`{path, sha256}`, section 18, required in CONFIRMATORY; else `null`), `labels`. The re-dispatch check still
reads an earlier run's V1 declaration (without the two U3 keys). **U3 refusals in plan:** more than 400
observations (units × `observations_per_unit`) is exit 6 `OBSERVATION_BUDGET`; a CONFIRMATORY ITEM1 or POOL
policy without params is exit 3 `POLICY_GATES_UNSET`, a PENDING `gates_per_run` exit 3 `POLICY_GATES_PENDING`,
one that is not 1 … 200 exit 2 `POLICY_GATES`; a CONFIRMATORY ITEM1 policy without `method_policy` is exit 3
`METHOD_POLICY_UNDECLARED`, a malformed one exit 2 `METHOD_POLICY_DECLARATION`; its `path` must be a file of
the dispatched commit (exit 3 `INPUT_PATH_NOT_IN_COMMIT`) whose SHA-256 is the declared one (exit 6
`METHOD_POLICY_SHA256`). `plan` refuses a slice that does not fit 330 minutes: 30 (setup) + `units_per_slice` ×
`unit_minutes` + 15 (upload) > 330 is exit 6 `SLICE_BUDGET`; a CONFIRMATORY dispatch without its three
inputs is exit 3; a CONFIRMATORY second attempt is exit 6 `RUN_ATTEMPT_NOT_FIRST`. The `policy` and
`registration` paths must be files of the dispatched commit (pre-PR round 2, D-2): a path that is empty,
absolute, holds `..`, or is not a blob at `git cat-file -t HEAD:<path>` (from the repository root, where the
workflow runs the tool) is exit 3 `INPUT_PATH_NOT_IN_COMMIT` in plan, so no slice starts on it. The
declaration is uploaded last (step `Upload the declaration`), after the re-dispatch check, so a dispatch
whose plan refused declares nothing; a later check reads that from the server's jobs listing, never from a
missing artifact (see "Re-dispatch rule").

**Slice record (`BITAGI_CT_ARDR_SLICE_V2` since U3 Part C, artifact `ardr-slice-<n>`, file `slice-record.json`).**

| Key | Value |
|---|---|
| `schema`, `mode`, `evidence_status`, `experiment`, `labels` | as the declaration (`mode` `PR_SMOKE` in the PR smoke) |
| `slice`, `job_name` | the slice number and its job name `ARDR slice <n>` |
| `slice_commit` | `git rev-parse HEAD` of the job's checkout, equal to the declaration's `run.commit` |
| `run` | the declaration's `run` |
| `policy_sha256` | SHA-256 of the policy file's exact bytes (each raw log's `policy_sha256` must equal it); `null` before the policy is read |
| `registration_sha256` | the declaration's (CONFIRMATORY), else `null` |
| `s04` | CONFIRMATORY: `{record_sha256, record_source, s04_run_id, s04_run_attempt, s04_head_sha, subjects}` (`record_source` `ARTIFACT` or `JOB_LOG`); else `null`; `null` before the citation is derived |
| `started_at` | `{"source": "GITHUB_JOB_STARTED_AT", "utc"}`: the slice job's `started_at` from the Actions jobs listing of this run attempt (Q9); `LOCAL_EXPLORATORY` only for a slice without it, never CONFIRMATORY; `null` before it is read |
| `units` | one entry per unit of the slice, in order: `unit`, `state`, `code`, `exit` (the driver's exit code, 4 for a unit killed at its limit, `null` before its driver ran; U3 Part C), `raw_log`, `raw_log_sha256` |

**Begin record.** The slice job's first tool step (`slice-begin`, right after the declaration download)
writes the record with every unit `BEFORE_START`, `code` `null`, and `policy_sha256`, `s04` and `started_at`
`null`, before the token step, the Core fetch and the S04 download. A failure of any of those leaves that
record (the units step is skipped; the record is uploaded always), so the units stay re-dispatchable; if the
started-at GET itself fails, the record is exactly that begin record. `slice` then requires the begin record
and reads the policy, the job's `started_at` from the saved jobs listing and, CONFIRMATORY, the S04 citation;
a refusal of any of them rewrites the record with every unit `BEFORE_START` and that refusal's `code` (for
example `POLICY_UNAVAILABLE`, `JOBS_UNAVAILABLE` or `S04_CITATION_UNAVAILABLE`, exit 3;
`S04_CITATION_RUN`, exit 6) and starts no
driver. U3, in the same place and before the policy: a `--work-root` that is not absolute is exit 2
`WORK_ROOT_NOT_ABSOLUTE` (checked before it is made); after the policy, its ITEM1 or POOL entry must still
give the declared `observations_per_unit` (exit 6 `OBSERVATIONS_PER_UNIT_CHANGED`) and `method_policy`, and the
method policy file at that path must still have the declared SHA-256 (exit 6 `METHOD_POLICY_CHANGED`; exit 3
`METHOD_POLICY_UNAVAILABLE` when it cannot be read). Each unit's driver then gets `--method-policy <path>`. A
git call that does not answer in time (`commit_file`, `git`, the S04 subject check) is exit 3 `GIT_TIMEOUT`. `slice-begin` refuses a checkout of another commit (`SLICE_COMMIT`, exit 6) without writing a record.
A record whose units are all `BEFORE_START` may hold the three `null`s; one with a started unit holds all
three.

Unit states: `BEFORE_START` (no observation: the driver was not started, or it refused before writing
`RUN_START`); `IN_PROGRESS` (written before the driver starts); `OBSERVED` (the raw log runs `RUN_START` …
`RUN_END` `DONE` and the driver ended 0); `EXCLUDED` (`RUN_START` was written and the unit did not end so,
including a unit killed at `unit_minutes`, `UNIT_TIMEOUT`). A raw log cut by that kill (`UNIT_TIMEOUT` with a
line that does not parse), or one whose first line parses and whose last line does not, is `EXCLUDED`
`RAW_LOG_TRUNCATED`, and the slice goes on with the next unit; a first line that does not parse without the
kill stays a refusal (exit 2 `RAW_LOG_JSON`). The record is rewritten whole after each change.
The driver runs in its own process group per unit and the group is killed at the unit's limit. A driver
refusal before `RUN_START` (for example `CONFIRMATORY_CAMPAIGN_NOT_BUILT` until D2-3/D3a, or a reserved
miner policy) leaves that unit and every later one `BEFORE_START` and ends the slice with the driver's
code. A unit that would not finish inside the slice's budget is not started (`BEFORE_START`).

**S04 citation (A section 1), derived from the server (2026-10-31 follow-up).** Every CONFIRMATORY slice
record cites the S04 `PASS_CLASS_T` record of a main push whose `subject_oids` match at the slice commit. The
plan job derives it; no committed copy is read. In its one GET-only token step it saves, for the `s04_run_id`
input: the run (`GET repos/{repo}/actions/runs/{id}`, `run.json`), checked before the next request; the
artifact listing by the exact name `s04-record-v2-<id>-<run_attempt>` (`artifacts.json`); then either that
artifact's zip (`record.zip`) or, when the artifact is not listed or is expired, the run attempt's jobs
listing (`jobs.json`) and the log of the job named `S04 record v2 (leg set s04-legs-v1, this run only)`
(`job.log`). `s04-cite` then derives the citation from these files and writes `citation.json`; the files and
the citation are uploaded as artifact `ardr-s04`. Each CONFIRMATORY slice downloads `ardr-s04` and carries
its `citation.json` (pre-PR round 1): it checks only the shape (exit 2 `S04_CITATION_SHAPE`) and that its
`s04_run_id` is the declaration's (exit 6 `S04_CITATION_RUN`); it derives nothing (no git, no API; its
checkout is shallow), so every refusal below happens in plan, before any slice job starts. The tool itself makes no network call. Refusals, all exit 6 unless stated:

- the run: its `id` is not the input (`S04_RUN_ID`); its `path` (not its display name) is not
  `.github/workflows/claude-track-rx02.yml` (`S04_RUN_WORKFLOW`); `event` not `push` (`S04_RUN_EVENT`);
  `head_branch` not `main` (`S04_RUN_BRANCH`); not `completed` with conclusion `success`
  (`S04_RUN_NOT_SUCCESS`); no `run_attempt` (`S04_RUN_ATTEMPT`); `head_sha` not in
  `git rev-list --first-parent <slice commit>` (`S04_NOT_ON_SLICE_HISTORY`: ancestor or equal on the first
  parent line; a later head, or one reached only through a merge's second parent, is refused);
- the source. The artifact wins: when it is listed once and not expired, its zip is the record and the log
  is not read; a zip that is not exactly one member `s04_record_v2.json` within 1 MiB is
  `S04_ARTIFACT_ZIP`, more than one listed artifact `S04_ARTIFACT_LISTING`, a listed artifact whose zip is
  absent exit 3 `S04_RECORD_MISSING` (never a fallback). Otherwise the record job's log (at most 16 MiB) must
  hold exactly one timestamped line that is a JSON object with the record's `schema`
  (`S04_JOB_LOG_AMBIGUOUS` for more than one), and the next line must be the `sha256sum` line of
  `.../s04_record_v2.json` whose digest equals SHA-256 of that line's text plus `\n` (the job prints the
  one-line record with `cat` and then its digest); else exit 3 `S04_RECORD_MISSING`. A record job not in
  the listing is `S04_JOB_NOT_LISTED`;
- the record: `schema` not `bitagi.claude_track.s04_record.v2` (`S04_RECORD_SCHEMA`); `s04` not
  `PASS_CLASS_T` (`S04_NOT_PASS`); its `commit` not the run's `head_sha` (`S04_RECORD_COMMIT`); its `run`
  not `{event push, ref refs/heads/main, run_id, run_attempt, commit}` of that run (`S04_RECORD_RUN`); any
  `subject_oids` entry not equal to `git rev-parse <slice commit>:<path>` (`S04_SUBJECTS_CHANGED`: a new main
  push's PASS is needed before the next slice). Only object ids are compared; no subject's bytes are read.

The collector also refuses a CONFIRMATORY slice record whose `s04.s04_run_id` is not the declaration's
(exit 6 `SLICE_RECORD_S04`). The record job's log is kept by GitHub for the repository's log retention (90
days by default), as are the artifacts; a citation whose sources are both gone is exit 3.

**Collection (`BITAGI_CT_ARDR_COLLECTION_V1`, artifact `ardr-collection`, file `collection.json`).** The
collect job reads only this run's declaration, this run's slice artifacts and the jobs listing of this run
attempt read from the Actions API in the same job; nothing comes from a caller. Per slice: a record whose
`run`, `slice`, `job_name`, `experiment`, `slice_commit` or unit list differs from the declaration is
refused (exit 6); a CONFIRMATORY record whose `started_at` is not the listing's `started_at` for its job is
refused (exit 6 `STARTED_AT_NOT_SERVER`; checked when a unit of the record started). Each started unit's raw
log must be in the slice artifact as `raw-<run>.jsonl` (else exit 3 `RAW_LOG_MISSING`) with the recorded
SHA-256 (else exit 6 `RAW_LOG_SHA256`; the log is read whole once, at most 256 MiB, else exit 2 `RAW_LOG_SIZE`,
checked before the first byte and while reading), an `OBSERVED` unit's log must run `RUN_START` (seq 1, this unit) ..
`RUN_END` `DONE` (else exit 6 `RAW_LOG_NOT_DONE`), and a `BEFORE_START` unit has no log (exit 6
`SLICE_RECORD_RAW_LOG`). A declared slice without a record is `BEFORE_START` when its job never started
(`SLICE_NOT_STARTED`: not listed, no `started_at`, or, pre-PR round 2, a `started_at` with no step that ran;
a hosted job queued and then cancelled can list a `started_at` and an empty step list. A step ran unless it
is `queued`, `pending`, `waiting` or `completed` `skipped`; a cancelled or unknown step counts as ran) or when the jobs listing shows its step `Run the slice's units` `completed` and
`skipped` (`SLICE_UNITS_NOT_RUN`: a step before it failed, so no unit started), and `EXCLUDED`
(`SLICE_RECORD_MISSING`) for every unit otherwise (the job was lost after its units step began, before its
upload): the units may have been observed. A unit left `IN_PROGRESS` is `EXCLUDED` (`RUN_INTERRUPTED`). The
collect job refuses any attempt but the first, like plan and slice: recovery after a failed attempt-1 collect
is a new `RECOLLECT` dispatch of that run (D4-2, "Collect-only recovery" below). Until one has recollected it,
that run's declaration without a collection makes the re-dispatch check refuse every later CONFIRMATORY
dispatch of the experiment (exit 3 `PRIOR_COLLECTION_MISSING`, fail closed). Each unit entry: `unit`, `slice`, `state`, `code`, `started_at`,
`slice_record_sha256`, `observation_id` (a run-level experiment's), `gates` (U3; `null` for a run-level
experiment or a `BEFORE_START` unit, else one `{gate, state, code, observation_id}` per declared gate), `exit`
(the slice record's) and `gate_counts` (U3 Part C; `null` where `gates` is: `{gates, observed, excluded,
missing, missing_or_excluded, over_10_percent, cause, failed_gate, cluster_prefix, cluster_prefix_reason,
prefix, deadline_reached}`, below). The collect step's summary adds `ten_percent_rule` `{gates,
missing_or_excluded, over_10_percent}` over every gate of a started unit, and `exit_5` `{units, codes}`: the
units whose driver ended exit 5, counted by code apart from the other EXCLUDED units (A #638 check 6552915714
For-A 3; whether the slice should stop on them stays A's call, and the slice still goes on). The
schema is `BITAGI_CT_ARDR_COLLECTION_V2` (U3); the re-dispatch check reads V1 and V2. The record says
`observation_completeness` `WORKFLOW_DERIVED_NOT_AUTHENTICATED_LOG`.

**Gate states (U3, ITEM1 and POOL, from the whole raw log).** A unit with no log read (`IN_PROGRESS`, a lost
slice) or whose first line was cut has every gate `EXCLUDED` with the unit's code. Otherwise `RUN_START`'s
`gates` must be `0 … observations_per_unit − 1`, and every `GATE_START` and `GATE_END` line must carry its
gate's `unit` and `observation_id`, start in gate order once, and end once with `status` `OBSERVED` after its
start (else exit 6 `RAW_LOG_GATES`); a line before the last that does not parse is exit 2 `RAW_LOG_JSON`. An
`OBSERVED` unit needs every gate's `GATE_END` and has every gate `OBSERVED`. In an `EXCLUDED` unit a gate that
started, or may have started (the gate after the last `GATE_START` when the last line was cut), is `EXCLUDED`,
and any other gate `NOT_STARTED` (A Q2: missing), with `RUN_END FAILED`'s `code` (else the unit's); that
line's `excluded_gates` must hold every gate without `GATE_END`. U3 Part C reads U2's lines in the same
single pass, by event (the `PREFIX_START` lines, each `CLUSTER_TOOL` line's `prefix`, `gates`, `exit` and
`output_bytes` only, and per pool `GATE_END` whether its inputs rebuild from the lines before it), never the
whole log in memory:

- **Log shape** (U3 pre-PR P3-1). `seq` must run 1, 2, … over the lines with no gap or repeat, and no line may
  follow the first `RUN_END` (a second `RUN_END` included); else exit 6 `RAW_LOG_GATES`. The driver writes
  `RUN_END` last, so a line after it is never a kill's leftover. *(2026-11-26: except item 2's and item 4's cleanup: when the run is already failing and the L0 seat's stop then fails, it writes `L0_STOP_FAILED` after `RUN_END` (section 20's row of that event; section 22, "Cleanup"), and the judge takes that one line after `RUN_END` `FAILED` or `EXCLUDED` (ARDR_JUDGE_V1 section 4); the ITEM1 and POOL logs this bullet reads have no L0 seat)* A pool `GATE_END` (one with
  `producer_tags`) must carry an integer `seq` and a string `block_hash`, and a pool `BLOCK` (one with
  `producer`) a string `block_hash`, since the single pass keys on them; else exit 6 `RAW_LOG_GATES` (#713),
  in `slice` and `collect` alike. This is wider than an unhashable value: a `block_hash` of `null` or `7`, or
  a `seq` of `"1"`, `true` or `null`, once passed (that gate was only not rebuilt) and now refuses the whole
  command. That is fail-closed; the driver writes no such line.
- **Death cause.** `RUN_END FAILED`'s `code` and `failed_gate`; with no `RUN_END`, the last `PREFIX_START`'s
  (a unit killed during the prefix, section 16); else none, and the gates carry the unit's code
  (`RAW_LOG_TRUNCATED`, `UNIT_TIMEOUT`, ...). Never the slice record's code when the log names one (in the
  two prefix exit-5 cases the driver's FAIL code is the prefix's reason, not the first failure).
- **Prefix outcome.** `RUN_END FAILED`'s `cluster_prefix` and `cluster_prefix_reason` must be a row of
  section 16's reason table (`OK` with `null`; `NOT_RUN` with one of its reasons; `FAILED` with a code word),
  else exit 6 `RAW_LOG_GATES`.
- **ITEM1** (A Q2). The gates that reached `GATE_END` are `OBSERVED` (`PREFIX`) only when `RUN_END FAILED`
  is phase `GATES` with `cluster_prefix` `OK`, `cluster_failed` false and `failed_gate` g (null when every
  gate reached it), and the log holds one `PREFIX_START` and, after it, one `CLUSTER_TOOL` with `prefix` true,
  `exit` 0 and output bytes, both naming exactly the gates 0 … g − 1. Otherwise (no `RUN_END`, a prefix
  `FAILED` or `NOT_RUN` for any reason, `SECRET_IN_LOG` and `LOG_BOUND` included, or any condition missing)
  every gate that started is `EXCLUDED` with the death cause. The gates that never started stay
  `NOT_STARTED` (missing); for A Q2's 10% rule missing and `EXCLUDED` add up, so the result is the same as
  excluding them, and the list stays one entry per gate that started (B default).
- **POOL** (A Q6, section 16). A gate with `GATE_END` that `excluded_gates` does not list is `OBSERVED`
  (`REBUILT_FROM_LOG`) when its judgement inputs rebuild from the lines before its `GATE_END`: exactly one
  `BLOCK` line with the `GATE_END`'s `block_hash`, whose coinbase producer tags read from its `block_hex` (the
  campaign's `coinbase_producers`) equal the `GATE_END`'s `producer_tags` (an untagged block, `[]`, is
  missing data and still rebuilds), at the `GATE_END`'s `height` and named by no earlier `GATE_END` of the
  run (P3-2: block G belongs to this gate), and exactly one `DRAW` `PRODUCER_H<height>` line for that height
  with the `BLOCK`'s `producer`. Else it is `EXCLUDED`. A truncated log (its last line cut) so counts to its last
  whole `GATE_END`; a gate whose `GATE_END` is the cut line is `EXCLUDED`.
- **Deadline** (A Q5, section 18; pre-PR P3-3). `RUN_START`'s `deadline` must be the driver's for the
  declaration's unit limit (`unit_seconds` = `unit_minutes` × 60, `d2_2_share_seconds` 5,700,
  `margin_seconds` 900, `gate_loop_seconds` the rest, an integer `clock_ns`), and non-null in a CONFIRMATORY
  ITEM1 or POOL run; with a deadline every `GATE_START` is stamped (`t_ns`, the campaign's own clock reading
  for the check) before `clock_ns`. Else exit 6 `RAW_LOG_GATES`.
- **Deadline stop** (A Q5, section 18). An `OBSERVED` unit whose `RUN_END DONE` has `deadline_reached` true
  has its gates 0 … k − 1 `OBSERVED` and the gates in `gates_not_started` (exactly k … end, no line of theirs,
  k ≥ 1, `RUN_START` with a `deadline`, and the line right after the last `GATE_END` stamped at or after
  `clock_ns`: the stop is proved from the log, P3-3) `NOT_STARTED` `DEADLINE_REACHED`; any other shape is
  exit 6 `RAW_LOG_GATES`. Without those fields (or `false` and `[]`) every gate needs its `GATE_END`. A unit
  the slice killed in teardown after `RUN_END DONE` (`UNIT_TIMEOUT`; P3-5) stays `EXCLUDED` with that code;
  its deadline facts are still read and checked the same way, so the gates it never started say
  `DEADLINE_REACHED`.
- **Counts** (A Q2). Each ITEM1 or POOL unit's `gate_counts`: `observed`, `excluded`, `missing`
  (`NOT_STARTED`), `missing_or_excluded` and `over_10_percent` (more than a tenth of the run's gates: 20 of
  200), the death cause and g, the prefix outcome, `prefix` (gates counted from a failed run's prefix D2-2),
  and `deadline_reached`. The collection reports these; the judge makes the NOT_ESTABLISHED call.
  `ten_percent_rule` and `over_10_percent` count only the gates of the units started in this collection
  (its `BEFORE_START` units and other dispatches are not in it): they are not the experiment's 10%
  judgement, which the judge makes over the whole registered N (045b 4.6 counts runs; A #641 check P3-4).

**Observation list (`BITAGI_CT_OBSERVATION_LIST_V2`, artifact `ardr-observations`; V2 since U3).** Written
only for a CONFIRMATORY collection with at least one observation, exactly in the shape
`tools/ct_preregistration_receipt.py` parses: `{"schema", "observations"}`, each observation
`{"observation_id", "registration_sha256", "start_time_utc"}`, one id form per list. For ITEM1 and POOL one
entry per gate that is `OBSERVED` or `EXCLUDED` (it started or may have started; `NOT_STARTED` gates are not
listed), with the gate id `OBS-<e><run:07>-G<gate:03>`; for any other experiment one entry per unit that is
not `BEFORE_START`, with the run id `OBS-` followed by the experiment's position in section 3's list (1-8)
and the run index in seven digits, so one unit or gate has one id in every dispatch of a registration. The
longest entry is 157 bytes (a gate id and a 12-digit start time) plus a comma, so 400 entries are at most
63,260 bytes. `start_time_utc` is the slice job's server `started_at` in whole
seconds since the epoch: it is not later than the unit's own start, so the receipt's "strictly earlier
than the first observation" (045b 3.2) is compared with a time no later than the observation. EXPLORATORY
and PR_SMOKE units are never observations. A list over the receipt tool's 64 KiB input bound is refused
(exit 2 `OBSERVATIONS_OVERSIZED`) before anything is written: no collection either.

**Re-dispatch rule (A section 3).** A unit is dispatched once. An EXPLORATORY dispatch reads no earlier
run. For a CONFIRMATORY dispatch, `plan` lists this workflow's dispatch runs on `main` (filtered
`event=workflow_dispatch&branch=main`; GitHub's list-workflow-runs returns at most 1,000 runs when a filter
is used, so every page of 100 is read, at most 10 pages, and a `total_count` of 1,000 or more is exit 3
`RUNS_LISTING_CAPPED`, so the oldest runs are never dropped silently; pages that disagree on the total, a
short page or a run listed twice is exit 3 `RUNS_LISTING_CHANGED`: dispatch again). A run on another branch is skipped (its plan refuses
at its first step); a run of another workflow path, or whose `display_title` is not
`ardr CONFIRMATORY|EXPLORATORY <experiment>` or `ardr RECOLLECT <experiment>[ <run id>]`, is exit 3
(`RUNS_LISTING`, `RUNS_TITLE`). Only the runs titled `ardr CONFIRMATORY <this experiment>` are read (and the
`RECOLLECT` runs of this experiment, below). **Order (D4-2, Desktop r4431587744).** GitHub's concurrency group
does not promise that dispatches run in `run_number` order, so the number alone never hides a finished run. A
listed run is skipped only when it is the current run (by its id, whatever number the listing gives it) or
when it is NEWER (`run_number` above the current run's, `--current-run-number "$GITHUB_RUN_NUMBER"`) AND not
`completed`: such a run is one the group holds pending behind the current run and holds no observation yet;
refusing it would abort the current plan whenever the next dispatch is submitted (#619 review). Every
`completed` run, whatever its number, is read exactly as a preceding run (declaration, D-1, collection or
recollection, `REDISPATCH_OBSERVED_UNIT`): a newer dispatch the group admitted first and that completed may
have observed a unit. Any other chosen run that is not `completed` (an older one, or a synthetic one with the
current number and another id) is refused (exit 3 `PRIOR_RUN_IN_PROGRESS`). `run_number` counts up by one for
each run of this workflow and is kept across re-run attempts (a CONFIRMATORY plan refuses any attempt but the
first, so the current run is always attempt 1); `created_at` (one-second resolution) and `id` (not documented
as ordered) are not used. Every listed run, whatever its title or branch, carries a positive JSON integer
`run_number`, else exit 3 `RUNS_LISTING`. Runs of other experiments and EXPLORATORY runs are neither read nor
waited for.
Two CONFIRMATORY dispatches of one experiment never run at once (pre-PR round 2, P3-f): they share the
workflow's concurrency group `claude-track-ardr-confirmatory-<experiment>` with `cancel-in-progress` false,
so the later one starts only after the earlier one completed and its plan reads the earlier one's
collection; the in-progress refusal stays as a second guard. An EXPLORATORY dispatch keeps its own group
(`claude-track-ardr-<run id>`) and a pull request its ref's cancellable group (CR-22). GitHub keeps at most
one run waiting in a group: a third CONFIRMATORY dispatch of the experiment while one runs and one waits
cancels the waiting one before any of its jobs runs; that run declared nothing (below) and A dispatches its
units again. For each chosen run, `plan` reads its `ardr-declaration` and `ardr-collection` artifacts and its
attempt-1 jobs listing. **DEFAULT (B, D-1, for A to confirm):** a run without a declaration dispatched nothing,
and is skipped, when that listing shows its plan job `ARDR dispatch plan (main only, slice budget, re-dispatch
rule)` not listed or `completed` without success, AND every `ARDR slice <n>` job not listed or with no step
that ran (as in "Collection"), AND the run has no collection. Units are observed only inside slice jobs, and a
slice job needs a successful plan, so this holds whatever the plan's `Upload the declaration` step shows
(failed, cancelled or skipped) and for a run the concurrency group cancelled before it started (an empty
listing). Otherwise, including a run where any slice job ran a step, it is exit 3
`PRIOR_DECLARATION_MISSING` (fail closed). A declaration
that is not CONFIRMATORY of this experiment is exit 6 `PRIOR_DECLARATION_TITLE`. A planned unit is refused
(exit 6 `REDISPATCH_OBSERVED_UNIT`) when any earlier CONFIRMATORY dispatch of the same experiment holds it in
a state other than `BEFORE_START`, whatever that dispatch's `registration_sha256` (A section 3 names no
registration scope, and the observation id is the same under every registration); such a unit ends PASS,
FAIL or excluded, and an exclusion counts toward the 10 % rule (045b 4.6). An earlier CONFIRMATORY dispatch
with a declaration and no collection uses its recollection instead (below); without one it is exit 3
`PRIOR_COLLECTION_MISSING`, as is an expired artifact (`PRIOR_ARTIFACT_EXPIRED`; fail closed: the units may
have been observed).

**Collect-only recovery (D4-2, A #619 issuecomment-6542865820; mode `RECOLLECT`).** A CONFIRMATORY run `O`
whose attempt-1 collect job failed is recovered by a new dispatch from `main` with `mode` `RECOLLECT`, the
same `experiment` and `recollect_run_id` `O`. It shares the experiment's CONFIRMATORY concurrency group
(`claude-track-ardr-confirmatory-<experiment>`, `cancel-in-progress` false), so it never overlaps a
CONFIRMATORY run of the experiment; its plan and slice jobs (and so collect) do not run. A group holds at most
one pending run and a newer pending run cancels it, so a pending RECOLLECT and a pending CONFIRMATORY dispatch
of one experiment cancel each other: dispatch RECOLLECT only when nothing of the experiment is queued (B pre-PR
review, P3-3). Operating rule (A check 6547983257; availability only): (1) dispatch RECOLLECT; (2) when it
completes, check that `ardr-recollection` was uploaded; (3) dispatch the next CONFIRMATORY of the experiment from
a `main` at or after that RECOLLECT run's commit. A recollection made on a `main` commit newer than a plan's
dispatched commit is not on that commit's first-parent history and is refused exit 6
`PRIOR_RECOLLECTION_NOT_ON_HISTORY` (below); that is not a forgery, and the remedy is to dispatch again from
current `main`. An original run `O` that uploaded `ardr-observations` but no `ardr-collection` can also be
recollected; the recollected observations keep the same ids and add none. Its `recollect` job
refuses any ref but `main` and any attempt but the first, checks the input (digits, exit 2
`RECOLLECT_RUN_ID_INPUT`) before its token step, and then, in its one GET-only token step, saves `O`'s run
(`GET repos/{repo}/actions/runs/{O}`), checked before the next request: `id` the input (`RECOLLECT_RUN_ID`),
`path` this workflow (`RECOLLECT_RUN_WORKFLOW`), `event` `workflow_dispatch` (`RECOLLECT_RUN_EVENT`),
`head_branch` `main` (`RECOLLECT_RUN_BRANCH`), `display_title` exactly `ardr CONFIRMATORY <experiment>`
(`RECOLLECT_RUN_TITLE`), all exit 6, and `status` `completed` (exit 3 `RECOLLECT_RUN_NOT_COMPLETED`). It then
saves `O`'s attempt-1 jobs listing, `O`'s artifact listing (`.../runs/{O}/artifacts?per_page=100`), the
`ardr-declaration` zip and the zip of each declared slice's `ardr-slice-<n>` that the listing holds. The
listing must hold at most 100 items, its total, each name once, and every item's `workflow_run.id` must be `O`
(exit 6 `RECOLLECT_ARTIFACT_LISTING`, `RECOLLECT_ARTIFACT_RUN`: only that run's own artifacts); it may hold only
the names a D4 dispatch uploads (`ardr-declaration`, `ardr-s04`, `ardr-collection`, `ardr-observations`,
`ardr-slice-<n>` with n 1-999), any other name is exit 6 `RECOLLECT_ARTIFACT_LISTING`. The jobs read are always
attempt 1's, whatever `run_attempt` `run.json` shows. A listed
`ardr-collection`, expired or not, means there is nothing to recover (exit 6 `RECOLLECT_COLLECTION_EXISTS`);
no listed declaration or its zip absent is exit 3 `RECOLLECT_DECLARATION_MISSING`; an expired declaration or
slice artifact is exit 3 `RECOLLECT_ARTIFACT_EXPIRED`; a listed slice whose zip is absent is exit 3
`RECOLLECT_SLICE_MISSING`. Before the declaration is read, `recollect` requires `O`'s `head_sha` to be a commit
id on the first-parent history of the RECOLLECT dispatch commit (`github.sha`; `git rev-list --first-parent`,
the recollect job checks out full history; exit 6 `RECOLLECT_RUN_NOT_ON_HISTORY`, W653q, finding #654):
`head_branch` `main`
alone does not prove that `O` ran `main`'s workflow, since a dispatch on a tag named `main` lists the same way
and may run a changed workflow without the `refs/heads/main` checks. As for `PRIOR_RECOLLECTION_NOT_ON_HISTORY`,
this binds `O` to `main` only while `main` takes changes by merge commit or squash merge alone: a fast-forward
push or a rebase merge (GitHub's rebase merge, which main's ruleset 24579265 allows today beside merge and
squash, adds each rewritten commit to main's first-parent line) puts commits `main` never pointed at on its
first-parent history, so a tag `main` on one of them would pass; a tag ruleset refusing `refs/tags/main`, or a
`main` ruleset allowing merge and squash only (repository settings, the Founder's), closes that gap. The earlier
GET-only steps may still save that run's files onto the runner; the failed `recollect` step fails the job, so
the upload steps (no `if:`) are skipped and nothing is uploaded. The
declaration must be CONFIRMATORY (`RECOLLECT_NOT_CONFIRMATORY`), of the
input experiment (`RECOLLECT_EXPERIMENT`), and name run `O`, attempt `1` and `O`'s `head_sha`
(`RECOLLECT_DECLARATION_RUN`), all exit 6. A slice zip may hold only `slice-record.json` and `raw-<run>.jsonl`
of that slice's runs, each within its bound (1 MiB, 256 MiB; the zip within 1 GiB), else exit 6
`RECOLLECT_SLICE_ZIP`; a member `slice-record.json.tmp` (a slice job killed between the open and the rename of
its record, kept by the `always()` upload) is skipped and not extracted, as collect never reads it. `recollect` then lays the zips out as the collect job's download would and derives the
collection with the same function `collect` uses, from `O`'s declaration, those slice records and raw logs and
`O`'s attempt-1 jobs listing: every check of "Collection" applies unchanged (raw-log SHA-256 `RAW_LOG_SHA256`,
`RAW_LOG_NOT_DONE`, `STARTED_AT_NOT_SERVER`, the record-to-run checks), and a slice whose artifact is not
listed is a missing slice record (`EXCLUDED` `SLICE_RECORD_MISSING` unless the server shows its job or units
step never ran). So a recollection is exactly what `O`'s collect job would have written from the same
artifacts; it adds no observation (no unit becomes `OBSERVED` that its slice record does not hold as
`OBSERVED`) and no new run id (the collection's `run` is `O`'s). It is uploaded as artifact
`ardr-recollection`, one member `recollection.json` (`BITAGI_CT_ARDR_RECOLLECTION_V1`): `schema`,
`recollected` `true`, `recollected_from` `{run_id O, run_attempt "1"}`, `recollect_run` `{run_id, run_attempt,
commit, tool_sha256}` of the RECOLLECT run (`tool_sha256`: SHA-256 of the recollecting tool file; the rules
applied are that commit's, not `O`'s), `collection` (the collection object), `collection_sha256` (SHA-256 of the
collection as `collect` writes it), `slice_artifacts` (`[{slice, artifact_id}]`), `labels`; and, when the
collection holds a CONFIRMATORY observation, the observation list as `collect` would write it as artifact
`ardr-recollected-observations` (the list keeps exactly the receipt tool's keys `schema` and `observations`,
so it names no run; the artifact's name and the recollection beside it say it is recollected). A refused recollection uploads nothing. In a later CONFIRMATORY plan,
every `RECOLLECT` run titled `ardr RECOLLECT <this experiment> <O>` with a digit `O` that the same order rule
does not skip (the current run, a newer unfinished dispatch, another branch) must be `completed` (exit 3
`PRIOR_RUN_IN_PROGRESS`) and list a commit-id `head_sha` (exit 3 `RUNS_LISTING`), whatever its `O`; only after
that are the runs whose `O` is a chosen run kept (a title whose run id is not digits recollected nothing and is
skipped). So an unfinished RECOLLECT run of this experiment for any target, chosen or not, stops the plan
(exit 3, availability only; A check 6547983257 P3-2). The plan saves each kept
one's `ardr-recollection` (an expired one is exit 3 `PRIOR_ARTIFACT_EXPIRED`). A chosen run with a declaration
and no collection uses its recollection in place of the collection, with the same unit checks
(`PRIOR_COLLECTION_SHAPE`, `PRIOR_COLLECTION_UNITS`, `REDISPATCH_OBSERVED_UNIT`); the recollection must hold
`recollected` `true`, its keys and a matching digest (exit 6 `PRIOR_RECOLLECTION_SHAPE`), name the RECOLLECT
run it came from and `O` (exit 6 `PRIOR_RECOLLECTION_RUN`), and two recollections of one run must agree (exit 6
`PRIOR_RECOLLECTION_CONFLICT`). `PRIOR_RECOLLECTION_SHAPE` also covers `recollected_from.run_attempt` or
`recollect_run.run_attempt` other than `"1"` (`recollect_run.tool_sha256` is informational and not checked), `labels` other than the tool's, and a `slice_artifacts` item that is not `{slice, artifact_id}` with an
integer slice and a digit-string id. A listed `head_branch` `main` does not prove the run ran `main`'s workflow (a
dispatch on a tag named `main` lists the same way and may run a changed workflow; B pre-PR review, P2-1), so a
RECOLLECT run's listed `head_sha` must be a commit id (exit 3 `RUNS_LISTING`), its recollection's
`recollect_run.commit` must equal that `head_sha` (exit 6 `PRIOR_RECOLLECTION_COMMIT`) and be on the
dispatched commit's first-parent history (`git rev-list --first-parent`, the plan job has full history; exit 6
`PRIOR_RECOLLECTION_NOT_ON_HISTORY`; this binds a recollection to `main` only while `main` takes changes by merge
commit or squash merge alone: a fast-forward push or a rebase merge, which GitHub's rebase merge performs and
main's ruleset 24579265 allows today, puts commits `main` never pointed at on its first-parent history, and a tag
ruleset refusing `refs/tags/main` or a merge-and-squash-only `main` ruleset closes that gap; W653q, finding #654), and its collection's `declaration_sha256` must be the SHA-256 of `O`'s
declaration bytes as the plan saved them (exit 6 `PRIOR_RECOLLECTION_DECLARATION`). A RECOLLECT run without the artifact is not read; with none left, the run stays
exit 3 `PRIOR_COLLECTION_MISSING`. A run with its own collection reads that collection only. The registration binds tool versions and run commands (T-5005,
`docs/tasks/P5-005_PREOBSERVATION_REGISTRATION.md:13`), so the driver commit, this tool and A's judge are on
`main` before registration.

**Limits (left for others).** The list is derived inside the workflow from the run's own records and the
server's jobs listing; it is not bound to an authenticated append-only collection log, so #110 stays open.
A later binding needs: the dispatch run ids, each run's artifact digests as the API lists them, and the
union of the lists of every dispatch under one registration (the ids do not collide). A run chosen by its
title assumes `run-name` as on `main`; a run whose plan job the listing misreports is outside this check
(same root as #110). The jobs listing is one page (100 jobs: 64 slices at most). A unit is `(experiment,
run)`; a gate or cohort unit needs a new observation id format (see "Unit"). A recollection is derived by the
tool at the RECOLLECT run's `main` commit (recorded as `recollect_run.commit`), not at `O`'s. For a recollected
run A records its `collection_sha256`, `O`, the RECOLLECT run id and the SHA-256 of its `recollection.json`. A run whose own
records fail collect's checks is refused by `recollect` the same way and stays blocking (A decides). A
residual is left for A (pre-PR round 2): artifacts expire after 90 days, after which a re-dispatch check that needs them is exit 3
(`PRIOR_ARTIFACT_EXPIRED`), so the campaign's CONFIRMATORY dispatches of one experiment must fit 90 days or
a later unit must keep the collections elsewhere.

**Refusal codes.** Every code the tool prints in its one refusal line, with the exit codes it prints it
with (`tests/claude_track/test_ardr_workflow.py` `RefusalCodes` reads the codes from the tool's source and
requires this table to hold exactly them). A code `<PREFIX>_UNAVAILABLE` (exit 3) or `<PREFIX>_JSON`
(exit 2) is an input file that is missing or unreadable, or not one JSON object. Exit 4 is only
`OUTPUT_WRITE_FAILED` (AGENTS.md section 12). A slice's unit codes (`DONE`, `UNIT_TIMEOUT`,
`RAW_LOG_TRUNCATED`, `RUN_NOT_DONE`, `NO_RAW_LOG`, the driver's own codes) and the collector's slice codes
(`SLICE_NOT_STARTED`, `SLICE_UNITS_NOT_RUN`, `SLICE_RECORD_MISSING`, `RUN_INTERRUPTED`, and `stopped`
`SLICE_BUDGET_LEFT_UNITS_BEFORE_START`) are record fields, not refusals.

| Code | Exit | When |
|---|---|---|
| `ARTIFACTS_JSON` | 2 | artifact-id: the earlier run's artifact listing is not one JSON object |
| `ARTIFACTS_LISTING` | 2 | artifact-id: more than one item, a total that differs, or an item of another name or without an id |
| `ARTIFACTS_UNAVAILABLE` | 3 | artifact-id: the listing file is missing or unreadable |
| `CONFIRMATORY_INPUTS` | 3 | plan: CONFIRMATORY without `registration` or `s04_run_id` |
| `DECLARATION_JSON` | 2 | the declaration file is not one JSON object |
| `DECLARATION_SHAPE` | 2 | the declaration's keys, mode, units, registration, S04 or run fields are not as `plan` writes them |
| `DECLARATION_SLICES` | 2 | the declaration's slices are not the ones its unit range and `units_per_slice` give |
| `DECLARATION_UNAVAILABLE` | 3 | the declaration file is missing or unreadable |
| `EXPERIMENT` | 2 | plan: not one of section 3's experiments |
| `EXPLORATORY_INPUTS` | 2 | plan: EXPLORATORY with a registration or its SHA-256 |
| `GIT` | 3 | a `git` command the tool needs failed (`rev-parse HEAD`, `rev-list`) |
| `GIT_TIMEOUT` | 3 | a git call that does not answer in time (U4 LATENT, U3) |
| `INPUT_PATH_NOT_IN_COMMIT` | 3 | plan: the policy or registration path is empty, absolute, holds `..` or is not a file of the checkout's `HEAD` (D-2) |
| `IO_ERROR` | 3 | any other OS error or bad zip while reading an input |
| `JOBS_DUPLICATE_NAME` | 2 | a jobs listing names one job twice |
| `JOBS_JSON` | 2 | a jobs listing is not one JSON object |
| `JOBS_LISTING` | 2 | a jobs listing's total differs from its jobs, it holds more than 100, or a job, its name or its steps are malformed |
| `JOBS_LISTING_MISSING` | 3 | collect: a CONFIRMATORY collection without `--jobs` |
| `JOBS_RUN` | 6 | a jobs listing holds a job of another run or attempt |
| `JOBS_UNAVAILABLE` | 3 | a jobs listing file is missing or unreadable |
| `JOB_NOT_LISTED` | 6 | started-at / slice: this job is not in this run attempt's jobs listing |
| `METHOD_POLICY_CHANGED` | 6 | slice: the policy's ITEM1 `method_policy` or the file's SHA-256 is not the declared one (U3) |
| `METHOD_POLICY_DECLARATION` | 2 | plan / slice: a `method_policy` outside ITEM1 or not `{path, sha256}` (U3) |
| `METHOD_POLICY_SHA256` | 6 | plan: the method policy file's SHA-256 is not the one the policy names (U3) |
| `METHOD_POLICY_UNAVAILABLE` | 3 | plan / slice: the method policy file is unreadable (U3) |
| `METHOD_POLICY_UNDECLARED` | 3 | plan / slice: CONFIRMATORY ITEM1 whose policy names no `method_policy` (U3) |
| `MODE` | 2 | plan: `mode` is not CONFIRMATORY or EXPLORATORY |
| `OBSERVATIONS_OVERSIZED` | 2 | collect: the list is over the receipt tool's 64 KiB bound; nothing is written |
| `OBSERVATIONS_PER_UNIT_CHANGED` | 6 | slice: the policy's gates per run is not the declared one (U3) |
| `OBSERVATION_BUDGET` | 6 | plan: more than 400 observations (units x gates per run for ITEM1 and POOL) (U3) |
| `OPTIMIZED_PYTHON` | 6 | run under `python -O` |
| `OUTPUT_EXISTS` | 3 | an output file, or slice-begin's record directory, already exists |
| `OUTPUT_WRITE_FAILED` | 4 | an output (declaration, `--github-output`, citation, slice record or its directory, collection, observation list) cannot be written |
| `POLICY_GATES` | 2 | plan / slice: an ITEM1 or POOL `gates_per_run` that is not 1..200 (U3) |
| `POLICY_GATES_PENDING` | 3 | plan / slice: a PENDING ITEM1 or POOL `gates_per_run` (U3) |
| `POLICY_GATES_UNSET` | 3 | plan / slice: a CONFIRMATORY ITEM1 or POOL policy without params (U3) |
| `POLICY_JSON` | 2 | plan / slice: the policy is not JSON with the experiment's `experiments` entry (U3) |
| `POLICY_UNAVAILABLE` | 3 | slice: the declared policy file is missing or unreadable (every unit stays BEFORE_START) |
| `PRIOR_ARTIFACT_EXPIRED` | 3 | artifact-id: an earlier run's declaration or collection artifact is expired |
| `PRIOR_COLLECTION_JSON` | 2 | an earlier run's collection is not one JSON object |
| `PRIOR_COLLECTION_MISSING` | 3 | an earlier CONFIRMATORY run with a declaration has no collection and no recollection |
| `PRIOR_COLLECTION_SHAPE` | 6 | an earlier collection's schema, run or unit entries are not as collect writes them |
| `PRIOR_COLLECTION_SIZE` | 2 | an earlier collection zip is over 1 MiB |
| `PRIOR_COLLECTION_UNITS` | 6 | an earlier collection's units are not its declaration's |
| `PRIOR_COLLECTION_ZIP` | 2 | an earlier collection zip is not exactly `collection.json` within 1 MiB |
| `PRIOR_DECLARATION_JSON` | 2 | an earlier declaration is not one JSON object |
| `PRIOR_DECLARATION_MISSING` | 3 | an earlier CONFIRMATORY run has no declaration and the server does not show that it dispatched nothing (D-1) |
| `PRIOR_DECLARATION_RUN` | 6 | an earlier declaration names another run id |
| `PRIOR_DECLARATION_SIZE` | 2 | an earlier declaration zip is over 1 MiB |
| `PRIOR_DECLARATION_TITLE` | 6 | an earlier run titled CONFIRMATORY of this experiment declared another mode or experiment |
| `PRIOR_DECLARATION_ZIP` | 2 | an earlier declaration zip is not exactly `declaration.json` within 1 MiB |
| `PRIOR_RECOLLECTION_COMMIT` | 6 | an earlier recollection's `recollect_run.commit` is not its RECOLLECT run's listed `head_sha` |
| `PRIOR_RECOLLECTION_CONFLICT` | 6 | two recollections of one earlier run hold different collections |
| `PRIOR_RECOLLECTION_DECLARATION` | 6 | an earlier recollection's collection names other declaration bytes than the original run's saved declaration |
| `PRIOR_RECOLLECTION_JSON` | 2 | an earlier recollection is not one JSON object |
| `PRIOR_RECOLLECTION_NOT_ON_HISTORY` | 6 | an earlier recollection's RECOLLECT commit is not on the dispatched commit's first-parent history (also a genuine recollection made on a `main` commit newer than the dispatched commit: dispatch again from current `main`) |
| `PRIOR_RECOLLECTION_RUN` | 6 | an earlier recollection names another RECOLLECT run or another original run than its title |
| `PRIOR_RECOLLECTION_SHAPE` | 6 | an earlier recollection's keys, `recollected` mark, collection run, digest, original or RECOLLECT attempt, labels or slice artifact ids are not as recollect writes them |
| `PRIOR_RECOLLECTION_SIZE` | 2 | an earlier recollection zip is over 1 MiB |
| `PRIOR_RECOLLECTION_ZIP` | 2 | an earlier recollection zip is not exactly `recollection.json` within 1 MiB |
| `PRIOR_RUN_IN_PROGRESS` | 3 | a chosen CONFIRMATORY run of this experiment, or any RECOLLECT run of this experiment with a digit target (chosen or not), that is not newer (or is the current number with another id) is not `completed` |
| `RAW_LOG_EVIDENCE_STATUS` | 6 | slice: the raw log's first line has another `evidence_status` |
| `RAW_LOG_GATES` | 6 | collect (and slice, for the #713 shapes): an ITEM1 or POOL raw log's gate lines are not the declared gates' (U3); since U3 Part C also a prefix outcome outside section 16's table, a `seq` gap or a line after `RUN_END`, a pool `GATE_END` whose `seq` is not an integer or whose `block_hash` is not a string or a pool `BLOCK` whose `block_hash` is not a string (#713), a `deadline` that is not the declaration's (or null in CONFIRMATORY), a `GATE_START` at or after it, or a deadline stop the log does not prove ("Gate states") |
| `RAW_LOG_JSON` | 2 | slice: the raw log's first line does not parse and the unit was not killed at its limit |
| `RAW_LOG_MISSING` | 3 | collect: a started unit's raw log is not in the slice artifact |
| `RAW_LOG_MODE` | 6 | slice: the raw log's first line has another `mode` |
| `RAW_LOG_NOT_DONE` | 6 | collect: an OBSERVED unit's log does not run RUN_START (seq 1, this unit) .. RUN_END DONE |
| `RAW_LOG_POLICY_SHA256` | 6 | slice: the raw log's first line has another `policy_sha256` |
| `RAW_LOG_REGISTRATION_SHA256` | 6 | slice: the raw log's first line has another `registration_sha256` |
| `RAW_LOG_SHA256` | 6 | collect: a raw log's SHA-256 is not the recorded one |
| `RAW_LOG_SIZE` | 2 | a raw log is over 256 MiB, a symlink or not a regular file |
| `RAW_LOG_START` | 2 | slice: the raw log's first line is not RUN_START seq 1 of the raw schema |
| `RAW_LOG_UNIT` | 6 | slice: the raw log's first line names another unit |
| `RECOLLECT_ARTIFACTS_JSON` | 2 | recollect: the original run's artifact listing is not one JSON object |
| `RECOLLECT_ARTIFACTS_UNAVAILABLE` | 3 | recollect: the original run's artifact listing file is missing or unreadable |
| `RECOLLECT_ARTIFACT_EXPIRED` | 3 | recollect: the original run's declaration or a slice artifact is expired |
| `RECOLLECT_ARTIFACT_LISTING` | 6 | recollect: the artifact listing is over 100 items, its total differs, a name repeats or is not a D4 name, or an item is malformed |
| `RECOLLECT_ARTIFACT_RUN` | 6 | recollect: a listed artifact's `workflow_run.id` is not the original run |
| `RECOLLECT_COLLECTION_EXISTS` | 6 | recollect: the original run lists an `ardr-collection` (nothing to recover) |
| `RECOLLECT_DECLARATION_JSON` | 2 | recollect: the original run's declaration is not one JSON object |
| `RECOLLECT_DECLARATION_MISSING` | 3 | recollect: the original run lists no declaration, or its zip is absent |
| `RECOLLECT_DECLARATION_RUN` | 6 | recollect: the declaration names another run, an attempt other than 1 or another commit than the run's head |
| `RECOLLECT_DECLARATION_SIZE` | 2 | recollect: the declaration zip is over 1 MiB |
| `RECOLLECT_DECLARATION_ZIP` | 2 | recollect: the declaration zip is not exactly `declaration.json` within 1 MiB |
| `RECOLLECT_EXPERIMENT` | 6 | recollect: the declaration is of another experiment than the input |
| `RECOLLECT_NOT_CONFIRMATORY` | 6 | recollect: the declaration is not CONFIRMATORY |
| `RECOLLECT_RUN_BRANCH` | 6 | recollect: the original run's `head_branch` is not main |
| `RECOLLECT_RUN_EVENT` | 6 | recollect: the original run is not a `workflow_dispatch` |
| `RECOLLECT_RUN_ID` | 6 | recollect: the original run's id is not the input |
| `RECOLLECT_RUN_ID_INPUT` | 2 | recollect: `recollect_run_id` is not a run id (digits) |
| `RECOLLECT_RUN_JSON` | 2 | recollect: the original run file is not one JSON object |
| `RECOLLECT_RUN_NOT_COMPLETED` | 3 | recollect: the original run is not `completed` |
| `RECOLLECT_RUN_NOT_ON_HISTORY` | 6 | recollect: the original run's `head_sha` is not a commit id on the RECOLLECT dispatch commit's first-parent history |
| `RECOLLECT_RUN_TITLE` | 6 | recollect: the original run's `display_title` is not `ardr CONFIRMATORY <experiment>` |
| `RECOLLECT_RUN_UNAVAILABLE` | 3 | recollect: the original run file is missing or unreadable |
| `RECOLLECT_RUN_WORKFLOW` | 6 | recollect: the original run's `path` is not this workflow |
| `RECOLLECT_SLICE_MISSING` | 3 | recollect: a listed slice artifact's zip is absent |
| `RECOLLECT_SLICE_ZIP` | 6 | recollect: a slice zip is unreadable, over its bounds, or holds a member other than `slice-record.json` and `raw-<run>.jsonl` of its slice |
| `REDISPATCH_OBSERVED_UNIT` | 6 | a planned unit is not BEFORE_START in an earlier CONFIRMATORY dispatch of the experiment |
| `REGISTRATION_SHA256` | 3 | plan: CONFIRMATORY without a 64-hex `registration_sha256` |
| `RUNS_JSON` | 2 | a runs listing page is not one JSON object |
| `RUNS_LISTING` | 3 | the runs listing's total is not a count, or a run is malformed (including a `run_number` that is not a positive JSON integer), not a dispatch or of another workflow path, or a RECOLLECT run of this experiment with a digit target (chosen or not) that is not a newer unfinished dispatch has a `head_sha` that is not a commit id |
| `RUNS_LISTING_CAPPED` | 3 | the filtered runs listing says 1,000 runs or more: the oldest may be missing (P3-e) |
| `RUNS_LISTING_CHANGED` | 3 | the runs listing pages disagree on the total, a page is short or a run is listed twice |
| `RUNS_TITLE` | 3 | a dispatch run on main whose `display_title` is not `ardr <mode> <experiment>` or `ardr RECOLLECT <experiment>[ <run id>]` of a section 3 experiment |
| `RUNS_UNAVAILABLE` | 3 | a runs listing page is missing or unreadable |
| `RUN_ATTEMPT_NOT_FIRST` | 6 | plan: a CONFIRMATORY attempt other than 1; recollect: an attempt other than 1 |
| `RUN_FIELDS` | 2 | plan / recollect: the run id, attempt or commit is malformed; prior-runs / redispatch: `--current-run-number` below 1 |
| `S04_ARTIFACTS_JSON` | 2 | the S04 artifact listing is not one JSON object |
| `S04_ARTIFACTS_UNAVAILABLE` | 3 | the S04 artifact listing file is missing or unreadable |
| `S04_ARTIFACT_LISTING` | 6 | the S04 artifact listing: a total that differs, an item of another name, more than one, or no id |
| `S04_ARTIFACT_SIZE` | 6 | the S04 record zip is over 1 MiB |
| `S04_ARTIFACT_ZIP` | 6 | the S04 record zip is not exactly `s04_record_v2.json` within 1 MiB |
| `S04_CITATION_JSON` | 2 | slice: `citation.json` is not one JSON object |
| `S04_CITATION_RUN` | 6 | slice: the citation names another S04 run than the declaration |
| `S04_CITATION_SHAPE` | 2 | slice: the citation's keys or values are not as `s04-cite` writes them |
| `S04_CITATION_UNAVAILABLE` | 3 | slice: CONFIRMATORY without plan's `citation.json` |
| `S04_JOB_LOG_AMBIGUOUS` | 6 | the S04 record job's log prints more than one record line |
| `S04_JOB_NOT_LISTED` | 6 | the S04 record job is not in the cited run attempt's jobs listing |
| `S04_NOT_ON_SLICE_HISTORY` | 6 | the cited run's head is not on the dispatched commit's first-parent history |
| `S04_NOT_PASS` | 6 | the S04 record is not `PASS_CLASS_T` |
| `S04_RECORD_COMMIT` | 6 | the S04 record's commit is not the cited run's head |
| `S04_RECORD_JSON` | 6 | the S04 record bytes are not JSON |
| `S04_RECORD_MISSING` | 3 | the listed S04 artifact's zip is absent, or the log holds no record line with its `sha256sum` line |
| `S04_RECORD_RUN` | 6 | the S04 record's `run` is not the cited main push run |
| `S04_RECORD_SCHEMA` | 6 | the S04 record's schema or `subject_oids` are not the v2 record's |
| `S04_RUN_ATTEMPT` | 6 | the cited run has no `run_attempt` of 1..999 |
| `S04_RUN_BRANCH` | 6 | the cited run's `head_branch` is not main |
| `S04_RUN_EVENT` | 6 | the cited run is not a push |
| `S04_RUN_HEAD` | 6 | the cited run's `head_sha` is not a 40-hex object id |
| `S04_RUN_ID` | 6 | the cited run's id is not the input |
| `S04_RUN_ID_INPUT` | 2 | plan: `s04_run_id` is not a run id (digits) |
| `S04_RUN_JSON` | 2 | the cited run file is not one JSON object |
| `S04_RUN_NOT_SUCCESS` | 6 | the cited run is not completed with success |
| `S04_RUN_UNAVAILABLE` | 3 | the cited run file is missing or unreadable |
| `S04_RUN_WORKFLOW` | 6 | the cited run's `path` is not `.github/workflows/claude-track-rx02.yml` |
| `S04_SUBJECTS_CHANGED` | 6 | a subject's object id at the dispatched commit is not the S04 record's |
| `SLICE_BUDGET` | 6 | plan: 30 + `units_per_slice` x `unit_minutes` + 15 > 330 |
| `SLICE_COMMIT` | 6 | slice-begin / slice: the checkout is not the declared commit (no record written) |
| `SLICE_COUNT` | 2 | plan: more than 64 slices |
| `SLICE_MODE` | 2 | slice-begin / slice: the mode is not the declared one (PR_SMOKE only for EXPLORATORY) |
| `SLICE_NUMBER` | 2 | slice-begin / slice: no declared slice of that number |
| `SLICE_RECORD_JSON` | 2 | collect: a slice record is not one JSON object |
| `SLICE_RECORD_MODE` | 6 | collect: a slice record's mode is not the declaration's |
| `SLICE_RECORD_NOT_BEGUN` | 3, 6 | slice: no begin record (3) or one that is not exactly the begin record (6) |
| `SLICE_RECORD_RAW_LOG` | 6 | collect: a BEFORE_START unit names a raw log, or a started unit names another than `raw-<run>.jsonl` |
| `SLICE_RECORD_REGISTRATION` | 6 | collect: a CONFIRMATORY slice record's registration is not the declaration's |
| `SLICE_RECORD_RUN` | 6 | collect: a slice record's slice, job name, run, experiment or commit is not the declaration's |
| `SLICE_RECORD_S04` | 6 | collect: a CONFIRMATORY slice record cites another S04 run |
| `SLICE_RECORD_SHAPE` | 2 | collect: a slice record's keys, states, unit codes (`null` or a code word, #713), start time, policy hash or citation are malformed |
| `SLICE_RECORD_UNAVAILABLE` | 3 | collect: a slice record is unreadable |
| `SLICE_RECORD_UNITS` | 6 | collect: a slice record's units are not the declared slice's, in order |
| `SLICE_SHAPE` | 2 | plan: `unit_minutes` not 1..330 or `units_per_slice` not 1..400 |
| `STARTED_AT` | 2, 6 | a `started_at` that is not `YYYY-MM-DDTHH:MM:SSZ` (2), or `--started-at` that differs from the listing (6) |
| `STARTED_AT_MISSING` | 3 | slice: CONFIRMATORY without `--jobs` or `--started-at` |
| `STARTED_AT_NOT_SERVER` | 6 | collect: a CONFIRMATORY record's start time is not the listing's `started_at` of its job |
| `UNIT_MINUTES_SHORT` | 6 | plan: a CONFIRMATORY ITEM1 or POOL `unit_minutes` x 60 not above the driver's D2-2 share and margin, 6,600 s (U3) |
| `UNIT_RANGE` | 2 | plan: the unit range is not 0 <= first <= last <= 9999999 |
| `WORK_ROOT_NOT_ABSOLUTE` | 2 | slice: `--work-root` is not an absolute path (U4 LATENT, U3) |


## 14. Chained BIRTH (D2-3a)

Status: D2-3a of the CT-P5-001 driver (A #258 issuecomment-6543158220 Q2: chained BIRTH is D2-3a's merge
condition; B -6542840327, -6543176330). Added 2026-10-31 after section 13; sections 1-13 are unchanged.
Class T Regtest development evidence only. Every value in sections 14-19 is PENDING_FREEZE / DRAFT.

**Worker line.** One more request line beside section 10's (tab-separated, one file per call):

    BIRTHS <first height> <prestate hex | -> <block hex>,<block hex>,…

Each block is replayed exactly as one `BIRTH` line would replay it, on the poststate of the block before
it (the first on the given prestate), and each block must extend the one before it: its header's
previous-block hash is the hash of the block before it in the list (`BLOCK_CHAIN`). The answer is one row
per block, in height order, then the last poststate:

    BIRTH_ROW <height> <born txids, comma-separated | -> <next birth> <poststate SHA-256>
    POSTSTATE <last height> <poststate hex>

**Client checks** (`Worker.births` in `tools/claude_track_ardr_bidders.py`). One `BIRTH_ROW` per height,
`first`, `first + 1`, … in order, with a 64-hex state hash; a birth only at the gate height the caller
names (none when it names none); `POSTSTATE` at the last height, and the SHA-256 of its bytes equal to the
last row's state hash. One request stays under the worker's 4 MiB request bound: the campaign sends at most
3 MiB of block hex per call and carries the poststate to the next call. The campaign makes two calls per
gate (the blocks before block G, then block G) and writes one `CORE_REPLAY` line per height (`height`,
`born`, `next_birth`, `state_sha256`).

| Code | Exit | Raised by | When |
|---|---|---|---|
| `BIRTHS_EMPTY` | 2, 3 | client (2); worker (panic: 3, as `PREREQUISITE WORKER_FAILED`) | a `BIRTHS` call with no block: the client refuses it (exit 2) before any worker call; a request that reaches the worker with no block panics there (exit 3) |
| `BIRTHS_FIELDS` | 3 | worker (panic) | a `BIRTHS` line without exactly four fields |
| `BLOCK_CHAIN` | 3 | worker (panic) | a block does not extend the one before it in the list |
| `BIRTHS_ROWS` | 2 | client | a row missing, out of order, mis-tagged or without a 64-hex state hash |
| `BIRTH_OUTSIDE_GATE` | 2 | client | a row with a birth at a height other than the named gate height |
| `BIRTHS_POSTSTATE` | 2 | client | no `POSTSTATE` at the last height, or its SHA-256 is not the last row's |
| `CHAIN_HEIGHT` | 2 | campaign | a block that is not the next height of the run's chain |

A worker panic (`BIRTHS_EMPTY`, `BIRTHS_FIELDS`, `BLOCK_CHAIN`) reaches the driver as a failed worker call, `PREREQUISITE WORKER_FAILED`, exit 3;
the panic text stays in the worker's own output.

## 15. The D2-2 input converter and the method policy (D2-3a)

`tools/claude_track_ardr_truth.py` turns the ground truth of section 12 into D2-2's three inputs
(`ARDR_CLUSTER_V1`, PR #616), each a new file, sorted keys, ASCII, indent 1, ending in one LF:

- `cluster_truth.json` (`BITAGI_CT_ARDR_CLUSTER_TRUTH_V1`): `cluster_truth_projection` of section 12, the
  one projection;
- `gates.json` (`BITAGI_CT_ARDR_GATES_V1`): one row per ground-truth gate in order, `gate`, `winner_txid`
  (the gate's single born txid; never null), `project` false, `block_hash` of block G;
- `method.json` (`BITAGI_CT_ARDR_CLUSTER_METHOD_V1`): `boundary.excluded_txids` = the ground truth's
  `excluded_txids`, and `boundary.floor_height`, `max_depth`, `max_window_blocks`, `thresholds` from the
  method policy.

**Method policy (`BITAGI_CT_ARDR_METHOD_POLICY_V1`).** One JSON object, exactly `schema`, `floor_height`,
`max_depth`, `max_window_blocks`, `thresholds`. Any value may be a PENDING string. Otherwise
`floor_height` is an integer 0 … 2^32 − 1, `max_depth` 1 … 10,000, `max_window_blocks` 1 … 100,000 and
`thresholds` a non-empty, strictly ascending list of integers 1 … 1,000,000: D2-2's own bounds
(`MAX_DEPTH`, `MAX_WINDOW`, `MAX_THRESHOLD` in `tools/claude_track_ardr_cluster.py` at `77ad3abd`), checked
when the file is read, before any node starts (round 1, P3-4). Its SHA-256 must be in the registration's
`ardr_policy_sha256` list in CONFIRMATORY (section 18). A PENDING value is refused in CONFIRMATORY (exit 3);
EXPLORATORY and PR_SMOKE take its DRAFT value (floor 1, depth 16, window 40,000, thresholds [4, 15]) and
the `CLUSTER_TOOL` line lists the fields that did (`drafted_method_fields`).

**Against the run** (round 1, P3-4), also before any node starts: `floor_height` ≤ `H0`, and the window
holds the expected chain, `H0 + (gates_per_run − 1) × 144 − floor_height + 1 ≤ max_window_blocks` (144 is
the DRAFT spacing of consecutive item-1 births, measured in every gate so far). A chain that still grows
past the window is refused by D2-2 itself (`WINDOW_TOO_LARGE`), and the run then ends FAILED (section 16). *Dated line 2026-11-10 (B, ITEM3W W3-1; 045b :1623): the W policy `BITAGI_CT_ARDR_W_POLICY_V1` is not a D2-2 input. The W-row tool `tools/claude_track_ardr_wrows.py` reads it, and its paragraph and its `W_POLICY_*` rows, which 045b :1623 places beside `METHOD_POLICY_SHAPE`, are in `ARDR_WROWS_V1.md` section 4 until A rules where they go (an in-place row would move every line under it; a dated addition at the end of this file would not; `docs/claude-track/plans/notes/CT-P5-001_DRIVER_EN/2026-11-10_item3w-w3-frozen.md` question A1), so that no line of this file moves under the frozen 045b's line citations (045b :1903).*

| Code | Exit | Raised by | When |
|---|---|---|---|
| `METHOD_POLICY_JSON` | 2 | converter, driver | the method policy is not one JSON object |
| `METHOD_POLICY_SHAPE` | 2 | converter, driver | other keys, another schema, a value of the wrong type, or unsorted thresholds |
| `METHOD_POLICY_BOUND` | 2 | converter, driver | a value past D2-2's bound above |
| `METHOD_POLICY_PENDING` | 3 | converter, driver | a PENDING value in CONFIRMATORY |
| `METHOD_FLOOR_ABOVE_H0` | 2 | driver, campaign | `floor_height` > `H0` |
| `METHOD_WINDOW_SHORT` | 2 | driver, campaign | the window cannot hold the expected chain |
| `GROUND_TRUTH_SCHEMA` | 2 | converter | the ground truth is not `BITAGI_CT_ARDR_GROUND_TRUTH_V1` |
| `GROUND_TRUTH_GATES` | 2 | converter | the ground truth has no gate row |
| `GATE_BORN_COUNT` | 2 | converter | a gate row without exactly one born txid |
| `GATE_WINNER_UNKNOWN` | 2 | converter | a gate's born txid is not in `winners` |
| `GATE_BLOCK_HASH` | 2 | converter | a gate row without a 64-hex `block_hash` |
| `OUT_DIR_MISSING` | 3 | converter CLI | `--out-dir` is not a directory |
| `OUTPUT_EXISTS` | 3 | converter CLI | one of the three files exists (new files only) |

## 16. The item-1 campaign (D2-3a)

One ITEM1 run is gates 0-199 on one chain (045b 4.6; A Q2: the unit is the gate inside the run). One
PUBLIC SYNTHETIC seat per gate, the gate's winner, at rung 0 = `b` (`f_0 = ceil(b × 213 / 1000)`, no fee
draw). Gates 100-119 go to the planted owner's wallet `j mod m` (`j` = gate − 100, `m` its wallet count,
ascending order; no draw); every other gate draws `WINNER_G<ggg>` (n = 40), winner `W<value>`. The
generated bidder list and its SHA-256 are in `RUN_START` and `BIDDERS` (A Q6). The miner policy is
`ITEM1_WINNER_ONLY` (section 18): at block G it keeps the winner's REGISTER and drops the gate's other
REGISTERs and their descendants.

**Raw-log events** (section 2's line, with section 5's `unit`; `gate` set from the first gate on):

- `GATE_START` (`gate`, `height` = G, `wallet`, `observation_id`) before the gate's filler blocks;
- `GATE_END` (`gate`, `height`, `status` `OBSERVED`, `observation_id`, `winner_txid`, `wallet`,
  `block_hash`, `next_birth`; in a pool run also `producer_tags`) once block G is accepted and replayed;
- `CLUSTER_TOOL` (ITEM1, after the last gate, before teardown; or on a failed run's prefix, D2-3c):
  `prefix` (true for D2-2 on the gates of a failed run that reached `GATE_END`), `gates` (the gate numbers
  D2-2 judged), `tool_sha256`, `exit`, `stdout` (D2-2's
  summary line parsed, or null), `truth_sha256`, `inputs_sha256`, `drafted_method_fields`, `output_sha256`,
  `output_bytes`, then `truth`, `inputs` (the three documents) and `output` (D2-2's output bytes as text, or
  `null` when they are not ASCII; the line is written before the output is decoded, so D2-2's exit code and
  every SHA-256 are in the log whatever the bytes are; round 2, P3-D);
- `PREFIX_START` (ITEM1, a failed run's prefix only; D2-3c round 4, P2-a): `code` (the first failure's,
  as `RUN_END FAILED` will carry it), `phase` (`GATES`), `failed_gate` and `gates` (the gates the prefix
  judges). Written after the quick `NOT_RUN` checks and before the prefix's first slow step (the Node A
  probe), so a unit killed during the prefix still has its death cause in the log. A unit whose log has
  `PREFIX_START` and no `RUN_END`: the death cause is `PREFIX_START`'s (`code`, `phase`, `failed_gate`),
  and every gate is EXCLUDED (no prefix outcome); U3 reads it;
- `RUN_END` `DONE` with `timing` (`setup_ns`, `mine_ns`, `mine_blocks`, `birth_ns`, `birth_calls`,
  `build_ns`, `build_calls`, `cluster_ns`, `total_ns`) and the run summary (`gates`, `winners`,
  `excluded_txids`, `owner_txids`, `tip`, `cluster`), `deadline_reached` and `gates_not_started` (U3 Part C,
  section 18).

**Observation id of a gate.** `OBS-<e><run:07>-G<ggg>`: section 13's run-level id and the gate number in
three digits (for example `OBS-10000000-G103` for ITEM1 run 0 gate 103). Section 13's observation list
still carries one id per `(experiment, run)`; a list format that carries the gate ids is a new version
(D4-2 or D2-3b), not this section.

**Rule (A #636 check 6551799924, "For A" 2; U3 Part C).** Every CONFIRMATORY run path writes RUN_END
FAILED with a code after RUN_START. D1 smoke is not CONFIRMATORY (CONFIRMATORY_CAMPAIGN_NOT_BUILT). Later
CONFIRMATORY paths (ITEM2, ITEM3, ITEM4 after D3a-1) use the campaign's and item 2's RUN_END FAILED path.

**RUN_END FAILED.** Any failure inside the run after `RUN_START` (a refusal of either copy of the driver
module, a node prerequisite or mismatch, an internal error) writes one `RUN_END` with `status` `FAILED`,
`code` (the death cause), `phase`, `failed_gate` (g: the first gate of the run without `GATE_END`, null
when every gate has one; A 6549827052 Q2; for ITEM1 and POOL alike; null in every phase but `GATES`, since
`CLUSTER`, `POST_GATES` and `END` start after the last `GATE_END`, D2-3c round 3), `cluster_failed`, `cluster_prefix`, `cluster_prefix_reason`,
`timing`, `excluded_gates` and `excluded_observation_ids`, then the run ends with the failure's exit code. The code and the exit are
always those of the first failure; the failed-prefix D2-2 below never changes them, except the run's exit in
the two exit-5 cases below (`RUN_END`'s `code` stays the first failure's), and never turns a failed run into
exit 0:

- `phase` `GATES`: the gates without `GATE_END` are EXCLUDED, the failed gate and every later one; no run
  replaces them (A Q2; 045b 4.6 stopping rule). For ITEM1 this holds only when the prefix D2-2 is `OK`;
  otherwise every gate is EXCLUDED and `cluster_failed` is true (below);
- `phase` `POST_GATES` (POOL, D2-3c; A 6548007197 For-A 1): a pool run failed after its last `GATE_END`,
  in the ground truth or the producer description. The gates without `GATE_END` are EXCLUDED (none, when
  every gate reached it); `cluster_failed` is false;
- `phase` `CLUSTER` (round 1, P2-2; round 2, P3-A): an ITEM1 run failed after its last `GATE_END` and
  before D2-2's output exists: the ground truth, the ANCHOR_KEY scripts (a worker call), the placed members
  (`ANCHOR_PLACED_MISMATCH`), D2-2's inputs, or D2-2 itself (failed, timed out, could not start, was missing,
  or wrote output that is not ASCII). No gate has its D2-2 output, so every gate of the run is EXCLUDED and
  `cluster_failed` is true. The phase starts right after the last gate's `GATE_END`;
- `phase` `END`: `RUN_END DONE` itself could not be written (for example `LOG_BOUND`); the gates without
  `GATE_END` are EXCLUDED.

**D2-2 on a failed ITEM1 prefix** (D2-3c; A 6548007197 For-A 2). When an ITEM1 run fails in phase
`GATES`, the campaign, before teardown and before `RUN_END FAILED`, runs D2-2 on the prefix: the gates
that reached `GATE_END` (the campaign keeps a snapshot of the run's state after each `GATE_END`; a gate
whose `GATE_END` was not written is never in it). It writes the prefix's ground truth and inputs into a new
0700 `cluster_prefix` directory and one `CLUSTER_TOOL` line with `prefix` true and `gates` the prefix's
gates; D2-2 has the same 3,600-second limit and reads Node A's chain to its tip (blocks past the last
`GATE_END` are in its window; no gate row names them). `cluster_prefix` records the outcome. The `NOT_RUN`
checks run in this order (U3 Part C, A #638 check 6552915714 P3-1): `SECRET_IN_LOG` / `LOG_BOUND`, then
`NO_GATE_DONE`, then the `PREFIX_SKIP_TIMEOUTS` table (`NODE_A_TIMEOUT`, `WORKER_TIMEOUT`), then
`PREFIX_START` is written, then the Node A probe (`NODE_A_DOWN`); so a timeout with no gate done is
`NO_GATE_DONE`.

| `cluster_prefix` | `cluster_prefix_reason` | When | Excluded |
|---|---|---|---|
| `OK` | null | the prefix D2-2 exited 0 with output | the gates without `GATE_END` |
| `FAILED` | the prefix's code (for example `CLUSTER_TOOL_FAILED 3`, `PREREQUISITE CLUSTER_TOOL_TIMEOUT`, `LOG_BOUND`) | the prefix truth, its inputs, its `CLUSTER_TOOL` line or D2-2 failed | every gate |
| `NOT_RUN` | `SECRET_IN_LOG`, `LOG_BOUND` | the first failure was the log refusing a line: nothing more is tried | every gate |
| `NOT_RUN` | `NO_GATE_DONE` | no gate reached `GATE_END` | every gate |
| `NOT_RUN` | `NODE_A_DOWN` | Node A does not answer the driver's `getblockchaininfo` | every gate |
| `NOT_RUN` | `NODE_A_TIMEOUT` | the first failure was a node-call timeout on Node A (`PREREQUISITE NODE_CALL_TIMEOUT A`, U4): the probe is not tried, so the unit does not wait for Node A twice (round 4, P2-b; a timeout on another node keeps the probe) | every gate |
| `NOT_RUN` | `WORKER_TIMEOUT` | the first failure was a worker timeout (`PREREQUISITE WORKER_TIMEOUT`, U4): the prefix is not tried, since its truth asks the worker again (up to 1,800 seconds) before D2-2 (round 5, A 6551799924 P3-3) | every gate |
| `NOT_RUN` | `PHASE_CLUSTER`, `PHASE_END` | an ITEM1 run failed in phase `CLUSTER` or `END` (the run's own D2-2 already ran or was tried) | as that phase says |
| `NOT_RUN` | `NO_CLUSTER` | a POOL run (no D2-2 in it) | as the phase says |
| `NOT_RUN` | `NO_OUTCOME` | the prefix itself was interrupted (not an `Exception`, for example a keyboard interrupt) | every gate |

A prefix failure never masks the first failure: the run still ends with one `RUN_END FAILED` carrying the
first failure's code and exit, with one exception, a security failure in the prefix (B decision, D2-3c
round 3; For A). A secret found in the prefix's own record is refused like any line (never written) and
makes the prefix `FAILED` with reason `SECRET_IN_LOG`; D2-2 exiting 5 on the prefix makes it `FAILED` with
reason `CLUSTER_TOOL_FAILED 5`. In both cases the run then ends with exit 5 (the raised code is the
prefix's reason), even when `RUN_END` cannot be written; `RUN_END FAILED` still records the first failure
as `code`. Reason: the prefix wrote its truth and D2-2's inputs into `cluster_prefix`, so a secret seen
there must show in the unit's exit and code as 5, and in phase `CLUSTER` D2-2's exit 5 already passes
through to the run; the prefix must not be the one path that masks it. In these two cases the driver's FAIL
code (the slice record's `code`) is the prefix's reason, while `RUN_END`'s `code` is the first failure: U3
takes the death cause from `RUN_END` (or `PREFIX_START`), never from the slice record (round 4, P3-2). Today
a started unit that exits 5 is EXCLUDED and the slice goes on (section 13; slices stops only before start);
whether it should stop the slice is A's call in U3 (B default: no, since the secret line itself was refused
and never written; round 4, P2-c); since U3 Part C collect lists such units apart (`exit_5`, section 13). Any other prefix failure (D2-2 exit 2, 3, 4 or 6,
a signal, exit 0 without output, a timeout, `LOG_BOUND`, an internal error) keeps the first failure's exit.

**The prefix's time** (round 4, P2-a; a U3 requirement). The prefix can take the probe (up to 300 seconds),
the worker's KEYS call for the ANCHOR_KEY labels (up to 1,800 seconds) and D2-2 (up to `CLUSTER_SECONDS`,
3,600). The driver deadline U3 adds (A Q5) must leave room for all three before the unit's time limit, or
a slow prefix is killed and only `PREFIX_START` records the death cause.

**The prefix's window** (round 4, P3-6; corrected in U3 Part C after A #638 check 6552915714 P3-2). D2-2
reads Node A's chain to its tip, so the prefix's window includes the failed gate's filler blocks and, if
mined, its block G. D2-2 links only the recorded winners, by ancestry and by their own keys, so blocks after
the last judged gate's G change neither the links nor the metrics: ANCESTRY walks back from a recorded winner's
inputs (`tools/claude_track_ardr_cluster.py:432-465` at main `088fb946`), ANCHOR_KEY compares the keys of
recorded winners only (`:492-519`), and the union-find runs over recorded winners only (`:522-528`). A
accepted the tip-wide window (no tip given to D2-2).

**No choice after the result** (A 6549827052 Q2). Whether the prefix runs is decided only by the death
cause (`code`) and g (`failed_gate`, with the gates before it): `SECRET_IN_LOG` or `LOG_BOUND` means no
prefix and every gate EXCLUDED; no gate done, or Node A not answering the driver's `getblockchaininfo`,
likewise. Node A answering is an infrastructure condition, checked before the prefix starts, never a
result: the probe reads no field of its reply, and no D2-2 output exists when it runs. No metric, D2-2 output or other result is read to make that choice; a prefix that ran and
failed (any exit but 0 with output) excludes every gate whatever it reported.

**Which gates count, per experiment** (A #632 6548007197 P3-1, For-A 1 and 2; A Q2). In every
experiment a gate listed in `excluded_gates` is EXCLUDED whatever `GATE_END` it has.

- **ITEM1** (A 6549827052 Q2). A gate counts in a run that ends `RUN_END DONE`, or in a run that ends
  `RUN_END FAILED` phase `GATES` with `cluster_prefix` `OK`, for the gates of that prefix (its
  `CLUSTER_TOOL` line with `prefix` true judges them). In a run that dies at gate g (`failed_gate`) with a
  prefix `OK`, the gates g…199 count as missing. The missing gates and the gates EXCLUDED for any other
  reason are added together under 045b's 10% rule (045b `:381`): more than 20 of the 200 gates makes item
  1 NOT_ESTABLISHED, and otherwise the judgement uses the remaining gates. So a death at g < 180 (more
  than 20 missing gates on its own) is NOT_ESTABLISHED. Any other failed run (prefix `FAILED` or
  `NOT_RUN`, or a failure in phase `CLUSTER`) has every gate EXCLUDED. A job killed outside Python (the
  unit's time limit, a lost job) leaves no `RUN_END` and no prefix: every gate is EXCLUDED. A will write
  this rule into the 045b freeze PR as a dated line; this section does not change 045b. *Dated line 2026-11-10 (B, FZ-6, C27 pointer; sources 045b :1194's C27 dated line and A #664 issuecomment-6746599499): it is 045b :1083 (an item-1 job that dies at gate g: gates g … 199 count as missing, under the 10% rule).*
- **POOL** (A 6549827052 Q6: a gate counts only if everything its judgement needs is in the log). The
  pool judgement is the HHI of block-G producers and the missing-data count (045b 4.5); per gate it needs
  block G's identity and its producer tags. Both are in the log at or before the gate's `GATE_END`: the
  `DRAW` `PRODUCER_H<height>` line, the `BLOCK` line with `block_hex`, `block_hash` and `producer`
  (section 17), and `GATE_END` with `block_hash` and `producer_tags`. What runs after the loop in phase
  `POST_GATES` (the ground truth's ownership and link groups, and `producers_description`) is not part of
  the pool judgement (the truth is item 1's; the description is not judged, A Q3). So a gate with
  `GATE_END` counts whatever comes after it: in a run that ends `RUN_END DONE`, `RUN_END FAILED` in phase
  `GATES` or `POST_GATES`, or with no `RUN_END`. A truncated raw log counts only up to the last intact
  `GATE_END` line (a line that parses whole). Gates without `GATE_END` are EXCLUDED. If a later version
  makes the pool judgement need a field written only after the loop, the gates of a run that dies before
  it (or fails in `POST_GATES`) are EXCLUDED, and this item must say so. Scope of A's condition (D2-3c
  round 3, B's reading; For A): it covers the inputs of the pool judgement only, the HHI and the
  missing-tag count, which come from the `DRAW`, `BLOCK` and `GATE_END` lines. A pool run's ground truth
  (the item-1-shaped ownership and link truth built in `POST_GATES`: the funding layout, the worker's
  anchor keys) is not part of the pool judgement and need not be rebuildable from the log. If A means the
  whole truth, a dead pool run's gates become EXCLUDED instead. A cell (`PoolFromTheLog`) rebuilds each
  pool gate's `block_hash`, `producer_tags` and drawn producer from the log lines alone and checks them
  against the run's own gate rows.
- **ITEM2** is unchanged: the run is the unit (section 13); only `RUN_END DONE` with exit 0 is OBSERVED.

D4's `collect` reads these fields since U3 Part C (section 13, "Gate states").

**For A** (D2-3c, B accepted 2026-10-31). For ITEM1 in phase `GATES`, only a prefix `OK` keeps the
gates before g countable; a prefix `FAILED` or `NOT_RUN` excludes every gate and sets `cluster_failed`,
because an ITEM1 gate counts only with a D2-2 output (the reasoning of phase `CLUSTER`). With A Q2's 10%
rule such a run is NOT_ESTABLISHED anyway; the choice keeps the reader from counting a gate D2-2 never
judged. The raw log keeps 1 MiB of its 256 MiB bound for `RUN_END` (every
other line must leave it free, `LOG_BOUND`), so a run refused for its size still writes `RUN_END FAILED`
(round 1, P3-2). A refused line changes neither the file nor `seq`.

**D2-2 in the run** (A Q7). The driver checks that the D2-2 file exists before any node starts. After the
last gate it writes the truth and the three inputs into a new 0700 directory and runs D2-2 as a
subprocess (`--chain regtest`, Node A's `bitcoin-cli`, data directory and RPC port; D2-2 reads Node A's
cookie itself) with a 3,600-second limit. D2-2's exit code becomes the run's (round 1, P3-6; AGENTS.md
section 12): 2, 3, 5 and 6 pass through; 4, a signal, any other code, or exit 0 without an output file is
4.

| Code | Exit | Raised by | When |
|---|---|---|---|
| `CAMPAIGN_EXPERIMENT` | 2 | campaign | an experiment other than ITEM1 or POOL |
| `ITEM1_GATE` | 2 | campaign | a gate number outside 0-199 |
| `OBSERVATION_ID` | 2 | campaign | a gate or run outside the id's digits |
| `PARAM_B` | 2 | campaign | `b` not a positive integer |
| `H0_TOO_LOW` | 2 | campaign, item2 | the setup and funding blocks reach `H0` (item 2: G − 1, a second guard; ITEM2 `H0` ≥ 107: sections 18 and 20) |
| `MISMATCH TESTMEMPOOLACCEPT_REGISTER` | 2 | campaign | Node A or Node B does not accept the gate's REGISTER |
| `PREREQUISITE CLUSTER_TOOL_MISSING` | 3 | driver, campaign | the D2-2 file is missing (before any node, or after the last gate) |
| `PREREQUISITE CLUSTER_TOOL_TIMEOUT` | 3 | campaign | D2-2 ran past 3,600 seconds |
| `PREREQUISITE CLUSTER_TOOL_NOT_RUN` | 3 | campaign | D2-2 could not be started |
| `CLUSTER_TOOL_FAILED <exit>` | 2, 3, 4, 5, 6 | campaign | D2-2 exited non-zero, or 0 without output (on a failed prefix only exit 5 becomes the run's exit, D2-3c round 3) |
| `CLUSTER_OUTPUT_NOT_ASCII` | 2 | campaign | D2-2 exited 0 with output bytes that are not ASCII (round 2, P3-D) |
| `ANCHOR_PLACED_MISMATCH` | 2 | bidders | an ANCHOR_KEY group's placed members are not the group's winning wallets (round 1, P3-8) |
| `LOG_BOUND` | 2 | driver | a line would leave less than the RUN_END reserve (or RUN_END would pass 256 MiB) |
| `SECRET_IN_LOG` | 5 | driver, campaign | the log refused a line holding a run secret; the campaign raises it again, exit 5, when the line refused was the failed prefix's own `PREFIX_START` (the probe is then not called; U3 Part C, A #638 check P3-3) or `CLUSTER_TOOL` (D2-3c round 3, B decision; `RUN_END` keeps the first `code`) |
| `PREREQUISITE FUNDING_NOT_AT_MINER` | 3 | campaign | the funding transactions did not reach the miner's mempool within 120 s (U3 Part C, A #638 check P3-4; a node call's own `NODE_CALL_TIMEOUT` inside the wait is raised unchanged) |
| `PREREQUISITE BID_NOT_AT_MINER` | 3 | campaign | the gate's REGISTER did not reach the miner's mempool within 120 s (as above) |
| `PREREQUISITE DEADLINE_BEFORE_FIRST_GATE` | 3 | campaign | the gate-loop deadline (section 18) passed before the first gate started: no gate to judge (U3 Part C) |
| `DRAFT_FAULT` | 4 | campaign | the DRAFT test fault fired at its gate (D2-3c; never CONFIRMATORY) |
| `DRAFT_FAULT_IN_CONFIRMATORY` | 2 | campaign | a DRAFT test fault given to a CONFIRMATORY run, before any node |
| `DRAFT_FAULT_SHAPE` | 2 | campaign | a DRAFT test fault other than `{gate, when}` with a gate of the run and `when` `BEFORE_GATE_END` or `AFTER_GATE_END` |

**DRAFT test fault** (D2-3c). `campaign(..., draft_fault={'gate': g, 'when': 'BEFORE_GATE_END' |
'AFTER_GATE_END'})` is a Python-API-only parameter for tests and EXPLORATORY real-node rows: gate g raises
`DRAFT_FAULT` (exit 4) just before or just after its `GATE_END`. No command line (driver, campaign or
slices) sets it. `RUN_START` records it as `draft_fault` (null when unset). It is refused in CONFIRMATORY
and when malformed, before any node starts.

The driver prints `CLUSTER_TOOL_MISSING` (exit 3) without the `PREREQUISITE` prefix when it refuses before
any node starts; the campaign's own check, for a direct caller, raises the prefixed form.

**Placed ANCHOR_KEY members.** Each ANCHOR_KEY group of the ground truth gets `placed_wallets`: the winning
wallets whose REGISTER's `vout[1]` (read from the bytes) is the group key's script. At run time they must
equal the group's wallets that won a gate (D2-2's P_L-restricted group); otherwise a REGISTER carried
another key than the plan says (`ANCHOR_PLACED_MISMATCH`).

## 17. The pool run (D2-3a)

One POOL run is `gates_per_run` gates (A Q3: 4 per run, 50 runs; DEFAULT, PENDING_FREEZE), one PUBLIC *Dated line 2026-11-10 (B, FZ-6, C27 pointer; sources 045b :1194's C27 dated line and A #664 issuecomment-6746599499): frozen as 50 runs of 4 gates (045b :1901, section 14.21; :545), refused otherwise in CONFIRMATORY before any node (`POLICY_POOL_RUNS_GATES`, section 18).*
SYNTHETIC seat per gate, wallet `W<gate mod 40>` (DEFAULT), at rung 0 = `b`.

**Producer draw.** Every block of the run, setup blocks included, has a producer: the draw
`PRODUCER_H<height>` (section 6, experiment `POOL`, n = 100), `A` below 50, `B` below 80, else `C`; a
`DRAW` line records it. Three miner processes run on the miner node, one per producer, each with its own
whitelisted miner user (exactly section 1's miner set; the other nodes do not know these users). The
producer's process builds the block; `BLOCK` carries `producer`, and a block whose `producer` is not the
draw's is refused (`PRODUCER_MINER`).

**Tag.** The coinbase scriptSig is the BIP34 height push, an 8-byte extranonce push, then one direct push
of the 22 bytes `BITAGI_ARDR_PRODUCER_<A|B|C>`. A miner process refuses a producer for any policy but
`POOL_50_30_20`, and that policy refuses to run without one (`PRODUCER`).

**Reading the tag** (`coinbase_producers`; round 1, P3-3). The judge reads the producer from the block
bytes: the coinbase scriptSig is split into its data pushes in order: `OP_0` (an empty push),
`OP_PUSHBYTES_1` … `OP_PUSHBYTES_75` (0x01-0x4b), `OP_PUSHDATA1` (0x4c, a 1-byte length),
`OP_PUSHDATA2` (0x4d, a 2-byte little-endian length) and `OP_PUSHDATA4` (0x4e, a 4-byte little-endian
length); any other opcode carries no data and is skipped. A push whose length or data runs past the end of
the script is refused (`COINBASE_PUSH_TRUNCATED`). Bytes inside a push are data, never opcodes, so a tag
inside a longer push is not a tag. A tag is a push of exactly the 21 bytes `BITAGI_ARDR_PRODUCER_` and one
of `A`, `B`, `C`, in any push form. A block G with no tag or more than one is missing data: the judge
excludes and counts it (045b 4.5). `GATE_END` and the gate row carry `producer_tags`; `RUN_END` carries
`producers_description` (counts per producer and the missing count) as description only. The HHI is the
judge's, pooled over every pool gate (A Q3).

**Phase `POST_GATES`** (D2-3c; A 6548007197 For-A 1). After a pool run's last `GATE_END`, the ground
truth and `producers_description` run in phase `POST_GATES`; a failure there is `RUN_END FAILED` phase
`POST_GATES`, `cluster_failed` false, `cluster_prefix` `NOT_RUN` `NO_CLUSTER`, and the run's `GATE_END`
gates stay countable (section 16, POOL).

| Code | Exit | Raised by | When |
|---|---|---|---|
| `PRODUCER` | 2 | driver (miner) | a producer letter not A, B, C; a producer for another policy; POOL without one |
| `PRODUCER_MINER` | 2 | campaign | the block's producer is not the draw's |
| `MINER_USERS` | 2 | driver | further miner users on a node without a miner user |
| `BLOCK_NO_COINBASE` | 2 | campaign | a block without a transaction |
| `COINBASE_SHAPE` | 2 | campaign | a coinbase without exactly one input |
| `COINBASE_PUSH_TRUNCATED` | 2 | campaign | a scriptSig push runs past the script's end |

## 18. Policy params, `--method-policy` and the CONFIRMATORY refusals (D2-3a)

**`experiments.<E>.params`** (A Q6) for ITEM1 and POOL only: exactly `b` (1 … 2^32 − 1), `H0` (106 …
2^32 − 1: the 103 setup blocks and the two funding blocks come first; ITEM2 107 …, section 20) and
`gates_per_run` (1 … 200); any value may be a PENDING string. EXPLORATORY and PR_SMOKE runs of a policy without them take the DRAFT *Dated line 2026-11-10 (B, FZ-6, C27 pointer; sources 045b :1194's C27 dated line and A #664 issuecomment-6746599499): the frozen params are 045b :1901 (section 14.21: `b` 6,000, `H0` 1,000, `gates_per_run` ITEM1 200, POOL 4, ITEM2 1); the DRAFT params below stay EXPLORATORY and PR_SMOKE defaults.*
params (ITEM1 `b` 3,000, `H0` 110, 200 gates; POOL `b` 3,000, `H0` 110, 4 gates); a PENDING param refuses
every mode (a run needs numbers). The top-level `bidders` is not used by ITEM1, ITEM2 or POOL.

**Miner policy per experiment** (round 1, P2-1). `experiments.ITEM1.miner_policy` must be
`ITEM1_WINNER_ONLY` and `experiments.POOL.miner_policy` `POOL_50_30_20`; no other experiment may name
either. Every entry of the policy is checked, in every mode (a PENDING name is the PENDING rule's).

**`--method-policy <file>`** (ITEM1 only) names the method policy of section 15. **U3 (A Q3-Q4, 2026-11-01).**
The policy names that file in `experiments.ITEM1.method_policy` `{path, sha256}` (`path` a file of the
dispatched commit, `sha256` 64 lowercase hex or PENDING; only ITEM1's entry may hold the key, else exit 2
`POLICY_METHOD_POLICY`), so the registered policy hash binds the method file. CONFIRMATORY requires the key
(exit 3 `METHOD_POLICY_NOT_DECLARED`); whenever the policy names one, the file given must have its SHA-256
(exit 6 `METHOD_POLICY_SHA256`), and in CONFIRMATORY that SHA-256 is still matched against the registration
list too (no separate key, A Q4). Section 13's slice passes `--method-policy <path>` from the declaration.
**U3 run shape (A Q5 and A #636 decision (i), 2026-11-01).** The slice passes `--unit-seconds <unit_minutes x
60>` to every driver (other experiments ignore it). For ITEM1 and POOL the driver fixes, before any node starts,
a deadline from its own process start: `gate_loop_seconds` = the unit's limit − the D2-2 share (a node call 300
s, the worker's KEYS call 1,800 s, D2-2's `CLUSTER_SECONDS` 3,600 s; 5,700 s) − a 900 s margin (RUN_END, the
teardown, the slice's start-up). RUN_START carries `deadline` `{unit_seconds, d2_2_share_seconds,
margin_seconds, gate_loop_seconds, clock_ns, utc}` (`clock_ns` since the U3 pre-PR P3-3: the monotonic deadline
on the same clock as every line's `t_ns`, a number and not a secret, so collect can prove a stop from the log), or `null` for an EXPLORATORY or PR_SMOKE run without `--unit-seconds`
or with a limit not above 6,600 s. CONFIRMATORY needs it: exit 3 `UNIT_SECONDS_MISSING`, exit 6
`UNIT_SECONDS_SHORT` (plan refuses the same unit first, section 13 `UNIT_MINUTES_SHORT`); `--unit-seconds`
below 1 is exit 2 `UNIT_SECONDS`. The campaign starts the topology (the four nodes, the cookie probe, the
version check `NODE_VERSION`, the connect wait `NODES_NOT_CONNECTED`) BEFORE it writes RUN_START, so a setup
failure leaves an empty raw log: the unit is `BEFORE_START`, re-dispatchable, and the slice stops (section 13).
**Deadline stop (U3 Part C, A Q5; B default).** Before each `GATE_START`, when the run has a deadline and the
monotonic clock is at or past it, no further gate starts; the rule reads the clock only, never a result. The
run is not a failure: ITEM1 goes on to its CLUSTER phase (D2-2 over the gates done; the deadline already
reserves the D2-2 share) and POOL to `POST_GATES`, and `RUN_END DONE` carries `deadline_reached` true and
`gates_not_started` (always written: `false` and `[]` for a run the deadline did not stop). Collect marks
those gates `NOT_STARTED` `DEADLINE_REACHED` (missing, A Q2's 10% rule; section 13). A deadline passed before
the first gate is exit 3 `PREREQUISITE DEADLINE_BEFORE_FIRST_GATE` (section 16). Each `GATE_START`'s `t_ns` is
the clock reading the check used, so it is below `clock_ns`; the next line after the stop is stamped later. The 900 s margin does not
cover a gate in flight at the deadline (its worker build is bounded at 1,800 s): A decides at the freeze. *Dated line 2026-11-10 (B, FZ-6 fix round 1): A decided it, 045b :1903 (its dated line "A, freeze verification C28", a ruling for this line and :1727 by their numbers before #759, :1491-1492 and :1716): a gate already running at the gate-loop deadline runs to its own limits and is judged like any other gate if its records are complete in the collected log; if the runner's limit ends the run before collect, every gate without complete records counts as missing under the 10% rule, never as a success; B may widen the start margin in a tools unit only before the P5-005 registration, and after it a margin change needs a new registration.*

`--cluster-tool <file>`
(ITEM1 only, never CONFIRMATORY; round 1, P3-7) names another D2-2 file for an EXPLORATORY or PR_SMOKE run;
CONFIRMATORY runs the tree's own `tools/claude_track_ardr_cluster.py`, whose SHA-256 the `CLUSTER_TOOL`
line records.

**CONFIRMATORY**, all before any node starts and before the work directory is made: ITEM1 and POOL need
their params (exit 3), no PENDING anywhere (exit 3), ITEM1 exactly 200 gates per run (round 1, P3-5), the
method policy present, bound in the registration list and without PENDING, no `--cluster-tool`, and the
D2-2 file on the tree. ITEM2, ITEM3 and ITEM4 CONFIRMATORY runs still refuse
(`CONFIRMATORY_CAMPAIGN_NOT_BUILT`, exit 3).
*2026-11-10 (B-FZ-p round 2, Q-pol-4; A #258 issuecomment-6744913177): three early copies of what 045b and the [Dated line 2026-11-10 (B, FZ-6): the date 2026-11-10 of this B-FZ-p line is UTC 2026-11-09, A #759 issuecomment-6749449323, F3.]
judge bind, each refused before any node: the `--method-policy` file's thresholds must be 045b :434's [4, 15]
(every mode, as the judge's `METHOD_THRESHOLDS`; a PENDING one takes its DRAFT value); in CONFIRMATORY a POOL
run's count and `gates_per_run` must be 045b :545's 50 and 4 (the judge's `POOL_RUNS_GATES`), and the run's `b`
a multiple of 250 (045b F11, on #664), both in `load_policy`, so `check-policy` refuses them too. The thresholds check
reads the method file, which `check-policy` does not take.*

**PR smoke.** Besides section 13's ITEM2 smoke, a pull request runs one ITEM1 unit, run 0, driver mode
`PR_SMOKE`, through the same `plan`, `slice` and `collect` commands, with the draft policy
`tests/claude_track/ardr_pr_smoke_item1_policy_draft.json` (EXPLORATORY, a few gates; a CONFIRMATORY list
holds one id per gate, section 13, U3).

| Code | Exit | Raised by | When |
|---|---|---|---|
| `POLICY_MINER_EXPERIMENT` | 2 | driver | a miner policy that is not the experiment's variant (P2-1) |
| `POLICY_PARAMS` | 2 | driver | params with other keys or a value out of range |
| `POLICY_PARAMS_EXPERIMENT` | 2 | driver | params on an experiment other than ITEM1, POOL or ITEM2 (ITEM2 since D2-3b, section 20) |
| `POLICY_PARAMS_UNSET` | 3 | driver | CONFIRMATORY ITEM1 or POOL without params |
| `POLICY_PARAMS_PENDING` | 3 | driver | a PENDING param (any mode) |
| `POLICY_ITEM1_GATES` | 2 | driver | CONFIRMATORY ITEM1 with `gates_per_run` other than 200 (P3-5) |
| `POLICY_POOL_RUNS_GATES` | 2 | driver | (B-FZ-p round 2, Q-pol-4, 2026-11-10) CONFIRMATORY POOL whose `counts.POOL` is not 50 or whose `gates_per_run` is not 4 (045b :545, the judge's `POOL_RUNS_GATES`); `check-policy` and every run, before any node *Dated line 2026-11-10 (B, FZ-6): the date 2026-11-10 is UTC 2026-11-09 (A #759 issuecomment-6749449323, F3).* |
| `POLICY_B_NOT_MULTIPLE_OF_250` | 2 | driver | (B-FZ-p round 2, Q-pol-4, 2026-11-10) CONFIRMATORY whose run's `params.b` is not a multiple of 250 sat/kvB (045b F11, on #664); `check-policy` and every run, before any node *Dated line 2026-11-10 (B, FZ-6): the date 2026-11-10 is UTC 2026-11-09 (A #759 issuecomment-6749449323, F3); F11 is 045b :1140 on main since #664.* |
| ITEM2 `H0` ≥ 107: `H0_TOO_LOW` | 2 | driver | ITEM2 params with `H0` 106 (`check_params`: `check-policy` and every run, before any node; section 20) |
| `SEED_PENDING` | 3 | driver | an ITEM1 or POOL run with a PENDING seed (any mode) |
| `METHOD_POLICY_MISSING` | 3 | driver | CONFIRMATORY ITEM1 without `--method-policy` |
| `METHOD_POLICY_NOT_REGISTERED` | 6 | driver | the method policy's SHA-256 is not in the registration list |
| `METHOD_POLICY_NOT_DECLARED` | 3 | driver | CONFIRMATORY ITEM1 whose policy has no `experiments.ITEM1.method_policy` (U3) |
| `METHOD_POLICY_SHA256` | 6 | driver | the `--method-policy` file's SHA-256 is not the one the policy names (U3) |
| `METHOD_THRESHOLDS` | 2 | driver | (B-FZ-p round 2, Q-pol-4, 2026-11-10; the B-FZ-pol note's patch) the `--method-policy` file's `thresholds` (a PENDING one: its DRAFT value) are not 045b :434's [4, 15], which the judge binds; every mode, before any node *Dated line 2026-11-10 (B, FZ-6): the date 2026-11-10 is UTC 2026-11-09 (A #759 issuecomment-6749449323, F3).* |
| `POLICY_METHOD_POLICY` | 2 | driver | `method_policy` outside ITEM1's entry, or not `{path, sha256}` (U3) |
| `UNIT_SECONDS_MISSING` | 3 | driver | CONFIRMATORY ITEM1 or POOL without `--unit-seconds` (U3, A Q5) |
| `UNIT_SECONDS_SHORT` | 6 | driver | CONFIRMATORY ITEM1 or POOL whose `--unit-seconds` is not above 6,600 s (U3) |
| `UNIT_SECONDS` | 2 | driver | `--unit-seconds` below 1 (U3) |
| `METHOD_POLICY_OUTSIDE_ITEM1` | 2 | driver | `--method-policy` for another experiment |
| `CLUSTER_TOOL_OUTSIDE_ITEM1` | 2 | driver | `--cluster-tool` for another experiment |
| `CLUSTER_TOOL_IN_CONFIRMATORY` | 2 | driver, campaign | `--cluster-tool` (or another D2-2 file) in CONFIRMATORY (P3-7) |
| `CLUSTER_TOOL_MISSING` | 3 | driver | the D2-2 file is not on the tree (or not the named file) |
| `ITEM1_WINNER_MISSING` | 2 | driver (miner) | the winner is not a candidate at block G, or the filter or the weight cut drops it |
| `GATE_CONTEXT` | 2 | driver (miner) | a malformed gate context |
| `GATE_CONTEXT_POLICY` | 2 | driver (miner) | a gate context for a policy other than `ITEM1_WINNER_ONLY` |
| `GATE_HEIGHT` | 2 | driver (miner) | a gate context for another height |
| `GATE_WINNER_NOT_REGISTER` | 2 | driver (miner) | the winner is not among the gate's REGISTERs |

## 19. The reader node's cookie (D2-3a, A Q7)

In an ITEM1 run, Node A is the reader node. A's three conditions:

1. Node A's cookie user is whitelisted for exactly D2-2's `READ_RPCS`: `getblockchaininfo`, `getblockhash`,
   `getblock` (`-rpcwhitelist=__cookie__:getblock,getblockchaininfo,getblockhash`). Every other node's
   cookie line is empty (refused for everything), as before; a set wider than `READ_RPCS` is refused when
   the node is built (`COOKIE_RPCS`).
2. The driver never calls with the cookie. Its only cookie call is the start probe that the cookie is
   refused; on Node A the probe is `getnetworkinfo`, outside `READ_RPCS` (a probe inside the cookie set is
   refused, `COOKIE_PROBE`), so the driver reads nothing with it. Only D2-2's subprocess uses the cookie,
   through `bitcoin-cli -datadir`, which reads it from the node's data directory.
3. The real-node cells: on Node A all three `READ_RPCS` calls work as D2-2 makes them (`getblockchaininfo`,
   `getblockhash 0`, `getblock <hash> 0`) and every call outside them is refused with 403
   (`getnetworkinfo`, `getrawmempool`, `sendrawtransaction`, `stop`, `getblocktemplate`, `getblockheader`,
   `submitblock`); on the miner, relay and Node B every cookie call is refused with 403, the three
   `READ_RPCS` calls and `getnetworkinfo` included.

D2-2's output bytes and their SHA-256 go into the raw log (`CLUSTER_TOOL`), so section 13's record format
does not change.

| Code | Exit | Raised by | When |
|---|---|---|---|
| `COOKIE_RPCS` | 2 | driver | a cookie set that is not a subset of `READ_RPCS` |
| `COOKIE_PROBE` | 2 | driver | the cookie probe method is in the node's cookie set |
| `MISMATCH COOKIE_NOT_REFUSED <role>` | 2 | driver | the probe was not refused with 403 |

## 20. The item-2 run (D2-3b)

Status: D2-3b of the CT-P5-001 driver (A #258 -6543158220 Q4 and Q5; A -6546351822). Class T Regtest
development evidence only; every value is PENDING_FREEZE / DRAFT. The tool is
`tools/claude_track_ardr_item2.py`; the tests are `tests/claude_track/test_ardr_item2.py`.

**Routing.** `run --experiment ITEM2` with `experiments.ITEM2.params` runs the item-2 run (EXPLORATORY,
PR_SMOKE); without params it stays section 13's D1 smoke. ITEM2 CONFIRMATORY is still refused
(`CONFIRMATORY_CAMPAIGN_NOT_BUILT`, exit 3): 045b 4.5 counts PROJECT attempts, so D3a-1 comes first. ITEM2
params are section 18's with `gates_per_run` exactly 1 (`POLICY_ITEM2_GATES`).

**H0 (Codex r4433308775, A 6549379243).** Item 2 needs `H0` ≥ 107 (`ITEM2_MIN_H0` = section 18's
`MIN_H0` + 1): the setup blocks (to 103) and the funding blocks (104, 105) come first, then block G − 1 is
prepared on its own. `H0` = 106 is refused for ITEM2 with `H0_TOO_LOW` (exit 2) by the driver's
`check_params` (so `check-policy` refuses it too) and again by `plan_run`, before any node starts and before
`--work` or `--out` is written. The run-time check after the funding blocks stays as a second guard.

**The mapping (A Q4).** One run is one contested gate of a new chain, r = 0 … 199, at height G = `H0`; the
bidder list has one gate numbered r. Seats `S0`-`S4` hold wallets `W00`-`W04` (SYNTHETIC). Even r: `S0` is
PRIVATE, `S1`-`S4` PUBLIC; r = 0, 2, …, 98 are the 50 order-constrained runs (`PRIVATE_FEE`, n = b + 1, private
feerate p = b + value; `PUBLIC_FEE_j`, n = 4b − p + 1, public feerate p + value); r = 100 … 198 draw `BID_FEE_j`
(n = 3b + 1). Odd r: five PUBLIC seats, `BID_FEE_0…4`. The L0 seat is A's at the freeze with D3a-1 *Dated line 2026-11-10 (B, FZ-6, C27 pointer; sources 045b :1194's C27 dated line and A #664 issuecomment-6746599499): the freeze set it, 045b :1219 (F2: public seat S1 in all 200 runs, `experiments.ITEM2.l0_seat.seat` 1) in the F3 L0 policy keys (045b :1194).*
(`l0_seat` `PENDING_FREEZE` in RUN_START; section 22 adds a DRAFT `l0_seat` parameter). A run whose five
ladders are all empty is refused before any node
(`RUN_GATE_NO_BID_G<r>`, exit 2, as section 9).

**The time rule (A Q5).** One clock: the driver's `CLOCK` (CLOCK_MONOTONIC), shared with the miner process
on one host. t_G = `GATE_INTERVAL` + 1 s. The rung numbers released are fixed from t_G before any node
starts: k with 60k < t_G (rung 0 always). Each bidder's ladder (section 9, `i` = the larger of Node A's and
Node B's `incrementalfee`, D3a-2b-1) is fixed before block G − 1; the release steps are `SCHEDULE`'s `rounds` and the predicted
candidate count their sum.

1. Block G − 1 is built by the miner process without sending it (`prepare`); every bidder's ladder is built
   on its hash in one worker call (a REGISTER is built on G − 1: BUILD's tip), then G − 1 is sent
   (`submit`). t0 = its `t_submit_ns`.
2. Rung 0: once G − 1 is at the relay node (and at Node A and Node B, whose testmempoolaccept needs it;
   the four-node wait polls every 0.02 s). Rung k ≥ 1: at t0 + 60k.
3. Each release: testmempoolaccept of the rung on Node A and Node B (not allowed →
   `TESTMEMPOOLACCEPT_REGISTER` for rung 0, `TESTMEMPOOLACCEPT_REPLACEMENT` after, the run FAILED). For a
   PUBLIC rung k ≥ 1 the driver first waits, polling every 0.02 s for up to `REPLACED_WAIT_SECONDS` (5 s,
   DEFAULT), until rung k − 1 is in Node A's and Node B's `getrawmempool`, so the test is a replacement
   test; if it is still missing at either node, the rung is neither tested nor sent and the gate is EXCLUDED
   (`REPLACED_RUNG_NOT_IN_MEMPOOL`, `REPLACED_RUNG_MISSING` logged; no block G is mined). A PRIVATE rung does
   not wait (the miner process's `replace` checks the held txid). Then the hand-off: PUBLIC with the relay's
   `sendrawtransaction` (rung k replaces rung k − 1: the same funding output), PRIVATE to the miner process
   (rung 0 `private`, rung k ≥ 1 `replace`).
4. After each release step every node's mempool is logged (`RELEASE_MEMPOOLS`): the relay log.
5. Block G: its template is taken no earlier than t0 + t_G (`mine(at_ns=…)`); `G_TIMING` logs the lag.
   Block G's `MEMPOOL` lines (`before_block` true) are taken before that wait (`mine`'s snapshots come
   before `sleep_until`), that is right after the last release step, not at t0 + t_G.

The four nodes run with `-whitelist=in,out,noban@127.0.0.1` (A Q5: loopback noban accepted), so a relayed
rung skips Core's inv trickle. Only the item-2 topology sets it.

**Miner process commands (D2-3b).** `prepare` builds a block from the template and the private set and keeps
it unsent (one at a time: `MINER_BLOCK_PREPARED`); `submit` sends the kept block (`MINER_NO_PREPARED_BLOCK`
without one). `replace` takes a transaction that spends an input of exactly one held private transaction:
that one leaves the private set, the new one is held (`PRIVATE_REPLACE_CONFLICT` otherwise; nothing
changes). The `block` command is unchanged.

**RELEASE_NOT_IN_TEMPLATE (A -6546351822).** Only each bidder's LAST released rung is checked: a PUBLIC one
must be in block G's template, the PRIVATE one in the private set the miner process added at G. A miss
EXCLUDES the gate: `GATE_END` status `EXCLUDED` with the code and `misses`, `RUN_END` status `EXCLUDED`, exit
2. It counts in the 10% rule and is left out of section 4.5's first-row comparison. Earlier rungs are
observation candidates from the relay log, not checked against the template. `RELEASE_AFTER_G` (WR23b): a
release whose `sent_ns` (the CLOCK reading just before its hand-off) is at or after t0 + t_G EXCLUDES the
gate the same way (045b 4.6: rungs are released while block G has not been produced; the prediction counts
rungs released strictly before t_G); `GATE_END` lists them in `late_releases` (`seat`, `txid`, `k`,
`sent_ns`, `due_ns`, `g_due_ns`). `G_LATE` (DEFAULT, B): block G's template taken 1 s or more after t0 + t_G
EXCLUDES the gate the same way. One code per gate, in this order: `RELEASE_NOT_IN_TEMPLATE`, then
`RELEASE_AFTER_G`, then `G_LATE` (`gate_code`).

**Topology check (WR23b).** The item-2 run refuses, before the worker or any node starts and before
`RUN_START`, a topology whose four nodes do not each carry exactly the loopback noban whitelist
(`ITEM2_TOPOLOGY_WHITELIST`); `RUN_START` logs each node's real P2P arguments (`p2p_arguments`).

**Raw-log events** (section 2's line; `unit` gate = r from `GATE_START` on):

| Event | Fields |
|---|---|
| `RUN_START` | as section 16, with `gates` [r], `private_present`, `order_constrained`, `bidders_sha256`, `t_gate_seconds`, `rung_seconds`, `release_ks`, `l0_seat` and `l0_seat_source` (section 22; `REGISTERED_POLICY` in CONFIRMATORY, section 26; `POLICY_VALUE` outside CONFIRMATORY with a policy's `l0_seat`, B-FZ-a), `schedule_source` (`GATE_INTERVAL_DRAW`, or `DRAFT_OVERRIDE`), `p2p_arguments` (role → the node's P2P whitelist arguments) |
| `DRAW` | the `GATE_INTERVAL` draw, `applied` false under an override |
| `BIDDERS` | the list, its SHA-256, the fee draws (`label`, `n`, `k`, `value`, `feerate`) and the five feerates |
| `SCHEDULE` | `increment` (the synthetic ladders' i: the larger of Node A's and Node B's `incrementalfee`, D3a-2b-1), `increments` (Node A's and Node B's, D3a-1b), `increment_rule` (`MAX_NODE_A_NODE_B`), `ladders`, `rounds` (`k`, `offset_seconds`, `seats`), `predicted_candidates` |
| `GENERATED` | per bidder, as section 12 (every rung) |
| `TESTMEMPOOLACCEPT` | as section 12, with `rung` and `replaces_in_mempool` (whether rung k − 1 was in that node's mempool; null for rung 0 and PRIVATE rungs) |
| `REPLACED_RUNG_MISSING` | `seat`, `k`, `txid`, `replaces`, `replaces_in_mempool` (A, B), `waited_seconds` |
| `PRIVATE_HANDOFF`, `PUBLIC_SENT` | as section 12 |
| `PRIVATE_REPLACE` | `txid`, `replaced`, `hex`, `seat`, `kind` |
| `RELEASE` | `seat`, `path`, `k`, `txid`, `fee`, `replaces`, `due_ns`, `sent_ns`, `lag_ns`, `handed_off` (and `fault` in a fault-injected test) |
| `RELEASE_MEMPOOLS` | `k`, every node's mempool txids |
| `G_TIMING` | `t0_ns`, `due_ns`, `template_ns`, `submit_ns`, `lag_ns`, `t_gate_seconds` |
| `GATE_END` | `status` (`OBSERVED` or `EXCLUDED` with `code`), `observation_id` (`OBS-2<r:07>`, the run-level id: the unit is the run), `born`, `winner` (seat), `predicted_candidates`, `observed_candidates` (public rungs the relay's mempool held after a release step, plus the private rungs the miner process took), `last_rungs`, `misses`, `late_releases`, `order`, `next_birth`, `code_seats` (the seats behind `code`, section 22), `l0_seat` and `l0_attempt_id` (null without the L0 seat); under `REPLACED_RUNG_NOT_IN_MEMPOOL` `block_hash` null, `born` [] and `replaced_missing` |
| `RUN_END` | `DONE`, `EXCLUDED` (above) or `FAILED` (`code`, `phase` SETUP / GATE / END, `excluded_gates` [r]) with `timing` (`setup_ns`, `build_ns`, `release_ns`, `mine_ns`, `mine_blocks`, `birth_ns`, `birth_calls`, `g_lag_ns`, `total_ns`) |
| `L0_STOP_FAILED` | with the L0 seat only (section 22, D3a-1a): `code` (the stop's), `failure` (the run's own code, which is raised) |

**Tests only.** `plan_run(override={"t_gate_seconds", "rung_seconds"})` shortens the schedule for tests and
exploration (Python only; not in the driver CLI or the policy); refused in CONFIRMATORY with every other
item-2 run. `plan["fault"]` (`{"seat", "k"}`) logs one rung as released without handing it off, so a test can
reach RELEASE_NOT_IN_TEMPLATE on real nodes.

| Code | Exit | Raised by | When |
|---|---|---|---|
| `POLICY_ITEM2_GATES` | 2 | driver | ITEM2 params with `gates_per_run` other than 1 |
| `CONFIRMATORY_CAMPAIGN_NOT_BUILT` | 3 | driver, l0 | an ITEM3 CONFIRMATORY run, or any CONFIRMATORY run of the L0 module's DRAFT CLI (D3a-2b-2b: ITEM2 and item-4 CONFIRMATORY run the L0 seat through the driver, section 26) |
| `ITEM2_RUN` | 2 | item2 | a run index outside 0-199 |
| ITEM2 `H0` ≥ 107: `H0_TOO_LOW` | 2 | driver, item2 | `H0` 106 (`check_params`, then `plan_run`, before any node); the setup and funding blocks reach G − 1 (a second guard) |
| `ITEM2_SCHEDULE` | 2 | item2 | t_G or the rung spacing not a positive integer |
| `ITEM2_SCHEDULE_OVERRIDE` | 2 | item2 | a malformed schedule override |
| `GATE_NO_BID` | 2 | item2 | no seat has a non-empty ladder at G (a defence after the plan check) |
| `ITEM2_PREPARED_HEIGHT` | 2 | item2 | the prepared block is not at G − 1 |
| `ITEM2_PREPARED_HASH` | 2 | item2 | the block sent is not the prepared one |
| `ITEM2_RELEASE_AFTER_G` | 2 | item2 | a release step due at or after t0 + t_G (unreachable from the plan) |
| `WORKER_RUNG` | 2 | item2 | the BUILD answer's rungs do not match the request |
| `WORKER_TXID` | 2 | item2 | a rung's txid, number or fee is not the requested one |
| `CANDIDATE_VSIZE` | 2 | item2 | a rung's vsize is not 213 |
| `RUNG_FUNDING` | 2 | item2 | a rung does not spend exactly the bidder's funding output |
| `MISMATCH TESTMEMPOOLACCEPT_REPLACEMENT` | 2 | item2 | Node A or Node B does not accept a rung k ≥ 1 |
| `PRIVATE_REPLACE_TXID` | 2 | item2 | the miner process replaced another txid than the bidder's rung k − 1 |
| `MISMATCH PRIVATE_IN_MEMPOOL` | 2 | item2 | a held private txid in a node's mempool after a release step |
| `RELEASE_NOT_IN_TEMPLATE` | 2 | item2 | a bidder's last released rung is not in G's template / private set (gate EXCLUDED) |
| `RELEASE_AFTER_G` | 2 | item2 | a release sent at or after t0 + t_G (gate EXCLUDED; after RELEASE_NOT_IN_TEMPLATE, before G_LATE) |
| `G_LATE` | 2 | item2 | block G's template taken 1 s or more late (gate EXCLUDED) |
| `REPLACED_RUNG_NOT_IN_MEMPOOL` | 2 | item2 | a public rung k − 1 not in Node A's or Node B's mempool within 5 s before rung k's test (gate EXCLUDED) |
| `ITEM2_TOPOLOGY_WHITELIST` | 2 | item2 | the topology's four nodes do not all carry the loopback noban whitelist (before anything starts) |
| `PRIVATE_REPLACE_CONFLICT` | 2 | driver (miner) | a replacement that does not conflict with exactly one held private transaction |
| `MINER_BLOCK_PREPARED` | 2 | driver (miner) | a block is built while a prepared one is not sent |
| `MINER_NO_PREPARED_BLOCK` | 2 | driver (miner) | `submit` without a prepared block |

The L0 seat's codes (D3a-1a), among them `ITEM2_L0_FEE_INPUT`, `ITEM2_L0_LADDER_EMPTY`, `L0_DEADLINE` and
`L0_PREVIOUS_THREAD_ALIVE`, have their one row in section 22's table (a code has one row in sections 14 and
after).

## 21. Time limits and the work path (U4)

Class T Regtest development evidence only; every value is PENDING_FREEZE / DRAFT. Sources: A's #632
check 6548007197 (P3-7), B's unit draft 6549262924 (U4), A's answer 6549827052.

**Time limits.** Every `bitcoin-cli` call the driver makes on a node (`RoleNode`: the cookie probe, the
password on standard input, a long argument on standard input) keeps its 300-second limit, and each worker
call (`cargo test ... ardr_bidder_generator`) its 1,800-second limit. A call past its limit ends the run as
a missing prerequisite (exit 3), never as an internal error (exit 4); it is not retried and the limit is not
extended. The code holds code words only (the role, never the command line or a path). In the miner process
the code crosses to the driver as `MINER PREREQUISITE NODE_CALL_TIMEOUT MINER` (exit 3). The campaign and the
item-2 run write it in RUN_END FAILED (sections 16 and 20) and tear down; D1's smoke writes RUN_END only as
DONE, so it tears down without a RUN_END line, as for every other prerequisite. A wait that names its own
timeout (`BLOCK_NOT_ACCEPTED`, `NODES_NOT_CONNECTED`, `PUBLIC_NOT_AT_MINER`, and the throughput tool's
`LAUNCH_TX_NOT_AT_MINER`) passes a node call's timeout through unchanged.

**The gate-loop deadline** (U3, A Q5; section 18). The campaign's deadline stop reads the same monotonic clock
as these limits; it does not shorten or retry any call, and a gate already running at the deadline runs to
its own limits (the 900-second margin does not cover it: A at the freeze). Collect checks the deadline and the *Dated line 2026-11-10 (B, FZ-6 fix round 1): "A at the freeze" is decided, 045b :1903 (C28; the ruling is quoted at :1494).*
stop from the log (section 13, "Gate states").

**The work path.** `--work` is a raw-log needle (section 2). The driver refuses a relative `--work`
(`./w` would be the needle `w`) before it reads the policy or starts any node, and the raw log refuses any
needle shorter than 8 characters before its file exists. Every caller passes an absolute path (the
workflow's `--work-root "$RUNNER_TEMP/..."` through `slice`).

| Code | Exit | Raised by | When |
|---|---|---|---|
| `PREREQUISITE NODE_CALL_TIMEOUT <role>` | 3 | driver | a node call (`RoleNode`) ran past 300 seconds; role `MINER`, `RELAY`, `A` or `B` |
| `PREREQUISITE WORKER_TIMEOUT` | 3 | bidders | a worker call ran past 1,800 seconds |
| `PREREQUISITE PORT_COLLISION <role>` | 3 | driver | a node's first call (`-rpcwait`) failed and the node's own process had exited (10 s grace) with Core's "Unable to bind" in its debug log's last 64 KiB: a bind failure (#682); role `MINER`, `RELAY`, `A` or `B` |
| `PREREQUISITE NODE_EXITED <role>` | 3 | driver | the same, without a bind-failure line (#682) |
| `PREREQUISITE PORT_DRAW` | 3 | driver | a topology's port draw got no new port after `count + 64` sockets (#682) |
| `WORK_NOT_ABSOLUTE` | 2 | driver | `--work` is not an absolute path (before the policy read, any node or any output) |
| `NEEDLE_TOO_SHORT` | 2 | driver | a raw-log needle is shorter than 8 characters (before the raw-log file exists) |

## 22. The L0 project seat in item 2: rung 0 (D3a-1a), its whole ladder (D3a-1b)

Status: D3a-1a and D3a-1b of the CT-P5-001 driver (B #258 -6550996612, -6551963734; A -6551547851 Q1, Q2, Q7;
A -6552107427 Q-L1 to Q-L4). Class T Regtest development evidence only; every value is DRAFT /
PENDING_FREEZE. Section 21 is U4's (#636, merged). The tool is `tools/claude_track_ardr_l0.py`, a library with
a DRAFT CLI (`run`, below). The item-2 lines are in
`tools/claude_track_ardr_item2.py`, and the tests are in `tests/claude_track/test_ardr_l0.py`. The unit
note is `docs/claude-track/plans/notes/CT-P5-001_DRIVER_EN/2026-11-01_d3a-1a-l0-seat.md`.

**The seat.** `plan_run(…, l0_seat=j)` is a DRAFT parameter, like `override`. It is not in the driver CLI
or the policy; the L0 tool's own DRAFT CLI takes it (`--l0-seat`, D3a-1b). Seat `Sj` becomes the L0 project bidder: kind `L0_PROJECT`, wallet
`L0`, `PUBLIC`.
- `j` must be a seat index 0-4 (`ITEM2_L0_SEAT`). It may not be seat 0 of an even run, which is the
  private seat (`ITEM2_L0_SEAT_PRIVATE`).
- The run's `H0` must be 1000 (`ITEM2_L0_H0`). That is oe's `GATE`. L0's Class T profile and the
  item-2 replay's are both `BITAGI\x01 ‖ genesis ‖ rules_hash ‖ u64be(H0)` on the Regtest genesis, so
  they are one deployment only at H0 = 1000 (A Q2: every item-2 run uses H0 = 1000). H0 = 1000 passes
  `check_params` (≥ 107) and `plan_run`, and the release schedule does not depend on H0.
- `L0_SEAT` stays `PENDING_FREEZE`; A sets the seat at the freeze. D3a-2b-2b (section 26): ITEM2 *Dated line 2026-11-10 (B, FZ-6, C27 pointer; sources 045b :1194's C27 dated line and A #664 issuecomment-6746599499): A set it, 045b :1219 (F2, seat 1) and :1194 (the F3 L0 policy keys row); `L0_SEAT` itself stays the DRAFT / EXPLORATORY default.*
  CONFIRMATORY runs the L0 seat through the driver's CLI only, on the registered policy's
  `experiments.ITEM2.l0_seat.seat` (section 26; without the key the driver refuses `L0_FREEZE_PENDING`, exit 3,
  before any node). `RUN_START` logs `l0_seat` (j, or `PENDING_FREEZE`) and `l0_seat_source`: `REGISTERED_POLICY`
  (a CONFIRMATORY run, the policy's seat), `POLICY_VALUE` (B-FZ-a: a run outside CONFIRMATORY with a policy's
  `l0_seat` values, the L0 CLI's `--policy-l0-seat`), `DRAFT_PARAMETER` (the Python API's seat) or
  `PENDING_FREEZE` (no seat).
- The L0 seat draws no fee (A Q1; to be recorded at the freeze). Its `BID_FEE_j` or `PUBLIC_FEE_j` label *Dated line 2026-11-10 (B, FZ-6, C27 pointer; sources 045b :1194's C27 dated line and A #664 issuecomment-6746599499): recorded, 045b :1052 (the L0 seat takes no `BID_FEE` draw; it amends 045b :535 and the draw table :556).*
  is not drawn, and its feerate is null in `BIDDERS`. Every other seat's draw is the one without L0,
  since each label is drawn on its own.
- `SCHEDULE` gives the L0 seat its conflict set as its ladder (D3a-1b, below; D3a-1a gave it `[null]`, one
  rung). Its released rungs count in `predicted_candidates` like any bidder's.
- The run needs `item2_run(…, l0=<L0Seat>)` exactly when the plan has `l0_seat` (`ITEM2_L0_ADAPTER`).

**Topology.** Node A (31.1) and Node B (30.3) are `oe.Pair` nodes (`L0Node`, a subclass in the tool),
so the launch host reads them with oe's public Class T fixture read user, and step 8 submits with oe's
send user.
- Each also has one more user, `bitagi-ardr-l0-read`, whitelisted for exactly `getrawmempool` and
  `testmempoolaccept` (item 2's reads on A and B), and the loopback noban whitelist (section 20).
- Both come after oe's own argv, through oe.Node's extra-argv hook (`miner_lines`). No byte of oe
  changes, and oe's driver user keeps `ALLOWED_RPCS`.
- Calls of those two methods go through the new user; every other call goes through oe's driver user.
- The miner and the relay are item 2's D1 `RoleNode`s. The relay connects to the miner; A and B connect
  to the relay, and B to A (oe.Pair's link).

**Chain.**
- Block 1 is mined to oe's `FUNDING_DESCRIPTOR` on Node A (`generatetodescriptor`; `L0_FUNDING_BLOCK`).
  Its coinbase is L0's funding, which `oe.chain_facts` reads at height 1.
- Item 2's setup then runs unchanged from height 2: its setup blocks to 104, the fan-out at 105, the
  owner funding at 106, then blocks to H0 − 2. All of these are D1 template blocks.
- Every run of this mode has the L0 seat, so every run has this layout (A Q2: equal conditions per run).
  A run without `l0_seat` is D2-3b's mode and keeps D2-3b's layout. One campaign uses one mode.

**L0's attempt.** One attempt per run, `L0ATT-<observation id>-<attempt:02d>`, attempts counted from 1. D3a-1a
ran `oe.run_l0` (one candidate, rung 0) in a thread with five scoped patches of oe; D3a-1b retires that path for
the item-2 seat: `L0Seat` runs the set workers itself, in `oe.l0_chain`'s order (`MIRRORS`), and patches
nothing. Between the stages it makes oe's checks in their per-rung form (`CHECKS_MIRRORED`, WRD3a1b P3-4), except
four it leaves out on purpose (`DEVIATIONS`, under "Checks per rung"). The driver sends item 2's G − 1 only after `L0_READY` (every rung signed); G − 1 is L0's floor block,
and t0 is its send time. The driver waits for L0's last release after its own release steps, before block G.
- **Cleanup** (WRD3a1a P2-1, P3-2, kept). The run's cleanup stops L0 before the nodes: no new stage starts,
  and `stop` waits `FINISH_SECONDS` or up to the attempt's deadline (`READY_SECONDS` + `FLOOR_SECONDS` +
  `FINISH_SECONDS`, 2,700 s from `L0_LAUNCH_START`, on `L0Seat.monotonic`) plus 30 s, whichever is longer.
  Each worker stage is bounded by the time left, never more than oe's own 1,800 s; a stage due after the
  deadline is `L0_DEADLINE`. Not bounded by the deadline: oe's prestate subprocess (`PRESTATE_SECONDS`,
  300 s), each node call (300 s), `Pair.agreed`'s wait and the relay poll (5 s); one of them hung near the
  deadline can outlive the grace, and is then contained: a thread still alive is `L0_THREAD_ALIVE`, and every
  later `L0Seat.start` in the process is refused (`L0_PREVIOUS_THREAD_ALIVE`) until that thread has ended.
  When the run is already failing, a stop failure never replaces the run's own error: it is logged
  (`L0_STOP_FAILED`) and chained to it (`__context__` and a note), and the run's error is raised. The ladder
  seat patches nothing, so no patch outlives a stop.
- **Node calls** (WRD3a1a P3-3, kept). A call on Node A or Node B through `L0Node.call` or its read user, made
  by item 2 or the seat, that runs past 300 s is `PREREQUISITE NODE_CALL_TIMEOUT A` or `B` (exit 3); the
  seat's own `getmempoolentry` reads (`raw`) map a timeout the same way. Inside L0's thread it reaches the run
  through `ready` or `finish`.

**L0's ladder (D3a-1b).** Since D3a-1b the L0 seat releases its whole replacement ladder, a 045a §1.3 conflict
set (R2), not one rung (B #258 -6551963734, the D3a-0 real-node result; A -6552107427 Q-L1 to Q-L4). The unit
note is `docs/claude-track/plans/notes/CT-P5-001_DRIVER_EN/2026-11-01_d3a-1b-l0-ladder.md`.
- **The set.** `l0_set(b, i)` is the bidders' own `ladder(p_0, b, i, v)` (`item2.l0_ladder`, the single
  source, 045b :537): `f_0 = ceil(p_0 v / 1000)`, then `f_k = max(ceil(ceil(p_0 3^k / 2^k) v / 1000), f_(k−1) +
  max(1, ceil(i v / 1000)))`, ending before the first rung with `f_k × 1000 > 4b × v` or after rung 7. Its only
  inputs are p_0 = ceil(2.5 b), i (the larger `incrementalfee` of Node A and Node B, read every run), v (213 vB)
  and k. At b 3,000 and i 100 it is [1598, 2397] sat.
- `item2.check_l0_set` refuses a set the wallet would refuse (`ITEM2_L0_SET_REFUSED`): more than 8 rungs
  (`max_rungs_per_conflict_set`), or a rung above the draft `max_fee_per_candidate_sat` (100,000 sat).
  *2026-11-09 (B-FZ-p fix round 1, pre-PR review P3-2): since B-FZ-p the cap is A's frozen Class T L0
  record's `max_fee_per_candidate_sat`, 30,000 sat (`item2.L0_MAX_FEE_PER_CANDIDATE_SAT`; a cell ties it to
  the record's bytes): at b 140,000 rung 0 (74,550 sat) is already refused.*
  `plan_run` checks the set with i = 0 before any node (its fees are the least any i gives); `L0Seat.start`
  checks it again with the real i, before any stage.
- `SCHEDULE` gives the L0 seat its set as its ladder. Its rungs released at all are item 2's rule for every
  bidder: rung 0 at t0, rung k ≥ 1 at t0 + `rung_seconds` × k, only while `rung_seconds` × k < t_G. So
  `predicted_candidates` counts them like any bidder's.
- **Charged before rung 0 is signed** (045a item 7). One process (`launch_set_charge_stage_worker`) reserves
  the whole set, hands off and charges every rung, under the draft budget record (*2026-11-09: A's frozen
  Class T L0 record since B-FZ-p*). The set's fees and its
  declared `r_inc` (= i) reach it as two more launch-facts lines after D3a-1a's two: `l0_set_fees=<f_0>,…`
  and `l0_set_rinc=<i>`; the named sign stage also gets `l0_sign_entry=sign-input-<64 hex>.txt`
  (`crates/bitagi-signer/tests/launch_host_e2e_sign.rs` `set_lines`). The stages still read one environment
  value, the facts path (rn-1). Without the set lines every earlier facts file parses as before.
- **Signed at H0 − 2.** The set charge writes every rung's sign base for H0 − 2, and the host signs only at
  a base's own tip (`crates/bitagi-launch-host/src/sign_input.rs` tip lines). So every rung is signed before
  G − 1: for each k, `set_sign` (the host's Sign hand-off), the named offline sign stage, and for rung 0 only
  `set_wait` (the import below H0 − 1). A signed rung that is not imported waits for its signature
  (`OfflineSignaturePending`) and acts on nothing; an imported rung's candidate line must carry its bytes
  (`crates/bitagi-launch-host/src/candidates.rs` `bind`).
- **Released at its time.** After G − 1: rung 0's `set_send` (its H0 − 1 comparison, then step 8 to Node A and
  Node B). For each rung k ≥ 1 to release: right after rung k − 1's release, `set_ready` (rung k imported, its
  H0 − 1 comparison, the turns to the broadcast authority; the operator's authorization written, not
  presented); then at t0 + `rung_seconds` × k, `set_send` (the authorization presented with the transport; it
  ends on the turn whose act submitted rung k). Any rung's pending comparison ends a run, and the tool
  compares it (`oe.run_prestate`). The driver never builds, prices or hands off an L0 rung, and nothing goes
  to the relay.
- Rungs with `rung_seconds` × k ≥ t_G are charged but not released (A Q-L4: 045a is not changed, so the
  exposure is the whole set from the start).
- **Checks per rung.** Before its step 8 (after its last phase before it) the rung is in neither node's mempool
  (`L0_SENT_BEFORE_STEP_8`). After it, both nodes hold it (`L0_RUNG_NOT_IN_MEMPOOL`) and no longer hold rung
  k − 1 (`L0_RUNG_NOT_REPLACED`); the relay is polled for it up to 5 s (`L0_RELAY`, which counts it in
  `observed_candidates`). Step 8's bytes are the export's (`L0_BYTES`).
- **oe's checks between the stages** (WRD3a1b P3-4; `CHECKS_MIRRORED`, each at its `oe.l0_chain` line). After the
  set charge `launch/handoff/` is exactly the set's files (`L0_SET_HANDOFF`) and the outbox empty
  (`L0_OUTBOX`). After each `set_sign` the outbox holds exactly the rungs' sign inputs so far (`L0_SET_OUTBOX`)
  and no file under the work directory holds a key file's scalar line (oe's `scan_key_material`, as after each
  signer stage). After each named sign stage the launch tree is exactly `export`, `handoff`, `host`, `outbox`
  (`L0_SET_DIR`), `export/` exactly the exports so far (`L0_SET_EXPORTS`) and the outbox unchanged
  (`L0_SET_OUTBOX`). On Node A and Node B, before the charge, after each stage below H0 − 1 and before each
  step 8 the tip is unmoved (H0 − 2, then G − 1: `L0_TIP_MOVED`) and L0's funding output is unspent in the
  chain and, in the mempool, spent by nothing (by rung k − 1 before rung k's step 8) (`L0_FUNDING_SPENDER`);
  after each step 8 rung k alone spends it there, the chain still has it unspent, and the tip is still
  G − 1 (oe's `check_submitted`).
- **oe's checks left out** (`DEVIATIONS`): the mempool sizes of `check_nothing_sent` / `check_submitted`
  (`getmempoolinfo` 0 and 1: item 2's other bidders share the mempools, so the checks are per txid); each
  phase's steps count (`L0_STEPS`: the set worker reports turns, so each phase checks rung k's final verdict
  instead, `L0_SET_PHASE_VERDICT`); the host processes' event lines (`event_names`: the set worker writes none);
  the count of H0 − 1 comparisons (`L0_PENDING`: the host orders the rungs' comparisons itself, so every
  pending comparison is run and each phase must end with none pending, with no fixed count).
- **Each phase's verdict** (WRD3a1b P3-3). A set-worker run ends done on a refusal or a final outcome too, so
  each phase checks rung k's last verdict (the worker's `labels` line): `set_sign` `Wait:OfflineSignaturePending`,
  `set_wait` `Wait:SignedAwaitingOpeningGate`, `set_ready` `Wait:BroadcastAuthorityRequired`, `set_send` and
  `set_broadcast` `Act:Broadcast` or `Wait:AwaitingInclusion` (`L0_SET_PHASE_VERDICT` otherwise).
- **What L0 sent.** For each released rung, `RELEASE` (`k`, `txid`, `fee`, `vsize`, `replaces` (rung k − 1's
  txid, null for rung 0), `due_ns` (t0 + `rung_seconds` × k), `turn_start_ns`, `sent_ns` (the end of its
  step-8 process), `lag_ns`, `sent_by` `L0_STEP8`, `fee_source` `NODE_MEMPOOL_ENTRY`, `attempt_id`).
  `GENERATED` is written once, with the set's fees as `ladder` and the released rungs (`source` `L0_PRODUCT`).
  `last_rungs` holds L0's latest released rung, so the presence check (045b :538) reads it.
- **The fee check (A Q-L1).** Right after the set charge, before any rung is signed, every rung's wallet row
  (`fee_sat` and `vsize`, `ReservationLedger::candidate`, read by the set charge) and its charge base's
  `absolute_fee_sat` must be the computed `f_k` and v, also for a rung charged and never released (WRD3a1b
  P3-1; `L0_SET_CHARGED` logs every rung's row and `charge_bases`). `L0_ADMISSION` per released rung logs the
  computed `f_k`, the wallet row, the charge base and both nodes' `getmempoolentry`; a node's fee or vsize
  other than f_k and v fails the run. Any difference fails the run (`L0_FEE_MISMATCH`). The admissions of the
  rungs released are written also when a later rung failed, before that failure is raised (WRD3a1b P3-2).
- **Labels.** After block G one host turn (`set_observe`) reads every rung's verdict and report outcome
  (`L0_LABELS`, with the expected ones and `match`; a difference is `L0_LABEL_MISMATCH` on a gate that is not
  excluded). The expected labels follow the L0 rung block G holds and the one the replay found born (item 2
  reads the first from block G's own transactions, `order`, and the second from the replay; delta review P3-B:
  the template's L0 rungs must be the same, `L0_IN_G` otherwise, on any gate),
  not L0's latest released rung (WRD3a1b P2-1): when the latest rung misses G while an earlier one is in it,
  the labels describe the earlier one, and the gate's code (`RELEASE_NOT_IN_TEMPLATE`) excludes it like any
  seat's. More than one L0 rung in G, or a born rung not in G, is `L0_IN_G` on a gate that is not excluded.
  On a gate item 2 excludes (its code, computed first) a label mismatch or such an `L0_IN_G` is logged
  (`L0_LABELS` `match` false, with both label lists) and never fails the run (delta review P3-A: an excluded
  gate's labels can rest on the "no L0 rung in G" prediction below). L0's rung born: it is `Done:Born`
  at the opening and every other rung `Done:ProjectBornByOther` (a sibling of the campaign born). No L0 rung
  born: no project REGISTER was accepted at H0, so under the STOP_CAMPAIGN budget every rung is refused
  `ExactHeightMissed` before its outcome is read (`crates/bitagi-launch/src/machine.rs:1317-1332`, which also
  raises the campaign stop); under the CONTINUE_WITHIN_LIMITS budget (D3a-2b-1, A 6557723699: this branch's
  policy for item 2 and item 4) the verdicts are section 24's CONTINUE column (`Done:IncludedNoEffect@<h>`,
  `Refuse:GateAdvanced`, `Wait:OfflineSignaturePending`). Under either policy the report still carries the outcome: `IncludedNoEffect` at H0 for the rung
  block G holds, `Stale` (target H0, the replay's next birth height) for every other rung (every rung when G
  holds none: predicted, with no real-node row). The observing turn due past the attempt's deadline is
  `L0_DEADLINE` (WRD3a1b P3-7).
- **Counters.** `L0_BUDGET_COUNTERS` logs the wallet ledger's own CT-P3-045a §2.2 counters
  (`release_budget::budget_counters`: `released`, `gate_attempts`, `fee_exposure_sat`, `principal_exposure_sat`),
  as the set worker's `budget_counters` line reads them after G; the tool computes none (`L0_BUDGET_COUNTERS`
  for a malformed line). `GATE_END` carries them as `l0_budget_counters`, beside `l0_released_ks` and
  `l0_charged_not_released` (`count`, `fee_sum_sat`, `ks`). A gate with no block G
  (`REPLACED_RUNG_NOT_IN_MEMPOOL`) has no `set_observe`: its `L0_BUDGET_COUNTERS` and `l0_budget_counters`
  are the last set-worker phase's line (every phase reports the counters; WRD3a1b P3-6), with that phase and
  rung logged, so every gate with an L0 attempt carries the wallet's exposure.
- These are raw-log fields only. The judge's per-seat report that reads them (A Q7, Q-L4) is the collect /
  judge unit's (WU3c changes the campaign and collect now).
- **The DRAFT CLI.** `python3 tools/claude_track_ardr_l0.py run --mode EXPLORATORY|PR_SMOKE --policy …
  --experiment ITEM2 --run-index r --l0-seat j --node-a … --node-b … --work … --out …` runs one item-2 run with
  the L0 seat from a policy whose ITEM2 entry has `params`. It is DRAFT / EXPLORATORY only: a CONFIRMATORY run
  with the L0 seat will enter through the driver's CLI, which imports this module lazily inside `run()` (A #645
  correction 6557914275; this module stays outside XD-1's static import closure). CONFIRMATORY is refused
  before anything is read (exit 3), `L0_SEAT` stays `PENDING_FREEZE`, and no policy key names the seat. *Dated line 2026-11-10 (B, FZ-6, C27 pointer; sources 045b :1194's C27 dated line and A #664 issuecomment-6746599499): the freeze named it, 045b :1219 (F2, seat 1) in the F3 L0 policy keys (045b :1194); since B-FZ-a `--policy-l0-seat` reads that key (section 26).*

**Exclusions (A Q7).**
- The L0 seat's latest released rung is its last released rung, like any bidder's. Missing from block G's
  template, it gives `RELEASE_NOT_IN_TEMPLATE`. Any L0 rung sent at or after t0 + t_G gives
  `RELEASE_AFTER_G` (section 20's order).
- Each counts under the 10% rule like any other exclusion.
- `GATE_END` (and `RUN_END`) carry `code_seats`: the seats behind the code. For
  `RELEASE_NOT_IN_TEMPLATE` these are the missing seats; for `RELEASE_AFTER_G` the late seats; for
  `REPLACED_RUNG_NOT_IN_MEMPOOL` the seat whose rung was missing; for `G_LATE` none. With `l0_seat` and
  `l0_attempt_id` this lets the judge report exclusions per seat and per code, the L0 seat on its own line.
- After a `REPLACED_RUNG_NOT_IN_MEMPOOL` exclusion the driver still waits for L0's releases and logs its
  rungs (no block G, so no `set_observe`; the counters are the last phase's, above).

**Budget (A Q1, Q-L3).** L0's own budget record carries the Q1 draft values, Class T `DRAFT_TEST_ONLY`:
`max_fee_per_candidate_sat` 100,000, `max_fee_exposure_sat` 500,000, `max_principal_exposure_sat` 240,000
(Anchor 10,000 sat × 24) and `max_gate_attempts` 24. *2026-11-09 (B-FZ-p fix round 1, pre-PR review P3-2):
this sentence and the source bullet below are the Q1 draft's history. Since B-FZ-p the record is A's frozen
Class T L0 record (`docs/claude-track/preregistration/CAMPAIGN_BUDGET_V1_CLASS_T_REGTEST_L0.json` on #664,
SHA-256 `7d0a7a35…`; a repository file once #664 merges), status `FROZEN_TEST_ONLY`: `max_fee_per_candidate_sat` [Dated line 2026-11-10 (B, FZ-6, A #759 n3, issuecomment-6756854076): "status `FROZEN_TEST_ONLY`" is the logged status label `BUDGET_DRAFT['status']`, not a field of A's record, which has no `status` field. An L0 run that reaches L0_BUDGET (written after its last release) logs it in `product.status`; a run without policy values also logs it at the start, in L0_LAUNCH_START's `budget_draft` (a run with policy values, every CONFIRMATORY one, has `budget_sha256` there instead). #664 put the record on main (`317ecbf5`).]
30,000, `max_fee_exposure_sat` 500,000, `max_principal_exposure_sat` 240,000 and `max_gate_attempts` 24, as
`BUDGET_DRAFT` (the name kept) holds them; `test_budget_draft_is_the_frozen_record` ties each of them, and the
threshold 500000/24, to the record's bytes.*
- Source: A's Q1 draft table #258 issuecomment-6545342828, field by field, and A -6552107427 Q-L3 for 24.
  No repository file holds these numbers.
- The set charge writes them into the product's `budget.json` (the launch facts' `l0_budget=DRAFT_TEST_ONLY`
  line, which the set lines follow) (`Chain.frozen_l0_budget`, was `draft_budget`; `crates/bitagi-signer/tests/common/v2_writer.rs`
  `FROZEN_L0_BUDGET` since B-FZ-p, was `DRAFT_BUDGET`). Without that line the record is the fixture's, byte for byte.
- `L0_BUDGET` `product` logs the four fields as `budget.json` holds them. Its SHA-256 must be the set charge
  stage's `budget_sha256`, and (since B-FZ-p, 2026-11-10) the whole record must be A's frozen Class T L0 record *Dated line 2026-11-10 (B, FZ-6): the date 2026-11-10 of B-FZ-p is UTC 2026-11-09 (A #759 issuecomment-6749449323, F3).*
  for the run's `exact_height_miss` (`PRODUCT_BUDGET_SHA256`; `L0_BUDGET_NOT_FROZEN`; before B-FZ-p the four
  values had to be the Q1 draft's, `L0_BUDGET_NOT_DRAFT`).
- It also logs `status` (`FROZEN_TEST_ONLY` since B-FZ-p, was `DRAFT_TEST_ONLY`) and the 4.5 fee-row threshold `max_fee_exposure_sat /
  max_gate_attempts` (500000/24 sat per attempt). This does not decide Q1's Class E values.

**Raw-log events** (section 2's line; `unit` as section 20): *Dated line 2026-11-10 (L0-501, A #258 issuecomment-6764861681): `L0_RUNG_TEST`'s `nodes` now carry each node's `replaces_in_mempool`, and a failed attempt keeps its rung tests; see the addition to section 22 at the end of this file.*

| Event | Fields |
|---|---|
| `L0_FUNDING_BLOCK` | `height` 1, `block_hash`, `block_hex`, `coinbase_txid`, `funding_script`, `mined_by` `generatetodescriptor` |
| `L0_LAUNCH_START` | `seat`, `kind`, `attempt`, `attempt_id`, `h0`, `fee` (`rule`, `p0_rule`, `b`, `p0`, `increments`, `i`, `v`, `k` 0, `f_k` (rung 0's), `ladder` (the set)), `budget_source` with `budget_draft` (`BUDGET_DRAFT`, the module's record) or `budget_sha256` (`REGISTERED_POLICY`, a CONFIRMATORY policy's digest; `POLICY_VALUE`, a policy's digest outside CONFIRMATORY, B-FZ-a; section 26), `worker` (`launch_set_worker`), `exact_height_miss` (D3a-2b-1, section 24) |
| `L0_SET_CHARGED` | `attempt_id`, `set_id`, `budget_sha256`, `rungs` (per rung the set charge's line: `k`, `wallet_candidate`, `charge_sequence`, `fee_sat`, `wallet_fee_sat`, `wallet_vsize` (the wallet row's), `txid`, `base_sha256`), `fees`, `charge_bases` (per rung as `L0_ADMISSION`'s `charge_base`; null when the charge check did not get to read them); written also when a later stage before G − 1 failed |
| `L0_TURN` | one per worker process: `attempt_id`, `worker`, `lines` (the worker's result lines, as the worker wrote them), `start_ns`, `end_ns`. B-J5F (2026-11-05, A 6656311995 B2): an observing host turn's L0_TURN (`set_observe`, `set_reorged`, `set_release`) is written before the turn's own parse of its lines (`labels`, `flags`, `reorg`, `released`, `budget_counters`), and is written also when one of its lines fails to parse (before that error propagates; `_phase`'s own checks run first). So a malformed line still leaves its raw turn in the log, and the run refuses with that line's code (`L0_LABELS`, `L0_REORG_LINE`, `L0_BUDGET_COUNTERS`, `L0_SET_PHASE …`). A refusal of the L0_TURN write itself (`SECRET_IN_LOG`, `LOG_BOUND`) takes precedence over the turn's own code. A worker that `oe.run_stage` refuses (nonzero exit, timeout, a missing or extra result line, a secret) leaves no L0_TURN. The other phases' lines are logged by `ready` and `finish` before the L0 thread's error is raised. No new event or field |
| `L0_READY` | `attempt_id`, `t_ready_ns`, `txid`, `raw_tx_sha256`, `candidate_id` (rung 0's), `rungs` (each rung's `k`, `txid`, `raw_tx_sha256`, `candidate_id`) |
| `L0_ADMISSION` | one per released rung: `attempt_id`, `k`, `txid`, `nodes` (A, B: `in_mempool`, `fee`, `vsize`, `wtxid`), `sent_by`, `computed` (the `fee` record with this rung's `k` and `f_k`), `wallet` (`fee_sat`, `vsize`, `source` `WALLET_ROW`, `charge_base`: `absolute_fee_sat`, `signed_weight_wu` (the declared upper bound), `declared_vsize_bound`, `source` `CHARGE_BASE`) |
| `L0_BUDGET` | `attempt_id`, `product` (the four fields, `exact_height_miss` (D3a-2b-1), `budget_sha256`, `status`, `source` `PRODUCT_BUDGET_JSON`, `class`), `threshold_sat_per_attempt`, `policy_compare` (B-FZ-a: `EQUAL` with `policy_budget_sha256`, the policy's digest, compared with `product.budget_sha256`; `NO_POLICY_VALUE` without a policy's `l0_seat`) |
| `L0_LAUNCH_END` | `status` `DONE`, `attempt_id`, `txid` (the latest released rung's), `released` (the ks), `stages` |
| `L0_RELAY` | one per released rung: `txid`, `k`, `at_relay`, `waited_ns` |
| `L0_LABELS` | `attempt_id`, `won`, `latest` (k), `in_g` (the k of the L0 rung block G holds, or null), `born` (the k born, or null), `labels` and `expected` (per rung in rung order: `verdict`, `outcome`; `expected` null when `in_g` / `born` are inconsistent on an excluded gate, which then adds `in_g_ks` and `born_ks`), `match`, `excluded`, `exact_height_miss` (D3a-2b-1) |
| `L0_BUDGET_COUNTERS` | `attempt_id`, `counters` (`released`, `gate_attempts`, `fee_exposure_sat`, `principal_exposure_sat`), `source` `WALLET_LEDGER_WORKER_LINE`, `worker`, `phase` (`set_observe` after G; without G the last phase's) and `rung` |
| `L0_RUNG_TEST` | (D3a-2b-1, section 24) one per rung k ≥ 1: `attempt_id`, `k`, `txid`, `when` (`BEFORE_RELEASE`, or `CHARGED_NOT_RELEASED_BEFORE_G`), `source` `NODE_TESTMEMPOOLACCEPT`, `nodes` (Node A's and Node B's answer as returned, or null), `untested_reason` (`TIP_NOT_G_MINUS_1`, or null) |
| `L0_STOP_FAILED` | `code` (the stop's, e.g. `PREREQUISITE L0_THREAD_ALIVE`), `failure` (the run's own code, which is raised) |
| `GENERATED`, `RELEASE` | section 20's, for the L0 seat with the fields above |
| `GATE_END`, `RUN_END` | section 20's, plus `l0_seat`, `l0_attempt_id`, `l0_released_ks`, `l0_charged_not_released` (`count`, `fee_sum_sat`, `ks`) and `l0_budget_counters` (after block G the observing turn's, without it the last phase's) |

| Code | Exit | Raised by | When |
|---|---|---|---|
| `ITEM2_L0_SEAT` | 2 | item2 | `l0_seat` not a seat index 0-4 |
| `ITEM2_L0_SEAT_PRIVATE` | 2 | item2 | `l0_seat` 0 in an even run (the private seat) |
| `ITEM2_L0_H0` | 2 | item2 | `l0_seat` with `H0` other than 1000 |
| `ITEM2_L0_ADAPTER` | 2 | item2, l0 | an L0 adapter without `l0_seat`, or `l0_seat` without one |
| `BIDDERS_L0_SEAT` | 2 | bidders | an `L0_PROJECT` seat not `PUBLIC` or not wallet `L0` (item 2's L0 list) |
| `PREREQUISITE NODE_VERSION` | 3 | l0 | a node's Core version is not its role's (as section 8's D1 topology) |
| `PREREQUISITE NODES_NOT_CONNECTED` | 3 | l0 | the relay did not reach three peers (as section 8) |
| `PREREQUISITE RPC_FAILED` | 3 | l0 | a read through `bitagi-ardr-l0-read` failed (oe's driver-user calls keep oe's messages) |
| `MISMATCH RPC_NOT_ALLOWED` | 2 | l0 | a call outside `getrawmempool` / `testmempoolaccept` asked of the read user |
| `L0_ATTEMPT` | 2 | l0 | an attempt number outside 1-99 |
| `L0_STARTED` | 2 | l0 | a second L0 launch in one run |
| `L0_NOT_STARTED` | 2 | l0 | `finish` before `start` |
| `PREREQUISITE L0_NOT_READY` | 3 | l0 | L0 did not ask for the floor block within 900 s |
| `PREREQUISITE L0_FLOOR_NOT_MINED` | 3 | l0 | G − 1 did not come within 900 s |
| `PREREQUISITE L0_NOT_FINISHED` | 3 | l0 | L0's step 8 did not end within 900 s after G − 1 |
| `PREREQUISITE L0_THREAD_ALIVE` | 3 | l0 | L0's thread did not end at cleanup |
| `PREREQUISITE L0_PREVIOUS_THREAD_ALIVE` | 3 | l0 | an L0 launch while an earlier L0 thread that outlived its `stop` is still alive (its stage process or node call still running; the seat patches nothing) |
| `PREREQUISITE L0_DEADLINE` | 3 | l0 | an L0 stage due after the attempt's 2,700 s deadline (in L0's thread, or the observing turn in the main thread; also that turn after `stop`) |
| `PREREQUISITE NODE_CALL_TIMEOUT` | 3 | l0 | a call on Node A or Node B through `L0Node` ran past 300 s (`NODE_CALL_TIMEOUT A` / `B`, section 21) |
| `MISMATCH L0_FUND_NOT_AT_GENESIS` | 2 | l0 | the four nodes are not at the genesis when block 1 is mined |
| `MISMATCH L0_FLOOR_NOT_G_MINUS_1` | 2 | l0 | the floor block A and B agree on is not item 2's G − 1 |
| `MISMATCH L0_BYTES` | 2 | l0 | step 8's bytes are not the offline export's |
| `MISMATCH L0_BUDGET_SHA256` | 2 | l0 | `budget.json` is not the record the charge stage named |
| `ITEM2_L0_FEE_INPUT` | 2 | item2 | L0's p_0 given a b that is not an integer ≥ 1 (the ladder's own inputs are `LADDER_INPUT`) |
| `ITEM2_L0_LADDER_EMPTY` | 2 | item2, l0 | L0's ladder is empty at this b (rung 0 past the cap): refused at `plan_run`, before any node, and at `L0Seat.start` |
| `MISMATCH L0_FEE_MISMATCH` | 2 | l0 | on any rung of the set (right after the charge), the computed f_k or v differs from the wallet row's fee or vsize or the charge base's fee; or on any released rung from either node's fee or vsize (the run FAILED, A Q-L1) |
| `ITEM2_L0_SET_REFUSED` | 2 | item2, l0 | L0's set has more than 8 rungs or a rung above the draft `max_fee_per_candidate_sat` (*2026-11-09: since B-FZ-p the frozen record's, 30,000 sat*): refused at `plan_run` (i = 0) and at `L0Seat.start` (the real i) |
| `L0_SCHEDULE` | 2 | l0 | item 2's release list for the seat is not rungs 0, 1, … of the set |
| `MISMATCH L0_SET_CHARGE` | 2 | l0 | the set charge's `set_id` or `budget_sha256` is not a digest |
| `MISMATCH L0_SET_RUNGS` | 2 | l0 | the set charge's `rungs` line is not one well-formed token per rung, in rung order, with the set's fees and charge sequences 1, 2, … (a wallet row without fee or vsize too) |
| `MISMATCH L0_OUTBOX` | 2 | l0 | the outbox is not empty after the set charge |
| `MISMATCH L0_SET_OUTBOX` | 2 | l0 | a `set_sign` did not add exactly one `sign-input-<64 hex>.txt`, or the outbox is not exactly the rungs' sign inputs so far (after each `set_sign` and named sign stage) |
| `MISMATCH L0_SET_HANDOFF` | 2 | l0 | `launch/handoff/` after the set charge is not exactly the set's files (`set_handoff`) |
| `MISMATCH L0_SET_DIR` | 2 | l0 | the launch tree after a named sign stage is not exactly `export`, `handoff`, `host`, `outbox` |
| `MISMATCH L0_TIP_MOVED` | 2 | l0 | Node A's or Node B's tip is not H0 − 2 during L0's stages below H0 − 1, or not G − 1 around a step 8 |
| `MISMATCH L0_FUNDING_SPENDER` | 2 | l0 | L0's funding output is spent in a node's chain, or in its mempool by another than nothing / rung k − 1 (before rung k's step 8) / rung k (after it) |
| `MISMATCH L0_SET_PHASE_VERDICT` | 2 | l0 | a set-worker phase ended with rung k's verdict not the phase's (a refusal or a final outcome among them) |
| `MISMATCH L0_IN_G` | 2 | l0 | block G's L0 rungs differ from its template's (any gate); or, on a gate that is not excluded, more than one L0 rung in block G, or an L0 rung born that G does not hold |
| `MISMATCH L0_SET_EXPORT_TXID` | 2 | l0 | a rung's offline export is not the charged row's transaction |
| `MISMATCH L0_SET_EXPORTS` | 2 | l0 | `launch/export/` is not exactly the set's exports so far (after each named sign stage) |
| `MISMATCH L0_SET_PHASE` | 2 | l0 | a set-worker phase ended not done, for another phase, rung or rung count, or still pending a comparison |
| `MISMATCH L0_SET_SEND` | 2 | l0 | a sending phase did not hand off once with both nodes' `Accepted` submission for its rung |
| `MISMATCH L0_SENT_BEFORE_STEP_8` | 2 | l0 | an L0 rung is in Node A's or Node B's mempool before its own step 8 |
| `MISMATCH L0_RUNG_NOT_IN_MEMPOOL` | 2 | l0 | after its step 8 a rung is not in both nodes' mempools |
| `MISMATCH L0_RUNG_NOT_REPLACED` | 2 | l0 | after rung k's step 8, rung k − 1 is still in a node's mempool |
| `MISMATCH L0_BUDGET_COUNTERS` | 2 | l0 | the set worker's `budget_counters` line is not exactly the four counters as decimals |
| `MISMATCH L0_LABELS` | 2 | l0 | the set worker's `labels` line is not one `r<j>=<verdict>/<outcome>` per rung of the set |
| `MISMATCH L0_LABEL_MISMATCH` | 2 | l0 | a rung's label after block G is not the expected one on a gate that is not excluded (the run FAILED; on an excluded gate it is logged, `match` false) |
| `ITEM2_L0_EXPERIMENT` | 2 | l0 (CLI) | `run` for another experiment than ITEM2 |
| `ITEM2_L0_PARAMS` | 2 | l0 (CLI) | `run` with a policy whose ITEM2 entry has no `params` |
| `L0_SEAT_SOURCE` | 2 | l0 (CLI) | (B-FZ-a) `run` with both or neither of `--l0-seat` and `--policy-l0-seat`, before the policy is read |
| `MISMATCH L0_WALLET_FEE` | 2 | l0 | the charge's base lacks one decimal `absolute_fee_sat` or `signed_weight_wu` |
| `MISMATCH L0_BUDGET_NOT_FROZEN` | 2 | l0 | (B-FZ-p; was `L0_BUDGET_NOT_DRAFT`, the Q1 draft values) the product's `budget.json` is not A's frozen Class T L0 record for the run's `exact_height_miss` (its whole SHA-256, `PRODUCT_BUDGET_SHA256`) |
| `L0_BUDGET_JSON` | 2 | l0 | `budget.json` is not a JSON object |
| `L0_BUDGET_FIELDS` | 2 | l0 | the budget record lacks one of the four fields as an integer |
| `MISMATCH L0_BUDGET_MISS` | 2 | l0 | (D3a-2b-1) the product's `budget.json` `exact_height_miss` is not the run's |
| `L0_EXACT_HEIGHT_MISS` | 2 | l0 | (D3a-2b-1) an `exact_height_miss` other than `STOP_CAMPAIGN` or `CONTINUE_WITHIN_LIMITS` |
| `MISMATCH L0_RAW_HEX` | 2 | l0 | (D3a-2b-1) the named sign stage's `raw_tx_hex` is not hex or not the bytes of its `raw_tx_sha256` |
| `MISMATCH L0_RUNG_TEST` | 2 | l0 | (D3a-2b-1) a node's `testmempoolaccept` answer for rung k is not one result for its txid with a boolean `allowed` |
| `MISMATCH L0_REORG_LINE` | 2 | l0 | (D3a-2b-2a) the set worker's `reorg` line is neither `-` nor its form (section 25) |
| `L0_OBSERVE_PHASE` | 2 | l0 | (D3a-2b-2a) `observe_turn` for a phase other than `set_observe` / `set_reorged` (`set_release` runs only inside `release_reorg67`) |
| `L0_RELEASE_NOT_TEST_ONLY` | 5 | l0 | (D3a-2b-2a) the Reorg67 release asked without the `RELEASE_REORG67_TEST_ONLY` mark, off `ITEM4_REORG`, in CONFIRMATORY, or with Node A or Node B not on `regtest` (before any host process) *2026-11-25 (B-B1; 045b :1069): CONFIRMATORY is no longer refused for ITEM4_REORG with the mark on Regtest nodes; a mode other than EXPLORATORY, PR_SMOKE and CONFIRMATORY still is* |
| `L0_FREEZE_PENDING` | 3 | l0 | (D3a-2b-2b) a CONFIRMATORY ITEM2 or item-4 run whose policy has no `experiments.<E>.l0_seat` (a PENDING one is `POLICY_PENDING` first); before any node, output or worker (section 26). (2026-11-09, B-FZ-a fix round 1) An EXPLORATORY `--policy-l0-seat` run refuses the same way through `confirmatory_l0_seat`: a missing `l0_seat` is `L0_FREEZE_PENDING`; a PENDING or nested-PENDING one, or any PENDING in the policy, is `POLICY_PENDING` first (`load_policy(complete=True)`), and an uncounted experiment `POLICY_COUNT_UNSET` |
| `L0_POLICY_P0_RULE` | 6 | l0 | (D3a-2b-2b) the policy's `l0_seat.p0_rule` is not the run's (`CEIL_2_5_B`), before any node *Dated line 2026-11-10 (B, FZ-6 F1, A #759 issuecomment-6749449323): CONFIRMATORY `check-policy` refuses it too, through `load_policy` (section 26).* |
| `L0_POLICY_ATTEMPTS` | 6 | l0 | (D3a-2b-2b) the policy's `l0_seat.max_gate_attempts` is not the budget record's (24), before any node *Dated line 2026-11-10 (B, FZ-6 F1, A #759 issuecomment-6749449323): CONFIRMATORY `check-policy` refuses it too, through `load_policy` (section 26).* |
| `L0_POLICY_BUDGET_NOT_PRODUCT` | 6 | l0 | (B-FZ-a FZ-2) the policy's `l0_seat.budget_sha256` is not the product's record for its `exact_height_miss` (`PRODUCT_BUDGET_SHA256`, section 26), before any node, output or worker *Dated line 2026-11-10 (B, FZ-6 F1, A #759 issuecomment-6749449323): CONFIRMATORY `check-policy` refuses it too, through `load_policy` (section 26).* |
| `L0_REGISTERED_WITHOUT_BUDGET` | 2 | l0 | (B-FZ-a) an `L0Seat` marked registered without a policy `budget_sha256` (a Python API misuse) |
| `L0_CONFIRMATORY_OUTSIDE_DRIVER` | 6 | l0 | (D3a-2b-2b, pre-PR review P3-5) `item2_l0_run` or `item4_l0_run` given a CONFIRMATORY plan without the policy's `l0_seat` values (a Python API call; only the driver's `_run_l0` passes them), before any node, output or worker *Dated line 2026-11-10 (B, FZ-6 n1, A #759 issuecomment-6749449323): with values, a CONFIRMATORY plan whose `exact_height_miss` is STOP_CAMPAIGN is `L0_STOP_CAMPAIGN_EXPLORATORY_ONLY` (exit 6) there, through the driver's `refuse_stop_twin` (section 26).* |
| `MISMATCH L0_POLICY_BUDGET_SHA256` | 2 | l0 | (D3a-2b-2b) the product's `budget.json` after the charge is not the record the policy's `l0_seat.budget_sha256` names |
| `L0_CONFIRMATORY_EXPERIMENT` | 2 | l0 | (D3a-2b-2b) `confirmatory_l0_seat` asked for an experiment other than ITEM2 and the four item-4 experiments |
| `MISMATCH L0_RELEASE_NOT_REORG67` | 2 | l0 | (D3a-2b-2a) the release turn's `released` line is not the Reorg67 release with step 6 not performed |
| `MISMATCH L0_PROCEDURE_NOT_TEST_ONLY` | 2 | l0 | (D3a-2b-2a) the procedure file's `procedure_sha256` is not the TEST_ONLY Class T record's, or the file is missing, not ASCII, or has a line without `=` or a name twice |

The DRAFT CLI's other refusals are the driver's own codes, with their rows where they first appear:
`CONFIRMATORY_CAMPAIGN_NOT_BUILT` (exit 3, section 20; refused before anything is read; D3a-2b-2b keeps it: the
DRAFT CLI is never a CONFIRMATORY entry), `SEED_PENDING` and
`POLICY_PARAMS_PENDING` (exit 3, section 18) and `OUTPUT_EXISTS` (exit 3, section 13).

## 23. The item-4 run: miner policies and run shape (D3a-2a)

Class T Regtest development evidence only; every value is PENDING_FREEZE / DRAFT. Sources: B's D3a draft
#258 issuecomment-6550996612 (fact 3), A's answer -6551547851 (Q3-Q7), B's split note -6554438116 (D3a-2a,
B defaults), 045b item 4 (:383, :407-424, :524, :541-543). The tool is `tools/claude_track_ardr_item4.py`;
the tests are `tests/claude_track/test_ardr_item4.py`. D3a-2b adds the L0 project host and its labels.

**Routing.** `run --experiment ITEM4_<scenario>` with `experiments.<E>.params` runs one item-4 run
(EXPLORATORY, PR_SMOKE). Without params, an experiment pinned to an item-4 policy is refused
`ITEM4_PARAMS_MISSING` (exit 2) in every mode, before any node or output (D1's smoke would run under the policy
name and apply no filter; pre-PR P3-1); `ITEM4_FEE_ASYMMETRY` (pinned to `ITEM2_DEFAULT`) without params stays
section 13's D1 smoke. An item-4 CONFIRMATORY run is judged on the L0 project host's labels (045b :383, 4.3):
D3a-2b-2b sends it to the L0 seat (section 26); the stand-in never runs CONFIRMATORY
(`CONFIRMATORY_NEEDS_L0_SEAT`). `ITEM4_L0_NOT_BUILT` (D3a-2a to D3a-2b-2a) is retired. Item-4 params have section 18's
shape with `gates_per_run` exactly 1 and `H0` ≥ 107 (`POLICY_ITEM4_PARAMS`); the DRAFT `H0` is 1000 (A Q2,
B Q7). One run is one contested gate G = `H0`, run index r = 0 … 49 (045b :524; `ITEM4_RUN`).

**Policy pins (every mode, `POLICY_MINER_EXPERIMENT`, exit 2).** Like section 18's campaign pins:

| Experiment | Miner policy |
|---|---|
| `ITEM4_SELF_DEALING` | `ITEM4_SELF_FIRST_ZERO_FEE` |
| `ITEM4_CENSORSHIP` | `ITEM4_CENSOR_144` |
| `ITEM4_REORG` | `ITEM4_REORG_REPLACE` |
| `ITEM4_FEE_ASYMMETRY` | `ITEM2_DEFAULT` |

No other experiment may name one of the three item-4 policies. None is reserved any more
(`MINER_POLICY_NOT_BUILT` is unreachable).

**The policies (miner process).** Each orders what it keeps by section 7's ancestor feerate. A block of an
item-4 run may carry one context (`block` op field `item4`, JSON across the process boundary); its kind is
fixed by the policy (`ITEM4_CONTEXT_POLICY`), its shape is closed (`ITEM4_CONTEXT`); a block without one is
section 7 alone.

- `ITEM4_SELF_FIRST_ZERO_FEE`, context `{"kind": "SELF", "height", "self"}` (block G only,
  `ITEM4_CONTEXT_HEIGHT`): the self transaction is placed at index 0 after the coinbase whatever its fee,
  0 included; it must be a candidate (`ITEM4_SELF_MISSING`) with no parent among them
  (`ITEM4_SELF_PARENT`); a candidate spending one of its outpoints is dropped (`SELF_CONFLICT`). Its weight
  comes off the budget first. A candidate spending the self transaction's output is ordered without it as a
  parent (it is already at index 0; Codex P2 r4434970466).
- `ITEM4_CENSOR_144`, context `{"kind": "CENSOR", "first", "txids", "outpoints"}`: in blocks `first` …
  `first` + 143 (`CENSOR_BLOCKS` = 144, 045b :542) every candidate with a listed txid (`TXID`) or spending a
  listed outpoint (`OUTPOINT`: a replacement rung has a new txid but spends the project's funding output)
  is dropped with its descendants (`DESCENDANT`); from `first` + 144 on nothing is dropped.
- `ITEM4_REORG_REPLACE`, context `{"kind": "REORG", "drop"}`: every listed txid (the replaced winner,
  which the template offers again after `invalidateblock`) is dropped with its descendants
  (`REPLACED_WINNER`); `offered` lists the listed txids the candidates held. No `prioritisetransaction`.

The block's record (`MINER_FILTER`) is `kind`, `policy`, `filtered` (txid and reason, candidate order) and
the kind's fields (`self_txid`, `self_fee`, `self_index`; `censor_index` (null outside the window),
`first`, `last`; `offered`).

**Seats (B Q1-Q3 defaults, A 6554792879).** The project seat is `PROJECT_STANDIN` (SYNTHETIC wallet W01) until
D3a-2b. Its configured rung-0 feerate p0 is ceil(2.5 b) (the D3a rule for L0's `p_0`; DRAFT), in every
scenario.

| Scenario | Seats (seat, wallet, path, role) | Fees |
|---|---|---|
| self dealing | S0 W00 PRIVATE `SELF`; S1 W01 PUBLIC stand-in | self `SELF_FEE` = 600 sat; stand-in ceil(p0 × 213 / 1000), p0 = ceil(2.5 b) |
| censorship | S0 W01 PUBLIC stand-in (rungs 0 and 1); S1 C00 PUBLIC `COMPETITOR` | stand-in `ladder(p0, b, i, 213)[:2]`; competitor 2 × the stand-in's rung-0 fee + 1 |
| reorg | S0 W01 PUBLIC stand-in; S1 C00 PUBLIC `COMPETITOR` (released after G) | as censorship, rung 0 only |
| fee asymmetry | S0 W00 PUBLIC `ASYMMETRIC`; S1 W01 stand-in; S2-S4 W02-W04 `HONEST` | below |

The product signer refuses a 0-fee REGISTER (`crates/bitagi-signer/src/semantic.rs:714`, :767-778 *(dated 2026-11-25, B4-38: on main `fc492865` these are :719 and :772-783)*; the
generator panics `BelowTargetFeeRate` first, `crates/bitagi-signer/tests/ardr_bidder_generator.rs:341`), so
the self REGISTER pays the product floor, 600 sat (2,000 sat/kvB over the fixture's 300 vB signed weight;
426 and 599 measured refused); RUN_START's `self_fee` is 600 and `self_fee_rule`
`PRODUCT_FLOOR_ZERO_FEE_NEEDS_SRC`, and the not-run list names `ITEM4_SELF_ZERO_FEE_REGISTER`. So that the
self REGISTER is first by the policy and not by its feerate, its fee must be strictly below every other
seat's rung 0 (equal vsize). A 6554792879 Q8's static check, when the params are fixed (`check-policy`,
`check_params` and planning, before any node): the project's rung 0, ceil(p0 × 213 / 1000), must pay strictly
more than 600 sat (b ≥ 1127; `ITEM4_SELF_FEE_NOT_BELOW`). Block G is checked again (`ITEM4_SELF_NOT_FIRST`,
then `ITEM4_SELF_FEE_NOT_LOWEST`: the self REGISTER's feerate strictly below every other released rung's).
A's figure "P0 feerate > 2,000 sat/kvB" is not enough at 213 vB: the 600-sat floor is 2,817 sat/kvB there. The miner policy itself places a 0-fee self
transaction first: a real-node cell shows `submitblock` taking a block whose index-0 transaction is a TEST_ONLY
OP_TRUE spend paying 0 (block acceptance only; no key, not a REGISTER).

**Fee asymmetry (A Q5, B Q1-Q4, A 6554792879 Q1-Q2).** The honest rung-0 feerates are fixed before any rung
is released, never read from a mempool or a template: the project seat's configured p0 = ceil(2.5 b) (no
draw) and seats 2-4's `BID_FEE_j` of experiment `ITEM4_FEE_ASYMMETRY` (n = 3b + 1, feerate b + value;
section 6's mapping). Their median is the nearest-rank p50 (the 2nd smallest of four). The asymmetric bidder
pays one rung of ceil(10 × p50 × 213 / 1000) sat, outside the 4b ladder cap. `ASYMMETRIC_BID` is written after
the rung-0 releases: `seat`, `median`, `factor`, `feerate`, `fee`, `honest_feerates`,
`project_configured_p0`, and apart `project_seat` and `project_sent` (`fee`, `txid`: what the project seat
really sent, for the judge to compare); the asymmetric seat's sent fee must be the planned one
(`ITEM4_ASYMMETRIC_FEE_MOVED`). A fee above 90,000 sat (the
generator's caps) is refused before any node (`ITEM4_ASYMMETRIC_FEE_CAP`). Honest seats bid rung 0 only.

**Block G (A Q6).** No `t_G`. Block G − 1 is prepared and the rungs built on its hash (section 20, step 1),
then sent. Every bidder not released after G releases rung 0 once G − 1 is at all four nodes (Node A and
Node B `testmempoolaccept` first, as section 20 step 3). Block G is mined once every released public rung is
at the miner node (`ITEM4_RELEASE_NOT_AT_MINER`, exit 3, after 120 s); then each bidder's last released rung
is checked against G's template / private set (`RELEASE_NOT_IN_TEMPLATE` excludes the gate, as section 20).

**Censorship.** Block G and G + 1 … G + 144 carry the CENSOR context (`first` = G, the stand-in's rung-0
txid, its funding outpoint); the stand-in's rung 1 is released after block G. Every block G … G + 143
holding a project transaction (listed txid or a spend of the outpoint) fails the run
(`ITEM4_CENSOR_LEAK`); G + 144 must hold one (`ITEM4_CENSOR_NOT_LIFTED`; 2026-11-02, D3a-2c: the stand-in also requires its rung 1 by txid there, so a re-signed spend of the outpoint alone is not the lift). `CENSOR_WINDOW` logs the window.
(D3a-2c) Each block is judged from its own bytes (`block_hit`, as section 24: header hash, merkle root and
order checked, `ITEM4_BLOCK_BYTES` otherwise): a transaction is the stand-in's when its txid is one of its
ladder's rungs or when any of its inputs spends the stand-in's funding outpoint, whatever its txid.
Rung 1 is released as section 20 releases a public replacement: if rung 0 is not in Node A's and Node B's
mempools within 5 s, the gate is EXCLUDED with `REPLACED_RUNG_NOT_IN_MEMPOOL` (item 2's code and detail:
`REPLACED_RUNG_MISSING`, then `GATE_END` and `RUN_END` EXCLUDED with `replaced_missing` and `code_seats`, exit 2;
Desktop P3 r4435089959). Any item-4 release step that raises it ends the run the same way.

**Reorg (A Q3, Q5; B Q6).** Depth d = 1 for even r, 2 for odd r. After G (the stand-in wins) the
competitor's rung 0 is released; d = 2 mines G + 1. At least 6 s after G's template (Core keeps a
`getblocktemplate` result for the same tip for 5 s, so a depth-1 run would get G's own template back;
`TEMPLATE_CACHE_NS`, counted from when G's template answer arrived, `t_template_answer_ns`; the time actually
waited is `template_cache_wait_ns` in `REORG` and in `timing`) the miner node's driver user calls
`invalidateblock` on G (the miner node's best hash
must then be G − 1, `ITEM4_REORG_TIP`). The miner process builds d + 1 replacement blocks on G − 1 with the
REORG context: none may hold the winner, by its txid or by any spend of the stand-in's funding outpoint
whatever its txid (D3a-2c: `winner_check` through `block_hit`, from the block's own bytes, as section 25;
`ITEM4_WINNER_READDED`), and the first must be offered the
competitor (`ITEM4_TEMPLATE_STALE`). The first d wait for the miner node only (the other nodes keep the
longer chain); the last waits for all four (more work: the reorg reaches them by P2P). `REORG` logs
`depth`, `invalidated`, `node` (`miner`), `replaced`, `replacement`, `winner`, `winner_offered` (per
replacement block, whether its template offered the winner), `template_cache_wait_ns`. The replay of the
replaced blocks must give exactly the winner's birth (`ITEM4_REPLACED_NOT_WINNER`) and the FINAL replay must not
(`ITEM4_WINNER_STILL_BORN`). The topology check refuses, before anything
starts, a reorg run whose miner driver user lacks `invalidateblock`, any other run whose miner driver user
has it, and any set beyond the default plus `invalidateblock` (`ITEM4_REORG_TOPOLOGY`).

**Replay.** The final chain from G is replayed with the Core worker (`BIRTHS`, `CORE_REPLAY` with `chain`
`FINAL`); a reorg run also replays the replaced blocks (`chain` `REPLACED`). `GATE_END`'s `born` and
`winner` (the born txid's role) come from the FINAL replay.

**Not run (045b :383).** Every run logs `SCENARIO_NOT_RUN` with the cases it does not cover:
`Done:Born{late, at_opening: false}` (censorship; A Q4: the competitor holds G), `ITEM4_SELF_ZERO_FEE_REGISTER`
(self dealing; the reason cites the file lines above), and the L0 project seat (every scenario; D3a-2b).

**Raw-log events** (section 2's line; `unit` gate = r from `GATE_START` on):

| Event | Fields |
|---|---|
| `RUN_START` | as section 20, with `scenario`, `depth` (reorg; else null), `roles`, `fees`, `project_seat`, `self_fee` and `self_fee_rule` (self dealing; else null), `miner_driver_rpcs`, `l0_control` (B-J5F, 2026-11-05, A 6656311995 B3: a bool on every item-4 run, true exactly for the censorship run's local control row with the L0 seat, section 24; false otherwise) |
| `BIDDERS` | the list, its SHA-256, the draws (fee asymmetry) and the four honest feerates |
| `SCENARIO_NOT_RUN` | `not_run`: `scenario`, `case`, `label`, `reason` |
| `SCHEDULE` | `increment`, `ladders`, `after_g` (seats released after G), `rule` `G_WHEN_RELEASED_IN_TEMPLATE` |
| `ASYMMETRIC_BID` | `seat`, `median`, `factor`, `feerate`, `fee`, `honest_feerates`, `project_configured_p0`, `project_seat`, `project_sent` |
| `MINER_FILTER` | `height`, `block_hash` and the block's record above |
| `SELF_REGISTER` | `txid`, `fee`, `index` 0, `height`, `block_hash`, `seat`, `policy` |
| `CENSOR_WINDOW` | `first`, `last`, `lifted`, `txids`, `outpoints`, `seat` |
| `REORG` | above |
| `CORE_REPLAY` | as section 16, with `chain` |
| `GATE_END` | `OBSERVED` (`born`, `winner`, `last_rungs`, `order`, `tip`, and `censor` or `reorg`) or `EXCLUDED` (`RELEASE_NOT_IN_TEMPLATE`, `misses`; or `REPLACED_RUNG_NOT_IN_MEMPOOL`, `misses` [], `code_seats`, `replaced_missing`, `block_hash` G's when mined, else null) |
| `RUN_END` | as section 20 (`FAILED`: `excluded_observation_ids` `OBS-<e><r:07>`) |

`BLOCK_ACCEPTED`'s `nodes` lists the nodes the block waited for.

| Code | Exit | Raised by | When |
|---|---|---|---|
| `POLICY_ITEM4_PARAMS` | 2 | driver | item-4 params out of bounds (`gates_per_run` not 1, `H0` below 107, `b` not positive) |
| `ITEM4_SCENARIO` | 2 | item4 | not one of the four item-4 experiments |
| `ITEM4_RUN` | 2 | item4 | a run index outside 0-49 |
| `ITEM4_P50_EMPTY` | 2 | item4 | a median of no feerates |
| `ITEM4_ASYMMETRIC_FEE_CAP` | 2 | item4 | the asymmetric fee above 90,000 sat (before any node) |
| `ITEM4_HONEST_LADDER_EMPTY` | 2 | item4 | an honest seat's rung 0 over 4b (unreachable: p0 ≤ 4b) |
| `ITEM4_STANDIN_LADDER` | 2 | item4 | the stand-in's ladder has fewer than two rungs in a censorship run |
| `ITEM4_REORG_TOPOLOGY` | 2 | item4 | `invalidateblock` on the miner driver user other than exactly in a reorg run, or any other set changed |
| `ITEM4_CONTEXT` | 2 | driver (miner) | a malformed item-4 block context |
| `ITEM4_CONTEXT_POLICY` | 2 | driver (miner) | a context for another policy, or for a non-item-4 policy |
| `ITEM4_CONTEXT_HEIGHT` | 2 | driver (miner) | a SELF context at another height |
| `ITEM4_SELF_MISSING` | 2 | driver (miner) | the self transaction is not a candidate |
| `ITEM4_SELF_PARENT` | 2 | driver (miner) | the self transaction has a parent among the candidates |
| `ITEM4_SELF_NOT_FIRST` | 2 | item4 | block G's first transaction is not the self REGISTER |
| `ITEM4_SELF_FEE_NOT_BELOW` | 2 | driver | ITEM4_SELF_DEALING params whose project rung 0 (ceil(2.5 b) at 213 vB) pays 600 sat or less (check-policy, planning; before any node) |
| `ITEM4_SELF_FEE_NOT_LOWEST` | 2 | item4 | the self REGISTER's feerate not strictly below every other released rung's in block G |
| `ITEM4_ASYMMETRIC_FEE_MOVED` | 2 | item4 | the asymmetric seat's sent fee is not the planned one |
| `ITEM4_CENSOR_LEAK` | 2 | item4 | a block G … G + 143 holds a project transaction (a ladder txid or a spend of the stand-in's funding outpoint, D3a-2c) |
| `ITEM4_CENSOR_NOT_LIFTED` | 2 | item4 | block G + 144 holds no project transaction (2026-11-02, D3a-2c: for the stand-in, block G + 144 does not hold its rung 1 by txid) |
| `ITEM4_WINNER_READDED` | 2 | item4 | a replacement block holds the replaced winner (its txid or a spend of the stand-in's funding outpoint, D3a-2c) |
| `ITEM4_TEMPLATE_STALE` | 2 | item4 | the first replacement block's template lacks the competitor released after G |
| `ITEM4_PARAMS_MISSING` | 2 | driver | an experiment pinned to an item-4 policy without `params` (every mode, before any node) |
| `ITEM4_REPLACED_NOT_WINNER` | 2 | item4 | the replaced blocks' replay does not give exactly the winner's birth |
| `ITEM4_WINNER_STILL_BORN` | 2 | item4 | the FINAL chain's replay gives the replaced winner's birth |
| `ITEM4_CENSOR_END` | 2 | item4 | the censorship run did not reach block G + 144 (checked after the loop) |
| `ITEM4_POLICY_MISMATCH` | 2 | driver | the item-4 plan's miner policy is not the policy file's pinned one |
| `MINER_CONTEXT_BOTH` | 2 | driver (miner) | a `block` request with both an ITEM1 `gate` and an item-4 context |
| `ITEM4_REORG_TIP` | 2 | item4 | the miner node's best block after `invalidateblock` is not G − 1 |
| `ITEM4_HEIGHT` | 2 | item4 | a block of the run at an unexpected height |
| `PREREQUISITE ITEM4_RELEASE_NOT_AT_MINER` | 3 | item4 | a released public rung not at the miner node within 120 s |

## 24. The item-4 run with the L0 project seat (D3a-2b-1)

Class T Regtest development evidence only; every value is PENDING_FREEZE / DRAFT. Sources: B's unit note
#258 issuecomment-6557558721, A's answer -6557723699 (binding: the L0 budget's `exact_height_miss`, Q1 the
verdict judged too, Q2 E7 not run, Q3 the censor turns and a control row, Q6 the local rows' records, Q7 the
GateAdvanced refusal), A's judge plan -6557890079 (request 1: one increment rule; request 2: the rung tests),
A's correction -6557914275 (Q5), A's earlier answer -6554792879 (Q1 the asymmetry median, Q3 fixed fees, Q4
the asymmetric bidder, Q5 the censor window, Q7 H0 1000), 045b 4.3's item-4 labels (:407-424). The code is
`tools/claude_track_ardr_item4.py` (`plan_run(…, l0=True)`, `_gate_l0`) and `tools/claude_track_ardr_l0.py`
(`item4_l0_run`, `L0Seat.observe_turn`); the cells are `tests/claude_track/test_ardr_item4_l0.py`. The unit
note is `docs/claude-track/plans/notes/CT-P5-001_DRIVER_EN/2026-11-01_d3a-2b-1-item4-l0.md`.

**Shape.** The Python API `item4_l0_run` runs `ITEM4_SELF_DEALING`, `ITEM4_FEE_ASYMMETRY` and
`ITEM4_CENSORSHIP` with the L0 project bidder (section 22's `L0Seat`, kind and role `L0_PROJECT`, wallet
`L0`, PUBLIC) in the project seat, on section 22's `L0Topology` (oe's Node A 31.1 and Node B 30.3, D1's
miner and relay), H0 = 1000 (`ITEM4_L0_H0`). Seats: self dealing S0 SELF (PRIVATE), S1 L0; fee asymmetry
S0 the asymmetric bidder, S1 L0, S2-S4 `BID_FEE_j`; censorship S0 L0, S1 the competitor (2 × the configured
rung-0 fee + 1). The driver's EXPLORATORY and PR_SMOKE ITEM4 runs keep the stand-in (section 23); its
CONFIRMATORY runs are this L0 path (D3a-2b-2b, section 26). (D3a-2b-2a: `ITEM4_REORG` with L0 is section 25's; the D3a-2b-1 refusal
`ITEM4_L0_REORG_NOT_BUILT` is gone.) CONFIRMATORY is D3a-2b-2b's; there (A -6557914275) item 2's and item 4's
CONFIRMATORY with the L0 seat enter through the one ARDR driver CLI, which imports the L0 module inside
`run()` as it does item 2 and item 4; the L0 module's `run --l0-seat` stays DRAFT / EXPLORATORY.

**The L0 budget (A -6557723699).** The L0 seat's `DRAFT_TEST_ONLY` budget record carries
`exact_height_miss = CONTINUE_WITHIN_LIMITS` (045b :103's draft value) in item 2 and item 4 (*2026-11-09,
B-FZ-p fix round 1, pre-PR review P3-2: since B-FZ-p the record is A's frozen Class T L0 record, `7d0a7a35…`,
status `FROZEN_TEST_ONLY`, which carries CONTINUE_WITHIN_LIMITS; its STOP_CAMPAIGN twin `9ea208bd…` is [Dated line 2026-11-10 (B, FZ-6, A #759 n3, issuecomment-6756854076): "status `FROZEN_TEST_ONLY`" is the logged status label `BUDGET_DRAFT['status']` (L0_BUDGET `product.status`, written after L0's last release); A's record has no `status` field.]
EXPLORATORY only, section 26*). The L0 tool
writes it as a third set line of the launch facts, `l0_set_exact_height_miss` (signer test `SET_LINES`; the
stages still read only the facts path), the set charge writes it into `budget.json`, and the tool checks the
product's record carries the run's value (`L0_BUDGET_MISS`). `L0_LAUNCH_START`, `L0_BUDGET` (`product`) and
`GATE_END` (`l0_exact_height_miss`) write it, in item 2 `L0_LABELS` and in item 4 `ITEM4_LABELS` (an item-4 run
writes no `L0_LABELS` and no `L0_BUDGET_COUNTERS`: its turns' counters are in `ITEM4_L0_OBSERVE`, D3a-2b-2a,
A's #652 check); the expected labels are chosen
by it.

**One increment rule (A -6557890079 request 1).** Every ladder's `i` is the larger of Node A's and Node B's
`incrementalfee`, read per run (`bidders.node_increments`; `ladder` stays the one fee formula): item 2's and
item 4's synthetic ladders, the bidders cell and the L0 seat. `SCHEDULE` writes `increments` (both),
`increment` and `increment_rule` `MAX_NODE_A_NODE_B`; the bidders cell writes `INCREMENTS`. RUN_START is
written before the nodes start, so the values are in `SCHEDULE` (`INCREMENTS` in the cell).

**L0's rungs.** As section 22. Item 4 has no t_G (A Q6), so after G − 1 only rung 0 is released (`floor`
gets `[(0, t0)]`; `SCHEDULE` `l0_release_ks` [0]), by L0's own step 8 to Node A and Node B; every other rung
is charged and never released (`GATE_END` `l0_charged_not_released`, A Q7). L0's released rung is read from
the product and the nodes (`L0_ADMISSION`, `RELEASE` with `sent_by` `L0_STEP8` and `fee_source`
`NODE_MEMPOOL_ENTRY`); it must be rung 0 (`ITEM4_L0_RELEASED`). Block G waits until it is at the miner node.
After G the product refuses any release (`Refuse:GateAdvanced`): that refusal, with its reason, is the
released rung's verdict in the host's labels at every turn while it is not mined (`ITEM4_L0_OBSERVE`). No
probe changes the host's state after G. For each rung charged and never released, `GATE_END`
`l0_charged_not_released_after_g` writes its fee and the host's own verdict and outcome for it at the first
turn after G (`verdict_after_g`, `outcome_after_g`, `source` `SET_WORKER_LABELS_FIRST_TURN_AFTER_G`), in item 2
and item 4.

**Rung tests (A -6557890079 request 2).** For every L0 rung k ≥ 1 the tool asks Node A and Node B
`testmempoolaccept` of the rung's signed bytes (the named sign stage's new `raw_tx_hex` line, checked
against its `raw_tx_sha256`, `L0_RAW_HEX`) and logs each answer as returned (`L0_RUNG_TEST`): a released
rung right before its step 8 (`BEFORE_RELEASE`: rung k − 1 in both mempools), a rung never released before G
(`CHARGED_NOT_RELEASED_BEFORE_G`, from `finish`: the tip still G − 1, the last released rung in both
mempools); a rung whose nodes are not at G − 1 is logged untested with `untested_reason`. Item 2 and item 4. *Dated line 2026-11-10 (L0-501): each node's answer also says whether the replaced rung was in that node's mempool (`replaces_in_mempool`); see the addition to section 22 at the end of this file.*

**Self dealing.** The rival set of `self_check` is every non-SELF seat's released rung, so L0's rung 0 as
the product released it (`SELF_REGISTER` `rivals`).

**Fee asymmetry.** The median and the asymmetric fee are the plan's (section 23), from the configured p_0
(`item4_project_p0(b)`, which must equal L0's `l0_p0(b)`, `ITEM4_L0_P0_TWO_SOURCES`) and `BID_FEE_2..4`, never
from what L0 sent. `ASYMMETRIC_BID` adds `project_p0_sources` and `project_sent` from L0's release (the nodes'
`getmempoolentry` fee and vsize: `source` `L0_ADMISSION`; `ITEM4_L0_SENT_SOURCE` otherwise).

**Censorship.** The censor context lists L0's rung 0 by txid and L0's funding outpoint (every rung of the
set spends it). Each block G … G + 144 is checked with `censor_check` over the block's own transactions,
read from the bytes the miner submitted (`block_hex`; the header must hash to the block hash Node A and
Node B report, the merkle root must be the txids', and the transactions after the coinbase must be the
block's `order`: `ITEM4_BLOCK_BYTES` otherwise): a transaction is L0's when its txid is a rung of L0's set or
any of its inputs spends L0's funding outpoint, whatever its txid (a re-signed rung counts). During G … G +
143 L0's rung 0 must stay in Node A's and Node B's mempools (`ITEM4_L0_CENSORED_LEFT_MEMPOOL`;
`CENSOR_MEMPOOL`); G + 144 holds it.

**Host turns and labels.** After block G, and in the censorship run after G + 143 and G + 144 (`L0_TURNS`; A
Q3), the host takes one turn (`L0Seat.observe_turn`: the set worker's `set_observe`) with Node A and Node B
at that block (`ITEM4_L0_OBSERVE_TIP`); `ITEM4_L0_OBSERVE` and `ITEM4_LABELS` write the turn's height and tip
hash. The local control row (`plan_run(…, l0_control=True)`, censorship only, `ITEM4_L0_CONTROL` otherwise)
takes a turn at every block G … G + 144. The set worker reports, beside `labels`, a `flags` line (host test
`set_flags`): `r<j>=opening_block_missed:<true|false>,reorged_before_inclusion:<true|false>` for every rung,
the core report's two fields; `ITEM4_L0_FLAGS` refuses any other form. The tool logs them as written and
never computes a flag. After the FINAL replay each turn is judged against `ITEM4_LABELS` (045b 4.3) by all
three, the verdict, the report outcome and the two flags (A Q1; any one different is a mismatch):

| Rung at a turn | Outcome | Verdict, CONTINUE_WITHIN_LIMITS | Verdict, STOP_CAMPAIGN |
|---|---|---|---|
| rung 0 in a block (self dealing and fee asymmetry at G; censorship at G + 144) | `IncludedNoEffect@<height>` | `Done:IncludedNoEffect@<height>` | `Refuse:ExactHeightMissed` at G, `Refuse:StopOpen(ExactHeightMissed)` later |
| rung 0 released, not mined (censorship at G and G + 1 … G + 143) | `Stale@G><next birth>` | `Refuse:GateAdvanced` | as above |
| rung k ≥ 1, charged and never released | `Stale@G><next birth>` | `Wait:OfflineSignaturePending` | as above |

Every rung at every turn: `opening_block_missed` true, `reorged_before_inclusion` false. The next birth is
the replay's at the turn's height. The verdicts are the real-node rows' (unit note section 6); the STOP
column is the first round's (head 6b117143). An unknown policy is `ITEM4_L0_MISS`. One `ITEM4_LABELS` line
per turn (`match`, `exact_height_miss`, `judged`); any mismatch fails the run after all are written
(`ITEM4_LABEL_MISMATCH`). Item 2's `expected_labels` (section 22) follows the same CONTINUE column.

**Not run.** `SCENARIO_NOT_RUN` in an L0 run lists section 23's first two cases, E7 (a rung reorged out
before its inclusion: no item-4 miner policy reorgs one, A Q2; 1e-2b-2b's E7 real-node row covers its label
for item 4's entry set). (D3a-2b-2a: the reorg run with L0 is no longer listed; section 25.)

**Raw-log events** (in addition to section 22's L0 events, which an item-4 L0 run writes as item 2's does,
except `L0_LABELS` and `L0_BUDGET_COUNTERS`, which item 2's `observe` writes: item 4 writes `ITEM4_L0_OBSERVE`
(with the counters) and `ITEM4_LABELS` instead):

| Event | Fields |
|---|---|
| `RUN_START` | section 23's (`l0_control` included), `project_seat` `L0_PROJECT`, `fees` null for the L0 seat |
| `SCHEDULE` | section 23's (or 20's), `increments`, `increment_rule`, and in item 4 with L0 `l0_seat`, `l0_release_ks` |
| `INCREMENTS` | (bidders cell) `increments`, `increment`, `rule` |
| `ASYMMETRIC_BID` | section 23's, `project_p0_sources`, `project_sent` (`fee`, `vsize`, `txid`, `k`, `source`, `fee_source`) |
| `SELF_REGISTER` | section 23's and `rivals` |
| `ITEM4_L0_OBSERVE` | `attempt_id`, `turn`, `phase` `set_observe`, `height`, `block_hash`, `labels` (verdict, outcome), `flags`, `counters`, `flags_source` |
| `ITEM4_LABELS` | `turn`, `height`, `block_hash`, `labels` and `expected` (verdict, outcome, flags), `match`, `exact_height_miss`, `judged`, `rule` |
| `CENSOR_MEMPOOL` | `txid`, `nodes`, `heights` (first and last checked), `blocks` |
| `GATE_END` | section 23's, with section 22's `l0_seat`, `l0_attempt_id`, `l0_released_ks`, `l0_charged_not_released`, `l0_charged_not_released_after_g` (also item 2's), and `l0_turns` (turn, height, block hash), `l0_exact_height_miss`, `l0_budget_counters` |

| Code | Exit | Raised by | When |
|---|---|---|---|
| `ITEM4_L0_H0` | 2 | item4 | an L0 plan with H0 other than 1000 |
| `ITEM4_L0_P0_TWO_SOURCES` | 2 | item4 | the item-4 configured p_0 differs from L0's p_0 |
| `ITEM4_L0_ADAPTER` | 2 | item4 | an L0 seat without an L0 plan, or an L0 plan without the seat |
| `ITEM4_L0_CONTROL` | 2 | item4 | the control turns asked without L0 or outside the censorship run |
| `ITEM4_L0_RELEASED` | 2 | item4 | L0 released anything but rung 0 of its set before G |
| `ITEM4_L0_SENT_SOURCE` | 2 | item4 | the project seat's rung in `ASYMMETRIC_BID` is not L0's release with the nodes' fee |
| `ITEM4_L0_OBSERVE_TIP` | 2 | item4 | Node A or Node B not at the turn's block |
| `ITEM4_L0_FLAGS` | 2 | item4 | the set worker's `flags` line not in its form (every rung once) |
| `ITEM4_L0_TURNS` | 2 | item4 | the host turns taken are not the plan's (names or heights) |
| `ITEM4_L0_MISS` | 2 | item4 | an `exact_height_miss` with no expected-verdict column |
| `ITEM4_LABEL_MISMATCH` | 2 | item4 | a turn's verdict, outcome or flags differ from `ITEM4_LABELS` |
| `ITEM4_L0_CENSORED_LEFT_MEMPOOL` | 2 | item4 | L0's censored rung 0 missing from Node A's or Node B's mempool in G … G + 143 |
| `ITEM4_BLOCK_BYTES` | 2 | item4 | (L0 censorship and reorg; the stand-in's censorship and reorg since D3a-2c) a block's `block_hex` does not parse, its header does not hash to the block hash, its merkle root is not its txids', or its transactions are not the block's `order` |

## 25. The item-4 reorg run with the L0 project seat (D3a-2b-2a)

Class T Regtest development evidence only; every value is PENDING_FREEZE / DRAFT; TEST_ONLY material only.
Sources: A's answer #258 issuecomment-6557723699 Q4 (binding: a host turn at G and the Reorg67 release through a
`RELEASE_REORG67_TEST_ONLY` phase under (가) TEST_ONLY and Class T Regtest only, never a product path; (나) the
label line `Done:Born` (G) → `Refuse:Locked(Reorg67)` → (release) → `Stale` kept whole; (다) the 045b freeze's
E9-d row gains the lock step), Q6 (the local rows' records); A's answer -6554792879 Q6 (depth d: G … G + d − 1
replaced by d + 1 blocks; even r depth 1, odd r depth 2); B's unit note -6557558721 (fact 4); 045b 4.3's E9-d
row (`:418`). The code is `tools/claude_track_ardr_item4.py` (`_gate_l0`, `reorg_run_l0`,
`reorg_block_check_l0`, `expected_reorg_labels`, `expected_label_line`, `judge_label_line`) and
`tools/claude_track_ardr_l0.py` (`L0Topology(reorg=True)`, `L0Seat.observe_turn`, `L0Seat.release_reorg67`,
`check_release_test_only`, `parse_reorg`); the host phases are `set_reorged` and `set_release` in
`crates/bitagi-launch-host/tests/two_node_launch_accept.rs` (`launch_set_worker`, an ignored test). The cells are
`tests/claude_track/test_ardr_item4_l0.py`. The unit note is
`docs/claude-track/plans/notes/CT-P5-001_DRIVER_EN/2026-11-01_d3a-2b-2a-item4-reorg-l0.md`.

**Shape.** `plan_run('ITEM4_REORG', …, l0=True)` (EXPLORATORY or PR_SMOKE; D3a-2b-2b: CONFIRMATORY is refused
`ITEM4_L0_REORG_CONFIRMATORY`, exit 3, at plan time, section 26; *2026-11-25, B-B1: lifted for the TEST_ONLY release; see the addition at the end of this file (2026-11-25, B-B1 and B4-09)*): S0 the L0 project bidder, S1 the competitor (2 × the configured
rung-0 fee + 1), released after G (`SCHEDULE` `after_g`). H0 1000. On `L0Topology(reorg=True)` the miner's driver
user is its D1 set plus `invalidateblock`; the relay keeps its D1 set; Node A and Node B are oe's nodes (oe's
driver user; `check_l0_topology` reads no `.rpcs` on them, `ITEM4_REORG_TOPOLOGY` otherwise). L0 alone releases
rung 0 before G; block G must hold it and no other rung of its set (`ITEM4_L0_NOT_IN_G`).

**The reorg** (`reorg_run_l0`). After the G turn: the competitor's rung 0 is released; depth 2 mines G + 1 and
the host turns there (`G+1`), so the host has seen every block the reorg replaces (`ITEM4_L0_TURNS`
otherwise); the template-cache wait (section 23); `invalidateblock` G on the miner (`ITEM4_REORG_TIP`); d + 1
replacement blocks under the REORG context (the miner drops rung 0 by txid, section 23), the last waited for
by all four nodes. Each replacement block is read from its own bytes (`block_hit`, section 24) and must hold
no L0 transaction, by any txid of the set or by any spend of L0's funding outpoint whatever its txid
(`reorg_block_check_l0`: `ITEM4_WINNER_READDED`). The replaced chain's Core replay must have rung 0 alone born
(`ITEM4_REPLACED_NOT_WINNER`); the FINAL chain must have no rung of the set born (`ITEM4_WINNER_STILL_BORN`).

**Turns on the replacement tip G + d.** `REORGED` (`set_reorged`): one turn; the host's hook raises Reorg67 and
binds the ancestor; the worker asserts the raise, the open lock `[Reorg67]` and the ancestor, and keeps the
operator's copy. Its `reorg` line must be the reorg the driver made (`ITEM4_L0_REORG_SEEN`): `raised` true,
`local` the host's last tip (G, or G + 1 at depth 2), `at_local` the replacement's block at that height,
`ancestor` (G − 1). `RELEASE` (the `RELEASE_REORG67_TEST_ONLY` phase, `set_release`): see (가) below; one turn
presents the TDS 6.7 procedure file the worker writes from the copy (step 6 not performed); its `released`
line must be `reason:Reorg67;step6:Some(NotPerformed)` (`L0_RELEASE_NOT_REORG67`) and its `reorg` line `-`.
`release_reorg67` checks the file against the driver's own reads (`oe.check_reorg_procedure`: local, at_local,
ancestor, step 6) inside one try/finally that removes the procedure file and the release record on every path
from the record's write on; `reorg_run_l0` removes both again after the RELEASE turn, whatever happened in it.
`STALE` (`set_observe`): one turn, `reorg` `-`. Node A and Node B must be at the turn's block
(`ITEM4_L0_OBSERVE_TIP`).

**(가) TEST_ONLY, Class T Regtest only.** The release runs only through `L0Seat.release_reorg67`, which first
calls `check_release_test_only`: the mark `RELEASE_REORG67_TEST_ONLY`, scenario `ITEM4_REORG`, mode EXPLORATORY
or PR_SMOKE (*2026-11-25, B-B1: or CONFIRMATORY, 045b :1069; see the addition at the end of this file (2026-11-25, B-B1 and B4-09)*), and Node A's and Node B's `getblockchaininfo` `chain` both `regtest`; otherwise
`L0_RELEASE_NOT_TEST_ONLY` (exit 5) before any host process. The public `observe_turn` never runs
`set_release` (`L0_OBSERVE_PHASE`); only `release_reorg67` reaches that turn, through a private helper. The mark reaches the host in a file, not an environment value (the stages read one
input): after its checks the tool writes `host/release-record.txt` (mode 0600), exactly the TEST_ONLY Class T
release record (`RELEASE_RECORD_TEST_ONLY`, host `SET_RELEASE_RECORD`: `TEST_ONLY Class T D3a-2b-2a:
RELEASE_REORG67_TEST_ONLY, TDS 6.7 procedure record, step 6 not performed (1D3 Q17)`), and removes it with the
procedure file on every path (above). The host's `set_release` phase refuses unless that file is those bytes (`E3D3_RELEASE_TEST_ONLY`) before
it writes the procedure file, whose `procedure_sha256` is that record's digest (the tool checks it,
`L0_PROCEDURE_NOT_TEST_ONLY`). The worker is an ignored test in `crates/*/tests`. No file under `crates/*/` but
`crates/*/tests/`, under `.github/workflows/` or under `scripts/` names the phase, the mark, the record file, the
host phases, the record, the record constant or the release keyword, and in `tools/` only the item-4 and L0
modules do, and so does A's judge (`claude_track_ardr_judge.py`, J5), which names the phase and the host phases `set_release` and `set_reorged` only to read them from the raw log and runs nothing (cell `ReleaseTestOnly`).

**Labels (045b 4.3 E9-d with (나)).** Every turn is judged by verdict, outcome and both flags
(`expected_reorg_labels`, CONTINUE_WITHIN_LIMITS only, `ITEM4_L0_MISS` otherwise); the next birth is the FINAL
replay's at the turn's height:

| Turn | Rung 0 | Rungs k ≥ 1 | `opening_block_missed` |
|---|---|---|---|
| `G`, `G+1` (replaced chain) | `Done:Born@<H0>+opening` / `Born@<H0>+opening` | `Done:ProjectBornByOther@<H0>` / `ProjectBornByOther@<H0>` | false |
| `REORGED`, `RELEASE` | `Refuse:Locked(Reorg67)` / `Stale@<H0>><next birth>` | the same | true |
| `STALE` | `Refuse:GateAdvanced` / `Stale@<H0>><next birth>` | `Wait:OfflineSignaturePending` / `Stale@<H0>><next birth>` | true |

`reorged_before_inclusion` is false at every turn (block H0 − 1, where rung 0 was submitted, is not replaced).
`ITEM4_L0_LABEL_LINE` writes rung 0's line, every turn's verdict and outcome in order with the release step
(`RELEASE_REORG67_TEST_ONLY` and its `released`) after `RELEASE`, each step with its height and tip hash, and
compares it with `expected_label_line` (nothing dropped or added); a mismatch there or in any `ITEM4_LABELS`
line is `ITEM4_LABEL_MISMATCH` after all are written.

**Raw-log events** (in addition to sections 22-24's):

| Event | Fields |
|---|---|
| `ITEM4_L0_OBSERVE` | section 24's, `phase` (`set_observe`, `set_reorged`, `set_release`), `reorg` (parsed or null), `released`, and at `RELEASE` `procedure` (`fields`, `chains`, `mark`) |
| `REORG` | `depth`, `invalidated`, `node`, `replaced` and `replacement` (height, block hash), `tip`, `winner`, `winner_offered`, `set_txids`, `outpoint`, `checked_by`, `template_cache_wait_ns` |
| `ITEM4_L0_RELEASE` | `attempt_id`, `turn`, `height`, `block_hash`, `step`, `released`, `procedure_sha256`, `chains`, `local`, `at_local`, `ancestor` (display order) |
| `ITEM4_L0_LABEL_LINE` | `line`, `expected`, `match`, `steps` (each turn's step with `height`, `block_hash`), `release`, `rule` |
| `GATE_END`, `RUN_END` | section 24's, and `reorg`: the `REORG` record's fields with `replaced_born` (the replaced chain's replay births) and `release` (`ITEM4_L0_RELEASE`'s fields) |

A's #658 integration check (issuecomment-6565529813, P3-3):

- `GATE_END`'s (and `RUN_END`'s) `block_hash`, `order` and `height` are the FINAL chain's block G′ (the
  replacement at H0); `l0_turns[0]` (and `l0_turns[1]` at depth 2) carry the replaced block's hash, the tip the
  host saw at G (and G + 1).
- `l0_charged_not_released_after_g` (section 24: from the first turn after G) comes, in an ITEM4_REORG run,
  from the G turn on the replaced chain, so rung 1 reads `Done:ProjectBornByOther@1000` there. The final tip's
  answer (`Wait:OfflineSignaturePending` for a rung never released) is in the STALE turn's `ITEM4_L0_OBSERVE`;
  A's judge reads it there (A's decision: documented, no code change).
- Order and conditions: `ITEM4_L0_RELEASE` is written after the STALE turn and its checks; `ITEM4_L0_LABEL_LINE`
  only after the turn list passed (`ITEM4_L0_TURNS`). `ITEM4_L0_OBSERVE.reorg` is the parsed line (`local` and
  `ancestor` as [height, internal-order hash], `at_local` internal order), while `ITEM4_L0_RELEASE`'s `local`,
  `at_local` and `ancestor` are in display order.

The set worker's lines (section 22) gain `reorg` and `released` after `flags`, on every phase (`-` when none):
`reorg` is `raised:<true|false>;local:<h>:<hash>;at_local:<hash|below>;ancestor:<h>:<hash>` (`-` for no
ancestor), hashes in internal byte order (host `set_reorg`); `released` is `reason:<lock>;step6:<status>`.

| Code | Exit | Raised by | When |
|---|---|---|---|
| `ITEM4_L0_NOT_IN_G` | 2 | item4 | (reorg) block G does not hold L0's rung 0 alone of its set |
| `ITEM4_L0_REORG_SEEN` | 2 | item4 | the `REORGED` turn's `reorg` line is not the driver's reorg, or a later turn reports one |
| `ITEM4_DEPTH` | 2 | item4 | a reorg depth other than 1 or 2, or the plan's depth not the run index's |

## 26. CONFIRMATORY with the L0 seat and the hosted L0 build (D3a-2b-2b)

Class T Regtest development evidence only; every value is PENDING_FREEZE / DRAFT. No CONFIRMATORY dispatch
happens here (only A dispatches). Sources: A's answer #258 issuecomment-6557723699 (Q5, Q6), its correction
-6557914275, the D3a-2b-1 and D3a-2b-2a notes' section 5. The unit note is
`docs/claude-track/plans/notes/CT-P5-001_DRIVER_EN/2026-11-01_d3a-2b-2b-l0-confirmatory.md`.

**One entry.** A CONFIRMATORY run of ITEM2 or of one of the four item-4 experiments runs the L0 project seat,
and it enters through the driver's CLI only (`run --mode CONFIRMATORY`, as every slice calls it). The driver
imports `claude_track_ardr_l0` lazily inside `_run_l0` (as it imports item 2 and item 4); the driver stays
outside XD-1's closure (`tests/claude_track/test_xd1_workflow.py`), and so does the L0 module. The L0 module's
own `run --l0-seat` stays DRAFT / EXPLORATORY: it refuses CONFIRMATORY before it reads anything
(`CONFIRMATORY_CAMPAIGN_NOT_BUILT`, exit 3). Its Python API runs (`item2_l0_run`, `item4_l0_run`) refuse a
CONFIRMATORY plan that comes without the policy's `l0_seat` values (`L0_CONFIRMATORY_OUTSIDE_DRIVER`, exit 6,
before any node): only the driver's `_run_l0` passes them. EXPLORATORY and PR_SMOKE runs through the driver keep today's
paths (item 2's D2-3b run, item 4's stand-in seat). *Dated line 2026-11-10 (B, FZ-6, A #759 issuecomment-6749449323): F1: `load_policy` imports the L0 module lazily too, in CONFIRMATORY for an experiment with an `l0_seat`, for `confirmatory_l0_seat` only (order of checks below); the one CONFIRMATORY L0 entry is still `_run_l0`. n1: the Python API runs also refuse a CONFIRMATORY plan whose values are the STOP_CAMPAIGN twin (`L0_STOP_CAMPAIGN_EXPLORATORY_ONLY`, exit 6, before any node), through the driver's `refuse_stop_twin`, the one check of `load_policy`, `_run_l0` and these runs.*

**Order of checks** (each before any node, output or worker): `load_policy` as before (registration and its
hash, the policy hash in the registration, exit 6; PENDING anywhere, `POLICY_PENDING`, exit 3; shape; every
experiment counted, `POLICY_COUNT_UNSET`); `ITEM4_PARAMS_MISSING`; `STARTED_AT_MISSING` (exit 3); then `_run_l0`:
`POLICY_PARAMS_UNSET` (exit 3, no params), `L0_FREEZE_PENDING` (exit 3, `confirmatory_l0_seat`: the policy
has no `l0_seat`), `L0_POLICY_P0_RULE` / `L0_POLICY_ATTEMPTS` / `L0_POLICY_BUDGET_NOT_PRODUCT` (exit 6, its values are not the run's;
the last one B-FZ-a FZ-2), `L0_STOP_CAMPAIGN_EXPLORATORY_ONLY` (exit 6; *2026-11-10, B-FZ-p round 2, A #258 [Dated line 2026-11-10 (B, FZ-6): the date 2026-11-10 of this B-FZ-p line is UTC 2026-11-09, A #759 issuecomment-6749449323, F3.]
issuecomment-6744913177: the policy's `exact_height_miss` is STOP_CAMPAIGN, the twin `9ea208bd…` of A's frozen
record, EXPLORATORY only; CONFIRMATORY takes CONTINUE_WITHIN_LIMITS, `7d0a7a35…`, only*; *2026-11-09, B-FZ-p
fix round 1: `load_policy` refuses it first, so CONFIRMATORY `check-policy` refuses it too and a CONFIRMATORY
run stops there; `_run_l0` keeps the check for a `loaded` given to `run_l0` directly*), the plan (item 2 with
the frozen seat; item 4 with `l0=True`; neither takes an override or the control row; ITEM4_REORG is refused
`ITEM4_L0_REORG_CONFIRMATORY`; *2026-11-25, B-B1: not at plan time any more; `item4_run` refuses a CONFIRMATORY ITEM4_REORG run off the TEST_ONLY release before any node; see the addition at the end of this file (2026-11-25, B-B1 and B4-09)*), `OUTPUT_EXISTS`. Main-only
dispatch and attempt 1 stay the workflow's and the slice tool's checks (section 13). The L0 workers are the
repository's own builds: `target` (the host) and `target/offline-build` (the offline signer); the CLI takes
no other target. *Dated line 2026-11-10 (B, FZ-6 F1, A #759 issuecomment-6749449323): in CONFIRMATORY `load_policy` now also runs `confirmatory_l0_seat` on the experiment's `l0_seat`, when it has one, right before its STOP_CAMPAIGN check, so `check-policy` and every CONFIRMATORY run refuse `L0_POLICY_P0_RULE`, `L0_POLICY_ATTEMPTS` and `L0_POLICY_BUDGET_NOT_PRODUCT` (exit 6) there, before `ITEM4_PARAMS_MISSING` and `STARTED_AT_MISSING`; a policy without the key still reaches `_run_l0`'s `POLICY_PARAMS_UNSET` and `L0_FREEZE_PENDING`, and `_run_l0` keeps its own call for a `loaded` given to `run_l0` directly.*

**The policy key `l0_seat`** (A #258 issuecomment-6565897037 Q1: A's judge reads only the raw logs and the
frozen policy, which the registration binds). `experiments.ITEM2.l0_seat` and, for each item-4 experiment,
`experiments.ITEM4_<scenario>.l0_seat` (the policy has no `ITEM4` entry; each item-4 experiment is its own):

```json
{"p0_rule": "CEIL_2_5_B", "max_gate_attempts": 24, "exact_height_miss": "CONTINUE_WITHIN_LIMITS",
 "budget_sha256": "<64 lowercase hex>", "seat": 2}
```

`seat` (1-4, the PUBLIC seat L0 takes) is ITEM2's only; no other key is allowed (`POLICY_L0_SEAT`, exit 2,
every mode; a PENDING string may stand for any value). Seat 0 is refused `POLICY_L0_SEAT_PRIVATE` (exit 2, every
mode): it is the even runs' private seat, which `plan_run` refuses, so a frozen 0 would refuse half the runs. `p0_rule` must be
`CEIL_2_5_B` (p_0 = ⌈2.5 b⌉, item 2's `l0_p0`) and `max_gate_attempts` the budget record's 24 (exit 6 otherwise,
before any node); the run uses the key's `exact_height_miss` (the budget record and `GATE_END` carry it) and
item 2's `seat`; `budget_sha256` must be the SHA-256 of the product's `budget.json` that the set charge writes
(checked after the charge, `L0_POLICY_BUDGET_SHA256`; under today's draft record and
CONTINUE_WITHIN_LIMITS it is `3a1050ad…387cc5d`). B-FZ-a FZ-2 (2026-11-09): it is also checked before any node.
Today's product writes that record from its own fixture (the Regtest genesis, the Q1 draft values and the
placeholder digests `fee_policy_sha256` 0x11.., `disposition_policy_sha256` 0x22..,
`first_beat_operations_sha256` 0x33..), so its SHA-256 depends on `exact_height_miss` only; the L0 module pins it
(`PRODUCT_BUDGET_SHA256`: STOP_CAMPAIGN `572ed789…b5a7d9bb`, CONTINUE_WITHIN_LIMITS `3a1050ad…387cc5d`, both
observed on real nodes), and `confirmatory_l0_seat` refuses any other `budget_sha256` for that `exact_height_miss`
`L0_POLICY_BUDGET_NOT_PRODUCT` (exit 6). A frozen record whose bytes differ from the product's is therefore
refused before any node until the product writes those bytes (a `crates/` change). *2026-11-10 (B-FZ-p, FD-CT-67: [Dated line 2026-11-10 (B, FZ-6): the date 2026-11-10 of this B-FZ-p line is UTC 2026-11-09, A #759 issuecomment-6749449323, F3; #664 put the file on main, `317ecbf5`.]
signer test code, no `crates/*/src` change, A #258 issuecomment-6744913177; A #258 issuecomment-6743375133,
-6744276619): the product's L0 worker now writes A's frozen Class T L0 record,
`docs/claude-track/preregistration/CAMPAIGN_BUDGET_V1_CLASS_T_REGTEST_L0.json` (#664), byte for byte (signer
`FROZEN_L0_BUDGET`; its `fee_policy_sha256` is the L0 chain's sign input `fee_policy_id`). `PRODUCT_BUDGET_SHA256` is
CONTINUE_WITHIN_LIMITS `7d0a7a35…7c7f4dd4` (the file) and STOP_CAMPAIGN `9ea208bd…b3a26d0` (its one
`exact_height_miss` edit; EXPLORATORY only, not approved); the Q1 draft digests above are history, and the
draft bytes are refused (`L0_BUDGET_NOT_FROZEN`). Item 2's L0 cap is the record's `max_fee_per_candidate_sat`
30,000.* The module constants (`L0_SEAT`, `BUDGET_DRAFT`,
`EXACT_HEIGHT_MISS`) stay the DRAFT / EXPLORATORY defaults only. A fills the key in the 045b freeze PR. *Dated line 2026-11-10 (B, FZ-6, C27 pointer; sources 045b :1194's C27 dated line and A #664 issuecomment-6746599499): A filled it, 045b :1194 (the F3 L0 policy keys row: `CEIL_2_5_B`, 24, CONTINUE_WITHIN_LIMITS, `7d0a7a35…`) and :1901 (section 14.21), in the frozen policy `docs/claude-track/preregistration/ARDR_POLICY_V1_CLASS_T_REGTEST_FIRST.json` (`624428cc…`; ITEM2 only, the item-4 keys come with its follow-up policy).*

**Where the values came from, in the log** (#667 A integration check P3-2; B-FZ-a, #667 A 6571519328 P3-1).
`REGISTERED_POLICY` is written only in CONFIRMATORY. In a CONFIRMATORY ITEM2 run `RUN_START` has
`l0_seat_source` `REGISTERED_POLICY` (the policy's seat); in every CONFIRMATORY L0 run `L0_LAUNCH_START` has
`budget_source` `REGISTERED_POLICY` and the policy's `budget_sha256` (the record the charge must write) and no
`budget_draft`. A DRAFT / EXPLORATORY / PR_SMOKE run with a policy's `l0_seat` values (the L0 CLI's
`--policy-l0-seat`, below) writes `POLICY_VALUE` in both places, with the policy's `budget_sha256`. Any other
DRAFT / EXPLORATORY / PR_SMOKE run keeps `DRAFT_PARAMETER` (or `PENDING_FREEZE`) and `budget_source`
`BUDGET_DRAFT` with the module's `budget_draft`. In every L0 run `L0_BUDGET` has `policy_compare`: `EQUAL` (and
`policy_budget_sha256`) when a policy digest was compared with the product's record, `NO_POLICY_VALUE` otherwise.

**The freeze-checklist command (045b F3 command; B-FZ-a FZ-1).** The L0 CLI's `run --mode EXPLORATORY
--policy-l0-seat` reads the policy file's own `experiments.ITEM2.l0_seat` through `confirmatory_l0_seat`, as a
CONFIRMATORY run does (its seat, `exact_height_miss` and `budget_sha256`; the digest before any node and after
the charge), with no registration. `--l0-seat` is then refused (`L0_SEAT_SOURCE`). Its raw log shows the digest
compared and equal (`L0_BUDGET` `policy_compare` `EQUAL`) and labels the values `POLICY_VALUE`. It needs the two
Core bin dirs and the built L0 workers; no network and no secret. The TEST_ONLY policy
`tests/claude_track/ardr_fz1_policy_test_only.json` (seed `00..1f`, b 3000, seat 2, CONTINUE_WITHIN_LIMITS)
is the throwaway one; the B-FZ-a note gives the command and its outputs.

**What blocks CONFIRMATORY today.** For every policy in the tree the first refusal is `load_policy`'s:
`REGISTRATION_MISSING` without a registration, `POLICY_PENDING` with one (the draft policies hold PENDING
values). A registered policy without PENDING values and without `l0_seat` stops at `L0_FREEZE_PENDING` (exit 3),
before any node; with a PENDING `l0_seat` it stops at `POLICY_PENDING` (the policy read comes first).

| Refusal | Before | After D3a-2b-2b |
|---|---|---|
| `ITEM4_L0_NOT_BUILT` (driver, item4) | every item-4 CONFIRMATORY run | retired: CONFIRMATORY runs the L0 seat |
| `CONFIRMATORY_CAMPAIGN_NOT_BUILT` (driver) | ITEM2, ITEM3 CONFIRMATORY | ITEM3 only |
| `CONFIRMATORY_CAMPAIGN_NOT_BUILT` (item2 `plan_run`) | every CONFIRMATORY plan | replaced by `CONFIRMATORY_NEEDS_L0_SEAT` (no seat) |
| `CONFIRMATORY_CAMPAIGN_NOT_BUILT` (l0 DRAFT CLI) | every CONFIRMATORY run | unchanged |
| `L0_RELEASE_NOT_TEST_ONLY` in CONFIRMATORY (l0) | refused | unchanged (still refused) *2026-11-25, B-B1: no longer for ITEM4_REORG with the mark on Regtest nodes, still for every other release (045b :1069)* |
| `ITEM4_L0_REORG_CONFIRMATORY` (item4 `plan_run`) | none | new: a CONFIRMATORY ITEM4_REORG run with the L0 seat, at plan time *2026-11-25, B-B1: lifted for the TEST_ONLY release; `item4_run` raises it, before any node, for a CONFIRMATORY ITEM4_REORG plan off that release* |
| `L0_FREEZE_PENDING` (l0, via the driver) | none | new: the one that blocks a PENDING-free registered policy today |

**Item 4 CONFIRMATORY** runs the L0 path of section 24 for ITEM4_SELF_DEALING, ITEM4_FEE_ASYMMETRY and
ITEM4_CENSORSHIP. ITEM4_REORG waits for A's decision on whether the TEST_ONLY Reorg67 release (section 25,
condition (가)) may run in a CONFIRMATORY run: `check_release_test_only` still refuses CONFIRMATORY (*until 2026-11-25: B-B1, the dated line at the end of this paragraph*), and
`plan_run` refuses a CONFIRMATORY ITEM4_REORG run with the L0 seat `ITEM4_L0_REORG_CONFIRMATORY` (exit 3) (*until 2026-11-25: B-B1, the dated line at the end of this paragraph*) before
any node or output, so it never fails mid-run at the release. Lifting it is that one check and the release
check's mode set. The control row (a turn at every block) is a local check only. *Dated line 2026-11-25 (B, B-B1, FD-CT-67; WORK_TABLE B4-26; 045b :1069, A's decision 2026-11-02, option (ㄱ)): A decided that a CONFIRMATORY E9-d run with the L0 seat uses the TEST_ONLY release, with its mark in the raw log. B-B1 lifts the plan-time refusal for that release only: `plan_run` plans a CONFIRMATORY ITEM4_REORG run with the L0 seat, `check_release_test_only` takes CONFIRMATORY for ITEM4_REORG with the mark on Regtest nodes, and `item4_run` refuses any other release path `ITEM4_L0_REORG_CONFIRMATORY` (exit 3) before any node. See the addition at the end of this file (2026-11-25, B-B1 and B4-09).*

| Code | Exit | Raised by | When |
|---|---|---|---|
| `CONFIRMATORY_NEEDS_L0_SEAT` | 3 | item2, item4 | a CONFIRMATORY plan without the L0 seat (item 2 without a seat, item 4 with the stand-in) |
| `ITEM2_OVERRIDE_CONFIRMATORY` | 2 | item2 | a CONFIRMATORY item-2 plan with a schedule override |
| `ITEM4_L0_CONTROL_CONFIRMATORY` | 2 | item4 | a CONFIRMATORY item-4 plan with the control row |
| `ITEM4_L0_REORG_CONFIRMATORY` | 3 | item4 | a CONFIRMATORY ITEM4_REORG plan with the L0 seat: waits for A's decision on the Reorg67 release in CONFIRMATORY (before any node or output) *2026-11-25 (B-B1; 045b :1069): lifted for the TEST_ONLY release. Now `item4_run` (`check_confirmatory_release`), before RUN_START and any node: a CONFIRMATORY ITEM4_REORG plan without the L0 seat or whose `reorg_release` is not `RELEASE_REORG67_TEST_ONLY`* |
| `L0_RUN_MODE` | 2 | driver | `_run_l0` called outside a CONFIRMATORY ITEM2 or item-4 run |
| `POLICY_L0_SEAT` | 2 | driver | an `l0_seat` key outside ITEM2 and the item-4 experiments, or not the shape above |
| `POLICY_L0_SEAT_PRIVATE` | 2 | driver | ITEM2's `l0_seat.seat` is 0, the even runs' private seat (every mode, before any node) |
| `L0_STOP_CAMPAIGN_EXPLORATORY_ONLY` | 6 | driver | (B-FZ-p round 2, 2026-11-10; A #258 issuecomment-6744913177) a CONFIRMATORY L0 run whose `l0_seat.exact_height_miss` is STOP_CAMPAIGN (A's frozen record's twin `9ea208bd…`, EXPLORATORY only); after `confirmatory_l0_seat`, before the plan and any node, output or worker. The L0 CLI's EXPLORATORY `--policy-l0-seat` still takes it. *2026-11-09 (B-FZ-p fix round 1): also `load_policy` in CONFIRMATORY, so `check-policy` and every CONFIRMATORY run refuse it, before `_run_l0`'s own check* *Dated line 2026-11-10 (B, FZ-6): the date 2026-11-10 is UTC 2026-11-09 (A #759 issuecomment-6749449323, F3). n1: the L0 module's Python API runs (`item2_l0_run`, `item4_l0_run`) refuse a CONFIRMATORY plan whose values are the twin the same way, through the driver's `refuse_stop_twin`.* |

**Hosted L0 build (A Q6).** `.github/workflows/claude-track-ardr.yml` builds the L0 workers exactly as the
L0 seat's stages call them, so a run compiles nothing inside a stage's time:

- online: `cargo test --locked --no-run -p bitagi-launch-host --test two_node_launch_accept` (target `target`);
- offline: `RUSTFLAGS='--cfg bitagi_offline_build'`, `CARGO_TARGET_DIR=target/offline-build`,
  `cargo test --locked --no-run -p bitagi-signer --features offline-ceremony --test launch_host_e2e_sign` (the
  offline-export workflow's cfg and directory). `CARGO_INCREMENTAL` is `0` job-wide; the run step does not set
  `RUSTFLAGS` (the L0 seat refuses it, `RUSTFLAGS_SET`).

A separate pull-request job, `ardr-l0-real-nodes` ("ARDR L0 real-node rows (Core 31.1 + 30.3, Class T)"),
runs in parallel with the PR smoke job (which is unchanged): checkout without persisted credentials, the head
check, Python, the toolchain, Core 31.1 and 30.3 with the pinned SHA-256, the generator worker, the two L0
builds, then the L0 real-node rows (`BITAGI_ARDR_L0_REAL=1`, work under `$RUNNER_TEMP`; none may be skipped):
item 4 `RealNodesItem4L0` `test_self_dealing`, `test_fee_asymmetry`, `test_censorship`, `test_reorg_depth_1`,
`test_reorg_depth_2`, and item 2 `RealNodesLadder` (rows a, b, c). The control row stays local. The job is not a
required check (A #258 issuecomment-6565897037 Q3). Right after the head check it diffs the PR's
`base...head` with `git diff --no-renames --name-only` and runs the rest only when a changed path is one of the
workflow's `pull_request` paths (except the format text, the two PR smoke policies and the S04 log excerpt,
which no row reads; the trigger paths include everything under `crates/bitagi-launch-host/` and
`crates/bitagi-signer/`, whose test helpers and workers the rows build, and the `src/` of every other crate the
two workers compile by path: their path-dependency closure, which a cell computes from the Cargo.toml files and
pins) or matches A's patterns (`tools/claude_track_ardr_*.py`,
`tests/claude_track/test_ardr_*.py`, `crates/bitagi-launch-host/tests/`, `crates/bitagi-signer/tests/`); otherwise it prints "no changed files" and
ends green without building. The rows step runs `tests/claude_track/ardr_l0_rows.py`, which names the eight
rows, reports each from unittest's result as one `L0_ROW <test id> <outcome>` line (`ok`, `FAIL`, `ERROR`,
`SKIPPED`, `MISSING`, `EXPECTED_FAILURE`, `UNEXPECTED_SUCCESS`; all eight, also after a failure) and exits
non-zero unless all eight are `ok`. A slice job whose dispatch is CONFIRMATORY
and whose experiment is ITEM2 or an item-4 experiment builds them before it runs its units (inside the slice's
setup minutes, counted in `--spent-seconds`). The jobs keep their `refs/heads/main` guards,
`persist-credentials: false`, permissions and pins; no secret and no trigger is added.

## Addition to section 4 (2026-11-02, 045b freeze draft 1)

A dated addition to section 4 (:153-159), placed at the end of this file so that every line above keeps its number (A #258 issuecomment-6561758412, A's decision on the D2-2 hash registration). The CT-P5-005 registration file carries a second key, `d2_2_tool_sha256`: the SHA-256 of the bytes of `tools/claude_track_ardr_cluster.py` at the registration commit, as 64 lowercase hex. The driver still reads only `ardr_policy_sha256` and ignores any other key (section 4). The judge reads `d2_2_tool_sha256` (`docs/claude-track/formats/ARDR_JUDGE_V1.md` section 3): every `CLUSTER_TOOL.tool_sha256` in a CONFIRMATORY log must equal it, and on the workflow path the file's bytes at the run's commit bind the same lines (`D2_2_TOOL_NOT_AT_RUN_COMMIT`). The registration list's shape (a method-hash key; one schema per list) is set at the 045b freeze.

## Addition to section 22 (2026-11-10, L0-501)

A dated addition to section 22 (:1745-2064; the `L0_RUNG_TEST` row :1980, the codes :1994, :2005, :2045) and to
section 24's rung tests (:2304-2309), placed at the end of this file so that every line above keeps its number (the
frozen 045b cites this file by line). Source: A's decision on #258, issuecomment-6764861681 (unit L0-501, owner B,
FD-CT-67). Unit note: `docs/claude-track/plans/notes/CT-P5-001_DRIVER_EN/2026-11-10_l0-501.md`. Class T Regtest
development evidence only.

**`L0_RUNG_TEST` `nodes`.** The other fields are unchanged. `nodes` holds Node A's and Node B's
`testmempoolaccept` answer as returned plus one field, `replaces_in_mempool` (bool): whether the rung the tested
rung replaces was in that node's mempool when that node answered. It is read with `getmempoolentry` on the same
node right before that node's `testmempoolaccept` (Node A's read, Node A's test, Node B's read, Node B's test).
The replaced rung is, for `BEFORE_RELEASE`, rung k − 1 (then the last rung released) and, for
`CHARGED_NOT_RELEASED_BEFORE_G`, the last rung released at that time (rung 0 for every charged rung when only
rung 0 went out). An untested rung (`untested_reason` `TIP_NOT_G_MINUS_1`) keeps `nodes` null and makes no read.
The field means what item 2's synthetic `TESTMEMPOOLACCEPT` `replaces_in_mempool` means (section 20; item 2 reads
it from `getrawmempool`). A node answer that already holds the key is refused, so the node's own words are never
overwritten.

**The read's mapping.** An entry (one JSON object) is true. bitcoin-cli's RPC error -5 with Core's message
"Transaction not in mempool" (the two stderr lines `error code: -5` and `Transaction not in mempool`) is false.
Everything else fails closed with an existing code, and the rung gets no test record: any other error (another
code, or -5 with another message) is `PREREQUISITE RPC_FAILED A getmempoolentry` / `B` (exit 3; the read goes
through oe's driver user, as the seat's other `getmempoolentry` reads, so this extends :1994); a call past 300 s
is `PREREQUISITE NODE_CALL_TIMEOUT A` / `B` (exit 3, :2005, section 21); and an answer that is not one JSON object,
a node answer that already holds `replaces_in_mempool`, or a replaced rung the seat cannot name (another `when`,
no rung released, a last released rung that is not k − 1 before a release or not below k after the releases) is
`MISMATCH L0_RUNG_TEST` (exit 2, extending :2045). No new code.

**A failed attempt's rung tests.** When the L0 thread failed, `finish` writes the rung tests gathered in the
attempt (each released rung k ≥ 1's, taken right before its step 8) as `L0_RUNG_TEST` lines, by k, just before it
raises that error: after the remaining `L0_TURN` lines and the released rungs' `L0_ADMISSION` lines, as the
attempt's last L0 lines. So a released rung refused by both nodes' `testmempoolaccept` and then at step 8
(`MISMATCH L0_SET_SEND k`, the attempt FAILED) keeps its refusal in the raw log. Nothing else changes on that path:
the other lines, their order, the error and the FAILED outcome are as before. Without an error, `finish` writes
the rung tests where it always did (after the admissions, before `L0_BUDGET`), one per rung k ≥ 1, and the lines
are as before apart from the new field. Each rung's line is written once per attempt: the two writes are the two
outcomes of one check of the thread's error, which can no longer change (the thread has ended). Still without
rung tests in the log (as before): an attempt that fails after that check (`L0_FEE_MISMATCH`, or a refused read or
answer in a charged rung's test), and one whose `finish` never reads the thread's error (item 2 failing before it
calls `finish`, or `L0_NOT_FINISHED`).

**Which runs write `L0_RUNG_TEST`.** Only `L0Seat.finish`, reached through item 2's `_l0_release`: ITEM2 runs with
the L0 seat (both `when` values) and the item-4 runs with it (rung 0 is the only rung released, so
`CHARGED_NOT_RELEASED_BEFORE_G` only; section 24). ITEM1 and POOL runs have no L0 seat and never write it.

## Addition to section 13 (2026-11-11, B-UM)

A dated addition to section 13 (:534-1114; the plan refusals :579-593, the `UNIT_MINUTES_SHORT` row :1110), placed at
the end of this file so that every line above keeps its number (the frozen 045b cites this file by line). Source: A's
request on #258, issuecomment-6768800772 (unit B-UM, owner B, FD-CT-67), its scope issuecomment-6791687759, and
Reviewer RV-185 (b), issuecomment-6783082453. Unit note: `docs/claude-track/plans/notes/CT-P5-001_DRIVER_EN/2026-11-11_b-um.md`.
Class T Regtest development evidence only.

**The rule.** `plan` refuses a CONFIRMATORY ITEM2 dispatch whose `unit_minutes` x 60 is below 1,500 s: exit 6
`UNIT_MINUTES_SHORT`, the code and exit of the ITEM1 and POOL check (U3), so section 13's table keeps its rows. The
row :1110 stays byte-identical and names the ITEM1 and POOL condition only; this addition extends that row to the
CONFIRMATORY ITEM2 condition. 25 minutes (1,500 s) is taken, 24 is refused. The check runs right after the ITEM1
and POOL check and before the declaration is written, so a refused dispatch declares nothing and no slice runs
(:591-592). It applies to CONFIRMATORY ITEM2 only: an EXPLORATORY ITEM2 dispatch (the PR smoke's one unit of 15
minutes, or 5 minutes) is taken as before, and ITEM1, POOL, ITEM3 and the item-4 experiments are unchanged.
`check_declaration` does not apply it, so an earlier run's declaration is still read (the re-dispatch check,
recollect).

**The value.** 1,500 s is t_G's bound plus an allowance: `ITEM2_GATE_SECONDS` 1,200 (the driver's `GATE_INTERVAL_N`;
t_G is uniform in [1, 1,200] s, 045b :559, and the unit waits t_G after G - 1 before block G's template) plus
`ITEM2_OVERHEAD_SECONDS` 300 for the unit's time besides t_G (driver start, nodes, the blocks up to G - 1, the L0
seat's charge and signing, the replay and teardown). That time was measured at 23.1-31.4 s a unit on hosted runners
without the L0 seat (EXPLORATORY campaign 42826277310), 21.8-36.7 s on hosted runners with the L0 seat (the
`ARDR L0 real-node rows` jobs' `item2_l0_run`, t_G overridden), and 36-41 s locally with the L0 seat (t_G 679 s and
1,193 s); 300 s is about 7.3 times the largest. The tool's constant is tied to the driver's by a test.

**What it does not change.** `unit_minutes` bounds an ITEM2 unit only through the slice's kill at `unit_minutes` x
60 s (`UNIT_TIMEOUT`; the ITEM2 driver ignores `--unit-seconds`), so a higher `unit_minutes` does not lengthen a
normal unit; it only lowers how many units a slice holds. With 10 units a slice, the slice budget (`SLICE_BUDGET`,
30 + 10 x `unit_minutes` + 15 <= 330) allows 25 to 28 minutes; A's decision of 2026-11-11 (issuecomment-6783840771)
is 28 minutes, 10 units a slice. The floor does not cover the failure paths' own limits (an L0 ready, a node call, a
block accept); a unit that reaches one is FAILED or EXCLUDED either way.

## Addition to section 4 (2026-11-12, FD-CT-133)

A dated addition to section 4 (:153-159) and to the addition to section 4 of 2026-11-02 above, placed at the end of
this file so that every line above keeps its number (the frozen 045b cites this file by line). Source: Founder
decision FD-CT-133 (2026-11-12T00:06:51Z; receipt #258 issuecomment-6810346851; A's plan #807
issuecomment-6810354648; decision file `docs/claude-track/decisions/FD-CT-133_2026-11-12.md`). Unit note:
`docs/claude-track/plans/notes/CT-P5-005_EN/2026-11-12_d4-item2-out.md`. Class T Regtest development evidence only.

**The rule.** The first CT-P5-005 registration covers ITEM1 and POOL; ITEM2 goes in a follow-up registration. Its
frozen policy still lists ITEM2, so the policy hash the registration binds is not enough to keep ITEM2 out. The
driver therefore reads a second registration key, `experiments`, when the registration has it: a non-empty list of
strings naming the experiments the registration covers. In CONFIRMATORY, right after `POLICY_NOT_REGISTERED` and
before the policy is parsed, a run whose experiment is not in that list is refused, exit 6
`EXPERIMENT_NOT_REGISTERED`; a key whose value is not such a list (a string, an empty list, a non-string entry,
`null`) is exit 2 `REGISTRATION_SHAPE`. A registration without the key is read as before (section 4: the D1
placeholder). The rule covers `check-policy` and `run`, so every CONFIRMATORY unit a slice runs: a refused unit
writes no raw-log line, so the slice records it `BEFORE_START` (section 13), and a later dispatch under the
follow-up registration may still run it. EXPLORATORY and PR_SMOKE take no registration and are unchanged.

**What it does not change.** The judge does not read `experiments`: it judges logs, and the driver writes no
CONFIRMATORY ITEM2 line under a registration that leaves ITEM2 out. `tools/claude_track_p5005_registration.py`
writes the key (`["ITEM1", "POOL"]`) and, before it accepts a registration, checks that the tree's driver refuses
ITEM2 under it with `EXPERIMENT_NOT_REGISTERED` (`DRIVER_RUNS_UNREGISTERED_EXPERIMENT` otherwise).

## L0's p_0 rule after FD-CT-133 (dated 2026-11-12, B4-80, finding #807)

*Dated section 2026-11-12 (B, B4-80, FD-CT-67; A's design #807 issuecomment-6810795838, A's answers
issuecomment-6811277603). STEP-02: the lines above that say `CEIL_2_5_B` (`:2050`, `:2534`, `:2541`) are cited
and stay as they are; this section is added at the end.*

- **The rule.** L0's p_0 is the largest integer p_0 with 2b ≤ p_0 ≤ 4b whose 045b `:537` ladder
  `ladder(p_0, b, 0, v)` has exactly two rungs, counted at i = 0 and v = 213. Its rung 1 is then the cap fee
  floor(4b × v / 1000). One function computes it, `tools/claude_track_ardr_bidders.py` `l0_p0(b, v)`. Item 2's
  `l0_p0(b)` and the driver's `item4_project_p0(b)` both call it. For b = 6000 it is 16,000, with the ladder
  [3,408, 5,112].
- **The name.** The driver's `L0_P0_RULE`, which a CONFIRMATORY `l0_seat.p0_rule` must equal (`L0_POLICY_P0_RULE`,
  exit 6), is now `MAX_P0_TWO_RUNGS`. A policy whose `p0_rule` is `CEIL_2_5_B` is refused there. The first
  registration's frozen policy keeps `CEIL_2_5_B` in its ITEM2 `l0_seat` (its bytes do not change). The first
  registration (ITEM1, POOL; A's D4 unit, FD-CT-133) does not read that seat through this check. ITEM2's follow-up
  registration binds a policy with `MAX_P0_TWO_RUNGS`.
- **New refusals.**

| Code | Exit | Where | When |
|---|---|---|---|
| `L0_P0_NO_TWO_RUNGS` | 2 | bidders `l0_p0` | no p_0 in [2b, 4b] gives a two-rung ladder (b × v below about 667, e.g. b = 1); it replaces `ITEM2_L0_LADDER_EMPTY` for L0 |
| `L0_P0_INPUT` | 2 | bidders `l0_p0` | b or v not a positive int |
| `ITEM2_L0_LADDER_NOT_TWO_RUNGS` | 2 | item 2 `l0_ladder` | at the run's `i` (the nodes' `incrementalfee`) the ladder is not two rungs ending at the cap fee; at the L0 seat's `start`, before its charge, signing or broadcast (the item-2 gate's funding and setup run before it; Desktop #823 r4546050104) |

## Addition to sections 5, 25 and 26 (2026-11-25, B-B1 and B4-09)

*Dated section 2026-11-25 (B, FD-CT-67; WORK_TABLE B4-26 and B4-09; unit note
`docs/claude-track/plans/notes/CT-P5-001_DRIVER_EN/2026-11-25_b1-item4-reorg-release.md`). The lines above that it
changes keep their place; each carries a dated pointer here.*

- **ITEM4_REORG in CONFIRMATORY (B-B1; 045b :1069, A's decision 2026-11-02, option (ㄱ); A #258
  issuecomment-6656311995 B1).** A CONFIRMATORY E9-d run with the L0 seat uses the TEST_ONLY release, with its mark
  in the raw log; the judge report labels the row "release: Class T test step" (ARDR_JUDGE_V1 :1561). The
  D3a-2b-2b refusal at plan time (`ITEM4_L0_REORG_CONFIRMATORY`) is lifted for that release path only.
  - `plan_run('ITEM4_REORG', …, l0=True)` plans in every mode. The plan's `reorg_release` names the run's one
    Reorg67 release path: `RELEASE_REORG67_TEST_ONLY` for ITEM4_REORG with the L0 seat, null in every other plan.
    `reorg_run_l0` hands it to `L0Seat.release_reorg67` as the mark.
  - `item4_run` refuses an ITEM4_REORG plan in CONFIRMATORY, or in any mode but EXPLORATORY and PR_SMOKE (fail
    closed), without the L0 seat or whose `reorg_release` is anything else, `ITEM4_L0_REORG_CONFIRMATORY` (exit 3),
    right after its adapter check: before RUN_START, the worker directory and any node (`check_confirmatory_release`).
    On the driver's path the plan is `plan_run`'s; a plan given to the Python API `item4_l0_run` is refused there
    after that function made the work directory and the raw-log file, which stays empty.
  - `check_release_test_only` takes EXPLORATORY, PR_SMOKE and CONFIRMATORY. In each, a release without the mark,
    off ITEM4_REORG or with Node A or Node B not on `regtest` is `L0_RELEASE_NOT_TEST_ONLY` (exit 5) before any
    host process, and so is a release in any other mode.
  - The raw-log mark is the two existing fields the judge reads (ARDR_JUDGE_V1 :1611-1612, A's Q10): the RELEASE
    turn's `ITEM4_L0_OBSERVE` `procedure.mark` and the one `ITEM4_L0_RELEASE` `step` (section 25's events), both
    `RELEASE_REORG67_TEST_ONLY`. B-B1 adds no event or field and changes no EXPLORATORY or PR_SMOKE line; B4-38
    changes only the `ITEM4_SELF_ZERO_FEE_REGISTER` reason text (`SCENARIO_NOT_RUN`), which the judge does not compare.
- **The pool's exclusion unit (B4-09; 045b :1085, judge decision 6, #258 issuecomment-6557890079 and
  -6567369540).** Section 5's default "run for item 4 and the pool run" (`:176-177`; 045b :1085 cites it as
  `:169`) holds for item 4 only. For the pool the exclusion unit is the gate: its "a run of 4 gates" defines its
  run unit, and its 10% rule counts gates, more than 20 of its 200 gates.
