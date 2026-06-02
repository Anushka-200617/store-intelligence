import json
lines = open('../data/events/STORE_BLR_002.jsonl').readlines()
print(f'Total lines: {len(lines)}')
first = json.loads(lines[0])
print(f'First event: store_id={first["store_id"]}, type={first["event_type"]}, is_staff={first["is_staff"]}')
entry_count = sum(1 for l in lines if json.loads(l)['event_type']=='ENTRY')
print(f'ENTRY events: {entry_count}')
