import streamlit as st

from omega_indicators import (
    TransformConfig,
    get_excel_sheet_names,
    read_uploaded_file,
    transform_incodes,
)


st.set_page_config(
    page_title="OMEGA PSIR Journal Indicators Generator",
    page_icon=":books:",
    layout="wide",
)

st.title("OMEGA PSIR Journal Indicators Generator")
st.caption(
    "Transform InCites Journal Citation Reports exports into an OMEGA PSIR "
    "journal indicator import file. This tool does not calculate, estimate, "
    "or invent indicator values."
)


def none_if_blank(value: str):
    value = value.strip() if value else ""
    return value if value else None


uploaded_file = st.file_uploader(
    "Upload InCites export",
    type=["xlsx", "xls", "csv"],
)

if uploaded_file is not None:
    sheet_names = get_excel_sheet_names(uploaded_file)

    with st.sidebar:
        st.header("Settings")

        if sheet_names:
            selected_sheet = st.selectbox(
                "Excel sheet",
                sheet_names,
                index=0,
            )
        else:
            selected_sheet = 0

        include_eissn_column = st.checkbox(
            "Include eISSN column",
            value=True,
            help=(
                "Recommended by OMEGA documentation. If disabled, output uses "
                "the sample layout with issn only, and eISSN-only records are skipped."
            ),
        )

        hardcode_ifwos_svalue = st.checkbox(
            "Hardcode svalue='2' for IFWoS",
            value=True,
            help=(
                "When enabled, every IFWoS row receives svalue='2', matching "
                "the provided sample file and project instruction."
            ),
        )

        ifwos_svalue = st.text_input(
            "IFWoS svalue",
            value="2",
            disabled=not hardcode_ifwos_svalue,
        )

        sort_output = st.checkbox(
            "Sort output deterministically",
            value=True,
            help="Sort by identifier, systemName, and year.",
        )

        with st.expander("Advanced column mapping"):
            issn_col = st.text_input("ISSN column", value="ISSN")
            eissn_col = st.text_input("eISSN column", value="eISSN")
            year_col = st.text_input("Year column", value="Publication Year")
            jif_col = st.text_input(
                "Journal Impact Factor column",
                value="Journal Impact Factor",
            )
            quartile_col = st.text_input(
                "JIF Quartile column",
                value="JIF Quartile",
            )
            title_col = st.text_input(
                "Journal title column",
                value="Name",
            )

    st.info("Configure options in the sidebar, then click Generate.")

    generate_clicked = st.button(
        "Generate import file",
        type="primary",
    )

    if generate_clicked:
        try:
            source_df = read_uploaded_file(uploaded_file, selected_sheet)

            config = TransformConfig(
                issn_col=none_if_blank(issn_col),
                eissn_col=none_if_blank(eissn_col),
                year_col=none_if_blank(year_col),
                jif_col=none_if_blank(jif_col),
                quartile_col=none_if_blank(quartile_col),
                title_col=none_if_blank(title_col),
                hardcode_ifwos_svalue=hardcode_ifwos_svalue,
                ifwos_svalue=ifwos_svalue,
                include_eissn_column=include_eissn_column,
                sort_output=sort_output,
            )

            result = transform_incodes(source_df, config)

            st.session_state.result = result
            st.session_state.source_preview = source_df.head(50)

        except Exception as exc:
            st.error(f"Transformation failed: {exc}")

    if "result" in st.session_state:
        result = st.session_state.result
        summary = result.summary

        st.subheader("Summary")

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Input rows", summary["input_rows"])
        col2.metric("Output rows", summary["output_rows"])
        col3.metric("IFWoS rows", summary["ifwos_rows"])
        col4.metric("JIFQuartile rows", summary["jif_quartile_rows"])

        col5, col6, col7, col8 = st.columns(4)

        col5.metric("Warnings", summary["warnings"])
        col6.metric("Duplicate source rows", summary["duplicate_source_rows"])
        col7.metric("Conflicts", summary["conflicts"])
        col8.metric("Unmatched journals", summary["unmatched_journals"])

        import_csv = result.output_df.to_csv(sep=";", index=False)
        report_csv = result.report_df.to_csv(sep=";", index=False)

        st.subheader("Downloads")

        download_col1, download_col2 = st.columns(2)

        with download_col1:
            st.download_button(
                label="Download OMEGA import CSV",
                data=import_csv.encode("utf-8"),
                file_name="OMEGA_journal_indicators_import.csv",
                mime="text/csv",
            )

        with download_col2:
            st.download_button(
                label="Download validation report CSV",
                data=report_csv.encode("utf-8"),
                file_name="OMEGA_journal_indicators_validation_report.csv",
                mime="text/csv",
            )

        tab_import, tab_report, tab_missing, tab_duplicates, tab_source = st.tabs(
            [
                "Import preview",
                "Validation report",
                "Missing / unmatched",
                "Duplicates / conflicts",
                "Source preview",
            ]
        )

        with tab_import:
            st.write("First 1,000 rows of the generated OMEGA import file.")
            st.dataframe(result.output_df.head(1000), use_container_width=True)

        with tab_report:
            report_df = result.report_df

            if report_df.empty:
                st.success("No validation issues detected.")
            else:
                report_types = ["All"] + sorted(report_df["type"].unique().tolist())
                selected_type = st.selectbox(
                    "Filter by issue type",
                    report_types,
                    key="report_type_filter",
                )

                filtered_report = report_df

                if selected_type != "All":
                    filtered_report = report_df[report_df["type"] == selected_type]

                st.dataframe(filtered_report, use_container_width=True)

        with tab_missing:
            missing_report = result.report_df[
                result.report_df["type"].isin(
                    [
                        "missing_journal",
                        "unmatched_journal",
                        "missing_indicator",
                        "invalid_year",
                        "invalid_jif",
                        "invalid_quartile",
                    ]
                )
            ]

            if missing_report.empty:
                st.success("No missing or unmatched records detected.")
            else:
                st.dataframe(missing_report, use_container_width=True)

        with tab_duplicates:
            duplicate_report = result.report_df[
                result.report_df["type"].isin(
                    [
                        "duplicate_issn",
                        "duplicate_import_row",
                        "conflicting_value",
                    ]
                )
            ]

            if duplicate_report.empty:
                st.success("No duplicate or conflicting records detected.")
            else:
                st.dataframe(duplicate_report, use_container_width=True)

        with tab_source:
            if "source_preview" in st.session_state:
                st.write("First 50 rows of the uploaded source file.")
                st.dataframe(
                    st.session_state.source_preview,
                    use_container_width=True,
                )
            else:
                st.info("No source preview available.")

else:
    st.info("Upload an InCites Excel export to begin.")
