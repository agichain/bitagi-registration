#!/usr/bin/env python3
"""CT-P5-001 D2-2: the ARDR item-1 common-control clustering tool and its 4- and 15-gate reports.

Class T Regtest development evidence when run on the Class T campaign; built to run unchanged on a real
node in Class E (A's unit request #258 issuecomment-6537782009 Q7: under `tools/`, node reads only). The
format is `docs/claude-track/formats/ARDR_CLUSTER_V1.md`. Sources: 045b draft section 4.3 item 1 and section
4.4 (`docs/claude-track/plans/CT-P3-045b_PREREGISTRATION_DRAFT_EN.md`, a draft input, not frozen bytes);
the Anchor predicate and REGISTER `vout[1]` (SSoT 6.1, 12).

What it does:

- Reads the gate list (each gate's winner REGISTER txid, or none: "unknown control"), the method file (the
  shared-ancestry boundary, the walk depth, the report thresholds) and, in Class T, the ground truth.
- Reads every block of the window [floor height, tip] as raw bytes from one node through `bitcoin-cli`
  (the node reads its own cookie; no credential is ever an argument) under an allowlist of three read
  methods with fixed parameter shapes; no transaction index is needed. Block hashes, merkle roots and
  txids are recomputed from the bytes. No wallet, no send, no generate, no write of any kind.
- Links two winners when their ancestor sets inside the boundary meet (ANCESTRY) or their Anchor keys are
  equal (ANCHOR_KEY), joins links by transitive closure (union-find) and reports every run of at least each
  threshold of consecutive gates won by one cluster other than the project's, for link-based clusters and,
  with ground truth, for ownership clusters.
- With ground truth: link-based recall and precision over winning wallets' pairs, ownership-based recall
  and the unlinkable share, as exact fractions.

It records; it never judges. A's judge computes the expected report lists itself; the two do not import
each other. Exit codes (AGENTS.md section 12): 0 report written (not a verdict), 2 validation failure,
3 missing prerequisite, 4 internal error, 5 security policy (optimized Python, a credential-like argument, a
method outside the allowlist). Stdlib only.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

sys.dont_write_bytecode = True

# AGENTS.md section 12; EXIT_INTERNAL is common.EXIT_INTERNAL, as in claude_track_exit.py:39 (common.py's
# bytes are pinned, so it is not imported).
EXIT_DONE, EXIT_VALIDATION, EXIT_PREREQUISITE, EXIT_INTERNAL, EXIT_SECURITY = 0, 2, 3, 4, 5

OUTPUT_SCHEMA = 'BITAGI_CT_ARDR_CLUSTER_V1'
GATES_SCHEMA = 'BITAGI_CT_ARDR_GATES_V1'
METHOD_SCHEMA = 'BITAGI_CT_ARDR_CLUSTER_METHOD_V1'
TRUTH_SCHEMA = 'BITAGI_CT_ARDR_CLUSTER_TRUTH_V1'
LABELS = ['TOOL_RECORD_NOT_VERDICT', 'NODE_READ_ONLY']
LINK_KINDS = ('ANCESTRY', 'ANCHOR_KEY')
CHAINS = ('main', 'test', 'testnet4', 'signet', 'regtest')

INPUT_LIMIT = 16 * 1024 * 1024
MAX_GATES = 100_000
MAX_DEPTH = 10_000
MAX_WINDOW = 100_000       # blocks in the window [floor_height, tip]
MAX_TXS = 2_000_000        # transactions held from the window
MAX_THRESHOLD = 1_000_000
CALL_TIMEOUT = 300

HEX64 = re.compile(r'[0-9a-f]{64}\Z')
NAME = re.compile(r'[A-Za-z0-9_.:-]{1,64}\Z')
CREDENTIAL = re.compile(r'rpcpassword|rpcuser|rpcauth|stdinrpcpass|password', re.IGNORECASE)
NULL_PREVOUT = ('0' * 64, 0xffffffff)
ANCHOR_PREFIX = b'\x51\x20'   # SSoT 6.1: 0x51 0x20 <32-byte witness program>, exactly 34 bytes
UNKNOWN = 'UNKNOWN'   # the cluster name of an unknown-only run (R3, A 6541483273 item 1)
PROJECT = 0           # a project gate in the run sequence: never a cluster, it breaks every run


class Refusal(Exception):
    """A typed outcome: a stable code and its exit code. No input text is echoed."""

    def __init__(self, code: str, exit_code: int = EXIT_VALIDATION):
        super().__init__(code)
        self.code, self.exit_code = code, exit_code


def need(condition: bool, code: str, exit_code: int = EXIT_VALIDATION) -> None:
    if not condition:
        raise Refusal(code, exit_code)


# ---------------------------------------------------------------------------------------------------------
# Strict JSON (no float, no duplicate key, no non-finite constant).

def _no_float(text: str):
    raise Refusal('FLOAT_IN_INPUT')


class FloatText(str):
    """A JSON number with a fraction or exponent in a node reply, kept as text and never read."""


def _unique(pairs):
    keys = [key for key, _ in pairs]
    need(len(keys) == len(set(keys)), 'DUPLICATE_KEY')
    return dict(pairs)


def _no_constant(text: str):
    raise Refusal('NONFINITE_IN_INPUT')


def loads(text: str, code: str, floats_as_text: bool = False):
    try:
        return json.loads(text, parse_float=FloatText if floats_as_text else _no_float,
                          parse_constant=_no_constant, object_pairs_hook=_unique)
    except (ValueError, RecursionError):
        raise Refusal(code) from None


def read_input(path: Path) -> bytes:
    """One regular file, read once without following a final symlink, at most INPUT_LIMIT bytes."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise Refusal('INPUT_UNAVAILABLE', EXIT_PREREQUISITE) from None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise Refusal('INPUT_NOT_REGULAR', EXIT_PREREQUISITE)
        chunks, size = [], 0
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                break
            size += len(chunk)
            need(size <= INPUT_LIMIT, 'INPUT_BOUND')
            chunks.append(chunk)
        return b''.join(chunks)
    finally:
        os.close(fd)


