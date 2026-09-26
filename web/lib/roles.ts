// The v2 role vocabulary and its field colors. Roles are categorical, so the field needs eight distinguishable
// marks on dark ink; every color is paired with a legend label (identity is never color alone).
export const ROLES = ["EDGE", "INTERIOR_DL", "OFF_BALL_LB", "SLOT_CB", "BOUNDARY_CB", "BOX_SAFETY", "DEEP_HALF", "DEEP_MIDDLE"] as const;
export type Role = (typeof ROLES)[number];
export const ROLE_LABEL: Record<string, string> = {
  EDGE: "Edge", INTERIOR_DL: "Interior D-Line", OFF_BALL_LB: "Off-Ball Linebacker", SLOT_CB: "Slot", BOUNDARY_CB: "Boundary Corner",
  BOX_SAFETY: "Box Safety", DEEP_HALF: "Deep Half", DEEP_MIDDLE: "Post Safety",
};
export const ROLE_COLOR: Record<string, string> = {
  EDGE: "#F43F5E", INTERIOR_DL: "#F59E0B", OFF_BALL_LB: "#A78BFA", SLOT_CB: "#10B981", BOUNDARY_CB: "#1CA3E0",
  BOX_SAFETY: "#FB923C", DEEP_HALF: "#22D3EE", DEEP_MIDDLE: "#E6EAED",
};
export const RESP = ["RUSH", "RUN_FIT", "MAN", "MAN_MATCH", "UNDER_ZONE", "DEEP_ZONE"] as const;
export const RESP_LABEL: Record<string, string> = {
  RUSH: "Pass Rush", RUN_FIT: "Run Fit", MAN: "Man Coverage", MAN_MATCH: "Match (Zone Played As Man)", UNDER_ZONE: "Underneath Zone", DEEP_ZONE: "Deep Zone",
};
export const GROUP_LABEL: Record<string, string> = { S: "Safeties", CB: "Corners", LB: "Linebackers", EDGE: "Edge", IDL: "Interior Line", DB: "Defensive Backs" };
/** the roles each position group is read against, in the order a coach reads them */
export const GROUP_ROLES: Record<string, Role[]> = {
  S: ["DEEP_MIDDLE", "DEEP_HALF", "BOX_SAFETY", "SLOT_CB", "OFF_BALL_LB", "BOUNDARY_CB", "EDGE"],
  CB: ["BOUNDARY_CB", "SLOT_CB", "DEEP_HALF", "BOX_SAFETY", "OFF_BALL_LB"],
  LB: ["OFF_BALL_LB", "EDGE", "SLOT_CB", "BOX_SAFETY", "INTERIOR_DL"],
  EDGE: ["EDGE", "INTERIOR_DL", "OFF_BALL_LB"],
  IDL: ["INTERIOR_DL", "EDGE"],
  DB: ["BOUNDARY_CB", "SLOT_CB", "DEEP_HALF", "DEEP_MIDDLE", "BOX_SAFETY"],
};
export function ordinal(n: number): string {
  const v = Math.round(n), s = ["th", "st", "nd", "rd"], m = v % 100;
  return `${v}${s[(m - 20) % 10] || s[m] || s[0]}`;
}
export function downDistance(down: number | null, dist: string | number | null): string {
  if (!down) return "";
  const d = ["", "1st", "2nd", "3rd", "4th"][down] ?? `${down}th`;
  return dist == null || dist === "" ? d : `${d} and ${dist}`;
}
