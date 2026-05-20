export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  is_admin: boolean;
}

export interface Account {
  id: string;
  name: string;
  institution: string;
  account_type: string;
  balance: number;
  external_account_id: string;
  is_active: boolean;
  created_at: string;
}

export interface Transaction {
  id: string;
  account_id: string;
  amount: number;
  description: string;
  category: string;
  merchant: string | null;
  transaction_date: string;
  created_at: string;
}

export interface TransactionListResponse {
  transactions: Transaction[];
  total: number;
  page: number;
  page_size: number;
}

export interface SpendingByCategory {
  category: string;
  total: number;
  count: number;
}

export interface DashboardData {
  total_balance: number;
  monthly_spending: number;
  monthly_income: number;
  spending_by_category: SpendingByCategory[];
  recent_transactions: Transaction[];
}
