# Planning Document

## Purpose

This document is the design record for the next planner feature. `TODO.md` is the
prioritised work queue; this file explains **how** the feature will be built and what
"done" means.

Current state (November 2026):

- The planner renders a seven-day table starting at today, with a recipe autocomplete,
  an update button per row, and a separate recipe-summary table.
- The table is loaded lazily: `GET /plan.html` renders a placeholder that HTMX fills from
  `GET /weeks_plan`.
- There is no way to browse another seven-day window, no visual indication of today, and no
  way to remove a planned meal. An empty meal name is treated as "recipe not found" and
  shows the error state.
- `PlanService.week()` calls `get_range(today, today + 7)`. `get_range` uses SQL `BETWEEN`,
  so it is inclusive on both ends: the query fetches eight days while only seven are
  rendered. The extra row is harmless today but is an off-by-one waiting to become a bug.
- The schema is owned by Alembic; the app is single-user on a Raspberry Pi, reachable over
  Tailscale, with `TZ=Europe/London` set by the systemd unit.

## Feature: Planner navigation and day controls (TODO Features item 3)

### Summary

Turn the planner from a fixed "today plus six days" view into a navigable rolling
seven-day window:

- Previous/next seven-day windows and a "jump to today" control.
- A rolling window anchored on the selected start date, defaulting to today at the top,
  with the current day highlighted when it is visible.
- A Clear button on planned rows that removes the plan for that day.
- The off-by-one in the window query fixed, with a regression test.

No database migration, new dependency, or schema change is required.

### Goals

- Browse any seven-day window without leaving the planner page, and make the viewed window
  part of the URL so it survives a reload and works with the browser back/forward buttons.
- Keep the no-JavaScript path working for navigation: controls are real links to
  `/plan.html?start=...` that HTMX upgrades into partial swaps.
- Keep today at the top of the default view, so forward planning always shows the next six
  days. On a Sunday the default view is still today plus the coming week, not six days that
  have already passed.
- Make "today" discoverable when a browsed window includes it.
- Allow a plan to be cleared without typing or guessing an empty name.
- Keep all writes user-scoped and idempotent.
- Keep 100% branch coverage and the API/web layers sharing the plan service.

### Non-goals (this pass)

- Multiple meals per day, drag-and-drop, or recurring plans.
- Non-recipe meals (TODO Features item 2); a cleared day is simply empty.
- A shopping list (TODO Features item 4).
- Refreshing the summary table after a plan is updated or cleared. The summary is still a
  separately loaded fragment; making both panels invalidate each other is a follow-up.
- Plan history, undo, or a confirmation dialog for clearing. Clearing is idempotent and a
  meal can be re-planned in one request.
- Changing the JSON API's existing inclusive `start_date`/`end_date` contract.
- Client-side date pickers or infinite scrolling.

### Decisions

| Topic | Decision |
| --- | --- |
| Window model | Rolling seven-day window starting on the selected date; not a calendar week |
| Default view | Today at the top, followed by the next six days |
| URL state | `?start=YYYY-MM-DD`; the date is used exactly as the first row, not snapped to Monday |
| Navigation | Previous/next shift the window by seven days; Today resets the start to today |
| Navigation labels | "Previous 7 days", "Today", "Next 7 days" |
| Navigation controls | Real `<a href="/plan.html?start=...">` links upgraded by HTMX partial swaps |
| Back/forward | `hx-push-url="true"` so the address bar holds the page URL, not the fragment URL |
| Page rendering | `GET /plan.html` renders the window server-side (no first-load XHR placeholder) |
| Highlight | Today's row gets `aria-current="date"`, a "Today" badge, and a tinted background when visible |
| Clear action | Explicit `POST /planned_day/clear`; an empty meal on Update remains an error |
| Clear result | Idempotent, and re-renders the window the user was viewing |
| API parity | `DELETE /api/v1/planned_day?day=...` with `204 No Content`, always idempotent |
| Off-by-one | Keep `get_range` inclusive and pass `start + 6`; test the requested range |
| Summary refresh | Out of scope; the summary panel is unchanged |

## Window model and date handling

The planner uses a **rolling seven-day window**, not a calendar week. The window starts on
the selected date and runs for six more days. With no selection the start is today, so the
default view always begins at today and looks forward, including on a Sunday.

Rules:

- A requested start is used exactly as given, so `/plan.html?start=2020-01-01` shows
  2020-01-01 through 2020-01-07. There is no snapping to Monday.
