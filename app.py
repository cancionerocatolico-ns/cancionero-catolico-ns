import streamlit as st
import pandas as pd
import requests
import base64
import re
import time
import io

# --- CONFIGURACIÓN DE GITHUB ---
TOKEN = st.secrets["GITHUB_TOKEN"]
REPO = st.secrets["GITHUB_REPO"]

# --- FUNCIONES DE COMUNICACIÓN ---

def cargar_categorias_csv():
    path = "canciones/categorias.csv"
    t_fuerza = int(time.time())
    url = f"https://api.github.com/repos/{REPO}/contents/{path}?t={t_fuerza}"
    headers = {"Authorization": f"token {TOKEN}", "Cache-Control": "no-cache"}
    st.cache_data.clear()
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        try:
            download_url = res.json()['download_url'] + f"&nocache={t_fuerza}"
            content = requests.get(download_url).text
            df_cat = pd.read_csv(io.StringIO(content), sep=',', skip_blank_lines=True)
            if 'nombre' in df_cat.columns:
                lista = df_cat['nombre'].dropna().unique().tolist()
                return sorted([str(c).strip() for c in lista if str(c).strip() and "Error" not in str(c)])
        except: pass
    return ["Entrada", "Piedad", "Gloria", "Ofertorio", "Comunión", "Salida"]

def guardar_categorias_csv(lista_cats):
    csv_content = "nombre,\n" + "\n".join([f"{c}," for c in lista_cats])
    path = "canciones/categorias.csv"
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    headers = {"Authorization": f"token {TOKEN}"}
    res = requests.get(url, headers=headers)
    sha = res.json().get('sha') if res.status_code == 200 else None
    payload = {"message": "Update categorias CSV", "content": base64.b64encode(csv_content.encode('utf-8')).decode('utf-8')}
    if sha: payload["sha"] = sha
    if requests.put(url, headers=headers, json=payload).status_code in [200, 201]:
        st.cache_data.clear()
        time.sleep(1)
        return True
    return False

def leer_canciones_github():
    t = int(time.time())
    url = f"https://api.github.com/repos/{REPO}/contents/canciones?t={t}"
    headers = {"Authorization": f"token {TOKEN}", "Cache-Control": "no-cache"}
    res = requests.get(url, headers=headers)
    canciones = []
    if res.status_code == 200:
        for f in res.json():
            if f['name'].endswith('.txt') and not f['name'].startswith('categorias'):
                c = requests.get(f['download_url'] + f"&t={t}").text
                lineas = c.split('\n')
                titulo = lineas[0].replace("Título: ", "").strip() if "Título: " in lineas[0] else f['name']
                autor = lineas[1].replace("Autor: ", "").strip() if len(lineas) > 1 and "Autor: " in lineas[1] else "Anónimo"
                cat = lineas[2].replace("Categoría: ", "").strip() if len(lineas) > 2 and "Categoría: " in lineas[2] else "Varios"
                letra = "\n".join(lineas[5:]) if len(lineas) > 5 else c
                canciones.append({"Título": titulo, "Autor": autor, "Categoría": cat, "Letra": letra, "archivo": f['name']})
    return pd.DataFrame(canciones)

def guardar_en_github(nombre_archivo, contenido):
    if not nombre_archivo.endswith(".txt"): nombre_archivo += ".txt"
    path = f"canciones/{nombre_archivo}"
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    headers = {"Authorization": f"token {TOKEN}"}
    res = requests.get(url, headers=headers)
    sha = res.json().get('sha') if res.status_code == 200 else None
    payload = {"message": f"Update {nombre_archivo}", "content": base64.b64encode(contenido.encode('utf-8')).decode('utf-8')}
    if sha: payload["sha"] = sha
    if requests.put(url, headers=headers, json=payload).status_code in [200, 201]:
        st.cache_data.clear(); time.sleep(1); return True
    return False

# --- PROCESAMIENTO MUSICAL MEJORADO (SIN FALSOS POSITIVOS) ---

NOTAS_LAT = ["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"]
NOTAS_AMER = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def transportar_nota(nota, semitonos):
    for lista in [NOTAS_AMER, NOTAS_LAT]:
        if nota in lista:
            idx = (lista.index(nota) + semitonos) % 12
            return lista[idx]
    return nota

