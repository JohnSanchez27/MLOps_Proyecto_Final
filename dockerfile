# Imagen base de Airflow
FROM apache/airflow:2.6.0-python3.9

# Cambiar a root temporalmente para instalación
USER root

# Copiar el archivo de dependencias
COPY requirements.txt /work/requirements.txt

# Instalar los paquetes necesarios sin usar --user
RUN pip install --no-cache-dir -r /work/requirements.txt

# Volver al usuario airflow (buena práctica de seguridad)
USER airflow

# Exponer el puerto web de Airflow
EXPOSE 8080


