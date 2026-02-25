import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import re

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="ChordMaster Pro", layout="wide")

# Conexión con la librería oficial
# IMPORTANTE: Debes tener configurado el Secret 'connections.gsheets'
conn = st.connection("gsheets", type=GSheetsConnection)

def cargar_datos():
    return conn.read(ttl=0) # ttl=0 para leer cambios al instante

# --- LÓGICA MUSICAL ---
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
        nueva_raiz = transportar_nota(raiz, semitonos)
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

st.sidebar.title("🎸 ChordMaster Pro")
menu = st.sidebar.selectbox("Menú", ["🏠 Cantar", "📋 Mi Setlist", "➕ Agregar Canción", "📂 Gestionar Base"])
f_size = st.sidebar.slider("Tamaño Fuente", 15, 45, 22)

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Courier+Prime&display=swap');
    .visor-musical {{ font-family: 'Courier Prime', monospace !important; background: white; color: black; padding: 25px; border-radius: 12px; font-size: {f_size}px; border: 1px solid #ddd; }}
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
    st.header("➕ Nueva Canción a la Nube")
    with st.form("form_nuevo"):
        t_n = st.text_input("Título")
        a_n = st.text_input("Autor")
        cat_n = st.selectbox("Categoría", ["Entrada", "Comunión", "Salida", "Varios"])
        l_n = st.text_area("Letra y Acordes (Respeta los espacios)", height=300)
        enviar = st.form_submit_button("💾 Guardar en Google Sheets")
        
        if enviar:
            if t_n and l_n:
                # Creamos el nuevo registro
                nueva_fila = pd.DataFrame([[t_n, a_n, cat_n, l_n]], columns=df.columns)
                df_actualizado = pd.concat([df, nueva_fila], ignore_index=True)
                # GUARDAR EN LA NUBE
                conn.update(data=df_actualizado)
                st.success("¡Canción guardada exitosamente!")
                st.cache_data.clear()
            else:
                st.error("Por favor completa Título y Letra.")

elif menu == "📂 Gestionar Base":
    st.dataframe(df)
    if st.button("🔄 Refrescar"):
        st.cache_data.clear()
        st.rerun()
