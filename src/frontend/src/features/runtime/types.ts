export type DeploymentState = "never_deployed" | "deployed" | "failed";

export type RuntimeGeneratedConfigStatus = {
  can_generate: boolean;
  checksum: string | null;
  generated_at: string | null;
  error: string | null;
};

export type HaproxyConfigSource = "generated" | "seed" | "missing";
export type CorazaConfigSource = "generated" | "fallback";

/**
 * What HAProxy and Coraza are actually running from.
 *
 * `seed`/`missing` on the HAProxy side means the demo or startup config is
 * serving traffic; `fallback` on the Coraza side means the single application
 * baked into the Coraza image inspects every request at paranoia level 1 in
 * detect-only mode and per-policy settings are ignored.
 */
export type ActiveRuntimeConfig = {
  haproxy_source: HaproxyConfigSource;
  coraza_source: CorazaConfigSource;
  degraded: boolean;
  warning: string | null;
};

export type RuntimeOperationSnapshot = {
  id: number;
  operation_type: string;
  status: string;
  config_checksum: string | null;
  message: string | null;
  created_at: string;
};

export type RuntimeStatusResponse = {
  frontend_contract_version: string;
  deployment_state: DeploymentState;
  generated_config: RuntimeGeneratedConfigStatus;
  active_config: ActiveRuntimeConfig;
  latest_validation: RuntimeOperationSnapshot | null;
  latest_reload: RuntimeOperationSnapshot | null;
};

export type ConfigApplyResponse = {
  status: string;
  correlation_id: string;
  checksum: string;
  message: string;
};
