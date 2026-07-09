
import requests

#--------------------------------------
#
# Need an admin token with
# Repo Permissions
#   Admin: Read and Write
#   Contents: Read and Write
#   Metadata: Read Only
# Org Permissions
#   Repo Admin: Read and Write
#--------------------------------------


BIOC_ORG="bioconductor-source"
BIOC_TOKEN = os.environ["BIOC_TOKEN"]

BIOC_HEADERS = {
    "Authorization": f"Bearer {BIOC_TOKEN}",
    "Accept": "application/vnd.github+json"
}


# ----------------------------
#  Current orgs are Free not Team
#  Cannot implement rulesets org wide
#  Implement per repo
#      protect branch (devel, current release)
#      no force pushes except for admins  ---  force push freeze must be done by
#  ruleset to exclude admins
# ----------------------------


# ----------------------------    
## branch given:
## branch cannot be deleted
## normal pushes are allowed
# ----------------------------    
def protect_branch(repo_name, branch="devel"):
    url = f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/branches/{branch}/protection"
    data = {
        "required_status_checks": None,
        "enforce_admins": True,
        "required_pull_request_reviews": None,
        "restrictions": None,
        "allow_force_pushes": True,
        "allow_deletions": False
    }
    r = requests.put(url, headers=BIOC_HEADERS, json=data)
    if r.status_code not in [200]:
        print(f"⚠️ Failed to protect branch: {repo_name} {branch} {r.status_code} {r.text}")
    else:
        print("✅ devel protection applied")


# ----------------------------    
#  Implement per repo
#      protect freeze (legacy release)
#      no force pushes except for admins
# ----------------------------

