import { type FormEvent, useState } from "react";

import { Modal } from "@/components/shared/Modal";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api-client";

import { createVHost, updateVHost } from "./api";
import type { Policy, VHost } from "./types";

type CreateMode = { mode: "create" };
type EditMode = { mode: "edit"; vhost: VHost };

type VHostFormModalProps = (CreateMode | EditMode) & {
  policies: Policy[];
  onSuccess: () => void;
  onClose: () => void;
};

export function VHostFormModal(props: VHostFormModalProps) {
  const { policies, onSuccess, onClose } = props;
  const { accessToken } = useAuth();

  const initial = props.mode === "edit" ? props.vhost : null;

  const [domain, setDomain] = useState(initial?.domain ?? "");
  const [backendUrl, setBackendUrl] = useState(initial?.backend_url ?? "");
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
      backend_url: backendUrl,
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

        <div className="space-y-1.5">
          <Label htmlFor="vhost-backend-url">Backend URL</Label>
          <Input
            id="vhost-backend-url"
            type="url"
            required
            maxLength={512}
            value={backendUrl}
            onChange={(e) => setBackendUrl(e.target.value)}
            placeholder="https://backend.internal"
          />
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

        <div className="space-y-1.5 border-t pt-4">
          <Label className="flex cursor-pointer items-center gap-2 font-semibold">
            <Checkbox
              checked={sslEnabled}
              onChange={(e) => setSslEnabled(e.target.checked)}
            />
            Enable SSL
          </Label>

          {sslEnabled && (
            <div className="mt-4 space-y-4 rounded-md border p-4">
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

        <div className="border-t pt-4">
          <Label className="flex cursor-pointer items-center gap-2">
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
