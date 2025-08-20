## docs/curl-examples.sh

#!/usr/bin/env bash

# Port-forward to Nexus service first:

# oc -n <YOUR_NAMESPACE> port-forward svc/nexus3 18081:8081

# Enable Anonymous (temporary)

```bash
curl -u 'admin:PASS' -H 'Content-Type: application/json' \
  -X PUT -d '{"enabled":true,"userId":"anonymous","realmName":"NexusAuthorizingRealm"}' \
  http://127.0.0.1:18081/service/rest/v1/security/anonymous
```

# Realms order (RUT first)

```bash
curl -u 'admin:PASS' -H 'Content-Type: application/json' -X PUT \
  -d '["rutauth-realm","NexusAuthenticatingRealm","DefaultRole"]' \
  http://127.0.0.1:18081/service/rest/v1/security/realms/active
```

# (UI) Create Capability → "Rut Auth", header "X-Forwarded-User"

# Optional: Base URL capability to your proxy host

# Disable Anonymous again

```bash
curl -u 'admin:PASS' -H 'Content-Type: application/json' \
  -X PUT -d '{"enabled":false,"userId":"anonymous","realmName":"NexusAuthorizingRealm"}' \
  http://127.0.0.1:18081/service/rest/v1/security/anonymous
```