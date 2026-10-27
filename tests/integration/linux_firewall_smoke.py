#!/usr/bin/env python3
"""Opt-in read-only/runtime checks on a disposable Linux deployment.

Requires Docker access, an active notebook, installed firewall rules, and a local
mkcert CA. Creates/removes one temporary HTTP container. Does not change firewall
rules, accounts, existing notebooks or storage. Docker access is root-equivalent.
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid


def command(*args):
    return subprocess.check_output(args, text=True, timeout=60).strip()


def execute(container, code, *args):
    return command("docker", "exec", container, "python3", "-c", code, *args)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", required=True, help="Running notebook container")
    parser.add_argument("--hub", default="jhub")
    parser.add_argument("--network", default="jupyterhub_net")
    parser.add_argument("--ca", required=True, type=Path)
    parser.add_argument("--environment", help="Optional persistent environment Python path in the client")
    args = parser.parse_args()
    target = "jhub-fw-smoke-" + uuid.uuid4().hex[:12]
    results = []

    def check(name, action):
        try:
            detail = action()
            results.append({"check": name, "passed": True, "detail": detail})
        except Exception as error:
            results.append({"check": name, "passed": False,
                            "detail": f"{type(error).__name__}: {error}"})

    http = '''import sys, urllib.request
with urllib.request.urlopen(sys.argv[1], timeout=10) as response:
    assert response.status == 200, response.status
    print(response.status)
'''
    blocked = '''import socket, sys
try:
    connection = socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=5)
except (TimeoutError, socket.timeout):
    print("timeout")
else:
    connection.close()
    raise AssertionError("Connection was allowed")
'''
    network = json.loads(command("docker", "network", "inspect", args.network))[0]
    hub_ip = json.loads(command("docker", "inspect", args.hub))[0]["NetworkSettings"]["Networks"][args.network]["IPAddress"]
    client = json.loads(command("docker", "inspect", args.client))[0]
    if args.network not in client["NetworkSettings"]["Networks"]:
        raise RuntimeError("Client must join the specified user network")

    def assert_equal(actual, expected):
        if actual != expected:
            raise AssertionError(f"{actual!r} != {expected!r}")
        return actual

    try:
        command("docker", "run", "-d", "--name", target,
                "--network", args.network, "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges:true",
                "--entrypoint", "python3", client["Config"]["Image"],
                "-m", "http.server", "9000", "--bind", "0.0.0.0",
                "--directory", "/tmp")
        target_ip = json.loads(command("docker", "inspect", target))[0]["NetworkSettings"]["Networks"][args.network]["IPAddress"]
        url = f"http://{target_ip}:9000"
        # Wait for a real positive control before asserting isolation.
        for attempt in range(10):
            try:
                positive = execute(args.hub, http, url)
                break
            except subprocess.CalledProcessError:
                if attempt == 9:
                    raise
                time.sleep(1)
        check("Hub can reach temporary HTTP target", lambda: positive)
        check("Notebook cannot reach temporary HTTP target",
              lambda: execute(args.client, blocked, target_ip, "9000"))
        check("Hub API health from notebook",
              lambda: execute(args.client, http, f"http://{hub_ip}:8081/hub/health"))
        check("Hub port 8000 positive control", lambda: execute(args.hub,
              'import socket,sys\nwith socket.create_connection((sys.argv[1],8000),timeout=5): print("listening")', hub_ip))
        check("Notebook cannot reach Hub port 8000",
              lambda: execute(args.client, blocked, hub_ip, "8000"))
        check("Notebook DNS", lambda: execute(args.client,
              'import socket; print(socket.gethostbyname("example.com"))'))
        check("Notebook Internet HTTPS", lambda: execute(args.client, http, "https://example.com"))
        check("Verified Traefik HTTPS", lambda: command(sys.executable, "-c",
              'import ssl,sys,urllib.request\nwith urllib.request.urlopen("https://localhost:8443/hub/login",context=ssl.create_default_context(cafile=sys.argv[1]),timeout=10) as r:\n assert r.status == 200; print(r.status)', str(args.ca)))
        check("Notebook PyROOT", lambda: execute(args.client,
              'import ROOT; print(ROOT.gROOT.GetVersion())'))
        if args.environment:
            check("Persistent environment", lambda: command("docker", "exec", args.client,
                  args.environment, "-c",
                  'import sys,numpy; print(sys.executable); print(numpy.__version__)'))
        check("User network IPv6 disabled", lambda: assert_equal(network["EnableIPv6"], False))
        username = next(item.split("=", 1)[1] for item in client["Config"]["Env"]
                        if item.startswith("JUPYTERHUB_USER="))
        check("Workspace UID/GID/mode", lambda: execute(args.hub,
              'import os,stat,sys\ns=os.stat("/srv/jupyterhub/users/"+sys.argv[1]); actual=(s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode)); assert actual==(1000,100,0o700),actual; print("1000:100 0700")', username))
    finally:
        subprocess.run(["docker", "rm", "-f", target], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=30, check=False)
    print(json.dumps({"client": args.client, "checks": results}, indent=2))
    return 0 if results and all(item["passed"] for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
