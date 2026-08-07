## Main function to
## Disable git lfs 
def disable_git_lfs(repo_name):
    url = f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/lfs"
    r = github_request("DELETE", url)
    if r.status_code == 204:
        print(f"✅ Disabled Git LFS for {repo_name}")
        return True
    print(f"⚠️ Failed to disable Git LFS: "
          f"{repo_name} {r.status_code} {r.text}")
    return False

##
## Wrapper to Disable Git LFS
##
if disable_git_lfs(repo):
    log("  ✓ Git LFS disabled")
else:
    log("  ✗ FAILED: disable Git LFS")


##
## In BiocContribtions
##  probably run before branch protection rules 
##


###############################################

##
## check existing packages if someone is using git lfs
##

import base64

def check_git_lfs_usage(repo_name):
    url = f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/contents/.gitattributes"
    r = github_request("GET", url)
    # No .gitattributes file means no LFS configuration
    if r.status_code == 404:
        return False
    if r.status_code != 200:
        print(f"⚠️ Failed to retrieve .gitattributes: "
              f"{repo_name} {r.status_code} {r.text}")
        return None
    try:
        content = r.json()
        if "content" not in content:
            return False
        attr_text = base64.b64decode(
            content["content"]
        ).decode("utf-8")
        if "filter=lfs" in attr_text:
            return True
        return False
    except Exception as e:
        print(f"⚠️ Failed to parse .gitattributes: {repo_name} {e}")
        return None



for repo in repos:
    time.sleep(0.5)
    lfs = check_git_lfs_usage(repo)
    if lfs is True:
        print(f"⚠️ Git LFS configured: {repo}")
    elif lfs is None:
        print(f"❓ Unable to check: {repo}")    


###################################################################
##
## Disable Git LFS for Bioconductor repositories
##
## Requires a classic PAT with:
##     repo scope
##
###################################################################

import requests
import time
import os


def github_lfs_request(method, url, **kwargs):
    while True:
        r = requests.request(
            method,
            url,
            headers=LFS_HEADERS,
            **kwargs
        )

        remaining = int(r.headers.get("X-RateLimit-Remaining", 5000))
        reset = int(r.headers.get("X-RateLimit-Reset", 0))

        if remaining % 200 == 0:
            print(f"[rate-limit] remaining={remaining}")

        if remaining < 300:
            sleep_time = max(reset - int(time.time()) + 10, 5)
            print(f"[rate-limit] low ({remaining}). sleeping {sleep_time}s")
            time.sleep(sleep_time)
            continue

        return r


def disable_git_lfs(repo_name):
    url = f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/lfs"

    r = github_lfs_request("DELETE", url)

    if r.status_code == 204:
        print(f"✅ Disabled Git LFS: {repo_name}")
        return True

    print(
        f"⚠️ Failed to disable Git LFS: "
        f"{repo_name} {r.status_code} {r.text}"
    )
    return False


BIOC_ORG = "bioconductor-source"

# Classic PAT with repo scope
LFS_TOKEN = os.environ["BIOC_LFS_TOKEN"]

LFS_HEADERS = {
    "Authorization": f"Bearer {LFS_TOKEN}",
    "Accept": "application/vnd.github+json"
}


MANIFEST = "/home/lkern/BioconductorPackages/PkgManagement/manifest/all_workflows.txt"
LOGFILE = "/home/lkern/BioconductorPackages/Syncing/git_lfs_disable.log"


def log(msg):
    with open(LOGFILE, "a") as out:
        out.write(msg + "\n")


with open(LOGFILE, "w") as out:
    out.write("Git LFS disable\n")
    out.write("================\n\n")


with open(MANIFEST) as f:
    repos = [line.strip() for line in f if line.strip()]


for repo in repos:
    time.sleep(0.5)

    log(f"Repository: {repo}")

    if disable_git_lfs(repo):
        log("  ✓ Git LFS disabled")
    else:
        log("  ✗ FAILED disabling Git LFS")

    log("")
