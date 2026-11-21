#!/usr/bin/env python3
"""CT-P5-001 D2-3a: D2-1's ground truth (GROUND_TRUTH_V1) into D2-2's three inputs.

Class T Regtest development evidence only; never mainnet, never S17-PREP, and no ARDR verdict. Sources: A's
answer #258 issuecomment-6543158220 (Q6, Q7), B's fact memo -6542840327 (the D2-2 input converter) and D2-2's
`ARDR_CLUSTER_V1` (PR #616) sections 2-6 for the three shapes. Format: `docs/claude-track/formats/ARDR_RUN_V1.md`
section 15. Every value is PENDING_FREEZE / DRAFT.

- CLUSTER_TRUTH_V1 = `claude_track_ardr_bidders.cluster_truth_projection` (one projection, not a second one).
- GATES_V1: one row per ground-truth gate in order: `gate`, `winner_txid` = the gate's single born txid
  (never null: a gate row with no birth or two is refused, GATE_BORN_COUNT), `project` false, `block_hash`
  of block G.
- METHOD_V1: `boundary.excluded_txids` = the ground truth's excluded fan-out, and `floor_height`,
  `max_depth`, `max_window_blocks`, `thresholds` from the method policy file
  (`BITAGI_CT_ARDR_METHOD_POLICY_V1`, its SHA-256 bound in the registration list like the policy's). A
  PENDING value is refused in CONFIRMATORY (exit 3, METHOD_POLICY_PENDING); EXPLORATORY and PR_SMOKE take the
  DRAFT value for it (`DRAFT_METHOD`) and say so in the answer.

Exit codes (AGENTS.md section 12) as D1's. Optimized Python (-O) is refused. Stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).absolute().parent))
import claude_track_ardr_bidders as B  # noqa: E402
import claude_track_ardr_driver as D  # noqa: E402

Refusal, invalid = D.Refusal, D.invalid

GATES_SCHEMA = 'BITAGI_CT_ARDR_GATES_V1'
METHOD_SCHEMA = 'BITAGI_CT_ARDR_CLUSTER_METHOD_V1'
METHOD_POLICY_SCHEMA = 'BITAGI_CT_ARDR_METHOD_POLICY_V1'
METHOD_FIELDS = ('floor_height', 'max_depth', 'max_window_blocks', 'thresholds')
# DRAFT (PENDING_FREEZE): the window starts at height 1 (the funding fan-out and the owner funding
# transactions are inside it); a REGISTER's ancestry inside the boundary is at most two deep (owner funding
# transaction, then the excluded fan-out), so 16 is ample; 40,000 blocks hold one 200-gate run (~28,900);
# the 045b 4.4 thresholds 4 and 15.
DRAFT_METHOD = {'floor_height': 1, 'max_depth': 16, 'max_window_blocks': 40_000, 'thresholds': [4, 15]}
# D2-3a round 1 (P3-4): D2-2's own bounds (tools/claude_track_ardr_cluster.py at 77ad3abd: MAX_DEPTH,
# MAX_WINDOW, MAX_THRESHOLD, the floor a u32), checked when the method policy is read, before any node starts.
MAX_FLOOR = 2**32 - 1
MAX_DEPTH = 10_000
MAX_WINDOW = 100_000
MAX_THRESHOLD = 1_000_000
# DRAFT (PENDING_FREEZE): the expected spacing of consecutive item-1 births on a run's chain (measured: 144 in
# every gate of the cross-tool cell and of the 15-gate local run). The window must hold [floor, H0 + (gates -
# 1) x 144]; a longer chain is still refused by D2-2 itself (WINDOW_TOO_LARGE), and the run then ends FAILED.
BIRTH_SPACING = 144


def parse_method_policy(blob: bytes) -> dict:
    """`{"schema", "floor_height", "max_depth", "max_window_blocks", "thresholds"}`; any value may be a PENDING
    string. Shape refusals are exit 2 (METHOD_POLICY_SHAPE)."""
    doc = D.parse_json(blob, 'METHOD_POLICY_JSON')
    if set(doc) != {'schema', *METHOD_FIELDS} or doc['schema'] != METHOD_POLICY_SCHEMA:
        raise invalid('METHOD_POLICY_SHAPE')
    for name in METHOD_FIELDS:
        value = doc[name]
        if D.pending(value):
            continue
        if name == 'thresholds':
            ok = (isinstance(value, list) and value and all(type(t) is int and t >= 1 for t in value)
                  and value == sorted(set(value)))
        else:
            ok = type(value) is int and (value >= 0 if name == 'floor_height' else value >= 1)
        if not ok:
            raise invalid('METHOD_POLICY_SHAPE')
        high = {'floor_height': MAX_FLOOR, 'max_depth': MAX_DEPTH, 'max_window_blocks': MAX_WINDOW}.get(name)
        if (value[-1] > MAX_THRESHOLD) if name == 'thresholds' else value > high:
            raise invalid('METHOD_POLICY_BOUND')
    return doc


def check_method_bounds(values: dict, params: dict) -> None:
    """The method values against the run (P3-4): the floor at or below H0 (METHOD_FLOOR_ABOVE_H0) and the
    window holding the expected chain [floor, H0 + (gates_per_run - 1) x BIRTH_SPACING] (METHOD_WINDOW_SHORT);
    both exit 2, before any node starts."""
    floor, h0 = values['floor_height'], params['H0']
    if floor > h0:
        raise invalid('METHOD_FLOOR_ABOVE_H0')
    if h0 + (params['gates_per_run'] - 1) * BIRTH_SPACING - floor + 1 > values['max_window_blocks']:
        raise invalid('METHOD_WINDOW_SHORT')


def method_values(doc: dict, mode: str) -> tuple[dict, list[str]]:
    """The method values and the fields that took their DRAFT value. CONFIRMATORY: any PENDING is exit 3."""
    if mode not in D.MODES:
        raise invalid('MODE')
    out, drafted = {}, []
    for name in METHOD_FIELDS:
        if D.pending(doc[name]):
            if mode == 'CONFIRMATORY':
                raise Refusal('METHOD_POLICY_PENDING', D.EXIT_PREREQUISITE)
            out[name], drafted = DRAFT_METHOD[name], drafted + [name]
        else:
            out[name] = doc[name]
    return out, drafted


def check_truth(gt: dict) -> dict:
    if not isinstance(gt, dict) or gt.get('schema') != B.GROUND_TRUTH_SCHEMA:
        raise invalid('GROUND_TRUTH_SCHEMA')
    if not isinstance(gt.get('gates'), list) or not gt['gates']:
        raise invalid('GROUND_TRUTH_GATES')
    return gt


def gates_input(gt: dict) -> dict:
    """GATES_V1 from the ground truth's `gates` rows (each with exactly one born txid and its block hash)."""
    rows = []
    for row in check_truth(gt)['gates']:
        if len(row.get('born', [])) != 1:
            raise invalid('GATE_BORN_COUNT')
        txid = row['born'][0]
        if txid not in gt['winners']:
            raise invalid('GATE_WINNER_UNKNOWN')
        block_hash = row.get('block_hash')
        if not (isinstance(block_hash, str) and D.HEX64.match(block_hash)):
            raise invalid('GATE_BLOCK_HASH')
        rows.append({'gate': row['gate'], 'winner_txid': txid, 'project': False, 'block_hash': block_hash})
    return {'schema': GATES_SCHEMA, 'gates': rows}


