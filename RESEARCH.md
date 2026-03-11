# Lineup Builder Research

## Goal

Build rulesets that people can download to auto-build their Dispatcharr via ECM's auto channel pipeline (YAML outputs) — creating channel lineups identical to their TV providers.

## Data Sources Evaluated

### Gracenote Lineups API
- **Verdict: Not viable** — enterprise-only, no free tier, no self-service API keys
- Has the right data (channel numbers, station IDs, provider lineups by zip)
- Query: `?country=USA&postalCode=12804&api_key=[key]`
- Returns: lineup ID, headend ID, provider name, channel list with `prgSvcId`, `channelNumber`, tier, effective/expiration dates
- Lineup types: OTA, DIGITAL, CABLE, SATELLITE, IPTV, OTT, VIRTUAL
- Docs: https://documentation.gracenote.com/on-api/html/Content/dev-guide/Lineups%20Endpoint.htm

### TVGuide.com
- **Verdict: Dead end** — server-side rendered Nuxt.js app, no public API
- Backend endpoints (`backend.tvguide.com/components/...`) are CMS components, not data APIs
- Would require scraping rendered HTML — fragile, against ToS

### Schedules Direct (Winner)
- **Verdict: Best option** — $25/year nonprofit, open-source friendly, fully documented JSON API
- Docs: https://github.com/SchedulesDirect/JSON-Service/wiki/API-20141201
- Base URL: `https://json.schedulesdirect.org/20141201`
- Sources from Gracenote under the hood (logos say `source: "Gracenote"`)

## Schedules Direct API Details

### Authentication
```
POST /20141201/token
Body: {"username":"user@email.com", "password":"sha1hexpassword"}
Header for subsequent requests: token: <value>
Tokens valid 24 hours
```

### Key Endpoints

**Provider lookup by zip:**
```
GET /20141201/headends?country=USA&postalcode=60030
```
Returns all providers (Cable, Satellite, OTA, IPTV) at that location with lineup IDs.

**Lineup preview (channel map):**
```
GET /20141201/lineups/preview/{COUNTRY}-{LINEUP}-{DEVICE}
```
Returns per channel: stationID, channel number, providerCallsign, logicalChannelNumber

**Full lineup with station metadata:**
```
GET /20141201/lineups/{COUNTRY}-{LINEUP}-{DEVICE}
```
Returns:
- `map[]`: stationID, channel, providerCallsign, logicalChannelNumber, matchType
- `stations[]`: name, callsign, affiliate (e.g. "CBS"), broadcastLanguage, broadcaster (city/state), isCommercialFree, stationLogo[] (URL, height, width, category: dark/light/gray)
- `metadata`: lineup ID, transport type, modulation

### Constraints
- Auth required for all lineup endpoints
- 6 lineup adds per 24 hours per account
- 5000 stationIDs per schedule request

## ECM Auto-Creation YAML Format (Target Output)

ECM already has full YAML import/export at `/api/auto-creation/export/yaml` and `/api/auto-creation/import/yaml`.

### Field Mapping: SD → ECM YAML

| SD Field | ECM Rule Element |
|-|-|
| `channel` | `channel_number` in `create_channel` action |
| `name` / `callsign` | `stream_name_contains` condition + `name_template` |
| `affiliate` (CBS, NBC...) | Could group by network |
| `stationLogo[].URL` | `assign_logo` action |
| `stationID` | Could map to `tvg_id` for EPG matching |

### Example Generated YAML
```yaml
rules:
  - name: "WBBM - CBS (Channel 2)"
    conditions:
      - type: or
        conditions:
          - type: stream_name_contains
            value: "WBBM"
          - type: stream_name_contains
            value: "CBS Chicago"
    actions:
      - type: create_channel
        name_template: "WBBM"
        channel_number: 2
      - type: assign_logo
        logo_url: "https://schedulesdirect-api...s20454_dark_360w_270h.png"
      - type: assign_epg
        set_tvg_id: true
```

### Available ECM Condition Types (44 total)
- Stream metadata: `stream_name_matches/contains`, `stream_group_contains/matches`, `tvg_id_*`, `logo_exists`, `provider_is`, `quality_min/max`, `codec_is`, `has_audio_tracks`
- Channel checks: `has_channel`, `channel_exists_*`, `channel_in_group`, `normalized_name_*`
- Logical: `and`, `or`, `not`
- Special: `always`, `never`

### Available ECM Action Types (13 total)
- `create_channel` (name_template, channel_number: auto|int|"min-max", group_id, if_exists)
- `create_group` (name_template, if_exists)
- `merge_streams` (target: new_channel|existing_channel|auto, match_by: tvg_id|normalized_name|stream_group)
- `assign_logo`, `assign_tvg_id`, `assign_epg`, `assign_profile`
- `set_channel_number`, `set_variable`, `remove_from_channel`, `set_stream_priority`, `skip`, `stop_processing`, `log_match`

### Template Variables
`{stream_name}`, `{stream_group}`, `{tvg_id}`, `{tvg_name}`, `{quality}`, `{quality_raw}`, `{provider}`, `{provider_id}`, `{normalized_name}`

## Implementation Options

**Option A: Direct SD Integration in ECM** — "Import from Provider" wizard inside ECM. Best UX, but ties users to $25/yr SD subscription.

**Option B: Standalone CLI Tool** — User runs it once, imports the YAML. Lower coupling.

**Option C: Hybrid** — Use SD to generate starter packs for major providers, publish as community YAML packs. Broadest reach.

## Planned Architecture
```
lineup-builder/
├── sd_client.py          # Schedules Direct API wrapper
├── yaml_generator.py     # SD lineup → ECM YAML conversion
├── cli.py                # CLI: enter zip → pick provider → get YAML
└── presets/              # Pre-generated YAML packs for popular providers
```
