# 2026 SERTP extraction inspection notes

Source inspected: `2026 SERTP Preliminary Expansion Plan Report (Non-CEII)` discovered from the public SERTP Reference Library.

- Source SHA-256: `d3785576bb2f558f558931b7fea22503deaafc6d1f81cec25b8d471deb32cb2c`
- Extracted with: PyMuPDF 1.28.2, sorted text mode
- Physical pages: 115
- Printed pages detected: 1 through 115, with no missing values

## Ranges inspected

- PDF indexes 0-12 / printed pages 1-13: AECI followed by Duke Carolinas. These pages include `#2`, multiline project names, transformers, line rebuilds, `230/100/44 kV`, conductor sizes such as `795 ACSR`, and temperatures such as `100°C` and `200°C`.
- PDF indexes 16-22 / printed pages 17-23: Duke Progress East and West authority-header variants.
- PDF indexes 23-25 / printed pages 24-26: LG&E/KU authority transition.
- PDF indexes 26-31 / printed pages 27-32: SOUTHERN balancing authority with `GTC:`, `MEAG:`, `PS:`, and `SOCO:` owner prefixes. Includes `GTC: MORNING HORNET 2ND 230/115 KV BANK & STANTON SP 115 KV` and a detailed multi-owner East Walton project.
- PDF indexes 102-104 / printed pages 103-105: TVA authority transition, generation-interconnection projects, a compact ID-only title (`TS25-422`), and multiline descriptions/supporting statements.

## Observed extraction structure

- Each page begins with `SERTP TRANSMISSION PROJECTS`, a visually composed authority line whose extracted words are concatenated, and `Balancing Authority`.
- The authority forms observed across all pages begin at PDF indexes 0 (AECI), 1 (Duke Carolinas), 16 (Duke Progress East), 22 (Duke Progress West), 23 (LG&E/KU), 26 (SOUTHERN), and 102 (TVA).
- Each record uses the labels `In-Service` / `Year:`, `Project Name:`, `Description:`, and `Supporting` / `Statement:`. Labels and values can share a line or wrap independently.
- The repeated public template header contains `CEII`; it is header noise inside the publicly linked Non-CEII document and is not an access-classification signal.
- Footers have the form `06/12/2026 Page N of 115` with variable spacing.
- All 115 pages in this document start with a new `In-Service` record after the repeated header. No real record crossing a physical page boundary was found in the full-boundary scan. The parser must nevertheless preserve page-spanning records, and a synthetic page-boundary fixture will cover that failure mode.
- Project names can wrap, use hyphen/en-dash variants, preserve identifiers such as `#2` and `PHASE 1/2`, or consist only of an identifier.
- Voltage extraction must distinguish slash-delimited voltages from conductor sizes and temperatures. Lengths appear as integers, decimals, approximate values, parenthetical values, and multiple independent sections.
- `SOUTHERN` is the balancing authority. Prefixes such as `SOCO:` and `GTC:` remain separate source facts and do not establish Georgia Power ownership.
