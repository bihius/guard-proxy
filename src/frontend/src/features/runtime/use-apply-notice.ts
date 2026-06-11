import { useContext } from "react";

import {
  ApplyNoticeContext,
  type ApplyNoticeContextValue,
} from "./apply-notice-context";

export function useApplyNotice(): ApplyNoticeContextValue {
  const context = useContext(ApplyNoticeContext);
  if (!context) {
    throw new Error("useApplyNotice must be used within an ApplyNoticeProvider");
  }
  return context;
}
