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


STARS = ["1 star", "2 stars", "3 stars", "4 stars", "5 stars"]
STAR_COLORS = ["#c63b3a", "#ef9c9a", "#e1e0d9", "#86b6ef", "#2a78d6"]


def rating_split(df, store_order):
    """Diverging stacked bar per store, centered on the middle of 3 stars."""
    rows = []
    for store in store_order:
        g = df[df["store"] == store].set_index("rating")
        share = g["share"].reindex(range(1, 6), fill_value=0)
        count = g["reviews"].reindex(range(1, 6), fill_value=0)
        x = -(share[1] + share[2] + share[3] / 2)
        for r in range(1, 6):
            rows.append({"store": store, "rating": r, "stars": STARS[r - 1],
                         "share": share[r], "reviews": int(count[r]),
                         "x0": x, "x1": x + share[r]})
            x += share[r]
    d = pd.DataFrame(rows)
    d["mid"] = (d["x0"] + d["x1"]) / 2
    d["tip"] = d["share"].map("{:.0%}".format)

    lo = min(-0.4, d["x0"].min() - 0.05)
    hi = max(0.8, d["x1"].max() + 0.05)
    y = alt.Y("store:N", sort=store_order, title=None,
              axis=alt.Axis(domain=False, ticks=False, labelPadding=10,
                            labelFontSize=13, labelColor=INK))
    x = alt.X("x0:Q", title=None, scale=alt.Scale(domain=[lo, hi]),
              axis=alt.Axis(format="%", values=[v / 10 for v in range(-6, 11, 2)
                                                if lo <= v / 10 <= hi],
                            labelExpr="format(abs(datum.value), '.0%')",
                            grid=True, domain=False, ticks=False))
    tooltip = [alt.Tooltip("share:Q", title="Share", format=".1%"),
               alt.Tooltip("stars:N", title="Rating"),
               alt.Tooltip("reviews:Q", title="Reviews", format=","),
               alt.Tooltip("store:N", title="Store")]
    hover = alt.selection_point(on="pointerover", fields=["store", "rating"],
                                empty=False, clear="pointerout")
    bars = alt.Chart(d).mark_bar(size=26, stroke=SURFACE, strokeWidth=2).encode(
        y=y, x=x, x2="x1:Q",
        color=alt.Color("stars:N", sort=STARS,
                        scale=alt.Scale(domain=STARS, range=STAR_COLORS),
                        legend=alt.Legend(title=None, orient="top", direction="horizontal",
                                          symbolType="square", offset=4)),
        opacity=alt.condition(hover, alt.value(0.8), alt.value(1)),
        tooltip=tooltip,
    ).add_params(hover)
    fits = alt.datum.share >= 0.07
    dark = alt.FieldOneOfPredicate(field="rating", oneOf=[1, 5])
    text_on_dark = alt.Chart(d).transform_filter(fits).transform_filter(dark).mark_text(
        fontSize=12, color="#ffffff").encode(y=y, x="mid:Q", text="tip:N", tooltip=tooltip)
    text_on_light = alt.Chart(d).transform_filter(fits).transform_filter(
        {"not": dark}).mark_text(fontSize=12, color=INK).encode(
        y=y, x="mid:Q", text="tip:N", tooltip=tooltip)
    zero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=INK_2, strokeWidth=1).encode(x="x:Q")
    # Streamlit fits the whole chart into this height, legend and axis included.
    return finish(zero + bars + text_on_dark + text_on_light,
                  height=len(store_order) * 52 + 90)


