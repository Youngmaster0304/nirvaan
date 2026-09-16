import numpy as np
from typing import Dict, Optional
from app.schemas import HealthScoreInput, HealthScoreOutput
from app.models import HealthStatus
from app.config import settings


class PredictiveEngine:
    def __init__(self):
        self.weights = {
            "gmt_load": 0.25,
            "weather": 0.15,
            "sensor_tms": 0.20,
            "sensor_tdms": 0.15,
            "sensor_smms": 0.10,
            "inspection": 0.15,
        }

    def calculate_gmt_factor(self, gmt_load: float, segment_length: float) -> float:
        gmt_per_km = gmt_load / max(segment_length, 1.0)
        if gmt_per_km <= 10:
            return 1.0
        elif gmt_per_km <= 20:
            return 0.85
        elif gmt_per_km <= 30:
            return 0.7
        elif gmt_per_km <= 40:
            return 0.55
        else:
            return 0.4

    def calculate_weather_factor(
        self,
        weather_condition: str,
        temperature: float,
        humidity: float,
        rainfall: float,
        wind_speed: float,
    ) -> float:
        weather_scores = {
            "Clear": 1.0,
            "Partly Cloudy": 0.95,
            "Cloudy": 0.9,
            "Light Rain": 0.8,
            "Moderate Rain": 0.7,
            "Heavy Rain": 0.55,
            "Storm": 0.4,
            "Fog": 0.85,
            "Extreme Heat": 0.75,
            "Extreme Cold": 0.8,
        }
        base_score = weather_scores.get(weather_condition, 0.9)

        if temperature > 45:
            base_score *= 0.9
        elif temperature < 0:
            base_score *= 0.92

        if humidity > 90:
            base_score *= 0.95

        if rainfall > 50:
            base_score *= 0.7
        elif rainfall > 20:
            base_score *= 0.85

        if wind_speed > 80:
            base_score *= 0.85
        elif wind_speed > 50:
            base_score *= 0.92

        return max(0.3, min(1.0, base_score))

    def calculate_sensor_factor(
        self,
        tms_value: Optional[float],
        tdms_value: Optional[float],
        smms_value: Optional[float],
    ) -> float:
        factors = []

        if tms_value is not None:
            if tms_value <= 0.5:
                factors.append(1.0)
            elif tms_value <= 1.0:
                factors.append(0.85)
            elif tms_value <= 2.0:
                factors.append(0.7)
            elif tms_value <= 3.0:
                factors.append(0.5)
            else:
                factors.append(0.3)

        if tdms_value is not None:
            if tdms_value <= 0.3:
                factors.append(1.0)
            elif tdms_value <= 0.6:
                factors.append(0.85)
            elif tdms_value <= 1.0:
                factors.append(0.7)
            elif tdms_value <= 1.5:
                factors.append(0.55)
            else:
                factors.append(0.35)

        if smms_value is not None:
            if smms_value <= 0.2:
                factors.append(1.0)
            elif smms_value <= 0.5:
                factors.append(0.9)
            elif smms_value <= 1.0:
                factors.append(0.75)
            elif smms_value <= 1.5:
                factors.append(0.6)
            else:
                factors.append(0.4)

        if not factors:
            return 0.85
        return np.mean(factors)

    def calculate_inspection_factor(self, severity: float) -> float:
        if severity <= 0.1:
            return 1.0
        elif severity <= 0.3:
            return 0.9
        elif severity <= 0.5:
            return 0.75
        elif severity <= 0.7:
            return 0.6
        else:
            return 0.4

    def calculate_health_score(
        self,
        input_data: HealthScoreInput,
        segment_length: float = 10.0,
    ) -> HealthScoreOutput:
        gmt_factor = self.calculate_gmt_factor(input_data.gmt_load, segment_length)
        weather_factor = self.calculate_weather_factor(
            input_data.weather_condition,
            input_data.temperature_celsius,
            input_data.humidity_percent,
            input_data.rainfall_mm,
            input_data.wind_speed_kmph,
        )
        sensor_factor = self.calculate_sensor_factor(
            input_data.sensor_tms_value,
            input_data.sensor_tdms_value,
            input_data.sensor_smms_value,
        )
        inspection_factor = self.calculate_inspection_factor(input_data.inspection_severity)

        contributing_factors = {
            "gmt_load": gmt_factor,
            "weather": weather_factor,
            "sensors": sensor_factor,
            "inspection": inspection_factor,
        }

        weighted_score = (
            self.weights["gmt_load"] * gmt_factor
            + self.weights["weather"] * weather_factor
            + self.weights["sensor_tms"] * sensor_factor
            + self.weights["sensor_tdms"] * sensor_factor
            + self.weights["sensor_smms"] * sensor_factor
            + self.weights["inspection"] * inspection_factor
        )

        health_score = max(0.0, min(1.0, weighted_score))

        if health_score >= settings.HEALTH_GREEN_THRESHOLD:
            health_status = HealthStatus.GREEN
        elif health_score >= settings.HEALTH_ORANGE_THRESHOLD:
            health_status = HealthStatus.ORANGE
        elif health_score >= settings.HEALTH_RED_THRESHOLD:
            health_status = HealthStatus.RED
        else:
            health_status = HealthStatus.DARK_RED

        recommendation = self._generate_recommendation(health_status, contributing_factors)

        return HealthScoreOutput(
            track_segment_id=input_data.track_segment_id,
            health_score=round(health_score, 3),
            health_status=health_status,
            contributing_factors={k: round(v, 3) for k, v in contributing_factors.items()},
            recommendation=recommendation,
        )

    def _generate_recommendation(
        self, status: HealthStatus, factors: Dict[str, float]
    ) -> str:
        recommendations = {
            HealthStatus.GREEN: "Track segment in excellent condition. Continue routine monitoring.",
            HealthStatus.ORANGE: "Track segment shows early signs of degradation. Schedule preventive maintenance within 30 days.",
            HealthStatus.RED: "Track segment requires urgent maintenance. Plan maintenance within 7 days. Consider speed restrictions.",
            HealthStatus.DARK_RED: "CRITICAL: Track segment at risk of failure. Immediate emergency response required. Halt traffic if necessary.",
        }

        base_rec = recommendations.get(status, "Monitor condition.")

        worst_factor = min(factors, key=factors.get)
        factor_details = {
            "gmt_load": "High traffic load (GMT) is the primary concern.",
            "weather": "Adverse weather conditions accelerating degradation.",
            "sensors": "Sensor readings (TMS/TDMS/SMMS) indicate abnormal track behavior.",
            "inspection": "Recent inspections reveal significant defects.",
        }

        detail = factor_details.get(worst_factor, "")
        return f"{base_rec} {detail}"


predictive_engine = PredictiveEngine()