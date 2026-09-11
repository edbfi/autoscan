#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Publish only the two tested archives for the unchanged protected branch."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess


def validate(evidence, repository, branch):
    if not re.fullmatch(r"edbfi/[a-z0-9][a-z0-9._-]*", repository):
        raise ValueError("Unexpected repository")
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,79}", branch):
        raise ValueError("Invalid image branch")
    records = []
    for arch in ("amd64", "arm64"):
        folder = evidence / (branch + "-" + arch)
        data = json.loads((folder / "metadata.json").read_text())
        if (data["repository"], data["branch"], data["arch"]) != (repository, branch, arch):
            raise ValueError("Artifact identity mismatch")
        if not re.fullmatch(r"[0-9a-f]{40}", data["revision"]):
            raise ValueError("Invalid revision")
        if not data["tags"] or any(not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", t) for t in data["tags"]):
            raise ValueError("Invalid image tags")
        for name in ("image.tar", "result.txt", "packages.txt"):
            if not (folder / name).is_file() or (folder / name).stat().st_size == 0:
                raise ValueError("Missing tested artifact: " + name)
        records.append(data)
    if any(records[0][k] != records[1][k] for k in ("revision", "tags")):
        raise ValueError("Architecture revisions or tags differ")
    return records[0]


def run(args):
    subprocess.run(args, check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("evidence", "repository", "branch"):
        parser.add_argument("--" + name, required=True)
    opts = parser.parse_args()
    evidence = Path(opts.evidence)
    data = validate(evidence, opts.repository, opts.branch)
    live = json.loads(subprocess.check_output(["gh", "api", f"repos/{opts.repository}/branches/{opts.branch}"], text=True))
    if live["commit"]["sha"] != data["revision"] or not live["protected"]:
        raise SystemExit("Source branch changed or is not protected; rebuild before publishing")
    registry = "ghcr.io/" + opts.repository
    temporary = []
    for arch in ("amd64", "arm64"):
        run(["docker", "load", "-i", str(evidence / (opts.branch + "-" + arch) / "image.tar")])
        tag = registry + ":" + opts.branch + "-" + data["revision"][:7] + "-" + os.environ["GITHUB_RUN_ID"] + "-" + arch
        run(["docker", "tag", "local-validation:" + opts.branch + "-" + arch, tag])
        run(["docker", "push", tag])
        temporary.append(tag)
    command = ["docker", "buildx", "imagetools", "create"]
    for tag in data["tags"]:
        command.extend(["--tag", registry + ":" + tag])
    run(command + temporary)
    run(["docker", "buildx", "imagetools", "inspect", registry + ":" + opts.branch])
