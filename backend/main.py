import sqlite3
import json
import os
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query, Depends, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import random
import math

app = FastAPI(title="RailBlock AI API", version="3.0.0")

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

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_token():
    return secrets.token_hex(32)

def get_current_user(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    conn = get_db()
    session = conn.execute(
        "SELECT s.*, u.id as user_id, u.username, u.full_name, u.role, u.division "
        "FROM sessions s JOIN users u ON s.user_id = u.id "
        "WHERE s.token = ? AND s.expires_at > ?",
        (token, datetime.now().isoformat())
    ).fetchone()
    conn.close()
    if not session:
        return None
    return {
        "user_id": session["user_id"], "username": session["username"],
        "full_name": session["full_name"], "role": session["role"],
        "division": session["division"]
    }

def require_auth(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user

def require_admin(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

# ============================================
# DATABASE INIT
# ============================================
def init_db():
    conn = get_db()
    c = conn.cursor()

    version_table = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'").fetchone()
    if not version_table:
        c.execute("CREATE TABLE schema_version (version INTEGER DEFAULT 1)")
        c.execute("INSERT INTO schema_version (version) VALUES (1)")
    else:
        v = c.execute("SELECT version FROM schema_version").fetchone()
        if v and v[0] >= 3:
            conn.commit()
            conn.close()
            return

    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT CHECK(role IN ('admin', 'controller', 'engineer', 'viewer')) DEFAULT 'viewer',
        division TEXT DEFAULT 'Mumbai Division',
        department TEXT,
        email TEXT,
        phone TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token TEXT UNIQUE NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

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
        created_by INTEGER,
        approved_by INTEGER,
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

    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT NOT NULL,
        entity_type TEXT,
        entity_id TEXT,
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """)

    # Seed default admin user (password: admin123)
    admin_hash = hash_password("admin123")
    c.execute("INSERT OR IGNORE INTO users (username, password_hash, full_name, role, division, department) VALUES (?, ?, ?, ?, ?, ?)",
              ("admin", admin_hash, "System Administrator", "admin", "Mumbai Division", "Operations"))
    c.execute("INSERT OR IGNORE INTO users (username, password_hash, full_name, role, division, department) VALUES (?, ?, ?, ?, ?, ?)",
              ("controller", hash_password("ctrl123"), "Section Controller", "controller", "Mumbai Division", "Operations"))
    c.execute("INSERT OR IGNORE INTO users (username, password_hash, full_name, role, division, department) VALUES (?, ?, ?, ?, ?, ?)",
              ("engineer", hash_password("eng123"), "Chief Engineer", "engineer", "Mumbai Division", "Engineering"))

    # Seed departments
    departments = [
        ('Engineering', 'ENG', '#3B82F6'),
        ('Traction Distribution', 'TRD', '#F59E0B'),
        ('Signal & Telecom', 'SIG', '#10B981'),
    ]
    c.executemany("INSERT OR IGNORE INTO departments (name, code, color) VALUES (?, ?, ?)", departments)

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
            is_emergency, 0, 1, None
        ))
    c.executemany("INSERT OR IGNORE INTO blocks (block_id, department_id, corridor_id, defect_id, block_date, start_time, end_time, block_type, maintenance_category, status, ai_score, is_emergency, vvip_priority, created_by, approved_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", blocks)

    token_data = [
        (4, 'Kalyan-Pune Section', 'UP', 1, None, None, 'available'),
        (4, 'Kalyan-Pune Section', 'DOWN', 1, None, None, 'available'),
        (9, 'Prayagraj-DDU Section', 'UP', 1, '12951', datetime.now().isoformat(), 'locked'),
        (9, 'Prayagraj-DDU Section', 'DOWN', 1, None, None, 'available'),
        (10, 'Jhansi-Kanpur Section', 'UP', 1, None, None, 'available'),
        (10, 'Jhansi-Kanpur Section', 'DOWN', 1, None, None, 'available'),
    ]
    c.executemany("INSERT OR IGNORE INTO token_locks (corridor_id, section_name, direction, token_number, locked_by_train, lock_time, status) VALUES (?, ?, ?, ?, ?, ?, ?)", token_data)

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

    emergencies = [
        ('95104', 'Local Fast Virar-Churchgate', 11.5, 'critical_push', 'completed', 'Train delayed 11.5 hours, critical push triggered to prevent HOER violation cascade'),
        ('12951', 'Mumbai Rajdhani', 2.0, 'vvip_protect', 'active', 'Rajdhani approaching maintenance corridor, protected passage scheduled'),
        ('G-102', 'Goods Freight JNPT-Pune', 14.0, 'rescue', 'active', 'Goods train stranded 14 hours, rescue locomotive dispatched'),
    ]
    c.executemany("INSERT OR IGNORE INTO emergency_push (train_number, train_name, delay_hours, push_type, status, description) VALUES (?, ?, ?, ?, ?, ?)", emergencies)

    conn.commit()
    c.execute("UPDATE schema_version SET version = 3")
    conn.commit()
    conn.close()

init_db()

# ============================================
# PYDANTIC MODELS
# ============================================
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    full_name: str
    role: str = "viewer"
    division: str = "Mumbai Division"
    department: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

class BlockCreate(BaseModel):
    department_id: int
    corridor_id: int
    defect_id: Optional[int] = None
    block_date: str
    start_time: str
    end_time: str
    block_type: str
    maintenance_category: str = "routine"

class BlockUpdate(BaseModel):
    status: Optional[str] = None
    block_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    approved_by: Optional[int] = None

class DefectCreate(BaseModel):
    department_id: int
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    priority: str = "medium"
    maintenance_type: str = "fault"

class DefectUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None

class CorridorCreate(BaseModel):
    corridor_id: str
    route_name: str
    length_km: float
    single_line_section: int = 0

class TrainCreate(BaseModel):
    train_number: str
    train_name: str
    origin: str
    destination: str
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None
    days_of_week: Optional[str] = None
    train_type: str = "passenger"
    is_vvip: int = 0

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    division: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[int] = None

# ============================================
# AUTH ENDPOINTS
# ============================================
@app.post("/api/auth/login")
def login(req: LoginRequest):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ? AND is_active = 1", (req.username,)).fetchone()
    if not user or user["password_hash"] != hash_password(req.password):
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = generate_token()
    expires = (datetime.now() + timedelta(hours=12)).isoformat()
    conn.execute("INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)",
                 (user["id"], token, expires))
    conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.now().isoformat(), user["id"]))
    conn.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?)",
                 (user["id"], "login", "user", user["username"], f"User {user['username']} logged in"))
    conn.commit()
    conn.close()

    return {
        "token": token,
        "user": {
            "id": user["id"], "username": user["username"],
            "full_name": user["full_name"], "role": user["role"],
            "division": user["division"], "department": user["department"]
        },
        "expires_at": expires
    }

@app.post("/api/auth/register")
def register(req: RegisterRequest, user: dict = Depends(require_admin)):
    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE username = ?", (req.username,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="Username already exists")

    conn.execute(
        "INSERT INTO users (username, password_hash, full_name, role, division, department, email, phone) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (req.username, hash_password(req.password), req.full_name, req.role, req.division, req.department, req.email, req.phone)
    )
    conn.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?)",
                 (user["user_id"], "register", "user", req.username, f"Created user {req.username} with role {req.role}"))
    conn.commit()
    conn.close()
    return {"message": "User created successfully"}

@app.post("/api/auth/logout")
def logout(request: Request, user: dict = Depends(require_auth)):
    auth = request.headers.get("Authorization", "")[7:]
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE token = ?", (auth,))
    conn.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?)",
                 (user["user_id"], "logout", "user", user["username"], f"User {user['username']} logged out"))
    conn.commit()
    conn.close()
    return {"message": "Logged out"}

@app.get("/api/auth/me")
def get_me(user: dict = Depends(require_auth)):
    return {"user": user}

# ============================================
# ADMIN - USER MANAGEMENT
# ============================================
@app.get("/api/admin/users")
def list_users(user: dict = Depends(require_admin)):
    conn = get_db()
    rows = conn.execute("SELECT id, username, full_name, role, division, department, email, phone, is_active, created_at, last_login FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return [{"id": r[0], "username": r[1], "full_name": r[2], "role": r[3], "division": r[4],
             "department": r[5], "email": r[6], "phone": r[7], "is_active": r[8],
             "created_at": r[9], "last_login": r[10]} for r in rows]

@app.put("/api/admin/users/{user_id}")
def update_user(user_id: int, update: UserUpdate, user: dict = Depends(require_admin)):
    conn = get_db()
    if update.full_name:
        conn.execute("UPDATE users SET full_name = ? WHERE id = ?", (update.full_name, user_id))
    if update.role:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (update.role, user_id))
    if update.division:
        conn.execute("UPDATE users SET division = ? WHERE id = ?", (update.division, user_id))
    if update.department is not None:
        conn.execute("UPDATE users SET department = ? WHERE id = ?", (update.department, user_id))
    if update.is_active is not None:
        conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (update.is_active, user_id))
    conn.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?)",
                 (user["user_id"], "update_user", "user", str(user_id), f"Updated user {user_id}"))
    conn.commit()
    conn.close()
    return {"message": "User updated"}

@app.delete("/api/admin/users/{user_id}")
def delete_user(user_id: int, user: dict = Depends(require_admin)):
    conn = get_db()
    target = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    if not target:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    if user_id == user["user_id"]:
        conn.close()
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_id,))
    conn.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?)",
                 (user["user_id"], "deactivate_user", "user", target["username"], f"Deactivated user {target['username']}"))
    conn.commit()
    conn.close()
    return {"message": "User deactivated"}

# ============================================
# ADMIN - BLOCK MANAGEMENT
# ============================================
@app.get("/api/admin/blocks")
def admin_list_blocks(user: dict = Depends(require_auth)):
    conn = get_db()
    rows = conn.execute("""
        SELECT b.*, dep.name as dept_name, dep.code as dept_code, dep.color as dept_color,
               c.route_name, c.corridor_id as corr_id,
               u1.full_name as created_by_name, u2.full_name as approved_by_name
        FROM blocks b
        JOIN departments dep ON b.department_id = dep.id
        LEFT JOIN corridors c ON b.corridor_id = c.id
        LEFT JOIN users u1 ON b.created_by = u1.id
        LEFT JOIN users u2 ON b.approved_by = u2.id
        ORDER BY b.block_date, b.start_time
    """).fetchall()
    conn.close()
    return [{"id": r[0], "block_id": r[1], "department_id": r[2], "corridor_id": r[3],
             "defect_id": r[4], "block_date": r[5], "start_time": r[6], "end_time": r[7],
             "block_type": r[8], "maintenance_category": r[9], "status": r[10], "ai_score": r[11],
             "is_emergency": r[12], "vvip_priority": r[13], "created_by": r[14], "approved_by": r[15],
             "dept_name": r[17], "dept_code": r[18], "dept_color": r[19],
             "route_name": r[20], "corridor_name": r[21],
             "created_by_name": r[22], "approved_by_name": r[23]} for r in rows]

@app.post("/api/admin/blocks")
def admin_create_block(block: BlockCreate, user: dict = Depends(require_auth)):
    conn = get_db()
    block_id = f"BLK-{random.randint(1000, 9999)}"
    conn.execute("""
        INSERT INTO blocks (block_id, department_id, corridor_id, defect_id, block_date, start_time, end_time, block_type, maintenance_category, status, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'planned', ?)
    """, (block_id, block.department_id, block.corridor_id, block.defect_id,
          block.block_date, block.start_time, block.end_time, block.block_type, block.maintenance_category, user["user_id"]))
    conn.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?)",
                 (user["user_id"], "create_block", "block", block_id, f"Created block {block_id}"))
    conn.commit()
    conn.close()
    return {"block_id": block_id, "message": "Block created"}

@app.put("/api/admin/blocks/{block_id}")
def admin_update_block(block_id: int, update: BlockUpdate, user: dict = Depends(require_auth)):
    conn = get_db()
    if update.status:
        conn.execute("UPDATE blocks SET status = ? WHERE id = ?", (update.status, block_id))
        if update.status == "approved" and user["role"] in ("admin", "controller"):
            conn.execute("UPDATE blocks SET approved_by = ? WHERE id = ?", (user["user_id"], block_id))
    if update.block_date:
        conn.execute("UPDATE blocks SET block_date = ? WHERE id = ?", (update.block_date, block_id))
    if update.start_time:
        conn.execute("UPDATE blocks SET start_time = ? WHERE id = ?", (update.start_time, block_id))
    if update.end_time:
        conn.execute("UPDATE blocks SET end_time = ? WHERE id = ?", (update.end_time, block_id))
    conn.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?)",
                 (user["user_id"], "update_block", "block", str(block_id), f"Updated block {block_id}"))
    conn.commit()
    conn.close()
    return {"message": "Block updated"}

@app.delete("/api/admin/blocks/{block_id}")
def admin_delete_block(block_id: int, user: dict = Depends(require_admin)):
    conn = get_db()
    conn.execute("DELETE FROM blocks WHERE id = ?", (block_id,))
    conn.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?)",
                 (user["user_id"], "delete_block", "block", str(block_id), f"Deleted block {block_id}"))
    conn.commit()
    conn.close()
    return {"message": "Block deleted"}

# ============================================
# ADMIN - DEFECT MANAGEMENT
# ============================================
@app.get("/api/admin/defects")
def admin_list_defects(user: dict = Depends(require_auth)):
    conn = get_db()
    rows = conn.execute("""
        SELECT d.*, dep.name as dept_name, dep.code as dept_code, dep.color as dept_color
        FROM defects d JOIN departments dep ON d.department_id = dep.id
        ORDER BY CASE d.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END
    """).fetchall()
    conn.close()
    return [{"id": r[0], "defect_id": r[1], "department_id": r[2], "title": r[3],
             "description": r[4], "location": r[5], "priority": r[6], "maintenance_type": r[7],
             "status": r[8], "created_at": r[9],
             "dept_name": r[10], "dept_code": r[11], "dept_color": r[12]} for r in rows]

@app.post("/api/admin/defects")
def admin_create_defect(defect: DefectCreate, user: dict = Depends(require_auth)):
    conn = get_db()
    defect_id = f"DEF-{random.randint(100, 999)}"
    conn.execute(
        "INSERT INTO defects (defect_id, department_id, title, description, location, priority, maintenance_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (defect_id, defect.department_id, defect.title, defect.description, defect.location, defect.priority, defect.maintenance_type)
    )
    conn.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?)",
                 (user["user_id"], "create_defect", "defect", defect_id, f"Created defect {defect_id}"))
    conn.commit()
    conn.close()
    return {"defect_id": defect_id, "message": "Defect created"}

@app.put("/api/admin/defects/{defect_id}")
def admin_update_defect(defect_id: int, update: DefectUpdate, user: dict = Depends(require_auth)):
    conn = get_db()
    if update.status:
        conn.execute("UPDATE defects SET status = ? WHERE id = ?", (update.status, defect_id))
    if update.priority:
        conn.execute("UPDATE defects SET priority = ? WHERE id = ?", (update.priority, defect_id))
    conn.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?)",
                 (user["user_id"], "update_defect", "defect", str(defect_id), f"Updated defect {defect_id}"))
    conn.commit()
    conn.close()
    return {"message": "Defect updated"}

@app.delete("/api/admin/defects/{defect_id}")
def admin_delete_defect(defect_id: int, user: dict = Depends(require_admin)):
    conn = get_db()
    conn.execute("DELETE FROM defects WHERE id = ?", (defect_id,))
    conn.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?)",
                 (user["user_id"], "delete_defect", "defect", str(defect_id), f"Deleted defect {defect_id}"))
    conn.commit()
    conn.close()
    return {"message": "Defect deleted"}

# ============================================
# ADMIN - CORRIDOR MANAGEMENT
# ============================================
@app.get("/api/admin/corridors")
def admin_list_corridors(user: dict = Depends(require_auth)):
    conn = get_db()
    rows = conn.execute("""
        SELECT c.*, COUNT(b.id) as block_count,
            SUM(CASE WHEN b.status = 'completed' THEN 1 ELSE 0 END) as completed
        FROM corridors c LEFT JOIN blocks b ON c.id = b.corridor_id GROUP BY c.id
    """).fetchall()
    conn.close()
    return [{"id": r[0], "corridor_id": r[1], "route_name": r[2], "length_km": r[3],
             "status": r[4], "single_line": r[5], "blocks": r[6], "completed": r[7]} for r in rows]

@app.post("/api/admin/corridors")
def admin_create_corridor(corridor: CorridorCreate, user: dict = Depends(require_admin)):
    conn = get_db()
    existing = conn.execute("SELECT id FROM corridors WHERE corridor_id = ?", (corridor.corridor_id,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="Corridor ID already exists")
    conn.execute("INSERT INTO corridors (corridor_id, route_name, length_km, single_line_section) VALUES (?, ?, ?, ?)",
                 (corridor.corridor_id, corridor.route_name, corridor.length_km, corridor.single_line_section))
    conn.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?)",
                 (user["user_id"], "create_corridor", "corridor", corridor.corridor_id, f"Created corridor {corridor.corridor_id}"))
    conn.commit()
    conn.close()
    return {"message": "Corridor created"}

@app.delete("/api/admin/corridors/{corridor_id}")
def admin_delete_corridor(corridor_id: int, user: dict = Depends(require_admin)):
    conn = get_db()
    conn.execute("DELETE FROM corridors WHERE id = ?", (corridor_id,))
    conn.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?)",
                 (user["user_id"], "delete_corridor", "corridor", str(corridor_id), f"Deleted corridor {corridor_id}"))
    conn.commit()
    conn.close()
    return {"message": "Corridor deleted"}

# ============================================
# ADMIN - TRAIN MANAGEMENT
# ============================================
@app.get("/api/admin/trains")
def admin_list_trains(user: dict = Depends(require_auth)):
    conn = get_db()
    rows = conn.execute("SELECT * FROM train_schedule ORDER BY is_vvip DESC, departure_time").fetchall()
    conn.close()
    return [{"id": r[0], "train_number": r[1], "train_name": r[2], "origin": r[3],
             "destination": r[4], "departure_time": r[5], "arrival_time": r[6],
             "days_of_week": r[7], "train_type": r[8], "is_vvip": r[9]} for r in rows]

@app.post("/api/admin/trains")
def admin_create_train(train: TrainCreate, user: dict = Depends(require_auth)):
    conn = get_db()
    existing = conn.execute("SELECT id FROM train_schedule WHERE train_number = ?", (train.train_number,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="Train number already exists")
    conn.execute(
        "INSERT INTO train_schedule (train_number, train_name, origin, destination, departure_time, arrival_time, days_of_week, train_type, is_vvip) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (train.train_number, train.train_name, train.origin, train.destination,
         train.departure_time, train.arrival_time, train.days_of_week, train.train_type, train.is_vvip)
    )
    conn.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?)",
                 (user["user_id"], "create_train", "train", train.train_number, f"Created train {train.train_number}"))
    conn.commit()
    conn.close()
    return {"message": "Train created"}

@app.delete("/api/admin/trains/{train_id}")
def admin_delete_train(train_id: int, user: dict = Depends(require_admin)):
    conn = get_db()
    conn.execute("DELETE FROM train_schedule WHERE id = ?", (train_id,))
    conn.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, details) VALUES (?, ?, ?, ?, ?)",
                 (user["user_id"], "delete_train", "train", str(train_id), f"Deleted train {train_id}"))
    conn.commit()
    conn.close()
    return {"message": "Train deleted"}

# ============================================
# ADMIN - AUDIT LOG
# ============================================
@app.get("/api/admin/audit")
def admin_audit_log(user: dict = Depends(require_admin), limit: int = 50):
    conn = get_db()
    rows = conn.execute("""
        SELECT a.*, u.username, u.full_name
        FROM audit_log a LEFT JOIN users u ON a.user_id = u.id
        ORDER BY a.created_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [{"id": r[0], "user_id": r[1], "action": r[2], "entity_type": r[3],
             "entity_id": r[4], "details": r[5], "created_at": r[6],
             "username": r[7], "full_name": r[8]} for r in rows]

# ============================================
# ADMIN - DASHBOARD STATS
# ============================================
@app.get("/api/admin/stats")
def admin_stats(user: dict = Depends(require_admin)):
    conn = get_db()
    total_blocks = conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0]
    active_blocks = conn.execute("SELECT COUNT(*) FROM blocks WHERE status IN ('planned', 'approved', 'in_progress')").fetchone()[0]
    pending_defects = conn.execute("SELECT COUNT(*) FROM defects WHERE status = 'pending'").fetchone()[0]
    critical_defects = conn.execute("SELECT COUNT(*) FROM defects WHERE priority = 'critical' AND status = 'pending'").fetchone()[0]
    total_users = conn.execute("SELECT COUNT(*) FROM users WHERE is_active = 1").fetchone()[0]
    total_trains = conn.execute("SELECT COUNT(*) FROM train_schedule").fetchone()[0]
    total_corridors = conn.execute("SELECT COUNT(*) FROM corridors").fetchone()[0]
    completed_blocks = conn.execute("SELECT COUNT(*) FROM blocks WHERE status = 'completed'").fetchone()[0]
    recent_audit = conn.execute("SELECT COUNT(*) FROM audit_log WHERE created_at > ?", ((datetime.now() - timedelta(hours=24)).isoformat(),)).fetchone()[0]
    conn.close()
    return {
        "total_blocks": total_blocks, "active_blocks": active_blocks,
        "pending_defects": pending_defects, "critical_defects": critical_defects,
        "total_users": total_users, "total_trains": total_trains,
        "total_corridors": total_corridors, "completed_blocks": completed_blocks,
        "recent_audit_actions": recent_audit
    }

# ============================================
# PUBLIC API ENDPOINTS (no auth required)
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
        FROM departments d LEFT JOIN blocks b ON d.id = b.department_id GROUP BY d.id
    """).fetchall()
    corridor_stats = c.execute("""
        SELECT c.corridor_id, c.route_name, c.length_km,
            COUNT(b.id) as blocks,
            SUM(CASE WHEN b.status != 'cancelled' THEN 1 ELSE 0 END) as active_blocks
        FROM corridors c LEFT JOIN blocks b ON c.id = b.corridor_id GROUP BY c.id
    """).fetchall()
    recommendations = c.execute("SELECT * FROM ai_recommendations ORDER BY impact_score DESC LIMIT 5").fetchall()
    token_locked = c.execute("SELECT COUNT(*) FROM token_locks WHERE status = 'locked'").fetchone()[0]
    crew_violations = c.execute("SELECT COUNT(*) FROM crew_duty WHERE status = 'violation'").fetchone()[0]
    active_emergencies = c.execute("SELECT COUNT(*) FROM emergency_push WHERE status = 'active'").fetchone()[0]
    conn.close()
    return {
        "total_blocks": total_blocks, "active_blocks": active_blocks,
        "pending_defects": pending_defects, "critical_defects": critical_defects,
        "urgent_defects": urgent_defects,
        "asset_availability": round(85 + random.uniform(0, 10), 1),
        "ai_efficiency": round(90 + random.uniform(0, 8), 1),
        "departments": [{"name": r[0], "code": r[1], "color": r[2], "blocks": r[3]} for r in dept_stats],
        "corridors": [{"id": r[0], "route": r[1], "length": r[2], "blocks": r[3], "active": r[4]} for r in corridor_stats],
        "recommendations": [{"id": r[0], "type": r[1], "title": r[2], "description": r[3], "score": r[4]} for r in recommendations],
        "token_locked": token_locked, "crew_violations": crew_violations, "active_emergencies": active_emergencies
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
    query = "SELECT d.*, dep.name as dept_name, dep.code as dept_code, dep.color as dept_color FROM defects d JOIN departments dep ON d.department_id = dep.id WHERE 1=1"
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

@app.get("/api/blocks")
def get_blocks(start_date: str = None, end_date: str = None, department: str = "all"):
    conn = get_db()
    query = """SELECT b.*, dep.name as dept_name, dep.code as dept_code, dep.color as dept_color,
               c.route_name, c.corridor_id FROM blocks b
               JOIN departments dep ON b.department_id = dep.id
               LEFT JOIN corridors c ON b.corridor_id = c.id WHERE 1=1"""
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
                    recommendations.append({"type": "merge", "title": f"Merge blocks on corridor {key[0]}", "description": f"Combine blocks to save {saved} hours", "impact": 85 + random.uniform(0, 10)})
    recommendations.append({"type": "reschedule", "title": "Reschedule to Night Window (01:00-04:00)", "description": "Move non-critical maintenance to night slots for zero train impact", "impact": 90})
    current_efficiency = 62 + random.uniform(0, 5)
    optimized_efficiency = min(95, current_efficiency + 25 + random.uniform(0, 5))
    projected_uptime = min(98, optimized_efficiency + 5)
    conn.close()
    return {"current_efficiency": round(current_efficiency, 1), "optimized_efficiency": round(optimized_efficiency, 1),
            "projected_uptime": round(projected_uptime, 1), "blocks_merged": blocks_merged,
            "downtime_saved_hours": total_downtime_saved, "recommendations": recommendations[:10]}

@app.get("/api/ai/generate-plan")
def generate_ai_plan(week_offset: int = 0):
    conn = get_db()
    today = datetime.now().date() + timedelta(weeks=week_offset)
    start_of_week = today - timedelta(days=today.weekday())
    corridors = conn.execute("SELECT * FROM corridors").fetchall()
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
                    day_blocks.append({"block_id": f"BLK-{random.randint(1000,9999)}", "corridor": corridor[2],
                        "department": dept_names[dept], "color": dept_colors[dept], "start": slot[0], "end": slot[1],
                        "type": random.choice(["Track Renewal", "OHE Maintenance", "Signal Check", "Point Machine"]),
                        "category": cat, "ai_score": round(random.uniform(70, 98), 1)})
                    break
        plan.append({"date": current_date.isoformat(), "day_name": current_date.strftime("%A"), "blocks": day_blocks})
    conn.close()
    return {"week_start": start_of_week.isoformat(), "plan": plan, "total_blocks": sum(len(day["blocks"]) for day in plan)}

@app.get("/api/maintenance/engine")
def get_maintenance_engine():
    conn = get_db()
    defects = conn.execute("SELECT d.*, dep.name as dept_name, dep.code as dept_code FROM defects d JOIN departments dep ON d.department_id = dep.id WHERE d.status = 'pending'").fetchall()
    categories = {"routine": [], "fault": [], "urgent": []}
    for d in defects:
        cat = d[7] or 'fault'
        item = {"id": d[0], "defect_id": d[1], "title": d[3], "description": d[4], "location": d[5], "priority": d[6], "maintenance_type": cat, "dept_name": d[10], "dept_code": d[11]}
        if cat in categories:
            categories[cat].append(item)
    rules = {"routine": {"description": "Can be split across multiple time windows.", "sla_hours": 168, "can_split": True, "requires_block": True, "auto_schedule": True},
             "fault": {"description": "Must be fixed within 24 hours. Cannot be split.", "sla_hours": 24, "can_split": False, "requires_block": True, "auto_schedule": False},
             "urgent": {"description": "Immediate emergency override. Triggers critical push.", "sla_hours": 4, "can_split": False, "requires_block": True, "auto_schedule": False, "emergency_override": True}}
    conn.close()
    return {"categories": {"routine": {"count": len(categories["routine"]), "items": categories["routine"]}, "fault": {"count": len(categories["fault"]), "items": categories["fault"]}, "urgent": {"count": len(categories["urgent"]), "items": categories["urgent"]}}, "rules": rules, "total_pending": len(defects)}

@app.get("/api/token/locks")
def get_token_locks():
    conn = get_db()
    rows = conn.execute("SELECT tl.*, c.route_name FROM token_locks tl JOIN corridors c ON tl.corridor_id = c.id ORDER BY c.route_name, tl.direction").fetchall()
    conn.close()
    return [{"id": r[0], "corridor_id": r[1], "section": r[2], "direction": r[3], "token": r[4], "locked_by": r[5], "lock_time": r[6], "status": r[7], "route_name": r[8]} for r in rows]

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
        result.append({"id": r[0], "crew_id": r[1], "name": r[2], "role": r[3], "duty_start": r[4], "duty_end": r[5],
                       "hours_worked": hours_worked, "max_hours": max_hours, "status": r[8], "current_train": r[9],
                       "section": r[10], "remaining_hours": round(remaining, 1), "hoer_compliant": remaining > 0})
    violations = [x for x in result if not x["hoer_compliant"]]
    at_risk = [x for x in result if 0 < x["remaining_hours"] <= 1]
    return {"crew": result, "total_violations": len(violations), "at_risk_count": len(at_risk), "violations": violations, "at_risk": at_risk}

@app.get("/api/emergency/pushes")
def get_emergency_pushes():
    conn = get_db()
    rows = conn.execute("SELECT * FROM emergency_push ORDER BY delay_hours DESC").fetchall()
    conn.close()
    return [{"id": r[0], "train_number": r[1], "train_name": r[2], "delay_hours": r[3], "type": r[4], "triggered_at": r[5], "status": r[6], "description": r[7]} for r in rows]

@app.get("/api/emergency/vvip-status")
def get_vvip_status():
    conn = get_db()
    vvip_trains = conn.execute("SELECT * FROM train_schedule WHERE is_vvip = 1").fetchall()
    corridors = conn.execute("SELECT * FROM corridors WHERE single_line_section = 1").fetchall()
    protection_rules = []
    for t in vvip_trains:
        for c in corridors:
            protection_rules.append({"train": t[1], "train_name": t[2], "corridor": c[2], "route_name": c[3],
                "rule": f"Rajdhani/special train {t[1]} must pass through {c[3]} without any maintenance block",
                "action": "Auto-reschedule any planned blocks in the 2-hour window around train passage"})
    conn.close()
    return {"vvip_trains": [{"number": t[1], "name": t[2], "origin": t[3], "destination": t[4]} for t in vvip_trains], "protection_rules": protection_rules[:10]}

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
    monthly_stats = conn.execute("SELECT strftime('%Y-%m', block_date) as month, COUNT(*) as blocks FROM blocks GROUP BY month ORDER BY month DESC LIMIT 6").fetchall()
    conn.close()
    return {"departments": [{"name": r[0], "color": r[1], "total": r[2], "completed": r[3], "planned": r[4], "avg_score": round(r[5] or 0, 1)} for r in dept_summary],
            "defects_by_priority": [{"priority": r[0], "count": r[1]} for r in defect_summary],
            "monthly_blocks": [{"month": r[0], "count": r[1]} for r in monthly_stats]}

# Serve static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
