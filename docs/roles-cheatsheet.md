# Roles Cheatsheet

---

## docs/roles-cheatsheet.md

# Roles / privileges cheat sheet

To **upload** to a hosted Maven repo:

- `nx-repository-view-maven2-<repo>-add`
- `nx-repository-view-maven2-<repo>-edit`
- `nx-repository-view-maven2-<repo>-read`

Create a deployer role via REST:

```bash
curl -u 'admin:PASS' -H 'Content-Type: application/json' \
  -X POST http://127.0.0.1:18081/service/rest/v1/security/roles \
  -d '{
    "id":"maven-deployer",
    "name":"Maven Deployer",
    "description":"Can deploy to releases & snapshots",
    "privileges":[
      "nx-repository-view-maven2-maven-releases-add",
      "nx-repository-view-maven2-maven-releases-edit",
      "nx-repository-view-maven2-maven-releases-read",
      "nx-repository-view-maven2-maven-snapshots-add",
      "nx-repository-view-maven2-maven-snapshots-edit",
      "nx-repository-view-maven2-maven-snapshots-read"
    ],
    "roles":[]
  }'
```

```bash
curl -s -u 'admin:PASS' http://127.0.0.1:18081/service/rest/beta/security/users/USER \
| jq '.roles += ["maven-deployer"]' \
| curl -u 'admin:PASS' -H 'Content-Type: application/json' -X PUT \
  -d @- http://127.0.0.1:18081/service/rest/beta/security/users/USER
```