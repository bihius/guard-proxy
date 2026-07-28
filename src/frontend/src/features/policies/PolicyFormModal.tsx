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
import { cn } from "@/lib/utils";

import { createPolicy, updatePolicy } from "./api";
import { COUNTRY_CODES_SET } from "./countries";
import type { GeoipMode, Policy } from "./types";

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
  const [ddosProtectionEnabled, setDdosProtectionEnabled] = useState(
    initial?.ddos_protection_enabled ?? false,
  );
  const [rateLimitRequests, setRateLimitRequests] = useState<string>(
    String(initial?.rate_limit_requests ?? 100),
  );
  const [rateLimitWindowSeconds, setRateLimitWindowSeconds] = useState<string>(
    String(initial?.rate_limit_window_seconds ?? 10),
  );
  const [maxConnectionsPerIp, setMaxConnectionsPerIp] = useState<string>(
    String(initial?.max_connections_per_ip ?? 20),
  );
  const [autoBanEnabled, setAutoBanEnabled] = useState(
    initial?.auto_ban_enabled ?? false,
  );
  const [banThreshold, setBanThreshold] = useState<string>(
    String(initial?.ban_threshold ?? 10),
  );
  const [banDurationSeconds, setBanDurationSeconds] = useState<string>(
    String(initial?.ban_duration_seconds ?? 600),
  );
  const [geoipMode, setGeoipMode] = useState<GeoipMode>(
    initial?.geoip_mode ?? "off",
  );
  const [geoipCountries, setGeoipCountries] = useState<string>(
    (initial?.geoip_countries ?? []).join(", "),
  );
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  function parseGeoipCountries(): string[] {
    const seen = new Set<string>();
    const codes: string[] = [];
    for (const raw of geoipCountries.split(",")) {
      const code = raw.trim().toUpperCase();
      if (!code) continue;
      if (!seen.has(code)) {
        seen.add(code);
        codes.push(code);
      }
    }
    return codes;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!accessToken) return;

    setSubmitting(true);
    setServerError(null);

    const parsedGeoipCountries = parseGeoipCountries();
    if (geoipMode !== "off") {
      if (parsedGeoipCountries.length === 0) {
        setServerError("Select at least one country code.");
        setSubmitting(false);
        return;
      }
      const unknown = parsedGeoipCountries.find(
        (code) => !COUNTRY_CODES_SET.has(code),
      );
      if (unknown) {
        setServerError(`Unknown country code: ${unknown}`);
        setSubmitting(false);
        return;
      }
    }

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
          ddos_protection_enabled: ddosProtectionEnabled,
          rate_limit_requests: Number(rateLimitRequests),
          rate_limit_window_seconds: Number(rateLimitWindowSeconds),
          max_connections_per_ip: Number(maxConnectionsPerIp),
          auto_ban_enabled: autoBanEnabled,
          ban_threshold: Number(banThreshold),
          ban_duration_seconds: Number(banDurationSeconds),
          geoip_mode: geoipMode,
          geoip_countries: parsedGeoipCountries,
        });
      } else {
        await createPolicy(accessToken, {
          name,
          description: description || null,
          enforcement_mode: enforcementMode,
          paranoia_level: Number(paranoiaLevel) as 1 | 2 | 3 | 4,
          inbound_anomaly_threshold: Number(inboundThreshold),
          outbound_anomaly_threshold: Number(outboundThreshold),
          ddos_protection_enabled: ddosProtectionEnabled,
          rate_limit_requests: Number(rateLimitRequests),
          rate_limit_window_seconds: Number(rateLimitWindowSeconds),
          max_connections_per_ip: Number(maxConnectionsPerIp),
          auto_ban_enabled: autoBanEnabled,
          ban_threshold: Number(banThreshold),
          ban_duration_seconds: Number(banDurationSeconds),
          geoip_mode: geoipMode,
          geoip_countries: parsedGeoipCountries,
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

        <div className="space-y-3 rounded-md border border-border p-3">
          <Label
            className={cn(
              "flex cursor-pointer items-center gap-2",
              ddosProtectionEnabled && "text-foreground",
            )}
          >
            <Checkbox
              checked={ddosProtectionEnabled}
              onChange={(e) => {
                setDdosProtectionEnabled(e.target.checked);
                if (!e.target.checked) setAutoBanEnabled(false);
              }}
            />
            DDoS protection
            <InfoTooltip label="Enable per-vhost request-rate limiting and connection throttling in the generated HAProxy config." />
          </Label>

          {ddosProtectionEnabled && (
            <>
              <div className="space-y-1.5">
                <Label htmlFor="policy-rate-limit-requests">Rate limit (requests)</Label>
                <Input
                  id="policy-rate-limit-requests"
                  type="number"
                  required
                  min={1}
                  value={rateLimitRequests}
                  onChange={(e) => setRateLimitRequests(e.target.value)}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="policy-rate-limit-window">Rate limit window (seconds)</Label>
                <Input
                  id="policy-rate-limit-window"
                  type="number"
                  required
                  min={1}
                  max={3600}
                  value={rateLimitWindowSeconds}
                  onChange={(e) => setRateLimitWindowSeconds(e.target.value)}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="policy-max-connections">Max connections per IP</Label>
                <Input
                  id="policy-max-connections"
                  type="number"
                  required
                  min={1}
                  value={maxConnectionsPerIp}
                  onChange={(e) => setMaxConnectionsPerIp(e.target.value)}
                />
              </div>

              <div className="space-y-3 border-t border-border pt-3">
                <Label
                  className={cn(
                    "flex cursor-pointer items-center gap-2",
                    autoBanEnabled && "text-foreground",
                  )}
                >
                  <Checkbox
                    checked={autoBanEnabled}
                    onChange={(e) => setAutoBanEnabled(e.target.checked)}
                  />
                  Automatic IP banning
                  <InfoTooltip label="Ban a source IP after repeated rate-limit or connection-limit violations. The ban lifts automatically once the IP stays quiet for the ban duration." />
                </Label>

                {autoBanEnabled && (
                  <>
                    <div className="space-y-1.5">
                      <Label htmlFor="policy-ban-threshold">Ban threshold (violations)</Label>
                      <Input
                        id="policy-ban-threshold"
                        type="number"
                        required
                        min={1}
                        value={banThreshold}
                        onChange={(e) => setBanThreshold(e.target.value)}
                      />
                    </div>

                    <div className="space-y-1.5">
                      <Label htmlFor="policy-ban-duration">Ban duration (seconds)</Label>
                      <Input
                        id="policy-ban-duration"
                        type="number"
                        required
                        min={1}
                        max={86400}
                        value={banDurationSeconds}
                        onChange={(e) => setBanDurationSeconds(e.target.value)}
                      />
                    </div>
                  </>
                )}
              </div>
            </>
          )}
        </div>

        <div className="space-y-3 rounded-md border border-border p-3">
          <div className="flex items-center gap-2">
            <Label htmlFor="policy-geoip-mode">GeoIP country filtering</Label>
            <InfoTooltip label="Allowlist: only the listed countries may reach this vhost; everything else gets 403. Blocklist: the listed countries get 403. Requests whose country cannot be resolved are allowed by default." />
          </div>
          <Select
            id="policy-geoip-mode"
            value={geoipMode}
            onChange={(e) => setGeoipMode(e.target.value as GeoipMode)}
          >
            <option value="off">Off</option>
            <option value="allowlist">Allowlist</option>
            <option value="blocklist">Blocklist</option>
          </Select>

          {geoipMode !== "off" && (
            <div className="space-y-1.5">
              <Label htmlFor="policy-geoip-countries">Country codes</Label>
              <Input
                id="policy-geoip-countries"
                type="text"
                value={geoipCountries}
                onChange={(e) => setGeoipCountries(e.target.value)}
                placeholder="e.g. US, CA, GB"
              />
            </div>
          )}
        </div>

        {props.mode === "edit" && (
          <Label className={cn("flex cursor-pointer items-center gap-2", isActive && "text-foreground")}>
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
