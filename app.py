import os
import json
import streamlit as st
from datetime import datetime
from openai import OpenAI
from st_audiorec import st_audiorec

# ---------------------------------------------------------
# CONFIGURACIÓN INICIAL Y CARPETAS
# ---------------------------------------------------------
st.set_page_config(page_title="Sistema de Informes Médicos", layout="wide")

BASE_DIR = "datos_medicos"
AUDIOS_DIR = os.path.join(BASE_DIR, "audios")
TEXTOS_DIR = os.path.join(BASE_DIR, "textos")
IMAGENES_DIR = os.path.join(BASE_DIR, "imagenes")

for carpeta in [AUDIOS_DIR, TEXTOS_DIR, IMAGENES_DIR]:
    os.makedirs(carpeta, exist_ok=True)

# ---------------------------------------------------------
# AUTENTICACIÓN / API KEY
# ---------------------------------------------------------
api_key = st.sidebar.text_input("OpenAI API Key", type="password")

# ---------------------------------------------------------
# FUNCIONES DE IA
# ---------------------------------------------------------
def procesar_audio_medico(ruta_audio, client):
    with open(ruta_audio, "rb") as audio_file:
        transcripcion = client.audio.transcriptions.create(
            model="whisper-1", 
            file=audio_file,
            language="es"
        ).text

    prompt = f"""
    Extrae el nombre y apellido del paciente del siguiente texto médico.
    Devuelve ÚNICAMENTE un JSON con el formato: {{"paciente": "Nombre Apellido"}}
    Si no menciona nombre, devuelve {{"paciente": "Paciente_Desconocido"}}.

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
# NAVEGACIÓN Y ROLES
# ---------------------------------------------------------
st.sidebar.title("🏥 Menú del Sistema")
rol = st.sidebar.radio("Selecciona tu Rol:", ["👨‍⚕️ Vista Médico", "👩‍💼 Vista Secretaria"])

# =========================================================
# VISTA MÉDICO
# =========================================================
if rol == "👨‍⚕️ Vista Médico":
    st.title("👨‍⚕️ Captura de Audio Médico")
    st.info("Presiona el botón para grabar o adjunta un archivo existente.")

    tab1, tab2 = st.tabs(["🎙️ Grabar Audio Directo", "📁 Subir Archivo"])

    audio_bytes = None

    with tab1:
        st.subheader("Grabar Dictado")
        audio_bytes = st_audiorec()

    with tab2:
        st.subheader("Subir Archivo de Audio")
        uploaded_file = st.file_uploader("Formataos (.mp3, .m4a, .wav)", type=["mp3", "m4a", "wav"])
        if uploaded_file:
            audio_bytes = uploaded_file.read()

    st.write("---")
    
    # BOTÓN GRANDE DE PROCESAMIENTO
    if audio_bytes is not None:
        st.audio(audio_bytes, format="audio/wav")
        
        if st.button("🚀 PROCESAR Y ENVIAR INFORME", type="primary", use_container_width=True):
            if not api_key:
                st.error("⚠️ Ingresa tu OpenAI API Key en la barra lateral para procesar.")
            else:
                client = OpenAI(api_key=api_key)
                with st.spinner("Transcribiendo y extrayendo expediente del paciente..."):
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    temp_path = os.path.join(AUDIOS_DIR, f"temp_{timestamp}.wav")
                    
                    with open(temp_path, "wb") as f:
                        f.write(audio_bytes)

                    texto, nombre_paciente = procesar_audio_medico(temp_path, client)

                    nombre_base = f"{nombre_paciente}_{timestamp}"
                    ruta_audio_final = os.path.join(AUDIOS_DIR, f"{nombre_base}.wav")
                    ruta_texto_final = os.path.join(TEXTOS_DIR, f"{nombre_base}.txt")

                    os.rename(temp_path, ruta_audio_final)
                    with open(ruta_texto_final, "w", encoding="utf-8") as f:
                        f.write(texto)

                    st.success(f"✅ Informe guardado para: **{nombre_paciente.replace('_', ' ')}**")

# =========================================================
# VISTA SECRETARIA
# =========================================================
elif rol == "👩‍💼 Vista Secretaria":
    st.title("👩‍💼 Panel de Gestión de Informes")

    archivos_texto = [f for f in os.listdir(TEXTOS_DIR) if f.endswith(".txt")]

    if not archivos_texto:
        st.warning("No hay informes registrados aún.")
    else:
        st.subheader("📁 Portafolio de Pacientes")
        
        informe_sel = st.selectbox("Selecciona un informe:", archivos_texto)
        nombre_base = informe_sel.replace(".txt", "")
        paciente_nombre = nombre_base.split("_")[0] + " " + nombre_base.split("_")[1]

        st.markdown(f"### 👤 Paciente: **{paciente_nombre}**")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📝 Transcripción del Dictado")
            
            with open(os.path.join(TEXTOS_DIR, informe_sel), "r", encoding="utf-8") as f:
                contenido_texto = f.read()
            
            st.text_area("Texto transcrito:", contenido_texto, height=250)

            ruta_audio = os.path.join(AUDIOS_DIR, f"{nombre_base}.wav")
            if os.path.exists(ruta_audio):
                st.audio(ruta_audio)

        with col2:
            st.subheader("🖼️ Diagnóstico por Imágenes")
            
            imgs_subidas = st.file_uploader(
                f"Adjuntar imágenes para {paciente_nombre}", 
                type=["png", "jpg", "jpeg"], 
                accept_multiple_files=True
            )

            if imgs_subidas:
                for img in imgs_subidas:
                    ruta_img = os.path.join(IMAGENES_DIR, f"{nombre_base}_{img.name}")
                    with open(ruta_img, "wb") as f:
                        f.write(img.read())
                st.success("Imágenes guardadas correctamente.")

            st.write("**Imágenes asociadas:**")
            imgs_guardadas = [f for f in os.listdir(IMAGENES_DIR) if f.startswith(nombre_base)]
            for img_name in imgs_guardadas:
                st.image(os.path.join(IMAGENES_DIR, img_name), caption=img_name, use_column_width=True)