def freeze_branch(repo_name, branch):
    url = (f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/branches/{branch}/protection")
    data = {
        "required_status_checks": None,
        "enforce_admins": True,
        "required_pull_request_reviews": None,
        "restrictions": None,
        "required_linear_history": False,
        "allow_force_pushes": False,
        "allow_deletions": False,
        "block_creations": True,
        "required_conversation_resolution": False,
        "lock_branch": True,
        "allow_fork_syncing": False
    }
    r = requests.put(url, headers=BIOC_HEADERS, json=data)
    if r.status_code != 200:
        print(f"⚠️ Failed to freeze branch '{branch}': {r.status_code} {r.text}")
    else:
        print(f"✅ Branch '{branch}' is now frozen")

#
# Blocks creation of new branch matching RELEASE_*
#    
def disallow_release_branch(repo_name):
    url = f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/rulesets"
    data = {
        "name": "Disallow non-admin RELEASE branches",
        "target": "branch",
        "enforcement": "active",
        "conditions": {
            "ref_name": {
                "include": ["refs/heads/RELEASE_*"],
                "exclude": []
            }
        },
        "bypass_actors": [
            {
                "actor_type": "RepositoryRole",
                "actor_id": 5,
                "bypass_mode": "always"
            }
        ],
        "rules": [
            {"type": "creation"}
        ]
    }
    r = requests.post(url, headers=BIOC_HEADERS, json=data)
    if r.status_code not in [200, 201]:
        print(f"⚠️ Failed: {repo_name} {r.status_code} {r.text}")
    else:
        print(f"✅ RELEASE ruleset applied for {repo_name}")


#
# New rulese to block force pushes except for admin
#
def admin_force_push_devel_and_release(repo_name):
    url = f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/rulesets"
    data = {
        "name": "Admin-only force push (devel + RELEASE)",
        "target": "branch",
        "enforcement": "active",
        "conditions": {
            "ref_name": {
                "include": [
                    "refs/heads/devel",
                    "refs/heads/RELEASE_*"
                ],
                "exclude": []
            }
        },
        "bypass_actors": [
            {
                "actor_type": "RepositoryRole",
                "actor_id": 5,   
                "bypass_mode": "always"
            }
        ],
        "rules": [
            {
                "type": "non_fast_forward"
            }
        ]
    }
    r = requests.post(url, headers=BIOC_HEADERS, json=data)
    if r.status_code not in [200, 201]:
        print(f"⚠️ Failed ruleset: {repo_name} {r.status_code} {r.text}")
    else:
        print(f"✅ Admin-only force push applied (devel + RELEASE_*)")

        
        
protect_branch("spbtest3")
protect_branch("spbtest3", branch="RELEASE_3_23")
freeze_branch("spbtest3", "RELEASE_3_22")
freeze_branch("spbtest3", "RELEASE_3_4")
disallow_release_branch("spbtest3")
admin_force_push_devel_and_release("spbtest3")



##
## displays current branch protection settings 
##
def get_branch_protection(repo_name, branch):
    url = (f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/branches/{branch}/protection")
    r = requests.get(url, headers=BIOC_HEADERS)
    print(r.status_code)
    print(r.text)


    
get_branch_protection("spbtest3", "devel")


##
## displays current rulesets
##
def get_rulesets(repo_name):
    url = (f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/rulesets")
    r = requests.get(url, headers=BIOC_HEADERS)
    print(r.status_code)
    #print(r.text)
    if r.status_code == 200:
        return r.json()
    return None

get_rulesets("spbtest3")




##
## delete all current rulesets
##
def delete_all_rulesets(repo_name):
    url = f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/rulesets"
    r = requests.get(url, headers=BIOC_HEADERS)
    if r.status_code != 200:
        print(f"⚠️ Failed to fetch rulesets: {r.status_code} {r.text}")
        return
    rulesets = r.json()
    if not rulesets:
        print("ℹ️ No rulesets to delete")
        return
    deleted = 0
    for rs in rulesets:
        rs_id = rs.get("id")
        rs_name = rs.get("name")
        del_url = f"{url}/{rs_id}"
        r_del = requests.delete(del_url, headers=BIOC_HEADERS)
        if r_del.status_code == 204:
            print(f"✅ Deleted ruleset: {rs_name} ({rs_id})")
            deleted += 1
        else:
            print(f"⚠️ Failed to delete ruleset {rs_name} ({rs_id}): "
                  f"{r_del.status_code} {r_del.text}")
    print(f"\n🧹 Finished. Deleted {deleted}/{len(rulesets)} rulesets.")



delete_rulesets("spbtest3")


#############################################################
##
##
##
##
##
## Lifecycle of package
##
##
##
##
##
#############################################################

# 
# When a package is first created:
#     devel is protected
#     collaborator cannot delete devel
#     collaborator cannot force push to devel
#     administrators can force push devel
#     collaborators cannot create future RELEASE_* branches
#
protect_branch(repo, "devel")
disallow_release_branch(repo)
admin_force_push_devel_and_release(repo)
disable_actions(repo)
 
#
# When there is a new release
#   example: RELEASE_3_26
#      
#
protect_branch(repo, "RELEASE_3_26")
freeze_branch(repo, "RELEASE_3_25")

##
## Retro active will need to freeze each available
##



def get_branches(repo_name):
    url = f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/branches?per_page=100"
    r = requests.get(url, headers=BIOC_HEADERS)
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        print(f"⚠️ Failed to retrieve branches for {repo_name}: "
              f"{r.status_code} {r.text}")
        return None
    return [b["name"] for b in r.json()]




## Test
log(f"Repository: {repo}")
branches = get_branches(repo)
if branches is None:
    log("  ✗ Repository not found")
    log("")
    continue
    #
    # Base protection
    #
if protect_branch(repo, "devel"):
    log("  ✓ Protected: devel")
else:
    log("  ✗ FAILED: protect devel")
if CURRENT_RELEASE in branches:
    if protect_branch(repo, CURRENT_RELEASE):
        log(f"  ✓ Protected: {CURRENT_RELEASE}")
    else:
        log(f"  ✗ FAILED: protect {CURRENT_RELEASE}")
else:
    log(f"  - Current release missing: {CURRENT_RELEASE}")
if disallow_release_branch(repo):
    log("  ✓ Applied RELEASE_* creation ruleset")
else:
    log("  ✗ FAILED: RELEASE_* creation ruleset")
if admin_force_push_devel_and_release(repo):
    log("  ✓ Applied admin-only force-push ruleset")
else:
    log("  ✗ FAILED: admin-only force-push ruleset")
    #
    # Freeze historical releases
    #
frozen = []
for branch in branches:
    if branch.startswith("RELEASE_") and branch != CURRENT_RELEASE:
        if freeze_branch(repo, branch):
            frozen.append(branch)
        else:
            log(f"  ✗ FAILED: freeze {branch}")
if frozen:
    for branch in frozen:
        log(f"  ✓ Frozen: {branch}")
else:
    log("  - No historical RELEASE branches found")
log("")



###################################################################
##
##
##
##
##
##
## Script to automate
##
##
##
##
##
###################################################################


import requests
import time

def protect_branch(repo_name, branch="devel"):
    url = f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/branches/{branch}/protection"
    data = {
        "required_status_checks": None,
        "enforce_admins": True,
        "required_pull_request_reviews": None,
        "restrictions": None,
        "allow_force_pushes": True,
        "allow_deletions": False
    }
    r = requests.put(url, headers=BIOC_HEADERS, json=data)
    if r.status_code not in [200]:
        print(f"⚠️ Failed to protect branch: {repo_name} {branch} {r.status_code} {r.text}")
        return False
    else:
        print(f"✅ {branch} protection applied")
        return True


def freeze_branch(repo_name, branch):
    url = (f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/branches/{branch}/protection")
    data = {
        "required_status_checks": None,
        "enforce_admins": True,
        "required_pull_request_reviews": None,
        "restrictions": None,
        "required_linear_history": False,
        "allow_force_pushes": False,
        "allow_deletions": False,
        "block_creations": True,
        "required_conversation_resolution": False,
        "lock_branch": True,
        "allow_fork_syncing": False
    }
    r = requests.put(url, headers=BIOC_HEADERS, json=data)
    if r.status_code != 200:
        print(f"⚠️ Failed to freeze branch '{branch}': {r.status_code} {r.text}")
        return False
    else:
        print(f"✅ Branch '{branch}' is now frozen")
        return True


def disallow_release_branch(repo_name):
    url = f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/rulesets"
    data = {
        "name": "Disallow non-admin RELEASE branches",
        "target": "branch",
        "enforcement": "active",
        "conditions": {
            "ref_name": {
                "include": ["refs/heads/RELEASE_*"],
                "exclude": []
            }
        },
        "bypass_actors": [
            {
                "actor_type": "RepositoryRole",
                "actor_id": 5,
                "bypass_mode": "always"
            }
        ],
        "rules": [
            {"type": "creation"}
        ]
    }
    r = requests.post(url, headers=BIOC_HEADERS, json=data)
    if r.status_code not in [200, 201]:
        print(f"⚠️ Failed: {repo_name} {r.status_code} {r.text}")
        return False
    else:
        print(f"✅ RELEASE ruleset applied for {repo_name}")
        return True


def admin_force_push_devel_and_release(repo_name):
    url = f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/rulesets"
    data = {
        "name": "Admin-only force push (devel + RELEASE)",
        "target": "branch",
        "enforcement": "active",
        "conditions": {
            "ref_name": {
                "include": [
                    "refs/heads/devel",
                    "refs/heads/RELEASE_*"
                ],
                "exclude": []
            }
        },
        "bypass_actors": [
            {
                "actor_type": "RepositoryRole",
                "actor_id": 5,   
                "bypass_mode": "always"
            }
        ],
        "rules": [
            {
                "type": "non_fast_forward"
            }
        ]
    }
    r = requests.post(url, headers=BIOC_HEADERS, json=data)
    if r.status_code not in [200, 201]:
        print(f"⚠️ Failed ruleset: {repo_name} {r.status_code} {r.text}")
        return False
    else:
        print(f"✅ Admin-only force push applied (devel + RELEASE_*)")
        return True


    
def get_branches(repo_name):
    url = f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/branches?per_page=100"
    r = requests.get(url, headers=BIOC_HEADERS)
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        print(f"⚠️ Failed to retrieve branches for {repo_name}: "
              f"{r.status_code} {r.text}")
        return None
    return [b["name"] for b in r.json()]


    
BIOC_ORG="bioconductor-source"
BIOC_TOKEN = os.environ["BIOC_TOKEN"]

BIOC_HEADERS = {
    "Authorization": f"Bearer {BIOC_TOKEN}",
    "Accept": "application/vnd.github+json"
}

CURRENT_RELEASE = "RELEASE_3_23"

MANIFEST = "/home/lkern/BioconductorPackages/PkgManagement/manifest/all_workflows.txt"
LOGFILE = "/home/lkern/BioconductorPackages/Syncing/workflow_protection.txt"


def log(msg):
    with open(LOGFILE, "a") as out:
        out.write(msg + "\n")


with open(LOGFILE, "w") as out:
    out.write("Workflow branch protection\n")
    out.write("==========================\n\n")


with open(MANIFEST) as f:
    repos = [line.strip() for line in f if line.strip()]


    
for repo in repos:
    time.sleep(0.5)
    log(f"Repository: {repo}")
    branches = get_branches(repo)
    if branches is None:
        log("  ✗ Repository not found")
        log("")
        continue
    #
    # Base protection
    #
    if protect_branch(repo, "devel"):
        log("  ✓ Protected: devel")
    else:
        log("  ✗ FAILED: protect devel")
    if CURRENT_RELEASE in branches:
        if protect_branch(repo, CURRENT_RELEASE):
            log(f"  ✓ Protected: {CURRENT_RELEASE}")
        else:
            log(f"  ✗ FAILED: protect {CURRENT_RELEASE}")
    else:
        log(f"  - Current release missing: {CURRENT_RELEASE}")
    if disallow_release_branch(repo):
        log("  ✓ Applied RELEASE_* creation ruleset")
    else:
        log("  ✗ FAILED: RELEASE_* creation ruleset")
    if admin_force_push_devel_and_release(repo):
        log("  ✓ Applied admin-only force-push ruleset")
    else:
        log("  ✗ FAILED: admin-only force-push ruleset")
    #
    # Freeze historical releases
    #
    frozen = []
    for branch in branches:
        if branch.startswith("RELEASE_") and branch != CURRENT_RELEASE:
            if freeze_branch(repo, branch):
                frozen.append(branch)
            else:
                log(f"  ✗ FAILED: freeze {branch}")
    if frozen:
        for branch in frozen:
            log(f"  ✓ Frozen: {branch}")
    else:
        log("  - No historical RELEASE branches found")
    log("")




    

###################################################################
##
##
##
##
##
##
## Script to automate
##     Version 2 with built in rate limit control 
##
##
##
##
###################################################################


import requests
import time

def github_request(method, url, **kwargs):
    while True:
        r = requests.request(method, url, headers=BIOC_HEADERS, **kwargs)
        remaining = int(r.headers.get("X-RateLimit-Remaining", 5000))
        reset = int(r.headers.get("X-RateLimit-Reset", 0))
        # optional progress
        if remaining % 200 == 0:
            print(f"[rate-limit] remaining={remaining}")
        # If we are about to hit limit, sleep until reset
        if remaining < 300:
            sleep_time = max(reset - int(time.time()) + 10, 5)
            print(f"[rate-limit] low ({remaining}). sleeping {sleep_time}s")
            time.sleep(sleep_time)
            continue
        return r


def protect_branch(repo_name, branch="devel"):
    url = f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/branches/{branch}/protection"
    data = {
        "required_status_checks": None,
        "enforce_admins": True,
        "required_pull_request_reviews": None,
        "restrictions": None,
        "allow_force_pushes": True,
        "allow_deletions": False
    }
    r = github_request("PUT", url, json=data)
    if r.status_code not in [200]:
        print(f"⚠️ Failed to protect branch: {repo_name} {branch} {r.status_code} {r.text}")
        return False
    else:
        print(f"✅ {branch} protection applied")
        return True


def freeze_branch(repo_name, branch):
    url = (f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/branches/{branch}/protection")
    data = {
        "required_status_checks": None,
        "enforce_admins": True,
        "required_pull_request_reviews": None,
        "restrictions": None,
        "required_linear_history": False,
        "allow_force_pushes": False,
        "allow_deletions": False,
        "block_creations": True,
        "required_conversation_resolution": False,
        "lock_branch": True,
        "allow_fork_syncing": False
    }
    r = github_request("PUT", url, json=data)
    if r.status_code != 200:
        print(f"⚠️ Failed to freeze branch '{branch}': {r.status_code} {r.text}")
        return False
    else:
        print(f"✅ Branch '{branch}' is now frozen")
        return True


def disallow_release_branch(repo_name):
    url = f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/rulesets"
    data = {
        "name": "Disallow non-admin RELEASE branches",
        "target": "branch",
        "enforcement": "active",
        "conditions": {
            "ref_name": {
                "include": ["refs/heads/RELEASE_*"],
                "exclude": []
            }
        },
        "bypass_actors": [
            {
                "actor_type": "RepositoryRole",
                "actor_id": 5,
                "bypass_mode": "always"
            }
        ],
        "rules": [
            {"type": "creation"}
        ]
    }
    r = github_request("POST", url, json=data)
    if r.status_code not in [200, 201]:
        print(f"⚠️ Failed: {repo_name} {r.status_code} {r.text}")
        return False
    else:
        print(f"✅ RELEASE ruleset applied for {repo_name}")
        return True


def admin_force_push_devel_and_release(repo_name):
    url = f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/rulesets"
    data = {
        "name": "Admin-only force push (devel + RELEASE)",
        "target": "branch",
        "enforcement": "active",
        "conditions": {
            "ref_name": {
                "include": [
                    "refs/heads/devel",
                    "refs/heads/RELEASE_*"
                ],
                "exclude": []
            }
        },
        "bypass_actors": [
            {
                "actor_type": "RepositoryRole",
                "actor_id": 5,   
                "bypass_mode": "always"
            }
        ],
        "rules": [
            {
                "type": "non_fast_forward"
            }
        ]
    }
    r = github_request("POST", url, json=data)
    if r.status_code not in [200, 201]:
        print(f"⚠️ Failed ruleset: {repo_name} {r.status_code} {r.text}")
        return False
    else:
        print(f"✅ Admin-only force push applied (devel + RELEASE_*)")
        return True


def disable_actions(repo_name):
    url = f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/actions/permissions"
    data = {
        "enabled": False
    }
    r = github_request("PUT", url, json=data)
    if r.status_code == 204:
        print(f"✅ Disabled GitHub Actions for {repo_name}")
        return True
    else:
        print(f"⚠️ Failed to disable Actions: {repo_name} {r.status_code} {r.text}")
        return False

    
def get_branches(repo_name):
    url = f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/branches?per_page=100"
    r = github_request("GET", url)
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        print(f"⚠️ Failed to retrieve branches for {repo_name}: "
              f"{r.status_code} {r.text}")
        return None
    return [b["name"] for b in r.json()]


    
BIOC_ORG="bioconductor-source"
BIOC_TOKEN = os.environ["BIOC_TOKEN"]

BIOC_HEADERS = {
    "Authorization": f"Bearer {BIOC_TOKEN}",
    "Accept": "application/vnd.github+json"
}

CURRENT_RELEASE = "RELEASE_3_23"

MANIFEST = "/home/lkern/BioconductorPackages/PkgManagement/manifest/all_workflows.txt"
LOGFILE = "/home/lkern/BioconductorPackages/Syncing/workflow_protection.txt"


def log(msg):
    with open(LOGFILE, "a") as out:
        out.write(msg + "\n")


with open(LOGFILE, "w") as out:
    out.write("Workflow branch protection\n")
    out.write("==========================\n\n")


with open(MANIFEST) as f:
    repos = [line.strip() for line in f if line.strip()]


    
for repo in repos:
    time.sleep(0.5)
    log(f"Repository: {repo}")
    branches = get_branches(repo)
    if branches is None:
        log("  ✗ Repository not found")
        log("")
        continue
    #
    # Base protection
    #
    if protect_branch(repo, "devel"):
        log("  ✓ Protected: devel")
    else:
        log("  ✗ FAILED: protect devel")
    if CURRENT_RELEASE in branches:
        if protect_branch(repo, CURRENT_RELEASE):
            log(f"  ✓ Protected: {CURRENT_RELEASE}")
        else:
            log(f"  ✗ FAILED: protect {CURRENT_RELEASE}")
    else:
        log(f"  - Current release missing: {CURRENT_RELEASE}")
    if disallow_release_branch(repo):
        log("  ✓ Applied RELEASE_* creation ruleset")
    else:
        log("  ✗ FAILED: RELEASE_* creation ruleset")
    if admin_force_push_devel_and_release(repo):
        log("  ✓ Applied admin-only force-push ruleset")
    else:
        log("  ✗ FAILED: admin-only force-push ruleset")
    #
    # Disable Actions
    #
    if disable_actions(repo):
        log("  ✓ Disabled GitHub Actions")
    else:
        log("  ✗ FAILED: disable GitHub Actions")
    #
    # Freeze historical releases
    #
    frozen = []
    for branch in branches:
        if branch.startswith("RELEASE_") and branch != CURRENT_RELEASE:
            if freeze_branch(repo, branch):
                frozen.append(branch)
            else:
                log(f"  ✗ FAILED: freeze {branch}")
    if frozen:
        for branch in frozen:
            log(f"  ✓ Frozen: {branch}")
    else:
        log("  - No historical RELEASE branches found")
    log("")




    
