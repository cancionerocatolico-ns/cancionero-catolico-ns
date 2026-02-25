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

# --- FUNCIONES DE CATEGORÍAS (SISTEMA CSV) ---

def cargar_categorias_csv():
    """Carga categorías desde CSV con soporte para formato de comas de GitHub."""
    path = "canciones/categorias.csv"
    url = f"https://api.github.com/repos/{REPO}/contents/{path}?t={int(time.time())}"
    headers = {"Authorization": f"token {TOKEN}", "Cache-Control": "no-cache"}
    res = requests.get(url, headers=headers)
    
    if res.status_code == 200:
        try:
            csv_url = res.json()['download_url'] + f"&nocache={int(time.time())}"
            content = requests.get(csv_url).text
            # sep=',' asegura que lea bien las comas que pusimos para GitHub
            df_cat = pd.read_csv(io.StringIO(content), sep=',', skip_blank_lines=True)
            if 'nombre' in df_cat.columns:
                lista = df_cat['nombre'].dropna().unique().tolist()
                return sorted([str(c).strip() for c in lista if str(c).strip()])
        except:
            pass
    return ["Entrada", "Piedad", "Gloria", "Ofertorio", "Comunión", "Salida"]

def guardar_categorias_csv(lista_cats):
    """Guarda categorías en CSV con comas finales para activar el buscador de GitHub."""
    # Creamos el contenido manualmente para asegurar la coma final que GitHub ama
    csv_content = "nombre,\n" + "\n".join([f"{c}," for c in lista_cats])
    
    path = "canciones/categorias.csv"
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    headers = {"Authorization": f"token {TOKEN}"}
    
    res = requests.get(url, headers=headers)
    sha = res.json().get('sha') if res.status_code == 200 else None
    
    content_b64 = base64.b64encode(csv_content.encode('utf-8')).decode('utf-8')
    payload = {"message": "Update searchable categorias CSV", "content": content_b64}
    if sha: payload["sha"] = sha
    
    if requests.put(url, headers=headers, json=payload).status_code in [200, 201]:
        st.cache_data.clear()
        time.sleep(1)
        return True
    return False

# --- FUNCIONES DE CANCIONES ---

def leer_canciones_github():
    url = f"https://api.github.com/repos/{REPO}/contents/canciones?t={int(time.time())}"
    headers = {"Authorization": f"token {TOKEN}"}
    response = requests.get(url, headers=headers)
    canciones = []
    if response.status_code == 200:
        for archivo in response.json():
            # Evitamos leer archivos de configuración como si fueran canciones
            if archivo['name'].endswith('.txt') and not archivo['name'].startswith('categorias'):
                res_file = requests.get(archivo['download_url'] + f"?t={int(time.time())}")
                lineas = res_file.text.split('\n')
                # Parseo de metadatos
                titulo = lineas[0].replace("Título: ", "").strip() if "Título: " in lineas[0] else archivo['name']
                autor = lineas[1].replace("Autor: ", "").strip() if len(lineas) > 1 and "Autor: " in lineas[1] else "Anónimo"
                cat = lineas[2].replace("Categoría: ", "").strip() if len(lineas) > 2 and "Categoría: " in lineas[2] else "Varios"
                ref = lineas[3].replace("Referencia: ", "").strip() if len(lineas) > 3 and "Referencia: " in lineas[3] else ""
                letra = "\n".join(lineas[5:]) if len(lineas) > 5 else res_file.text
                canciones.append({
                    "Título": titulo, "Autor": autor, "Categoría": cat, 
                    "Referencia": ref, "Letra": letra, "archivo": archivo['name']
                })
    return pd.DataFrame(canciones)

def guardar_cancion(titulo, contenido):
    nombre_f = titulo.lower().replace(" ", "_") + ".txt"
    path = f"canciones/{nombre_f}"
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    headers = {"Authorization": f"token {TOKEN}"}
    res = requests.get(url, headers=headers)
    sha = res.json().get('sha') if res.status_code == 200 else None
    payload = {
        "message": f"Update {nombre_f}", 
        "content": base64.b64encode(contenido.encode('utf-8')).decode('utf-8')
    }
    if sha: payload["sha"] = sha
    if requests.put(url, headers=headers, json=payload).status_code in [200, 201]:
        st.cache_data.clear()
        time.sleep(1)
        return True
    return False

# --- PROCESAMIENTO MUSICAL ---

NOTAS = ["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si", "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def transportar_nota(nota, semitonos):
    # Lógica simplificada de transporte
    listas = [["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"],
              ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]]
    for lista in listas:
        if nota in lista:
            return lista[(lista.index(nota) + semitonos) % 12]
    return nota

