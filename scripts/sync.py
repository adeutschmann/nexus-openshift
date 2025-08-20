#!/usr/bin/env python3
"""
Sync GitHub org members into Nexus Repository OSS local users (create/update/optional disable).

REQUIRED ENVs
  NEXUS_URL, NEXUS_ADMIN_PASS, GITHUB_ORG, GITHUB_TOKEN

OPTIONAL ENVs
  NEXUS_ADMIN_USER=admin
  DEFAULT_ROLES=nx-browser
  USERNAME_STRATEGY=github_login|email_localpart|raw
  DISABLE_MISSING=false
  DEFAULT_PASSWORD=unused-temp
  EXCLUDE_USERS=admin,ops-admin
  DRY_RUN=false
"""
import base64, json, os, sys, urllib.parse, urllib.request

NEXUS_URL = os.getenv("NEXUS_URL", "http://nexus3:8081").rstrip("/")
N_ADMIN   = os.getenv("NEXUS_ADMIN_USER", "admin")
N_PASS    = os.getenv("NEXUS_ADMIN_PASS")
G_ORG     = os.getenv("GITHUB_ORG")
G_TOKEN   = os.getenv("GITHUB_TOKEN")
DEFAULT_ROLES = [r.strip() for r in os.getenv("DEFAULT_ROLES", "nx-browser").split(",") if r.strip()]
USERNAME_STRATEGY = os.getenv("USERNAME_STRATEGY", "github_login")
DISABLE_MISSING = os.getenv("DISABLE_MISSING", "false").lower() == "true"
DEFAULT_PASSWORD = os.getenv("DEFAULT_PASSWORD", "unused-temp")
EXCLUDE_USERS = {u.strip() for u in os.getenv("EXCLUDE_USERS", "admin").split(",") if u.strip()}
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

if not all([N_PASS, G_ORG, G_TOKEN]):
    print("ERROR: Missing required env: NEXUS_ADMIN_PASS, GITHUB_ORG, GITHUB_TOKEN", file=sys.stderr); sys.exit(2)

BASIC = "Basic " + base64.b64encode(f"{N_ADMIN}:{N_PASS}".encode()).decode()
GH_HEADERS = {"Authorization": f"Bearer {G_TOKEN}","Accept":"application/vnd.github+json",
              "X-GitHub-Api-Version":"2022-11-28","User-Agent":"nexus-user-sync"}

def http_json(url, method="GET", headers=None, data=None, expected=(200,201,204)):
    req = urllib.request.Request(url, method=method)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    body = json.dumps(data).encode() if data is not None else None
    if body: req.add_header("Content-Type","application/json")
    try:
        with urllib.request.urlopen(req, body, timeout=90) as r:
            code = r.getcode(); raw = r.read()
            out = json.loads(raw.decode()) if (raw and r.headers.get_content_type()=="application/json") else (raw.decode() if raw else None)
            if code not in expected: raise Exception(f"Unexpected {code} from {url} (expected {expected}): {out}")
            return out
    except urllib.error.HTTPError as e:
        text = e.read().decode()
        if e.code == 404: return None
        raise Exception(f"HTTPError {e.code} {url}: {text}")

def gh_paginate(url):
    items = []
    while url:
        req = urllib.request.Request(url, headers=GH_HEADERS)
        with urllib.request.urlopen(req, timeout=90) as r:
            items += json.loads(r.read().decode())
            link = r.headers.get("Link"); next_url = None
            if link:
                for part in [p.strip() for p in link.split(",")]:
                    if 'rel="next"' in part:
                        next_url = part[part.find("<")+1:part.find(">")]; break
            url = next_url
    return items

def gh_org_members(org): return gh_paginate(f"https://api.github.com/orgs/{urllib.parse.quote(org)}/members?per_page=100")
def gh_user(login): return http_json(f"https://api.github.com/users/{urllib.parse.quote(login)}", headers=GH_HEADERS)
def normalize_user_id(login, email):
    return login if USERNAME_STRATEGY in ("github_login","raw") else (email.split("@")[0] if email else login)

