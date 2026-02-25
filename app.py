import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import re

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="ChordMaster Cloud", layout="wide")

# Conexión con tu Google Sheet
conn = st.connection("gsheets", type=GSheetsConnection)

def cargar_datos():
    try:
        # ttl=0 obliga a la app a leer los cambios del Excel al instante
        return conn.read(ttl=0)
    except Exception as e:
        st.error(f"Error al conectar con la hoja de Google: {e}")
        return pd.DataFrame(columns=["Título", "Autor", "Categoría", "Letra"])

# --- LÓGICA DE TRANSPOSICIÓN Y ALINEACIÓN ---
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
f_size = st.sidebar.slider("Tamaño Fuente", 15, 45, 22)

# Estilo para Tablet (Fuente Courier Prime para alineación perfecta)
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Courier+Prime&display=swap');
    .visor-musical, textarea {{ font-family: 'Courier Prime', monospace !important; }}
    .visor-musical {{ 
        background-color: white; color: black; border-radius: 10px; padding: 25px;
        font-size: {f_size}px; line-height: 1.2; border: 1px solid #ddd;
    }}
    .visor-musical b {{ font-weight: 700; color: #d32f2f; }}
    </style>
    """, unsafe_allow_html=True)

if menu == "🏠 Cantar":
    busqueda = st.text_input("🔍 Buscar canción...")
    df_v = df[df['Título'].str.contains(busqueda, case=False, na=False)] if busqueda else df
    if not df_v.empty:
        sel_c = st.selectbox("Selecciona:", df_v['Título'])
        data = df_v[df_v['Título'] == sel_c].iloc[0]
        tp = st.number_input("Transportar", -6, 6, 0)
        st.markdown(f'<div class="visor-musical"><h2>{data["Título"]}</h2><hr>{procesar_texto_final(data["Letra"], tp)}</div>', unsafe_allow_html=True)

elif menu == "➕ Agregar Canción":
    st.header("➕ Agregar a la Nube")
    t_n = st.text_input("Título")
    a_n = st.text_input("Autor")
    l_n = st.text_area("Letra y Acordes", height=300)
    if st.button("💾 Guardar en Google Sheets"):
        if t_n and l_n:
            nuevo = pd.DataFrame([[t_n, a_n, "Varios", l_n]], columns=df.columns)
            df_upd = pd.concat([df, nuevo], ignore_index=True)
            conn.update(data=df_upd)
            st.success("¡Guardado en el Excel!"); st.cache_data.clear(); st.rerun()

elif menu == "📂 Gestionar Base":
    st.write("Datos actuales en Google Sheets:")
    st.dataframe(df[["Título", "Autor", "Categoría"]])
    if st.button("🔄 Refrescar"):
        st.cache_data.clear(); st.rerun()
