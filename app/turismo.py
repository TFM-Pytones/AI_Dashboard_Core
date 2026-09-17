import math

import pandas as pd
import plotly.express as px
import streamlit as st

from app.color_scales import ACCENT_TURISMO, ACCENT_TURISMO_AEREO, hex_to_rgba
from app.ui_helpers import add_chart_motion, format_metric

# (value_column, yoy_delta_column | None, label, kind, help)
HOTELERO_KPI_COLUMNS = [
    (
        "viajeros_entrados_total",
        "crec_viajeros_yoy_pct",
        "🧳 Viajeros entrados",
        "entero",
        "Viajeros alojados en establecimientos hoteleros durante el año.",
    ),
    (
        "pernoctaciones_total",
        "crec_pernoctaciones_yoy_pct",
        "🛌 Pernoctaciones",
        "entero",
        "Noches pernoctadas en establecimientos hoteleros durante el año.",
    ),
    (
        "ocupacion_media_plazas",
        None,
        "📊 Ocupación media plazas",
        "pct",
        "Porcentaje medio de ocupación de plazas hoteleras.",
    ),
    (
        "estancia_media_hotel_dias",
        None,
        "🕐 Estancia media",
        "decimal",
        "Duración media de la estancia en establecimientos hoteleros, en días.",
    ),
]

# (column, help) -- se muestra un caption con la explicacion encima de la
# grafica de estacionalidad, igual que en la pagina de Clima.
ESTACIONALIDAD_METRICS = {
    "Pernoctaciones": (
        "pernoctaciones",
        "Noches pernoctadas en establecimientos hoteleros, promediadas por mes a lo largo de los años.",
    ),
    "Viajeros entrados": (
        "viajeros_entrados",
        "Viajeros alojados en establecimientos hoteleros, promediados por mes a lo largo de los años.",
    ),
    "Ocupación plazas (%)": (
        "tasa_ocupacion_plazas",
        "Porcentaje medio de plazas hoteleras ocupadas ese mes.",
    ),
    "Estancia media (días)": (
        "estancia_media_hotel_dias",
        "Duración media de la estancia en establecimientos hoteleros, en días.",
    ),
}

MES_LABELS = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}
MES_ORDER = [MES_LABELS[m] for m in range(1, 13)]

AENA_KPI_COLUMNS = [
    ("pasajeros", "✈️ Pasajeros (último mes)", "entero", "Pasajeros en el mes (aeropuerto seleccionado o total insular)."),
]


def format_yoy_delta(value) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return f"{value:+.1f}%"


def get_hotelero_anual_row(df: pd.DataFrame, municipio: str, anio: int) -> pd.Series | None:
    matches = df.loc[(df["municipio"] == municipio) & (df["anio"] == anio)]
    if matches.empty:
        return None
    return matches.iloc[0]


def estacionalidad_by_mes(df: pd.DataFrame, municipio: str, column: str) -> pd.DataFrame:
    subset = df.loc[df["municipio"] == municipio, ["mes", column]]
    result = subset.groupby("mes", as_index=False)[column].mean()
    result = result.rename(columns={column: "valor"}).sort_values("mes")
    result["mes_label"] = result["mes"].map(MES_LABELS)
    return result


AENA_TOTAL_CODIGO = "TOTAL"
AENA_TOTAL_NOMBRE = "Total (Tenerife)"


def aena_series(df: pd.DataFrame, aeropuerto_codigo: str) -> pd.DataFrame:
    if df.empty:
        return df
    if str(aeropuerto_codigo).upper() in ("TOTAL", "TODOS"):
        grouped = (
            df.groupby("periodo", as_index=False)[["pasajeros", "operaciones"]]
            .sum()
            .sort_values("periodo")
        )
        grouped["aeropuerto_codigo"] = AENA_TOTAL_CODIGO
        grouped["aeropuerto_nombre"] = AENA_TOTAL_NOMBRE
        grouped["pasajeros_por_operacion"] = (
            grouped["pasajeros"] / grouped["operaciones"].replace(0, float("nan"))
        ).round(1)
        return grouped
    return df.loc[df["aeropuerto_codigo"] == aeropuerto_codigo].sort_values("periodo")


