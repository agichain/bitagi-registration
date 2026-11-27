#!/usr/bin/env python3
"""CT-P5-001 D2-1: the TEST_ONLY synthetic-bidder / competitor REGISTER generator and the bidder-list input.

Class T Regtest development evidence only; never mainnet, never S17-PREP, and no ARDR verdict. Sources: A's
unit request #258 issuecomment-6537782009 (Q2, Q3, section 4 row D2), A's answer -6538196742 (1E Q15: one
TEST_ONLY competitor generator, the product wallet with a second TEST_ONLY key set and its own ledger, marked
COMPETITOR; D2's synthetic bidders use the same generator), and the 045b draft sections 4.3-4.6
(`CT-P3-045b_PREREGISTRATION_DRAFT_EN.md`), a draft input, not frozen bytes. Format:
`docs/claude-track/formats/ARDR_RUN_V1.md` sections 9-12.

What D2-1 builds:

- The generator: the ignored Rust worker `crates/bitagi-signer/tests/ardr_bidder_generator.rs` builds, signs
  and releases every REGISTER through the product wallet and signer path (each bidder's own fresh ledgers per
  gate; SYNTHETIC and COMPETITOR are separate key sets and ledger identities). This tool writes its request
  lines, runs it, and reads its answer lines (public bytes only; no key scalar crosses).
- Item 1 synthetic owners: 40 wallets, 10 owners (`OWNER_Wii`, n = 10), shared funding ancestry within an
  owner (`ANCESTRY_Wii` < 30), Anchor key reuse (`KEY_REUSE_Wii` < 30), all with D1's `draw`. The funding
  follows 045b :351 and is placed once per run, before the run's first gate: one common fan-out from the
  Regtest funding source (outside the boundary, its txid is excluded), then per owner one non-coinbase
  owner funding transaction that pays each of the owner's ancestry-flagged wallets one output per gate the
  wallet bids in. So an owner's flagged wallets that win different gates share that one ancestor. The
  ground truth (`BITAGI_CT_ARDR_GROUND_TRUTH_V1`) records owners, flags, the
  funding actually placed and the links it places, for D2-2's clustering tool; `cluster_truth_projection`
  gives D2-2's `BITAGI_CT_ARDR_CLUSTER_TRUTH_V1` view of it.
- Rung fees: 045b 4.6's formula (`ladder`), `p_0` from `BID_FEE_j` with n = 3b + 1 and j the seat index
  (`gate_bids`). A ladder whose rung 0 is over the cap is empty (DEFAULT, PENDING_FREEZE): the seat bids
  nothing (LADDER_EMPTY). A gate where every seat's ladder is empty would have no REGISTER and no winner,
  which D2-2's gates input cannot carry; `BID_FEE_j` depends only on (seed, run, j, b), so `plan_gates`
  refuses such a run before any node starts (RUN_GATE_NO_BID_G<gate>, exit 2; DEFAULT, PENDING_FREEZE).
- The bidder list (`BITAGI_CT_ARDR_BIDDERS_V1`): which seats bid in a gate, SYNTHETIC / COMPETITOR /
  L0_PROJECT; the L0 seat is refused (exit 3, `L0_PROJECT_SEAT_NOT_BUILT`) until D3a-1 fills it.
- The hand-off: a PUBLIC seat's rung goes to the relay node (`sendrawtransaction`); a PRIVATE seat's rung goes
  only to D1's miner process. A private rung never reaches `sendrawtransaction`.

Exit codes (AGENTS.md section 12) as D1's. Optimized Python (-O) is refused. Stdlib only. TEST_ONLY material
only: every key is a TEST_ONLY key from the policy seed (DRAFT rule, PENDING_FREEZE), every ledger is a
TEST_ONLY Class T ledger.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).absolute().parent))
import claude_track_ardr_driver as D  # noqa: E402
import claude_track_regtest_offline_export as oe  # noqa: E402

Refusal, invalid = D.Refusal, D.invalid
EXIT_DONE, EXIT_VALIDATION, EXIT_PREREQUISITE = D.EXIT_DONE, D.EXIT_VALIDATION, D.EXIT_PREREQUISITE

BIDDERS_SCHEMA = 'BITAGI_CT_ARDR_BIDDERS_V1'
GROUND_TRUTH_SCHEMA = 'BITAGI_CT_ARDR_GROUND_TRUTH_V1'
# D2-2's ARDR_CLUSTER_V1 section 6, as it stands at 36e1e62e (claude/b-p5001-d2-cluster, PR #616)
CLUSTER_TRUTH_SCHEMA = 'BITAGI_CT_ARDR_CLUSTER_TRUTH_V1'
LABELS = ['CLASS_T', 'REGTEST', 'TEST_ONLY_KEYS_FROM_POLICY_SEED', 'KEY_RULE_FROZEN_045B_F13',   # FZ-6: 045b :1221 (F13)
          'CLASS_T_DEVELOPMENT_EVIDENCE_NOT_S17_PREP']
WALLETS, OWNERS = 40, 10
COMPETITORS = 10
SHARE_BELOW = 30          # ANCESTRY_Wii and KEY_REUSE_Wii: value < 30 of n = 100
MAX_RUNG = 7              # 045b 4.6: a ladder ends after rung 7
KINDS = ('SYNTHETIC', 'COMPETITOR', 'L0_PROJECT')
PATHS = ('PUBLIC', 'PRIVATE')
MAX_SEATS = 5               # the draw table has BID_FEE_0..BID_FEE_4 (045b 4.6); BID_FEE_j is seat j's
FUNDING_VALUE = 1_000_000   # sat per bidder funding output (one per wallet and gate)
FUNDING_FEE = 10_000        # sat per funding transaction (funding_tx)
OWNER_SLACK = 2 * FUNDING_FEE   # an owner funding transaction's input: its outputs + its fee + its change
# The most seats (one funding output each) a bidder list may hold over all its gates: 200 gates x 5 seats,
# 045b 4.6's item 1 run. The fan-out then has at most 1,001 outputs of 43 bytes (34-byte P2TR or P2WSH
# script): 172,389 WU (43,098 vB), under the 400,000 WU standard weight, and FUNDING_FEE over 43,098 vB is
# 232 sat/kvB, over the 100 sat/kvB minrelaytxfee of Core 30.3 and 31.1 (ARDR_RUN_V1 section 9).
MAX_FUNDING_OUTPUTS = 1_000
WORKER_TEST = 'worker::ardr_bidder_worker'
# The measured vsize (vB) of the product REGISTER shape (one P2TR key-path input; carrier, Anchor and change
# outputs): 045b 4.6's `v`. Every built rung is checked against it.
CANDIDATE_VSIZE = 213
SYNTHETIC_ID = re.compile(r'W([0-3][0-9])\Z')
COMPETITOR_ID = re.compile(r'C(0[0-9])\Z')


def wallet_id(i: int) -> str:
    return f'W{i:02d}'


# ---------------------------------------------------------------------------------------------------------
# Item 1 ownership (045b 4.6 `item 1 ownership clusters` and `item 1 Anchor keys`), with D1's draw.

def assignment(seed: bytes, run: int) -> dict:
    """Owner, shared-ancestry flag and key-reuse flag of every synthetic wallet, and each owner's planted
    facts: base wallet (lowest index), and the planted owner (most wallets, lowest owner index on ties)."""
    wallets = {}
    for i in range(WALLETS):
        w = wallet_id(i)
        owner, _ = D.draw(seed, 'ITEM1', run, f'OWNER_{w}', OWNERS)
        ancestry, _ = D.draw(seed, 'ITEM1', run, f'ANCESTRY_{w}', 100)
        reuse, _ = D.draw(seed, 'ITEM1', run, f'KEY_REUSE_{w}', 100)
        wallets[w] = {'owner': f'O{owner}', 'shares_ancestry': ancestry < SHARE_BELOW,
                      'reuses_base_key': reuse < SHARE_BELOW,
                      'draws': {'OWNER': owner, 'ANCESTRY': ancestry, 'KEY_REUSE': reuse}}
    owners = {}
    for o in range(OWNERS):
        members = sorted(w for w, v in wallets.items() if v['owner'] == f'O{o}')
        owners[f'O{o}'] = {'wallets': members, 'base_wallet': members[0] if members else None}
    planted = max(range(OWNERS), key=lambda o: (len(owners[f'O{o}']['wallets']), -o))
    return {'wallets': wallets, 'owners': owners, 'planted_owner': f'O{planted}'}


def anchor_label(plan: dict, wallet: str, heart: int) -> str:
    """The key label of `wallet`'s Heart number `heart`: the owner's base key (its base wallet's first Heart)
    when the wallet reuses it, else the wallet's own fresh key for that Heart."""
    if not 0 <= heart < 1000:
        raise invalid('HEART_INDEX')
    entry = plan['wallets'][wallet]
    if entry['reuses_base_key']:
        return f"SYNTHETIC_{plan['owners'][entry['owner']]['base_wallet']}_ANCHOR_H000"
    return f'SYNTHETIC_{wallet}_ANCHOR_H{heart:03d}'


def pairs(members: list[str]) -> list[list[str]]:
    return [[a, b] for i, a in enumerate(members) for b in members[i + 1:]]


def funding_layout(plan: dict, gates: list[dict]) -> dict:
    """The funding of a whole run (045b :351), placed once before the run's first gate. Each seat of each
    gate gets its own output (`(wallet, gate)`). One common fan-out from the Regtest funding source pays
    every unflagged SYNTHETIC wallet and every competitor directly, one output per gate it bids in, and one
    output per owner that has an ancestry-flagged SYNTHETIC wallet anywhere in the run; that owner's one
    non-coinbase owner funding transaction spends it into one output per (flagged wallet, gate). The fan-out
    is outside the boundary; the owner transactions are inside it. Returns `{"direct": [(wallet, gate)],
    "owners": [{"owner", "wallets", "outputs": [(wallet, gate)]}]}` in gate / seat / owner order."""
    direct, by_owner = [], {}
    for g in gates:
        for s in g['seats']:
            key = (s['wallet'], g['gate'])
            if s['kind'] == 'SYNTHETIC' and plan['wallets'][s['wallet']]['shares_ancestry']:
                by_owner.setdefault(plan['wallets'][s['wallet']]['owner'], []).append(key)
            else:
                direct.append(key)
    ordered = sorted(by_owner.items(), key=lambda item: int(item[0][1:]))
    owners = [{'owner': o, 'wallets': sorted({w for w, _ in keys}), 'outputs': keys} for o, keys in ordered]
    return {'direct': direct, 'owners': owners}


def build_funding(layout: dict, source: tuple[str, int], source_value: int,
                  fee_scripts: dict[str, bytes]) -> dict:
    """The funding transactions of `layout`: the fan-out spending `source` (a TEST_ONLY P2WSH(OP_TRUE)
    output), then the owner funding transactions spending its owner outputs. Returns the raw transactions in
    send order, the fan-out txid (the excluded set), each owner's funding txid and each `(wallet, gate)`'s
    funding outpoint."""
    outs = [(FUNDING_VALUE, fee_scripts[w]) for w, _ in layout['direct']]
    outs += [(FUNDING_VALUE * len(g['outputs']) + OWNER_SLACK, D.PAYOUT_SCRIPT) for g in layout['owners']]
    fan_raw = funding_tx(source, source_value, outs)
    fan = D.Tx(fan_raw)
    funding = {key: {'txid': fan.txid, 'vout': n, 'value': FUNDING_VALUE} for n, key in enumerate(layout['direct'])}
    raws, owner_txids = [fan_raw], {}
    for k, g in enumerate(layout['owners']):
        vout = len(layout['direct']) + k
        raw = funding_tx((fan.txid, vout), fan.outputs[vout][0],
                         [(FUNDING_VALUE, fee_scripts[w]) for w, _ in g['outputs']])
        tx = D.Tx(raw)
        raws.append(raw)
        owner_txids[g['owner']] = tx.txid
        funding.update({key: {'txid': tx.txid, 'vout': n, 'value': FUNDING_VALUE}
                        for n, key in enumerate(g['outputs'])})
    return {'raws': raws, 'excluded_txids': [fan.txid], 'owner_txids': owner_txids, 'funding': funding}


def funding_sent_fields(funding: dict, txid: str, seats: dict) -> dict:
    """`FUNDING_SENT`'s `wallets`, `outputs` and `kinds` for the funding transaction `txid` (ARDR_RUN_V1
    section 12): `outputs` lists its `(wallet, gate)` keys in output (vout) order, `kinds` follows `outputs`,
    and `wallets` is the sorted set of their wallets. The fan-out's owner outputs and each transaction's
    change output come after its keys' outputs and are not keys, so `outputs[i]` is vout i of `txid`."""
    paid = sorted((key for key, f in funding.items() if f['txid'] == txid), key=lambda key: funding[key]['vout'])
    return {'wallets': sorted({w for w, _ in paid}), 'outputs': [[w, g] for w, g in paid],
            'kinds': [seats[w]['kind'] for w, _ in paid]}


def funding_by_wallet(funding: dict) -> dict[str, dict[str, str]]:
    """`{(wallet, gate): {"txid", ...}}` → `{wallet: {"<gate>": txid}}`, the ground truth's per-gate map."""
    out: dict[str, dict[str, str]] = {}
    for (w, gate), f in sorted(funding.items()):
        out.setdefault(w, {})[str(gate)] = f['txid']
    return out


def ancestry_groups(plan: dict, funding: dict[str, dict[str, str]], excluded_txids: list[str]) -> list[dict]:
    """The ANCESTRY groups the funding actually placed over the whole run: the wallets with a funding output
    (in any gate) of one shared transaction inside the boundary (not excluded). A group has exactly one
    funding txid and at least two distinct wallets; its wallets must be of one owner and ancestry-flagged
    (else GROUND_TRUTH_ANCESTRY, exit 2). `funding` is wallet → {gate: txid}."""
    by_txid: dict[str, set[str]] = {}
    for w, per_gate in funding.items():
        if w not in plan['wallets']:
            continue
        for txid in per_gate.values():
            if txid is not None and txid not in excluded_txids:
                by_txid.setdefault(txid, set()).add(w)
    groups = []
    for txid, members in by_txid.items():
        if len(members) < 2:
            continue
        owners = {plan['wallets'][w]['owner'] for w in members}
        if len(owners) != 1 or not all(plan['wallets'][w]['shares_ancestry'] for w in members):
            raise invalid('GROUND_TRUTH_ANCESTRY')
        groups.append({'kind': 'ANCESTRY', 'owner': owners.pop(), 'wallets': sorted(members),
                       'funding_txids': [txid]})
    return sorted(groups, key=lambda g: (int(g['owner'][1:]), g['wallets']))


def ground_truth(seed: bytes, run: int, plan: dict, funding: dict[str, dict[str, str]], competitors: list[str],
                 winners: dict[str, str] | None = None, excluded_txids: list[str] | None = None,
                 gates: list[dict] | None = None) -> dict:
    """The ground-truth record for D2-2. `funding` maps each funded wallet to its per-gate funding txids
    (`{"<gate>": txid}`); `winners` maps each winning REGISTER txid to its wallet; `excluded_txids` lists the
    common fan-out funding transactions from the Regtest funding source (the clustering method's boundary,
    besides the coinbase outputs); `gates` lists each gate's `gate`, `height`, `status` (always `BID`:
    `gate_row`) and `born` txids (exactly one). Links
    placed: ANCESTRY groups derived from the funding actually placed (`ancestry_groups`) and ANCHOR_KEY groups
    (one Anchor key, read on chain as the REGISTER's vout[1] P2TR program). An ANCHOR_KEY link is on chain
    only once both ends are (D2-3 records which are)."""
    excluded = sorted(excluded_txids or [])
    groups = ancestry_groups(plan, funding, excluded)
    keys: dict[str, list[str]] = {}
    for w in sorted(plan['wallets']):
        keys.setdefault(anchor_label(plan, w, 0), []).append(w)
    for label, members in sorted(keys.items()):
        if len(members) > 1:
            groups.append({'kind': 'ANCHOR_KEY', 'owner': plan['wallets'][members[0]]['owner'],
                           'wallets': sorted(members), 'anchor_label': label})
    ancestry = [p for g in groups if g['kind'] == 'ANCESTRY' for p in pairs(g['wallets'])]
    key_links = [p for g in groups if g['kind'] == 'ANCHOR_KEY' for p in pairs(g['wallets'])]
    return {
        'schema': GROUND_TRUTH_SCHEMA,
        'labels': LABELS,
        'seed_sha256': hashlib.sha256(seed).hexdigest(),
        'run': run,
        'boundary': 'REGTEST_FUNDING_SOURCE_AND_COINBASE_OUTPUTS_EXCLUDED',
        'excluded_txids': excluded,
        'planted_owner': plan['planted_owner'],
        'owners': plan['owners'],
        'wallet_to_owner': {w: v['owner'] for w, v in sorted(plan['wallets'].items())},
        'winners': dict(sorted((winners or {}).items())),
        'gates': list(gates or []),
        'wallets': {w: {**v, 'set': 'SYNTHETIC', 'funding_txids': dict(sorted(funding.get(w, {}).items())),
                        'anchor_label_h0': anchor_label(plan, w, 0)} for w, v in sorted(plan['wallets'].items())},
        'competitors': {c: {'set': 'COMPETITOR', 'owner': competitor_owner(c),
                            'funding_txids': dict(sorted(funding.get(c, {}).items()))} for c in competitors},
        'link_groups': groups,
        'links': {'ancestry': ancestry, 'anchor_key': key_links},
    }


def record_anchor_placed(truth: dict, winner_anchor_scripts: dict[str, str], label_scripts: dict[str, str]) -> dict:
    """D2-3a: each ANCHOR_KEY group's `placed_wallets`, the winning wallets whose REGISTER's vout[1] carries
    the group's key (read from the REGISTER bytes, `winner_anchor_scripts` txid → script hex; the key's script
    from the worker's KEYS answer for the group's label). An ANCHOR_KEY link is on chain only between placed
    wallets. A wallet that reuses the base key carries it on every Heart; the base wallet carries it on its
    first Heart only (`anchor_label`), and its first winning REGISTER is that Heart."""
    for group in truth['link_groups']:
        if group['kind'] != 'ANCHOR_KEY':
            continue
        script = label_scripts[group['anchor_label']]
        group['placed_wallets'] = sorted({truth['winners'][t] for t, s in winner_anchor_scripts.items()
                                          if s == script and truth['winners'][t] in group['wallets']})
        # D2-3a round 1 (P3-8): checked at run time: the members whose winning REGISTER carries the group's
        # key are exactly the group's winning wallets (D2-2's P_L-restricted group); otherwise a REGISTER
        # carried another key than the plan says (ANCHOR_PLACED_MISMATCH, exit 2).
        if group['placed_wallets'] != sorted(set(group['wallets']) & set(truth['winners'].values())):
            raise invalid('ANCHOR_PLACED_MISMATCH')
    return truth

def competitor_owner(wallet: str) -> str:
    """Every competitor is its own owner (`COMPETITOR_C00`, …): no shared owner joins two competitors."""
    if not COMPETITOR_ID.match(wallet):
        raise invalid('BIDDERS_WALLET')
    return f'COMPETITOR_{wallet}'


def cluster_truth_projection(gt: dict) -> dict:
    """GROUND_TRUTH_V1 → D2-2's CLUSTER_TRUTH_V1 (ARDR_CLUSTER_V1 section 6 at 36e1e62e; ARDR_RUN_V1 section
    12): `winners` as is; `owners` wallet → owner over the synthetic wallets and the competitors;
    `planted_links` one `{"kind", "wallets"}` per link group. D2-3 adds the converter file and the cross-tool
    cell; this function is the projection it must equal. D2-2 restricts each planted group to the winning
    wallets first and then closes the restricted groups (its P_L rule), so a planted link counts only when
    at least two of its wallets win."""
    if gt.get('schema') != GROUND_TRUTH_SCHEMA:
        raise invalid('GROUND_TRUTH_SCHEMA')
    owners = dict(gt['wallet_to_owner'])
    owners.update({c: v['owner'] for c, v in gt['competitors'].items()})
    return {'schema': CLUSTER_TRUTH_SCHEMA, 'winners': dict(gt['winners']),
            'owners': dict(sorted(owners.items())),
            'planted_links': [{'kind': g['kind'], 'wallets': list(g['wallets'])} for g in gt['link_groups']]}


def write_lf(path: Path, value) -> bytes:
    """One JSON document, sorted keys, ASCII, ending in exactly one LF; a new file only."""
    data = (json.dumps(value, sort_keys=True, indent=1) + '\n').encode('ascii')
    with path.open('xb') as stream:
        stream.write(data)
    return data


# ---------------------------------------------------------------------------------------------------------
# Rung fees (045b 4.6 `item 2 release schedule`, with p_0 in place of b).

def ceil_div(a: int, b: int) -> int:
    return -(-a // b)


def node_increments(nodes) -> tuple[int, dict[str, int]]:
    """D3a-2b-1 (A #258 issuecomment-6557890079 request 1, decision 9): the ladder's `i` is the larger of
    Node A's and Node B's `getnetworkinfo` `incrementalfee` (sat/kvB), read per run, as the L0 seat's (045b
    1.3). Returns (that `i`, both values) so the caller logs both. `ladder` stays the one fee formula."""
    increments = {role: oe.sats(nodes[role].call('getnetworkinfo')['incrementalfee']) for role in ('A', 'B')}
    return max(increments.values()), increments


def ladder(p0: int, b: int, i: int, v: int) -> list[int]:
    """Absolute rung fees: f_0 = ceil(p0 v / 1000); r_k = ceil(p0 3^k / 2^k);
    f_k = max(ceil(r_k v / 1000), f_(k-1) + max(1, ceil(i v / 1000))); the ladder ends before the first rung
    with f_k × 1000 > 4b × v, or after rung 7. When that first rung is rung 0 (only through rounding: p0 = 4b
    region with b not a multiple of 250 at v = 213), the ladder is empty (DEFAULT, PENDING_FREEZE): the seat
    bids nothing, the raw log records LADDER_EMPTY and the gate continues."""
    for name, value in (('p0', p0), ('b', b), ('i', i), ('v', v)):
        if type(value) is not int or value < (0 if name == 'i' else 1):
            raise invalid('LADDER_INPUT')
    if not b <= p0 <= 4 * b:
        raise invalid('LADDER_P0_RANGE')
    fees = [ceil_div(p0 * v, 1000)]
    if fees[0] * 1000 > 4 * b * v:
        return []
    step = max(1, ceil_div(i * v, 1000))
    for k in range(1, MAX_RUNG + 1):
        r_k = ceil_div(p0 * 3**k, 2**k)
        fee = max(ceil_div(r_k * v, 1000), fees[-1] + step)
        if fee * 1000 > 4 * b * v:
            break
        fees.append(fee)
    return fees


def l0_p0(b: int, v: int) -> int:
    """FD-CT-133 (A #807 issuecomment-6810795838): the L0 seat's p_0 is the largest integer p_0 with 2b <= p_0 <= 4b
    whose `ladder(p_0, b, 0, v)` has exactly two rungs. From 2b up no rung 2 fits (r_2 = ceil(2.25 p_0) > 4b), and
    f_0 and f_1 never fall as p_0 rises, so the rung count only falls (2, 1, 0) and a binary search finds the last
    p_0 with two; its rung 1 is then the cap fee floor(4b v / 1000) (f_1 rises at most 1 sat per step of p_0). None
    in range is L0_P0_NO_TWO_RUNGS. Counted at i = 0 (A, QL-1), so the policy and the judge get the same p_0 before
    any run; the run checks its own ladder at its `i` (item 2's `l0_ladder`). The one source: item 2's `l0_p0` and
    the driver's `item4_project_p0` call it."""
    for name, value in (('b', b), ('v', v)):
        if type(value) is not int or value < 1:
            raise invalid('L0_P0_INPUT')
    low, high = 2 * b, 4 * b
    if len(ladder(low, b, 0, v)) != 2:
        raise invalid('L0_P0_NO_TWO_RUNGS')
    while low < high:   # ladder(low) has two rungs; no p_0 above high has
        mid = (low + high + 1) // 2
        if len(ladder(mid, b, 0, v)) == 2:
            low = mid
        else:
            high = mid - 1
    return low


def bid_feerate(seed: bytes, run: int, bidder: int, b: int) -> int:
    """`BID_FEE_j` (unconstrained runs): n = 3b + 1, feerate b + value, so uniform in [b, 4b] (D1 note R.6)."""
    value, _ = D.draw(seed, 'ITEM2', run, f'BID_FEE_{bidder}', 3 * b + 1)
    return b + value


def gate_bids(seed: bytes, run: int, gate: dict, b: int, increment: int, v: int = CANDIDATE_VSIZE
              ) -> tuple[list[dict], list[tuple[str, dict]]]:
    """One gate's per-seat step, without a node: seat j draws `BID_FEE_j`, its ladder follows, and it bids
    (a non-empty ladder) or logs LADDER_EMPTY. A gate where no seat bids also logs GATE_NO_BID; a run with
    such a gate is refused before any node starts (`plan_gates`), so in a run the event is only reached
    through a defect (the run then refuses, GATE_NO_BID). Returns the bids (`{"seat": <seat>, "j", "p0",
    "fees"}`, seat order) and the raw-log events in write order."""
    bids, events = [], []
    for j, s in enumerate(gate['seats']):
        p0 = bid_feerate(seed, run, j, b)
        events.append(('DRAW', {'e': 'ITEM2', 'r': run, 'label': f'BID_FEE_{j}', 'value': p0 - b, 'feerate': p0}))
        fees = ladder(p0, b, increment, v)
        if not fees:
            events.append(('LADDER_EMPTY', {'seat': s['seat'], 'kind': s['kind'], 'feerate': p0}))
            continue
        bids.append({'seat': s, 'j': j, 'p0': p0, 'fees': fees})
    if not bids:
        events.append(('GATE_NO_BID', {'gate': gate['gate'], 'seats': [s['seat'] for s in gate['seats']]}))
    return bids, events


def plan_gates(seed: bytes, run: int, gates: list[dict], b: int) -> None:
    """The plan-time no-bid check (DEFAULT for A, PENDING_FREEZE): every gate needs at least one seat with a
    non-empty ladder, else the run is refused before any node starts (`RUN_GATE_NO_BID_G<gate>`, exit 2).
    Whether a ladder is empty depends only on rung 0 (`f_0 × 1000 > 4b × v`), so only on `BID_FEE_j`
    (seed, run, j, b), never on the nodes' incremental relay fee: `gate_bids` runs with i = 0 here. One
    empty seat in a gate with another bid is not refused; the run logs its LADDER_EMPTY."""
    for gate in gates:
        bids, _ = gate_bids(seed, run, gate, b, 0)
        if not bids:
            raise invalid(f"RUN_GATE_NO_BID_G{gate['gate']}")


def gate_row(gate: dict, height: int, bids: list[dict], born: list[str], rung_txids: set[str]) -> dict:
    """One `gates` row of the ground truth, after the Core replay of block G. D2-2 takes exactly one
    `winner_txid` per gate, so this refuses (exit 2; the row is never written) a gate with no bid
    (GATE_NO_BID: unreachable from a run that passed `plan_gates`), a bid gate whose replay shows no birth
    or more than one (GATE_BORN_COUNT), and a birth that is not one of the gate's rung-0 txids
    (GATE_BORN_UNKNOWN). A written row's status is always BID."""
    if not bids:
        raise invalid('GATE_NO_BID')
    if len(born) != 1:
        raise invalid('GATE_BORN_COUNT')
    if born[0] not in rung_txids:
        raise invalid('GATE_BORN_UNKNOWN')
    return {'gate': gate['gate'], 'height': height, 'born': list(born), 'status': 'BID'}


# ---------------------------------------------------------------------------------------------------------
# Bidder list (format doc section 11).

def parse_bidders(blob: bytes, l0: bool = False) -> dict:
    """The bidder list: `{"schema", "gates": [{"gate": int, "seats": [{"seat", "kind", "wallet", "path"}]}]}`.
    A gate has 1-5 seats (BID_FEE_j is seat j's draw), at most one PRIVATE seat and that seat is seat 0 (045b
    4.6: bidder 0 is the private bidder when present); a wallet bids once per gate; L0_PROJECT is refused
    (exit 3), except with `l0` (D3a-1a, item 2's DRAFT L0 seat only): then a gate may hold one L0_PROJECT
    seat, PUBLIC, wallet `L0` (BIDDERS_L0_SEAT otherwise). The gate numbers are consecutive in list order (`gates[k].gate == gates[0].gate + k`; cell()
    runs list order and D2-2 refuses non-consecutive gates rows), and the list holds at most
    MAX_FUNDING_OUTPUTS seats over all gates (FUNDING_TOO_LARGE). Every refusal is before any node starts."""
    doc = D.parse_json(blob, 'BIDDERS_JSON')
    if set(doc) != {'schema', 'gates'} or doc['schema'] != BIDDERS_SCHEMA or not isinstance(doc['gates'], list):
        raise invalid('BIDDERS_SHAPE')
    seen_gates = set()
    for k, gate in enumerate(doc['gates']):
        if not (isinstance(gate, dict) and set(gate) == {'gate', 'seats'} and type(gate['gate']) is int
                and 0 <= gate['gate'] < D.U32 and isinstance(gate['seats'], list)
                and 1 <= len(gate['seats']) <= MAX_SEATS):
            raise invalid('BIDDERS_GATE')
        if gate['gate'] in seen_gates:
            raise invalid('BIDDERS_GATE_DUPLICATE')
        if gate['gate'] != doc['gates'][0]['gate'] + k:
            raise invalid('BIDDERS_GATES_NOT_CONSECUTIVE')
        seen_gates.add(gate['gate'])
        names, wallets = set(), set()
        for seat in gate['seats']:
            if not (isinstance(seat, dict) and set(seat) == {'seat', 'kind', 'wallet', 'path'}
                    and all(isinstance(seat[k], str) for k in seat)):
                raise invalid('BIDDERS_SEAT')
            if seat['kind'] not in KINDS or seat['path'] not in PATHS:
                raise invalid('BIDDERS_SEAT_KIND')
            if seat['kind'] == 'L0_PROJECT':
                if not l0:
                    raise Refusal('L0_PROJECT_SEAT_NOT_BUILT', EXIT_PREREQUISITE)   # only item 2's L0 seat
                if seat['path'] != 'PUBLIC' or seat['wallet'] != 'L0':
                    raise invalid('BIDDERS_L0_SEAT')
            else:
                pattern = SYNTHETIC_ID if seat['kind'] == 'SYNTHETIC' else COMPETITOR_ID
                if not pattern.match(seat['wallet']):
                    raise invalid('BIDDERS_WALLET')
            if seat['seat'] in names or seat['wallet'] in wallets:
                raise invalid('BIDDERS_SEAT_DUPLICATE')
            names.add(seat['seat'])
            wallets.add(seat['wallet'])
        private = [j for j, seat in enumerate(gate['seats']) if seat['path'] == 'PRIVATE']
        if len(private) > 1:
            raise invalid('BIDDERS_TWO_PRIVATE')
        if private and private[0] != 0:
            raise invalid('BIDDERS_PRIVATE_NOT_FIRST')
    if sum(len(gate['seats']) for gate in doc['gates']) > MAX_FUNDING_OUTPUTS:
        raise invalid('FUNDING_TOO_LARGE')
    return doc


def hand_off(seat: dict, raw_hex: str, relay, miner, held: set[str], log, unit: dict) -> str:
    """One rung to where its seat's path says: PUBLIC to the relay node, PRIVATE to the miner process only
    (and into the run's held private set). Returns the txid."""
    txid = D.Tx(bytes.fromhex(raw_hex)).txid
    if seat['path'] == 'PRIVATE':
        got = miner.add_private(raw_hex)
        if got != txid:
            raise invalid('PRIVATE_TXID')
        held.add(txid)
        log.write('PRIVATE_HANDOFF', unit, txid=txid, hex=raw_hex, seat=seat['seat'], kind=seat['kind'])
    elif seat['path'] == 'PUBLIC':
        answer = relay.rpc('sendrawtransaction', raw_hex)
        log.write('PUBLIC_SENT', unit, node='relay', txid=txid, hex=raw_hex, answer=answer, seat=seat['seat'],
                  kind=seat['kind'])
    else:
        raise invalid('BIDDERS_SEAT_KIND')
    return txid


# ---------------------------------------------------------------------------------------------------------
# Funding from TEST_ONLY Regtest outputs: OP_TRUE coinbase outputs into the bidders' fee outputs.

def funding_tx(prevout: tuple[str, int], value: int, outputs: list[tuple[int, bytes]]) -> bytes:
    """A version-2 transaction spending one P2WSH(OP_TRUE) output into `outputs` and an OP_TRUE change."""
    change = value - sum(v for v, _ in outputs) - FUNDING_FEE
    if change < 1_000:
        raise invalid('FUNDING_VALUE')
    outs = [*outputs, (change, D.PAYOUT_SCRIPT)]
    body = D.varint(1) + bytes.fromhex(prevout[0])[::-1] + prevout[1].to_bytes(4, 'little') + b'\x00' \
        + b'\xfd\xff\xff\xff'
    body += D.varint(len(outs)) + b''.join(v.to_bytes(8, 'little') + D.varint(len(s)) + s for v, s in outs)
    return (2).to_bytes(4, 'little') + b'\x00\x01' + body + b'\x01\x01' + D.OP_TRUE_SCRIPT + bytes(4)


# ---------------------------------------------------------------------------------------------------------
# The Rust worker (the product path).

class Worker:
    """One request file in, one answer file out, per call (`cargo test ... --ignored --exact`). A request
    holds the TEST_ONLY policy seed: it is created 0600 and unlinked once its answer is read (or the call
    fails)."""

    def __init__(self, cargo: str, seed: bytes, run: int, h0: int, work: Path):
        self.cargo, self.seed, self.run, self.h0 = cargo, seed, run, h0
        self.dir = work
        self.calls = 0

    def ask(self, lines: list[list[str]]) -> list[list[str]]:
        self.calls += 1
        request = self.dir / f'request-{self.calls}.txt'
        answer = self.dir / f'answer-{self.calls}.txt'
        text = ''.join('\t'.join(map(str, f)) + '\n' for f in
                       [['ARDR_BIDDERS_REQUEST_V1'], ['SEED', self.seed.hex(), self.run, self.h0], *lines])
        fd = os.open(request, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(text.encode('ascii'))
            return self._answer(request, answer)
        finally:
            request.unlink(missing_ok=True)

    def _answer(self, request: Path, answer: Path) -> list[list[str]]:
        ledgers = self.dir / 'ledgers'
        ledgers.mkdir(exist_ok=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith('BITAGI_ARDR_BIDDERS_')}
        env.update({'BITAGI_ARDR_BIDDERS_REQUEST': str(request), 'BITAGI_ARDR_BIDDERS_ANSWER': str(answer),
                    'BITAGI_ARDR_BIDDERS_DIR': str(ledgers.resolve())})
        try:
            done = subprocess.run([self.cargo, 'test', '--locked', '-q', '-p', 'bitagi-signer', '--test',
                                   'ardr_bidder_generator', '--', '--exact', WORKER_TEST, '--ignored',
                                   '--test-threads=1'], env=env, capture_output=True, text=True, timeout=1800,
                                  check=False)
        except subprocess.TimeoutExpired:   # U4 (A #632 6548007197 P3-7): exit 3, never retried
            raise oe.Prerequisite('WORKER_TIMEOUT') from None
        if done.returncode != 0 or not answer.is_file():
            raise oe.Prerequisite('WORKER_FAILED')
        data = answer.read_bytes()
        if not data.endswith(b'\n') or b'\r' in data:
            raise invalid('WORKER_ANSWER')
        rows = [line.split('\t') for line in data.decode('ascii').split('\n')[:-1]]
        if rows[0] != ['ARDR_BIDDERS_ANSWER_V1']:
            raise invalid('WORKER_ANSWER')
        return rows[1:]

    def keys(self, requests: list[tuple[str, str, str]]) -> dict[str, dict]:
        rows = self.ask([['KEYS', s, w, label] for s, w, label in requests])
        out = {}
        for row in rows:
            if row[0] != 'KEY' or len(row) != 6:
                raise invalid('WORKER_KEY')
            out[row[2]] = {'set': row[1], 'anchor_label': row[3], 'fee_script': row[4], 'anchor_script': row[5]}
        return out

    def build(self, set_: str, wallet: str, gate: int, tip: tuple[int, str], funding: dict, anchor: str,
              fees: list[int], state: str | None) -> list[dict]:
        rows = self.ask([['BUILD', set_, wallet, gate, tip[0], tip[1], funding['txid'], funding['vout'],
                          funding['value'], funding['height'], anchor, ','.join(map(str, fees)), state or '-']])
        keys = ('kind', 'set', 'wallet', 'gate', 'rung', 'fee', 'txid', 'vsize', 'raw_sha256', 'ledger_id',
                'candidate_id', 'lineage', 'hex')
        rungs = [dict(zip(keys, row)) for row in rows]
        if len(rungs) != len(fees) or any(r['kind'] != 'RUNG' or r['set'] != set_ for r in rungs):
            raise invalid('WORKER_RUNG')
        for r in rungs:
            r.pop('kind')
            for k in ('gate', 'rung', 'fee', 'vsize'):
                r[k] = int(r[k])
            if D.Tx(bytes.fromhex(r['hex'])).txid != r['txid']:
                raise invalid('WORKER_TXID')
            if r['vsize'] != CANDIDATE_VSIZE:
                raise invalid('CANDIDATE_VSIZE')   # 045b 4.6 needs one equal v for the campaign's candidates
            r['marks'] = [set_, 'TEST_ONLY']
        return rungs

    def birth(self, height: int, block_hex: str, state: str | None) -> dict:
        rows = self.ask([['BIRTH', height, block_hex, state or '-']])
        if len(rows) != 1 or rows[0][0] != 'BIRTH' or len(rows[0]) != 5:
            raise invalid('WORKER_BIRTH')
        _, got, born, next_birth, poststate = rows[0]
        return {'height': int(got), 'born': [] if born == '-' else born.split(','), 'next_birth': int(next_birth),
                'state': poststate}

    def births(self, first: int, blocks_hex: list[str], state: str | None, gate: int | None = None) -> dict:
        """D2-3a chained BIRTH: one `BIRTHS` request for the consecutive blocks `first`, `first + 1`, … (the
        worker refuses blocks that do not chain, BLOCK_CHAIN). Every answer row is checked here: one
        `BIRTH_ROW` per height in order (BIRTHS_ROWS), a birth only at `gate` (BIRTH_OUTSIDE_GATE; with
        `gate` None no row may have one), then `POSTSTATE` at the last height whose SHA-256 is the last
        row's (BIRTHS_POSTSTATE). Returns the rows (`height`, `born`, `next_birth`, `state_sha256`) and the
        final poststate. `births_rows` holds the checks without the worker call."""
        if not blocks_hex:
            raise invalid('BIRTHS_EMPTY')
        rows = self.ask([['BIRTHS', first, state or '-', ','.join(blocks_hex)]])
        return births_rows(rows, first, len(blocks_hex), gate)


def births_rows(rows: list[list[str]], first: int, count: int, gate: int | None) -> dict:
    """The client's checks of a `BIRTHS` answer (see `Worker.births`)."""
    if len(rows) != count + 1:
        raise invalid('BIRTHS_ROWS')
    out = []
    for k, row in enumerate(rows[:-1]):
        if len(row) != 5 or row[0] != 'BIRTH_ROW' or row[1] != str(first + k) or not D.HEX64.match(row[4]):
            raise invalid('BIRTHS_ROWS')
        born = [] if row[2] == '-' else row[2].split(',')
        if born and first + k != gate:
            raise invalid('BIRTH_OUTSIDE_GATE')
        out.append({'height': first + k, 'born': born, 'next_birth': int(row[3]), 'state_sha256': row[4]})
    last = rows[-1]
    if len(last) != 3 or last[0] != 'POSTSTATE' or last[1] != str(first + count - 1):
        raise invalid('BIRTHS_POSTSTATE')
    if hashlib.sha256(bytes.fromhex(last[2])).hexdigest() != out[-1]['state_sha256']:
        raise invalid('BIRTHS_POSTSTATE')
    return {'rows': out, 'state': last[2]}


# ---------------------------------------------------------------------------------------------------------
# The real-node cell (D1's topology): every gate of the bidder list, in order, from gate H0 on.

CELL_H0 = 110
CELL_B = 3000   # sat/kvB; the product fixture's floor is 2,000 sat/kvB over 1,200 WU (600 sat at v = 213)


def seat_anchor_label(plan: dict, seat: dict, heart: int) -> str:
    """The Anchor key label a seat bids with: SYNTHETIC per `anchor_label`, COMPETITOR its own key of Heart
    number `heart` (the Hearts the wallet already won in the run)."""
    if seat['kind'] == 'SYNTHETIC':
        return anchor_label(plan, seat['wallet'], heart)
    return f"COMPETITOR_{seat['wallet']}_ANCHOR_H{heart:03d}"


def cell(node_a: Path, node_b: Path, work: Path, out: Path, truth_path: Path, cargo: str, bidders: dict,
         seed: bytes, run: int = 0, cell_b: int = CELL_B) -> dict:
    """Setup blocks from templates; the run's funding, once, before the first gate (`funding_layout`): the
    common fan-out from the first mature coinbase (the Regtest funding source; excluded), mined, then the
    owner funding transactions, mined (all public). Then every gate of the bidder list in order: the first
    at H0, each next one at the Core replay's next birth height; blocks to G − 1 (each block from H0 on is
    replayed for the canonical state); every seat's rung 0 through the generator (`gate_bids`: an empty
    ladder logs LADDER_EMPTY); testmempoolaccept on Node A and Node B; the
    hand-off per the bidder list; block G from D1's miner process; the Core replay of the logged block G
    bytes. The worker directory (its request files hold the TEST_ONLY seed) is removed at the end. Before
    any node starts (and before any output exists) the bidder list is checked again (`parse_bidders`:
    consecutive gates, the funding bound) and so is the plan (`plan_gates`: no gate without a bid)."""
    gates = parse_bidders(json.dumps(bidders).encode('ascii'))['gates']
    plan_gates(seed, run, gates, cell_b)
    if out.exists() or work.exists() or truth_path.exists():
        raise Refusal('OUTPUT_EXISTS', EXIT_PREREQUISITE)
    work = oe.private(work)
    worker_dir = work / 'worker'
    try:
        worker_dir.mkdir()
        topology = D.Topology(node_a, node_b, work / 'nodes')
        loaded = {'mode': 'PR_SMOKE', 'evidence_status': 'EXPLORATORY', 'policy_sha256': None,
                  'registration_sha256': None}
        log = D.RawLog(out, D.log_header(loaded), topology.needles() + (str(work), str(work.resolve())))
        worker = Worker(cargo, seed, run, CELL_H0, worker_dir)
        return _cell_gates(topology, log, worker, gates, seed, run, cell_b, truth_path)
    finally:
        shutil.rmtree(worker_dir, ignore_errors=True)


def _cell_gates(topology, log, worker: Worker, gates: list[dict], seed: bytes, run: int, cell_b: int,
                truth_path: Path) -> dict:
    run_unit = D.unit_id('ITEM2', run)
    miner = None
    plan = assignment(seed, run)
    try:
        log.write('RUN_START', run_unit, observation_start={'source': 'LOCAL_EXPLORATORY', 'utc': None},
                  miner_policy='ITEM2_DEFAULT', node_versions=D.ROLE_VERSIONS)
        topology.start()
        nodes = topology.nodes
        miner = D.MinerProcess(nodes['miner'], 'ITEM2_DEFAULT')
        held: set[str] = set()
        last = [0]
        coinbases = []
        for _ in range(D.SETUP_BLOCKS):
            block = D.mine(log, run_unit, nodes, miner, held, last)
            coinbases.append((block['coinbase_txid'], block['coinbase_value']))
        seats = {s['wallet']: s for g in gates for s in g['seats']}
        keys = worker.keys([(s['kind'], w, seat_anchor_label(plan, s, 0)) for w, s in seats.items()])
        layout = funding_layout(plan, gates)
        # The first coinbase (height 1) is mature at tip SETUP_BLOCKS; every seat of every gate is funded from
        # its one fan-out, before the first gate.
        built_funding = build_funding(layout, (coinbases[0][0], 0), coinbases[0][1],
                                      {w: bytes.fromhex(k['fee_script']) for w, k in keys.items()})
        funding = built_funding['funding']
        for stage, raws in (('FAN_OUT', built_funding['raws'][:1]), ('OWNER', built_funding['raws'][1:])):
            if not raws:
                continue
            sent = []
            for raw in raws:
                tx = D.Tx(raw)
                nodes['relay'].rpc('sendrawtransaction', raw.hex())
                log.write('FUNDING_SENT', run_unit, node='relay', txid=tx.txid, hex=raw.hex(), stage=stage,
                          **funding_sent_fields(funding, tx.txid, seats))
                sent.append(tx.txid)
            oe.wait_for(lambda: set(sent) <= set(nodes['miner'].call('getrawmempool')),
                        'the funding at the miner')
            block = D.mine(log, run_unit, nodes, miner, held, last)
            for f in funding.values():
                if f['txid'] in sent:
                    f['height'] = block['height']
        increment, increments = node_increments(nodes)   # D3a-2b-1: the larger of A's and B's
        log.write('INCREMENTS', run_unit, increments=increments, increment=increment, rule='MAX_NODE_A_NODE_B')
        state, height, hearts = None, CELL_H0, {}
        winners, gate_rows, rungs_by_gate = {}, [], []

        def advance(block):
            nonlocal state
            birth = None
            if block['height'] >= CELL_H0:
                birth = worker.birth(block['height'], block['block_hex'], state)
                state = birth['state']
            return birth

        for gate_entry in gates:
            unit = D.unit_id('ITEM2', run, gate=gate_entry['gate'])
            while block['height'] < height - 1:
                block = D.mine(log, unit, nodes, miner, held, last)
                advance(block)
            tip = (block['height'], block['block_hash'])
            bids, events = gate_bids(seed, run, gate_entry, cell_b, increment)
            for event, fields in events:
                log.write(event, unit, **fields)
            if not bids:
                # A defence: plan_gates refused every plan with a gate without a bid before any node started.
                raise invalid('GATE_NO_BID')
            rungs = {}
            for bid in bids:
                s = bid['seat']
                key = (s['wallet'], gate_entry['gate'])
                built = worker.build(s['kind'], s['wallet'], height, tip, funding[key],
                                     seat_anchor_label(plan, s, hearts.get(s['wallet'], 0)), bid['fees'], state)
                rungs[s['wallet']] = built[0]
                log.write('GENERATED', unit, seat=s['seat'], ladder=bid['fees'],
                          rungs=[{k: v for k, v in r.items() if k != 'hex'} for r in built])
            bidding = [bid['seat'] for bid in bids]
            for s in bidding:
                raw = rungs[s['wallet']]['hex']
                for role in ('A', 'B'):
                    result = nodes[role].rpc('testmempoolaccept', [raw])
                    log.write('TESTMEMPOOLACCEPT', unit, node=role, txid=rungs[s['wallet']]['txid'], result=result)
                    if not (isinstance(result, list) and len(result) == 1 and result[0].get('allowed') is True):
                        raise oe.Mismatch('TESTMEMPOOLACCEPT_REGISTER')
            for s in bidding:
                hand_off(s, rungs[s['wallet']]['hex'], nodes['relay'], miner, held, log, unit)
            public = {rungs[s['wallet']]['txid'] for s in bidding if s['path'] == 'PUBLIC'}
            oe.wait_for(lambda: public <= set(nodes['miner'].call('getrawmempool')), 'the public bids at the miner')
            block = D.mine(log, unit, nodes, miner, held, last)
            birth = advance(block)
            log.write('CORE_REPLAY', unit, height=birth['height'], born=birth['born'], next_birth=birth['next_birth'])
            by_txid = {r['txid']: w for w, r in rungs.items()}
            gate_rows.append(gate_row(gate_entry, height, bids, birth['born'], set(by_txid)))
            for t in birth['born']:
                winners[t] = by_txid[t]
                hearts[by_txid[t]] = hearts.get(by_txid[t], 0) + 1
            rungs_by_gate.append({w: {k: r[k] for k in ('set', 'txid', 'fee', 'vsize')} for w, r in rungs.items()})
            gate_rows[-1]['order'] = [o['txid'] for o in block['order']]
            gate_rows[-1]['next_birth'] = birth['next_birth']
            # Every written gate has exactly one birth (gate_row), so the next gate is the replay's next birth;
            # the max only guards the loop against a next birth at or below G.
            height = max(birth['next_birth'], block['height'] + 1)
        truth = ground_truth(seed, run, plan, funding_by_wallet(funding),
                             sorted(w for w, s in seats.items() if s['kind'] == 'COMPETITOR'),
                             winners=winners, excluded_txids=built_funding['excluded_txids'],
                             gates=[{k: g[k] for k in ('gate', 'height', 'born', 'status')} for g in gate_rows])
        write_lf(truth_path, truth)
        summary = {'gates': gate_rows, 'rungs': rungs_by_gate, 'winners': winners,
                   'funding': funding_by_wallet(funding), 'owner_txids': built_funding['owner_txids'],
                   'excluded_txids': built_funding['excluded_txids']}
        log.write('RUN_END', run_unit, status='DONE', **summary)
        return summary
    finally:
        if miner is not None:
            miner.stop()
        topology.stop()
        log.close()


# ---------------------------------------------------------------------------------------------------------
# CLI.

def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = top.add_subparsers(dest='command', required=True)
    a = sub.add_parser('assign', help='item 1 owners, flags and Anchor labels from a seed')
    a.add_argument('--seed', required=True)
    a.add_argument('--run', type=int, required=True)
    f = sub.add_parser('ladder', help="045b 4.6 rung fees")
    for name in ('p0', 'b', 'i', 'v'):
        f.add_argument(f'--{name}', type=int, required=True)
    c = sub.add_parser('check-bidders')
    c.add_argument('--bidders', required=True, type=Path)
    return top


def main(argv: list[str] | None = None) -> int:
    if not __debug__:
        print(json.dumps({'result': 'FAIL', 'code': 'OPTIMIZED_PYTHON', 'exit': D.EXIT_REFUSAL}))
        return D.EXIT_REFUSAL
    args = parser().parse_args(argv)
    try:
        if args.command == 'assign':
            if not D.HEX64.match(args.seed):
                raise invalid('SEED')
            summary = assignment(bytes.fromhex(args.seed), args.run)
        elif args.command == 'ladder':
            summary = {'fees': ladder(args.p0, args.b, args.i, args.v)}
        else:
            blob = D.read_input(args.bidders, D.POLICY_LIMIT)
            doc = parse_bidders(blob)
            summary = {'bidders_sha256': hashlib.sha256(blob).hexdigest(), 'gates': len(doc['gates'])}
    except Refusal as refusal:
        print(json.dumps({'result': 'FAIL', 'code': refusal.code, 'exit': refusal.exit_code}, sort_keys=True))
        return refusal.exit_code
    print(json.dumps({'result': 'DONE', **summary, 'exit': EXIT_DONE}, sort_keys=True))
    return EXIT_DONE


if __name__ == '__main__':
    import claude_track_exit
    claude_track_exit.run(main)
