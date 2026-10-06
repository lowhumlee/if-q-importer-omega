from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


OUTPUT_COLUMNS_WITH_EISSN = [
    "issn",
    "eissn",
    "systemName",
    "year",
    "value",
    "svalue",
]

OUTPUT_COLUMNS_SAMPLE = [
    "issn",
    "systemName",
    "year",
    "value",
    "svalue",
]

REPORT_COLUMNS = [
    "type",
    "level",
    "source_row",
    "journal",
    "identifier",
    "year",
    "systemName",
    "detail",
]

ISSN_REGEX = re.compile(r"^\d{4}-?\d{3}[\dX]$")
QUARTILE_REGEX = re.compile(r"Q\s*([1-4])", re.IGNORECASE)
YEAR_REGEX = re.compile(r"(19|20)\d{2}")

COLUMN_ALIASES = {
    "issn": ["issn", "print issn", "issn_print"],
    "eissn": ["eissn", "e-issn", "electronic issn", "online issn"],
    "year": ["publication year", "year", "published year", "publication_year"],
    "jif": ["journal impact factor", "impact factor", "jif", "journal impact factor (jif)"],
    "quartile": ["jif quartile", "impact factor quartile", "jif quartile (q)", "quartile"],
    "title": ["name", "journal name", "source title", "title", "journal"],
}


@dataclass(frozen=True)
class TransformConfig:
    issn_col: Optional[str] = None
    eissn_col: Optional[str] = None
    year_col: Optional[str] = None
    jif_col: Optional[str] = None
    quartile_col: Optional[str] = None
    title_col: Optional[str] = None

    ifwos_system_name: str = "IFWoS"
    jif_quartile_system_name: str = "JIFQuartile"

    hardcode_ifwos_svalue: bool = True
    ifwos_svalue: str = "2"

    include_eissn_column: bool = True
    sort_output: bool = True

    blank_values: Tuple[str, ...] = ("", "na", "n/a", "none", "null")


@dataclass
class TransformResult:
    output_df: pd.DataFrame
    report_df: pd.DataFrame
    summary: Dict[str, int]


def normalize_header(value: Any) -> str:
    return str(value).strip().lower()


def detect_column(
    df: pd.DataFrame,
    aliases: List[str],
    configured: Optional[str] = None,
) -> Optional[str]:
    """
    Detect source column by explicit configured name, falling back to aliases.
    """
    lookup = {normalize_header(col): col for col in df.columns}

    # 1. Try the configured value first (if provided)
    if configured:
        configured_lower = str(configured).strip().lower()
        if configured_lower in lookup:
            return lookup[configured_lower]

    # 2. Fall back to aliases if configured is missing or not found in the file
    for alias in aliases:
        if alias in lookup:
            return lookup[alias]

    return None


def resolve_columns(
    df: pd.DataFrame,
    config: TransformConfig,
) -> Tuple[Dict[str, Optional[str]], List[str]]:
    colmap = {
        "issn": detect_column(df, COLUMN_ALIASES["issn"], config.issn_col),
        "eissn": detect_column(df, COLUMN_ALIASES["eissn"], config.eissn_col),
        "year": detect_column(df, COLUMN_ALIASES["year"], config.year_col),
        "jif": detect_column(df, COLUMN_ALIASES["jif"], config.jif_col),
        "quartile": detect_column(df, COLUMN_ALIASES["quartile"], config.quartile_col),
        "title": detect_column(df, COLUMN_ALIASES["title"], config.title_col),
    }

    missing = []
    if not colmap.get("year"):
        missing.append("year")
    if not colmap.get("jif") and not colmap.get("quartile"):
        missing.append("jif/quartile")
    if not colmap.get("issn") and not colmap.get("eissn"):
        missing.append("issn/eissn")

    return colmap, missing


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def normalize_issn(value: Any) -> str:
    s = clean_text(value).upper()
    s = re.sub(r"\s+", "", s)
    return s


def is_valid_issn(value: str) -> bool:
    return bool(ISSN_REGEX.match(normalize_issn(value)))


def parse_year(value: Any) -> Optional[int]:
    s = clean_text(value)
    if not s:
        return None
    m = YEAR_REGEX.search(s)
    if m:
        return int(m.group(0))
    try:
        year = int(float(s))
        if 1900 <= year <= 2100:
            return year
    except (ValueError, TypeError):
        pass
    return None


def is_numeric_value(value: Any) -> bool:
    s = clean_text(value).replace(",", ".")
    if not s:
        return False
    try:
        Decimal(s)
        return True
    except InvalidOperation:
        return False


def parse_quartile(value: Any) -> Optional[str]:
    s = clean_text(value)
    if not s:
        return None
    m = QUARTILE_REGEX.search(s)
    if m:
        return m.group(1)
    if s in {"1", "2", "3", "4"}:
        return s
    return None


def output_columns(config: TransformConfig) -> List[str]:
    if config.include_eissn_column:
        return OUTPUT_COLUMNS_WITH_EISSN
    return OUTPUT_COLUMNS_SAMPLE


