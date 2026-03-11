# Lineup Builder

A tool that converts TV provider channel lineups from Schedules Direct into ECM auto-creation YAML rulesets.

## Project Overview

- **Input**: Zip code + provider selection → Schedules Direct API
- **Output**: ECM-compatible YAML rulesets with channel numbers, names, logos, and EPG mappings
- **Target consumer**: ECM (Enhanced Channel Manager) auto-creation pipeline import

## Key Files

| File | Purpose |
|-|-|
| `RESEARCH.md` | Full research notes — SD API details, ECM YAML format, field mappings |
| `sd_client.py` | Schedules Direct API wrapper |
| `yaml_generator.py` | SD lineup → ECM YAML conversion |
| `cli.py` | CLI interface: zip → pick provider → get YAML |
| `presets/` | Pre-generated YAML packs for popular providers |

## Schedules Direct API

- Base URL: `https://json.schedulesdirect.org/20141201`
- Auth: POST `/token` with `{"username":"...", "password":"sha1hex"}` → 24hr token
- Providers: GET `/headends?country=USA&postalcode=XXXXX`
- Lineup: GET `/lineups/{LINEUP_ID}` → channel map + station metadata
- Docs: https://github.com/SchedulesDirect/JSON-Service/wiki/API-20141201

## ECM YAML Target Format

Rules are imported via ECM's `/api/auto-creation/import/yaml` endpoint. See `RESEARCH.md` for full field mapping and example output.

Key rule structure:
```yaml
rules:
  - name: "Station Name (Channel N)"
    conditions:
      - type: stream_name_contains
        value: "CALLSIGN"
    actions:
      - type: create_channel
        name_template: "Station Name"
        channel_number: N
      - type: assign_logo
        logo_url: "https://..."
      - type: assign_epg
        set_tvg_id: true
```

## Development

- Python project, uses `uv` for package management
- Dependencies: `httpx` (HTTP client), `pyyaml` (YAML output)
- No framework — CLI-first, keep it simple

## Related Project

ECM repo: `/home/lecaptainc/ecm/enhancedchannelmanager` (branch: `dev`)
- Auto-creation schema: `backend/auto_creation_schema.py`
- YAML import/export: `backend/routers/auto_creation.py`
- Frontend types: `frontend/src/types/autoCreation.ts`
