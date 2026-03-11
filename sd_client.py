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
        """GET /lineups/{id} — full channel map + station metadata.

        Returns list of merged channel dicts, each with:
            channel, name, callsign, affiliate, logo_url, station_id
        """
        self._ensure_auth()
        resp = self._http.get(
            f"/lineups/{lineup_id}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        data = resp.json()

        # Index stations by stationID for O(1) lookup
        stations = {}
        for s in data.get("stations", []):
            stations[s["stationID"]] = s

        channels = []
        for entry in data.get("map", []):
            station_id = entry.get("stationID")
            station = stations.get(station_id, {})

            # Pick best logo: prefer "dark" category, largest width
            logo_url = None
            logos = station.get("stationLogo", []) or station.get("logo", []) or []
            if logos:
                dark_logos = [l for l in logos if l.get("category") == "dark"]
                best = max(dark_logos or logos, key=lambda l: l.get("width", 0))
                logo_url = best.get("URL")

            channel_num = entry.get("channel", entry.get("logicalChannelNumber"))

            channels.append({
                "channel": channel_num,
                "name": station.get("name", ""),
                "callsign": station.get("callsign", ""),
                "affiliate": station.get("affiliate", ""),
                "logo_url": logo_url,
                "station_id": station_id,
            })

        return channels

    def close(self):
        self._http.close()
