# -*- coding: utf-8 -*-
"""在 git 通道不通时，用 GitHub Git Data API 推送本地提交。

用法（在仓库目录下）：
    GH_TOKEN=xxx python _push_via_api.py
以本地 HEAD 与远端 main 的 diff 为准，构造一个新提交并快进 refs/heads/main。
"""
from __future__ import annotations

import base64
import json
import os
import ssl
import subprocess
import sys
import urllib.request

OWNER = "Maybe-in"
REPO = "xiangcong-monitor"
API = "https://api.github.com"
TOKEN = os.environ.get("GH_TOKEN", "").strip()

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def git(*args: str) -> str:
    """取 git 输出（文本）；强制关闭路径转义，避免中文文件名被转成八进制。"""
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        check=True, capture_output=True).stdout.decode().strip()


def git_bytes(*args: str) -> bytes:
    """取 git 原始字节（不做 strip，保留文件末尾换行）。"""
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        check=True, capture_output=True).stdout


def call(method: str, path: str, payload: dict | None = None) -> dict:
    url = API + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + TOKEN)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
        body = r.read().decode()
        return json.loads(body) if body else {}


def main() -> int:
    if not TOKEN:
        print("缺少 GH_TOKEN")
        return 1

    head = git("rev-parse", "HEAD")
    message = git("log", "-1", "--pretty=%B", head)

    remote = call("GET", f"/repos/{OWNER}/{REPO}/git/ref/heads/main")["object"]["sha"]
    if remote == head:
        print("远端已是最新，无需推送")
        return 0

    print(f"本地 HEAD  {head[:7]}")
    print(f"远端 main  {remote[:7]}")

    changed = git("diff", "--name-only", remote, head).splitlines()
    changed = [p for p in changed if p]
    print(f"待推送文件 {len(changed)} 个:")
    for p in changed:
        print("   ", p)

    base_tree = call("GET", f"/repos/{OWNER}/{REPO}/git/commits/{remote}")["tree"]["sha"]

    entries = []
    for path in changed:
        raw = git_bytes("show", f"{head}:{path}")
        sha = call("POST", f"/repos/{OWNER}/{REPO}/git/blobs",
                   {"content": base64.b64encode(raw).decode(), "encoding": "base64"})["sha"]
        entries.append({"path": path, "mode": "100644", "type": "blob", "sha": sha})
        print(f"    blob {sha[:10]}  {path}  {len(raw):,} B")

    tree = call("POST", f"/repos/{OWNER}/{REPO}/git/trees",
                {"base_tree": base_tree, "tree": entries})["sha"]
    commit = call("POST", f"/repos/{OWNER}/{REPO}/git/commits",
                  {"message": message, "tree": tree, "parents": [remote]})["sha"]
    print(f"新提交 {commit[:7]}")

    call("PATCH", f"/repos/{OWNER}/{REPO}/git/refs/heads/main", {"sha": commit, "force": False})
    print("refs/heads/main 已快进 ✓")
    print("本地需执行： git fetch origin && git reset --hard origin/main")
    return 0


if __name__ == "__main__":
    sys.exit(main())
