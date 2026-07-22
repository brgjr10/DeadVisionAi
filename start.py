#!/usr/bin/env python3
"""
Startup script to run Dead Vision AI backend, frontend, Qdrant, and Redis concurrently.
"""
import subprocess
import sys
import os
import threading
import time
import signal
import socket

# Global variables to track processes
backend_process = None
frontend_process = None
qdrant_process = None
redis_process = None
llama_process = None

def is_port_in_use(port):
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return False
        except socket.error:
            return True

def run_redis():
    """Run Redis via Docker."""
    global redis_process
    print("[START] Starting Redis...")
    try:
        subprocess.run(["docker", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[WARNING] Docker not found. Please install Docker or start Redis manually.")
        print("[INFO] Continuing without Redis - caching will be unavailable.")
        return
    
    redis_process = subprocess.Popen([
        "docker", "run", "--rm",
        "-p", "6379:6379",
        "redis"
    ])
    redis_process.wait()

def run_qdrant():
    """Run Qdrant vector store via Docker."""
    global qdrant_process
    print("[START] Starting Qdrant Vector Store...")
    # Check if Docker is available
    try:
        subprocess.run(["docker", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[WARNING] Docker not found. Please install Docker or start Qdrant manually.")
        print("[INFO] Continuing without Qdrant - vector store will be unavailable.")
        return
    
    # Create storage directory if it doesn't exist
    storage_dir = os.path.join(os.path.dirname(__file__), "qdrant_storage")
    os.makedirs(storage_dir, exist_ok=True)
    
    # Run Qdrant via Docker
    qdrant_process = subprocess.Popen([
        "docker", "run", "--rm",
        "-p", "6333:6333",
        "-p", "6334:6334",
        "-v", f"{storage_dir}:/qdrant/storage",
        "qdrant/qdrant"
    ])
    qdrant_process.wait()

def run_llama():
    """Run the llama.cpp server."""
    global llama_process
    print("[START] Starting llama.cpp server...")
    llama_process = subprocess.Popen([
        "F:\\DeadVisionAi\\llama.cpp\\llama-server.exe",
        "-m", "F:\\DeadVisionAi\\llama.cpp\\Models\\Llama-3.2-3B-Instruct-Q4_K_S.gguf",
        "--host", "0.0.0.0",
        "--port", "8080",
        "--threads", "12",
        "-ngl", "32",
        "--ui-mcp-proxy"
    ])
    llama_process.wait()

def run_backend():
    """Run the backend server."""
    global backend_process
    print("[START] Starting Dead Vision AI Backend...")
    os.chdir(os.path.join(os.path.dirname(__file__), "backend"))
    backend_process = subprocess.Popen([sys.executable, "main.py"])
    backend_process.wait()

def run_frontend():
    """Run the frontend development server."""
    global frontend_process
    print("[START] Starting Dead Vision AI Frontend...")
    os.chdir(os.path.join(os.path.dirname(__file__), "frontend"))
    # On Windows, we need to use shell=True for npm commands
    if sys.platform == "win32":
        frontend_process = subprocess.Popen("npm run dev", shell=True)
    else:
        frontend_process = subprocess.Popen(["npm", "run", "dev"])
    frontend_process.wait()

def signal_handler(sig, frame):
    """Handle Ctrl+C to shutdown all processes."""
    print("\n[STOP] Shutting down Dead Vision AI...")
    if backend_process:
        backend_process.terminate()
    if frontend_process:
        frontend_process.terminate()
    if qdrant_process:
        qdrant_process.terminate()
    if redis_process:
        redis_process.terminate()
    if llama_process:
        llama_process.terminate()
    sys.exit(0)

if __name__ == "__main__":
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("[INFO] Dead Vision AI - Starting Full Stack")
    print("=" * 50)
    print("[INFO] Backend will run on: http://localhost:8000")
    print("[INFO] Frontend will run on: http://localhost:3000")
    print("[INFO] Qdrant will run on: http://localhost:6333")
    print("[INFO] Redis will run on: localhost:6379")
    print("[INFO] llama.cpp server will run on: http://localhost:8080")
    print("=" * 50)
    
    # Check if Qdrant is already running on port 6333
    if is_port_in_use(6333):
        print("[INFO] Qdrant already running on port 6333, skipping Qdrant startup")
        qdrant_process = None  # No process to manage
    else:
        # Start Qdrant in a separate thread
        qdrant_thread = threading.Thread(target=run_qdrant)
        qdrant_thread.daemon = True  # Daemon thread will be killed when main exits
        qdrant_thread.start()
        
        # Give Qdrant time to start
        time.sleep(3)
    
    # Check if Redis is already running on port 6379
    if is_port_in_use(6379):
        print("[INFO] Redis already running on port 6379, skipping Redis startup")
        redis_process = None  # No process to manage
    else:
        # Start Redis in a separate thread
        redis_thread = threading.Thread(target=run_redis)
        redis_thread.daemon = True  # Daemon thread will be killed when main exits
        redis_thread.start()
        
        # Give Redis time to start
        time.sleep(3)
    
    # Check if llama.cpp server is already running on port 8080
    if is_port_in_use(8080):
        print("[INFO] llama.cpp server already running on port 8080, skipping llama.cpp startup")
        llama_process = None  # No process to manage
    else:
        # Start llama.cpp server in a separate thread
        llama_thread = threading.Thread(target=run_llama)
        llama_thread.daemon = True  # Daemon thread will be killed when main exits
        llama_thread.start()
        
        # Give llama.cpp time to start
        time.sleep(3)
    
    # Check if backend is already running on port 8000
    if is_port_in_use(8000):
        print("[INFO] Backend already running on port 8000, skipping backend startup")
        backend_process = None  # No process to manage
    else:
        # Start backend in a separate thread
        backend_thread = threading.Thread(target=run_backend)
        backend_thread.daemon = True  # Daemon thread will be killed when main exits
        backend_thread.start()
        
        # Give backend time to start
        time.sleep(3)
    
    # Start frontend in main thread and wait for it
    try:
        run_frontend()
    except KeyboardInterrupt:
        print("\n[STOP] Shutting down Dead Vision AI...")
        if backend_process:
            backend_process.terminate()
        if frontend_process:
            frontend_process.terminate()
        if qdrant_process:
            qdrant_process.terminate()
        if redis_process:
            redis_process.terminate()
        if llama_process:
            llama_process.terminate()
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Failed to start servers: {e}")
        if backend_process:
            backend_process.terminate()
        if frontend_process:
            frontend_process.terminate()
        if qdrant_process:
            qdrant_process.terminate()
        if redis_process:
            redis_process.terminate()
        if llama_process:
            llama_process.terminate()
        sys.exit(1)