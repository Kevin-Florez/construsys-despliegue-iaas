#!/bin/bash

# Instalar dependencias
pip3 install -r requirements.txt

# Recolectar archivos estáticos
python3 manage.py collectstatic --noinput --clear