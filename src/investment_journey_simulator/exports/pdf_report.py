"""Printable report export rendered with reportlab and kaleido."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Optional

import pandas as pd
import plotly.graph_objects as go

IS_PDF_TOOLCHAIN_AVAILABLE_BOOL: bool = True
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Image as ReportLabImage,
    )
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        TableStyle,
    )
    from reportlab.platypus.tables import LongTable
except ImportError:  # pragma: no cover - optional dependency
    IS_PDF_TOOLCHAIN_AVAILABLE_BOOL = False

FIGURE_SCALE_INT: int = 2
FIGURE_WIDTH_CM_FLOAT: float = 26.0
FIGURE_HEIGHT_CM_FLOAT: float = 16.0
PAGE_MARGIN_CM_FLOAT: float = 1.2
TABLE_FONT_SIZE_INT: int = 7
TABLE_PADDING_INT: int = 3
FOOTER_FONT_SIZE_INT: int = 7
FOOTER_MARGIN_CM_FLOAT: float = 0.6


def render_figure_as_png_bytes(figure: go.Figure) -> bytes:
    """Render a Plotly figure into in-memory image bytes.

    Brief:
        Keeps the image in memory so no temporary file is needed.

    Arguments:
        figure (go.Figure): Figure to rasterise.

    Returns:
        bytes: Encoded image of the figure.

    Warning:
        Requires a working kaleido installation and raises when it
        is missing or misconfigured.
    """
    return figure.to_image(format="png", scale=FIGURE_SCALE_INT)


def draw_page_footer(canvas_object, document_object) -> None:
    """Stamp every page with a timestamp and a page number.

    Brief:
        A printed plan without a date is unusable six months
        later, so both are drawn on every page.

    Arguments:
        canvas_object: Reportlab canvas of the page.
        document_object: Document being rendered.

    Returns:
        None: The footer is drawn on the current page.

    Warning:
        Called by reportlab, never directly.
    """
    canvas_object.saveState()
    canvas_object.setFont("Helvetica", FOOTER_FONT_SIZE_INT)
    footer_text_str = (
        f"Generated {datetime.now():%d %b %Y %H:%M} | "
        f"Page {document_object.page}"
    )
    canvas_object.drawRightString(
        document_object.pagesize[0] - PAGE_MARGIN_CM_FLOAT * cm,
        FOOTER_MARGIN_CM_FLOAT * cm,
        footer_text_str,
    )
    canvas_object.restoreState()


def build_pdf_report_bytes(
    dashboard_title_str: str,
    nominal_summary_lines_list: list[str],
    real_summary_lines_list: list[str],
    notes_lines_list: list[str],
    nominal_figure: go.Figure,
    real_figure: go.Figure,
    nominal_summary_dataframe: pd.DataFrame,
    real_summary_dataframe: pd.DataFrame,
    scenario_dataframe: pd.DataFrame | None = None,
) -> bytes:
    """Build a landscape report snapshot of one simulation run.

    Brief:
        Pairs each dashboard image with its per-fund table and ends
        with the method notes and cautions.

    Arguments:
        dashboard_title_str (str): Report title.
        nominal_summary_lines_list (List[str]): Nominal totals.
        real_summary_lines_list (List[str]): Real totals.
        notes_lines_list (List[str]): Method notes and cautions.
        nominal_figure (go.Figure): Nominal dashboard figure.
        real_figure (go.Figure): Inflation-adjusted figure.
        nominal_summary_dataframe (pd.DataFrame): Nominal table.
        real_summary_dataframe (pd.DataFrame): Real table.
        scenario_dataframe (Optional[pd.DataFrame]): Appendix.

    Returns:
        bytes: Complete report ready for download.

    Warning:
        Raises when reportlab is not installed.
    """
    _require_pdf_toolchain()
    story_list = _build_story_list(
        dashboard_title_str,
        _build_section_argument_list(
            nominal_summary_lines_list,
            real_summary_lines_list,
            nominal_figure,
            real_figure,
            nominal_summary_dataframe,
            real_summary_dataframe,
        ),
        notes_lines_list,
    )
    _append_appendix(story_list, scenario_dataframe)
    return _render_story_bytes(story_list, dashboard_title_str)


def _require_pdf_toolchain() -> None:
    """Fail loudly when the optional report toolchain is absent.

    Brief:
        Turns a confusing import error into an actionable message.

    Arguments:
        None.

    Returns:
        None: Returns when the toolchain is available.

    Warning:
        Raises a runtime error otherwise.
    """
    if not IS_PDF_TOOLCHAIN_AVAILABLE_BOOL:
        raise RuntimeError(
            "reportlab is required for report export; install it "
            "with: pip install reportlab kaleido"
        )


def _append_appendix(
    story_list: list,
    scenario_dataframe: pd.DataFrame | None,
) -> None:
    """Add the scenario appendix when inputs were supplied.

    Brief:
        Skipped silently when no fund table was passed.

    Arguments:
        story_list (List): Story being extended.
        scenario_dataframe (Optional[pd.DataFrame]): Inputs.

    Returns:
        None: The story is extended in place.

    Warning:
        An empty table is treated as no table.
    """
    if scenario_dataframe is None or scenario_dataframe.empty:
        return
    story_list.append(PageBreak())
    story_list.extend(
        _build_appendix_flowables_list(scenario_dataframe)
    )


def _build_appendix_flowables_list(
    scenario_dataframe: pd.DataFrame,
) -> list:
    """Build the appendix listing the exact inputs used.

    Brief:
        A report that cannot be reproduced is not evidence, so the
        fund table travels with it.

    Arguments:
        scenario_dataframe (pd.DataFrame): Fund inputs.

    Returns:
        List: Flowables for the appendix page.

    Warning:
        Wide fund tables render in a very small font.
    """
    style_sheet = getSampleStyleSheet()
    return [
        Paragraph(
            "<b>Appendix: scenario inputs</b>",
            style_sheet["Heading2"],
        ),
        Spacer(1, 8),
        _build_summary_table(scenario_dataframe),
    ]


def _build_story_list(
    dashboard_title_str: str,
    section_argument_list: list[tuple],
    notes_lines_list: list[str],
) -> list:
    """Assemble the title, both sections and the closing notes.

    Brief:
        Each section is followed by a page break so the printed
        report keeps one topic per page.

    Arguments:
        dashboard_title_str (str): Report title.
        section_argument_list (List[tuple]): Section arguments.
        notes_lines_list (List[str]): Method notes and cautions.

    Returns:
        List: Ordered flowables of the whole report.

    Warning:
        Building this list rasterises every figure.
    """
    style_sheet = getSampleStyleSheet()
    story_list = [
        Paragraph(
            f"<b>{dashboard_title_str}</b>", style_sheet["Title"]
        ),
        Spacer(1, 10),
    ]
    for section_argument_tuple in section_argument_list:
        story_list.extend(
            _build_section_flowables_list(
                style_sheet, *section_argument_tuple
            )
        )
        story_list.append(PageBreak())
    story_list.extend(
        _build_notes_flowables_list(style_sheet, notes_lines_list)
    )
    return story_list


def _build_section_argument_list(
    nominal_summary_lines_list: list[str],
    real_summary_lines_list: list[str],
    nominal_figure: go.Figure,
    real_figure: go.Figure,
    nominal_summary_dataframe: pd.DataFrame,
    real_summary_dataframe: pd.DataFrame,
) -> list[tuple]:
    """Pair each run with the headings its section needs.

    Brief:
        Both report sections share one builder, so their varying
        parts are collected here as argument tuples.

    Arguments:
        nominal_summary_lines_list (List[str]): Nominal totals.
        real_summary_lines_list (List[str]): Real totals.
        nominal_figure (go.Figure): Nominal dashboard figure.
        real_figure (go.Figure): Inflation-adjusted figure.
        nominal_summary_dataframe (pd.DataFrame): Nominal table.
        real_summary_dataframe (pd.DataFrame): Real table.

    Returns:
        List[tuple]: One argument tuple per report section.

    Warning:
        Tuple order must match the section builder signature.
    """
    return [
        (
            "Portfolio Summary (Nominal)",
            nominal_summary_lines_list,
            nominal_figure,
            "Per-Fund Summary (Nominal)",
            nominal_summary_dataframe,
        ),
        (
            "Portfolio Summary (Real)",
            real_summary_lines_list,
            real_figure,
            "Per-Fund Summary (Real)",
            real_summary_dataframe,
        ),
    ]


def _build_notes_flowables_list(
    style_sheet,
    notes_lines_list: list[str],
) -> list:
    """Build the closing notes page of the report.

    Brief:
        Blank lines become spacing so the block keeps the shape it
        has on screen.

    Arguments:
        style_sheet: Paragraph styles supplied by reportlab.
        notes_lines_list (List[str]): Method notes and cautions.

    Returns:
        List: Flowables ready to append to the report story.

    Warning:
        Markup inside the note lines is interpreted as rich text.
    """
    notes_flowable_list = [
        Paragraph(
            "<b>Notes, cautions and how to use</b>",
            style_sheet["Heading2"],
        )
    ]
    for note_line_str in notes_lines_list:
        notes_flowable_list.append(
            Paragraph(
                note_line_str or "&nbsp;", style_sheet["BodyText"]
            )
        )
    return notes_flowable_list


def _build_section_flowables_list(
    style_sheet,
    summary_heading_str: str,
    summary_lines_list: list[str],
    figure: go.Figure,
    table_heading_str: str,
    summary_dataframe: pd.DataFrame,
) -> list:
    """Build one report section of totals, chart and table.

    Brief:
        The nominal and real halves of the report share the same
        layout, so they share this builder.

    Arguments:
        style_sheet: Paragraph styles supplied by reportlab.
        summary_heading_str (str): Heading above the totals.
        summary_lines_list (List[str]): Total lines to print.
        figure (go.Figure): Dashboard figure of the section.
        table_heading_str (str): Heading above the fund table.
        summary_dataframe (pd.DataFrame): Per-fund table.

    Returns:
        List: Flowables ready to append to the report story.

    Warning:
        Rasterising the figure is the slowest step of the export.
    """
    section_flowable_list = [
        Paragraph(f"<b>{summary_heading_str}</b>",
                  style_sheet["Heading2"]),
    ]
    section_flowable_list.extend(
        Paragraph(summary_line_str, style_sheet["BodyText"])
        for summary_line_str in summary_lines_list
    )
    section_flowable_list.append(Spacer(1, 10))
    section_flowable_list.append(_build_figure_flowable(figure))
    section_flowable_list.append(Spacer(1, 10))
    section_flowable_list.append(
        Paragraph(f"<b>{table_heading_str}</b>",
                  style_sheet["Heading2"])
    )
    section_flowable_list.append(
        _build_summary_table(summary_dataframe)
    )
    return section_flowable_list


def _build_figure_flowable(figure: go.Figure):
    """Rasterise a figure into a page-sized report image.

    Brief:
        Sizes the image to the printable width of a landscape
        page so nothing is clipped.

    Arguments:
        figure (go.Figure): Figure to place on the page.

    Returns:
        ReportLabImage: Image flowable ready for the story.

    Warning:
        Requires a working kaleido installation.
    """
    return ReportLabImage(
        BytesIO(render_figure_as_png_bytes(figure)),
        width=FIGURE_WIDTH_CM_FLOAT * cm,
        height=FIGURE_HEIGHT_CM_FLOAT * cm,
    )


def _build_summary_table(summary_dataframe: pd.DataFrame):
    """Convert a per-fund table into a styled report table.

    Brief:
        Uses a long table so that many funds can span pages while
        repeating the header row.

    Arguments:
        summary_dataframe (pd.DataFrame): Per-fund table.

    Returns:
        LongTable: Styled, page-splitting table flowable.

    Warning:
        Every value is stringified, so numeric alignment is lost.
    """
    table_data_list = [list(summary_dataframe.columns)]
    table_data_list.extend(
        summary_dataframe.astype(str).values.tolist()
    )
    summary_table = LongTable(table_data_list, repeatRows=1)
    summary_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), TABLE_FONT_SIZE_INT),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), TABLE_PADDING_INT),
                ("RIGHTPADDING", (0, 0), (-1, -1), TABLE_PADDING_INT),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return summary_table


def _render_story_bytes(
    story_list: list,
    dashboard_title_str: str,
) -> bytes:
    """Lay the assembled flowables onto landscape pages.

    Brief:
        Landscape pages keep the wide per-fund tables readable.

    Arguments:
        story_list (List): Flowables to lay out.
        dashboard_title_str (str): Document metadata title.

    Returns:
        bytes: Rendered document bytes.

    Warning:
        Rendering mutates the flowables, so a story can be built
        into a document only once.
    """
    document_buffer = BytesIO()
    document = SimpleDocTemplate(
        document_buffer,
        pagesize=landscape(A4),
        leftMargin=PAGE_MARGIN_CM_FLOAT * cm,
        rightMargin=PAGE_MARGIN_CM_FLOAT * cm,
        topMargin=PAGE_MARGIN_CM_FLOAT * cm,
        bottomMargin=PAGE_MARGIN_CM_FLOAT * cm,
        title=dashboard_title_str,
    )
    document.build(
        story_list,
        onFirstPage=draw_page_footer,
        onLaterPages=draw_page_footer,
    )
    return document_buffer.getvalue()
