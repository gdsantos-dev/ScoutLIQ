# ScoutLIQ frontend redesign audit

## Scope

Visual and interaction-layer redesign only. Backend routes, authentication, API contracts, persistence, database models and business rules were intentionally left unchanged.

## Audit findings from the v1.0 frontend

- The shell and page hierarchy were functional but visually uniform; many unrelated functions shared the same panel/card treatment.
- Native selects and date inputs broke product identity and introduced browser-dependent visuals.
- Radar treated the map as a contained widget instead of the primary working surface.
- Pipeline depended on a conventional kanban composition that became cramped as stages and cards grew.
- Finance used equal-weight summary blocks instead of a strong result hierarchy.
- Settings split preferences into similarly weighted boxes instead of contextual groups.
- Tables were operational but read as raw application tables rather than product-specific data ledgers.
- Desktop scale and sidebar/content relationships required more deliberate handling at 100% zoom.

## New system

- Grid-based application shell. The sidebar participates in layout on desktop and becomes an off-canvas navigation on mobile, preventing content overlap.
- Crimson is the ScoutLIQ brand signal. Warm off-white, charcoal surfaces and hairline borders carry most of the visual weight. Champagne is reserved for subtle ORLIQ attribution.
- Custom SmartSelect and DateField components replace visible native selects and date pickers without changing submitted field names or API payloads.
- Overview uses a commercial-result hierarchy, an operational pulse and a unified territory/trend field.
- Radar uses one discovery command line, custom filters and an integrated map/results workstation.
- Pipeline uses a vertical stage ledger with horizontally scrollable deal tracks instead of six compressed columns.
- Clients, Sites and Finance use editorial ledgers, typographic hierarchy and hairlines rather than grids of equal cards.
- Settings uses contextual sections and custom controls.
- About remains factual and editorial.
- Login/auth flows keep existing states and endpoints while receiving the same product visual system.

## Motion and accessibility

- Short spatial transitions only; no scroll hijacking.
- `prefers-reduced-motion` is respected globally.
- Focus-visible states are explicit.
- Icon-only actions use product tooltips rather than native browser title tooltips.
- Scrollbars are visually hidden while scrolling remains available.

## Verification performed

- Backend directory diff: unchanged from the provided v1.0 baseline.
- CSS parsed with zero syntax errors.
- All TS/TSX source files passed TypeScript `transpileModule` syntax validation.
- No visible native `<select>` or `input[type=date]` remains in the frontend source.
- Desktop compositions for Overview, Radar and Pipeline were rendered during design review at a 1664×936 reference viewport.

A complete dependency build could not be certified in the isolated editing environment because the local `node_modules` snapshot was incomplete. The deployment build remains the authoritative full TypeScript/Vite check.
