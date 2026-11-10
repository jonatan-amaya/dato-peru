# -*- coding: utf-8 -*-
"""Genera el video de respaldo de DatoPerú (60-90 s, 1280x720).

Diapositivas (PIL/matplotlib) + narración edge-tts + música sintetizada.
Salida: static/video_respaldo.mp4

Uso (env tarea1): python scripts/hacer_video.py
"""
import asyncio
import json
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
REC = RAIZ / "static"
REC.mkdir(exist_ok=True)
W, H = 1280, 720
BG = (15, 22, 32)
FG = (232, 238, 245)
VERDE = (42, 157, 143)
ROJO = (230, 57, 70)
MUTED = (147, 165, 182)

FONT_BIG = "arialbd.ttf"
FONT = "arial.ttf"


def fuente(nombre, tam):
    try:
        return ImageFont.truetype(nombre, tam)
    except OSError:
        return ImageFont.load_default()


def lienzo():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    return img, d


def texto_centro(d, txt, y, fnt, color=FG):
    caja = d.textbbox((0, 0), txt, font=fnt)
    d.text(((W - (caja[2] - caja[0])) / 2, y), txt, font=fnt, fill=color)


def escena_titulo():
    img, d = lienzo()
    d.rectangle([0, 0, W, 8], fill=VERDE)
    texto_centro(d, "🇵🇪 DATOPERÚ", 210, fuente(FONT_BIG, 84), VERDE)
    texto_centro(d, "Tu pregunta, dato oficial en 5 segundos", 330,
                 fuente(FONT, 40))
    texto_centro(d, "BCRP + INEI (ENAHO) · respuestas verificables con fuente",
                 400, fuente(FONT, 28), MUTED)
    texto_centro(d, "Proyecto Q-Lab PUCP · Jonatan Amaya", 640,
                 fuente(FONT, 22), MUTED)
    return img


def escena_problema():
    img, d = lienzo()
    texto_centro(d, "El problema", 90, fuente(FONT_BIG, 56), ROJO)
    lineas = [
        "Una cifra oficial —inflación, pobreza, tipo de cambio—",
        "toma 20-40 minutos: buscar el portal, descargar,",
        "procesar, verificar la fuente… y rezar que sea el dato vigente.",
        "",
        "Periodistas, tesistas y funcionarios lo hacen a diario.",
    ]
    for i, l in enumerate(lineas):
        texto_centro(d, l, 220 + i * 58, fuente(FONT, 34))
    return img


