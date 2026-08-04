#!/usr/bin/env python3
"""
check_bioc_source_repos.py

Monitors recently updated repositories in the bioconductor-source GitHub organization.
Checks targeted branches (`devel` and `RELEASE_3_23`) for:
  1. Large files (> 5 MB)
  2. Git LFS usage (.gitattributes or LFS pointer files)
  3. Checked-in secrets and sensitive credentials
  4. Invalid version bump (compared against official Bioconductor VIEWS file versions:
     x unchanged, y unchanged or 99 on devel, z > last known z)

Operates in READ-ONLY mode on target repositories (no write action performed on destination repos).
Outputs detailed diagnostics to stdout and step summary, and writes failure report files
into generic branch subdirectories (`FailedChecks/devel/` and `FailedChecks/release/`) for any offending repository.

Author: Bioconductor Tooling / Transition Team
"""

import os
import re
import sys
import json
import base64
import argparse
import requests
import time
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# Environment & Default Configuration
# ---------------------------------------------------------------------------
DEFAULT_ORG = os.environ.get("BIOC_SOURCE_ORG", "bioconductor-source")
GITHUB_TOKEN = (
    os.environ.get("GITHUB_TOKEN")
    or os.environ.get("BIOC_SOURCE_TOKEN")
    or os.environ.get("BIOC_ORG_TOKEN")
)

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# Standard targeted branches
TARGET_BRANCHES = ["devel", "RELEASE_3_23"]