def aena_estacionalidad_comparativa(df: pd.DataFrame, column: str = "pasajeros") -> pd.DataFrame:
    grouped = df.groupby(["aeropuerto_nombre", "mes"], as_index=False)[column].mean()
    grouped = grouped.rename(columns={column: "valor"}).sort_values(["aeropuerto_nombre", "mes"])
    grouped["mes_label"] = grouped["mes"].map(MES_LABELS)
    return grouped.reset_index(drop=True)


def get_latest_aena_row(df: pd.DataFrame, aeropuerto_codigo: str) -> pd.Series | None:
    if df.empty:
        return None
    if str(aeropuerto_codigo).upper() in ("TOTAL", "TODOS"):
        serie = aena_series(df, AENA_TOTAL_CODIGO)
        if serie.empty:
            return None
        return serie.iloc[-1]
    matches = df.loc[df["aeropuerto_codigo"] == aeropuerto_codigo]
    if matches.empty:
        return None
    return matches.sort_values("periodo").iloc[-1]


def compute_aena_kpis(serie_aena: pd.DataFrame) -> list[dict]:
    if serie_aena.empty:
        return []
    latest = serie_aena.iloc[-1]
    last_period = str(latest["periodo"])

    # YoY delta vs mismo mes del año anterior
    prev_year_period = f"{int(last_period[:4]) - 1}{last_period[4:]}"
    prev_match = serie_aena.loc[serie_aena["periodo"] == prev_year_period]
    yoy_pct = None
    if not prev_match.empty and prev_match["pasajeros"].iloc[0] > 0:
        yoy_pct = ((latest["pasajeros"] - prev_match["pasajeros"].iloc[0]) / prev_match["pasajeros"].iloc[0]) * 100

    # Acumulado últimos 12 meses (año móvil)
    pax_12m = float(serie_aena.tail(12)["pasajeros"].sum())

    # Media mensual de pasajeros en toda la serie histórica
    pax_mean = float(serie_aena["pasajeros"].mean())

    return [
        {
            "label": "✈️ Pasajeros (último mes)",
            "value": latest["pasajeros"],
            "delta": format_yoy_delta(yoy_pct),
            "kind": "entero",
            "help": f"Pasajeros transportados en {last_period} y variación frente al mismo mes del año anterior.",
        },
        {
            "label": "📅 Acumulado anual (12 meses)",
            "value": pax_12m,
            "delta": None,
            "kind": "entero",
            "help": "Total de pasajeros comerciales transportados en los últimos 12 meses móviles.",
        },
        {
            "label": "📊 Media mensual histórica",
            "value": pax_mean,
            "delta": None,
            "kind": "entero",
            "help": "Promedio mensual de pasajeros a lo largo de toda la serie registrada.",
        },
    ]


