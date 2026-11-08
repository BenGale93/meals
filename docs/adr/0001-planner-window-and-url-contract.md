# 0001: Define the planner window and URL contract

- Status: Accepted
- Date: 2026-11-08

## Context

The planner originally rendered the seven days starting at `date.today()` with no way to
browse another period. A calendar-week view (Monday to Sunday) would make the default view
on a Sunday show six days that have already passed, which conflicts with forward meal
planning. The viewed window also needs to survive a reload and work with browser history.

Separately, the plan query uses an inclusive date range: `PlanRepository.get_range(start, end)`
delegates to SQL `BETWEEN`, and the JSON API exposes the same inclusive `start_date`/`end_date`
contract. The planner needs exactly seven days and must not fetch an eighth.

## Decision

- A planner window starts on a selected date and runs for seven consecutive days.
- With no `start` parameter, the start is today, so today is always the first row by default.
- `?start=YYYY-MM-DD` is used exactly as the first row; it is not snapped to Monday or any
  other weekday.
- Previous and Next shift the start by seven days. Today resets the start to today.
- The URL determines the viewed window.
- Today is highlighted only when it falls inside the viewed window. The Today control is
  disabled when the window starts today and is a link otherwise.
- Planner date ranges stay inclusive on both ends. A seven-day window passes `start` and
  `start + timedelta(days=6)`; the public API is not changed to an exclusive end date.
- A service-level regression test records the repository arguments and asserts `start`
  through `start + 6`.

## Consequences

- Forward planning always begins at today, including on Sundays.
- Windows can start midweek, so the controls say "Previous 7 days" and "Next 7 days" rather
  than naming a calendar week.
- A link to `/plan.html?start=...` is shareable and reloadable, and back/forward restores a
  viewed window when navigation pushes the page URL.
- Date arithmetic uses `datetime.date`, so adding days is not affected by DST or timezone
  transitions.
- The server evaluates `date.today()` once per request. The Pi's `TZ=Europe/London` setting
  is what makes that the user's local date.
- Date boundaries are explicit: the end date is included, and the next window starts on
  the following day, so adjacent windows do not overlap.
- Callers must remember the inclusive convention; the regression test records it.

## Alternatives considered

- **Monday-to-Sunday calendar week**: rejected because the default view on a Sunday would
  show mostly past days.
- **Snap any start date to Monday**: rejected because the URL would no longer describe the
  rows shown and navigation would be surprising.
- **Client-side-only window state**: rejected because the no-JavaScript path and reloads
  would not retain the window.
- **Exclusive end date**: cleaner for some range APIs, but would break the existing JSON
  contract and require coordinated changes across callers.
