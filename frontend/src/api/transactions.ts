import client from "./client";
import type { TransactionListResponse } from "../types";

export const getTransactions = (params?: { page?: number; page_size?: number; category?: string; account_id?: string }) =>
  client.get<TransactionListResponse>("/transactions", { params }).then((r) => r.data);

export interface ReceiptLineItem {
  name: string;
  quantity: number | null;
  unit_price: number | null;
  total: number | null;
}

export interface ScannedReceipt {
  merchant: string | null;
  amount: number | null;
  description: string;
  category: string;
  transaction_date: string | null;
  tax: number | null;
  tip: number | null;
  items: ReceiptLineItem[];
}

export interface TransactionCreate {
  account_id: string;
  amount: number;
  description: string;
  category: string;
  merchant?: string;
  transaction_date: string;
}

export const scanReceipt = async (file: File): Promise<ScannedReceipt> => {
  const form = new FormData();
  form.append("image", file);
  const res = await client.post<ScannedReceipt>("/transactions/scan-receipt", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
};

export interface BulkJob {
  filename: string;
  job_id: string | null;
  error: string | null;
}

export const submitBulkScan = async (files: File[]): Promise<BulkJob[]> => {
  const form = new FormData();
  files.forEach((f) => form.append("images", f));
  const res = await client.post<{ jobs: BulkJob[] }>("/transactions/scan-receipts/bulk", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data.jobs;
};

export type JobStatus = "pending" | "done" | "error";

export const pollScanResult = async (jobId: string): Promise<{ status: JobStatus; data?: ScannedReceipt; error?: string }> => {
  const res = await client.get(`/transactions/scan-receipts/result/${jobId}`);
  return res.data;
};

export const createTransaction = async (data: TransactionCreate): Promise<void> => {
  await client.post("/transactions", data);
};
