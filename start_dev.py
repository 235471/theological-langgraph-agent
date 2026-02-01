import subprocess
import sys
import time
import os
import signal


def start_services():
    # Caminho para o python do venv
    venv_python = os.path.join(os.getcwd(), "venv", "Scripts", "python.exe")

    if not os.path.exists(venv_python):
        print("❌ Erro: Ambiente virtual não encontrado em ./venv")
        return

    print("🚀 Iniciando sistema teológico...")

    # Comando para o Backend
    # Usamos o PYTHONPATH=src para que os imports funcionem
    backend_env = os.environ.copy()
    backend_env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")

    backend_cmd = [
        venv_python,
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--reload",
    ]

    # Comando para o Frontend
    frontend_cmd = [
        venv_python,
        "-m",
        "streamlit",
        "run",
        "streamlit/app.py",
        "--server.port",
        "8501",
    ]

    processes = []

    try:
        # Abre o Backend
        print("📡 Iniciando Backend na porta 8000...")
        p_backend = subprocess.Popen(
            backend_cmd, cwd=os.path.join(os.getcwd(), "src"), env=backend_env
        )
        processes.append(p_backend)

        # Espera um pouco para o backend subir e processar o JSON se necessário
        time.sleep(5)

        # Abre o Frontend
        print("💻 Iniciando Streamlit na porta 8501...")
        p_frontend = subprocess.Popen(frontend_cmd)
        processes.append(p_frontend)

        print("\n✅ Sistema pronto! Pressione Ctrl+C para encerrar tudo.\n")

        # Mantém o script rodando enquanto os processos estiverem vivos
        while True:
            time.sleep(1)
            if p_backend.poll() is not None or p_frontend.poll() is not None:
                break

    except KeyboardInterrupt:
        print("\nBye! Encerrando processos...")
    finally:
        for p in processes:
            try:
                p.terminate()
                p.wait(timeout=2)
            except:
                try:
                    p.kill()
                except:
                    pass
        print("✨ Tudo limpo.")


if __name__ == "__main__":
    start_services()
