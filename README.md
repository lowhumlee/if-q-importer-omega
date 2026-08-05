# OMEGA PSIR Journal Indicators Generator

This tool transforms InCites / Journal Citation Reports journal indicator exports into an OMEGA PSIR journal indicator import file.

## Implemented rules

- Journal Impact Factor is mapped to `systemName = IFWoS`.
- JIF Quartile is mapped to `systemName = JIFQuartile`.
- For `IFWoS`, `svalue` is hardcoded to `2`.
- For `JIFQuartile`, `svalue` is left blank.
- JIF values are preserved as provided.
- JIF Quartiles are transformed from `Q1`, `Q2`, `Q3`, `Q4` to `1`, `2`, `3`, `4`.
- Missing values are not filled, estimated, or calculated.
- Exact duplicate rows are removed and reported.
- Conflicting values are reported; the first source occurrence is kept.
- ISSN is used as the primary identifier.
- eISSN is used only when ISSN is missing and the eISSN output column is enabled.

## Output columns

Default OMEGA documentation-compatible output:

```csv
issn;eissn;systemName;year;value;svalue
