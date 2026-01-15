import sys
from pathlib import Path
import os

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

BASE_DIR = Path(__file__).parent
frontend_path = BASE_DIR / "frontend.py"

if __name__ == "__main__":
    import subprocess
    
    env = os.environ.copy()
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    
    # 获取本机局域网IP地址
    def get_server_ip():
        """获取本机局域网IP地址"""
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "localhost"
    
    server_ip = get_server_ip()
    print("启动Streamlit前端...")
    print(f"前端地址（本机）: http://localhost:8501")
    print(f"前端地址（局域网）: http://{server_ip}:8501")
    
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        str(frontend_path),
        "--server.port=8501",
        "--server.address=0.0.0.0"
    ], env=env)