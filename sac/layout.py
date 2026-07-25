"""Gramática de layout [windows] e plano de splits (v17).

Gramática v1 (flat): `;` separa colunas (split horizontal), `,` empilha
(split vertical). `,` liga mais forte que `;`. Percentuais proporcionais ao
número de folhas, aplicados ao espaço restante (mesma regra do CCB).
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import ConfigError


@dataclass
class Leaf:
    agent: str


@dataclass
class Row:
    """Split vertical — folhas empilhadas."""
    children: list[Node]


@dataclass
class Col:
    """Split horizontal — colunas lado a lado."""
    children: list[Node]


Node = Leaf | Row | Col


@dataclass
class SplitOp:
    agent: str
    direction: str  # "area" (split -h -f do sidebar) | "col" (split -h -f) | "row" (split -v)
    pct: int


@dataclass
class WindowPlan:
    name: str
    ops: list[SplitOp]


def parse_spec(spec: str) -> Node:
    cols = [c.strip() for c in spec.split(";")]
    if not spec.strip() or any(not c for c in cols):
        raise ConfigError(f"spec de layout inválido: {spec!r}")
    col_nodes: list[Node] = []
    for c in cols:
        rows = [r.strip() for r in c.split(",")]
        if any(not r for r in rows):
            raise ConfigError(f"spec de layout inválido: {spec!r}")
        leaves: list[Node] = [Leaf(r) for r in rows]
        col_nodes.append(leaves[0] if len(leaves) == 1 else Row(leaves))
    return col_nodes[0] if len(col_nodes) == 1 else Col(col_nodes)


def leaf_names(node: Node) -> list[str]:
    if isinstance(node, Leaf):
        return [node.agent]
    return [name for child in node.children for name in leaf_names(child)]


def _row_ops(leaves: list[str], first_direction: str, first_pct: int) -> list[SplitOp]:
    ops = [SplitOp(leaves[0], first_direction, first_pct)]
    remaining = len(leaves) - 1
    for leaf in leaves[1:]:
        ops.append(SplitOp(leaf, "row", round(remaining / (remaining + 1) * 100)))
        remaining -= 1
    return ops


def build_plan(windows: dict[str, str]) -> list[WindowPlan]:
    plans: list[WindowPlan] = []
    for name, spec in windows.items():
        node = parse_spec(spec)
        cols = node.children if isinstance(node, Col) else [node]
        weights = [len(leaf_names(c)) for c in cols]
        ops: list[SplitOp] = []
        for i, col in enumerate(cols):
            leaves = leaf_names(col)
            if i == 0:
                ops.extend(_row_ops(leaves, "area", 85))
            else:
                pct = round(sum(weights[i:]) / sum(weights[i - 1:]) * 100)
                ops.extend(_row_ops(leaves, "col", pct))
        plans.append(WindowPlan(name, ops))
    return plans
