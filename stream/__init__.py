"""Record stream and viewer (slice 1c as re-scoped by OD-009, checkpoint 1).

One append-only file per run holds the genesis state, every tick record with
its committed state, and separate timing lines. The viewer renders from that
file only. Nothing here is imported by the kernel, and nothing here decides
anything: the stream is what the engine produced, written down.
"""
