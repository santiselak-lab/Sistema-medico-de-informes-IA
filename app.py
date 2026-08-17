from datetime import datetime
import io
import json
from openai import OpenAI
from supabase import create_client
import streamlit as st

st.set_page_config(page_title="Sistema Médico", layout="wide")

# Lectura de credenciales
try:
    groq_key = st.secrets["GROQ_API_KEY"]
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]

    # Conexión al motor gratuito de Groq usando la misma librería de OpenAI
    client = OpenAI(
        base_url="https://api.groq.com/openai/v1", api_key=groq_key
    )
    supabase = create_client(supabase_url, supabase_key)
except Exception as e:
    st.error("⚠️ Revisa las credenciales en 'Secrets' de Streamlit Cloud.")
    st.stop()

st.sidebar.title("🏥 Menú del Sistema")
rol = st.sidebar.radio(
    "Selecciona tu Rol:", ["👨‍⚕️ Vista Médico", "👩‍💼 Vista Secretaria"]
)

# =========================================================
# VISTA MÉDICO
# =========================================================
if rol == "👨‍⚕️ Vista Médico":
    st.title("👨‍⚕️ Captura de Audio Médico")
    st.write("Graba un dictado directamente o sube un archivo grabado:")

    audio_data = st.audio_input("🎙️ Toca para grabar o subir audio")

    if audio_data is not None:
        st.audio(audio_data)

        if st.button(
            "🚀 PROCESAR Y ENVIAR", type="primary", use_container_width=True
        ):
            with st.status(
                "Procesando dictado médico...", expanded=True
            ) as status:
                try:
                    # 1. Preparar buffer de audio
                    status.write("⏳ Leyendo archivo de audio...")
                    audio_bytes = audio_data.getvalue()
                    buffer_audio = io.BytesIO(audio_bytes)
                    buffer_audio.name = "dictado.m4a"

                    # 2. Transcripción con Whisper Large v3 (Gratis en Groq)
                    status.write("🎙️ Transcribiendo audio con Whisper...")
                    transcripcion = client.audio.transcriptions.create(
                        model="whisper-large-v3",
                        file=buffer_audio,
                        language="es",
                    ).text

                    # 3. Extracción de nombre de paciente con Llama 3.1 (Gratis en Groq)
                    status.write("🧠 Extrayendo nombre del paciente...")
                    prompt = f'Extrae el nombre del paciente del siguiente texto. Devuelve un JSON estricto con la clave "paciente". Texto: {transcripcion}'
                    res = client.chat.completions.create(
                        model="llama-3.1-8b-instant",
                        messages=[{"role": "user", "content": prompt}],
                        response_format={"type": "json_object"},
                    )
                    nombre_paciente = json.loads(
                        res.choices[0].message.content
                    ).get("paciente", "Paciente Desconocido")

                    # 4. Subir audio a Supabase Storage
                    status.write("☁️ Guardando audio en Supabase...")
                    file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_dictado.wav"

                    supabase.storage.from_("audios").upload(
                        file_name,
                        audio_bytes,
                        file_options={
                            "content-type": "audio/wav",
                            "upsert": "true",
                        },
                    )
                    audio_url = supabase.storage.from_(
                        "audios"
                    ).get_public_url(file_name)

                    # 5. Guardar en base de datos
                    status.write("💾 Registrando informe en la base de datos...")
                    supabase.table("informes").insert({
                        "paciente": nombre_paciente,
                        "transcripcion": transcripcion,
                        "audio_url": audio_url,
                    }).execute()

                    status.update(
                        label="✅ ¡Proceso completado con éxito!",
                        state="complete",
                        expanded=False,
                    )
                    st.success(
                        f"¡Informe guardado correctamente para **{nombre_paciente}**!"
                    )

                except Exception as e:
                    status.update(label="❌ Ocurrió un error", state="error")
                    st.error(f"Detalle técnico del fallo: {e}")

# =========================================================
# VISTA SECRETARIA
# =========================================================
elif rol == "👩‍💼 Vista Secretaria":
    st.title("👩‍💼 Panel de Gestión")
    try:
        respuesta = (
            supabase.table("informes")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        datos = respuesta.data

        if not datos:
            st.info("No hay informes registrados aún.")
        else:
            opciones = [
                f"{d['paciente']} - {d['created_at'][:10]}" for d in datos
            ]
            seleccion = st.selectbox("Seleccionar expediente:", opciones)
            idx = opciones.index(seleccion)
            informe = datos[idx]

            st.markdown(f"### 👤 Paciente: **{informe['paciente']}**")
            col1, col2 = st.columns(2)
            with col1:
                st.text_area(
                    "Transcripción del Dictado:",
                    informe["transcripcion"],
                    height=250,
                )
            with col2:
                st.subheader("🔊 Audio Original")
                st.audio(informe["audio_url"])
    except Exception as e:
        st.error(f"❌ Error al consultar la base de datos:\n\n`{e}`")
