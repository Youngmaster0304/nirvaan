import math
import heapq
import networkx as nx
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from app.models import (
    TrackSegment, TrainSchedule, Train, Junction, TrackConnection,
    ResponseTeam, EmergencyAlert, FailureType, ResponseTeamType, TaskUrgency
)
from app.schemas import (
    EmergencyResponsePlan, EmergencyTrainInfo, AlternateRoute,
    EmergencyAlertCreate, ResponseTeamResponse
)
from app.config import settings


class EmergencyResponseEngine:
    def __init__(self):
        self.graph = nx.Graph()
        self._graph_built = False

    async def build_graph(self, db: AsyncSession):
        if self._graph_built:
            return

        junctions_result = await db.execute(select(Junction).where(Junction.is_active == True))
        junctions = junctions_result.scalars().all()

        for junction in junctions:
            self.graph.add_node(
                junction.id,
                code=junction.code,
                name=junction.name,
                lat=junction.latitude,
                lon=junction.longitude,
            )

        connections_result = await db.execute(
            select(TrackConnection).where(TrackConnection.is_active == True)
        )
        connections = connections_result.scalars().all()

        for conn in connections:
            travel_time = (conn.distance_km / max(conn.max_speed_kmph, 1)) * 60
            self.graph.add_edge(
                conn.from_junction_id,
                conn.to_junction_id,
                weight=travel_time,
                distance=conn.distance_km,
                track_segment_id=conn.track_segment_id,
                max_speed=conn.max_speed_kmph,
            )

            if conn.is_bidirectional:
                self.graph.add_edge(
                    conn.to_junction_id,
                    conn.from_junction_id,
                    weight=travel_time,
                    distance=conn.distance_km,
                    track_segment_id=conn.track_segment_id,
                    max_speed=conn.max_speed_kmph,
                )

        self._graph_built = True

    def haversine_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        R = 6371
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = math.sin(delta_phi / 2) ** 2 + \
            math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    async def find_trains_in_radius(
        self,
        db: AsyncSession,
        segment: TrackSegment,
        radius_km: float = 50.0,
    ) -> List[EmergencyTrainInfo]:
        segment_center_lat = (segment.latitude_start + segment.latitude_end) / 2
        segment_center_lon = (segment.longitude_start + segment.longitude_end) / 2

        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        hour_later = now + timedelta(hours=2)

        schedules_result = await db.execute(
            select(TrainSchedule)
            .join(Train)
            .where(
                and_(
                    TrainSchedule.is_running == True,
                    Train.is_active == True,
                    TrainSchedule.scheduled_arrival >= hour_ago,
                    TrainSchedule.scheduled_arrival <= hour_later,
                )
            )
        )
        schedules = schedules_result.scalars().all()

        trains_in_radius = []
        for schedule in schedules:
            if schedule.current_latitude and schedule.current_longitude:
                distance = self.haversine_distance(
                    segment_center_lat,
                    segment_center_lon,
                    schedule.current_latitude,
                    schedule.current_longitude,
                )
            else:
                seg_lat = (segment.latitude_start + segment.latitude_end) / 2
                seg_lon = (segment.longitude_start + segment.longitude_end) / 2
                distance = self.haversine_distance(
                    seg_lat, seg_lon,
                    segment.latitude_start, segment.longitude_start
                )

            if distance <= radius_km:
                train = schedule.train
                eta_minutes = (distance / max(schedule.current_speed_kmph, 30)) * 60 if schedule.current_speed_kmph > 0 else 60

                trains_in_radius.append(EmergencyTrainInfo(
                    train_id=train.id,
                    train_number=train.train_number,
                    train_name=train.train_name,
                    current_latitude=schedule.current_latitude or segment.latitude_start,
                    current_longitude=schedule.current_longitude or segment.longitude_start,
                    current_speed_kmph=schedule.current_speed_kmph,
                    distance_to_segment_km=round(distance, 2),
                    estimated_arrival_minutes=round(eta_minutes, 1),
                    current_track_segment_id=schedule.track_segment_id,
                ))

        return sorted(trains_in_radius, key=lambda t: t.distance_to_segment_km)

    def find_alternate_routes(
        self,
        db: AsyncSession,
        blocked_segment: TrackSegment,
        start_junction_id: int,
        target_junction_id: int,
        max_routes: int = 3,
    ) -> List[AlternateRoute]:
        if not self._graph_built:
            return []

        if start_junction_id not in self.graph or target_junction_id not in self.graph:
            return []

        blocked_edges = []
        for u, v, data in self.graph.edges(data=True):
            if data.get("track_segment_id") == blocked_segment.id:
                blocked_edges.append((u, v))

        for u, v in blocked_edges:
            if self.graph.has_edge(u, v):
                self.graph.remove_edge(u, v)

        routes = []
        try:
            paths = list(nx.shortest_simple_paths(
                self.graph, start_junction_id, target_junction_id, weight="weight"
            ))[:max_routes]

            for i, path in enumerate(paths):
                junctions_info = []
                total_distance = 0.0
                total_time = 0.0
                track_segments = []

                for j in range(len(path) - 1):
                    u, v = path[j], path[j + 1]
                    edge_data = self.graph[u][v]
                    junctions_info.append({
                        "junction_id": u,
                        "code": self.graph.nodes[u]["code"],
                        "name": self.graph.nodes[u]["name"],
                        "latitude": self.graph.nodes[u]["lat"],
                        "longitude": self.graph.nodes[u]["lon"],
                    })
                    total_distance += edge_data.get("distance", 0)
                    total_time += edge_data.get("weight", 0)
                    if edge_data.get("track_segment_id"):
                        track_segments.append(edge_data["track_segment_id"])

                junctions_info.append({
                    "junction_id": path[-1],
                    "code": self.graph.nodes[path[-1]]["code"],
                    "name": self.graph.nodes[path[-1]]["name"],
                    "latitude": self.graph.nodes[path[-1]]["lat"],
                    "longitude": self.graph.nodes[path[-1]]["lon"],
                })

                routes.append(AlternateRoute(
                    route_id=f"ALT-{blocked_segment.id}-{i+1}",
                    junctions=junctions_info,
                    total_distance_km=round(total_distance, 2),
                    estimated_time_minutes=round(total_time, 1),
                    track_segments=track_segments,
                ))
        except nx.NetworkXNoPath:
            pass
        finally:
            for u, v in blocked_edges:
                edge_data = self.graph[u][v] if self.graph.has_edge(u, v) else None
                if edge_data is None:
                    pass

        return routes

    def get_recommended_team(
        self, failure_type: FailureType
    ) -> ResponseTeamType:
        team_mapping = {
            FailureType.TRACK_FRACTURE: ResponseTeamType.TRACK_ENGINEERING,
            FailureType.OHE_FAILURE: ResponseTeamType.TOWER_WAGON,
            FailureType.SIGNAL_FAILURE: ResponseTeamType.SIGNAL_TELECOM,
            FailureType.POINTS_FAILURE: ResponseTeamType.SIGNAL_TELECOM,
            FailureType.TRACK_CIRCUIT_FAILURE: ResponseTeamType.SIGNAL_TELECOM,
            FailureType.EARTHWORK_SLIP: ResponseTeamType.TRACK_ENGINEERING,
            FailureType.BRIDGE_ISSUE: ResponseTeamType.BRIDGE,
            FailureType.LEVEL_CROSSING: ResponseTeamType.SIGNAL_TELECOM,
        }
        return team_mapping.get(failure_type, ResponseTeamType.EMERGENCY_RELIEF)

    async def find_nearest_available_team(
        self,
        db: AsyncSession,
        team_type: ResponseTeamType,
        latitude: float,
        longitude: float,
    ) -> Optional[ResponseTeam]:
        result = await db.execute(
            select(ResponseTeam).where(
                and_(
                    ResponseTeam.team_type == team_type,
                    ResponseTeam.is_available == True,
                )
            )
        )
        teams = result.scalars().all()

        if not teams:
            return None

        nearest_team = min(
            teams,
            key=lambda t: self.haversine_distance(
                latitude, longitude, t.base_latitude, t.base_longitude
            ) if t.base_latitude and t.base_longitude else float("inf")
        )
        return nearest_team

    async def trigger_emergency(
        self,
        db: AsyncSession,
        alert_data: EmergencyAlertCreate,
    ) -> EmergencyResponsePlan:
        await self.build_graph(db)

        segment = await db.get(TrackSegment, alert_data.track_segment_id)
        if not segment:
            raise ValueError(f"Track segment {alert_data.track_segment_id} not found")

        alert = EmergencyAlert(
            alert_code=f"EMG-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            track_segment_id=alert_data.track_segment_id,
            failure_type=alert_data.failure_type,
            description=alert_data.description,
            severity=alert_data.severity,
            status="Active",
        )
        db.add(alert)
        await db.flush()

        trains_to_halt = await self.find_trains_in_radius(
            db, segment, settings.EMERGENCY_RADIUS_KM
        )

        # Approximate 20km in degrees (~0.18 degrees) to avoid raw PostGIS typecast syntax error
        lat_delta = 0.18
        lon_delta = 0.18

        start_junctions_result = await db.execute(
            select(Junction).where(
                and_(
                    Junction.is_active == True,
                    Junction.latitude.between(segment.latitude_start - lat_delta, segment.latitude_start + lat_delta),
                    Junction.longitude.between(segment.longitude_start - lon_delta, segment.longitude_start + lon_delta)
                )
            ).limit(5)
        )
        start_junctions = start_junctions_result.scalars().all()

        end_junctions_result = await db.execute(
            select(Junction).where(
                and_(
                    Junction.is_active == True,
                    Junction.latitude.between(segment.latitude_end - lat_delta, segment.latitude_end + lat_delta),
                    Junction.longitude.between(segment.longitude_end - lon_delta, segment.longitude_end + lon_delta)
                )
            ).limit(5)
        )
        end_junctions = end_junctions_result.scalars().all()

        all_routes = []
        for start_j in start_junctions:
            for end_j in end_junctions:
                if start_j.id != end_j.id:
                    routes = await self.find_alternate_routes(
                        db, segment, start_j.id, end_j.id, max_routes=2
                    )
                    all_routes.extend(routes)

        all_routes.sort(key=lambda r: r.estimated_time_minutes)
        unique_routes = []
        seen_segments = set()
        for route in all_routes:
            seg_tuple = tuple(sorted(route.track_segments))
            if seg_tuple not in seen_segments:
                seen_segments.add(seg_tuple)
                unique_routes.append(route)
            if len(unique_routes) >= 3:
                break

        recommended_team_type = self.get_recommended_team(alert_data.failure_type)
        nearest_team = await self.find_nearest_available_team(
            db, recommended_team_type, segment.latitude_start, segment.longitude_start
        )

        team_response = None
        if nearest_team:
            team_response = ResponseTeamResponse(
                id=nearest_team.id,
                team_code=nearest_team.team_code,
                name=nearest_team.name,
                team_type=nearest_team.team_type,
                base_station=nearest_team.base_station,
                base_latitude=nearest_team.base_latitude,
                base_longitude=nearest_team.base_longitude,
                contact_number=nearest_team.contact_number,
                contact_person=nearest_team.contact_person,
                is_available=nearest_team.is_available,
                current_latitude=nearest_team.current_latitude,
                current_longitude=nearest_team.current_longitude,
                last_updated=nearest_team.last_updated,
            )
            alert.assigned_team_id = nearest_team.id
            nearest_team.is_available = False

        await db.commit()
        await db.refresh(alert)

        return EmergencyResponsePlan(
            alert_id=alert.id,
            affected_segment_id=segment.id,
            affected_segment_name=segment.name,
            failure_type=alert_data.failure_type,
            trains_to_halt=trains_to_halt,
            alternate_routes=unique_routes,
            recommended_response_team=team_response,
            kavach_activated=len(trains_to_halt) > 0,
            message=f"Emergency response activated for {alert_data.failure_type.value} on {segment.name}. "
                    f"{len(trains_to_halt)} trains in radius. KAVACH {'activated' if trains_to_halt else 'not needed'}.",
        )


emergency_engine = EmergencyResponseEngine()