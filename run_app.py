import os
import sys
import platform
import subprocess
import venv
from pathlib import Path

def is_venv_exists():
    venv_dir = '.venv'
    return os.path.exists(venv_dir) and os.path.isdir(venv_dir)

def create_venv():
    print("Creando el entorno virtual...")
    venv.create('.venv', with_pip=True)

def get_python_executable():
    if platform.system().lower() == 'windows':
        return os.path.join('.venv', 'Scripts', 'python.exe')
    return os.path.join('.venv', 'bin', 'python')

def get_pip_executable():
    if platform.system().lower() == 'windows':
        return os.path.join('.venv', 'Scripts', 'pip.exe')
    return os.path.join('.venv', 'bin', 'pip')

def install_requirements():
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
    python_exe = get_python_executable()
    main_file = 'main.py'
    
    if not os.path.exists(main_file):
        print(f"Error: {main_file} not found")
        sys.exit(1)
    
    print("Iniciando la aplicación...")
    subprocess.run([python_exe, main_file], check=True)

def main():
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