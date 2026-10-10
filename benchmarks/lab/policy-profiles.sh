# policy-profiles.sh — Lab policy naming and PL1/PL2 settings profiles.
#
# Sourced by setup-lab.sh, set-policy.sh and runners/lib.sh, which must define
# env_value() first.
#
# Every lab vhost has its own WAF policy, named after its domain. A profile
# (pl1 or pl2) is the set of settings set-policy.sh writes into those
# per-vhost policies.
#
# The two profiles differ only in the paranoia level, so a PL1 vs PL2
# difference in the results can be attributed to the paranoia level alone.
# Both use inbound threshold 5, outbound threshold 4 (CRS defaults), block
# mode, no rate limiting and no GeoIP filtering. The values are fixed here on
# purpose; they are not read from benchmarks/lab/.env.

PROFILE_INBOUND_THRESHOLD=5
PROFILE_OUTBOUND_THRESHOLD=4
PROFILE_MODE=block

lab_policy_name() {
  printf 'Lab %s' "$1"
}

# Older lab .env files defined the profile settings (LAB_POLICY_* for pl1,
# LAB_PL2_POLICY_* for pl2), with a lower PL2 threshold. Refuse to run when
# such a file asks for values the fixed profiles do not use, instead of
# measuring something other than what the operator expects.
check_profile_env() {
  local pair name expected value failed=0
  for pair in \
    "LAB_POLICY_PARANOIA=1" \
    "LAB_POLICY_INBOUND_THRESHOLD=${PROFILE_INBOUND_THRESHOLD}" \
    "LAB_POLICY_OUTBOUND_THRESHOLD=${PROFILE_OUTBOUND_THRESHOLD}" \
    "LAB_PL2_POLICY_PARANOIA=2" \
    "LAB_PL2_POLICY_INBOUND_THRESHOLD=${PROFILE_INBOUND_THRESHOLD}" \
    "LAB_PL2_POLICY_OUTBOUND_THRESHOLD=${PROFILE_OUTBOUND_THRESHOLD}"; do
    name="${pair%%=*}"
    expected="${pair#*=}"
    value="$(env_value "${name}" "${expected}")"
    if [[ "${value}" != "${expected}" ]]; then
      echo "ERROR: ${name}=${value} in the lab .env, but the lab profiles are fixed at ${expected}." >&2
      failed=1
    fi
  done
  if (( failed )); then
    echo "PL1 and PL2 must differ only in paranoia (thresholds ${PROFILE_INBOUND_THRESHOLD}/${PROFILE_OUTBOUND_THRESHOLD})." >&2
    echo "Remove these LAB_*POLICY_* lines from benchmarks/lab/.env." >&2
    return 1
  fi
}

# Sets PROFILE_PARANOIA for the named profile.
load_policy_profile() {
  check_profile_env || return 1
  case "$1" in
    pl1) PROFILE_PARANOIA=1 ;;
    pl2) PROFILE_PARANOIA=2 ;;
    *)
      echo "Unknown POLICY '$1' (expected pl1 or pl2)." >&2
      return 1
      ;;
  esac
}