def parse_input(blob: bytes, schema: str, code: str) -> dict:
    try:
        text = blob.decode('utf-8')
    except UnicodeDecodeError:
        raise Refusal(code) from None
    value = loads(text, code)
    need(isinstance(value, dict) and value.get('schema') == schema, code)
    return value


def pending(value) -> bool:
    """A PENDING marker anywhere: a string value that starts with "PENDING" (ARDR_RUN_V1 section 3)."""
    if isinstance(value, str):
        return value.startswith('PENDING')
    if isinstance(value, dict):
        return any(pending(item) for item in value.values())
    if isinstance(value, list):
        return any(pending(item) for item in value)
    return False


def integer(value, low: int, high: int, code: str) -> int:
    need(type(value) is int and low <= value <= high, code)
    return value


# ---------------------------------------------------------------------------------------------------------
# Inputs (format doc sections 2-4).

def check_gates(doc: dict) -> list[dict]:
    need(set(doc) == {'schema', 'gates'}, 'GATES_KEYS')
    gates = doc['gates']
    need(isinstance(gates, list) and 1 <= len(gates) <= MAX_GATES, 'GATES_SHAPE')
    out, seen = [], set()
    for at, item in enumerate(gates):
        need(isinstance(item, dict) and {'gate', 'winner_txid', 'project'} <= set(item)
             <= {'gate', 'winner_txid', 'project', 'block_hash'}, 'GATE_KEYS')
        gate = integer(item['gate'], 0, 2**32 - 1, 'GATE_NUMBER')
        need(at == 0 or gate == out[-1]['gate'] + 1, 'GATES_NOT_CONSECUTIVE')
        txid = item['winner_txid']
        need(txid is None or (isinstance(txid, str) and HEX64.match(txid) is not None), 'GATE_WINNER')
        need(type(item['project']) is bool and not (item['project'] and txid is None), 'GATE_PROJECT')
        block = item.get('block_hash')
        need(block is None or (isinstance(block, str) and HEX64.match(block) is not None and txid is not None),
             'GATE_BLOCK_HASH')
        if txid is not None:
            need(txid not in seen, 'DUPLICATE_WINNER')
            seen.add(txid)
        out.append({'gate': gate, 'winner_txid': txid, 'project': item['project'], 'block_hash': block})
    return out


def check_method(doc: dict) -> dict:
    need(not pending(doc), 'METHOD_PENDING', EXIT_PREREQUISITE)
    need(set(doc) == {'schema', 'boundary', 'max_depth', 'max_window_blocks', 'thresholds'}, 'METHOD_KEYS')
    boundary = doc['boundary']
    need(isinstance(boundary, dict) and set(boundary) == {'floor_height', 'excluded_txids'}, 'METHOD_BOUNDARY')
    floor = integer(boundary['floor_height'], 0, 2**32 - 1, 'METHOD_FLOOR')
    excluded = boundary['excluded_txids']
    need(isinstance(excluded, list) and all(isinstance(t, str) and HEX64.match(t) for t in excluded)
         and len(set(excluded)) == len(excluded), 'METHOD_EXCLUDED')
    depth = integer(doc['max_depth'], 1, MAX_DEPTH, 'METHOD_DEPTH')
    window = integer(doc['max_window_blocks'], 1, MAX_WINDOW, 'METHOD_WINDOW')
    thresholds = doc['thresholds']
    need(isinstance(thresholds, list) and thresholds
         and all(type(t) is int and 1 <= t <= MAX_THRESHOLD for t in thresholds)
         and thresholds == sorted(set(thresholds)), 'METHOD_THRESHOLDS')
    return {'floor_height': floor, 'excluded_txids': frozenset(excluded), 'max_depth': depth,
            'max_window_blocks': window, 'thresholds': list(thresholds)}


