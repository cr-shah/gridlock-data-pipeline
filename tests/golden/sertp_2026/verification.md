# SERTP 2026 golden-record verification

The following records were manually checked against rendered pages of the official public 2026 Non-CEII PDF with source SHA-256 `d3785576bb2f558f558931b7fea22503deaafc6d1f81cec25b8d471deb32cb2c`.

| Printed page | Balancing authority | Source project name | Coverage |
|---:|---|---|---|
| 2 | DUKE CAROLINAS | BUSH RIVER TIE 115/100 KV AUTOTRANSFORMERS, REPLACE | Duke, transformer, multi-voltage, multiline description/support |
| 27 | SOUTHERN | GTC: ADAMSVILLE - BUZZARD ROOST 230 KV REBUILD | GTC prefix, line rebuild, conductor/temperature exclusion |
| 27 | SOUTHERN | GTC: EAST MOULTRIE - HIGHWAY 112 230 KV LINE | GTC prefix, new line, multiline support |
| 30 | SOUTHERN | GTC: REPLACE 230/115 KV AUTO TRANSFORMERS AT SOUTH HAZLEHURST | transformer, multi-voltage |
| 31 | SOUTHERN | SOCO: ANNISTON - BYNUM 115 KV TL UPGRADE | SOCO prefix, en-dash in description |
| 32 | SOUTHERN | SOCO: ATHENA - EAST WATKINSVILLE 115 KV REBUILD | SOCO prefix, line rebuild |
| 32 | SOUTHERN | SOCO: AUTAUGAVILLE - EAST PELHAM NEW 230 KV TRANSMISSION LINE | SOCO prefix, multiline support |
| 32 | SOUTHERN | SOCO: BESSEMER – SOUTH BESSEMER 115 KV TL RECONDUCTOR - PHASE 1 | SOCO prefix, source en dash, phase identifier |
| 103 | TVA | BULL RUN 500 KV SYNCHRONOUS CONDENSER, INSTALL | TVA, installation, multiline text |
| 103 | TVA | CORDOVA - YUM YUM 161 KV TRANSMISSION LINE, RECONDUCTOR | TVA, line reconductor, decimal length, conductor/temperature exclusion |

Checks performed for every row: exact raw project name, in-service year, raw description, raw supporting statement, printed/PDF page provenance, source SHA, balancing authority, owner prefix, voltage derivation, extraction engine/version, and stable observation ID.

The official 2026 document contains no record that crosses a physical page boundary: a complete scan found every page begins with a new `In-Service` block. Cross-page parser continuity is therefore verified with a clearly synthetic fixture rather than mislabeled as an official golden record.
