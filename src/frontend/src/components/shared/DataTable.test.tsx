import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DataTable, type DataTableColumn } from "./DataTable";

type TestRow = {
  id: string;
  name: string;
};

const columns: DataTableColumn<TestRow>[] = [
  {
    key: "name",
    header: "Name",
    cell: (row) => row.name,
  },
];

describe("DataTable", () => {
  it("renders rows and headers", () => {
    render(
      <DataTable
        columns={columns}
        rows={[
          { id: "1", name: "Alpha" },
          { id: "2", name: "Beta" },
        ]}
        getRowKey={(row) => row.id}
      />,
    );

    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
  });

  it("renders empty state when there are no rows", () => {
    render(
      <DataTable
        columns={columns}
        rows={[]}
        getRowKey={(row) => row.id}
        emptyTitle="No rows"
        emptyDescription="Nothing to display"
      />,
    );

    expect(screen.getByText("No rows")).toBeInTheDocument();
    expect(screen.getByText("Nothing to display")).toBeInTheDocument();
  });

  it("invokes onRowClick with the clicked row", () => {
    const onRowClick = vi.fn();

    render(
      <DataTable
        columns={columns}
        rows={[
          { id: "1", name: "Alpha" },
          { id: "2", name: "Beta" },
        ]}
        getRowKey={(row) => row.id}
        onRowClick={onRowClick}
      />,
    );

    fireEvent.click(screen.getByText("Beta"));

    expect(onRowClick).toHaveBeenCalledTimes(1);
    expect(onRowClick).toHaveBeenCalledWith({ id: "2", name: "Beta" });
  });
});
