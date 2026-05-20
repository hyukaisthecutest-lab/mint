import client from "./client";
import type { DashboardData } from "../types";

export const getDashboard = () => client.get<DashboardData>("/dashboard").then((r) => r.data);
