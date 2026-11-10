# -*- coding: utf-8 -*-
"""Router de intenciones de DatoPerú: pregunta en lenguaje natural -> respuesta
con datos oficiales, gráfico y cita. Determinista y auditable (sin LLM en el
camino crítico del demo); la "inteligencia" está en elegir la herramienta
correcta (MCP BCRP o Skill ENAHO) y componer la cita.
"""
import re
import unicodedata
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from engine import bcrp_tools as bcrp
from engine import enaho

RAIZ = Path(__file__).resolve().parent.parent

SERIES = {
    "ipc": "PN01273PM",     # IPC Lima var% interanual
    "tc": "PN01215PM",      # tipo de cambio interbancario venta fin de periodo
    "tasa": "PD04722MM",    # tasa de referencia
    "desempleo": "PN38063GM",  # tasa de desempleo Lima
}
NOMBRES_SERIE = {
    "ipc": "Inflación interanual (IPC Lima, var% 12 meses)",
    "tc": "Tipo de cambio interbancario venta, fin de periodo (S/ por US$)",
    "tasa": "Tasa de referencia de la política monetaria (%)",
    "desempleo": "Tasa de desempleo en Lima Metropolitana (%)",
}
FUENTE_BCRP = "BCRP · estadisticas.bcrp.gob.pe"
FUENTE_ENAHO = "INEI · ENAHO 2024 (facpob07)"


def _norm(s):
    return unicodedata.normalize("NFD", s.lower()).encode("ascii", "ignore").decode()


def _fig_linea(datos, titulo, ylabel, color="#e63946"):
    df = pd.DataFrame(datos)
    fig = px.line(df, x="periodo", y="valor", markers=True, title=titulo,
                  labels={"periodo": "Periodo", "valor": ylabel})
    fig.update_traces(line_color=color, marker_size=5)
    fig.update_layout(margin=dict(t=50, b=40, l=50, r=20), height=320,
                      title_font_size=13)
    return fig


def _respuesta(texto, fuente, fig=None, extra=None):
    return {"texto": texto, "fuente": fuente, "fig": fig, "extra": extra or [],
            "html": None}


def _ultimo_o_periodo(clave, desde, hasta):
    r = bcrp.resumen(SERIES[clave], desde, hasta)
    return r


AYUDA = _respuesta(
    "Puedo responder con **datos oficiales del BCRP y del INEI**. Prueba con:\n\n"
    "- ¿Cuál fue la inflación de diciembre 2024?\n"
    "- ¿Cuál es la inflación más reciente?\n"
    "- ¿En qué mes fue el pico de la inflación entre 2020 y 2024?\n"
    "- ¿Cuánto está el tipo de cambio?\n"
    "- ¿Cuál es la tasa de referencia del BCRP?\n"
    "- ¿Cuánto es la pobreza nacional / urbana / rural?\n"
    "- ¿Cuál es la pobreza en Cusco (o cualquier departamento)?\n"
    "- Muéstrame el mapa de pobreza por departamento\n"
    "- ¿Cuál es la brecha de pobreza entre zonas urbanas y rurales?",
    "DatoPerú · Motor de intenciones v1")


