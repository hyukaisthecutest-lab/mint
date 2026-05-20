import client from "./client";
import type { Account } from "../types";

export const getAccounts = () => client.get<Account[]>("/accounts").then((r) => r.data);

export const linkAccount = (data: { name: string; institution: string; account_type: string; initial_balance?: number }) =>
  client.post<Account>("/accounts", data).then((r) => r.data);

export const unlinkAccount = (id: string) => client.delete(`/accounts/${id}`);

export const syncAccount = (id: string) =>
  client.post<{ task_id: string; message: string }>(`/accounts/${id}/sync`).then((r) => r.data);

export const syncAllAccounts = () =>
  client.post<{ task_id: string; message: string }[]>("/accounts/sync-all").then((r) => r.data);