def procesar_texto_final(texto, semitonos):
    if not texto: return ""
    lineas = []
    for linea in texto.split('\n'):
        if not linea.strip():
            lineas.append("&nbsp;")
            continue
        es_acordes = (linea.count(" ") / len(linea)) > 0.15 if len(linea) > 5 else True
        partes = re.split(r"(\s+)", linea)
        procesada = ""
        for p in partes:
            if re.match(r"^(Do#?|Re#?|Mi|Fa#?|Sol#?|La#?|Si|[A-G][#b]?)([\#bmM79dimatusj0-9]*)$", p):
                raiz = re.match(r"^(Do#?|Re#?|Mi|Fa#?|Sol#?|La#?|Si|[A-G][#b]?)", p).group(1)
                resto = p[len(raiz):]
                procesada += f"<b>{transportar_nota(raiz, semitonos)}{resto}</b>"
            else:
                procesada += p
        lineas.append(procesada.replace(" ", "&nbsp;"))
    return "<br>".join(lineas)

# --- INTERFAZ ---

st.set_page_config(page_title="ChordMaster Pro", layout="wide")
categorias = cargar_categorias_csv()
df = leer_canciones_github()

st.sidebar.title("🎸 ChordMaster")
menu = st.sidebar.selectbox("Ir a:", ["🏠 Cantar", "➕ Agregar", "📂 Editar", "⚙️ Categorías"])
f_size = st.sidebar.slider("Tamaño Fuente", 12, 40, 18)
c_chord = st.sidebar.color_picker("Color Acordes", "#D32F2F")

st.markdown(f"""<style>
    @import url('https://fonts.googleapis.com/css2?family=Courier+Prime&display=swap');
    .visor-musical {{ font-family: 'Courier Prime', monospace; font-size: {f_size}px; white-space: pre !important; line-height: 1.2; padding: 25px; background: #fff; color: #000; border: 1px solid #ddd; border-radius: 12px; }}
    .visor-musical b {{ color: {c_chord}; font-weight: bold; }}
</style>""", unsafe_allow_html=True)

if menu == "🏠 Cantar":
    col1, col2 = st.columns([2, 1])
    busc = col1.text_input("🔍 Buscar canción...")
    filt = col2.selectbox("📂 Categoría", ["Todas"] + categorias)
    df_v = df.copy()
    if not df_v.empty:
        if busc: df_v = df_v[df_v['Título'].str.contains(busc, case=False, na=False)]
        if filt != "Todas": df_v = df_v[df_v['Categoría'] == filt]
        if not df_v.empty:
            sel = st.selectbox("Selecciona:", df_v['Título'])
            data = df_v[df_v['Título'] == sel].iloc[0]
            tp = st.number_input("Transportar", -6, 6, 0)
            st.markdown(f'<div class="visor-musical"><h2>{data["Título"]}</h2><p>{data["Autor"]} | {data["Categoría"]}</p><hr>{procesar_texto_final(data["Letra"], tp)}</div>', unsafe_allow_html=True)

elif menu == "➕ Agregar":
    st.header("➕ Nueva Canción")
    t = st.text_input("Título")
    a = st.text_input("Autor")
    c = st.selectbox("Categoría", categorias)
    l = st.text_area("Letra y Acordes", height=300)
    if st.button("💾 Guardar"):
        if t and l:
            cont = f"Título: {t}\nAutor: {a}\nCategoría: {c}\nReferencia: \n\n{l}"
            if guardar_cancion(t, cont): st.success("Guardada!"); st.rerun()

elif menu == "📂 Editar":
    st.header("📂 Editar Biblioteca")
    if not df.empty:
        for i, row in df.iterrows():
            with st.expander(f"📝 {row['Título']}"):
                ut = st.text_input("Título", row['Título'], key=f"t{i}")
                uc = st.selectbox("Categoría", categorias, index=categorias.index(row['Categoría']) if row['Categoría'] in categorias else 0, key=f"c{i}")
                ul = st.text_area("Letra", row['Letra'], height=250, key=f"l{i}")
                if st.button("Actualizar", key=f"b{i}"):
                    nc = f"Título: {ut}\nAutor: {row['Autor']}\nCategoría: {uc}\nReferencia: {row['Referencia']}\n\n{ul}"
                    if guardar_cancion(ut, nc): st.rerun()

elif menu == "⚙️ Categorías":
    st.header("⚙️ Gestión de Categorías")
    nueva = st.text_input("Añadir nueva:")
    if st.button("Guardar"):
        if nueva and nueva.strip() not in categorias:
            categorias.append(nueva.strip())
            if guardar_categorias_csv(categorias): st.success("Categoría añadida"); st.rerun()
    st.markdown("---")
    for cat in categorias:
        c1, c2 = st.columns([3, 1])
        c1.write(f"• {cat}")
        if c2.button("Eliminar", key=f"del{cat}"):
            categorias.remove(cat)
            if guardar_categorias_csv(categorias): st.rerun()

if st.sidebar.button("🔄 Forzar Recarga"):
    st.cache_data.clear(); st.rerun()
