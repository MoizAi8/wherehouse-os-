import sys
sys.path.insert(0, 'src')
from fulfillment.api.chat import detect_intent

tests = [
    ('kitne orders hain aur status breakdown do', 'metrics'),
    ('konse orders abhi tak fulfillment center assign nahi huay', 'fulfillment_centers'),
    ('jin orders ka fulfillment center assign ho chuka hai unko konsa carrier diya gaya', 'fulfillment_centers'),
    ('kitne active shipments hain aur unka status kya hai', 'active_shipments'),
    ('konse shipments delayed hain delay ki wajah kya hai', 'delayed_shipments'),
    ('sabse purana pending order konsa hai jo abhi tak process nahi hua', 'oldest_pending'),
    ('konse orders high risk hain', 'high_risk_shipments'),
    ('sabse zyada risk wala shipment konsa hai aur risk probability kitni hai', 'high_risk_shipments'),
    ('aaj tak kitne shipments reroute ho chuke hain', 'reroute_list'),
    ('reroute hone wale shipments ka original aur naya carrier batao', 'reroute_list'),
    ('average shipping cost kitna hai', 'cost_analysis'),
    ('sabse mehnga aur sabse sasta shipment konsa hai', 'cost_analysis'),
    ('ab tak kitne customers ko alerts bheje gaye hain', 'notification_stats'),
    ('kitne alerts successfully deliver huay aur kitne fail huay', 'notification_stats'),
    ('sab agents ka current health status kya hai', 'agent_count'),
    ('last workflow cycle kab chala tha aur usmein kya process hua', 'cycle_stats'),
]

all_ok = True
for msg, expected in tests:
    result = detect_intent(msg)
    status = 'OK' if result == expected else f'WRONG (got {result})'
    if result != expected:
        all_ok = False
        print(f'FAIL: "{msg}" -> {status}')
    else:
        print(f'OK: "{msg}" -> {result}')

print(f'\nALL PASSED: {all_ok}')
