#!/usr/bin/env python3

import os
import re
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests


# ============================================================
# Configuration
# ============================================================

ORG = "bioconductor-source"

TOKEN = os.environ["BIOC_SOURCE_TOKEN"]

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json"
}

DEFAULT_LARGE_FILE_LIMIT_MB = 5

EXCEPTION_FILE = "large_file_exceptions.txt"

OUTPUT_DIR = Path("FailedChecks")


# ============================================================
# GitHub API helper
# ============================================================

def github_get(url, params=None):

    r = requests.get(
        url,
        headers=HEADERS,
        params=params
    )
    r.raise_for_status()
    return r.json()

# ============================================================
# Recently pushed repositories
# ============================================================

def get_recently_pushed_repos(hours):

    url = f"https://api.github.com/orgs/{ORG}/repos"
    cutoff = (
        datetime.now(timezone.utc)
        -
        timedelta(hours=hours)
    )
    repos = []
    page = 1
    while True:
        data = github_get(
            url,
            {
                "type": "all",
                "sort": "pushed",
                "direction": "desc",
                "per_page": 100,
                "page": page
            }
        )
        if not data:
            break

        for repo in data:
            pushed = datetime.fromisoformat(
                repo["pushed_at"]
                .replace("Z", "+00:00")
            )

            if pushed < cutoff:
                return repos

            repos.append(repo)

        page += 1

    return repos



# ============================================================
# Branch discovery
# ============================================================

def get_branches(repo):

    url = (
        f"https://api.github.com/repos/"
        f"{repo}/branches"
    )
    data = github_get(
        url,
        {
            "per_page": 100
        }
    )
    return [
        x["name"]
        for x in data
    ]



def get_latest_release_branch(branches):

    releases = [
        b
        for b in branches
        if re.match(
            r"RELEASE_\d+_\d+",
            b
        )
    ]
    if not releases:
        return None

    releases.sort(
        key=lambda x: [
            int(v)
            for v in
            x.replace(
                "RELEASE_",
                ""
            ).split("_")
        ]
    )

    return releases[-1]



# ============================================================
# Branch commit information
# ============================================================

def get_branch_commit(repo, branch):

    url = (
        f"https://api.github.com/repos/"
        f"{repo}/branches/{branch}"
    )
    data = github_get(url)
    commit = data["commit"]
    sha = commit["sha"]
    commit_data = github_get(
        commit["url"]
    )
    commit_time = datetime.fromisoformat(
        commit_data["commit"]["committer"]["date"]
        .replace("Z", "+00:00")
    )
    return {
        "sha": sha,
        "time": commit_time
    }



def get_changed_branches(repo, hours, force=False):

    branches = get_branches(repo)
    check = []
    if "devel" in branches:
        check.append("devel")

    release = get_latest_release_branch(
        branches
    )

    if release:
        check.append(release)

    cutoff = (
        datetime.now(timezone.utc)
        -
        timedelta(hours=hours)
    )

    changed = []

    for branch in check:
        info = get_branch_commit(
            repo,
            branch
        )
        if force or info["time"] >= cutoff:
            changed.append(
                {
                    "branch": branch,
                    "sha": info["sha"],
                    "time": info["time"]
                }
            )

    return changed



# ============================================================
# Checks
# ============================================================

def check_version(repo, branch):

    """
    Placeholder.

    Future:
       fetch DESCRIPTION
       validate version rules
    """

    return []



def get_changed_files(repo, branch):

    commit = get_branch_commit(
        repo,
        branch
    )
    url = (
        f"https://api.github.com/repos/"
        f"{repo}/commits/{commit['sha']}"
    )
    data = github_get(url)
    return data.get(
        "files",
        []
    )

def get_branch_tree(repo, branch):

    url = (
        f"https://api.github.com/repos/"
        f"{repo}/git/trees/{branch}"
    )
    return github_get(
        url,
        {
            "recursive": "true"
        }
    )



