import time
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

PASSWORD = 'Compaq*87'
HOST = '10.43.101.200:31306'  # Este es el nombre del servicio Docker, no 'localhost' mysql

# Esperar hasta que MySQL esté disponible
def esperar_mysql():
    while True:
        try:
            engine = create_engine(f'mysql+pymysql://root:{PASSWORD}@{HOST}')
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            break
        except OperationalError:
            print("Esperando a que MySQL esté disponible...")
            time.sleep(2)

esperar_mysql()


# Crear bases si no existen
engine_server = create_engine(f'mysql+pymysql://root:{PASSWORD}@{HOST}')
with engine_server.connect() as conn:
    conn.execute(text("CREATE DATABASE IF NOT EXISTS RAW_DATA"))
    conn.execute(text("CREATE DATABASE IF NOT EXISTS CLEAN_DATA"))

# Conexiones
engine_raw_data = create_engine(f'mysql+pymysql://root:{PASSWORD}@{HOST}/RAW_DATA')
engine_clean_data = create_engine(f'mysql+pymysql://root:{PASSWORD}@{HOST}/CLEAN_DATA')

connectionsdb = [engine_raw_data, engine_clean_data]


