#!/usr/bin/env python3
"""Sync local files to GitHub via API (no git push needed).
Handles empty repos by initializing with Contents API first."""

import base64
import json
import os
import sys
import urllib.request
import urllib.error
import time

TOKEN = sys.argv[1]
REPO = sys.argv[2]
LOCAL_ROOT = sys.argv[3]
BRANCH = sys.argv[4] if len(sys.argv) > 4 else "main"
COMMIT_MSG = sys.argv[5] if len(sys.argv) > 5 else "Sync local files"
EXCLUDE_EXTRA = set(sys.argv[6].split(",")) if len(sys.argv) > 6 else set()

EXCLUDE_DIRS = {'.git', '__pycache__', '.venv', 'venv', 'node_modules', '.pytest_cache', '.DS_Store'}
EXCLUDE_EXTS = {'.pyc', '.pyo', '.so', '.egg'}
EXCLUDE_FILES = {'_sync_to_github.py', '.DS_Store'}

API = "https://api.github.com"
HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/vnd.github.v3+json",
}

def api_call(method, path, data=None, retry=2):
    url = f"{API}{path}" if path.startswith("/") else path
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=HEADERS, method=method)
    for attempt in range(retry + 1):
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (403, 429) and attempt < retry:
                print(f"  Rate limited, waiting 5s...")
                time.sleep(5)
                continue
            err_body = e.read().decode()
            print(f"  API Error {e.code}: {method} {url[:80]}")
            print(f"  {err_body[:200]}")
            raise

def collect_files(root):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        if dirpath == root:
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_EXTRA]
        for f in filenames:
            if f in EXCLUDE_FILES:
                continue
            if any(f.endswith(e) for e in EXCLUDE_EXTS):
                continue
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, root)
            files.append((rel, full))
    return files

def init_repo_if_empty(repo, branch):
    """Check if repo is empty; if so, create initial commit via Contents API."""
    try:
        api_call("GET", f"/repos/{repo}/git/ref/heads/{branch}")
        return False
    except urllib.error.HTTPError as e:
        if e.code in (404, 409):
            print(f"Repo is empty, initializing with .gitkeep...")
            b64 = base64.b64encode(b"").decode()
            api_call("PUT", f"/repos/{repo}/contents/.gitkeep", {
                "message": "Initialize repository",
                "content": b64,
                "branch": branch
            })
            print("  Initialized.")
            return True
        raise

def create_blob(repo, filepath):
    with open(filepath, 'rb') as f:
        content = f.read()
    b64 = base64.b64encode(content).decode()
    result = api_call("POST", f"/repos/{repo}/git/blobs", {
        "content": b64,
        "encoding": "base64"
    })
    return result["sha"]

def main():
    print(f"Syncing {LOCAL_ROOT} -> github.com/{REPO} (branch: {BRANCH})")
    if EXCLUDE_EXTRA:
        print(f"Excluding top-level dirs: {EXCLUDE_EXTRA}")

    files = collect_files(LOCAL_ROOT)
    print(f"Found {len(files)} files to sync")

    init_repo_if_empty(REPO, BRANCH)

    ref = api_call("GET", f"/repos/{REPO}/git/ref/heads/{BRANCH}")
    parent_sha = ref["object"]["sha"]
    print(f"Current HEAD: {parent_sha[:8]}")

    tree_items = []
    errors = []
    for i, (rel_path, full_path) in enumerate(files):
        try:
            blob_sha = create_blob(REPO, full_path)
            tree_items.append({
                "path": rel_path,
                "mode": "100644",
                "type": "blob",
                "sha": blob_sha
            })
            if (i + 1) % 20 == 0 or i == len(files) - 1:
                print(f"  Blobs: {i+1}/{len(files)}")
        except Exception as ex:
            errors.append(rel_path)
            print(f"  SKIP {rel_path}: {ex}")

    if not tree_items:
        print("No files to upload!")
        return

    print(f"Creating tree with {len(tree_items)} entries...")
    tree = api_call("POST", f"/repos/{REPO}/git/trees", {"tree": tree_items})
    tree_sha = tree["sha"]
    print(f"Tree: {tree_sha[:8]}")

    new_commit = api_call("POST", f"/repos/{REPO}/git/commits", {
        "message": COMMIT_MSG,
        "tree": tree_sha,
        "parents": [parent_sha]
    })
    commit_sha = new_commit["sha"]
    print(f"Commit: {commit_sha[:8]}")

    api_call("PATCH", f"/repos/{REPO}/git/refs/heads/{BRANCH}", {
        "sha": commit_sha,
        "force": True
    })
    print(f"Updated refs/heads/{BRANCH}")

    if errors:
        print(f"\nWarning: {len(errors)} files skipped due to errors")
    print(f"\nDone! https://github.com/{REPO}")

if __name__ == "__main__":
    main()