- The default start is `date.today()`, giving the current day at the top followed by the
  next six days.
- The window end is `start + timedelta(days=6)`. `PlanRepository.get_range` keeps its
  inclusive `BETWEEN` semantics, so the service passes the seventh day, not day eight.
- Previous shifts the start by `-7` days; Next shifts it by `+7` days. Today resets the
  start to `date.today()`. This makes window boundaries independent of weekday.
- The header displays `start` and `end` with `strftime("%d %b %Y")`, for example
  `08 Nov 2026 - 14 Nov 2026`.
- Weekday cells display both the weekday and the date (`%A` and `%d %b`) so a future
  window is unambiguous. Tests derive expected strings with the same `strftime` calls
  rather than hard-coding locale-dependent names.
- `date.today()` is evaluated once per request. The Pi's `TZ=Europe/London` setting is what
  makes that the user's local date; no new timezone configuration is introduced.
- The "Today" control is rendered as a disabled `<span>` when the window starts today, and
  as a link otherwise. A window that merely *contains* today but starts earlier still
  shows today highlighted, while Today remains enabled so the user can return to the
  today-at-top view.
- Highlighting depends only on `day == today`, so it disappears when browsing a window
  that does not include today.

## Data and repository changes

No migration is needed.

`PlanRepository` gains one method:

```python
async def clear(self, day: date, user_pk: int) -> None:
    """Remove the user's plan for a day, if there is one."""
```

Implementation notes:

- Select `StoredPlannedDay` by `day` and `user_pk`, delete it if found, and flush. Prefer
  this over a bulk `DELETE` so the session identity map stays consistent and the
  not-found branch is explicit and testable.
- Do not delete the recipe; only the plan row. The recipe and its ingredients/labels are
  untouched.
- Scoping by `user_pk` is mandatory, matching `update`, `get_range`, and `summarise`. A
  user must never be able to clear another user's plan even if they guess the date.
- `get_range` is unchanged.

## Service changes

`PlanService` gains:

- `week(user_pk, start=None) -> PlannedDays`
  - Resolve `start = start or date.today()`; do not normalise it.
  - Query `get_range(start, start + timedelta(days=6), user_pk)`.
  - Build exactly seven `DayToPlan` rows from `start` onwards, filling unmatched days with
    `recipe=None` as today. The loop length and the query end must agree; a test asserts
    the repository is asked for `start..start + 6`.
- `clear(day, user_pk) -> None`
  - Delegate to `PlanRepository.clear`. No existence check in the service; the operation is
    idempotent.

Both web routes and the JSON API call these methods. `meals.web` keeps only date parsing
and view-model construction; it does not touch the session or build SQL.

## Web routes and view model

`src/meals/web/planner.py` gets a small view model:

```python
class PlannerWindow(t.NamedTuple):
    start: date
    days: PlannedDays
    today: date

    @property
    def end(self) -> date: ...
    @property
    def starts_today(self) -> bool: ...
```

Both properties are used by the renderer and need tests for their two values.

### Page route

```text
GET /plan.html?start=YYYY-MM-DD
```

- Requires `CurrentUser`, as it already does.
- Accepts an optional `start: date | None` query parameter. FastAPI returns 422 for a
  malformed date (for example `start=not-a-date`); any valid date is accepted exactly as
  the first row.
- Builds `PlannerWindow` and returns it to `plan_page`, which renders the window table
  directly. The old `hx-get="/weeks_plan" hx-trigger="load"` placeholder is removed.
- The summary placeholder (`hx-get="/summary" hx-trigger="load"`) is unchanged.

### Fragment route

```text
GET /weeks_plan?start=YYYY-MM-DD
```

- Same optional `start` handling and the same `PlannerWindow` view model.
- Returns the whole window panel, not just the table: wrapper, header/navigation, and table.
- Used by HTMX for previous/next/today navigation and as the refresh target after a clear.

### Clear route

```text
POST /planned_day/clear?start=YYYY-MM-DD
Form fields: day=YYYY-MM-DD
```

- Requires `CurrentUser`; both `start` (query) and `day` (form) are required, and missing or
  malformed values are 422.
- `start` is the first day of the window the user is looking at. The Clear button includes
  it in the request so the response re-renders the same window instead of jumping the
  cleared day to the top.
- Calls `PlanService.clear(day, user.pk)`, then returns `planned_week_div` for the window
  starting at `start`, so the caller sees the empty row immediately.
