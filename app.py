import streamlit as st
import pandas as pd
import requests
import base64
import re

# --- CONFIGURACIÓN DE GITHUB ---
TOKEN = st.secrets["GITHUB_TOKEN"]
REPO = st.secrets["GITHUB_REPO"]

def leer_archivo_github(path):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    headers = {"Authorization": f"token {TOKEN}"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        return requests.get(res.json()['download_url']).text
    return None

def leer_canciones_github():
    url = f"https://api.github.com/repos/{REPO}/contents/canciones"
    headers = {"Authorization": f"token {TOKEN}"}
    response = requests.get(url, headers=headers)
    canciones = []
    if response.status_code == 200:
        archivos = response.json()
        for archivo in archivos:
            if archivo['name'].endswith('.txt') and archivo['name'] != 'categorias.txt':
                res_file = requests.get(archivo['download_url'])
                content = res_file.text
                lineas = content.split('\n')
                # Parseo de metadatos (Título, Autor, Categoría)
                titulo = lineas[0].replace("Título: ", "").strip() if "Título: " in lineas[0] else archivo['name']
                autor = lineas[1].replace("Autor: ", "").strip() if len(lineas) > 1 and "Autor: " in lineas[1] else "Anónimo"
                categoria = lineas[2].replace("Categoría: ", "").strip() if len(lineas) > 2 and "Categoría: " in lineas[2] else "Varios"
                letra = "\n".join(lineas[4:]) if len(lineas) > 4 else content
                canciones.append({
                    "Título": titulo, "Autor": autor, "Categoría": categoria, 
                    "Letra": letra, "archivo": archivo['name']
                })
    return pd.DataFrame(canciones)

def guardar_en_github(nombre_archivo, contenido, es_config=False):
    path = f"canciones/{nombre_archivo}.txt" if not es_config else f"canciones/{nombre_archivo}"
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    headers = {"Authorization": f"token {TOKEN}"}
    res = requests.get(url, headers=headers)
    sha = res.json().get('sha') if res.status_code == 200 else None
    content_b64 = base64.b64encode(contenido.encode('utf-8')).decode('utf-8')
    payload = {"message": f"Update {nombre_archivo}", "content": content_b64}
    if sha: payload["sha"] = sha
    return requests.put(url, headers=headers, json=payload).status_code in [200, 201]

def eliminar_de_github(nombre_archivo):
    path = f"canciones/{nombre_archivo}"
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    headers = {"Authorization": f"token {TOKEN}"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        sha = res.json().get('sha')
        payload = {"message": f"Delete {nombre_archivo}", "sha": sha}
        return requests.delete(url, headers=headers, json=payload).status_code == 200
    return False

# --- PROCESAMIENTO MUSICAL ---
NOTAS_LAT = ["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"]
NOTAS_AMER = ["C", "C#", "D", "D#", "E
