import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import random
import math

app = FastAPI(title="RailBlock AI API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "railblock.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Check if already seeded
    version_table = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'").fetchone()
    if not version_table:
        c.execute("CREATE TABLE schema_version (version INTEGER DEFAULT 1)")
        c.execute("INSERT INTO schema_version (version) VALUES (1)")
    else:
        v = c.execute("SELECT version FROM schema_version").fetchone()
        if v and v[0] >= 2:
            conn.commit()
            conn.close()
            return
    
    c.executescript("""
    CREATE TABLE IF NOT EXISTS departments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        code TEXT UNIQUE NOT NULL,
        color TEXT NOT NULL
    );
    
    CREATE TABLE IF NOT EXISTS corridors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        corridor_id TEXT UNIQUE NOT NULL,
        route_name TEXT NOT NULL,
        length_km REAL NOT NULL,
        status TEXT DEFAULT 'active',
        single_line_section INTEGER DEFAULT 0
    );
    
    CREATE TABLE IF NOT EXISTS defects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        defect_id TEXT UNIQUE NOT NULL,
        department_id INTEGER,
        title TEXT NOT NULL,
        description TEXT,
        location TEXT,
        priority TEXT CHECK(priority IN ('critical', 'high', 'medium', 'low')),
        maintenance_type TEXT DEFAULT 'fault',
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (department_id) REFERENCES departments(id)
    );
    
    CREATE TABLE IF NOT EXISTS blocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        block_id TEXT UNIQUE NOT NULL,
        department_id INTEGER,
        corridor_id INTEGER,
        defect_id INTEGER,
        block_date DATE NOT NULL,
        start_time TIME NOT NULL,
        end_time TIME NOT NULL,
        block_type TEXT NOT NULL,
        maintenance_category TEXT DEFAULT 'routine',
        status TEXT CHECK(status IN ('planned', 'approved', 'in_progress', 'completed', 'cancelled')),
        ai_score REAL DEFAULT 0,
        is_emergency INTEGER DEFAULT 0,
        vvip_priority INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (department_id) REFERENCES departments(id),
        FOREIGN KEY (corridor_id) REFERENCES corridors(id),
        FOREIGN KEY (defect_id) REFERENCES defects(id)
    );
    
    CREATE TABLE IF NOT EXISTS train_schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        train_number TEXT NOT NULL,
        train_name TEXT NOT NULL,
        origin TEXT NOT NULL,
        destination TEXT NOT NULL,
        departure_time TIME,
        arrival_time TIME,
        days_of_week TEXT,
        train_type TEXT CHECK(train_type IN ('passenger', 'express', 'goods', 'maintenance', 'vvip')),
        is_vvip INTEGER DEFAULT 0
    );
    
    CREATE TABLE IF NOT EXISTS ai_recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recommendation_type TEXT,
        title TEXT NOT NULL,
        description TEXT,
        impact_score REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS token_locks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        corridor_id INTEGER,
        section_name TEXT NOT NULL,
        direction TEXT CHECK(direction IN ('UP', 'DOWN')),
        token_number INTEGER DEFAULT 1,
        locked_by_train TEXT,
        lock_time TIMESTAMP,
        status TEXT CHECK(status IN ('available', 'locked', 'released')),
        FOREIGN KEY (corridor_id) REFERENCES corridors(id)
    );
    
    CREATE TABLE IF NOT EXISTS crew_duty (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        crew_id TEXT UNIQUE NOT NULL,
        crew_name TEXT NOT NULL,
        role TEXT CHECK(role IN ('loco_pilot', 'assistant_pilot', 'guard', 'controller')),
        duty_start TIME NOT NULL,
        duty_end TIME NOT NULL,
        hours_worked REAL DEFAULT 0,
        max_hours REAL DEFAULT 10,
        status TEXT CHECK(status IN ('on_duty', 'off_duty', 'rest', 'violation')),
        current_train TEXT,
        section TEXT
    );
    
    CREATE TABLE IF NOT EXISTS emergency_push (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        train_number TEXT NOT NULL,
        train_name TEXT NOT NULL,
        delay_hours REAL NOT NULL,
        push_type TEXT CHECK(push_type IN ('vvip_protect', 'critical_push', 'rescue')),
        triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT CHECK(status IN ('active', 'completed', 'cancelled')),
        description TEXT
    );
    """)
    
    # Seed departments
    departments = [
        ('Engineering', 'ENG', '#3B82F6'),
        ('Traction Distribution', 'TRD', '#F59E0B'),
        ('Signal & Telecom', 'SIG', '#10B981'),
    ]
    c.executemany("INSERT OR IGNORE INTO departments (name, code, color) VALUES (?, ?, ?)", departments)
    
    # Seed corridors with single line sections
    corridors = [
        ('COR-001', 'Mumbai Central - Virar', 120.5, 0),
        ('COR-002', 'Thane - Kalyan', 28.3, 0),
        ('COR-003', 'Dadar - Thane', 32.1, 0),
        ('COR-004', 'Kalyan - Pune', 95.0, 1),
        ('COR-005', 'Borivali - Virar', 45.2, 0),
        ('COR-006', 'Churchgate - Mumbai CST', 12.8, 0),
        ('COR-007', 'Dadar - Bandra', 6.4, 0),
        ('COR-008', 'Andheri - Borivali', 8.9, 0),
        ('COR-009', 'Prayagraj - DD Upadhyaya', 152.0, 1),
        ('COR-010', 'Jhansi - Kanpur', 122.0, 1),
    ]
    c.executemany("INSERT OR IGNORE INTO corridors (corridor_id, route_name, length_km, single_line_section) VALUES (?, ?, ?, ?)", corridors)
    
    # Seed defects with maintenance types
    defects = [
        ('DEF-001', 1, 'Rail Wear Exceeding Limit', 'Rail head wear on Track 2 near Thane exceeds 6mm limit', 'Track 2, Km 124+300', 'critical', 'fault'),
        ('DEF-002', 2, 'OHE Wire Sagging', 'Overhead equipment wire sag near Kalyan junction', 'OHE Line 3, Km 89+150', 'critical', 'fault'),
        ('DEF-003', 3, 'Signal Light Failure', 'Home signal at Thane showing intermittent red', 'Signal TH-12', 'high', 'fault'),
        ('DEF-004', 1, 'Point Machine Misalignment', 'Point machine No. 5 at Dadar showing alignment error', 'Point 5, Dadar', 'high', 'fault'),
        ('DEF-005', 2, 'Feeder Trip Issue', 'Recurrent tripping at Feeder Station 4', 'Feeder 4, Km 56+200', 'medium', 'routine'),
        ('DEF-006', 3, 'Track Circuit Faulty', 'Track circuit T-8 showing false occupied status', 'Track Circuit T-8, Virar', 'high', 'fault'),
        ('DEF-007', 1, 'Ballast Deficiency', 'Ballast depth below required level', 'Track 1, Km 34+500', 'low', 'routine'),
        ('DEF-008', 2, 'Insulator Contamination', 'Porcelain insulators near Virar depot contaminated', 'OHE Km 112+800', 'medium', 'routine'),
        ('DEF-009', 3, 'Bonding Wire Damage', 'Rail bonding wire damaged at crossing section', 'Crossing Km 78+400', 'low', 'routine'),
        ('DEF-010', 1, 'Sleeper Damage', 'Concrete sleepers cracked in section Km 67', 'Track 1, Km 67+200', 'high', 'fault'),
        ('DEF-011', 1, 'Emergency Rail Fracture', 'Rail fracture detected by ultrasonic inspection car near Prayagraj', 'Track 1, Km 847+200', 'critical', 'urgent'),
        ('DEF-012', 2, 'OHE Catenary Snap Risk', 'Catenary wire showing 40% reduction in tensile strength near DD Upadhyaya', 'OHE Km 1523+100', 'critical', 'urgent'),
    ]
    c.executemany("INSERT OR IGNORE INTO defects (defect_id, department_id, title, description, location, priority, maintenance_type) VALUES (?, ?, ?, ?, ?, ?, ?)", defects)
    
    # Seed train schedules with VVIP
    trains = [
        ('12951', 'Mumbai Rajdhani', 'Mumbai Central', 'New Delhi', '16:35', '08:35', '1,3,5,7', 'express', 1),
        ('12137', 'Punjab Mail', 'Mumbai CST', 'Firozpur', '19:15', '11:40', '1,2,3,4,5,6,7', 'express', 0),
        ('12903', 'Golden Temple Mail', 'Mumbai Central', 'Amritsar', '23:05', '11:25', '1,2,3,4,5,6,7', 'express', 0),
        ('17031', 'Maharashtra Express', 'Mumbai CST', 'Nagpur', '21:10', '13:55', '1,3,5,7', 'express', 0),
        ('95101', 'Local Fast', 'Churchgate', 'Virar', '05:30', '07:15', '1,2,3,4,5,6,7', 'passenger', 0),
        ('95102', 'Local Fast', 'Virar', 'Churchgate', '05:45', '07:30', '1,2,3,4,5,6,7', 'passenger', 0),
        ('95103', 'Local Fast', 'Churchgate', 'Virar', '07:00', '08:45', '1,2,3,4,5,6,7', 'passenger', 0),
        ('95104', 'Local Fast', 'Virar', 'Churchgate', '07:15', '09:00', '1,2,3,4,5,6,7', 'passenger', 0),
        ('G-101', 'Goods Freight', 'Mumbai Port', 'Igatpuri', '22:00', '02:30', '1,2,3,4,5,6,7', 'goods', 0),
        ('G-102', 'Goods Freight', 'JNPT', 'Pune', '20:00', '01:00', '1,2,3,4,5,6,7', 'goods', 0),
        ('M-001', 'Track Machine', 'Kalyan', 'Karjat', '00:00', '04:00', '2,5', 'maintenance', 0),
        ('12301', 'Howrah Rajdhani', 'Howrah', 'New Delhi', '17:00', '10:00', '1,2,3,4,5,6,7', 'express', 1),
        ('12952', 'Mumbai Rajdhani', 'New Delhi', 'Mumbai Central', '16:35', '08:35', '2,4,6', 'express', 1),
        ('12259', 'Sealdah Rajdhani', 'Sealdah', 'New Delhi', '17:45', '10:55', '1,3,5,7', 'express', 1),
        ('22691', 'Rajdhani Express', 'Hazrat Nizamuddin', 'Bangalore', '20:00', '05:40', '1,3,5', 'express', 1),
    ]
    c.executemany("INSERT OR IGNORE INTO train_schedule (train_number, train_name, origin, destination, departure_time, arrival_time, days_of_week, train_type, is_vvip) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", trains)
    
    # Seed AI recommendations
    recs = [
        ('merge', 'Combine Engineering Blocks in Sector A', 'Merge 3 separate Engineering blocks into 1 integrated block to save 4.5 hours of downtime', 85.0),
        ('reschedule', 'Reschedule OHE to Night Slot', 'Move Traction Distribution maintenance to 01:00-04:00 for zero train impact', 92.0),
        ('integrate', 'Link S&T + Traction Blocks', 'Coordinate Signal and Traction blocks in Corridor B to avoid double closure', 78.0),
        ('prioritize', 'Urgent: Rail Fracture DEF-011', 'Emergency rail fracture at Prayagraj requires immediate block allocation', 98.0),
        ('optimize', 'Weekend Mega Block', 'Schedule major renewal work during weekend low-traffic window', 88.0),
        ('vvip', 'Rajdhani Protection Protocol', 'Ensure Mumbai Rajdhani (12951) passes through maintenance corridor without delay', 95.0),
        ('hoger', 'Crew Duty Compliance Alert', 'LP-2847 approaching 10-hour HOER limit, reassign train 95103 to fresh crew', 90.0),
        ('token', 'Single Line Token Conflict', 'Directional token lock detected on Kalyan-Pune section, route trains sequentially', 87.0),
    ]
    c.executemany("INSERT OR IGNORE INTO ai_recommendations (recommendation_type, title, description, impact_score) VALUES (?, ?, ?, ?)", recs)
    
    # Seed blocks
    today = datetime.now().date()
    blocks = []
    for i in range(30):
        block_date = today + timedelta(days=random.randint(0, 13))
        dept_id = random.randint(1, 3)
        corridor_id = random.randint(1, 10)
        hour = random.choice([0, 1, 2, 3, 22, 23])
        minute = random.choice([0, 30])
        start = f"{hour:02d}:{minute:02d}"
        end_hour = (hour + random.randint(2, 4)) % 24
        end = f"{end_hour:02d}:{minute:02d}"
        block_types = ['Track Renewal', 'OHE Replacement', 'Signal Maintenance', 'Point Machine', 'Rail Grinding', 'Feeder Check']
        cat = random.choice(['routine', 'routine', 'fault', 'urgent']) if i < 3 else 'routine'
        status = random.choice(['planned', 'approved', 'in_progress', 'completed'])
        is_emergency = 1 if cat == 'urgent' else 0
        blocks.append((
            f'BLK-{1000+i}', dept_id, corridor_id, None,
            block_date.isoformat(), start, end,
            random.choice(block_types), cat, status, random.uniform(50, 98),
            is_emergency, 0
        ))
    c.executemany("INSERT OR IGNORE INTO blocks (block_id, department_id, corridor_id, defect_id, block_date, start_time, end_time, block_type, maintenance_category, status, ai_score, is_emergency, vvip_priority) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", blocks)
    
    # Seed token locks for single line sections
    token_data = [
        (4, 'Kalyan-Pune Section', 'UP', 1, None, None, 'available'),
        (4, 'Kalyan-Pune Section', 'DOWN', 1, None, None, 'available'),
        (9, 'Prayagraj-DDU Section', 'UP', 1, '12951', datetime.now().isoformat(), 'locked'),
        (9, 'Prayagraj-DDU Section', 'DOWN', 1, None, None, 'available'),
        (10, 'Jhansi-Kanpur Section', 'UP', 1, None, None, 'available'),
        (10, 'Jhansi-Kanpur Section', 'DOWN', 1, None, None, 'available'),
    ]
    c.executemany("INSERT OR IGNORE INTO token_locks (corridor_id, section_name, direction, token_number, locked_by_train, lock_time, status) VALUES (?, ?, ?, ?, ?, ?, ?)", token_data)
    
    # Seed crew duty
    crew = [
        ('LP-2847', 'Rajesh Kumar', 'loco_pilot', '06:00', '15:30', 9.5, 10, 'on_duty', '95103', 'Churchgate-Virar'),
        ('LP-3102', 'Suresh Singh', 'loco_pilot', '08:00', '18:00', 10.0, 10, 'violation', '95104', 'Virar-Churchgate'),
        ('AP-1156', 'Amit Verma', 'assistant_pilot', '06:00', '15:30', 9.5, 10, 'on_duty', '95103', 'Churchgate-Virar'),
        ('GD-0834', 'Prakash Yadav', 'guard', '05:30', '14:30', 9.0, 10, 'on_duty', '95101', 'Churchgate-Virar'),
        ('CT-0198', 'Vikram Joshi', 'controller', '06:00', '14:00', 8.0, 10, 'on_duty', None, 'Mumbai Control'),
        ('LP-4521', 'Manoj Tiwari', 'loco_pilot', '22:00', '08:00', 10.0, 10, 'on_duty', '12951', 'Mumbai Rajdhani'),
        ('LP-5567', 'Anil Gupta', 'loco_pilot', '14:00', '00:00', 10.0, 10, 'rest', None, None),
    ]
    c.executemany("INSERT OR IGNORE INTO crew_duty (crew_id, crew_name, role, duty_start, duty_end, hours_worked, max_hours, status, current_train, section) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", crew)
    
    # Seed emergency pushes
    emergencies = [
        ('95104', 'Local Fast Virar-Churchgate', 11.5, 'critical_push', 'completed', 'Train delayed 11.5 hours, critical push triggered to prevent HOER violation cascade'),
        ('12951', 'Mumbai Rajdhani', 2.0, 'vvip_protect', 'active', 'Rajdhani approaching maintenance corridor, protected passage scheduled'),
        ('G-102', 'Goods Freight JNPT-Pune', 14.0, 'rescue', 'active', 'Goods train stranded 14 hours, rescue locomotive dispatched'),
    ]
    c.executemany("INSERT OR IGNORE INTO emergency_push (train_number, train_name, delay_hours, push_type, status, description) VALUES (?, ?, ?, ?, ?, ?)", emergencies)
    
    conn.commit()
    c.execute("UPDATE schema_version SET version = 2")
    conn.commit()
    conn.close()

init_db()

# ============================================
# MODELS
# ============================================
class BlockCreate(BaseModel):
    department_id: int
    corridor_id: int
    defect_id: Optional[int] = None
    block_date: str
    start_time: str
    end_time: str
    block_type: str
    maintenance_category: str = "routine"

class DefectUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None

# ============================================
# MAINTENANCE ENGINE
# ============================================
@app.get("/api/maintenance/engine")
def get_maintenance_engine():
    conn = get_db()
    
    defects = conn.execute("""
        SELECT d.*, dep.name as dept_name, dep.code as dept_code
        FROM defects d
        JOIN departments dep ON d.department_id = dep.id
        WHERE d.status = 'pending'
    """).fetchall()
    
    categories = {"routine": [], "fault": [], "urgent": []}
    for d in defects:
        cat = d[7] or 'fault'  # maintenance_type is index 7
        item = {
            "id": d[0], "defect_id": d[1], "title": d[3], "description": d[4],
            "location": d[5], "priority": d[6], "maintenance_type": cat,
            "dept_name": d[10], "dept_code": d[11]
        }
        if cat in categories:
            categories[cat].append(item)
    
    rules = {
        "routine": {
            "description": "Can be split across multiple time windows. Scheduled during maintenance corridors.",
            "sla_hours": 168,
            "can_split": True,
            "requires_block": True,
            "auto_schedule": True
        },
        "fault": {
            "description": "Must be fixed within 24 hours. Cannot be split. Requires dedicated block.",
            "sla_hours": 24,
            "can_split": False,
            "requires_block": True,
            "auto_schedule": False
        },
        "urgent": {
            "description": "Immediate emergency override. Triggers critical push. All other blocks may be cancelled.",
            "sla_hours": 4,
            "can_split": False,
            "requires_block": True,
            "auto_schedule": False,
            "emergency_override": True
        }
    }
    
    conn.close()
    
    return {
        "categories": {
            "routine": {"count": len(categories["routine"]), "items": categories["routine"]},
            "fault": {"count": len(categories["fault"]), "items": categories["fault"]},
            "urgent": {"count": len(categories["urgent"]), "items": categories["urgent"]}
        },
        "rules": rules,
        "total_pending": len(defects)
    }

# ============================================
# DIRECTIONAL TOKEN LOCKS
# ============================================
@app.get("/api/token/locks")
def get_token_locks():
    conn = get_db()
    rows = conn.execute("""
        SELECT tl.*, c.route_name
        FROM token_locks tl
        JOIN corridors c ON tl.corridor_id = c.id
        ORDER BY c.route_name, tl.direction
    """).fetchall()
    conn.close()
    return [{"id": r[0], "corridor_id": r[1], "section": r[2], "direction": r[3],
             "token": r[4], "locked_by": r[5], "lock_time": r[6], "status": r[7],
             "route_name": r[8]} for r in rows]

@app.post("/api/token/lock")
def acquire_token_lock(corridor_id: int, direction: str, train_number: str):
    conn = get_db()
    existing = conn.execute(
        "SELECT * FROM token_locks WHERE corridor_id = ? AND direction = ? AND status = 'locked'",
        (corridor_id, direction)
    ).fetchone()
    
    if existing:
        conn.close()
        return {"success": False, "message": f"Token already held by {existing[5]} on {direction} direction. Deadlock prevented."}
    
    opposite = "DOWN" if direction == "UP" else "UP"
    opp_lock = conn.execute(
        "SELECT * FROM token_locks WHERE corridor_id = ? AND direction = ? AND status = 'locked'",
        (corridor_id, opposite)
    ).fetchone()
    
    if opp_lock:
        conn.close()
        return {"success": False, "message": f"Opposite direction {opposite} locked by {opp_lock[5]}. Single line conflict detected."}
    
    conn.execute(
        "UPDATE token_locks SET status = 'locked', locked_by_train = ?, lock_time = ? WHERE corridor_id = ? AND direction = ?",
        (train_number, datetime.now().isoformat(), corridor_id, direction)
    )
    conn.commit()
    conn.close()
    return {"success": True, "message": f"Token acquired for {direction} direction by {train_number}"}

@app.post("/api/token/release")
def release_token_lock(corridor_id: int, direction: str):
    conn = get_db()
    conn.execute(
        "UPDATE token_locks SET status = 'released', locked_by_train = NULL, lock_time = NULL WHERE corridor_id = ? AND direction = ?",
        (corridor_id, direction)
    )
    conn.commit()
    conn.close()
    return {"success": True, "message": f"Token released for {direction} direction"}

# ============================================
# HOER CREW COMPLIANCE
# ============================================
@app.get("/api/crew/duty")
def get_crew_duty():
    conn = get_db()
    rows = conn.execute("SELECT * FROM crew_duty ORDER BY hours_worked DESC").fetchall()
    conn.close()
    
    result = []
    for r in rows:
        hours_worked = float(r[6]) if r[6] else 0
        max_hours = float(r[7]) if r[7] else 10
        remaining = max_hours - hours_worked
        item = {
            "id": r[0], "crew_id": r[1], "name": r[2], "role": r[3],
            "duty_start": r[4], "duty_end": r[5], "hours_worked": hours_worked,
            "max_hours": max_hours, "status": r[8], "current_train": r[9],
            "section": r[10], "remaining_hours": round(remaining, 1),
            "hoer_compliant": remaining > 0
        }
        result.append(item)
    
    violations = [x for x in result if not x["hoer_compliant"]]
    at_risk = [x for x in result if 0 < x["remaining_hours"] <= 1]
    
    return {
        "crew": result,
        "total_violations": len(violations),
        "at_risk_count": len(at_risk),
        "violations": violations,
        "at_risk": at_risk
    }

@app.post("/api/crew/check-hoer")
def check_hoer_compliance(crew_id: str, proposed_train: str, proposed_section: str):
    conn = get_db()
    crew = conn.execute("SELECT * FROM crew_duty WHERE crew_id = ?", (crew_id,)).fetchone()
    
    if not crew:
        conn.close()
        return {"compliant": False, "message": "Crew member not found"}
    
    remaining = crew[6] - crew[5]  # max_hours - hours_worked
    estimated_hours = 4.0  # average section time
    
    if remaining <= 0:
        conn.close()
        return {
            "compliant": False,
            "message": f"HOER VIOLATION: {crew[2]} has exhausted {crew[6]} duty hours. Cannot assign new train.",
            "current_hours": crew[5],
            "max_hours": crew[6]
        }
    
    if remaining < estimated_hours:
        conn.close()
        return {
            "compliant": False,
            "message": f"HOER RISK: {crew[2]} has only {remaining:.1f}h remaining. Section requires ~{estimated_hours}h.",
            "current_hours": crew[5],
            "max_hours": crew[6],
            "remaining": remaining
        }
    
    conn.close()
    return {
        "compliant": True,
        "message": f"HOER OK: {crew[2]} has {remaining:.1f}h remaining. Safe to assign.",
        "remaining": remaining
    }

# ============================================
# VVIP & EMERGENCY PUSH
# ============================================
@app.get("/api/emergency/pushes")
def get_emergency_pushes():
    conn = get_db()
    rows = conn.execute("SELECT * FROM emergency_push ORDER BY delay_hours DESC").fetchall()
    conn.close()
    return [{"id": r[0], "train_number": r[1], "train_name": r[2], "delay_hours": r[3],
             "type": r[4], "triggered_at": r[5], "status": r[6], "description": r[7]} for r in rows]

@app.get("/api/emergency/vvip-status")
def get_vvip_status():
    conn = get_db()
    vvip_trains = conn.execute("SELECT * FROM train_schedule WHERE is_vvip = 1").fetchall()
    corridors = conn.execute("SELECT * FROM corridors WHERE single_line_section = 1").fetchall()
    
    protection_rules = []
    for t in vvip_trains:
        for c in corridors:
            protection_rules.append({
                "train": t[1],
                "train_name": t[2],
                "corridor": c[2],
                "route_name": c[3],
                "rule": f"Rajdhani/special train {t[1]} must pass through {c[3]} without any maintenance block during its scheduled passage window",
                "action": "Auto-reschedule any planned blocks in the 2-hour window around train passage"
            })
    
    conn.close()
    return {
        "vvip_trains": [{"number": t[1], "name": t[2], "origin": t[3], "destination": t[4]} for t in vvip_trains],
        "protection_rules": protection_rules[:10]
    }

@app.post("/api/emergency/critical-push")
def trigger_critical_push(train_number: str, delay_hours: float):
    conn = get_db()
    
    if delay_hours >= 11:
        push_type = "critical_push"
        description = f"Train {train_number} delayed {delay_hours}h. Critical push triggered per HOER protocol."
    else:
        push_type = "rescue"
        description = f"Train {train_number} delayed {delay_hours}h. Rescue locomotive recommended."
    
    conn.execute(
        "INSERT INTO emergency_push (train_number, train_name, delay_hours, push_type, status, description) VALUES (?, ?, ?, ?, 'active', ?)",
        (train_number, f"Train {train_number}", delay_hours, push_type, description)
    )
    conn.commit()
    conn.close()
    return {"success": True, "type": push_type, "message": description}

# ============================================
# EXISTING ENDPOINTS (updated)
# ============================================

@app.get("/api/dashboard/stats")
def get_dashboard_stats():
    conn = get_db()
    c = conn.cursor()
    
    total_blocks = c.execute("SELECT COUNT(*) FROM blocks").fetchone()[0]
    active_blocks = c.execute("SELECT COUNT(*) FROM blocks WHERE status IN ('planned', 'approved', 'in_progress')").fetchone()[0]
    pending_defects = c.execute("SELECT COUNT(*) FROM defects WHERE status = 'pending'").fetchone()[0]
    critical_defects = c.execute("SELECT COUNT(*) FROM defects WHERE priority = 'critical' AND status = 'pending'").fetchone()[0]
    urgent_defects = c.execute("SELECT COUNT(*) FROM defects WHERE maintenance_type = 'urgent' AND status = 'pending'").fetchone()[0]
    
    dept_stats = c.execute("""
        SELECT d.name, d.code, d.color, COUNT(b.id) as block_count
        FROM departments d LEFT JOIN blocks b ON d.id = b.department_id
        GROUP BY d.id
    """).fetchall()
    
    corridor_stats = c.execute("""
        SELECT c.corridor_id, c.route_name, c.length_km,
            COUNT(b.id) as blocks,
            SUM(CASE WHEN b.status != 'cancelled' THEN 1 ELSE 0 END) as active_blocks
        FROM corridors c LEFT JOIN blocks b ON c.id = b.corridor_id
        GROUP BY c.id
    """).fetchall()
    
    recommendations = c.execute("SELECT * FROM ai_recommendations ORDER BY impact_score DESC LIMIT 5").fetchall()
    
    token_locked = c.execute("SELECT COUNT(*) FROM token_locks WHERE status = 'locked'").fetchone()[0]
    crew_violations = c.execute("SELECT COUNT(*) FROM crew_duty WHERE status = 'violation'").fetchone()[0]
    active_emergencies = c.execute("SELECT COUNT(*) FROM emergency_push WHERE status = 'active'").fetchone()[0]
    
    conn.close()
    
    return {
        "total_blocks": total_blocks,
        "active_blocks": active_blocks,
        "pending_defects": pending_defects,
        "critical_defects": critical_defects,
        "urgent_defects": urgent_defects,
        "asset_availability": round(85 + random.uniform(0, 10), 1),
        "ai_efficiency": round(90 + random.uniform(0, 8), 1),
        "departments": [{"name": r[0], "code": r[1], "color": r[2], "blocks": r[3]} for r in dept_stats],
        "corridors": [{"id": r[0], "route": r[1], "length": r[2], "blocks": r[3], "active": r[4]} for r in corridor_stats],
        "recommendations": [{"id": r[0], "type": r[1], "title": r[2], "description": r[3], "score": r[4]} for r in recommendations],
        "token_locked": token_locked,
        "crew_violations": crew_violations,
        "active_emergencies": active_emergencies
    }

@app.get("/api/departments")
def get_departments():
    conn = get_db()
    rows = conn.execute("SELECT * FROM departments").fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "code": r[2], "color": r[3]} for r in rows]

