import streamlit as st
import pandas as pd
import os
import re

# --- CONFIGURACIÓN DE ARCHIVOS ---
DB_FILE = "cancionero.csv"
CAT_FILE = "categorias.csv"
SETLIST_FILE = "setlist_fijo.csv"

# --- FUNCIONES DE DATOS ---
def cargar_datos():
    if os.path.exists(DB_FILE):
        try: return pd.read_csv(DB_FILE)
        except: pass
    return pd.DataFrame(columns=["Título", "Autor", "Categoría", "Letra"])

def cargar_categorias():
    cat_base = ["Entrada", "Piedad", "Gloria", "Aleluya", "Ofertorio", "Santo", "Cordero", "Comunión", "Salida", "Adoración", "María"]
    if os.path.exists(CAT_FILE):
        try:
            df_cat = pd.read_csv(CAT_FILE)
            return df_cat.iloc[:, 0].dropna().unique().tolist()
        except: pass
    return cat_base

def cargar_setlist():
    if os.path.exists(SETLIST_FILE):
        try: return pd.read_csv(SETLIST_FILE)["Título"].tolist()
        except: pass
    return []

def guardar_datos(df): df.to_csv(DB_FILE, index=False)
def guardar_categorias(lista_cat): pd.DataFrame(lista_cat, columns=["Nombre"]).to_csv(CAT_FILE, index=False)
def guardar_setlist(lista_sl): pd.DataFrame(lista_sl, columns=["Título"]).to_csv(SETLIST_FILE, index=False)

# --- LÓGICA DE PROCESAMIENTO MUSICAL ---
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
        # Detectar si es línea de acordes por densidad de espacios
        es_linea_acordes = (linea.count(" ") / len(linea)) > 0.2 if len(linea) > 6 else True
        partes = re.split(r"(\s+)", linea)
        procesada = "".join([p if p.strip() == "" else procesar_palabra(p, semitonos, es_linea_acordes) for p in partes])
        lineas.append(procesada.replace(" ", "&nbsp;"))
    return "<br>".join(lineas)

# --- INTERFAZ ---
st.set_page_config(page_title="ChordMaster Pro", layout="wide")
if 'setlist' not in st.session_state: st.session_state.setlist = cargar_setlist()

df = cargar_datos()
categorias = cargar_categorias()

# Sidebar
st.sidebar.title("🎸 ChordMaster")
menu = st.sidebar.selectbox("Menú:", ["🏠 Cantar / Vivo", "📋 Mi Setlist", "➕ Agregar Canción", "📂 Gestionar / Editar", "⚙️ Categorías"])
st.sidebar.markdown("---")
c_bg = st.sidebar.color_picker("Fondo Visor", "#FFFFFF")
c_txt = st.sidebar.color_picker("Color Letra", "#000000")
f_size = st.sidebar.slider("Tamaño Fuente", 12, 45, 18)

