"""
Telemetry Specialist Agent for PitWall AI (A2A).
Provides:
- Corner telemetry comparison using CircuitCornerEngine (resolves '130R' to Turn 15, returns unknown_corner hint if unknown)
- Full-lap telemetry overlay
- Tyre stint degradation analytics
- Strict 2023+ OpenF1 era boundary enforcement
- Large series/dataframes stored in ArtifactStore; compact metrics + dataset_id returned.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import numpy as np
from google.adk.agents.llm_agent import LlmAgent
from a2a.types import AgentCard, AgentSkill, AgentInterface

from backend.app.a2a.artifact_store import get_artifact_store
from backend.app.data.circuit_corners import get_circuit_corner_engine
from backend.app.data.openf1_client import get_openf1_client
from backend.app.agent.tools.corner_compare import (
    compare_corner_telemetry as base_compare_corners,
    compute_corner_metrics,
)
from backend.app.agent.tools.telemetry import (
    compare_full_lap_telemetry as base_compare_full_lap,
)
from backend.app.agent.tools.strategy import (
    analyze_tyre_stints as base_analyze_stints,
)

logger = logging.getLogger("pitwall.a2a.telemetry")


class TelemetryAgent:
    """Specialist agent for OpenF1 car sensor telemetry & strategy (2023–present)."""

    def __init__(self, name: str = "telemetry_agent"):
        self.name = name
        self.artifact_store = get_artifact_store()
        self.corner_engine = get_circuit_corner_engine()
        self.openf1_client = get_openf1_client()
        self.adk_agent = self._build_adk_agent()

    def _build_adk_agent(self) -> LlmAgent:
        """Create ADK LlmAgent wrapper."""
        return LlmAgent(
            name=self.name,
            model="gemini-3.8-flash",
            instruction=(
                "You are the PitWall AI Telemetry & Strategy Engineer. Analyze high-frequency car sensor "
                "telemetry (speed, throttle, brake, gear, delta) and tyre stint degradation for 2023-present "
                "Formula 1 sessions using OpenF1. Never hallucinate sensor readings."
            ),
            tools=[self.compare_corners, self.compare_full_lap, self.analyze_tyre_stints],
        )

    def _check_era_boundary(self, year: int) -> Optional[Dict[str, Any]]:
        """Enforce strict 2023+ OpenF1 era boundary."""
        if year < 2023:
            return {
                "success": False,
                "era_boundary": True,
                "year": year,
                "message": (
                    f"Car sensor telemetry is available for the 2023–present seasons via OpenF1. "
                    f"For {year}, only lap-by-lap pace and finishing statistics are available via historical DuckDB data."
                ),
                "suggestion": "query_historical_f1",
            }
        return None

    def compare_corners(
        self,
        year: int,
        grand_prix: str,
        session_type: str,
        driver_1: str,
        driver_2: str,
        corner: str,
        lap_number_1: Optional[int] = None,
        lap_number_2: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Compare corner telemetry between two drivers.
        Uses CircuitCornerEngine for nickname-first resolution (e.g. Suzuka 130R -> Turn 15).
        Returns structured unknown_corner hint if corner nickname is unrecognized.
        Stores heavy interpolated series in ArtifactStore and returns compact metrics + dataset_id.
        """
        # 1. Era boundary check
        era_check = self._check_era_boundary(year)
        if era_check:
            return era_check

        # 2. Corner Nickname Resolution via CircuitCornerEngine
        corner_res = self.corner_engine.resolve_corner(
            circuit_query=grand_prix,
            corner_query=corner,
            year=year,
        )

        if not corner_res.get("resolved"):
            logger.info(f"Unknown corner query '{corner}' at {grand_prix}.")
            return {
                "success": False,
                "unknown_corner": True,
                "corner_query": corner,
                "grand_prix": grand_prix,
                "year": year,
                "hint": corner_res.get("hint", f"Unknown corner '{corner}' at {grand_prix}."),
            }

        # 3. Execute base corner comparison
        turn_num = corner_res.get("turn_number")
        corner_nick = corner_res.get("nickname")

        try:
            base_res = base_compare_corners(
                year=year,
                grand_prix=grand_prix,
                session_type=session_type,
                driver1=driver_1,
                driver2=driver_2,
                corner=str(turn_num) if turn_num else corner,
                lap_number_1=lap_number_1,
                lap_number_2=lap_number_2,
            )

            if not base_res or ("success" in base_res and not base_res["success"]):
                return base_res if isinstance(base_res, dict) else {"success": False, "error": "Corner telemetry failed"}

            # 4. Store raw telemetry arrays in ArtifactStore
            dataset_metadata = {
                "domain": "corner_telemetry",
                "year": year,
                "grand_prix": grand_prix,
                "session_type": session_type,
                "drivers": [driver_1, driver_2],
                "turn_number": turn_num,
                "corner_nickname": corner_nick,
                "metrics": base_res.get("metrics"),
            }
            dataset_id = self.artifact_store.put(
                data={
                    "metrics": base_res.get("metrics"),
                    "chart_spec": base_res.get("chart", {}).get("spec"),
                    "minimap_spec": base_res.get("minimap", {}).get("spec"),
                    "metadata": base_res.get("chart", {}).get("metadata"),
                },
                metadata=dataset_metadata,
                ttl_seconds=3600,
            )

            # 5. Return compact metrics + dataset_id
            metrics_dict = base_res.get("metrics", {})
            apex_spd = metrics_dict.get("apex_min_speed_kph") or metrics_dict.get("apex_min_speed") or {}
            if isinstance(apex_spd, dict) and "driver_a" in apex_spd:
                spd_a = apex_spd.get("driver_a")
                spd_b = apex_spd.get("driver_b")
                delta_val = apex_spd.get("delta", 0.0)
                apex_summary_str = f"{driver_1}: {spd_a} km/h, {driver_2}: {spd_b} km/h (delta: {delta_val:+.1f} km/h)"
            else:
                apex_summary_str = str(apex_spd)

            return {
                "success": True,
                "domain": "corner_telemetry",
                "dataset_id": dataset_id,
                "metrics": metrics_dict,
                "corner_info": corner_res,
                "summary": (
                    f"Corner comparison for {driver_1} vs {driver_2} at {grand_prix} {corner_nick} (Turn {turn_num}) "
                    f"computed successfully. Apex speeds: {apex_summary_str}. "
                    f"Stored in artifact '{dataset_id}'."
                ),
                "trace": base_res.get("trace", {}),
            }
        except Exception as e:
            logger.error(f"Error in compare_corners: {e}", exc_info=True)
            return {
                "success": False,
                "domain": "corner_telemetry",
                "error": str(e),
                "message": f"Failed to compare corner telemetry for {driver_1} vs {driver_2}: {str(e)}",
            }

    def compare_full_lap(
        self,
        year: int,
        grand_prix: str,
        session_type: str,
        driver_1: str,
        driver_2: str,
        lap_number_1: Optional[int] = None,
        lap_number_2: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Compare full-lap telemetry between two drivers."""
        era_check = self._check_era_boundary(year)
        if era_check:
            return era_check

        try:
            base_res = base_compare_full_lap(
                year=year,
                grand_prix=grand_prix,
                session_type=session_type,
                driver1=driver_1,
                driver2=driver_2,
                lap_number_1=lap_number_1,
                lap_number_2=lap_number_2,
            )

            if not base_res or ("success" in base_res and not base_res["success"]):
                return base_res if isinstance(base_res, dict) else {"success": False, "error": "Full lap comparison failed"}

            dataset_metadata = {
                "domain": "full_lap_telemetry",
                "year": year,
                "grand_prix": grand_prix,
                "session_type": session_type,
                "drivers": [driver_1, driver_2],
                "metrics": base_res.get("metrics"),
            }
            dataset_id = self.artifact_store.put(
                data={
                    "metrics": base_res.get("metrics"),
                    "chart_spec": base_res.get("chart", {}).get("spec"),
                    "metadata": base_res.get("chart", {}).get("metadata"),
                },
                metadata=dataset_metadata,
                ttl_seconds=3600,
            )

            lap_delta = base_res.get("metrics", {}).get("lap_times", {}).get("delta_s", 0)
            return {
                "success": True,
                "domain": "full_lap_telemetry",
                "dataset_id": dataset_id,
                "metrics": base_res.get("metrics"),
                "summary": (
                    f"Full lap telemetry overlay for {driver_1} vs {driver_2} at {grand_prix} {year} "
                    f"computed successfully. Lap delta: {lap_delta:.3f}s. "
                    f"Stored in artifact '{dataset_id}'."
                ),
                "trace": base_res.get("trace", {}),
            }
        except Exception as e:
            logger.error(f"Error in compare_full_lap: {e}", exc_info=True)
            return {
                "success": False,
                "domain": "full_lap_telemetry",
                "error": str(e),
                "message": f"Failed to compare full lap telemetry for {driver_1} vs {driver_2}: {str(e)}",
            }

    def analyze_tyre_stints(
        self,
        year: int,
        grand_prix: str,
        session_type: str = "Race",
        drivers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Analyze tyre stint pace degradation."""
        era_check = self._check_era_boundary(year)
        if era_check:
            return era_check

        try:
            base_res = base_analyze_stints(
                year=year,
                grand_prix=grand_prix,
                session_type=session_type,
                drivers=drivers,
            )

            if not base_res or ("success" in base_res and not base_res["success"]):
                return base_res if isinstance(base_res, dict) else {"success": False, "error": "Stint analysis failed"}

            # Validate that driver data or metrics were produced
            drivers_data = base_res.get("drivers_data", {})
            if not drivers_data and "metrics" not in base_res:
                return {"success": False, "error": "No stint data available for requested drivers/session"}

            resolved_drivers = list(drivers_data.keys()) or (drivers or [])
            dataset_metadata = {
                "domain": "tyre_degradation",
                "year": year,
                "grand_prix": grand_prix,
                "session_type": session_type,
                "drivers": resolved_drivers,
            }
            dataset_id = self.artifact_store.put(
                data={
                    "metrics": base_res.get("metrics"),
                    "drivers_data": drivers_data,
                    "chart_spec": base_res.get("chart", {}).get("spec"),
                    "metadata": base_res.get("chart", {}).get("metadata"),
                },
                metadata=dataset_metadata,
                ttl_seconds=3600,
            )

            return {
                "success": True,
                "domain": "tyre_degradation",
                "dataset_id": dataset_id,
                "metrics": base_res.get("metrics"),
                "drivers_data": drivers_data,
                "summary": (
                    f"Tyre stint degradation analysis for {', '.join(resolved_drivers)} at {grand_prix} {year} completed. "
                    f"Stored in artifact '{dataset_id}'."
                ),
                "trace": base_res.get("trace", {}),
            }
        except Exception as e:
            logger.error(f"Error in analyze_tyre_stints: {e}", exc_info=True)
            return {
                "success": False,
                "domain": "tyre_degradation",
                "error": str(e),
                "message": f"Failed to analyze tyre stints: {str(e)}",
            }

    @classmethod
    def get_agent_card(cls, base_url: str = "http://localhost:8000/a2a/telemetry") -> AgentCard:
        """Construct standard A2A AgentCard for TelemetryAgent."""
        return AgentCard(
            name="telemetry_agent",
            description="Formula 1 Car Telemetry & Tyre Strategy Agent (2023-present) powered by OpenF1 and CircuitCornerEngine.",
            version="1.0.0",
            supported_interfaces=[
                AgentInterface(url=base_url, protocol_binding="HTTP_JSON", protocol_version="1.0")
            ],
            skills=[
                AgentSkill(
                    id="compare_corners",
                    name="compare_corners",
                    description="Compares high-frequency telemetry across a corner (braking point, apex speed, throttle pickup).",
                    tags=["telemetry", "corner", "speed", "throttle", "brake"],
                ),
                AgentSkill(
                    id="compare_full_lap",
                    name="compare_full_lap",
                    description="Compares full-lap telemetry overlay and sector times between two drivers.",
                    tags=["telemetry", "full_lap", "overlay", "sectors"],
                ),
                AgentSkill(
                    id="analyze_tyre_stints",
                    name="analyze_tyre_stints",
                    description="Analyzes tyre stint degradation and race pace.",
                    tags=["strategy", "tyres", "stints", "degradation"],
                ),
            ],
        )


_telemetry_agent_instance: Optional[TelemetryAgent] = None


def get_telemetry_agent() -> TelemetryAgent:
    """Get singleton TelemetryAgent."""
    global _telemetry_agent_instance
    if _telemetry_agent_instance is None:
        _telemetry_agent_instance = TelemetryAgent()
    return _telemetry_agent_instance
