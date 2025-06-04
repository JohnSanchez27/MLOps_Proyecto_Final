from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import joblib
import pandas as pd
import os
import json
import datetime
from connections import connectionsdb
from sqlalchemy import text
from prometheus_fastapi_instrumentator import Instrumentator
import mlflow.pyfunc
from mlflow.tracking import MlflowClient

MLFLOW_TRACKING_URI = "http://10.43.101.200:31500"  # igual que en el script de entrenamiento
mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
MODEL_NAME = "modelo_regresion_produccion"
client = MlflowClient()

app = FastAPI()
cleandatadb_engine = connectionsdb[1]

Instrumentator().instrument(app).expose(app)

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
        # Obtener versión Production del modelo
        versions = client.get_latest_versions(MODEL_NAME, stages=["Production"])
        if not versions:
            raise HTTPException(status_code=500, detail="No se encontró modelo en Production en MLflow")

        prod_version = versions[0]  # asumimos solo una en Production
        model_uri = f"models:/{MODEL_NAME}/Production"

        # Cargar modelo desde MLflow
        model = mlflow.pyfunc.load_model(model_uri)

        # Cargar columnas de entrenamiento (puedes dejar igual o mejorar almacenándolas en MLflow)
        if not os.path.exists(COLUMNS_PATH):
            raise FileNotFoundError("Archivo columnas_entrenamiento.json no encontrado")
        with open(COLUMNS_PATH, "r") as f:
            columnas = json.load(f)

        # Preparar datos igual que antes
        df = pd.DataFrame([datos.dict()])
        df_encoded = pd.get_dummies(df, drop_first=True)
        df_encoded = df_encoded.reindex(columns=columnas, fill_value=0)

        # Predecir con el modelo cargado desde MLflow
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
