import * as React from "react";

import { cn } from "@/lib/utils";

const Checkbox = React.forwardRef<
  HTMLInputElement,
  Omit<React.ComponentProps<"input">, "type">
>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    type="checkbox"
    className={cn(
      "h-4 w-4 rounded border-border bg-background text-primary accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      className,
    )}
    {...props}
  />
));
Checkbox.displayName = "Checkbox";

export { Checkbox };
