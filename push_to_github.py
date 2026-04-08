#!/usr/bin/env python3
"""Push SkillWeaver to GitHub using the Git Data API.

Since git push is not available (internal network), this script uses
the GitHub REST API to create blobs, trees, commits, and refs.
"""

import base64
import json
import os
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

GITHUB_API = "https://api.github.com"
OWNER = "hellogxp"
REPO = "skillweaver"
PAT = os.environ.get("GITHUB_TOKEN", "")

# Directories and files to skip
SKIP_DIRS = {".pytest_cache", "__pycache__", ".git", "node_modules", ".venv", "venv"}
SKIP_FILES = {".DS_Store", "Thumbs.db"}
SKIP_EXTENSIONS = {".pyc", ".pyo", ".egg-info"}

PROJECT_ROOT = Path(__file__).parent / "skillweaver"


def api_request(method, path, data=None, retry=3):
    """Make a GitHub API request."""
    url = f"{GITHUB_API}{path}" if path.startswith("/") else path
    headers = {
        "Authorization": f"token {PAT}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode() if data else None

    for attempt in range(retry):
        try:
            req = Request(url, data=body, headers=headers, method=method)
            resp = urlopen(req, timeout=60)
            return json.loads(resp.read().decode()) if resp.read else {}
        except HTTPError as e:
            body_text = e.read().decode() if e.fp else ""
            if e.code == 422 and "already exists" in body_text:
                print(f"  [SKIP] Already exists: {path}")
                return json.loads(body_text) if body_text else {}
            if attempt < retry - 1 and e.code in (502, 503, 429):
                wait = 2 ** attempt
                print(f"  [RETRY] {e.code} on {path}, waiting {wait}s...")
                time.sleep(wait)
                continue
            print(f"  [ERROR] {e.code} {method} {path}: {body_text[:200]}")
            raise
        except Exception as e:
            if attempt < retry - 1:
                time.sleep(2 ** attempt)
                continue
            raise


def create_repo():
    """Create the GitHub repository if it doesn't exist."""
    print(f"Creating repo {OWNER}/{REPO}...")
    try:
        result = api_request("POST", "/user/repos", {
            "name": REPO,
            "description": "AI Agent skill discovery and compositional workflow orchestration",
            "private": False,
            "auto_init": True,
            "license_template": "apache-2.0",
        })
        print(f"  Repo created: {result.get('html_url', 'OK')}")
        time.sleep(2)  # Wait for initialization
        return True
    except HTTPError as e:
        if e.code == 422:
            print(f"  Repo already exists, continuing...")
            return True
        raise


def collect_files(root: Path) -> list[tuple[str, bytes, bool]]:
    """Collect all files to upload. Returns (relative_path, content, is_binary)."""
    files = []
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            continue
        # Skip unwanted directories
        parts = p.relative_to(root).parts
        if any(part in SKIP_DIRS for part in parts):
            continue
        if p.name in SKIP_FILES:
            continue
        if p.suffix in SKIP_EXTENSIONS:
            continue

        rel_path = str(p.relative_to(root))
        try:
            content = p.read_bytes()
            # Check if binary
            is_binary = b"\x00" in content[:8192]
            files.append((rel_path, content, is_binary))
        except Exception as e:
            print(f"  [WARN] Could not read {rel_path}: {e}")

    return files


def create_blob(content: bytes, is_binary: bool) -> str:
    """Create a git blob and return its SHA."""
    if is_binary:
        data = {
            "content": base64.b64encode(content).decode("ascii"),
            "encoding": "base64",
        }
    else:
        data = {
            "content": content.decode("utf-8", errors="replace"),
            "encoding": "utf-8",
        }
    result = api_request("POST", f"/repos/{OWNER}/{REPO}/git/blobs", data)
    return result["sha"]


def main():
    if not PAT:
        print("Error: Set GITHUB_TOKEN environment variable")
        sys.exit(1)

    # Step 1: Create repo
    create_repo()

    # Step 2: Get current main branch ref
    print("\nGetting current main branch...")
    try:
        ref = api_request("GET", f"/repos/{OWNER}/{REPO}/git/ref/heads/main")
        base_commit_sha = ref["object"]["sha"]
        print(f"  Base commit: {base_commit_sha[:12]}")
    except HTTPError:
        # Try 'master' branch instead
        try:
            ref = api_request("GET", f"/repos/{OWNER}/{REPO}/git/ref/heads/master")
            base_commit_sha = ref["object"]["sha"]
            print(f"  Base commit (master): {base_commit_sha[:12]}")
        except HTTPError:
            print("  No existing branch found, creating from scratch")
            base_commit_sha = None

    # Step 3: Collect files
    print(f"\nCollecting files from {PROJECT_ROOT}...")
    files = collect_files(PROJECT_ROOT)
    print(f"  Found {len(files)} files")

    # Step 4: Create blobs
    print("\nCreating blobs...")
    tree_items = []
    for i, (rel_path, content, is_binary) in enumerate(files):
        sha = create_blob(content, is_binary)
        tree_items.append({
            "path": rel_path,
            "mode": "100644",
            "type": "blob",
            "sha": sha,
        })
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(files)} blobs created...")
            time.sleep(0.5)  # Rate limiting

    print(f"  {len(tree_items)} blobs created")

    # Step 5: Create tree
    print("\nCreating tree...")
    tree_data = {"tree": tree_items}
    if base_commit_sha:
        # Get base tree to merge with
        base_commit = api_request("GET", f"/repos/{OWNER}/{REPO}/git/commits/{base_commit_sha}")
        tree_data["base_tree"] = base_commit["tree"]["sha"]

    tree = api_request("POST", f"/repos/{OWNER}/{REPO}/git/trees", tree_data)
    tree_sha = tree["sha"]
    print(f"  Tree SHA: {tree_sha[:12]}")

    # Step 6: Create commit
    print("\nCreating commit...")
    commit_data = {
        "message": "feat: SkillWeaver v0.1.0 - AI Agent skill discovery and compositional workflow orchestration\n\n"
                   "- Core pipeline: Decompose-Retrieve-Compose with 4 LLM backends\n"
                   "- Semantic skill search with FAISS + sentence-transformers\n"
                   "- MCP Smart Proxy with context-aware tool filtering\n"
                   "- Multi-format adapters: SKILL.md, MCP, OpenAI Functions, LangChain\n"
                   "- CLI with 11 commands, FastAPI HTTP server, Python SDK\n"
                   "- 60 demo skills and 20 test queries\n"
                   "- 152 tests passing",
        "tree": tree_sha,
    }
    if base_commit_sha:
        commit_data["parents"] = [base_commit_sha]

    commit = api_request("POST", f"/repos/{OWNER}/{REPO}/git/commits", commit_data)
    commit_sha = commit["sha"]
    print(f"  Commit SHA: {commit_sha[:12]}")

    # Step 7: Update ref
    print("\nUpdating main branch...")
    try:
        api_request("PATCH", f"/repos/{OWNER}/{REPO}/git/refs/heads/main", {
            "sha": commit_sha,
            "force": True,
        })
        print("  main branch updated!")
    except HTTPError:
        # Branch might not exist, create it
        api_request("POST", f"/repos/{OWNER}/{REPO}/git/refs", {
            "ref": "refs/heads/main",
            "sha": commit_sha,
        })
        print("  main branch created!")

    print(f"\nDone! Repo: https://github.com/{OWNER}/{REPO}")


if __name__ == "__main__":
    main()
