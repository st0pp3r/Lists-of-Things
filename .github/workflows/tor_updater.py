import requests
from pathlib import Path
import json
from datetime import datetime
import re

FEED_URL = "https://onionoo.torproject.org/details"
OUTPUT_DIR = Path("tor")

MITRE = [
    {
        "tactic": "Command and Control",
        "techniques": ["T1090", "T1090.003"]
    }
]

# Regex for addresses with ports
IPV4_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}:\d+$")
IPV6_RE = re.compile(r"^\[([0-9a-fA-F:]+)\]:\d+$")


def ensure_output_dir():
    OUTPUT_DIR.mkdir(exist_ok=True)


def build_template(name: str):
    return {
        "name": name,
        "last_updated": datetime.now().isoformat(),
        "original_project": FEED_URL,
        "changes": "Fetched Onionoo relay feed and converted to standardized format.",
        "things": []
    }


def fetch_relays():
    response = requests.get(FEED_URL, timeout=60)
    response.raise_for_status()
    data = response.json()
    return data.get("relays", [])


def relay_to_thing(relay, addresses, type_desc="ip:port"):
    """Create a 'thing' entry for a relay with a specific list of addresses."""
    search_value = ""
    if len(addresses) >= 2:
        search_value = relay.get('nickname')
    else:
        if type_desc == "ip-only":
            search_value = addresses[0]
        else:
            ip = ":".join((addresses[0].split(":"))[:-1]).strip("[]")  # Remove port for URL
            search_value = ip
    return {
        "thing": addresses,
        "type": type_desc,
        "description": f"Tor relay node ({relay.get('nickname')}).",
        "references": [FEED_URL],
        "mitre": MITRE,
        "tags": ["tor"],
        "meta": {
            "nickname": relay.get("nickname"),
            "flags": relay.get("flags"),
            "country": relay.get("country"),
            "country_name": relay.get("country_name"),
            "running": relay.get("running"),
            "verified_host_names": relay.get("verified_host_names"),
            "external_url": f"https://metrics.torproject.org/rs.html#search/{search_value}"
        }
    }


def split_relay_addresses(relays):
    """
    Returns six lists:
    ipv4_ip_only, ipv4_ip_port,
    ipv6_ip_only, ipv6_ip_port,
    mixed_ip_only, mixed_ip_port
    """
    ipv4_ip_only, ipv4_ip_port = [], []
    ipv6_ip_only, ipv6_ip_port = [], []
    mixed_ip_only, mixed_ip_port = [], []

    for relay in relays:
        or_addrs = relay.get("or_addresses", [])

        ipv4_ip_only_list, ipv6_ip_only_list = [], []
        ipv4_ip_port_list, ipv6_ip_port_list = [], []

        for a in or_addrs:
            if IPV4_RE.match(a):  # IPv4 with port
                ipv4_ip_port_list.append(a)
                ipv4_ip_only_list.append(a.split(":")[0])
            elif IPV6_RE.match(a):  # IPv6 with port
                ipv6_ip_port_list.append(a)
                ipv6_ip_only_list.append(a.split("]")[0][1:])
            else:  # bare IP (no port)
                if ":" not in a:  # simple IPv4
                    ipv4_ip_only_list.append(a)
                else:  # simple IPv6 without port
                    ipv6_ip_only_list.append(a)

        # Combine for mixed
        mixed_ip_only_list = ipv4_ip_only_list + ipv6_ip_only_list
        mixed_ip_port_list = ipv4_ip_port_list + ipv6_ip_port_list

        # Append to lists if non-empty
        if ipv4_ip_only_list or ipv4_ip_port_list:
            if ipv4_ip_only_list:
                ipv4_ip_only.append(relay_to_thing(relay, ipv4_ip_only_list, type_desc="ip-only"))
            if ipv4_ip_port_list:
                ipv4_ip_port.append(relay_to_thing(relay, ipv4_ip_port_list, type_desc="ip:port"))

        if ipv6_ip_only_list or ipv6_ip_port_list:
            if ipv6_ip_only_list:
                ipv6_ip_only.append(relay_to_thing(relay, ipv6_ip_only_list, type_desc="ip-only"))
            if ipv6_ip_port_list:
                ipv6_ip_port.append(relay_to_thing(relay, ipv6_ip_port_list, type_desc="ip:port"))

        if mixed_ip_only_list or mixed_ip_port_list:
            if mixed_ip_only_list:
                mixed_ip_only.append(relay_to_thing(relay, mixed_ip_only_list, type_desc="ip-only"))
            if mixed_ip_port_list:
                mixed_ip_port.append(relay_to_thing(relay, mixed_ip_port_list, type_desc="ip:port"))

    return ipv4_ip_only, ipv4_ip_port, ipv6_ip_only, ipv6_ip_port, mixed_ip_only, mixed_ip_port


