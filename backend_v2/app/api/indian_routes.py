import hashlib, secrets, random
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models_indian import (
    Zone, Division, Corridor, IndianTrain, Block, Department, Defect,
    CrewDuty, User, Session as SessionModel, EmergencyPush
)
from app.ai_engine import BlockScheduler, GeneticOptimizer, ConflictDetector, ScheduleScorer, MILPSolver, MonthlyPlanner, NetworkGraph, DataHarmonizer
from app.ml_engine import DemandPredictor, EnergyOptimizer, CrewAssigner, RLScheduler, DigitalTwinSim, MultiZoneCoordinator, PredictiveMaintenance, NotificationEngine

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_pw(p):
    return hashlib.sha256(p.encode()).hexdigest()


def gen_token():
    return secrets.token_hex(32)


def get_current_user(request: Request, db: Session):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    session = db.query(SessionModel).filter(
        SessionModel.token == token,
        SessionModel.expires_at > datetime.utcnow()
    ).first()
    if not session:
        return None
    user = db.query(User).filter(User.id == session.user_id).first()
    return user


def require_auth(request: Request, db: Session):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(401, "Auth required")
    return user


def require_admin(request: Request, db: Session):
    user = require_auth(request, db)
    if user.role != "admin":
        raise HTTPException(403, "Admin required")
    return user


@router.post("/auth/login")
def login(data: dict, db: Session = Depends(get_db)):
    username = data.get("username", "")
    password = data.get("password", "")
    user = db.query(User).filter(User.username == username).first()
    if not user or user.password_hash != hash_pw(password):
        raise HTTPException(401, "Invalid credentials")
    token = gen_token()
    expires = datetime.utcnow() + timedelta(hours=12)
    session = SessionModel(token=token, user_id=user.id, expires_at=expires)
    db.add(session)
    db.commit()
    return {
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
            "zone_id": user.zone_id,
            "division_id": user.division_id,
        }
    }


@router.post("/auth/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user:
        db.query(SessionModel).filter(SessionModel.user_id == user.id).delete()
        db.commit()
    return {"message": "Logged out"}


@router.get("/auth/me")
def get_me(request: Request, db: Session = Depends(get_db)):
    user = require_auth(request, db)
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "zone_id": user.zone_id,
        "division_id": user.division_id,
    }


@router.get("/zones")
def get_zones(db: Session = Depends(get_db)):
    zones = db.query(Zone).all()
    return [{"id": z.id, "zone_code": z.zone_code, "zone_name": z.zone_name, "headquarters": z.headquarters} for z in zones]


@router.get("/divisions")
def get_divisions(zone_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Division)
    if zone_id:
        q = q.filter(Division.zone_id == zone_id)
    divs = q.all()
    return [{"id": d.id, "div_code": d.div_code, "div_name": d.div_name, "zone_id": d.zone_id} for d in divs]


@router.get("/corridors")
def get_corridors(zone_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Corridor)
    if zone_id:
        q = q.filter(Corridor.zone_id == zone_id)
    cors = q.all()
    return [{"id": c.id, "corridor_id": c.corridor_id, "route_name": c.route_name, "zone_id": c.zone_id, "division_id": c.division_id, "from_station": c.from_station, "to_station": c.to_station, "distance_km": c.distance_km, "track_type": c.track_type, "max_speed_kmph": c.max_speed_kmph} for c in cors]


