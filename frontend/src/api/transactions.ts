import client from "./client";
import type { TransactionListResponse } from "../types";

export const getTransactions = (params?: { page?: number; page_size?: number; category?: string; account_id?: string }) =>
  client.get<TransactionListResponse>("/transactions", { params }).then((r) => r.data);