- Idempotent: if no plan exists, it still returns the refreshed panel with 200.
- No `HX-Trigger` feedback is needed because the row itself is replaced. If feedback is
  added later, it must not rely on the detached button element.

## JSON API

Add one endpoint for parity and future CLI use:

```text
DELETE /api/v1/planned_day?day=YYYY-MM-DD  ->  204 No Content
```

- Requires `CurrentUser`.
- Calls `PlanService.clear`; succeeds whether or not a plan existed.
- Uses `response_class=Response` / an explicit empty body so the 204 contract is
  unambiguous under the installed FastAPI version.
- `GET /api/v1/planned_day` and its inclusive date range are unchanged.

## Rendering contract

### Window panel

`planned_week_div(view: PlannerWindow)` returns a wrapper with `id="week-panel"` containing:

1. A header with the window range and navigation.
2. The seven-row table.

Navigation markup:

```html
<a href="/plan.html?start=<previous start>"
   hx-get="/weeks_plan?start=<previous start>"
   hx-target="#week-panel"
   hx-swap="outerHTML"
   hx-push-url="true">Previous 7 days</a>
```

- Previous uses `start - 7`, Next uses `start + 7`, and both use the same attributes.
- Today links to `/plan.html` (the canonical today-at-top URL) and requests
  `/weeks_plan?start=<today>`.
- When `starts_today`, Today is a `<span aria-disabled="true">Today</span>` instead of a
  link.
- The navigation deliberately targets the panel by id. The page always renders the panel
  inside the page shell, and the fragment endpoint always returns the panel as its root, so
  `outerHTML` swaps cannot replace the wrong element.

### Table rows

Each row keeps the existing hidden `day` input and meal input so the Update button and
`hx-include="closest tr"` continue to work. Additions:

- Today's row (when visible): `aria-current="date"`, tinted row class (for example
  `bg-green-50`), and a small "Today" badge next to the weekday.
- Date cell: weekday plus `%d %b`.
- Actions cell (or the existing meal cell) contains the Update button as today, and, only
  when `recipe is not None`, a Clear button:

```html
<button hx-post="/planned_day/clear?start=<window start>"
        hx-target="#week-panel"
        hx-swap="outerHTML"
        hx-include="closest tr">Clear</button>
```

- The Clear button is absent on empty rows. This keeps the action discoverable only when it
  applies and avoids a request that can never do anything.
- `hx-include="closest tr"` submits the hidden `day`; the meal input is also included but
  ignored by the clear route.
- The existing Update button keeps `hx-swap="none"` and the `show-success`/`show-error`
  triggers. Changing update to re-render the whole panel is out of scope and would make the
  existing button feedback script point at a destroyed element.

### Page function

`plan_page(view: PlannerWindow)` renders:

- the page shell from `meals.web.core.page()`,
- the heading "Weekly Meal Plan",
- `planned_week_div(view)` (server-rendered),
- the existing summary placeholder,
- `PLANNER_SCRIPT`.

`PLANNER_SCRIPT` is unchanged; no new Alpine state is needed for navigation. A small amount
of server-rendered markup replaces the old lazy load, so there is no new client-side
component to define.

## Edge cases and behaviour matrix

| Case | Expected behaviour |
| --- | --- |
| No `start` | Today at the top, next six days following, today highlighted |
| `start` is any valid date | Exactly that date is the first row |
| `start` is malformed | 422; no silent fallback to a different window |
| Browsing past/future windows | Seven rows, plans shown when present, otherwise empty |
| Today outside the viewed window | No highlighted row, Today control is a link |
| Window starts today | Today highlighted; Today control disabled |
| Today inside the window but not first | Today highlighted; Today control is an enabled link back to today-at-top |
| Update with a valid recipe | Existing behaviour and success trigger |
| Update with an unknown recipe | Existing behaviour and error trigger |
| Clear a planned day | Plan row removed, the same window re-rendered with that day empty |
| Clear an unplanned day | 200 for the web route / 204 for the API; no state change |
| Clear another user's day | Their plan is untouched; the caller's is cleared/no-op |
| Window query boundary | Only `start..start + 6` is requested; day 7 belongs to the next window |

## Testing plan

Follow the existing layout; no new modules are expected.

### `tests/web/test_planner.py`

- Replace the old assertion that `/plan.html` contains a `hx-get="/weeks_plan"` placeholder;
  assert the page contains `id="week-panel"`, the window header, and a rendered table.
