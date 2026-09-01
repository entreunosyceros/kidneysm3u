"""Módulo de run app."""

import os
import sys
import platform
import subprocess
from pathlib import Path

def is_venv_exists():
    """Indica si venv exists."""
    venv_dir = '.venv'
    return os.path.exists(venv_dir) and os.path.isdir(venv_dir)

def preferred_python():
    """Preferred python."""
    if platform.system().lower() == 'windows':
        return sys.executable
    for path in ('/usr/bin/python3', '/usr/local/bin/python3'):
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return sys.executable


def create_venv():
    """Crea venv."""
    base = preferred_python()
    print(f"Creando el entorno virtual con {base}...")
    subprocess.run([base, '-m', 'venv', '.venv'], check=True)

def get_python_executable():
    """Obtiene python executable."""
    if platform.system().lower() == 'windows':
        return os.path.join('.venv', 'Scripts', 'python.exe')
    return os.path.join('.venv', 'bin', 'python')

def get_pip_executable():
    """Obtiene PiP executable."""
    if platform.system().lower() == 'windows':
        return os.path.join('.venv', 'Scripts', 'pip.exe')
    return os.path.join('.venv', 'bin', 'pip')

def install_requirements():
    """Install requirements."""
    pip_exe = get_pip_executable()
    requirements_file = 'requirements.txt'
    
    print("Instalando setuptools para resolver dependencias...")
    subprocess.run([pip_exe, 'install', '--upgrade', 'setuptools'], check=True)
    
    if not os.path.exists(requirements_file):
        print(f"Error: {requirements_file} not found")
        sys.exit(1)
    
    print("Instalando dependencias desde requirements.txt...")
    subprocess.run([pip_exe, 'install', '-r', requirements_file], check=True)

def run_main_app():
    """Ejecuta main app."""
    python_exe = os.path.abspath(get_python_executable())
    main_file = os.path.abspath('main.py')

    if not os.path.exists(main_file):
        print(f"Error: {main_file} not found")
        sys.exit(1)

    print("Iniciando la aplicación...")
    # Sustituye este proceso para que el lanzador de GNOME agrupe la ventana
    # en el mismo icono (mismo PID que arrancó el .desktop).
    os.execv(python_exe, [python_exe, main_file])

def main():
    """Main."""
    # Cambiar al directorio que contenga este script
    os.chdir(Path(__file__).parent)
    
    if not is_venv_exists():
        create_venv()
    
    try:
        install_requirements()
        run_main_app()
    except subprocess.CalledProcessError as e:
        print(f"Error ocurrido: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error inesperado: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()