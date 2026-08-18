from datetime import datetime, timedelta
import io
import json
import re
from docx import Document
from openai import OpenAI
from supabase import create_client
import streamlit as st

st.set_page_config(page_title="Sistema Médico", layout="wide")

# Configuración
try:
    groq_key = st.secrets["GROQ_API_KEY"]
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]
    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)
    supabase = create_client(supabase_url, supabase_key)
except Exception:
    st.error("⚠️ Error de configuración.")
    st.stop()

# Funciones auxiliares
def obtener_modelo(): return "llama-3.3-70b-versatile"

def formatear_fecha(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        dt_local = dt - timedelta(hours=6)
        return dt_local.strftime("%d/%m/%Y %H:%M hrs")
    except: return iso_str[:16]

def generar_documento_word(paciente, fecha, transcripcion):
    doc = Document()
    doc.add_heading(f"Informe Clínico — {paciente}", level=1)
    doc.add_paragraph(f"Fecha: {fecha}")
    doc.add_paragraph(transcripcion)
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# --- ESTRUCTURA PRINCIPAL ---
st.sidebar.title("🏥 Sistema Médico")
rol = st.sidebar.radio("Selecciona Rol:", ["👨‍⚕️ Vista Médico", "👩‍💼 Vista Secretaria"])

if rol == "👨‍⚕️ Vista Médico":
    st.title("👨‍⚕️ Captura de Audio")
    audio_data = st.audio_input("Grabar dictado")
    
    if audio_data and st.button("🚀 Procesar"):
        with st.spinner("Procesando..."):
            # 1. Transcripción
            transcripcion = client.audio.transcriptions.create(
                model="whisper-large-v3", file=audio_data, language="es"
            ).text
            
            # 2. Guardar (simplificado para evitar errores)
            supabase.table("informes").insert({
                "paciente": "Paciente Nuevo", 
                "transcripcion": transcripcion
            }).execute()
            st.success("Guardado.")

elif rol == "👩‍💼 Vista Secretaria":
    st.title("👩‍💼 Panel de Gestión")
    # Obtener informes
    res = supabase.table("informes").select("*").order("created_at", desc=True).execute()
    datos = res.data
    
    if datos:
        # Selección de informe
        opciones = [f"{d['paciente']} - {d['created_at']}" for d in datos]
        seleccion = st.selectbox("Seleccionar expediente", opciones)
        idx = opciones.index(seleccion)
        informe = datos[idx]
        
        # Edición
        st.subheader("📄 Transcripción Médica")
        with st.form("editor_form"):
            texto_editado = st.text_area("Dictado procesado:", informe["transcripcion"], height=200)
            guardar = st.form_submit_button("💾 Guardar cambios")
            
            if guardar:
                supabase.table("informes").update({"transcripcion": texto_editado}).eq("id", informe["id"]).execute()
                st.success("¡Guardado!")
                st.rerun()

        # Word
        docx_file = generar_documento_word(informe["paciente"], informe["created_at"], informe["transcripcion"])
        st.download_button("📥 Descargar Word", data=docx_file, file_name="informe.docx")
