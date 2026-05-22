#!/usr/bin/env python3
"""
通过 GitHub REST API（Git Data API）推送本地未推送的 commits 到远程。
适用于阿里内网无法直接 git push 的场景。
"""
import base64
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error

OWNER = "hellogxp"
REPO = "skill-research"
BRANCH = "main"
API = f"https://api.github.com/repos/{OWNER}/{REPO}"

# 从 git remote 提取 token
remote_url = subprocess.check_output(["git", "remote", "get-url", "origin"], text=True).strip()
TOKEN = remote_url.split("xueping.gxp:")[1].split("@github.com")[0]

HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "skill-research-pusher",
}


def api_request(method, path, data=None):
    url = API + path
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(
        url, data=body, method=method,
        headers={**HEADERS, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} on {method} {path}: {e.read().decode('utf-8', errors='ignore')[:500]}", file=sys.stderr)
        raise


def get_remote_head():
    r = api_request("GET", f"/branches/{BRANCH}")
    return r["commit"]["sha"]


def get_local_commits_to_push(remote_sha):
    out = subprocess.check_output(
        ["git", "rev-list", f"{remote_sha}..HEAD", "--reverse"], text=True
    ).strip()
    return out.splitlines() if out else []


def get_changed_files(commit_sha):
    out = subprocess.check_output(
        ["git", "diff-tree", "--no-commit-id", "--name-status", "-r", commit_sha], text=True
    ).strip()
    files = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            files.append((parts[0], parts[1]))
    return files


def get_commit_meta(commit_sha):
    msg = subprocess.check_output(["git", "log", "-1", "--format=%B", commit_sha], text=True).rstrip("\n")
    author_name = subprocess.check_output(["git", "log", "-1", "--format=%an", commit_sha], text=True).strip()
    author_email = subprocess.check_output(["git", "log", "-1", "--format=%ae", commit_sha], text=True).strip()
    return msg, author_name, author_email


def get_file_blob_content(commit_sha, path):
    return subprocess.check_output(["git", "show", f"{commit_sha}:{path}"])


def create_blob(content_bytes):
    b64 = base64.b64encode(content_bytes).decode("ascii")
    r = api_request("POST", "/git/blobs", {"content": b64, "encoding": "base64"})
    return r["sha"]


def create_tree(base_tree_sha, tree_items):
    r = api_request("POST", "/git/trees", {"base_tree": base_tree_sha, "tree": tree_items})
    return r["sha"]


def create_commit(message, tree_sha, parent_shas, author_name, author_email):
    r = api_request("POST", "/git/commits", {
        "message": message,
        "tree": tree_sha,
        "parents": parent_shas,
        "author": {"name": author_name, "email": author_email},
    })
    return r["sha"]


def update_ref(new_commit_sha):
    r = api_request("PATCH", f"/git/refs/heads/{BRANCH}", {"sha": new_commit_sha, "force": False})
    return r["object"]["sha"]


def push_one_commit(local_sha, parent_remote_sha):
    msg, author_name, author_email = get_commit_meta(local_sha)
    files = get_changed_files(local_sha)
    print(f"  Commit {local_sha[:10]}: {len(files)} files | {msg.splitlines()[0][:60]}")

    tree_items = []
    for status, path in files:
        if status == "D":
            tree_items.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
        else:
            content = get_file_blob_content(local_sha, path)
            blob_sha = create_blob(content)
            tree_items.append({"path": path, "mode": "100644", "type": "blob", "sha": blob_sha})
            print(f"    blob[{blob_sha[:10]}] ← {path} ({len(content)} bytes)")

    parent_commit = api_request("GET", f"/git/commits/{parent_remote_sha}")
    base_tree = parent_commit["tree"]["sha"]
    new_tree = create_tree(base_tree, tree_items)
    new_commit = create_commit(msg, new_tree, [parent_remote_sha], author_name, author_email)
    print(f"  → new remote commit: {new_commit[:10]}")
    return new_commit


def main():
    os.chdir("/Users/xuepinxueping.gxpg.gxp/skill-research")
    remote_sha = get_remote_head()
    print(f"Remote HEAD: {remote_sha[:10]}")
    commits = get_local_commits_to_push(remote_sha)
    if not commits:
        print("✅ Already up to date.")
        return
    print(f"Will push {len(commits)} commit(s):")
    for c in commits:
        print(f"  - {c[:10]}")

    parent = remote_sha
    last_new = None
    for local_sha in commits:
        last_new = push_one_commit(local_sha, parent)
        parent = last_new

    final = update_ref(last_new)
    print(f"\n✅ Updated refs/heads/{BRANCH} → {final[:10]}")


if __name__ == "__main__":
    main()