# Botón de Respaldo en la Sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("💾 Seguridad")
csv_data = df.to_csv(index=False).encode('utf-8')
st.sidebar.download_button(
    label="Descargar Cancionero (CSV)",
    data=csv_data,
    file_name='cancionero_backup.csv',
    mime='text/csv',
    use_container_width=True
)

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
    .stTextArea textarea {{ font-size: {f_size}px !important; line-height: 1.2 !important; }}
    .visor-musical b {{ font-weight: 700 !important; color: inherit; }}
    </style>
    """, unsafe_allow_html=True)

# --- MÓDULOS ---

if menu == "🏠 Cantar / Vivo":
    col1, col2 = st.columns([2, 1])
    busqueda = col1.text_input("🔍 Buscar por título o letra...")
    filtro_cat = col2.selectbox("📂 Filtrar Categoría", ["Todas"] + categorias)
    
    df_v = df.copy()
    if busqueda: df_v = df_v[df_v['Título'].str.contains(busqueda, case=False, na=False) | df_v['Letra'].str.contains(busqueda, case=False, na=False)]
    if filtro_cat != "Todas": df_v = df_v[df_v['Categoría'] == filtro_cat]

    if not df_v.empty:
        sel_c = st.selectbox("Selecciona una canción:", df_v['Título'])
        data = df_v[df_v['Título'] == sel_c].iloc[0]
        
        c_at, c_tp = st.columns([1, 1])
        if c_at.button("➕ Añadir al Setlist", use_container_width=True):
            if sel_c not in st.session_state.setlist:
                st.session_state.setlist.append(sel_c)
                guardar_setlist(st.session_state.setlist); st.toast("Añadida al setlist")
        
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
        st.info("El setlist está vacío. Ve a 'Cantar / Vivo' para añadir canciones.")
    else:
        for i, t in enumerate(st.session_state.setlist):
            with st.expander(f"🎵 {i+1}. {t}"):
                cancion = df[df['Título'] == t]
                if not cancion.empty:
                    data = cancion.iloc[0]
                    c_del, c_tp_s = st.columns([1, 2])
                    if c_del.button("🗑️ Quitar", key=f"del_{i}", use_container_width=True):
                        st.session_state.setlist.pop(i); guardar_setlist(st.session_state.setlist); st.rerun()
                    tp_s = c_tp_s.number_input("Transportar", -6, 6, 0, key=f"tp_{i}")
                    st.markdown(f'<div class="visor-musical">{procesar_texto_final(data["Letra"], tp_s)}</div>', unsafe_allow_html=True)

elif menu == "➕ Agregar Canción":
    st.header("➕ Nueva Canción")
    c1, c2 = st.columns(2)
    t_n = c1.text_input("Título de la canción")
    a_n = c2.text_input("Autor / Artista")
    cat_n = st.selectbox("Categoría", categorias)
    l_n = st.text_area("Letra y Acordes (usa espacios para alinear):", height=300)
    
    if l_n:
        st.subheader("👀 Vista Previa")
        st.markdown(f'<div class="visor-musical">{procesar_texto_final(l_n, 0)}</div>', unsafe_allow_html=True)
    
    if st.button("💾 Guardar en el Cancionero"):
        if t_n and l_n:
            nueva = pd.DataFrame([[t_n, a_n if a_n else "Anónimo", cat_n, l_n]], columns=df.columns)
            df = pd.concat([df, nueva], ignore_index=True); guardar_datos(df); st.success("¡Canción guardada correctamente!"); st.rerun()

elif menu == "📂 Gestionar / Editar":
    st.header("📂 Administrar Biblioteca")
    for i, row in df.iterrows():
        with st.expander(f"📝 Editar: {row['Título']}"):
            ut = st.text_input("Título", row['Título'], key=f"edit_t_{i}")
            ua = st.text_input("Autor", row['Autor'], key=f"edit_a_{i}")
            uc = st.selectbox("Categoría", categorias, index=categorias.index(row['Categoría']) if row['Categoría'] in categorias else 0, key=f"edit_c_{i}")
            ul = st.text_area("Letra", row['Letra'], height=250, key=f"edit_l_{i}")
            
            c_upd, c_del_db = st.columns(2)
            if c_upd.button("Actualizar Cambios", key=f"btn_u_{i}"):
                df.at[i, 'Título'], df.at[i, 'Autor'], df.at[i, 'Categoría'], df.at[i, 'Letra'] = ut, ua, uc, ul
                guardar_datos(df); st.rerun()
            if c_del_db.button("⚠️ Eliminar Permanente", key=f"btn_d_{i}"):
                df = df.drop(i).reset_index(drop=True); guardar_datos(df); st.rerun()

elif menu == "⚙️ Categorías":
    st.header("⚙️ Gestión de Categorías")
    for c in categorias:
        col_c, col_b = st.columns([3, 1])
        col_c.write(f"• **{c}**")
        if col_b.button("Eliminar", key=f"cat_del_{c}"):
            categorias.remove(c); guardar_categorias(categorias); st.rerun()
    
    n_cat = st.text_input("Nombre de la nueva categoría:")
    if st.button("Añadir Categoría"):
        if n_cat and n_cat not in categorias:
            categorias.append(n_cat); guardar_categorias(categorias); st.rerun()