@app.get("/api/defects")
def get_defects(department: str = "all", priority: str = "all"):
    conn = get_db()
    query = """
        SELECT d.*, dep.name as dept_name, dep.code as dept_code, dep.color as dept_color
        FROM defects d JOIN departments dep ON d.department_id = dep.id WHERE 1=1
    """
    params = []
    if department != "all":
        query += " AND dep.code = ?"
        params.append(department.upper())
    if priority != "all":
        query += " AND d.priority = ?"
        params.append(priority)
    query += " ORDER BY CASE d.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [{"id": r[0], "defect_id": r[1], "department_id": r[2], "title": r[3],
             "description": r[4], "location": r[5], "priority": r[6], "maintenance_type": r[7],
             "status": r[8], "dept_name": r[10], "dept_code": r[11], "dept_color": r[12]} for r in rows]

@app.put("/api/defects/{defect_id}")
def update_defect(defect_id: int, update: DefectUpdate):
    conn = get_db()
    if update.status:
        conn.execute("UPDATE defects SET status = ? WHERE id = ?", (update.status, defect_id))
    if update.priority:
        conn.execute("UPDATE defects SET priority = ? WHERE id = ?", (update.priority, defect_id))
    conn.commit()
    conn.close()
    return {"message": "Defect updated"}

