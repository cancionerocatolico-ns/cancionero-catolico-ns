import streamlit as st
import pandas as pd
import re
import requests

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="ChordMaster Cloud", layout="wide", page_icon="🎸")

# --- CONEXIÓN DIRECTA A GOOGLE SHEETS ---
SHEET_ID = "13AbeB4wcgNnXM5JMcuIgMS2Ql2qSAF_3-uJOg4duiKs"
# URL para leer
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
# URL para escribir (vía Formulario/Script o edición directa)
EDIT_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"

def cargar_datos():
    try:
        # Leemos los datos directamente de la URL de Google
        # Agregamos un parámetro aleatorio para evitar que el navegador guarde una versión vieja (caché)
        return pd.read_csv(f"{CSV_URL}&cachebuster={st.sidebar.get('cb', 0)}")
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return pd.DataFrame(columns=["Título", "Autor", "Categoría", "Letra"])

# --- LÓGICA MUSICAL (Alineación Espejo) ---
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
menu = st.sidebar.selectbox("Menú Principal:", ["🏠 Cantar", "📋 Mi Setlist", "➕ Agregar Canción", "📂 Gestionar Base"])
f_size = st.sidebar.slider("Tamaño de Fuente", 15, 45, 22)

# Estilos CSS
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
    busqueda = st.text_input("🔍 Buscar canción...")
    if not df.empty:
        df_v = df[df['Título'].str.contains(busqueda, case=False, na=False)] if busqueda else df
        if not df_v.empty:
            sel_c = st.selectbox("Selecciona una canción:", df_v['Título'])
            data = df_v[df_v['Título'] == sel_c].iloc[0]
            tp = st.number_input("Transportar Tonalidad", -6, 6, 0)
            
            # Botón para añadir al Setlist (temporal)
            if st.button("➕ Añadir a mi Setlist"):
                if 'setlist' not in st.session_state: st.session_state.setlist = []
                if sel_c not in st.session_state.setlist:
                    st.session_state.setlist.append(sel_c)
                    st.success("Añadida!")

            st.markdown(f'''
                <div class="visor-musical">
                    <h2>{data["Título"]}</h2>
                    <p style="opacity:0.6;">{data["Autor"]} | {data.get("Categoría", "Varios")}</p>
                    <hr>
                    {procesar_texto_final(data["Letra"], tp)}
                </div>
            ''', unsafe_allow_html=True)

elif menu == "📋 Mi Setlist":
    st.header("📋 Setlist del Día")
    if 'setlist' in st.session_state and st.session_state.setlist:
        for cancion_nombre in st.session_state.setlist:
            with st.expander(f"📖 {cancion_nombre}"):
                data_s = df[df['Título'] == cancion_nombre].iloc[0]
                st.markdown(f'<div class="visor-musical">{procesar_texto_final(data_s["Letra"], 0)}</div>', unsafe_allow_html=True)
        if st.button("🗑️ Borrar Setlist"):
            st.session_state.setlist = []
            st.rerun()
    else:
        st.info("Tu setlist está vacío. Ve a 'Cantar' y añade algunas canciones.")

elif menu == "➕ Agregar Canción":
    st.header("➕ Agregar a la Nube")
    st.warning("Debido a restricciones de seguridad de Google, para guardar canciones nuevas debes hacerlo directamente en la hoja de cálculo.")
    st.link_button("🚀 Abrir Google Sheets para Escribir", EDIT_URL)
    st.info("Una vez que escribas la canción en la hoja, vuelve aquí y selecciona 'Gestionar Base' -> 'Refrescar'.")

elif menu == "📂 Gestionar Base":
    st.header("📂 Gestión de Datos")
    st.write(f"Total de canciones: {len(df)}")
    st.dataframe(df)
    if st.button("🔄 Refrescar y Sincronizar"):
        st.session_state.cb = st.session_state.get('cb', 0) + 1
        st.rerun()