def check_truth(doc: dict, gates: list[dict]) -> dict:
    need(set(doc) == {'schema', 'winners', 'owners', 'planted_links'}, 'TRUTH_KEYS')
    winners, owners, planted = doc['winners'], doc['owners'], doc['planted_links']
    # An owner is an ownership cluster's name; UNKNOWN names the unknown-only runs (section 5).
    need(isinstance(owners, dict) and all(NAME.match(w) and isinstance(o, str) and NAME.match(o)
                                          and o != UNKNOWN for w, o in owners.items()), 'TRUTH_OWNERS')
    need(isinstance(winners, dict) and all(HEX64.match(t) and isinstance(w, str) and w in owners
                                           for t, w in winners.items()), 'TRUTH_WINNERS')
    for gate in gates:
        need(gate['winner_txid'] is None or gate['winner_txid'] in winners, 'TRUTH_WINNER_MISSING')
    need(isinstance(planted, list), 'TRUTH_LINKS')
    groups = []
    for item in planted:
        need(isinstance(item, dict) and set(item) == {'kind', 'wallets'} and item['kind'] in LINK_KINDS,
             'TRUTH_LINKS')
        wallets = item['wallets']
        # Each element's type before set(): a {} or [] element is TRUTH_LINKS, not a TypeError (PR #616).
        need(isinstance(wallets, list) and len(wallets) >= 2
             and all(isinstance(w, str) and w in owners for w in wallets)
             and len(set(wallets)) == len(wallets), 'TRUTH_LINKS')
        need(len({owners[w] for w in wallets}) == 1, 'TRUTH_LINK_ACROSS_OWNERS')   # 045b 4.6: no shared key
        groups.append((item['kind'], sorted(wallets)))
    return {'winners': dict(winners), 'owners': dict(owners), 'planted': groups}


# ---------------------------------------------------------------------------------------------------------
# Transactions (the bytes the node returned; txid recomputed, so a reply cannot name another transaction).

