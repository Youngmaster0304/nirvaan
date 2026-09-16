from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from ortools.sat.python import cp_model
import math

from app.schemas import ScheduleBlockRequest, ShadowBlock, ScheduleBlockResponse
from app.models import TrackSegment, TrainSchedule, Train
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_


class ShadowBlockScheduler:
    def __init__(self, time_limit_seconds: int = 30):
        self.time_limit_seconds = time_limit_seconds

    async def find_shadow_blocks(
        self,
        db: AsyncSession,
        request: ScheduleBlockRequest,
    ) -> ScheduleBlockResponse:
        segment = await db.get(TrackSegment, request.track_segment_id)
        if not segment:
            raise ValueError(f"Track segment {request.track_segment_id} not found")

        schedules = await self._get_train_schedules(db, request.track_segment_id)
        if not schedules:
            return self._empty_response(segment, request)

        time_windows = self._generate_time_windows(request, schedules)
        shadow_blocks = self._analyze_gaps(schedules, time_windows, request.requested_duration_hours)

        if not shadow_blocks:
            return ScheduleBlockResponse(
                track_segment_id=segment.id,
                track_segment_name=segment.name,
                requested_duration_hours=request.requested_duration_hours,
                recommended_windows=[],
                optimal_window=None,
                message="No suitable maintenance window found in the next 7 days",
            )

        shadow_blocks.sort(key=lambda x: x.disruption_score)
        optimal = shadow_blocks[0]

        return ScheduleBlockResponse(
            track_segment_id=segment.id,
            track_segment_name=segment.name,
            requested_duration_hours=request.requested_duration_hours,
            recommended_windows=shadow_blocks[:5],
            optimal_window=optimal,
            message=f"Found {len(shadow_blocks)} potential maintenance windows",
        )

    async def _get_train_schedules(
        self, db: AsyncSession, segment_id: int
    ) -> List[TrainSchedule]:
        now = datetime.utcnow()
        week_later = now + timedelta(days=7)

        result = await db.execute(
            select(TrainSchedule)
            .join(Train)
            .where(
                and_(
                    TrainSchedule.track_segment_id == segment_id,
                    TrainSchedule.scheduled_arrival >= now,
                    TrainSchedule.scheduled_arrival <= week_later,
                    Train.is_active == True,
                )
            )
            .order_by(TrainSchedule.scheduled_arrival)
        )
        return list(result.scalars().all())

    def _generate_time_windows(
        self, request: ScheduleBlockRequest, schedules: List[TrainSchedule]
    ) -> List[Tuple[datetime, datetime]]:
        now = datetime.utcnow()
        start_time = request.preferred_start_time or now
        end_time = start_time + timedelta(days=7)

        windows = []
        current = start_time

        while current < end_time:
            next_day = current.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            window_end = min(next_day, end_time)
            windows.append((current, window_end))
            current = next_day

        return windows

    def _analyze_gaps(
        self,
        schedules: List[TrainSchedule],
        time_windows: List[Tuple[datetime, datetime]],
        required_duration: float,
    ) -> List[ShadowBlock]:
        required_minutes = int(required_duration * 60)
        shadow_blocks = []

        for window_start, window_end in time_windows:
            window_schedules = [
                s for s in schedules
                if window_start <= s.scheduled_arrival < window_end
            ]

            if not window_schedules:
                duration = (window_end - window_start).total_seconds() / 60
                if duration >= required_minutes:
                    shadow_blocks.append(ShadowBlock(
                        start_time=window_start,
                        end_time=window_start + timedelta(minutes=required_minutes),
                        duration_hours=required_duration,
                        trains_before=0,
                        trains_after=0,
                        disruption_score=0.0,
                    ))
                continue

            window_schedules.sort(key=lambda s: s.scheduled_arrival)

            prev_end = window_start
            for i, schedule in enumerate(window_schedules):
                gap_minutes = (schedule.scheduled_arrival - prev_end).total_seconds() / 60

                if gap_minutes >= required_minutes:
                    block_start = prev_end
                    block_end = block_start + timedelta(minutes=required_minutes)
                    disruption = self._calculate_disruption_score(
                        window_schedules, i, gap_minutes
                    )
                    shadow_blocks.append(ShadowBlock(
                        start_time=block_start,
                        end_time=block_end,
                        duration_hours=required_duration,
                        trains_before=i,
                        trains_after=len(window_schedules) - i,
                        disruption_score=disruption,
                    ))

                prev_end = schedule.scheduled_departure

            final_gap = (window_end - prev_end).total_seconds() / 60
            if final_gap >= required_minutes:
                disruption = self._calculate_disruption_score(
                    window_schedules, len(window_schedules), final_gap
                )
                shadow_blocks.append(ShadowBlock(
                    start_time=prev_end,
                    end_time=prev_end + timedelta(minutes=required_minutes),
                    duration_hours=required_duration,
                    trains_before=len(window_schedules),
                    trains_after=0,
                    disruption_score=disruption,
                ))

        return shadow_blocks

    def _calculate_disruption_score(
        self, schedules: List[TrainSchedule], gap_index: int, gap_minutes: float
    ) -> float:
        if not schedules:
            return 0.0

        trains_before = gap_index
        trains_after = len(schedules) - gap_index
        total_trains = len(schedules)

        if total_trains == 0:
            return 0.0

        time_pressure = max(0, 1.0 - (gap_minutes / 240.0))
        train_density = total_trains / 24.0

        return round(time_pressure * 0.6 + train_density * 0.4, 3)

    def _empty_response(
        self, segment: TrackSegment, request: ScheduleBlockRequest
    ) -> ScheduleBlockResponse:
        return ScheduleBlockResponse(
            track_segment_id=segment.id,
            track_segment_name=segment.name,
            requested_duration_hours=request.requested_duration_hours,
            recommended_windows=[],
            optimal_window=None,
            message="No train schedules found for this segment",
        )

    async def optimize_with_ortools(
        self,
        db: AsyncSession,
        request: ScheduleBlockRequest,
    ) -> ScheduleBlockResponse:
        segment = await db.get(TrackSegment, request.track_segment_id)
        if not segment:
            raise ValueError(f"Track segment {request.track_segment_id} not found")

        schedules = await self._get_train_schedules(db, request.track_segment_id)
        if not schedules:
            return self._empty_response(segment, request)

        model = cp_model.CpModel()

        now = datetime.utcnow()
        horizon_end = now + timedelta(days=7)
        horizon_minutes = int((horizon_end - now).total_seconds() / 60)
        required_minutes = int(request.requested_duration_hours * 60)

        train_intervals = []
        for i, schedule in enumerate(schedules):
            start_min = int((schedule.scheduled_arrival - now).total_seconds() / 60)
            end_min = int((schedule.scheduled_departure - now).total_seconds() / 60)
            if 0 <= start_min < horizon_minutes and 0 <= end_min < horizon_minutes:
                interval = model.NewIntervalVar(
                    start_min,
                    end_min - start_min,
                    end_min,
                    f"train_{i}"
                )
                train_intervals.append(interval)

        maintenance_start = model.NewIntVar(0, horizon_minutes - required_minutes, "maint_start")
        maintenance_end = model.NewIntVar(required_minutes, horizon_minutes, "maint_end")
        maintenance_interval = model.NewIntervalVar(
            maintenance_start,
            required_minutes,
            maintenance_end,
            "maintenance"
        )

        for train_interval in train_intervals:
            model.AddNoOverlap([train_interval, maintenance_interval])

        model.Minimize(maintenance_start)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit_seconds
        solver.parameters.num_search_workers = 8

        status = solver.Solve(model)

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            opt_start = now + timedelta(minutes=solver.Value(maintenance_start))
            opt_end = opt_start + timedelta(minutes=required_minutes)

            trains_before = sum(
                1 for s in schedules if s.scheduled_departure <= opt_start
            )
            trains_after = sum(
                1 for s in schedules if s.scheduled_arrival >= opt_end
            )

            optimal_block = ShadowBlock(
                start_time=opt_start,
                end_time=opt_end,
                duration_hours=request.requested_duration_hours,
                trains_before=trains_before,
                trains_after=trains_after,
                disruption_score=0.0,
            )

            all_blocks = self._analyze_gaps(
                schedules,
                [(now, horizon_end)],
                request.requested_duration_hours,
            )
            all_blocks.sort(key=lambda x: x.disruption_score)

            return ScheduleBlockResponse(
                track_segment_id=segment.id,
                track_segment_name=segment.name,
                requested_duration_hours=request.requested_duration_hours,
                recommended_windows=all_blocks[:5],
                optimal_window=optimal_block,
                message="Optimal window found using OR-Tools CP-SAT solver",
            )
        else:
            return await self.find_shadow_blocks(db, request)


shadow_block_scheduler = ShadowBlockScheduler()