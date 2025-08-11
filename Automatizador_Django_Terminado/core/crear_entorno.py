
import subprocess
import asyncio
from pathlib import Path
import sys
import os

async def crear_entorno_virtual(nombre: str, ruta_base: str, nombre_proyecto: str) -> str:
    try:
        ruta_completa = Path(ruta_base) / nombre
        
        # 1. Crear entorno virtual
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "venv", str(ruta_completa),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, "venv creation")

        # 2. Instalar Django - Detectar sistema operativo
        if os.name == "nt":  # Windows
            pip_path = str(ruta_completa / "Scripts" / "pip")
            django_admin = str(ruta_completa / "Scripts" / "python")
        else:  # Linux/macOS
            pip_path = str(ruta_completa / "bin" / "pip")
            django_admin = str(ruta_completa / "bin" / "python")
            
        proc = await asyncio.create_subprocess_exec(
            pip_path, "install", "django",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, "django installation")
        
        # 3. Crear proyecto Django usando python -m django (más compatible)
        # Django creará automáticamente la carpeta del proyecto
        proc = await asyncio.create_subprocess_exec(
            django_admin, "-m", "django", "startproject", nombre_proyecto,
            cwd=ruta_base,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, "django project creation")
        
        return f"Entorno '{nombre}' y proyecto '{nombre_proyecto}' creados correctamente"
    except subprocess.CalledProcessError as e:
        # Si hay error de nombre conflictivo, sugerir alternativa
        if "conflicts with the name" in str(e):
            return f"Error: El nombre '{nombre_proyecto}' está reservado. Prueba con nombres como: sitio_web, mi_app, proyecto_django"
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"

async def instalar_psycopg2(ruta_entorno: str) -> bool:
    """Instala psycopg2-binary para soporte de PostgreSQL"""
    try:
        # Detectar sistema operativo para encontrar pip
        if os.name == "nt":  # Windows
            pip_path = str(Path(ruta_entorno) / "Scripts" / "pip")
        else:  # Linux/macOS
            pip_path = str(Path(ruta_entorno) / "bin" / "pip")
            
        print(" Instalando psycopg2-binary para PostgreSQL...")
        
        proc = await asyncio.create_subprocess_exec(
            pip_path, "install", "psycopg2-binary",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            print(f"Error instalando psycopg2: {stderr.decode()}")
            return False
        
        print("psycopg2-binary instalado correctamente")
        return True
        
    except Exception as e:
        print(f"Error instalando psycopg2: {str(e)}")
        return False

def instalar_psycopg2_sync(ruta_entorno: str) -> bool:
    """Versión síncrona para instalar psycopg2-binary para soporte de PostgreSQL"""
    try:
        # Detectar sistema operativo para encontrar pip
        if os.name == "nt":  # Windows
            pip_path = str(Path(ruta_entorno) / "Scripts" / "pip")
        else:  # Linux/macOS
            pip_path = str(Path(ruta_entorno) / "bin" / "pip")
            
        print(" Instalando psycopg2-binary para PostgreSQL...")
        
        result = subprocess.run(
            [pip_path, "install", "psycopg2-binary"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"Error instalando psycopg2: {result.stderr}")
            return False
        
        print("psycopg2-binary instalado correctamente")
        return True
        
    except Exception as e:
        print(f"Error instalando psycopg2: {str(e)}")
        return False