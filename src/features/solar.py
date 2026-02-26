"""Solar monitoring feature — answer solar production queries via voice."""

import logging
import re
from datetime import datetime

from enphase.storage import SolarStorage
from features.base import BaseFeature
from llm.base import BaseLLM

log = logging.getLogger("home-hud.features.solar")

# Broad match for any energy-related query
_ANY_SOLAR = re.compile(
    r"\b(solar|panels?|inverters?|production|generating|energy|power|grid"
    r"|enphase|kilowatts?|watts?)\b",
    re.IGNORECASE,
)

# Complex query indicators — route these to the LLM
_COMPLEX = re.compile(
    r"\b(compare|yesterday|last\s+week|trend|average|why|similar|history"
    r"|month|week|better|worse|typical|forecast|predict|explain)\b",
    re.IGNORECASE,
)

# Simple query patterns
_CURRENT_PRODUCTION = re.compile(
    r"\b(?:how\s+much|what(?:'s| is))\s+(?:solar|power|energy)\s+"
    r"(?:am\s+I\s+)?(?:producing|generating|making)\b",
    re.IGNORECASE,
)
_CURRENT_PRODUCTION_ALT = re.compile(
    r"\b(?:what(?:'s| is)\s+(?:my\s+)?(?:solar|energy)\s+production)\b",
    re.IGNORECASE,
)
_TODAY_CONSUMPTION = re.compile(
    r"\b(?:how\s+much)\s+(?:power|energy)\s+(?:have\s+I\s+)?used\s+today\b",
    re.IGNORECASE,
)
_TODAY_PRODUCTION = re.compile(
    r"\b(?:how\s+much)\s+(?:solar|energy)\s+(?:have\s+I\s+)?generated\s+today\b",
    re.IGNORECASE,
)
_GRID_STATUS = re.compile(
    r"\b(?:am\s+I\s+)?(?:exporting|importing)\s+(?:to|from)\s+(?:the\s+)?grid\b",
    re.IGNORECASE,
)
_PANEL_HEALTH = re.compile(
    r"\b(?:how\s+are)\s+(?:my\s+)?(?:panels?|inverters?)\b",
    re.IGNORECASE,
)
_SYSTEM_STATUS = re.compile(
    r"\b(?:is\s+(?:the\s+)?(?:solar\s+)?system\s+(?:online|working|up))\b",
    re.IGNORECASE,
)

_SOLAR_SYSTEM_PROMPT = (
    "You are a solar energy analyst assistant on a home automation system. "
    "Analyze the solar production data provided and answer the user's question. "
    "Keep responses concise — 2 to 3 sentences max. Be conversational and direct. "
    "Use kW for power and kWh for energy. Round to 1 decimal place."
)


