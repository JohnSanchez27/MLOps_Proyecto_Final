import requests
import pandas as pd
import datetime
import os
import joblib
import json
import os
import sys
import mlflow
import mlflow.sklearn

from sqlalchemy import text
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from connections import connectionsdb
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta


sys.path.append(os.path.dirname(__file__))

# Configuración
GROUP_NUMBER = 7
DAY = "Wednesday"
TIMEOUT = 20

# Conexiones
rawdatadb_engine = connectionsdb[0]
cleandatadb_engine = connectionsdb[1]

os.environ['MLFLOW_S3_ENDPOINT_URL'] = 'http://minio:9000'
os.environ['AWS_ACCESS_KEY_ID'] = 'admin'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'supersecret'

mlflow.set_tracking_uri("http://mlflow_server:5000")
mlflow.set_experiment("Default")

# ----- FASE 1: EXTRACCIÓN -----

def crear_tabla_crudos_si_no_existe():
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS datos_crudos (
        id INT AUTO_INCREMENT PRIMARY KEY,
        bed FLOAT, bath FLOAT, city VARCHAR(100), price FLOAT,
        state VARCHAR(50), zip_code VARCHAR(10), house_size FLOAT,
        street VARCHAR(150), brokered_by VARCHAR(100), status VARCHAR(50),
        acre_lot FLOAT, prev_sold_date DATE,
        group_number INT, day VARCHAR(20),
        fetch_date DATETIME, batch_number INT
    )
    """
    with rawdatadb_engine.connect() as conn:
        conn.execute(text(create_table_sql))
        print("Tabla 'datos_crudos' verificada o creada.")

def reiniciar_generacion_datos(group_number, day):
    base_url = "http://10.43.101.108:80"
    params = {"group_number": group_number, "day": day}
    try:
        r = requests.get(f"{base_url}/restart_data_generation", params=params, timeout=TIMEOUT)
        r.raise_for_status()
        print("Generación de datos reiniciada.")
    except Exception as e:
        print(f"Error al reiniciar datos: {e}")

def obtener_ultimo_batch():
    query = "SELECT MAX(batch_number) FROM datos_crudos"
    result = pd.read_sql(query, con=rawdatadb_engine).iloc[0, 0]
    return int(result) if result is not None else -1

def hay_datos_en_raw():
    query = "SELECT COUNT(*) FROM datos_crudos"
    result = pd.read_sql(query, con=rawdatadb_engine).iloc[0, 0]
    return result > 0

def fetch_and_store_batch(group_number, day, batch_number):
    base_url = "http://10.43.101.108:80"
    params = {"group_number": group_number, "day": day}
    try:
        response = requests.get(f"{base_url}/data", params=params, timeout=TIMEOUT)
        response.raise_for_status()
        raw_json = response.json()

        if not raw_json:
            print(f"Lote {batch_number} vacío. No se insertan datos.")
            return

        print(f"Lote {batch_number} recibido.")
        if isinstance(raw_json, list):
            print(raw_json[:1])
        else:
            print(raw_json)

        if isinstance(raw_json, list):
            if isinstance(raw_json[0], dict) and "data" in raw_json[0]:
                df = pd.json_normalize([item["data"] for item in raw_json])
            else:
                df = pd.DataFrame(raw_json)
        elif isinstance(raw_json, dict) and "data" in raw_json:
            df = pd.json_normalize(raw_json["data"])
        else:
            raise ValueError("Estructura inesperada")

        for col in df.columns:
            if df[col].apply(lambda x: isinstance(x, dict)).any():
                print(f"Columna '{col}' contiene dicts. Se elimina.")
                df.drop(columns=[col], inplace=True)

        df["fetch_date"] = datetime.now()
        df["group_number"] = group_number
        df["day"] = day
        df["batch_number"] = batch_number

        df.to_sql("datos_crudos", con=rawdatadb_engine, if_exists="append", index=False)
        print(f"Batch {batch_number} guardado en 'datos_crudos'.")
    except Exception as e:
        print(f"Error en batch {batch_number}: {e}")

def ejecutar_extraccion_condicional():
    crear_tabla_crudos_si_no_existe()
    ultimo_batch = obtener_ultimo_batch()
    if ultimo_batch < 0:
        print("No hay datos en RAW_DATA. Se va a consumir el primer batch.")
        reiniciar_generacion_datos(GROUP_NUMBER, DAY)
        fetch_and_store_batch(GROUP_NUMBER, DAY, batch_number=0)
    else:
        print("Ya existen datos en RAW_DATA. Se intentará consumir el siguiente batch.")
        nuevo_batch = ultimo_batch + 1
        fetch_and_store_batch(GROUP_NUMBER, DAY, batch_number=nuevo_batch)

# ----- FASE 2: PROCESAMIENTO Y DIVISIÓN -----

def limpiar_dividir_y_guardar():
    try:
        print("Leyendo desde RAW_DATA.datos_crudos...")
        df = pd.read_sql("SELECT * FROM datos_crudos", con=rawdatadb_engine)
        print(f"Total registros crudos: {len(df)}")

        if df.empty:
            print("No hay datos disponibles para limpiar y dividir. Proceso detenido.")
            return

        df.drop(columns=["street", "prev_sold_date"], inplace=True, errors="ignore")
        df = df.dropna(subset=["price", "bed", "bath", "house_size"])

        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df["bed"] = pd.to_numeric(df["bed"], errors="coerce")
        df["bath"] = pd.to_numeric(df["bath"], errors="coerce")
        df["house_size"] = pd.to_numeric(df["house_size"], errors="coerce")
        df["acre_lot"] = pd.to_numeric(df["acre_lot"], errors="coerce")
        df["zip_code"] = pd.to_numeric(df["zip_code"], errors="coerce")

        df = df[(df["price"] > 0) & (df["bed"] > 0) & (df["bath"] > 0) & (df["house_size"] > 0)]

        print(f"Total registros limpios: {len(df)}")

        if len(df) < 10:
            print("No hay suficientes datos limpios para dividir. Proceso detenido.")
            return

        train_df, temp_df = train_test_split(df, test_size=0.4, random_state=42)
        val_df, test_df = train_test_split(temp_df, test_size=0.5, random_state=42)

        print(f"Train: {len(train_df)} - Val: {len(val_df)} - Test: {len(test_df)}")

        train_df.to_sql("train_set", con=cleandatadb_engine, if_exists="replace", index=False)
        val_df.to_sql("validation_set", con=cleandatadb_engine, if_exists="replace", index=False)
        test_df.to_sql("test_set", con=cleandatadb_engine, if_exists="replace", index=False)
        print("Los conjuntos fueron guardados en CLEAN_DATA.")
    except Exception as e:
        print(f"Error durante limpieza/división/almacenamiento: {e}")

# ----- FASE 3: ENTRENAMIENTO -----

def crear_tabla_metricas_si_no_existe():
    sql = """
    CREATE TABLE IF NOT EXISTS modelo_metricas (
        id INT AUTO_INCREMENT PRIMARY KEY,
        modelo VARCHAR(255),
        mse FLOAT,
        r2 FLOAT,
        fecha_entrenamiento DATETIME,
        es_mejor BOOLEAN DEFAULT FALSE
    )
    """
    with cleandatadb_engine.connect() as conn:
        conn.execute(text(sql))

from mlflow.exceptions import MlflowException

def entrenar_y_guardar_modelo():
    try:
        mlflow.set_tracking_uri("http://mlflow_server:5000")
        mlflow.set_experiment("entrenamiento_inmobiliario")

        ultimo_batch = obtener_ultimo_batch()
        query_ultimo = f"SELECT COUNT(*) AS total FROM datos_crudos WHERE batch_number = {ultimo_batch}"
        tam_ultimo = pd.read_sql(query_ultimo, con=rawdatadb_engine)["total"].iloc[0]

        query_previos = f"SELECT COUNT(*) AS total FROM datos_crudos WHERE batch_number < {ultimo_batch}"
        tam_previos = pd.read_sql(query_previos, con=rawdatadb_engine)["total"].iloc[0]

        if tam_previos > 0 and tam_ultimo < 0.1 * tam_previos:
            print("El nuevo batch representa menos del 10% del total anterior. No se reentrena.")
            return

        train_df = pd.read_sql("SELECT * FROM train_set", con=cleandatadb_engine)
        val_df = pd.read_sql("SELECT * FROM validation_set", con=cleandatadb_engine)

        cat_cols = ["state", "status"]
        num_cols = ["bed", "bath", "house_size", "acre_lot", "zip_code"]
        target = "price"

        X_train = pd.get_dummies(train_df[cat_cols + num_cols], drop_first=True)
        y_train = train_df[target]
        X_val = pd.get_dummies(val_df[cat_cols + num_cols], drop_first=True)
        y_val = val_df[target]

        X_train, X_val = X_train.align(X_val, join='left', axis=1, fill_value=0)

        os.makedirs("models", exist_ok=True)
        with open("models/columnas_entrenamiento.json", "w") as f:
            json.dump(list(X_train.columns), f)

        with mlflow.start_run() as run:
            model = LinearRegression()
            model.fit(X_train, y_train)

            y_pred = model.predict(X_val)
            mse = mean_squared_error(y_val, y_pred)
            r2 = r2_score(y_val, y_pred)

            mlflow.log_param("modelo", "LinearRegression")
            mlflow.log_param("batch_ultimo", tam_ultimo)
            mlflow.log_param("batch_previos", tam_previos)
            mlflow.log_metric("mse", mse)
            mlflow.log_metric("r2", r2)

            mlflow.sklearn.log_model(model, "modelo_regresion")

            print(f"Modelo registrado en MLflow con mse={mse:.4f} y r2={r2:.4f}")

            # Aquí obtengo el id del run
            run_id = run.info.run_id

        crear_tabla_metricas_si_no_existe()

        best_r2 = pd.read_sql("SELECT MAX(r2) AS max_r2 FROM modelo_metricas", con=cleandatadb_engine)["max_r2"].iloc[0]
        es_mejor = best_r2 is None or r2 > best_r2

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        modelo_filename = f"modelo_linear_regression_{timestamp}.pkl"
        joblib.dump(model, os.path.join("models", modelo_filename))

        with cleandatadb_engine.connect() as conn:
            if es_mejor:
                conn.execute(text("UPDATE modelo_metricas SET es_mejor = FALSE"))

            df_metrics = pd.DataFrame([{
                "modelo": modelo_filename,
                "mse": mse,
                "r2": r2,
                "fecha_entrenamiento": datetime.now(),
                "es_mejor": es_mejor
            }])
            df_metrics.to_sql("modelo_metricas", con=conn, if_exists="append", index=False)

        if es_mejor:
            best_path = os.path.join("models", "modelo_mejor.pkl")
            joblib.dump(model, best_path)
            print("Nuevo modelo es el mejor y fue guardado como modelo_mejor.pkl")

            # -------------------- NUEVO BLOQUE PARA ETIQUETAR EN PRODUCCIÓN ---------------------

            model_name = "modelo_regresion_produccion"

            # Registrar modelo en el registro si no existe
            try:
                mlflow.register_model(f"runs:/{run_id}/modelo_regresion", model_name)
                print(f"Modelo registrado en el Model Registry bajo el nombre '{model_name}'")
            except MlflowException:
                # Ya existe, seguimos igual
                print(f"El modelo '{model_name}' ya está registrado en el Model Registry.")

            # Obtener versiones existentes del modelo
            client = mlflow.tracking.MlflowClient()
            versions = client.get_latest_versions(model_name, stages=["Production"])

            # Archivar versiones anteriores en producción
            for v in versions:
                if v.run_id != run_id:
                    client.transition_model_version_stage(
                        name=model_name,
                        version=v.version,
                        stage="Archived"
                    )
                    print(f"Modelo versión {v.version} archivado.")

            # Buscar versión actual recién registrada
            all_versions = client.get_latest_versions(model_name)
            current_version = None
            for v in all_versions:
                if v.run_id == run_id:
                    current_version = v.version
                    break

            if current_version is not None:
                client.transition_model_version_stage(
                    name=model_name,
                    version=current_version,
                    stage="Production"
                )
                print(f"Modelo versión {current_version} marcado como Production.")
            else:
                print("No se encontró la versión recién registrada para asignar etapa Production.")

        else:
            print("Modelo entrenado no supera al anterior. Se conserva el mejor previo.")

    except Exception as e:
        print(f"Error durante el entrenamiento o guardado del modelo: {e}")


default_args = {
    "owner": "John_Sanchez",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}

with DAG(
    dag_id="pipeline_entrenamiento_unificado",
    default_args=default_args,
    description="Pipeline completo: extracción → limpieza → entrenamiento",
    schedule_interval=None,
    start_date=datetime(2025, 5, 27),
    catchup=False,
    tags=["mlops"],
) as dag:

    t1 = PythonOperator(
        task_id="fase_1_extraccion",
        python_callable=ejecutar_extraccion_condicional
    )

    t2 = PythonOperator(
        task_id="fase_2_limpieza_y_division",
        python_callable=limpiar_dividir_y_guardar
    )

    t3 = PythonOperator(
        task_id="fase_3_entrenamiento_modelo",
        python_callable=entrenar_y_guardar_modelo
    )

    t1 >> t2 >> t3

