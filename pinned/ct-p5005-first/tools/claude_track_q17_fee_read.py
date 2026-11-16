#!/usr/bin/env python3
"""Q17 fee-observation read from a mainnet node (045b Q17 note 2026-10-26 section 3.4).

A's unit request #258 issuecomment-6423115104, B's ACK and design choices
issuecomment-6423158249. Unit note:
docs/claude-track/plans/notes/CT-P3-045b_PREREGISTRATION_DRAFT_EN/2026-10-27_q17-fee-read-script.md.

The Founder runs this on their own fully validating, unpruned mainnet node
host. It calls `bitcoin-cli -nogenerate -nonamed` with `-datadir` or
`-rpccookiefile` (and optional `-rpcconnect`, `-rpcport`); bitcoin-cli reads
the cookie itself. bitcoin-cli also reads the node's bitcoin.conf (the default
datadir's when only `-rpccookiefile` is given), and the command line overrides
it: `-nogenerate` because a conf `generate=1` would make bitcoin-cli call
`getnewaddress` (a wallet write) and `generatetoaddress` before the method,
`-nonamed` so the parameters stay positional (unit note 2026-10-31). This tool
never takes a credential value, never opens the cookie file and refuses any
argument that looks like a credential. It calls five RPC methods only, through
one allowlist with one parameter shape per method: `getblockchaininfo`,
`getnetworkinfo`, `getblockhash <height>`, `getblockheader <hash>` and
`getblockstats <hash> ["height","blockhash","feerate_percentiles"]`.

The rows form one chain. For every height read, `getblockheader` must give the
row's `hash` and `height`, and its `previousblockhash` must be the blockhash
of the row before it (the file's last row for the first row a resumed run
reads; the row at `start` has no parent check). The row at `h_obs` must be the
header's `h_obs_hash`, which is read again at the end, so every row is an
ancestor of the block at `h_obs` on the node's chain at the end.

Output, JSON Lines (UTF-8, LF, flushed and fsynced line by line):
- a header: format, Core version (`subversion`, `version`), chain, `h_obs`,
  `start`, the tip height and hash at start, the hash at `h_obs`, the UTC start
  time and this script's SHA-256;
- one line per height from `start` to `h_obs`, each the parent of the next:
  `{"height", "blockhash", "feerate_percentiles": [5 integers]}`;
- a trailer: the tip height and hash at end, the hash at `h_obs` at end, the
  UTC end time and the number of heights.
A file with a trailer is complete; running again writes nothing. A file
without one is resumed after its last height when its header matches and its
heights are continuous; any other file is refused and left as it is.

Numbers are read without float (AGENTS.md section 4): a getblockstats reply or
a line of the output with a fraction or exponent is refused, and a value read
from any reply must be a JSON integer (not a bool). The node-information
replies carry floats in fields this tool does not read (`difficulty`,
`verificationprogress`, `relayfee`); those are kept as their text, never
converted, and never accepted where a value is read.

It computes nothing from the percentiles (no `b_obs`, no cap: the 11-03
numbers draft's). Class T development tooling: no signing, broadcast, wallet,
GO or release authority. Stdlib only.

Exit codes (AGENTS.md section 12): 0 written or already complete,
2 validation failure (a reply or the existing output is not as required, a
reorganization at `h_obs`, a block whose header does not name the previous row
as its parent: `BLOCKHEADER_REPLY`, `BLOCKHEADER_HASH`, `BLOCKHEADER_HEIGHT`,
`CHAIN_NOT_LINKED`), 3 missing prerequisite (bitcoin-cli, the node, the
output folder), 4 internal error, 5 security policy (optimized Python, a
credential-like argument, a method outside the allowlist), 6 refused (chain not
`main`, a pruned node or one in initial block download at start, `h_obs`
within 6 blocks of the tip).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

sys.dont_write_bytecode = True
FORMAT = "BITAGI_CT_Q17_FEE_READ_V1"
DEFAULT_START = 481824   # SegWit active: vsize means the same throughout (note section 3.2)
CONFIRMATIONS = 6
STATS = ("height", "blockhash", "feerate_percentiles")
STATS_ARG = json.dumps(list(STATS), separators=(",", ":"))
CREDENTIAL = re.compile(r"rpcpassword|rpcuser|rpcauth|stdinrpcpass|password", re.IGNORECASE)
HEX64 = re.compile(r"[0-9a-f]{64}")
HEIGHT = re.compile(r"0|[1-9][0-9]{0,9}")
# The only path to bitcoin-cli: method -> the shape of each parameter, in order.
ALLOWED = {"getblockchaininfo": (), "getnetworkinfo": (), "getblockhash": (HEIGHT,),
           "getblockheader": (HEX64,), "getblockstats": (HEX64, re.compile(re.escape(STATS_ARG)))}
HOST = re.compile(r"[A-Za-z0-9.:\[\]-]{1,253}")
UTC = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ")
CALL_TIMEOUT = 900
HEADER_KEYS = ("format", "kind", "core_subversion", "core_version", "chain", "h_obs", "start",
               "tip_height_start", "tip_hash_start", "h_obs_hash", "utc_start", "script_sha256")
TRAILER_KEYS = ("format", "kind", "tip_height_end", "tip_hash_end", "h_obs_hash_end", "utc_end", "heights")
# A resumed file continues the same read only when these header fields are this run's.
RESUME_KEYS = ("format", "chain", "h_obs", "start", "script_sha256")


class Refusal(Exception):
    def __init__(self, code: str, exit_code: int = 2, detail: str = ""):
        super().__init__(code)
        self.code = code
        self.exit_code = exit_code
        self.detail = detail


class FloatText(str):
    """A JSON number with a fraction or exponent, kept as its text; never converted, never a read value."""


def need(condition: bool, code: str, exit_code: int = 2, detail: str = "") -> None:
    if not condition:
        raise Refusal(code, exit_code, detail)


def _no_float(text: str) -> Any:
    raise Refusal("FLOAT_IN_REPLY", 2, text)


def _no_constant(text: str) -> Any:
    raise Refusal("NONFINITE_IN_REPLY", 2, text)


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    keys = [key for key, _ in pairs]
    need(len(keys) == len(set(keys)), "DUPLICATE_KEY")
    return dict(pairs)


def loads(text: str, code: str, *, floats_as_text: bool = False) -> Any:
    """Parse JSON without float: a fraction or exponent is refused, or kept as FloatText when allowed."""
    try:
        return json.loads(text, parse_float=FloatText if floats_as_text else _no_float,
                          parse_constant=_no_constant, object_pairs_hook=_unique)
    except ValueError:
        raise Refusal(code) from None


def integer(value: Any, code: str) -> int:
    need(type(value) is int and value >= 0, code)   # not bool, not FloatText
    return value


def block_hash_text(value: Any, code: str) -> str:
    need(type(value) is str and HEX64.fullmatch(value) is not None, code)
    return value


def percentiles(value: Any) -> list[int]:
    need(type(value) is list and len(value) == 5, "PERCENTILES_NOT_FIVE")
    for item in value:
        integer(item, "PERCENTILE_NOT_INTEGER")
    need(all(low <= high for low, high in zip(value, value[1:])), "PERCENTILES_NOT_MONOTONE")
    return list(value)


def rpc(cli: list[str], method: str, *params: str) -> str:
    """Call bitcoin-cli for one allowlisted method; anything else is refused before the call."""
    need(method in ALLOWED and len(params) == len(ALLOWED[method]), "RPC_NOT_ALLOWED", 5, method)
    need(all(type(p) is str and shape.fullmatch(p) for shape, p in zip(ALLOWED[method], params)),
         "RPC_NOT_ALLOWED", 5, method)
    try:
        done = subprocess.run([*cli, method, *params], stdin=subprocess.DEVNULL, capture_output=True,
                              timeout=CALL_TIMEOUT, check=False)
    except OSError:
        raise Refusal("CLI_MISSING", 3, cli[0]) from None
    except subprocess.TimeoutExpired:
        raise Refusal("RPC_TIMEOUT", 3, method) from None
    # bitcoin-cli's own message is not repeated: run the same call by hand to read it.
    need(done.returncode == 0, "RPC_FAILED", 3, f"{method} exited {done.returncode}")
    try:
        return done.stdout.decode("utf-8")
    except UnicodeDecodeError:
        raise Refusal("REPLY_NOT_UTF8", 2, method) from None


def chain_tip(cli: list[str], *, at_start: bool = False) -> tuple[int, str]:
    reply = loads(rpc(cli, "getblockchaininfo"), "BLOCKCHAININFO_REPLY", floats_as_text=True)
    need(type(reply) is dict, "BLOCKCHAININFO_REPLY")
    need(type(reply.get("chain")) is str, "BLOCKCHAININFO_REPLY")
    need(reply["chain"] == "main", "CHAIN_NOT_MAIN", 6, reply["chain"])
    tip = integer(reply.get("blocks"), "BLOCKCHAININFO_REPLY")
    tip_hash = block_hash_text(reply.get("bestblockhash"), "BLOCKCHAININFO_REPLY")
    if at_start:   # a fully validating, unpruned node (Q17 note section 3.3): JSON false only
        need(reply.get("pruned") is False, "NODE_PRUNED", 6)
        need(reply.get("initialblockdownload") is False, "NODE_IN_IBD", 6)
    return tip, tip_hash


def core_version(cli: list[str]) -> tuple[str, int]:
    reply = loads(rpc(cli, "getnetworkinfo"), "NETWORKINFO_REPLY", floats_as_text=True)
    need(type(reply) is dict and type(reply.get("subversion")) is str, "NETWORKINFO_REPLY")
    return reply["subversion"], integer(reply.get("version"), "NETWORKINFO_REPLY")


def block_hash(cli: list[str], height: int) -> str:
    text = rpc(cli, "getblockhash", str(height))   # a string result: bitcoin-cli prints it unquoted
    return block_hash_text(text.removesuffix("\n").removesuffix("\r"), "BLOCKHASH_REPLY")


def block_header(cli: list[str], height: int, blockhash: str, parent: str | None) -> None:
    """The block's header names this height and hash and, unless parent is None, the previous row as its parent."""
    reply = loads(rpc(cli, "getblockheader", blockhash), "BLOCKHEADER_REPLY", floats_as_text=True)  # `difficulty`
    need(type(reply) is dict, "BLOCKHEADER_REPLY", 2, str(height))
    need(block_hash_text(reply.get("hash"), "BLOCKHEADER_REPLY") == blockhash, "BLOCKHEADER_HASH", 2, str(height))
    need(integer(reply.get("height"), "BLOCKHEADER_REPLY") == height, "BLOCKHEADER_HEIGHT", 2, str(height))
    if parent is not None:
        need(block_hash_text(reply.get("previousblockhash"), "BLOCKHEADER_REPLY") == parent,
             "CHAIN_NOT_LINKED", 2, str(height))


