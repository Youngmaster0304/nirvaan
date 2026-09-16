from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Enum, Boolean, Text, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum
from datetime import datetime
from typing import Optional


class HealthStatus(str, enum.Enum):
    GREEN = "Green"
    ORANGE = "Orange"
    RED = "Red"
    DARK_RED = "Dark Red"


class TaskUrgency(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class FailureType(str, enum.Enum):
    TRACK_FRACTURE = "Track Fracture"
    OHE_FAILURE = "OHE Failure"
    SIGNAL_FAILURE = "Signal Failure"
    POINTS_FAILURE = "Points Failure"
    TRACK_CIRCUIT_FAILURE = "Track Circuit Failure"
    EARTHWORK_SLIP = "Earthwork Slip"
    BRIDGE_ISSUE = "Bridge Issue"
    LEVEL_CROSSING = "Level Crossing Issue"


class ResponseTeamType(str, enum.Enum):
    TRACK_ENGINEERING = "Track Engineering"
    SIGNAL_TELECOM = "Signal & Telecom"
    OHE = "OHE"
    BRIDGE = "Bridge"
    TOWER_WAGON = "Tower Wagon"
    CRANE = "Crane"
    EMERGENCY_RELIEF = "Emergency Relief Train"


class TrackSegment(Base):
    __tablename__ = "track_segments"

    id = Column(Integer, primary_key=True, index=True)
    segment_code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    start_station = Column(String(100), nullable=False)
    end_station = Column(String(100), nullable=False)
    length_km = Column(Float, nullable=False)
    capacity_trains_per_hour = Column(Integer, default=20)
    current_health_score = Column(Float, default=1.0)
    health_status = Column(Enum(HealthStatus), default=HealthStatus.GREEN)
    gmt_load = Column(Float, default=0.0)
    latitude_start = Column(Float, nullable=False)
    longitude_start = Column(Float, nullable=False)
    latitude_end = Column(Float, nullable=False)
    longitude_end = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    maintenance_tasks = relationship("MaintenanceTask", back_populates="track_segment")
    train_schedules = relationship("TrainSchedule", back_populates="track_segment")

    __table_args__ = (
        Index("idx_track_segment_health", "health_status"),
        Index("idx_track_segment_location", "latitude_start", "longitude_start"),
    )


class MaintenanceTask(Base):
    __tablename__ = "maintenance_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_code = Column(String(50), unique=True, index=True, nullable=False)
    track_segment_id = Column(Integer, ForeignKey("track_segments.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    urgency = Column(Enum(TaskUrgency), default=TaskUrgency.MEDIUM)
    required_team_type = Column(Enum(ResponseTeamType), nullable=False)
    estimated_duration_hours = Column(Float, nullable=False)
    required_personnel = Column(Integer, default=5)
    scheduled_start = Column(DateTime(timezone=True), nullable=True)
    scheduled_end = Column(DateTime(timezone=True), nullable=True)
    actual_start = Column(DateTime(timezone=True), nullable=True)
    actual_end = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), default="Planned")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    track_segment = relationship("TrackSegment", back_populates="maintenance_tasks")


class Train(Base):
    __tablename__ = "trains"

    id = Column(Integer, primary_key=True, index=True)
    train_number = Column(String(20), unique=True, index=True, nullable=False)
    train_name = Column(String(200))
    train_type = Column(String(50))
    max_speed_kmph = Column(Integer, default=110)
    length_meters = Column(Integer, default=500)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    schedules = relationship("TrainSchedule", back_populates="train")


class TrainSchedule(Base):
    __tablename__ = "train_schedules"

    id = Column(Integer, primary_key=True, index=True)
    train_id = Column(Integer, ForeignKey("trains.id"), nullable=False)
    track_segment_id = Column(Integer, ForeignKey("track_segments.id"), nullable=False)
    sequence_order = Column(Integer, nullable=False)
    scheduled_arrival = Column(DateTime(timezone=True), nullable=False)
    scheduled_departure = Column(DateTime(timezone=True), nullable=False)
    actual_arrival = Column(DateTime(timezone=True), nullable=True)
    actual_departure = Column(DateTime(timezone=True), nullable=True)
    current_latitude = Column(Float, nullable=True)
    current_longitude = Column(Float, nullable=True)
    current_speed_kmph = Column(Float, default=0.0)
    is_running = Column(Boolean, default=False)
    delay_minutes = Column(Integer, default=0)

    train = relationship("Train", back_populates="schedules")
    track_segment = relationship("TrackSegment", back_populates="train_schedules")

    __table_args__ = (
        Index("idx_schedule_time", "scheduled_arrival", "scheduled_departure"),
        Index("idx_schedule_segment_time", "track_segment_id", "scheduled_arrival"),
    )


class Junction(Base):
    __tablename__ = "junctions"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    station_type = Column(String(50))
    is_active = Column(Boolean, default=True)


class TrackConnection(Base):
    __tablename__ = "track_connections"

    id = Column(Integer, primary_key=True, index=True)
    from_junction_id = Column(Integer, ForeignKey("junctions.id"), nullable=False)
    to_junction_id = Column(Integer, ForeignKey("junctions.id"), nullable=False)
    track_segment_id = Column(Integer, ForeignKey("track_segments.id"), nullable=False)
    distance_km = Column(Float, nullable=False)
    max_speed_kmph = Column(Integer, default=110)
    is_bidirectional = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)

    from_junction = relationship("Junction", foreign_keys=[from_junction_id])
    to_junction = relationship("Junction", foreign_keys=[to_junction_id])
    track_segment = relationship("TrackSegment")

    __table_args__ = (
        Index("idx_connection_from", "from_junction_id"),
        Index("idx_connection_to", "to_junction_id"),
    )


