import streamlit as st
import pandas as pd
import re

# --- INTENTO DE IMPORTACIÓN ROBUSTO ---
try:
    from streamlit_gsheets import GSheetsConnection
except ImportError:
    try:
        from st_gsheets_connection import GSheetsConnection
    except ImportError:
        st.error("🚀 El servidor está instalando las librerías necesarias. Por favor, refresca la página en 30 segundos.")
        st.info("Si el error persiste, asegúrate de que 'st-gsheets-connection' esté en tu requirements.txt")
        st.stop()

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="ChordMaster Cloud", layout="wide", page_icon="🎸")

# Conexión con Google Sheets (Lee la URL desde Secrets)
# Asegúrate de tener en Secrets: [connections.gsheets] -> spreadsheet = "TU_URL"
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Error al establecer la conexión. Revisa tus 'Secrets' en Streamlit Cloud.")
    st.stop()

def cargar_datos():
    try:
        # ttl=0 para que no use caché y los cambios en el Excel se vean al instante
        return conn.read(ttl=0)
    except Exception as e:
        st.warning("No se pudo leer la hoja de Google Sheets. Mostrando base vacía.")
        return pd.DataFrame(columns=["Título", "Autor", "Categoría", "Letra"])

# --- LÓGICA MUSICAL (Alineación y Transporte) ---
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
        if semitonos == 0: return f"<b>{palabra}</b>"
        dic_bemoles = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}
        nota_busqueda = dic_bemoles.get(raiz, raiz)
        nueva_raiz = transportar_nota(nota_busqueda, semitonos)
        return f"<b>{nueva_raiz}{resto}</b>"
    return palabra

def procesar_texto_final(texto, semitonos):
    if not texto or pd.isna(texto): return ""
    lineas = []
    for linea in str(texto).split('\n'):
        if not linea.strip():
            lineas.append("&nbsp;")
            continue
        # Lógica para detectar si es una línea de acordes
        es_linea_acordes = (linea.count(" ") / len(linea)) > 0.2 if len(linea) > 6 else True
        partes = re.split(r"(\s+)", linea)
        procesada = "".join([p if p.strip() == "" else procesar_palabra(p, semitonos, es_linea_acordes) for p in partes])
        lineas.append(procesada.replace(" ", "&nbsp;"))
    return "<br>".join(lineas)

# --- INTERFAZ ---
df = cargar_datos()
categorias = ["Entrada", "Piedad", "Gloria", "Aleluya", "Ofertorio", "Santo", "Cordero", "Comunión", "Salida", "Adoración", "María"]

st.sidebar.title("🎸 ChordMaster Cloud")
menu = st.sidebar.selectbox("Menú:", ["🏠 Cantar", "📋 Mi Setlist", "➕ Agregar Canción", "📂 Gestionar Base"])
f_size = st.sidebar.slider("Tamaño de Fuente", 15, 45, 22)

# Estilos CSS para mantener la alineación de acordes
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Courier+Prime&display=swap');
    .visor-musical {{ 
        font-family: 'Courier Prime', monospace !important; 
        background-color: white; color: black; border-radius: 12px; padding: 30px;
        font-size: {f_size}px; line-height: 1.2; border: 1px solid #ddd;
    }}
    .visor-musical b {{ font-weight: 700; color: #d32f2f; }}
    </style>
    """, unsafe_allow_html=True)

if menu == "🏠 Cantar":
    busqueda = st.text_input("🔍 Buscar canción por título...")
    df_v = df[df['Título'].str.contains(busqueda, case=False, na=False)] if busqueda else df
    
    if not df_v.empty:
        sel_c = st.selectbox("Selecciona una canción:", df_v['Título'])
        data = df_v[df_v['Título'] == sel_c].iloc[0]
        tp = st.number_input("Transportar Tonalidad", -6, 6, 0)
        st.markdown(f'''
            <div class="visor-musical">
                <h2>{data["Título"]}</h2>
                <p style="opacity:0.6;">{data["Autor"]} | {data["Categoría"]}</p>
                <hr>
                {procesar_texto_final(data["Letra"], tp)}
            </div>
        ''', unsafe_allow_html=True)
    else:
        st.info("No se encontraron canciones con ese nombre.")

elif menu == "➕ Agregar Canción":
    st.header("➕ Nueva Canción a la Nube")
    col1, col2 = st.columns(2)
    t_n = col1.text_input("Título")
    a_n = col2.text_input("Autor")
    cat_n = st.selectbox("Categoría", categorias)
    l_n = st.text_area("Letra y Acordes (usa espacios para alinear)", height=300)
    
    if st.button("💾 Guardar en Google Sheets"):
        if t_n and l_n:
            # Crear nueva fila
            nueva_fila = pd.DataFrame([[t_n, a_n if a_n else "Anónimo", cat_n, l_n]], columns=df.columns)
            df_upd = pd.concat([df, nueva_fila], ignore_index=True)
            # Actualizar la nube
            conn.update(data=df_upd)
            st.success("¡Canción guardada permanentemente en la nube!")
            st.rerun()
        else:
            st.error("El título y la letra son obligatorios.")

elif menu == "📂 Gestionar Base":
    st.header("📂 Estado de la Base de Datos")
    st.write(f"Total de canciones: {len(df)}")
    st.dataframe(df[["Título", "Autor", "Categoría"]])
    
    if st.button("🔄 Forzar Sincronización"):
        st.cache_data.clear()
        st.rerun()

elif menu == "📋 Mi Setlist":
    st.header("📋 Setlist del Día")
    st.info("Función de setlist temporal activa. Selecciona canciones para cantar.")
    # (Aquí puedes añadir la lógica de setlist que desees)
