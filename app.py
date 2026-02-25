import streamlit as st
import pandas as pd
import requests
import base64
import re

# --- CONFIGURACIÓN DE GITHUB (MOTOR DE ALMACENAMIENTO) ---
TOKEN = st.secrets["GITHUB_TOKEN"]
REPO = st.secrets["GITHUB_REPO"]

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
                # Extraer metadatos de las primeras líneas del archivo .txt
                titulo = lineas[0].replace("Título: ", "").strip() if "Título: " in lineas[0] else archivo['name']
                autor = lineas[1].replace("Autor: ", "").strip() if len(lineas) > 1 and "Autor: " in lineas[1] else "Anónimo"
                categoria = lineas[2].replace("Categoría: ", "").strip() if len(lineas) > 2 and "Categoría: " in lineas[2] else "Varios"
                letra = "\n".join(lineas[4:]) if len(lineas) > 4 else content
                
                canciones.append({
                    "Título": titulo, 
                    "Autor": autor, 
                    "Categoría": categoria, 
                    "Letra": letra, 
                    "archivo": archivo['name']
                })
    return pd.DataFrame(canciones)

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

def eliminar_de_github(nombre_archivo):
    path = f"canciones/{nombre_archivo}"
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    headers = {"Authorization": f"token {TOKEN}"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        sha = res.json().get('sha')
        payload = {"message": f"Eliminar: {nombre_archivo}", "sha": sha}
        requests.delete(url, headers=headers, json=payload)
        return True
    return False

# --- LÓGICA DE PROCESAMIENTO MUSICAL (ORIGINAL) ---
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
        if raiz in ["Si", "La", "A"] and not resto and not es_linea_acordes:
            return palabra
        if semitonos == 0:
            return f"<b>{palabra}</b>"
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

# Cargar datos desde GitHub
df = leer_canciones_github()
categorias = ["Entrada", "Piedad", "Gloria", "Aleluya", "Ofertorio", "Santo", "Cordero", "Comunión", "Salida", "Adoración", "María"]

# Sidebar
st.sidebar.title("🎸 ChordMaster")
menu = st.sidebar.selectbox("Menú:", ["🏠 Cantar / Vivo", "📋 Mi Setlist", "➕ Agregar Canción", "📂 Gestionar / Editar"])
st.sidebar.markdown("---")
c_bg = st.sidebar.color_picker("Fondo Visor", "#FFFFFF")
c_txt = st.sidebar.color_picker("Color Letra", "#000000")
f_size = st.sidebar.slider("Tamaño Fuente", 12, 45, 18)

# Estilos CSS
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Courier+Prime&display=swap');
    .visor-musical, textarea {{ font-family: 'Courier Prime', monospace !important; }}
    .visor-musical {{ 
        background-color: {c_bg} !important; color: {c_txt} !important; 
        border-radius: 12px; padding: 25px; border: 1px solid #ddd; 
        line-height: 1.2; font-size: {f_size}px; overflow-x: auto;
    }}
    .visor-musical b {{ font-weight: 700 !important; color: #d32f2f; }}
    </style>
    """, unsafe_allow_html=True)

# --- MÓDULOS ---

if menu == "🏠 Cantar / Vivo":
    col1, col2 = st.columns([2, 1])
    busqueda = col1.text_input("🔍 Buscar por título...")
    filtro_cat = col2.selectbox("📂 Filtrar Categoría", ["Todas"] + categorias)
    
    df_v = df.copy()
    if busqueda and not df_v.empty: df_v = df_v[df_v['Título'].str.contains(busqueda, case=False, na=False)]
    if filtro_cat != "Todas" and not df_v.empty: df_v = df_v[df_v['Categoría'] == filtro_cat]

    if not df_v.empty:
        sel_c = st.selectbox("Selecciona una canción:", df_v['Título'])
        data = df_v[df_v['Título'] == sel_c].iloc[0]
        
        c_at, c_tp = st.columns([1, 1])
        if c_at.button("➕ Añadir al Setlist", use_container_width=True):
            if sel_c not in st.session_state.setlist:
                st.session_state.setlist.append(sel_c)
                st.toast("Añadida al setlist")
        
        tp = c_tp.number_input("Transportar Tonalidad", -6, 6, 0)
        
        st.markdown(f'''
            <div class="visor-musical">
                <h2 style="margin-bottom:0; color:inherit;">{data["Título"]}</h2>
                <p style="margin-top:0; opacity:0.7;">{data["Autor"]} | {data["Categoría"]}</p>
                <hr style="border-color: {c_txt}; opacity:0.2;">
                {procesar_texto_final(data["Letra"], tp)}
            </div>
        ''', unsafe_allow_html=True)

elif menu == "📋 Mi Setlist":
    st.header("📋 Mi Setlist de Hoy")
    if not st.session_state.setlist:
        st.info("El setlist está vacío.")
    else:
        for i, t in enumerate(st.session_state.setlist):
            with st.expander(f"🎵 {i+1}. {t}"):
                cancion = df[df['Título'] == t]
                if not cancion.empty:
                    data = cancion.iloc[0]
                    c_del, c_tp_s = st.columns([1, 2])
                    if c_del.button("🗑️ Quitar", key=f"del_{i}", use_container_width=True):
                        st.session_state.setlist.pop(i); st.rerun()
                    tp_s = c_tp_s.number_input("Transportar", -6, 6, 0, key=f"tp_{i}")
                    st.markdown(f'<div class="visor-musical">{procesar_texto_final(data["Letra"], tp_s)}</div>', unsafe_allow_html=True)
        if st.button("🗑️ Limpiar Todo el Setlist"):
            st.session_state.setlist = []
            st.rerun()

elif menu == "➕ Agregar Canción":
    st.header("➕ Nueva Canción")
    c1, c2 = st.columns(2)
    t_n = c1.text_input("Título de la canción")
    a_n = c2.text_input("Autor / Artista")
    cat_n = st.selectbox("Categoría", categorias)
    l_n = st.text_area("Letra y Acordes (usa espacios para alinear):", height=300)
    
    if l_n:
        st.subheader("👀 Vista Previa")
        st.markdown(f'''
            <div class="visor-musical">
                <h2 style="margin-bottom:0; color:inherit;">{t_n if t_n else "Título"}</h2>
                <p style="margin-top:0; opacity:0.7;">{a_n if a_n else "Autor"} | {cat_n}</p>
                <hr style="border-color: {c_txt}; opacity:0.2;">
                {procesar_texto_final(l_n, 0)}
            </div>
        ''', unsafe_allow_html=True)
    
    if st.button("💾 Guardar en GitHub"):
        if t_n and l_n:
            nombre_f = t_n.lower().replace(" ", "_")
            contenido = f"Título: {t_n}\nAutor: {a_n if a_n else 'Anónimo'}\nCategoría: {cat_n}\n\n{l_n}"
            if guardar_en_github(nombre_f, contenido):
                st.success("¡Canción guardada correctamente en la nube!"); st.balloons(); st.rerun()
            else:
                st.error("Error al conectar con GitHub.")

elif menu == "📂 Gestionar / Editar":
    st.header("📂 Administrar Biblioteca")
    if df.empty:
        st.info("No hay canciones para editar.")
    else:
        for i, row in df.iterrows():
            with st.expander(f"📝 Editar: {row['Título']}"):
                ut = st.text_input("Título", row['Título'], key=f"edit_t_{i}")
                ul = st.text_area("Letra", row['Letra'], height=250, key=f"edit_l_{i}")
                
                c_upd, c_del_db = st.columns(2)
                if c_upd.button("Actualizar Cambios", key=f"btn_u_{i}"):
                    nombre_f = ut.lower().replace(" ", "_")
                    contenido = f"Título: {ut}\nAutor: {row['Autor']}\nCategoría: {row['Categoría']}\n\n{ul}"
                    guardar_en_github(row['archivo'].replace(".txt", ""), contenido)
                    st.rerun()
                if c_del_db.button("⚠️ Eliminar Permanente", key=f"btn_d_{i}"):
                    eliminar_de_github(row['archivo'])
                    st.rerun()

if st.sidebar.button("🔄 Refrescar Nube"):
    st.cache_data.clear()
    st.rerun()
