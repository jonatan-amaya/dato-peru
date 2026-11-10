# -*- coding: utf-8 -*-
"""Indicadores ENAHO 2024 del producto (de la Skill limpiando-enaho de la Tarea 4).

Los indicadores se calculan con factores de expansión (facpob07) desde los
microdatos; aquí se leen los agregados empaquetados (datos/*.csv) que genera
scripts/empaquetar_datos.py.
"""
from functools import cache
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
DEPTOS = RAIZ / "datos" / "pobreza_departamentos.csv"
IND = RAIZ / "datos" / "indicadores_enaho.csv"


@cache
def indicadores():
    return pd.read_csv(IND).set_index("indicador")["valor"].to_dict()


@cache
def departamentos():
    df = pd.read_csv(DEPTOS, dtype={"ccdd": str})
    df["ccdd"] = df["ccdd"].str.zfill(2)
    return df


def pobreza_departamento(nombre_o_codigo):
    df = departamentos()
    q = str(nombre_o_codigo).strip().upper()
    m = df[(df.departamento.str.upper() == q) | (df.ccdd == q.zfill(2))]
    if m.empty:
        return None
    r = m.iloc[0]
    return {"departamento": r["departamento"].title(), "ccdd": r["ccdd"],
            "pobreza_pct": float(r["pobreza_pct"])}


def tabla_departamentos():
    return departamentos().sort_values("pobreza_pct", ascending=False)
