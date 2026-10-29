import { describe, it, expect, vi } from "vitest";
import { cents, money, stageLabel, inputDate } from "./types";
describe("commercial formatting", () => {
  it("converts decimal values to exact integer cents", () => {
    expect(cents("19.99")).toBe(1999);
    expect(cents("0.01")).toBe(1);
    expect(cents("1000.50")).toBe(100050);
  });
  it("formats money and pipeline labels", () => {
    expect(money(125099)).toContain("1.250,99");
    expect(stageLabel("won")).toBe("Fechado");
  });
  it("produces ISO date inputs for an IANA timezone", () => {
    expect(inputDate("America/Sao_Paulo")).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});

describe("review date near UTC midnight", () => {
  it("keeps the product calendar day instead of tomorrow in UTC", () => {
    vi.useFakeTimers();
    try {
      vi.setSystemTime(new Date("2026-10-25T01:30:00Z"));
      expect(inputDate()).toBe("2026-10-24");
      expect(inputDate("UTC")).toBe("2026-10-25");
    } finally {
      vi.useRealTimers();
    }
  });
});