def nexus_roles(): return http_json(f"{NEXUS_URL}/service/rest/v1/security/roles", headers={"Authorization": BASIC}) or []
def nexus_users(): return http_json(f"{NEXUS_URL}/service/rest/beta/security/users", headers={"Authorization": BASIC}) or []
def nexus_user_create(user):
    if DRY_RUN: print(f"DRY-RUN create: {user['userId']} roles={user.get('roles')}"); return {}
    return http_json(f"{NEXUS_URL}/service/rest/beta/security/users", method="POST",
                     headers={"Authorization": BASIC}, data=user, expected=(200,201))
def nexus_user_update(uid, user):
    if DRY_RUN: print(f"DRY-RUN update: {uid} status={user.get('status')} roles={user.get('roles')}"); return {}
    return http_json(f"{NEXUS_URL}/service/rest/beta/security/users/{urllib.parse.quote(uid)}",
                     method="PUT", headers={"Authorization": BASIC}, data=user, expected=(200,204))

members = gh_org_members(G_ORG)
gh_map = {}
for m in members:
    login = m.get("login"); email=None; display=login
    try:
        profile = gh_user(login)
        if isinstance(profile, dict):
            email = profile.get("email"); display = profile.get("name") or login
    except Exception as e:
        print(f"WARN: profile fetch failed for {login}: {e}", file=sys.stderr)
    uid = normalize_user_id(login, email)
    full = (display or login).strip()
    first,last = (full.split(" ",1) if " " in full else (full,"user"))
    if not first: first = uid
    if not last: last = "user"
    if uid in EXCLUDE_USERS: print(f"INFO: Skipping excluded userId '{uid}'"); continue
    gh_map[uid] = {"first":first,"last":last,"email": email or f"{login}@example.invalid","display":display,"source_login":login}

print(f"INFO: GitHub members considered (after excludes): {len(gh_map)}")
existing = {u["userId"]: u for u in nexus_users() if isinstance(u, dict)}
for x in list(existing.keys()):
    if x in EXCLUDE_USERS: existing.pop(x)
print(f"INFO: Existing Nexus users (after excludes): {len(existing)}")

to_create = [uid for uid in gh_map if uid not in existing]
to_disable = [uid for uid in existing if uid not in gh_map] if DISABLE_MISSING else []
def get_users_to_disable(existing_users, gh_users, exclude_users):
    """
    Returns a list of user IDs that are in existing_users but not in gh_users, excluding any in exclude_users.
    """
    return [uid for uid in existing_users if uid not in gh_users and uid not in exclude_users]

to_disable = get_users_to_disable(existing, gh_map, EXCLUDE_USERS) if DISABLE_MISSING else []
role_ids = {r["id"] for r in nexus_roles() if isinstance(r, dict)}
for rid in DEFAULT_ROLES:
    if rid not in {"nx-browser","nx-admin","nx-anonymous"} and rid not in role_ids:
        print(f'WARN: role "{rid}" not found in Nexus; create it or adjust DEFAULT_ROLES', file=sys.stderr)

created=0
for uid in to_create:
    meta = gh_map[uid]
    payload = {"userId":uid,"firstName":meta["first"],"lastName":meta["last"],
               "emailAddress":meta["email"],"password":DEFAULT_PASSWORD,"status":"active","roles":DEFAULT_ROLES}
    try: nexus_user_create(payload); created+=1; print(f'INFO: Created user "{uid}" roles={DEFAULT_ROLES}')
    except Exception as e: print(f'ERROR: Create user "{uid}" failed: {e}', file=sys.stderr)

disabled=0
if DISABLE_MISSING:
    for uid in to_disable:
        u = existing[uid]
        if u.get("status")=="disabled": continue
        u["status"]="disabled"
        try: nexus_user_update(uid,u); disabled+=1; print(f'INFO: Disabled user "{uid}" (not in GitHub org)')
        except Exception as e: print(f'ERROR: Disable user "{uid}" failed: {e}', file=sys.stderr)

print(json.dumps({"github_org":G_ORG,"default_roles":DEFAULT_ROLES,"username_strategy":USERNAME_STRATEGY,
                  "exclude_users":sorted(list(EXCLUDE_USERS)),"disable_missing":DISABLE_MISSING,
                  "nexus_url":NEXUS_URL,"created":created,"disabled":disabled,"total_considered":len(gh_map)}, indent=2))