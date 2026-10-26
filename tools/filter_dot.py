#!/usr/bin/env python3
"""Reduce un grafo DOT de BitBake a las dependencias de las recetas de interés.

    filter_dot.py task-depends.dot --roots edgeai-helpdesk ollama-bin --depth 1 --tasks
    filter_dot.py buildhistory/.../depends.dot --roots edgeai-helpdesk --depth 2

--tasks: los nodos son tareas ("receta.do_tarea"); se colapsan a nivel de receta.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict, deque

EDGE = re.compile(r'^\s*"([^"]+)"\s*->\s*"([^"]+)"(.*)$')


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("dot")
    p.add_argument("--roots", nargs="+", required=True)
    p.add_argument("--depth", type=int, default=1)
    p.add_argument("--tasks", action="store_true", help="colapsar receta.do_tarea a receta")
    a = p.parse_args()

    graph: dict[str, set[str]] = defaultdict(set)
    styles: dict[tuple[str, str], str] = {}
    with open(a.dot, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = EDGE.match(line)
            if not m:
                continue
            src, dst, rest = m.groups()
            if a.tasks:
                src, dst = src.rsplit(".", 1)[0], dst.rsplit(".", 1)[0]
            if src == dst or dst.endswith("-native") and src not in a.roots:
                continue
            graph[src].add(dst)
            if "dotted" in rest:
                styles[(src, dst)] = "dotted"

    keep: set[tuple[str, str]] = set()
    seen = set(a.roots)
    queue = deque((r, 0) for r in a.roots if r in graph)
    while queue:
        node, depth = queue.popleft()
        if depth >= a.depth:
            continue
        for dst in sorted(graph[node]):
            keep.add((node, dst))
            if dst not in seen:
                seen.add(dst)
                queue.append((dst, depth + 1))

    print("digraph edgeai {")
    print('  rankdir=LR; node [shape=box, fontname="Helvetica", fontsize=10];')
    for r in a.roots:
        print(f'  "{r}" [style=filled, fillcolor="#cfe8e3"];')
    for src, dst in sorted(keep):
        style = ' [style=dotted]' if styles.get((src, dst)) == "dotted" else ""
        print(f'  "{src}" -> "{dst}"{style};')
    print("}")
    print(f"{len(keep)} aristas", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
