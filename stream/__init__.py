"""Record stream, sealed evidence, replay, recovery and viewer.

One append-only file per run holds the genesis state, every tick record with
its committed state and the proposals submitted, and separate timing lines.
Since slice 1c the file is sealed (v3.stream.3): replay checks it against the
engine, and recovery continues a cut file from its last sealed tick. The
viewer renders from the file only. Nothing here is imported by the kernel,
and nothing here decides anything: the stream is what the engine produced,
written down.
"""