def block_stats(cli: list[str], height: int, blockhash: str) -> dict[str, Any]:
    reply = loads(rpc(cli, "getblockstats", blockhash, STATS_ARG), "BLOCKSTATS_REPLY")
    need(type(reply) is dict and set(reply) == set(STATS), "BLOCKSTATS_KEYS", 2, str(height))
    need(integer(reply["height"], "BLOCKSTATS_HEIGHT") == height, "BLOCKSTATS_HEIGHT", 2, str(height))
    need(block_hash_text(reply["blockhash"], "BLOCKSTATS_HASH") == blockhash, "BLOCKSTATS_HASH", 2, str(height))
    return {"height": height, "blockhash": blockhash, "feerate_percentiles": percentiles(reply["feerate_percentiles"])}


def check_row(row: Any, height: int) -> None:
    need(type(row) is dict and set(row) == set(STATS), "OUTPUT_LINE", 2, str(height))
    need(integer(row["height"], "OUTPUT_LINE") == height, "OUTPUT_HEIGHTS", 2, str(height))
    block_hash_text(row["blockhash"], "OUTPUT_LINE")
    percentiles(row["feerate_percentiles"])


def check_header(header: Any, expected: dict[str, Any]) -> dict[str, Any]:
    need(type(header) is dict and list(header) == list(HEADER_KEYS) and header["kind"] == "header",
         "OUTPUT_HEADER_MISMATCH")
    for key in RESUME_KEYS:
        need(header[key] == expected[key], "OUTPUT_HEADER_MISMATCH", 2, key)
    for key in ("core_version", "h_obs", "start"):
        integer(header[key], "OUTPUT_HEADER_MISMATCH")
    for key in ("tip_hash_start", "h_obs_hash"):
        block_hash_text(header[key], "OUTPUT_HEADER_MISMATCH")
    # As the writing run checked them (Desktop review r4381709026): the start tip and the start time.
    need(integer(header["tip_height_start"], "OUTPUT_HEADER_MISMATCH") >= header["h_obs"] + CONFIRMATIONS,
         "OUTPUT_HEADER_MISMATCH", 2, "tip_height_start")
    need(type(header["utc_start"]) is str and UTC.fullmatch(header["utc_start"]) is not None,
         "OUTPUT_HEADER_MISMATCH", 2, "utc_start")
    need(type(header["core_subversion"]) is str, "OUTPUT_HEADER_MISMATCH")
    return header