def daily_trend(df, average):
    """Line of daily negative share with a crosshair, an average rule and an end label."""
    d = df.copy()
    d["tip"] = d["neg_share"].map("{:.0%}".format)
    d["is_last"] = d["day"] == d["day"].max()
    top = max(0.4, d["neg_share"].max() * 1.3)
    x = alt.X("day:T", title=None,
              axis=alt.Axis(format="%b %-d", tickCount={"interval": "day", "step": 1},
                            grid=False, labelAngle=0, domainColor=AXIS, ticks=False))
    y = alt.Y("neg_share:Q", title=None, scale=alt.Scale(domain=[0, top]),
              axis=alt.Axis(format=".0%", tickCount=4, domain=False, ticks=False))
    tooltip = [alt.Tooltip("neg_share:Q", title="Negative", format=".1%"),
               alt.Tooltip("day:T", title="Day", format="%b %-d"),
               alt.Tooltip("negative:Q", title="Negative reviews", format=","),
               alt.Tooltip("reviews:Q", title="All reviews", format=",")]
    nearest = alt.selection_point(nearest=True, on="pointerover", fields=["day"],
                                  empty=False, clear="pointerout")

    base = alt.Chart(d)
    avg_rule = alt.Chart(pd.DataFrame({"y": [average]})).mark_rule(
        color=MUTED, strokeWidth=1).encode(y="y:Q")
    line = base.mark_line(strokeWidth=2, color=ACCENT, strokeCap="round",
                          strokeJoin="round").encode(x=x, y=y)
    points = base.mark_point(filled=True, size=70, color=ACCENT, stroke=SURFACE,
                             strokeWidth=2, opacity=1).encode(x=x, y=y)
    hit = base.mark_rule(strokeWidth=48, color=SURFACE, opacity=0.001).encode(
        x=x, tooltip=tooltip).add_params(nearest)
    cross = base.mark_rule(color=AXIS, strokeWidth=1).encode(x=x).transform_filter(nearest)
    focus = base.mark_point(filled=True, size=140, color=ACCENT, stroke=SURFACE,
                            strokeWidth=2).encode(x=x, y=y).transform_filter(nearest)
    end = base.transform_filter("datum.is_last").mark_text(
        align="left", dx=10, fontSize=12, color=INK_2).encode(x=x, y=y, text="tip:N")
    return finish(avg_rule + cross + line + points + focus + end + hit, height=280)


def version_compare(df):
    """Columns of negative share per app version, newest in the accent."""
    d = df.reset_index(drop=True).copy()
    d["emph"] = d.index == len(d) - 1
    d["tip"] = d["neg_share"].map("{:.0%}".format)
    d["axis_label"] = d["version"] + "|" + d["reviews"].map("{:,} reviews".format)
    order = d["axis_label"].tolist()
    hover = _hover("axis_label")
    x = alt.X("axis_label:N", sort=order, title=None,
              axis=alt.Axis(labelExpr="split(datum.label, '|')", labelAngle=0,
                            labelColor=INK_2, labelFontSize=12, ticks=False,
                            domainColor=AXIS, labelPadding=8))
    y = alt.Y("neg_share:Q", title=None, axis=None,
              scale=alt.Scale(domain=[0, max(0.3, d["neg_share"].max() * 1.25)]))
    tooltip = [alt.Tooltip("neg_share:Q", title="Negative", format=".1%"),
               alt.Tooltip("app_version:N", title="Version"),
               alt.Tooltip("reviews:Q", title="Reviews", format=","),
               alt.Tooltip("avg_rating:Q", title="Average rating", format=".2f")]
    cols = alt.Chart(d).mark_bar(size=24, cornerRadiusEnd=4).encode(
        x=x, y=y,
        color=alt.condition("datum.emph", alt.value(ACCENT), alt.value(CONTEXT)),
        opacity=alt.condition(hover, alt.value(0.75), alt.value(1)),
        tooltip=tooltip,
    ).add_params(hover)
    labels = alt.Chart(d).mark_text(dy=-8, fontSize=12, color=INK_2).encode(
        x=x, y=y, text="tip:N", tooltip=tooltip)
    return finish(cols + labels, height=280)


def reply_rate(df):
    """Columns: share of reviews with a developer reply, by star rating."""
    d = df.copy()
    d["stars"] = d["rating"].map(lambda r: STARS[int(r) - 1])
    d["tip"] = d["reply_rate"].map(lambda v: f"{v:.0%}" if v >= 0.01 else f"{v:.1%}")
    hover = _hover("stars")
    x = alt.X("stars:N", sort=STARS, title=None,
              axis=alt.Axis(labelAngle=0, labelColor=INK_2, labelFontSize=12, ticks=False,
                            domainColor=AXIS, labelPadding=8))
    y = alt.Y("reply_rate:Q", title=None, axis=None,
              scale=alt.Scale(domain=[0, max(0.5, d["reply_rate"].max() * 1.25)]))
    tooltip = [alt.Tooltip("reply_rate:Q", title="Replied to", format=".1%"),
               alt.Tooltip("stars:N", title="Rating"),
               alt.Tooltip("replied:Q", title="Replies", format=","),
               alt.Tooltip("reviews:Q", title="Reviews", format=",")]
    cols = alt.Chart(d).mark_bar(size=24, cornerRadiusEnd=4, color=ACCENT).encode(
        x=x, y=y, opacity=alt.condition(hover, alt.value(0.75), alt.value(1)),
        tooltip=tooltip).add_params(hover)
    labels = alt.Chart(d).mark_text(dy=-8, fontSize=12, color=INK_2).encode(
        x=x, y=y, text="tip:N", tooltip=tooltip)
    return finish(cols + labels, height=260)
