# Security Checklist — <Target> — <date>

> Adapted from the `release-testing` skill. **Procedure:** skill `qa-security` (how to pick, run, and record each slice).
> Run one category per **exploratory or regression run** (rotate); confirm a finding with evidence
> Note dev-only caveats (e.g. on http://localhost some headers like HSTS/Secure-cookie are expected absent).

## Headers (curl -I on main page + an API route)
- [ ] Strict-Transport-Security (HSTS)  *(n/a on plain http localhost)*
- [ ] Content-Security-Policy
- [ ] X-Frame-Options or CSP frame-ancestors
- [ ] X-Content-Type-Options: nosniff
- [ ] Referrer-Policy
- [ ] Permissions-Policy
- [ ] X-Powered-By absent / not revealing version

## Authentication
- [ ] Wrong password → generic error (not 200, not 500)
- [ ] Unknown user → same response as wrong password (no user enumeration)
- [ ] Session cookie flags: HttpOnly, SameSite (Secure expected only over https)
- [ ] All protected routes redirect/деny unauthenticated requests

## Authorization / RBAC / IDOR
- [ ] Low-privilege user cannot reach admin/manager routes directly (list routes in `project-memory.md`)
- [ ] **IDOR**: user A cannot access user B's resource by ID (or only per documented policy)
- [ ] Mutation endpoints reject the wrong role
- [ ] API/server actions reject unauthenticated calls

## Brute force / rate limiting
- [ ] N rapid bad logins trigger throttling/429 (or documented absence)
- [ ] Valid login still works after bad attempts (no good-user lockout)

## Input validation
- [ ] XSS payload in a text field (e.g. request objective) is escaped on display, not executed
- [ ] SQL/ORM injection payload does not break queries or leak data
- [ ] Oversized payload returns 4xx, not 500
- [ ] Empty / malformed JSON handled gracefully

## Data exposure
- [ ] Error responses don't expose stack traces / file paths / DB internals
- [ ] No secrets/PII in client bundle or API responses beyond need
- [ ] Debug/secret paths 404: `/.env`, `/.git/config`, `/api/debug`

## Findings
> File confirmed issues to Jira under the epic (severity per qa-team scale). Note dev-only caveats.
