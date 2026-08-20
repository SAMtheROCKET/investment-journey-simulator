"""Asset table widgets for both instalment entry modes.

The engine has never cared what an asset is called. It applies
the rate and the tax treatment you give a row, so a row may be
a mutual fund, a stock, gold, land, a deposit or something you
name yourself. The captions say "asset" rather than "fund" so
the interface stops contradicting that.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from investment_journey_simulator.asset_presets import (
    ALL_PRESET_NAME_TUPLE,
    ASSET_PRESET_TUPLE,
    describe_preset_str,
)
from investment_journey_simulator.constants import (
    COLUMN_ALLOCATION_PERCENT_STR,
    COLUMN_EXEMPTION_AMOUNT_STR,
    COLUMN_EXEMPTION_SCOPE_STR,
    COLUMN_EXIT_LOAD_MONTHS_STR,
    COLUMN_EXIT_LOAD_STR,
    COLUMN_EXPENSE_STR,
    COLUMN_FUND_NAME_STR,
    COLUMN_FUND_START_STR,
    COLUMN_FUND_STEPUP_STR,
    COLUMN_GROSS_RETURN_STR,
    COLUMN_INITIAL_INVESTMENT_STR,
    COLUMN_LONG_TERM_MONTHS_STR,
    COLUMN_LONG_TERM_TAX_STR,
    COLUMN_MONTHLY_SIP_STR,
    COLUMN_OVERRIDE_PRESET_STR,
    COLUMN_PRESET_STR,
    COLUMN_SHORT_TERM_TAX_STR,
    COLUMN_TARGET_ALLOCATION_STR,
    COLUMN_TRANSACTION_TAX_STR,
    EXEMPTION_SCOPES_TUPLE,
    PERCENT_TOTAL_FLOAT,
)
from investment_journey_simulator.currency import Currency
from investment_journey_simulator.formatting import resolve_display_currency
from investment_journey_simulator.fund_builder import (
    apply_tax_presets_to_dataframe,
    build_additional_fund_row_dict,
    build_default_fund_dataframe,
    build_fund_row_dict,
)

FUND_TABLE_STATE_KEY_STR: str = "fund_table_dataframe"
ALLOCATION_TABLE_STATE_KEY_STR: str = "allocation_table_dataframe"
TOTAL_INSTALMENT_STATE_KEY_STR: str = "total_monthly_instalment"
MANUAL_MODE_LABEL_STR: str = "Per-fund SIP (manual)"
ALLOCATION_MODE_LABEL_STR: str = "Total SIP -> Allocate by %"
DEFAULT_TOTAL_INSTALMENT_FLOAT: float = 4000.0
DEFAULT_ALLOCATION_PERCENT_FLOAT: float = 50.0
DEFAULT_DERIVED_RETURN_PERCENT_FLOAT: float = 12.0
DEFAULT_DERIVED_EXPENSE_PERCENT_FLOAT: float = 0.50

HELP_BOTH_SHOWS_A_SLIDER_STR: str = (
    "Both shows a slider and a box. Typing is the only way to "
    "land on an exact figure."
)


def render_fund_table_dataframe(
    portfolio_start_date: date,
    slab_rate_percent_float: float,
    is_stagger_enabled_bool: bool,
    currency: Currency | None = None,
) -> pd.DataFrame:
    """Render the fund inputs and return the edited table.

    Brief:
        Offers a manual per-fund mode and a total-plus-allocation
        mode that derives the per-fund instalments.

    Arguments:
        portfolio_start_date (date): First simulated month.
        slab_rate_percent_float (float): Investor slab rate.
        is_stagger_enabled_bool (bool): Per-fund start dates.
        currency (Optional[Currency]): Label currency.

    Returns:
        pd.DataFrame: Fund table with tax presets applied.

    Warning:
        The allocation mode always forces one shared start date.
    """
    _initialise_session_state(portfolio_start_date)
    st.subheader("Your assets")
    render_asset_scope_note()
    input_mode_str = st.radio(
        "Choose input mode",
        help=HELP_BOTH_SHOWS_A_SLIDER_STR,
        options=[MANUAL_MODE_LABEL_STR, ALLOCATION_MODE_LABEL_STR],
        index=0,
        horizontal=True,
    )
    if input_mode_str == MANUAL_MODE_LABEL_STR:
        edited_dataframe = _render_manual_mode_dataframe(
            portfolio_start_date,
            slab_rate_percent_float,
            is_stagger_enabled_bool,
        )
    else:
        edited_dataframe = _render_allocation_mode_dataframe(
            portfolio_start_date, slab_rate_percent_float, currency
        )
    st.session_state[FUND_TABLE_STATE_KEY_STR] = edited_dataframe
    return apply_tax_presets_to_dataframe(
        edited_dataframe, slab_rate_percent_float
    )


ASSET_SCOPE_SUMMARY_STR: str = (
    "Name any asset you like - and what this does not model"
)
ASSET_SCOPE_BODY_STR: str = (
    "A row can be a mutual fund, a stock, an ETF, gold, land, a "
    "deposit, a business, or something you name yourself. The "
    "engine does not care what you call it: it applies the return "
    "and the tax treatment you give the row.\n\n"
    "**What that means it does not capture.** Each asset compounds "
    "at a *steady monthly rate*. That is a fair way to ask \"what "
    "if gold returns 8% a year\". It is not how land or a single "
    "stock actually behaves - those move in jumps, cannot always "
    "be sold when you want, and carry costs on the way in and out "
    "that no percentage captures.\n\n"
    "So read a row as **your assumption, applied consistently and "
    "to the rupee** - which is genuinely useful - rather than as a "
    "simulation of that asset class."
)


def render_asset_scope_note() -> None:
    """Say what naming an asset does and does not buy you.

    Brief:
        The interface invites a reader to model land or a business,
        and it should. But the engine compounds everything at a
        steady monthly rate, and a smooth curve over an illiquid,
        lumpy asset looks far more authoritative than it is.

    Arguments:
        None.

    Returns:
        None: The note is rendered.

    Warning:
        Collapsed rather than a warning banner: this is scope, not
        an error, and a permanent red box beside every asset would
        be ignored within a week.
    """
    with st.expander(ASSET_SCOPE_SUMMARY_STR, expanded=False):
        st.markdown(ASSET_SCOPE_BODY_STR)
        _render_preset_reference()


def _render_preset_reference() -> None:
    """List each tax treatment and how far it can be trusted.

    Brief:
        Two of these are verified against the Act by section and
        date; the rest are opening values nobody has checked to
        that standard. Showing them in one list without saying
        which is which would make the sourced ones worth less
        rather than the others worth more.

    Arguments:
        None.

    Returns:
        None: The reference is rendered.

    Warning:
        Reads the sourcing flag from the preset rather than a list
        kept here, so adding a preset cannot forget to declare it.
    """
    st.markdown("**What each tax treatment assumes**")
    for preset in ASSET_PRESET_TUPLE:
        marker_str = "✅" if preset.is_sourced_bool else "⚠️"
        st.markdown(
            f"{marker_str} **{preset.name_str}** - "
            f"{describe_preset_str(preset)}"
        )
    st.caption(
        "✅ verified against the Act, by section, in "
        "docs/SOURCES.md. ⚠️ a sensible starting point that has "
        "not been verified to that standard - edit it, and tick "
        "\"Override Preset?\" to keep what you type."
    )


def _initialise_session_state(portfolio_start_date: date) -> None:
    """Seed the session tables on the first script run.

    Brief:
        Streamlit reruns the script constantly, so the editable
        tables must survive in session state.

    Arguments:
        portfolio_start_date (date): First simulated month.

    Returns:
        None: Session state is populated in place.

    Warning:
        Existing session tables are never overwritten here.
    """
    if FUND_TABLE_STATE_KEY_STR not in st.session_state:
        st.session_state[FUND_TABLE_STATE_KEY_STR] = (
            build_default_fund_dataframe(portfolio_start_date)
        )
    if ALLOCATION_TABLE_STATE_KEY_STR not in st.session_state:
        st.session_state[ALLOCATION_TABLE_STATE_KEY_STR] = (
            pd.DataFrame(
                [
                    {
                        COLUMN_FUND_NAME_STR: "Fund-A",
                        COLUMN_ALLOCATION_PERCENT_STR: (
                            DEFAULT_ALLOCATION_PERCENT_FLOAT
                        ),
                    },
                    {
                        COLUMN_FUND_NAME_STR: "Fund-B",
                        COLUMN_ALLOCATION_PERCENT_STR: (
                            DEFAULT_ALLOCATION_PERCENT_FLOAT
                        ),
                    },
                ]
            )
        )
    if TOTAL_INSTALMENT_STATE_KEY_STR not in st.session_state:
        st.session_state[TOTAL_INSTALMENT_STATE_KEY_STR] = (
            DEFAULT_TOTAL_INSTALMENT_FLOAT
        )


def _render_manual_mode_dataframe(
    portfolio_start_date: date,
    slab_rate_percent_float: float,
    is_stagger_enabled_bool: bool,
) -> pd.DataFrame:
    """Render the editable per-fund instalment table.

    Brief:
        Adds or removes funds through buttons and edits every
        parameter directly inside the table.

    Arguments:
        portfolio_start_date (date): First simulated month.
        slab_rate_percent_float (float): Investor slab rate.
        is_stagger_enabled_bool (bool): Allow per-fund start dates.

    Returns:
        pd.DataFrame: Edited fund table.

    Warning:
        Disabling staggered starts rewrites every start date.
    """
    st.caption("Enter what you put into each asset each month.")
    _render_row_buttons(portfolio_start_date)
    working_dataframe = st.session_state[
        FUND_TABLE_STATE_KEY_STR
    ].copy()
    if not is_stagger_enabled_bool:
        working_dataframe[COLUMN_FUND_START_STR] = (
            portfolio_start_date
        )
    working_dataframe = apply_tax_presets_to_dataframe(
        working_dataframe, slab_rate_percent_float
    )
    return st.data_editor(
        working_dataframe,
        width="stretch",
        num_rows="dynamic",
        column_config=_build_fund_column_config_dict(False),
    )


def _render_row_buttons(portfolio_start_date: date) -> None:
    """Render the add and remove buttons of the fund table.

    Brief:
        Keeps row management out of the table editor itself so the
        default row template stays under our control.

    Arguments:
        portfolio_start_date (date): First simulated month.

    Returns:
        None: Session state is updated in place.

    Warning:
        The last remaining fund cannot be removed.
    """
    add_column, remove_column, _spacer_column = st.columns([1, 1, 4])
    with add_column:
        if st.button("Add an asset", key="add_fund_button"):
            current_dataframe = st.session_state[
                FUND_TABLE_STATE_KEY_STR
            ]
            st.session_state[FUND_TABLE_STATE_KEY_STR] = pd.concat(
                [
                    current_dataframe,
                    pd.DataFrame(
                        [
                            build_additional_fund_row_dict(
                                len(current_dataframe),
                                portfolio_start_date,
                            )
                        ]
                    ),
                ],
                ignore_index=True,
            )
    with remove_column:
        is_removable_bool = (
            len(st.session_state[FUND_TABLE_STATE_KEY_STR]) > 1
        )
        is_pressed_bool = st.button(
            "Remove last asset", key="remove_fund_button"
        )
        if is_pressed_bool and is_removable_bool:
                st.session_state[FUND_TABLE_STATE_KEY_STR] = (
                    st.session_state[FUND_TABLE_STATE_KEY_STR]
                    .iloc[:-1]
                    .reset_index(drop=True)
                )


def _render_allocation_mode_dataframe(
    portfolio_start_date: date,
    slab_rate_percent_float: float,
    currency: Currency | None = None,
) -> pd.DataFrame:
    """Render the total instalment and allocation percentages.

    Brief:
        Splits one monthly budget across funds by weight and then
        exposes the derived funds for further editing.

    Arguments:
        portfolio_start_date (date): First simulated month.
        slab_rate_percent_float (float): Investor slab rate.
        currency (Optional[Currency]): Label currency.

    Returns:
        pd.DataFrame: Derived and edited fund table.

    Warning:
        Weights that do not add up to one hundred are normalised
        only while the normalise switch is on.
    """
    st.caption(
        "Enter the total monthly instalment and split it by "
        "percentage. All assets share the plan start date."
    )
    total_instalment_float = _render_total_instalment_float(
        currency
    )
    allocation_dataframe = _render_allocation_editor_dataframe()
    derived_dataframe = _build_derived_fund_dataframe(
        allocation_dataframe,
        total_instalment_float,
        portfolio_start_date,
    )
    derived_dataframe = apply_tax_presets_to_dataframe(
        derived_dataframe, slab_rate_percent_float
    )
    st.markdown("### Derived funds (edit returns, tax and step-up)")
    return st.data_editor(
        derived_dataframe,
        width="stretch",
        num_rows="dynamic",
        column_config=_build_fund_column_config_dict(True),
        key="derived_fund_editor",
    )


def _render_total_instalment_float(
    currency: Currency | None = None,
) -> float:
    """Render the total monthly budget input.

    Brief:
        The budget is remembered in session state so it
        survives every rerun triggered by another widget.

    Arguments:
        currency (Optional[Currency]): Label currency.

    Returns:
        float: Total monthly instalment.

    Warning:
        A zero budget produces a portfolio that never grows.
    """
    symbol_str = resolve_display_currency(currency).symbol_str
    total_instalment_float = float(
        st.number_input(
            f"Total SIP per month ({symbol_str})",
            min_value=0.0,
            step=500.0,
            help=(
                "The whole monthly budget. It is split across the "
                "funds by the weights below."
            ),
            value=float(
                st.session_state[TOTAL_INSTALMENT_STATE_KEY_STR]
            ),
            key="total_instalment_input",
        )
    )
    st.session_state[TOTAL_INSTALMENT_STATE_KEY_STR] = (
        total_instalment_float
    )
    return total_instalment_float


def _render_allocation_row_buttons() -> None:
    """Render the add and remove buttons of the weight table.

    Brief:
        Mirrors the row buttons of the manual fund table.

    Arguments:
        None.

    Returns:
        None: Session state is updated in place.

    Warning:
        The last remaining weight row cannot be removed.
    """
    current_dataframe = st.session_state[
        ALLOCATION_TABLE_STATE_KEY_STR
    ]
    if st.button("Add MF row", key="add_allocation_row"):
        new_row_dict = {
            COLUMN_FUND_NAME_STR: (
                f"MF-{len(current_dataframe) + 1}"
            ),
            COLUMN_ALLOCATION_PERCENT_STR: 0.0,
        }
        st.session_state[ALLOCATION_TABLE_STATE_KEY_STR] = (
            pd.concat(
                [current_dataframe, pd.DataFrame([new_row_dict])],
                ignore_index=True,
            )
        )


def _render_allocation_remove_button() -> None:
    """Render the button that drops the last weight row.

    Brief:
        Kept separate so each column of the toolbar renders one
        control only.

    Arguments:
        None.

    Returns:
        None: Session state is updated in place.

    Warning:
        The last remaining weight row cannot be removed.
    """
    if not st.button(
        "Remove last row", key="remove_allocation_row"
    ):
        return
    current_dataframe = st.session_state[
        ALLOCATION_TABLE_STATE_KEY_STR
    ]
    if len(current_dataframe) > 1:
        st.session_state[ALLOCATION_TABLE_STATE_KEY_STR] = (
            current_dataframe.iloc[:-1].reset_index(drop=True)
        )


def _render_allocation_editor_dataframe() -> pd.DataFrame:
    """Render the fund name and weight table with normalising.

    Brief:
        Shows the running weight total so an unbalanced split is
        obvious before the simulation runs.

    Arguments:
        None.

    Returns:
        pd.DataFrame: Edited and optionally normalised weights.

    Warning:
        An all-zero weight table leaves every instalment at zero.
    """
    add_column, remove_column, normalise_column = st.columns(
        [1, 1, 2]
    )
    with add_column:
        _render_allocation_row_buttons()
    with remove_column:
        _render_allocation_remove_button()
    edited_dataframe = st.data_editor(
        st.session_state[ALLOCATION_TABLE_STATE_KEY_STR].copy(),
        width="stretch",
        num_rows="dynamic",
        column_config={
            COLUMN_FUND_NAME_STR: st.column_config.TextColumn(
                required=True
            ),
            COLUMN_ALLOCATION_PERCENT_STR: (
                st.column_config.NumberColumn(
                    min_value=0.0, max_value=100.0, step=0.5
                )
            ),
        },
        key="allocation_editor",
    )
    edited_dataframe = _clean_allocation_dataframe(edited_dataframe)
    with normalise_column:
        edited_dataframe = _apply_weight_normalisation(
            edited_dataframe
        )
    st.session_state[ALLOCATION_TABLE_STATE_KEY_STR] = (
        edited_dataframe
    )
    return edited_dataframe


def _apply_weight_normalisation(
    allocation_dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Offer and apply rescaling of the weights to one hundred.

    Brief:
        The toggle defaults to on whenever the typed weights do
        not already add up to a full allocation.

    Arguments:
        allocation_dataframe (pd.DataFrame): Cleaned weights.

    Returns:
        pd.DataFrame: Weights, rescaled when the toggle is on.

    Warning:
        An all-zero table is returned unchanged.
    """
    weight_total_float = float(
        allocation_dataframe[COLUMN_ALLOCATION_PERCENT_STR].sum()
    )
    is_normalising_bool = st.toggle(
        "Normalise allocations to 100% (current sum: "
        f"{weight_total_float:.2f}%)",
        value=weight_total_float not in (0.0, PERCENT_TOTAL_FLOAT),
        key="allocation_normalise_toggle",
    )
    if not is_normalising_bool or weight_total_float <= 0.0:
        return allocation_dataframe
    normalised_dataframe = allocation_dataframe.copy()
    normalised_dataframe[COLUMN_ALLOCATION_PERCENT_STR] = (
        normalised_dataframe[COLUMN_ALLOCATION_PERCENT_STR]
        * PERCENT_TOTAL_FLOAT
        / weight_total_float
    )
    return normalised_dataframe


