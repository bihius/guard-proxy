import { type FormEvent, useState } from "react";
import { Plus, Trash2 } from "lucide-react";

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

import { createVHost, updateVHost } from "./api";
import type { Policy, VHost, VHostBackendInput } from "./types";

type CreateMode = { mode: "create" };
type EditMode = { mode: "edit"; vhost: VHost };

type VHostFormModalProps = (CreateMode | EditMode) & {
  policies: Policy[];
  onSuccess: () => void;
  onClose: () => void;
};

function newBackend(url = ""): VHostBackendInput {
  return {
    url,
    is_active: true,
    health_check_enabled: true,
    health_check_path: "/",
    health_check_interval_seconds: 5,
    health_check_fall: 3,
    health_check_rise: 2,
  };
}

export function VHostFormModal(props: VHostFormModalProps) {
  const { policies, onSuccess, onClose } = props;
  const { accessToken } = useAuth();

  const initial = props.mode === "edit" ? props.vhost : null;
  const initialBackends =
    initial?.backends && initial.backends.length > 0
      ? initial.backends.map((backend) => ({
          url: backend.url,
          is_active: backend.is_active,
          health_check_enabled: backend.health_check_enabled,
          health_check_path: backend.health_check_path,
          health_check_interval_seconds: backend.health_check_interval_seconds,
          health_check_fall: backend.health_check_fall,
          health_check_rise: backend.health_check_rise,
        }))
      : [newBackend(initial?.backend_url ?? "")];

  const [domain, setDomain] = useState(initial?.domain ?? "");
  const [backends, setBackends] = useState<VHostBackendInput[]>(initialBackends);
  const [description, setDescription] = useState(initial?.description ?? "");
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);
  const [sslEnabled, setSslEnabled] = useState(initial?.ssl_enabled ?? false);
  const [sslProvider, setSslProvider] = useState<"none" | "upload" | "letsencrypt">(
    initial?.ssl_provider ?? "none"
  );
  const [sslCert, setSslCert] = useState("");
  const [sslKey, setSslKey] = useState("");
  const [policyId, setPolicyId] = useState<string>(
    initial?.policy_id != null ? String(initial.policy_id) : "",
  );
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!accessToken) return;

    setSubmitting(true);
    setServerError(null);

    const body = {
      domain,
      backend_url: backends[0]?.url ?? null,
      backends,
      description: description || null,
      ssl_enabled: sslEnabled,
      ssl_provider: sslProvider,
      ssl_cert: sslProvider === "upload" ? (sslCert || null) : null,
      ssl_key: sslProvider === "upload" ? (sslKey || null) : null,
      is_active: isActive,
      policy_id: policyId ? Number(policyId) : null,
    };

    try {
      if (props.mode === "edit") {
        await updateVHost(accessToken, props.vhost.id, body);
      } else {
        await createVHost(accessToken, body);
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

  function updateBackend(index: number, patch: Partial<VHostBackendInput>) {
    setBackends((current) =>
      current.map((backend, candidateIndex) =>
        candidateIndex === index ? { ...backend, ...patch } : backend,
      ),
    );
  }

  function addBackend() {
    setBackends((current) => [...current, newBackend()]);
  }

  function removeBackend(index: number) {
    setBackends((current) => current.filter((_, candidateIndex) => candidateIndex !== index));
  }

  const title = props.mode === "create" ? "New virtual host" : "Edit virtual host";

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
            form="vhost-form"
            disabled={submitting}
          >
            {submitting ? "Saving…" : props.mode === "create" ? "Create" : "Save"}
          </Button>
        </>
      }
    >
      <form id="vhost-form" onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
        {serverError && (
          <Alert
            variant="destructive"
            aria-live="assertive"
          >
            {serverError}
          </Alert>
        )}

        <div className="space-y-1.5">
          <Label htmlFor="vhost-domain">Domain</Label>
          <Input
            id="vhost-domain"
            type="text"
            required
            maxLength={255}
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            placeholder="example.com"
          />
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <Label>Backends</Label>
            <Button type="button" variant="outline" size="sm" onClick={addBackend}>
              <Plus aria-hidden="true" />
              Add
            </Button>
          </div>

          <div className="space-y-3">
            {backends.map((backend, index) => (
              <div
                key={index}
                className="space-y-3 rounded-md border border-border bg-muted/20 p-3"
              >
                <div className="flex items-end gap-2">
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <Label htmlFor={`vhost-backend-url-${index}`}>Backend URL</Label>
                    <Input
                      id={`vhost-backend-url-${index}`}
                      type="url"
                      required
                      maxLength={512}
                      value={backend.url}
                      onChange={(e) => updateBackend(index, { url: e.target.value })}
                      placeholder="https://backend.internal"
                    />
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label="Remove backend"
                    disabled={backends.length === 1}
                    onClick={() => removeBackend(index)}
                  >
                    <Trash2 aria-hidden="true" />
                  </Button>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <Label className={cn("flex cursor-pointer items-center gap-2", backend.is_active && "text-foreground")}>
                    <Checkbox
                      checked={backend.is_active}
                      onChange={(e) =>
                        updateBackend(index, { is_active: e.target.checked })
                      }
                    />
                    Active
                  </Label>
                  <Label className={cn("flex cursor-pointer items-center gap-2", backend.health_check_enabled && "text-foreground")}>
                    <Checkbox
                      checked={backend.health_check_enabled}
                      onChange={(e) =>
                        updateBackend(index, {
                          health_check_enabled: e.target.checked,
                        })
                      }
                    />
                    Health checks
                  </Label>
                </div>

                <div className="grid gap-3 sm:grid-cols-4">
                  <div className="space-y-1.5 sm:col-span-1">
                    <Label htmlFor={`vhost-health-path-${index}`}>Path</Label>
                    <Input
                      id={`vhost-health-path-${index}`}
                      type="text"
                      maxLength={255}
                      value={backend.health_check_path}
                      onChange={(e) =>
                        updateBackend(index, {
                          health_check_path: e.target.value,
                        })
                      }
                      disabled={!backend.health_check_enabled}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor={`vhost-health-interval-${index}`}>Interval</Label>
                    <Input
                      id={`vhost-health-interval-${index}`}
                      type="number"
                      min={1}
                      value={backend.health_check_interval_seconds}
                      onChange={(e) =>
                        updateBackend(index, {
                          health_check_interval_seconds: Number(e.target.value),
                        })
                      }
                      disabled={!backend.health_check_enabled}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor={`vhost-health-fall-${index}`}>Fall</Label>
                    <Input
                      id={`vhost-health-fall-${index}`}
                      type="number"
                      min={1}
                      value={backend.health_check_fall}
                      onChange={(e) =>
                        updateBackend(index, {
                          health_check_fall: Number(e.target.value),
                        })
                      }
                      disabled={!backend.health_check_enabled}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor={`vhost-health-rise-${index}`}>Rise</Label>
                    <Input
                      id={`vhost-health-rise-${index}`}
                      type="number"
                      min={1}
                      value={backend.health_check_rise}
                      onChange={(e) =>
                        updateBackend(index, {
                          health_check_rise: Number(e.target.value),
                        })
                      }
                      disabled={!backend.health_check_enabled}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="vhost-description">Description</Label>
          <Input
            id="vhost-description"
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="vhost-policy">Policy</Label>
          <Select
            id="vhost-policy"
            value={policyId}
            onChange={(e) => setPolicyId(e.target.value)}
          >
            <option value="">None (default policy)</option>
            {policies.map((p) => (
              <option key={p.id} value={String(p.id)}>
                {p.name}
              </option>
            ))}
          </Select>
        </div>

        <div className="space-y-1.5 pt-2">
          <Label className={cn("flex cursor-pointer items-center gap-2 font-semibold", sslEnabled && "text-foreground")}>
            <Checkbox
              checked={sslEnabled}
              onChange={(e) => setSslEnabled(e.target.checked)}
            />
            Enable SSL
          </Label>

          {sslEnabled && (
            <div className="mt-4 space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="vhost-ssl-provider">SSL Provider</Label>
                <Select
                  id="vhost-ssl-provider"
                  value={sslProvider}
                  onChange={(e) => setSslProvider(e.target.value as "none" | "upload" | "letsencrypt")}
                >
                  <option value="none">None</option>
                  <option value="upload">Upload Custom Certificate</option>
                  <option value="letsencrypt">Let's Encrypt (Auto-provision)</option>
                </Select>
              </div>

              {sslProvider === "upload" && (
                <>
                  <div className="space-y-1.5">
                    <Label htmlFor="vhost-ssl-cert">Certificate (PEM)</Label>
                    <textarea
                      id="vhost-ssl-cert"
                      className="flex min-h-[100px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 font-mono"
                      value={sslCert}
                      onChange={(e) => setSslCert(e.target.value)}
                      placeholder="-----BEGIN CERTIFICATE-----..."
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="vhost-ssl-key">Private Key (PEM)</Label>
                    <textarea
                      id="vhost-ssl-key"
                      className="flex min-h-[100px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 font-mono"
                      value={sslKey}
                      onChange={(e) => setSslKey(e.target.value)}
                      placeholder="-----BEGIN PRIVATE KEY-----..."
                    />
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        <div className="pt-2">
          <Label className={cn("flex cursor-pointer items-center gap-2", isActive && "text-foreground")}>
            <Checkbox
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
            />
            Active
          </Label>
        </div>
      </form>
    </Modal>
  );
}
