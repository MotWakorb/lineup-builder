"""Generate preset YAML packs for popular US providers.

Usage:
    SD_USERNAME=... SD_PASSWORD=... uv run python generate_presets.py

Requires a Schedules Direct account. Fetches lineups for major providers
and writes YAML files to presets/.
"""

import os
import sys

from sd_client import SDClient
from yaml_generator import generate_rules, write_yaml

# Popular US providers with representative zip codes.
# Each entry: (label, zip_code, transport_filter)
# The script picks the first matching provider for each.
POPULAR_PROVIDERS = [
    ("comcast-chicago", "60030", "Cable", "Comcast"),
    ("comcast-philadelphia", "19103", "Cable", "Comcast"),
    ("spectrum-nyc", "10001", "Cable", "Spectrum"),
    ("spectrum-la", "90001", "Cable", "Spectrum"),
    ("directv", "60030", "Satellite", "DirecTV"),
    ("dish", "60030", "Satellite", "DISH"),
    ("ota-chicago", "60030", "Antenna", None),
    ("ota-nyc", "10001", "Antenna", None),
    ("ota-la", "90001", "Antenna", None),
]


def find_provider(providers: list[dict], transport: str, name_filter: str | None) -> dict | None:
    """Find the first provider matching transport and optional name substring."""
    for p in providers:
        if transport.lower() not in p["transport"].lower():
            continue
        if name_filter and name_filter.lower() not in p["name"].lower():
            continue
        return p
    return None


def main():
    username = os.environ.get("SD_USERNAME")
    password = os.environ.get("SD_PASSWORD")
    if not username or not password:
        print("Set SD_USERNAME and SD_PASSWORD env vars.", file=sys.stderr)
        sys.exit(1)

    client = SDClient(username, password)
    try:
        client.authenticate()
        print("Authenticated.\n")

        for label, zipcode, transport, name_filter in POPULAR_PROVIDERS:
            print(f"--- {label} (zip: {zipcode}) ---")
            providers = client.get_headends("USA", zipcode)
            provider = find_provider(providers, transport, name_filter)
            if not provider:
                print(f"  No matching provider found, skipping.\n")
                continue

            print(f"  Provider: {provider['name']} ({provider['lineup_id']})")
            channels = client.get_lineup(provider["lineup_id"])
            rules = generate_rules(channels)
            out_path = f"presets/{label}.yaml"
            write_yaml(rules, out_path)
            print(f"  Wrote {len(rules['rules'])} rules to {out_path}\n")
    finally:
        client.close()


if __name__ == "__main__":
    main()
