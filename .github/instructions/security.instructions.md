---
applyTo: "**"
---

# Security Review Instructions

Guard Proxy *is* a security product (WAF + reverse proxy + admin panel). Hold its own code to a high bar. Treat every PR as if an attacker will read the diff.

## Always check for

1. **Secrets in the diff.**
   - No passwords, API tokens, JWT secrets, DB URLs with credentials, private keys, or `.env` files.
   - No `.env`, `*.pem`, `*.key`, `id_rsa*`, `credentials.json`, or similar files added to the repo.
   - Test fixtures must use obviously-fake values (`"test-secret"`, `"changeme"`) and never reuse real credentials.
2. **Authentication & authorization.**
   - Any new backend route: is there an auth dependency? Does the intended role (admin vs. user) match the check?
   - Object-level access: when fetching by ID, does the handler verify the current user is allowed to see/modify that object (no IDOR)?
   - Token handling: never log tokens, never store them in `localStorage` without a stated reason, never put them in URLs.
3. **Input validation.**
   - All request bodies/params go through Pydantic schemas with constrained types (`EmailStr`, `conint(ge=...)`, `constr(max_length=...)`, `HttpUrl`, `Literal[...]`).
   - User-controlled strings must never be concatenated into:
     - SQL (use SQLAlchemy parameters / ORM, never `text(f"...")` with interpolation),
     - shell commands (`subprocess` with `shell=True` + interpolation is a hard no),
     - file paths (reject `..`, absolute paths where only relative expected),
     - HAProxy / Coraza config snippets (escape/validate hostnames, regex patterns, headers),
     - HTML rendered on the frontend (`dangerouslySetInnerHTML` needs a very good reason).
4. **SSRF & outbound requests.** If the backend fetches a URL the user provided, there must be validation: scheme allowlist, no internal IP ranges (`127.0.0.0/8`, `10.0.0.0/8`, `169.254.0.0/16`, `::1`, etc.), and a timeout.
5. **CORS & cookies.**
   - CORS origins must not be `*` combined with credentials.
   - Auth cookies (if any): `HttpOnly`, `Secure`, `SameSite=Lax` or `Strict`.
6. **Rate limiting / brute force.** Login, password reset, and token endpoints should be rate-limited. Flag new sensitive endpoints that aren't.
7. **Crypto.**
   - Passwords: bcrypt / argon2 via a maintained library. Never MD5/SHA1 for passwords.
   - Random for tokens/IDs: `secrets.token_urlsafe(...)` on the backend, not `random`.
   - Don't roll custom crypto.
8. **Dependencies.**
   - New dependencies should be pinned via `uv` / `pnpm` lockfiles and should not be abandoned packages. Flag suspicious new packages.
   - No `curl | sh` or unpinned installs in CI/Dockerfiles.
9. **Docker / infrastructure.**
   - Containers should not run as root where avoidable.
   - Secrets come from environment / secret store, not baked into images.
   - Exposed ports should be minimal and documented.
10. **Logging.** Never log: passwords, tokens, full `Authorization` headers, session IDs, full request/response bodies that may contain PII. Redact before logging.

## HAProxy / Coraza specific

- Generated `haproxy.cfg` must be validated with `haproxy -c -f ...` before deploy.
- Coraza rule changes: ensure paranoia level and anomaly thresholds are not silently lowered.
- SPOE configuration changes: verify timeouts are set; an unbounded SPOE call is a DoS risk.

## How to phrase security findings

- Start with the severity: **Critical / High / Medium / Low**.
- State the concrete attack or failure mode in one sentence.
- Suggest the concrete fix (code or config).
- Do **not** describe weaponized payloads beyond what is necessary to demonstrate the issue.
