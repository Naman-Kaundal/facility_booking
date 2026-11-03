import type { StaffRole } from "../../types/user";
import type { Desk } from "../../types/workflow";

export interface DeskInfo {
  desk: Desk;
  path: string;
  title: string;
  short: string;
  description: string;
}

export const DESKS: DeskInfo[] = [
  {
    desk: "FACILITY",
    path: "/desk/facilities",
    title: "Facilities desk",
    short: "Facilities",
    description: "Check new requests, then forward them to the sections or return them for correction.",
  },
  {
    desk: "ACADEMIC",
    path: "/desk/academic",
    title: "Academic desk",
    short: "Academic",
    description: "Confirm or reject lecture hall and auditorium bookings.",
  },
  {
    desk: "SPORTS",
    path: "/desk/sports",
    title: "Sports desk",
    short: "Sports",
    description: "Confirm or reject sports ground and court bookings.",
  },
];

export function desksFor(roles: StaffRole[] | undefined): DeskInfo[] {
  return DESKS.filter((d) => roles?.includes(d.desk));
}
