import type { RateCategory } from "./facility";

/** Staff roles granted by email (python -m app.db.grant_role). Requesters have none. */
export type StaffRole = "FACILITY" | "ACADEMIC" | "SPORTS" | "ESTATE" | "ADMIN";

export interface Me {
  id: number;
  email: string;
  name: string;
  rate_category: RateCategory | null;
  is_iit: boolean;
  needs_category: boolean;
  csrf_token: string;
  roles: StaffRole[];
}

export interface AuthConfig {
  google_enabled: boolean;
  dev_login_enabled: boolean;
}
