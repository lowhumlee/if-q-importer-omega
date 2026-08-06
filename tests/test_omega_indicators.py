import pandas as pd

from omega_indicators import TransformConfig, transform_incodes


def test_ifwos_svalue_hardcoded_to_2():
    df = pd.DataFrame(
        [
            {
                "ISSN": "1234-5678",
                "eISSN": "",
                "Publication Year": "2023",
                "Journal Impact Factor": "2.5",
                "JIF Quartile": "Q3",
                "Name": "TEST JOURNAL",
            }
        ]
    )

    config = TransformConfig()
    result = transform_incodes(df, config)

    out = result.output_df

    ifwos_rows = out[out["systemName"] == "IFWoS"]
    assert len(ifwos_rows) == 1

    ifwos_row = ifwos_rows.iloc[0]

    assert ifwos_row["issn"] == "1234-5678"
    assert ifwos_row["year"] == "2023"
    assert ifwos_row["value"] == "2.5"
    assert ifwos_row["svalue"] == "2"


def test_jif_quartile_maps_q3_to_3_and_svalue_blank():
    df = pd.DataFrame(
        [
            {
                "ISSN": "1234-5678",
                "eISSN": "",
                "Publication Year": "2023",
                "Journal Impact Factor": "2.5",
                "JIF Quartile": "Q3",
                "Name": "TEST JOURNAL",
            }
        ]
    )

    config = TransformConfig()
    result = transform_incodes(df, config)

    out = result.output_df

    quartile_rows = out[out["systemName"] == "JIFQuartile"]
    assert len(quartile_rows) == 1

    quartile_row = quartile_rows.iloc[0]

    assert quartile_row["value"] == "3"
    assert quartile_row["svalue"] == ""


def test_eissn_fallback_when_issn_missing():
    df = pd.DataFrame(
        [
            {
                "ISSN": "",
                "eISSN": "2673-7051",
                "Publication Year": "2024",
                "Journal Impact Factor": "0.8",
                "JIF Quartile": "Q4",
                "Name": "ADOLESCENTS",
            }
        ]
    )

    config = TransformConfig(include_eissn_column=True)
    result = transform_incodes(df, config)

    out = result.output_df

    assert len(out) == 2

    assert (out["issn"] == "").all()
    assert (out["eissn"] == "2673-7051").all()


def test_missing_quartile_does_not_create_quartile_row():
    df = pd.DataFrame(
        [
            {
                "ISSN": "1108-7471",
                "eISSN": "1792-7463",
                "Publication Year": "2022",
                "Journal Impact Factor": "2.2",
                "JIF Quartile": "",
                "Name": "ANNALS OF GASTROENTEROLOGY",
            }
        ]
    )

    config = TransformConfig()
    result = transform_incodes(df, config)

    out = result.output_df

    assert len(out) == 1
    assert out.iloc[0]["systemName"] == "IFWoS"
    assert out.iloc[0]["value"] == "2.2"
    assert out.iloc[0]["svalue"] == "2"


def test_duplicate_rows_are_removed_and_reported():
    df = pd.DataFrame(
        [
            {
                "ISSN": "0139-3006",
                "eISSN": "1588-2535",
                "Publication Year": "2024",
                "Journal Impact Factor": "1",
                "JIF Quartile": "Q4",
                "Name": "ACTA ALIMENTARIA",
            },
            {
                "ISSN": "0139-3006",
                "eISSN": "1588-2535",
                "Publication Year": "2024",
                "Journal Impact Factor": "1",
                "JIF Quartile": "Q4",
                "Name": "ACTA ALIMENTARIA",
            },
        ]
    )

    config = TransformConfig()
    result = transform_incodes(df, config)

    out = result.output_df

    assert len(out) == 2

    assert not result.report_df.empty
    assert result.summary["duplicate_source_rows"] >= 1
