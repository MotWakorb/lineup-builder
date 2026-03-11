"""CLI interface: interactive or config-driven batch mode."""

import argparse
import getpass
import os
import sys
from pathlib import Path

import yaml

from sd_client import SDClient
from yaml_generator import generate_rules, write_yaml, DEFAULT_STRIP_SUFFIXES


def load_config(path: str) -> dict:
    """Load config.yaml, returning empty dict if not found."""
    p = Path(path)
    if not p.exists():
        return {}
    with open(p) as f:
        return yaml.safe_load(f) or {}


def get_credentials(config: dict) -> tuple[str, str]:
    """Get SD credentials from env vars, config, or interactive prompt."""
    creds = config.get("credentials", {})
    username = os.environ.get("SD_USERNAME") or creds.get("username") or input("Schedules Direct username: ")
    password = os.environ.get("SD_PASSWORD") or creds.get("password") or getpass.getpass("Schedules Direct password: ")
    return username, password


def pick_provider(providers: list[dict]) -> dict:
    """Display provider list and let user choose."""
    print(f"\nFound {len(providers)} providers:\n")
    for i, p in enumerate(providers, 1):
        print(f"  {i:3d}. [{p['transport']}] {p['name']} ({p['location']})")

    while True:
        try:
            choice = int(input(f"\nSelect provider (1-{len(providers)}): "))
            if 1 <= choice <= len(providers):
                return providers[choice - 1]
        except (ValueError, EOFError):
            pass
        print("Invalid selection, try again.")


def detect_market(providers: list[dict]) -> str | None:
    """Auto-detect the local TV market from provider locations.

    Picks the most common location across all providers, which is
    typically the nearest major city / DMA name.
    """
    from collections import Counter
    locations = [p["location"] for p in providers if p["location"]]
    if not locations:
        return None
    most_common = Counter(locations).most_common(1)[0][0]
    return most_common


def filter_providers(providers: list[dict], exclude_locations: list[str]) -> list[dict]:
    """Remove providers whose location matches any exclusion substring."""
    if not exclude_locations:
        return providers
    filtered = []
    for p in providers:
        loc = p["location"].lower()
        if any(excl.lower() in loc for excl in exclude_locations):
            continue
        filtered.append(p)
    return filtered


def find_provider(providers: list[dict], transport: str | None,
                  name_filter: str | None, location_filter: str | None) -> dict | None:
    """Find first provider matching optional transport, name, and location filters."""
    for p in providers:
        if transport and transport.lower() not in p["transport"].lower():
            continue
        if name_filter and name_filter.lower() not in p["name"].lower():
            continue
        if location_filter and location_filter.lower() not in p["location"].lower():
            continue
        return p
    return None


def process_lineup(client: SDClient, country: str, zipcode: str, provider: dict,
                   output_path: str, strip_suffixes: list[str]) -> None:
    """Fetch a lineup and write the ECM YAML."""
    lineup_id = provider["lineup_id"]
    print(f"  Fetching lineup: {provider['name']} ({lineup_id})...")
    channels = client.get_lineup(lineup_id)
    print(f"  Found {len(channels)} channels.")
    rules = generate_rules(channels, strip_suffixes)
    write_yaml(rules, output_path)
    print(f"  Wrote {len(rules['rules'])} rules to {output_path}")


def run_batch(client: SDClient, config: dict) -> None:
    """Process all lineups defined in config."""
    lineups = config.get("lineups", [])
    if not lineups:
        print("No lineups defined in config. Add entries under 'lineups:' key.", file=sys.stderr)
        sys.exit(1)

    strip_suffixes = config.get("strip_suffixes", DEFAULT_STRIP_SUFFIXES)
    exclude_locations = config.get("exclude_locations", [])
    output_dir = config.get("output_dir", "output")

    for i, entry in enumerate(lineups, 1):
        zipcode = str(entry["zipcode"])
        country = entry.get("country", "USA")
        transport = entry.get("transport")
        name_filter = entry.get("provider")
        location_filter = entry.get("location")
        output_file = entry.get("output", None)

        print(f"\n[{i}/{len(lineups)}] Zip: {zipcode}, filter: transport={transport}, provider={name_filter}, location={location_filter}")

        providers = client.get_headends(country, zipcode)
        if not providers:
            print(f"  No providers found for {zipcode}, skipping.", file=sys.stderr)
            continue

        providers = filter_providers(providers, exclude_locations)

        # Auto-detect market if no location filter specified
        if not location_filter:
            market = detect_market(providers)
            if market:
                print(f"  Detected market: {market}")
                location_filter = market

        provider = find_provider(providers, transport, name_filter, location_filter)
        if not provider:
            print(f"  No provider matched filters, skipping.", file=sys.stderr)
            available = ", ".join(f"{p['name']} ({p['location']})" for p in providers[:5])
            print(f"  Available: {available}...")
            continue

        out_path = os.path.join(output_dir, output_file or f"{provider['lineup_id']}.yaml")
        process_lineup(client, country, zipcode, provider, out_path, strip_suffixes)

    print("\nBatch complete.")


def run_interactive(client: SDClient, config: dict, zipcode: str, country: str, output: str | None) -> None:
    """Interactive mode: pick provider, generate YAML."""
    strip_suffixes = config.get("strip_suffixes", DEFAULT_STRIP_SUFFIXES)
    exclude_locations = config.get("exclude_locations", [])
    output_dir = config.get("output_dir", "output")

    print(f"Looking up providers for {zipcode}...")
    providers = client.get_headends(country, zipcode)
    if not providers:
        print("No providers found for that zip code.", file=sys.stderr)
        sys.exit(1)

    providers = filter_providers(providers, exclude_locations)
    if not providers:
        print("All providers excluded by location filter.", file=sys.stderr)
        sys.exit(1)

    market = detect_market(providers)
    if market:
        print(f"Detected market: {market}")
        # Filter to market providers only for a cleaner list
        market_providers = [p for p in providers if p["location"] == market]
        if market_providers:
            providers = market_providers

    provider = pick_provider(providers)
    out_path = output or os.path.join(output_dir, f"{provider['lineup_id']}.yaml")
    process_lineup(client, country, zipcode, provider, out_path, strip_suffixes)


def main():
    """Entry point for the lineup-builder CLI."""
    parser = argparse.ArgumentParser(
        description="Generate ECM auto-creation YAML from a TV provider lineup",
    )
    parser.add_argument("zipcode", nargs="?", help="US zip code (prompted if not given)")
    parser.add_argument("-o", "--output", default=None, help="Output YAML file path")
    parser.add_argument("-c", "--config", default="config.yaml", help="Config file path (default: config.yaml)")
    parser.add_argument("--country", default="USA", help="Country code (default: USA)")
    parser.add_argument("--batch", action="store_true", help="Process all lineups from config file")
    args = parser.parse_args()

    config = load_config(args.config)
    username, password = get_credentials(config)
    client = SDClient(username, password)

    try:
        print("Authenticating with Schedules Direct...")
        client.authenticate()
        print("OK")

        if args.batch:
            run_batch(client, config)
        else:
            zipcode = args.zipcode or input("Enter zip code: ")
            run_interactive(client, config, zipcode, args.country, args.output)
    finally:
        client.close()


if __name__ == "__main__":
    main()
