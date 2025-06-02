FROM apache/airflow:2.6.0-python3.9

USER root 
RUN mkdir /work && chown airflow: /work
WORKDIR /work

USER airflow

# Copiar el archivo requirements.txt al contenedor
COPY ./requirements.txt /work/requirements.txt

RUN ls -l /work
# Instalar dependencias adicionales desde requirements.txt
# Asegúrate de que tu requirements.txt no incluya jupyter o jupyterlab si decides excluirlos
RUN pip install -r /work/requirements.txt

# Exponer puertos necesarios (ejemplo: el puerto web de Airflow y otros que necesites)
EXPOSE 8080 8081 8082

# Utilizar el ENTRYPOINT y CMD por defecto de Airflow

