"""Append-only run files: one JSON line per event, canonical bytes for content.

Line kinds:
  header  run identity, engine/schema versions, scenario, genesis state
  tick    the tick record, the committed state, the engine's own availability
  timing  wall-clock cost of that tick (outside every digest and seal)
  end     tick count and the trail digest over all tick lines

Content lines are canonical JSON (sorted keys, integers and strings only), so
two runs of the same scenario produce byte-identical content lines. Timing
lines are the only non-deterministic bytes and are kept separate on purpose.

Format v3.stream.2 added optional blocks a world run needs, each verified by
the reader: a `world` overlay (positions, needs) with its own digest on the
header and on every tick; `decisions` (what each actor chose and why);
`observations` (what each living person saw at tick start); and `production`,
the renewal applied to sources after the tick, with the digest of the state
that results. When production is present the next tick chains from that
produced state, and the reader recomputes it from the stored state rather
than trusting the digest.

Format v3.stream.3 is the sealed evidence stream of slice 1c, declared in
evidence/stage-01/RECORD.md before this code. The header adds `horizon` (the
declared tick count), `code_identity` (sha256 of every simulation source file)
and `config_identity` (digest of the scenario description). Every tick line
adds `inputs`: the proposals submitted to the kernel that tick, in submission
order. Seals chain the whole file:

    header seal = digest(header without "seal")
    tick seal   = digest({"prev": previous seal, "tick": digest(tick without "seal")})

and the end line carries the final seal. The reader verifies the chain, names
the first line that fails any check, and reports `last_sealed_tick`: the last
tick that its own line and every line before it vouch for. Timing lines stay
outside the chain. v3.stream.1 and v3.stream.2 files remain readable, without
seal checks.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kernel import (ENGINE_VERSION, SCHEMA_VERSION, CanonicalError, Proposal, TickRecord, WorldState,
                    canonical_bytes, canonicalise, digest)

STREAM_FORMAT = "v3.stream.3"
SEALED_FORMATS = frozenset({STREAM_FORMAT})
READABLE_FORMATS = frozenset({"v3.stream.1", "v3.stream.2", STREAM_FORMAT})
CODE_PACKAGES = ("kernel", "stream", "world")
REPO_ROOT = Path(__file__).resolve().parent.parent
INPUT_FIELDS = ("proposal_id", "actor", "order", "operation")


class RunFileError(Exception):
    """A run file is missing, malformed, or does not verify."""


def _line(payload: dict[str, Any]) -> bytes:
    return canonical_bytes(payload) + b"\n"


def _safe_digest(value: Any) -> str | None:
    """The digest of untrusted file content, or None when it has no canonical form."""
    try:
        return digest(value)
    except CanonicalError:
        return None


# --- identities and seals --------------------------------------------------------

def code_identity(root: Path = REPO_ROOT) -> dict[str, Any]:
    """What produced a run, independent of git: the sha256 of every Python file
    under kernel/, stream/ and world/ (bytes read with CRLF as LF, so a checkout's
    line endings do not change it) and the digest of that map."""
    files: dict[str, str] = {}
    for package in CODE_PACKAGES:
        for path in sorted((root / package).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            files[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    return {"files": files, "digest": digest(files)}


def without_seal(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "seal"}


def header_seal(header: Mapping[str, Any]) -> str:
    return digest(without_seal(header))


def tick_seal(previous: str | None, payload: Mapping[str, Any]) -> str:
    return digest({"prev": previous, "tick": digest(without_seal(payload))})


# --- inputs ------------------------------------------------------------------------

def _typed(value: Any) -> list[Any]:
    """The declared encoding for a submitted value with no canonical form."""
    if value is None:
        return ["none", None]
    if isinstance(value, bool):
        return ["bool", 1 if value else 0]
    if isinstance(value, int):
        return ["int", value]
    if isinstance(value, float):
        return ["float", value.hex()]
    if isinstance(value, str):
        return ["str", value]
    if isinstance(value, Mapping):
        pairs = [[_typed(key), _typed(item)] for key, item in value.items()]
        return ["map", sorted(pairs, key=lambda pair: canonical_bytes(pair[0]))]
    if isinstance(value, (list, tuple)):
        return ["seq", [_typed(item) for item in value]]
    raise RunFileError(f"a submitted {type(value).__name__} has no declared input encoding")


def _untyped(encoded: Any) -> Any:
    if not (isinstance(encoded, list) and len(encoded) == 2 and isinstance(encoded[0], str)):
        raise RunFileError(f"not a typed input value: {encoded!r}")
    tag, payload = encoded
    if tag == "none" and payload is None:
        return None
    if tag == "bool" and type(payload) is int and payload in (0, 1):
        return payload == 1
    if tag == "int" and type(payload) is int:
        return payload
    if tag == "str" and isinstance(payload, str):
        return payload
    if tag == "float" and isinstance(payload, str):
        try:
            return float.fromhex(payload)
        except ValueError as exc:
            raise RunFileError(f"not a typed float: {payload!r}") from exc
    if tag == "seq" and isinstance(payload, list):
        return tuple(_untyped(item) for item in payload)
    if tag == "map" and isinstance(payload, list) and all(isinstance(pair, list) and len(pair) == 2 for pair in payload):
        try:
            return {_untyped(key): _untyped(item) for key, item in payload}
        except TypeError as exc:
            raise RunFileError(f"a typed map key is not hashable: {exc}") from exc
    raise RunFileError(f"not a typed input value: {encoded!r}")


def encode_input(proposal: Proposal) -> dict[str, Any]:
    """One submitted proposal as its tick line records it: `params` in canonical
    form when the params have one, else `params_typed` in the declared encoding."""
    if not isinstance(proposal, Proposal):
        raise RunFileError(f"an input must be a Proposal, got {type(proposal).__name__}")
    entry: dict[str, Any] = {name: getattr(proposal, name) for name in INPUT_FIELDS}
    try:
        entry["params"] = canonicalise(proposal.params)
    except CanonicalError:
        entry["params_typed"] = _typed(proposal.params)
    return entry


def decode_input(entry: Mapping[str, Any]) -> Proposal:
    """The Proposal an input entry records; it equals the one that was submitted."""
    if not isinstance(entry, Mapping):
        raise RunFileError("an input entry must be a mapping")
    base = set(INPUT_FIELDS)
    if set(entry) == base | {"params"}:
        params = entry["params"]
    elif set(entry) == base | {"params_typed"}:
        params = _untyped(entry["params_typed"])
    else:
        raise RunFileError(f"an input entry needs {sorted(base)} and params or params_typed, got {sorted(entry)}")
    try:
        return Proposal(entry["proposal_id"], entry["actor"], entry["order"], entry["operation"], params)
    except (TypeError, ValueError) as exc:
        raise RunFileError(f"an input entry does not make a proposal: {exc}") from exc


# --- production --------------------------------------------------------------------

def apply_production(state: dict[str, Any], production: list[dict[str, Any]]) -> dict[str, Any]:
    """The production rule on a stored canonical state: each entry adds
    `amount` (a positive integer) to the stock of an existing source and
    nothing else changes. Pure, on plain JSON, so a reader can recompute the
    produced state without the kernel. Raises RunFileError on a bad entry."""
    produced = json.loads(json.dumps(state))
    sources = produced.get("sources")
    if not isinstance(sources, dict):
        raise RunFileError("production needs a state with sources")
    seen: set[str] = set()
    for entry in production:
        source = entry.get("source") if isinstance(entry, dict) else None
        amount = entry.get("amount") if isinstance(entry, dict) else None
        if not isinstance(source, str) or source not in sources:
            raise RunFileError(f"production names an unknown source {source!r}")
        if source in seen:
            raise RunFileError(f"production names {source!r} twice")
        if type(amount) is not int or amount <= 0:
            raise RunFileError(f"production of {source!r} must be a positive integer, got {amount!r}")
        seen.add(source)
        sources[source]["stock"] = int(sources[source]["stock"]) + amount
    return produced


# --- writing -----------------------------------------------------------------------

def tick_payload(record: TickRecord, next_state: WorldState, *, inputs: Iterable[Proposal],
                 world: Mapping[str, Any] | None = None, decisions: Mapping[str, Any] | None = None,
                 observations: Mapping[str, Any] | None = None, production: list[dict[str, Any]] | None = None,
                 produced_state: WorldState | None = None) -> dict[str, Any]:
    """The content of one tick line, without its seal.

    The writer seals and writes it; replay rebuilds it with the live code and
    compares it with the file. `next_state` is what settlement committed and
    `inputs` are the proposals that record settled. When a world process then
    produced stock, pass `production` (the rule's entries) and `produced_state`
    (the kernel state that resulted): the pure rule on the committed state must
    give exactly that state, so a file never records production that did not
    happen."""
    if record.next_state_digest != next_state.digest():
        raise RunFileError("committed state does not match the record's next_state_digest")
    encoded = [encode_input(proposal) for proposal in inputs]
    if sorted(entry["proposal_id"] for entry in encoded) != sorted(outcome.proposal_id for outcome in record.outcomes):
        raise RunFileError("inputs are not the proposals this record settled")
    payload: dict[str, Any] = {
        "kind": "tick",
        "tick": record.tick,
        "record": record.canonical(),
        "record_digest": record.digest(),
        "state": next_state.canonical(),
        "state_digest": next_state.digest(),
        "availability": next_state.availability(),
        "inputs": encoded,
    }
    if world is not None:
        payload["world"] = world
        payload["world_digest"] = digest(world)
    if decisions is not None:
        payload["decisions"] = decisions
    if observations is not None:
        payload["observations"] = observations
    if production:
        if produced_state is None:
            raise RunFileError("production needs the produced state")
        expected = digest(apply_production(next_state.canonical(), production))
        if expected != produced_state.digest():
            raise RunFileError("produced state is not the production rule applied to the committed state")
        payload["production"] = production
        payload["produced_state_digest"] = produced_state.digest()
    elif produced_state is not None and produced_state.digest() != next_state.digest():
        raise RunFileError("state changed after settlement without production")
    return payload


class RunWriter:
    """Write one sealed run. Refuses to overwrite; every line is flushed as written.

    The end line is written only when `horizon` ticks were recorded and the
    writer is closed normally. A run stopped early (an exception inside the
    `with` block, or `abort()`) is left cut, with no end line, so recovery can
    resume it from its last sealed tick."""

    def __init__(self, path: Path, *, run_id: str, genesis: WorldState, scenario: dict[str, Any],
                 horizon: int, world: dict[str, Any] | None = None) -> None:
        if type(horizon) is not int or horizon < 0:
            raise RunFileError(f"a run horizon must be an integer of zero or more, got {horizon!r}")
        header: dict[str, Any] = {
            "kind": "header",
            "format": STREAM_FORMAT,
            "run_id": run_id,
            "engine_version": ENGINE_VERSION,
            "schema_version": SCHEMA_VERSION,
            "scenario": scenario,
            "config_identity": digest(scenario),
            "code_identity": code_identity(),
            "horizon": horizon,
            "genesis": genesis.canonical(),
            "genesis_digest": genesis.digest(),
        }
        if world is not None:
            header["world"] = world
            header["world_digest"] = digest(world)
        header["seal"] = header_seal(header)
        self.header = header
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("xb")
        self._closed = False
        self._seal = header["seal"]
        self._ticks = 0
        self._next_tick = genesis.tick
        self._trail = hashlib.sha256()
        self._write(header)

    @classmethod
    def resume(cls, path: Path, *, header: dict[str, Any], prefix: bytes, tick_lines: Iterable[bytes],
               seal: str, next_tick: int) -> "RunWriter":
        """Continue a sealed run in a new file from its sealed prefix (slice 1c
        recovery). The prefix bytes are written unchanged, and the seal chain,
        trail digest and tick count carry on from them, so a faithful
        continuation is byte-identical to an uninterrupted run, timing aside.
        The caller vouches for the prefix; stream/recover.py builds it from
        what the reader verified."""
        if header.get("format") not in SEALED_FORMATS:
            raise RunFileError("only a sealed run can be resumed")
        writer = cls.__new__(cls)
        writer.header = header
        writer._trail = hashlib.sha256()
        writer._ticks = 0
        for raw in tick_lines:
            writer._trail.update(raw)
            writer._ticks += 1
        if writer._ticks > header["horizon"]:
            raise RunFileError("the sealed prefix is longer than the run's horizon")
        writer._seal = seal
        writer._next_tick = next_tick
        writer.path = Path(path)
        writer.path.parent.mkdir(parents=True, exist_ok=True)
        writer._handle = writer.path.open("xb")
        writer._closed = False
        writer._handle.write(prefix)
        writer._handle.flush()
        return writer

    def _write(self, payload: dict[str, Any]) -> bytes:
        raw = _line(payload)
        self._handle.write(raw)
        self._handle.flush()
        return raw

    @property
    def seal(self) -> str:
        """The seal the next tick line will chain from."""
        return self._seal

    def record(self, record: TickRecord, next_state: WorldState, *, inputs: Iterable[Proposal],
               elapsed_ns: int | None = None, world: dict[str, Any] | None = None,
               decisions: dict[str, Any] | None = None, observations: dict[str, Any] | None = None,
               production: list[dict[str, Any]] | None = None, produced_state: WorldState | None = None) -> None:
        """Append one sealed tick. See `tick_payload` for what is checked."""
        if self._closed:
            raise RunFileError("run file already closed")
        if self._ticks >= self.header["horizon"]:
            raise RunFileError(f"the run's horizon of {self.header['horizon']} ticks is already written")
        if record.tick != self._next_tick:
            raise RunFileError(f"expected a record for tick {self._next_tick}, got tick {record.tick}")
        payload = tick_payload(record, next_state, inputs=inputs, world=world, decisions=decisions,
                               observations=observations, production=production, produced_state=produced_state)
        payload["seal"] = tick_seal(self._seal, payload)
        raw = self._write(payload)
        self._seal = payload["seal"]
        self._trail.update(raw)
        self._ticks += 1
        self._next_tick += 1
        if elapsed_ns is not None:
            self._write({"kind": "timing", "tick": record.tick, "elapsed_ns": int(elapsed_ns)})

    def close(self) -> str:
        """Write the end line and return the trail digest. Refuses, leaving the
        file cut, when fewer than `horizon` ticks were recorded."""
        if self._closed:
            return self._trail.hexdigest()
        if self._ticks != self.header["horizon"]:
            self.abort()
            raise RunFileError(f"closed after {self._ticks} of {self.header['horizon']} ticks; "
                               "the file is left without an end line")
        trail = self._trail.hexdigest()
        self._write({"kind": "end", "ticks": self._ticks, "trail_digest": trail, "final_seal": self._seal})
        self._handle.flush()
        os.fsync(self._handle.fileno())
        self._handle.close()
        self._closed = True
        return trail

    def abort(self) -> None:
        """Stop without an end line: the file stays a cut run."""
        if not self._closed:
            self._handle.flush()
            self._handle.close()
            self._closed = True

    def __enter__(self) -> "RunWriter":
        return self

    def __exit__(self, exc_type: object, *exc: object) -> None:
        if exc_type is None:
            self.close()
        else:
            self.abort()


# --- reading -----------------------------------------------------------------------

@dataclass(frozen=True)
class Run:
    path: Path
    header: dict[str, Any]
    ticks: tuple[dict[str, Any], ...]
    timings: dict[int, int]
    end: dict[str, Any] | None
    trail_digest: str
    problems: tuple[str, ...] = field(default_factory=tuple)
    # v3.stream.3: the last tick the seal chain and every check vouch for
    # (-1 when none does); None for unsealed formats.
    last_sealed_tick: int | None = None
    # the first line that failed any check, or None
    first_break_line: int | None = None

    @property
    def run_id(self) -> str:
        return str(self.header.get("run_id", ""))

    @property
    def complete(self) -> bool:
        return self.end is not None and not self.problems

    @property
    def has_world(self) -> bool:
        return "world" in self.header

    @property
    def sealed(self) -> bool:
        return self.header.get("format") in SEALED_FORMATS


def chained_from(tick: dict[str, Any]) -> Any:
    """The state digest the next tick must start from: the produced state
    when a world process produced stock after this tick, else the committed one."""
    if "production" in tick:
        return tick.get("produced_state_digest")
    return tick.get("state_digest")


def _sealed_header_problems(header: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    horizon = header.get("horizon")
    if type(horizon) is not int or horizon < 0:
        problems.append("header horizon is not an integer of zero or more")
    identity = header.get("code_identity")
    if (not isinstance(identity, dict) or not isinstance(identity.get("files"), dict)
            or identity.get("digest") != _safe_digest(identity["files"])):
        problems.append("header code identity does not match its file map")
    if header.get("config_identity") != _safe_digest(header.get("scenario")):
        problems.append("header config identity is not the digest of its scenario")
    if header.get("seal") != _safe_digest(without_seal(header)):
        problems.append("header seal does not verify")
    return problems


def _input_problems(payload: Mapping[str, Any]) -> list[str]:
    inputs = payload.get("inputs")
    if not isinstance(inputs, list):
        return ["tick has no inputs list"]
    try:
        ids = sorted(decode_input(entry).proposal_id for entry in inputs)
    except RunFileError as exc:
        return [f"inputs do not decode ({exc})"]
    record = payload.get("record")
    outcomes = record.get("outcomes") if isinstance(record, dict) else None
    if not isinstance(outcomes, list) or not all(isinstance(o, dict) and isinstance(o.get("proposal_id"), str)
                                                 for o in outcomes):
        return ["tick record has no readable outcomes to match its inputs"]
    if ids != sorted(o["proposal_id"] for o in outcomes):
        return ["inputs are not the proposals the record settled"]
    return []


def read_run(path: Path) -> Run:
    """Read and verify a run file. Every stored digest is recomputed from the
    stored content and, for sealed formats, every seal; a run with problems is
    still returned so a viewer can show what exists, but `complete` is false."""
    path = Path(path)
    if not path.is_file():
        raise RunFileError(f"no run file at {path}")
    header: dict[str, Any] | None = None
    ticks: list[dict[str, Any]] = []
    timings: dict[int, int] = {}
    end: dict[str, Any] | None = None
    problems: list[str] = []
    trail = hashlib.sha256()
    expected_tick = None
    sealed = False
    seal: str | None = None       # the stored seal the next tick line chains from
    last_sealed: int | None = None
    first_break: int | None = None
    intact = True                 # no line so far has failed any check
    with path.open("rb") as handle:
        for number, raw in enumerate(handle, start=1):
            before = len(problems)
            try:
                if not raw.endswith(b"\n"):
                    problems.append(f"line {number}: incomplete (no newline)")
                    break
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError as exc:
                    problems.append(f"line {number}: not JSON ({exc.msg})")
                    continue
                if not isinstance(payload, dict) or "kind" not in payload:
                    problems.append(f"line {number}: not an event")
                    continue
                if end is not None:
                    problems.append(f"line {number}: event after end")
                kind = payload["kind"]
                if kind == "header":
                    first_header = header is None
                    if not first_header:
                        problems.append(f"line {number}: second header")
                    header = payload
                    if payload.get("format") not in READABLE_FORMATS:
                        problems.append(f"line {number}: unsupported format {payload.get('format')!r}")
                    elif digest(payload.get("genesis")) != payload.get("genesis_digest"):
                        problems.append(f"line {number}: genesis digest does not match content")
                    else:
                        expected_tick = int(payload["genesis"]["tick"])
                    if "world" in payload and digest(payload.get("world")) != payload.get("world_digest"):
                        problems.append(f"line {number}: world genesis digest does not match content")
                    if first_header and payload.get("format") in SEALED_FORMATS:
                        sealed, last_sealed, seal = True, -1, payload.get("seal")
                        problems.extend(f"line {number}: {p}" for p in _sealed_header_problems(payload))
                elif kind == "tick":
                    if header is None:
                        problems.append(f"line {number}: tick before header")
                    if canonical_bytes(payload) + b"\n" != raw:
                        problems.append(f"line {number}: tick line is not canonical bytes")
                    if digest(payload.get("record")) != payload.get("record_digest"):
                        problems.append(f"line {number}: record digest does not match content")
                    if digest(payload.get("state")) != payload.get("state_digest"):
                        problems.append(f"line {number}: state digest does not match content")
                    record = payload.get("record") or {}
                    if record.get("next_state_digest") != payload.get("state_digest"):
                        problems.append(f"line {number}: record and state disagree")
                    if expected_tick is not None and payload.get("tick") != expected_tick:
                        problems.append(f"line {number}: expected tick {expected_tick}, found {payload.get('tick')}")
                    if ticks and chained_from(ticks[-1]) != record.get("prior_state_digest"):
                        problems.append(f"line {number}: prior state digest does not chain")
                    if not ticks and header is not None and header.get("genesis_digest") != record.get("prior_state_digest"):
                        problems.append(f"line {number}: first tick does not start from genesis")
                    if "world" in payload and digest(payload.get("world")) != payload.get("world_digest"):
                        problems.append(f"line {number}: world digest does not match content")
                    if "production" in payload:
                        try:
                            produced = digest(apply_production(payload.get("state") or {}, payload["production"]))
                        except RunFileError as exc:
                            problems.append(f"line {number}: {exc}")
                        else:
                            if produced != payload.get("produced_state_digest"):
                                problems.append(f"line {number}: produced state digest is not the production rule on the committed state")
                    elif "produced_state_digest" in payload:
                        problems.append(f"line {number}: produced state without production")
                    if sealed:
                        problems.extend(f"line {number}: {p}" for p in _input_problems(payload))
                        try:
                            expected_seal = tick_seal(seal, payload)
                        except CanonicalError:
                            expected_seal = None
                        if expected_seal is None or payload.get("seal") != expected_seal:
                            problems.append(f"line {number}: seal does not verify")
                        seal = payload.get("seal")
                    trail.update(raw)
                    ticks.append(payload)
                    expected_tick = int(payload.get("tick", -1)) + 1
                    if sealed and intact and len(problems) == before:
                        last_sealed = payload.get("tick")
                elif kind == "timing":
                    timings[int(payload.get("tick", -1))] = int(payload.get("elapsed_ns", 0))
                elif kind == "end":
                    end = payload
                    if payload.get("ticks") != len(ticks):
                        problems.append(f"line {number}: end declares {payload.get('ticks')} ticks, file has {len(ticks)}")
                    if payload.get("trail_digest") != trail.hexdigest():
                        problems.append(f"line {number}: trail digest does not match the tick lines")
                    if sealed:
                        if payload.get("final_seal") != seal:
                            problems.append(f"line {number}: final seal is not the last tick's seal")
                        if header is not None and payload.get("ticks") != header.get("horizon"):
                            problems.append(f"line {number}: end declares {payload.get('ticks')} ticks, "
                                            f"horizon is {header.get('horizon')}")
                else:
                    problems.append(f"line {number}: unknown event kind {kind!r}")
            finally:
                if len(problems) > before:
                    intact = False
                    if first_break is None:
                        first_break = number
    if header is None:
        problems.append("no header")
        header = {}
    if end is None:
        problems.append("no end record (run did not finish, or the file was cut)")
    return Run(path=path, header=header, ticks=tuple(ticks), timings=timings, end=end,
               trail_digest=trail.hexdigest(), problems=tuple(problems),
               last_sealed_tick=last_sealed if sealed else None, first_break_line=first_break)