@app.get("/api/blocks")
def get_blocks(start_date: str = None, end_date: str = None, department: str = "all"):
    conn = get_db()
    query = """
        SELECT b.*, dep.name as dept_name, dep.code as dept_code, dep.color as dept_color,
               c.route_name, c.corridor_id
        FROM blocks b JOIN departments dep ON b.department_id = dep.id
        LEFT JOIN corridors c ON b.corridor_id = c.id WHERE 1=1
    """
    params = []
    if start_date:
        query += " AND b.block_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND b.block_date <= ?"
        params.append(end_date)
    if department != "all":
        query += " AND dep.code = ?"
        params.append(department.upper())
    query += " ORDER BY b.block_date, b.start_time"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [{"id": r[0], "block_id": r[1], "department_id": r[2], "corridor_id": r[3],
             "defect_id": r[4], "block_date": r[5], "start_time": r[6], "end_time": r[7],
             "block_type": r[8], "maintenance_category": r[9], "status": r[10], "ai_score": r[11],
             "is_emergency": r[12], "vvip_priority": r[13],
             "dept_name": r[15], "dept_code": r[16], "dept_color": r[17],
             "route_name": r[18], "corridor_id_text": r[19]} for r in rows]

@app.post("/api/blocks")
def create_block(block: BlockCreate):
    conn = get_db()
    block_id = f"BLK-{random.randint(1000, 9999)}"
    conn.execute("""
        INSERT INTO blocks (block_id, department_id, corridor_id, defect_id, block_date, start_time, end_time, block_type, maintenance_category, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'planned')
    """, (block_id, block.department_id, block.corridor_id, block.defect_id,
          block.block_date, block.start_time, block.end_time, block.block_type, block.maintenance_category))
    conn.commit()
    conn.close()
    return {"block_id": block_id, "message": "Block created"}

