#!/usr/bin/env python3
"""Read-only health check for the local agent operation tools."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import socket
import stat
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path


AGENTS_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = Path("~/.config/agent-tools/config.json").expanduser()


@dataclass(frozen=True)
class Finding:
    level: str
    component: str
    message: str


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


def cdp_ready(port: int) -> bool:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json/version", timeout=0.5
        ) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def check_config(path: Path) -> list[Finding]:
    if not path.exists():
        return [Finding("WARN", "config", f"not found: {path}")]
    findings: list[Finding] = []
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
        if not isinstance(value, dict):
            raise ValueError("top-level JSON value must be an object")
        findings.append(Finding("OK", "config", f"valid JSON: {path}"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [Finding("ERROR", "config", f"invalid JSON: {exc}")]

    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        findings.append(
            Finding("WARN", "config", f"permissions are {mode:04o}; recommend chmod 600")
        )
    else:
        findings.append(Finding("OK", "config", f"permissions are {mode:04o}"))
    return findings


def check_onenote(path: Path) -> list[Finding]:
    if not path.exists():
        return []
    try:
        with path.open(encoding="utf-8") as handle:
            config = json.load(handle).get("onenote", {})
    except (OSError, json.JSONDecodeError, AttributeError):
        return []
    client_id = config.get("client_id", "")
    configured = bool(client_id and client_id != "YOUR_CLIENT_ID")
    findings = [
        Finding(
            "OK" if configured else "WARN",
            "onenote",
            "client_id configured" if configured else "client_id not configured",
        )
    ]
    token_path = Path(
        os.path.expandvars(
            os.path.expanduser(
                config.get("token_file", "~/.config/agent-tools/onenote-token.json")
            )
        )
    )
    findings.append(
        Finding(
            "OK" if token_path.is_file() else "INFO",
            "onenote",
            f"token {'present' if token_path.is_file() else 'not found'}: {token_path}",
        )
    )
    return findings


def collect_findings(config_path: Path) -> list[Finding]:
    findings: list[Finding] = []
    for command in ("python3", "git", "curl"):
        location = shutil.which(command)
        level = "OK" if location else "ERROR"
        findings.append(Finding(level, command, location or "not found"))

    for command in ("himalaya", "gcalcli", "google-chrome", "vncserver"):
        location = shutil.which(command)
        level = "OK" if location else "WARN"
        findings.append(Finding(level, command, location or "not installed"))

    websockify = shutil.which("websockify")
    fallback_websockify = Path(
        "~/.cache/agent-tools/moneyforward-mcp-venv/bin/websockify"
    ).expanduser()
    if not websockify and os.access(fallback_websockify, os.X_OK):
        websockify = str(fallback_websockify)
    findings.append(
        Finding("OK" if websockify else "WARN", "websockify", websockify or "not installed")
    )

    for module in ("websockets", "googleapiclient"):
        present = importlib.util.find_spec(module) is not None
        findings.append(
            Finding("OK" if present else "WARN", f"python:{module}", "available" if present else "not installed")
        )

    findings.extend(check_config(config_path))
    findings.extend(check_onenote(config_path))

    inventory = json.loads((AGENTS_DIR / "services.json").read_text(encoding="utf-8"))
    for service in inventory["services"]:
        name = service["name"]
        if start := service.get("start"):
            path = AGENTS_DIR / start
            findings.append(
                Finding("OK" if os.access(path, os.X_OK) else "ERROR", name, f"launcher: {path.name}")
            )
        vnc = port_open(int(service["vnc_port"]))
        cdp = cdp_ready(int(service["cdp_port"]))
        findings.append(
            Finding(
                "OK" if vnc else "INFO",
                name,
                f"VNC {service['vnc_port']}: {'listening' if vnc else 'stopped'}",
            )
        )
        findings.append(
            Finding(
                "OK" if cdp else "INFO",
                name,
                f"CDP {service['cdp_port']}: {'ready' if cdp else 'stopped'}",
            )
        )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    args = parser.parse_args()

    findings = collect_findings(args.config.expanduser())
    if args.json:
        print(json.dumps([asdict(item) for item in findings], ensure_ascii=False, indent=2))
    else:
        for item in findings:
            print(f"{item.level:5} {item.component:20} {item.message}")
        counts = {level: sum(item.level == level for item in findings) for level in ("OK", "INFO", "WARN", "ERROR")}
        print("\n" + " ".join(f"{key}={value}" for key, value in counts.items()))

    if any(item.level == "ERROR" for item in findings):
        return 1
    if args.strict and any(item.level == "WARN" for item in findings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
