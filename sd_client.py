"""Schedules Direct API client."""

import hashlib

import httpx

SD_BASE_URL = "https://json.schedulesdirect.org/20141201"


class SDError(Exception):
    """Raised when the SD API returns an error response."""

    def __init__(self, code: int, message: str):
        self.code = code
        super().__init__(f"SD API error {code}: {message}")


class SDClient:
    """Wrapper for the Schedules Direct JSON API."""

    def __init__(self, username: str, password: str):
        self.username = username
        self.password_hash = hashlib.sha1(password.encode()).hexdigest()
        self.token: str | None = None
        self._http = httpx.Client(base_url=SD_BASE_URL)

    def _headers(self) -> dict[str, str]:
        """Build request headers, including token if authenticated."""
        h = {"User-Agent": "lineup-builder/0.1"}
        if self.token:
            h["token"] = self.token
        return h

    def authenticate(self) -> str:
        """POST /token — obtain a 24hr session token."""
        resp = self._http.post(
            "/token",
            json={"username": self.username, "password": self.password_hash},
            headers=self._headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code", 0) != 0:
            raise SDError(data["code"], data.get("message", "authentication failed"))
        self.token = data["token"]
        return self.token

    def _ensure_auth(self):
        if not self.token:
            self.authenticate()

    def get_headends(self, country: str, postalcode: str) -> list[dict]:
        """GET /headends — list providers for a zip code.

        Returns flat list of providers, each with keys:
            lineup_id, name, location, transport (Cable/Satellite/OTA/IPTV)
        """
        self._ensure_auth()
        resp = self._http.get(
            "/headends",
            params={"country": country, "postalcode": postalcode},
            headers=self._headers(),
        )
        resp.raise_for_status()
        headends = resp.json()
        providers = []
        for headend in headends:
            transport = headend.get("transport", "Unknown")
            location = headend.get("location", "")
            for lineup in headend.get("lineups", []):
                providers.append({
                    "lineup_id": lineup["lineup"],
                    "name": lineup.get("name", ""),
                    "location": location,
                    "transport": transport,
                })
        return providers

    def get_lineup(self, lineup_id: str) -> list[dict]:
        """GET /lineups/preview/{id} — channel map without adding lineup.

        Returns list of channel dicts, each with:
            channel, name, callsign, affiliate, station_id
        """
        self._ensure_auth()
        resp = self._http.get(
            f"/lineups/preview/{lineup_id}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        entries = resp.json()

        channels = []
        for entry in entries:
            channels.append({
                "channel": entry.get("channel"),
                "name": entry.get("name", ""),
                "callsign": entry.get("callsign", ""),
                "affiliate": entry.get("affiliate", ""),
                "logo_url": None,
                "station_id": entry.get("stationID"),
            })

        return channels

    def close(self):
        self._http.close()