@app.get("/api/corridors")
def get_corridors():
    conn = get_db()
    rows = conn.execute("""
        SELECT c.*, COUNT(b.id) as block_count,
            SUM(CASE WHEN b.status = 'completed' THEN 1 ELSE 0 END) as completed
        FROM corridors c LEFT JOIN blocks b ON c.id = b.corridor_id GROUP BY c.id
    """).fetchall()
    conn.close()
    return [{"id": r[0], "corridor_id": r[1], "route_name": r[2], "length_km": r[3],
             "status": r[4], "single_line": r[5], "blocks": r[6], "completed": r[7]} for r in rows]

@app.get("/api/trains")
def get_trains():
    conn = get_db()
    rows = conn.execute("SELECT * FROM train_schedule ORDER BY is_vvip DESC, departure_time").fetchall()
    conn.close()
    return [{"id": r[0], "number": r[1], "name": r[2], "origin": r[3],
             "destination": r[4], "departure": r[5], "arrival": r[6],
             "days": r[7], "type": r[8], "is_vvip": r[9]} for r in rows]

@app.get("/api/ai/optimize")
def run_ai_optimization():
    conn = get_db()
    defects = conn.execute("""
        SELECT d.*, dep.name as dept_name FROM defects d
        JOIN departments dep ON d.department_id = dep.id WHERE d.status = 'pending'
        ORDER BY CASE d.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END
    """).fetchall()
    blocks = conn.execute("""
        SELECT b.*, dep.name as dept_name, c.route_name FROM blocks b
        JOIN departments dep ON b.department_id = dep.id LEFT JOIN corridors c ON b.corridor_id = c.id
        WHERE b.status IN ('planned', 'approved')
    """).fetchall()
    
    recommendations = []
    total_downtime_saved = 0
    blocks_merged = 0
    
    corridor_blocks = {}
    for b in blocks:
        key = (b[3], b[5])
        if key not in corridor_blocks:
            corridor_blocks[key] = []
        corridor_blocks[key].append(b)
    
    for key, group in corridor_blocks.items():
        if len(group) > 1:
            time_slots = []
            for b in group:
                start = int(b[6].split(':')[0])
                end = int(b[7].split(':')[0])
                time_slots.append((start, end, b))
            time_slots.sort()
            for i in range(len(time_slots) - 1):
                if time_slots[i+1][0] - time_slots[i][1] <= 2:
                    saved = time_slots[i][1] - time_slots[i][0]
                    total_downtime_saved += saved
                    blocks_merged += 1
                    recommendations.append({
                        "type": "merge",
                        "title": f"Merge blocks on corridor {key[0]}",
                        "description": f"Combine blocks {time_slots[0][2][1]} and {time_slots[1][2][1]} to save {saved} hours",
                        "impact": 85 + random.uniform(0, 10)
                    })
    
    for d in defects:
        if d[5] == 'critical':
            recommendations.append({
                "type": "priority",
                "title": f"Urgent: {d[3]}",
                "description": f"Critical defect at {d[5]} requires immediate attention",
                "impact": 95
            })
    
    recommendations.append({
        "type": "reschedule",
        "title": "Reschedule to Night Window (01:00-04:00)",
        "description": "Move non-critical maintenance to night slots for zero train impact",
        "impact": 90
    })
    
    current_efficiency = 62 + random.uniform(0, 5)
    optimized_efficiency = min(95, current_efficiency + 25 + random.uniform(0, 5))
    projected_uptime = min(98, optimized_efficiency + 5)
    
    conn.close()
    return {
        "current_efficiency": round(current_efficiency, 1),
        "optimized_efficiency": round(optimized_efficiency, 1),
        "projected_uptime": round(projected_uptime, 1),
        "blocks_merged": blocks_merged,
        "downtime_saved_hours": total_downtime_saved,
        "recommendations": recommendations[:10]
    }

