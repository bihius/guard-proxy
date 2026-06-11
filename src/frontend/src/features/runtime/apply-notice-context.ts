import { createContext } from "react";

import type { ApplyResult } from "./ApplyConfigButton";

export type ApplyNoticeContextValue = {
  showNotice: (result: ApplyResult) => void;
};

export const ApplyNoticeContext = createContext<ApplyNoticeContextValue | null>(
  null,
);
