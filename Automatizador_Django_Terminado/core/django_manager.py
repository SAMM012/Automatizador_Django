from pathlib import Path
import re
import subprocess
import os

class DjangoManager:
    @staticmethod
    def create_standard_project(env_path: str, project_name: str, project_dir: str) -> bool:
        try:
            python_executable = str(
                Path(env_path) / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            )
            
            subprocess.run(
                [python_executable, "-m", "django", "startproject", project_name, str(project_dir)],
                check=True
            )
            
            # Crear requirements.txt básico
            requirements_path = Path(project_dir) / "requirements.txt"
            with open(requirements_path, "w") as f:
                f.write("Django>=5.0.0\n")
            
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error al crear proyecto: {e}")
            return False

    @staticmethod
    def create_app(project_path: str, app_name: str, python_path: str = "python") -> bool:
        """Crea una nueva app Django"""
        try:
            if not app_name.strip():
                print("Error: El nombre de la app no puede estar vacío")
                return False
            manage_py = Path(project_path) / "manage.py"
            if not manage_py.exists():
                print(f"Error: manage.py no encontrado en {project_path}")
                return False
            subprocess.run(
                [python_path, str(manage_py), "startapp", app_name],
                check=True,
                cwd=project_path
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error al crear app {app_name}: {e}")
            return False
        except Exception as e:
            print(f"Error inesperado al crear app {app_name}: {e}")
            return False

    @staticmethod
    def generate_apps_structure(project_path: str, apps_list: list, project_name: str) -> dict:
        try:
            project_dir = Path(project_path)
            results = {"success": [], "errors": []}            
            apps_dir = project_dir / "apps"
            apps_dir.mkdir(exist_ok=True)            
            for app_name in apps_list:
                try:
                    app_result = DjangoManager._create_single_app(project_dir, app_name, project_name)
                    if app_result["success"]:
                        results["success"].append(app_name)
                    else:
                        results["errors"].append(f"{app_name}: {app_result['error']}")
                except Exception as e:
                    results["errors"].append(f"{app_name}: {str(e)}")
            
            return results
            
        except Exception as e:
            return {"success": [], "errors": [f"Error general: {str(e)}"]}

    @staticmethod
    def _create_single_app(project_dir: Path, app_name: str, project_name: str) -> dict:
        try:
            apps_dir = project_dir / "apps"
            app_dir = apps_dir / app_name
            app_dir.mkdir(exist_ok=True)            
            DjangoManager._create_app_files(app_dir, app_name)
            DjangoManager._update_settings_with_app(project_dir, app_name, project_name)
            return {"success": True, "error": None}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _create_app_files(app_dir: Path, app_name: str):
        init_file = app_dir / "__init__.py"
        if not init_file.exists():
            init_file.touch()
        
        apps_py = app_dir / "apps.py"
        if not apps_py.exists():
            apps_content = f"""from django.apps import AppConfig

class {app_name.capitalize()}Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.{app_name}'
"""
            with open(apps_py, "w", encoding='utf-8') as f:
                f.write(apps_content)
        models_py = app_dir / "models.py"
        if not models_py.exists():
            with open(models_py, "w", encoding='utf-8') as f:
                f.write("from django.db import models\n\n# Modelos aqui\n")        
        admin_py = app_dir / "admin.py"
        if not admin_py.exists():
            with open(admin_py, "w", encoding='utf-8') as f:
                f.write("from django.contrib import admin\n\n# Registra tus modelos aqui\n")        
        views_py = app_dir / "views.py"
        if not views_py.exists():
            with open(views_py, "w", encoding='utf-8') as f:
                f.write("from django.shortcuts import render\n\n# Vistas aqui\n")

    @staticmethod
    def _update_settings_with_app(project_dir: Path, app_name: str, project_name: str):
        settings_path = project_dir / project_name / "settings.py"
        
        if not settings_path.exists():
            possible_paths = [
                project_dir / project_name / "settings.py",
                project_dir / project_name.lower() / "settings.py"
            ]
            
            for path in possible_paths:
                if path.exists():
                    settings_path = path
                    break
        
        if settings_path.exists():
            with open(settings_path, "r+", encoding='utf-8') as f:
                content = f.read()                
                if f"'apps.{app_name}'" not in content:
                    if "'django.contrib.staticfiles'," in content:
                        # Preservar la indentación existente
                        lines = content.split('\n')
                        for i, line in enumerate(lines):
                            if "'django.contrib.staticfiles'," in line:
                                # Obtener la indentación de la línea actual
                                indentation = line[:len(line) - len(line.lstrip())]
                                lines.insert(i + 1, f"{indentation}'apps.{app_name}',")
                                break
                        new_content = '\n'.join(lines)
                        f.seek(0)
                        f.write(new_content)
                        f.truncate()
        else:
            print(f"Advertencia: No se encontró settings.py para registrar {app_name}")

    @staticmethod
    def crear_modelo(project_path: str, app_name: str, nombre_tabla: str, campos: list, venv_path: str) -> dict:
        try:
            project_dir = Path(project_path)
            app_dir = project_dir / "apps" / app_name
            if not app_dir.exists():
                return {"success": False, "error": f"La app {app_name} no existe"}
            
            # Campos reservados que no pueden ser usados (Django los crea automáticamente)
            CAMPOS_RESERVADOS = {'id', 'pk'}
            
            TIPOS_VALIDOS = {
                'CharField': 'CharField(max_length=100)',
                'IntegerField': 'IntegerField()',
                'TextField': 'TextField()',
                'BooleanField': 'BooleanField()',
                'DateTimeField': 'DateTimeField(auto_now_add=True)',
                'EmailField': 'EmailField()',
                'ForeignKey': 'ForeignKey(to="self", on_delete=models.CASCADE)'
            }
            
            # Validar campos antes de generar el modelo
            nombres_usados = set()
            for campo in campos:
                nombre_campo = campo['name'].lower()
                
                # Validar campos reservados
                if nombre_campo in CAMPOS_RESERVADOS:
                    return {"success": False, "error": f"El campo '{campo['name']}' es reservado por Django. Usa otro nombre."}
                
                # Validar nombres duplicados (Django convierte a minúsculas)
                if nombre_campo in nombres_usados:
                    return {"success": False, "error": f"El campo '{campo['name']}' está duplicado. Cada campo debe tener un nombre único."}
                nombres_usados.add(nombre_campo)
                
                # Validar tipo de campo
                if campo['type'] not in TIPOS_VALIDOS:
                    return {"success": False, "error": f"Tipo de campo '{campo['type']}' no válido. Tipos disponibles: {', '.join(TIPOS_VALIDOS.keys())}"}
            
            models_path = app_dir / "models.py"
            contenido = "from django.db import models\n\n"
            if models_path.exists():
                with open(models_path, "r") as f:
                    contenido = f.read()
            nuevo_modelo = f"class {nombre_tabla}(models.Model):\n"
            for campo in campos:
                tipo_campo = campo['type']
                if tipo_campo not in TIPOS_VALIDOS:
                    tipo_campo = 'CharField'
                    print(f"Tipo '{campo['type']}' no válido. Usando CharField")
                    
                nuevo_modelo += f"    {campo['name']} = models.{TIPOS_VALIDOS[tipo_campo]}\n"
            patron = re.compile(rf"class {nombre_tabla}\(models\.Model\):.*?\n\n", re.DOTALL)
            if patron.search(contenido):
                contenido = patron.sub(nuevo_modelo, contenido)
            else:
                contenido += "\n" + nuevo_modelo
            
            with open(models_path, "w", encoding='utf-8') as f:
                f.write(contenido)
            admin_path = app_dir / "admin.py"
            admin_content = "from django.contrib import admin\n"
            
            if admin_path.exists():
                with open(admin_path, "r") as f:
                    admin_content = f.read()
            if f"from .models import {nombre_tabla}" not in admin_content:
                admin_content += f"\nfrom .models import {nombre_tabla}\n"

            if f"admin.site.register({nombre_tabla})" not in admin_content:
                admin_content += f"\nadmin.site.register({nombre_tabla})\n"
            
            with open(admin_path, "w", encoding='utf-8') as f:
                f.write(admin_content)
            
            venv_python = Path(venv_path) / ("Scripts" if os.name == "nt" else "bin") / "python"
            manage_py = project_dir / "manage.py"
            
            # Ejecutar makemigrations con manejo de errores
            print(f"Generando migración para {app_name}...")
            try:
                result_makemig = subprocess.run(
                    [str(venv_python), str(manage_py), "makemigrations", app_name],
                    check=True,
                    cwd=str(project_dir),
                    capture_output=True,
                    text=True
                )
                print("Makemigrations exitoso:")
                print(result_makemig.stdout)
            except subprocess.CalledProcessError as e:
                return {"success": False, "error": f"Error en makemigrations: {e.stderr or e.stdout or str(e)}"}
            
            # Ejecutar migrate con manejo de errores
            print("Aplicando migraciones...")
            try:
                result_migrate = subprocess.run(
                    [str(venv_python), str(manage_py), "migrate"],
                    check=True,
                    cwd=str(project_dir),
                    capture_output=True,
                    text=True
                )
                print("Migrate exitoso:")
                print(result_migrate.stdout)
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr or e.stdout or str(e)
                if "duplicate column name" in error_msg:
                    return {"success": False, "error": f"Ya existe un campo con ese nombre en la base de datos. Usa un nombre diferente o elimina las migraciones anteriores."}
                else:
                    return {"success": False, "error": f"Error en migrate: {error_msg}"}
            
            # PASO 1: Generar views CRUD
            print(f"PASO 1: Generando views CRUD para {nombre_tabla}...")
            DjangoManager.generar_views_crud(str(project_dir), app_name, nombre_tabla)
            
            # PASO 2: Generar forms CRUD
            print(f"PASO 2: Generando forms para {nombre_tabla}...")
            DjangoManager.generar_forms_crud(str(project_dir), app_name, nombre_tabla)
            
            # PASO 3: Generar URLs de la app
            print(f"PASO 3: Generando URLs de la app para {nombre_tabla}...")
            DjangoManager.generar_urls_app(str(project_dir), app_name, nombre_tabla)
            print(f"URLs de app generadas para {nombre_tabla}")
            
            # PASO 4: Conectando al proyecto principal
            print(f"PASO 4: Conectando {app_name} al proyecto principal...")
            DjangoManager._conectar_urls_proyecto(project_dir, app_name)
            print(f"URLs de {app_name} conectadas al proyecto principal")
            print(f"URLs conectadas al proyecto principal")
            
            # PASO 5: Generar templates HTML para CRUD
            print(f"PASO 5: Generando templates HTML para {nombre_tabla}...")
            DjangoManager.generar_templates_crud(str(project_dir), app_name, nombre_tabla)
            
            # PASO 6: Creando página índice del proyecto
            print(f"PASO 6: Creando página índice del proyecto...")
            DjangoManager._crear_pagina_indice(project_dir)
            print(f" Pagina indice creada")

            return {"success": True, "error": None}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def generar_apps_legacy(project_path: str, apps_list: list) -> dict:
        try:
            if not project_path:
                return {"success": False, "apps_creadas": [], "error": "Primero crea el proyecto Django"}
                
            project_dir = Path(project_path)
            apps_dir = project_dir / "apps"
            apps_dir.mkdir(exist_ok=True)
            apps_creadas = []
            for app_name in apps_list:
                app_dir = apps_dir / app_name
                app_dir.mkdir(exist_ok=True)
                init_file = app_dir / "__init__.py"
                if not init_file.exists():
                    init_file.touch()
                apps_py = app_dir / "apps.py"
                if not apps_py.exists():
                    with open(apps_py, "w") as f:
                        f.write(f"""from django.apps import AppConfig
class {app_name.capitalize()}Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.{app_name}'
""")
                models_py = app_dir / "models.py"
                if not models_py.exists():
                    with open(models_py, "w", encoding='utf-8') as f:
                        f.write("from django.db import models\n\n# Modelos aqui\n")
                admin_py = app_dir / "admin.py"
                if not admin_py.exists():
                    with open(admin_py, "w", encoding='utf-8') as f:
                        f.write("from django.contrib import admin\n\n# Registra tus modelos aqui\n")
                views_py = app_dir / "views.py"
                if not views_py.exists():
                    with open(views_py, "w", encoding='utf-8') as f:
                        f.write("from django.shortcuts import render\n\n# Vistas aqui\n")
                # Buscar el archivo settings.py en el directorio del proyecto
                settings_files = list(project_dir.glob("*/settings.py"))
                if settings_files:
                    settings_path = settings_files[0]
                else:
                    # Si no lo encuentra, intentar con el nombre del proyecto
                    project_folders = [f for f in project_dir.iterdir() if f.is_dir() and not f.name.startswith('.') and f.name not in ['apps', '__pycache__']]
                    if project_folders:
                        settings_path = project_folders[0] / "settings.py"
                    else:
                        continue  # Skip si no encuentra settings.py
                if settings_path.exists():
                    with open(settings_path, "r+", encoding='utf-8') as f:
                        content = f.read()
                        if f"'apps.{app_name}'" not in content:
                            # Preservar la indentación existente
                            lines = content.split('\n')
                            for i, line in enumerate(lines):
                                if "'django.contrib.staticfiles'," in line:
                                    # Obtener la indentación de la línea actual
                                    indentation = line[:len(line) - len(line.lstrip())]
                                    lines.insert(i + 1, f"{indentation}'apps.{app_name}',")
                                    break
                            new_content = '\n'.join(lines)
                            f.seek(0)
                            f.write(new_content)
                            f.truncate()
                
                apps_creadas.append(app_name)
                print(f"App '{app_name}' creada exitosamente")
            
            print(f"Apps generadas: {', '.join(apps_creadas)}")
            return {"success": True, "apps_creadas": apps_creadas, "error": None}
        
        except Exception as ex:
            error_msg = f"Error al generar apps: {str(ex)}"
            print(error_msg)
            return {"success": False, "apps_creadas": [], "error": error_msg}

    @staticmethod
    def generar_views_crud(project_path: str, app_name: str, model_name: str) -> dict:
        try:
            project_dir = Path(project_path)
            app_dir = project_dir / "apps" / app_name
            views_path = app_dir / "views.py"
            
            if not app_dir.exists():
                return {"success": False, "error": f"La app {app_name} no existe"}
            
            model_lower = model_name.lower()
            
            views_content = f'''from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse
from .models import {model_name}
from .forms import {model_name}Form

def {model_lower}_lista(request):
    """Lista todos los {model_name}s"""
    objetos = {model_name}.objects.all()
    return render(request, '{app_name}/{model_lower}_lista.html', {{
        'objetos': objetos,
        'titulo': 'Lista de {model_name}s'
    }})

def {model_lower}_detalle(request, id):
    """Muestra el detalle de un {model_name}"""
    objeto = get_object_or_404({model_name}, id=id)
    return render(request, '{app_name}/{model_lower}_detalle.html', {{
        'objeto': objeto,
        'titulo': f'Detalle de {{objeto}}'
    }})

def {model_lower}_crear(request):
    """Crea un nuevo {model_name}"""
    if request.method == 'POST':
        form = {model_name}Form(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '{model_name} creado exitosamente.')
            return redirect('{app_name}:{model_lower}_lista')
    else:
        form = {model_name}Form()
    
    return render(request, '{app_name}/{model_lower}_form.html', {{
        'form': form,
        'titulo': 'Crear {model_name}',
        'accion': 'Crear'
    }})

def {model_lower}_editar(request, id):
    """Edita un {model_name} existente"""
    objeto = get_object_or_404({model_name}, id=id)
    
    if request.method == 'POST':
        form = {model_name}Form(request.POST, instance=objeto)
        if form.is_valid():
            form.save()
            messages.success(request, '{model_name} actualizado exitosamente.')
            return redirect('{app_name}:{model_lower}_detalle', id=objeto.id)
    else:
        form = {model_name}Form(instance=objeto)
    
    return render(request, '{app_name}/{model_lower}_form.html', {{
        'form': form,
        'objeto': objeto,
        'titulo': f'Editar {{objeto}}',
        'accion': 'Actualizar'
    }})

def {model_lower}_eliminar(request, id):
    """Elimina un {model_name}"""
    objeto = get_object_or_404({model_name}, id=id)
    
    if request.method == 'POST':
        objeto.delete()
        messages.success(request, '{model_name} eliminado exitosamente.')
        return redirect('{app_name}:{model_lower}_lista')
    
    return render(request, '{app_name}/{model_lower}_confirmar_eliminar.html', {{
        'objeto': objeto,
        'titulo': f'Eliminar {{objeto}}'
    }})
'''
            
            with open(views_path, "w", encoding='utf-8') as f:
                f.write(views_content)
            
            print(f"Views CRUD generadas para {model_name} en {app_name}")
            return {"success": True, "error": None}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def generar_forms_crud(project_path: str, app_name: str, model_name: str) -> dict:
        try:
            project_dir = Path(project_path)
            app_dir = project_dir / "apps" / app_name
            forms_path = app_dir / "forms.py"
            
            if not app_dir.exists():
                return {"success": False, "error": f"La app {app_name} no existe"}
            
            forms_content = f'''from django import forms
from .models import {model_name}

class {model_name}Form(forms.ModelForm):
    class Meta:
        model = {model_name}
        fields = '__all__'
        widgets = {{
            # Personaliza widgets aqui si es necesario
        }}
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Agregar clases CSS a todos los campos
        for field_name, field in self.fields.items():
            field.widget.attrs.update({{'class': 'form-control'}})
'''
            
            with open(forms_path, "w", encoding='utf-8') as f:
                f.write(forms_content)
            
            print(f"Forms generado para {model_name}")
            return {"success": True, "error": None}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def generar_urls_app(project_path: str, app_name: str, model_name: str) -> dict:
        try:
            project_dir = Path(project_path)
            app_dir = project_dir / "apps" / app_name
            urls_path = app_dir / "urls.py"
            
            if not app_dir.exists():
                return {"success": False, "error": f"La app {app_name} no existe"}

            model_lower = model_name.lower()
            
            urls_content = f'''from django.urls import path
from . import views

app_name = '{app_name}'

urlpatterns = [
    # Lista de {model_name}s
    path('', views.{model_lower}_lista, name='{model_lower}_lista'),
    
    # Detalle de {model_name}
    path('<int:id>/', views.{model_lower}_detalle, name='{model_lower}_detalle'),
    
    # Crear nuevo {model_name}
    path('crear/', views.{model_lower}_crear, name='{model_lower}_crear'),
    
    # Editar {model_name}
    path('<int:id>/editar/', views.{model_lower}_editar, name='{model_lower}_editar'),
    
    # Eliminar {model_name}
    path('<int:id>/eliminar/', views.{model_lower}_eliminar, name='{model_lower}_eliminar'),
]
'''   
            with open(urls_path, "w", encoding='utf-8') as f:
                f.write(urls_content)
            
            print(f"URLs de app generadas para {model_name} en {app_name}")
            return {"success": True, "error": None}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def generar_templates_crud(project_path: str, app_name: str, model_name: str) -> dict:
        try:
            project_dir = Path(project_path)
            templates_dir = project_dir / "templates" / app_name
            templates_dir.mkdir(parents=True, exist_ok=True)
            
            model_lower = model_name.lower()
            
            # Template lista
            lista_template = templates_dir / f"{model_lower}_lista.html"
            lista_content = """{% extends 'base.html' %}

{% block title %}""" + model_name + """s - Mi Proyecto Django{% endblock %}

{% block content %}
<div class="row">
    <div class="col-12">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Inicio</a></li>
                <li class="breadcrumb-item active">""" + model_name + """s</li>
            </ol>
        </nav>
        
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2>""" + model_name + """s</h2>
            <a href="{% url '""" + app_name + ":" + model_lower + """_crear' %}" class="btn btn-primary">Crear """ + model_name + """</a>
        </div>

        {% if objetos %}
            <div class="table-responsive">
                <table class="table table-striped">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Información</th>
                            <th>Acciones</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for objeto in objetos %}
                        <tr>
                            <td>{{ objeto.id }}</td>
                            <td>{{ objeto }}</td>
                            <td>
                                <a href="{% url '""" + app_name + ":" + model_lower + """_detalle' objeto.id %}" class="btn btn-sm btn-info">Ver</a>
                                <a href="{% url '""" + app_name + ":" + model_lower + """_editar' objeto.id %}" class="btn btn-sm btn-warning">Editar</a>
                                <a href="{% url '""" + app_name + ":" + model_lower + """_eliminar' objeto.id %}" class="btn btn-sm btn-danger">Eliminar</a>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        {% else %}
            <div class="alert alert-info">
                <h4>No hay """ + model_name + """s registrados</h4>
                <p>Comienza creando tu primer """ + model_name + """.</p>
                <a href="{% url '""" + app_name + ":" + model_lower + """_crear' %}" class="btn btn-primary">Crear """ + model_name + """</a>
            </div>
        {% endif %}
    </div>
</div>
{% endblock %}
"""
            
            with open(lista_template, "w", encoding='utf-8') as f:
                f.write(lista_content)
            
            # Template formulario (crear/editar)
            form_template = templates_dir / f"{model_lower}_form.html"
            form_content = """{% extends 'base.html' %}

{% block title %}{{ titulo }} - Mi Proyecto Django{% endblock %}

{% block content %}
<div class="row">
    <div class="col-12">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Inicio</a></li>
                <li class="breadcrumb-item"><a href="{% url '""" + app_name + ":" + model_lower + """_lista' %}">""" + model_name + """s</a></li>
                <li class="breadcrumb-item active">{{ titulo }}</li>
            </ol>
        </nav>
    </div>
</div>

<div class="row justify-content-center">
    <div class="col-md-8">
        <div class="card">
            <div class="card-header">
                <h5>{{ titulo }}</h5>
            </div>
            <div class="card-body">
                <form method="post">
                    {% csrf_token %}
                    {% for field in form %}
                        <div class="mb-3">
                            <label class="form-label">{{ field.label }}</label>
                            {{ field }}
                            {% for error in field.errors %}
                                <div class="text-danger">{{ error }}</div>
                            {% endfor %}
                        </div>
                    {% endfor %}
                    
                    <div class="d-flex justify-content-end">
                        <a href="{% url '""" + app_name + ":" + model_lower + """_lista' %}" class="btn btn-secondary me-2">Cancelar</a>
                        <button type="submit" class="btn btn-primary">{{ accion }}</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}
"""
            
            with open(form_template, "w", encoding='utf-8') as f:
                f.write(form_content)
            
            # Template detalle
            detalle_template = templates_dir / f"{model_lower}_detalle.html"
            detalle_content = """{% extends 'base.html' %}

{% block title %}{{ objeto }} - Mi Proyecto Django{% endblock %}

{% block content %}
<div class="row">
    <div class="col-12">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Inicio</a></li>
                <li class="breadcrumb-item"><a href="{% url '""" + app_name + ":" + model_lower + """_lista' %}">""" + model_name + """s</a></li>
                <li class="breadcrumb-item active">{{ objeto }}</li>
            </ol>
        </nav>
        
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2>{{ objeto }}</h2>
            <div>
                <a href="{% url '""" + app_name + ":" + model_lower + """_editar' objeto.id %}" class="btn btn-warning">Editar</a>
                <a href="{% url '""" + app_name + ":" + model_lower + """_eliminar' objeto.id %}" class="btn btn-danger">Eliminar</a>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h5>Detalles del """ + model_name + """</h5>
            </div>
            <div class="card-body">
                <p><strong>ID:</strong> {{ objeto.id }}</p>
                <!-- Aqui se mostrarian todos los campos del modelo -->
            </div>
        </div>

        <div class="mt-3">
            <a href="{% url '""" + app_name + ":" + model_lower + """_lista' %}" class="btn btn-secondary">Volver</a>
        </div>
    </div>
</div>
{% endblock %}
"""
            
            with open(detalle_template, "w", encoding='utf-8') as f:
                f.write(detalle_content)
            
            # Template confirmar eliminar
            confirmar_template = templates_dir / f"{model_lower}_confirmar_eliminar.html"
            confirmar_content = """{% extends 'base.html' %}

{% block title %}Eliminar {{ objeto }} - Mi Proyecto Django{% endblock %}

{% block content %}
<div class="row">
    <div class="col-12">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Inicio</a></li>
                <li class="breadcrumb-item"><a href="{% url '""" + app_name + ":" + model_lower + """_lista' %}">""" + model_name + """s</a></li>
                <li class="breadcrumb-item active">Eliminar</li>
            </ol>
        </nav>
    </div>
</div>

<div class="row justify-content-center">
    <div class="col-md-6">
        <div class="card border-danger">
            <div class="card-header bg-danger text-white">
                <h5>Confirmar eliminacion</h5>
            </div>
            <div class="card-body">
                <div class="alert alert-warning">
                    <strong>Estas seguro de eliminar este """ + model_name + """?</strong>
                </div>
                <p><strong>{{ objeto }}</strong></p>
                
                <form method="post">
                    {% csrf_token %}
                    <div class="d-flex justify-content-end">
                        <a href="{% url '""" + app_name + ":" + model_lower + """_detalle' objeto.id %}" class="btn btn-secondary me-2">Cancelar</a>
                        <button type="submit" class="btn btn-danger">Eliminar</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}
"""
            
            with open(confirmar_template, "w", encoding='utf-8') as f:
                f.write(confirmar_content)
            
            print(f"Templates CRUD generados para {model_name}")
            return {"success": True, "error": None}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _conectar_urls_proyecto(project_dir: Path, app_name: str):
        # Buscar el archivo urls.py en el directorio del proyecto
        urls_files = list(project_dir.glob("*/urls.py"))
        if urls_files:
            main_urls_path = urls_files[0]
        else:
            # Si no lo encuentra, intentar con el nombre del proyecto
            project_folders = [f for f in project_dir.iterdir() if f.is_dir() and not f.name.startswith('.') and f.name not in ['apps', '__pycache__']]
            if project_folders:
                main_urls_path = project_folders[0] / "urls.py"
            else:
                main_urls_path = project_dir / "urls.py"  # fallback
        
        if not main_urls_path.exists():
            possible_paths = [
                project_dir / "urls.py", 
                project_dir / "config" / "urls.py",  
            ]
            
            for path in possible_paths:
                if path.exists():
                    main_urls_path = path
                    break
        
        if main_urls_path.exists():
            with open(main_urls_path, "r") as f:
                content = f.read()
            if "from django.urls import path" in content and "from django.urls import path, include" not in content:
                content = content.replace(
                    "from django.urls import path",
                    "from django.urls import path, include"
                )
            if "from . import views" not in content:
                if "from django.urls import" in content:
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if line.startswith("from django.urls import"):
                            lines.insert(i + 1, "from . import views")
                            break
                    content = '\n'.join(lines)
            if f"path('{app_name}/', include('apps.{app_name}.urls'))" not in content:
                if "urlpatterns = [" in content:
                    if "path('admin/', admin.site.urls)," in content:
                        content = content.replace(
                            "path('admin/', admin.site.urls),",
                            f"path('admin/', admin.site.urls),\n    path('{app_name}/', include('apps.{app_name}.urls')),"
                        )
                    else:
                        content = content.replace(
                            "urlpatterns = [",
                            f"urlpatterns = [\n    path('{app_name}/', include('apps.{app_name}.urls')),"
                        )
            if "path('', views.index, name='index')" not in content:
                if "]" in content:
                    content = content.replace(
                        "]",
                        "    path('', views.index, name='index'),\n]"
                    )
            
            with open(main_urls_path, "w", encoding='utf-8') as f:
                f.write(content)
            
            print(f"URLs de {app_name} conectadas al proyecto principal")
        else:
            print(f"No se encontró urls.py del proyecto principal")

    @staticmethod
    def _crear_pagina_indice(project_dir: Path):
        templates_dir = project_dir / "templates"
        templates_dir.mkdir(exist_ok=True)
        base_template = templates_dir / "base.html"
        if not base_template.exists():
            base_content = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Mi Proyecto Django{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/">Mi Proyecto</a>
        </div>
    </nav>
    
    <div class="container mt-4">
        {% if messages %}
            {% for message in messages %}
                <div class="alert alert-{{ message.tags }} alert-dismissible fade show" role="alert">
                    {{ message }}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            {% endfor %}
        {% endif %}
        
        {% block content %}
        {% endblock %}
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""
            with open(base_template, "w", encoding='utf-8') as f:
                f.write(base_content)
        index_template = templates_dir / "index.html"
        index_content = """{% extends 'base.html' %}

{% block title %}Inicio - Mi Proyecto Django{% endblock %}

{% block content %}
<div class="row">
    <div class="col-12">
        <h1 class="mb-4">Mi Proyecto Django</h1>
        <p class="lead">Bienvenido a tu proyecto Django generado automaticamente</p>
    </div>
</div>

<div class="row">
    <div class="col-md-8">
        <div class="card">
            <div class="card-header">
                <h5 class="card-title mb-0">Apps Disponibles</h5>
            </div>
            <div class="card-body">
                <div class="list-group">
                    {% for app_info in apps %}
                    <a href="/{{ app_info.name }}/" class="list-group-item list-group-item-action">
                        <div class="d-flex w-100 justify-content-between">
                            <h6 class="mb-1">{{ app_info.name|title }}</h6>
                            <small>{{ app_info.models|length }} modelo{{ app_info.models|length|pluralize }}</small>
                        </div>
                        <p class="mb-1">Modelos: {{ app_info.models|join:", " }}</p>
                    </a>
                    {% empty %}
                    <div class="text-muted">No hay apps disponibles aun</div>
                    {% endfor %}
                </div>
            </div>
        </div>
    </div>
    
    <div class="col-md-4">
        <div class="card">
            <div class="card-header">
                <h5 class="card-title mb-0">Enlaces Utiles</h5>
            </div>
            <div class="card-body">
                <ul class="list-unstyled">
                    <li><a href="/admin/" target="_blank">Panel de Admin</a></li>
                    <li><a href="#" onclick="alert('Funcionalidad proximamente')">Estadisticas</a></li>
                    <li><a href="#" onclick="alert('Funcionalidad proximamente')">Configuracion</a></li>
                </ul>
            </div>
        </div>
    </div>
</div>
{% endblock %}"""
        
        with open(index_template, "w", encoding='utf-8') as f:
            f.write(index_content) 
        # Buscar el directorio del proyecto principal
        project_folders = [f for f in project_dir.iterdir() if f.is_dir() and not f.name.startswith('.') and f.name not in ['apps', '__pycache__']]
        if project_folders:
            main_views_path = project_folders[0] / "views.py"
        else:
            main_views_path = project_dir / "views.py"  # fallback
        if not main_views_path.exists():
            views_content = """from django.shortcuts import render
import os
from pathlib import Path

def index(request):
    \"\"\"Vista principal que muestra todas las apps disponibles\"\"\"
    apps_info = []
    
    # Buscar apps en el directorio apps/
    apps_dir = Path(__file__).parent.parent / "apps"
    
    if apps_dir.exists():
        for app_folder in apps_dir.iterdir():
            if app_folder.is_dir() and not app_folder.name.startswith('.'):
                models_file = app_folder / "models.py"
                models = []
                
                if models_file.exists():
                    try:
                        with open(models_file, 'r') as f:
                            content = f.read()
                            # Buscar clases que hereden de models.Model
                            import re
                            model_matches = re.findall(r'class (\w+)\(models\.Model\):', content)
                            models = model_matches
                    except:
                        pass
                
                apps_info.append({
                    'name': app_folder.name,
                    'models': models
                })
    
    return render(request, 'index.html', {
        'apps': apps_info
    })
"""
            
            with open(main_views_path, "w", encoding='utf-8') as f:
                f.write(views_content)
        # Buscar settings.py en el directorio del proyecto principal
        settings_files = list(project_dir.glob("*/settings.py"))
        if settings_files:
            settings_path = settings_files[0]
        else:
            settings_path = project_dir / "settings.py"  # fallback
        if settings_path.exists():
            with open(settings_path, "r") as f:
                content = f.read()
            
            if "'DIRS': []" in content:
                content = content.replace(
                    "'DIRS': []",
                    "'DIRS': [BASE_DIR / 'templates']"
                )
                
                with open(settings_path, "w", encoding='utf-8') as f:
                    f.write(content)
        
        print("Pagina indice creada con templates configurados")