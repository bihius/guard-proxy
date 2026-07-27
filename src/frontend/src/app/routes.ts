export const appRoutes = {
  root: "/",
  login: "/login",
  dashboard: "/dashboard",
  forbidden: "/forbidden",
  vhosts: "/vhosts",
  policies: "/policies",
  logs: "/logs",
  bannedIps: "/banned-ips",
} as const;

export function getVHostDetailPath(vhostId: string | number) {
  return `${appRoutes.vhosts}/${vhostId}`;
}

export function getPolicyDetailPath(policyId: string | number) {
  return `${appRoutes.policies}/${policyId}`;
}
