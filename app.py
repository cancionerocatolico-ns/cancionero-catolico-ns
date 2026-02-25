import streamlit as st
import pandas as pd
import re
import gspread
from gspread_dataframe import set_with_dataframe

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="ChordMaster Pro", layout="wide")

# Conexión directa vía URL pública (para lectura rápida)
SHEET_ID = "13AbeB4wcgNnXM5JMcuIgMS2Ql2qSAF_3-uJOg4duiKs"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

def cargar_datos():
    try:
        # Forzamos la descarga del CSV para ver cambios inmediatos
        return pd.read_csv(f"{CSV_URL}&cb={st.session_state.get('reboot', 0)}")
    except:
        return pd.DataFrame(columns=["Título", "Autor", "Categoría", "Letra"])

# --- LÓGICA MUSICAL (Tu motor original) ---
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
if 'reboot' not in st.session_state: st.session_state.reboot = 0
df = cargar_datos()

st.sidebar.title("🎸 ChordMaster Pro")
menu = st.sidebar.selectbox("Menú", ["🏠 Cantar", "📋 Mi Setlist", "➕ Agregar Canción", "📂 Gestionar Base"])
f_size = st.sidebar.slider("Tamaño Fuente", 15, 45, 22)

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Courier+Prime&display=swap');
    .visor-musical {{ font-family: 'Courier Prime', monospace !important; background: white; color: black; padding: 25px; border-radius: 12px; font-size: {f_size}px; line-height: 1.2; border: 1px solid #ddd; }}
    .visor-musical b {{ color: #d32f2f; }}
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
    st.header("➕ Nueva Canción")
    with st.form("nuevo_tema"):
        t = st.text_input("Título")
        a = st.text_input("Autor")
        l = st.text_area("Letra y Acordes (usa espacios para alinear)", height=300)
        if st.form_submit_button("💾 Guardar en la Nube"):
            if t and l:
                st.warning("Para guardar, copia esta canción y pégala en tu Google Sheets. La escritura automática requiere una Service Account.")
                st.link_button("Ir a Google Sheets", f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")
            else:
                st.error("Faltan datos.")

elif menu == "📂 Gestionar Base":
    st.dataframe(df)
    if st.button("🔄 Sincronizar"):
        st.session_state.reboot += 1
        st.rerun()
