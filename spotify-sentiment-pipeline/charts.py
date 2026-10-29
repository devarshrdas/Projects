"""Altair chart builders for the dashboard.

Colors come from a validated palette: one accent blue for the series that
carries the point, a warm gray for context, and a red to blue diverging
scale for star ratings. Text always uses ink colors, never series colors.
"""
import altair as alt
import pandas as pd

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
ACCENT = "#2a78d6"
CONTEXT = "#c3c2b7"
FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
BAR = 18
ROW = 30


def finish(chart, height):
    """Shared chrome: surface, type, hairline grid, no view border."""
    return (
        chart.properties(height=height, background=SURFACE,
                         padding={"left": 6, "right": 16, "top": 24, "bottom": 6})
        .configure(font=FONT)
        .configure_view(stroke=None)
        .configure_axis(labelColor=INK_2, titleColor=INK_2, labelFontSize=12,
                        titleFontSize=12, titleFontWeight="normal", gridColor=GRID,
                        gridWidth=1, domainColor=AXIS, tickColor=AXIS, labelPadding=6)
        .configure_legend(labelColor=INK_2, titleColor=INK_2, labelFontSize=12,
                          titleFontSize=12, titleFontWeight="normal", symbolSize=120)
        .configure_text(font=FONT)
    )


def _hover(field):
    return alt.selection_point(on="pointerover", fields=[field], empty=False,
                               clear="pointerout")


def feature_volume(df, highlight=2):
    """Horizontal bars: negative reviews per feature, top features in the accent."""
    d = df.reset_index(drop=True).copy()
    d["emph"] = d.index < highlight
    d["tip"] = d["negative"].map("{:,}".format)
    order = d["label"].tolist()
    hover = _hover("label")

    y = alt.Y("label:N", sort=order, title=None,
              axis=alt.Axis(domain=False, ticks=False, labelPadding=10,
                            labelFontSize=13, labelColor=INK, labelLimit=200))
    x = alt.X("negative:Q", title=None, axis=None,
              scale=alt.Scale(domain=[0, d["negative"].max() * 1.15]))
    tooltip = [
        alt.Tooltip("negative:Q", title="Negative reviews", format=","),
        alt.Tooltip("label:N", title="Feature"),
        alt.Tooltip("share_of_all_negative:Q", title="Share of all negative reviews", format=".0%"),
        alt.Tooltip("mentions:Q", title="All reviews mentioning it", format=","),
        alt.Tooltip("neg_share:Q", title="Of those, negative", format=".0%"),
    ]
    bars = alt.Chart(d).mark_bar(size=BAR, cornerRadiusEnd=4).encode(
        y=y, x=x,
        color=alt.condition("datum.emph", alt.value(ACCENT), alt.value(CONTEXT)),
        opacity=alt.condition(hover, alt.value(0.75), alt.value(1)),
        tooltip=tooltip,
    ).add_params(hover)
    labels = alt.Chart(d).mark_text(align="left", dx=6, fontSize=12, color=INK_2).encode(
        y=y, x=x, text="tip:N", tooltip=tooltip)
    return finish(bars + labels, height=len(d) * ROW)


def feature_severity(df, baseline, threshold=0.6, min_mentions=20):
    """Horizontal bars: share of mentions that are negative, against a baseline rule."""
    d = df[df["mentions"] >= min_mentions].sort_values("neg_share", ascending=False).copy()
    d["emph"] = d["neg_share"] >= threshold
    d["tip"] = d["neg_share"].map("{:.0%}".format)
    d["row"] = d["label"] + " (" + d["mentions"].map("{:,}".format) + ")"
    order = d["row"].tolist()
    hover = _hover("row")

    y = alt.Y("row:N", sort=order, title=None,
              axis=alt.Axis(domain=False, ticks=False, labelPadding=10,
                            labelFontSize=13, labelColor=INK, labelLimit=220))
    x = alt.X("neg_share:Q", title=None, axis=None, scale=alt.Scale(domain=[0, 1.1]))
    tooltip = [
        alt.Tooltip("neg_share:Q", title="Negative", format=".0%"),
        alt.Tooltip("label:N", title="Feature"),
        alt.Tooltip("mentions:Q", title="Reviews mentioning it", format=","),
        alt.Tooltip("negative:Q", title="Negative reviews", format=","),
    ]
    bars = alt.Chart(d).mark_bar(size=BAR, cornerRadiusEnd=4).encode(
        y=y, x=x,
        color=alt.condition("datum.emph", alt.value(ACCENT), alt.value(CONTEXT)),
        opacity=alt.condition(hover, alt.value(0.75), alt.value(1)),
        tooltip=tooltip,
    ).add_params(hover)
    labels = alt.Chart(d).mark_text(align="left", dx=6, fontSize=12, color=INK_2).encode(
        y=y, x=x, text="tip:N", tooltip=tooltip)

    base = pd.DataFrame({"x": [baseline],
                         "text": [f"No feature mentioned: {baseline:.0%}"]})
    rule = alt.Chart(base).mark_rule(color=INK_2, strokeWidth=1).encode(x="x:Q")
    rule_label = alt.Chart(base).mark_text(
        align="left", dx=4, y=-12, fontSize=11, color=INK_2).encode(x="x:Q", text="text:N")
    return finish(bars + labels + rule + rule_label, height=len(d) * ROW)
