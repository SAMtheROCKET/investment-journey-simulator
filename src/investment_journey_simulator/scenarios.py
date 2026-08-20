"""Saving and restoring a whole scenario as portable JSON."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

SCENARIO_VERSION_STR: str = "2.1"
SCENARIO_FILE_NAME_STR: str = "sip_scenario.json"
SCENARIO_MIME_TYPE_STR: str = "application/json"
VERSION_KEY_STR: str = "scenario_version"
SETTINGS_KEY_STR: str = "settings"
FUNDS_KEY_STR: str = "funds"
INFLATION_KEY_STR: str = "inflation_percent"
EXPENSE_MODEL_KEY_STR: str = "expense_model"
SLAB_RATE_KEY_STR: str = "slab_rate_percent"
LOADED_SCENARIO_STATE_KEY_STR: str = "loaded_scenario_dict"
SECTION_HEADING_STR: str = "Save / load this scenario"


def encode_json_value(value_object: Any) -> Any:
    """Convert one value into something JSON can represent.

    Brief:
        Dates become ISO strings and nested dataclasses become
        dictionaries, so a whole settings tree round-trips.

    Arguments:
        value_object (Any): Value being encoded.

    Returns:
        Any: JSON-serialisable equivalent.

    Warning:
        Unknown objects fall back to their string form.
    """
    if isinstance(value_object, (date, pd.Timestamp)):
        return pd.Timestamp(value_object).date().isoformat()
    if is_dataclass(value_object) and not isinstance(
        value_object, type
    ):
        return {
            key_str: encode_json_value(nested_value)
            for key_str, nested_value in asdict(
                value_object
            ).items()
        }
    if isinstance(value_object, dict):
        return {
            str(key_str): encode_json_value(nested_value)
            for key_str, nested_value in value_object.items()
        }
    if isinstance(value_object, (list, tuple)):
        return [
            encode_json_value(nested_value)
            for nested_value in value_object
        ]
    if isinstance(value_object, (str, int, float, bool)):
        return value_object
    if value_object is None:
        return None
    return str(value_object)


def build_scenario_dict(
    sidebar_selections: Any,
    fund_table_dataframe: pd.DataFrame,
) -> dict[str, Any]:
    """Capture every input of the current run.

    Brief:
        The fund table plus the sidebar selections are everything
        needed to reproduce a result exactly.

    Arguments:
        sidebar_selections (Any): Collected sidebar inputs.
        fund_table_dataframe (pd.DataFrame): Fund inputs.

    Returns:
        Dict[str, Any]: JSON-serialisable scenario.

    Warning:
        Results are never saved, only the inputs that create them.
    """
    return {
        VERSION_KEY_STR: SCENARIO_VERSION_STR,
        SETTINGS_KEY_STR: encode_json_value(
            sidebar_selections.settings
        ),
        INFLATION_KEY_STR: float(
            sidebar_selections.inflation_percent_float
        ),
        SLAB_RATE_KEY_STR: float(
            sidebar_selections.slab_rate_percent_float
        ),
        EXPENSE_MODEL_KEY_STR: (
            sidebar_selections.expense_model_str
        ),
        FUNDS_KEY_STR: encode_json_value(
            fund_table_dataframe.to_dict(orient="records")
        ),
    }


def build_scenario_json_bytes(
    scenario_dict: dict[str, Any],
) -> bytes:
    """Serialise a scenario into downloadable bytes.

    Brief:
        Indented output so a saved plan stays readable and can be
        diffed in version control.

    Arguments:
        scenario_dict (Dict[str, Any]): Scenario to serialise.

    Returns:
        bytes: Encoded JSON document.

    Warning:
        Encoded as UTF-8, so the rupee symbol survives.
    """
    return json.dumps(
        scenario_dict, indent=2, ensure_ascii=False
    ).encode("utf-8")


def parse_scenario_dict(uploaded_bytes: bytes) -> dict[str, Any]:
    """Read a saved scenario back into a dictionary.

    Brief:
        Validates only the version marker, because the fund table
        is rebuilt defensively downstream anyway.

    Arguments:
        uploaded_bytes (bytes): Uploaded JSON document.

    Returns:
        Dict[str, Any]: Parsed scenario.

    Warning:
        Raises when the document is not valid JSON.
    """
    scenario_dict = json.loads(uploaded_bytes.decode("utf-8"))
    if VERSION_KEY_STR not in scenario_dict:
        raise ValueError(
            "This file does not look like a saved scenario."
        )
    return scenario_dict


def render_scenario_controls(
    sidebar_selections: Any,
    fund_table_dataframe: pd.DataFrame,
) -> None:
    """Render the save and load controls for a scenario.

    Brief:
        Saving is instant; loading restores the fund table and
        reports which sidebar values to set by hand.

    Arguments:
        sidebar_selections (Any): Collected sidebar inputs.
        fund_table_dataframe (pd.DataFrame): Fund inputs.

    Returns:
        None: Widgets are written to the page.

    Warning:
        Streamlit widgets cannot be set programmatically after
        they are drawn, so sidebar values are reported rather than
        applied.
    """
    with st.expander(SECTION_HEADING_STR):
        st.download_button(
            label="Save scenario as JSON",
            data=build_scenario_json_bytes(
                build_scenario_dict(
                    sidebar_selections, fund_table_dataframe
                )
            ),
            file_name=SCENARIO_FILE_NAME_STR,
            mime=SCENARIO_MIME_TYPE_STR,
        )
        uploaded_file = st.file_uploader(
            "Load a saved scenario", type=["json"]
        )
        if uploaded_file is not None:
            _apply_uploaded_scenario(uploaded_file)


def _apply_uploaded_scenario(uploaded_file: Any) -> None:
    """Restore the fund table from an uploaded scenario.

    Brief:
        The fund table is state we own, so it can be restored
        directly; sidebar widgets are reported instead.

    Arguments:
        uploaded_file (Any): Uploaded file handle.

    Returns:
        None: Session state is updated and a note is shown.

    Warning:
        A malformed file shows an error and changes nothing.
    """
    from investment_journey_simulator.ui.fund_inputs import (
        FUND_TABLE_STATE_KEY_STR,
    )

    try:
        scenario_dict = parse_scenario_dict(uploaded_file.getvalue())
    except (ValueError, json.JSONDecodeError) as parse_error:
        st.error(f"Could not read that file: {parse_error}")
        return
    st.session_state[FUND_TABLE_STATE_KEY_STR] = pd.DataFrame(
        scenario_dict.get(FUNDS_KEY_STR, [])
    )
    st.session_state[LOADED_SCENARIO_STATE_KEY_STR] = scenario_dict
    st.success(
        "Fund table restored. Set the sidebar to: "
        f"inflation {scenario_dict.get(INFLATION_KEY_STR)}%, "
        f"slab {scenario_dict.get(SLAB_RATE_KEY_STR)}%, "
        f"expense model {scenario_dict.get(EXPENSE_MODEL_KEY_STR)}."
    )
