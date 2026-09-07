"""Bounded orthogonal routing with electrically separate wire crossings."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import networkx as nx

Point = tuple[float, float]


@dataclass(frozen=True)
class Wire:
    net: str
    start: Point
    end: Point


def route_nets(
    terminals: dict[str, list[Point]],
    rectangles: list[tuple[float, float, float, float]],
    *,
    clearance: float = 2.54,
) -> tuple[list[Wire], set[Point]]:
    if not terminals:
        return [], set()
    rectangles = [tuple(round(value, 6) for value in box) for box in rectangles]
    points = [point for values in terminals.values() for point in values]
    xs = {round(point[0], 6) for point in points}
    ys = {round(point[1], 6) for point in points}
    for left, top, right, bottom in rectangles:
        xs.update(round(v, 6) for v in (left - clearance, left, right, right + clearance))
        ys.update(round(v, 6) for v in (top - clearance, top, bottom, bottom + clearance))
    xs.update((round(min(xs) - 2 * clearance, 6), round(max(xs) + 2 * clearance, 6)))
    ys.update((round(min(ys) - 2 * clearance, 6), round(max(ys) + 2 * clearance, 6)))
    x_values, y_values = sorted(xs), sorted(ys)
    if len(xs) * len(ys) > 50000:
        raise ValueError("Routing grid exceeds 50000 points; simplify the placement.")
    coordinates = {
        (x, y): (xx, yy) for x, xx in enumerate(x_values) for y, yy in enumerate(y_values)
    }
    lookup = {point: index for index, point in coordinates.items()}
    occupied: dict[tuple[int, int, str], str] = {}
    for net, pins in terminals.items():
        for point in pins:
            index = lookup[(round(point[0], 6), round(point[1], 6))]
            for direction in ("H", "V", "P"):
                node = (*index, direction)
                if node in occupied and occupied[node] != net:
                    raise ValueError("Pins from different nets overlap.")
                occupied[node] = net
    graph = nx.Graph()
    for (x, y), point in coordinates.items():
        if any(
            left < point[0] < right and top < point[1] < bottom
            for left, top, right, bottom in rectangles
        ):
            continue
        graph.add_edge((x, y, "H"), (x, y, "V"), weight=0.1 * clearance)
        if (x, y, "P") in occupied:
            graph.add_edge((x, y, "P"), (x, y, "H"), weight=0)
            graph.add_edge((x, y, "P"), (x, y, "V"), weight=0)
    for (x, y), point in coordinates.items():
        for neighbor, direction in (((x + 1, y), "H"), ((x, y + 1), "V")):
            start, end = (x, y, direction), (*neighbor, direction)
            if start not in graph or end not in graph:
                continue
            other = coordinates[neighbor]
            obstructed = any(
                (
                    direction == "H"
                    and top < point[1] < bottom
                    and point[0] < right
                    and other[0] > left
                )
                or (
                    direction == "V"
                    and left < point[0] < right
                    and point[1] < bottom
                    and other[1] > top
                )
                for left, top, right, bottom in rectangles
            )
            if not obstructed:
                graph.add_edge(
                    start, end, weight=abs(point[0] - other[0]) + abs(point[1] - other[1])
                )
    wires: list[Wire] = []
    junctions: set[Point] = set()

    def priority(item: tuple[str, list[Point]]) -> tuple[int, float]:
        pins = item[1]
        return -len(pins), (
            max(p[0] for p in pins)
            - min(p[0] for p in pins)
            + max(p[1] for p in pins)
            - min(p[1] for p in pins)
        )

    for net, pins in sorted(terminals.items(), key=priority):
        nodes = list(dict.fromkeys((*lookup[(round(p[0], 6), round(p[1], 6))], "P") for p in pins))
        if len(nodes) < 2:
            continue
        tree = {nodes[0]}
        edges: set[tuple[Point, Point]] = set()
        for target in nodes[1:]:
            view = nx.subgraph_view(
                graph, filter_node=lambda node, owner=net: occupied.get(node, owner) == owner
            )
            try:
                _, path = nx.multi_source_dijkstra(view, tree, target, weight="weight")
            except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
                raise ValueError(f"Cannot route net {net}; increase component spacing.") from exc
            for node in path:
                occupied[node] = net
            tree.update(path)
            for a, b in zip(path, path[1:], strict=False):
                pa, pb = coordinates[a[:2]], coordinates[b[:2]]
                if pa != pb:
                    edges.add(tuple(sorted((pa, pb))))
        adjacency: dict[Point, set[Point]] = defaultdict(set)
        for a, b in edges:
            adjacency[a].add(b)
            adjacency[b].add(a)
        stops = set(pins)
        for point, neighbors in adjacency.items():
            if len(neighbors) != 2:
                stops.add(point)
            else:
                a, b = tuple(neighbors)
                if a[0] != b[0] and a[1] != b[1]:
                    stops.add(point)
            if len(neighbors) > 2:
                junctions.add(point)
        seen: set[tuple[Point, Point]] = set()
        for start in sorted(stops):
            for neighbor in sorted(adjacency.get(start, ())):
                if tuple(sorted((start, neighbor))) in seen:
                    continue
                previous, current = start, neighbor
                seen.add(tuple(sorted((previous, current))))
                while current not in stops:
                    following = next(point for point in adjacency[current] if point != previous)
                    previous, current = current, following
                    seen.add(tuple(sorted((previous, current))))
                wires.append(Wire(net, start, current))
    return wires, junctions