def procesar_palabra(palabra, semitonos, es_linea_acordes):
    # Regla: Palabras muy comunes que NO son acordes si la línea es de texto
    excepciones_texto = ["La", "Si", "Do", "A"]
    
    # Expresión regular para detectar acordes (Raiz + alteraciones)
    patron = r"^(Do#?|Re#?|Mi|Fa#?|Sol#?|La#?|Si|[A-G][#b]?)([\#bmM79dimatusj0-9]*)$"
    match = re.match(patron, palabra)
    
    if match:
        raiz, resto = match.group(1), match.group(2)
        
        # SI es una palabra conflictiva Y la línea parece texto -> NO es acorde
        if raiz in excepciones_texto and not resto and not es_linea_acordes:
            return palabra
        
        # Si es una línea de acordes o tiene extensiones (ej: La7), es un acorde
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
        
        # Un línea es de acordes si tiene muchos espacios o caracteres cortos
        # Calculamos la densidad: si hay pocos caracteres alfabéticos vs longitud total
        solo_letras = re.sub(r'[^a-zA-Z]', '', linea)
        es_linea_acordes = len(solo_letras) < (len(linea) * 0.4) or (linea.count("   ") > 0)
        
        partes = re.split(r"(\s+)", linea)
        procesada = "".join([p if p.strip() == "" else procesar_palabra(p, semitonos, es_linea_acordes) for p in partes])
        lineas.append(procesada.replace(" ", "&nbsp;"))
    return "<br>".join(lineas)

# --- INTERFAZ ---
st.set_page_config(page_title="ChordMaster Pro", layout="wide")
categorias = cargar_categorias_csv()
df = leer_canciones_github()

st.sidebar.title("🎸 ChordMaster")
menu = st.sidebar.selectbox("Menú:", ["🏠 Cantar", "➕ Agregar", "📂 Editar", "⚙️ Categorías"])
c_bg = st.sidebar.color_picker("Fondo", "#FFFFFF")
c_txt = st.sidebar.color_picker("Texto", "#000000")
c_chord = st.sidebar.color_picker("Acordes", "#D32F2F")
f_size = st.sidebar.slider("Fuente", 12, 45, 18)

st.markdown(f"""<style>
    .visor-musical {{ font-family: 'Courier Prime', monospace; font-size: {f_size}px; line-height: 1.2; 
    background-color: {c_bg}; color: {c_txt}; padding: 25px; border-radius: 12px; border: 1px solid #ddd; }}
    .visor-musical b {{ color: {c_chord}; }}
</style>""", unsafe_allow_html=True)

if menu == "🏠 Cantar":
    col1, col2 = st.columns([2, 1])
    busc = col1.text_input("🔍 Buscar...")
    filt = col2.selectbox("📂 Categoría", ["Todas"] + categorias)
    df_v = df.copy()
    if not df_v.empty:
        if busc: df_v = df_v[df_v['Título'].str.contains(busc, case=False, na=False)]
        if filt != "Todas": df_v = df_v[df_v['Categoría'] == filt]
        if not df_v.empty:
            sel = st.selectbox("Selecciona:", df_v['Título'])
            row = df_v[df_v['Título'] == sel].iloc[0]
            tp = st.number_input("Transportar", -6, 6, 0)
            st.markdown(f'<div class="visor-musical"><h2>{row["Título"]}</h2><p>{row["Autor"]} | {row["Categoría"]}</p><hr>{procesar_texto_final(row["Letra"], tp)}</div>', unsafe_allow_html=True)

elif menu == "➕ Agregar":
    st.header("➕ Nueva")
    t = st.text_input("Título"); a = st.text_input("Autor"); c = st.selectbox("Categoría", categorias)
    l = st.text_area("Letra y Acordes", height=300)
    if st.button("Guardar"):
        cont = f"Título: {t}\nAutor: {a}\nCategoría: {c}\nReferencia: \n\n{l}"
        if guardar_en_github(t.lower().replace(" ", "_"), cont): st.success("OK"); st.rerun()

elif menu == "📂 Editar":
    st.header("📂 Editar")
    for i, row in df.iterrows():
        with st.expander(f"📝 {row['Título']}"):
            ut = st.text_input("Título", row['Título'], key=f"t{i}")
            uc = st.selectbox("Categoría", categorias, index=categorias.index(row['Categoría']) if row['Categoría'] in categorias else 0, key=f"c{i}")
            ul = st.text_area("Letra", row['Letra'], height=250, key=f"l{i}")
            if st.button("Actualizar", key=f"b{i}"):
                if guardar_en_github(row['archivo'], f"Título: {ut}\nAutor: {row['Autor']}\nCategoría: {uc}\nReferencia: \n\n{ul}"): st.rerun()

elif menu == "⚙️ Categorías":
    st.header("⚙️ Categorías (CSV)")
    n = st.text_input("Nueva:")
    if st.button("Añadir"):
        if n and n not in categorias:
            categorias.append(n); guardar_categorias_csv(categorias); st.rerun()
    for c in categorias:
        col1, col2 = st.columns([4, 1])
        col1.write(f"• {c}")
        if col2.button("X", key=f"d{c}"):
            categorias.remove(c); guardar_categorias_csv(categorias); st.rerun()

if st.sidebar.button("🔄 Refrescar"):
    st.cache_data.clear(); st.rerun()
