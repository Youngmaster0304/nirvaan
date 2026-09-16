from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import (
    TrackSegment, MaintenanceTask, Train, TrainSchedule,
    Junction, TrackConnection, ResponseTeam, EmergencyAlert,
    SensorData, InspectionLog, HealthStatus, TaskUrgency,
    FailureType, ResponseTeamType
)
from app.schemas import (
    TrackSegmentCreate, TrackSegmentUpdate, TrackSegmentResponse,
    MaintenanceTaskCreate, MaintenanceTaskUpdate, MaintenanceTaskResponse,
    TrainCreate, TrainResponse, TrainScheduleCreate, TrainScheduleResponse,
    JunctionCreate, JunctionResponse, TrackConnectionCreate, TrackConnectionResponse,
    ResponseTeamCreate, ResponseTeamResponse,
    EmergencyAlertCreate, EmergencyAlertResponse,
    SensorDataCreate, SensorDataResponse,
    InspectionLogCreate, InspectionLogResponse,
    ScheduleBlockRequest, ScheduleBlockResponse,
    EmergencyResponsePlan, HealthScoreInput, HealthScoreOutput,
    APIResponse, WebSocketMessage
)
from app.predictive_engine import predictive_engine
from app.scheduler import shadow_block_scheduler
from app.emergency import emergency_engine
from app.websocket import manager
from app.config import settings


router = APIRouter()


@router.get("/health", response_model=APIResponse)
async def health_check():
    return APIResponse(
        success=True,
        message="RailVision-AI API is running",
        data={"version": "1.0.0", "status": "healthy"},
    )


@router.post("/api/track-segments", response_model=TrackSegmentResponse, status_code=201)
async def create_track_segment(
    segment: TrackSegmentCreate, db: AsyncSession = Depends(get_db)
):
    db_segment = TrackSegment(**segment.model_dump())
    db.add(db_segment)
    await db.commit()
    await db.refresh(db_segment)
    return db_segment


