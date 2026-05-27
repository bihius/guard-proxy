export type DeploymentState = "never_deployed" | "deployed" | "failed";

export type RuntimeGeneratedConfigStatus = {
  can_generate: boolean;
  checksum: string | null;
  generated_at: string | null;
  error: string | null;
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
  latest_validation: RuntimeOperationSnapshot | null;
  latest_reload: RuntimeOperationSnapshot | null;
};

export type ConfigApplyResponse = {
  status: string;
  correlation_id: string;
  checksum: string;
  message: string;
};
