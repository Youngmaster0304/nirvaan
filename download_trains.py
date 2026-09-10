import urllib.request, csv, io, json

url = 'https://raw.githubusercontent.com/ayushbarthwal/Railway-Management-System/main/Train_details_22122017.csv'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req, timeout=15)
content = resp.read().decode('utf-8')
reader = csv.DictReader(io.StringIO(content))
rows = list(reader)

# Group by train number
trains = {}
for r in rows:
    tno = r['Train No'].strip()
    if tno not in trains:
        trains[tno] = {
            'number': tno, 'name': r['Train Name'].strip(),
            'source': r['Source Station Name'].strip(),
            'dest': r['Destination Station Name'].strip(),
            'source_code': r['Source Station'].strip(),
            'dest_code': r['Destination Station'].strip(),
            'stops': []
        }
    trains[tno]['stops'].append({
        'seq': int(r['SEQ']) if r['SEQ'].strip().isdigit() else 0,
        'station': r['Station Name'].strip(),
        'code': r['Station Code'].strip(),
        'arrival': r['Arrival time'].strip(),
        'departure': r['Departure Time'].strip(),
        'distance': r['Distance'].strip()
    })

# Build unique trains
unique_trains = []
for tno, t in trains.items():
    stops = sorted(t['stops'], key=lambda x: x['seq'])
    max_dist = max([int(s['distance']) for s in stops if s['distance'].isdigit()] or [0])
    
    # Determine train type from name
    name_upper = t['name'].upper()
    if any(x in name_upper for x in ['RAJDHANI', 'SHATABDI', 'VANDE BHARAT', 'GATIMAAN']):
        train_type = 'express'
        is_vvip = 1
    elif any(x in name_upper for x in ['EXPRESS', 'SF', 'SUPERFAST', 'MAIL']):
        train_type = 'express'
        is_vvip = 0
    elif any(x in name_upper for x in ['PASS', 'PASSENGER', 'LOCAL', 'EMU', 'MEMU']):
        train_type = 'passenger'
        is_vvip = 0
    elif any(x in name_upper for x in ['FREIGHT', 'GOODS', 'CONTAINER', 'OIL', 'COAL']):
        train_type = 'goods'
        is_vvip = 0
    elif any(x in name_upper for x in ['SP', 'SPECIAL', 'HOLIDAY']):
        train_type = 'express'
        is_vvip = 0
    else:
        train_type = 'express'
        is_vvip = 0
    
    # Determine days (assume daily for most)
    days = '1,2,3,4,5,6,7'
    
    unique_trains.append({
        'number': t['number'], 'name': t['name'],
        'source': t['source'], 'dest': t['dest'],
        'source_code': t['source_code'], 'dest_code': t['dest_code'],
        'distance_km': max_dist, 'total_stops': len(stops),
        'train_type': train_type, 'is_vvip': is_vvip,
        'departure': stops[0]['departure'] if stops else '',
        'arrival': stops[-1]['arrival'] if stops else '',
        'days': days
    })

# Sort by distance, take top 300
unique_trains.sort(key=lambda x: x['distance_km'], reverse=True)
top300 = unique_trains[:300]

# Save
with open('C:/Users/Abhinav/sih-railways/real_trains.json', 'w') as f:
    json.dump(top300, f, indent=2)

print(f"Total unique trains: {len(unique_trains)}")
print(f"Saved top 300 longest trains")
print(f"\nTop 15 trains by distance:")
for t in top300[:15]:
    print(f"  {t['number']} {t['name']}: {t['source']} -> {t['dest']} ({t['distance_km']} km, {t['total_stops']} stops, {t['train_type']})")

# Also get unique stations
all_stations = set()
for t in unique_trains:
    all_stations.add(t['source'])
    all_stations.add(t['dest'])
print(f"\nUnique stations: {len(all_stations)}")
