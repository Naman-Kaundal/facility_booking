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
    description: "Check new requests, forward or return them, and send the advance intimation once costed.",
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
  {
    desk: "ESTATE",
    path: "/desk/estate",
    title: "Estate desk",
    short: "Estate",
    description: "Enter the approximate electricity charge once every section has decided.",
  },
];

export function desksFor(roles: StaffRole[] | undefined): DeskInfo[] {
  return DESKS.filter((d) => roles?.includes(d.desk));
}
