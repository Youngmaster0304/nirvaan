import sqlite3, json, os, hashlib, random
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "railblock.db")
TRAINS_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "real_trains.json")

def hash_pw(p): return hashlib.sha256(p.encode()).hexdigest()

def get_zone(sn):
    sn = sn.upper()
    if any(x in sn for x in ['MUMBAI','THANE','KALYAN','VIRAR','DADAR','CHURCHGATE','CSMT','CST','LTT','BORIVALI','ANDHERI','PUNE','NAGPUR','BHUSAWAL','SOLAPUR']):
        return 1
    if any(x in sn for x in ['RAJKOT','AHMEDABAD','BHAVNAGAR','VADODARA','RATLAM','BHUJ']):
        return 2
    if any(x in sn for x in ['NEW DELHI','NDLS','DELHI','HAZRAT NIZAMUDDIN','NZM','OLD DELHI','DELHI CANTT','AMBALA','FIROZPUR','LUCKNOW','MORADABAD','BAREILLY','AGRA']):
        return 3
    if any(x in sn for x in ['HOWRAH','HWH','SEALDAH','SDAH','KOLKATA','MALDA','ASANSOL','CHANDRAPURA','DANBAD','PATNA','GAYA','MUGALSARAI','SAMBALPUR']):
        return 4
    if any(x in sn for x in ['CHENNAI','MAS','MS','MADURAI','TRICHY','COIMBATORE','PALAKKAD','ERNAKULAM','TRIVANDRUM','TVC','KANNIYAKUMARI']):
        return 5
    if any(x in sn for x in ['SECUNDERABAD','SC','HYDERABAD','GUNTAKAL','NANDED','VIJAYAWADA','GUNTUR','WARANGAL']):
        return 6
    if any(x in sn for x in ['PRAYAGRAJ','ALLAHABAD','JHANSI','KANPUR']):
        return 7
    if any(x in sn for x in ['JAIPUR','AJMER','JODHPUR','BIKANER']):
        return 8
    if any(x in sn for x in ['GUWAHATI','GHY','TINSUKIA','LUMDING','NEW JALPAIGURI','NJP']):
        return 9
    if any(x in sn for x in ['BHUBANESWAR','BBS','CUTTACK','WALTAIR','VISAKHAPATNAM','VSKP']):
        return 12
    if any(x in sn for x in ['BILASPUR','R','RAIPUR']):
        return 13
    if any(x in sn for x in ['BANGALORE','SBC','BNC','MYSORE','MYS','HUBLI','UBL']):
        return 14
    if any(x in sn for x in ['JABALPUR','BHOPAL','KOTA','HABIBGANJ']):
        return 15
    return random.randint(1,15)

