import streamlit as st
import pandas as pd
import re

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="ChordMaster Cloud", layout="wide", page_icon="🎸")

# --- CONEXIÓN DIRECTA A TU GOOGLE SHEET ---
# Usamos el ID de tu hoja que proporcionaste
SHEET_ID = "13AbeB4wcgNnXM5JMcuIgMS2Ql2qSAF_3-uJOg4duiKs"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

def cargar_datos():
    try:
        # Leemos los datos directamente de la URL de Google sin caché para ver cambios al instante
        return pd.read_csv(CSV_URL)
    except Exception as e:
        st.error(f"No se pudo conectar con la hoja de Google Sheets: {e}")
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
        # Detectar si es línea de acordes
        es_linea_acordes = (linea.count(" ") / len(linea)) > 0.2 if len(linea) > 6 else True
        partes = re.split(r"(\s+)", linea)
        procesada = "".join([p if p.strip() == "" else procesar_palabra(p, semitonos, es_linea_acordes) for p in partes])
        lineas.append(procesada.replace(" ", "&nbsp;"))
    return "<br>".join(lineas)

# --- INTERFAZ ---
df = cargar_datos()

st.sidebar.title("🎸 ChordMaster Cloud")
menu = st.sidebar.selectbox("Menú:", ["🏠 Cantar", "📂 Gestionar Base"])
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
    
    if not df.empty:
        # Filtrar por búsqueda
        df_v = df[df['Título'].str.contains(busqueda, case=False, na=False)] if busqueda else df
        
        if not df_v.empty:
            sel_c = st.selectbox("Selecciona una canción:", df_v['Título'])
            data = df_v[df_v['Título'] == sel_c].iloc[0]
            tp = st.number_input("Transportar Tonalidad", -6, 6, 0)
            
            st.markdown(f'''
                <div class="visor-musical">
                    <h2>{data["Título"]}</h2>
                    <p style="opacity:0.6;">{data["Autor"]} | {data.get("Categoría", "Varios")}</p>
                    <hr>
                    {procesar_texto_final(data["Letra"], tp)}
                </div>
            ''', unsafe_allow_html=True)
    else:
        st.info("No hay canciones disponibles. Verifica tu Google Sheet.")

elif menu == "📂 Gestionar Base":
    st.header("📂 Base de Datos en la Nube")
    st.write(f"Conectado a: {SHEET_ID}")
    st.dataframe(df)
    
    st.info("Para agregar o editar canciones, hazlo directamente en tu archivo de Google Sheets:")
    st.link_button("Ir a mi Google Sheets", f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")
    
    if st.button("🔄 Refrescar App"):
        st.rerun()
