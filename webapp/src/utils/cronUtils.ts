/**
 * Time-of-day scheduling utilities for cron expressions
 *
 * This module handles conversion between user-friendly 12-hour time schedules
 * and cron expressions. It supports daily, weekday, and specific day patterns.
 */

export interface TimeOfDaySchedule {
  hour: number; // 1-12
  minute: number; // 0-59
  period: "AM" | "PM";
  frequency: "daily" | "weekdays" | "specific";
  days?: number[]; // 0-6 (Sun-Sat), only when frequency="specific"
}

/**
 * Convert 12-hour time to 24-hour format
 *
 * Edge cases:
 * - 12 AM → 0 (midnight)
 * - 1-11 AM → 1-11
 * - 12 PM → 12 (noon)
 * - 1-11 PM → 13-23
 *
 * @param hour - Hour in 12-hour format (1-12)
 * @param period - "AM" or "PM"
 * @returns Hour in 24-hour format (0-23)
 */
export function convertTo24Hour(hour: number, period: "AM" | "PM"): number {
  if (hour < 1 || hour > 12) {
    throw new Error(`Invalid hour: ${hour}. Must be 1-12`);
  }

  if (period === "AM") {
    // 12 AM is midnight (0), 1-11 AM stay the same
    return hour === 12 ? 0 : hour;
  } else {
    // 12 PM is noon (12), 1-11 PM add 12
    return hour === 12 ? 12 : hour + 12;
  }
}

/**
 * Convert 24-hour time to 12-hour format with AM/PM
 *
 * @param hour24 - Hour in 24-hour format (0-23)
 * @returns Object with hour (1-12) and period ("AM" or "PM")
 */
export function convertTo12Hour(hour24: number): {
  hour: number;
  period: "AM" | "PM";
} {
  if (hour24 < 0 || hour24 > 23) {
    throw new Error(`Invalid 24-hour: ${hour24}. Must be 0-23`);
  }

  if (hour24 === 0) {
    // Midnight: 12 AM
    return { hour: 12, period: "AM" };
  } else if (hour24 < 12) {
    // 1-11 AM
    return { hour: hour24, period: "AM" };
  } else if (hour24 === 12) {
    // Noon: 12 PM
    return { hour: 12, period: "PM" };
  } else {
    // 1-11 PM (13-23 → 1-11)
    return { hour: hour24 - 12, period: "PM" };
  }
}

/**
 * Generate a 5-part cron expression from a time-of-day schedule
 *
 * Cron format: <minute> <hour> <day-of-month> <month> <day-of-week>
 * We use: <minute> <hour> * * <days>
 *
 * Day-of-week patterns:
 * - "daily" → * (all days)
 * - "weekdays" → 1-5 (Mon-Fri)
 * - "specific" → comma-separated list (e.g., "1,3,5")
 *
 * @param schedule - Time-of-day schedule configuration
 * @returns 5-part cron expression
 */
export function generateTimeOfDayCron(schedule: TimeOfDaySchedule): string {
  const { hour, minute, period, frequency, days } = schedule;

  // Validate inputs
  if (minute < 0 || minute > 59) {
    throw new Error(`Invalid minute: ${minute}. Must be 0-59`);
  }

  // Convert to 24-hour format
  const hour24 = convertTo24Hour(hour, period);

  // Generate day-of-week pattern based on frequency
  let dayPattern: string;
  switch (frequency) {
    case "daily":
      dayPattern = "*";
      break;
    case "weekdays":
      dayPattern = "1-5"; // Mon-Fri
      break;
    case "specific":
      if (!days || days.length === 0) {
        throw new Error("Days array required for specific frequency");
      }
      // Sort and join with commas
      dayPattern = [...days].sort((a, b) => a - b).join(",");
      break;
    default:
      throw new Error(`Unknown frequency: ${frequency}`);
  }

  // Build cron expression: <minute> <hour> * * <days>
  return `${minute} ${hour24} * * ${dayPattern}`;
}

/**
 * Parse a cron expression into a time-of-day schedule
 *
 * Only parses time-of-day patterns (minute hour * * days).
 * Returns null for interval patterns (e.g., every 15 minutes).
 *
 * @param cron - 5-part cron expression
 * @returns TimeOfDaySchedule if valid time-of-day pattern, null otherwise
 */
export function parseTimeOfDayCron(cron: string): TimeOfDaySchedule | null {
  const parts = cron.trim().split(/\s+/);

  // Must be 5 parts
  if (parts.length !== 5) {
    return null;
  }

  const [minutePart, hourPart, dayOfMonthPart, monthPart, dayOfWeekPart] =
    parts;

  // Must have * for day-of-month and month (time-of-day pattern)
  if (dayOfMonthPart !== "*" || monthPart !== "*") {
    return null;
  }

  // Parse minute (must be a single number, not */15 or range)
  const minute = parseInt(minutePart, 10);
  if (isNaN(minute) || minutePart.includes("/") || minutePart.includes("-")) {
    return null;
  }

  // Parse hour (must be a single number)
  const hour24 = parseInt(hourPart, 10);
  if (isNaN(hour24) || hourPart.includes("/") || hourPart.includes("-")) {
    return null;
  }

  // Convert to 12-hour format
  const { hour, period } = convertTo12Hour(hour24);

  // Parse day-of-week pattern
  let frequency: "daily" | "weekdays" | "specific";
  let days: number[] | undefined;

  if (dayOfWeekPart === "*") {
    frequency = "daily";
  } else if (dayOfWeekPart === "1-5") {
    frequency = "weekdays";
  } else {
    // Specific days (e.g., "1,3,5" or "0,6")
    frequency = "specific";
    days = dayOfWeekPart.split(",").map((d) => parseInt(d.trim(), 10));

    // Validate all days are numbers 0-6
    if (days.some((d) => isNaN(d) || d < 0 || d > 6)) {
      return null;
    }
  }

  return {
    hour,
    minute,
    period,
    frequency,
    days,
  };
}
