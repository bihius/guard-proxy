import { useState } from "react";

import type { DataTableColumn } from "@/components/shared/DataTable";
import { DataTable } from "@/components/shared/DataTable";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import { PageHeader } from "@/components/shared/PageHeader";
import { SectionCard } from "@/components/shared/SectionCard";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { LogDetailModal } from "@/features/logs/LogDetailModal";
import { useLogs } from "@/features/logs/use-logs";
import type { Log, LogAction, LogFilters } from "@/features/logs/types";
import { EMPTY_FILTERS } from "@/features/logs/types";

function actionTone(action: LogAction) {
  if (action === "deny") return "error" as const;
  if (action === "monitor") return "warning" as const;
  return "success" as const;
}

const columns: DataTableColumn<Log>[] = [
  {
    key: "timestamp",
    header: "Timestamp",
    cell: (row) => (
      <span className="whitespace-nowrap text-xs text-fg-muted">
        {new Date(row.event_at).toLocaleString()}
      </span>
    ),
  },
  {
    key: "vhost",
    header: "VHost",
    cell: (row) => row.vhost,
  },
  {
    key: "method",
    header: "Method",
    cell: (row) => <span className="font-mono text-xs">{row.method}</span>,
  },
  {
    key: "path",
    header: "Path",
    cell: (row) => (
      <span
        className="block max-w-xs truncate font-mono text-xs"
        title={row.request_uri}
      >
        {row.request_uri}
      </span>
    ),
  },
  {
    key: "action",
    header: "Action",
    cell: (row) => <StatusBadge label={row.action} tone={actionTone(row.action)} />,
  },
  {
    key: "score",
    header: "Score",
    cell: (row) => <span>{row.anomaly_score ?? "—"}</span>,
  },
  {
    // The log model stores a single matched rule per event.
    key: "rules",
    header: "Top matched rules",
    cell: (row) => {
      if (row.rule_id === null) return <span className="text-fg-subtle">—</span>;
      const label = row.rule_message
        ? `#${row.rule_id} — ${row.rule_message}`
        : `#${row.rule_id}`;
      return (
        <span className="block max-w-xs truncate text-xs" title={label}>
          {label}
        </span>
      );
    },
  },
];

export function LogsPage() {
  const { logs, total, page, pageSize, policies, isLoading, error, setPage, applyFilters, refresh } =
    useLogs();
  const [draft, setDraft] = useState<LogFilters>(EMPTY_FILTERS);
  const [selected, setSelected] = useState<Log | null>(null);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  function handleApply() {
    applyFilters(draft);
  }

  function handleClear() {
    setDraft(EMPTY_FILTERS);
    applyFilters(EMPTY_FILTERS);
  }

  const allColumns: DataTableColumn<Log>[] = [
    ...columns,
    {
      key: "actions",
      header: "",
      className: "w-px whitespace-nowrap",
      cell: (row) => (
        <button
          type="button"
          onClick={() => setSelected(row)}
          className="rounded-[var(--radius-sm)] border border-border bg-surface-hover px-3 py-1.5 text-xs font-semibold text-fg-muted transition hover:text-fg"
        >
          View
        </button>
      ),
    },
  ];

  return (
    <section className="space-y-8">
      <PageHeader
        title="Logs"
        description="Browse and filter WAF events captured by Guard Proxy."
      />

      <SectionCard title="Filters">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-fg-muted">VHost</label>
            <input
              type="text"
              value={draft.vhost}
              onChange={(e) => setDraft({ ...draft, vhost: e.target.value })}
              className="input-field"
              placeholder="example.com (exact match)"
            />
          </div>

          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-fg-muted">Action</label>
            <select
              value={draft.action}
              onChange={(e) => setDraft({ ...draft, action: e.target.value as LogFilters["action"] })}
              className="input-field"
            >
              <option value="">All actions</option>
              <option value="allow">Allow</option>
              <option value="deny">Deny</option>
              <option value="monitor">Monitor</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-fg-muted">Policy</label>
            <select
              value={draft.policy_id ?? ""}
              onChange={(e) =>
                setDraft({ ...draft, policy_id: e.target.value ? Number(e.target.value) : null })
              }
              className="input-field"
            >
              <option value="">All policies</option>
              {policies.map((p) => (
                <option key={p.id} value={String(p.id)}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-fg-muted">From</label>
            <input
              type="datetime-local"
              value={draft.date_from}
              onChange={(e) => setDraft({ ...draft, date_from: e.target.value })}
              className="input-field"
            />
          </div>

          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-fg-muted">To</label>
            <input
              type="datetime-local"
              value={draft.date_to}
              onChange={(e) => setDraft({ ...draft, date_to: e.target.value })}
              className="input-field"
            />
          </div>
        </div>

        <div className="mt-4 flex gap-3">
          <button type="button" onClick={handleApply} className="btn-primary px-4 py-2 text-sm">
            Apply
          </button>
          <button type="button" onClick={handleClear} className="btn-ghost px-4 py-2 text-sm">
            Clear
          </button>
        </div>
      </SectionCard>

      <SectionCard title="Events" description="Most recent events first.">
        {isLoading ? (
          <LoadingState label="Loading logs…" />
        ) : error ? (
          <ErrorState
            title="Failed to load logs"
            description={error}
            action={
              <button type="button" onClick={refresh} className="btn-ghost px-4 py-2 text-sm">
                Retry
              </button>
            }
          />
        ) : (
          <>
            <DataTable
              columns={allColumns}
              rows={logs}
              getRowKey={(row) => String(row.id)}
              emptyTitle="No events found"
              emptyDescription="No log events match the current filters. Try adjusting or clearing them."
            />

            {total > 0 && (
              <div className="mt-4 flex items-center justify-between gap-4">
                <span className="text-sm text-fg-muted">
                  Page {page} of {totalPages} · {total} events
                </span>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setPage(page - 1)}
                    disabled={page <= 1}
                    className="btn-ghost px-4 py-2 text-sm disabled:opacity-40"
                  >
                    Prev
                  </button>
                  <button
                    type="button"
                    onClick={() => setPage(page + 1)}
                    disabled={page >= totalPages}
                    className="btn-ghost px-4 py-2 text-sm disabled:opacity-40"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </SectionCard>

      {selected !== null && (
        <LogDetailModal log={selected} onClose={() => setSelected(null)} />
      )}
    </section>
  );
}