@app.get("/api/ai/generate-plan")
def generate_ai_plan(week_offset: int = 0):
    conn = get_db()
    today = datetime.now().date() + timedelta(weeks=week_offset)
    start_of_week = today - timedelta(days=today.weekday())
    corridors = conn.execute("SELECT * FROM corridors").fetchall()
    pending_defects = conn.execute("SELECT * FROM defects WHERE status = 'pending'").fetchall()
    
    plan = []
    for day_offset in range(7):
        current_date = start_of_week + timedelta(days=day_offset)
        day_blocks = []
        available_slots = [("00:00", "04:00"), ("22:00", "24:00")]
        for corridor in corridors:
            if len(day_blocks) < 5:
                for slot in available_slots:
                    dept = random.choice([1, 2, 3])
                    dept_names = {1: 'Engineering', 2: 'Traction Distribution', 3: 'Signal & Telecom'}
                    dept_colors = {1: '#3B82F6', 2: '#F59E0B', 3: '#10B981'}
                    cat = random.choice(['routine', 'routine', 'fault'])
                    day_blocks.append({
                        "block_id": f"BLK-{random.randint(1000,9999)}",
                        "corridor": corridor[2],
                        "department": dept_names[dept],
                        "color": dept_colors[dept],
                        "start": slot[0], "end": slot[1],
                        "type": random.choice(["Track Renewal", "OHE Maintenance", "Signal Check", "Point Machine"]),
                        "category": cat,
                        "ai_score": round(random.uniform(70, 98), 1)
                    })
                    break
        plan.append({"date": current_date.isoformat(), "day_name": current_date.strftime("%A"), "blocks": day_blocks})
    
    urgent_blocks = []
    for d in pending_defects:
        if d[6] == 'urgent':
            urgent_blocks.append({
                "defect_id": d[1], "title": d[2], "location": d[4],
                "priority": d[5], "maintenance_type": d[6],
                "recommended_date": (start_of_week + timedelta(days=random.randint(0, 1))).isoformat()
            })
    
    conn.close()
    return {"week_start": start_of_week.isoformat(), "plan": plan, "urgent_blocks": urgent_blocks,
            "total_blocks": sum(len(day["blocks"]) for day in plan)}