@router.get("/api/track-segments", response_model=List[TrackSegmentResponse])
async def list_track_segments(
    skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(TrackSegment).where(TrackSegment.is_active == True).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/api/track-segments/{segment_id}", response_model=TrackSegmentResponse)
async def get_track_segment(segment_id: int, db: AsyncSession = Depends(get_db)):
    segment = await db.get(TrackSegment, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Track segment not found")
    return segment


@router.patch("/api/track-segments/{segment_id}", response_model=TrackSegmentResponse)
async def update_track_segment(
    segment_id: int, update: TrackSegmentUpdate, db: AsyncSession = Depends(get_db)
):
    segment = await db.get(TrackSegment, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Track segment not found")

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(segment, field, value)

    await db.commit()
    await db.refresh(segment)
    return segment


@router.post("/api/maintenance-tasks", response_model=MaintenanceTaskResponse, status_code=201)
async def create_maintenance_task(
    task: MaintenanceTaskCreate, db: AsyncSession = Depends(get_db)
):
    segment = await db.get(TrackSegment, task.track_segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Track segment not found")

    db_task = MaintenanceTask(**task.model_dump())
    db.add(db_task)
    await db.commit()
    await db.refresh(db_task)
    return db_task


@router.get("/api/maintenance-tasks", response_model=List[MaintenanceTaskResponse])
async def list_maintenance_tasks(
    segment_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    query = select(MaintenanceTask)
    if segment_id:
        query = query.where(MaintenanceTask.track_segment_id == segment_id)
    if status:
        query = query.where(MaintenanceTask.status == status)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/api/trains", response_model=TrainResponse, status_code=201)
async def create_train(train: TrainCreate, db: AsyncSession = Depends(get_db)):
    db_train = Train(**train.model_dump())
    db.add(db_train)
    await db.commit()
    await db.refresh(db_train)
    return db_train


@router.get("/api/trains", response_model=List[TrainResponse])
async def list_trains(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Train).where(Train.is_active == True).offset(skip).limit(limit))
    return result.scalars().all()


@router.post("/api/train-schedules", response_model=TrainScheduleResponse, status_code=201)
async def create_train_schedule(
    schedule: TrainScheduleCreate, db: AsyncSession = Depends(get_db)
):
    train = await db.get(Train, schedule.train_id)
    if not train:
        raise HTTPException(status_code=404, detail="Train not found")
    segment = await db.get(TrackSegment, schedule.track_segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Track segment not found")

    db_schedule = TrainSchedule(**schedule.model_dump())
    db.add(db_schedule)
    await db.commit()
    await db.refresh(db_schedule)
    return db_schedule


@router.get("/api/train-schedules", response_model=List[TrainScheduleResponse])
async def list_train_schedules(
    segment_id: Optional[int] = None,
    train_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    query = select(TrainSchedule).options(selectinload(TrainSchedule.train))
    if segment_id:
        query = query.where(TrainSchedule.track_segment_id == segment_id)
    if train_id:
        query = query.where(TrainSchedule.train_id == train_id)
    query = query.order_by(TrainSchedule.scheduled_arrival).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/api/junctions", response_model=JunctionResponse, status_code=201)
async def create_junction(junction: JunctionCreate, db: AsyncSession = Depends(get_db)):
    db_junction = Junction(**junction.model_dump())
    db.add(db_junction)
    await db.commit()
    await db.refresh(db_junction)
    return db_junction


@router.get("/api/junctions", response_model=List[JunctionResponse])
async def list_junctions(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Junction).where(Junction.is_active == True).offset(skip).limit(limit))
    return result.scalars().all()


@router.post("/api/track-connections", response_model=TrackConnectionResponse, status_code=201)
async def create_track_connection(
    connection: TrackConnectionCreate, db: AsyncSession = Depends(get_db)
):
    from_j = await db.get(Junction, connection.from_junction_id)
    to_j = await db.get(Junction, connection.to_junction_id)
    segment = await db.get(TrackSegment, connection.track_segment_id)
    if not from_j or not to_j or not segment:
        raise HTTPException(status_code=404, detail="Referenced entity not found")

    db_conn = TrackConnection(**connection.model_dump())
    db.add(db_conn)
    await db.commit()
    await db.refresh(db_conn)
    return db_conn


@router.get("/api/track-connections", response_model=List[TrackConnectionResponse])
async def list_track_connections(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TrackConnection).where(TrackConnection.is_active == True).offset(skip).limit(limit))
    return result.scalars().all()


@router.post("/api/response-teams", response_model=ResponseTeamResponse, status_code=201)
async def create_response_team(team: ResponseTeamCreate, db: AsyncSession = Depends(get_db)):
    db_team = ResponseTeam(**team.model_dump())
    db.add(db_team)
    await db.commit()
    await db.refresh(db_team)
    return db_team


@router.get("/api/response-teams", response_model=List[ResponseTeamResponse])
async def list_response_teams(
    team_type: Optional[ResponseTeamType] = None,
    available_only: bool = False,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    query = select(ResponseTeam)
    if team_type:
        query = query.where(ResponseTeam.team_type == team_type)
    if available_only:
        query = query.where(ResponseTeam.is_available == True)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/api/sensor-data", response_model=SensorDataResponse, status_code=201)
async def create_sensor_data(data: SensorDataCreate, db: AsyncSession = Depends(get_db)):
    segment = await db.get(TrackSegment, data.track_segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Track segment not found")

    db_data = SensorData(**data.model_dump())
    db.add(db_data)
    await db.commit()
    await db.refresh(db_data)
    return db_data


@router.get("/api/sensor-data", response_model=List[SensorDataResponse])
async def list_sensor_data(
    segment_id: int,
    sensor_type: Optional[str] = None,
    hours: int = 24,
    skip: int = 0,
    limit: int = 1000,
    db: AsyncSession = Depends(get_db),
):
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(hours=hours)
    query = select(SensorData).where(
        and_(SensorData.track_segment_id == segment_id, SensorData.recorded_at >= since)
    )
    if sensor_type:
        query = query.where(SensorData.sensor_type == sensor_type)
    query = query.order_by(SensorData.recorded_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/api/inspection-logs", response_model=InspectionLogResponse, status_code=201)
async def create_inspection_log(log: InspectionLogCreate, db: AsyncSession = Depends(get_db)):
    segment = await db.get(TrackSegment, log.track_segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Track segment not found")

    db_log = InspectionLog(**log.model_dump())
    db.add(db_log)
    await db.commit()
    await db.refresh(db_log)
    return db_log


@router.get("/api/inspection-logs", response_model=List[InspectionLogResponse])
async def list_inspection_logs(
    segment_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    query = select(InspectionLog)
    if segment_id:
        query = query.where(InspectionLog.track_segment_id == segment_id)
    query = query.order_by(InspectionLog.inspection_date.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/api/health-score", response_model=HealthScoreOutput)
async def calculate_health_score(input_data: HealthScoreInput, db: AsyncSession = Depends(get_db)):
    segment = await db.get(TrackSegment, input_data.track_segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Track segment not found")

    result = predictive_engine.calculate_health_score(input_data, segment.length_km)

    segment.current_health_score = result.health_score
    segment.health_status = result.health_status
    segment.gmt_load = input_data.gmt_load
    await db.commit()

    await manager.send_health_update(
        segment.id, segment.name, result.health_score, result.health_status.value
    )

    if result.health_status == HealthStatus.DARK_RED:
        await manager.send_dark_red_alert(
            alert_id=0,
            segment_name=segment.name,
            failure_type="Auto-detected",
            severity="CRITICAL",
            trains_affected=0,
            location={"lat": segment.latitude_start, "lon": segment.longitude_start},
        )

    return result


@router.post("/api/schedule-block", response_model=ScheduleBlockResponse)
async def schedule_maintenance_block(
    request: ScheduleBlockRequest, db: AsyncSession = Depends(get_db)
):
    use_ortools = request.requested_duration_hours > 4

    if use_ortools:
        result = await shadow_block_scheduler.optimize_with_ortools(db, request)
    else:
        result = await shadow_block_scheduler.find_shadow_blocks(db, request)

    if request.maintenance_task_id:
        task = await db.get(MaintenanceTask, request.maintenance_task_id)
        if task and result.optimal_window:
            task.scheduled_start = result.optimal_window.start_time
            task.scheduled_end = result.optimal_window.end_time
            task.status = "Scheduled"
            await db.commit()

    if result.optimal_window:
        await manager.send_schedule_update(request.track_segment_id, {
            "start": result.optimal_window.start_time.isoformat(),
            "end": result.optimal_window.end_time.isoformat(),
            "duration_hours": result.optimal_window.duration_hours,
        })

    return result


@router.post("/api/trigger-emergency", response_model=EmergencyResponsePlan)
async def trigger_emergency(alert_data: EmergencyAlertCreate, db: AsyncSession = Depends(get_db)):
    result = await emergency_engine.trigger_emergency(db, alert_data)

    await manager.send_dark_red_alert(
        alert_id=result.alert_id,
        segment_name=result.affected_segment_name,
        failure_type=result.failure_type.value,
        severity="CRITICAL",
        trains_affected=len(result.trains_to_halt),
        location={
            "lat": (await db.get(TrackSegment, result.affected_segment_id)).latitude_start,
            "lon": (await db.get(TrackSegment, result.affected_segment_id)).longitude_start,
        },
    )

    return result


@router.get("/api/emergency-alerts", response_model=List[EmergencyAlertResponse])
async def list_emergency_alerts(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    query = select(EmergencyAlert).order_by(EmergencyAlert.reported_at.desc())
    if status:
        query = query.where(EmergencyAlert.status == status)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/api/dashboard/summary")
async def get_dashboard_summary(db: AsyncSession = Depends(get_db)):
    total_segments = await db.execute(select(func.count(TrackSegment.id)).where(TrackSegment.is_active == True))
    critical_segments = await db.execute(
        select(func.count(TrackSegment.id)).where(
            and_(TrackSegment.is_active == True, TrackSegment.health_status == HealthStatus.DARK_RED)
        )
    )
    red_segments = await db.execute(
        select(func.count(TrackSegment.id)).where(
            and_(TrackSegment.is_active == True, TrackSegment.health_status == HealthStatus.RED)
        )
    )
    orange_segments = await db.execute(
        select(func.count(TrackSegment.id)).where(
            and_(TrackSegment.is_active == True, TrackSegment.health_status == HealthStatus.ORANGE)
        )
    )
    active_alerts = await db.execute(
        select(func.count(EmergencyAlert.id)).where(EmergencyAlert.status == "Active")
    )
    active_trains = await db.execute(
        select(func.count(TrainSchedule.id)).where(TrainSchedule.is_running == True)
    )
    available_teams = await db.execute(
        select(func.count(ResponseTeam.id)).where(ResponseTeam.is_available == True)
    )

    return APIResponse(
        success=True,
        message="Dashboard summary",
        data={
            "track_segments": {
                "total": total_segments.scalar(),
                "dark_red": critical_segments.scalar(),
                "red": red_segments.scalar(),
                "orange": orange_segments.scalar(),
                "green": total_segments.scalar() - critical_segments.scalar() - red_segments.scalar() - orange_segments.scalar(),
            },
            "active_emergency_alerts": active_alerts.scalar(),
            "active_trains": active_trains.scalar(),
            "available_response_teams": available_teams.scalar(),
            "websocket_connections": manager.get_connection_stats(),
        },
    )


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str, channel: str = "all"):
    await manager.connect(websocket, client_id, channel)
    try:
        while True:
            data = await websocket.receive_text()
            message = WebSocketMessage(
                type="echo",
                timestamp=datetime.utcnow(),
                data={"received": data, "client_id": client_id},
            )
            await manager.send_personal_message(websocket, message)
    except WebSocketDisconnect:
        manager.disconnect(websocket)