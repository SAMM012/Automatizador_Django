# core/project_state.py
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field
import os

@dataclass
class ProjectState:
    
    ruta_base: str = ""
    ruta_proyecto: str = ""
    nombre_proyecto: str = ""
    
    database_choice: str = "sqlite"
    
    apps_a_crear: List[str] = field(default_factory=list)
    apps_generadas: List[str] = field(default_factory=list)
    
    wizard_states: Dict[str, bool] = field(default_factory=lambda: {
        "carpeta": False,
        "entorno": False,
        "bd_config": False,
        "apps": False,
        "modelos": False,
        "servidor": False
    })
    
    proceso_servidor: Optional[object] = None
    
    def get_venv_python_path(self) -> Path:
        venv_dir = Path(self.ruta_base) / "venv"

        if os.name == "nt":
            return venv_dir / "Scripts" / "python.exe"
        
        return venv_dir / "bin" / "python"
    
    def get_manage_py_path(self) -> Path:
        return Path(self.ruta_proyecto) / "manage.py"
    
    def is_project_ready(self) -> bool:
        return (
            self.ruta_base and 
            self.ruta_proyecto and 
            self.get_manage_py_path().exists()
        )
    
    def add_app_to_create(self, app_name: str) -> bool:
        if app_name not in self.apps_a_crear and app_name not in self.apps_generadas:
            self.apps_a_crear.append(app_name)
            return True
        return False
    
    def move_apps_to_generated(self) -> List[str]:
        moved_apps = self.apps_a_crear.copy()
        self.apps_generadas.extend(moved_apps)
        self.apps_a_crear.clear()
        return moved_apps
    
    def update_wizard_step(self, step: str, completed: bool = True):
        if step in self.wizard_states:
            self.wizard_states[step] = completed
    
    def get_current_step(self) -> Optional[str]:
        steps_order = ["carpeta", "entorno", "bd_config", "apps", "modelos", "servidor"]
        
        for step in steps_order:
            if not self.wizard_states[step]:
                return step
        return None
    
    def is_step_available(self, step: str) -> bool:
        steps_order = ["carpeta", "entorno", "bd_config", "apps", "modelos", "servidor"]
        
        try:
            step_index = steps_order.index(step)
            return all(self.wizard_states[steps_order[i]] for i in range(step_index))
        except ValueError:
            return False