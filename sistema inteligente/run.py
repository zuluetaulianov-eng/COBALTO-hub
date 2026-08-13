"""Script de inicio del Sistema Inteligente."""
import subprocess, sys

if __name__ == "__main__":
    print("Iniciando Sistema Inteligente en http://localhost:8100")
    subprocess.run([sys.executable, "-m", "uvicorn", "api:app", "--reload", "--port", "8100"])
