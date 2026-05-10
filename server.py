"""
MCP server exposing security-relevant tools to an AI agent.

Tools:
- parse_auth_log: extract failed SSH login attempts from a log file,
  grouped by source IP with attempt counts and target usernames.
- check_ip_reputation: query AbuseIPDB to check if an IP has been
  reported as malicious, returning the abuse confidence score and metadata.
"""

import os
import re
from collections import defaultdict
from pathlib import Path

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Load secrets from .env into the process environment at server startup.
# After this call, os.getenv("ABUSEIPDB_API_KEY") returns the key.
load_dotenv()

mcp = FastMCP("security-tools")


# --- Tool 1: auth log parser ---

FAILED_LOGIN_PATTERN = re.compile(
    r"Failed password for (?:invalid user )?(?P<user>\S+) from (?P<ip>\d+\.\d+\.\d+\.\d+)"
)


@mcp.tool()
def parse_auth_log(filepath: str) -> dict:
    """
    Parse an SSH auth log file and return failed login attempts grouped by source IP.

    Args:
        filepath: Absolute or relative path to the auth log file (e.g., /var/log/auth.log
                  or sample_data/auth.log).

    Returns:
        A dict with:
        - total_failed_attempts: total count of failed login lines found
        - unique_source_ips: count of distinct IPs that failed
        - sources: list of dicts, one per unique source IP, each containing:
            - ip: the source IP address
            - attempt_count: how many times this IP failed
            - targeted_users: sorted list of unique usernames this IP tried
            - first_seen: timestamp of first attempt (raw log format)
            - last_seen: timestamp of last attempt
        Sorted by attempt_count descending so the noisiest sources surface first.
    """
    path = Path(filepath)
    if not path.exists():
        return {"error": f"File not found: {filepath}"}

    by_ip = defaultdict(lambda: {"attempts": 0, "users": set(), "first": None, "last": None})

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            match = FAILED_LOGIN_PATTERN.search(line)
            if not match:
                continue

            ip = match.group("ip")
            user = match.group("user")
            timestamp = line[:15]

            entry = by_ip[ip]
            entry["attempts"] += 1
            entry["users"].add(user)
            if entry["first"] is None:
                entry["first"] = timestamp
            entry["last"] = timestamp

    sources = [
        {
            "ip": ip,
            "attempt_count": data["attempts"],
            "targeted_users": sorted(data["users"]),
            "first_seen": data["first"],
            "last_seen": data["last"],
        }
        for ip, data in by_ip.items()
    ]
    sources.sort(key=lambda s: s["attempt_count"], reverse=True)

    return {
        "total_failed_attempts": sum(s["attempt_count"] for s in sources),
        "unique_source_ips": len(sources),
        "sources": sources,
    }


# --- Tool 2: AbuseIPDB reputation lookup ---

ABUSEIPDB_URL = "https://api.abuseipdb.com/api/v2/check"


@mcp.tool()
def check_ip_reputation(ip: str) -> dict:
    """
    Query AbuseIPDB to check if an IP address has been reported as malicious.

    Use this to enrich findings from parse_auth_log: pass each suspicious source IP
    through this tool to see if other operators have flagged it for abuse.

    Args:
        ip: The IPv4 address to check (e.g., "185.220.101.42").

    Returns:
        A dict with:
        - ip: the IP that was checked
        - abuse_confidence_score: 0-100, where 100 means definitely malicious
        - total_reports: how many distinct reports AbuseIPDB has seen for this IP
        - country_code: the country the IP is registered in (e.g., "DE")
        - isp: the internet service provider
        - usage_type: e.g., "Data Center", "Fixed Line ISP", "University"
        - is_tor: whether AbuseIPDB has identified this as a Tor exit node
        - last_reported_at: ISO timestamp of the most recent abuse report (or None)
        On error, returns a dict with an "error" key explaining what went wrong.
    """
    api_key = os.getenv("ABUSEIPDB_API_KEY")
    if not api_key:
        return {"error": "ABUSEIPDB_API_KEY not set. Check the .env file in the project root."}

    headers = {
        "Key": api_key,
        "Accept": "application/json",
    }
    params = {
        "ipAddress": ip,
        "maxAgeInDays": 90,
    }

    try:
        response = requests.get(ABUSEIPDB_URL, headers=headers, params=params, timeout=10)
    except requests.exceptions.RequestException as e:
        return {"error": f"Network error contacting AbuseIPDB: {e}"}

    if response.status_code == 401:
        return {"error": "AbuseIPDB authentication failed (401). Check the API key."}
    if response.status_code == 429:
        return {"error": "AbuseIPDB rate limit exceeded (429). Free tier allows 1000 checks/day."}
    if response.status_code != 200:
        return {"error": f"AbuseIPDB returned HTTP {response.status_code}: {response.text[:200]}"}

    data = response.json().get("data", {})
    return {
        "ip": data.get("ipAddress"),
        "abuse_confidence_score": data.get("abuseConfidenceScore"),
        "total_reports": data.get("totalReports"),
        "country_code": data.get("countryCode"),
        "isp": data.get("isp"),
        "usage_type": data.get("usageType"),
        "is_tor": data.get("isTor"),
        "last_reported_at": data.get("lastReportedAt"),
    }


if __name__ == "__main__":
    mcp.run()