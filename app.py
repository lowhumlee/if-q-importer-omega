import streamlit as st
import pandas as pd

# Safely import the core logic
try:
    from omega_indicators import TransformConfig, get_excel_sheet_names, read_uploaded_file, transform_incodes
    IMPORT_SUCCESS = True
except Exception as e:
    IMPORT_SUCCESS = False
    st.error(f"❌ Failed to import omega_indicators module: {e}")

st.set_page_config(page_title="OMEGA PSIR Journal Indicators", layout="wide")
st.title("OMEGA PSIR Journal Indicators Generator")

if not IMPORT_SUCCESS:
    st.stop()

uploaded_file = st.file_uploader("Upload InCites export (.xlsx or .csv)", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    st.info("File uploaded. Processing...")
    
    try:
        # 1. Read the file
        df = read_uploaded_file(uploaded_file)
        st.write("✅ Preview of uploaded data:")
        st.dataframe(df.head())
        
        # 2. Configure transformation (Hardcoded svalue='2' for IFWoS)
        config = TransformConfig(
            hardcode_ifwos_svalue=True,
            ifwos_svalue="2",
            include_eissn_column=True,
            sort_output=True
        )
        
        # 3. Transform
        result = transform_incodes(df, config)
        st.success(f"✅ Transformation complete! Generated {result.summary['output_rows']} rows.")
        
        # 4. Provide downloads
        import_csv = result.output_df.to_csv(sep=";", index=False)
        report_csv = result.report_df.to_csv(sep=";", index=False)
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("📥 Download OMEGA Import CSV", import_csv, "OMEGA_import.csv", "text/csv")
        with col2:
            st.download_button("📥 Download Validation Report", report_csv, "validation_report.csv", "text/csv")
            
    except Exception as e:
        st.error("❌ An error occurred during processing:")
        st.exception(e)  # THIS WILL SHOW THE EXACT ERROR INSTEAD OF LOOPING
