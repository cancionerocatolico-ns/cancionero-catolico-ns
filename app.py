import streamlit as st
import pandas as pd
import requests
import base64
import re
import time
import io

# --- OPTIMIZACIÓN CRON-JOB ---
if "user_agent" in st.context.headers:
    if "cron-job.org" in st.context.headers["user_agent"]:
        st.write("Ping recibido.")
        st.stop()

# --- CONFIGURACIÓN DE GITHUB ---
TOKEN = st.secrets["GITHUB_TOKEN"]
REPO = st.secrets["GITHUB_REPO"]

# --- FUNCIONES CORE ---

def leer_archivo_github(path):
    """Lee archivos de texto con cache-breaker."""
    url = f"https://api.github.com/repos/{REPO}/contents/{path}?t={int(time.time())}"
    headers = {"Authorization": f"token {TOKEN}", "Cache-Control": "no-cache"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        download_url = res.json()['download_url'] + f"&nocache={int(time.time())}"
        return requests.get(download_url).text
    return None

def cargar_categorias_csv():
    """Lee las categorías desde un archivo CSV de forma robusta."""
    url = f"https://api.github.com/repos/{REPO}/contents/canciones/categorias.csv?t={int(time.time())}"
    headers = {"Authorization": f"token {TOKEN}"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        csv_url = res.json()['download_url'] + f"&nocache={int(time.time())}"
        try:
            content = requests.get(csv_url).text
            df_cat = pd.read_csv(io.StringIO(content))
            return sorted(df_cat['nombre'].unique().tolist())
        except Exception as e:
            return ["Error en CSV", "Revisar GitHub"]
    return ["Entrada", "Piedad", "Gloria", "Ofertorio", "Comunión", "Salida"]

def guardar_categorias_csv(lista_cats):
    """Guarda la lista de categorías en formato CSV en GitHub."""
    df_new = pd.DataFrame({"nombre": lista_cats})
    csv_content = df_new.to_csv(index=False)
    
    path = "canciones/categorias.csv"
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    headers = {"Authorization": f"token {TOKEN}"}
    
    res = requests.get(url, headers=headers)
    sha = res.json().get('sha') if res.status_code == 200 else None
    
    content_b64 = base64.b64encode(csv_content.encode('utf-8')).decode('utf-8')
    payload = {"message": "Update categorias CSV", "content": content_b64}
    if sha: payload["sha"] = sha
    
    result = requests.put(url, headers=headers, json=payload)
    if result.status_code in [200, 201]:
        st.cache_data.clear()
        time.sleep(1) # Pausa técnica para propagación
        return True
    return False

def leer_canciones_github():
    """Lee todas las canciones en la carpeta /canciones/."""
    url = f"https://api.github.com/repos/{REPO}/contents/canciones?t={int(time.time())}"
    headers = {"Authorization": f"token {TOKEN}"}
    response = requests.get(url, headers=headers)
    canciones = []
    if response.status_code == 200:
        archivos = response.json()
        for archivo in archivos:
            if archivo['name'].endswith('.txt') and archivo['name'] != 'categorias.txt':
                res_file = requests.get(archivo['download_url'] + f"?t={int(time.time())}")
                content = res_file.text
                lineas = content.split('\n')
                # Metadatos
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

def guardar_cancion(nombre_f, contenido):
    if not nombre_f.endswith(".txt"): nombre_f += ".txt"
    path = f"canciones/{nombre_f}"
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    headers = {"Authorization": f"token {TOKEN}"}
    res = requests.get(url, headers=headers)
    sha = res.json().get('sha') if res.status_code == 200 else None
    content_b64 = base64.b64encode(contenido.encode('utf-8')).decode('utf-8')
    payload = {"message": f"Update {nombre_f}", "content": content_b64}
    if sha: payload["sha"] = sha
    if requests.put(url, headers=headers, json=payload).status_code in [200, 201]:
        st.cache_data.clear()
        time.sleep(1)
        return True
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
        es_linea_acordes = (linea.count(" ") / len(linea)) > 0.18 if len(linea) > 5 else True
        partes = re.split(r"(\s+)", linea)
        procesada = "".join([p if p.strip() == "" else procesar_palabra(p, semitonos, es_linea_acordes) for p in partes])
        lineas.append(procesada.replace(" ", "&nbsp;"))
    return "<br>".join(lineas)

# --- INTERFAZ ---

st.set_page_config(page_title="ChordMaster Pro", layout="wide")
if 'setlist' not in st.session_state: st.session_state.setlist = []

# Carga inicial de datos
categorias = cargar_categorias_csv()
df = leer_canciones_github()

st.sidebar.title("🎸 ChordMaster")
menu = st.sidebar.selectbox("Menú:", ["🏠 Cantar", "📋 Setlist", "➕ Agregar", "📂 Editar", "⚙️ Categorías"])
st.sidebar.markdown("---")
c_bg = st.sidebar.color_picker("Fondo", "#FFFFFF")
c_txt = st.sidebar.color_picker("Letra", "#000000")
c_chord = st.sidebar.color_picker("Acordes", "#D32F2F")
f_size = st.sidebar.slider("Tamaño", 12, 45, 18)

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Courier+Prime&display=swap');
    .visor-musical, textarea, .stTextArea textarea {{
        font-family: 'Courier Prime', monospace !important;
        line-height: 1.2 !important; font-size: {f_size}px !important;
    }}
    .visor-musical {{ 
        background-color: {c_bg} !important; color: {c_txt} !important; 
        border-radius: 12px; padding: 25px; border: 1px solid #ddd; 
        overflow-x: auto; white-space: pre !important;
    }}
    .visor-musical b {{ color: {c_chord} !important; font-weight: bold; }}
    </style>
    """, unsafe_allow_html=True)

# --- MÓDULOS ---

if menu == "🏠 Cantar":
    col1, col2 = st.columns([2, 1])
    busqueda = col1.text_input("🔍 Buscar...")
    filtro_cat = col2.selectbox("📂 Categoría", ["Todas"] + categorias)
    df_v = df.copy()
    if not df_v.empty:
        if busqueda: df_v = df_v[df_v['Título'].str.contains(busqueda, case=False, na=False)]
        if filtro_cat != "Todas": df_v = df_v[df_v['Categoría'] == filtro_cat]
    
    if not df_v.empty:
        sel_c = st.selectbox("Selecciona:", df_v['Título'])
        data = df_v[df_v['Título'] == sel_c].iloc[0]
        tp = st.number_input("Transportar", -6, 6, 0)
        if data["Referencia"]: st.link_button("🔗 Ver Referencia", data["Referencia"])
        st.markdown(f'''<div class="visor-musical"><h2>{data["Título"]}</h2><p>{data["Autor"]} | {data["Categoría"]}</p><hr>{procesar_texto_final(data["Letra"], tp)}</div>''', unsafe_allow_html=True)

elif menu == "➕ Agregar":
    st.header("➕ Nueva Canción")
    t_n = st.text_input("Título")
    a_n = st.text_input("Autor")
    cat_n = st.selectbox("Categoría", categorias)
    r_n = st.text_input("Referencia")
    l_n = st.text_area("Letra y Acordes", height=300)
    if st.button("💾 Guardar"):
        cont = f"Título: {t_n}\nAutor: {a_n}\nCategoría: {cat_n}\nReferencia: {r_n}\n\n{l_n}"
        if guardar_cancion(t_n.lower().replace(" ", "_"), cont): st.success("¡OK!"); st.rerun()

elif menu == "📂 Editar":
    st.header("📂 Editar")
    for i, row in df.iterrows():
        with st.expander(f"📝 {row['Título']}"):
            ut = st.text_input("Título", row['Título'], key=f"t_{i}")
            uc = st.selectbox("Categoría", categorias, index=categorias.index(row['Categoría']) if row['Categoría'] in categorias else 0, key=f"c_{i}")
            ul = st.text_area("Letra", row['Letra'], height=250, key=f"l_{i}")
            if st.button("Actualizar", key=f"b_{i}"):
                nuevo_c = f"Título: {ut}\nAutor: {row['Autor']}\nCategoría: {uc}\nReferencia: {row['Referencia']}\n\n{ul}"
                if guardar_cancion(row['archivo'], nuevo_c): st.rerun()

elif menu == "⚙️ Categorías":
    st.header("⚙️ Gestión CSV")
    nueva = st.text_input("Nueva Categoría:")
    if st.button("Añadir"):
        if nueva and nueva.strip() not in categorias:
            categorias.append(nueva.strip())
            if guardar_categorias_csv(categorias): st.rerun()
    st.markdown("---")
    for c in categorias:
        col_c, col_b = st.columns([3, 1])
        col_c.write(f"• {c}")
        if col_b.button("Eliminar", key=f"del_{c}"):
            categorias.remove(c)
            if guardar_categorias_csv(categorias): st.rerun()

if st.sidebar.button("🔄 Refrescar"):
    st.cache_data.clear(); st.rerun()