def dsha(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


class Reader:
    def __init__(self, data: bytes):
        self.data, self.at = data, 0

    def take(self, n: int) -> bytes:
        need(0 <= n and self.at + n <= len(self.data), 'TX_TRUNCATED')
        chunk = self.data[self.at:self.at + n]
        self.at += n
        return chunk

    def int(self, n: int) -> int:
        return int.from_bytes(self.take(n), 'little')

    def varint(self) -> int:
        first = self.int(1)
        return first if first < 0xfd else self.int({0xfd: 2, 0xfe: 4, 0xff: 8}[first])


def read_tx(reader: Reader) -> dict:
    """One serialized transaction at the reader: txid, inputs (prev txid display hex, vout), output scripts."""
    begin = reader.at
    version = reader.take(4)
    segwit = reader.data[reader.at:reader.at + 2] == b'\x00\x01'
    if segwit:
        reader.take(2)
    start = reader.at
    inputs = []
    for _ in range(reader.varint()):
        prev = reader.take(32)[::-1].hex()
        vout = reader.int(4)
        reader.take(reader.varint())
        reader.take(4)
        inputs.append((prev, vout))
    scripts = []
    for _ in range(reader.varint()):
        reader.take(8)
        scripts.append(reader.take(reader.varint()))
    end = reader.at
    if segwit:
        for _ in inputs:
            for _ in range(reader.varint()):
                reader.take(reader.varint())
    locktime = reader.take(4)
    need(inputs and scripts and reader.at > begin, 'TX_MALFORMED')
    return {'txid': dsha(version + reader.data[start:end] + locktime)[::-1].hex(), 'inputs': inputs,
            'scripts': scripts, 'coinbase': len(inputs) == 1 and inputs[0] == NULL_PREVOUT}


def merkle_root(hashes: list[bytes]) -> bytes:
    level = list(hashes)
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [dsha(level[i] + level[i + 1]) for i in range(0, len(level), 2)]
    return level[0]


def parse_block(raw: bytes, block_hash: str) -> list[dict]:
    """The block's transactions; its header hash must be `block_hash` and its merkle root the txids'."""
    need(len(raw) > 80 and dsha(raw[:80])[::-1].hex() == block_hash, 'BLOCK_HASH_MISMATCH')
    reader = Reader(raw)
    reader.take(80)
    count = reader.varint()
    need(1 <= count <= len(raw), 'BLOCK_MALFORMED')
    txs = [read_tx(reader) for _ in range(count)]
    need(reader.at == len(raw), 'BLOCK_MALFORMED')
    need(merkle_root([bytes.fromhex(tx['txid'])[::-1] for tx in txs]) == raw[36:68], 'MERKLE_MISMATCH')
    return txs


def anchor_key(tx: dict) -> str | None:
    """The 32-byte witness program of `vout[1]` when it has the exact Anchor form (SSoT 6.1, 12 item 6)."""
    if len(tx['scripts']) < 2:
        return None
    script = tx['scripts'][1]
    return script[2:].hex() if len(script) == 34 and script[:2] == ANCHOR_PREFIX else None


# ---------------------------------------------------------------------------------------------------------
# Node reads: one allowlist, fixed parameter shapes, refused before any process starts. No transaction
# index is needed: the tool reads every block of the window [floor_height, tip] (B, D2-2 design answer).

READ_RPCS = {
    'getblockchaininfo': (),
    'getblockhash': ('height',),
    'getblock': ('hash', '0'),
}
TEXT_RPCS = frozenset({'getblockhash', 'getblock'})   # bitcoin-cli prints these replies as bare text
HEIGHT = re.compile(r'(0|[1-9][0-9]{0,9})\Z')


def check_call(method: str, params: tuple) -> None:
    shape = READ_RPCS.get(method)
    need(shape is not None and len(params) == len(shape), 'RPC_NOT_ALLOWED', EXIT_SECURITY)
    for kind, param in zip(shape, params):
        if kind == 'hash':
            ok = isinstance(param, str) and HEX64.match(param) is not None
        elif kind == 'height':
            ok = isinstance(param, str) and HEIGHT.match(param) is not None
        else:
            ok = param == kind
        need(ok, 'RPC_NOT_ALLOWED', EXIT_SECURITY)


class AllowlistRPC:
    """Every call passes `check_call` before the inner client sees it."""

    def __init__(self, inner):
        self.inner = inner

    def call(self, method: str, *params: str):
        check_call(method, params)
        return self.inner.call(method, *params)


class CliRPC:
    """bitcoin-cli with -datadir or -rpccookiefile: bitcoin-cli reads the cookie itself."""

    def __init__(self, cli: list[str]):
        self.cli = cli

    def call(self, method: str, *params: str):
        try:
            done = subprocess.run([*self.cli, method, *params], stdin=subprocess.DEVNULL, capture_output=True,
                                  timeout=CALL_TIMEOUT, check=False)
        except OSError:
            raise Refusal('CLI_MISSING', EXIT_PREREQUISITE) from None
        except subprocess.TimeoutExpired:
            raise Refusal('RPC_TIMEOUT', EXIT_PREREQUISITE) from None
        need(done.returncode == 0, f'RPC_FAILED {method.upper()}', EXIT_PREREQUISITE)
        try:
            text = done.stdout.decode('ascii' if method in TEXT_RPCS else 'utf-8')
        except UnicodeDecodeError:
            raise Refusal('RPC_REPLY') from None
        return text.strip() if method in TEXT_RPCS else loads(text, 'RPC_REPLY', floats_as_text=True)


class Chain:
    """The transactions of every block in the window, read once from one node."""

    def __init__(self, rpc):
        self.rpc = AllowlistRPC(rpc)
        self.txs: dict[str, dict] = {}

    def block_hash(self, height: int) -> str:
        reply = self.rpc.call('getblockhash', str(height))
        need(isinstance(reply, str) and HEX64.match(reply) is not None, 'RPC_REPLY')
        return reply

    def scan(self, chain: str, method: dict) -> dict:
        info = self.rpc.call('getblockchaininfo')
        need(isinstance(info, dict) and info.get('chain') == chain, 'CHAIN_MISMATCH')
        tip, tip_hash = info.get('blocks'), info.get('bestblockhash')
        need(type(tip) is int and tip >= 0 and isinstance(tip_hash, str) and HEX64.match(tip_hash) is not None,
             'RPC_REPLY')
        floor = method['floor_height']
        need(floor <= tip, 'FLOOR_ABOVE_TIP')
        need(tip - floor + 1 <= method['max_window_blocks'], 'WINDOW_TOO_LARGE')
        need(self.block_hash(tip) == tip_hash, 'REORG_DURING_SCAN')
        previous = None
        for height in range(floor, tip + 1):
            block_hash = self.block_hash(height)
            reply = self.rpc.call('getblock', block_hash, '0')
            need(isinstance(reply, str), 'RPC_REPLY')
            try:
                raw = bytes.fromhex(reply)
            except ValueError:
                raise Refusal('RPC_REPLY') from None
            txs = parse_block(raw, block_hash)
            # One chain: each block above the floor names the block read at the height below as its parent,
            # so a reorg that goes away and comes back during the scan is refused, not mixed in.
            need(previous is None or raw[4:36][::-1].hex() == previous, 'REORG_DURING_SCAN')
            previous = block_hash
            for tx in txs:
                if tx['txid'] in self.txs:
                    need(tx['coinbase'] and self.txs[tx['txid']]['coinbase'], 'DUPLICATE_TXID')
                    continue   # a repeated coinbase txid (BIP30 history): the first is kept; both are boundary
                need(len(self.txs) < MAX_TXS, 'TX_BOUND')
                tx['height'], tx['block_hash'] = height, block_hash
                self.txs[tx['txid']] = tx
        # The chain read ends in the tip named by getblockchaininfo (also when floor == tip), so a tip that
        # goes away and comes back between the re-reads below and the loop's own read is refused.
        need(previous == tip_hash, 'REORG_DURING_SCAN')
        need(self.block_hash(tip) == tip_hash, 'REORG_DURING_SCAN')
        return {'floor_height': floor, 'tip_height': tip, 'tip_hash': tip_hash, 'blocks': tip - floor + 1,
                'transactions': len(self.txs)}


# ---------------------------------------------------------------------------------------------------------
# Links and closure (045b 4.3 item 1).

def ancestors(chain: Chain, txid: str, method: dict) -> tuple[frozenset, bool, dict]:
    """The winner and its ancestors inside the boundary, whether the depth cap stopped the walk, and the
    distinct transactions where it stopped at the boundary.

    A transaction outside the boundary is neither in the set nor walked past: a coinbase, an excluded txid
    (the funding source), or one not in the window (confirmed below the floor height)."""
    found, truncated = {txid}, False
    stops: dict[str, set] = {'coinbase': set(), 'excluded': set(), 'outside_window': set()}
    frontier = [txid]
    for depth in range(method['max_depth'] + 1):
        if not frontier:
            break
        following = []
        for current in frontier:
            for prev, _ in chain.txs[current]['inputs']:
                if prev in found:
                    continue
                if prev in method['excluded_txids']:
                    stops['excluded'].add(prev)
                    continue
                parent = chain.txs.get(prev)
                if parent is None:
                    stops['outside_window'].add(prev)
                    continue
                if parent['coinbase']:
                    stops['coinbase'].add(prev)
                    continue
                if depth == method['max_depth']:
                    truncated = True   # inside the boundary but past the cap: not in the set
                    continue
                found.add(prev)
                following.append(prev)
        frontier = sorted(following)
    return frozenset(found), truncated, {kind: len(items) for kind, items in stops.items()}


class UnionFind:
    def __init__(self, items):
        self.parent = {item: item for item in items}

    def find(self, item):
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != root:
            self.parent[item], item = root, self.parent[item]
        return root

    def union(self, a, b) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)   # deterministic root: the smaller item

    def groups(self) -> list[list]:
        out: dict = {}
        for item in self.parent:
            out.setdefault(self.find(item), []).append(item)
        return sorted(sorted(group) for group in out.values())