- Default window: travel to a fixed Sunday (the awkward case) with `time_machine`; assert
  that day is the first rendered date, the next six days follow, the seven Update buttons
  are present, and today's row has `aria-current="date"` and the Today badge.
- Previous/next: assert the two `href` and `hx-get` URLs, `hx-target="#week-panel"`,
  `hx-swap="outerHTML"`, and `hx-push-url="true"`; the URLs differ by seven days.
- Today control: disabled span when the window starts today; link with `href="/plan.html"`
  when the window starts elsewhere, including a window that contains today but starts
  earlier.
- `GET /weeks_plan?start=<fixed Wednesday>` uses that exact date as the first row, proving
  there is no Monday normalisation.
- A plan made in a future window appears when that window is requested and is absent from
  the current window (no leakage across windows).
- Invalid `start` returns 422 for both `/plan.html` and `/weeks_plan`.
- Clear: plan a meal, POST `/planned_day/clear?start=<viewed start>` with the day, assert
  the response is the refreshed panel, the first row is still the viewed start, the meal
  input is empty, and the Clear button is gone.
- Clear again: same request still succeeds and renders the same empty row.
- Clear is user-scoped: use the two-user fixtures; clearing as user two leaves user one's
  plan intact.
- The Clear button is absent from empty rows and present on planned rows.

### `tests/api/test_planner.py`

- `DELETE /api/v1/planned_day?day=...` returns 204 and removes the plan.
- Deleting a day with no plan also returns 204 (idempotent).
- Deleting as another user does not remove the owner's plan.
- Malformed/missing `day` returns 422.
- Existing range/summary tests stay unchanged.

### Direct service test

Add a focused test (in `tests/test_services.py` if one exists, otherwise beside the planner
tests) with a stub plan repository that records `get_range` arguments:

- `PlanService.week(user_pk, date(2020, 1, 1))` requests exactly
  `date(2020, 1, 1)` through `date(2020, 1, 7)` and returns seven days.
- The exact date is used as the start, even when it is not a Monday.
- A `None` start requests `date.today()` through `date.today() + 6` (use `time_machine`).

This is the regression test for the off-by-one; asserting rendered output alone would pass
even with the old eight-day query.

### Coverage

- Both branches of `PlanRepository.clear` (row found / not found) are exercised by the
  delete API tests.
- Both truth values of `PlannerWindow.starts_today` are exercised by the navigation tests.
- Every new route's auth and validation paths are covered.
- `just` (lint, pyrefly, tests at 100% branch coverage) is the gate.

## Task breakdown

- [ ] **M1 - Window model and service.** Change `PlanService.week` to accept a start
      (default today) and query `start..start + 6`, add `PlanService.clear`, and add the
      service regression test for the query range.
- [ ] **M2 - Repository and JSON API.** Add `PlanRepository.clear` and
      `DELETE /api/v1/planned_day`; cover found, not-found, cross-user, and validation cases.
- [ ] **M3 - Web page and fragment.** Build `PlannerWindow`, server-render the window on
      `/plan.html`, make `/weeks_plan` accept `start`, add navigation, today highlighting,
      date labels, and the clear route. Update the existing page/fragment tests.
- [ ] **M4 - Clear UI.** Add the conditional Clear button and panel swap; cover planned and
      empty rows, idempotent clears, user scoping, and preserving the viewed window.
- [ ] **M5 - Verification.** Run `just`; click through in a browser (or headless) to confirm
      HTMX pushes `/plan.html?start=...`, back/forward restores a window, and Clear empties
      the row; update `TODO.md` and mark item 3 done.

## Acceptance criteria

- `/plan.html` shows today at the top followed by the next six days, with today highlighted
  and labelled.
- Previous and Next move the window by seven days; Today returns to the today-at-top view.
- The viewed window is in the URL, survives a reload, and works with browser back/forward.
- Navigation links work without JavaScript as normal page loads.
- A planned meal can be cleared from the row, and the row updates immediately without
  jumping to a different window.
- Clearing an empty day is a harmless no-op; clearing never affects another user.
- The window service requests exactly seven days (`start..start + 6`).
- `just` is green at 100% branch coverage, with no new migrations or dependencies.

## Rollout

- No schema, dependency, or configuration changes: deploy with the normal `just` gate and
  the standard `just deploy` path.
- A candidate deployment is optional for this change, but the browser smoke test in M5 is
  required because the behaviour depends on HTMX history and partial swaps.
- Rollback is the previous commit; no database restore is needed because no data shape
  changes and cleared plans are ordinary row deletions.