def method_input(gt: dict, values: dict) -> dict:
    """METHOD_V1: the boundary's excluded txids from the ground truth; the rest from the method policy."""
    excluded = check_truth(gt)['excluded_txids']
    return {'schema': METHOD_SCHEMA,
            'boundary': {'floor_height': values['floor_height'], 'excluded_txids': sorted(excluded)},
            'max_depth': values['max_depth'], 'max_window_blocks': values['max_window_blocks'],
            'thresholds': list(values['thresholds'])}


def convert(gt: dict, method_policy: dict, mode: str) -> dict:
    values, drafted = method_values(method_policy, mode)
    return {'cluster_truth': B.cluster_truth_projection(check_truth(gt)), 'gates': gates_input(gt),
            'method': method_input(gt, values), 'drafted': drafted}


def dumps(value) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=1) + '\n').encode('ascii')


def write_inputs(out_dir: Path, converted: dict) -> dict:
    """The three files (new files only, LF-exact); returns each file's SHA-256."""
    hashes = {}
    for name in ('cluster_truth', 'gates', 'method'):
        data = dumps(converted[name])
        with (out_dir / f'{name}.json').open('xb') as stream:
            stream.write(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    return hashes


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--truth', required=True, type=Path)
    p.add_argument('--method-policy', required=True, type=Path)
    p.add_argument('--mode', required=True, choices=D.MODES)
    p.add_argument('--out-dir', required=True, type=Path, help='an existing directory; three new files')
    return p


def main(argv: list[str] | None = None) -> int:
    if not __debug__:
        print(json.dumps({'result': 'FAIL', 'code': 'OPTIMIZED_PYTHON', 'exit': D.EXIT_REFUSAL}))
        return D.EXIT_REFUSAL
    args = parser().parse_args(argv)
    try:
        gt = D.parse_json(D.read_input(args.truth, 64 * 1024 * 1024), 'GROUND_TRUTH_JSON')
        policy_blob = D.read_input(args.method_policy, D.POLICY_LIMIT)
        converted = convert(gt, parse_method_policy(policy_blob), args.mode)
        if not args.out_dir.is_dir():
            raise Refusal('OUT_DIR_MISSING', D.EXIT_PREREQUISITE)
        try:
            hashes = write_inputs(args.out_dir, converted)
        except FileExistsError:
            raise Refusal('OUTPUT_EXISTS', D.EXIT_PREREQUISITE) from None
    except Refusal as refusal:
        print(json.dumps({'result': 'FAIL', 'code': refusal.code, 'exit': refusal.exit_code}, sort_keys=True))
        return refusal.exit_code
    print(json.dumps({'result': 'DONE', 'sha256': hashes, 'drafted': converted['drafted'],
                      'method_policy_sha256': hashlib.sha256(policy_blob).hexdigest(), 'exit': D.EXIT_DONE},
                     sort_keys=True))
    return D.EXIT_DONE


if __name__ == '__main__':
    import claude_track_exit
    claude_track_exit.run(main)