def _clean_allocation_dataframe(
    allocation_dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Normalise names and weights typed into the weight table.

    Brief:
        Blank names and non-numeric weights would otherwise break
        the derived fund table.

    Arguments:
        allocation_dataframe (pd.DataFrame): Raw edited table.

    Returns:
        pd.DataFrame: Cleaned copy of the table.

    Warning:
        Unparseable weights are silently replaced by zero.
    """
    cleaned_dataframe = allocation_dataframe.copy()
    cleaned_dataframe[COLUMN_FUND_NAME_STR] = (
        cleaned_dataframe[COLUMN_FUND_NAME_STR]
        .astype(str)
        .str.strip()
        .replace("", "Unnamed MF")
    )
    cleaned_dataframe[COLUMN_ALLOCATION_PERCENT_STR] = (
        pd.to_numeric(
            cleaned_dataframe[COLUMN_ALLOCATION_PERCENT_STR],
            errors="coerce",
        ).fillna(0.0)
    )
    return cleaned_dataframe


def _build_derived_fund_dataframe(
    allocation_dataframe: pd.DataFrame,
    total_instalment_float: float,
    portfolio_start_date: date,
) -> pd.DataFrame:
    """Derive one fund row per weight of the allocation table.

    Brief:
        Converts a single budget into per-fund instalments while
        keeping the weight as the rebalancing target.

    Arguments:
        allocation_dataframe (pd.DataFrame): Cleaned weights.
        total_instalment_float (float): Monthly budget in rupees.
        portfolio_start_date (date): First simulated month.

    Returns:
        pd.DataFrame: Derived fund table ready for editing.

    Warning:
        Derived instalments are recomputed on every rerun, so
        manual edits to that column do not survive.
    """
    derived_row_list = []
    for _, allocation_row in allocation_dataframe.iterrows():
        weight_percent_float = float(
            allocation_row[COLUMN_ALLOCATION_PERCENT_STR]
        )
        derived_row_list.append(
            build_fund_row_dict(
                fund_name_str=str(
                    allocation_row[COLUMN_FUND_NAME_STR]
                ),
                monthly_sip_float=round(
                    total_instalment_float
                    * weight_percent_float
                    / PERCENT_TOTAL_FLOAT,
                    2,
                ),
                gross_return_percent_float=(
                    DEFAULT_DERIVED_RETURN_PERCENT_FLOAT
                ),
                expense_percent_float=(
                    DEFAULT_DERIVED_EXPENSE_PERCENT_FLOAT
                ),
                start_date=portfolio_start_date,
                target_allocation_percent_float=weight_percent_float,
            )
        )
    return pd.DataFrame(derived_row_list)


def _build_fund_column_config_dict(
    is_derived_mode_bool: bool,
) -> dict:
    """Describe how every fund table column must be edited.

    Brief:
        Derived tables lock the instalment and start date because
        both are computed from the allocation inputs.

    Arguments:
        is_derived_mode_bool (bool): Lock the derived columns.

    Returns:
        dict: Column configuration for the data editor.

    Warning:
        Column labels must match the shared column constants.
    """
    column_config_dict = _build_plan_column_config_dict(
        is_derived_mode_bool
    )
    column_config_dict.update(_build_tax_column_config_dict())
    column_config_dict.update(_build_charge_column_config_dict())
    return column_config_dict


def _build_plan_column_config_dict(
    is_derived_mode_bool: bool,
) -> dict:
    """Describe how the investment columns must be edited.

    Brief:
        Naming, preset, money in, returns and target.

    Arguments:
        is_derived_mode_bool (bool): Lock derived columns.

    Returns:
        dict: Configuration of the investment columns.

    Warning:
        Locked columns recompute on every rerun.
    """
    percent_column = st.column_config.NumberColumn(
        min_value=0.0, max_value=100.0, step=0.5
    )
    return {
        COLUMN_FUND_NAME_STR: st.column_config.TextColumn(
            required=True
        ),
        COLUMN_PRESET_STR: st.column_config.SelectboxColumn(
            options=list(ALL_PRESET_NAME_TUPLE), required=True
        ),
        COLUMN_OVERRIDE_PRESET_STR: (
            st.column_config.CheckboxColumn()
        ),
        COLUMN_MONTHLY_SIP_STR: st.column_config.NumberColumn(
            min_value=0, step=100, disabled=is_derived_mode_bool
        ),
        COLUMN_INITIAL_INVESTMENT_STR: (
            st.column_config.NumberColumn(min_value=0, step=10000)
        ),
        COLUMN_FUND_STEPUP_STR: percent_column,
        COLUMN_GROSS_RETURN_STR: (
            st.column_config.NumberColumn(step=0.1)
        ),
        COLUMN_EXPENSE_STR: st.column_config.NumberColumn(
            min_value=0.0, step=0.05
        ),
        COLUMN_FUND_START_STR: st.column_config.DateColumn(
            disabled=is_derived_mode_bool
        ),
        COLUMN_TARGET_ALLOCATION_STR: percent_column,
    }


def _build_charge_column_config_dict() -> dict:
    """Describe how the exit load and STT columns are edited.

    Brief:
        Charges are separate from tax and are deducted from the
        redemption proceeds.

    Arguments:
        None.

    Returns:
        dict: Column configuration of the charge columns.

    Warning:
        STT is a fraction of a percent, so it needs three decimals.
    """
    return {
        COLUMN_EXIT_LOAD_STR: st.column_config.NumberColumn(
            min_value=0.0, max_value=10.0, step=0.25
        ),
        COLUMN_EXIT_LOAD_MONTHS_STR: (
            st.column_config.NumberColumn(
                min_value=0, max_value=120, step=1
            )
        ),
        COLUMN_TRANSACTION_TAX_STR: (
            st.column_config.NumberColumn(
                min_value=0.0, max_value=1.0, step=0.001,
                format="%.3f",
            )
        ),
    }


def _build_tax_column_config_dict() -> dict:
    """Describe how the taxation columns must be edited.

    Brief:
        Split from the plan columns to keep each builder short.

    Arguments:
        None.

    Returns:
        dict: Configuration of the taxation columns.

    Warning:
        Rates cap at sixty percent to catch typing errors.
    """
    return {
        COLUMN_SHORT_TERM_TAX_STR: st.column_config.NumberColumn(
            min_value=0.0, max_value=60.0, step=0.5
        ),
        COLUMN_LONG_TERM_TAX_STR: st.column_config.NumberColumn(
            min_value=0.0, max_value=60.0, step=0.5
        ),
        COLUMN_LONG_TERM_MONTHS_STR: (
            st.column_config.NumberColumn(
                min_value=1, max_value=9999, step=1
            )
        ),
        COLUMN_EXEMPTION_AMOUNT_STR: (
            st.column_config.NumberColumn(min_value=0, step=10000)
        ),
        COLUMN_EXEMPTION_SCOPE_STR: (
            st.column_config.SelectboxColumn(
                options=list(EXEMPTION_SCOPES_TUPLE)
            )
        ),
        COLUMN_EXIT_LOAD_STR: st.column_config.NumberColumn(
            min_value=0.0, max_value=10.0, step=0.25
        ),
        COLUMN_EXIT_LOAD_MONTHS_STR: (
            st.column_config.NumberColumn(
                min_value=0, max_value=120, step=1
            )
        ),
        COLUMN_TRANSACTION_TAX_STR: (
            st.column_config.NumberColumn(
                min_value=0.0, max_value=1.0, step=0.001,
                format="%.3f",
            )
        ),
    }
