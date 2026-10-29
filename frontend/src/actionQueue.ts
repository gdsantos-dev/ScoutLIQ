import type { Lead, Stage } from "./types";

export type ActionQueueBucket = "overdue" | "today" | "upcoming";
export type ActionQueueSource = "explicit" | "first_contact" | "stale";
export type ActionQueueReason =
  | { kind: "overdue"; days: number }
  | { kind: "today" }
  | { kind: "upcoming"; days: number }
  | { kind: "undated" }
  | { kind: "first_contact"; days: number }
  | { kind: "stale"; days: number }
  | { kind: "stage"; stage: Stage }
  | { kind: "score"; value: number };

export type ActionQueueItem = {
  lead: Lead;
  bucket: ActionQueueBucket;
  source: ActionQueueSource;
  action: string;
  dueOn: string | null;
  daysDelta: number;
  idleDays: number;
  priority: number;
  reasons: ActionQueueReason[];
};

const DAY = 86_400;
const FIRST_CONTACT_DAYS = 2;
const STALE_CONTACT_DAYS = 5;

const stagePriority: Record<Stage, number> = {
  discovered: 4,
  contacted: 9,
  replied: 14,
  negotiating: 18,
  won: 0,
  lost: 0,
};

function dateOrdinal(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return Math.floor(Date.UTC(year, month - 1, day) / 86_400_000);
}

function daysBetween(from: string, to: string) {
  return dateOrdinal(to) - dateOrdinal(from);
}

function daysSince(timestamp: number | null | undefined, nowSeconds: number) {
  if (!timestamp) return 0;
  return Math.max(0, Math.floor((nowSeconds - timestamp) / DAY));
}

export function buildActionQueue(
  leads: Lead[],
  today: string,
  nowSeconds = Math.floor(Date.now() / 1000),
): ActionQueueItem[] {
  return leads
    .filter(
      (lead) =>
        lead.in_pipeline && !["won", "lost"].includes(lead.stage),
    )
    .map((lead): ActionQueueItem | null => {
      const scoreWeight = Math.round(Math.max(0, lead.score.value) / 10);
      const stageWeight = stagePriority[lead.stage];
      const reference =
        lead.last_contact_at || lead.pipeline_added_at || lead.created_at;
      const idleDays = daysSince(reference, nowSeconds);

      if (lead.next_action) {
        if (!lead.next_action_on) {
          return {
            lead,
            bucket: "today",
            source: "explicit",
            action: lead.next_action,
            dueOn: null,
            daysDelta: 0,
            idleDays,
            priority: 74 + stageWeight + scoreWeight,
            reasons: [
              { kind: "undated" },
              { kind: "stage", stage: lead.stage },
              { kind: "score", value: lead.score.value },
            ],
          };
        }
        const delta = daysBetween(today, lead.next_action_on);
        const bucket: ActionQueueBucket =
          delta < 0 ? "overdue" : delta === 0 ? "today" : "upcoming";
        const urgency =
          bucket === "overdue"
            ? 88 + Math.min(12, Math.abs(delta) * 2)
            : bucket === "today"
              ? 80
              : Math.max(34, 58 - Math.min(24, delta));
        return {
          lead,
          bucket,
          source: "explicit",
          action: lead.next_action,
          dueOn: lead.next_action_on,
          daysDelta: delta,
          idleDays,
          priority: urgency + stageWeight + scoreWeight,
          reasons: [
            delta < 0
              ? { kind: "overdue", days: Math.abs(delta) }
              : delta === 0
                ? { kind: "today" }
                : { kind: "upcoming", days: delta },
            { kind: "stage", stage: lead.stage },
            { kind: "score", value: lead.score.value },
          ],
        };
      }

      if (!lead.last_contact_at && idleDays >= FIRST_CONTACT_DAYS) {
        return {
          lead,
          bucket: idleDays >= STALE_CONTACT_DAYS ? "overdue" : "today",
          source: "first_contact",
          action: "Fazer primeiro contato",
          dueOn: null,
          daysDelta: 0,
          idleDays,
          priority: 72 + Math.min(16, idleDays) + stageWeight + scoreWeight,
          reasons: [
            { kind: "first_contact", days: idleDays },
            { kind: "stage", stage: lead.stage },
            { kind: "score", value: lead.score.value },
          ],
        };
      }

      if (lead.last_contact_at && idleDays >= STALE_CONTACT_DAYS) {
        return {
          lead,
          bucket: "overdue",
          source: "stale",
          action: "Retomar contato",
          dueOn: null,
          daysDelta: 0,
          idleDays,
          priority: 78 + Math.min(18, idleDays - STALE_CONTACT_DAYS) + stageWeight + scoreWeight,
          reasons: [
            { kind: "stale", days: idleDays },
            { kind: "stage", stage: lead.stage },
            { kind: "score", value: lead.score.value },
          ],
        };
      }
      return null;
    })
    .filter((item): item is ActionQueueItem => Boolean(item))
    .sort((a, b) => {
      const bucketRank = { overdue: 0, today: 1, upcoming: 2 };
      return (
        bucketRank[a.bucket] - bucketRank[b.bucket] ||
        b.priority - a.priority ||
        (a.dueOn || "9999-12-31").localeCompare(b.dueOn || "9999-12-31") ||
        a.lead.name.localeCompare(b.lead.name)
      );
    });
}
