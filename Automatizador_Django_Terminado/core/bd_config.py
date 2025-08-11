import random
from textwrap import dedent
from pathlib import Path
import subprocess
from pathlib import Path
import os

class DatabaseConfig:
    def __init__(self, project_name="Mi_proyecto"):
        self.db_type = "sqlite"  # Valor por defecto
        self.postgres_config = {}
        self.models = []
        self.apps={}
        self.project_name = project_name

    def set_database_type(self, db_type: str):
        self.db_type = db_type

    def set_postgres_config(self, name: str, user: str, password: str, host: str = "localhost", port: str = "5432"):
        self.postgres_config = {
            "name": name,
            "user": user,
            "password": password,
            "host": host,
            "port": port
        }

    def add_model(self, app_name: str, model_name: str, fields: list):
        if app_name not in self.apps:
            self.apps[app_name] = []
            
        self.apps[app_name].append({
            "name": model_name,
            "fields": fields
        })
    
    def generate_django_settings(self) -> str:
        db_config = self._generate_db_config()
        
        return f'''import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = '{''.join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=50))}'

DEBUG = True
ALLOWED_HOSTS = []
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'

{db_config}

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = '{self.project_name}.urls'

TEMPLATES = [
    {{
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {{
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        }},
    }},
]

WSGI_APPLICATION = '{self.project_name}.wsgi.application'

AUTH_PASSWORD_VALIDATORS = [
    {{'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',}},
    {{'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',}},
    {{'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',}},
    {{'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',}},
]

USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'static'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
'''

    def _generate_sqlite_config(self) -> str:
        return '''DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}'''

    def _generate_postgres_config(self) -> str:
        return f'''DATABASES = {{
    'default': {{
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': '{self.postgres_config["name"]}',
        'USER': '{self.postgres_config["user"]}',
        'PASSWORD': '{self.postgres_config["password"]}',
        'HOST': '{self.postgres_config["host"]}',
        'PORT': '{self.postgres_config["port"]}',
    }}
}}'''

    def generate_models_code(self) -> str:
        if not self.models:
            return "from django.db import models\n\n# Añade tus modelos aquí."
        code = "from django.db import models\n\n"
        for model in self.models:
            class_name = model['name'].replace("_", "").title()  # "prueba_1" -> "Prueba1"
            code += f"class {class_name}(models.Model):\n"
            for field in model['fields']:
                code += f"    {field['name']} = models.{field['type']}(max_length=100)\n"
            code += "\n\n"
        return code

    def _map_field_type(self, field: dict) -> str:
        tipo = field['type']
        if tipo == "CharField":
            return "models.CharField(max_length=100, blank=True)"
        elif tipo == "EmailField":
            return "models.EmailField(unique=True)"
        elif tipo == "DateTimeField":
            return "models.DateTimeField(auto_now_add=True)"

    def generate_files(self, output_path: str):    
        project_dir = Path(output_path)
        
        apps_dir = project_dir / "apps"
        apps_dir.mkdir(exist_ok=True)

        # Corregir la ruta del settings.py (era incorrecta)
        settings_file = project_dir / self.project_name / "settings.py"
        
        # SIEMPRE sobrescribir el settings.py con la configuración actualizada
        with open(settings_file, "w") as f:
            f.write(self.generate_django_settings())
        
        print(f"Settings.py actualizado con configuración {self.db_type.upper()}") 
        
        for app_name, models in self.apps.items():
            app_dir = project_dir / "apps" / app_name
            app_dir.mkdir(exist_ok=True)
            
            with open(app_dir / "models.py", "w") as f:
                f.write("from django.db import models\n\n")
                for model in models:
                    f.write(f"class {model['name']}(models.Model):\n")
                    for field in model['fields']:
                        f.write(f"    {field['name']} = models.{field['type']}\n")
                    f.write("\n\n")

            with open(app_dir / "admin.py", "w") as f:
                f.write("from django.contrib import admin\nfrom .models import *\n\n")
                for model in models:
                    f.write(f"admin.site.register({model['name']})\n")

    def _generate_db_config(self) -> str:
        if self.db_type == "sqlite":
            return self._generate_sqlite_config()
        elif self.db_type == "postgres":
            return self._generate_postgres_config()
        else:
            raise ValueError(f"Tipo de BD no soportado: {self.db_type}")


    def update_installed_apps(self, settings_path: str, app_name: str):
        try:
            with open(settings_path, 'r+', encoding='utf-8') as f:
                content = f.read()
                
                # Verificar si la app ya está registrada
                if f"'apps.{app_name}'" in content:
                    return
                
                # Buscar el bloque INSTALLED_APPS y preservar indentación
                if "'django.contrib.staticfiles'," in content:
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if "'django.contrib.staticfiles'," in line:
                            # Obtener la indentación de la línea actual
                            indentation = line[:len(line) - len(line.lstrip())]
                            lines.insert(i + 1, f"{indentation}'apps.{app_name}',")
                            break
                    nuevo_content = '\n'.join(lines)
                    f.seek(0)
                    f.write(nuevo_content)
                    f.truncate()
        except Exception as e:
            print(f"Error al actualizar settings.py: {e}")

    def generar_modelo(self, app_name: str, model_name: str, fields: dict):
        """Genera código para un modelo y lo añade a models.py"""
        model_code = f"\nclass {model_name}(models.Model):\n"
        for field_name, field_type in fields.items():
            model_code += f"    {field_name} = models.{field_type}\n"
        return model_code

    def ejecutar_migraciones(self, project_path: str):
        """Ejecuta makemigrations y migrate"""
        try:
            manage_py = Path(project_path) / "manage.py"
            subprocess.run(["python", str(manage_py), "makemigrations"], check=True)
            subprocess.run(["python", str(manage_py), "migrate"], check=True)
            return True
        except Exception as e:
            print(f"Error en migraciones: {e}")
            return False