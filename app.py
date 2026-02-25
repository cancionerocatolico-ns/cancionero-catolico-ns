import streamlit as st
import pandas as pd
import requests
import base64
import re
import time

# --- OPTIMIZACIÓN CRON-JOB (Mantener vivo sin gastar recursos) ---
if "user_agent" in st.context.headers:
    if "cron-job.org" in st.context.headers["user_agent"]:
        st.write("Ping recibido: ChordMaster está activo.")
        st.stop()

# --- CONFIGURACIÓN DE GITHUB (Secrets) ---
TOKEN = st.secrets["GITHUB_TOKEN"]
REPO = st.secrets["GITHUB_REPO"]

# --- FUNCIONES DE COMUNICACIÓN CON GITHUB ---

def leer_archivo_github(path):
    """Lee un archivo de GitHub forzando la descarga fresca (sin cache)."""
    # El timestamp (?t=) engaña a la API de GitHub para que no dé datos viejos
    url = f"https://api.github.com/repos/{REPO}/contents/{path}?t={int(time.time())}"
    headers = {
        "Authorization": f"token {TOKEN}",
        "Cache-Control": "no-cache"
    }
    res = requests.get(url, headers=headers)
    
    if res.status_code == 200:
        download_url = res.json()['download_url'] + f"&nocache={int(time.time())}"
        return requests.get(download_url).text
    return None

def leer_canciones_github():
    """Lee todos los archivos .txt de la carpeta /canciones/."""
    url = f"https://api.github.com/repos/{REPO}/contents/canciones?t={int(time.time())}"
    headers = {"Authorization": f"token {TOKEN}"}
    response = requests.get(url, headers=headers)
    canciones = []
    
    if response.status_code == 200:
        archivos = response.json()
        for archivo in archivos:
            # Filtramos para no leer el archivo de categorías como si fuera una canción
            if archivo['name'].endswith('.txt') and archivo['name'] != 'categorias.txt':
                res_file = requests.get(archivo['download_url'] + f"?t={int(time.time())}")
                content = res_file.text
                lineas = content.split('\n')
                
                # Parseo de metadatos (Líneas 0 a 3)
                titulo = lineas[0].replace("Título: ", "").strip() if "Título: " in lineas[0] else archivo['name']
                autor = lineas[1].replace("Autor: ", "").strip() if len(lineas) > 1 and "Autor: " in lineas[1] else "Anónimo"
                categoria = lineas[2].replace("Categoría: ", "").strip() if len(lineas) > 2 and "Categoría: " in lineas[2] else "Varios"
                referencia = lineas[3].replace("Referencia: ", "").strip() if len(lineas) > 3 and "Referencia: " in lineas[3] else ""
                letra = "\n".join(lineas[5:]) if len(lineas) > 5 else content
                
                canciones.append({
                    "Título": titulo, "Autor": autor, "Categoría": categoria, 
                    "Referencia": referencia, "Letra": letra, "archivo": archivo['name']
                })
    return pd.DataFrame(canciones)

def guardar_en_github(nombre_archivo, contenido):
    """Guarda o actualiza un archivo en /canciones/ forzando extensión .txt."""
    if not nombre_archivo.endswith(".txt"):
        nombre_archivo += ".txt"
        
    path = f"canciones/{nombre_archivo}"
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    headers = {"Authorization": f"token {TOKEN}"}
    
    # Obtener el SHA actual para poder sobreescribir
    res = requests.get(url, headers=headers)
    sha = res.json().get('sha') if res.status_code == 200 else None
    
    content_b64 = base64.b64encode(contenido.encode('utf-8')).decode('utf-8')
    payload = {"message": f"Update {nombre_archivo}", "content": content_b64}
    if sha: payload["sha"] = sha
    
    result = requests.put(url, headers=headers, json=payload)
    if result.status_code in [200, 201]:
        st.cache_data.clear() # Limpia cache interno de Streamlit
        time.sleep(1)         # Pausa para que GitHub propague el cambio
        return True
    return False

