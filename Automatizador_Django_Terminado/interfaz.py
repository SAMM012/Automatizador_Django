import asyncio
import threading
import flet as ft
from core.crear_carpeta import FolderCreatorLogic
from core.crear_entorno import crear_entorno_virtual, instalar_psycopg2_sync
from core.django_manager import DjangoManager
from core.bd_config import DatabaseConfig
from core.project_state import ProjectState 
from pathlib import Path
import subprocess
import os
import re


class ValidadorNombres:
    #Validador estándar para nombres de carpetas, proyectos y aplicaciones
    
    # Nombres reservados del sistema
    NOMBRES_RESERVADOS_SISTEMA = {
        'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 
        'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 
        'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    
    # Nombres reservados de Django/Python
    NOMBRES_RESERVADOS_DJANGO = {
        'django', 'test', 'admin', 'auth', 'contenttypes', 'sessions', 
        'messages', 'staticfiles', 'models', 'views', 'urls', 'forms',
        'settings', 'wsgi', 'asgi', 'manage', 'migration', 'migrations',
        'import', 'class', 'def', 'if', 'else', 'for', 'while', 'try',
        'except', 'with', 'as', 'from', 'return', 'yield', 'lambda',
        'global', 'nonlocal', 'assert', 'del', 'pass', 'break', 'continue'
    }
    
    # Nombres específicos del proyecto
    NOMBRES_RESERVADOS_PROYECTO = {
        'venv', 'env', 'virtualenv', '__pycache__', 'node_modules'
    }
    
    @staticmethod
    def validar_nombre(nombre: str, tipo_validacion: str = "carpeta") -> dict:
        #   Valida un nombre según las reglas estándar
        
        nombre = nombre.strip()
        
        # Validar que no esté vacío
        if not nombre:
            return {"valido": False, "mensaje": "Advertencia: Debes ingresar un nombre"}
        
        # Validar caracteres permitidos: solo letras, números y guión bajo
        if not re.match(r'^[a-zA-Z0-9_]+$', nombre):
            return {
                "valido": False, 
                "mensaje": "Error: Solo se permiten letras (a-z, A-Z), números (0-9) y guión bajo (_). No se permiten espacios ni otros caracteres especiales."
            }
        
        # Validar que no empiece con número (para proyectos Django)
        if tipo_validacion in ["proyecto", "app"] and nombre[0].isdigit():
            return {
                "valido": False,
                "mensaje": "Error: El nombre no puede empezar con un número"
            }
        
        # Validar longitud
        if len(nombre) > 64:
            return {
                "valido": False,
                "mensaje": "Error: El nombre es demasiado largo (máximo 64 caracteres)"
            }
        
        # Validar nombres reservados del sistema
        if nombre.upper() in ValidadorNombres.NOMBRES_RESERVADOS_SISTEMA:
            return {
                "valido": False,
                "mensaje": f"Error: '{nombre}' es un nombre reservado del sistema"
            }
        
        # Validar nombres reservados de Django/Python
        if tipo_validacion in ["proyecto", "app"] and nombre.lower() in ValidadorNombres.NOMBRES_RESERVADOS_DJANGO:
            return {
                "valido": False,
                "mensaje": f"Error: '{nombre}' es una palabra reservada de Django/Python. Usa nombres como: mi_sitio, proyecto_web, app_principal"
            }
        
        # Validar nombres específicos del proyecto
        if nombre.lower() in ValidadorNombres.NOMBRES_RESERVADOS_PROYECTO:
            return {
                "valido": False,
                "mensaje": f"Error: '{nombre}' está reservado para uso del sistema. Usa otro nombre como: mi_proyecto, web_app, sistema_principal"
            }
        
        # Si llegamos aquí, el nombre es válido
        return {"valido": True, "mensaje": ""}


class GestorErrores:
    #Sistema centralizado para manejar errores con banner rojo y limpieza automática
    
    # Mapeo de contextos de error para limpieza automática
    CONTEXTOS_ERROR = {
        "carpeta": {
            "palabras_clave": ['carpeta', 'ubicación', 'letras', 'números', 'guión bajo', 'caracteres especiales', 'reservado del sistema', 'demasiado largo'],
            "metodo_limpieza": "limpiar_campos_carpeta"
        },
        "entorno": {
            "palabras_clave": ['proyecto', 'entorno', 'django', 'reservada', 'números', 'espacios', 'reservado para uso del sistema', 'empezar con un número'],
            "metodo_limpieza": "limpiar_campos_entorno"
        },
        "apps": {
            "palabras_clave": ['app', 'nombre para la app', 'app ya fue añadida'],
            "metodo_limpieza": "limpiar_campos_apps"
        },
        "base_datos": {
            "palabras_clave": ['base de datos', 'puerto', 'host', 'usuario'],
            "metodo_limpieza": "limpiar_campos_postgres"
        },
        "modelo": {
            "palabras_clave": ['tabla', 'modelo', 'campos', 'nombre para la tabla', 'seleccionar una app', 'campos válidos', 'error inesperado', 'campo reservado por django', 'nombres duplicados', 'campo único'],
            "metodo_limpieza": "limpiar_campos_modelo"
        },
        "superuser": {
            "palabras_clave": ['admin', 'superusuario', 'usuario', 'email', 'contraseña', 'nombre de admin'],
            "metodo_limpieza": "limpiar_campos_superuser"
        }
    }
    
    @staticmethod
    def mostrar_error_global(ui_instance, mensaje: str, contexto: str = "auto"):
       # Muestra error en el banner rojo con contexto automático o manual
        try:
            # Actualizar el mensaje del banner
            ui_instance.error_overlay.content.controls[1].content.value = mensaje
            ui_instance.error_overlay.visible = True
            
            # Guardar contexto para limpieza posterior
            if contexto == "auto":
                contexto = GestorErrores._detectar_contexto(mensaje)
            
            ui_instance._contexto_error_actual = contexto
            ui_instance.page.update()
            
            print(f"Error mostrado [{contexto}]: {mensaje}")
            
        except Exception as ex:
            print(f"Error al mostrar banner: {ex}")
    
    @staticmethod
    def _detectar_contexto(mensaje: str) -> str:
        #Detecta automáticamente el contexto basado en palabras clave del mensaje
        mensaje_lower = mensaje.lower()
        
        for contexto, config in GestorErrores.CONTEXTOS_ERROR.items():
            if any(keyword in mensaje_lower for keyword in config["palabras_clave"]):
                return contexto
        
        return "modelo"  # Contexto por defecto
    
    @staticmethod
    def limpiar_y_cerrar_inteligente(ui_instance):
        #Limpia campos según el contexto detectado automáticamente
        try:
            # Obtener contexto actual o detectarlo del mensaje
            contexto = getattr(ui_instance, '_contexto_error_actual', None)
            
            if not contexto:
                # Detectar contexto del mensaje actual
                mensaje_actual = ui_instance.error_overlay.content.controls[1].content.value
                contexto = GestorErrores._detectar_contexto(mensaje_actual)
            
            # Ejecutar método de limpieza correspondiente
            config = GestorErrores.CONTEXTOS_ERROR.get(contexto, GestorErrores.CONTEXTOS_ERROR["modelo"])
            metodo_limpieza = getattr(ui_instance, config["metodo_limpieza"])
            metodo_limpieza()
            
            # Cerrar banner
            GestorErrores.cerrar_error(ui_instance)
            
            print(f"Campos limpiados para contexto: {contexto}")
            
        except Exception as ex:
            print(f"Error al limpiar y cerrar: {ex}")
    
    @staticmethod
    def cerrar_error(ui_instance):
        try:
            ui_instance.error_overlay.visible = False
            ui_instance._contexto_error_actual = None
            ui_instance.page.update()
        except Exception as ex:
            print(f"Error al cerrar banner: {ex}")


class UI:
    
    def mostrar_error(self, mensaje: str, contexto: str = "auto"):
        GestorErrores.mostrar_error_global(self, mensaje, contexto)
    
    def cerrar_error(self, e=None):
        GestorErrores.cerrar_error(self)
    def mostrar_error_carpeta(self, mensaje: str):
        self.mostrar_error(mensaje, "carpeta")
    
    def mostrar_error_entorno(self, mensaje: str):
        self.mostrar_error(mensaje, "entorno")
        

    def __init__(self, page:ft.Page):

        self.page = page
        self.state = ProjectState()
        self.logic = FolderCreatorLogic(page)
        self.db_config = DatabaseConfig("Mi_proyecto")
        self.django_manager = DjangoManager()
        
        # Contenedor de error centrado
        self.error_overlay = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.WARNING, color=ft.Colors.WHITE),
                ft.Container(  # Contenedor para centrar el texto un poco más
                    content=ft.Text("", 
                                  color=ft.Colors.WHITE, 
                                  size=15,  # Un punto más grande
                                  text_align=ft.TextAlign.CENTER),
                    expand=True,
                    alignment=ft.alignment.center_left,
                    margin=ft.margin.only(left=20)  # 20% más centrado
                ),
                ft.IconButton(
                    icon=ft.Icons.CLEANING_SERVICES,
                    tooltip="Limpiar campos", 
                    icon_color=ft.Colors.WHITE,
                    on_click=lambda e: GestorErrores.limpiar_y_cerrar_inteligente(self)
                ),
                ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    tooltip="Cerrar",
                    icon_color=ft.Colors.WHITE,
                    on_click=lambda e: GestorErrores.cerrar_error(self)
                )
            ]),
            bgcolor=ft.Colors.RED_400,
            padding=15,
            border_radius=8,
            width=750,  # 50% más largo (500 + 250 = 750)
            alignment=ft.alignment.center,  # Centrar contenido
            shadow=ft.BoxShadow(
                spread_radius=2,
                blur_radius=15,
                color=ft.Colors.BLACK38,
            ),
            visible=False
        )

        self.txt_folder_name =ft.TextField(
            label="Ej: Mi proyecto",
            width=150,
            height=40,
            max_length=64,
            on_change=self.actualiza_nombr_carpeta
        )
        self.lbl_path = ft.Text("Ninguna", style=ft.TextThemeStyle.BODY_SMALL)
        self.dd_apps = ft.Dropdown(
                    options=[],
                    label="Selecciona una app",
                    width=200
        )
        
        self.txt_entorno = ft.TextField(
            label="Nombre del entorno virtual",
            width=200,
            height=40,
            value="venv",
            disabled=True,
            bgcolor=ft.Colors.GREY_200,
            color=ft.Colors.GREY_700
        )
        
        self.txt_tabla = ft.TextField(
            label="Ingresa el nombre de la tabla",
            width=280,
            height=40,
            on_change=self.valida_nombre_tabla  # Validación en tiempo real
        )
        
        self.txt_nombre_proyecto = ft.TextField(
            label="Ej: mi_proyecto",
            width=200,
            height=40,
            max_length=64,
            on_change=self.valida_nombre_proyecto
        )
        
        self.txt_nombre_app = ft.TextField(
            label="Ej: usuarios",
            width=200,
            height=40,
            on_change=self.valida_nombre_app  # Validación en tiempo real
        )
        
        self.lista_apps = ft.Column()
        self.color_teal = ft.Colors.TEAL_700 

        self.btn_iniciar_servidor = ft.ElevatedButton(
            "Iniciar Servidor",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self.iniciar_servidor,
            bgcolor=ft.Colors.GREEN_800,
            color=ft.Colors.WHITE,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=2),
                side=ft.BorderSide(1, ft.Colors.BLACK)
            )
        )

        self.btn_detener_servidor = ft.ElevatedButton(
            "Detener Servidor",
            icon=ft.Icons.STOP,
            on_click=self.detener_servidor,
            bgcolor=ft.Colors.RED_800,
            color=ft.Colors.WHITE,
            disabled=True,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=2),
                side=ft.BorderSide(1, ft.Colors.BLACK)
            )
        )

        self.txt_admin_user = ft.TextField(label="Nombre de admin", width=200, on_change=self.valida_nombre_admin)
        self.txt_admin_email = ft.TextField(label="Email (opcional)", width=200, value="admin@proyecto.local", on_change=self.valida_email_admin)
        self.txt_admin_pass = ft.TextField(label="Contraseña", password=True, width=200, on_change=self.valida_password_admin)

        # Campos para configuración PostgreSQL
        self.txt_db_name = ft.TextField(
            label="Nombre de la base de datos",
            width=200,
            height=35,
            value="mi_db",
            on_change=self.validar_campo_postgres
        )
        self.txt_db_user = ft.TextField(
            label="Usuario",
            width=200,
            height=35,
            value="postgres",
            on_change=self.validar_campo_postgres
        )
        self.txt_db_password = ft.TextField(
            label="Contraseña",
            width=200,
            height=35,
            password=True,
            on_change=self.validar_campo_postgres
        )
        self.txt_db_host = ft.TextField(
            label="Host",
            width=200,
            height=35,
            value="localhost",
            on_change=self.validar_campo_postgres
        )
        self.txt_db_port = ft.TextField(
            label="Puerto",
            width=200,
            height=35,
            value="5432",
            on_change=self.validar_campo_postgres
        )

        # Contenedor para campos PostgreSQL (inicialmente oculto)
        self.postgres_fields_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Configuración PostgreSQL:", weight=ft.FontWeight.BOLD, size=14),
                    ft.Row([
                        ft.Column([
                            self.txt_db_name,
                            self.txt_db_user,
                            self.txt_db_password
                        ], spacing=8),
                        ft.Column([
                            self.txt_db_host,
                            self.txt_db_port
                        ], spacing=8)
                    ], spacing=20)
                ],
                spacing=10
            ),
            padding=ft.padding.only(top=15, bottom=10),
            visible=False
        )

        # RadioGroup para selección de base de datos
        self.selec_bd_radio = ft.RadioGroup(
            content=ft.Row([
                ft.Radio(value="sqlite", label="SQLite"),
                ft.Radio(value="postgres", label="PostgreSQL (Próximamente)", disabled=True)
            ]),
            value="sqlite",
            on_change=self.actualiza_bd_check
        )

        self.btn_crear_su = ft.ElevatedButton(
            "Crear Superusuario",
            icon=ft.Icons.PERSON_ADD,
            on_click=lambda e: self._trigger_async_creation(),
            bgcolor=ft.Colors.BLUE_800,
            color="white",
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=2),
                side=ft.BorderSide(1, ft.Colors.BLACK)
            )
        )

        self.btn_aceptar_entorno = ft.ElevatedButton(
            content=ft.Text("ACEPTAR", color="white"),
            bgcolor="#4CAF50",
            height=40,
            on_click=lambda e: self.page.run_task(self.crea_entorno_h, e),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=2),
                overlay_color=ft.Colors.with_opacity(0.1, "white"),
                side=ft.BorderSide(1, ft.Colors.BLACK)
            )
        )

        self.btn_aceptar_bd = ft.ElevatedButton(
            content=ft.Text("ACEPTAR", color="white"),
            bgcolor="#4CAF50",
            height=40,
            on_click=self.guarda_bd_config,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=2),
                overlay_color=ft.Colors.with_opacity(0.1, "white"),
                side=ft.BorderSide(1, ft.Colors.BLACK)
            )
        )

        self.btn_aceptar_carpeta = ft.ElevatedButton(
            content=ft.Text("ACEPTAR", color="white"),
            bgcolor="#4CAF50",
            height=40,
            on_click=self.crea_carpeta,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=2),
                overlay_color="#FFFFFF",
                side=ft.BorderSide(1, ft.Colors.BLACK)
            )
        )

        self.lbl_estado_entorno = ft.Text(
            "",
            style=ft.TextThemeStyle.BODY_SMALL,
            color=ft.Colors.BLACK,
            visible=False
        )

        self.panel_tablas = self._crear_panel_tablas()

        self.contenedor1 = ft.Container(
            col=4,
            expand=True,
            bgcolor=self.color_teal,
            border_radius=10,
            padding=10,
            content=ft.Column(
                #Contenedor1
                expand=True,
                controls=[
                    ft.Container(
                        expand=True,
                        alignment=ft.alignment.center,
                        content=ft.Row(
                            controls=[
                                ft.Text("Crear carpeta del proyecto", size=20, weight=ft.FontWeight.BOLD)
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER
                        )
                    ),
                    ft.Divider(
                        height=1,
                        color="black"
                    ),
                    ft.Row(
                        expand=True,
                        controls=[
                            ft.Container(               #Contenedor1
                                expand=True,
                                height= 180,
                                content=ft.Column(
                                    controls=[
                                        ft.Text("Nombre de la carpeta:", weight=ft.FontWeight.BOLD),
                                        self.txt_folder_name,
                                        ft.ElevatedButton(
                                            "Seleccionar ubicaciion",
                                            icon=ft.Icons.FOLDER_OPEN,
                                            on_click= self.selec_carpeta,
                                            style=ft.ButtonStyle(
                                                side=ft.BorderSide(1, ft.Colors.BLACK)
                                            )
                                        ),
                                        ft.Row([
                                            ft.Text("Ubicacion seleccionada:", style=ft.TextThemeStyle.BODY_SMALL),
                                            self.lbl_path
                                        ]
                                        )
                                        
                                    ],
                                    spacing=10
                                ),
                                padding=20
                            ), 
                            ft.Container(
                                width=100,
                                alignment=ft.alignment.center,
                                content=self.btn_aceptar_carpeta
                            )                     
                        ],
                        spacing=20,
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    )
                ]
            )

        )

        self.contenedor2 = ft.Container(
            col=4,
            expand=True,
            bgcolor=self.color_teal,
            border_radius=10,
            padding=10,
            content=ft.Column(
                expand=True,
                controls=[
                    ft.Container(
                        expand=True,
                        alignment=ft.alignment.center,
                        content=ft.Row(
                            controls=[
                                ft.Text("Crear entonrno virtual", size=20, weight=ft.FontWeight.BOLD),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER
                        )
                    ),
                    ft.Divider(height=1, color="black"),
                    ft.Column(
                        expand=True,
                        controls=[
                            ft.Row(
                                expand=True,
                                controls=[
                                    ft.Container(
                                        expand=True,
                                        height=180,
                                        content=ft.Column(
                                            controls=[
                                                ft.Text("Ingresa el nombre de tu entorno virtual", weight=ft.FontWeight.BOLD),
                                                self.txt_entorno,
                                                ft.Text("Ingresa el nombre del proyecto Django", weight=ft.FontWeight.BOLD),
                                                self.txt_nombre_proyecto
                                            ],
                                            spacing=5
                                        ),
                                        padding=8
                                    ),
                                    ft.Container(
                                        width=100,
                                        content=ft.Column(
                                            controls=[
                                                self.btn_aceptar_entorno,
                                                ft.Container(
                                                    content=self.lbl_estado_entorno,
                                                    padding=ft.padding.only(top=10),
                                                    alignment=ft.alignment.center
                                                )
                                            ],
                                            horizontal_alignment=ft.CrossAxisAlignment.CENTER
                                        )
                                    )
                                ],
                                spacing=20,
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                            )
                        ]
                    )
                ]
            )
        )

        self.contenedor3 = ft.Container(
            col=4,
            expand=True,
            bgcolor=self.color_teal,
            border_radius=10,
            padding=10,
            content=ft.Column(
                expand=True,
                controls=[
                    ft.Container(
                        expand=True,
                        alignment=ft.alignment.center,
                        content=ft.Row(
                            controls=[
                                ft.Text("Tipo de Base de Datos", size=20, weight=ft.FontWeight.BOLD)
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        )
                    ),
                    ft.Divider(height=1, color="black"),
                    
                    ft.Row(
                        expand=True,
                        controls=[
                            ft.Container(
                                expand=True,
                                height=180,
                                content=ft.Column(
                                    controls=[
                                        ft.Text("Seleccione que tipo de base de datos usar:", size=16, weight=ft.FontWeight.BOLD),
                                        
                                        self.selec_bd_radio,
                                        
                                        # Contenedor de campos PostgreSQL (se muestra/oculta dinámicamente)
                                        self.postgres_fields_container
                                    ],
                                    spacing=10
                                ),
                                padding=20
                            ),
                            ft.Container(
                                width=100,
                                content=ft.Column(
                                    controls=[
                                        self.btn_aceptar_bd
                                    ],
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER
                                )
                            )
                        ],
                        spacing=10
                    )
                ]
            )
        )

        self.contenedor4 = ft.Container(
            height=550,
            col=4,
            expand=True,
            bgcolor=self.color_teal,
            border_radius=10,
            padding=10,
            content=self.panel_tablas
        )

        self.contenedor5 = ft.Container(
            col=4,
            expand=True,
            bgcolor=self.color_teal,
            border_radius=10,
            padding=10,
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Text("Crear Apps Django", size=20, weight="bold")
                            ],
                            alignment=ft.MainAxisAlignment.CENTER
                        )
                    ),
                    ft.Divider(height=1, color="black"),
                    ft.Column(
                        controls=[
                            ft.Text("Nombre de la App:", weight="bold"),
                            self.txt_nombre_app,
                            ft.ElevatedButton(
                                "Añadir App",
                                icon=ft.Icons.ADD,
                                on_click=self.add_app,
                                style=ft.ButtonStyle(
                                    side=ft.BorderSide(1, ft.Colors.BLACK)
                                )
                            ),
                            ft.Text("Apps a crear:", weight="bold"),
                            self.lista_apps,
                            ft.ElevatedButton(
                                "Generar Apps",
                                icon=ft.Icons.CHECK,
                                on_click=self.generar_apps,
                                bgcolor="#4CAF50",
                                color="white",
                                style=ft.ButtonStyle(
                                    side=ft.BorderSide(1, ft.Colors.BLACK)
                                )
                            )
                        ],
                        spacing=15
                    )
                ],
                expand=True
            )
        )

        self.contenedor6 = ft.Container(
            col=4,
            expand=True,
            bgcolor=self.color_teal,
            border_radius=10,
            padding=10,
            content=ft.Column(
                controls=[

                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Text("INICIAR / DETENER SERVIDOR", size=20, weight="bold")
                            ],
                            alignment=ft.MainAxisAlignment.CENTER
                        )
                    ),
                    ft.Divider(height=1, color="black"),
                    ft.Row(
                        controls=[
                            self.btn_iniciar_servidor,  
                            self.btn_detener_servidor  
                        ],
                        spacing=15
                    ),
                    ft.Divider(height=30, color=ft.Colors.TRANSPARENT),
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Text("CREAR SUPER USUARIO", size=20, weight="bold")
                            ],
                            alignment=ft.MainAxisAlignment.CENTER
                        )
                    ),
                    ft.Divider(height=1, color="black"),
                    ft.Column(
                        controls=[

                            self.txt_admin_user,
                            self.txt_admin_email,
                            self.txt_admin_pass,
                            ft.Text("* Todos los campos son obligatorios", style="italic")
                        ]
                    ),
                    ft.Row(
                        controls=[ 
                            self.btn_crear_su
                        ],
                        spacing=15
                    )        
                ],
                expand=True
            )
            
        )

        self.contenedor7 = ft.Container(
            col=4,
            expand=True,
            bgcolor=self.color_teal,
            border_radius=10,
            padding=10,
            content=ft.Column(
                controls=[
                    ft.Container(
                        expand=True,
                        alignment=ft.alignment.center,
                        content=ft.Row(
                            controls=[
                                ft.Text("Nuevo proyecto", size=20, weight=ft.FontWeight.BOLD)
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER
                        )
                    ),
                    ft.Divider(height=1, color="black"),
                    ft.Row(
                        expand=True,
                        controls=[
                            ft.Container(
                                expand=True,
                                height=180,
                                content=ft.Column(
                                    controls=[
                                        ft.Text(
                                            "¿Quieres crear otro proyecto?", 
                                            size=16, 
                                            weight=ft.FontWeight.BOLD,
                                            text_align=ft.TextAlign.CENTER
                                        ),
                                        ft.Text(
                                            "Este botón reiniciará completamente el asistente, "
                                            "permitiéndote crear un nuevo proyecto desde el inicio. "
                                            "Se borrarán todos los datos del proyecto actual.",
                                            size=12,
                                            text_align=ft.TextAlign.CENTER,
                                            color=ft.Colors.BLACK87
                                        )
                                    ],
                                    spacing=15,
                                    alignment=ft.MainAxisAlignment.CENTER,
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER
                                ),
                                padding=20
                            ),
                            ft.Container(
                                width=100,
                                alignment=ft.alignment.center,
                                content=ft.ElevatedButton(
                                    content=ft.Text("NUEVO PROYECTO", color="white", size=11),
                                    bgcolor="#4CAF50",
                                    height=40,
                                    on_click=self.nuevo_proyecto,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=2),
                                        overlay_color=ft.Colors.with_opacity(0.1, "white"),
                                        side=ft.BorderSide(1, ft.Colors.BLACK)
                                    )
                                )
                            )
                        ],
                        spacing=20,
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    )
                ]
            )
        )

        # Contenido principal sin overlay
        self.contenido_principal = ft.Column(
                controls=[
                    ft.ResponsiveRow(
                        controls=[
                            self._wrap_container_with_wizard(self.contenedor1, "carpeta", 1, "Crear carpeta del proyecto"),
                            self._wrap_container_with_wizard(self.contenedor2, "entorno", 2, "Crear entorno virtual"),
                            self._wrap_container_with_wizard(self.contenedor3, "bd_config", 3, "Configurar base de datos"),
                        ]
                    ),
                    ft.ResponsiveRow(
                        controls=[
                            ft.Column(
                                col=4,
                                controls=[
                                    self._wrap_container_with_wizard(self.contenedor5, "apps", 5, "Crear Apps Django"),
                                    ft.Container(height=10),  # Espacio reducido entre contenedores
                                    self.contenedor7
                                ]
                            ),
                            self._wrap_container_with_wizard(self.contenedor4, "modelos", 4, "Crear modelos"),
                            self._wrap_container_with_wizard(self.contenedor6, "servidor", 6, "Servidor y usuarios"),
                        ]
                    )
                ],
                scroll=ft.ScrollMode.AUTO,
                expand=True
            )
        
        # Contenedores con overlay centrado
        self.contenedores = ft.Column(
            controls=[
                ft.Container(  # Contenedor para centrar el error
                    content=self.error_overlay,
                    alignment=ft.alignment.center,
                    padding=ft.padding.symmetric(horizontal=20, vertical=10)
                ),
                self.contenido_principal  # Contenido principal
            ],
            spacing=0,
            expand=True
        )

    def _create_disabled_overlay(self):
        return ft.Container(
            expand=True,
            width=float('inf'),  
            height=float('inf'), 
            bgcolor=ft.Colors.with_opacity(0.6, "grey"),  
            border_radius=10,
            alignment=ft.alignment.center,
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.LOCK, size=50, color="white"),
                    ft.Text(
                        "Completa el paso anterior",
                        color="white",
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                        size=16
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=15,
                tight=True
            )
        )

    def _create_step_indicator(self, step_number: int, title: str, is_completed: bool, is_current: bool):
        if is_completed:
            icon = ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN, size=20)
            title_color = ft.Colors.GREEN
        elif is_current:
            icon = ft.Icon(ft.Icons.RADIO_BUTTON_UNCHECKED, color=ft.Colors.BLUE, size=20)
            title_color = ft.Colors.BLUE
        else:
            icon = ft.Icon(ft.Icons.LOCK, color=ft.Colors.GREY_400, size=20)
            title_color = ft.Colors.GREY_400
        
        return ft.Row(
            controls=[
                ft.Container(
                    width=30,
                    height=30,
                    bgcolor=ft.Colors.with_opacity(0.1, title_color),
                    border_radius=15,
                    alignment=ft.alignment.center,
                    content=ft.Text(str(step_number), color=title_color, weight=ft.FontWeight.BOLD)
                ),
                icon,
                ft.Text(title, color=title_color, weight=ft.FontWeight.BOLD, size=16)
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=5
        )

    def _wrap_container_with_wizard(self, container, step_key: str, step_number: int, title: str):
        is_completed = self.state.wizard_states[step_key] 
        is_current = self._is_current_step(step_key)
        is_enabled = is_completed or is_current
        
        if hasattr(container.content, 'controls') and len(container.content.controls) > 0:
            container.content.controls[0] = ft.Container(
                expand=True,
                alignment=ft.alignment.center,
                content=self._create_step_indicator(step_number, title, is_completed, is_current)
            )
        if is_enabled:
            return ft.Container(
                col=4,
                expand=True,
                content=container.content,
                bgcolor=container.bgcolor,
                border_radius=container.border_radius,
                padding=container.padding
            )
        else:
            return ft.Container(
                col=4,
                expand=True,
                content=ft.Stack(
                    controls=[
                        ft.Container(
                            expand=True,
                            content=container.content,
                            bgcolor=container.bgcolor,
                            border_radius=container.border_radius,
                            padding=container.padding
                        ),
                        ft.Container(
                            left=0,
                            top=0,
                            right=0,
                            bottom=0,
                            bgcolor=ft.Colors.with_opacity(0.85, "grey"),
                            border_radius=10,
                            alignment=ft.alignment.center,
                            content=ft.Column(
                                controls=[
                                    ft.Icon(ft.Icons.LOCK, size=50, color="white"),
                                    ft.Text(
                                        "Completa el paso anterior",
                                        color="white",
                                        weight=ft.FontWeight.BOLD,
                                        size=16
                                    )
                                ],
                                alignment=ft.MainAxisAlignment.CENTER,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=15
                            )
                        )
                    ]
                )
            )


    def _is_current_step(self, step_key: str) -> bool:
        steps_order = ["carpeta", "entorno", "bd_config", "apps", "modelos", "servidor"]
        
        for i, step in enumerate(steps_order):
            if step == step_key:
                if i == 0:
                    return not self.state.wizard_states[step] 
                else:
                    prev_completed = all(self.state.wizard_states[prev_step] for prev_step in steps_order[:i])  
                    return prev_completed and not self.state.wizard_states[step] 
        return False

    def _update_wizard_state(self, step_key: str, completed: bool = True):
        self.state.wizard_states[step_key] = completed 
        self._refresh_wizard_ui()

    def _refresh_wizard_ui(self):
        # Actualizar solo el contenido principal, no el overlay
        self.contenido_principal.controls = [
            ft.ResponsiveRow(
                controls=[
                    self._wrap_container_with_wizard(self.contenedor1, "carpeta", 1, "Crear carpeta del proyecto"),
                    self._wrap_container_with_wizard(self.contenedor2, "entorno", 2, "Crear entorno virtual"),
                    self._wrap_container_with_wizard(self.contenedor3, "bd_config", 3, "Configurar base de datos"),
                ]
            ),
            ft.ResponsiveRow(
                controls=[
                    ft.Column(
                        col=4,
                        controls=[
                            self._wrap_container_with_wizard(self.contenedor5, "apps", 5, "Crear Apps Django"),
                            ft.Container(height=10),  # Espacio reducido entre contenedores
                            self.contenedor7
                        ]
                    ),
                    self._wrap_container_with_wizard(self.contenedor4, "modelos", 4, "Crear modelos"),
                    self._wrap_container_with_wizard(self.contenedor6, "servidor", 6, "Servidor y usuarios"),
                ]
            )
        ]
        self.page.update()
    
    async def crea_entorno_h(self, e):
        # Verificar si hay errores activos antes de proceder
        if self.error_overlay.visible:
            print("No se puede crear entorno: hay errores de validación activos")
            return
            
        if not self.state.wizard_states["carpeta"]:
            self.mostrar_error_entorno("Advertencia: Primero debes crear la carpeta del proyecto")
            return

        nombre_entorno = self.txt_entorno.value.strip()
        nombre_proyecto = self.txt_nombre_proyecto.value.strip()
        
        if not nombre_entorno or not nombre_proyecto:
            self.mostrar_error_entorno("Advertencia: Ingresa nombres para el entorno virtual y el proyecto Django")
            return
            
        # VALIDACIÓN del nombre del proyecto usando validador estándar
        resultado = ValidadorNombres.validar_nombre(nombre_proyecto, "proyecto")
        if not resultado["valido"]:
            self.mostrar_error_entorno(resultado["mensaje"])
            return
            
        try:
            # Cambiar botón a estado de carga
            self.btn_aceptar_entorno.disabled = True
            self.btn_aceptar_entorno.bgcolor = ft.Colors.BLUE_800
            self.btn_aceptar_entorno.content = ft.Text("INSTALANDO...", color="white", size=12)
            
            # Mostrar primer mensaje
            self.lbl_estado_entorno.value = "Creando entorno virtual..."
            self.lbl_estado_entorno.visible = True
            self.page.update()
            
            self.state.nombre_proyecto = nombre_proyecto
            
            # Cambiar mensaje durante la instalación
            self.lbl_estado_entorno.value = "Descargando Django..."
            self.page.update()
            
            resultado = await crear_entorno_virtual(
                nombre_entorno,
                self.state.ruta_base,
                nombre_proyecto
            )
            
            # Mensaje final de configuración
            self.lbl_estado_entorno.value = "Configurando proyecto..."
            self.page.update()
            
            print(resultado)
            self.state.ruta_proyecto = str(Path(self.state.ruta_base) / nombre_proyecto)
            self.state.update_wizard_step("entorno", True)
            
            # Estado final: botón completado y ocultar texto
            self.btn_aceptar_entorno.bgcolor = ft.Colors.GREY_600
            self.btn_aceptar_entorno.content = ft.Text("COMPLETADO", color="white", size=12)
            self.lbl_estado_entorno.visible = False
            
            self._refresh_wizard_ui()
            
        except Exception as ex:
            # En caso de error, restaurar estado original
            self.btn_aceptar_entorno.disabled = False
            self.btn_aceptar_entorno.bgcolor = "#4CAF50"
            self.btn_aceptar_entorno.content = ft.Text("ACEPTAR", color="white")
            self.lbl_estado_entorno.visible = False
            self.page.update()
            
            # Mostrar error específico según el tipo
            error_msg = str(ex)
            if "conflicts with the name" in error_msg:
                self.mostrar_error_entorno(f"Error: El nombre '{nombre_proyecto}' está reservado por Django. Usa nombres como: sitio_web, mi_app, proyecto_django")
            elif "Permission denied" in error_msg or "Access is denied" in error_msg:
                self.mostrar_error_entorno("Error: Sin permisos para crear archivos en esta ubicación. Elige otra carpeta.")
            elif "No space left on device" in error_msg:
                self.mostrar_error_entorno("Error: Sin espacio en disco. Libera espacio o elige otra ubicación.")
            else:
                self.mostrar_error_entorno(f"Error: Error durante la instalación: {error_msg}")

    def actualiza_bd_check(self, e):
        self.state.database_choice = e.control.value
        
        # Mostrar/ocultar campos PostgreSQL según la selección
        if e.control.value == "postgres":
            self.postgres_fields_container.visible = True
        else:
            self.postgres_fields_container.visible = False
        
        # Actualizar la UI
        self.page.update()
        print(f"Base de datos seleccionada: {self.state.database_choice}")

    def guarda_bd_config(self, e):
        # Verificar si hay errores activos antes de proceder
        if self.error_overlay.visible:
            print("No se puede guardar configuración BD: hay errores de validación activos")
            return
            
        if not self.state.wizard_states["entorno"]:
            self.mostrar_error_entorno("Advertencia: Primero debes crear el entorno virtual")
            return
            
        # Cambiar botón a estado de carga
        self.btn_aceptar_bd.disabled = True
        self.btn_aceptar_bd.bgcolor = ft.Colors.BLUE_800
        self.btn_aceptar_bd.content = ft.Text("PROCESANDO...", color="white", size=12)
        self.page.update()
            
        try:
            # Validar configuración PostgreSQL si fue seleccionada
            if self.state.database_choice == "postgres":
                # Validar que todos los campos requeridos estén llenos
                if not self.txt_db_name.value.strip():
                    self.mostrar_error_entorno("Error: Ingresa el nombre de la base de datos")
                    return
                if not self.txt_db_user.value.strip():
                    self.mostrar_error_entorno("Error: Ingresa el usuario de la base de datos")
                    return
                if not self.txt_db_host.value.strip():
                    self.mostrar_error_entorno("Error: Ingresa el host de la base de datos")
                    return
                if not self.txt_db_port.value.strip():
                    self.mostrar_error_entorno("Error: Ingresa el puerto de la base de datos")
                    return
                    
                # Validar puerto
                try:
                    puerto = int(self.txt_db_port.value.strip())
                    if not (1 <= puerto <= 65535):
                        self.mostrar_error_entorno("Error: El puerto debe estar entre 1 y 65535")
                        return
                except ValueError:
                    self.mostrar_error_entorno("Error: El puerto debe ser un número válido")
                    return
                
                # Configurar PostgreSQL con los datos del usuario
                self.db_config.set_postgres_config(
                    name=self.txt_db_name.value.strip(),
                    user=self.txt_db_user.value.strip(),
                    password=self.txt_db_password.value,  # Puede estar vacío
                    host=self.txt_db_host.value.strip(),
                    port=self.txt_db_port.value.strip()
                )
            
            # Actualizar nombre del proyecto en db_config
            self.db_config.project_name = self.state.nombre_proyecto
            
            # Guardar tipo de base de datos
            self.db_config.set_database_type(self.state.database_choice)
            
            # Instalar psycopg2 si se selecciona PostgreSQL
            if self.state.database_choice == "postgres" and self.state.ruta_base:
                venv_path = str(Path(self.state.ruta_base) / "venv")
                print("Instalando driver de PostgreSQL...")
                try:
                    success = instalar_psycopg2_sync(venv_path)
                    if not success:
                        self.mostrar_error_entorno("Error: Error al instalar el driver de PostgreSQL. Verifica tu conexión a internet.")
                        return
                except Exception as e:
                    print(f"Error instalando psycopg2: {e}")
                    self.mostrar_error_entorno("Error: Error al instalar el driver de PostgreSQL.")
                    return
            
            # Generar/actualizar settings.py con la nueva configuración
            if self.state.ruta_proyecto:
                self.db_config.generate_files(self.state.ruta_proyecto)
            
            print(f"Configuración {self.state.database_choice.upper()} guardada y aplicada")
            
            # Estado final: botón completado
            self.btn_aceptar_bd.bgcolor = ft.Colors.GREY_600
            self.btn_aceptar_bd.content = ft.Text("COMPLETADO", color="white", size=12)
            
            self.state.update_wizard_step("bd_config", True)
            self._refresh_wizard_ui()
            
        except Exception as ex:
            # En caso de error, restaurar estado original
            self.btn_aceptar_bd.disabled = False
            self.btn_aceptar_bd.bgcolor = "#4CAF50"
            self.btn_aceptar_bd.content = ft.Text("ACEPTAR", color="white")
            self.page.update()
            
            error_msg = str(ex)
            self.mostrar_error_entorno(f"Error: Error al guardar configuración: {error_msg}")
            
        finally:
            self.page.update()


    async def guardar_modelo(self, e):
        try:
            # Verificar si hay errores activos antes de proceder
            if self.error_overlay.visible:
                print("No se puede guardar modelo: hay errores de validación activos")
                return
                
            nombre_tabla = self.txt_tabla.value.strip()
            if not nombre_tabla:
                self.mostrar_error("Advertencia: Debes ingresar un nombre para la tabla/modelo.", "modelo")
                return
            
            # VALIDACIÓN usando validador estándar ANTES de procesar
            resultado = ValidadorNombres.validar_nombre(nombre_tabla, "app")
            if not resultado["valido"]:
                self.mostrar_error(resultado["mensaje"], "modelo")
                return
                
            if not self.dd_apps.value:
                self.mostrar_error("Advertencia: Debes seleccionar una app antes de crear el modelo.", "modelo")
                return
                
            app_name = self.dd_apps.value.replace(" (pendiente)", "")
            
            campos = []
            print(f"\n=== DEBUG RECOLECCIÓN DE CAMPOS ===")
            print(f"Total controles en campos_column: {len(self.columna_campos.controls)}")
            
            for i, row in enumerate(self.columna_campos.controls[1:], 1): 
                print(f"Control {i}: {type(row)}")
                if isinstance(row, ft.Row) and len(row.controls) >= 2:
                    nombre = row.controls[0].value
                    tipo = row.controls[1].value
                    print(f"  Fila {i}: nombre='{nombre}', tipo='{tipo}'")
                    
                    # Filtrar campos problemáticos y vacíos
                    if (nombre and nombre.strip() and tipo and 
                        tipo != 'Tipo' and  # Filtrar tipo inválido
                        nombre.strip() != 'Nombre' and  # Filtrar nombre por defecto
                        tipo in ['CharField', 'IntegerField', 'TextField', 'BooleanField', 'DateTimeField', 'EmailField', 'ForeignKey']):
                        
                        campos.append({"name": nombre.strip(), "type": tipo})
                        print(f"  ✓ Campo agregado: {nombre.strip()} -> {tipo}")
                    else:
                        print(f"  ✗ Campo ignorado (vacío, inválido o fantasma): '{nombre}' -> '{tipo}'")
                        
            print(f"Campos obtenidos: {campos}")
            print("=====================================\n")
            
            if not campos:
                self.mostrar_error("Advertencia: No se encontraron campos válidos. Asegúrate de llenar al menos un campo con nombre y tipo válidos.", "modelo")
                return
            
            # VALIDACIÓN ADICIONAL: verificar nombres de campos antes de procesar
            campos_reservados_django = {
                'id', 'pk', 'objects', 'DoesNotExist', 'MultipleObjectsReturned',
                'save', 'delete', 'full_clean', 'clean', 'validate_unique'
            }
            nombres_campos = [campo["name"] for campo in campos]
            
            # Verificar campos reservados
            for nombre_campo in nombres_campos:
                resultado = ValidadorNombres.validar_nombre(nombre_campo, "app")
                if not resultado["valido"]:
                    self.mostrar_error(f"Campo '{nombre_campo}': {resultado['mensaje']}", "modelo")
                    return
                
                if nombre_campo.lower() in campos_reservados_django:
                    self.mostrar_error(f"Error: El campo '{nombre_campo}' es reservado por Django. Usa otro nombre como: mi_campo, nombre_usuario, fecha_creacion", "modelo")
                    return
            
            # Verificar nombres duplicados
            if len(nombres_campos) != len(set([n.lower() for n in nombres_campos])):
                self.mostrar_error("Error: Tienes campos con nombres duplicados. Cada campo debe tener un nombre único.", "modelo")
                return
            venv_path = str(Path(self.state.ruta_base) / "venv")
            resultado = DjangoManager.crear_modelo(
                project_path=self.state.ruta_proyecto, 
                app_name=app_name,
                nombre_tabla=nombre_tabla,
                campos=campos,
                venv_path=venv_path
            ) 
            if resultado["success"]:
                print(f"Modelo '{nombre_tabla}' guardado y migrado exitosamente")
                
                if not self.state.wizard_states["modelos"]:
                    self.state.update_wizard_step("modelos", True)
                    self._refresh_wizard_ui()
            else:
                print(f"Error: {resultado['error']}")
                self.mostrar_error(f"Error: {resultado['error']}", "modelo")
                
        except Exception as ex:
            error_msg = f"Error inesperado: {str(ex)}"
            print(f"\n=== ERROR ===\n{error_msg}\n=============")
            self.mostrar_error(f"Error: {error_msg}", "modelo")
            import traceback
            traceback.print_exc()

    def continuar_sin_modelo(self, e):
        try:
            if not self.state.wizard_states["apps"]:
                print("Primero debes crear al menos una app Django")
                return
                
            # Marcar el paso de modelos como completado
            if not self.state.wizard_states["modelos"]:
                self.state.update_wizard_step("modelos", True)
                self._refresh_wizard_ui()
                print("Paso de modelos omitido. Puedes continuar al paso del servidor.")
                
        except Exception as ex:
            print(f"Error al continuar sin modelo: {str(ex)}")

    def limpiar_campos_modelo(self, e=None):
        try:
            # Limpiar el nombre de la tabla
            self.txt_tabla.value = ""
            
            # Limpiar solo los TextFields existentes, más simple y seguro
            for i, row in enumerate(self.columna_campos.controls[2:], 1):  # Saltar dropdown y header
                if isinstance(row, ft.Row) and len(row.controls) >= 2:
                    # Limpiar el campo de texto
                    if hasattr(row.controls[0], 'value'):
                        row.controls[0].value = ""
                    
                    # Resetear dropdown a CharField
                    if hasattr(row.controls[1], 'value'):
                        row.controls[1].value = "CharField"
            
            # Actualizar la UI
            self.page.update()
            
            print("Campos limpiados. Puedes agregar nuevos valores.")
        except Exception as ex:
            print(f"Error al limpiar campos: {ex}")
            # Método alternativo más simple
            try:
                self.txt_tabla.value = ""
                self.page.update()
                print("Nombre de tabla limpiado. Edita los campos manualmente.")
            except:
                print("Error al limpiar. Edita los campos manualmente.")

    
    def limpiar_campos_entorno(self):
        #Limpia los campos del contenedor 2 (solo el nombre del proyecto Django)
        try:
            # Solo limpiar el nombre del proyecto Django (el entorno es fijo: "venv")
            self.txt_nombre_proyecto.value = ""
            # Actualizar la UI
            self.page.update()
            print("Campo del proyecto Django limpiado.")
        except Exception as ex:
            print(f"Error al limpiar campos de entorno: {ex}")

    def limpiar_campos_apps(self):
        try:
            # Limpiar el campo de nombre de app
            self.txt_nombre_app.value = ""
            # Actualizar la UI
            self.page.update()
            print("Campo de nombre de app limpiado.")
        except Exception as ex:
            print(f"Error al limpiar campos de apps: {ex}")

    def limpiar_campos_postgres(self):
        #Limpia los campos de configuración PostgreSQL
        try:
            # Resetear campos de PostgreSQL a valores por defecto
            self.txt_db_name.value = "mi_db"
            self.txt_db_user.value = "postgres"
            self.txt_db_password.value = ""
            self.txt_db_host.value = "localhost"
            self.txt_db_port.value = "5432"
            # Actualizar la UI
            self.page.update()
            print("Campos de PostgreSQL limpiados.")
        except Exception as ex:
            print(f"Error al limpiar campos de PostgreSQL: {ex}")

    def limpiar_campos_carpeta(self):
        try:
            # Limpiar el nombre de la carpeta
            self.txt_folder_name.value = ""
            # Resetear la ubicación
            self.lbl_path.value = "Ninguna"
            self.lbl_path.color = ft.Colors.BLACK
            # Limpiar la lógica interna
            if hasattr(self, 'logic'):
                self.logic.folder_name = ""
                self.logic.folder_path = ""
            # Actualizar la UI
            self.page.update()
            print("Campos de carpeta limpiados.")
        except Exception as ex:
            print(f"Error al limpiar campos de carpeta: {ex}")

    def limpiar_campos_superuser(self):
        try:
            # Limpiar todos los campos del superusuario
            self.txt_admin_user.value = ""
            self.txt_admin_email.value = ""
            self.txt_admin_pass.value = ""
            # Actualizar la UI
            self.page.update()
            print("Campos de superusuario limpiados.")
        except Exception as ex:
            print(f"Error al limpiar campos de superusuario: {ex}")


    def valida_nombre_proyecto(self, e):
        nombre_proyecto = e.control.value.strip()
        
        if not nombre_proyecto:
            return  # Permitir campo vacío temporalmente
        
        # Usar validador estándar con tipo "proyecto"
        resultado = ValidadorNombres.validar_nombre(nombre_proyecto, "proyecto")
        
        if not resultado["valido"]:
            self.mostrar_error(resultado["mensaje"], "entorno")
            return
            
        # Si la validación pasa, cerrar cualquier error
        self.cerrar_error()

    def valida_nombre_app(self, e):
        nombre_app = e.control.value.strip()
        
        if not nombre_app:
            return  # Permitir campo vacío temporalmente
        
        # Usar validador estándar con tipo "app"
        resultado = ValidadorNombres.validar_nombre(nombre_app, "app")
        
        if not resultado["valido"]:
            self.mostrar_error(resultado["mensaje"], "apps")
            return
            
        # Si la validación pasa, cerrar cualquier error
        self.cerrar_error()

    def valida_nombre_tabla(self, e):
        nombre_tabla = e.control.value.strip()
        
        if not nombre_tabla:
            return  # Permitir campo vacío temporalmente
        
        # Usar validador estándar con tipo "app" (tablas/modelos siguen las mismas reglas)
        resultado = ValidadorNombres.validar_nombre(nombre_tabla, "app")
        
        if not resultado["valido"]:
            self.mostrar_error(resultado["mensaje"], "modelo")
            return
            
        # Si la validación pasa, cerrar cualquier error
        self.cerrar_error()

    def valida_nombre_campo(self, e):
        nombre_campo = e.control.value.strip()
        
        if not nombre_campo:
            return  # Permitir campo vacío temporalmente
        
        # Campos reservados por Django (más estrictos que para nombres de proyecto)
        campos_reservados_django = {
            'id', 'pk', 'objects', 'DoesNotExist', 'MultipleObjectsReturned',
            'save', 'delete', 'full_clean', 'clean', 'validate_unique'
        }
        
        # Usar validador estándar con tipo "app" (nombres de campos siguen reglas similares)
        resultado = ValidadorNombres.validar_nombre(nombre_campo, "app")
        
        if not resultado["valido"]:
            self.mostrar_error(resultado["mensaje"], "modelo")
            return
            
        # Validación adicional específica para campos de modelo
        if nombre_campo.lower() in campos_reservados_django:
            self.mostrar_error(f"Error: '{nombre_campo}' es un campo reservado por Django. Usa otro nombre como: mi_campo, nombre_usuario, fecha_creacion", "modelo")
            return
            
        # Si la validación pasa, cerrar cualquier error
        self.cerrar_error()

    def valida_nombre_admin(self, e):
        nombre_admin = e.control.value.strip()
        
        if not nombre_admin:
            return  # Permitir campo vacío temporalmente
        
        # Nombres reservados del sistema
        nombres_reservados = {
            'root', 'admin', 'administrator', 'sa', 'system', 'daemon', 
            'bin', 'sys', 'adm', 'tty', 'disk', 'lp', 'mail', 'news'
        }
        
        # Usar validador estándar
        resultado = ValidadorNombres.validar_nombre(nombre_admin, "app")
        
        if not resultado["valido"]:
            self.mostrar_error(resultado["mensaje"], "superuser")
            return
            
        # Validación específica para nombres de admin
        if nombre_admin.lower() in nombres_reservados:
            self.mostrar_error(f"Error: '{nombre_admin}' es un nombre de admin reservado. Usa otro como: mi_admin, gestor, supervisor", "superuser")
            return
            
        # Longitud mínima para admin
        if len(nombre_admin) < 3:
            self.mostrar_error("Error: El nombre de admin debe tener al menos 3 caracteres", "superuser")
            return
            
        # Si la validación pasa, cerrar cualquier error
        self.cerrar_error()

    def valida_email_admin(self, e):
        email = e.control.value.strip()
        
        # Campo opcional - solo validar si hay contenido
        if not email:
            self.cerrar_error()  # Cerrar errores si está vacío
            return
            
        # Validación básica solo si el usuario ingresó algo
        if '@' not in email:
            self.mostrar_error("Error: Si ingresas email, debe tener formato válido (ej: admin@ejemplo.com)", "superuser")
            return
            
        # Verificar que tenga partes antes y después del @
        partes = email.split('@')
        if len(partes) != 2 or not partes[0] or not partes[1]:
            self.mostrar_error("Error: Formato de email inválido", "superuser")
            return
            
        # Si la validación pasa, cerrar cualquier error
        self.cerrar_error()

    def valida_password_admin(self, e):
        password = e.control.value.strip()
        
        if not password:
            return  # Permitir campo vacío temporalmente
            
        # Longitud mínima
        if len(password) < 6:
            self.mostrar_error("Error: La contraseña debe tener al menos 6 caracteres", "superuser")
            return
            
        # Verificar que no sea demasiado simple
        passwords_simples = {'123456', 'password', 'admin', 'qwerty', '111111', 'abc123'}
        if password.lower() in passwords_simples:
            self.mostrar_error("Error: Usa una contraseña más segura", "superuser")
            return
            
        # Si la validación pasa, cerrar cualquier error
        self.cerrar_error()

    def validar_campo_postgres(self, e):
        campo = e.control
        valor = campo.value.strip()
        
        # Validar que no esté vacío (excepto contraseña)
        if not valor and campo != self.txt_db_password:
            return  # Permitir vacío temporalmente
            
        # Validar puerto si es el campo de puerto
        if campo == self.txt_db_port:
            if not valor.isdigit():
                self.mostrar_error_entorno("Error: El puerto debe ser un número válido (ej: 5432)")
                return
            puerto = int(valor)
            if not (1 <= puerto <= 65535):
                self.mostrar_error_entorno("Error: El puerto debe estar entre 1 y 65535")
                return



    def obtener_campos(self) -> list:
        campos = []
        for row in self.columna_campos.controls[1:]: 
            if isinstance(row, ft.Row) and len(row.controls) >= 2:
                nombre = row.controls[0].value.strip()
                tipo = row.controls[1].value
                if nombre and tipo: 
                    campos.append({"name": nombre, "type": tipo})
        return campos
    

    def actualiza_nombr_carpeta(self, e):
        folder_name = e.control.value.strip()
        
        # Si está vacío, permitir temporal
        if not folder_name:
            self.logic.folder_name = ""
            return
        
        # Usar validador estándar
        resultado = ValidadorNombres.validar_nombre(folder_name, "carpeta")
        
        if not resultado["valido"]:
            self.mostrar_error(resultado["mensaje"], "carpeta")
            return
            
        # Si la validación pasa, actualizar el nombre y cerrar cualquier error
        self.logic.folder_name = folder_name
        self.txt_folder_name.value = folder_name
        self.cerrar_error()  # Cerrar error si todo está bien
        self.page.update()
    
    async def selec_carpeta(self, e):
        try:
            selected_path = await self.logic.open_folder_dialog()
            if selected_path:
                # Validar que la ruta existe y es accesible
                if not os.path.exists(selected_path):
                    self.mostrar_error_carpeta("Error: La ubicación seleccionada no existe")
                    return
                    
                if not os.access(selected_path, os.W_OK):
                    self.mostrar_error_carpeta("Error: No tienes permisos de escritura en la ubicación seleccionada")
                    return
                
                selected_path = os.path.normpath(selected_path)
                self.logic.folder_path = selected_path
                self.lbl_path.value = selected_path
                self.lbl_path.color = ft.Colors.BLACK
                self.page.update()
            else:
                print("No se seleccionó ninguna carpeta")
                
        except Exception as e:
            print(f"Error al seleccionar carpeta: {e}")
            self.mostrar_error_carpeta(f"Error: Error al seleccionar carpeta: {str(e)}")

    async def crea_carpeta(self, e):
        # Verificar si hay errores activos antes de proceder
        if self.error_overlay.visible:
            print("No se puede crear carpeta: hay errores de validación activos")
            return
            
        if not hasattr(self, 'logic'):
            self.mostrar_error_carpeta("Error: Error interno: no se pudo inicializar la lógica de carpetas")
            return 
            
        # Validar que se ha ingresado un nombre de carpeta
        folder_name = self.txt_folder_name.value.strip()
        if not folder_name:
            self.mostrar_error_carpeta("Advertencia: Debes ingresar un nombre para la carpeta")
            return
            
        # VALIDACIÓN usando validador estándar
        resultado = ValidadorNombres.validar_nombre(folder_name, "carpeta")
        if not resultado["valido"]:
            self.mostrar_error_carpeta(resultado["mensaje"])
            return
            
        # Validar que se ha seleccionado una ubicación
        if not self.logic.folder_path:
            self.mostrar_error_carpeta("Advertencia: Debes seleccionar una ubicación para crear la carpeta")
            return
        
        success, message, full_path = self.logic.create_folder_action()
        if success:
            self.state.ruta_base = os.path.normpath(full_path)
            self.lbl_path.value = full_path
            self.lbl_path.color = ft.Colors.BLACK

            # Deshabilitar el botón después del éxito
            self.btn_aceptar_carpeta.disabled = True
            self.btn_aceptar_carpeta.bgcolor = ft.Colors.GREY_600
            self.btn_aceptar_carpeta.content = ft.Text("COMPLETADO", color="white", size=12)

            self.state.update_wizard_step("carpeta", True)
            self._refresh_wizard_ui()
        else:
            # Mostrar error usando el banner rojo
            self.mostrar_error_carpeta(f"Error: {message}")
        self.page.update()                                     

    def _crear_panel_tablas(self):
        self.columna_campos = ft.Column(
            controls=[
                self.dd_apps,
                ft.Row([
                    ft.Text("Nombre", width=200, weight="bold"),
                    ft.Text("Tipo", width=150, weight="bold"),
                ],
                spacing=20
                ),
                *[self._crear_fila_campo(i) for i in range(1, 5)],
            ],
            spacing=10
        )
        
        container_campos = ft.Container(
            content=self.columna_campos,
            padding=ft.padding.only(left=20, right=20)
        )
        
        return ft.Column(
            controls=[
                ft.Text("Crear tabla", size=20, weight="bold"),
                self.txt_tabla,
                ft.Divider(height=20),
                container_campos, 
                ft.ElevatedButton(
                    "Añadir campo",
                    icon=ft.Icons.ADD,
                    on_click=self.nuevo_campo,
                    style=ft.ButtonStyle(
                        side=ft.BorderSide(1, ft.Colors.BLACK)
                    )
                ),
                ft.Row(
                    controls=[
                        ft.ElevatedButton(
                            "Guardar Modelo",
                            icon=ft.Icons.SAVE,
                            on_click=self.guardar_modelo,
                            bgcolor=ft.Colors.GREEN_800,
                            color=ft.Colors.WHITE,
                            style=ft.ButtonStyle(
                                side=ft.BorderSide(1, ft.Colors.BLACK)
                            )
                        ),
                        ft.ElevatedButton(
                            "Continuar sin Modelo",
                            icon=ft.Icons.SKIP_NEXT,
                            on_click=self.continuar_sin_modelo,
                            bgcolor=ft.Colors.ORANGE_800,
                            color=ft.Colors.WHITE,
                            style=ft.ButtonStyle(
                                side=ft.BorderSide(1, ft.Colors.BLACK)
                            )
                        )
                    ],
                    spacing=10,
                    alignment=ft.MainAxisAlignment.CENTER
                )
            ],
            expand=True,
            scroll=True
        )

    def nuevo_campo(self, e):
        try:
            new_index = len(self.columna_campos.controls)
            nueva_fila = self._crear_fila_campo(new_index + 1) 
            
            self.columna_campos.controls.append(nueva_fila)
            self.page.update()  # Usar page.update() en lugar de campos_column.update()
            print(f"Campo {new_index + 1} añadido correctamente")
        except Exception as ex:
            print(f"Error al añadir campo: {ex}")

    def _crear_fila_campo(self, index):
        print(f"\nCreando fila {index}...")  
        return ft.Row(
            controls=[
                ft.TextField(
                    hint_text=f"campo_{index}",
                    width=200,
                    value="",  # Forzar valor vacío
                    autofocus=False,
                    on_change=self.valida_nombre_campo  # Validación en tiempo real
                ),
                ft.Dropdown(
                    width=150,
                    options=[
                        ft.dropdown.Option("CharField"),
                        ft.dropdown.Option("IntegerField"), 
                        ft.dropdown.Option("TextField"),
                        ft.dropdown.Option("BooleanField"),
                        ft.dropdown.Option("DateTimeField"),
                        ft.dropdown.Option("EmailField"),
                        ft.dropdown.Option("ForeignKey")
                    ],
                    value="CharField"  # Valor por defecto seguro
                )
            ],
            spacing=20
        )
        
    def actualizar_dropdown_apps(self):
        self.dd_apps.options = []
        for app in self.state.apps_generadas:
            self.dd_apps.options.append(
                ft.dropdown.Option(
                    text=app,
                    style=ft.ButtonStyle(color=ft.Colors.GREEN)
                )
            )
        for app in self.state.apps_a_crear:
            self.dd_apps.options.append(
                ft.dropdown.Option(
                    text=f"{app} (pendiente)",
                    style=ft.ButtonStyle(color=ft.Colors.ORANGE)
                )
            )
        self.page.update()

    def add_app(self, e):
        # Verificar si hay errores activos antes de proceder
        if self.error_overlay.visible:
            print("No se puede agregar app: hay errores de validación activos")
            return
            
        nombre_app = self.txt_nombre_app.value.strip()
        if not nombre_app:
            self.mostrar_error("Advertencia: Ingresa un nombre para la app", "apps")
            return
            
        # Usar validador estándar con tipo "app"
        resultado = ValidadorNombres.validar_nombre(nombre_app, "app")
        if not resultado["valido"]:
            self.mostrar_error(resultado["mensaje"], "apps")
            return
            
        if self.state.add_app_to_create(nombre_app):
            self.lista_apps.controls.append(ft.Text(f"- {nombre_app}"))
            self.dd_apps.options = [
                ft.dropdown.Option(app) for app in self.state.apps_a_crear
            ]
            self.dd_apps.value = nombre_app
            self.txt_nombre_app.value = ""
            self.cerrar_error()  # Cerrar cualquier error previo al éxito
            self.page.update()
        else:
            self.mostrar_error("Advertencia: Esta app ya fue añadida", "apps")

    async def generar_apps(self, e):
        try:
            if not self.state.ruta_proyecto:
                print("Primero crea el proyecto Django")
                return
            
            if not self.state.apps_a_crear:
                print("No hay apps para generar")
                return
            
            resultado = DjangoManager.generar_apps_legacy(
                self.state.ruta_proyecto, 
                self.state.apps_a_crear 
            )
            
            if resultado["success"]:
                apps_creadas = self.state.move_apps_to_generated()
                
                self.lista_apps.controls.clear()
                self.actualizar_dropdown_apps()
                print(f"Apps generadas: {', '.join(apps_creadas)}")
                
                self.state.update_wizard_step("apps", True)
                self._refresh_wizard_ui()
                
                self.page.update()
            else:
                print(resultado["error"]) 
        except Exception as ex:
            print(f"Error al generar apps: {str(ex)}")

    async def iniciar_servidor(self, e):
        try:
            if not self.state.ruta_base:
                print("Primero selecciona una ubicación para el proyecto")
                return
                
            if not self.state.ruta_proyecto:
                print("Primero genera el proyecto Django")
                return

            python_exe = self.state.get_venv_python_path()
            manage_py = self.state.get_manage_py_path()
            
            if not python_exe.exists():
                print(f"No se encontró el ejecutable Python en: {python_exe}")
                return

            if not manage_py.exists():
                print(f"No se encontró manage.py en {manage_py}")
                return
            
            # Limpiar cualquier proceso previo del puerto 8000
            print("Limpiando puerto 8000...")
            self._kill_port_8000_processes()
            self.state.proceso_servidor = subprocess.Popen(
                [str(python_exe), str(manage_py), "runserver"],
                cwd=str(self.state.ruta_proyecto),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Redirige stderr a stdout
                text=True,
                bufsize=1,  # Buffering de línea
                universal_newlines=True
            )

            print(f"Intentando iniciar servidor en http://127.0.0.1:8000")
            print("Monitoreando salida del servidor...")
            threading.Thread(target=self.monitorear_servidor, daemon=True).start()
            
            self.btn_iniciar_servidor.disabled = True
            self.btn_detener_servidor.disabled = False
            self.page.update()

        except Exception as ex:
            print(f"Error al iniciar servidor: {str(ex)}")

    def detener_servidor(self, e):
        self._cleanup_server_process()
        self.btn_iniciar_servidor.disabled = False
        self.btn_detener_servidor.disabled = True
        self.page.update()
    
    def _cleanup_server_process(self):
        """Limpia el proceso del servidor Django de manera segura"""
        if (hasattr(self.state, 'proceso_servidor') and 
            self.state.proceso_servidor and 
            self.state.proceso_servidor.poll() is None):
            
            try:
                # Primero intentamos terminar suavemente
                self.state.proceso_servidor.terminate()
                print("Enviando señal de terminación al servidor...")
                
                # Esperamos un poco para que el proceso termine
                try:
                    self.state.proceso_servidor.wait(timeout=3)
                    print("Servidor detenido correctamente")
                except subprocess.TimeoutExpired:
                    # Si no responde en 3 segundos, lo forzamos
                    print("Forzando detención del servidor...")
                    self.state.proceso_servidor.kill()
                    self.state.proceso_servidor.wait()
                    print("Servidor detenido forzosamente")
                    
                # Limpiar referencia al proceso
                self.state.proceso_servidor = None
                    
            except Exception as ex:
                print(f"Error al detener servidor: {ex}")
        else:
            print("No hay servidor ejecutándose")
        
        # Además, matar cualquier proceso que use el puerto 8000
        self._kill_port_8000_processes()
    
    def _kill_port_8000_processes(self):
        """Mata todos los procesos que estén usando el puerto 8000"""
        try:
            # Intentar usar psutil si está disponible
            import psutil # type: ignore
            
            # Buscar procesos usando puerto 8000
            for proc in psutil.process_iter(['pid', 'name', 'connections']):
                try:
                    connections = proc.info['connections']
                    if connections:
                        for conn in connections:
                            if hasattr(conn, 'laddr') and conn.laddr and conn.laddr.port == 8000:
                                print(f"Matando proceso {proc.info['name']} (PID: {proc.info['pid']}) que usa puerto 8000")
                                proc.kill()
                                proc.wait(timeout=3)
                                print(f"Proceso PID {proc.info['pid']} eliminado")
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, Exception):
                    # Ignorar errores al acceder a procesos
                    continue
        except ImportError:
            # Si psutil no está disponible, usar método alternativo
            self._kill_port_8000_fallback()
        except Exception as ex:
            print(f"Error al limpiar puerto 8000: {ex}")
            # Como fallback, intentar el método alternativo
            self._kill_port_8000_fallback()
    
    def _kill_port_8000_fallback(self):
        """Método alternativo para limpiar puerto 8000 sin psutil"""
        try:
            import os
            if os.name == 'nt':  # Windows
                # Buscar procesos usando puerto 8000 en Windows
                result = subprocess.run(['netstat', '-ano'], 
                                      capture_output=True, text=True, timeout=10)
                if result.stdout:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if ':8000' in line and 'LISTENING' in line:
                            # Extraer el PID (última columna)
                            parts = line.strip().split()
                            if len(parts) > 4:
                                pid = parts[-1]
                                if pid.isdigit():
                                    try:
                                        subprocess.run(['taskkill', '/PID', pid, '/F'], 
                                                     capture_output=True, timeout=5)
                                        print(f"Proceso PID {pid} eliminado del puerto 8000 (Windows)")
                                    except Exception:
                                        pass
            else:  # Linux/Mac
                result = subprocess.run(['lsof', '-ti:8000'], 
                                      capture_output=True, text=True, timeout=5)
                if result.stdout.strip():
                    pids = result.stdout.strip().split('\n')
                    for pid in pids:
                        if pid.isdigit():
                            subprocess.run(['kill', '-9', pid], timeout=3)
                            print(f"Proceso PID {pid} eliminado del puerto 8000")
        except Exception as ex:
            print(f"No se pudo limpiar puerto 8000: {ex}")

    def monitorear_servidor(self):
        while (self.state.proceso_servidor and 
            self.state.proceso_servidor.poll() is None):
            output = self.state.proceso_servidor.stdout.readline().strip()
            if output:
                print(f"[Servidor]: {output}")
        
        # Si el proceso terminó, mostrar el código de salida
        if self.state.proceso_servidor:
            exit_code = self.state.proceso_servidor.poll()
            if exit_code is not None:
                if exit_code != 0:
                    print(f"SERVIDOR TERMINÓ CON ERROR (código: {exit_code})")
                    # Leer cualquier salida restante
                    try:
                        remaining_output = self.state.proceso_servidor.stdout.read()
                        if remaining_output:
                            print(f"Salida final: {remaining_output}")
                    except:
                        pass
                else:
                    print("Servidor detenido normalmente")
                
                # Actualizar estado de botones cuando el proceso termine
                self.btn_iniciar_servidor.disabled = False
                self.btn_detener_servidor.disabled = True
                try:
                    self.page.update()
                except:
                    pass

    def _trigger_async_creation(self):
        
        # Verificar si hay errores activos antes de proceder
        if self.error_overlay.visible:
            print("No se puede crear superusuario: hay errores de validación activos")
            return
        
        # Validar campos requeridos antes de proceder
        if not self.txt_admin_user.value.strip():
            self.mostrar_error("Error: Ingresa un nombre de usuario", "superuser")
            return
            
        if not self.txt_admin_pass.value.strip():
            self.mostrar_error("Error: Ingresa una contraseña", "superuser")
            return
        
        # VALIDACIÓN COMPLETA DE LOS CAMPOS (aunque el banner no esté visible)
        # Validar nombre de usuario
        nombre_admin = self.txt_admin_user.value.strip()
        nombres_reservados = {
            'root', 'admin', 'administrator', 'sa', 'system', 'daemon', 
            'bin', 'sys', 'adm', 'tty', 'disk', 'lp', 'mail', 'news'
        }
        
        # Usar validador estándar
        resultado = ValidadorNombres.validar_nombre(nombre_admin, "app")
        if not resultado["valido"]:
            self.mostrar_error(resultado["mensaje"], "superuser")
            return
            
        # Validación específica para nombres de admin
        if nombre_admin.lower() in nombres_reservados:
            self.mostrar_error(f"Error: '{nombre_admin}' es un nombre de admin reservado. Usa otro como: mi_admin, gestor, supervisor", "superuser")
            return
            
        # Longitud mínima para admin
        if len(nombre_admin) < 3:
            self.mostrar_error("Error: El nombre de admin debe tener al menos 3 caracteres", "superuser")
            return
        
        # Validar contraseña
        password = self.txt_admin_pass.value.strip()
        if len(password) < 6:
            self.mostrar_error("Error: La contraseña debe tener al menos 6 caracteres", "superuser")
            return
            
        # Verificar que no sea demasiado simple
        passwords_simples = {'123456', 'password', 'admin', 'qwerty', '111111', 'abc123'}
        if password.lower() in passwords_simples:
            self.mostrar_error("Error: Usa una contraseña más segura", "superuser")
            return
        
        # Validar email (si se proporcionó)
        email = self.txt_admin_email.value.strip()
        if email and '@' not in email:
            self.mostrar_error("Error: Si ingresas email, debe tener formato válido (ej: admin@ejemplo.com)", "superuser")
            return
        
        # Si llegamos aquí, todos los campos son válidos
        self.page.run_task(self._crear_su_handler_wrapper)

    async def _crear_su_handler_wrapper(self):
        try:
            await self._crear_su_handler()
        except Exception as ex:
            print(f"Error: {str(ex)}")

    async def _crear_su_handler(self):
        # Solo validar usuario y contraseña (email es opcional)
        if not all([
            self.txt_admin_user.value.strip(),
            self.txt_admin_pass.value.strip()
        ]):
            raise ValueError("Complete el nombre de usuario y contraseña")
        
        # Email opcional - usar por defecto si está vacío
        email = self.txt_admin_email.value.strip()
        if not email:
            email = "admin@proyecto.local"
        
        # Usar el método síncrono que funciona mejor
        try:
            self._crear_superusuario_alternativo(
                self.txt_admin_user.value.strip(),
                email,
                self.txt_admin_pass.value.strip()
            )
        except Exception as e:
            print(f"Error al crear superusuario: {str(e)}")
            raise



    def nuevo_proyecto(self, e):
        try:
            # Detener servidor si está ejecutándose
            # Limpiar proceso del servidor si está ejecutándose
            self._cleanup_server_process()
            
            # Resetear el estado del proyecto
            self.state = ProjectState()
            
            # Resetear configuración de base de datos
            self.db_config = DatabaseConfig("Mi_proyecto")
            self.selec_bd_radio.value = "sqlite"  # Resetear a SQLite por defecto
            
            # Limpiar todos los campos
            self.txt_folder_name.value = ""
            self.txt_nombre_proyecto.value = ""
            self.txt_nombre_app.value = ""
            self.txt_tabla.value = ""
            self.txt_admin_user.value = ""
            self.txt_admin_email.value = ""
            self.txt_admin_pass.value = ""
            
            # Resetear campos PostgreSQL
            self.txt_db_name.value = "mi_db"
            self.txt_db_user.value = "postgres" 
            self.txt_db_password.value = ""
            self.txt_db_host.value = "localhost"
            self.txt_db_port.value = "5432"
            self.postgres_fields_container.visible = False  # Ocultar campos PostgreSQL
            
            # Resetear labels y estados
            self.lbl_path.value = "Ninguna"
            self.lbl_path.color = ft.Colors.BLACK
            self.lbl_estado_entorno.visible = False
            
            # Resetear botones a estado inicial
            self.btn_aceptar_carpeta.disabled = False
            self.btn_aceptar_carpeta.bgcolor = "#4CAF50"
            self.btn_aceptar_carpeta.content = ft.Text("ACEPTAR", color="white")
            
            self.btn_aceptar_entorno.disabled = False
            self.btn_aceptar_entorno.bgcolor = "#4CAF50"
            self.btn_aceptar_entorno.content = ft.Text("ACEPTAR", color="white")
            
            self.btn_aceptar_bd.disabled = False
            self.btn_aceptar_bd.bgcolor = "#4CAF50"
            self.btn_aceptar_bd.content = ft.Text("ACEPTAR", color="white")
            
            self.btn_iniciar_servidor.disabled = False
            self.btn_detener_servidor.disabled = True
            
            # Limpiar listas
            self.lista_apps.controls.clear()
            self.dd_apps.options.clear()
            self.dd_apps.value = None
            
            # Limpiar campos de modelo - resetear a estado inicial
            self.columna_campos.controls = [
                self.dd_apps,
                ft.Row([
                    ft.Text("Nombre", width=200, weight="bold"),
                    ft.Text("Tipo", width=150, weight="bold"),
                ], spacing=20),
                *[self._crear_fila_campo(i) for i in range(1, 5)],
            ]
            
            # Resetear lógica de carpetas
            if hasattr(self, 'logic'):
                self.logic.folder_name = ""
                self.logic.folder_path = ""
            
            # Cerrar cualquier overlay de error visible
            self.error_overlay.visible = False
            
            # Refrescar la UI del wizard
            self._refresh_wizard_ui()
            
            print("Wizard reiniciado completamente. Listo para crear un nuevo proyecto.")
            
        except Exception as ex:
            print(f"Error al resetear el wizard: {ex}")
            # En caso de error, al menos cerrar overlay de error
            try:
                self.error_overlay.visible = False
                self.page.update()
            except:
                pass

    def _crear_superusuario_alternativo(self, username: str, email: str, password: str):
        try:
            venv_python = str(self.state.get_venv_python_path())
            manage_py = str(self.state.get_manage_py_path())
            one_liner = f"from django.contrib.auth import get_user_model; User = get_user_model(); user = User.objects.create_superuser('{username}', '{email}', '{password}'); print('Superuser created')"
            
            result = subprocess.run([
                venv_python, manage_py, "shell", "-c", one_liner
            ], check=True, capture_output=True, text=True, cwd=str(self.state.ruta_proyecto))
            
            print("Superusuario creado exitosamente!")
            self.page.snack_bar = ft.SnackBar(
                ft.Text(f"Superusuario {username} creado"),
                bgcolor=ft.Colors.GREEN
            )
            
        except subprocess.CalledProcessError as e:
            # Si el usuario ya existe, intentar solo cambiar contraseña
            if "already exists" in str(e.stderr):
                try:
                    change_pass = f"from django.contrib.auth import get_user_model; User = get_user_model(); u = User.objects.get(username='{username}'); u.set_password('{password}'); u.save(); print('Password updated')"
                    subprocess.run([
                        venv_python, manage_py, "shell", "-c", change_pass
                    ], check=True, capture_output=True, text=True, cwd=str(self.state.ruta_proyecto))
                    
                    self.page.snack_bar = ft.SnackBar(
                        ft.Text(f"Contraseña actualizada para {username}"),
                        bgcolor=ft.Colors.ORANGE
                    )
                except Exception:
                    self.page.snack_bar = ft.SnackBar(
                        ft.Text("Error: Usuario ya existe y no se pudo actualizar"),
                        bgcolor=ft.Colors.RED
                    )
            else:
                self.page.snack_bar = ft.SnackBar(
                    ft.Text(f"Error: {e.stderr}"),
                    bgcolor=ft.Colors.RED
                )
        except Exception as e:
            self.page.snack_bar = ft.SnackBar(
                ft.Text(f"Error: {str(e)}"),
                bgcolor=ft.Colors.RED
            )
        finally:
            self.page.snack_bar.open = True
            self.page.update()

    def handle_keyboard_event(self, e: ft.KeyboardEvent):
        #Maneja los atajos de teclado de la aplicación
        try:
            # Atajo: Escape - Cerrar overlay de error
            if e.key == "Escape" and self.error_overlay.visible:
                self.cerrar_error()
                return
            
            # Atajo: Ctrl+N - Nuevo proyecto
            if e.key == "N" and e.ctrl:
                self.nuevo_proyecto(e)
                return
                
            # Atajo: Enter - Activar botón ACEPTAR del paso actual
            if e.key == "Enter":
                current_step = self._get_current_step()
                if current_step:
                    self._execute_current_step_action(current_step)
                return
                
        except Exception as ex:
            print(f"Error en manejo de teclado: {ex}")

    def _get_current_step(self):
        steps_order = ["carpeta", "entorno", "bd_config", "apps", "modelos", "servidor"]
        
        for step in steps_order:
            if not self.state.wizard_states[step]:
                return step
        return None  # Todos los pasos completados

    def _execute_current_step_action(self, step):
        try:
            if step == "carpeta":
                self.page.run_task(self.crea_carpeta, None)
            elif step == "entorno":
                self.page.run_task(self.crea_entorno_h, None)
            elif step == "bd_config":
                self.guarda_bd_config(None)
            elif step == "apps":
                self.page.run_task(self.generar_apps, None)
            elif step == "modelos":
                # Para modelos, solo ejecutar si hay datos válidos
                if self.txt_tabla.value.strip() and self.dd_apps.value:
                    self.page.run_task(self.guardar_modelo, None)
            elif step == "servidor":
                # Para servidor, ejecutar crear superusuario si hay datos válidos (solo usuario y contraseña requeridos)
                if (self.txt_admin_user.value.strip() and 
                    self.txt_admin_pass.value.strip()):
                    self._trigger_async_creation()
                else:
                    # Si no hay datos de superusuario, intentar iniciar servidor
                    self.page.run_task(self.iniciar_servidor, None)
        except Exception as ex:
            print(f"Error ejecutando acción del paso {step}: {ex}")

    def build(self):
        return self.contenedores
    
def main(page: ft.Page):

    page.window_min_height = 600
    page.window_min_width = 400
    page.theme_mode = ft.ThemeMode.DARK 
    page.scroll = ft.ScrollMode.AUTO

    ui = UI(page) 
    page.on_keyboard_event = ui.handle_keyboard_event
    
    # Agregar handler para cuando se cierra la ventana
    def window_event_handler(e):
        if e.data == "close":
            print("Cerrando aplicación...")
            ui._cleanup_server_process()
            print("Procesos limpiados.")
            page.window_destroy()
    
    page.on_window_event = window_event_handler
    page.add(ui.build())

ft.app(target=main)