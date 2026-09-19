"""Capture records through the native fixture script and public engine accessors."""
import contextlib
import importlib.util
import json
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
destination = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(root))
from kernel import Engine
captured = []
class CapturingEngine(Engine):
    def tick(self, proposals=()):
        record = super().tick(proposals)
        captured.append({"record": record.canonical(), "record_digest": record.digest(),
                         "state": self.state.canonical(), "state_digest": self.state.digest()})
        return record

spec = importlib.util.spec_from_file_location("native_fixtures", root / "evidence/stage-01/instrument/fixture_digests.py")
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
fixtures.Engine = CapturingEngine
destination.parent.mkdir(parents=True, exist_ok=True)
with destination.with_suffix(".txt").open("w", encoding="utf-8", newline="\n") as stream, contextlib.redirect_stdout(stream):
    code = fixtures.main()
destination.write_text(json.dumps(captured, sort_keys=True, indent=2) + "\n", encoding="utf-8")
raise SystemExit(code)

