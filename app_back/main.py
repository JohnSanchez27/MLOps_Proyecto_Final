from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import joblib
import pandas as pd
import os
import json
import datetime
from connections import connectionsdb
from sqlalchemy import text

app = FastAPI()
cleandatadb_engine = connectionsdb[1]

MODEL_PATH = "models/modelo_mejor.pkl"
COLUMNS_PATH = "models/columnas_entrenamiento.json"

class HouseFeatures(BaseModel):
    state: str
    status: str
    bed: float
    bath: float
    house_size: float
    acre_lot: float
    zip_code: float

@app.get("/")
def root():
    return {"mensaje": "API de Predicción Inmobiliaria. Usa /docs para probar la inferencia."}

@app.post("/predecir")
def predecir_precio(datos: HouseFeatures):
    try:
        if not os.path.exists(MODEL_PATH) or not os.path.exists(COLUMNS_PATH):
            raise FileNotFoundError("Faltan archivos necesarios. Entrena primero el modelo.")

        model = joblib.load(MODEL_PATH)

        with open(COLUMNS_PATH, "r") as f:
            columnas = json.load(f)

        df = pd.DataFrame([datos.dict()])
        df_encoded = pd.get_dummies(df, drop_first=True)
        df_encoded = df_encoded.reindex(columns=columnas, fill_value=0)

        prediccion = model.predict(df_encoded)[0]

        crear_tabla_predicciones_si_no_existe()

        df_pred = df.copy()
        df_pred["prediccion_precio"] = prediccion
        df_pred["fecha"] = datetime.datetime.now()

        df_pred.to_sql("prediccion", con=cleandatadb_engine, if_exists="append", index=False)

        return {"prediccion_precio": round(prediccion, 2)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al hacer la predicción: {e}")

def crear_tabla_predicciones_si_no_existe():
    create_sql = """
    CREATE TABLE IF NOT EXISTS prediccion (
        id INT AUTO_INCREMENT PRIMARY KEY,
        state VARCHAR(50),
        status VARCHAR(50),
        bed FLOAT,
        bath FLOAT,
        house_size FLOAT,
        acre_lot FLOAT,
        zip_code FLOAT,
        prediccion_precio FLOAT,
        fecha DATETIME
    )
    """
    with cleandatadb_engine.connect() as conn:
        conn.execute(text(create_sql))
