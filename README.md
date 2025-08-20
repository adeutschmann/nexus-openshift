# Nexus on OpenShift with GitHub SSO, RUT, and Maven/CLI Access

This repository provides a ready‑to‑apply overlay for running **Nexus Repository 3** on **OpenShift** with:

- **GitHub SSO** for the **UI** via the OpenShift **oauth‑proxy**
- **RUT (Remote User Token)** in Nexus (trusts `X‑Forwarded‑User`)
- A **direct Route** for CLI tools (Maven, npm, Docker) that **bypasses OAuth**
- An optional **CronJob** that auto‑creates **Nexus local users** from a **GitHub org**
- Docs and examples for **Maven deploy/resolve** and **role/privilege** setup

> **TL;DR:** **Humans** use the SSO‑protected UI Route; **automation** uses the direct repo Route.

---

## Contents

- [What’s in here](#whats-in-here)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick start (Step‑by‑step)](#quick-start-step-by-step)
  - [1) Generate cookie secret](#1-generate-cookie-secret)
  - [2) Apply manifests](#2-apply-manifests)
  - [3) Enable RUT in Nexus (UI)](#3-enable-rut-in-nexus-ui)
  - [4) (Optional) Auto‑create users from GitHub](#4-optional-auto-create-users-from-github)
  - [5) Maven deploy & resolve](#5-maven-deploy--resolve)
- [Roles & privileges for uploads](#roles--privileges-for-uploads)
- [Common pitfalls & fixes](#common-pitfalls--fixes)
- [Security notes](#security-notes)
- [Uninstall / Cleanup](#uninstall--cleanup)
- [FAQ](#faq)

---

## What’s in here

**Kubernetes/OpenShift manifests**

- [`k8s/00-namespace.yaml`](k8s/00-namespace.yaml) — Namespace
- [`k8s/10-oauth-proxy.yaml`](k8s/10-oauth-proxy.yaml) — SA, Secret, Deployment, Service, Route for **oauth‑proxy** in front of Nexus UI  
- [`k8s/20-route-repo-direct.yaml`](k8s/20-route-repo-direct.yaml) — **Direct Route** to Nexus service for CLI (no OAuth)  
- [`k8s/30-secrets.yaml`](k8s/30-secrets.yaml) — Secrets for Nexus admin API and GitHub PAT  
- [`k8s/40-configmap-user-sync.yaml`](k8s/40-configmap-user-sync.yaml) — ConfigMap embedding the user‑sync script  
- [`k8s/50-cronjob-user-sync.yaml`](k8s/50-cronjob-user-sync.yaml) — CronJob to sync GitHub org members → Nexus users

**Scripts**

- [`scripts/sync.py`](scripts/sync.py) — Python script that:
  - Lists members of a GitHub org (PAT with `read:org`)
  - Creates **local** Nexus users with baseline roles
  - Optionally disables users who left the org
  - Skips break‑glass accounts (`EXCLUDE_USERS`)

**Docs**

- [`docs/maven-examples.md`](docs/maven-examples.md) — Maven deploy/resolve (POM and CLI)  
- [`docs/roles-cheatsheet.md`](docs/roles-cheatsheet.md) — Minimal privileges for uploads, plus role creation via REST  
- [`docs/curl-examples.sh`](docs/curl-examples.md) — Handy API snippets (anonymous on/off, realms order)

---

## Architecture

```text
Browser (GitHub SSO) --> OpenShift OAuth --> oauth-proxy --> Nexus UI
                                             (adds X-Forwarded-User)

Maven/npm/docker CLI -----------------------> Direct Route --> Nexus Repos
                                            (basic auth with Nexus user)
```

- **UI (human)**: protected by OAuth proxy → Nexus trusts `X‑Forwarded‑User` via **RUT capability**  
- **CLI (automation)**: talks to **direct Route**, authenticates with **Nexus local users**

---

## Prerequisites

- OpenShift cluster with GitHub configured as an **IdP** (OpenShift OAuth)  
- Running **Nexus Repository 3** service (commonly `svc/nexus3:8081`) in your namespace  
- `oc` CLI access to the target namespace  
- For GitHub sync: a **Personal Access Token (PAT)** with `read:org` scope

---

## Quick start (Step‑by‑step)

> **Replace placeholders** in the manifests before applying (namespace, hosts, admin password, GitHub org).

### 1) Generate cookie secret

```bash
head -c 32 /dev/urandom | base64
# Put this base64 value into k8s/10-oauth-proxy.yaml → Secret.data.COOKIE_SECRET
```

### 2) Apply manifests

```bash
# UI SSO via oauth-proxy
oc apply -f k8s/10-oauth-proxy.yaml

# Direct repo Route for CLI (no OAuth redirects)
oc apply -f k8s/20-route-repo-direct.yaml

# Admin + GitHub PAT secrets (update placeholders first)
oc apply -f k8s/30-secrets.yaml

# (Optional) GitHub → Nexus user sync
oc apply -f k8s/40-configmap-user-sync.yaml
oc apply -f k8s/50-cronjob-user-sync.yaml
```

### 3) Enable RUT in Nexus (UI)

1. Open the **UI SSO Route** host from [`k8s/10-oauth-proxy.yaml`](k8s/10-oauth-proxy.yaml)  
2. Log in via GitHub/OpenShift  
3. In Nexus: **Administration → System → Capabilities → Create**  
   - Type: **Rut Auth**  
   - **HTTP Header Name**: `X-Forwarded-User`  
4. **Administration → Security → Realms → Active** — ensure order:
   ```text
   Rut Auth Realm
   Local Authenticating Realm
   Default Role Realm (optional)
   ```
5. (Optional) **System → Capabilities → Create → Base URL** → set to your UI Route host

> Without RUT, Nexus treats you as **anonymous** even after SSO.

### 4) (Optional) Auto‑create users from GitHub

- Edit [`k8s/30-secrets.yaml`](k8s/30-secrets.yaml):
  - `nexus-admin` → your actual Nexus admin password  
  - `gh-org-sync` → GitHub **PAT** (`read:org`)
- Edit [`k8s/50-cronjob-user-sync.yaml`](k8s/50-cronjob-user-sync.yaml) env:
  - `GITHUB_ORG` → your org name  
  - `DEFAULT_ROLES` → baseline role(s) (e.g., `nx-browser` or a custom role)  
  - `EXCLUDE_USERS` → `admin,ops-admin` (break‑glass accounts)
- Apply again:

```bash
oc apply -f k8s/30-secrets.yaml
oc apply -f k8s/50-cronjob-user-sync.yaml
```

- Run once and watch logs:

```bash
oc create job --from=cronjob/nexus-user-sync nexus-user-sync-manual-$(date +%s)
oc logs -l job-name=$(oc get jobs -o jsonpath='{.items[-1:].0.metadata.name}') -f
```

> Nexus OSS **does not** auto‑provision users on first SSO login; this job creates them with a baseline role.

### 5) Maven deploy & resolve

**Rule of thumb:** **Deploy** only to **hosted** repos (`maven-releases` / `maven-snapshots`).  
Keep **resolve** via group (`maven-public`) if you like.

- Use the **direct Route** host from [`k8s/20-route-repo-direct.yaml`](k8s/20-route-repo-direct.yaml) for Maven/CLI.  
- Keep credentials in `~/.m2/settings.xml` `<servers>`.  
- Use POM `<distributionManagement>` **or** the CLI `alt…DeploymentRepository` properties.  

See: [`docs/maven-examples.md`](docs/maven-examples.md)

---

## Roles & privileges for uploads

To upload to a hosted Maven repo, a user needs **at least**:

- `nx-repository-view-maven2-<repo>-add`  
- `nx-repository-view-maven2-<repo>-edit`  
- `nx-repository-view-maven2-<repo>-read`

Create a deployer role and assign it as needed. Examples:  
[`docs/roles-cheatsheet.md`](docs/roles-cheatsheet.md)

---

## Common pitfalls & fixes

- **405 PUT to `/repository/maven-public/`** → You tried to deploy to a **group**. Deploy to **hosted** `maven-releases` or `maven-snapshots`.  
- **OAuth redirect in Maven logs** → You used the **SSO UI Route** host. Use the **direct repo Route** host.  
- **401/403 on deploy** → Wrong credentials or missing `add`/`edit` privileges on the target hosted repo.  
- **Still seeing “Login” in UI** → RUT capability missing/incorrect header name (`X‑Forwarded‑User`) or Realms order wrong.

---

## Security notes

- Keep a second **break‑glass** admin (e.g., `ops-admin`) and exclude it from sync (`EXCLUDE_USERS`).  
- Encrypt passwords in `~/.m2/settings.xml` with `mvn --encrypt-password`.  
- Consider restricting the **direct repo Route** initially (router IP whitelist annotation).

---

## Uninstall / Cleanup

```bash
oc delete -f k8s/50-cronjob-user-sync.yaml
oc delete -f k8s/40-configmap-user-sync.yaml
oc delete -f k8s/30-secrets.yaml
oc delete -f k8s/20-route-repo-direct.yaml
oc delete -f k8s/10-oauth-proxy.yaml
```

> *(This does **not** remove your Nexus instance.)*

---

## FAQ

**Q: Can CLI (Maven/npm/Docker) use the SSO Route?**  
A: No. CLI tools don’t follow the browser OAuth flow. Use the **direct Route** with Nexus credentials.

**Q: Can Nexus OSS auto‑create users on first SSO login?**  
A: No. That’s why this repo includes a **sync job** from your GitHub org.

**Q: Which header does Nexus read for SSO?**  
A: The **RUT capability** must point to `X‑Forwarded‑User`. The oauth‑proxy sets it when `--pass-user-headers=true` is enabled.