def escena_captura(ruta_img, titulo, caption, segundo_caption=None):
    img, d = lienzo()
    texto_centro(d, titulo, 40, fuente(FONT_BIG, 44), VERDE)
    captura = Image.open(ruta_img).convert("RGB")
    # escalar para caber en 1100x480 manteniendo proporción
    captura.thumbnail((1100, 470))
    img.paste(captura, ((W - captura.width) // 2, 120))
    texto_centro(d, caption, 620, fuente(FONT, 30))
    if segundo_caption:
        texto_centro(d, segundo_caption, 665, fuente(FONT, 26), MUTED)
    return img


def escena_tecnologia():
    img, d = lienzo()
    texto_centro(d, "Cómo funciona", 90, fuente(FONT_BIG, 56), VERDE)
    lineas = [
        "Motor de intenciones → elige la herramienta correcta:",
        "",
        "🔌 Servidor MCP del BCRP — 17,167 series oficiales en vivo",
        "🧠 Skills ENAHO — 108,664 personas procesadas, ponderadas",
        "🗺️ Mapa departamental con unión por código oficial",
        "",
        "Cada respuesta trae código de serie, periodo y fuente.",
    ]
    for i, l in enumerate(lineas):
        texto_centro(d, l, 210 + i * 62, fuente(FONT, 34))
    return img


def escena_cta():
    img, d = lienzo()
    d.rectangle([0, 0, W, 8], fill=ROJO)
    texto_centro(d, "Pruébalo hoy", 200, fuente(FONT_BIG, 64))
    texto_centro(d, "github.com/jonatan-amaya/dato-peru", 330,
                 fuente(FONT, 40), (77, 150, 255))
    texto_centro(d, "Demo en vivo · corre en local en 2 minutos", 420,
                 fuente(FONT, 32), MUTED)
    texto_centro(d, "Hecho con agentes de IA (Kimi Code) · datos públicos",
                 640, fuente(FONT, 22), MUTED)
    return img


ESCENAS = [
    ("titulo", None,
     "Presentamos DatoPerú: tu pregunta, dato oficial en cinco segundos. "
     "Datos del Banco Central de Reserva y del INEI, siempre con la fuente citada."),
    ("problema", None,
     "El problema: conseguir una cifra oficial toma de veinte a cuarenta minutos. "
     "Periodistas, tesistas y funcionarios pierden ese tiempo todos los días."),
    ("captura", "static/captura_inflacion.png",
     "Preguntas por la inflación de diciembre de dos mil veinticuatro y responde "
     "con la serie oficial del BCRP: uno coma noventa y siete por ciento, con gráfico y código de serie."),
    ("captura", "static/captura_cusco.png",
     "O preguntas la pobreza en Cusco: dieciocho coma cinco por ciento, calculado "
     "con los microdatos de la ENAHO, con factor de expansión."),
    ("captura", "static/captura_mapa.png",
     "Y el mapa de pobreza por departamento: veinticinco regiones, unidas por "
     "código oficial, desde Ica con seis por ciento hasta Cajamarca con cuarenta y cinco."),
    ("tecnologia", None,
     "¿Cómo funciona? Un motor de intenciones elige la herramienta: el servidor "
     "MCP del BCRP con diecisiete mil series, y las Skills de la ENAHO con ciento ocho mil personas procesadas."),
    ("cta", None,
     "Pruébalo hoy en github.com/jonatan-amaya/dato-peru. Corre en tu laptop en "
     "dos minutos. Hecho con agentes de IA y datos públicos del Perú."),
]


async def narrar(texto, destino):
    import edge_tts
    await edge_tts.Communicate(texto, "es-PE-AlexNeural",
                               rate="+6%").save(str(destino))


def musica(duracion, ruta):
    sr = 22050
    acordes = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63],
               [261.63, 329.63, 392.0], [196.0, 246.94, 293.66]]
    t_a = 4.0
    t = np.linspace(0, t_a, int(sr * t_a), endpoint=False)
    env = np.minimum(t / 0.8, 1.0) * np.minimum((t_a - t) / 0.8, 1.0)
    ondas = []
    for ac in acordes:
        o = sum(np.sin(2 * np.pi * f * t) * 0.28 for f in ac)
        o += 0.4 * np.sin(2 * np.pi * (ac[0] / 2) * t)
        ondas.append(o * env)
    ciclo = np.concatenate(ondas)
    senal = np.tile(ciclo, int(np.ceil(duracion / t_a)) + 1)[: int(sr * duracion)]
    senal = senal / np.abs(senal).max() * 0.9 * 0.14
    fade = int(sr * 1.5)
    senal[:fade] *= np.linspace(0, 1, fade)
    senal[-fade:] *= np.linspace(1, 0, fade)
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((senal * 32767).astype(np.int16).tobytes())


def main():
    from moviepy.editor import (AudioFileClip, CompositeAudioClip, ImageClip,
                                concatenate_videoclips)

    clips, tiempos = [], []
    inicio = 0.0
    for i, (tipo, ruta, narracion) in enumerate(ESCENAS, 1):
        if tipo == "titulo":
            img = escena_titulo()
        elif tipo == "problema":
            img = escena_problema()
        elif tipo == "tecnologia":
            img = escena_tecnologia()
        elif tipo == "cta":
            img = escena_cta()
        else:
            img = escena_captura(RAIZ / ruta, "Demo en vivo",
                                 narracion[:90] + "…" if len(narracion) > 90 else narracion)
        png = REC / f"_v{i}.png"
        img.save(png)

        mp3 = REC / f"_n{i}.mp3"
        if not mp3.exists():
            print(f"[tts] escena {i}")
            asyncio.run(narrar(narracion, mp3))
        audio = AudioFileClip(str(mp3))
        dur = max(audio.duration + 0.4, 5.0)
        clip = ImageClip(str(png)).set_duration(dur).set_audio(audio)
        clips.append(clip)
        tiempos.append((inicio, inicio + audio.duration, narracion))
        inicio += dur
        png.unlink()

    video = concatenate_videoclips(clips, method="compose")
    mrec = REC / "_musica.wav"
    musica(video.duration + 2, mrec)
    mus = AudioFileClip(str(mrec)).subclip(0, min(video.duration, 95))
    video = video.set_audio(CompositeAudioClip([video.audio, mus]))

    salida = REC / "video_respaldo.mp4"
    video.write_videofile(str(salida), fps=30, codec="libx264",
                          audio_codec="aac", bitrate="2200k", threads=4)
    print(f"[ok] {salida} · {video.duration:.1f}s")

    def fmt(s):
        return f"00:{int(s // 60):02d}:{int(s % 60):02d},{int((s % 1) * 1000):03d}"
    srt = "\n\n".join(f"{k}\n{fmt(a)} --> {fmt(b)}\n{t}" for k, (a, b, t)
                      in enumerate(tiempos, 1))
    (REC / "video_respaldo.srt").write_text(srt, encoding="utf-8")
    for p in REC.glob("_n*.mp3"):
        p.unlink()
    mrec.unlink()
    print("[ok] static/video_respaldo.mp4 + .srt")


if __name__ == "__main__":
    main()
