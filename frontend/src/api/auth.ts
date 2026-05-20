import client from "./client";
import type { User } from "../types";

export const register = (data: { email: string; password: string; first_name: string; last_name: string }) =>
  client.post<{ access_token: string }>("/auth/register", data).then((r) => r.data);

export const login = (data: { email: string; password: string }) =>
  client.post<{ access_token: string }>("/auth/login", data).then((r) => r.data);

export const getMe = () => client.get<User>("/auth/me").then((r) => r.data);
