import { useState } from "react";
import { Link } from "react-router-dom";
import { useAdminUsers } from "../../api/admin";
import { ErrorState } from "../../components/shared/ErrorState";
import { Pager } from "../../components/shared/Pager";
import { SimpleTable } from "../../components/shared/SimpleTable";
import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { Spinner } from "../../components/ui/Spinner";
import { usd } from "../analytics/format";

const LIMIT = 25;

export function AdminUsersPage() {
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const users = useAdminUsers({ q, limit: LIMIT, offset });

  return (
    <Card title="Users">
      <div className="mb-3 max-w-sm">
        <Input
          aria-label="Search users"
          placeholder="Search by email or name"
          value={q}
          onChange={(event) => {
            setQ(event.target.value);
            setOffset(0);
          }}
        />
      </div>
      {users.isLoading && <Spinner className="mx-auto my-8" />}
      {users.isError && <ErrorState error={users.error} onRetry={() => users.refetch()} />}
      {users.data && (
        <>
          <SimpleTable
            rows={users.data.items}
            rowKey={(row) => row.id}
            empty="No users match."
            columns={[
              {
                header: "User",
                cell: (row) => (
                  <>
                    <Link to={row.id} className="font-medium text-indigo-600 hover:underline">
                      {row.name || row.email}
                    </Link>
                    <p className="text-xs text-slate-500">{row.email}</p>
                  </>
                ),
              },
              {
                header: "Role",
                cell: (row) =>
                  !row.is_active ? (
                    <Badge tone="red">disabled</Badge>
                  ) : row.is_staff ? (
                    <Badge tone="blue">admin</Badge>
                  ) : (
                    <Badge>learner</Badge>
                  ),
              },
              { header: "Projects", numeric: true, cell: (row) => row.project_count },
              { header: "AI calls", numeric: true, cell: (row) => row.ai_calls },
              { header: "AI cost", numeric: true, cell: (row) => usd(row.ai_cost_usd) },
              {
                header: "Last activity",
                cell: (row) => (row.last_activity ? new Date(row.last_activity).toLocaleString() : "never"),
              },
            ]}
          />
          <Pager count={users.data.count} limit={LIMIT} offset={offset} onChange={setOffset} />
        </>
      )}
    </Card>
  );
}
