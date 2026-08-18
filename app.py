from datetime import datetime, timedelta
import io
import json
import re
from docx import Document
from openai import OpenAI
from supabase import create_client
import streamlit as st

# ... (Configuración de clientes igual que antes) ...
groq_key = st.secrets["GROQ_API_KEY"]
supabase_url = st.secrets["SUPABASE_URL"]
supabase_key = st.secrets["SUPABASE_KEY"]
client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)
supabase = create_client(supabase_url, supabase_key)

# Funciones de ayuda
def obtener_modelo_chat_activo():
    return "llama-3.3-70b-versatile"

def formatear_fecha(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        dt_local = dt - timedelta(hours=6)
        return dt_local.strftime("%d/%m/%Y %H:%M hrs")
    except: return iso_str[:16]

def generar_documento_word(paciente, fecha, transcripcion):
    doc = Document()
    doc.add_heading(f"Informe Clínico — {paciente}", level=1)
    doc.add_paragraph(f"Fecha de consulta: {fecha}")
    doc.add_heading("Transcripción:", level=2)
    doc.add_paragraph(transcripcion)
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# --- VISTA SECRETARIA (Modificada para Edición y Aprendizaje) ---
# (La vista Médico se mantiene igual, solo asegúrate de integrar la lógica de glosario ahí)

# ... En tu flujo de procesamiento en la VISTA MÉDICO, antes de enviar a Llama:
# 1. Consulta el glosario:
#    correcciones = supabase.table("glosario_medico").select("*").eq("paciente", nombre_paciente).execute()
# 2. Agrega al prompt: "Ten en cuenta estas correcciones previas: {correcciones}"

# --- AHORA, LA VISTA SECRETARIA CON EDICIÓN ---
elif rol == "👩‍💼 Vista Secretaria":
    # ... (código de selección de paciente e informe igual) ...
    
    informe_actual = consultas[idx_c] # Tu variable de informe seleccionado

    st.subheader("📄 Transcripción Médica")
    
    # Formulario para edición
    with st.form("form_edicion"):
        texto_editado = st.text_area(
            "Dictado procesado (Edita aquí):",
            informe_actual["transcripcion"],
            height=250,
        )
        col_b1, col_b2 = st.columns(2)
        
        guardar = col_b1.form_submit_button("💾 Guardar Cambios en Base de Datos")
        
        # Botón de "Enseñar a la IA"
        aprender = col_b2.form_submit_button("🧠 Enseñar esta corrección a la IA")

        if guardar:
            supabase.table("informes").update({"transcripcion": texto_editado}).eq("id", informe_actual["id"]).execute()
            st.success("¡Informe actualizado!")
            st.rerun()

        if aprender:
            # Aquí lógica simple: buscar diferencias para "enseñar"
            # O simplemente abrir un modal para pedir qué término corregir
            st.info("Para enseñar a la IA, por favor indica qué término corregiste.")
            termino_viejo = st.text_input("Término que salía mal (ej: Cela):")
            termino_nuevo = st.text_input("Cómo debería escribirse (ej: Cella):")
            if st.button("Confirmar aprendizaje"):
                supabase.table("glosario_medico").insert({
                    "paciente": informe_actual["paciente"],
                    "termino_original": termino_viejo,
                    "termino_correcto": termino_nuevo
                }).execute()
                st.success("¡Anotado! La próxima vez la IA lo recordará.")

    # Descarga Word con el texto que está actualmente en la DB
    st.divider()
    word_file = generar_documento_word(informe_actual["paciente"], fecha_formateada, informe_actual["transcripcion"])
    st.download_button("📥 Descargar Informe Final (.docx)", data=word_file, ...)