def read_existing(path: Path, expected: dict[str, Any]) -> tuple[dict[str, Any], int, bool, str | None]:
    """The header, the number of heights, whether a trailer closes it and the last row's hash (None without
    rows); refused unless exactly continuous."""
    try:
        raw = path.read_bytes()
    except OSError:
        raise Refusal("OUTPUT_UNREADABLE", 3) from None
    need(raw.endswith(b"\n"), "OUTPUT_TORN")   # a torn last line is refused, not repaired
    try:
        lines = raw.decode("utf-8").split("\n")[:-1]
    except UnicodeDecodeError:
        raise Refusal("OUTPUT_LINE") from None
    rows = [loads(line, "OUTPUT_LINE") for line in lines]
    header = check_header(rows[0], expected)
    body = rows[1:]
    trailer = body.pop() if body and type(body[-1]) is dict and body[-1].get("kind") == "trailer" else None
    for offset, row in enumerate(body):
        check_row(row, header["start"] + offset)
    need(len(body) <= header["h_obs"] - header["start"] + 1, "OUTPUT_HEIGHTS")
    # A body that already reaches H skips the resume loop's check at H (Codex review r4381904985): its last
    # row must be the header's block at H before any call or append.
    if trailer is None and len(body) == header["h_obs"] - header["start"] + 1:
        need(body[-1]["blockhash"] == header["h_obs_hash"], "OUTPUT_LINE", 2, "h_obs")
    if trailer is not None:
        # A complete file is accepted without a node, so its end is checked as the run that wrote it checked it.
        need(list(trailer) == list(TRAILER_KEYS) and trailer["format"] == FORMAT, "OUTPUT_TRAILER")
        need(integer(trailer["tip_height_end"], "OUTPUT_TRAILER") >= header["h_obs"] + CONFIRMATIONS, "OUTPUT_TRAILER")
        block_hash_text(trailer["tip_hash_end"], "OUTPUT_TRAILER")
        need(type(trailer["utc_end"]) is str and UTC.fullmatch(trailer["utc_end"]) is not None, "OUTPUT_TRAILER")
        need(integer(trailer["heights"], "OUTPUT_TRAILER") == len(body) == header["h_obs"] - header["start"] + 1,
             "OUTPUT_TRAILER")
        need(body[-1]["blockhash"] == header["h_obs_hash"] == trailer["h_obs_hash_end"], "OUTPUT_TRAILER")
    return header, len(body), trailer is not None, body[-1]["blockhash"] if body else None


