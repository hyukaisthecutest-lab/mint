import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getTransactions, scanReceipt, submitBulkScan, pollScanResult, createTransaction, ScannedReceipt, ReceiptLineItem } from "../api/transactions";
import { getAccounts } from "../api/accounts";
import { ArrowLeftRight, ChevronLeft, ChevronRight, ScanLine, X, Upload, Loader2, Files, CheckCircle2, AlertCircle, Trash2 } from "lucide-react";
import { format } from "date-fns";

const CATEGORIES = ["All", "Food & Drink", "Groceries", "Shopping", "Entertainment", "Transportation", "Bills & Utilities", "Health & Fitness", "Income", "Transfer", "Other"];
const CREATE_CATEGORIES = CATEGORIES.slice(1);

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

interface ReceiptModalProps {
  onClose: () => void;
  accounts: { id: string; name: string }[];
  onSaved: () => void;
}

function ReceiptModal({ onClose, accounts, onSaved }: ReceiptModalProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [scanning, setScanning] = useState(false);
  const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [scanned, setScanned] = useState<ScannedReceipt | null>(null);
  const [form, setForm] = useState({
    merchant: "", amount: "", description: "", category: "Shopping",
    transaction_date: format(new Date(), "yyyy-MM-dd"), account_id: accounts[0]?.id ?? "",
  });
  const [error, setError] = useState("");

  const handleFile = async (file: File) => {
    setError("");
    setPreview(URL.createObjectURL(file));
    setScanning(true);
    try {
      const data = await scanReceipt(file);
      setScanned(data);
      setForm((f) => ({
        ...f,
        merchant: data.merchant ?? "",
        amount: data.amount != null ? String(Math.abs(data.amount)) : "",
        description: data.description,
        category: data.category || "Shopping",
        transaction_date: data.transaction_date ?? f.transaction_date,
      }));
    } catch {
      setError("Could not read receipt. Please try a clearer image.");
    } finally {
      setScanning(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const handleSave = async () => {
    if (!form.account_id || !form.amount || !form.transaction_date) {
      setError("Account, amount and date are required.");
      return;
    }
    setSaving(true);
    try {
      await createTransaction({
        account_id: form.account_id,
        amount: -Math.abs(parseFloat(form.amount)),
        description: form.description || form.merchant || "Cash purchase",
        category: form.category,
        merchant: form.merchant || undefined,
        transaction_date: form.transaction_date,
      });
      onSaved();
      onClose();
    } catch {
      setError("Failed to save transaction. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <ScanLine className="w-5 h-5 text-mint-600" />
            <h2 className="text-lg font-semibold text-gray-900">Scan Receipt</h2>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded-lg">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {/* Upload area */}
          <div
            className="border-2 border-dashed border-gray-200 rounded-xl p-6 text-center cursor-pointer hover:border-mint-400 hover:bg-mint-50/30 transition-colors"
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            onClick={() => fileRef.current?.click()}
          >
            <input
              ref={fileRef}
              type="file"
              accept="image/jpeg,image/png,application/pdf"
              className="hidden"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
            />
            {scanning ? (
              <div className="flex flex-col items-center gap-2 text-mint-600">
                <Loader2 className="w-8 h-8 animate-spin" />
                <p className="text-sm font-medium">Scanning with AWS Textract…</p>
              </div>
            ) : preview ? (
              <img src={preview} alt="Receipt" className="max-h-40 mx-auto rounded-lg object-contain" />
            ) : (
              <div className="flex flex-col items-center gap-2 text-gray-400">
                <Upload className="w-8 h-8" />
                <p className="text-sm font-medium">Drop receipt or bill here or click to upload</p>
                <p className="text-xs">JPEG, PNG, PDF · Max 10 MB</p>
              </div>
            )}
          </div>

          {error && <p className="text-sm text-red-500">{error}</p>}

          {/* Line items extracted from receipt */}
          {scanned && scanned.items.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-600 mb-2">Items on receipt</p>
              <div className="border border-gray-100 rounded-lg overflow-hidden">
                <table className="w-full text-xs">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="text-left px-3 py-2 text-gray-500 font-medium">Item</th>
                      <th className="text-right px-3 py-2 text-gray-500 font-medium">Qty</th>
                      <th className="text-right px-3 py-2 text-gray-500 font-medium">Price</th>
                      <th className="text-right px-3 py-2 text-gray-500 font-medium">Total</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {scanned.items.map((item: ReceiptLineItem, i: number) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="px-3 py-2 text-gray-800">{item.name}</td>
                        <td className="px-3 py-2 text-right text-gray-500">{item.quantity ?? "—"}</td>
                        <td className="px-3 py-2 text-right text-gray-500">{item.unit_price != null ? `$${item.unit_price.toFixed(2)}` : "—"}</td>
                        <td className="px-3 py-2 text-right font-medium text-gray-800">{item.total != null ? `$${item.total.toFixed(2)}` : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                  {(scanned.tax != null || scanned.tip != null) && (
                    <tfoot className="bg-gray-50 border-t border-gray-100">
                      {scanned.tax != null && (
                        <tr>
                          <td colSpan={3} className="px-3 py-1.5 text-gray-500">Tax</td>
                          <td className="px-3 py-1.5 text-right text-gray-600">${scanned.tax.toFixed(2)}</td>
                        </tr>
                      )}
                      {scanned.tip != null && scanned.tip > 0 && (
                        <tr>
                          <td colSpan={3} className="px-3 py-1.5 text-gray-500">Tip</td>
                          <td className="px-3 py-1.5 text-right text-gray-600">${scanned.tip.toFixed(2)}</td>
                        </tr>
                      )}
                      <tr className="font-semibold">
                        <td colSpan={3} className="px-3 py-2 text-gray-700">Total</td>
                        <td className="px-3 py-2 text-right text-gray-900">${form.amount || "—"}</td>
                      </tr>
                    </tfoot>
                  )}
                </table>
              </div>
            </div>
          )}

          {/* Editable fields — shown after scan or always */}
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Merchant</label>
                <input className="input text-sm" value={form.merchant} onChange={(e) => setForm((f) => ({ ...f, merchant: e.target.value }))} placeholder="e.g. Starbucks" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Amount (USD)</label>
                <input className="input text-sm" type="number" step="0.01" min="0" value={form.amount} onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))} placeholder="0.00" />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Description</label>
              <input className="input text-sm" value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} placeholder="What did you buy?" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Category</label>
                <select className="input text-sm" value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}>
                  {CREATE_CATEGORIES.map((c) => <option key={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Date</label>
                <input className="input text-sm" type="date" value={form.transaction_date} onChange={(e) => setForm((f) => ({ ...f, transaction_date: e.target.value }))} />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Account</label>
              <select className="input text-sm" value={form.account_id} onChange={(e) => setForm((f) => ({ ...f, account_id: e.target.value }))}>
                {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
            </div>
          </div>
        </div>

        <div className="flex gap-3 p-6 pt-0">
          <button onClick={onClose} className="btn-secondary flex-1">Cancel</button>
          <button
            onClick={handleSave}
            disabled={saving || scanning || !form.amount}
            className="btn-primary flex-1 flex items-center justify-center gap-2"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            Save Transaction
          </button>
        </div>
      </div>
    </div>
  );
}

interface BillRow {
  id: string;
  filename: string;
  preview: string;
  status: "scanning" | "done" | "error";
  error?: string;
  merchant: string;
  amount: string;
  description: string;
  category: string;
  transaction_date: string;
  selected: boolean;
}

interface BulkModalProps {
  onClose: () => void;
  accounts: { id: string; name: string }[];
  onSaved: () => void;
}

function BulkReceiptModal({ onClose, accounts, onSaved }: BulkModalProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [rows, setRows] = useState<BillRow[]>([]);
  const [accountId, setAccountId] = useState(accounts[0]?.id ?? "");
  const [saving, setSaving] = useState(false);
  const [globalError, setGlobalError] = useState("");

  const processFiles = async (files: File[]) => {
    const today = format(new Date(), "yyyy-MM-dd");
    const newRows: BillRow[] = files.map((f, i) => ({
      id: `${Date.now()}-${i}`,
      filename: f.name,
      preview: URL.createObjectURL(f),
      status: "scanning",
      merchant: "", amount: "", description: "",
      category: "Shopping", transaction_date: today,
      selected: true,
    }));
    setRows((r) => [...r, ...newRows]);

    // Submit all files at once — backend queues Celery tasks immediately
    const jobs = await submitBulkScan(files);

    // Poll each job independently so rows update as they finish
    jobs.forEach((job, i) => {
      const rowId = newRows[i].id;
      if (!job.job_id) {
        setRows((r) => r.map((row) => row.id === rowId
          ? { ...row, status: "error", error: job.error ?? "Upload failed" } : row));
        return;
      }
      const poll = async () => {
        for (let attempt = 0; attempt < 40; attempt++) {
          await new Promise((res) => setTimeout(res, 3000));
          const result = await pollScanResult(job.job_id!);
          if (result.status === "pending") continue;
          setRows((r) => r.map((row) => {
            if (row.id !== rowId) return row;
            if (result.status === "error" || !result.data) {
              return { ...row, status: "error", error: result.error ?? "Scan failed" };
            }
            const d = result.data;
            return {
              ...row, status: "done",
              merchant: d.merchant ?? "",
              amount: d.amount != null ? String(Math.abs(d.amount)) : "",
              description: d.description ?? "",
              category: d.category ?? "Shopping",
              transaction_date: d.transaction_date ?? today,
            };
          }));
          return;
        }
        setRows((r) => r.map((row) => row.id === rowId
          ? { ...row, status: "error", error: "Timed out" } : row));
      };
      poll();
    });
  };

  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const arr = Array.from(files).filter((f) => ["image/jpeg", "image/png", "application/pdf"].includes(f.type));
    if (arr.length === 0) return;
    processFiles(arr);
  };

  const updateRow = (id: string, patch: Partial<BillRow>) =>
    setRows((r) => r.map((row) => (row.id === id ? { ...row, ...patch } : row)));

  const removeRow = (id: string) => setRows((r) => r.filter((row) => row.id !== id));

  const selectedRows = rows.filter((r) => r.selected && r.status === "done" && r.amount);
  const scanning = rows.some((r) => r.status === "scanning");

  const handleSaveAll = async () => {
    if (!accountId) { setGlobalError("Please select an account."); return; }
    setSaving(true);
    setGlobalError("");
    try {
      await Promise.all(selectedRows.map((row) =>
        createTransaction({
          account_id: accountId,
          amount: -Math.abs(parseFloat(row.amount)),
          description: row.description || row.merchant || "Cash purchase",
          category: row.category,
          merchant: row.merchant || undefined,
          transaction_date: row.transaction_date,
        })
      ));
      onSaved();
      onClose();
    } catch {
      setGlobalError("Some transactions failed to save. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-100 flex-shrink-0">
          <div className="flex items-center gap-2">
            <Files className="w-5 h-5 text-mint-600" />
            <h2 className="text-lg font-semibold text-gray-900">Upload Bills</h2>
            {rows.length > 0 && <span className="text-sm text-gray-400">{rows.length} file{rows.length > 1 ? "s" : ""}</span>}
          </div>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded-lg">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {/* Drop zone */}
          <div
            className="border-2 border-dashed border-gray-200 rounded-xl p-6 text-center cursor-pointer hover:border-mint-400 hover:bg-mint-50/30 transition-colors"
            onDrop={(e) => { e.preventDefault(); handleFiles(e.dataTransfer.files); }}
            onDragOver={(e) => e.preventDefault()}
            onClick={() => fileRef.current?.click()}
          >
            <input ref={fileRef} type="file" accept="image/jpeg,image/png,application/pdf" multiple className="hidden" onChange={(e) => handleFiles(e.target.files)} />
            <Upload className="w-7 h-7 mx-auto mb-2 text-gray-300" />
            <p className="text-sm font-medium text-gray-500">Drop receipts or bills here or click to select</p>
            <p className="text-xs text-gray-400 mt-1">JPEG, PNG, PDF · Max 10 MB each · Up to 20 files</p>
          </div>

          {/* Bill rows */}
          {rows.length > 0 && (
            <div className="space-y-3">
              {rows.map((row) => (
                <div key={row.id} className={`border rounded-xl p-4 ${row.selected && row.status === "done" ? "border-mint-200 bg-mint-50/20" : "border-gray-100 bg-gray-50"}`}>
                  <div className="flex items-start gap-4">
                    {/* Thumbnail */}
                    <img src={row.preview} alt={row.filename} className="w-16 h-16 object-cover rounded-lg flex-shrink-0 border border-gray-200" />

                    {/* Status / fields */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        {row.status === "scanning" && <Loader2 className="w-4 h-4 animate-spin text-mint-600" />}
                        {row.status === "done" && <CheckCircle2 className="w-4 h-4 text-green-500" />}
                        {row.status === "error" && <AlertCircle className="w-4 h-4 text-red-400" />}
                        <span className="text-xs font-medium text-gray-600 truncate">{row.filename}</span>
                        {row.status === "error" && <span className="text-xs text-red-400">{row.error}</span>}
                        {row.status === "scanning" && <span className="text-xs text-gray-400">Scanning…</span>}
                      </div>

                      {row.status === "done" && (
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                          <input className="input text-xs py-1.5" placeholder="Merchant" value={row.merchant} onChange={(e) => updateRow(row.id, { merchant: e.target.value })} />
                          <input className="input text-xs py-1.5" type="number" placeholder="Amount" min="0" step="0.01" value={row.amount} onChange={(e) => updateRow(row.id, { amount: e.target.value })} />
                          <input className="input text-xs py-1.5" type="date" value={row.transaction_date} onChange={(e) => updateRow(row.id, { transaction_date: e.target.value })} />
                          <input className="input text-xs py-1.5 col-span-2" placeholder="Description" value={row.description} onChange={(e) => updateRow(row.id, { description: e.target.value })} />
                          <select className="input text-xs py-1.5" value={row.category} onChange={(e) => updateRow(row.id, { category: e.target.value })}>
                            {CREATE_CATEGORIES.map((c) => <option key={c}>{c}</option>)}
                          </select>
                        </div>
                      )}
                    </div>

                    {/* Select / remove */}
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {row.status === "done" && (
                        <input type="checkbox" checked={row.selected} onChange={(e) => updateRow(row.id, { selected: e.target.checked })} className="w-4 h-4 accent-mint-600" title="Include in save" />
                      )}
                      <button onClick={() => removeRow(row.id)} className="p-1 hover:bg-red-50 rounded text-gray-300 hover:text-red-400 transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {globalError && <p className="text-sm text-red-500">{globalError}</p>}
        </div>

        {/* Footer */}
        <div className="flex items-center gap-4 p-6 border-t border-gray-100 flex-shrink-0">
          <div className="flex-1">
            <select className="input text-sm" value={accountId} onChange={(e) => setAccountId(e.target.value)}>
              {accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          </div>
          <button onClick={onClose} className="btn-secondary px-4">Cancel</button>
          <button
            onClick={handleSaveAll}
            disabled={saving || scanning || selectedRows.length === 0}
            className="btn-primary flex items-center gap-2 px-5"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            Save {selectedRows.length > 0 ? `${selectedRows.length} ` : ""}Transaction{selectedRows.length !== 1 ? "s" : ""}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function Transactions() {
  const [page, setPage] = useState(1);
  const [category, setCategory] = useState("");
  const [accountId, setAccountId] = useState("");
  const [showScan, setShowScan] = useState(false);
  const [showBulk, setShowBulk] = useState(false);
  const PAGE_SIZE = 20;
  const queryClient = useQueryClient();

  const { data: accounts = [] } = useQuery({ queryKey: ["accounts"], queryFn: getAccounts });
  const { data, isLoading } = useQuery({
    queryKey: ["transactions", page, category, accountId],
    queryFn: () => getTransactions({ page, page_size: PAGE_SIZE, category: category || undefined, account_id: accountId || undefined }),
  });

  const totalPages = Math.ceil((data?.total ?? 0) / PAGE_SIZE);

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Transactions</h1>
          <p className="text-gray-500 mt-1">{data?.total ?? 0} total transactions</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowScan(true)} className="btn-secondary flex items-center gap-2">
            <ScanLine className="w-4 h-4" />
            Scan Receipt
          </button>
          <button onClick={() => setShowBulk(true)} className="btn-primary flex items-center gap-2">
            <Files className="w-4 h-4" />
            Upload Bills
          </button>
        </div>
      </div>

      {showScan && (
        <ReceiptModal
          accounts={accounts}
          onClose={() => setShowScan(false)}
          onSaved={() => queryClient.invalidateQueries({ queryKey: ["transactions"] })}
        />
      )}
      {showBulk && (
        <BulkReceiptModal
          accounts={accounts}
          onClose={() => setShowBulk(false)}
          onSaved={() => queryClient.invalidateQueries({ queryKey: ["transactions"] })}
        />
      )}

      <div className="card mb-6">
        <div className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-48">
            <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
            <select className="input" value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }}>
              {CATEGORIES.map((c) => <option key={c} value={c === "All" ? "" : c}>{c}</option>)}
            </select>
          </div>
          <div className="flex-1 min-w-48">
            <label className="block text-sm font-medium text-gray-700 mb-1">Account</label>
            <select className="input" value={accountId} onChange={(e) => { setAccountId(e.target.value); setPage(1); }}>
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
          <p className="text-gray-400">Link an account or scan a receipt to get started</p>
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
              <p className="text-sm text-gray-500">Page {page} of {totalPages} · {data?.total} transactions</p>
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