# Patterns for secret scanning
SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN\s+(?:RSA|DSA|EC|OPENSSH|PGP)\s+PRIVATE\s+KEY-----"), "Private Key"),
    (re.compile(r"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])"), "AWS Access Key ID"),
    (re.compile(r"aws_secret_access_key\s*=\s*['"]?[A-Za-z0-9/+=]{40}['"]?", re.IGNORECASE), "AWS Secret Access Key"),
    (re.compile(r"ghp_[A-Za-z0-9_]{36}"), "GitHub Personal Access Token (classic)"),
    (re.compile(r"gho_[A-Za-z0-9_]{36}"), "GitHub OAuth Access Token"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{22}_[A-Za-z0-9_]{59}"), "GitHub Fine-grained Personal Access Token"),
    (re.compile(r"xox[baprs]-[0-9a-zA-Z]{10,48}"), "Slack Token"),
    (re.compile(r"(?:api[_\-]?key|secret[_\-]?key|auth[_\-]?token|password)\s*[:=]\s*['"][A-Za-z0-9_\-]{16,}['"]", re.IGNORECASE), "Generic Credential / API Key"),
]

# File extensions to ignore for secret scanning
SKIP_SECRET_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.zip', '.tar', '.gz', '.tgz',
    '.bz2', '.7z', '.rds', '.rda', '.RData', '.bam', '.sam', '.bw', '.bigWig',
    '.so', '.o', '.a', '.dll', '.exe', '.pyc', '.woff', '.woff2', '.ttf', '.eot'
}

# ---------------------------------------------------------------------------
# Bioconductor VIEWS Cache & Fetching
# ---------------------------------------------------------------------------
VIEWS_CACHE = {}

def get_views_urls_for_branch(branch):
    """
    Returns the list of Bioconductor VIEWS URLs for a given branch.
    Categories checked: bioc, data/experiment, data/annotation, workflows.
    """
    categories = ["bioc", "data/experiment", "data/annotation", "workflows"]

    if branch == "devel":
        return [f"https://www.bioconductor.org/packages/devel/{cat}/VIEWS" for cat in categories]

    # Check numeric release branch if matching RELEASE_X_Y
    rel_num_match = re.match(r"^RELEASE_(\d+)_(\d+)$", branch, re.IGNORECASE)
    urls = []
    if rel_num_match:
        rel_ver = f"{rel_num_match.group(1)}.{rel_num_match.group(2)}"
        urls.extend([f"https://www.bioconductor.org/packages/{rel_ver}/{cat}/VIEWS" for cat in categories])

    # Default release fallback URLs
    urls.extend([f"https://www.bioconductor.org/packages/release/{cat}/VIEWS" for cat in categories])
    return urls


def load_views_for_branch(branch):
    """
    Downloads and parses all VIEWS files for a branch into a single dictionary {pkg_name: version}.
    Caches results in memory to avoid redundant network calls.
    """
    if branch in VIEWS_CACHE:
        return VIEWS_CACHE[branch]

    pkg_map = {}
    urls = get_views_urls_for_branch(branch)

    for url in urls:
        r = github_request(url)
        if not r or r.status_code != 200:
            continue

        # Parse DCF blocks separated by double newlines
        blocks = r.text.split("\n\n")
        for block in blocks:
            pkg_name = None
            pkg_ver = None
            for line in block.splitlines():
                if line.startswith("Package:"):
                    pkg_name = line.split("Package:", 1)[1].strip()
                elif line.startswith("Version:"):
                    pkg_ver = line.split("Version:", 1)[1].strip()

            if pkg_name and pkg_ver:
                pkg_map[pkg_name] = pkg_ver

    VIEWS_CACHE[branch] = pkg_map
    return pkg_map


def get_known_bioconductor_version(repo_name, branch):
    """
    Fetches the known available Bioconductor version for `repo_name` on `branch`
    from official Bioconductor VIEWS files.
    """
    views_data = load_views_for_branch(branch)
    return views_data.get(repo_name)


# ---------------------------------------------------------------------------
# GitHub API Helpers (Strictly READ-ONLY GET requests)
# ---------------------------------------------------------------------------
def get_headers():
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def github_request(url, params=None):
    headers = get_headers()
    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
    except requests.RequestException as e:
        print(f"[ERROR] HTTP GET request failed for {url}: {e}")
        return None

    # Handle rate limiting
    remaining = int(r.headers.get("X-RateLimit-Remaining", 5000))
    if remaining < 50:
        reset_time = int(r.headers.get("X-RateLimit-Reset", 0))
        sleep_duration = max(reset_time - int(time.time()) + 5, 5)
        print(f"[WARN] GitHub API rate limit low ({remaining}). Sleeping {sleep_duration}s...")
        time.sleep(sleep_duration)

    return r


# ---------------------------------------------------------------------------
# Repository Fetcher
# ---------------------------------------------------------------------------
def get_updated_repos(org, hours_back=2.0, single_repo=None):
    """
    Fetch repositories in `org` that were pushed to within the last `hours_back` hours.
    If `single_repo` is specified, fetch only that repository.
    """
    if single_repo:
        url = f"https://api.github.com/repos/{org}/{single_repo}"
        r = github_request(url)
        if r and r.status_code == 200:
            return [r.json()]
        print(f"[ERROR] Repository '{single_repo}' not found in org '{org}' (status {r.status_code if r else 'N/A'})")
        return []

    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    print(f"[INFO] Scanning org '{org}' for repositories pushed since {cutoff_time.isoformat()} (last {hours_back} hours)")

    recently_updated = []
    page = 1
    per_page = 100

    while True:
        url = f"https://api.github.com/orgs/{org}/repos"
        params = {"sort": "pushed", "direction": "desc", "per_page": per_page, "page": page}
        r = github_request(url, params=params)

        if not r or r.status_code != 200:
            print(f"[ERROR] Could not fetch repos for org '{org}': status {r.status_code if r else 'N/A'}")
            break

        repos = r.json()
        if not repos or not isinstance(repos, list):
            break

        reached_cutoff = False
        for repo in repos:
            pushed_at_str = repo.get("pushed_at")
            if not pushed_at_str:
                continue

            pushed_at = datetime.fromisoformat(pushed_at_str.replace("Z", "+00:00"))
            if pushed_at >= cutoff_time:
                recently_updated.append(repo)
            else:
                reached_cutoff = True
                break

        if reached_cutoff or len(repos) < per_page:
            break

        page += 1

    return recently_updated


# ---------------------------------------------------------------------------
# Version Check Implementation
# ---------------------------------------------------------------------------
def parse_version(ver_str):
    try:
        parts = ver_str.split(".")
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            return int(parts[0]), int(parts[1]), int(parts[2])
    except Exception:
        pass
    return None


def check_version_bump_against_known(org, repo_name, branch, current_version):
    """
    Compares current DESCRIPTION version on `branch` against the known available Bioconductor VIEWS version.
    Rules:
      1. x component must not change relative to known version (x_curr == x_known).
      2. y component must not change (y_curr == y_known), EXCEPT on 'devel' branch where y can be 99.
      3. z component must be strictly greater than last known version z (z_curr > z_known).
    """
    errors = []

    # 1. Fetch known version from official Bioconductor VIEWS files
    known_version = get_known_bioconductor_version(repo_name, branch)
    source_label = "official Bioconductor VIEWS file"

    # 2. Fallback to parent commit on bioconductor-source if not present in VIEWS
    if not known_version:
        commits_url = f"https://api.github.com/repos/{org}/{repo_name}/commits"
        params = {"sha": branch, "path": "DESCRIPTION", "per_page": 2}
        r = github_request(commits_url, params=params)
        if r and r.status_code == 200:
            commits = r.json()
            if isinstance(commits, list) and len(commits) >= 2:
                parent_sha = commits[1]["sha"]
                parent_desc_url = f"https://api.github.com/repos/{org}/{repo_name}/contents/DESCRIPTION"
                r_parent = github_request(parent_desc_url, params={"ref": parent_sha})
                if r_parent and r_parent.status_code == 200:
                    try:
                        parent_content = base64.b64decode(r_parent.json()["content"]).decode("utf-8")
                        match = re.search(r"^Version:\s*(.+)$", parent_content, re.MULTILINE)
                        if match:
                            known_version = match.group(1).strip()
                            source_label = "parent commit in bioconductor-source"
                    except Exception:
                        pass

    if not known_version:
        # Brand new package not yet in VIEWS or commit history
        return errors

    curr_p = parse_version(current_version)
    known_p = parse_version(known_version)

    if not curr_p:
        errors.append(f"Invalid current version format '{current_version}' (must be x.y.z format).")
        return errors

    if not known_p:
        errors.append(f"Could not parse last known version '{known_version}'.")
        return errors

    curr_x, curr_y, curr_z = curr_p
    known_x, known_y, known_z = known_p

    # Rule 1: x component should not change
    if curr_x != known_x:
        errors.append(f"Invalid version bump on '{branch}': x component changed from {known_x} to {curr_x} (last known in {source_label}: {known_version}, current: {current_version}). x must remain {known_x}.")

    # Rule 2: y component should not change, EXCEPT on 'devel' where y can be 99
    if curr_y != known_y:
        if branch == "devel" and curr_y == 99:
            pass  # Allowed exception for devel branch
        else:
            suffix = " or be 99 on devel." if branch == "devel" else "."
            errors.append(f"Invalid version bump on '{branch}': y component changed from {known_y} to {curr_y} (last known in {source_label}: {known_version}, current: {current_version}). y must remain {known_y}{suffix}")

    # Rule 3: z component should be greater than last known version
    if curr_y == known_y:
        if curr_z <= known_z:
            errors.append(f"Invalid version bump on '{branch}': z component ({curr_z}) must be greater than last known version z ({known_z}) (last known in {source_label}: {known_version}, current: {current_version}).")

    return errors


# ---------------------------------------------------------------------------
# Branch Inspection
# ---------------------------------------------------------------------------
def inspect_branch(org, repo_name, branch):
    """
    Runs all 4 checks on a specific branch of a repo:
      1. Large files (> 5MB)
      2. Git LFS (.gitattributes & LFS pointer files)
      3. Checked-in secrets
      4. Invalid version bump against known Bioconductor VIEWS version
    """
    categorized_issues = {
        "large_files": [],
        "git_lfs": [],
        "secrets": [],
        "version_bump": []
    }

    # Check branch existence
    branch_url = f"https://api.github.com/repos/{org}/{repo_name}/branches/{branch}"
    r_branch = github_request(branch_url)
    if not r_branch or r_branch.status_code == 404:
        # Branch doesn't exist on this repo
        return None
    if r_branch.status_code != 200:
        categorized_issues["version_bump"].append(f"Could not check branch '{branch}': status {r_branch.status_code}")
        return categorized_issues

    # 1. Fetch Git Tree recursively
    tree_url = f"https://api.github.com/repos/{org}/{repo_name}/git/trees/{branch}"
    r_tree = github_request(tree_url, params={"recursive": "1"})

    tree_items = []
    if r_tree and r_tree.status_code == 200:
        tree_data = r_tree.json()
        tree_items = tree_data.get("tree", [])
        if tree_data.get("truncated"):
            print(f"[WARN] Git tree for {repo_name}@{branch} was truncated by GitHub API.")

    # Check 1: Large Files (> 5MB)
    for item in tree_items:
        if item.get("type") == "blob":
            size = item.get("size", 0)
            if size > MAX_FILE_SIZE_BYTES:
                size_mb = size / (1024 * 1024)
                categorized_issues["large_files"].append(f"File `{item['path']}` ({size_mb:.2f} MB exceeds 5 MB limit)")

    # Check 2: Git LFS (.gitattributes & LFS pointers)
    gitattr_url = f"https://api.github.com/repos/{org}/{repo_name}/contents/.gitattributes"
    r_attr = github_request(gitattr_url, params={"ref": branch})
    if r_attr and r_attr.status_code == 200:
        try:
            attr_content = base64.b64decode(r_attr.json()["content"]).decode("utf-8", errors="ignore")
            if "filter=lfs" in attr_content:
                categorized_issues["git_lfs"].append("Git LFS configured in `.gitattributes`")
        except Exception:
            pass

    for item in tree_items:
        if item.get("type") == "blob" and 0 < item.get("size", 0) < 500:
            file_path = item["path"]
            if file_path == ".gitattributes":
                continue
            content_url = f"https://api.github.com/repos/{org}/{repo_name}/contents/{file_path}"
            r_file = github_request(content_url, params={"ref": branch})
            if r_file and r_file.status_code == 200:
                try:
                    text = base64.b64decode(r_file.json()["content"]).decode("utf-8", errors="ignore")
                    if text.startswith("version https://git-lfs.github.com/spec/v1"):
                        categorized_issues["git_lfs"].append(f"Git LFS pointer file detected at `{file_path}`")
                except Exception:
                    pass

    # Check 3: Secrets & Sensitive Credentials
    for item in tree_items:
        if item.get("type") == "blob" and 0 < item.get("size", 0) < 1000000:
            file_path = item["path"]
            _, ext = os.path.splitext(file_path.lower())
            if ext in SKIP_SECRET_EXTENSIONS:
                continue

            content_url = f"https://api.github.com/repos/{org}/{repo_name}/contents/{file_path}"
            r_file = github_request(content_url, params={"ref": branch})
            if r_file and r_file.status_code == 200:
                try:
                    text = base64.b64decode(r_file.json()["content"]).decode("utf-8", errors="ignore")
                    for pattern, secret_type in SECRET_PATTERNS:
                        if pattern.search(text):
                            categorized_issues["secrets"].append(f"Secret detected (`{secret_type}`) in `{file_path}`")
                            break
                except Exception:
                    pass

    # Check 4: Version Bump against Known Bioconductor VIEWS Version
    desc_url = f"https://api.github.com/repos/{org}/{repo_name}/contents/DESCRIPTION"
    r_desc = github_request(desc_url, params={"ref": branch})
    if not r_desc or r_desc.status_code == 404:
        categorized_issues["version_bump"].append(f"`DESCRIPTION` file missing on branch `{branch}`")
    elif r_desc.status_code == 200:
        try:
            desc_text = base64.b64decode(r_desc.json()["content"]).decode("utf-8", errors="ignore")
            version_match = re.search(r"^Version:\s*(.+)$", desc_text, re.MULTILINE)
            if not version_match:
                categorized_issues["version_bump"].append(f"`DESCRIPTION` missing `Version:` field on branch `{branch}`")
            else:
                curr_version = version_match.group(1).strip()
                bump_errors = check_version_bump_against_known(org, repo_name, branch, curr_version)
                categorized_issues["version_bump"].extend(bump_errors)

        except Exception as e:
            categorized_issues["version_bump"].append(f"Unable to parse `DESCRIPTION` on branch `{branch}`: {e}")

    return categorized_issues


# ---------------------------------------------------------------------------
# Issue Template Generator
# ---------------------------------------------------------------------------
def generate_issue_template(org, repo_name, branch, categorized_issues):
    """
    Generates a Markdown template suitable for creating a GitHub issue on an offending repository.
    """
    title = f"[Action Required] Precheck Compliance Failures on branch `{branch}`"

    body_lines = [
        f"## 🚨 Bioconductor Precheck Issue Report: `{repo_name}`",
        "",
        f"**Repository:** `{org}/{repo_name}`  ",
        f"**Branch:** `{branch}`  ",
        f"**Date:** `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}`  ",
        "",
        "The automated repository checker identified compliance issues on this branch that require maintenance before building or syncing:",
        ""
    ]

    has_any = False
    if categorized_issues["large_files"]:
        has_any = True
        body_lines.append("### 🐘 Large Files (> 5MB)")
        body_lines.append("Bioconductor policy limits files in package repositories to 5MB. Large data files should be moved to ExperimentData/Annotation packages or hosted externally.")
        for item in categorized_issues["large_files"]:
            body_lines.append(f"- {item}")
        body_lines.append("")

    if categorized_issues["git_lfs"]:
        has_any = True
        body_lines.append("### 🐙 Git LFS Usage")
        body_lines.append("Bioconductor does **NOT** allow Git LFS. Please remove Git LFS tracking from `.gitattributes` and rewrite repository history to purge LFS objects.")
        for item in categorized_issues["git_lfs"]:
            body_lines.append(f"- {item}")
        body_lines.append("")

    if categorized_issues["secrets"]:
        has_any = True
        body_lines.append("### 🔑 Checked-in Secrets / Credentials")
        body_lines.append("Possible private keys or API tokens were detected. Immediately revoke the affected credentials and purge them from git history.")
        for item in categorized_issues["secrets"]:
            body_lines.append(f"- {item}")
        body_lines.append("")

    if categorized_issues["version_bump"]:
        has_any = True
        body_lines.append("### 📄 Version Bump Issues")
        body_lines.append("Package versions must follow Bioconductor version bump rules relative to official VIEWS version (x unchanged, y unchanged or 99 on devel, z > last known z).")
        for item in categorized_issues["version_bump"]:
            body_lines.append(f"- {item}")
        body_lines.append("")

    if not has_any:
        return None, None

    body_lines.append("---")
    body_lines.append("### 🛠️ Next Steps")
    body_lines.append("Please address these issues on the specified branch and push a new commit with an updated `Version:` number in `DESCRIPTION`.")

    return title, "\n".join(body_lines)


# ---------------------------------------------------------------------------
# Failed Checks Report File Generator (Generic 'devel' & 'release' Subdirectories)
# ---------------------------------------------------------------------------
def get_failed_check_subdirectory(branch):
    """
    Maps branch names to generic directory names under FailedChecks:
      - 'devel' -> 'devel'
      - Any release branch (e.g. 'RELEASE_3_23', 'release') -> 'release'
    """
    if branch == "devel":
        return "devel"
    if branch.startswith("RELEASE_") or branch.lower() == "release":
        return "release"
    return branch


def write_branch_failed_report(failed_dir, org, repo_name, branch, categorized, tmpl):
    """
    Writes or overwrites a branch-specific failure report file named `{repo_name}.txt`
    inside `{failed_dir}/{sub_dir}/` (e.g. `FailedChecks/devel/` or `FailedChecks/release/`).
    """
    sub_dir = get_failed_check_subdirectory(branch)
    branch_dir = os.path.join(failed_dir, sub_dir)
    os.makedirs(branch_dir, exist_ok=True)
    report_file_path = os.path.join(branch_dir, f"{repo_name}.txt")

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        f"PACKAGE: {repo_name}",
        f"ORGANIZATION: {org}",
        f"BRANCH: {branch}",
        f"CATEGORY_DIR: {sub_dir}",
        f"DATE: {now_str}",
        f"STATUS: FAILED",
        "=" * 65,
        f"SUMMARY OF DETECTED COMPLIANCE FAILURES ON BRANCH '{branch}'",
        "=" * 65,
        ""
    ]

    if categorized["large_files"]:
        lines.append("  [Large Files (> 5MB)]")
        for item in categorized["large_files"]:
            lines.append(f"    - {item}")

    if categorized["git_lfs"]:
        lines.append("  [Git LFS Usage]")
        for item in categorized["git_lfs"]:
            lines.append(f"    - {item}")

    if categorized["secrets"]:
        lines.append("  [Checked-in Secrets]")
        for item in categorized["secrets"]:
            lines.append(f"    - {item}")

    if categorized["version_bump"]:
        lines.append("  [Version Bump / Format Issues]")
        for item in categorized["version_bump"]:
            lines.append(f"    - {item}")

    lines.append("")
    lines.append("=" * 65)
    lines.append("GENERATED GITHUB ISSUE TEMPLATE")
    lines.append("=" * 65)
    lines.append("")
    if tmpl:
        lines.append(f"TITLE: {tmpl['title']}")
        lines.append("\nBODY:")
        lines.append(tmpl["body"])

    with open(report_file_path, "w", encoding="utf-8") as out:
        out.write("\n".join(lines))

    print(f"  💾 Branch failure report saved to: {report_file_path}")


def clear_branch_failed_report(failed_dir, repo_name, branch):
    """
    Removes `{failed_dir}/{sub_dir}/{repo_name}.txt` if the branch now passes all checks.
    """
    sub_dir = get_failed_check_subdirectory(branch)
    report_file_path = os.path.join(failed_dir, sub_dir, f"{repo_name}.txt")
    if os.path.exists(report_file_path):
        try:
            os.remove(report_file_path)
            print(f"  🧹 Cleared previous failure report for branch '{branch}': {report_file_path}")
        except Exception as e:
            print(f"  [WARN] Could not remove old failure report {report_file_path}: {e}")


# ---------------------------------------------------------------------------
# Main Execution Loop & Reporting
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Check bioconductor-source organization repos for issues.")
    parser.add_argument("--org", default=DEFAULT_ORG, help=f"GitHub organization (default: {DEFAULT_ORG})")
    parser.add_argument("--hours-back", type=float, default=2.0, help="Hours back to check for pushed repos (default: 2.0)")
    parser.add_argument("--repo", default=None, help="Check single repository name")
    parser.add_argument("--branches", default=",".join(TARGET_BRANCHES), help="Comma-separated branches to check")
    parser.add_argument("--failed-dir", default="DailyBuilder/FailedChecks", help="Directory to save failure report files (default: DailyBuilder/FailedChecks)")
    args = parser.parse_args()

    org = args.org
    hours_back = args.hours_back
    single_repo = args.repo
    branches_to_check = [b.strip() for b in args.branches.split(",") if b.strip()]
    failed_dir = args.failed_dir

    print("=================================================================")
    print(f"Bioconductor Source Repository Checker (READ-ONLY MODE)")
    print(f"Organization: {org}")
    print(f"Branches:     {', '.join(branches_to_check)}")
    print(f"Lookback:     {hours_back} hours")
    print(f"Failed Dir:   {failed_dir}")
    if single_repo:
        print(f"Single Repo:  {single_repo}")
    print("=================================================================\n")

    repos = get_updated_repos(org, hours_back=hours_back, single_repo=single_repo)

    if not repos:
        print("✅ No recently updated repositories found.")
        sys.exit(0)

    print(f"Found {len(repos)} repository(ies) to inspect.\n")

    summary_records = []
    issue_templates_to_print = []
    total_failures = 0

    for repo_data in repos:
        repo_name = repo_data["name"]
        print(f"-----------------------------------------------------------------")
        print(f"📦 Inspecting Repository: {repo_name}")
        print(f"-----------------------------------------------------------------")

        repo_record = {
            "name": repo_name,
            "url": repo_data.get("html_url"),
            "branches": {}
        }

        for branch in branches_to_check:
            categorized = inspect_branch(org, repo_name, branch)
            if categorized is None:
                print(f"  Branch `{branch}`: (Does not exist)")
                repo_record["branches"][branch] = None
                clear_branch_failed_report(failed_dir, repo_name, branch)
            else:
                all_branch_issues = (
                    categorized["large_files"]
                    + categorized["git_lfs"]
                    + categorized["secrets"]
                    + categorized["version_bump"]
                )
                if len(all_branch_issues) == 0:
                    print(f"  Branch `{branch}`: ✅ All checks passed")
                    repo_record["branches"][branch] = []
                    clear_branch_failed_report(failed_dir, repo_name, branch)
                else:
                    print(f"  Branch `{branch}`: ❌ {len(all_branch_issues)} issue(s) found:")
                    for issue in all_branch_issues:
                        print(f"    - {issue}")
                    repo_record["branches"][branch] = all_branch_issues
                    total_failures += len(all_branch_issues)

                    # Generate Issue Template
                    title, body = generate_issue_template(org, repo_name, branch, categorized)
                    tmpl = None
                    if title and body:
                        tmpl = {
                            "repo": repo_name,
                            "branch": branch,
                            "title": title,
                            "body": body
                        }
                        issue_templates_to_print.append(tmpl)

                    # Write branch-specific failure report to FailedChecks/<devel|release>/<repo_name>.txt
                    write_branch_failed_report(failed_dir, org, repo_name, branch, categorized, tmpl)

        summary_records.append(repo_record)

    # ---------------------------------------------------------
    # Print Generated Issue Templates for Offending Repositories
    # ---------------------------------------------------------
    if issue_templates_to_print:
        print("\n=================================================================")
        print("📋 GENERATED ISSUE TEMPLATES FOR OFFENDING REPOSITORIES")
        print("=================================================================\n")
        for item in issue_templates_to_print:
            print(f"--- [ISSUE TEMPLATE: {item['repo']} @ {item['branch']}] ---")
            print(f"TITLE: {item['title']}\n")
            print("BODY:")
            print(item["body"])
            print("-----------------------------------------------------------------\n")

    # ---------------------------------------------------------
    # Output GitHub Step Summary (Markdown)
    # ---------------------------------------------------------
    step_summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary_path:
        with open(step_summary_path, "a", encoding="utf-8") as summary_file:
            summary_file.write("## 🔍 Bioconductor Source Precheck Summary\n\n")
            summary_file.write(f"**Organization:** `{org}`  \n")
            summary_file.write(f"**Repos Inspected:** {len(repos)}  \n")
            summary_file.write(f"**Total Issues Found:** {total_failures}  \n\n")

            for rec in summary_records:
                summary_file.write(f"### 📦 [{rec['name']}]({rec['url']})\n\n")
                for branch, issues in rec["branches"].items():
                    if issues is None:
                        summary_file.write(f"- Branch `{branch}`: *Not present*\n")
                    elif len(issues) == 0:
                        summary_file.write(f"- Branch `{branch}`: ✅ **PASS**\n")
                    else:
                        summary_file.write(f"- Branch `{branch}`: ❌ **{len(issues)} Issue(s)**\n")
                        for iss in issues:
                            summary_file.write(f"  - {iss}\n")
                summary_file.write("\n")

            if issue_templates_to_print:
                summary_file.write("### 📋 Copy-Pasteable Issue Templates\n\n")
                for item in issue_templates_to_print:
                    summary_file.write(f"<details><summary>Issue Template for <b>{item['repo']}</b> (branch: {item['branch']})</summary>\n\n")
                    summary_file.write(f"**Title:** `{item['title']}`\n\n")
                    summary_file.write("```markdown\n")
                    summary_file.write(item["body"])
                    summary_file.write("\n```\n\n</details>\n\n")

    print("\n=================================================================")
    if total_failures > 0:
        print(f"❌ SCAN COMPLETE: Found {total_failures} issue(s) across repositories. Reports saved to 'devel/' and 'release/' subdirectories in '{failed_dir}'.")
        sys.exit(1)
    else:
        print("✅ SCAN COMPLETE: All checked repositories passed validation.")
        sys.exit(0)


if __name__ == "__main__":
    main()
