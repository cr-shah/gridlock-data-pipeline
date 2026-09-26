# Georgia Power GIS expansion — bounded investigation (2026-09-26)

Scope: improve defensible geometry for host-highlighted regions (Augusta/Thomson/Vogtle and
Savannah/Effingham/Plant McIntosh). No distance threshold, project inventory, or scorer was
changed. Candidates were chosen by published county/endpoint/facility text and evidence
availability, not by distance to DESC geometry.

## Urquhart (DESC) — unchanged
- Urquhart – Aiken PSA 46 kV and Urquhart – Toolebeck 115 kV keep the MEDIUM-confidence
  EIA-860 Urquhart endpoint Point.
- The official Dominion Energy Urquhart-Toolebeck project page publishes a schedule but no map,
  route, or substation location. No authoritative public location was found for Toolebeck
  Substation or the Aiken PSA tap point (inferring one from a road name would be fabrication).
  The SC PSC docket document returned by search is disallowed by robots.txt and was not fetched.
- No straight-line endpoint approximation was created because only one endpoint is defensible.

## Thomson–Vogtle — not added
- Official page: georgiapower.com/.../grid-projects/thomson-vogtle.html. It describes a 55-mile
  500 kV line from Plant Vogtle (Burke County) to Thomson Primary (McDuffie County), constructed
  2014–2017 and in service by 2018. It is completed, not current/planned, and is not listed on
  the current Georgia Power transmission-projects page, so it is out of scope.
- Current Thomson-area work is already represented by Callaway Road – Thomson Primary 500 kV,
  whose official route geometry is unchanged.

## Plant McIntosh — not added
- The Plant McIntosh expansion is new gas/oil-fired generation (units at the Rincon,
  Effingham County site), per public reporting; no Georgia Power transmission project page
  names Plant McIntosh.
- The related current transmission record is Effingham County 500 kV. Its official page states
  that a project map is not currently available, so geometry stays null (review queue reason
  updated). McIntosh is not used as a proxy location.

## Inventory completeness
- The live Georgia Power transmission-projects page lists exactly the 10 projects already
  ingested. No record was missed; totals remain 64 (54 DESC, 10 GPC).

## New geometry
- Hatch – Wadley Primary 500 kV (`georgia-power-2026-57d55e09e3bd5e9f6cb2`): Wadley Primary is
  in Jefferson County, one of the counties the Thomson–Vogtle corridor crosses, making it the
  closest remaining GPC record to the Augusta/Vogtle region by published county. The cached
  official project page embeds a single 130-vertex route polyline between labelled Plant Hatch
  and Wadley Primary markers. Method `official_project_route_coordinates`, confidence HIGH.

Geometry count: 5 → 6 total; GPC 1 → 2.

Note: seven other GPC pages (outside the host regions) also embed official route polylines and
could be added the same way in a later pass.