def responder(pregunta: str) -> dict:
    q = _norm(pregunta)

    # ---------------- ENAHO: mapa
    if "mapa" in q and "pobreza" in q:
        import json as _json
        df = enaho.tabla_departamentos()
        geo = _json.loads((RAIZ / "datos" / "peru_departamental_simple.geojson")
                          .read_text(encoding="utf-8"))
        fig = px.choropleth(df, geojson=geo,
                            locations="ccdd", featureidkey="properties.FIRST_IDDP",
                            color="pobreza_pct", color_continuous_scale="OrRd",
                            range_color=(0, 50),
                            hover_name="departamento",
                            labels={"pobreza_pct": "Pobreza (%)"},
                            title="Pobreza monetaria por departamento, ENAHO 2024")
        fig.update_geos(lataxis_range=[-19.5, 0.5], lonaxis_range=[-82.5, -68],
                    showframe=False, showcountries=True,
                    countrycolor="#888", landcolor="#f0f0f0",
                    oceancolor="white", showocean=True)
        fig.update_layout(margin=dict(t=50, b=10, l=10, r=10), height=460)
        top = df.iloc[0]
        baja = df.iloc[-1]
        r = _respuesta(
            f"**Mapa de pobreza monetaria 2024 (25 departamentos).** "
            f"Máxima: {top.departamento.title()} {top.pobreza_pct:.1f} % · "
            f"mínima: {baja.departamento.title()} {baja.pobreza_pct:.1f} %. "
            f"Pasa el cursor sobre cada región.",
            FUENTE_ENAHO)
        r["html"] = fig.to_html(include_plotlyjs="cdn", full_html=False,
                                config={"displaylogo": False})
        return r

    # ---------------- ENAHO: brechas
    if "brecha" in q:
        ind = enaho.indicadores()
        ur = float(ind["pobreza_rural_pct"]) - float(ind["pobreza_urbana_pct"])
        sx = abs(float(ind["pobreza_mujeres_pct"]) - float(ind["pobreza_hombres_pct"]))
        fig = px.bar(x=["Rural - urbana", "Mujeres - hombres"], y=[ur, sx],
                     title="Brechas de pobreza 2024: la territorial pesa 50 veces más que la de género",
                     labels={"x": "Brecha", "y": "Puntos porcentuales"},
                     text=[f"{ur:.1f} pts", f"{sx:.1f} pts"])
        fig.update_traces(marker_color="#2a9d8f", textposition="outside")
        fig.update_layout(margin=dict(t=50, b=40, l=50, r=20), height=300,
                          showlegend=False)
        return _respuesta(
            f"Sí, y no es comparable: la brecha **urbano-rural es de {ur:.1f} puntos** "
            f"(urbana {ind['pobreza_urbana_pct']} % vs rural {ind['pobreza_rural_pct']} %), "
            f"mientras la brecha de género es de apenas **{sx:.1f} puntos**. "
            f"La desigualdad territorial es el eje del problema.",
            FUENTE_ENAHO, fig)

    # ---------------- ENAHO: pobreza por departamento
    m = re.search(r"pobreza (?:en|de|del) ([a-zñ ]{3,20})", q)
    if "pobreza" in q and m:
        nombre = m.group(1).strip()
        r = enaho.pobreza_departamento(nombre)
        if r:
            fig = px.bar(enaho.tabla_departamentos().head(10), x="pobreza_pct",
                         y="departamento", orientation="h",
                         title="Top 10 departamentos con mayor pobreza, 2024",
                         labels={"pobreza_pct": "Pobreza (%)", "departamento": ""})
            fig.update_layout(margin=dict(t=50, b=40, l=110, r=20), height=340,
                              yaxis=dict(autorange="reversed"))
            return _respuesta(
                f"La pobreza monetaria en **{r['departamento']} (2024)** es "
                f"**{r['pobreza_pct']:.1f} %** de la población "
                f"(departamento {r['ccdd']}, estimación ponderada).",
                FUENTE_ENAHO, fig)
        return _respuesta(
            f"No encontré el departamento «{nombre}». Prueba con su nombre "
            f"(Cusco, Cajamarca, Lima, Arequipa…).", FUENTE_ENAHO)

    # ---------------- ENAHO: niveles de pobreza
    if "pobreza" in q:
        ind = enaho.indicadores()
        if "rural" in q:
            return _respuesta(
                f"La pobreza monetaria **rural 2024** es **{ind['pobreza_rural_pct']} %** "
                f"de la población rural (referencia oficial: 39.3 %).",
                FUENTE_ENAHO)
        if "urbana" in q:
            return _respuesta(
                f"La pobreza monetaria **urbana 2024** es **{ind['pobreza_urbana_pct']} %** "
                f"(referencia oficial: 24.8 %).",
                FUENTE_ENAHO)
        if "extrema" in q:
            return _respuesta(
                f"La **pobreza extrema 2024** es **{ind['pobreza_extrema_pct']} %** "
                f"de la población.", FUENTE_ENAHO)
        if "sexo" in q or "mujer" in q or "genero" in q:
            fig = px.bar(x=["Hombres", "Mujeres"],
                         y=[float(ind["pobreza_hombres_pct"]), float(ind["pobreza_mujeres_pct"])],
                         title="Pobreza por sexo, 2024: brecha menor a 0.5 puntos",
                         labels={"x": "", "y": "Pobreza (%)"},
                         text=[f"{ind['pobreza_hombres_pct']}%", f"{ind['pobreza_mujeres_pct']}%"])
            fig.update_traces(marker_color="#2a9d8f", textposition="outside")
            fig.update_layout(margin=dict(t=50, b=40, l=50, r=20), height=300,
                              showlegend=False)
            return _respuesta(
                f"Pobreza 2024: **hombres {ind['pobreza_hombres_pct']} %** vs "
                f"**mujeres {ind['pobreza_mujeres_pct']} %** — brecha de género "
                f"menor a 0.5 puntos.", FUENTE_ENAHO, fig)
        return _respuesta(
            f"La **pobreza monetaria nacional 2024** es **{ind['pobreza_nacional_pct']} %** "
            f"de la población (108,664 residentes habituales procesados; referencia "
            f"oficial del INEI: 27.6 %). Urbana: {ind['pobreza_urbana_pct']} % · "
            f"rural: {ind['pobreza_rural_pct']} % · extrema: {ind['pobreza_extrema_pct']} %.",
            FUENTE_ENAHO)

    # ---------------- BCRP
    if "pico" in q or "maxim" in q:
        if "inflac" in q or "ipc" in q or "precio" in q:
            r = _ultimo_o_periodo("ipc", "2020-01", "2024-12")
            return _respuesta(
                f"El **pico de la inflación interanual (IPC Lima)** entre 2020 y 2024 fue "
                f"**{r['maximo']['valor']:.2f} % en {r['maximo']['periodo']}** "
                f"(promedio del período: {r['promedio']:.2f} %).",
                f"{FUENTE_BCRP} · serie {SERIES['ipc']}")

    if "tasa" in q and ("referencia" in q or "interes" in q or "bcrp" in q):
        r = _ultimo_o_periodo("tasa", "2026-01", "2026-12")
        return _respuesta(
            f"La **tasa de referencia de la política monetaria** más reciente es "
            f"**{r['ultimo']['valor']:.2f} %** ({r['ultimo']['periodo']}).",
            f"{FUENTE_BCRP} · serie {SERIES['tasa']}")

    if "desempleo" in q or "desemple" in q:
        r = _ultimo_o_periodo("desempleo", "2026-09", "2026-10")
        return _respuesta(
            f"La **tasa de desempleo en Lima Metropolitana** más reciente es "
            f"**{r['ultimo']['valor']:.1f} %** ({r['ultimo']['periodo']}).",
            f"{FUENTE_BCRP} · serie {SERIES['desempleo']}")

    if "tipo de cambio" in q or "dolar" in q:
        if "evolucion" in q or "como" in q and "evoluciono" in q:
            r = bcrp.serie(SERIES["tc"], "2020-01", "2024-12")
            rs = bcrp.resumen(SERIES["tc"], "2020-01", "2024-12")
            fig = _fig_linea(r["datos"], "Tipo de cambio interbancario venta, 2020-2024",
                             "S/ por US$", color="#2a9d8f")
            return _respuesta(
                f"El tipo de cambio pasó de **S/ {rs['primero']['valor']:.4f}** "
                f"({rs['primero']['periodo']}) a **S/ {rs['ultimo']['valor']:.4f}** "
                f"({rs['ultimo']['periodo']}): **+{rs['variacion_pct']:.1f} %** acumulado.",
                f"{FUENTE_BCRP} · serie {SERIES['tc']}", fig)
        r = _ultimo_o_periodo("tc", "2024-10", "2024-12")
        fig = _fig_linea(bcrp.serie(SERIES["tc"], "2024-01", "2024-12")["datos"],
                         "Tipo de cambio interbancario venta, 2024", "S/ por US$",
                         color="#2a9d8f")
        return _respuesta(
            f"El tipo de cambio interbancario venta (fin de periodo) en "
            f"**{r['ultimo']['periodo']}** fue **S/ {r['ultimo']['valor']:.4f}** por US$.",
            f"{FUENTE_BCRP} · serie {SERIES['tc']}", fig)

    if "inflac" in q or "ipc" in q or "precio" in q or "precios" in q:
        if "evolucion" in q or "historico" in q or "2020" in q:
            r = bcrp.serie(SERIES["ipc"], "2020-01", "2024-12")
            rs = bcrp.resumen(SERIES["ipc"], "2020-01", "2024-12")
            fig = _fig_linea(r["datos"], "Inflación interanual Lima, 2020-2024",
                             "var% 12 meses")
            return _respuesta(
                f"La inflación interanual pasó del pico de **{rs['maximo']['valor']:.2f} %** "
                f"({rs['maximo']['periodo']}) a **{rs['ultimo']['valor']:.2f} %** en "
                f"{rs['ultimo']['periodo']}.",
                f"{FUENTE_BCRP} · serie {SERIES['ipc']}", fig)
        if "reciente" in q or "actual" in q or "ultim" in q or "hoy" in q:
            r = _ultimo_o_periodo("ipc", "2026-01", "2026-12")
            fig = _fig_linea(bcrp.serie(SERIES["ipc"], "2026-01", "2026-09")["datos"],
                             "Inflación interanual Lima, 2026", "var% 12 meses")
            return _respuesta(
                f"La **inflación interanual más reciente (IPC Lima)** es "
                f"**{r['ultimo']['valor']:.2f} %** ({r['ultimo']['periodo']}).",
                f"{FUENTE_BCRP} · serie {SERIES['ipc']}", fig)
        # por defecto: diciembre 2024
        r = _ultimo_o_periodo("ipc", "2024-12", "2024-12")
        fig = _fig_linea(bcrp.serie(SERIES["ipc"], "2024-01", "2024-12")["datos"],
                         "Inflación interanual Lima, 2024", "var% 12 meses")
        return _respuesta(
            f"La **inflación interanual (IPC Lima) de diciembre 2024** fue "
            f"**{r['ultimo']['valor']:.2f} %**.",
            f"{FUENTE_BCRP} · serie {SERIES['ipc']}", fig)

    return AYUDA
