import streamlit as st
import json
from datetime import datetime
from openai import OpenAI
from supabase import create_client

st.set_page_config(page_title="Sistema Médico Nube", layout="wide")

# ---------------------------------------------------------
# CREDENCIALES EN BARRA LATERAL
# ---------------------------------------------------------
st.sidebar.title("🔑 Configuración")
openai_key = st.sidebar.text_input("OpenAI API Key", type="password")
supabase_url = st.sidebar.text_input("Supabase URL")
supabase_key = st.sidebar.text_input("Supabase Anon Key", type="password")

# Inicializar Supabase si hay credenciales
supabase = None
if supabase_url and supabase_key:
    supabase = create_client(supabase_url, supabase_key)

st.sidebar.title("🏥 Menú del Sistema")
rol = st.sidebar.radio("Selecciona tu Rol:", ["👨‍⚕️ Vista Médico", "👩‍💼 Vista Secretaria"])

# =========================================================
# VISTA MÉDICO
# =========================================================
if rol == "👨‍⚕️ Vista Médico":
    st.title("👨‍⚕️ Captura de Audio Médico")
    
    audio_file = st.file_uploader("Grabar o subir dictado (.mp3, .m4a, .wav)", type=["mp3", "m4a", "wav"])

    if audio_file:
        st.audio(audio_file)
        if st.button("🚀 ENVIAR A SECRETARÍA", type="primary"):
            if not (openai_key and supabase):
                st.error("⚠️ Falta ingresar las claves en la barra lateral.")
            else:
                client = OpenAI(api_key=openai_key)
                with st.spinner("Procesando y subiendo a la nube..."):
                    # 1. Transcribir
                    audio_bytes = audio_file.read()
                    transcripcion = client.audio.transcriptions.create(
                        model="whisper-1", 
                        file=(audio_file.name, audio_bytes),
                        language="es"
                    ).text

                    # 2. Extraer nombre
                    prompt = f"Extrae el nombre del paciente. Devuelve JSON: {{\"paciente\": \"Nombre Apellido\"}}. Texto: {transcripcion}"
                    res = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": prompt}],
                        response_format={"type": "json_object"}
                    )
                    nombre_paciente = json.loads(res.choices[0].message.content).get("paciente", "Paciente Desconocido")

                    # 3. Subir Audio a Supabase Storage
                    file_path = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{audio_file.name}"
                    supabase.storage.from_("audios").upload(file_path, audio_bytes, {"content-type": "audio/wav"})
                    audio_url = supabase.storage.from_("audios").get_public_url(file_path)

                    # 4. Guardar registro en Base de Datos
                    supabase.table("informes").insert({
                        "paciente": nombre_paciente,
                        "transcripcion": transcripcion,
                        "audio_url": audio_url
                    }).execute()

                    st.success(f"✅ ¡Informe guardado en la nube para {nombre_paciente}!")

# =========================================================
# VISTA SECRETARIA
# =========================================================
elif rol == "👩‍💼 Vista Secretaria":
    st.title("👩‍💼 Panel de Gestión")

    if not supabase:
        st.warning("Ingresa las credenciales de Supabase en el menú lateral.")
    else:
        # Consultar base de datos
        datos = supabase.table("informes").select("*").order("created_at", desc=True).execute().data

        if not datos:
            st.info("No hay informes guardados aún.")
        else:
            opciones = [f"{d['id']} - {d['paciente']} ({d['created_at'][:10]})" for d in datos]
            seleccion = st.selectbox("Selecciona un paciente:", opciones)
            
            # Buscar el registro seleccionado
            idx = opciones.index(seleccion)
            informe = datos[idx]

            st.markdown(f"### 👤 Paciente: **{informe['paciente']}**")
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("📝 Transcripción")
                st.text_area("Texto:", informe['transcripcion'], height=250)
            
            with col2:
                st.subheader("🔊 Audio Original")
                st.audio(informe['audio_url'])
