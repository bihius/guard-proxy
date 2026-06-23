import { useState } from "react";
import { CalendarClock, SlidersHorizontal } from "lucide-react";

import type { DataTableColumn } from "@/components/shared/DataTable";
import { DataTable } from "@/components/shared/DataTable";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadingState } from "@/components/shared/LoadingState";
import { PageHeader } from "@/components/shared/PageHeader";
import { InfoTooltip } from "@/components/shared/InfoTooltip";
import { SectionCard } from "@/components/shared/SectionCard";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { LogDetailModal } from "@/features/logs/LogDetailModal";
import { useLogs } from "@/features/logs/use-logs";
import type { Log, LogAction, LogFilters } from "@/features/logs/types";
import { EMPTY_FILTERS } from "@/features/logs/types";
import { cn } from "@/lib/utils";

function actionTone(action: LogAction) {
  if (action === "deny") return "error" as const;
  if (action === "monitor") return "warning" as const;
  return "success" as const;
}

type DateRangePreset = {
  label: string;
  getRange: (now: Date) => Pick<LogFilters, "date_from" | "date_to">;
};

const dateRangePresets: DateRangePreset[] = [
  {
    label: "1 hour",
    getRange: (now) => ({
      date_from: toDateTimeLocal(new Date(now.getTime() - 60 * 60 * 1000)),
      date_to: toDateTimeLocal(now),
    }),
  },
  {
    label: "24 hours",
    getRange: (now) => ({
      date_from: toDateTimeLocal(new Date(now.getTime() - 24 * 60 * 60 * 1000)),
      date_to: toDateTimeLocal(now),
    }),
  },
  {
    label: "7 days",
    getRange: (now) => ({
      date_from: toDateTimeLocal(new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)),
      date_to: toDateTimeLocal(now),
    }),
  },
  {
    label: "Today",
    getRange: (now) => {
      const start = new Date(now);
      start.setHours(0, 0, 0, 0);
      return {
        date_from: toDateTimeLocal(start),
        date_to: toDateTimeLocal(now),
      };
    },
  },
];

function pad(value: number) {
  return String(value).padStart(2, "0");
}

function toDateTimeLocal(date: Date) {
  return [
    date.getFullYear(),
    "-",
    pad(date.getMonth() + 1),
    "-",
    pad(date.getDate()),
    "T",
    pad(date.getHours()),
    ":",
    pad(date.getMinutes()),
  ].join("");
}

function splitDateTime(value: string) {
  const [date = "", time = ""] = value.split("T");
  return {
    date,
    time,
  };
}

function combineDateTime(date: string, time: string) {
  if (!date) return "";
  return `${date}T${time || "00:00"}`;
}

type DateTimeRangePickerProps = {
  value: Pick<LogFilters, "date_from" | "date_to">;
  onChange: (next: Pick<LogFilters, "date_from" | "date_to">) => void;
};

function DateTimeRangePicker({ value, onChange }: DateTimeRangePickerProps) {
  const from = splitDateTime(value.date_from);
  const to = splitDateTime(value.date_to);

  function update(partial: Partial<Pick<LogFilters, "date_from" | "date_to">>) {
    onChange({
      date_from: partial.date_from ?? value.date_from,
      date_to: partial.date_to ?? value.date_to,
    });
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 text-sm font-medium text-foreground">
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary/10 text-foreground">
            <CalendarClock className="h-4 w-4" />
          </span>
          Time range
        </div>

        <div className="flex flex-wrap gap-2">
          {dateRangePresets.map((preset) => (
            <Button
              key={preset.label}
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onChange(preset.getRange(new Date()))}
            >
              {preset.label}
            </Button>
          ))}
        </div>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <DateTimeEndpoint
          label="From"
          dateId="filter-date-from"
          timeId="filter-time-from"
          date={from.date}
          time={from.time}
          onDateChange={(date) =>
            update({ date_from: combineDateTime(date, from.time) })
          }
          onTimeChange={(time) =>
            update({ date_from: combineDateTime(from.date, time) })
          }
        />

        <DateTimeEndpoint
          label="To"
          dateId="filter-date-to"
          timeId="filter-time-to"
          date={to.date}
          time={to.time}
          onDateChange={(date) =>
            update({ date_to: combineDateTime(date, to.time) })
          }
          onTimeChange={(time) =>
            update({ date_to: combineDateTime(to.date, time) })
          }
        />
      </div>
    </div>
  );
}

