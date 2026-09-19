"""Instrument validation for the Stage 1a test suite.

A suite that passes proves nothing until it is shown to fail when the rule it
claims to check is broken. This applies one deliberate defect to the kernel at a
time, runs the whole suite, records which tests noticed, and puts the file back
byte for byte.

Each mutation names the declared rule it breaks. A mutation that nobody notices
is a blind spot in the suite and is reported as such, with a non-zero exit,
unless it is declared unreachable below with the reason.

Run from the repository root:

    py -3 evidence/stage-01/instrument/mutation_check.py

Raw pytest output for every run is written beside this file under `runs/`, so a
reader can check the parsed summary against what pytest actually printed.

The first version of this harness reported one mutation's failures against the
next mutation. Two of the mutations below change `kernel/settlement.py` by
exactly the same number of bytes, and the runs fall inside one filesystem mtime
second, so CPython accepted the previous mutation's cached bytecode as current.
That version also rewrote the kernel through text-mode writes, which changed
line endings on Windows, so a restore was not byte for byte. Bytecode writing is
now disabled, every `__pycache__` is removed before each run, files are read and
written as bytes, and the harness checks both that the mutated text is really
the text on disk and that the restore is exact.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
RUNS = pathlib.Path(__file__).resolve().parent / "runs"

MUTATIONS = [
    (
        "rotation-frozen",
        "the rotation always starts at the sorted roster, giving a permanent winner",
        "kernel/ordering.py",
        "    offset = tick % len(roster)",
        "    offset = 0",
    ),
    (
        "credit-spendable-immediately",
        "a unit credited this tick becomes spendable this tick",
        "kernel/settlement.py",
        "            if effect.delta < 0:\n                available[effect.account] += effect.delta",
        "            if True:\n                available[effect.account] += effect.delta",
    ),
    (
        "authority-not-checked",
        "authority over a debited account is never checked",
        "kernel/settlement.py",
        "            refusal = _authority(proposal.actor, effects, state)",
        "            refusal = None",
    ),
    (
        "order-by-arrival",
        "resolution follows the order proposals were collected in",
        "kernel/settlement.py",
        "    candidates.sort(key=lambda candidate: (ranks[candidate[1].actor], sequences[(candidate[1].actor, candidate[1].order)]))",
        "    candidates.sort(key=lambda candidate: candidate[0])",
    ),
    (
        "outcome-order-by-arrival",
        "the record lists outcomes in the order proposals arrived",
        "kernel/settlement.py",
        "            ranks.get(outcome.actor, unranked),\n            outcome.actor,\n            outcome.sequence,\n            outcome.proposal_id,\n            outcome.operation,",
        "            0,",
    ),
    (
        "canonical-keys-unsorted",
        "canonical bytes follow mapping insertion order",
        "kernel/canonical.py",
        "        for key in sorted(value)",
        "        for key in value",
    ),
    (
        "state-mappings-writable",
        "state hands out a live mutable mapping",
        "kernel/state.py",
        '        object.__setattr__(self, "balances", MappingProxyType(balances))',
        '        object.__setattr__(self, "balances", balances)',
    ),
    (
        "view-shares-the-live-mapping",
        "a view points at the state's own mapping instead of a copy",
        "kernel/state.py",
        "            balances=MappingProxyType(dict(self.balances)),",
        "            balances=self.balances,",
    ),
    (
        "shortfall-checks-one-leg",
        "only the first leg of a transaction is checked against availability",
        "kernel/settlement.py",
        "    for account in sorted(required):",
        "    for account in sorted(required)[:1]:",
    ),
    (
        "duplicate-identity-allowed",
        "proposals sharing an identity are resolved instead of rejected",
        "kernel/settlement.py",
        "        if id_counts[proposal.proposal_id] > 1:",
        "        if id_counts[proposal.proposal_id] > 99:",
    ),
    (
        "duplicate-sequence-allowed",
        "one actor may declare two proposals at the same sequence",
        "kernel/settlement.py",
        "        if order_counts[(proposal.actor, proposal.order)] > 1:",
        "        if order_counts[(proposal.actor, proposal.order)] > 99:",
    ),
    (
        "balanced-effects-not-checked",
        "a transaction may create or destroy units",
        "kernel/settlement.py",
        "        if refusal is None and not effects_are_balanced(effects):",
        "        if False and not effects_are_balanced(effects):",
    ),
    (
        "amounts-may-be-fractional",
        "a transaction amount need not be a whole unit",
        "kernel/units.py",
        "    return isinstance(value, int) and not isinstance(value, bool)",
        "    return isinstance(value, (int, float))",
    ),
    (
        "conservation-rail-off",
        "settlement no longer checks that the declared total is conserved",
        "kernel/settlement.py",
        "    if next_state.total() != state.total():",
        "    if False and next_state.total() != state.total():",
    ),
    (
        "negative-balance-rail-off",
        "settlement no longer refuses to leave a negative balance",
        "kernel/settlement.py",
        "    if negatives:",
        "    if False and negatives:",
    ),
    (
        "tick-reentry-allowed",
        "same-thread callbacks can reenter the active engine tick",
        "kernel/engine.py",
        "from threading import Lock",
        "from threading import RLock as Lock",
    ),
    (
        "unknown-actor-order-ambiguous",
        "unknown actors share a rejected-outcome sorting key",
        "kernel/settlement.py",
        "            outcome.actor,\n",
        "",
    ),
    (
        "runner-errors-count-as-detection",
        "an invalid test execution is counted as a detected mutation",
        "evidence/stage-01/instrument/mutation_check.py",
        "    if code ==" " 1 and failures and not any(item.startswith(\"ERROR:\") for item in failures):",
        "    if code != 0:",
    ),
    (
        "integer-encoding-uses-global-limit",
        "accepted large quantities cannot be serialized",
        "kernel/canonical.py",
        '    return _encode(canonicalise(value)).encode("utf-8")',
        '    return json.dumps(canonicalise(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")',
    ),
    (
        "caller-assigns-output-sequence",
        "a caller order is copied instead of assigning an engine sequence",
        "kernel/settlement.py",
        "            sequence=sequences[(proposal.actor, proposal.order)],",
        "            sequence=proposal.order,",
    ),
]

# Mutations that no test can notice, with the reason. A rail whose precondition
# two earlier rails already make unreachable is defence in depth, not a checked
# behaviour, and saying so is more honest than quietly dropping the mutation.
UNREACHABLE = {
    "conservation-rail-off": (
        "no input can reach this rail: a committed transaction must already have "
        "balanced effects and touch only accounts inside the world, and those two "
        "together conserve the total by construction"
    ),
}


def clear_bytecode() -> None:
    for cache in ROOT.rglob("__pycache__"):
        if cache.is_symlink() or not cache.resolve().is_relative_to(ROOT.resolve()):
            raise RuntimeError(f"refusing bytecode cleanup outside the instrument root: {cache}")
        shutil.rmtree(cache, ignore_errors=True)


def run_suite(label: str) -> tuple[int, list[str]]:
    clear_bytecode()
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=environment,
    )
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / f"{label}.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
    failures = sorted(
        {
            line.split(" ")[1] if line.startswith("FAILED ") else "ERROR:" + line.split(" ")[1]
            for line in result.stdout.splitlines()
            if line.startswith(("FAILED ", "ERROR "))
        }
    )
    return result.returncode, failures


def classify_result(code: int, failures: list[str]) -> str:
    """A failed runner is not evidence that a test detected the mutation."""
    if code == 0 and not failures:
        return "survived"
    if code == 1 and failures and not any(item.startswith("ERROR:") for item in failures):
        return "detected"
    return "UNKNOWN"


def main() -> int:
    baseline_code, baseline_failures = run_suite("00-baseline")
    print(f"baseline: exit {baseline_code}, {len(baseline_failures)} failing")
    if baseline_code != 0:
        print("the suite does not pass before mutation; fix that first")
        return 1

    blind_spots: list[str] = []
    declared_unreachable: list[str] = []
    invalid_runs: list[str] = []

    for number, (name, description, relative, old, new) in enumerate(MUTATIONS, start=1):
        path = ROOT / relative
        original = path.read_bytes()
        source = original.decode("utf-8")
        if source.count(old) != 1:
            print(f"{name}: anchor text not found exactly once in {relative}")
            return 1

        mutated = source.replace(old, new, 1)
        try:
            path.write_bytes(mutated.encode("utf-8"))
            if path.read_bytes().decode("utf-8") != mutated:
                print(f"{name}: the mutation is not the text on disk")
                return 1
            code, failures = run_suite(f"{number:02d}-{name}")
        finally:
            path.write_bytes(original)

        if path.read_bytes() != original:
            print(f"{name}: {relative} was not restored byte for byte")
            return 1

        print(f"\n{name}: {description}")
        print(f"  file      {relative}")
        print(f"  exit      {code}")
        print(f"  noticed   {len(failures)} test(s)")
        for failure in failures:
            print(f"            {failure}")

        classification = classify_result(code, failures)
        if classification == "UNKNOWN":
            print("  UNKNOWN   runner/collection failure or no executed failing test")
            invalid_runs.append(name)
        elif classification == "survived":
            if name in UNREACHABLE:
                print(f"  unreachable  {UNREACHABLE[name]}")
                declared_unreachable.append(name)
            else:
                blind_spots.append(name)
        elif name in UNREACHABLE:
            print("  note      declared unreachable, yet a test noticed it; the declaration is wrong")
            blind_spots.append(name)

    restored_code, _ = run_suite("99-restored")
    print(f"\nrestored: exit {restored_code}")
    if restored_code != 0:
        print("the kernel was not restored cleanly")
        return 1

    if invalid_runs:
        print(f"\nUNKNOWN mutation results, not counted as detected: {invalid_runs}")
        return 1

    if blind_spots:
        print(f"\nBLIND SPOTS, no test noticed: {blind_spots}")
        return 1

    detected = len(MUTATIONS) - len(declared_unreachable)
    print(f"\n{detected} of {len(MUTATIONS)} mutations were detected by at least one test")
    for name in declared_unreachable:
        print(f"declared unreachable; survival alone does not prove unreachability: {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
