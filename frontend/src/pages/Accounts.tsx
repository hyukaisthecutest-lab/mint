import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { getAccounts, linkAccount, unlinkAccount, syncAccount } from "../api/accounts";
import { Building2, Plus, RefreshCw, Trash2, X } from "lucide-react";

const schema = z.object({
  name: z.string().min(1, "Account name required"),
  institution: z.string().min(1, "Institution required"),
  account_type: z.enum(["checking", "savings", "credit"]),
  initial_balance: z.coerce.number().default(0),
});
type FormData = z.infer<typeof schema>;

const INSTITUTIONS = ["Chase", "Bank of America", "Wells Fargo", "Citibank", "Capital One", "TD Bank", "US Bank", "Other"];
const ACCOUNT_TYPE_COLORS: Record<string, string> = {
  checking: "bg-blue-100 text-blue-700",
  savings: "bg-mint-100 text-mint-700",
  credit: "bg-orange-100 text-orange-700",
};

function fmt(n: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
}

export default function Accounts() {
  const [showModal, setShowModal] = useState(false);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const qc = useQueryClient();
  const { data: accounts = [], isLoading } = useQuery({ queryKey: ["accounts"], queryFn: getAccounts });

  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { account_type: "checking", initial_balance: 0 },
  });

  const linkMut = useMutation({
    mutationFn: linkAccount,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["accounts"] }); setShowModal(false); reset(); },
  });

  const unlinkMut = useMutation({
    mutationFn: unlinkAccount,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  });

  const handleSync = async (id: string) => {
    setSyncingId(id);
    try {
      await syncAccount(id);
      setTimeout(() => { qc.invalidateQueries({ queryKey: ["accounts"] }); setSyncingId(null); }, 3000);
    } catch { setSyncingId(null); }
  };

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Accounts</h1>
          <p className="text-gray-500 mt-1">{accounts.length} linked account{accounts.length !== 1 ? "s" : ""}</p>
        </div>
        <button onClick={() => setShowModal(true)} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" /> Link Account
        </button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16"><div className="animate-spin rounded-full h-10 w-10 border-4 border-mint-600 border-t-transparent" /></div>
      ) : accounts.length === 0 ? (
        <div className="card text-center py-16">
          <Building2 className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-500 mb-2">No accounts linked</h2>
          <p className="text-gray-400 mb-6">Link your bank account to start tracking finances</p>
          <button onClick={() => setShowModal(true)} className="btn-primary mx-auto flex items-center gap-2 w-fit">
            <Plus className="w-4 h-4" /> Link Your First Account
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {accounts.map((acct) => (
            <div key={acct.id} className="card flex flex-col gap-4">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-semibold text-gray-900">{acct.name}</p>
                  <p className="text-sm text-gray-400">{acct.institution}</p>
                </div>
                <span className={`text-xs font-medium px-2 py-1 rounded-full ${ACCOUNT_TYPE_COLORS[acct.account_type] ?? "bg-gray-100 text-gray-600"}`}>
                  {acct.account_type}
                </span>
              </div>
              <div>
                <p className="text-sm text-gray-400">Balance</p>
                <p className={`text-3xl font-bold ${Number(acct.balance) < 0 ? "text-red-500" : "text-gray-900"}`}>
                  {fmt(Number(acct.balance))}
                </p>
              </div>
              <div className="flex gap-2 mt-auto">
                <button
                  onClick={() => handleSync(acct.id)}
                  disabled={syncingId === acct.id}
                  className="btn-secondary flex-1 flex items-center justify-center gap-2 text-sm py-2"
                >
                  <RefreshCw className={`w-4 h-4 ${syncingId === acct.id ? "animate-spin" : ""}`} />
                  {syncingId === acct.id ? "Syncing..." : "Sync"}
                </button>
                <button
                  onClick={() => unlinkMut.mutate(acct.id)}
                  className="p-2 rounded-lg text-red-400 hover:bg-red-50 transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-8">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-gray-900">Link Account</h2>
              <button onClick={() => { setShowModal(false); reset(); }} className="text-gray-400 hover:text-gray-600">
                <X className="w-6 h-6" />
              </button>
            </div>
            <form onSubmit={handleSubmit((d) => linkMut.mutate(d))} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Account Name</label>
                <input {...register("name")} className="input" placeholder="My Checking Account" />
                {errors.name && <p className="text-red-500 text-sm mt-1">{errors.name.message}</p>}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Institution</label>
                <select {...register("institution")} className="input">
                  <option value="">Select institution</option>
                  {INSTITUTIONS.map((i) => <option key={i} value={i}>{i}</option>)}
                </select>
                {errors.institution && <p className="text-red-500 text-sm mt-1">{errors.institution.message}</p>}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Account Type</label>
                <select {...register("account_type")} className="input">
                  <option value="checking">Checking</option>
                  <option value="savings">Savings</option>
                  <option value="credit">Credit Card</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Initial Balance ($)</label>
                <input {...register("initial_balance")} type="number" step="0.01" className="input" placeholder="0.00" />
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => { setShowModal(false); reset(); }} className="btn-secondary flex-1">Cancel</button>
                <button type="submit" disabled={isSubmitting || linkMut.isPending} className="btn-primary flex-1">
                  {linkMut.isPending ? "Linking..." : "Link Account"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
