import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.ingestion import get_available_cases
from src.graph import build_case_graph
from src.analysis import analyze_case_graph
from src.explainability import explain_patterns, get_investigation_timeline

cases = get_available_cases()
results = {}
for c in cases:
    G = build_case_graph(c)
    ranking = analyze_case_graph(G)
    patterns = explain_patterns(c)
    timeline = get_investigation_timeline(c)
    results[c] = {
        'nodes': G.number_of_nodes(),
        'edges': G.number_of_edges(),
        'top_influencer': ranking[0]['canonical_name'] if ranking else None,
        'patterns': len(patterns),
        'timeline_events': len(timeline),
    }
print(results)
