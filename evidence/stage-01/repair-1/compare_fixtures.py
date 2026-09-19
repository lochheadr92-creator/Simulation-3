"""Check original fixture state identities and the explicitly versioned records."""
import json
from pathlib import Path
import sys

evidence = Path(sys.argv[1]).resolve()
base = json.loads((evidence / "fixtures-base.json").read_text(encoding="utf-8"))
fixed = json.loads((evidence / "fixtures-repaired.json").read_text(encoding="utf-8"))
other_seed = json.loads((evidence / "fixtures-repaired-seed17.json").read_text(encoding="utf-8"))
checks = {
    "captured_ticks": len(base),
    "same_number_of_ticks": len(base) == len(fixed),
    "state_bytes_and_digests_identical": all(
        a["state"] == b["state"] and a["state_digest"] == b["state_digest"] for a, b in zip(base, fixed)),
    "record_versions": sorted({(a["record"]["engine_version"], b["record"]["engine_version"]) for a, b in zip(base, fixed)}),
    "record_payloads_identical_except_engine_version": all(
        {k:v for k,v in a["record"].items() if k != "engine_version"} ==
        {k:v for k,v in b["record"].items() if k != "engine_version"} for a,b in zip(base, fixed)),
    "repaired_hash_seed_0_and_17_identical": fixed == other_seed,
}
assert len(base) == 8 and checks["same_number_of_ticks"]
assert checks["state_bytes_and_digests_identical"]
assert checks["record_payloads_identical_except_engine_version"]
assert checks["record_versions"] == [("0.1.0-stage1a", "0.1.1-stage1a")]
assert checks["repaired_hash_seed_0_and_17_identical"]
(evidence / "fixture-comparison.json").write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")
print(json.dumps(checks, indent=2))