class ResponseTeam(Base):
    __tablename__ = "response_teams"

    id = Column(Integer, primary_key=True, index=True)
    team_code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    team_type = Column(Enum(ResponseTeamType), nullable=False)
    base_station = Column(String(100), nullable=False)
    base_latitude = Column(Float, nullable=False)
    base_longitude = Column(Float, nullable=False)
    contact_number = Column(String(20))
    contact_person = Column(String(100))
    is_available = Column(Boolean, default=True)
    current_latitude = Column(Float, nullable=True)
    current_longitude = Column(Float, nullable=True)
    last_updated = Column(DateTime(timezone=True), onupdate=func.now())


class EmergencyAlert(Base):
    __tablename__ = "emergency_alerts"

    id = Column(Integer, primary_key=True, index=True)
    alert_code = Column(String(50), unique=True, index=True, nullable=False)
    track_segment_id = Column(Integer, ForeignKey("track_segments.id"), nullable=False)
    failure_type = Column(Enum(FailureType), nullable=False)
    description = Column(Text)
    severity = Column(Enum(TaskUrgency), default=TaskUrgency.CRITICAL)
    reported_at = Column(DateTime(timezone=True), server_default=func.now())
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), default="Active")
    assigned_team_id = Column(Integer, ForeignKey("response_teams.id"), nullable=True)

    track_segment = relationship("TrackSegment")
    assigned_team = relationship("ResponseTeam")


class SensorData(Base):
    __tablename__ = "sensor_data"

    id = Column(Integer, primary_key=True, index=True)
    track_segment_id = Column(Integer, ForeignKey("track_segments.id"), nullable=False)
    sensor_type = Column(String(50), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(20))
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())
    location_km = Column(Float, nullable=True)

    track_segment = relationship("TrackSegment")

    __table_args__ = (
        Index("idx_sensor_segment_time", "track_segment_id", "recorded_at"),
    )


class InspectionLog(Base):
    __tablename__ = "inspection_logs"

    id = Column(Integer, primary_key=True, index=True)
    track_segment_id = Column(Integer, ForeignKey("track_segments.id"), nullable=False)
    inspector_name = Column(String(100))
    inspection_date = Column(DateTime(timezone=True), nullable=False)
    findings = Column(Text)
    severity_score = Column(Float, default=0.0)
    recommended_action = Column(Text)

    track_segment = relationship("TrackSegment")

    __table_args__ = (
        Index("idx_inspection_segment_date", "track_segment_id", "inspection_date"),
    )