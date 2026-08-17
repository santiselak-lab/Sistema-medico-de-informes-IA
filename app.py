from datetime import datetime
import io
import json
from openai import OpenAI
from supabase import create_client
import streamlit as st

st.set_page_config(page_title="Sistema Médico", layout="wide")

# Lectura de credenciales desde Secrets
try:
    groq_key = st.secrets["GROQ_API_KEY"]
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]

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

    # Opción 1: Grabar con micrófono del navegador
    audio_grabado = st.audio_input("🎙️ Opción A: Grabar dictado en vivo")

    # Opción 2: Subir archivo HD grabado previamente en el celular
    audio_subido = st.file_uploader(
        "📁 Opción B: Subir nota de voz HD (.m4a, .mp3, .wav)",
        type=["m4a", "mp3", "wav"],
    )

    # Determinar cuál audio utilizar
    audio_data = audio_grabado if audio_grabado is not None else audio_subido

    if audio_data is not None:
        st.audio(audio_data)

        if st.button(
            "🚀 PROCESAR Y ENVIAR", type="primary", use_container_width=True
        ):
            with st.status(
                "Procesando dictado médico...", expanded=True
            ) as status:
                try:
                    # 1. Lectura del buffer de audio
                    status.write("⏳ Leyendo archivo de audio...")
                    audio_bytes = audio_data.getvalue()
                    buffer_audio = io.BytesIO(audio_bytes)
                    ext = (
                        audio_data.name.split(".")[-1]
                        if hasattr(audio_data, "name")
                        else "wav"
                    )
                    buffer_audio.name = f"dictado.{ext}"

                    # 2. Transcripción con Prompt Clínico de Alta Precisión
                    status.write(
                        "🎙️ Transcribiendo audio con Whisper (Modo Médico)..."
                    )
                    transcripcion = client.audio.transcriptions.create(
                        model="whisper-large-v3",
                        file=buffer_audio,
                        language="es",
                        prompt=(
                            "Dictado médico clínico formal. Contiene nombres de"
                            " pacientes, términos anatómicos, síntomas,"
                            " diagnóstico, fosa ilíaca, exploración física,"
                            " medicamentos y posología."
                        ),
                    ).text

                    # 3. Extracción de Nombre del Paciente con Llama 3
                    status.write("🧠 Extrayendo datos del paciente...")
                    nombre_paciente = "Paciente Desconocido"
                    try:
                        prompt_json = (
                            "Extrae únicamente el nombre completo del paciente"
                            " del siguiente dictado médico. Devuelve formato"
                            " JSON estricto: {\"paciente\": \"Nombre"
                            ' Apellido"}. Si no se menciona ningún nombre,'
                            ' devuelve {"paciente": "Paciente Desconocido"}.'
                            f" Texto: {transcripcion}"
                        )
                        res = client.chat.completions.create(
                            model="llama3-8b-8192",
                            messages=[{"role": "user", "content": prompt_json}],
                            response_format={"type": "json_object"},
                        )
                        nombre_paciente = json.loads(
                            res.choices[0].message.content
                        ).get("paciente", "Paciente Desconocido")
                    except Exception:
                        nombre_paciente = "Paciente (Revisar dictado)"

                    # 4. Guardar archivo en Supabase Storage
                    status.write("☁️ Guardando audio en la nube...")
                    file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_dictado.{ext}"
                    supabase.storage.from_("audios").upload(
                        file_name,
                        audio_bytes,
                        file_options={
                            "content-type": f"audio/{ext}",
                            "upsert": "true",
                        },
                    )
                    audio_url = supabase.storage.from_(
                        "audios"
                    ).get_public_url(file_name)

                    # 5. Insertar informe en la Base de Datos
                    status.write("💾 Guardando informe...")
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
