# WAF Policy Tuning Guide

> How to adjust OWASP CRS behaviour with rule overrides, target exclusions, and custom rules.

Guard Proxy does not only deploy the OWASP Core Rule Set (CRS) out of the box — it also lets you **fine-tune** it. Every virtual host can be bound to a *policy*, and every policy can carry three kinds of tuning entries:

1. **Rule overrides** — turn an entire CRS rule on or off.
2. **Rule exclusions** — stop a CRS rule from inspecting one specific argument, header, or URI.
3. **Custom rules** — write your own security rules on top of CRS.

This guide explains what each entry does, what fields you must fill in, and what Guard Proxy writes into the generated Coraza configuration.

---

## Table of Contents

- [Quick glossary](#quick-glossary)
- [Rule overrides](#rule-overrides)
- [Rule exclusions](#rule-exclusions)
- [From log to exclusion — a worked example](#from-log-to-exclusion--a-worked-example)
- [Custom rules](#custom-rules)
- [API cheat-sheet](#api-cheat-sheet)
- [What the generated config looks like](#what-the-generated-config-looks-like)
- [Further reading](#further-reading)

---

## Quick glossary

| Term | Meaning |
|---|---|
| **CRS** | OWASP Core Rule Set — a large collection of ready-made WAF rules (SQL-injection detection, XSS detection, etc.). |
| **Rule** | A single numbered check inside CRS, e.g. `942100` looks for SQL-injection patterns. |
| **Target** | The specific *place* a rule inspects: a query argument, a request header, the request URI, etc. |
| **Phase** | The moment in the HTTP life-cycle when a rule runs. Guard Proxy currently supports custom rules in Phase 1 = request headers and Phase 2 = request body. |
| **Action** | What Coraza does when a rule matches, e.g. `deny`, `pass`, `log`, `skipAfter`. |
| **SecRule** | The ModSecurity/Coraza directive that defines a rule. |

---

## Rule overrides

### What it does
A rule override is the simplest form of tuning: you **completely enable or completely disable** a CRS rule for a given policy.

**When to use it**
- A CRS rule is constantly blocking legitimate traffic on your application and you have no time to investigate a narrower fix → *disable* it.
- You previously disabled a rule and now want it back → *enable* it.

**When *not* to use it**
- The rule only misbehaves on one endpoint or for one request argument. In that case use a **rule exclusion** (see below) so you do not lose protection everywhere else.

### Fields

| Field | Required | Description |
|---|---|---|
| `rule_id` | Yes | CRS rule number, e.g. `941100` (XSS), `942100` (SQLi). |
| `action` | Yes | `enable` or `disable`. |
| `comment` | No | A free-text note for your team, e.g. "Disabled because of false positives on the legacy search endpoint". |

### Example

Disable rule `942100` inside policy `3`:

```json
POST /policies/3/rules
{
  "rule_id": 942100,
  "action": "disable",
  "comment": "False positives on search form"
}
```

---

## Rule exclusions

### What it does
Instead of turning a whole rule off, you tell the WAF: *"Rule X should stop looking at this one specific thing"*. In ModSecurity/Coraza terminology this is called removing a **target** from a rule.

**When to use it**
- Rule `942100` (SQLi) fires on a harmless `token` parameter sent by your mobile app to `/api/login`.
- Rule `941100` (XSS) fires on a rich-text field `description` in your admin panel.
- A third-party webhook sends a header `X-Signature` that looks suspicious to CRS but is actually expected.

### Fields

| Field | Required | Description |
|---|---|---|
| `rule_id` | Yes | CRS rule number you want to narrow down, e.g. `942100`. |
| `target_type` | Yes | What kind of target you are excluding. See the table below. |
| `target_value` | Yes | The concrete name of the target, e.g. `"token"`, `"X-Signature"`. |
| `scope_path` | No | A URL path prefix (e.g. `/api/login`) where the exclusion is valid. If omitted the exclusion is **global** — it applies to every request handled by the policy. |
| `comment` | No | A note explaining why the exclusion exists. |

### Target types

| `target_type` value | What it means | Example `target_value` |
|---|---|---|
| `args` | A query-string or body parameter | `"token"`, `"search"` |
| `args_names` | The *name* of a parameter (rarely needed) | `"old_name"` |
| `request_headers` | A request header | `"X-Signature"`, `"User-Agent"` |
| `request_uri` | The full request URI | Leave empty / same as target type (excludes the whole URI from inspection for that rule) |

### Examples

**Global exclusion** — stop rule `942100` from checking the `token` argument on *every* endpoint:

```json
POST /policies/3/exclusions
{
  "rule_id": 942100,
  "target_type": "args",
  "target_value": "token",
  "comment": "Mobile app sends long opaque tokens"
}
```

**Path-scoped exclusion** — same as above, but only for `/api/login`:

```json
POST /policies/3/exclusions
{
  "rule_id": 942100,
  "target_type": "args",
  "target_value": "token",
  "scope_path": "/api/login",
  "comment": "Login endpoint only"
}
```

**Header exclusion** — stop rule `920274` from inspecting the `X-Custom-Header` header:

```json
POST /policies/3/exclusions
{
  "rule_id": 920274,
  "target_type": "request_headers",
  "target_value": "X-Custom-Header",
  "comment": "Third-party integration header"
}
```

---

## From log to exclusion — a worked example

The hardest part of tuning a WAF is knowing **whether** a blocked request deserves an exclusion. Below are two step-by-step examples that show how to read a log and make the right decision.

---

### Example 1 — a rich-text field triggers XSS detection (create an exclusion)

Your team reports: *"When our editors save blog posts that contain HTML, the WAF blocks them with 403."*

You look at the log and see:

| Field | Value |
|---|---|
| Method | `POST` |
| Request URI | `/admin/posts` |
| Rule ID | `941100` |
| Rule message | `XSS Attack Detected via libinjection` |

**Step 1 — What does the rule do?**  
Rule `941100` detects cross-site scripting (XSS) patterns. It inspects request arguments and the request body.

**Step 2 — Is this a false positive?**  
Yes. An admin panel that intentionally accepts HTML from trusted editors is expected to contain `<script>`-like strings. The rule is doing its job, but the *context* (a trusted admin saving a post) makes it a false positive.

**Step 3 — What exactly should be excluded?**  
The rule fired on the `content` argument inside the POST body. You do not want to disable the whole rule — you only want to stop it from checking the `content` field on the admin endpoint.

**Step 4 — Build the exclusion**

| Exclusion field | Value | Reason |
|---|---|---|
| `rule_id` | `941100` | The rule that fired. |
| `target_type` | `args` | The rule inspected a request argument. |
| `target_value` | `"content"` | The argument name that contained the HTML. |
| `scope_path` | `/admin/posts` | Only the post-editing endpoint needs this. |
| `comment` | `Editors intentionally save HTML in posts` | So the next admin knows why this exists. |

**JSON to send:**

```json
POST /policies/3/exclusions
{
  "rule_id": 941100,
  "target_type": "args",
  "target_value": "content",
  "scope_path": "/admin/posts",
  "comment": "Editors intentionally save HTML in posts"
}
```

Then run `POST /config/apply` to regenerate the configuration.

---

### Example 2 — a mobile login token triggers SQLi detection (create an exclusion)

Your mobile app users cannot log in. The logs show:

| Field | Value |
|---|---|
| Method | `POST` |
| Request URI | `/api/login` |
| Rule ID | `942100` |
| Rule message | `SQL Injection Attack Detected via libinjection` |

The `token` parameter contains a long opaque JWT string that happens to contain a character sequence the SQLi rule treats as suspicious.

**Step 1 — What does the rule do?**  
Rule `942100` detects SQL-injection patterns in request arguments.

**Step 2 — Is this a false positive?**  
Yes. The `token` field is generated by your own authentication service. It is not user-supplied SQL.

**Step 3 — What exactly should be excluded?**  
The `token` argument on the login endpoint only.

**Step 4 — Build the exclusion**

| Exclusion field | Value | Reason |
|---|---|---|
| `rule_id` | `942100` | The rule that fired. |
| `target_type` | `args` | The rule inspected a request argument. |
| `target_value` | `"token"` | The argument name that triggered the rule. |
| `scope_path` | `/api/login` | Only the login endpoint needs this. |
| `comment` | `Mobile app JWT token contains SQL-like sequences` | Explains the business context. |

**JSON to send:**

```json
POST /policies/3/exclusions
{
  "rule_id": 942100,
  "target_type": "args",
  "target_value": "token",
  "scope_path": "/api/login",
  "comment": "Mobile app JWT token contains SQL-like sequences"
}
```

---

### Example 3 — a scanner probing sensitive files (do NOT create an exclusion)

You see a block in your logs:

| Field | Value |
|---|---|
| Method | `GET` |
| Request URI | `/.env` |
| Rule ID | `930130` |
| Rule message | `Restricted File Access Attempt` |

**Step 1 — What does the rule do?**  
Rule `930130` is part of the CRS file-access group. It blocks requests for sensitive files such as `.env`, `.git`, `.htaccess`, and backup files.

**Step 2 — Is this a false positive?**  
Ask yourself: *"Should a legitimate user ever request `/.env`?"*  
The answer is **no**. `.env` contains secrets (database passwords, API keys). A request for it is almost always a malicious scanner or bot.

**Step 3 — Decision**  
Do **nothing**. The WAF worked exactly as intended. Creating an exclusion here would open a security hole.

> **Golden rule:** If the blocked request looks like an attack, do not tune the rule — let it block.

---

### Quick checklist for every log

1. **Find the Rule ID** and read its message. What is the rule trying to protect against?
2. **Look at the Request URI, Method, and any arguments/headers.** Is this a normal, legitimate use of your application?
3. **If it is an attack** → do nothing. Let the rule block.
4. **If it is a false positive** → identify the **smallest possible target** (one argument, one header) and create a **rule exclusion** scoped to the specific path.
5. **Only as a last resort** — if the rule is completely incompatible with your application and you cannot narrow it down — use a **rule override** to disable the entire rule.

---

## Custom rules

### What it does
Custom rules let you **write your own security checks** that do not exist in CRS. They are standard Coraza `SecRule` directives created through the admin panel instead of being hand-edited into a `.conf` file.

**When to use it**
- Block requests from a specific bot user-agent that CRS does not catch.
- Reject requests that do not carry a mandatory internal header.
- Add geo-IP or time-based restrictions tailored to your organisation.

### Fields

| Field | Required | Description |
|---|---|---|
| `rule_id` | Yes | A number **you choose** between `9000000` and `9099999`. This range is reserved for administrator-authored rules so it never collides with CRS rule IDs. |
| `phase` | Yes | When the rule runs. Allowed values: `request_headers`, `request_body`. Response and logging phases are not available because Guard Proxy's current SPOA integration inspects requests only. |
| `variables` | Yes | What Coraza should inspect, e.g. `REQUEST_HEADERS:User-Agent`, `ARGS`, `ARGS\|REQUEST_BODY`. |
| `operator` | Yes | How to compare the variable against your pattern. See the operator table below. |
| `operator_argument` | Yes | The pattern or value for the operator, e.g. a regex or a literal string. |
| `actions` | Yes | Comma-separated Coraza actions, e.g. `deny,status:403,log` or `pass,skipAfter:END`. |
| `comment` | No | A human-readable note. |
| `is_active` | No (default `true`) | Inactive rules are kept in the database but are **not** written into the generated config. |

### Operators

| `operator` value | Coraza token | Meaning | Typical `operator_argument` |
|---|---|---|---|
| `rx` | `@rx` | Regular expression match | `(?i)badbot` |
| `streq` | `@streq` | Exact string match | `admin` |
| `contains` | `@contains` | Substring match | `internal` |
| `begins_with` | `@beginsWith` | Starts with | `/api/v1` |
| `ends_with` | `@endsWith` | Ends with | `.pdf` |
| `eq` | `@eq` | Numeric equal | `0` |
| `ge` | `@ge` | Greater than or equal | `18` |
| `gt` | `@gt` | Greater than | `100` |
| `le` | `@le` | Less than or equal | `5` |
| `lt` | `@lt` | Less than | `10` |
| `pm` | `@pm` | Phrase match (space-separated list) | `select drop delete` |
| `within` | `@within` | Value must be in a list | `GET POST HEAD` |
| `ip_match` | `@ipMatch` | IP or CIDR match | `192.168.1.0/24 10.0.0.5` |

### Phase mapping

| `phase` value | Coraza phase number | When it runs |
|---|---|---|
| `request_headers` | 1 | After the request headers are received |
| `request_body` | 2 | After the request body is received |

Coraza itself also has response and logging phases, but Guard Proxy does not run
them today. HAProxy sends request metadata and body data to Coraza through SPOE,
and the Coraza SPOA application is configured with `response_check: false`.
If you need response inspection later, the proxy/SPOA data flow must be extended
first; adding a phase 3, 4, or 5 custom rule in the current stack would not
execute as an operator expects.

### Examples

**Block every request whose User-Agent contains `curl`:**

```json
POST /policies/3/custom-rules
{
  "rule_id": 9000001,
  "phase": "request_headers",
  "variables": "REQUEST_HEADERS:User-Agent",
  "operator": "rx",
  "operator_argument": "(?i)curl",
  "actions": "deny,status:403,log",
  "comment": "No curl-based scraping"
}
```

**Require an internal header `X-Internal-Auth` on admin paths:**

```json
POST /policies/3/custom-rules
{
  "rule_id": 9000002,
  "phase": "request_headers",
  "variables": "REQUEST_HEADERS:X-Internal-Auth",
  "operator": "rx",
  "operator_argument": "^$",
  "actions": "deny,status:403,msg:'Missing internal auth header'",
  "comment": "All admin requests must carry the internal auth header"
}
```

**Allow only specific HTTP methods:**

```json
POST /policies/3/custom-rules
{
  "rule_id": 9000003,
  "phase": "request_headers",
  "variables": "REQUEST_METHOD",
  "operator": "within",
  "operator_argument": "GET POST HEAD OPTIONS",
  "actions": "deny,status:405,log",
  "comment": "Reject unexpected HTTP verbs"
}
```

---

## API cheat-sheet

All endpoints below require an `Authorization: Bearer <token>` header. `POST`, `PATCH`, and `DELETE` are restricted to admin users.

| Action | Endpoint | Method |
|---|---|---|
| **Rule overrides** | | |
| Create | `/policies/{id}/rules` | `POST` |
| List | `/policies/{id}/rules` | `GET` |
| Get one | `/policies/{id}/rules/{rule_override_id}` | `GET` |
| Update | `/policies/{id}/rules/{rule_override_id}` | `PATCH` |
| Delete | `/policies/{id}/rules/{rule_override_id}` | `DELETE` |
| **Rule exclusions** | | |
| Create | `/policies/{id}/exclusions` | `POST` |
| List | `/policies/{id}/exclusions` | `GET` |
| Get one | `/policies/{id}/exclusions/{rule_exclusion_id}` | `GET` |
| Update | `/policies/{id}/exclusions/{rule_exclusion_id}` | `PATCH` |
| Delete | `/policies/{id}/exclusions/{rule_exclusion_id}` | `DELETE` |
| **Custom rules** | | |
| Create | `/policies/{id}/custom-rules` | `POST` |
| List | `/policies/{id}/custom-rules` | `GET` |
| Get one | `/policies/{id}/custom-rules/{custom_rule_id}` | `GET` |
| Update | `/policies/{id}/custom-rules/{custom_rule_id}` | `PATCH` |
| Delete | `/policies/{id}/custom-rules/{custom_rule_id}` | `DELETE` |
| **Deploy config** | | |
| Generate & apply | `/config/apply` | `POST` |

After you create, update, or delete any tuning entry you must call `POST /config/apply` to regenerate the WAF configuration and reload HAProxy + Coraza.

---

## What the generated config looks like

Guard Proxy renders three files when you hit `POST /config/apply`. The tuning entries end up in `rule_overrides.conf`.

### Rule overrides

If you disabled rule `942100`:

```apache
SecRuleRemoveById 942100
```

### Rule exclusions

A **global** exclusion (no `scope_path`) is emitted as:

```apache
SecRuleRemoveTargetById 942100 ARGS:token
```

A **path-scoped** exclusion (e.g. `/api/login`) becomes a small control rule:

```apache
SecRule REQUEST_URI "@beginsWith /api/login" \
  "id:9990001,phase:1,pass,nolog,\
   ctl:ruleRemoveTargetById=942100;ARGS:token"
```

The control rule matches the request URI and then tells Coraza to remove the target for that single request only.

### Custom rules

A custom rule is emitted exactly as a `SecRule` directive:

```apache
SecRule REQUEST_HEADERS:User-Agent "@rx (?i)curl" \
  "id:9000001,phase:1,deny,status:403,log"
```

Inactive rules (`is_active: false`) are skipped entirely — they do not appear in the generated file.

---

## Further reading

- [OWASP CRS Documentation](https://coreruleset.org/docs/) — how the rule set works, paranoia levels, anomaly scoring, and rule numbering.
- [Coraza Reference](https://coraza.io/docs/seclang/) — SecRule syntax, variables, operators, actions, and phases.
- [ModSecurity Handbook](https://www.feistyduck.com/books/modsecurity-handbook/) (book) — deep dive into the engine that Coraza is compatible with.
- Guard Proxy [README.architecture.md](README.architecture.md) — how the generated config reaches HAProxy and Coraza.
