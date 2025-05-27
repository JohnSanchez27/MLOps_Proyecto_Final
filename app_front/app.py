import streamlit as st
import pandas as pd
import requests
import shap
import matplotlib.pyplot as plt
import joblib
import json
from connections import connectionsdb



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


if st.button("Ver interpretación SHAP del mejor modelo"):
    try:
        cleandatadb_engine = connectionsdb[1]
        query = "SELECT state, status, bed, bath, house_size, acre_lot, zip_code FROM train_set"
        df_train = pd.read_sql(query, con=cleandatadb_engine)

        X = pd.get_dummies(df_train, drop_first=True)

        with open("models/columnas_entrenamiento.json") as f:
            columnas = json.load(f)

        X = X.reindex(columns=columnas, fill_value=0)

        model = joblib.load("models/modelo_mejor.pkl")

        explainer = shap.Explainer(model, X)
        shap_values = explainer(X)

        st.subheader("📈 Interpretabilidad con SHAP")
        fig, ax = plt.subplots()
        shap.plots.beeswarm(shap_values, show=False)
        st.pyplot(fig)

    except Exception as e:
        st.error(f"Error generando SHAP: {e}")