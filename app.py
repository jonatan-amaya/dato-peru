# -*- coding: utf-8 -*-
"""DatoPerú — asistente de datos oficiales del Perú (BCRP + INEI).

App Streamlit: pregunta en lenguaje natural -> respuesta con cifra, gráfico
y cita verificable. Corre con: streamlit run app.py
"""
import streamlit as st
import streamlit.components.v1 as components

from engine.router import responder, AYUDA

st.set_page_config(page_title="DatoPerú · datos oficiales del Perú",
                   page_icon="🇵🇪", layout="centered")

st.title("🇵🇪 DatoPerú")
st.caption("Pregunta en lenguaje natural · responde con **datos oficiales del "
           "BCRP y del INEI (ENAHO)**, con gráfico y fuente citada.")

with st.expander("¿Qué puedo preguntar?"):
    st.markdown(AYUDA["texto"])

if "mensajes" not in st.session_state:
    st.session_state.mensajes = []

for msg in st.session_state.mensajes:
    with st.chat_message(msg["rol"]):
        st.markdown(msg["texto"])
        if msg.get("html"):
            components.html(msg["html"], height=460)
        elif msg.get("fig") is not None:
            st.plotly_chart(msg["fig"], use_container_width=True,
                            key=msg.get("key"))
        if msg.get("fuente"):
            st.caption(f"📎 {msg['fuente']}")

if pregunta := st.chat_input("Ej.: ¿Cuál fue la inflación de diciembre 2024?"):
    st.session_state.mensajes.append(
        {"rol": "user", "texto": pregunta, "fig": None, "fuente": None})
    with st.chat_message("user"):
        st.markdown(pregunta)
    with st.chat_message("assistant"):
        with st.spinner("Consultando fuentes oficiales…"):
            r = responder(pregunta)
        st.markdown(r["texto"])
        if r.get("html"):
            components.html(r["html"], height=460)
        elif r["fig"] is not None:
            st.plotly_chart(r["fig"], use_container_width=True,
                            key=f"fig_{len(st.session_state.mensajes)}")
        st.caption(f"📎 {r['fuente']}")
    st.session_state.mensajes.append(
        {"rol": "assistant", "texto": r["texto"], "fig": r["fig"],
         "html": r.get("html"),
         "fuente": r["fuente"], "key": f"hist_{len(st.session_state.mensajes)}"})

st.divider()
c1, c2, c3 = st.columns(3)
c1.metric("Series oficiales BCRP", "17,167")
c2.metric("Departamentos ENAHO", "25")
c3.metric("Residentes procesados", "108,664")
