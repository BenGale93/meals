# 0002: Use server-rendered HTML with HTMX navigation

- Status: Accepted
- Date: 2026-11-08

## Context

The app is server-rendered with FastAPI and htmy, with HTMX and Alpine loaded from CDNs.
There is no Node build, client-side router, or JSON-driven front end. The UI still needs
partial updates, browser history, and working links when JavaScript is unavailable.

## Decision

- Pages are rendered on the server with htmy from Pydantic models. There is no SPA, Node
  build, or separate asset pipeline.
- Front-end assets are pinned to exact CDN versions (Tailwind 3.4.17, HTMX 2.0.2, Alpine
  3.17.5) so a CDN release cannot silently change the page. If CDN access becomes a problem,
  vendor those files and serve them from FastAPI.
- Navigation controls are real `<a>` elements that point at full page URLs.
- HTMX upgrades a link with `hx-get` to a fragment endpoint, a panel target, and
  `hx-swap="outerHTML"`.
- `hx-push-url` is set explicitly to the matching page URL, not to `"true"`. HTMX pushes the
  request URL when given `"true"`, which would put the fragment endpoint in history and break
  a reload.
- Full-page routes and fragment routes share the same view model and service call. A fragment
  returns its whole panel as a single root with the id the caller targets.
- Writes that change a row re-render the viewed panel, so server-rendered actions such as
  Clear appear immediately. On a failed update, `HX-Reswap: none` preserves the typed text and
  current row.
- Alpine component functions are defined once in the shared page shell. Fragments may use
  them but must not define globals.

## Consequences

- Navigation works without JavaScript; with HTMX it avoids a full page reload and integrates
  with browser back/forward.
- History entries hold the page URL, so reloading or opening a back/forward entry renders the
  full page rather than the bare fragment.
- The panel id and the fragment root are a contract: the fragment must return the expected
  single root.
- Full-page and fragment routes cannot drift in content because they share the view model.
- Markup tests cannot verify history or partial-swap behaviour. Browser click-through remains
  part of verification for HTMX/Alpine changes.
- A page loaded before a markup change keeps its old HTMX attributes until reloaded, so
  template changes require a browser refresh after deploy.

## Alternatives considered

- **Full-page reloads only**: simplest and accessible, but loses the quick navigation feel
  and scroll state.
- **SPA or client-side router**: rejected as disproportionate for a server-rendered,
  single-user app and would add a build step.
- **Lazy-load the panel on every page load**: rejected because server rendering is simpler
  and removes a round trip.
- **Floating or unpinned CDN assets**: rejected because an upstream release could change the
  page without a code change or review.
