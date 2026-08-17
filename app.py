import streamlit as st
import json
from datetime import datetime
from openai import OpenAI
from supabase import create_client

# Configuración de página
st.set_page_config(page_title="Sistema Médico", layout="wide")

# CARGAR CLAVES DE FORMA SEGURA DESDE STREAMLIT SECRETS
try:
    openai_key = st.secrets["OPENAI_API_KEY"]
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]
    supabase = create_client(supabase_url, supabase_key)
except Exception as e:
    st.error("⚠️ Error: Configura tus 'Secrets' en Streamlit Cloud (OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY).")
    st.stop()

st.sidebar.title("🏥 Menú del Sistema")
rol = st.sidebar.radio("Selecciona tu Rol:", ["👨‍⚕️ Vista Médico", "👩‍💼 Vista Secretaria"])

# =========================================================
# VISTA MÉDICO
# =========================================================
if rol == "👨‍⚕️ Vista Médico":
    st.title("👨‍⚕️ Captura de Audio Médico")
    audio_file = st.file_uploader("Subir dictado de audio (.mp3, .m4a, .wav)", type=["mp3", "m4a", "wav"])

    if audio_file:
        st.audio(audio_file)
        if st.button("🚀 PROCESAR Y ENVIAR", type="primary"):
            client = OpenAI(api_key=openai_key)
            with st.spinner("Procesando audio y enviando a la nube..."):
                try:
                    # 1. Transcripción con Whisper
                    audio_bytes = audio_file.read()
                    transcripcion = client.audio.transcriptions.create(
                        model="whisper-1", 
                        file=(audio_file.name, audio_bytes),
                        language="es"
                    ).text

                    # 2. Extracción de nombre de paciente con GPT-4o-mini
                    prompt = f"Extrae el nombre del paciente. Devuelve JSON: {{\"paciente\": \"Nombre Apellido\"}}. Texto: {transcripcion}"
                    res = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": prompt}],
                        response_format={"type": "json_object"}
                    )
                    nombre_paciente = json.loads(res.choices[0].message.content).get("paciente", "Paciente Desconocido")

                    # 3. Subir archivo de audio a Supabase Storage
                    file_path = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{audio_file.name}"
                    supabase.storage.from_("audios").upload(file_path, audio_bytes, {"content-type": "audio/wav"})
                    audio_url = supabase.storage.from_("audios").get_public_url(file_path)

                    # 4. Insertar registro en la base de datos
                    supabase.table("informes").insert({
                        "paciente": nombre_paciente,
                        "transcripcion": transcripcion,
                        "audio_url": audio_url
                    }).execute()

                    st.success(f"✅ ¡Informe guardado con éxito para **{nombre_paciente}**!")
                except Exception as e:
                    st.error(f"❌ Error al procesar o guardar el informe: {e}")

# =========================================================
# VISTA SECRETARIA
# =========================================================
elif rol == "👩‍💼 Vista Secretaria":
    st.title("👩‍💼 Panel de Gestión")
    
    # Manejo seguro de la consulta a la base de datos
    try:
        respuesta = supabase.table("informes").select("*").order("created_at", desc=True).execute()
        datos = respuesta.data
    except Exception as e:
        st.error(f"⚠️ Error al conectar con Supabase. Verifica que la tabla 'informes' exista y tenga RLS desactivado.")
        datos = None

    if not datos:
        st.info("No hay informes registrados aún.")
    else:
        opciones = [f"{d['paciente']} - {d['created_at'][:10]}" for d in datos]
        seleccion = st.selectbox("Seleccionar expediente:", opciones)
        idx = opciones.index(seleccion)
        informe = datos[idx]

        st.markdown(f"### 👤 Paciente: **{informe['paciente']}**")
        col1, col2 = st.columns(2)
        with col1:
            st.text_area("Transcripción del Dictado:", informe['transcripcion'], height=250)
        with col2:
            st.subheader("🔊 Audio Original")
            st.audio(informe['audio_url'])