def write_line(stream, value: dict[str, Any]) -> None:
    stream.write(json.dumps(value, separators=(",", ":")) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cli_base(args: argparse.Namespace) -> list[str]:
    # The command line overrides the node's bitcoin.conf (module docstring): no `generate`, no `named`.
    cli = [args.bitcoin_cli, "-nogenerate", "-nonamed"]
    cli.append(f"-datadir={args.datadir}" if args.datadir is not None else f"-rpccookiefile={args.rpccookiefile}")
    if args.rpcconnect is not None:
        cli.append(f"-rpcconnect={args.rpcconnect}")
    if args.rpcport is not None:
        cli.append(f"-rpcport={args.rpcport}")
    return cli


def read(args: argparse.Namespace) -> int:
    h_obs, start = args.h_obs, args.start
    need(start <= h_obs, "START_AFTER_H_OBS")
    output = Path(args.output)
    expected = {"format": FORMAT, "chain": "main", "h_obs": h_obs, "start": start,
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    existing = read_existing(output, expected) if output.exists() else None
    if existing is not None and existing[2]:
        print(f"q17-fee-read: {output} is complete ({existing[1]} heights); nothing written")
        return 0
    need(existing is not None or output.parent.is_dir(), "OUTPUT_DIR_MISSING", 3)
    cli = cli_base(args)
    tip, tip_hash = chain_tip(cli, at_start=True)
    need(h_obs <= tip - CONFIRMATIONS, "H_OBS_TOO_RECENT", 6, f"tip {tip}")
    subversion, version = core_version(cli)
    h_obs_hash = block_hash(cli, h_obs)
    if existing is None:
        header = {"format": FORMAT, "kind": "header", "core_subversion": subversion, "core_version": version,
                  "chain": "main", "h_obs": h_obs, "start": start, "tip_height_start": tip,
                  "tip_hash_start": tip_hash, "h_obs_hash": h_obs_hash, "utc_start": utc_now(),
                  "script_sha256": expected["script_sha256"]}
        with open(output, "x", newline="", encoding="utf-8") as stream:
            write_line(stream, header)
        folder = os.open(output.parent, os.O_RDONLY)
        try:
            os.fsync(folder)
        finally:
            os.close(folder)
        written, parent = 0, None
    else:
        header, written, parent = existing[0], existing[1], existing[3]
        need((header["core_subversion"], header["core_version"]) == (subversion, version), "CORE_VERSION_CHANGED")
        need(header["h_obs_hash"] == h_obs_hash, "REORG_AT_H_OBS")
    with open(output, "a", newline="", encoding="utf-8") as stream:
        for height in range(start + written, h_obs + 1):
            blockhash = block_hash(cli, height)
            need(height != h_obs or blockhash == header["h_obs_hash"], "REORG_AT_H_OBS")
            block_header(cli, height, blockhash, parent)
            write_line(stream, block_stats(cli, height, blockhash))
            parent = blockhash
        end_tip, end_hash = chain_tip(cli)
        need(end_tip >= h_obs + CONFIRMATIONS, "TIP_BELOW_H_OBS_PLUS_6", 2, f"tip {end_tip}")
        end_h_obs_hash = block_hash(cli, h_obs)
        need(end_h_obs_hash == header["h_obs_hash"], "REORG_AT_H_OBS")
        write_line(stream, {"format": FORMAT, "kind": "trailer", "tip_height_end": end_tip, "tip_hash_end": end_hash,
                            "h_obs_hash_end": end_h_obs_hash, "utc_end": utc_now(), "heights": h_obs - start + 1})
    print(f"q17-fee-read: {output} complete: heights {start}..{h_obs} ({h_obs + 1 - start - written} read now)")
    return 0


def height_arg(text: str) -> int:
    if HEIGHT.fullmatch(text) is None:
        raise argparse.ArgumentTypeError("a height is a decimal integer")
    return int(text)


def port_arg(text: str) -> int:
    if HEIGHT.fullmatch(text) is None or not 0 < int(text) < 65536:
        raise argparse.ArgumentTypeError("a port is 1..65535")
    return int(text)


def host_arg(text: str) -> str:
    if HOST.fullmatch(text) is None:
        raise argparse.ArgumentTypeError("a host name or address")
    return text


def main(argv: list[str] | None = None) -> int:
    if sys.flags.optimize:
        return 5
    argv = sys.argv[1:] if argv is None else argv
    # Before argparse, which would repeat an unknown argument (and its value) in its message.
    if any(CREDENTIAL.search(arg) for arg in argv):
        print("q17-fee-read: refused: CREDENTIAL_ARGUMENT: credentials are never arguments; "
              "bitcoin-cli reads the cookie itself", file=sys.stderr)
        return 5
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    parser.add_argument("--h-obs", type=height_arg, required=True)
    parser.add_argument("--start", type=height_arg, default=DEFAULT_START)
    parser.add_argument("--output", required=True)
    parser.add_argument("--bitcoin-cli", default="bitcoin-cli")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--datadir")
    source.add_argument("--rpccookiefile")
    parser.add_argument("--rpcconnect", type=host_arg)
    parser.add_argument("--rpcport", type=port_arg)
    args = parser.parse_args(argv)
    try:
        return read(args)
    except Refusal as refusal:
        detail = f": {refusal.detail}" if refusal.detail else ""
        print(f"q17-fee-read: refused: {refusal.code}{detail}", file=sys.stderr)
        return refusal.exit_code


if __name__ == "__main__":
    import claude_track_exit

    claude_track_exit.run(main)
