import streamlit as st
from openai import OpenAI
from supabase import create_client

st.set_page_config(page_title="Diagnóstico", layout="wide")
st.title("🧪 Diagnóstico del Sistema")

# 1. Lectura de claves
try:
    openai_key = st.secrets["OPENAI_API_KEY"]
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]
    supabase = create_client(supabase_url, supabase_key)
    st.success("✅ Secrets cargados correctamente.")
except Exception as e:
    st.error(f"❌ Error al leer Secrets: {e}")

st.divider()

# 2. Prueba de OpenAI
if st.button("1️⃣ Probar OpenAI"):
    try:
        client = OpenAI(api_key=openai_key)
        client.models.list()
        st.success("✅ OpenAI responde correctamente.")
    except Exception as e:
        st.error(f"❌ Error en OpenAI: {e}")

# 3. Prueba de Base de Datos
if st.button("2️⃣ Probar Tabla 'informes'"):
    try:
        res = supabase.table("informes").select("*").limit(1).execute()
        st.success("✅ Tabla 'informes' conectada correctamente.")
    except Exception as e:
        st.error(f"❌ Error en Tabla 'informes': {e}")

# 4. Prueba de Bucket Storage
if st.button("3️⃣ Probar Bucket 'audios'"):
    try:
        res = supabase.storage.from_("audios").list()
        st.success("✅ Bucket 'audios' encontrado y accesible.")
    except Exception as e:
        st.error(f"❌ Error en Bucket 'audios': {e}")