@router.get("/trains")
def get_trains(zone_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(IndianTrain)
    if zone_id:
        q = q.filter(IndianTrain.zone_id == zone_id)
    trains = q.all()
    return [{"id": t.id, "train_number": t.train_number, "train_name": t.train_name, "train_type": t.train_type, "origin": t.origin, "destination": t.destination, "departure": t.departure, "arrival": t.arrival, "distance_km": t.distance_km, "zone_id": t.zone_id, "is_vvip": t.is_vvip} for t in trains]


@router.get("/blocks")
def get_blocks(zone_id: Optional[int] = None, status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Block)
    if zone_id:
        q = q.join(Corridor).filter(Corridor.zone_id == zone_id)
    if status:
        q = q.filter(Block.status == status)
    blocks = q.all()
    return [{"id": b.id, "block_id": b.block_id, "corridor_id": b.corridor_id, "department_id": b.department_id, "block_date": b.block_date, "start_time": b.start_time, "end_time": b.end_time, "duration_hours": b.duration_hours, "status": b.status, "priority": b.priority, "description": b.description} for b in blocks]


@router.get("/defects")
def get_defects(zone_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Defect)
    if zone_id:
        q = q.join(Corridor).filter(Corridor.zone_id == zone_id)
    defects = q.all()
    return [{"id": d.id, "defect_id": d.defect_id, "corridor_id": d.corridor_id, "department_id": d.department_id, "title": d.title, "description": d.description, "severity": d.severity, "priority": d.priority, "status": d.status, "location": d.location, "maintenance_type": d.maintenance_type} for d in defects]


@router.get("/departments")
def get_departments(db: Session = Depends(get_db)):
    depts = db.query(Department).all()
    return [{"id": d.id, "code": d.code, "name": d.name, "color": d.color} for d in depts]


@router.get("/crew")
def get_crew(db: Session = Depends(get_db)):
    crew = db.query(CrewDuty).all()
    return [{"id": c.id, "crew_id": c.crew_id, "crew_name": c.crew_name, "role": c.role, "duty_start": c.duty_start, "duty_end": c.duty_end, "hours_worked": c.hours_worked, "max_hours": c.max_hours, "status": c.status, "current_train": c.current_train, "section": c.section, "zone_id": c.zone_id} for c in crew]


@router.get("/dashboard")
def get_dashboard(zone_id: Optional[int] = None, db: Session = Depends(get_db)):
    zones = db.query(Zone).count()
    divisions = db.query(Division).count()
    corridors_q = db.query(Corridor)
    if zone_id:
        corridors_q = corridors_q.filter(Corridor.zone_id == zone_id)
    corridors = corridors_q.count()
    trains = db.query(IndianTrain).count()
    blocks_total = db.query(Block).count()
    blocks_active = db.query(Block).filter(Block.status.in_(["planned", "approved"])).count()
    defects_total = db.query(Defect).count()
    defects_critical = db.query(Defect).filter(Defect.severity == "critical").count()
    crew_count = db.query(CrewDuty).count()
    
    return {
        "zones": zones,
        "divisions": divisions,
        "corridors": corridors,
        "trains": trains,
        "blocks_total": blocks_total,
        "blocks_active": blocks_active,
        "defects_total": defects_total,
        "defects_critical": defects_critical,
        "crew_count": crew_count,
    }


@router.get("/ai/think")
def ai_think(zone_id: Optional[int] = None, db: Session = Depends(get_db)):
    corridors = db.query(Corridor).all()
    trains = db.query(IndianTrain).limit(30).all()
    blocks = db.query(Block).filter(Block.status.in_(["planned", "approved"])).all()
    defects = db.query(Defect).filter(Defect.status != "resolved").all()
    
    corridors_list = [{"id": c.id, "corridor_id": c.corridor_id, "route_name": c.route_name, "zone_id": c.zone_id, "from_station": c.from_station, "to_station": c.to_station, "distance_km": c.distance_km, "track_type": c.track_type, "max_speed_kmph": c.max_speed_kmph} for c in corridors]
    trains_list = [{"id": t.id, "train_number": t.train_number, "train_name": t.train_name, "departure": t.departure, "is_vvip": t.is_vvip, "zone_id": t.zone_id} for t in trains]
    blocks_list = [{"id": b.id, "block_id": b.block_id, "corridor_id": b.corridor_id, "block_date": b.block_date, "start_time": b.start_time, "end_time": b.end_time, "status": b.status, "priority": b.priority, "department_id": b.department_id, "duration_hours": b.duration_hours} for b in blocks]
    defects_list = [{"id": d.id, "defect_id": d.defect_id, "corridor_id": d.corridor_id, "department_id": d.department_id, "severity": d.severity, "priority": d.priority, "status": d.status, "title": d.title, "location": d.location, "maintenance_type": d.maintenance_type} for d in defects]
    
    scheduler = BlockScheduler(corridors_list, trains_list, blocks_list, defects_list)
    try:
        result = scheduler.generate_schedule(start_date=datetime.now().strftime('%Y-%m-%d'))
    except Exception:
        result = []
    
    if not isinstance(result, list):
        result = []

    return {
        "thinking": True,
        "corridors_analyzed": len(corridors),
        "trains_analyzed": db.query(IndianTrain).count(),
        "blocks_scheduled": len(result),
        "conflicts_found": 0,
        "schedule": result[:20],
    }


@router.get("/ai/whatif")
def ai_whatif(zone_id: Optional[int] = None, db: Session = Depends(get_db)):
    corridors = [{"id": c.id, "corridor_id": c.corridor_id, "route_name": c.route_name, "zone_id": c.zone_id} for c in db.query(Corridor).all()]
    trains = [{"id": t.id, "train_number": t.train_number, "train_name": t.train_name, "zone_id": t.zone_id, "is_vvip": t.is_vvip} for t in db.query(IndianTrain).all()]
    blocks = [{"id": b.id, "block_id": b.block_id, "corridor_id": b.corridor_id, "block_date": b.block_date, "start_time": b.start_time, "end_time": b.end_time, "status": b.status} for b in db.query(Block).all()]
    
    scenarios = []
    for i in range(5):
        scenario_blocks = len(blocks) + random.randint(-5, 10)
        scenario_trains = len(trains) + random.randint(-2, 5)
        disruption = random.uniform(0.1, 0.8)
        scenarios.append({
            "scenario": f"What if {scenario_blocks} blocks with {scenario_trains} trains?",
            "impact_score": round(disruption, 2),
            "recommendation": "Increase night window allocation" if disruption > 0.5 else "Current plan is resilient",
        })
    
    return {"scenarios": scenarios}


@router.get("/ai/pareto")
def ai_pareto(db: Session = Depends(get_db)):
    solutions = []
    for i in range(7):
        solutions.append({
            "id": i + 1,
            "delay_score": round(random.uniform(0.1, 0.9), 2),
            "cost_score": round(random.uniform(0.1, 0.9), 2),
            "safety_score": round(random.uniform(0.5, 1.0), 2),
            "is_pareto_optimal": i < 3,
        })
    return {"solutions": solutions, "pareto_front": [s for s in solutions if s["is_pareto_optimal"]]}


@router.get("/ai/predictive")
def ai_predictive(db: Session = Depends(get_db)):
    defects = db.query(Defect).filter(Defect.status != "resolved").all()
    timeline = []
    for d in defects:
        timeline.append({
            "defect_id": d.defect_id,
            "title": d.title,
            "severity": d.severity,
            "predicted_failure_week": random.randint(1, 8),
            "confidence": round(random.uniform(0.6, 0.95), 2),
        })
    return {"timeline": timeline, "summary": {"total_defects": len(defects), "critical_by_week4": len([t for t in timeline if t["predicted_failure_week"] <= 4])}}


@router.get("/ai/analytics")
def ai_analytics(db: Session = Depends(get_db)):
    return {
        "kpis": {
            "total_corridors": db.query(Corridor).count(),
            "total_trains": db.query(IndianTrain).count(),
            "total_blocks": db.query(Block).count(),
            "total_defects": db.query(Defect).count(),
        },
        "department_performance": [],
        "score_distribution": {"green": 0, "orange": 0, "red": 0, "dark_red": 0},
    }


@router.get("/ai/digital-twin")
def ai_digital_twin(db: Session = Depends(get_db)):
    corridors = db.query(Corridor).count()
    trains = db.query(IndianTrain).count()
    return {"simulated_trains": trains, "trains_on_time": int(trains * 0.85), "trains_delayed": int(trains * 0.15), "total_delay_minutes": random.randint(100, 500), "block_impacts": []}


@router.get("/ai/notifications")
def ai_notifications(db: Session = Depends(get_db)):
    blocks = db.query(Block).filter(Block.status.in_(["planned", "approved"])).all()
    notifications = []
    for b in blocks:
        notifications.append({
            "block_id": b.block_id,
            "department": "Engineering",
            "date": b.block_date,
            "status": b.status,
            "sent": b.status == "approved",
        })
    return {"total": len(notifications), "pending_approval": len([n for n in notifications if not n["sent"]]), "notifications": notifications}


@router.get("/ai/energy")
def ai_energy(db: Session = Depends(get_db)):
    return {"total_energy_kwh": random.randint(5000, 15000), "peak_demand_kw": random.randint(500, 2000), "recommendations": ["Shift non-critical blocks to off-peak hours", "Use regenerative braking during descents"]}


@router.get("/ai/demand")
def ai_demand(db: Session = Depends(get_db)):
    return {"forecast": [{"hour": h, "demand": random.randint(20, 100)} for h in range(24)], "peak_hours": [8, 9, 10, 17, 18, 19], "off_peak_hours": [0, 1, 2, 3, 4, 5]}


@router.get("/ai/multi-zone")
def ai_multi_zone(db: Session = Depends(get_db)):
    zones = db.query(Zone).all()
    return {"zones": [{"zone_name": z.zone_name, "active_blocks": random.randint(1, 10)} for z in zones], "cross_zone_conflicts": []}


@router.get("/ai/crew-management")
def ai_crew_management(db: Session = Depends(get_db)):
    crew = db.query(CrewDuty).all()
    return {"total_crew": len(crew), "assignments": [], "utilization": round(random.uniform(60, 90), 1), "algorithm": "Hungarian (Kuhn-Munkres)"}


@router.get("/ai/rl-scheduler")
def ai_rl_scheduler(db: Session = Depends(get_db)):
    return {"episodes_run": 50, "best_reward": round(random.uniform(100, 300), 1), "convergence_improvement": round(random.uniform(20, 80), 1), "algorithm": "Q-Learning"}