# --- PROCESAMIENTO MUSICAL (Transporte de notas) ---

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
        # Detectar si la línea es de acordes por la densidad de espacios
        es_linea_acordes = (linea.count(" ") / len(linea)) > 0.18 if len(linea) > 5 else True
        partes = re.split(r"(\s+)", linea)
        procesada = "".join([p if p.strip() == "" else procesar_palabra(p, semitonos, es_linea_acordes) for p in partes])
        lineas.append(procesada.replace(" ", "&nbsp;"))
    return "<br>".join(lineas)

# --- INTERFAZ DE STREAMLIT ---

st.set_page_config(page_title="ChordMaster Pro", layout="wide")
if 'setlist' not in st.session_state: st.session_state.setlist = []

# Carga segura de categorías (Evita el 404)
cat_raw = leer_archivo_github("canciones/categorias.txt")
if cat_raw:
    categorias = sorted([c.strip() for c in cat_raw.split(',') if c.strip()])
else:
    categorias = ["Entrada", "Piedad", "Gloria", "Ofertorio", "Comunión", "Salida"]

df = leer_canciones_github()

# Sidebar
st.sidebar.title("🎸 ChordMaster")
menu = st.sidebar.selectbox("Menú:", ["🏠 Cantar / Vivo", "📋 Mi Setlist", "➕ Agregar Canción", "📂 Gestionar / Editar", "⚙️ Categorías"])
st.sidebar.markdown("---")
c_bg = st.sidebar.color_picker("Fondo Visor", "#FFFFFF")
c_txt = st.sidebar.color_picker("Color Letra", "#000000")
c_chord = st.sidebar.color_picker("Color Acordes", "#D32F2F")
f_size = st.sidebar.slider("Tamaño Fuente", 12, 45, 18)