def transform_incodes(
    df: pd.DataFrame,
    config: Optional[TransformConfig] = None,
) -> TransformResult:
    config = config or TransformConfig()
    issues: List[Dict[str, Any]] = []

    def add_issue(level, issue_type, source_row, journal, identifier, year, system_name, detail):
        issues.append({
            "type": issue_type, "level": level, "source_row": source_row,
            "journal": journal, "identifier": identifier, 
            "year": year if year is not None else "", 
            "systemName": system_name, "detail": detail,
        })

    out_cols = output_columns(config)

    if df is None or df.empty:
        return TransformResult(
            output_df=pd.DataFrame(columns=out_cols),
            report_df=pd.DataFrame(columns=REPORT_COLUMNS),
            summary={"input_rows": 0, "output_rows": 0, "ifwos_rows": 0, "jif_quartile_rows": 0, 
                     "issues": 0, "warnings": 0, "duplicate_source_rows": 0, 
                     "duplicate_import_rows": 0, "conflicts": 0, "unmatched_journals": 0, "missing_journals": 0},
        )

    colmap, missing = resolve_columns(df, config)
    if missing:
        raise ValueError("Missing required source columns: " + ", ".join(missing) + ". Please adjust column mapping or verify the uploaded file.")

    records: List[Dict[str, Any]] = []
    source_identifier_year_rows: Dict[Tuple[str, int], List[int]] = {}

    for idx, row in df.iterrows():
        try:
            source_row = int(idx) + 2
        except (TypeError, ValueError):
            source_row = str(idx)

        title = clean_text(row.get(colmap.get("title"))) if colmap.get("title") else ""
        year_raw = clean_text(row.get(colmap.get("year"))) if colmap.get("year") else ""
        year = parse_year(year_raw)

        issn = normalize_issn(row.get(colmap.get("issn"))) if colmap.get("issn") else ""
        eissn = normalize_issn(row.get(colmap.get("eissn"))) if colmap.get("eissn") else ""
        primary_identifier = issn or eissn

        if year is None:
            add_issue("warning", "invalid_year", source_row, title, primary_identifier, year_raw, "", "Missing or unparsable publication year.")
            continue

        if primary_identifier:
            key = (primary_identifier, year)
            source_identifier_year_rows.setdefault(key, []).append(source_row)

        out_issn = ""
        out_eissn = ""

        if issn:
            out_issn = issn
            identifier = issn
            if not is_valid_issn(issn):
                add_issue("warning", "invalid_issn", source_row, title, identifier, year, "", "ISSN does not match expected format XXXX-XXXX.")
        elif eissn:
            if config.include_eissn_column:
                out_eissn = eissn
                identifier = eissn
                if not is_valid_issn(eissn):
                    add_issue("warning", "invalid_eissn", source_row, title, identifier, year, "", "eISSN does not match expected format XXXX-XXXX.")
            else:
                add_issue("warning", "eissn_only_skipped", source_row, title, eissn, year, "", "eISSN-only record skipped because output is restricted to the sample issn-only layout.")
                continue
        else:
            add_issue("warning", "unmatched_journal", source_row, title, "", year, "", "No ISSN/eISSN available; cannot create OMEGA identifier.")
            continue

        jif_raw = clean_text(row.get(colmap.get("jif"))) if colmap.get("jif") else ""
        quartile_raw = clean_text(row.get(colmap.get("quartile"))) if colmap.get("quartile") else ""
        created_any_row = False

        # Process JIF (IFWoS)
        if jif_raw.strip().lower() not in config.blank_values:
            if is_numeric_value(jif_raw):
                # FIX: Round JIF to 3 decimal places to remove floating-point artifacts
                try:
                    jif_numeric = float(clean_text(jif_raw).replace(",", "."))
                    jif_rounded = str(round(jif_numeric, 3))
                except (ValueError, TypeError):
                    jif_rounded = clean_text(jif_raw)
                
                records.append({
                    "issn": out_issn, "eissn": out_eissn,
                    "systemName": config.ifwos_system_name, "year": year,
                    "value": jif_rounded, 
                    "svalue": config.ifwos_svalue if config.hardcode_ifwos_svalue else "",
                    "_identifier": out_issn or out_eissn, "_title": title, "_row": source_row,
                })
                created_any_row = True
            else:
                add_issue("warning", "invalid_jif", source_row, title, identifier, year, config.ifwos_system_name, f"Journal Impact Factor is not numeric: '{jif_raw}'.")

        # Process Quartile (JIFQuartile)
        if quartile_raw.strip().lower() not in config.blank_values:
            quartile_value = parse_quartile(quartile_raw)
            if quartile_value:
                records.append({
                    "issn": out_issn, "eissn": out_eissn,
                    "systemName": config.jif_quartile_system_name, "year": year,
                    "value": quartile_value, "svalue": "",
                    "_identifier": out_issn or out_eissn, "_title": title, "_row": source_row,
                })
                created_any_row = True
            else:
                add_issue("warning", "invalid_quartile", source_row, title, identifier, year, config.jif_quartile_system_name, f"JIF quartile could not be parsed: '{quartile_raw}'.")

        if not created_any_row:
            add_issue("warning", "missing_journal", source_row, title, identifier, year, "", "No usable Journal Impact Factor or JIF Quartile value.")

    # Report duplicate ISSN/year combinations in the source file.
    for (identifier, year), rows in source_identifier_year_rows.items():
        if len(rows) > 1:
            rows_display = ", ".join(str(r) for r in rows[:20])
            suffix = "..." if len(rows) > 20 else ""
            add_issue("info", "duplicate_issn", rows[0], "", identifier, year, "", f"Same identifier/year appears in {len(rows)} source rows: {rows_display}{suffix}")

    if not records:
        output_df = pd.DataFrame(columns=out_cols)
    else:
        output_df = pd.DataFrame.from_records(records)
        output_df = output_df.sort_values("_row")

        dup_subset = [c for c in out_cols if c in output_df.columns]
        exact_duplicate_mask = output_df.duplicated(subset=dup_subset, keep="first")

        if exact_duplicate_mask.any():
            for _, r in output_df[exact_duplicate_mask].iterrows():
                add_issue("info", "duplicate_import_row", r["_row"], r["_title"], r["_identifier"], r["year"], r["systemName"], "Exact duplicate import row removed.")
            output_df = output_df[~exact_duplicate_mask]

        conflict_subset = ["_identifier", "systemName", "year"]
        keep_indices = []
        for _, group in output_df.groupby(conflict_subset, dropna=False):
            if len(group) > 1:
                values = "; ".join(f"{r['value']} (row {r['_row']})" for _, r in group.iterrows())
                add_issue("warning", "conflicting_value", group.iloc[0]["_row"], group.iloc[0]["_title"], group.iloc[0]["_identifier"], group.iloc[0]["year"], group.iloc[0]["systemName"], f"Conflicting values found; keeping first by source order. Values: {values}")
            keep_indices.append(group.sort_values("_row").index[0])

        output_df = output_df.loc[output_df.index.isin(keep_indices)]

        if config.sort_output:
            output_df = output_df.sort_values(["_identifier", "systemName", "year"])

        output_df = output_df[out_cols].copy()

    output_df = output_df.fillna("")
    output_df["year"] = output_df["year"].astype(str)

    report_df = pd.DataFrame(issues, columns=REPORT_COLUMNS) if issues else pd.DataFrame(columns=REPORT_COLUMNS)
    if not report_df.empty:
        report_df = report_df.sort_values(["type", "source_row"])

    summary = {
        "input_rows": int(len(df)),
        "output_rows": int(len(output_df)),
        "ifwos_rows": int((output_df["systemName"] == config.ifwos_system_name).sum()) if not output_df.empty else 0,
        "jif_quartile_rows": int((output_df["systemName"] == config.jif_quartile_system_name).sum()) if not output_df.empty else 0,
        "issues": int(len(report_df)),
        "warnings": int((report_df["level"] == "warning").sum()) if not report_df.empty else 0,
        "duplicate_source_rows": int((report_df["type"] == "duplicate_issn").sum()) if not report_df.empty else 0,
        "duplicate_import_rows": int((report_df["type"] == "duplicate_import_row").sum()) if not report_df.empty else 0,
        "conflicts": int((report_df["type"] == "conflicting_value").sum()) if not report_df.empty else 0,
        "unmatched_journals": int((report_df["type"] == "unmatched_journal").sum()) if not report_df.empty else 0,
        "missing_journals": int((report_df["type"] == "missing_journal").sum()) if not report_df.empty else 0,
    }

    return TransformResult(output_df=output_df, report_df=report_df, summary=summary)


def get_excel_sheet_names(uploaded_file) -> List[str]:
    try:
        uploaded_file.seek(0)
        import openpyxl
        workbook = openpyxl.load_workbook(uploaded_file, read_only=True)
        sheet_names = workbook.sheetnames
        workbook.close()
        uploaded_file.seek(0)
        return sheet_names
    except Exception:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        return []


def read_uploaded_file(uploaded_file, sheet_name: Any = 0) -> pd.DataFrame:
    """
    Read uploaded Excel or CSV file. 
    Uses auto-detection for CSV separators to handle both commas and semicolons.
    """
    name = getattr(uploaded_file, "name", "")
    try:
        uploaded_file.seek(0)
    except Exception:
        pass

    if str(name).lower().endswith(".csv"):
        # sep=None with engine='python' auto-detects whether the file uses commas or semicolons
        return pd.read_csv(uploaded_file, sep=None, engine='python', dtype=str)

    return pd.read_excel(uploaded_file, sheet_name=sheet_name, dtype=str)


def dataframe_to_csv(df: pd.DataFrame, sep: str = ";") -> str:
    return df.to_csv(sep=sep, index=False)
