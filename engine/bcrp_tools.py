# -*- coding: utf-8 -*-
"""Herramientas BCRP del producto (adaptadas del servidor MCP de la Tarea 4).

Misma lógica del servidor MCP (sesión 04 del curso): búsqueda en catálogo
oficial, descarga de series y resúmenes calculados con Python. Estrategia de
datos: (1) caché local de respuestas oficiales (datos/cache_bcrp/), (2) API
en vivo si responde JSON, (3) error claro con instrucción de precarga.
"""
import csv
import json
import re
import time
import unicodedata
from functools import cache
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
CATALOGO = RAIZ / "datos" / "catalogo_bcrp.csv"
CACHE = RAIZ / "datos" / "cache_bcrp"
API = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"

_MESES = {"Ene": 1, "Feb": 2, "Mar": 3, "Abr": 4, "May": 5, "Jun": 6,
          "Jul": 7, "Ago": 8, "Set": 9, "Sep": 9, "Oct": 10, "Nov": 11, "Dic": 12}


def _sin_tildes(s):
    return unicodedata.normalize("NFD", str(s).lower()).encode("ascii", "ignore").decode()


@cache
def catalogo():
    df = pd.read_csv(CATALOGO, sep=";", dtype=str, encoding="latin-1",
                     quoting=csv.QUOTE_NONE).fillna("")
    df = df.rename(columns={"Código de serie": "codigo", "Categoría de serie": "categoria",
                            "Grupo de serie": "grupo", "Nombre de serie": "nombre",
                            "Frecuencia": "frecuencia", "Fecha de actualización": "actualizada",
                            "Fecha de inicio": "inicio"})
    df["texto"] = (df.categoria + " " + df.grupo + " " + df.nombre).map(_sin_tildes)
    return df


def _ficha(codigo):
    fila = catalogo().query("codigo == @codigo")
    if fila.empty:
        raise ValueError(f"No existe el código de serie {codigo!r}.")
    f = fila.iloc[0]
    return {"codigo": f.codigo, "nombre": f"{f.grupo} - {f.nombre}",
            "categoria": f.categoria, "frecuencia": f.frecuencia,
            "inicio": f.inicio, "actualizada": f.actualizada}


def buscar_series(texto, frecuencia=None, limite=5):
    df = catalogo()
    m = pd.Series(True, index=df.index)
    for palabra in _sin_tildes(texto).split():
        m &= df.texto.str.contains(re.escape(palabra))
    if frecuencia:
        m &= df.frecuencia.str.lower() == frecuencia.lower()
    sel = df[m]
    orden = sel.assign(vieja=sel.actualizada < "2025",
                       largo=(sel.grupo + sel.nombre).str.len())
    return [_ficha(c) for c in orden.sort_values(["vieja", "largo"]).head(limite).codigo]


def _norma_fecha(fecha, frecuencia):
    base = fecha.strip()
    if frecuencia == "Anual":
        return base[:4]
    if frecuencia == "Diaria":
        return base
    anio, mes = base.split("-")[:2]
    return f"{anio}-{int(mes)}"


def _periodo_iso(nombre, frecuencia):
    partes = nombre.strip().split(".")
    if frecuencia == "Anual":
        return partes[0]
    if frecuencia == "Trimestral":
        return f"20{partes[1]}-T{partes[0].upper().replace('T', '')}"
    if frecuencia == "Diaria":
        return f"20{partes[2]}-{_MESES[partes[1]]:02d}-{int(partes[0]):02d}"
    return f"{partes[1]}-{_MESES[partes[0]]:02d}"


def _clave(p):
    if "-T" in p:
        a, t = p.split("-T")
        return (int(a), int(t))
    partes = p.split("-")
    return (int(partes[0]), int(partes[1])) + ((int(partes[2]),) if len(partes) == 3 else ())


def _descargar(codigo, desde, hasta):
    """Caché primero (cobertura de rangos); si no, API en vivo; si no, error claro."""
    cubre = []
    for c in sorted(CACHE.glob(f"{codigo}_*.json")):
        try:
            _, d, h = c.stem.split("_")
            if _clave(d) <= _clave(desde) and _clave(h) >= _clave(hasta):
                cubre.append(c)
        except ValueError:
            continue
    if cubre:
        cache_file = min(cubre, key=lambda c: len(c.read_text(encoding="utf-8")))
        periodos = json.loads(cache_file.read_text(encoding="utf-8"))["periods"]
        frec = _ficha(codigo)["frecuencia"]
        return [p for p in periodos
                if _clave(_periodo_iso(p["name"], frec)) >= _clave(desde)
                and _clave(_periodo_iso(p["name"], frec)) <= _clave(hasta)]
    import httpx
    url = f"{API}/{codigo}/json/{desde}/{hasta}"
    try:
        r = httpx.get(url, timeout=30)
        if r.text.lstrip().startswith("{"):
            datos = r.json()
            if "periods" in datos:
                return datos["periods"]
    except Exception:
        pass
    time.sleep(1)
    raise ValueError(f"Sin datos locales ni en vivo para {codigo} ({desde} a {hasta}). "
                     f"Precarga: uv run scripts/descargar_serie.py {codigo} {desde} {hasta}")


def serie(codigo, desde, hasta):
    ficha = _ficha(codigo)
    frec = ficha["frecuencia"]
    periodos = _descargar(codigo, _norma_fecha(desde, frec), _norma_fecha(hasta, frec))
    datos = []
    for p in periodos:
        valor = p["values"][0].strip()
        if valor in ("", "n.d."):
            continue
        datos.append({"periodo": _periodo_iso(p["name"], frec), "valor": float(valor)})
    return {**ficha, "datos": datos, "fuente": f"{API}/{codigo}"}


def resumen(codigo, desde, hasta):
    d = serie(codigo, desde, hasta)
    datos = d["datos"]
    if not datos:
        raise ValueError(f"La serie {codigo} no tiene datos en ese período.")
    vals = [x["valor"] for x in datos]
    primero, ultimo = datos[0], datos[-1]
    cambio = ultimo["valor"] - primero["valor"]
    variacion = cambio / primero["valor"] * 100 if primero["valor"] else None
    imax = max(range(len(vals)), key=lambda i: vals[i])
    imin = min(range(len(vals)), key=lambda i: vals[i])
    return {**d, "n": len(datos),
            "periodo": {"desde": primero["periodo"], "hasta": ultimo["periodo"]},
            "primero": primero, "ultimo": ultimo,
            "cambio": round(cambio, 4),
            "variacion_pct": round(variacion, 2) if variacion is not None else None,
            "promedio": round(sum(vals) / len(vals), 4),
            "maximo": datos[imax], "minimo": datos[imin]}
