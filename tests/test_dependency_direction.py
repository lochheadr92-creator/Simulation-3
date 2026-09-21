"""A9 - module dependency direction, required by doctrine principle 9.

State, proposal shape, ordering, resolution, evidence and diagnostics are
separate responsibilities, and the import graph has to say so. In particular
settlement must not be able to see the diagnostics channel at all, which is what
makes optional capture structurally unable to influence a decision.
"""

from __future__ import annotations

import ast
import pathlib

KERNEL = pathlib.Path(__file__).resolve().parent.parent / "kernel"

ALLOWED = {
    "version": set(),
    "canonical": set(),
    "reasons": set(),
    "units": set(),
    "ordering": set(),
    "diagnostics": {"canonical"},
    "state": {"version", "canonical", "units"},
    "proposals": {"units", "reasons", "state"},
    "outcomes": {"version", "canonical", "reasons", "state"},
    "settlement": {"units", "reasons", "ordering", "state", "proposals", "outcomes", "canonical"},
    "engine": {"version", "canonical", "state", "proposals", "outcomes", "settlement", "diagnostics"},
}


def kernel_imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("kernel"):
            parts = node.module.split(".")
            if len(parts) > 1:
                found.add(parts[1])
            else:
                found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == "kernel" and len(parts) > 1:
                    found.add(parts[1])
    return found


def module_paths() -> dict[str, pathlib.Path]:
    return {
        path.stem: path
        for path in sorted(KERNEL.glob("*.py"))
        if path.stem != "__init__"
    }


def test_every_kernel_module_has_a_declared_layer():
    assert set(module_paths()) == set(ALLOWED)


def test_no_module_imports_above_its_layer():
    offences = []
    for name, path in module_paths().items():
        forbidden = kernel_imports(path) - ALLOWED[name] - {name}
        if forbidden:
            offences.append((name, sorted(forbidden)))
    assert offences == []


def test_settlement_cannot_see_the_diagnostics_channel():
    assert "diagnostics" not in kernel_imports(module_paths()["settlement"])


def test_nothing_inside_the_kernel_imports_the_engine():
    importers = [
        name
        for name, path in module_paths().items()
        if name != "engine" and "engine" in kernel_imports(path)
    ]
    assert importers == []


def test_state_does_not_import_resolution_or_evidence():
    seen = kernel_imports(module_paths()["state"])
    assert not seen & {"settlement", "engine", "outcomes", "proposals"}


def test_the_declared_layering_is_acyclic():
    visiting: set[str] = set()
    done: set[str] = set()

    def walk(name: str, trail: tuple[str, ...]) -> None:
        if name in done:
            return
        assert name not in visiting, f"import cycle: {' -> '.join(trail + (name,))}"
        visiting.add(name)
        for dependency in sorted(ALLOWED[name]):
            walk(dependency, trail + (name,))
        visiting.discard(name)
        done.add(name)

    for module in sorted(ALLOWED):
        walk(module, ())
