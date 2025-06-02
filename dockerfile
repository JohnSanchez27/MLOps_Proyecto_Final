# Usamos la imagen de Airflow como base (sin el hash @sha256)
FROM apache/airflow:2.6.0-python3.9

# Ejecutar como root temporalmente para configurar permisos
USER root

# Crear directorio de trabajo y dar permisos al usuario airflow
RUN mkdir -p /work && chown -R airflow: /work

# Establecer el directorio de trabajo
WORKDIR /work

# Cambiar a usuario airflow para instalar dependencias
USER airflow

# Copiar el archivo requirements.txt al contenedor
COPY ./requirements.txt /work/requirements.txt

# Mostrar contenido del directorio de trabajo
RUN ls -l /work

# Instalar las dependencias adicionales
RUN pip install --no-cache-dir -r /work/requirements.txt

# Exponer puertos (si decides abrir múltiples interfaces o servicios web)
EXPOSE 8080 8081 8082