def filter_exit_relays(relays):
    return [r for r in relays if "Exit" in (r.get("flags") or [])]


def filter_entry_relays(relays):
    return [r for r in relays if "Guard" in (r.get("flags") or [])]


def write_output(filename: str, name: str, things: list):
    template = build_template(name)
    template["things"] = things
    with open(OUTPUT_DIR / filename, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2)


def main():
    ensure_output_dir()
    relays = fetch_relays()

    # --- All relays ---
    a_ipv4_ip_only, a_ipv4_ip_port, a_ipv6_ip_only, a_ipv6_ip_port, a_mixed_ip_only, a_mixed_ip_port = split_relay_addresses(relays)

    # --- Exit relays ---
    e_ipv4_ip_only, e_ipv4_ip_port, e_ipv6_ip_only, e_ipv6_ip_port, e_mixed_ip_only, e_mixed_ip_port = split_relay_addresses(filter_exit_relays(relays))

    # --- Entry relays ---
    g_ipv4_ip_only, g_ipv4_ip_port, g_ipv6_ip_only, g_ipv6_ip_port, g_mixed_ip_only, g_mixed_ip_port = split_relay_addresses(filter_entry_relays(relays))

    # --- Write all files ---
    # All relays
    write_output("tor_relays_ipv4_ip_only.json", "Tor Relays IPv4 IP-Only", a_ipv4_ip_only)
    write_output("tor_relays_ipv4_ip_port.json", "Tor Relays IPv4 IP:Port", a_ipv4_ip_port)
    write_output("tor_relays_ipv6_ip_only.json", "Tor Relays IPv6 IP-Only", a_ipv6_ip_only)
    write_output("tor_relays_ipv6_ip_port.json", "Tor Relays IPv6 IP:Port", a_ipv6_ip_port)
    write_output("tor_relays_mixed_ip_only.json", "Tor Relays Mixed IP-Only", a_mixed_ip_only)
    write_output("tor_relays_mixed_ip_port.json", "Tor Relays Mixed IP:Port", a_mixed_ip_port)

    # Exit relays
    write_output("tor_exit_relays_ipv4_ip_only.json", "Tor Exit Relays IPv4 IP-Only", e_ipv4_ip_only)
    write_output("tor_exit_relays_ipv4_ip_port.json", "Tor Exit Relays IPv4 IP:Port", e_ipv4_ip_port)
    write_output("tor_exit_relays_ipv6_ip_only.json", "Tor Exit Relays IPv6 IP-Only", e_ipv6_ip_only)
    write_output("tor_exit_relays_ipv6_ip_port.json", "Tor Exit Relays IPv6 IP:Port", e_ipv6_ip_port)
    write_output("tor_exit_relays_mixed_ip_only.json", "Tor Exit Relays Mixed IP-Only", e_mixed_ip_only)
    write_output("tor_exit_relays_mixed_ip_port.json", "Tor Exit Relays Mixed IP:Port", e_mixed_ip_port)

    # Entry relays
    write_output("tor_entry_relays_ipv4_ip_only.json", "Tor Entry Relays IPv4 IP-Only", g_ipv4_ip_only)
    write_output("tor_entry_relays_ipv4_ip_port.json", "Tor Entry Relays IPv4 IP:Port", g_ipv4_ip_port)
    write_output("tor_entry_relays_ipv6_ip_only.json", "Tor Entry Relays IPv6 IP-Only", g_ipv6_ip_only)
    write_output("tor_entry_relays_ipv6_ip_port.json", "Tor Entry Relays IPv6 IP:Port", g_ipv6_ip_port)
    write_output("tor_entry_relays_mixed_ip_only.json", "Tor Entry Relays Mixed IP-Only", g_mixed_ip_only)
    write_output("tor_entry_relays_mixed_ip_port.json", "Tor Entry Relays Mixed IP:Port", g_mixed_ip_port)

    print("Saved Tor relay files (IPv4, IPv6, Mixed) with IP-only and IP:Port splits for all, exit, and entry relays.")


if __name__ == "__main__":
    main()