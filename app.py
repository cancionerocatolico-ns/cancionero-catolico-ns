import streamlit as st
import pandas as pd
import requests
import base64
import re

# --- CONFIGURACIÓN DE GITHUB ---
TOKEN = st.secrets["GITHUB_TOKEN"]
REPO = st.secrets["GITHUB_REPO"]

def leer_archivo_github(path):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    headers = {"Authorization": f"token {TOKEN}"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        return requests.get(res.json()['download_url']).text
    return None

def leer_canciones_github():
    url = f"https://api.github.com/repos/{REPO}/contents/canciones"
    headers = {"Authorization": f"token {TOKEN}"}
    response = requests.get(url, headers=headers)
    canciones = []
    if response.status_code == 200:
        archivos = response.json()
        for archivo in archivos:
            if archivo['name'].endswith('.txt') and archivo['name'] != 'categorias.txt':
                res_file = requests.get(archivo['download_url'])
                content = res_file.text
                lineas = content.split('\n')
                titulo = lineas[0].replace("Título: ", "").strip() if "Título: " in lineas[0] else archivo['name']
                autor = lineas[1].replace("Autor: ", "").strip() if len(lineas) > 1 and "Autor: " in lineas[1] else "Anónimo"
                categoria = lineas[2].replace("Categoría: ", "").strip() if len(lineas) > 2 and "Categoría: " in lineas[2] else "Varios"
                letra = "\n".join(lineas[4:]) if len(lineas) > 4 else content
                canciones.append({
                    "Título": titulo, "Autor": autor, "Categoría": categoria, 
                    "Letra": letra, "archivo": archivo['name']
                })
    return pd.DataFrame(canciones)

def guardar_en_github(nombre_archivo, contenido, es_config=False):
    path = f"canciones/{nombre_archivo}.txt" if not es_config else f"canciones/{nombre_archivo}"
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    headers = {"Authorization": f"token {TOKEN}"}
    res = requests.get(url, headers=headers)
    sha = res.json().get('sha') if res.status_code == 200 else None
    content_b64 = base64.b64encode(contenido.encode('utf-8')).decode('utf-8')
    payload = {"message": f"Actualizar {nombre_archivo}", "content": content_b64}
    if sha: payload["sha"] = sha
    return requests.put(url, headers=headers, json=payload).status_code in [200, 201]

def eliminar_de_github(nombre_archivo):
    path = f"canciones/{nombre_archivo}"
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    headers = {"Authorization": f"token {TOKEN}"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        sha = res.json().get('sha')
        payload = {"message": f"Eliminar {nombre_archivo}", "sha": sha}
        return requests.delete(url, headers=headers, json=payload).status_code == 200
    return False

# --- PROCESAMIENTO MUSICAL ---
NOTAS_LAT = ["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"]
NOTAS_AMER = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def transportar_nota(nota, semitonos):
    for lista in [NOTAS_AMER, NOTAS_LAT]:
        if nota in lista:
            idx = (lista.index(nota) + semitonos) % 12
            return lista[idx]
    return nota

def procesar_palabra(palabra, semitonos, es_linea_acordes):
    patron = r"^(Do#?|Re#?|Mi|Fa#?|Sol#?|La#?|Si|[A-G][#b]?)([\#bmM79dimatusj0-9]*)$"
    match = re.match(patron, palabra)
    if match:
        raiz, resto = match.group(1), match.group(2)
        if raiz in ["Si", "La", "A"] and not resto and not es_linea_acordes: return palabra
        if semitonos == 0: return f"<b>{palabra}</b>"
        dic_bemoles = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}
        nota_busqueda = dic_bemoles.get(raiz, raiz)
        nueva_raiz = transportar_nota(nota_busqueda, semitonos)
        return f"<b>{nueva_raiz}{resto}</b>"
    return palabra

def procesar_texto_final(texto, semitonos):
    if not texto: return ""
    lineas = []
    for linea in texto.split('\n'):
        if not linea.strip():
            lineas.append("&nbsp;")
            continue
        es_linea_acordes = (linea.count(" ") / len(linea)) > 0.2 if len(linea) > 6 else True
        partes = re.split(r"(\s+)", linea)
        procesada = "".join([p if p.strip() == "" else procesar_palabra(p, semitonos, es_linea_acordes) for p in partes])
        lineas.append(procesada.replace(" ", "&nbsp;"))
    return "<br>".join(lineas)

# --- INTERFAZ ---
st.set_page_config(page_title="ChordMaster Pro", layout="wide")
if 'setlist' not in st.session_state: st.session_state.setlist = []

# Cargar Categorías desde GitHub
cat_raw = leer_archivo_github("canciones/categorias.txt")
categorias = cat_raw.split(',') if cat_raw else ["Entrada", "Piedad", "Gloria", "Ofertorio", "Comunión", "Salida"]

df = leer_canciones_github()

# Sidebar
st.sidebar.title("🎸 ChordMaster")
menu = st.sidebar.selectbox("Menú:", ["🏠 Cantar / Vivo", "📋 Mi Setlist", "➕ Agregar Canción", "📂 Gestionar / Editar", "⚙️ Categorías"])
st.sidebar.markdown("---")
c_bg = st.sidebar.color_picker("Fondo Visor", "#FFFFFF")
c_txt = st.sidebar.color_picker("Color Letra", "#000000")
c_chord = st.sidebar.color_picker("Color Acordes", "#D32F2F")
f_size = st.sidebar.slider("Tamaño Fuente", 12, 45, 18)

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Courier+Prime&display=swap');
    .visor-musical {{ 
        font-family: 'Courier Prime', monospace !important; 
        background-color: {c_bg} !important; color: {c_txt} !important; 
        border-radius: 12px; padding: 25px; border: 1px solid #ddd; 
        line-height: 1.2; font-size: {f_size}px;
    }}
    .visor-musical b {{ font-weight: 700 !important; color: {c_chord} !important; }}
    </style>
    """, unsafe_allow_html=True)

# --- MÓDULOS ---

if menu == "🏠 Cantar / Vivo":
    col1, col2 = st.columns([2, 1])
    busqueda = col1.text_input("🔍 Buscar...")
    filtro_cat = col2.selectbox("📂 Filtro", ["Todas"] + categorias)
    df_v = df.copy()
    if busqueda and not df_v.empty: df_v = df_v[df_v['Título'].str.contains(busqueda, case=False, na=False)]
    if filtro_cat != "Todas" and not df_v.empty: df_v = df_v[df_v['Categoría'] == filtro_cat]
    if not df_v.empty:
        sel_c = st.selectbox("Selecciona:", df_v['Título'])
        data = df_v[df_v['Título'] == sel_c].iloc[0]
        tp = st.number_input("Transportar", -6, 6, 0)
        st.markdown(f'<div class="visor-musical"><h2>{data["Título"]}</h2><p>{data["Autor"]} | {data["Categoría"]}</p><hr>{procesar_texto_final(data["Letra"], tp)}</div>', unsafe_allow_html=True)

elif menu == "➕ Agregar Canción":
    st.header("➕ Nueva Canción")
    t_n = st.text_input("Título")
    a_n = st.text_input("Autor")
    cat_n = st.selectbox("Categoría", categorias)
    l_n = st.text_area("Letra y Acordes:", height=300)
    if l_n:
        st.markdown(f'<div class="visor-musical">{procesar_texto_final(l_n, 0)}</div>', unsafe_allow_html=True)
    if st.button("💾 Guardar en GitHub"):
        if t_n and l_n:
            nombre_f = t_n.lower().replace(" ", "_")
            contenido = f"Título: {t_n}\nAutor: {a_n}\nCategoría: {cat_n}\n\n{l_n}"
            if guardar_en_github(nombre_f, contenido): st.success("¡Guardada!"); st.rerun()

elif menu == "⚙️ Categorías":
    st.header("⚙️ Gestionar Categorías")
    nueva_cat = st.text_input("Nueva Categoría:")
    if st.button("Añadir"):
        if nueva_cat and nueva_cat not in categorias:
            categorias.append(nueva_cat)
            guardar_en_github("categorias", ",".join(categorias), es_config=True)
            st.rerun()
    
    st.write("---")
    for c in categorias:
        col_c, col_b = st.columns([3, 1])
        col_c.write(f"• {c}")
        if col_b.button("Eliminar", key=f"del_{c}"):
            categorias.remove(c)
            guardar_en_github("categorias", ",".join(categorias), es_config=True)
            st.rerun()

elif menu == "📂 Gestionar / Editar":
    st.header("📂 Editar Biblioteca")
    for i, row in df.iterrows():
        with st.expander(f"📝 {row['Título']}"):
            ut = st.text_input("Título", row['Título'], key=f"e_t_{i}")
            uc = st.selectbox("Categoría", categorias, index=categorias.index(row['Categoría']) if row['Categoría'] in categorias else 0, key=f"e_c_{i}")
            ul = st.text_area("Letra", row['Letra'], height=250, key=f"e_l_{i}")
            if st.button("Guardar Cambios", key=f"b_u_{i}"):
                guardar_en_github(row['archivo'].replace(".txt", ""), f"Título: {ut}\nAutor: {row['Autor']}\nCategoría: {uc}\n\n{ul}")
                st.rerun()
            if st.button("Eliminar Permanente", key=f"b_d_{i}"):
                eliminar_de_github(row['archivo']); st.rerun()

if st.sidebar.button("🔄 Refrescar Nube"):
    st.cache_data.clear(); st.rerun()
