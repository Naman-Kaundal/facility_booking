import { API_BASE_URL, apiGet, apiRequest } from "./client";
import type { AuthConfig, Me } from "../types/user";

/** Full-page navigation target that starts Google sign-in on the backend. */
export const GOOGLE_SIGN_IN_URL = `${API_BASE_URL}/auth/google`;

export const fetchMe = () => apiGet<Me>("/users/me");
export const fetchAuthConfig = () => apiGet<AuthConfig>("/auth/config");
export const logout = () => apiRequest<void>("POST", "/auth/logout");
export const devLogin = (email: string, name: string) => apiRequest<Me>("POST", "/auth/dev-login", { email, name });
export const setRateCategory = (rate_category: "GOVT" | "PRIVATE") =>
  apiRequest<Me>("PUT", "/users/me/rate-category", { rate_category });
