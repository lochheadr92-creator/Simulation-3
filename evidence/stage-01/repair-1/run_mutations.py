"""Run the real mutation instrument with fresh outputs and bounded pytest temp."""
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
output = root / "evidence/stage-01/repair-1"
temp = Path(sys.argv[2]).resolve()
if not temp.parent.is_dir() or temp.is_symlink():
    raise SystemExit("Expected an explicit fresh pytest temp under an existing validation directory")
if temp.exists():
    raise SystemExit("Choose a fresh pytest temp directory; do not overwrite prior runs")
output.mkdir(parents=True, exist_ok=True)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PYTHONHASHSEED"] = "0"
os.environ["PYTEST_ADDOPTS"] = '--basetemp="' + temp.as_posix() + '"'
spec = importlib.util.spec_from_file_location("repair_mutations", root / "evidence/stage-01/instrument/mutation_check.py")
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)
harness.RUNS = output / "mutation-runs"
paths = sorted({root / mutation[2] for mutation in harness.MUTATIONS})
before = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
with (output / "mutation-output.txt").open("w", encoding="utf-8", newline="\n") as stream, contextlib.redirect_stdout(stream):
    code = harness.main()
after = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
result = {"exit_code": code, "files_restored_exactly": before == after, "before": before, "after": after,
          "python": sys.version, "python_hash_seed": "0", "pytest_addopts": os.environ["PYTEST_ADDOPTS"]}
(output / "mutation-restoration.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"exit_code": code, "files_restored_exactly": before == after}))
raise SystemExit(code or int(before != after))
