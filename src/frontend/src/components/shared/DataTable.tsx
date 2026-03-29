import type { ReactNode } from "react";

import { EmptyState } from "./EmptyState";

export type DataTableColumn<Row> = {
  key: string;
  header: ReactNode;
  className?: string;
  headerClassName?: string;
  cell: (row: Row) => ReactNode;
};

type DataTableProps<Row> = {
  columns: DataTableColumn<Row>[];
  rows: Row[];
  getRowKey: (row: Row) => string;
  emptyTitle?: string;
  emptyDescription?: string;
};

export function DataTable<Row>({
  columns,
  rows,
  getRowKey,
  emptyTitle = "No records yet",
  emptyDescription = "This table will show data here once the feature is connected to real records.",
}: DataTableProps<Row>) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title={emptyTitle}
        description={emptyDescription}
      />
    );
  }

  return (
    <div className="overflow-hidden rounded-[var(--radius-lg)] border border-border bg-surface">
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse">
          <thead className="bg-surface-hover">
            <tr className="border-b border-border">
              {columns.map((column) => (
                <th
                  key={column.key}
                  className={`px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-fg-muted ${column.headerClassName ?? ""}`.trim()}
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {rows.map((row, rowIndex) => (
              <tr
                key={getRowKey(row)}
                className={
                  rowIndex === rows.length - 1
                    ? ""
                    : "border-b border-border-subtle"
                }
              >
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={`px-4 py-3 align-top text-sm text-fg ${column.className ?? ""}`.trim()}
                  >
                    {column.cell(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