def find_links(winners: list[dict], sets: dict[int, frozenset], keys: dict[int, str]) -> list[dict]:
    """Every linked pair of winning gates, one entry per kind, with the smallest shared item as `via`.

    Indexed by ancestor txid and by Anchor key, so only pairs that share something are visited; the list is
    the same as comparing every pair (by gate pair, ANCESTRY before ANCHOR_KEY)."""
    by_item: dict[str, list[int]] = {}
    by_key: dict[str, list[int]] = {}
    for winner in winners:
        gate = winner['gate']
        for item in sets[gate]:
            by_item.setdefault(item, []).append(gate)
        by_key.setdefault(keys[gate], []).append(gate)
    shared: dict[tuple[int, int], str] = {}
    for item, holders in by_item.items():
        for i, a in enumerate(holders):
            for b in holders[i + 1:]:
                pair = (min(a, b), max(a, b))
                if pair not in shared or item < shared[pair]:
                    shared[pair] = item
    same_key = {(min(a, b), max(a, b)): key for key, holders in by_key.items()
                for i, a in enumerate(holders) for b in holders[i + 1:]}
    links = []
    for pair in sorted(set(shared) | set(same_key)):
        if pair in shared:
            links.append({'kind': 'ANCESTRY', 'gates': list(pair), 'via': shared[pair]})
        if pair in same_key:
            links.append({'kind': 'ANCHOR_KEY', 'gates': list(pair), 'via': same_key[pair]})
    return links


def link_clusters(gates: list[dict], links: list[dict]) -> dict[int, str]:
    """Winning gate -> link cluster id (`L<first gate>`), by transitive closure over every link."""
    won = [g['gate'] for g in gates if g['winner_txid'] is not None]
    uf = UnionFind(won)
    for link in links:
        uf.union(*link['gates'])
    return {gate: f'L{group[0]}' for group in uf.groups() for gate in group}


# ---------------------------------------------------------------------------------------------------------
# Runs and reports (045b 4.4).