type DateTimeEndpointProps = {
  label: "From" | "To";
  dateId: string;
  timeId: string;
  date: string;
  time: string;
  onDateChange: (value: string) => void;
  onTimeChange: (value: string) => void;
};

function DateTimeEndpoint({
  label,
  dateId,
  timeId,
  date,
  time,
  onDateChange,
  onTimeChange,
}: DateTimeEndpointProps) {
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium text-muted-foreground">
        {label}
      </legend>
      <div className="grid grid-cols-[minmax(0,1fr)_7.5rem] gap-2">
        <div className="space-y-1.5">
          <Label htmlFor={dateId} className="sr-only">
            {label} date
          </Label>
          <Input
            id={dateId}
            type="date"
            value={date}
            onChange={(event) => onDateChange(event.target.value)}
            aria-label={`${label} date`}
            className={cn(!date && "text-muted-foreground")}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor={timeId} className="sr-only">
            {label} time
          </Label>
          <Input
            id={timeId}
            type="time"
            value={time}
            onChange={(event) => onTimeChange(event.target.value)}
            aria-label={`${label} time`}
            className={cn(!time && "text-muted-foreground")}
          />
        </div>
      </div>
    </fieldset>
  );
}

export function LogsPage() {
  const { logs, total, page, pageSize, policies, isLoading, error, setPage, applyFilters, refresh } =
    useLogs();
  const [draft, setDraft] = useState<LogFilters>(EMPTY_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState<LogFilters>(EMPTY_FILTERS);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [selected, setSelected] = useState<Log | null>(null);

  const activeFilterCount = Object.entries(appliedFilters).filter(([key, value]) => {
    if (key === "policy_id") return value !== null;
    return value !== "";
  }).length;

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const columns: DataTableColumn<Log>[] = [
    {
      key: "timestamp",
      header: "Timestamp",
      cell: (row) => (
        <span className="whitespace-nowrap text-xs text-muted-foreground">
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
        if (row.rule_id === null) return <span className="text-muted-foreground">—</span>;
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
    {
      key: "actions",
      header: "",
      className: "w-px whitespace-nowrap",
      cell: (row) => (
        <Button
          type="button"
          onClick={() => setSelected(row)}
          variant="outline"
          size="sm"
        >
          View
        </Button>
      ),
    },
  ];

  function handleApply() {
    applyFilters(draft);
    setAppliedFilters(draft);
  }

  function handleClear() {
    setDraft(EMPTY_FILTERS);
    applyFilters(EMPTY_FILTERS);
    setAppliedFilters(EMPTY_FILTERS);
  }

  return (
    <section className="space-y-6">
      <PageHeader
        title="Logs"
        description="Browse and filter WAF events captured by Guard Proxy."
      />

      <SectionCard
        title="Events"
        description="Most recent events first."
        actions={
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setFiltersOpen((open) => !open)}
            aria-expanded={filtersOpen}
          >
            <SlidersHorizontal className="h-4 w-4" />
            Filters
            {activeFilterCount > 0 && (
              <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-primary/10 px-1 text-xs font-medium text-primary">
                {activeFilterCount}
              </span>
            )}
          </Button>
        }
      >
        {filtersOpen && (
          <div className="mb-5 rounded-md border border-border bg-muted/30 p-4">
            <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(24rem,0.95fr)] lg:items-start">
              <div className="grid gap-4 md:grid-cols-3">
                <div className="space-y-1.5">
                  <Label htmlFor="filter-vhost">VHost</Label>
                  <Input
                    id="filter-vhost"
                    type="text"
                    value={draft.vhost}
                    onChange={(e) => setDraft({ ...draft, vhost: e.target.value })}
                    placeholder="example.com (exact match)"
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center gap-1.5">
                    <Label htmlFor="filter-action">Action</Label>
                    <InfoTooltip label="Guard Proxy only logs requests that triggered at least one WAF rule. 'Allowed (flagged)' means a rule matched but the combined score stayed under the policy's anomaly threshold, so the request was let through. Fully clean traffic that never matches a rule is not logged." />
                  </div>
                  <Select
                    id="filter-action"
                    value={draft.action}
                    onChange={(e) =>
                      setDraft({ ...draft, action: e.target.value as LogFilters["action"] })
                    }
                  >
                    <option value="">All actions</option>
                    <option value="allow">Allowed (flagged)</option>
                    <option value="deny">Deny</option>
                    <option value="monitor">Monitor</option>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="filter-policy">Policy</Label>
                  <Select
                    id="filter-policy"
                    value={draft.policy_id ?? ""}
                    onChange={(e) =>
                      setDraft({ ...draft, policy_id: e.target.value ? Number(e.target.value) : null })
                    }
                  >
                    <option value="">All policies</option>
                    {policies.map((p) => (
                      <option key={p.id} value={String(p.id)}>
                        {p.name}
                      </option>
                    ))}
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="filter-severity">Severity</Label>
                  <Select
                    id="filter-severity"
                    value={draft.severity}
                    onChange={(e) =>
                      setDraft({ ...draft, severity: e.target.value as LogFilters["severity"] })
                    }
                  >
                    <option value="">All severities</option>
                    <option value="info">Info</option>
                    <option value="warning">Warning</option>
                    <option value="error">Error</option>
                    <option value="critical">Critical</option>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="filter-method">Method</Label>
                  <Input
                    id="filter-method"
                    type="text"
                    value={draft.method}
                    onChange={(e) => setDraft({ ...draft, method: e.target.value })}
                    placeholder="GET, POST, …"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="filter-source-ip">Source IP</Label>
                  <Input
                    id="filter-source-ip"
                    type="text"
                    value={draft.source_ip}
                    onChange={(e) => setDraft({ ...draft, source_ip: e.target.value })}
                    placeholder="203.0.113.10"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="filter-rule-id">Rule ID</Label>
                  <Input
                    id="filter-rule-id"
                    type="number"
                    value={draft.rule_id ?? ""}
                    onChange={(e) =>
                      setDraft({ ...draft, rule_id: e.target.value ? Number(e.target.value) : null })
                    }
                    placeholder="942290"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="filter-min-score">Min anomaly score</Label>
                  <Input
                    id="filter-min-score"
                    type="number"
                    value={draft.min_score ?? ""}
                    onChange={(e) =>
                      setDraft({ ...draft, min_score: e.target.value ? Number(e.target.value) : null })
                    }
                    placeholder="5"
                  />
                </div>
              </div>

              <DateTimeRangePicker
                value={{
                  date_from: draft.date_from,
                  date_to: draft.date_to,
                }}
                onChange={(range) => setDraft({ ...draft, ...range })}
              />
            </div>

            <div className="mt-4 flex gap-3">
              <Button type="button" onClick={handleApply}>
                Apply
              </Button>
              <Button type="button" onClick={handleClear} variant="outline">
                Clear
              </Button>
            </div>
          </div>
        )}

        {isLoading ? (
          <LoadingState label="Loading logs…" />
        ) : error ? (
          <ErrorState
            title="Failed to load logs"
            description={error}
            action={
              <Button type="button" onClick={refresh} variant="outline">
                Retry
              </Button>
            }
          />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={logs}
              getRowKey={(row) => String(row.id)}
              emptyTitle="No events found"
              emptyDescription="No log events match the current filters. Try adjusting or clearing them."
            />

            {total > 0 && (
              <div className="mt-4 flex items-center justify-between gap-4">
                <span className="text-sm text-muted-foreground">
                  Page {page} of {totalPages} · {total} events
                </span>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    onClick={() => setPage(page - 1)}
                    disabled={page <= 1}
                    variant="outline"
                  >
                    Prev
                  </Button>
                  <Button
                    type="button"
                    onClick={() => setPage(page + 1)}
                    disabled={page >= totalPages}
                    variant="outline"
                  >
                    Next
                  </Button>
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
