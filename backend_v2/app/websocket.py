import json
import asyncio
from typing import Dict, List, Set
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from app.schemas import WebSocketMessage


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {
            "alerts": set(),
            "dashboard": set(),
            "all": set(),
        }
        self.client_info: Dict[WebSocket, Dict] = {}

    async def connect(self, websocket: WebSocket, client_id: str, channel: str = "all"):
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = set()
        self.active_connections[channel].add(websocket)
        self.active_connections["all"].add(websocket)
        self.client_info[websocket] = {
            "client_id": client_id,
            "channel": channel,
            "connected_at": datetime.utcnow(),
        }
        await self.send_personal_message(
            websocket,
            WebSocketMessage(
                type="connection_established",
                timestamp=datetime.utcnow(),
                data={"client_id": client_id, "channel": channel, "message": "Connected to RailVision-AI WebSocket"},
            ),
        )

    def disconnect(self, websocket: WebSocket):
        for channel, connections in self.active_connections.items():
            if websocket in connections:
                connections.remove(websocket)
        if websocket in self.client_info:
            del self.client_info[websocket]

    async def send_personal_message(self, websocket: WebSocket, message: WebSocketMessage):
        try:
            await websocket.send_text(message.model_dump_json())
        except Exception:
            self.disconnect(websocket)

    async def broadcast_to_channel(self, channel: str, message: WebSocketMessage):
        if channel not in self.active_connections:
            return
        disconnected = []
        for websocket in self.active_connections[channel]:
            try:
                await websocket.send_text(message.model_dump_json())
            except Exception:
                disconnected.append(websocket)
        for ws in disconnected:
            self.disconnect(ws)

    async def broadcast_all(self, message: WebSocketMessage):
        await self.broadcast_to_channel("all", message)

    async def send_dark_red_alert(
        self,
        alert_id: int,
        segment_name: str,
        failure_type: str,
        severity: str,
        trains_affected: int,
        location: Dict[str, float],
    ):
        message = WebSocketMessage(
            type="dark_red_alert",
            timestamp=datetime.utcnow(),
            data={
                "alert_id": alert_id,
                "segment_name": segment_name,
                "failure_type": failure_type,
                "severity": severity,
                "trains_affected": trains_affected,
                "location": location,
                "priority": "CRITICAL",
                "action_required": "IMMEDIATE",
            },
        )
        await self.broadcast_to_channel("alerts", message)
        await self.broadcast_to_channel("dashboard", message)

    async def send_health_update(
        self,
        segment_id: int,
        segment_name: str,
        health_score: float,
        health_status: str,
    ):
        message = WebSocketMessage(
            type="health_update",
            timestamp=datetime.utcnow(),
            data={
                "segment_id": segment_id,
                "segment_name": segment_name,
                "health_score": health_score,
                "health_status": health_status,
            },
        )
        await self.broadcast_to_channel("dashboard", message)

    async def send_schedule_update(
        self,
        segment_id: int,
        maintenance_window: Dict,
    ):
        message = WebSocketMessage(
            type="schedule_update",
            timestamp=datetime.utcnow(),
            data={
                "segment_id": segment_id,
                "maintenance_window": maintenance_window,
            },
        )
        await self.broadcast_to_channel("dashboard", message)

    async def send_train_position_update(
        self,
        train_id: int,
        train_number: str,
        latitude: float,
        longitude: float,
        speed: float,
    ):
        message = WebSocketMessage(
            type="train_position",
            timestamp=datetime.utcnow(),
            data={
                "train_id": train_id,
                "train_number": train_number,
                "latitude": latitude,
                "longitude": longitude,
                "speed_kmph": speed,
            },
        )
        await self.broadcast_to_channel("dashboard", message)

    def get_connection_stats(self) -> Dict:
        return {
            "total_connections": len(self.active_connections["all"]),
            "alerts_channel": len(self.active_connections.get("alerts", set())),
            "dashboard_channel": len(self.active_connections.get("dashboard", set())),
            "clients": [
                {
                    "client_id": info["client_id"],
                    "channel": info["channel"],
                    "connected_at": info["connected_at"].isoformat(),
                }
                for info in self.client_info.values()
            ],
        }


manager = ConnectionManager()