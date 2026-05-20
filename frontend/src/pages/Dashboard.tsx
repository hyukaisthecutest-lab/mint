import { useQuery } from "@tanstack/react-query";
import { getDashboard } from "../api/dashboard";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { TrendingDown, TrendingUp, DollarSign, RefreshCw } from "lucide-react";
import { format } from "date-fns";
import { syncAllAccounts } from "../api/accounts";
import { useState } from "react";

const COLORS = ["#00A651", "#22c55e", "#4ade80", "#86efac", "#bbf7d0", "#007B3C", "#166534", "#fbbf24", "#f87171", "#60a5fa"];

function SummaryCard({ title, value, icon: Icon, color }: { title: string; value: string; icon: any; color: string }) {
  return (
    <div className="card flex items-center gap-4">
      <div className={`p-3 rounded-full ${color}`}>
        <Icon className="w-6 h-6 text-white" />
      </div>
      <div>
        <p className="text-sm text-gray-500">{title}</p>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
      </div>
    </div>
  );
}

function fmt(n: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
}

export default function Dashboard() {
  const [syncing, setSyncing] = useState(false);
  const { data, isLoading, refetch } = useQuery({ queryKey: ["dashboard"], queryFn: getDashboard });

  const handleSyncAll = async () => {
    setSyncing(true);
    try {
      await syncAllAccounts();
      setTimeout(() => { refetch(); setSyncing(false); }, 3000);
    } catch {
      setSyncing(false);
    }
  };

  if (isLoading) return <div className="flex items-center justify-center h-full"><div className="animate-spin rounded-full h-10 w-10 border-4 border-mint-600 border-t-transparent" /></div>;

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Overview</h1>
          <p className="text-gray-500 mt-1">{format(new Date(), "MMMM yyyy")}</p>
        </div>
        <button onClick={handleSyncAll} disabled={syncing} className="btn-primary flex items-center gap-2">
          <RefreshCw className={`w-4 h-4 ${syncing ? "animate-spin" : ""}`} />
          {syncing ? "Syncing..." : "Sync All"}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <SummaryCard title="Total Balance" value={fmt(data?.total_balance ?? 0)} icon={DollarSign} color="bg-mint-600" />
        <SummaryCard title="Monthly Spending" value={fmt(data?.monthly_spending ?? 0)} icon={TrendingDown} color="bg-red-400" />
        <SummaryCard title="Monthly Income" value={fmt(data?.monthly_income ?? 0)} icon={TrendingUp} color="bg-blue-400" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Spending by Category</h2>
          {data?.spending_by_category.length === 0 ? (
            <p className="text-gray-400 text-center py-8">No spending data this month</p>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={data?.spending_by_category} layout="vertical">
                <XAxis type="number" tickFormatter={(v) => `$${v}`} tick={{ fontSize: 12 }} />
                <YAxis type="category" dataKey="category" width={110} tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v: number) => fmt(v)} />
                <Bar dataKey="total" radius={[0, 4, 4, 0]}>
                  {data?.spending_by_category.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Transactions</h2>
          {data?.recent_transactions.length === 0 ? (
            <p className="text-gray-400 text-center py-8">No transactions yet. Link an account and sync!</p>
          ) : (
            <div className="space-y-3">
              {data?.recent_transactions.map((txn) => (
                <div key={txn.id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                  <div>
                    <p className="font-medium text-gray-900 text-sm">{txn.merchant || txn.description}</p>
                    <p className="text-xs text-gray-400">{txn.category} · {format(new Date(txn.transaction_date), "MMM d")}</p>
                  </div>
                  <span className={`font-semibold text-sm ${txn.amount < 0 ? "text-red-500" : "text-mint-600"}`}>
                    {txn.amount < 0 ? "-" : "+"}{fmt(Math.abs(txn.amount))}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
