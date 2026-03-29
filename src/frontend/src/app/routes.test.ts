import { describe, expect, it } from "vitest";

import { appRoutes, getVHostDetailPath } from "./routes";

describe("appRoutes", () => {
  it("keeps key routes centralized", () => {
    expect(appRoutes.login).toBe("/login");
    expect(appRoutes.dashboard).toBe("/dashboard");
    expect(appRoutes.vhosts).toBe("/vhosts");
    expect(appRoutes.policies).toBe("/policies");
  });

  it("builds vhost detail paths", () => {
    expect(getVHostDetailPath(23)).toBe("/vhosts/23");
    expect(getVHostDetailPath("abc")).toBe("/vhosts/abc");
  });
});
