
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



## ----------------------------
##
## Lifecycle of package
##
## ----------------------------

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

#
# When there is a new release
#   example: RELEASE_3_26
#      
#
protect_branch(repo, "RELEASE_3_26")
freeze_branch(repo, "RELEASE_3_26")

##
## Retro active will need to freeze each available
##
