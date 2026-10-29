import type { Lead, LeadActivity, Stage } from "./types";

const DAY_SECONDS = 86_400;
const OUTBOUND_KINDS = new Set<LeadActivity["kind"]>([
  "whatsapp",
  "call",
  "email",
]);
const INTERACTION_KINDS = new Set<LeadActivity["kind"]>([
  "whatsapp",
  "call",
  "email",
  "meeting",
  "proposal",
  "reply",
]);

export type ClosedHistoryRecord = {
  leadId: string;
  outcome: "won" | "lost";
  pipelineAt: number;
  closedAt: number;
  cycleDays: number | null;
  firstContactDays: number | null;
  interactions: number;
  outboundContacts: number;
  followUps: number;
  hasProposal: boolean;
  hasMeeting: boolean;
  hasReply: boolean;
  fastFirstContact: boolean;
  lossFromStage: Stage | "unknown" | null;
  activityLoaded: boolean;
};

export type OutcomeBehavior = {
  count: number;
  medianCycleDays: number | null;
  medianFirstContactDays: number | null;
  medianInteractions: number | null;
  medianFollowUps: number | null;
};

export type HistoryPatternKey =
  | "proposal"
  | "meeting"
  | "reply"
  | "follow_up"
  | "fast_first_contact";

export type HistoryPattern = {
  key: HistoryPatternKey;
  wonRate: number;
  lostRate: number;
  deltaPp: number;
  wonMatches: number;
  lostMatches: number;
  wonSample: number;
  lostSample: number;
};

export type LossStageSummary = {
  stage: Stage | "unknown";
  count: number;
  share: number;
};

export type HistoryIntelligence = {
  closedCount: number;
  wonCount: number;
  lostCount: number;
  activityCoverage: number;
  ready: boolean;
  won: OutcomeBehavior;
  lost: OutcomeBehavior;
  patterns: HistoryPattern[];
  lossStages: LossStageSummary[];
  records: ClosedHistoryRecord[];
};

function round1(value: number) {
  return Math.round(value * 10) / 10;
}

function percentage(value: number, total: number) {
  return total ? Math.round((value / total) * 100) : 0;
}

function median(values: Array<number | null>) {
  const sorted = values
    .filter((value): value is number => value !== null && Number.isFinite(value))
    .sort((a, b) => a - b);
  if (!sorted.length) return null;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2
    ? round1(sorted[middle])
    : round1((sorted[middle - 1] + sorted[middle]) / 2);
}

function daysBetween(start: number, end: number) {
  if (!start || !end || end < start) return null;
  return round1((end - start) / DAY_SECONDS);
}

function stageValue(value: unknown): Stage | "unknown" {
  return ["discovered", "contacted", "replied", "negotiating", "won", "lost"].includes(
    String(value),
  )
    ? (value as Stage)
    : "unknown";
}

function closeActivity(lead: Lead, activities: LeadActivity[]) {
  const ascending = [...activities].sort((a, b) => a.created_at - b.created_at);
  if (lead.stage === "won") {
    return [...ascending].reverse().find((item) => item.kind === "sale_won");
  }
  return [...ascending]
    .reverse()
    .find(
      (item) =>
        item.kind === "stage_changed" && String(item.metadata.to || "") === "lost",
    );
}

