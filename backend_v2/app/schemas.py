from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from app.models import HealthStatus, TaskUrgency, FailureType, ResponseTeamType


class TrackSegmentBase(BaseModel):
    segment_code: str
    name: str
    start_station: str
    end_station: str
    length_km: float
    capacity_trains_per_hour: int = 20
    latitude_start: float
    longitude_start: float
    latitude_end: float
    longitude_end: float


class TrackSegmentCreate(TrackSegmentBase):
    gmt_load: float = 0.0


class TrackSegmentUpdate(BaseModel):
    name: Optional[str] = None
    capacity_trains_per_hour: Optional[int] = None
    current_health_score: Optional[float] = None
    health_status: Optional[HealthStatus] = None
    gmt_load: Optional[float] = None
    is_active: Optional[bool] = None


class TrackSegmentResponse(TrackSegmentBase):
    id: int
    current_health_score: float
    health_status: HealthStatus
    gmt_load: float
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MaintenanceTaskBase(BaseModel):
    task_code: str
    track_segment_id: int
    title: str
    description: Optional[str] = None
    urgency: TaskUrgency = TaskUrgency.MEDIUM
    required_team_type: ResponseTeamType
    estimated_duration_hours: float
    required_personnel: int = 5


class MaintenanceTaskCreate(MaintenanceTaskBase):
    pass


class MaintenanceTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    urgency: Optional[TaskUrgency] = None
    required_team_type: Optional[ResponseTeamType] = None
    estimated_duration_hours: Optional[float] = None
    required_personnel: Optional[int] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    status: Optional[str] = None


class MaintenanceTaskResponse(MaintenanceTaskBase):
    id: int
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TrainBase(BaseModel):
    train_number: str
    train_name: Optional[str] = None
    train_type: Optional[str] = None
    max_speed_kmph: int = 110
    length_meters: int = 500


class TrainCreate(TrainBase):
    pass


class TrainResponse(TrainBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TrainScheduleBase(BaseModel):
    train_id: int
    track_segment_id: int
    sequence_order: int
    scheduled_arrival: datetime
    scheduled_departure: datetime


class TrainScheduleCreate(TrainScheduleBase):
    pass


class TrainScheduleResponse(TrainScheduleBase):
    id: int
    actual_arrival: Optional[datetime] = None
    actual_departure: Optional[datetime] = None
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    current_speed_kmph: float
    is_running: bool
    delay_minutes: int

    class Config:
        from_attributes = True


class JunctionBase(BaseModel):
    code: str
    name: str
    latitude: float
    longitude: float
    station_type: Optional[str] = None


class JunctionCreate(JunctionBase):
    pass


class JunctionResponse(JunctionBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class TrackConnectionBase(BaseModel):
    from_junction_id: int
    to_junction_id: int
    track_segment_id: int
    distance_km: float
    max_speed_kmph: int = 110
    is_bidirectional: bool = True


class TrackConnectionCreate(TrackConnectionBase):
    pass


class TrackConnectionResponse(TrackConnectionBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class ResponseTeamBase(BaseModel):
    team_code: str
    name: str
    team_type: ResponseTeamType
    base_station: str
    base_latitude: float
    base_longitude: float
    contact_number: Optional[str] = None
    contact_person: Optional[str] = None


class ResponseTeamCreate(ResponseTeamBase):
    pass


class ResponseTeamResponse(ResponseTeamBase):
    id: int
    is_available: bool
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    last_updated: Optional[datetime] = None

    class Config:
        from_attributes = True


class EmergencyAlertBase(BaseModel):
    track_segment_id: int
    failure_type: FailureType
    description: Optional[str] = None
    severity: TaskUrgency = TaskUrgency.CRITICAL


class EmergencyAlertCreate(EmergencyAlertBase):
    pass


class EmergencyAlertResponse(EmergencyAlertBase):
    id: int
    alert_code: str
    reported_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    status: str
    assigned_team_id: Optional[int] = None

    class Config:
        from_attributes = True


class SensorDataBase(BaseModel):
    track_segment_id: int
    sensor_type: str
    value: float
    unit: Optional[str] = None
    location_km: Optional[float] = None


class SensorDataCreate(SensorDataBase):
    pass


class SensorDataResponse(SensorDataBase):
    id: int
    recorded_at: datetime

    class Config:
        from_attributes = True


class InspectionLogBase(BaseModel):
    track_segment_id: int
    inspector_name: Optional[str] = None
    inspection_date: datetime
    findings: Optional[str] = None
    severity_score: float = 0.0
    recommended_action: Optional[str] = None


class InspectionLogCreate(InspectionLogBase):
    pass


class InspectionLogResponse(InspectionLogBase):
    id: int

    class Config:
        from_attributes = True


class ScheduleBlockRequest(BaseModel):
    track_segment_id: int
    requested_duration_hours: float
    preferred_start_time: Optional[datetime] = None
    maintenance_task_id: Optional[int] = None


class ShadowBlock(BaseModel):
    start_time: datetime
    end_time: datetime
    duration_hours: float
    trains_before: int
    trains_after: int
    disruption_score: float


class ScheduleBlockResponse(BaseModel):
    track_segment_id: int
    track_segment_name: str
    requested_duration_hours: float
    recommended_windows: List[ShadowBlock]
    optimal_window: Optional[ShadowBlock] = None
    message: str


class EmergencyTrainInfo(BaseModel):
    train_id: int
    train_number: str
    train_name: Optional[str] = None
    current_latitude: float
    current_longitude: float
    current_speed_kmph: float
    distance_to_segment_km: float
    estimated_arrival_minutes: float
    current_track_segment_id: Optional[int] = None


class AlternateRoute(BaseModel):
    route_id: str
    junctions: List[Dict[str, Any]]
    total_distance_km: float
    estimated_time_minutes: float
    track_segments: List[int]


class EmergencyResponsePlan(BaseModel):
    alert_id: int
    affected_segment_id: int
    affected_segment_name: str
    failure_type: FailureType
    trains_to_halt: List[EmergencyTrainInfo]
    alternate_routes: List[AlternateRoute]
    recommended_response_team: Optional[ResponseTeamResponse] = None
    kavach_activated: bool
    message: str


class HealthScoreInput(BaseModel):
    track_segment_id: int
    gmt_load: float
    weather_condition: str = "Clear"
    temperature_celsius: float = 25.0
    humidity_percent: float = 60.0
    rainfall_mm: float = 0.0
    wind_speed_kmph: float = 10.0
    sensor_tms_value: Optional[float] = None
    sensor_tdms_value: Optional[float] = None
    sensor_smms_value: Optional[float] = None
    inspection_severity: float = 0.0


class HealthScoreOutput(BaseModel):
    track_segment_id: int
    health_score: float
    health_status: HealthStatus
    contributing_factors: Dict[str, float]
    recommendation: str


class WebSocketMessage(BaseModel):
    type: str
    timestamp: datetime
    data: Dict[str, Any]


class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)