def render_turismo_tab(
    hotelero_anual_df: pd.DataFrame,
    hotelero_mensual_df: pd.DataFrame,
    aena_df: pd.DataFrame,
    municipio_anual_df: pd.DataFrame | None = None,
    municipio_mensual_df: pd.DataFrame | None = None,
) -> None:
    st.subheader("Turismo hotelero por polo turístico")
    municipios = sorted(hotelero_anual_df["municipio"].dropna().unique().tolist())
    col1, col2 = st.columns([2, 1])
    municipio = col1.selectbox("Municipio", municipios, key="turismo_municipio")
    years = sorted(
        hotelero_anual_df.loc[hotelero_anual_df["municipio"] == municipio, "anio"].unique().tolist()
    )
    anio = col2.selectbox("Año", years, index=len(years) - 1, key="turismo_anio")

    anual_row = get_hotelero_anual_row(hotelero_anual_df, municipio, anio)
    if anual_row is None:
        st.info("No hay datos hoteleros para este municipio en el año seleccionado.")
    else:
        st.caption(anual_row["polo_turistico"])
        cols = st.columns(4)
        for i, (column, delta_column, label, kind, help_text) in enumerate(HOTELERO_KPI_COLUMNS):
            delta = format_yoy_delta(anual_row.get(delta_column)) if delta_column else None
            with cols[i % 4].container(border=True):
                st.metric(label, format_metric(anual_row.get(column), kind), delta=delta, help=help_text)

    st.subheader("Estacionalidad")
    metrica_label = st.selectbox(
        "Métrica", list(ESTACIONALIDAD_METRICS.keys()), key="turismo_estacionalidad_metrica"
    )
    metrica_columna, metrica_help = ESTACIONALIDAD_METRICS[metrica_label]
    st.caption(f"ℹ️ {metrica_help}")
    serie = estacionalidad_by_mes(hotelero_mensual_df, municipio, metrica_columna)
    fig = px.bar(
        serie,
        x="mes_label",
        y="valor",
        category_orders={"mes_label": MES_ORDER},
        title=f"{metrica_label} media por mes — {municipio}",
        labels={"mes_label": "Mes", "valor": metrica_label},
    )
    fig.update_traces(marker_color=ACCENT_TURISMO)
    add_chart_motion(fig)
    st.plotly_chart(fig, width="stretch")

    st.divider()
    st.subheader("Vivienda vacacional (VV)")
    st.caption(
        "Indicadores oficiales de oferta, ocupación, rentabilidad y evolución mensual "
        "de la Vivienda Vacacional para los 31 municipios de Tenerife (ISTAC)."
    )

    if municipio_anual_df is not None and not municipio_anual_df.empty:
        all_vv_mun = sorted(municipio_anual_df["municipio"].dropna().unique().tolist())
        col_vv1, col_vv2 = st.columns([2, 1])
        default_idx = all_vv_mun.index(municipio) if municipio in all_vv_mun else 0
        muni_vv = col_vv1.selectbox("Municipio (VV)", all_vv_mun, index=default_idx, key="turismo_vv_municipio")

        vv_years = sorted(
            municipio_anual_df.loc[municipio_anual_df["municipio"] == muni_vv, "anio"].dropna().unique().tolist()
        )
        anio_vv = col_vv2.selectbox(
            "Año (VV)", vv_years, index=len(vv_years) - 1 if vv_years else 0, key="turismo_vv_anio"
        )

        row_vv = municipio_anual_df.loc[
            (municipio_anual_df["municipio"] == muni_vv) & (municipio_anual_df["anio"] == anio_vv)
        ]
        if not row_vv.empty:
            r = row_vv.iloc[0]
            cols_kpi = st.columns(4)
            with cols_kpi[0].container(border=True):
                st.metric(
                    "🏘️ Plazas VV medias",
                    format_metric(r.get("plazas_vv_media"), "entero"),
                    delta=format_yoy_delta(r.get("crec_plazas_vv_yoy_pct")),
                    help="Plazas medias registradas en vivienda vacacional y variación interanual (YoY).",
                )
            with cols_kpi[1].container(border=True):
                st.metric(
                    "📊 Tasa ocupación VV",
                    format_metric(r.get("tasa_ocupacion_vv_media"), "pct"),
                    help="Porcentaje medio de ocupación de las plazas de vivienda vacacional.",
                )
            with cols_kpi[2].container(border=True):
                val_estancia = r.get("estancia_media_vv")
                st.metric(
                    "🕐 Estancia media VV",
                    f"{val_estancia:.1f} días" if pd.notna(val_estancia) else "—",
                    help="Duración media de la estancia de viajeros en vivienda vacacional.",
                )
            with cols_kpi[3].container(border=True):
                ingresos = r.get("ingresos_vv_acumulados")
                ing_str = f"{ingresos:,.0f} €".replace(",", ".") if pd.notna(ingresos) else "—"
                st.metric(
                    "💶 Ingresos VV acumulados",
                    ing_str,
                    delta=format_yoy_delta(r.get("crec_ingresos_mensual_yoy_pct")),
                    help="Ingresos brutos acumulados en vivienda vacacional durante el año.",
                )

        if municipio_mensual_df is not None and not municipio_mensual_df.empty:
            metrica_vv_opciones = {
                "Plazas VV": ("plazas_vv", "Plazas"),
                "Tasa ocupación (%)": ("tasa_ocupacion_vv", "% ocupación"),
                "Ingresos mensuales (€)": ("ingresos_vv", "Euros (€)"),
                "Alojamientos abiertos": ("alojamientos_abiertos_vv", "Viviendas abiertas"),
            }
            metrica_vv_label = st.selectbox(
                "Métrica mensual VV", list(metrica_vv_opciones.keys()), key="turismo_vv_metrica"
            )
            col_vv_val, col_vv_unit = metrica_vv_opciones[metrica_vv_label]

            sub_mensual = municipio_mensual_df[municipio_mensual_df["municipio"] == muni_vv].sort_values("periodo")
            if not sub_mensual.empty and col_vv_val in sub_mensual.columns:
                fig_vv = px.area(
                    sub_mensual,
                    x="periodo",
                    y=col_vv_val,
                    title=f"Evolución mensual de {metrica_vv_label} — {muni_vv}",
                    labels={"periodo": "Periodo (Año-Mes)", col_vv_val: col_vv_unit},
                )
                fig_vv.update_traces(
                    line_color="#10b981", line_shape="spline", fillcolor=hex_to_rgba("#10b981", 0.15)
                )
                add_chart_motion(fig_vv)
                st.plotly_chart(fig_vv, width="stretch")

    st.divider()
    st.subheader("Tráfico aéreo")
    aeropuertos = sorted(aena_df["aeropuerto_nombre"].dropna().unique().tolist())
    opciones_aeropuerto = [AENA_TOTAL_NOMBRE] + aeropuertos
    aeropuerto_nombre = st.selectbox("Aeropuerto", opciones_aeropuerto, key="turismo_aeropuerto")
    if aeropuerto_nombre == AENA_TOTAL_NOMBRE or str(aeropuerto_nombre).upper().startswith("TOTAL"):
        codigo = AENA_TOTAL_CODIGO
    else:
        codigo = aena_df.loc[aena_df["aeropuerto_nombre"] == aeropuerto_nombre, "aeropuerto_codigo"].iloc[0]

    serie_aena = aena_series(aena_df, codigo)
    kpis = compute_aena_kpis(serie_aena)
    if kpis:
        latest_period = serie_aena.iloc[-1]["periodo"]
        st.caption(f"Último dato: {latest_period}")
        cols = st.columns(len(kpis))
        for i, kpi in enumerate(kpis):
            with cols[i].container(border=True):
                st.metric(
                    kpi["label"],
                    format_metric(kpi["value"], kpi["kind"]),
                    delta=kpi["delta"],
                    help=kpi["help"],
                )

    fig_aena = px.area(
        serie_aena, x="periodo", y="pasajeros", title=f"Pasajeros mensuales — {aeropuerto_nombre}"
    )
    fig_aena.update_traces(
        line_color=ACCENT_TURISMO_AEREO, line_shape="spline", fillcolor=hex_to_rgba(ACCENT_TURISMO_AEREO, 0.15)
    )
    add_chart_motion(fig_aena)
    st.plotly_chart(fig_aena, width="stretch")

    st.subheader("Estacionalidad comparada: TFS vs. TFN")
    st.caption(
        "Tenerife Sur (tráfico internacional predominante, pico en invierno) frente a "
        "Tenerife Norte (tráfico nacional e interinsular, pico en verano)."
    )
    serie_comparativa = aena_estacionalidad_comparativa(aena_df, "pasajeros")
    fig_comparativa = px.line(
        serie_comparativa,
        x="mes_label",
        y="valor",
        color="aeropuerto_nombre",
        category_orders={"mes_label": MES_ORDER},
        markers=True,
        color_discrete_map={
            "Tenerife Sur - Reina Sofía": ACCENT_TURISMO,
            "Tenerife Norte - Ciudad de La Laguna": ACCENT_TURISMO_AEREO,
        },
        title="Pasajeros medios por mes — TFS vs. TFN",
        labels={"mes_label": "Mes", "valor": "Pasajeros medios", "aeropuerto_nombre": "Aeropuerto"},
    )
    add_chart_motion(fig_comparativa)
    st.plotly_chart(fig_comparativa, width="stretch")