@app.get("/api/reports/summary")
def get_report_summary():
    conn = get_db()
    dept_summary = conn.execute("""
        SELECT dep.name, dep.color, COUNT(b.id) as total,
            SUM(CASE WHEN b.status = 'completed' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN b.status = 'planned' THEN 1 ELSE 0 END) as planned,
            AVG(b.ai_score) as avg_score
        FROM departments dep LEFT JOIN blocks b ON dep.id = b.department_id GROUP BY dep.id
    """).fetchall()
    defect_summary = conn.execute("SELECT priority, COUNT(*) as count FROM defects GROUP BY priority").fetchall()
    monthly_stats = conn.execute("""
        SELECT strftime('%Y-%m', block_date) as month, COUNT(*) as blocks
        FROM blocks GROUP BY month ORDER BY month DESC LIMIT 6
    """).fetchall()
    conn.close()
    return {
        "departments": [{"name": r[0], "color": r[1], "total": r[2], "completed": r[3],
                         "planned": r[4], "avg_score": round(r[5] or 0, 1)} for r in dept_summary],
        "defects_by_priority": [{"priority": r[0], "count": r[1]} for r in defect_summary],
        "monthly_blocks": [{"month": r[0], "count": r[1]} for r in monthly_stats]
    }

# Serve static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
