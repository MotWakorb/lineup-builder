"""CLI interface: zip code → pick provider → generate ECM YAML."""

import argparse
import getpass
import os
import sys

from sd_client import SDClient
from yaml_generator import generate_rules, write_yaml


def prompt_credentials() -> tuple[str, str]:
    """Get SD credentials from env vars or interactive prompt."""
    username = os.environ.get("SD_USERNAME") or input("Schedules Direct username: ")
    password = os.environ.get("SD_PASSWORD") or getpass.getpass("Schedules Direct password: ")
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


def main():
    """Entry point for the lineup-builder CLI."""
    parser = argparse.ArgumentParser(
        description="Generate ECM auto-creation YAML from a TV provider lineup",
    )
    parser.add_argument("zipcode", nargs="?", help="US zip code (prompted if not given)")
    parser.add_argument("-o", "--output", default=None, help="Output YAML file path (default: <lineup_id>.yaml)")
    parser.add_argument("--country", default="USA", help="Country code (default: USA)")
    args = parser.parse_args()

    zipcode = args.zipcode or input("Enter zip code: ")

    username, password = prompt_credentials()
    client = SDClient(username, password)

    try:
        print("Authenticating with Schedules Direct...")
        client.authenticate()
        print("OK")

        print(f"Looking up providers for {zipcode}...")
        providers = client.get_headends(args.country, zipcode)
        if not providers:
            print("No providers found for that zip code.", file=sys.stderr)
            sys.exit(1)

        provider = pick_provider(providers)
        lineup_id = provider["lineup_id"]
        print(f"\nFetching lineup: {provider['name']}...")

        channels = client.get_lineup(lineup_id)
        print(f"Found {len(channels)} channels.")

        rules = generate_rules(channels)
        output_path = args.output or f"{lineup_id}.yaml"
        write_yaml(rules, output_path)
        print(f"\nWrote {len(rules['rules'])} rules to {output_path}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