def init():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    
    c.executescript("""
    DROP TABLE IF EXISTS audit_log; DROP TABLE IF EXISTS sessions; DROP TABLE IF EXISTS users;
    DROP TABLE IF EXISTS emergency_push; DROP TABLE IF EXISTS crew_duty; DROP TABLE IF EXISTS token_locks;
    DROP TABLE IF EXISTS ai_recommendations; DROP TABLE IF EXISTS blocks; DROP TABLE IF EXISTS defects;
    DROP TABLE IF EXISTS train_schedule; DROP TABLE IF EXISTS corridors; DROP TABLE IF EXISTS departments;
    DROP TABLE IF EXISTS divisions; DROP TABLE IF EXISTS zones; DROP TABLE IF EXISTS schema_version;
    """)
    
    c.executescript("""
    CREATE TABLE zones (id INTEGER PRIMARY KEY AUTOINCREMENT, zone_code TEXT UNIQUE, zone_name TEXT, hq_city TEXT, region TEXT);
    CREATE TABLE divisions (id INTEGER PRIMARY KEY AUTOINCREMENT, zone_id INTEGER, div_code TEXT UNIQUE, div_name TEXT, hq_city TEXT);
    CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password_hash TEXT, full_name TEXT,
        role TEXT DEFAULT 'viewer', zone_id INTEGER, division_id INTEGER, is_active INTEGER DEFAULT 1, created_at TIMESTAMP, last_login TIMESTAMP);
    CREATE TABLE sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, token TEXT UNIQUE, expires_at TIMESTAMP);
    CREATE TABLE departments (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, code TEXT UNIQUE, color TEXT);
    CREATE TABLE corridors (id INTEGER PRIMARY KEY AUTOINCREMENT, corridor_id TEXT UNIQUE, route_name TEXT, length_km REAL,
        zone_id INTEGER, division_id INTEGER, status TEXT DEFAULT 'active', single_line INTEGER DEFAULT 0);
    CREATE TABLE defects (id INTEGER PRIMARY KEY AUTOINCREMENT, defect_id TEXT UNIQUE, department_id INTEGER, zone_id INTEGER,
        division_id INTEGER, title TEXT, description TEXT, location TEXT, priority TEXT, maintenance_type TEXT DEFAULT 'fault',
        status TEXT DEFAULT 'pending', created_at TIMESTAMP);
    CREATE TABLE blocks (id INTEGER PRIMARY KEY AUTOINCREMENT, block_id TEXT UNIQUE, department_id INTEGER, corridor_id INTEGER,
        defect_id INTEGER, block_date DATE, start_time TIME, end_time TIME, block_type TEXT, maintenance_category TEXT DEFAULT 'routine',
        status TEXT, ai_score REAL DEFAULT 0, is_emergency INTEGER DEFAULT 0, vvip_priority INTEGER DEFAULT 0,
        zone_id INTEGER, division_id INTEGER, created_by INTEGER, approved_by INTEGER, created_at TIMESTAMP);
    CREATE TABLE train_schedule (id INTEGER PRIMARY KEY AUTOINCREMENT, train_number TEXT, train_name TEXT,
        origin TEXT, destination TEXT, departure_time TIME, arrival_time TIME,
        days_of_week TEXT, train_type TEXT, is_vvip INTEGER DEFAULT 0, zone_id INTEGER,
        origin_zone_id INTEGER, dest_zone_id INTEGER);
    CREATE TABLE ai_recommendations (id INTEGER PRIMARY KEY AUTOINCREMENT, recommendation_type TEXT, title TEXT,
        description TEXT, impact_score REAL, zone_id INTEGER, created_at TIMESTAMP);
    CREATE TABLE token_locks (id INTEGER PRIMARY KEY AUTOINCREMENT, corridor_id INTEGER, section_name TEXT,
        direction TEXT, token_number INTEGER DEFAULT 1, locked_by_train TEXT, lock_time TIMESTAMP, status TEXT);
    CREATE TABLE crew_duty (id INTEGER PRIMARY KEY AUTOINCREMENT, crew_id TEXT UNIQUE, crew_name TEXT, role TEXT,
        duty_start TIME, duty_end TIME, hours_worked REAL DEFAULT 0, max_hours REAL DEFAULT 10, status TEXT,
        current_train TEXT, section TEXT, zone_id INTEGER);
    CREATE TABLE emergency_push (id INTEGER PRIMARY KEY AUTOINCREMENT, train_number TEXT, train_name TEXT,
        delay_hours REAL, push_type TEXT, triggered_at TIMESTAMP, status TEXT, description TEXT, zone_id INTEGER);
    CREATE TABLE audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT, entity_type TEXT,
        entity_id TEXT, details TEXT, created_at TIMESTAMP);
    CREATE TABLE schema_version (version INTEGER DEFAULT 1);
    """)
    c.execute("INSERT INTO schema_version(version) VALUES(4)")

    # ZONES
    zones = [('CR','Central Railway','Mumbai','South'),('WR','Western Railway','Mumbai','West'),
        ('NR','Northern Railway','New Delhi','North'),('ER','Eastern Railway','Kolkata','East'),
        ('SR','Southern Railway','Chennai','South'),('SCR','South Central Railway','Secunderabad','South'),
        ('NCR','North Central Railway','Prayagraj','Central'),('NWR','North Western Railway','Jaipur','West'),
        ('NER','North Eastern Railway','Guwahati','East'),('NFR','Northeast Frontier Railway','Guwahati','East'),
        ('ECR','East Central Railway','Hajipur','East'),('ECoR','East Coast Railway','Bhubaneswar','East'),
        ('SECR','South East Central Railway','Bilaspur','Central'),('SWR','South Western Railway','Bangalore','South'),
        ('WCR','West Central Railway','Jabalpur','Central')]
    c.executemany("INSERT INTO zones(zone_code,zone_name,hq_city,region) VALUES(?,?,?,?)", zones)

    # DIVISIONS
    divs = [
        (1,'MCR','Mumbai CR','Mumbai CST'),(1,'PUNE','Pune','Pune'),(1,'NGP','Nagpur','Nagpur'),(1,'BSL','Bhusawal','Bhusawal'),(1,'SUR','Solapur','Solapur'),
        (2,'MWR','Mumbai WR','Mumbai Central'),(2,'RJT','Rajkot','Rajkot'),(2,'ADI','Ahmedabad','Ahmedabad'),(2,'BVC','Bhavnagar','Bhavnagar'),(2,'BRC','Vadodara','Vadodara'),
        (3,'NDLS','Delhi','New Delhi'),(3,'UMB','Ambala','Ambala'),(3,'FZR','Firozpur','Firozpur'),(3,'LKO','Lucknow NR','Lucknow'),(3,'MB','Moradabad','Moradabad'),
        (4,'HWH','Howrah','Howrah'),(4,'SDAH','Sealdah','Kolkata'),(4,'MLDT','Malda Town','Malda'),(4,'ASN','Asansol','Asansol'),
        (5,'MAS','Chennai','Chennai'),(5,'MDU','Madurai','Madurai'),(5,'TPJ','Trichy','Tiruchirappalli'),(5,'CBE','Coimbatore','Coimbatore'),
        (6,'SC','Secunderabad','Secunderabad'),(6,'HYB','Hyderabad','Hyderabad'),(6,'GTL','Guntakal','Guntakal'),(6,'NED','Nanded','Nanded'),(6,'BZA','Vijayawada','Vijayawada'),
        (7,'PRYJ','Prayagraj','Prayagraj'),(7,'JHS','Jhansi','Jhansi'),(7,'AGC','Agra','Agra'),
        (8,'JP','Jaipur','Jaipur'),(8,'AII','Ajmer','Ajmer'),(8,'JU','Jodhpur','Jodhpur'),(8,'BKN','Bikaner','Bikaner'),
        (9,'GHY','Guwahati','Guwahati'),(9,'NTSK','Tinsukia','Tinsukia'),
        (10,'NJP','New Jalpaiguri','New Jalpaiguri'),(10,'RNY','Rangia','Rangia'),
        (11,'DNR','Danapur','Patna'),(11,'DHN','Dhanbad','Dhanbad'),(11,'MGS','Mugalsarai','Mugalsarai'),(11,'SPJ','Samastipur','Samastipur'),
        (12,'BBS','Bhubaneswar','Bhubaneswar'),(12,'SBP','Sambalpur','Sambalpur'),(12,'VSKP','Waltair','Visakhapatnam'),
        (13,'BSP','Bilaspur','Bilaspur'),(13,'R','Raipur','Raipur'),
        (14,'SBC','Bangalore','Bangalore'),(14,'MYS','Mysore','Mysore'),(14,'UBL','Hubli','Hubli'),
        (15,'JBP','Jabalpur','Jabalpur'),(15,'BPL','Bhopal','Bhopal'),(15,'KOTA','Kota','Kota')
    ]
    c.executemany("INSERT INTO divisions(zone_id,div_code,div_name,hq_city) VALUES(?,?,?,?)", divs)

    # USERS
    c.execute("INSERT INTO users(username,password_hash,full_name,role,zone_id,division_id,created_at) VALUES(?,?,?,?,?,?,?)",
        ("admin",hash_pw("admin123"),"System Administrator","admin",1,1,datetime.now().isoformat()))
    c.execute("INSERT INTO users(username,password_hash,full_name,role,zone_id,division_id,created_at) VALUES(?,?,?,?,?,?,?)",
        ("controller",hash_pw("ctrl123"),"Section Controller","controller",1,1,datetime.now().isoformat()))
    c.execute("INSERT INTO users(username,password_hash,full_name,role,zone_id,division_id,created_at) VALUES(?,?,?,?,?,?,?)",
        ("engineer",hash_pw("eng123"),"Chief Engineer","engineer",2,6,datetime.now().isoformat()))

    # DEPARTMENTS
    for n,co,cl in [('Engineering','ENG','#3B82F6'),('Traction Distribution','TRD','#F59E0B'),('Signal & Telecom','SIG','#10B981'),
                     ('Mechanical','MCH','#8b5cf6'),('Electrical','ELC','#ec4899')]:
        c.execute("INSERT INTO departments(name,code,color) VALUES(?,?,?)",(n,co,cl))

    # CORRIDORS
    cors = [
        ('COR-001','Mumbai Central - Virar',120.5,1,1,0),('COR-002','Thane - Kalyan',28.3,1,1,0),
        ('COR-003','Dadar - Thane',32.1,1,1,0),('COR-004','Kalyan - Pune',95.0,1,1,1),
        ('COR-005','Borivali - Virar',45.2,1,1,0),('COR-006','Churchgate - Mumbai CST',12.8,1,1,0),
        ('COR-007','Dadar - Bandra',6.4,1,1,0),('COR-008','Andheri - Borivali',8.9,1,1,0),
        ('COR-009','New Delhi - Howrah',1445.0,3,14,1),('COR-010','Delhi - Mumbai Rajdhani',1384.0,3,14,1),
        ('COR-011','Mumbai - Chennai',1329.0,1,1,1),('COR-012','Chennai - Bangalore',346.0,5,21,0),
        ('COR-013','Howrah - Chennai',1663.0,4,17,1),('COR-014','Delhi - Kolkata',1445.0,3,14,1),
        ('COR-015','Bangalore - Hubli',410.0,14,50,0),('COR-016','Secunderabad - Vijayawada',353.0,6,27,0),
        ('COR-017','Ahmedabad - Mumbai',493.0,2,8,0),('COR-018','Jaipur - Delhi',308.0,8,33,0),
        ('COR-019','Bhopal - Jabalpur',202.0,15,53,0),('COR-020','Patna - Gaya',92.0,11,43,0),
        ('COR-021','Nagpur - Bilaspur',412.0,13,47,1),('COR-022','Guwahati - New Jalpaiguri',427.0,9,38,1),
        ('COR-023','Chennai - Madurai',461.0,5,22,0),('COR-024','Pune - Solapur',253.0,1,2,0),
        ('COR-025','Jhansi - Kanpur',122.0,7,31,1),('COR-026','Prayagraj - DD Upadhyaya',152.0,7,30,1),
        ('COR-027','Bhubaneswar - Sambalpur',342.0,12,45,0),('COR-028','Raipur - Bilaspur',160.0,13,48,0),
        ('COR-029','Kota - Ratlam',260.0,15,54,0),('COR-030','Lucknow - Gorakhpur',270.0,3,17,0),
        ('COR-031','Mysore - Bangalore',139.0,14,51,0),('COR-032','Vizag - Waltair',120.0,12,46,0),
    ]
    c.executemany("INSERT INTO corridors(corridor_id,route_name,length_km,zone_id,division_id,single_line) VALUES(?,?,?,?,?,?)", cors)

    # DEFECTS
    defs = [
        ('DEF-001',1,1,1,'Rail Wear Exceeding Limit','Rail head wear near Thane exceeds 6mm','Track 2, Km 124','critical','fault'),
        ('DEF-002',2,1,1,'OHE Wire Sagging','Overhead equipment wire sag near Kalyan','OHE Km 89','critical','fault'),
        ('DEF-003',3,1,1,'Signal Light Failure','Home signal intermittent red','Signal TH-12','high','fault'),
        ('DEF-004',1,3,11,'Point Machine Misalignment','Point 5 alignment error','Delhi Junction','high','fault'),
        ('DEF-005',2,5,21,'Feeder Trip Issue','Recurrent tripping Feeder 4','Chennai Feeder','medium','routine'),
        ('DEF-006',3,4,16,'Track Circuit Faulty','False occupied status','Howrah Circuit','high','fault'),
        ('DEF-007',1,8,33,'Ballast Deficiency','Below required level','Jaipur Section','low','routine'),
        ('DEF-008',2,6,25,'Insulator Contamination','Porcelain insulators contaminated','Secunderabad','medium','routine'),
        ('DEF-009',3,11,43,'Bonding Wire Damage','Rail bonding wire damaged','Patna Crossing','low','routine'),
        ('DEF-010',1,14,50,'Sleeper Damage','Concrete sleepers cracked','Bangalore Track','high','fault'),
        ('DEF-011',1,7,30,'Emergency Rail Fracture','Rail fracture detected near Prayagraj','Prayagraj Track','critical','urgent'),
        ('DEF-012',2,12,45,'OHE Catenary Snap Risk','Catenary 40% tensile reduction','Bhubaneswar OHE','critical','urgent'),
    ]
    c.executemany("INSERT INTO defects(defect_id,department_id,zone_id,division_id,title,description,location,priority,maintenance_type) VALUES(?,?,?,?,?,?,?,?,?)", defs)

    # TRAINS from real data
    with open(TRAINS_JSON) as f:
        real_trains = json.load(f)
    
    print(f"Loading {len(real_trains)} real trains...")
    for t in real_trains:
        origin_zone = get_zone(t['source'])
        dest_zone = get_zone(t['dest'])
        c.execute("""INSERT INTO train_schedule(train_number,train_name,origin,destination,departure_time,arrival_time,
            days_of_week,train_type,is_vvip,zone_id,origin_zone_id,dest_zone_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (t['number'],t['name'],t['source'],t['dest'],t['departure'],t['arrival'],
             t['days'],t['train_type'],t['is_vvip'],origin_zone,origin_zone,dest_zone))
    print(f"Inserted {len(real_trains)} trains")

    # RECOMMENDATIONS
    for typ,title,desc,score in [
        ('merge','Combine Engineering Blocks in Mumbai Suburban','Save 4.5 hours by merging adjacent blocks',85),
        ('reschedule','Move OHE to Night Window','Zero train impact with 01:00-04:00 slot',92),
        ('prioritize','Emergency Rail Fracture DEF-011','Immediate block allocation required',98),
        ('optimize','Weekend Mega Block','Major renewal during low-traffic window',88),
        ('vvip','Rajdhani Protection Protocol','Auto-protect through all maintenance corridors',95),
        ('hoger','Crew Duty Compliance Alert','Reassign approaching 10-hour limit crew',90),
    ]:
        c.execute("INSERT INTO ai_recommendations(recommendation_type,title,description,impact_score) VALUES(?,?,?,?)",(typ,title,desc,score+random.uniform(-3,3)))

    # BLOCKS
    today = datetime.now().date()
    for i in range(60):
        bd = today + timedelta(days=random.randint(0,13))
        dept = random.randint(1,3); zone = random.randint(1,15); div = random.randint(1,54)
        h = random.choice([0,1,2,3,22,23]); m = random.choice([0,30]); eh = (h+random.randint(2,4))%24
        cat = random.choice(['routine','routine','fault','urgent']) if i < 5 else 'routine'
        st = random.choice(['planned','approved','in_progress','completed'])
        c.execute("INSERT INTO blocks(block_id,department_id,corridor_id,block_date,start_time,end_time,block_type,maintenance_category,status,ai_score,is_emergency,zone_id,division_id,created_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f'BLK-{1000+i}',dept,random.randint(1,32),bd.isoformat(),f'{h:02d}:{m:02d}',f'{eh:02d}:{m:02d}',
             random.choice(['Track Renewal','OHE Replacement','Signal Maintenance','Point Machine','Rail Grinding']),
             cat,st,random.uniform(50,98),1 if cat=='urgent' else 0,zone,div,1))

    # TOKEN LOCKS
    for ci,sn in [(4,'Kalyan-Pune'),(9,'Delhi-Howrah'),(25,'Jhansi-Kanpur'),(26,'Prayagraj-DDU')]:
        for d in ['UP','DOWN']:
            lb = '12951' if ci==26 and d=='UP' else None
            c.execute("INSERT INTO token_locks(corridor_id,section_name,direction,token_number,locked_by_train,lock_time,status) VALUES(?,?,?,?,?,?,?)",
                (ci,sn,d,1,lb,datetime.now().isoformat() if lb else None,'locked' if lb else 'available'))

    # CREW
    crew = [
        ('LP-2847','Rajesh Kumar','loco_pilot','06:00','15:30',9.5,10,'on_duty','12951','Mumbai-Delhi',1),
        ('LP-3102','Suresh Singh','loco_pilot','08:00','18:00',10.0,10,'violation','95104','Virar-Churchgate',1),
        ('LP-4521','Manoj Tiwari','loco_pilot','22:00','08:00',10.0,10,'on_duty','12951','Mumbai Rajdhani',1),
        ('LP-5567','Anil Gupta','loco_pilot','14:00','00:00',10.0,10,'rest',None,None,1),
        ('LP-6234','Vikram Singh','loco_pilot','05:00','15:00',9.2,10,'on_duty','12301','Howrah Rajdhani',4),
        ('LP-7891','Pradeep Das','loco_pilot','20:00','06:00',8.5,10,'on_duty','12615','Grand Trunk',5),
        ('LP-8123','Ravi Shankar','loco_pilot','06:00','16:00',9.8,10,'on_duty','22691','Rajdhani Exp',3),
        ('AP-1156','Amit Verma','assistant_pilot','06:00','15:30',9.5,10,'on_duty','12951','Mumbai Rajdhani',1),
        ('GD-0834','Prakash Yadav','guard','05:30','14:30',9.0,10,'on_duty','95101','Churchgate-Virar',1),
        ('CT-0198','Vikram Joshi','controller','06:00','14:00',8.0,10,'on_duty',None,'Mumbai Control',1),
        ('CT-0245','Arun Kumar','controller','14:00','22:00',7.5,10,'on_duty',None,'Delhi Control',3),
    ]
    c.executemany("INSERT INTO crew_duty(crew_id,crew_name,role,duty_start,duty_end,hours_worked,max_hours,status,current_train,section,zone_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)", crew)

    # EMERGENCIES
    for tn,nn,dh,pt,ds,desc,zi in [
        ('95104','Local Fast',11.5,'critical_push','completed','Train delayed 11.5h, critical push triggered',1),
        ('12951','Mumbai Rajdhani',2.0,'vvip_protect','active','Rajdhani approaching maintenance corridor',1),
        ('G-103','Coal Freight',14.0,'rescue','active','Coal train stranded, rescue locomotive dispatched',12),
        ('12301','Howrah Rajdhani',1.5,'vvip_protect','active','Rajdhani protected through work zone',4),
    ]:
        c.execute("INSERT INTO emergency_push(train_number,train_name,delay_hours,push_type,status,description,zone_id) VALUES(?,?,?,?,?,?,?)",(tn,nn,dh,pt,ds,desc,zi))

    conn.commit(); conn.close()
    print("Database seeded successfully!")

if __name__ == "__main__":
    init()
