from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Zone(Base):
    __tablename__ = "zones"
    id = Column(Integer, primary_key=True, index=True)
    zone_code = Column(String(10), unique=True, nullable=False)
    zone_name = Column(String(100), nullable=False)
    headquarters = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Division(Base):
    __tablename__ = "divisions"
    id = Column(Integer, primary_key=True, index=True)
    div_code = Column(String(10), unique=True, nullable=False)
    div_name = Column(String(100), nullable=False)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=False)
    zone = relationship("Zone")


class Corridor(Base):
    __tablename__ = "corridors"
    id = Column(Integer, primary_key=True, index=True)
    corridor_id = Column(String(20), unique=True, nullable=False)
    route_name = Column(String(200), nullable=False)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=False)
    division_id = Column(Integer, ForeignKey("divisions.id"), nullable=True)
    from_station = Column(String(100))
    to_station = Column(String(100))
    distance_km = Column(Float, default=0)
    track_type = Column(String(50), default="single")
    max_speed_kmph = Column(Integer, default=110)
    zone = relationship("Zone")
    division = relationship("Division")


class IndianTrain(Base):
    __tablename__ = "indian_trains"
    id = Column(Integer, primary_key=True, index=True)
    train_number = Column(String(10), unique=True, nullable=False)
    train_name = Column(String(200), nullable=False)
    train_type = Column(String(50))
    origin = Column(String(100))
    destination = Column(String(100))
    departure = Column(String(10))
    arrival = Column(String(10))
    distance_km = Column(Float, default=0)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=True)
    is_vvip = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Block(Base):
    __tablename__ = "blocks"
    id = Column(Integer, primary_key=True, index=True)
    block_id = Column(String(20), unique=True, nullable=False)
    corridor_id = Column(Integer, ForeignKey("corridors.id"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    block_date = Column(String(20), nullable=False)
    start_time = Column(String(10), nullable=False)
    end_time = Column(String(10), nullable=False)
    duration_hours = Column(Float, default=3)
    status = Column(String(20), default="planned")
    priority = Column(String(20), default="medium")
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    corridor = relationship("Corridor")
    department = relationship("Department")


class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(10), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    color = Column(String(20), default="#3B82F6")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Defect(Base):
    __tablename__ = "defects"
    id = Column(Integer, primary_key=True, index=True)
    defect_id = Column(String(20), unique=True, nullable=False)
    corridor_id = Column(Integer, ForeignKey("corridors.id"), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    severity = Column(String(20), default="medium")
    priority = Column(String(20), default="medium")
    status = Column(String(20), default="pending")
    location = Column(String(200))
    maintenance_type = Column(String(50), default="routine")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    corridor = relationship("Corridor")
    department = relationship("Department")


class CrewDuty(Base):
    __tablename__ = "crew_duty"
    id = Column(Integer, primary_key=True, index=True)
    crew_id = Column(String(20), unique=True, nullable=False)
    crew_name = Column(String(100), nullable=False)
    role = Column(String(50))
    duty_start = Column(String(20))
    duty_end = Column(String(20))
    hours_worked = Column(Float, default=0)
    max_hours = Column(Float, default=12)
    status = Column(String(20), default="available")
    current_train = Column(String(50))
    section = Column(String(100))
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=True)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    full_name = Column(String(100))
    role = Column(String(20), default="engineer")
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=True)
    division_id = Column(Integer, ForeignKey("divisions.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(64), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User")


class EmergencyPush(Base):
    __tablename__ = "emergency_pushes"
    id = Column(Integer, primary_key=True, index=True)
    push_id = Column(String(20), unique=True, nullable=False)
    corridor_id = Column(Integer, ForeignKey("corridors.id"), nullable=True)
    reason = Column(String(200))
    priority = Column(String(20), default="high")
    status = Column(String(20), default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