def runs(sequence: list, gates: list[int]) -> list[dict]:
    """For each cluster C (a str; PROJECT and None are not clusters): every maximal interval of consecutive
    gates each won by C or unknown (None) that holds at least one gate won by C. An unknown gate never
    breaks a run; a project gate breaks every run."""
    out = []
    for cluster in sorted({c for c in sequence if isinstance(c, str)}):
        at = 0
        while at < len(sequence):
            if sequence[at] not in (cluster, None):
                at += 1
                continue
            end = at
            while end < len(sequence) and sequence[end] in (cluster, None):
                end += 1
            if cluster in sequence[at:end]:
                out.append({'cluster': cluster, 'first_gate': gates[at], 'last_gate': gates[end - 1],
                            'length': end - at, 'first_won_gate': gates[sequence.index(cluster, at, end)],
                            'unknown_gates': [gates[i] for i in range(at, end) if sequence[i] is None]})
            at = end
    return out


def unknown_runs(sequence: list, gates: list[int]) -> list[dict]:
    """R3: every maximal interval of consecutive unknown gates, as cluster UNKNOWN; its first gate is its
    first 'win', so its trigger gate is first_gate + T - 1."""
    out, at = [], 0
    while at < len(sequence):
        if sequence[at] is not None:
            at += 1
            continue
        end = at
        while end < len(sequence) and sequence[end] is None:
            end += 1
        out.append({'cluster': UNKNOWN, 'first_gate': gates[at], 'last_gate': gates[end - 1], 'length': end - at,
                    'first_won_gate': gates[at], 'unknown_gates': gates[at:end]})
        at = end
    return out


def reports(sequence: list, gates: list[int], thresholds: list[int]) -> dict:
    found = runs(sequence, gates) + unknown_runs(sequence, gates)
    out = {}
    for threshold in thresholds:
        # The trigger gate: the run has reached T gates and C has won one of them (format doc section 5).
        rows = [{**{k: v for k, v in run.items() if k != 'first_won_gate'}, 'threshold': threshold,
                 'trigger_gate': max(run['first_gate'] + threshold - 1, run['first_won_gate'])}
                for run in found if run['length'] >= threshold]
        out[str(threshold)] = sorted(rows, key=lambda r: (r['trigger_gate'], r['cluster']))
    return out


def repeat_winner(sequence: list[str | None], gates: list[int]) -> dict:
    counts: dict[str, int] = {}
    for cluster in sequence:
        if cluster is not None:
            counts[cluster] = counts.get(cluster, 0) + 1
    top = max(counts.values(), default=0)
    longest = max((r['length'] for r in runs(sequence, gates)), default=0)
    return {'known_gates': sum(counts.values()), 'unknown_gates': sequence.count(None),
            'top_cluster_gates': top, 'top_clusters': sorted(c for c, n in counts.items() if n == top),
            'longest_run': longest}


def clustering(gates: list[dict], cluster_of: dict[int, str], thresholds: list[int],
               owner_of: dict[int, str] | None = None) -> dict:
    """One clustering's clusters, reports and repeat-winner counts. `owner_of` (winning gate -> owner, Class T
    truth) names which non-project gates in a project cluster are not the project owner's."""
    numbers = [g['gate'] for g in gates]
    sequence = [cluster_of[g['gate']] if g['winner_txid'] is not None else None for g in gates]
    project = {cluster_of[g['gate']] for g in gates if g['project']}
    members: dict[str, list[int]] = {}
    for g in gates:
        if g['winner_txid'] is not None:
            members.setdefault(cluster_of[g['gate']], []).append(g['gate'])
    # Reading (b) of 045b "other than the project" (A 6541483273 item 2): only the project's own gates are
    # removed, and each breaks every run; the other gates of a cluster holding a project gate still form
    # runs. They are also listed here (format doc section 5).
    others = [g['gate'] for g in gates
              if g['winner_txid'] is not None and not g['project'] and cluster_of[g['gate']] in project]
    foreign = None
    if owner_of is not None:
        project_owners = {owner_of[g['gate']] for g in gates if g['project']}
        foreign = [gate for gate in others if owner_of[gate] not in project_owners]
    return {'clusters': [{'id': c, 'gates': members[c], 'project': c in project} for c in sorted(members)],
            'project_clusters': sorted(project),
            'project_cluster_other_gates': {'gates': others, 'not_project_owner': foreign},
            'reports': reports([PROJECT if g['project'] else c for g, c in zip(gates, sequence)], numbers,
                               thresholds),
            'repeat_winner': repeat_winner(sequence, numbers)}


# ---------------------------------------------------------------------------------------------------------
# Metrics with ground truth (045b 4.3 item 1).

def pairs_of(groups) -> set[tuple[str, str]]:
    return {(a, b) for group in groups for i, a in enumerate(group) for b in group[i + 1:]}


def fraction(num: int, den: int) -> dict:
    """An exact fraction; with no pairs (den 0) it is marked undefined: neither 1 nor 0 (format doc section 6)."""
    return {'num': num, 'den': den, 'undefined': True} if den == 0 else {'num': num, 'den': den}


