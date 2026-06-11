import {
  useCallback,
  useEffect,
  useState,
  type PropsWithChildren,
} from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

import type { ApplyResult } from "./ApplyConfigButton";
import { ApplyNoticeContext } from "./apply-notice-context";

const SUCCESS_AUTO_DISMISS_MS = 6000;

export function ApplyNoticeProvider({ children }: PropsWithChildren) {
  const [notice, setNotice] = useState<ApplyResult | null>(null);

  const dismiss = useCallback(() => setNotice(null), []);
  const showNotice = useCallback((result: ApplyResult) => {
    setNotice(result);
  }, []);

  useEffect(() => {
    if (!notice || notice.kind !== "success") return;
    const timer = setTimeout(dismiss, SUCCESS_AUTO_DISMISS_MS);
    return () => clearTimeout(timer);
  }, [notice, dismiss]);

  return (
    <ApplyNoticeContext.Provider value={{ showNotice }}>
      {children}
      {notice ? (
        <div className="pointer-events-none fixed inset-x-0 top-16 z-[100] flex justify-center px-4 sm:justify-end sm:px-6">
          <Alert
            variant={notice.kind === "success" ? "success" : "destructive"}
            className="pointer-events-auto flex w-full max-w-md items-start justify-between gap-4 shadow-lg"
          >
            <span>{notice.message}</span>
            <Button
              type="button"
              onClick={dismiss}
              variant="ghost"
              size="sm"
              className="h-6 px-2 text-current hover:bg-current/10"
              aria-label="Dismiss apply result"
            >
              Close
            </Button>
          </Alert>
        </div>
      ) : null}
    </ApplyNoticeContext.Provider>
  );
}
