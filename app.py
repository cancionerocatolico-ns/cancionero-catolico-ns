import streamlit as st
import pandas as pd
import requests
import base64
import re

# --- CONFIGURACIÓN DE PÁGINA (ESTILO ORIGINAL) ---
st.set_page_config(page_title="ChordMaster Pro", layout="wide", page_icon="🎸")

# Carga de credenciales desde Secrets
TOKEN = st.secrets["GITHUB_TOKEN"]
REPO = st.secrets["GITHUB_REPO"]

# --- FUNCIONES DE GITHUB ---
def leer_canciones_github():
    url = f"https://api.github.com/repos/{REPO}/contents/canciones"
    headers = {"Authorization": f"token {TOKEN}"}
    response = requests.get(url, headers=headers)
    canciones = []
    if response.status_code == 200:
        archivos = response.json()
        for archivo in archivos:
            if archivo['name'].endswith('.txt'):
                res_file = requests.get(archivo['download_url'])
                content = res_file.text
                lineas = content.split('\n')
                titulo = lineas[0].replace("Título: ", "").strip()
                canciones.append({"archivo": archivo['name'], "titulo": titulo, "contenido": content})
    return canciones

def guardar_en_github(nombre_archivo, contenido):
    path = f"canciones/{nombre_archivo}.txt"
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    headers = {"Authorization": f"token {TOKEN}"}
    res = requests.get(url, headers=headers)
    sha = res.json().get('sha') if res.status_code == 200 else None
    content_b64 = base64.b64encode(contenido.encode('utf-8')).decode('utf-8')
    payload = {"message": f"Actualizar: {nombre_archivo}", "content": content_b64}
    if sha: payload["sha"] = sha
    put_res = requests.put(url, headers=headers, json=payload)
    return put_res.status_code in [200, 201]

# --- MOTOR DE TRANSPORTE ---
NOTAS_LAT = ["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"]
NOTAS_AMER = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def transportar_nota(nota, semitonos):
    for lista in [NOTAS_AMER, NOTAS_LAT]:
        if nota in lista:
            idx = (lista.index(nota) + semitonos) % 12
            return lista[idx]
    return nota

def procesar_palabra(p, semitonos, es_acordes):
    patron = r"^(Do#?|Re#?|Mi|Fa#?|Sol#?|La#?|Si|[A-G][#b]?)([\#bmM79dimatusj0-9]*)$"
    m = re.match(patron, p)
    if m:
        raiz, resto = m.group(1), m.group(2)
        if semitonos == 0: return f"<b>{p}</b>"
        nueva = transportar_nota(raiz, semitonos)
        return f"<b>{nueva}{resto}</b>"
    return p

def procesar_texto_final(texto, semitonos):
    if not texto: return ""
    lineas = []
    for linea in texto.split('\n'):
        if not linea.strip():
            lineas.append("&nbsp;")
            continue
        es_acordes = (linea.count(" ") / len(linea)) > 0.15 if len(linea) > 5 else True
        partes = re.split(r"(\s+)", linea)
        procesada = "".join([p if p.strip() == "" else procesar_palabra(p, semitonos, es_acordes) for p in partes])
        lineas.append(procesada.replace(" ", "&nbsp;"))
    return "<br>".join(lineas)

# --- INTERFAZ (ENTORNO ORIGINAL) ---
if 'setlist' not in st.session_state: st.session_state.setlist = []

st.sidebar.title("🎸 ChordMaster Pro")
menu = st.sidebar.selectbox("Menú Principal", ["🏠 Cantar", "📋 Mi Setlist", "➕ Agregar Canción", "📂 Gestionar Base"])
f_size = st.sidebar.slider("Tamaño Fuente", 15, 45, 25)

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Courier+Prime&display=swap');
    .visor-musical {{ 
        font-family: 'Courier Prime', monospace !important; 
        background: white; color: black; padding: 30px; border-radius: 12px;
        font-size: {f_size}px; line-height: 1.1; border: 1px solid #ddd;
    }}
    .visor-musical b {{ color: #d32f2f; font-weight: bold; }}
    </style>
    """, unsafe_allow_html=True)

# --- NAVEGACIÓN ---
if menu == "🏠 Cantar":
    canciones = leer_canciones_github()
    if canciones:
        titulos = [c['titulo'] for c in canciones]
        sel = st.selectbox("🔍 Buscar canción:", titulos)
        can = next(item for item in canciones if item["titulo"] == sel)
        
        col1, col2 = st.columns([1,1])
        tp = col1.number_input("Transportar", -6, 6, 0)
        if col2.button("➕ Añadir al Setlist"):
            if sel not in st.session_state.setlist:
                st.session_state.setlist.append(sel)
                st.success("Añadida!")

        st.markdown(f'<div class="visor-musical">{procesar_texto_final(can["contenido"], tp)}</div>', unsafe_allow_html=True)
    else:
        st.info("No hay canciones en GitHub. Agrégalas en el menú correspondiente.")

elif menu == "📋 Mi Setlist":
    st.header("📋 Setlist del Día")
    if st.session_state.setlist:
        canciones = leer_canciones_github()
        for nombre in st.session_state.setlist:
            with st.expander(f"📖 {nombre}"):
                c_data = next(item for item in canciones if item["titulo"] == nombre)
                st.markdown(f'<div class="visor-musical">{procesar_texto_final(c_data["contenido"], 0)}</div>', unsafe_allow_html=True)
        if st.button("🗑️ Limpiar Setlist"):
            st.session_state.setlist = []
            st.rerun()
    else:
        st.info("Tu setlist está vacío.")

elif menu == "➕ Agregar Canción":
    st.header("➕ Nueva Canción")
    t = st.text_input("Título")
    a = st.text_input("Autor")
    l = st.text_area("Letra y Cifrado (Usa espacios para alinear)", height=400)
    
    if st.button("💾 Guardar permanentemente"):
        if t and l:
            nombre_archivo = t.lower().replace(" ", "_")
            contenido = f"Título: {t}\nAutor: {a}\n\n{l}"
            if guardar_en_github(nombre_archivo, contenido):
                st.success(f"¡'{t}' guardada en la nube!")
                st.balloons()
            else:
                st.error("Error al guardar en GitHub. Revisa los Secrets.")

elif menu == "📂 Gestionar Base":
    st.header("📂 Gestión de Archivos")
    canciones = leer_canciones_github()
    st.write(f"Total de archivos en GitHub: {len(canciones)}")
    for c in canciones:
        st.text(f"📄 {c['archivo']}")
    if st.button("🔄 Forzar Sincronización"):
        st.rerun()
