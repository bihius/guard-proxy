import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { appRoutes } from "@/app/routes";
import type { DataTableColumn } from "@/components/shared/DataTable";
import { DataTable } from "@/components/shared/DataTable";
import { ErrorState } from "@/components/shared/ErrorState";
import { SectionCard } from "@/components/shared/SectionCard";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  analyzeTuningSuggestions,
  approveTuningSuggestion,
  listTuningSuggestions,
  rejectTuningSuggestion,
} from "@/features/policies/api";
import { RuleExclusionFormModal } from "@/features/policies/RuleExclusionModals";
import type { TuningAnalysis, TuningSuggestion } from "@/features/policies/types";
import { toDateTimeLocal } from "@/features/logs/url-filters";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api-client";
import { formatDateTime, parseUtc } from "@/lib/datetime";

type TuningSuggestionsCardProps = {
  policyId: number;
  /** Called after an approval created an exclusion. */
  onExclusionCreated: () => void;
};

const actionButtonClass =
  "rounded-[var(--radius-sm)] border border-border bg-surface-hover px-3 py-1.5 text-xs font-semibold text-fg-muted transition hover:text-fg disabled:opacity-50";

function confidenceBadge(confidence: number) {
  if (confidence >= 70) return <StatusBadge label={`${confidence} · likely FP`} tone="success" />;
  if (confidence >= 40) return <StatusBadge label={`${confidence} · review`} tone="warning" />;
  return <StatusBadge label={`${confidence} · unlikely FP`} tone="error" />;
}

/** Log viewer bounded to the suggestion's events. The picker has minute precision. */
function eventsLink(suggestion: TuningSuggestion) {
  const params = new URLSearchParams({
    rule_id: String(suggestion.rule_id),
    date_from: toDateTimeLocal(parseUtc(suggestion.first_seen_at)),
    date_to: toDateTimeLocal(
      new Date(Math.ceil(parseUtc(suggestion.last_seen_at).getTime() / 60_000) * 60_000),
    ),
  });
  return `${appRoutes.logs}?${params.toString()}`;
}

/**
 * Learning mode (#263): exclusions proposed from rules that keep firing on
 * the same input. Nothing takes effect until an admin reviews and approves.
 */