def metrics(gates: list[dict], links: list[dict], truth: dict) -> dict:
    """Over wallets that won at least one gate. D: tool links lifted to wallets, closed; P_L: planted links
    restricted to winning wallets, then closed (A 6541483273 item 3, format doc section 6); P_O: same-owner
    pairs."""
    wallet_of = {g['gate']: truth['winners'][g['winner_txid']] for g in gates if g['winner_txid'] is not None}
    observed = sorted(set(wallet_of.values()))
    detected = UnionFind(observed)
    for link in links:
        detected.union(*(wallet_of[gate] for gate in link['gates']))
    seen = set(observed)
    planted = UnionFind(observed)
    for _, wallets in truth['planted']:
        winning = [wallet for wallet in wallets if wallet in seen]
        for wallet in winning[1:]:
            planted.union(winning[0], wallet)
    d = pairs_of(detected.groups())
    p_l = pairs_of(planted.groups())
    by_owner: dict[str, list[str]] = {}
    for wallet in observed:
        by_owner.setdefault(truth['owners'][wallet], []).append(wallet)
    p_o = pairs_of(sorted(by_owner.values()))
    return {'observed_wallets': len(observed), 'detected_pairs': len(d), 'planted_pairs': len(p_l),
            'same_owner_pairs': len(p_o),
            'link_recall': fraction(len(d & p_l), len(p_l)),
            'link_precision': fraction(len(d & p_l), len(d)),
            'ownership_recall': fraction(len(d & p_o), len(p_o)),
            'unlinkable_share': fraction(len(p_o - p_l), len(p_o)),
            'missed_planted_pairs': [list(p) for p in sorted(p_l - d)],
            'false_pairs': [list(p) for p in sorted(d - p_l)]}


# ---------------------------------------------------------------------------------------------------------
# The run.

def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def cluster(chain: Chain, chain_name: str, gates_blob: bytes, method_blob: bytes,
            truth_blob: bytes | None) -> dict:
    gates = check_gates(parse_input(gates_blob, GATES_SCHEMA, 'GATES_INPUT'))
    method = check_method(parse_input(method_blob, METHOD_SCHEMA, 'METHOD_INPUT'))
    truth = None if truth_blob is None else check_truth(parse_input(truth_blob, TRUTH_SCHEMA, 'TRUTH_INPUT'), gates)
    window = chain.scan(chain_name, method)
    winners = [g for g in gates if g['winner_txid'] is not None]
    sets, keys, truncated, rows = {}, {}, [], []
    for gate in winners:
        tx = chain.txs.get(gate['winner_txid'])
        need(tx is not None, 'WINNER_NOT_IN_WINDOW')
        need(gate['block_hash'] in (None, tx['block_hash']), 'GATE_BLOCK_MISMATCH')
        need(not tx['coinbase'] and gate['winner_txid'] not in method['excluded_txids'], 'WINNER_IN_BOUNDARY')
        key = anchor_key(tx)
        need(key is not None, 'WINNER_NOT_REGISTER')
        keys[gate['gate']] = key
        sets[gate['gate']], cut, stops = ancestors(chain, gate['winner_txid'], method)
        if cut:
            truncated.append(gate['gate'])
        rows.append({'gate': gate['gate'], 'winner_txid': gate['winner_txid'], 'height': tx['height'],
                     'block_hash': tx['block_hash'], 'anchor_key': key,
                     'ancestors_in_boundary': len(sets[gate['gate']]), 'boundary_stops': stops})
    links = find_links(winners, sets, keys)
    by_link = link_clusters(gates, links)
    for row in rows:
        row['link_cluster'] = by_link[row['gate']]
    result = {
        'schema': OUTPUT_SCHEMA, 'labels': LABELS, 'chain': chain_name, 'window': window,
        'inputs': {'gates_sha256': sha256(gates_blob), 'method_sha256': sha256(method_blob),
                   'truth_sha256': None if truth_blob is None else sha256(truth_blob)},
        'method': {'floor_height': method['floor_height'], 'excluded_txids': sorted(method['excluded_txids']),
                   'max_depth': method['max_depth'], 'max_window_blocks': method['max_window_blocks'],
                   'thresholds': method['thresholds']},
        'gates': {'count': len(gates), 'first': gates[0]['gate'], 'last': gates[-1]['gate'],
                  'unknown': [g['gate'] for g in gates if g['winner_txid'] is None],
                  'project': [g['gate'] for g in gates if g['project']]},
        'winners': rows, 'walk_truncated': truncated, 'incomplete': bool(truncated), 'links': links,
        'link_based': None, 'ownership': None, 'metrics': None,
    }
    by_owner = None
    if truth is not None:
        by_owner = {g['gate']: truth['owners'][truth['winners'][g['winner_txid']]] for g in winners}
    result['link_based'] = clustering(gates, by_link, method['thresholds'], by_owner)
    if truth is not None:
        result['ownership'] = clustering(gates, by_owner, method['thresholds'], by_owner)
        result['metrics'] = metrics(gates, links, truth)
    return result


