"""Declared code and schema identities.

These are carried in every tick record and in every state identity, so a change
to either is visible in the canonical results rather than silently changing what
an old digest means.
"""

from __future__ import annotations

ENGINE_VERSION = "0.2.0-stage1b"
SCHEMA_VERSION = "v3.kernel.1b.1"
