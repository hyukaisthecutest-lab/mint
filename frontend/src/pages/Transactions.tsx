import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getTransactions } from "../api/transactions";
import { getAccounts } from "../api/accounts";
import { ArrowLeftRight, ChevronLeft, ChevronRight } from "lucide-react";
import { format } from "date-fns";

const CATEGORIES = ["All", "Food & Drink", "Groceries", "Shopping", "Entertainment", "Transportation", "Bills & Utilities", "Health & Fitness", "Income", "Transfer"];

function fmt(n: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Math.abs(n));
}

const CATEGORY_COLORS: Record<string, string> = {
  "Food & Drink": "bg-orange-100 text-orange-700",
  "Groceries": "bg-mint-100 text-mint-700",
  "Shopping": "bg-purple-100 text-purple-700",
  "Entertainment": "bg-pink-100 text-pink-700",
  "Transportation": "bg-blue-100 text-blue-700",
  "Bills & Utilities": "bg-yellow-100 text-yellow-700",
  "Health & Fitness": "bg-red-100 text-red-700",
  "Income": "bg-mint-100 text-mint-700",
  "Transfer": "bg-gray-100 text-gray-600",
};

export default function Transactions() {
  const [page, setPage] = useState(1);
  const [category, setCategory] = useState("");
  const [accountId, setAccountId] = useState("");
  const PAGE_SIZE = 20;

  const { data: accounts = [] } = useQuery({ queryKey: ["accounts"], queryFn: getAccounts });
  const { data, isLoading } = useQuery({
    queryKey: ["transactions", page, category, accountId],
    queryFn: () => getTransactions({ page, page_size: PAGE_SIZE, category: category || undefined, account_id: accountId || undefined }),
  });

  const totalPages = Math.ceil((data?.total ?? 0) / PAGE_SIZE);

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Transactions</h1>
        <p className="text-gray-500 mt-1">{data?.total ?? 0} total transactions</p>
      </div>

      <div className="card mb-6">
        <div className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-48">
            <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
            <select
              className="input"
              value={category}
              onChange={(e) => { setCategory(e.target.value); setPage(1); }}
            >
              {CATEGORIES.map((c) => <option key={c} value={c === "All" ? "" : c}>{c}</option>)}
            </select>
          </div>
          <div className="flex-1 min-w-48">
            <label className="block text-sm font-medium text-gray-700 mb-1">Account</label>
            <select
              className="input"
              value={accountId}
              onChange={(e) => { setAccountId(e.target.value); setPage(1); }}
            >
              <option value="">All accounts</option>
              {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16"><div className="animate-spin rounded-full h-10 w-10 border-4 border-mint-600 border-t-transparent" /></div>
      ) : data?.transactions.length === 0 ? (
        <div className="card text-center py-16">
          <ArrowLeftRight className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-500 mb-2">No transactions found</h2>
          <p className="text-gray-400">Link an account and sync to see transactions</p>
        </div>
      ) : (
        <div className="card p-0 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider px-6 py-4">Merchant</th>
                <th className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider px-6 py-4">Category</th>
                <th className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wider px-6 py-4">Date</th>
                <th className="text-right text-xs font-semibold text-gray-500 uppercase tracking-wider px-6 py-4">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {data?.transactions.map((txn) => (
                <tr key={txn.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-4">
                    <p className="font-medium text-gray-900">{txn.merchant || txn.description}</p>
                    {txn.merchant && <p className="text-xs text-gray-400 truncate max-w-xs">{txn.description}</p>}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`text-xs font-medium px-2 py-1 rounded-full ${CATEGORY_COLORS[txn.category] ?? "bg-gray-100 text-gray-600"}`}>
                      {txn.category}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {format(new Date(txn.transaction_date), "MMM d, yyyy")}
                  </td>
                  <td className={`px-6 py-4 text-right font-semibold text-sm ${txn.amount < 0 ? "text-red-500" : "text-mint-600"}`}>
                    {txn.amount < 0 ? "-" : "+"}{fmt(txn.amount)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {totalPages > 1 && (
            <div className="flex items-center justify-between px-6 py-4 border-t border-gray-100">
              <p className="text-sm text-gray-500">
                Page {page} of {totalPages} · {data?.total} transactions
              </p>
              <div className="flex gap-2">
                <button onClick={() => setPage((p) => p - 1)} disabled={page === 1} className="btn-secondary p-2 disabled:opacity-40">
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button onClick={() => setPage((p) => p + 1)} disabled={page === totalPages} className="btn-secondary p-2 disabled:opacity-40">
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
