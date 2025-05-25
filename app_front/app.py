import streamlit as st
import pandas as pd
import requests


st.set_page_config(page_title="Predicción Inmobiliaria", layout="centered")

st.title("🏠 Predicción de Precio de Vivienda")

st.markdown("Ingrese las características de la propiedad:")

# Campos de entrada
state = st.selectbox("Estado", ["Alaska", "Massachusetts", "California", "Texas", "Florida"])
status = st.selectbox("Estado de la vivienda", ["for_sale", "ready_to_build"])
bed = st.number_input("N° de habitaciones (bed)", min_value=0, step=1)
bath = st.number_input("N° de baños (bath)", min_value=0, step=1)
house_size = st.number_input("Tamaño de la casa (sqft)", min_value=0)
acre_lot = st.number_input("Tamaño del terreno (acres)", min_value=0.0, format="%.2f")
zip_code = st.number_input("Código postal", min_value=0, step=1)

input_data = {
    "state": state,
    "status": status,
    "bed": bed,
    "bath": bath,
    "house_size": house_size,
    "acre_lot": acre_lot,
    "zip_code": zip_code
}

if st.button("Predecir Precio"):
    try:
        response = requests.post("http://fastapi:8000/predecir", json=input_data)
        if response.status_code == 200:
            resultado = response.json()
            precio = resultado["prediccion_precio"]
            st.success(f"Precio estimado: ${precio:,.2f}")
        else:
            st.error(f"Error en la predicción: {response.text}")
    except Exception as e:
        st.error(f"No se pudo conectar con el servicio: {e}")