def check_large_files(repo, branch, limit_mb):

    failures = []
    tree = get_branch_tree(
        repo,
        branch
    )
    limit = (limit_mb * 1024 * 1024)

    for item in tree.get("tree", []):
        if item["type"] != "blob":
            continue

        size = item.get("size", 0)

        if size > limit:
            failures.append(
                f"{item['path']} "
                f"({size / 1024 / 1024:.2f} MB)"
            )

    return failures


def check_git_lfs(repo, branch):

    url = (
        f"https://raw.githubusercontent.com/"
        f"{repo}/{branch}/.gitattributes"
    )
    r = requests.get(url, headers=HEADERS)

    if r.status_code != 200:
        return []

    for line in r.text.splitlines():
        line = line.strip()
        if not line:
            continue

        if line.startswith("#"):
            continue

        if "filter=lfs" in line:
            return [
                "Git LFS detected in .gitattributes"
            ]

    return []


# ============================================================
# Exceptions
# ============================================================

def load_large_file_exceptions():

    path = Path(EXCEPTION_FILE)
    if not path.exists():
        return set()

    with open(path) as f:

        return {
            x.strip()
            for x in f
            if x.strip()
        }



# ============================================================
# Markdown reporting
# ============================================================

def write_report(repo, branch, failures):

    package = repo.split("/")[-1]
    folder = OUTPUT_DIR

    if branch.startswith("RELEASE_"):
        folder = folder / "release"
    else:
        folder = folder / "devel"

    folder.mkdir(
        parents=True,
        exist_ok=True
    )

    output = folder / f"{package}.md"
    with open(output, "w") as f:
        f.write(
            f"# Failed Checks: {package}\n\n"
        )
        f.write(
            f"Repository: `{repo}`\n\n"
        )
        f.write(
            f"Branch: `{branch}`\n\n"
        )
        for check, errors in failures.items():
            if errors:
                f.write(
                    f"## {check}\n\n"
                )
                for error in errors:
                    f.write(
                        f"- {error}\n"
                    )
                f.write("\n")



# ============================================================
# Validation
# ============================================================

def validate_branch(
        repo,
        branch,
        exceptions,
        large_file_limit):


    failures = {
        "Version": [],
        "Large Files": [],
        "Git LFS": []
    }

    failures["Version"] = check_version(
        repo,
        branch
    )

    package = repo.split("/")[-1]
    if package not in exceptions:
        failures["Large Files"] = check_large_files(
            repo,
            branch,
            large_file_limit
        )

    failures["Git LFS"] = check_git_lfs(
        repo,
        branch
    )

    if any(failures.values()):
        print(
            f"\nFAIL: {repo} [{branch}]"
        )
        write_report(
            repo,
            branch,
            failures
        )
    else:
        print(f"PASS: {repo} [{branch}]")


# ============================================================
# Main
# ============================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--hours",
        type=int,
        default=1
    )

    parser.add_argument(
        "--large-file-limit",
        type=int,
        default=DEFAULT_LARGE_FILE_LIMIT_MB
    )
    
    parser.add_argument(
        "--repo",
        help="Run validation on a single repository (owner/repo)"
    )

    args = parser.parse_args()

    exceptions = load_large_file_exceptions()

    if args.repo:
        repos = [
            {
                "full_name": args.repo
            }
        ]
    else:
        repos = get_recently_pushed_repos(
            args.hours
        )
        
    print(
        f"Found {len(repos)} recently pushed repositories"
    )

    checked = 0

    for repo in repos:
        name = repo["full_name"]
        changed = get_changed_branches(
            name,
            args.hours,
            force=bool(args.repo)
        )
        
        if changed:
            print(
            f"{name}: "
            f"{[x['branch'] for x in changed]}"
        )
            
        for branch in changed:
            checked += 1
            validate_branch(
                name,
                branch["branch"],
                exceptions,
                args.large_file_limit
            )

    print(
        f"Checked {checked} changed branches"
    )



if __name__ == "__main__":
    main()
