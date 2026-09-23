"""Slice 1c, declaration item 11: recorded reference results stay byte-identical.

The recorded 1b fixture output is the before-capture of kernel canonical bytes:
its state and record digests are sha256 over them, so an unchanged output means
unchanged canonical forms. The head-b305783 world decisions fixture is checked
by test_perception.py and test_yield.py. Nothing here is regenerated.
"""

from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def normalised(text: str) -> str:
    return text.replace("\r\n", "\n").strip()


def test_fixture_digests_reproduce_the_recorded_1b_output(capsys):
    namespace = runpy.run_path(str(ROOT / "evidence" / "stage-01" / "instrument" / "fixture_digests.py"))
    assert namespace["main"]() == 0
    produced = capsys.readouterr().out
    recorded = (ROOT / "evidence" / "stage-01" / "slice-1b" / "fixtures-stage1b.txt").read_text(encoding="utf-8")
    assert normalised(produced) == normalised(recorded)
