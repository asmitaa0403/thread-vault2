import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.ingestion import get_available_cases
from src.anomaly import detect_patterns

for c in get_available_cases():
    pats = detect_patterns(c)
    print(c, len(pats))
    for p in pats:
        print(' -', p['pattern_type'], p.get('severity'), p.get('entities_involved'))
    print()
