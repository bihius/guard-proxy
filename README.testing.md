# Testing Strategy - Guard Proxy

## Test Pyramid

| Level | Location | Tools | Coverage Goal |
|-------|----------|-------|---------------|
| **Unit** (many, fast) | `src/*/tests/unit/` | pytest, Vitest | >80% |
| **Integration** (some) | `src/*/tests/integration/` | pytest, Docker | Key flows |
| **Security** | `tests/security/` | sqlmap, OWASP ZAP, custom payloads | OWASP Top 10 |
| **Performance** | `benchmarks/` | wrk, k6, Locust | <20% WAF overhead |

## WAF Testing

### Detection Targets
- SQL Injection: >95% detection rate
- XSS: >95% detection rate
- Path Traversal: >95% detection rate
- False positive rate: <10%

### Paranoia Levels
Start at PL1 (least restrictive), increase gradually. Document ALL rule exclusions with reason.

### False Positive/Negative Tracking
Document every case in `notes/testing/`. Include:
- Request that triggered it
- Rule ID that fired (or missed)
- Whether it's legitimate traffic
- Fix applied (exclusion rule or custom rule)

## Test Data

- Payloads: `benchmarks/payloads/` (sqli.txt, xss.txt, legitimate.txt)
- Fixtures: `tests/fixtures/` (policies, configs)
- Results: `benchmarks/results/` (timestamped JSON, gitignored)

## Commands

See [README.commands.md](README.commands.md) for all test commands.
