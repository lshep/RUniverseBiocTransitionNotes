
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
#      no force pushes except for admins
# ----------------------------

def protect_branch(repo_name, branch="devel"):
    url = f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/branches/{branch}/protection"
    data = {
        "required_status_checks": None,
        "enforce_admins": False,
        "required_pull_request_reviews": None,
        "restrictions": None,
        "allow_force_pushes": False,
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
# Will this reliably prevent collaborators from creating a RELEASE_X_Y branch?
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
        "rules": [
            {"type": "creation"}
        ]
    }
    r = requests.post(url, headers=BIOC_HEADERS, json=data)
    if r.status_code not in [200, 201]:
        print(f"⚠️ Failed: {repo_name} {r.status_code} {r.text}")
    else:
        print(f"✅ RELEASE ruleset applied for {repo_name}")


protect_branch("spbtest3")
protect_branch("spbtest3", branch="RELEASE_3_23")
freeze_branch("spbtest3", "RELEASE_3_22")
freeze_branch("spbtest3", "RELEASE_3_4")
disallow_release_branch("spbtest3")




def get_branch_protection(repo_name, branch):
    url = (f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/branches/{branch}/protection")
    r = requests.get(url, headers=BIOC_HEADERS)
    print(r.status_code)
    print(r.text)


    
get_branch_protection("spbtest3", "devel")


def get_rulesets(repo_name):
    url = (f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/rulesets")
    r = requests.get(url, headers=BIOC_HEADERS)
    print(r.status_code)
    print(r.text)


get_rulesets("spbtest3")


def delete_ruleset(repo_name, ruleset_id):
    url = f"https://api.github.com/repos/{BIOC_ORG}/{repo_name}/rulesets/{ruleset_id}"
    r = requests.delete(url, headers=BIOC_HEADERS)
    print(r.status_code, r.text)


delete_ruleset("spbtest3", 16451656)
