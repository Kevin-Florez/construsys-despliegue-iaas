#!/bin/bash

# Salir inmediatamente si un comando falla
set -e

# Instalar las dependencias de Python
pip install -r requirements.txt

# Recolectar todos los archivos estáticos en el directorio 'staticfiles'
python manage.py collectstatic --noinput

# (Opcional, pero recomendado) Correr las migraciones de la base de datos en cada despliegue
python manage.py migrate