import os
import flet as ft
from typing import Tuple, Optional
import asyncio
import re

class FolderCreatorLogic:

    def __init__(self, page: ft.Page):
        self.page = page
        self.folder_path = ""
        self.folder_name = ""
        self._dialog_completed = False
        self._selected_path = None
        
        self.file_picker = ft.FilePicker(on_result=self._folder_selected)
        page.overlay.append(self.file_picker)

    async def open_folder_dialog(self) -> Optional[str]:
        """Abre el diálogo nativo para seleccionar carpeta"""
        self._dialog_completed = False
        self._selected_path = None
        
        self.file_picker.get_directory_path()
        
        # Esperar hasta que el callback complete
        while not self._dialog_completed:
            await asyncio.sleep(0.1)
        
        return self._selected_path

    def _folder_selected(self, e: ft.FilePickerResultEvent):
        """Callback cuando se selecciona carpeta"""
        if e.path:
            self.folder_path = e.path
            self._selected_path = e.path
        else:
            self._selected_path = None
            
        self._dialog_completed = True

    def _validate_folder_name(self, name: str) -> Tuple[bool, str]:
        """Valida el nombre de la carpeta"""
        if not name.strip():
            return False, "El nombre no puede estar vacío"
            
        # Caracteres no permitidos en Windows/Linux
        invalid_chars = r'[<>:"/\\|?*]'
        if re.search(invalid_chars, name):
            return False, "El nombre contiene caracteres no válidos: < > : \" / \\ | ? *"
            
        # Nombres reservados en Windows
        reserved_names = {
            'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 
            'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 
            'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        }
        if name.upper() in reserved_names:
            return False, f"'{name}' es un nombre reservado del sistema"
            
        if len(name) > 255:
            return False, "El nombre es demasiado largo (máximo 255 caracteres)"
            
        return True, ""

    def create_folder_action(self) -> Tuple[bool, str, Optional[str]]:
        """Crear carpeta con validación completa"""
        # Validar ubicación seleccionada
        if not self.folder_path:
            return False, "Selecciona una ubicación primero", None
            
        if not os.path.exists(self.folder_path):
            return False, "La ubicación seleccionada no existe", None
            
        if not os.access(self.folder_path, os.W_OK):
            return False, "No tienes permisos de escritura en la ubicación seleccionada", None

        # Validar nombre de carpeta
        if not self.folder_name:
            return False, "Ingresa un nombre para la carpeta", None
            
        is_valid, error_msg = self._validate_folder_name(self.folder_name)
        if not is_valid:
            return False, error_msg, None

        try:
            full_path = os.path.join(self.folder_path, self.folder_name)
            
            # Verificar si ya existe
            if os.path.exists(full_path):
                return False, f"La carpeta '{self.folder_name}' ya existe en esta ubicación", None
                
            # Crear la carpeta
            os.makedirs(full_path, exist_ok=False)
            
            # Verificar que se creó correctamente
            if not os.path.exists(full_path):
                return False, "La carpeta no se pudo crear correctamente", None
                
            return True, f"Carpeta '{self.folder_name}' creada exitosamente", full_path
            
        except PermissionError:
            return False, "Sin permisos para crear la carpeta en esta ubicación", None
        except OSError as e:
            return False, f"Error del sistema: {str(e)}", None
        except Exception as e:
            return False, f"Error inesperado: {str(e)}", None

    async def get_selected_path(self) -> Optional[str]:
        """Obtiene la ruta seleccionada"""
        return self.folder_path

    def reset(self):
        """Reinicia el estado del creador de carpetas"""
        self.folder_path = ""
        self.folder_name = ""
        self._dialog_completed = False
        self._selected_path = None