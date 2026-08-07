#!/usr/bin/env python3

import argparse
import subprocess
from pathlib import Path
import json
import time
import sys
from datetime import datetime
import requests
import os


## Shouldn't need to unset if you HEADER below
## unset GITHUB_TOKEN
## unset GH_TOKEN
## gh auth logout
## gh auth login 



# ============================================================
# Configuration
# ============================================================

BIOC_TOKEN = os.environ["BIOC_TOKEN"]

BIOC_HEADERS = {
    "Authorization": f"Bearer {BIOC_TOKEN}",
    "Accept": "application/vnd.github+json"
}


ORG = "bioconductor-source"

# Location of the manifest git repository
MANIFEST_REPO = Path("~/BioconductorPackages/PkgManagement/manifest").expanduser()

DEVEL_BRANCH = "devel"
RELEASE_BRANCH = "RELEASE_3_23"

MANIFEST_FILES = [
    "software.txt",
    "data-annotation.txt",
    "data-experiment.txt",
    "books.txt",
    "workflows.txt",
]

OUTPUT_FILE = "deprecated_candidates.txt"

SLEEP_SECONDS = 1
RATE_LIMIT_CHECK_INTERVAL = 100
RATE_LIMIT_THRESHOLD = 100
RATE_LIMIT_BUFFER = 30   

# ============================================================
# Manifest handling
# ============================================================

def read_manifest_from_git(branch, filename):
    result = subprocess.run(
        [
            "git",
            "-C",
            str(MANIFEST_REPO),
            "show",
            f"{branch}:{filename}",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    packages = set()
    for line in result.stdout.splitlines():
        if line.startswith("Package:"):
            packages.add(line.split(":", 1)[1].strip())
    return packages


def get_packages_from_branch(branch):
    packages = set()
    print(f"\nReading manifest branch: {branch}")
    for filename in MANIFEST_FILES:
        found = read_manifest_from_git(branch, filename)
        print(f"  {filename:<25} {len(found)}")
        packages.update(found)
    print(f"  Total unique packages: {len(packages)}")
    return packages


# ============================================================
# GitHub handling
# ============================================================

def github_request(method, url, **kwargs):
    while True:
        r = requests.request(
            method,
            url,
            headers=BIOC_HEADERS,
            **kwargs,
        )
        remaining = int(r.headers.get("X-RateLimit-Remaining", 5000))
        reset = int(r.headers.get("X-RateLimit-Reset", 0))
        if remaining % 200 == 0:
            print(f"[rate-limit] remaining={remaining}")
        if remaining < RATE_LIMIT_THRESHOLD and reset:
            sleep_time = max(reset - int(time.time()) + RATE_LIMIT_BUFFER, 5)
            print(f"[rate-limit] low ({remaining}). sleeping {sleep_time}s")
            time.sleep(sleep_time)
            continue
        return r


def get_bioc_package_repositories():
    print(
        f"\nGetting bioc-package repositories from {ORG}"
    )
    repos = set()
    cursor = None
    while True:
        if cursor:
            after_clause = f', after: "{cursor}"'
        else:
            after_clause = ""
        query = f"""
        query {{
          organization(login: "{ORG}") {{
            repositories(first: 100{after_clause}) {{
              pageInfo {{
                hasNextPage
                endCursor
              }}
              nodes {{
                name
                repositoryTopics(first: 100) {{
                  nodes {{
                    topic {{
                      name
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """
        result = github_request("POST", "https://api.github.com/graphql",
            json={"query": query})
        data = result.json()
        repositories = data["data"]["organization"]["repositories"]
        for repo in repositories["nodes"]:
            topics = {
                t["topic"]["name"]
                for t in repo["repositoryTopics"]["nodes"]
            }
            if "bioc-package" in topics:
                repos.add(repo["name"])
        page_info = repositories["pageInfo"]
        if not page_info["hasNextPage"]:
            break
        cursor = page_info["endCursor"]
    print(
        f"bioc-package repositories found: {len(repos)}"
    )
    return repos



def add_topic(repo):
    url = f"https://api.github.com/repos/{ORG}/{repo}/topics"
    r = github_request("GET", url)
    if not r.ok:
        print(
            f"  ERROR getting topics for {repo}: "
            f"{r.status_code} {r.text}"
        )
        return False
    topics = r.json()["names"]
    if "bioc-deprecated" not in topics:
        topics.append("bioc-deprecated")
        r = github_request("PUT", url, json={"names": topics})
        if not r.ok:
            print(
                f"  ERROR adding topic to {repo}: "
                f"{r.status_code} {r.text}"
            )
            return False
    return True

def archive_repo(repo):
    url = f"https://api.github.com/repos/{ORG}/{repo}"
    r = github_request("PATCH", url,
        json={
            "archived": True
        })
    if not r.ok:
        print(
            f"  ERROR archiving {repo}: "
            f"{r.status_code} {r.text}"
        )
        return False
    return True


    
# ============================================================
# Main
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Archive repositories not present in "
            "devel or RELEASE_3_23 manifests."
        )
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Actually modify GitHub. "
            "Without this flag, only performs a dry run."
        ),
    )
    args = parser.parse_args()
    # --------------------------------------------------------
    # Build current package list
    # --------------------------------------------------------
    devel_packages = get_packages_from_branch(DEVEL_BRANCH)
    release_packages = get_packages_from_branch(RELEASE_BRANCH)
    current_packages = (
        devel_packages |
        release_packages
    )
    print("\nCurrent package summary")
    print("----------------------")
    print(f"devel:        {len(devel_packages)}")
    print(f"RELEASE_3_23: {len(release_packages)}")
    print(f"combined:     {len(current_packages)}")
    # --------------------------------------------------------
    # Compare against GitHub
    # --------------------------------------------------------
    github_repos = get_bioc_package_repositories()
    deprecated = sorted(
        github_repos - current_packages
    )
    print("\nRepositories not in current manifests")
    print("------------------------------------")
    if not deprecated:
        print("None found")
        return
    for repo in deprecated:
        print(repo)
    print("------------------------------------")
    print(f"Candidates: {len(deprecated)}")
    # Always write the candidate list
    with open(OUTPUT_FILE, "w") as out:
        for repo in deprecated:
            out.write(repo + "\n")
    print(f"\nCandidate list written to {OUTPUT_FILE}")
    # --------------------------------------------------------
    # Dry run
    # --------------------------------------------------------
    if not args.execute:
        print("\nDRY RUN ONLY")
        print("No repositories were modified.")
        print("Run with --execute to archive these repositories.")
        return
    # --------------------------------------------------------
    # Execute changes
    # --------------------------------------------------------
    print("\nEXECUTING CHANGES")
    failures = []
    for repo in deprecated:
        print(f"\nProcessing {repo}")
        print("  Adding topic: bioc-deprecated")
        if not add_topic(repo):
            failures.append(
                (repo, "topic update failed")
            )
            continue
        if not archive_repo(repo):
            failures.append(
                (repo, "archive failed")
             )
            continue
        print("  Done")
    if failures:
        print("\nFailures")
        print("========")
        for repo, reason in failures:
            print(f"{repo}: {reason}")
        with open("archive_failures.txt", "w") as out:
            for repo, reason in failures:
                out.write(f"{repo}\t{reason}\n")

                
if __name__ == "__main__":
    main()
