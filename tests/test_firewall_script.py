"""Exercise firewall preflight using fake commands, without root or real rules."""

import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "deploy_linux/jhub-net-rules.sh"


class FirewallPreflightTests(unittest.TestCase):
    def run_script(self, *, bridge="1", chain="0", action="start", configured=True):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "rules.sh"
            text = SCRIPT.read_text()
            dns = "192.0.2.53" if configured else "CHANGE_ME"
            text = re.sub(r'^DNS_SERVERS=\([^\n]*?\)',
                          f'DNS_SERVERS=("{dns}")', text, count=1, flags=re.M)
            script.write_text(text)
            for name, body in {
                "iptables": 'echo "$*" >> "$CALL_LOG"\nif [ "$*" = "-S DOCKER-USER" ]; then exit "$CHAIN_STATUS"; fi\n',
                "sysctl": 'printf "%s\\n" "$BRIDGE_VALUE"\n',
            }.items():
                command = root / name
                command.write_text("#!/bin/sh\n" + body)
                command.chmod(0o755)
            log = root / "calls"
            environment = dict(os.environ, PATH=f"{root}:{os.environ['PATH']}",
                               CALL_LOG=str(log), CHAIN_STATUS=chain, BRIDGE_VALUE=bridge)
            result = subprocess.run(["bash", str(script), action], env=environment,
                                    text=True, capture_output=True)
            return result, log.read_text().splitlines() if log.exists() else []

    def test_missing_docker_chain_does_not_mutate_rules(self):
        result, calls = self.run_script(chain="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, ["-S DOCKER-USER"])

    def test_missing_or_disabled_bridge_filter_does_not_mutate_rules(self):
        for bridge in ("", "0"):
            with self.subTest(bridge=bridge):
                result, calls = self.run_script(bridge=bridge)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("br_netfilter", result.stderr)
                self.assertEqual(calls, ["-S DOCKER-USER"])

    def test_unconfigured_dns_does_not_mutate_rules(self):
        result, calls = self.run_script(configured=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])

    def test_valid_prerequisites_install_rules(self):
        result, calls = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("-I DOCKER-USER 1 -j JHUB-USERS", calls)
        self.assertIn("-I INPUT 1 -j JHUB-USERS-INPUT", calls)
        self.assertNotIn("-N DOCKER-USER", calls)

    def test_stop_does_not_require_dns_or_bridge_configuration(self):
        result, calls = self.run_script(action="stop", configured=False, bridge="", chain="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("-D DOCKER-USER -j JHUB-USERS", calls)
        self.assertNotIn("-S DOCKER-USER", calls)