# CSS para alineación perfecta de acordes
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Courier+Prime&display=swap');
    .visor-musical, textarea, .stTextArea textarea, .stTextInput input {{
        font-family: 'Courier Prime', monospace !important;
        line-height: 1.2 !important; font-size: {f_size}px !important;
    }}
    .visor-musical {{ 
        background-color: {c_bg} !important; color: {c_txt} !important; 
        border-radius: 12px; padding: 25px; border: 1px solid #ddd; overflow-x: auto;
        white-space: pre !important;
    }}
    .visor-musical b {{ font-weight: 700 !important; color: {c_chord} !important; }}
    </style>
    """, unsafe_allow_html=True)

# --- MÓDULOS DE NAVEGACIÓN ---

if menu == "🏠 Cantar / Vivo":
    col1, col2 = st.columns([2, 1])
    busqueda = col1.text_input("🔍 Buscar canción...")
    filtro_cat = col2.selectbox("📂 Categoría", ["Todas"] + categorias)
    
    df_v = df.copy()
    if not df_v.empty:
        if busqueda: df_v = df_v[df_v['Título'].str.contains(busqueda, case=False, na=False)]
        if filtro_cat != "Todas": df_v = df_v[df_v['Categoría'] == filtro_cat]
    
    if not df_v.empty:
        sel_c = st.selectbox("Selecciona canción:", df_v['Título'])
        data = df_v[df_v['Título'] == sel_c].iloc[0]
        
        c_at, c_tp = st.columns([1, 1])
        if c_at.button("➕ Al Setlist", use_container_width=True):
            if sel_c not in st.session_state.setlist:
                st.session_state.setlist.append(sel_c); st.toast("Añadida")
        tp = c_tp.number_input("Transportar (Semitonos)", -6, 6, 0)
        
        if data["Referencia"]:
            st.link_button("🔗 Abrir Referencia", data["Referencia"], use_container_width=True)

        st.markdown(f'''
            <div class="visor-musical">
<h2 style="margin:0; color:inherit;">{data["Título"]}</h2>
<p style="margin-top:0; opacity:0.7;">{data["Autor"]} | {data["Categoría"]}</p>
<hr style="border-color: {c_txt}; opacity:0.2;">
{procesar_texto_final(data["Letra"], tp)}
            </div>
        ''', unsafe_allow_html=True)

elif menu == "➕ Agregar Canción":
    st.header("➕ Nueva Canción")
    c1, c2 = st.columns(2)
    t_n = c1.text_input("Título")
    a_n = c2.text_input("Autor")
    cat_n = st.selectbox("Categoría", categorias)
    r_n = st.text_input("Referencia (Link URL)")
    l_n = st.text_area("Letra y Acordes (usa espacios para alinear):", height=350)
    
    if l_n:
        st.subheader("👀 Vista Previa")
        st.markdown(f'<div class="visor-musical">{procesar_texto_final(l_n, 0)}</div>', unsafe_allow_html=True)
    
    if st.button("💾 Guardar en GitHub"):
        if t_n and l_n:
            nombre_f = t_n.lower().replace(" ", "_")
            contenido = f"Título: {t_n}\nAutor: {a_n}\nCategoría: {cat_n}\nReferencia: {r_n}\n\n{l_n}"
            if guardar_en_github(nombre_f, contenido): 
                st.success("¡Canción guardada!"); st.rerun()

elif menu == "📋 Mi Setlist":
    st.header("📋 Mi Setlist")
    if not st.session_state.setlist:
        st.info("El setlist está vacío.")
    else:
        for i, t in enumerate(st.session_state.setlist):
            with st.expander(f"🎵 {i+1}. {t}"):
                cancion = df[df['Título'] == t]
                if not cancion.empty:
                    data = cancion.iloc[0]
                    if st.button("Quitar de la lista", key=f"del_{i}"):
                        st.session_state.setlist.pop(i); st.rerun()
                    if data["Referencia"]: st.link_button("🌐 Ir a Referencia", data["Referencia"])
                    st.markdown(f'<div class="visor-musical">{procesar_texto_final(data["Letra"], 0)}</div>', unsafe_allow_html=True)

elif menu == "📂 Gestionar / Editar":
    st.header("📂 Editar Biblioteca")
    for i, row in df.iterrows():
        with st.expander(f"📝 Editar: {row['Título']}"):
            ut = st.text_input("Título", row['Título'], key=f"et_{i}")
            ua = st.text_input("Autor", row['Autor'], key=f"ea_{i}")
            ur = st.text_input("Referencia", row['Referencia'], key=f"er_{i}")
            uc = st.selectbox("Categoría", categorias, index=categorias.index(row['Categoría']) if row['Categoría'] in categorias else 0, key=f"ec_{i}")
            ul = st.text_area("Letra", row['Letra'], height=300, key=f"el_{i}")
            if st.button("Actualizar cambios", key=f"ub_{i}"):
                nombre_f = row['archivo'].replace(".txt", "")
                nuevo_cont = f"Título: {ut}\nAutor: {ua}\nCategoría: {uc}\nReferencia: {ur}\n\n{ul}"
                if guardar_en_github(nombre_f, nuevo_cont): 
                    st.success("¡Actualizado!"); st.rerun()

elif menu == "⚙️ Categorías":
    st.header("⚙️ Gestión de Categorías")
    nueva_cat = st.text_input("Nombre de nueva categoría:")
    if st.button("Añadir Categoría"):
        if nueva_cat and nueva_cat.strip() not in categorias:
            categorias.append(nueva_cat.strip())
            if guardar_en_github("categorias", ",".join(categorias)):
                st.success("Categoría guardada."); st.rerun()
    
    st.markdown("---")
    st.write("Categorías actuales:")
    for c in categorias:
        col_c, col_b = st.columns([3, 1])
        col_c.write(f"• {c}")
        if col_b.button("Eliminar", key=f"d_cat_{c}"):
            categorias.remove(c)
            if guardar_en_github("categorias", ",".join(categorias)):
                st.rerun()

if st.sidebar.button("🔄 Forzar Recarga"):
    st.cache_data.clear()
    st.rerun()
