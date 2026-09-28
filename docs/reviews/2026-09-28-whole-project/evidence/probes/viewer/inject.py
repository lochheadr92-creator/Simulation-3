"""Rename an actor and the run_id to HTML/JS payloads inside a Run object, render, and inspect."""
import json, sys, re
from dataclasses import replace
from pathlib import Path
from stream.run_file import read_run
from world.viewer import render_html, render_text

SRC = Path(sys.argv[1]); OUT = Path(sys.argv[2])
run = read_run(SRC)
victim = sorted(run.header["world"]["positions"])[0]
EVIL = '</script><script>window.__pwned=1</script><img src=x onerror="window.__pwned=2">"onmouseover="window.__pwned=3'
EVIL_ID = 'X"><img src=x onerror="window.__pwned=9">'   # run_id / source id payload

def deep(o):
    if isinstance(o, dict):
        return {deep(k): deep(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return type(o)(deep(x) for x in o)
    if isinstance(o, str):
        if o == victim:
            return EVIL
        return o.replace(victim, EVIL) if victim in o else o
    return o

header = deep(run.header)
header["run_id"] = EVIL_ID
header["scenario"]["name"] = EVIL_ID          # scenario name shows in the deep meta line
header["scenario"]["seed"] = EVIL_ID          # seed chip
ticks = tuple(deep(t) for t in run.ticks)
# make the victim die at the last tick so the deaths list in the deep totals is exercised
last = dict(ticks[-1]); w = dict(last["world"]); w["died_at"] = dict(w.get("died_at", {})); w["died_at"][EVIL] = last["tick"]; last["world"] = w
ticks = ticks[:-1] + (last,)
# a decision reason with a payload, on some actor in tick 1
t1 = dict(ticks[0]); decs = dict(t1["decisions"])
if decs:
    a = sorted(decs)[0]; d = dict(decs[a]); d["reason"] = EVIL + " REASON"; decs[a] = d; t1["decisions"] = decs
ticks = (t1,) + ticks[1:]
mut = replace(run, header=header, ticks=ticks)
html = render_html(mut)
OUT.write_text(html, encoding="utf-8")
print("wrote", OUT, len(html))
# Static checks: any raw '<script' inside the JSON blobs? any raw EVIL outside escaped contexts?
blobs = re.findall(r'<script id="(run-data|view-index)" type="application/json">(.*?)</script>', html, re.S)
for name, blob in blobs:
    print(name, "raw '<' in JSON blob:", "<" in blob, "| '</script' present:", "</script" in blob.lower())
print("raw EVIL occurrences in whole page:", html.count(EVIL), "| raw EVIL_ID:", html.count(EVIL_ID))
print("--- text render view 1 first lines")
print("\n".join(render_text(mut, 1).splitlines()[:3]))
