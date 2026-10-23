import sys, os
sys.path.insert(0, os.path.abspath('.'))
from src.visualization import create_network_html
from src.audit import append_audit_event, verify_audit_chain, get_audit_log
from src.ingestion import get_available_cases

cases = get_available_cases()
print('cases:', cases)
html = create_network_html('CG-2026-001')
print('html_len=', len(html))
r = append_audit_event('test_event', 'CG-2026-001', 'DemoAgent', {'note':'phase4 smoke'})
print('audit_record_id_hash=', r.get('current_hash')[:8])
print('verify=', verify_audit_chain())
print('recent_logs=', len(get_audit_log(5)))
