# FlaskProxy

Small Flask-based proxy for forwarding requests to predefined external API endpoints.

## Request Format

- Authentication header: `PRX-AUTH: <jwt>`
- Proxy path format: `/{host_id}/{path}`

Example:

```text
/openai/v1/chat/completions
```

The target host is selected from `TARGET_HOSTS` in the environment. Clients can no longer choose arbitrary destination URLs.

## Environment Variables

- `SIGN_KEY`: required shared secret for JWT validation
- `TARGET_HOSTS`: required comma-separated `id:hostname` or `id:https://hostname` entries
- `IP_ALLOWED`: optional comma-separated source IPs or CIDR ranges
- `REQUEST_TIMEOUT`: optional outbound timeout in seconds
- `ALLOW_PRIVATE_TARGETS`: optional, defaults to `false`

Example:

```text
SIGN_KEY=replace_me
TARGET_HOSTS=openai:api.openai.com,example:https://service.example.com
IP_ALLOWED=203.0.113.10,198.51.100.0/24
REQUEST_TIMEOUT=20
ALLOW_PRIVATE_TARGETS=false
```

## Security Notes

- `PRX-AUTH` is validated locally and removed before the request is sent to the target.
- Clients cannot set the destination host directly anymore, which reduces SSRF risk.
- By default, private and loopback target addresses are blocked. Only set `ALLOW_PRIVATE_TARGETS=true` if you fully trust callers.
- If `IP_ALLOWED` is set, only those source IPs or CIDR ranges can call the proxy.
- Run this service behind HTTPS only.
- `SIGN_KEY` must be long, random, and stored outside source control.
- Use short JWT expirations.

## Leak Prevention

The proxy strips headers that often reveal the caller or proxy chain:

- `PRX-AUTH`
- `Forwarded`
- `X-Forwarded-*`
- `X-Real-IP`
- `Via`
- CDN-specific client IP headers

It also avoids forwarding Flask cookie parsing state as a Requests cookie jar, which could otherwise leak unrelated cookies or alter target behavior.

## Behavior Safeguards

- Only `http` and `https` targets are accepted.
- URLs with embedded credentials are rejected.
- Request query parameters are forwarded without collapsing duplicate keys.
- Hop-by-hop headers are removed from both request and response handling.
- Outbound requests use a timeout controlled by `REQUEST_TIMEOUT` to avoid hanging workers indefinitely.
- Debug mode is forced off in the application entrypoint.

## Remaining Risks

- This proxy is still generic at the path level. If you need stronger control, bind each JWT to an allowed path prefix or method and enforce that in code.
- If you run behind a reverse proxy, make sure `request.remote_addr` reflects the real client IP before relying on `IP_ALLOWED`.
- Browser cookie flows, redirects, and CORS-sensitive applications may still need a target-specific reverse proxy design.