export function buildClosedHistoryRecord(
  lead: Lead,
  activities: LeadActivity[],
  activityLoaded = true,
): ClosedHistoryRecord | null {
  if (lead.stage !== "won" && lead.stage !== "lost") return null;
  const ascending = [...activities].sort((a, b) => a.created_at - b.created_at);
  const close = closeActivity(lead, ascending);
  const closedAt =
    close?.created_at ||
    ascending.at(-1)?.created_at ||
    lead.last_contact_at ||
    lead.pipeline_added_at ||
    lead.created_at;
  const pipelineActivity = ascending.find((item) => item.kind === "pipeline_added");
  const pipelineAt = pipelineActivity?.created_at || lead.pipeline_added_at || lead.created_at;
  const beforeClose = ascending.filter((item) => item.created_at <= closedAt);
  const interactions = beforeClose.filter((item) => INTERACTION_KINDS.has(item.kind));
  const outbound = interactions.filter((item) => OUTBOUND_KINDS.has(item.kind));
  const firstContact = outbound[0];
  const lossEvent =
    lead.stage === "lost"
      ? [...beforeClose]
          .reverse()
          .find(
            (item) =>
              item.kind === "stage_changed" &&
              String(item.metadata.to || "") === "lost",
          )
      : undefined;

  return {
    leadId: lead.id,
    outcome: lead.stage,
    pipelineAt,
    closedAt,
    cycleDays: daysBetween(pipelineAt, closedAt),
    firstContactDays: firstContact
      ? daysBetween(pipelineAt, firstContact.created_at)
      : null,
    interactions: interactions.length,
    outboundContacts: outbound.length,
    followUps: Math.max(0, outbound.length - 1),
    hasProposal: interactions.some((item) => item.kind === "proposal"),
    hasMeeting: interactions.some((item) => item.kind === "meeting"),
    hasReply: interactions.some((item) => item.kind === "reply"),
    fastFirstContact: Boolean(
      firstContact && daysBetween(pipelineAt, firstContact.created_at) !== null &&
        (daysBetween(pipelineAt, firstContact.created_at) as number) <= 1,
    ),
    lossFromStage:
      lead.stage === "lost"
        ? stageValue(lossEvent?.metadata.from)
        : null,
    activityLoaded,
  };
}

function behavior(records: ClosedHistoryRecord[]): OutcomeBehavior {
  return {
    count: records.length,
    medianCycleDays: median(records.map((item) => item.cycleDays)),
    medianFirstContactDays: median(records.map((item) => item.firstContactDays)),
    medianInteractions: median(records.map((item) => item.interactions)),
    medianFollowUps: median(records.map((item) => item.followUps)),
  };
}

const patternChecks: Array<[
  HistoryPatternKey,
  (record: ClosedHistoryRecord) => boolean,
]> = [
  ["proposal", (record) => record.hasProposal],
  ["meeting", (record) => record.hasMeeting],
  ["reply", (record) => record.hasReply],
  ["follow_up", (record) => record.followUps > 0],
  ["fast_first_contact", (record) => record.fastFirstContact],
];

export function buildHistoryIntelligence(
  leads: Lead[],
  activitiesByLead: Record<string, LeadActivity[] | undefined>,
): HistoryIntelligence {
  const closed = leads.filter((lead) => lead.stage === "won" || lead.stage === "lost");
  const records = closed
    .map((lead) =>
      buildClosedHistoryRecord(
        lead,
        activitiesByLead[lead.id] || [],
        activitiesByLead[lead.id] !== undefined,
      ),
    )
    .filter((item): item is ClosedHistoryRecord => Boolean(item));
  const loaded = records.filter((item) => item.activityLoaded);
  const won = loaded.filter((item) => item.outcome === "won");
  const lost = loaded.filter((item) => item.outcome === "lost");

  const patterns = patternChecks
    .map(([key, predicate]) => {
      const wonMatches = won.filter(predicate).length;
      const lostMatches = lost.filter(predicate).length;
      const wonRate = percentage(wonMatches, won.length);
      const lostRate = percentage(lostMatches, lost.length);
      return {
        key,
        wonRate,
        lostRate,
        deltaPp: wonRate - lostRate,
        wonMatches,
        lostMatches,
        wonSample: won.length,
        lostSample: lost.length,
      } satisfies HistoryPattern;
    })
    .filter((item) => item.wonSample >= 2 && item.lostSample >= 2)
    .sort((a, b) => Math.abs(b.deltaPp) - Math.abs(a.deltaPp));

  const lossStageCounts = new Map<Stage | "unknown", number>();
  lost.forEach((record) => {
    const stage = record.lossFromStage || "unknown";
    lossStageCounts.set(stage, (lossStageCounts.get(stage) || 0) + 1);
  });
  const lossStages = [...lossStageCounts.entries()]
    .map(([stage, count]) => ({
      stage,
      count,
      share: percentage(count, lost.length),
    }))
    .sort((a, b) => b.count - a.count);

  return {
    closedCount: records.length,
    wonCount: records.filter((item) => item.outcome === "won").length,
    lostCount: records.filter((item) => item.outcome === "lost").length,
    activityCoverage: percentage(loaded.length, records.length),
    ready: loaded.length >= 6 && won.length >= 2 && lost.length >= 2,
    won: behavior(won),
    lost: behavior(lost),
    patterns,
    lossStages,
    records,
  };
}
