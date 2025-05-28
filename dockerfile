# Imagen base de Airflow
FROM apache/airflow:2.6.0-python3.9

# Copiar archivo de dependencias
COPY requirements.txt /requirements.txt

# Instalar paquetes como el usuario airflow en su entorno
USER airflow
RUN pip install --no-cache-dir --user -r /requirements.txt

# Exponer puertos típicos de Airflow (puedes ajustar si necesitas otros)
EXPOSE 8080
