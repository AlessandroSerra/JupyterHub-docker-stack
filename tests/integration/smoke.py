#!/usr/bin/env python3
"""Opt-in Docker Desktop smoke/migration rehearsal using disposable storage.

Run with the dependencies in requirements.txt. Never loads the repository .env.
Existing image contents are reused, not rebuilt. No native Linux firewall changes.
"""

import argparse
from datetime import datetime, timezone
import io
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import tarfile
import tempfile
import time
import uuid

import requests
import websocket
import yaml


ROOT = Path(__file__).resolve().parents[2]
LABEL = "org.jupyterhub-deploy.validation"


def run(*args, input=None, timeout=180):
    result = subprocess.run(args, input=input, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        # Avoid exposing tokens, passwords, or cookie headers in subprocess output.
        raise RuntimeError(f"Command failed ({result.returncode}): {args[0]} {args[1] if len(args) > 1 else ''}")
    return result.stdout.strip()


def inspect(kind, name):
    return json.loads(run("docker", kind, "inspect", name))[0]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Rehearsal:
    def __init__(self, report, hub_image, notebook_image):
        self.report_path = report
        self.project = "jhub-check-" + secrets.token_hex(4)
        # macOS /var temporary-directory aliases are unsuitable for daemon bind mounts.
        self.work = Path(tempfile.mkdtemp(prefix=self.project + "-", dir=Path.home())).resolve()
        os.chmod(self.work, 0o700)
        print("Private fixture storage:", self.work, flush=True)
        self.http_port, self.https_port = free_port(), free_port()
        while self.https_port == self.http_port:
            self.https_port = free_port()
        self.url = f"https://localhost:{self.https_port}"
        self.hub = self.project + "-hub"
        self.user_net = self.project + "-users"
        self.proxy_net = self.project + "-proxy"
        self.password = secrets.token_urlsafe(24)
        self.token = None
        self.compose_file = None
        self.session = None
        self.report = {"started_at": datetime.now(timezone.utc).isoformat(), "baseline_commit": run("git", "rev-parse", "v0.1.0^{commit}"), "project": self.project, "source_commit": run("git", "rev-parse", "HEAD"), "checks": [], "limitations": ["Build provenance is separate; the harness does not build images", "No native Linux firewall or permissions validation", "No visual browser inspection, load testing, or resource-exhaustion testing", "Fixture changes names, subnet, ports, TLS paths, and spawner prefix for isolation"]}
        self.report["harness_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        self.report["source_worktree_dirty"] = bool(run("git", "status", "--porcelain"))
        self.original = self.snapshot()
        self.report["images"] = {name: inspect("image", name)["Id"] for name in ("jupyterhub-scientific-hub:0.1.0", "jupyterhub-scientific-notebook:0.1.0", "traefik:v3.7")}
        self.report["candidate_images"] = {"hub": inspect("image", hub_image)["Id"], "notebook": inspect("image", notebook_image)["Id"]}
        self.report["platform"] = {"docker_engine": run("docker", "version", "--format", "{{.Server.Version}}"), "compose": run("docker", "compose", "version", "--short"), "architecture": inspect("image", notebook_image)["Architecture"]}
        self.ca = Path(run("mkcert", "-CAROOT")) / "rootCA.pem"
        self.cert_dir = self.work / "certs"
        self.cert_dir.mkdir()
        run("mkcert", "-cert-file", str(self.cert_dir / "local.pem"), "-key-file", str(self.cert_dir / "local-key.pem"), "localhost", "127.0.0.1", "::1")
        self.subnet = self.choose_subnet()
        self.hub_ip = str(self.subnet.network_address + 10)
        for name in ("hub", "users"):
            (self.work / name).mkdir(mode=0o700)
        archive = subprocess.check_output(["git", "archive", "v0.1.0"])
        self.baseline = self.work / "release-source"
        self.baseline.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(self.baseline, filter="data")

    @staticmethod
    def snapshot():
        ids = run("docker", "ps", "-q").split()
        return {cid: (inspect("container", cid)["State"]["StartedAt"], inspect("container", cid)["NetworkSettings"]["Networks"]) for cid in ids}

    def choose_subnet(self):
        import ipaddress
        networks = json.loads(run("docker", "network", "inspect", *run("docker", "network", "ls", "-q").split()))
        used = [ipaddress.ip_network(c["Subnet"]) for n in networks for c in (n.get("IPAM", {}).get("Config") or []) if c.get("Subnet")]
        for third in range(240, 255):
            candidate = ipaddress.ip_network(f"172.29.{third}.0/24")
            if not any(candidate.overlaps(other) for other in used):
                return candidate
        raise RuntimeError("No unused test subnet found")

    def check(self, label, condition=True):
        if not condition:
            raise AssertionError(label)
        self.report["checks"].append(label)
        print("PASS:", label, flush=True)

    def compose(self, *args):
        return run("docker", "compose", "-p", self.project, "-f", str(self.compose_file), *args)

    def configure(self, source, stage, modern):
        directory = self.work / stage
        directory.mkdir()
        cfg = (source / "jupyterhub/jupyterhub_config.py").read_text()
        if modern:
            cfg = cfg.replace('HUB_IP = "172.30.250.10"', f'HUB_IP = "{self.hub_ip}"')
        else:
            cfg = cfg.replace('= "jhub"', '= "jupyterhub"')
        cfg += "\n# Disposable integration-fixture overrides; never used by the live deployment.\n"
        notebook_image = self.report['candidate_images']['notebook'] if modern else self.report['images']['jupyterhub-scientific-notebook:0.1.0']
        cfg += f"c.DockerSpawner.network_name = {self.user_net!r}\nc.DockerSpawner.image = {notebook_image!r}\nc.DockerSpawner.prefix = {self.project + '-notebook'!r}\nc.DockerSpawner.extra_create_kwargs = {{'labels': {{{LABEL!r}: {self.project!r}, {LABEL + '.role'!r}: 'notebook'}}}}\n"
        config_path = directory / "jupyterhub_config.py"
        config_path.write_text(cfg)
        dynamic = directory / "dynamic"
        shutil.copytree(source / "traefik/dynamic", dynamic)
        if modern:
            route = dynamic / "jupyterhub.yml"
            route.write_text(route.read_text().replace("http://jhub:8000", "http://jupyterhub:8000"))
        spec = yaml.safe_load((source / "compose.yml").read_text())
        hub, traefik = spec["services"]["jupyterhub"], spec["services"]["traefik"]
        hub["image"] = self.report["candidate_images"]["hub"] if modern else self.report["images"]["jupyterhub-scientific-hub:0.1.0"]
        traefik["image"] = self.report["images"]["traefik:v3.7"]
        hub["container_name"], traefik["container_name"] = self.hub, self.project + "-traefik"
        for service in (hub, traefik):
            service.setdefault("labels", {})[LABEL] = self.project
        if not modern:
            traefik["command"].append(f"--providers.docker.constraints=Label(`{LABEL}`,`{self.project}`)")
        hub["environment"] = {"JUPYTERHUB_USERS_DIR": str(self.work / "users")}
        hub["volumes"] = ["/var/run/docker.sock:/var/run/docker.sock", f"{self.work / 'hub'}:/srv/jupyterhub/hub", f"{self.work / 'users'}:/srv/jupyterhub/users", f"{config_path}:/etc/jupyterhub/jupyterhub_config.py:ro"]
        traefik["volumes"] = [f"{dynamic}:/etc/traefik/dynamic:ro", f"{self.cert_dir}:/etc/traefik/certs:ro"]
        if not modern:
            traefik["volumes"].append("/var/run/docker.sock:/var/run/docker.sock:ro")
        traefik["ports"] = [f"127.0.0.1:{self.http_port}:80", f"127.0.0.1:{self.https_port}:443"]
        traefik["command"] = [re.sub(r"entrypoint.to=:\d+", f"entrypoint.to=:{self.https_port}", arg) for arg in traefik["command"]]
        spec["networks"]["jupyterhub_net"]["name"] = self.user_net
        if modern:
            spec["networks"]["proxy_net"]["name"] = self.proxy_net
            spec["networks"]["jupyterhub_net"]["ipam"]["config"] = [{"subnet": str(self.subnet)}]
            spec["networks"]["jupyterhub_net"]["driver_opts"]["com.docker.network.bridge.name"] = "br-" + self.project[-8:]
            hub["networks"]["jupyterhub_net"]["ipv4_address"] = self.hub_ip
        self.compose_file = directory / "compose.yml"
        self.compose_file.write_text(yaml.safe_dump(spec, sort_keys=False))
        self.compose("config", "--quiet")
        self.compose("up", "-d", "--pull", "never")
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.verify = str(self.ca)
        for _ in range(90):
            try:
                if self.session.get(self.url + "/hub/login", timeout=3).status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(1)
        else:
            raise AssertionError("Hub readiness timed out")
        response = self.session.get(f"http://localhost:{self.http_port}/hub/login", allow_redirects=False, timeout=10)
        self.check(stage + ": HTTP redirect and trusted HTTPS", response.status_code == 301 and response.headers["Location"] == self.url + "/hub/login")
        if modern:
            proxy = inspect("container", self.project + "-traefik")
            hub_state = inspect("container", self.hub)
            self.check(stage + ": proxy network separated", set(proxy["NetworkSettings"]["Networks"]) == {self.proxy_net} and set(hub_state["NetworkSettings"]["Networks"]) == {self.proxy_net, self.user_net})
            self.check(stage + ": Traefik socket absent and root filesystem read-only", not any(m["Destination"] == "/var/run/docker.sock" for m in proxy["Mounts"]) and proxy["HostConfig"]["ReadonlyRootfs"])
            self.report["hub_packages"] = json.loads(run("docker", "exec", self.hub, "python", "-c", "import importlib.metadata as m, json; print(json.dumps({n:m.version(n) for n in ['jupyterhub','dockerspawner','jupyterhub-nativeauthenticator']}))"))

    def form(self, path, data):
        response = self.session.get(self.url + path, timeout=20)
        response.raise_for_status()
        match = re.search(r'name="_xsrf" value="([^"]+)"', response.text)
        assert match, "Expected a fresh authentication form with an XSRF token"
        xsrf = match.group(1)
        response = self.session.post(self.url + path, data={**data, "_xsrf": xsrf}, timeout=30)
        response.raise_for_status()
        return response

    def signup(self, username, password):
        return self.form("/hub/signup", {"username": username, "signup_password": password, "signup_password_confirmation": password})

    def login(self, stage):
        # Require credential authentication again, not an existing session redirect.
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.verify = str(self.ca)
        for _ in range(60):
            try:
                if self.session.get(self.url + "/hub/login", timeout=3).status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(1)
        else:
            raise AssertionError("Login readiness timed out")
        self.form("/hub/login", {"username": "jhubadmin", "password": self.password})
        response = self.session.get(self.url + "/hub/admin", timeout=20)
        self.check(stage + ": session login and administrator access", response.status_code == 200 and "/hub/admin" in response.url)
        if not self.token:
            output = run("docker", "exec", self.hub, "jupyterhub", "token", "jhubadmin", "-f", "/etc/jupyterhub/jupyterhub_config.py")
            self.token = output.splitlines()[-1]
        self.check(stage + ": persisted Hub API token", self.api("GET", "/hub/api/user").json()["name"] == "jhubadmin")

    def api(self, method, path, **kwargs):
        response = self.session.request(method, self.url + path, headers={"Authorization": "token " + self.token}, timeout=180, **kwargs)
        response.raise_for_status()
        return response

    def notebook_ids(self):
        return run("docker", "ps", "-aq", "--filter", f"label={LABEL}={self.project}", "--filter", f"label={LABEL}.role=notebook").split()

    def notebook(self):
        ids = self.notebook_ids()
        assert len(ids) == 1, "Expected one isolated notebook container"
        return ids[0]

    def spawn(self, stage):
        self.api("POST", "/hub/api/users/jhubadmin/server")
        for _ in range(90):
            user = self.api("GET", "/hub/api/users/jhubadmin").json()
            if user.get("servers", {}).get("", {}).get("ready"):
                break
            time.sleep(1)
        else:
            raise AssertionError("Notebook spawning timed out")
        response = self.session.get(self.url + "/user/jhubadmin/lab", timeout=60)
        self.check(stage + ": notebook access and OAuth redirects", response.status_code == 200 and "/user/jhubadmin/lab" in response.url)
        state = inspect("container", self.notebook())
        host = state["HostConfig"]
        self.check(stage + ": notebook security/resource settings", host["Memory"] == 2 * 1024**3 and host["CpuQuota"] / host["CpuPeriod"] == 1 and host["PidsLimit"] == 1024 and "ALL" in host["CapDrop"] and any("no-new-privileges" in opt for opt in host["SecurityOpt"]))
        self.check(stage + ": notebook only on isolated user network", set(state["NetworkSettings"]["Networks"]) == {self.user_net})
        if stage == "current":
            self.report["notebook_packages"] = json.loads(self.exec_notebook("import importlib.metadata as m, json, ROOT\nversions = {n:m.version(n) for n in ['jupyterhub','jupyterlab','jupyter-server','numpy','scipy','matplotlib','pandas','sympy','ipykernel']}\nversions['ROOT'] = ROOT.gROOT.GetVersion()\nprint(json.dumps(versions))\n"))

    def exec_notebook(self, code, timeout=300):
        return run("docker", "exec", "-i", self.notebook(), "python", "-", input=code, timeout=timeout)

    def kernel(self, stage, name="python3", code="print('websocket-smoke-ok')"):
        # Exercise the public HTTPS/WebSocket route with real OAuth session cookies.
        response = self.session.get(self.url + "/user/jhubadmin/api/kernelspecs", timeout=30)
        response.raise_for_status()
        self.check(stage + ": kernel discovered: " + name, name in response.json()["kernelspecs"])
        xsrf = next(cookie.value for cookie in self.session.cookies if cookie.name == "_xsrf" and cookie.path.startswith("/user/"))
        response = self.session.post(self.url + "/user/jhubadmin/api/kernels", json={"name": name}, headers={"X-XSRFToken": xsrf}, timeout=60)
        response.raise_for_status()
        kid = response.json()["id"]
        cookie = self.session.prepare_request(requests.Request("GET", self.url + "/user/jhubadmin/api/kernels")).headers["Cookie"]
        ws = websocket.create_connection(self.url.replace("https:", "wss:") + f"/user/jhubadmin/api/kernels/{kid}/channels?session_id={uuid.uuid4().hex}", cookie=cookie, origin=self.url, sslopt={"ca_certs": str(self.ca)}, http_no_proxy=["localhost", "127.0.0.1"], timeout=90)
        try:
            mid = uuid.uuid4().hex
            ws.send(json.dumps({"header": {"msg_id": mid, "username": "jhubadmin", "session": uuid.uuid4().hex, "msg_type": "execute_request", "version": "5.3"}, "parent_header": {}, "metadata": {}, "channel": "shell", "content": {"code": code, "silent": False, "store_history": False, "user_expressions": {}, "allow_stdin": False, "stop_on_error": True}}))
            output, success = "", False
            for _ in range(150):
                message = json.loads(ws.recv())
                if message.get("parent_header", {}).get("msg_id") != mid:
                    continue
                if message["msg_type"] == "stream":
                    output += message["content"]["text"]
                if message["msg_type"] == "execute_reply":
                    success = message["content"]["status"] == "ok"
                    break
            self.check(stage + ": WebSocket execution: " + name, success and "websocket-smoke-ok" in output)
        finally:
            ws.close()
            self.session.delete(self.url + f"/user/jhubadmin/api/kernels/{kid}", headers={"X-XSRFToken": xsrf}, timeout=30).raise_for_status()

    def scientific_demos(self):
        self.exec_notebook("import numpy, scipy, matplotlib, pandas, sympy, ROOT; print(ROOT.gROOT.GetVersion())")
        for path, kernel in (("pyroot.ipynb", "python3"), ("croot.ipynb", "root")):
            # Execute repository examples with the actual installed kernels, without changing saved files.
            content = json.loads((ROOT / "notebooks" / path).read_text())
            code = "import nbformat\nfrom nbclient import NotebookClient\n"
            code += f"notebook = nbformat.reads({json.dumps(content)!r}, as_version=4)\n"
            code += f"NotebookClient(notebook, timeout=180, kernel_name={kernel!r}).execute()\n"
            code += "assert any(cell.get('outputs') for cell in notebook.cells if cell.cell_type == 'code')\n"
            self.exec_notebook(code)
            self.check("current: demo executed with output: " + path)

    def create_environment(self):
        run("docker", "exec", self.notebook(), "mamba", "create", "-y", "-n", "smoke", "python=3.12", "ipykernel", timeout=900)
        run("docker", "exec", self.notebook(), "register-conda-kernel", "smoke", "--display-name", "Python (smoke)")
        self.exec_notebook("from pathlib import Path\nPath('/home/jovyan/work/persistence.txt').write_text('baseline-preserved')\n")
        self.check("baseline: persistent Conda environment and custom kernel registered")

    def persistence(self, stage):
        self.exec_notebook("from pathlib import Path\nassert Path('/home/jovyan/work/persistence.txt').read_text() == 'baseline-preserved'\nassert Path('/home/jovyan/work/.conda/envs/smoke/bin/python').is_file()\n")
        self.kernel(stage, "smoke", "import sys; assert '/work/.conda/envs/smoke/' in sys.executable; print('websocket-smoke-ok')")
        self.check(stage + ": workspace and custom environment persisted")

    def stop_notebook(self, stage):
        self.api("DELETE", "/hub/api/users/jhubadmin/server")
        for _ in range(60):
            if not self.notebook_ids():
                self.check(stage + ": stopped notebook container removed")
                return
            time.sleep(1)
        raise AssertionError("Notebook container was not removed")

    def policies(self):
        # New unauthenticated sessions keep browser cookies separate from the admin.
        admin = self.session
        for username, password, expected in (("shortpass", "X9!abc123", False), ("invalid.name", self.password, False), ("unapproved", self.password, True)):
            self.session = requests.Session()
            self.session.trust_env = False
            self.session.verify = str(self.ca)
            result = self.signup(username, password)
            self.check("current: signup policy: " + username, ('class="alert alert-info"' in result.text) if expected else ('class="alert alert-danger"' in result.text))
            if expected:
                self.form("/hub/login", {"username": username, "password": password})
                response = self.session.get(self.url + "/hub/home", timeout=20)
                self.check("current: unapproved account cannot log in", "/hub/login" in response.url)
        self.session = admin
        response = self.session.get(self.url + "/hub/home", timeout=20)
        self.check("current: administrator has authorization navigation",
                   response.status_code == 200 and 'href="/hub/authorize"' in response.text)
        response = self.session.get(self.url + "/hub/authorize/unapproved", timeout=20)
        self.check("current: administrator can approve registered account",
                   response.status_code == 200 and "/hub/authorize" in response.url)
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.verify = str(self.ca)
        self.form("/hub/login", {"username": "unapproved", "password": self.password})
        response = self.session.get(self.url + "/hub/home", timeout=20)
        self.check("current: approved account can log in without Hub allowlist",
                   response.status_code == 200 and "/hub/home" in response.url)
        self.session = admin
        response = self.session.get(self.url + "/hub/login", timeout=20)
        self.check("current: security headers", response.headers.get("X-Content-Type-Options") == "nosniff" and response.headers.get("Referrer-Policy") == "same-origin")
        statuses = [self.session.get(self.url + "/hub/login", timeout=10).status_code for _ in range(30)]
        self.check("current: login rate limit returns 429", 429 in statuses)

    def lockout(self):
        # Run last on the candidate: this deliberately locks the disposable admin.
        for _ in range(5):
            self.session = requests.Session()
            self.session.trust_env = False
            self.session.verify = str(self.ca)
            response = self.form("/hub/login", {"username": "jhubadmin", "password": "incorrect-" + secrets.token_urlsafe(16)})
            assert "/hub/login" in response.url, "Invalid password unexpectedly authenticated"
        self.check("current: five invalid administrator logins denied")
        response = self.form("/hub/login", {"username": "jhubadmin", "password": self.password})
        self.check("current: correct password denied during login lockout", "/hub/login" in response.url)

    def teardown(self):
        # Remove only resources with this randomly generated run's ownership label.
        ids = self.notebook_ids()
        if ids:
            run("docker", "rm", "-f", *ids)
        if self.compose_file:
            self.compose("down")
        assert not run("docker", "ps", "-aq", "--filter", f"label={LABEL}={self.project}"), "Fixture containers remain"
        networks = run("docker", "network", "ls", "--format", "{{.Name}}").splitlines()
        assert self.user_net not in networks and self.proxy_net not in networks, "Fixture networks remain"

    def execute(self):
        try:
            self.configure(self.baseline, "baseline", False)
            self.signup("jhubadmin", self.password)
            self.login("baseline")
            self.spawn("baseline")
            self.kernel("baseline")
            self.create_environment()
            self.persistence("baseline")
            self.stop_notebook("baseline")
            old_network = inspect("network", self.user_net)["Id"]
            self.compose("stop")
            for name in ("hub", "users"):
                shutil.copytree(self.work / name, self.work / ("backup-" + name), symlinks=True)
            self.compose("down")
            self.configure(ROOT, "current", True)
            self.check("migration: user network recreated", inspect("network", self.user_net)["Id"] != old_network)
            self.login("current")
            self.spawn("current")
            self.kernel("current")
            self.kernel("current", "root", 'std::cout << "websocket-smoke-ok" << std::endl;')
            self.scientific_demos()
            self.persistence("current")
            self.exec_notebook("from pathlib import Path\nPath('/home/jovyan/work/current-only.txt').write_text('not-in-baseline-snapshot')\n")
            self.api("POST", "/hub/api/users/rollbackprobe", json={})
            self.check("current: post-snapshot workspace and Hub state created")
            self.policies()
            # Let the configured login limiter refill before testing a new login.
            time.sleep(65)
            self.stop_notebook("current")
            self.compose("restart", "jupyterhub")
            time.sleep(5)
            self.login("restart")
            self.spawn("restart")
            self.persistence("restart")
            self.stop_notebook("restart")
            self.lockout()
            self.compose("down")
            for name in ("hub", "users"):
                shutil.rmtree(self.work / name)
                shutil.copytree(self.work / ("backup-" + name), self.work / name, symlinks=True)
            self.configure(self.baseline, "rollback", False)
            self.login("rollback")
            self.spawn("rollback")
            self.persistence("rollback")
            self.exec_notebook("from pathlib import Path\nassert not Path('/home/jovyan/work/current-only.txt').exists()\n")
            probe = self.session.get(self.url + "/hub/api/users/rollbackprobe", headers={"Authorization": "token " + self.token}, timeout=20)
            self.check("rollback: post-snapshot workspace and Hub state absent", probe.status_code == 404)
            self.stop_notebook("rollback")
            self.report["result"] = "passed"
        except Exception as error:
            self.report["result"] = "failed"
            self.report["error"] = type(error).__name__ + ": " + str(error)
            raise
        finally:
            cleanup_error = None
            try:
                self.teardown()
                self.report["fixture_resources_removed"] = True
            except Exception as error:
                cleanup_error = error
                self.report["fixture_resources_removed"] = False
                self.report["result"] = "failed"
            now = self.snapshot()
            unchanged = all(now.get(cid) == state for cid, state in self.original.items())
            self.report["preexisting_containers_unchanged"] = unchanged
            if not unchanged:
                self.report["result"] = "failed"
            self.report.setdefault("result", "interrupted")
            self.report["finished_at"] = datetime.now(timezone.utc).isoformat()
            self.report_path.write_text(json.dumps(self.report, indent=2) + "\n")
            print("Report:", self.report_path, flush=True)
            if unchanged and self.report["result"] == "passed":
                shutil.rmtree(self.work)
            else:
                print("Private diagnostic storage retained:", self.work, flush=True)
            if cleanup_error:
                raise RuntimeError("Fixture cleanup failed; inspect the private fixture directory") from cleanup_error
            if not unchanged:
                raise AssertionError("Pre-existing container state changed; investigate immediately")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True, help="Sanitized JSON report outside temporary storage")
    parser.add_argument("--hub-image", default="jupyterhub-scientific-hub:0.2.0", help="Candidate Hub image (baseline/rollback always retain original 0.1.0 contents)")
    parser.add_argument("--notebook-image", default="jupyterhub-scientific-notebook:0.2.0", help="Candidate notebook image")
    args = parser.parse_args()
    Rehearsal(args.report.resolve(), args.hub_image, args.notebook_image).execute()
