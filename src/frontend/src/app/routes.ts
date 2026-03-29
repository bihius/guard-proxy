export const appRoutes = {
  root: "/",
  login: "/login",
  dashboard: "/dashboard",
  forbidden: "/forbidden",
  vhosts: "/vhosts",
  policies: "/policies",
} as const;

export function getVHostDetailPath(vhostId: string | number) {
  return `${appRoutes.vhosts}/${vhostId}`;
}
