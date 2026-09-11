#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Exercise the packaged service with disposable configuration and scan data."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid

image, output = sys.argv[1:]
out = Path(output).resolve()
meta = json.loads(Path("meta.json").read_text())


def run(*args):
    return subprocess.check_output(["docker", *args], text=True)


version = run("run", "--rm", "--entrypoint", "/app/autoscan", image, "--version")
assert version.startswith(meta["version"] + " (") and meta["source_ref"] in version, version
(out / "version.txt").write_text(version)
info = run("run", "--rm", "--entrypoint", "cat", image, "/app/build-evidence/build-info.txt")
assert "github.com/cloudbox/autoscan/cmd/autoscan" in info and "modernc.org/sqlite" in info
(out / "build-info.txt").write_text(info)
checksum = run("run", "--rm", "--entrypoint", "sh", image, "-ec",
               "cd /app; sha256sum -c build-evidence/binary-sha256.txt")
(out / "binary-check.txt").write_text(checksum)

for authenticated in (False, True):
    name = "autoscan-check-" + uuid.uuid4().hex[:12]
    mode = "authenticated" if authenticated else "default"
    with tempfile.TemporaryDirectory() as folder:
        try:
            run("create", "--name", name, "-e", "VPN_ENABLED=false", image)
            if authenticated:
                config = Path(folder) / "config.yml"
                config.write_text("port: 3030\nauthentication:\n  username: smoke\n  password: fixture-only\n")
                run("cp", str(config), name + ":/config/config.yml")
            run("start", name)
            for attempt in range(90):
                result = subprocess.run(["docker", "exec", name, "curl", "-fsS",
                                         "http://127.0.0.1:3030/health"], capture_output=True)
                if result.returncode == 0:
                    break
                time.sleep(1)
            else:
                raise AssertionError("Autoscan health endpoint did not become ready")

            def request(method, path, auth=False):
                args = ["exec", name, "curl", "-sS", "-o", "/tmp/response", "-w", "%{http_code}", "-X", method]
                if auth:
                    args += ["-u", "smoke:fixture-only"]
                return run(*args, "http://127.0.0.1:3030" + path)

            assert request("GET", "/triggers/manual") == ("401" if authenticated else "200")
            assert request("GET", "/triggers/manual", authenticated) == "200"
            html = run("exec", name, "cat", "/tmp/response")
            assert "<html" in html.lower() and "autoscan" in html.lower()
            assert request("POST", "/triggers/manual", authenticated) == "400"
            assert request("POST", "/triggers/manual?dir=/media/smoke", authenticated) == "200"
            run("exec", name, "sh", "-ec", 'for f in config.yml autoscan.db autoscan.log; do test "$(stat -c %u /config/$f)" = 1000; done')
            run("restart", name)
            for attempt in range(60):
                result = subprocess.run(["docker", "exec", name, "curl", "-fsS",
                                         "http://127.0.0.1:3030/health"], capture_output=True)
                if result.returncode == 0:
                    break
                time.sleep(1)
            else:
                raise AssertionError("Restart failed")
            assert request("GET", "/triggers/manual") == ("401" if authenticated else "200")
            run("stop", name)
            db = Path(folder) / "autoscan.db"
            run("cp", name + ":/config/autoscan.db", str(db))
            with sqlite3.connect(db) as connection:
                assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
                rows = connection.execute("SELECT folder FROM scan").fetchall()
                assert rows == [("/media/smoke",)], rows
            (out / (mode + ".json")).write_text(json.dumps({"health": 200, "manual": 200,
                "unauthenticated": 401 if authenticated else 200, "invalid_scan": 400,
                "valid_scan": 200, "persisted_scans": rows, "restart": "passed", "ownership": 1000}))
        finally:
            logs = subprocess.run(["docker", "logs", name], capture_output=True, text=True)
            (out / (mode + ".log")).write_text(logs.stdout + logs.stderr)
            subprocess.run(["docker", "rm", "-f", name], check=False, stdout=subprocess.DEVNULL)
with (out / "result.txt").open("a") as stream:
    stream.write("Autoscan version/binary checksum, health/manual HTTP, Basic Auth401, valid/invalid scan, SQLite integrity/persistence after restart and ownership passed.\n")
