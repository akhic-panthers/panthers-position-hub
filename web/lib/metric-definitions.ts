// Scout-readable definitions for every number the position hub shows. Deployment metrics: "higher" is never
// "better" here, so no direction is set; a share says how much of a job, not how well.
export type MetricDirection = "higher" | "lower" | "neutral";
export type MetricDefinition = { label: string; short: string; description: string; direction?: MetricDirection };

const DEFS: Record<string, MetricDefinition> = {
  snaps: { label: "Snaps", short: "Defensive snaps on run and pass plays", description: "Every run and pass snap he was on the field for in the tracking. Penalties, kneels and spikes are not counted." },
  role_mix: { label: "Role mix", short: "Where he lined up, snap by snap", description: "For every snap, the model reads where he stood when the ball was snapped and gives the chance a PFF charter would call that snap each job. The mix is the average over his snaps." },
  jobs: { label: "Jobs", short: "How many different jobs he did", description: "Entropy of his role mix. 0 means the same spot every snap; 1.0 is about three jobs split evenly; above 1.6 he plays all over the defense." },
  depth: { label: "Depth", short: "Average yards off the ball at the snap", description: "Measured from the snapper, so it runs about 0.6 yards deeper than the league's line-of-scrimmage depth." },
  box: { label: "In the box", short: "Share of snaps inside the box", description: "Within 7 yards of the ball and inside the tackles plus a yard and a half." },
  pct: { label: "Percentile", short: "Against his position group, same season", description: "How much MORE of this job he did than other players at his position with at least 200 snaps. It rates deployment, not play." },
  call_explains: { label: "Call explains", short: "How much of his mix is the coverage call", description: "Share of the snap-to-snap variation in his deep alignment that PFF's one-high vs two-high call accounts for. Low means the mix is his, not the coordinator's call." },
  double_team: { label: "Double teamed", short: "Share of blocked snaps with two blockers on him", description: "From PFF's blocking chart: snaps where two or more offensive players blocked him." },
  unblocked: { label: "Unblocked", short: "Share of charted snaps nobody blocked him", description: "PFF's unblocked flag: never physically blocked and never had to evade a blocker." },
};
export function getMetricDefinition(key: string): MetricDefinition | undefined { return DEFS[key]; }
export function getMetricTip(key: string): string | undefined { return DEFS[key]?.description; }
