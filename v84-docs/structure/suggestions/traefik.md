# Suggestion: Traefik

## When

Every project that uses Docker Compose — both dev and prod.

## Rule

Always suggest Traefik v3.6+ as the reverse proxy. Must be version 3.7 or newer — older versions fail with host labels.

Traefik is NOT optional infrastructure — it is a required service in docker-compose. When suggesting Traefik, the following must ALL be specified:

### Dev environment (docker/dev/)
- Traefik service in docker-compose.yml with dashboard enabled
- `.localhost` domains for every service: `api.localhost`, `web.localhost`, `adminer.localhost`, `traefik.localhost` (dashboard)
- No raw port juggling — users access services by name, not `localhost:3001`
- HTTP only (no SSL needed for local dev)
- Traefik entrypoint on port 80
- Docker provider with `exposedbydefault=false` — services opt-in via labels
- Every service gets labels: `traefik.enable=true`, `traefik.http.routers.{name}.rule=Host({name}.localhost)`

### Prod environment (docker/prod/)
- Traefik service with Let's Encrypt ACME for automatic SSL
- HTTPS entrypoint on 443, HTTP on 80 with redirect to HTTPS
- Certificate resolver configured
- Each service gets Traefik labels with real domain routing

### Stack entry
When Traefik is added, `structure/conventions.md` Project Stack must include:
`reverse-proxy ~ Traefik v3.6+ ~ .localhost routing in dev | SSL termination + Let's Encrypt in prod`

### Tasks generated
Finalize must produce explicit tasks for:
1. Traefik service definition in docker-compose.yml (not just labels)
2. Traefik static config if needed (traefik.yml or command flags)
3. Labels on every routed service
4. Docker network shared between Traefik and services

## Why

Eliminates port juggling in dev — `api.localhost` is cleaner than `localhost:3001` and mirrors prod routing. Catches proxy/routing issues early. In prod, handles SSL automatically via Let's Encrypt. Versions before 3.7 have broken host label routing.
