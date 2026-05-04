# CRS paranoia levels and anomaly scoring

## Scope

Guard Proxy maps each WAF `Policy` to the OWASP Core Rule Set controls rendered
in `crs-setup.conf`:

- `paranoia_level` -> `tx.blocking_paranoia_level` and
  `tx.detection_paranoia_level`
- `inbound_anomaly_threshold` -> `tx.inbound_anomaly_score_threshold`
- `outbound_anomaly_threshold` -> `tx.outbound_anomaly_score_threshold`
- `enforcement_mode` -> `SecRuleEngine On` or `SecRuleEngine DetectionOnly`

References:

- CRS anomaly scoring: https://coreruleset.org/docs/concepts/anomaly_scoring/
- CRS paranoia levels: https://coreruleset.org/docs/concepts/paranoia_levels/
- CRS paranoia level FAQ:
  https://coreruleset.org/faq/what-are-the-paranoia-levels

## Paranoia levels

PL1 is the baseline. It is designed for broad compatibility and should have the
lowest false-positive rate. Guard Proxy should use PL1 as the default policy
level for new vhosts.

PL2 enables additional CRS rules and is a reasonable next step for applications
handling customer data. It provides stronger coverage but needs application-
specific tuning before broad blocking rollout.

PL3 is aggressive. It detects more specialized attack patterns and is expected
to generate more false positives, especially on applications with complex query
syntax, rich text input, or API payloads.

PL4 is maximum CRS coverage. It is useful for high-risk workloads only after
careful tuning. Running PL4 in blocking mode without exclusions is likely to
block legitimate traffic.

## Anomaly thresholds

CRS anomaly mode adds scores from matching rules instead of relying only on a
single rule decision. Lower thresholds block faster; higher thresholds tolerate
more suspicious matches before a transaction is denied.

Recommended Guard Proxy starting points:

- Inbound threshold: `5`
- Outbound threshold: `4` or `5`

The existing M1 baseline used `5` for both inbound and outbound. The M2 policy
model stores the two values separately so outbound response inspection can be
tuned independently when response-body inspection is enabled later.

## Enforcement mode

`block` maps to `SecRuleEngine On`. Matching CRS rules can block according to
the anomaly score and disruptive action configuration.

`detect_only` maps to `SecRuleEngine DetectionOnly`. CRS still evaluates and
logs matches, but does not block. Use this during rollout, after increasing
paranoia level, or while tuning false positives for a new application.

## Rollout guidance

Start new applications at PL1, inbound threshold `5`, outbound threshold `5`,
and `detect_only` if traffic is unknown. Review WAF events, add targeted rule
overrides or exclusions for confirmed false positives, then switch to `block`.

Increase to PL2 only after PL1 is stable. Treat PL3 and PL4 as explicit
hardening choices that require monitoring and application-specific tuning.
