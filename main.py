import sys
import subprocess
import threading
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent
BASE_DIR_PARENT = BASE_DIR.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(BASE_DIR_PARENT) not in sys.path:
    sys.path.insert(0, str(BASE_DIR_PARENT))

def run_api_server():
    try:
        from api_server import run_api_server
        run_api_server(port=8000)
    except ImportError:
        try:
            from api_server import run_api_server
            run_api_server(port=8000)
        except Exception as e:
            print(f"启动API服务器失败: {e}")
            import traceback
            traceback.print_exc()

def check_port(port):
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('localhost', port))
    sock.close()
    return result != 0

def run_frontend():
    frontend_path = BASE_DIR / "frontend.py"
    
    if not check_port(8501):
        print("⚠ 端口8501已被占用，请关闭占用该端口的程序或使用其他端口")
        return None
    
    try:
        import os
        env = os.environ.copy()
        env['PYTHONUTF8'] = '1'
        env['PYTHONIOENCODING'] = 'utf-8'
        
        cmd = [
            sys.executable, "-m", "streamlit", "run",
            str(frontend_path),
            "--server.port=8501",
            "--server.address=0.0.0.0",
            "--server.headless=true",
            "--browser.gatherUsageStats=false",
            "--server.runOnSave=false"
        ]
        
        print(f"执行命令: {' '.join(cmd)}")
        
        if sys.platform == "win32":
            process = subprocess.Popen(
                cmd,
                env=env,
                shell=False
            )
        else:
            process = subprocess.Popen(
                cmd,
                env=env
            )
        
        return process
    except Exception as e:
        print(f"启动前端失败: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("=" * 60)
    print("空地智能体系统启动中...")
    print("=" * 60)
    
    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()
    
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
    print("✓ 后端API服务启动中: http://localhost:8000")
    print(f"✓ 后端API服务（局域网）: http://{server_ip}:8000")
    print("✓ API文档: http://localhost:8000/docs")
    time.sleep(3)
    
    print("✓ 前端界面启动中...")
    frontend_process = run_frontend()
    if frontend_process:
        time.sleep(5)
        if frontend_process.poll() is None:
            print(f"✓ 前端地址（本机）: http://localhost:8501")
            print(f"✓ 前端地址（局域网）: http://{server_ip}:8501")
            print("=" * 60)
            print("按 Ctrl+C 停止服务")
            print("=" * 60)

            try:
                while True:
                    time.sleep(1)
                    if frontend_process and frontend_process.poll() is not None:
                        print("前端进程已退出，正在重启...")
                        frontend_process = run_frontend()
                        time.sleep(2)
            except KeyboardInterrupt:
                print("\n正在停止服务...")
                if frontend_process:
                    try:
                        frontend_process.terminate()
                        frontend_process.wait(timeout=5)
                    except:
                        frontend_process.kill()
                print("服务已停止")
        else:
            print("⚠ 前端进程启动后立即退出，请检查错误信息")
            print("您可以手动运行以下命令启动前端:")
            print(f"  cd {BASE_DIR}")
            print("  python run_frontend.py")
            print("\n或者:")
            print("  streamlit run frontend.py --server.port=8501")
    else:
        print("⚠ 前端启动失败，请检查错误信息")
        print("您可以手动运行以下命令启动前端:")
        print(f"  cd {BASE_DIR}")
        print("  python run_frontend.py")
        print("\n或者:")
        print("  streamlit run frontend.py --server.port=8501")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n服务已停止")