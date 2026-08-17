import os
import json
import streamlit as st
from datetime import datetime
from openai import OpenAI

# ---------------------------------------------------------
# CONFIGURACIÓN INICIAL
# ---------------------------------------------------------
st.set_page_config(page_title="Sistema de Informes Médicos", layout="wide")

BASE_DIR = "datos_medicos"
AUDIOS_DIR = os.path.join(BASE_DIR, "audios")
TEXTOS_DIR = os.path.join(BASE_DIR, "textos")
IMAGENES_DIR = os.path.join(BASE_DIR, "imagenes")

for carpeta in [AUDIOS_DIR, TEXTOS_DIR, IMAGENES_DIR]:
    os.makedirs(carpeta, exist_ok=True)

api_key = st.sidebar.text_input("OpenAI API Key", type="password")

def procesar_audio_medico(ruta_audio, client):
    with open(ruta_audio, "rb") as audio_file:
        transcripcion = client.audio.transcriptions.create(
            model="whisper-1", 
            file=audio_file,
            language="es"
        ).text

    prompt = f"""
    Extrae el nombre y apellido del paciente. Devuelve JSON: {{"paciente": "Nombre Apellido"}}
    Texto: {transcripcion}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    datos = json.loads(response.choices[0].message.content)
    nombre_paciente = datos.get("paciente", "Paciente_Desconocido").replace(" ", "_")
    return transcripcion, nombre_paciente

# ---------------------------------------------------------
# INTERFAZ
# ---------------------------------------------------------
st.sidebar.title("🏥 Menú del Sistema")
rol = st.sidebar.radio("Selecciona tu Rol:", ["👨‍⚕️ Vista Médico", "👩‍💼 Vista Secretaria"])

if rol == "👨‍⚕️ Vista Médico":
    st.title("👨‍⚕️ Captura de Audio Médico")
    
    # Usamos el Uploader nativo: al tocar "Upload" en Android,
    # el sistema te permite elegir "Grabar" desde la grabadora del celular.
    audio_file = st.file_uploader("Grabar o subir dictado (.mp3, .m4a, .wav)", type=["mp3", "m4a", "wav"])

    if audio_file:
        st.audio(audio_file)
        if st.button("🚀 PROCESAR Y ENVIAR INFORME", type="primary"):
            if not api_key:
                st.error("⚠️ Ingresa API Key.")
            else:
                client = OpenAI(api_key=api_key)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                temp_path = os.path.join(AUDIOS_DIR, f"temp_{timestamp}.wav")
                
                with open(temp_path, "wb") as f:
                    f.write(audio_file.read())

                texto, nombre_paciente = procesar_audio_medico(temp_path, client)
                ruta_final = os.path.join(TEXTOS_DIR, f"{nombre_paciente}_{timestamp}.txt")
                with open(ruta_final, "w", encoding="utf-8") as f:
                    f.write(texto)
                st.success("✅ Informe enviado.")

elif rol == "👩‍💼 Vista Secretaria":
    st.title("👩‍💼 Gestión")
    archivos = [f for f in os.listdir(TEXTOS_DIR) if f.endswith(".txt")]
    if archivos:
        sel = st.selectbox("Pacientes:", archivos)
        with open(os.path.join(TEXTOS_DIR, sel), "r") as f:
            st.text_area("Transcripción:", f.read())
    else:
        st.info("Sin informes aún.")
