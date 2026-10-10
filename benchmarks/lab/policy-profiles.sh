# policy-profiles.sh — Lab policy naming and PL1/PL2 settings profiles.
#
# Sourced by setup-lab.sh, set-policy.sh and runners/lib.sh, which must define
# env_value() first.
#
# Every lab vhost has its own WAF policy, named after its domain. A profile
# (pl1 or pl2) is only a set of settings that set-policy.sh writes into those
# per-vhost policies, so one vhost can be moved to PL2 while the others stay on
# PL1, and vhost-specific tuning (exclusions, custom rules) never leaks into
# another target.

lab_policy_name() {
  printf 'Lab %s' "$1"
}

# Sets PROFILE_PARANOIA, PROFILE_INBOUND_THRESHOLD and PROFILE_OUTBOUND_THRESHOLD.
load_policy_profile() {
  case "$1" in
    pl1)
      PROFILE_PARANOIA="$(env_value LAB_POLICY_PARANOIA 1)"
      PROFILE_INBOUND_THRESHOLD="$(env_value LAB_POLICY_INBOUND_THRESHOLD 5)"
      PROFILE_OUTBOUND_THRESHOLD="$(env_value LAB_POLICY_OUTBOUND_THRESHOLD 4)"
      ;;
    pl2)
      # Same thresholds as pl1: only the paranoia level changes, so a PL1 vs
      # PL2 difference can be attributed to the paranoia level alone.
      PROFILE_PARANOIA="$(env_value LAB_PL2_POLICY_PARANOIA 2)"
      PROFILE_INBOUND_THRESHOLD="$(env_value LAB_PL2_POLICY_INBOUND_THRESHOLD 5)"
      PROFILE_OUTBOUND_THRESHOLD="$(env_value LAB_PL2_POLICY_OUTBOUND_THRESHOLD 4)"
      ;;
    *)
      echo "Unknown POLICY '$1' (expected pl1 or pl2)." >&2
      return 1
      ;;
  esac
}
