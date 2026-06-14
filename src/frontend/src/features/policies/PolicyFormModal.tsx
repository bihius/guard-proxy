import { type FormEvent, useState } from "react";

import { InfoTooltip } from "@/components/shared/InfoTooltip";
import { Modal } from "@/components/shared/Modal";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api-client";

import { createPolicy, updatePolicy } from "./api";
import type { Policy } from "./types";

type CreateMode = { mode: "create" };
type EditMode = { mode: "edit"; policy: Policy };

type PolicyFormModalProps = (CreateMode | EditMode) & {
  onSuccess: () => void;
  onClose: () => void;
};

export function PolicyFormModal(props: PolicyFormModalProps) {
  const { onSuccess, onClose } = props;
  const { accessToken } = useAuth();

  const initial = props.mode === "edit" ? props.policy : null;

  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [enforcementMode, setEnforcementMode] = useState<"block" | "detect_only">(
    initial?.enforcement_mode ?? "block",
  );
  const [paranoiaLevel, setParanoiaLevel] = useState<string>(
    String(initial?.paranoia_level ?? 1),
  );
  const [inboundThreshold, setInboundThreshold] = useState<string>(
    String(initial?.inbound_anomaly_threshold ?? 5),
  );
  const outboundThreshold = String(initial?.outbound_anomaly_threshold ?? 4);
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!accessToken) return;

    setSubmitting(true);
    setServerError(null);

    try {
      if (props.mode === "edit") {
        await updatePolicy(accessToken, props.policy.id, {
          name,
          description: description || null,
          enforcement_mode: enforcementMode,
          paranoia_level: Number(paranoiaLevel) as 1 | 2 | 3 | 4,
          inbound_anomaly_threshold: Number(inboundThreshold),
          outbound_anomaly_threshold: Number(outboundThreshold),
          is_active: isActive,
        });
      } else {
        await createPolicy(accessToken, {
          name,
          description: description || null,
          enforcement_mode: enforcementMode,
          paranoia_level: Number(paranoiaLevel) as 1 | 2 | 3 | 4,
          inbound_anomaly_threshold: Number(inboundThreshold),
          outbound_anomaly_threshold: Number(outboundThreshold),
        });
      }
      onSuccess();
    } catch (err) {
      setServerError(
        err instanceof ApiError ? err.detail : "An unexpected error occurred",
      );
    } finally {
      setSubmitting(false);
    }
  }

  const title = props.mode === "create" ? "New policy" : "Edit policy";

  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={
        <>
          <Button type="button" onClick={onClose} variant="outline">
            Cancel
          </Button>
          <Button
            type="submit"
            form="policy-form"
            disabled={submitting}
          >
            {submitting ? "Saving…" : props.mode === "create" ? "Create" : "Save"}
          </Button>
        </>
      }
    >
      <form id="policy-form" onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
        {serverError && (
          <Alert
            variant="destructive"
            aria-live="assertive"
          >
            {serverError}
          </Alert>
        )}

        <div className="space-y-1.5">
          <Label htmlFor="policy-name">Name</Label>
          <Input
            id="policy-name"
            type="text"
            required
            maxLength={255}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="My WAF policy"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="policy-description">Description</Label>
          <Input
            id="policy-description"
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional"
          />
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <Label htmlFor="policy-enforcement-mode">Enforcement mode</Label>
            <InfoTooltip label="Block denies requests that exceed the policy threshold. Detect only logs matches without blocking traffic." />
          </div>
          <Select
            id="policy-enforcement-mode"
            value={enforcementMode}
            onChange={(e) => setEnforcementMode(e.target.value as "block" | "detect_only")}
          >
            <option value="block">Block</option>
            <option value="detect_only">Detect only</option>
          </Select>
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <Label htmlFor="policy-paranoia-level">Paranoia level</Label>
            <InfoTooltip label="Higher paranoia levels enable stricter CRS checks. Start low and raise only when the application tolerates the extra sensitivity." />
          </div>
          <Select
            id="policy-paranoia-level"
            value={paranoiaLevel}
            onChange={(e) => setParanoiaLevel(e.target.value)}
          >
            <option value="1">1 — Minimal</option>
            <option value="2">2 — Low</option>
            <option value="3">3 — High</option>
            <option value="4">4 — Maximum</option>
          </Select>
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <Label htmlFor="policy-inbound-threshold">Inbound threshold</Label>
            <InfoTooltip label="Requests are treated as suspicious when their inbound anomaly score reaches this threshold." />
          </div>
          <Input
            id="policy-inbound-threshold"
            type="number"
            required
            min={1}
            value={inboundThreshold}
            onChange={(e) => setInboundThreshold(e.target.value)}
          />
        </div>

        {props.mode === "edit" && (
          <Label className="flex cursor-pointer items-center gap-2">
            <Checkbox
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
            />
            Active
          </Label>
        )}
      </form>
    </Modal>
  );
}