class SolarFeature(BaseFeature):
    """Answers solar production queries using stored Enphase data.

    Simple queries (current production, today's totals, grid status) are
    answered directly. Complex analytical queries (comparisons, trends)
    are delegated to the LLM with relevant data as context.
    """

    def __init__(self, config: dict, storage: SolarStorage, llm: BaseLLM):
        super().__init__(config)
        self._storage = storage
        self._llm = llm

    @property
    def description(self) -> str:
        return (
            'Solar monitoring: triggered by "solar", "panels", "inverters", '
            '"production", "generating", "energy", "power", "grid". '
            'Commands: "how much solar am I producing", "how much energy have I used today", '
            '"am I exporting to the grid", "how are my panels".'
        )

    def matches(self, text: str) -> bool:
        return bool(_ANY_SOLAR.search(text))

    def handle(self, text: str) -> str:
        # Complex queries go to LLM
        if _COMPLEX.search(text):
            return self._handle_complex(text)

        # Simple query patterns
        if _CURRENT_PRODUCTION.search(text) or _CURRENT_PRODUCTION_ALT.search(text):
            return self._handle_current()

        if _TODAY_CONSUMPTION.search(text):
            return self._handle_today_consumption()

        if _TODAY_PRODUCTION.search(text):
            return self._handle_today_production()

        if _GRID_STATUS.search(text):
            return self._handle_grid_status()

        if _PANEL_HEALTH.search(text):
            return self._handle_panel_health()

        if _SYSTEM_STATUS.search(text):
            return self._handle_system_status()

        # Fallback: try current production for generic solar queries
        return self._handle_current()

    # -- Simple query handlers --

    def _handle_current(self) -> str:
        latest = self._storage.get_latest()
        if not latest:
            return "I don't have any solar data yet. The system may still be starting up."

        prod_kw = latest["production_w"] / 1000
        cons_kw = latest["consumption_w"] / 1000
        net_kw = latest["net_w"] / 1000

        if net_kw > 0:
            return (
                f"You're producing {prod_kw:.1f} kilowatts and using {cons_kw:.1f} kilowatts. "
                f"You're exporting {net_kw:.1f} kilowatts to the grid."
            )
        return (
            f"You're producing {prod_kw:.1f} kilowatts and using {cons_kw:.1f} kilowatts. "
            f"You're importing {abs(net_kw):.1f} kilowatts from the grid."
        )

    def _handle_today_consumption(self) -> str:
        summary = self._storage.get_today_summary()
        if not summary:
            return "I don't have enough data for today's consumption yet."

        cons_kwh = summary["total_consumption_wh"] / 1000
        return f"You've used {cons_kwh:.1f} kilowatt hours today."

    def _handle_today_production(self) -> str:
        summary = self._storage.get_today_summary()
        if not summary:
            return "I don't have enough data for today's production yet."

        prod_kwh = summary["total_production_wh"] / 1000
        return f"You've generated {prod_kwh:.1f} kilowatt hours of solar energy today."

    def _handle_grid_status(self) -> str:
        latest = self._storage.get_latest()
        if not latest:
            return "I don't have any solar data yet."

        net_kw = latest["net_w"] / 1000
        if net_kw > 0.05:
            return f"Yes, you're exporting {net_kw:.1f} kilowatts to the grid."
        if net_kw < -0.05:
            return f"No, you're importing {abs(net_kw):.1f} kilowatts from the grid."
        return "You're roughly breaking even — neither importing nor exporting."

    def _handle_panel_health(self) -> str:
        latest = self._storage.get_latest()
        if not latest:
            return "I don't have any solar data yet."

        # Get latest inverter data from DB
        today = datetime.now().strftime("%Y-%m-%d")
        rows = self._storage._conn.execute(
            "SELECT serial_number, watts, max_watts FROM inverter_readings "
            "WHERE timestamp LIKE ? "
            "ORDER BY timestamp DESC "
            "LIMIT 100",
            (f"{today}%",),
        ).fetchall()

        if not rows:
            prod_kw = latest["production_w"] / 1000
            return (
                f"The system is producing {prod_kw:.1f} kilowatts "
                "but I don't have individual inverter data yet."
            )

        # Deduplicate to latest reading per serial
        seen = {}
        for r in rows:
            serial = r["serial_number"]
            if serial not in seen:
                seen[serial] = {"watts": r["watts"], "max_watts": r["max_watts"]}

        total = len(seen)
        underperformers = [
            s for s, d in seen.items()
            if d["max_watts"] > 0 and d["watts"] < d["max_watts"] * 0.3
        ]

        if underperformers:
            return (
                f"{total} inverters reporting. "
                f"{len(underperformers)} appear to be underperforming."
            )
        return f"All {total} inverters are reporting and performing normally."

    def _handle_system_status(self) -> str:
        latest = self._storage.get_latest()
        if not latest:
            return "I don't have any data from the solar system yet. It may still be starting up."

        prod_kw = latest["production_w"] / 1000
        if prod_kw > 0:
            return f"The solar system is online and producing {prod_kw:.1f} kilowatts."
        return (
            "The solar system is online but not currently producing "
            "— it may be nighttime or cloudy."
        )

    # -- Complex query handler (LLM-assisted) --

    def _handle_complex(self, text: str) -> str:
        """Gather context data and send to LLM for analytical response."""
        context_parts = []

        # Today's summary
        summary = self._storage.get_today_summary()
        if summary:
            context_parts.append(
                f"Today ({summary['date']}): "
                f"{summary['total_production_wh'] / 1000:.1f} kWh produced, "
                f"{summary['total_consumption_wh'] / 1000:.1f} kWh consumed, "
                f"peak {summary['peak_production_w'] / 1000:.1f} kW, "
                f"{summary['reading_count']} readings"
            )
            if summary.get("avg_temperature_c") is not None:
                context_parts[-1] += (
                    f", avg temp {summary['avg_temperature_c']:.0f}C"
                    f", avg clouds {summary['avg_cloud_cover_pct']:.0f}%"
                )

        # Recent daily summaries for comparison
        recent = self._storage.get_daily_summaries(days=7)
        if recent:
            context_parts.append("Recent daily summaries:")
            for day in recent:
                line = (
                    f"  {day['date']}: "
                    f"{day['total_production_wh'] / 1000:.1f} kWh produced, "
                    f"peak {day['peak_production_w'] / 1000:.1f} kW"
                )
                if day.get("avg_temperature_c") is not None:
                    line += f", {day['avg_temperature_c']:.0f}C"
                context_parts.append(line)

        # Current reading
        latest = self._storage.get_latest()
        if latest:
            context_parts.append(
                f"Current: {latest['production_w'] / 1000:.1f} kW production, "
                f"{latest['consumption_w'] / 1000:.1f} kW consumption"
            )

        if not context_parts:
            return "I don't have enough solar data to answer that yet."

        context = "\n".join(context_parts)
        prompt = (
            f"{_SOLAR_SYSTEM_PROMPT}\n\n"
            f"Solar data:\n{context}\n\n"
            f"User question: {text}"
        )

        return self._llm.respond(prompt)