def write_output(path: Path, result: dict) -> None:
    """A file that cannot be created is a missing prerequisite (3). Once this call has created it, a failed
    write, flush or close (ENOSPC, EFBIG) is a tool that cannot write its output: AGENTS.md section 12 says
    4, and the partial file, ours since 'x' created it, is removed."""
    text = json.dumps(result, sort_keys=True, separators=(',', ':')) + '\n'
    try:
        stream = path.open('x', encoding='ascii', newline='')
    except FileExistsError:
        raise Refusal('OUTPUT_EXISTS', EXIT_PREREQUISITE) from None
    except OSError:
        raise Refusal('OUTPUT_UNAVAILABLE', EXIT_PREREQUISITE) from None
    created = None
    try:
        created = os.fstat(stream.fileno())
        stream.write(text)
        stream.close()   # inside the guard: a buffered stream may raise only when it flushes at close
    except OSError:
        with contextlib.suppress(OSError):
            stream.close()
        with contextlib.suppress(OSError):
            now = os.lstat(path)
            # Only while the path still names the file this call created.
            if created is not None and (now.st_dev, now.st_ino) == (created.st_dev, created.st_ino):
                path.unlink()
        raise Refusal('OUTPUT_WRITE_FAILED', EXIT_INTERNAL) from None


def cli_base(args) -> list[str]:
    # bitcoin-cli reads the node's bitcoin.conf; the command line overrides it. `-nogenerate`: a conf
    # `generate=1` would make bitcoin-cli call getnewaddress (a wallet write) and generatetoaddress before
    # the method. `-nonamed`: the parameters stay positional. Both accepted by Core 31.1 and 30.3.
    cli = [args.bitcoin_cli, f'-chain={args.chain}', '-nogenerate', '-nonamed']
    cli.append(f'-datadir={args.datadir}' if args.datadir is not None else f'-rpccookiefile={args.rpccookiefile}')
    if args.rpcconnect is not None:
        cli.append(f'-rpcconnect={args.rpcconnect}')
    if args.rpcport is not None:
        cli.append(f'-rpcport={args.rpcport}')
    return cli


def port_arg(text: str) -> int:
    if not re.fullmatch(r'[1-9][0-9]{0,4}', text) or int(text) > 65535:
        raise argparse.ArgumentTypeError('a port is 1..65535')
    return int(text)


def host_arg(text: str) -> str:
    if not re.fullmatch(r'[A-Za-z0-9.:\[\]-]{1,253}', text):
        raise argparse.ArgumentTypeError('a host name or address')
    return text


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--gates', required=True, type=Path)
    p.add_argument('--method', required=True, type=Path)
    p.add_argument('--truth', type=Path, help='Class T ground truth (optional)')
    p.add_argument('--out', required=True, type=Path, help='new output file')
    p.add_argument('--chain', required=True, choices=CHAINS)
    p.add_argument('--bitcoin-cli', default='bitcoin-cli')
    node = p.add_mutually_exclusive_group(required=True)
    node.add_argument('--datadir')
    node.add_argument('--rpccookiefile')
    p.add_argument('--rpcconnect', type=host_arg)
    p.add_argument('--rpcport', type=port_arg)
    return p


def main(argv: list[str] | None = None, rpc=None) -> int:
    if sys.flags.optimize or not __debug__:
        print(json.dumps({'code': 'OPTIMIZED_PYTHON', 'exit': EXIT_SECURITY, 'result': 'FAIL'}, sort_keys=True))
        return EXIT_SECURITY
    argv = sys.argv[1:] if argv is None else argv
    # Before argparse, which would repeat an unknown argument (and its value) in its message.
    if any(CREDENTIAL.search(arg) for arg in argv):
        print(json.dumps({'code': 'CREDENTIAL_ARGUMENT', 'exit': EXIT_SECURITY, 'result': 'FAIL'}, sort_keys=True))
        return EXIT_SECURITY
    args = parser().parse_args(argv)
    try:
        if args.out.exists() or args.out.is_symlink():
            raise Refusal('OUTPUT_EXISTS', EXIT_PREREQUISITE)
        blobs = [read_input(args.gates), read_input(args.method),
                 None if args.truth is None else read_input(args.truth)]
        chain = Chain(rpc if rpc is not None else CliRPC(cli_base(args)))
        result = cluster(chain, args.chain, *blobs)
        write_output(args.out, result)
    except Refusal as refusal:
        print(json.dumps({'code': refusal.code, 'exit': refusal.exit_code, 'result': 'FAIL'}, sort_keys=True))
        return refusal.exit_code
    summary = {'result': 'DONE', 'exit': EXIT_DONE, 'winners': len(result['winners']), 'links': len(result['links']),
               'link_reports': {t: len(r) for t, r in result['link_based']['reports'].items()}}
    print(json.dumps(summary, sort_keys=True))
    return EXIT_DONE


if __name__ == '__main__':
    import claude_track_exit
    claude_track_exit.run(main)
