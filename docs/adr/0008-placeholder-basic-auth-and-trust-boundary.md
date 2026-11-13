# 0008: Use placeholder Basic auth behind a private network boundary

- Status: Accepted
- Date: 2026-11-13

## Context

The app runs on a private Raspberry Pi for one user. At home, clients reach it over the home
LAN. Away from home, they reach it through a Tailscale tailnet. It is not exposed to the public
internet. The app still needs a user identity because recipes, plans, and timings are scoped by
`user_pk` (ADR 0006).

A full authentication system would add password storage, hashing, a reset flow, sessions, CSRF
protection, and a login UI. That is more than a single-user, trusted-network deployment needs
now. The app keeps the smallest mechanism that gives each request a user identity and rejects
unknown users: HTTP Basic auth with a username lookup.

The password is ignored. This ADR records that limitation and the network boundary that makes
it acceptable, so the placeholder is not mistaken for real authentication.

## Decision

### Authentication

- Use FastAPI's `HTTPBasic` security scheme. `get_current_user` reads `credentials.username`,
  looks the user up with `UserRepository.get_by_name`, and ignores `credentials.password`.
- An unknown username returns 401 with `WWW-Authenticate: Basic` and the generic detail
  "Incorrect username or password".
- `CurrentUser` is the only source of identity. Every data route and page shell depends on it;
  handlers pass `user.pk` to the service for scoped queries.
- `CreateUserRequest` has only `user_name`; `UserResponse` exposes `pk` and `user_name`. No
  password or hash is stored or returned.
- Users are created through `POST /api/v1/users` or the `meals-seed` CLI. Tests and CLI helpers
  use `auth_headers()`, which sends a fixed dummy password (`test`); it is not a secret.
- `meals.auth` is an application-layer dependency because it uses the user repository and is
  consumed by both HTTP adapters (ADR 0003).

### Trust boundary

- The app depends on the home LAN and Tailscale tailnet to keep untrusted clients out. At home,
  clients reach the Pi over the LAN; away from home, they use Tailscale. The service binds
  `0.0.0.0:8000`, so both paths reach it. It is not port-forwarded to the public internet.
- Tailscale provides encrypted transport and tailnet access control. The app itself does not
  check the client's device, network, or Tailscale identity.
- Anyone who can reach the service can create a user, and anyone who knows an existing username
  can authenticate as that user. A password, if sent, is ignored. This is acceptable only while
  the app has one trusted user and every device inside the LAN and tailnet is trusted.
- Adding a second user or admitting an untrusted device makes the placeholder unsafe: every user
  can still impersonate every other user by username. The user-scoped data rules (ADR 0006)
  prevent accidental cross-user access, but they do not provide authentication security.
- `POST /api/v1/users` is unauthenticated because the first user must exist before anyone can
  authenticate. It is safe only inside the trusted network. `/health` is unauthenticated.
  FastAPI's `/docs`, `/redoc`, and `/openapi.json` are also unauthenticated; they expose the API
  shape, not data.
- Do not expose the app to the public internet. Real authentication is required before the
  boundary changes.

## Consequences

- There is no password storage, hashing, reset flow, session store, CSRF handling, or
  login/logout UI. The auth code stays small.
- A browser shows the HTTP Basic prompt and re-prompts after the browser session ends. There is
  no explicit logout.
- HTTP Basic sends the username and password on every request. Tailscale encrypts remote
  traffic; direct LAN traffic is plain HTTP. The password is ignored, so it carries no secret
  today. Real password authentication would need TLS, and a signed session would avoid
  resending the password.
- An attacker on the LAN or tailnet who knows a username can act as that user. There is no
  per-device authorization.
- The open user-creation route lets any client inside the boundary add users. User names are
  not secret.
- Moving to real authentication needs a password hash at creation, verification in
  `get_current_user`, a response model that never exposes the hash, and updated CLI and tests.
  A signed session cookie would also remove the repeated Basic prompt.

## Alternatives considered

- **No auth at all and rely on the network**: rejected because the data routes need a user
  identity for user scoping, and the page and API handlers already use `CurrentUser`. Removing
  it would require a fixed user or another identity source.
- **Full signup/login with hashed passwords now**: rejected as disproportionate for one trusted
  user; it adds password storage, reset, sessions, CSRF, and UI before the deployment needs them.
- **Hash passwords and keep Basic auth**: the smallest real-auth upgrade, but it adds password
  management and still prompts. Deferred until the trust boundary changes.
- **Signed session cookie now**: rejected for the same reason; it would improve convenience,
  not the trust boundary, while adding session and CSRF handling.
- **OAuth or OIDC**: rejected as too much infrastructure for one user on a private network.
- **A shared static password**: rejected because it is not per-user, still needs secret
  management, and would still be sent on every request. The current placeholder does not
  pretend to verify a password.
- **Rely only on Tailscale identity**: rejected because the service also listens on the LAN and
  the app needs a local user record for scoped data. Tailscale controls remote access but does
  not supply an application user here.
- **Expose the app publicly with Basic auth**: rejected because the password is ignored; any
  network client could use a known username. The private network is what limits access.
