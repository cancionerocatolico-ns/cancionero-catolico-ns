import streamlit as st
import pandas as pd
import requests
import base64
import re

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="ChordMaster GitHub DB", layout="wide", page_icon="🎸")

# Carga de credenciales desde Secrets
TOKEN = st.secrets["GITHUB_TOKEN"]
REPO = st.secrets["GITHUB_REPO"]

# --- FUNCIONES DE GITHUB ---

def leer_canciones_github():
    """Busca archivos .txt en la carpeta 'canciones' del repositorio"""
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
                # Extraemos el título de la primera línea
                titulo = content.split('\n')[0].replace("Título: ", "").strip()
                canciones.append({"archivo": archivo['name'], "titulo": titulo, "contenido": content})
    return canciones

def guardar_en_github(nombre_archivo, contenido):
    """Crea un nuevo archivo .txt en la carpeta 'canciones'"""
    path = f"canciones/{nombre_archivo}.txt"
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    headers = {"Authorization": f"token {TOKEN}"}
    
    # Verificamos si existe para actualizarlo o crearlo de cero
    res = requests.get(url, headers=headers)
    sha = res.json().get('sha') if res.status_code == 200 else None
    
    content_b64 = base64.b64encode(contenido.encode('utf-8')).decode('utf-8')
    payload = {
        "message": f"Nueva canción: {nombre_archivo}",
        "content": content_b64
    }
    if sha: payload["sha"] = sha
    
    put_res = requests.put(url, headers=headers, json=payload)
    return put_res.status_code in [200, 201]

# --- MOTOR MUSICAL ---
NOTAS_LAT = ["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"]
NOTAS_AMER = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def transportar_nota(nota, semitonos):
    for lista in [NOTAS_AMER, NOTAS_LAT]:
        if nota in lista:
            idx = (lista.index(nota) + semitonos) % 12
            return lista[idx]
    return nota

def procesar_texto(texto, semitonos):
    if not texto: return ""
    lineas = []
    for linea in texto.split('\n'):
        if not linea.strip():
            lineas.append("&nbsp;")
            continue
        # Detectar si la línea es de acordes (más del 20% de espacios)
        es_acordes = (linea.count(" ") / len(linea)) > 0.15 if len(linea) > 5 else True
        partes = re.split(r"(\s+)", linea)
        linea_proc = ""
        for p in partes:
            if p.strip() == "":
                linea_proc += p.replace(" ", "&nbsp;")
            else:
                patron = r"^(Do#?|Re#?|Mi|Fa#?|Sol#?|La#?|Si|[A-G][#b]?)(.*)$"
                m = re.match(patron, p)
                if m:
                    n_nota = transportar_nota(m.group(1), semitonos)
                    linea_proc += f"<b>{n_nota}{m.group(2)}</b>"
                else:
                    linea_proc += p
        lineas.append(linea_proc)
    return "<br>".join(lineas)

# --- INTERFAZ ---
st.sidebar.title("🎸 ChordMaster Pro")
menu = st.sidebar.selectbox("Menú", ["🏠 Cantar", "➕ Agregar Canción", "🔄 Sincronizar"])
f_size = st.sidebar.slider("Tamaño Fuente", 15, 45, 25)

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Courier+Prime&display=swap');
    .visor-musical {{ 
        font-family: 'Courier Prime', monospace !important; 
        background: white; color: black; padding: 30px; border-radius: 15px;
        font-size: {f_size}px; line-height: 1.1; border: 1px solid #eee;
    }}
    .visor-musical b {{ color: #d32f2f; font-weight: bold; }}
    </style>
    """, unsafe_allow_html=True)

if menu == "🏠 Cantar":
    with st.spinner("Cargando canciones..."):
        canciones = leer_canciones_github()
    
    if canciones:
        titulos = [c['titulo'] for c in canciones]
        sel = st.selectbox("Buscar canción:", titulos)
        can = next(item for item in canciones if item["titulo"] == sel)
        
        tp = st.number_input("Transportar", -6, 6, 0)
        st.markdown(f'<div class="visor-musical">{procesar_texto(can["contenido"], tp)}</div>', unsafe_allow_html=True)
    else:
        st.info("No hay canciones. ¡Agrega la primera!")

elif menu == "➕ Agregar Canción":
    st.header("➕ Nueva Canción")
    titulo = st.text_input("Título")
    autor = st.text_input("Autor")
    letra = st.text_area("Letra y Acordes (usa espacios para alinear)", height=350)
    
    if st.button("💾 Guardar en GitHub"):
        if titulo and letra:
            # Formateamos el contenido del archivo
            contenido_final = f"Título: {titulo}\nAutor: {autor}\n\n{letra}"
            # Nombre de archivo limpio (sin espacios)
            nombre_archivo = titulo.lower().replace(" ", "_")
            
            if guardar_en_github(nombre_archivo, contenido_final):
                st.success(f"¡'{titulo}' guardada exitosamente!")
                st.balloons()
            else:
                st.error("Error al guardar. Revisa los Secrets.")
        else:
            st.error("Título y Letra son obligatorios.")

elif menu == "🔄 Sincronizar":
    st.write("Sincroniza la app con los archivos de GitHub.")
    if st.button("Actualizar Lista"):
        st.rerun()
