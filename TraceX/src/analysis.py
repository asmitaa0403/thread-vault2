from __future__ import annotations

from typing import List, Dict
import networkx as nx


def analyze_case_graph(G: nx.Graph) -> List[Dict]:
    """Compute centrality measures and influence score for nodes in G."""
    if G is None or len(G) == 0:
        return []

    # degree centrality (normalized)
    deg = nx.degree_centrality(G)
    # betweenness
    btw = nx.betweenness_centrality(G)
    # pagerank (works on undirected graphs)
    try:
        pr = nx.pagerank(G)
    except Exception:
        # Fallback: pure-Python power-iteration PageRank when optional
        # dependencies (scipy) are missing or pagerank raises.
        nodes = list(G.nodes())
        n = len(nodes)
        if n == 0:
            pr = {}
        else:
            # build outlink map (treat undirected edges as bidirectional)
            outlinks = {node: set() for node in nodes}
            for u, v in G.edges():
                outlinks[u].add(v)
                outlinks[v].add(u)

            # power iteration
            alpha = 0.85
            tol = 1.0e-6
            max_iter = 100
            pr = {node: 1.0 / n for node in nodes}
            for _ in range(max_iter):
                new_pr = {node: (1.0 - alpha) / n for node in nodes}
                # distribute ranks
                for node in nodes:
                    neighbors = outlinks.get(node, ())
                    if neighbors:
                        share = alpha * pr[node] / len(neighbors)
                        for nbr in neighbors:
                            new_pr[nbr] += share
                    else:
                        # dangling node: distribute uniformly
                        share = alpha * pr[node] / n
                        for nbr in nodes:
                            new_pr[nbr] += share
                # check convergence
                diff = sum(abs(new_pr[node] - pr[node]) for node in nodes)
                pr = new_pr
                if diff < tol:
                    break

    # Build ranking list
    rows = []
    for n in G.nodes():
        data = G.nodes[n]
        d = deg.get(n, 0.0)
        b = btw.get(n, 0.0)
        p = pr.get(n, 0.0)
        influence = 0.30 * d + 0.40 * b + 0.30 * p
        rows.append(
            {
                "canonical_id": n,
                "canonical_name": data.get("canonical_name"),
                "entity_type": data.get("entity_type"),
                "degree": d,
                "betweenness": b,
                "pagerank": p,
                "influence_score": influence,
            }
        )

    # sort descending
    rows.sort(key=lambda r: r["influence_score"], reverse=True)
    return rows
