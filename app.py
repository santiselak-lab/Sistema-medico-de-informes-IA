from datetime import datetime
import io
import json
import re
from openai import OpenAI
from supabase import create_client
import streamlit as st

st.set_page_config(page_title="Sistema Médico", layout="wide")

# Lectura de credenciales
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


def formatear_fecha(iso_str):
    """Convierte fecha ISO de Supabase a formato 'DD/MM/YYYY HH:MM hrs'"""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M hrs")
    except Exception:
        return iso_str[:16]


st.sidebar.title("🏥 Menú del Sistema")
rol = st.sidebar.radio(
    "Selecciona tu Rol:", ["👨‍⚕️ Vista Médico", "👩‍💼 Vista Secretaria"]
)

# =========================================================
# VISTA MÉDICO
# =========================================================
if rol == "👨‍⚕️ Vista Médico":
    st.title("👨‍⚕️ Captura de Audio Médico")

    audio_grabado = st.audio_input("🎙️ Opción A: Grabar dictado en vivo")
    audio_subido = st.file_uploader(
        "📁 Opción B: Subir nota de voz HD (.m4a, .mp3, .wav)",
        type=["m4a", "mp3", "wav"],
    )

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
                    # 1. Preparar audio
                    status.write("⏳ Leyendo archivo de audio...")
                    audio_bytes = audio_data.getvalue()
                    buffer_audio = io.BytesIO(audio_bytes)
                    ext = (
                        audio_data.name.split(".")[-1]
                        if hasattr(audio_data, "name")
                        else "wav"
                    )
                    buffer_audio.name = f"dictado.{ext}"

                    # 2. Transcripción con Whisper Large v3
                    status.write(
                        "🎙️ Transcribiendo audio con Whisper (Modo Médico)..."
                    )
                    transcripcion = client.audio.transcriptions.create(
                        model="whisper-large-v3",
                        file=buffer_audio,
                        language="es",
                        prompt=(
                            "Dictado clínico formal. Incluye nombre del"
                            " paciente, expediente, diagnóstico, anatomía y"
                            " tratamiento."
                        ),
                    ).text

                    # 3. Extracción de Nombre de Paciente
                    status.write("🧠 Extrayendo nombre del paciente...")
                    nombre_paciente = "Paciente Desconocido"
                    try:
                        prompt_json = (
                            "Eres un asistente médico. Identifica y extrae el"
                            " NOMBRE COMPLETO del paciente mencionado en el"
                            ' dictado. Responde ÚNICAMENTE un JSON: {"paciente":'
                            ' "Nombre Apellido"}. Si no hay nombre, usa'
                            ' {"paciente": "Paciente Desconocido"}.'
                            f" Dictado: {transcripcion}"
                        )

                        res = client.chat.completions.create(
                            model="llama3-8b-8192",
                            messages=[{"role": "user", "content": prompt_json}],
                            response_format={"type": "json_object"},
                            temperature=0.1,
                        )
                        parsed = json.loads(res.choices[0].message.content)
                        nombre_paciente = parsed.get(
                            "paciente", "Paciente Desconocido"
                        ).strip()

                    except Exception:
                        pass

                    # Fallback por expresiones regulares si el JSON devolvió valor genérico
                    if (
                        nombre_paciente == "Paciente Desconocido"
                        or not nombre_paciente
                    ):
                        match = re.search(
                            r"paciente\s+([A-ZÁÉÍÓÚÑa-záléíóúñ\s]{3,30})(?:,|\s+del|\s+con|\s+de)",
                            transcripcion,
                            re.IGNORECASE,
                        )
                        if match:
                            nombre_paciente = match.group(1).strip().title()

                    # 4. Guardar archivo en Supabase Storage con Nombre de Paciente y Fecha/Hora
                    status.write("☁️ Guardando audio en la nube...")
                    nombre_limpio = re.sub(r"[^\w\s-]", "", nombre_paciente).replace(" ", "_")
                    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    file_name = f"{timestamp_str}_{nombre_limpio}.{ext}"

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

                    # 5. Insertar en Base de Datos
                    status.write("💾 Registrando informe...")
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
                        f"¡Informe registrado para **{nombre_paciente}**!"
                    )

                except Exception as e:
                    status.update(label="❌ Ocurrió un error", state="error")
                    st.error(f"Detalle técnico: {e}")

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
            # Desplegable con Paciente + Fecha y Hora exacta
            opciones = [
                f"👤 {d['paciente']} — 📅 {formatear_fecha(d['created_at'])}"
                for d in datos
            ]
            seleccion = st.selectbox("Seleccionar expediente:", opciones)
            idx = opciones.index(seleccion)
            informe = datos[idx]

            st.markdown(f"### 👤 Paciente: **{informe['paciente']}**")
            st.caption(
                f"🕒 Registrado el: {formatear_fecha(informe['created_at'])}"
            )

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