export function TuningSuggestionsCard({ policyId, onExclusionCreated }: TuningSuggestionsCardProps) {
  const { accessToken, hasRole } = useAuth();
  const isAdmin = hasRole("admin");
  const [suggestions, setSuggestions] = useState<TuningSuggestion[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<TuningAnalysis | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [reviewing, setReviewing] = useState<TuningSuggestion | null>(null);

  const load = useCallback(() => {
    if (!accessToken) return;
    const controller = new AbortController();
    listTuningSuggestions(accessToken, policyId, controller.signal)
      .then((rows) => {
        setSuggestions(rows);
        setLoadError(null);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setLoadError(err instanceof ApiError ? err.detail : "Could not load suggestions");
      });
    return () => controller.abort();
  }, [accessToken, policyId]);

  useEffect(() => load(), [load]);

  async function analyze() {
    if (!accessToken) return;
    setIsAnalyzing(true);
    setActionError(null);
    try {
      setAnalysis(await analyzeTuningSuggestions(accessToken, policyId));
      load();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.detail : "Analysis failed");
    } finally {
      setIsAnalyzing(false);
    }
  }

  async function reject(suggestion: TuningSuggestion) {
    if (!accessToken) return;
    setBusyId(suggestion.id);
    setActionError(null);
    try {
      await rejectTuningSuggestion(accessToken, policyId, suggestion.id);
      load();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.detail : "Could not reject the suggestion");
    } finally {
      setBusyId(null);
    }
  }

  const columns: DataTableColumn<TuningSuggestion>[] = [
    {
      key: "rule",
      header: "Rule",
      cell: (row) => (
        <div>
          <div className="font-mono text-xs">{row.rule_id}</div>
          {row.rule_message && (
            <div className="text-xs text-muted-foreground">{row.rule_message}</div>
          )}
        </div>
      ),
    },
    {
      key: "target",
      header: "Target",
      cell: (row) => (
        <span className="font-mono text-xs">
          {row.target_type.toUpperCase()}
          {row.target_value !== null && `:${row.target_value}`}
        </span>
      ),
    },
    {
      key: "scope_path",
      header: "Scope",
      cell: (row) => <span className="font-mono text-xs">{row.scope_path ?? "All paths"}</span>,
    },
    { key: "confidence", header: "Confidence", cell: (row) => confidenceBadge(row.confidence) },
    {
      key: "evidence",
      header: "Evidence",
      cell: (row) => (
        <div className="text-xs">
          <div>
            {row.event_count} events · {row.source_ip_count}{" "}
            {row.source_ip_count === 1 ? "client" : "clients"}
          </div>
          <div className="text-muted-foreground">last {formatDateTime(row.last_seen_at)}</div>
          <Link to={eventsLink(row)} className="font-medium text-primary hover:opacity-80">
            View events
          </Link>
        </div>
      ),
    },
    ...(isAdmin
      ? [
          {
            key: "actions",
            header: "",
            className: "w-px whitespace-nowrap",
            cell: (row: TuningSuggestion) => (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className={actionButtonClass}
                  disabled={busyId === row.id}
                  onClick={() => setReviewing(row)}
                >
                  Review
                </button>
                <button
                  type="button"
                  className={actionButtonClass}
                  disabled={busyId === row.id}
                  onClick={() => void reject(row)}
                >
                  Reject
                </button>
              </div>
            ),
          } satisfies DataTableColumn<TuningSuggestion>,
        ]
      : []),
  ];

  return (
    <SectionCard
      title="Tuning suggestions"
      description="Learning mode proposes exclusions for rules that keep firing on the same input. It runs nightly for detect-only policies; nothing takes effect until an admin approves it."
      descriptionDisplay="tooltip"
      actions={
        isAdmin ? (
          <Button type="button" size="sm" onClick={() => void analyze()} disabled={isAnalyzing}>
            {isAnalyzing ? "Analyzing..." : "Analyze now"}
          </Button>
        ) : undefined
      }
    >
      <div className="space-y-3">
        {analysis && (
          <Alert aria-live="polite">
            Scanned {analysis.events_scanned} events from the last {analysis.window_hours} hours:{" "}
            {analysis.created} new, {analysis.updated} updated.
          </Alert>
        )}
        {actionError && (
          <Alert variant="destructive" aria-live="assertive">
            {actionError}
          </Alert>
        )}
        {loadError ? (
          <ErrorState title="Could not load suggestions" description={loadError} />
        ) : (
          <DataTable
            columns={columns}
            rows={suggestions ?? []}
            getRowKey={(row) => String(row.id)}
            emptyTitle="No pending suggestions"
            emptyDescription="Suggestions appear after analysis finds a rule firing repeatedly on the same input."
          />
        )}
      </div>

      {reviewing && (
        <RuleExclusionFormModal
          mode="create"
          policyId={policyId}
          suggestion={{
            ...reviewing,
            comment: `Learning mode: ${reviewing.event_count} events from ${reviewing.source_ip_count} clients`,
          }}
          intro={
            <p className="text-sm text-muted-foreground">
              Rule {reviewing.rule_id} matched this target in {reviewing.event_count} events.
              Narrow the scope if it should apply to fewer paths.
            </p>
          }
          submitLabel="Approve"
          createExclusion={(body) =>
            approveTuningSuggestion(accessToken ?? "", policyId, reviewing.id, body)
          }
          onSuccess={() => {
            setReviewing(null);
            load();
            onExclusionCreated();
          }}
          onClose={() => setReviewing(null)}
        />
      )}
    </SectionCard>
  );
}
