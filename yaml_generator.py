"""Convert Schedules Direct lineup data into ECM auto-creation YAML rulesets."""

from pathlib import Path

import yaml


def _build_rule(ch: dict) -> dict:
    """Build a single ECM auto-creation rule from a channel dict."""
    callsign = ch["callsign"]
    name = ch.get("name") or callsign
    channel = ch.get("channel")
    station_id = ch.get("station_id")
    logo_url = ch.get("logo_url")

    label = f"{callsign} - {ch['affiliate']} (Channel {channel})" if ch.get("affiliate") else f"{callsign} (Channel {channel})"

    # Condition: match on callsign
    conditions: list[dict] = [{"type": "stream_name_contains", "value": callsign}]

    # If name differs from callsign, use OR to match either
    if name != callsign:
        conditions = [{
            "type": "or",
            "conditions": [
                {"type": "stream_name_contains", "value": callsign},
                {"type": "stream_name_contains", "value": name},
            ],
        }]

    # Actions
    actions: list[dict] = [
        {
            "type": "create_channel",
            "name_template": name,
            "channel_number": int(channel) if str(channel).isdigit() else channel,
        },
    ]

    if logo_url:
        actions.append({"type": "assign_logo", "logo_url": logo_url})

    if station_id:
        actions.append({"type": "assign_epg", "set_tvg_id": True})

    return {"name": label, "conditions": conditions, "actions": actions}


def generate_rules(channels: list[dict]) -> dict:
    """Build ECM YAML ruleset from merged SD channel data.

    Args:
        channels: List of dicts with keys: channel, name, callsign,
                  affiliate, logo_url, station_id
    Returns:
        Dict ready to be serialized as YAML.
    """
    # Sort by channel number (numeric where possible)
    def sort_key(ch):
        c = ch.get("channel", "0")
        try:
            return (float(c), "")
        except (ValueError, TypeError):
            return (float("inf"), str(c))

    sorted_channels = sorted(channels, key=sort_key)

    rules = []
    for ch in sorted_channels:
        if not ch.get("callsign"):
            continue
        rules.append(_build_rule(ch))

    return {"rules": rules}


def write_yaml(rules: dict, path: str) -> None:
    """Write rules dict to a YAML file."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        yaml.dump(rules, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
