import json
import io
from datetime import datetime
import streamlit as st
from openai import OpenAI
from supabase import create_client

st.set_page_config(page_title="Sistema Médico", layout="wide")

# Lectura de credenciales desde Secrets
try:
    openai_key = st.secrets["OPENAI_API_KEY"]
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]
    supabase = create_client(supabase_url, supabase_key)
except Exception as e:
    st.error("⚠️ Error en la lectura de Secrets.")
    st.stop()

st.sidebar.title("🏥 Menú del Sistema")
rol = st.sidebar.radio("Selecciona tu Rol:", ["👨‍⚕️ Vista Médico", "👩‍💼 Vista Secretaria"])

# =========================================================
# VISTA MÉDICO
# =========================================================
if rol == "👨‍⚕️ Vista Médico":
    st.title("👨‍⚕️ Captura de Audio Médico")
    st.write("Graba un dictado directamente o sube un archivo grabado:")

    # Entrada de audio nativa con soporte para grabación en vivo y carga
    audio_data = st.audio_input("🎙️ Toca para grabar o subir audio")

    if audio_data is not None:
        st.audio(audio_data)

        if st.button("🚀 PROCESAR Y ENVIAR", type="primary", use_container_width=True):
            with st.status("Procesando dictado médico...", expanded=True) as status:
                try:
                    client = OpenAI(api_key=openai_key)

                    # 1. Preparar el buffer de audio
                    status.write("⏳ Leyendo archivo de audio...")
                    audio_bytes = audio_data.getvalue()
                    buffer_audio = io.BytesIO(audio_bytes)
                    buffer_audio.name = "dictado.wav"

                    # 2. Transcripción con Whisper
                    status.write("🎙️ Transcribiendo audio con Whisper...")
                    transcripcion = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=buffer_audio,
                        language="es"
                    ).text

                    # 3. Extracción del nombre del paciente con GPT-4o-mini
                    status.write("🧠 Extrayendo nombre del paciente...")
                    prompt = f'Extrae el nombre del paciente del siguiente texto. Devuelve un JSON estricto con la clave "paciente". Texto: {transcripcion}'
                    res = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": prompt}],
                        response_format={"type": "json_object"}
                    )
                    nombre_paciente = json.loads(res.choices[0].message.content).get("paciente", "Paciente Desconocido")

                    # 4. Guardar audio en Supabase Storage
                    status.write("☁️ Guardando audio en Supabase Storage...")
                    file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_dictado.wav"

                    supabase.storage.from_("audios").upload(
                        file_name,
                        audio_bytes,
                        file_options={"content-type": "audio/wav", "upsert": "true"}
                    )
                    audio_url = supabase.storage.from_("audios").get_public_url(file_name)

                    # 5. Insertar datos en la base de datos
                    status.write("💾 Registrando informe en la base de datos...")
                    supabase.table("informes").insert({
                        "paciente": nombre_paciente,
                        "transcripcion": transcripcion,
                        "audio_url": audio_url
                    }).execute()

                    status.update(label="✅ ¡Proceso completado con éxito!", state="complete", expanded=False)
                    st.success(f"¡Informe guardado correctamente para **{nombre_paciente}**!")

                except Exception as e:
                    status.update(label="❌ Ocurrió un error", state="error")
                    st.error(f"Detalle técnico del fallo: {e}")

# =========================================================
# VISTA SECRETARIA
# =========================================================
elif rol == "👩‍💼 Vista Secretaria":
    st.title("👩‍💼 Panel de Gestión")
    try:
        respuesta = supabase.table("informes").select("*").order("created_at", desc=True).execute()
        datos = respuesta.data

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
    except Exception as e:
        st.error(f"❌ Error al consultar la base de datos:\n\n`{e}`")
