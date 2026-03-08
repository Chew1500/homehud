"""LLM-powered discovery engine — generates recommendations from taste profile."""

from __future__ import annotations

import json
import logging
import re

from discovery.storage import DiscoveryStorage

log = logging.getLogger("home-hud.discovery.engine")

_DISCOVERY_PROMPT = (
    "You are a media recommendation engine. Based on the user's taste "
    "profile and library, suggest new movies and TV shows they would "
    "enjoy that are NOT already in their library.\n\n"
    "## Taste Profile\n{taste_summary}\n\n"
    "## Already in Library (do NOT recommend these)\n{library_titles}\n\n"
    "## Instructions\n"
    "- Recommend {num_movies} movies and {num_series} TV series\n"
    "- Focus on titles the user is likely to enjoy based on their taste\n"
    "- Include a mix of well-known and hidden gems\n"
    "- Each recommendation needs a brief reason matching their taste\n"
    "- Respond with ONLY a JSON array, no other text\n\n"
    "## Response Format\n"
    "```json\n"
    "[\n"
    '  {{"title": "Movie Title", "media_type": "movie", "year": 2023,\n'
    '    "reason": "Brief reason", "genres": ["Genre1"], '
    '"confidence": 0.8}},\n'
    '  {{"title": "Series Title", "media_type": "series", "year": 2022,\n'
    '    "reason": "Brief reason", "genres": ["Genre1"], '
    '"confidence": 0.7}}\n'
    "]\n```"
)


class DiscoveryEngine:
    """Generates media recommendations using the taste profile and an LLM."""

    def __init__(self, storage: DiscoveryStorage, llm, config: dict):
        self._storage = storage
        self._llm = llm
        self._config = config
        self._max_recs = config.get("discovery_max_recommendations", 10)

    def generate(self) -> list[dict]:
        """Generate new recommendations, replacing existing active ones."""
        taste_summary = self._storage.get_taste_summary()
        if "No taste profile" in taste_summary:
            log.info("No taste profile yet, skipping discovery")
            return []

        library_titles = self._format_library_titles()
        num_movies = self._max_recs // 2
        num_series = self._max_recs - num_movies

        prompt = _DISCOVERY_PROMPT.format(
            taste_summary=taste_summary,
            library_titles=library_titles,
            num_movies=num_movies,
            num_series=num_series,
        )

        response = self._llm.respond(prompt)
        recommendations = self._parse_recommendations(response)

        if not recommendations:
            log.warning("No valid recommendations parsed from LLM response")
            return []

        # Filter against existing library
        existing_titles = {t.lower() for t in self._storage.get_library_titles()}
        filtered = [
            r for r in recommendations
            if r["title"].lower() not in existing_titles
        ]

        # Clear old active recommendations and save new ones
        self._storage.clear_active_recommendations()
        for rec in filtered[:self._max_recs]:
            self._storage.add_recommendation(rec)

        log.info("Generated %d recommendations (%d after filtering)",
                 len(recommendations), len(filtered))
        return filtered[:self._max_recs]

    def _format_library_titles(self) -> str:
        """Format library titles for the prompt, truncated to 50."""
        titles = self._storage.get_library_titles()
        if len(titles) > 50:
            titles = titles[:50]
            return ", ".join(titles) + f" ... and {len(titles) - 50} more"
        return ", ".join(titles) if titles else "(empty library)"

    def _parse_recommendations(self, response: str) -> list[dict]:
        """Parse JSON recommendations from LLM response, handling code fences."""
        # Strip markdown code fences if present
        text = response.strip()
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to find a JSON array in the response
            match = re.search(r"\[[\s\S]*\]", text)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    log.warning("Failed to parse recommendations JSON")
                    return []
            else:
                log.warning("No JSON array found in LLM response")
                return []

        if not isinstance(data, list):
            log.warning("Expected JSON array, got %s", type(data).__name__)
            return []

        results = []
        for item in data:
            if not isinstance(item, dict) or "title" not in item:
                continue
            results.append({
                "title": item["title"],
                "media_type": item.get("media_type", "movie"),
                "year": item.get("year"),
                "reason": item.get("reason", ""),
                "genres": item.get("genres", []),
                "confidence": min(1.0, max(0.0, float(item.get("confidence", 0.5)))),
            })
        return results
