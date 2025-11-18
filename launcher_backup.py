# Author: eddy

import threading
import subprocess
import sys
import os
import json
import time
import platform
import psutil
import webbrowser
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request
from datetime import datetime
from collections import deque
from typing import Dict, List, Any, Optional

try:
    import webview
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False

try:
    import GPUtil
    HAS_GPU_UTIL = True
except ImportError:
    HAS_GPU_UTIL = False

flask_app = Flask(__name__)
flask_app.config['SECRET_KEY'] = 'fuxkcomfy_launcher_enhanced_2024'

class ConfigManager:
    def __init__(self, config_file: str = "launcher_config.json"):
        self.config_file = Path(config_file)
        self.presets_file = Path("launcher_presets.json")
        self.history_file = Path("launcher_history.json")
        self.default_config = {
            "port": "8188",
            "listen": "0.0.0.0",
            "auto_launch": True,
            "gpu_opt": True,
            "cpu_mode": False,
            "lowvram": False,
            "highvram": False,
            "normalvram": False,
            "novram": False,
            "fp16_vae": False,
            "fp32_vae": False,
            "bf16_unet": False,
            "fp16_unet": False,
            "fp8_e4m3fn_unet": False,
            "fp8_e5m2_unet": False,
            "disable_smart_memory": False,
            "deterministic": False,
            "dont_upcast_attention": False,
            "force_upcast_attention": False,
            "disable_xformers": False,
            "use_pytorch_cross_attention": False,
            "directml": False,
            "preview_method": "auto",
            "extra_args": "",
            "language": "zh",
            "theme": "dark",
            "auto_restart": False,
            "max_restart_attempts": 3,
            "log_level": "all"
        }

    def load(self) -> Dict[str, Any]:
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return {**self.default_config, **config}
            except Exception:
                pass
        return self.default_config.copy()

    def save(self, config: Dict[str, Any]) -> bool:
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def load_presets(self) -> Dict[str, Dict[str, Any]]:
        if self.presets_file.exists():
            try:
                with open(self.presets_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "default": self.default_config.copy(),
            "performance": {
                "port": "8188",
                "listen": "0.0.0.0",
                "auto_launch": False,
                "gpu_opt": True,
                "cpu_mode": False,
                "lowvram": False,
                "highvram": True,
                "normalvram": False,
                "extra_args": "--preview-method auto --cache-lru 32",
                "theme": "dark",
                "auto_restart": False,
                "max_restart_attempts": 3,
                "log_level": "all"
            },
            "low_memory": {
                "port": "8188",
                "listen": "0.0.0.0",
                "auto_launch": False,
                "gpu_opt": True,
                "cpu_mode": False,
                "lowvram": True,
                "highvram": False,
                "normalvram": False,
                "extra_args": "--cache-lru 8",
                "theme": "dark",
                "auto_restart": False,
                "max_restart_attempts": 3,
                "log_level": "all"
            }
        }

    def save_presets(self, presets: Dict[str, Dict[str, Any]]) -> bool:
        try:
            with open(self.presets_file, 'w', encoding='utf-8') as f:
                json.dump(presets, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def load_history(self) -> List[Dict[str, Any]]:
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                    return history[-50:]
            except Exception:
                pass
        return []

    def save_history(self, history: List[Dict[str, Any]]) -> bool:
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history[-50:], f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

class SystemMonitor:
    def __init__(self):
        self.process_pid = None

    def get_cpu_usage(self) -> float:
        try:
            return psutil.cpu_percent(interval=0.1)
        except Exception:
            return 0.0

    def get_memory_usage(self) -> Dict[str, Any]:
        try:
            mem = psutil.virtual_memory()
            return {
                "percent": mem.percent,
                "used_gb": round(mem.used / (1024**3), 2),
                "total_gb": round(mem.total / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2)
            }
        except Exception:
            return {"percent": 0, "used_gb": 0, "total_gb": 0, "available_gb": 0}

    def get_gpu_usage(self) -> List[Dict[str, Any]]:
        if not HAS_GPU_UTIL:
            return []
        try:
            gpus = GPUtil.getGPUs()
            return [{
                "id": gpu.id,
                "name": gpu.name,
                "load": round(gpu.load * 100, 1),
                "memory_used": round(gpu.memoryUsed / 1024, 2),
                "memory_total": round(gpu.memoryTotal / 1024, 2),
                "memory_percent": round((gpu.memoryUsed / gpu.memoryTotal) * 100, 1),
                "temperature": gpu.temperature
            } for gpu in gpus]
        except Exception:
            return []

    def get_process_info(self) -> Optional[Dict[str, Any]]:
        if not self.process_pid:
            return None
        try:
            proc = psutil.Process(self.process_pid)
            return {
                "cpu_percent": proc.cpu_percent(interval=0.1),
                "memory_mb": round(proc.memory_info().rss / (1024**2), 2),
                "status": proc.status(),
                "create_time": proc.create_time(),
                "num_threads": proc.num_threads()
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    def get_system_info(self) -> Dict[str, Any]:
        return {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "python_version": sys.version,
            "cpu_count": psutil.cpu_count(),
            "cpu_freq": psutil.cpu_freq().current if psutil.cpu_freq() else 0,
            "total_memory_gb": round(psutil.virtual_memory().total / (1024**3), 2)
        }

class LogEntry:
    def __init__(self, message: str, level: str = "info"):
        self.timestamp = datetime.now()
        self.message = message
        self.level = level

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.strftime("%H:%M:%S.%f")[:-3],
            "message": self.message,
            "level": self.level
        }

class FuxkComfyLauncher:
    def __init__(self):
        self.process = None
        self.is_running = False
        self.config_manager = ConfigManager()
        self.system_monitor = SystemMonitor()
        self.config = self.config_manager.load()
        self.presets = self.config_manager.load_presets()
        self.history = self.config_manager.load_history()
        self.logs = deque(maxlen=2000)
        self.restart_attempts = 0
        self.last_crash_time = None
        self.start_time = None

    def get_config_value(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def update_config(self, updates: Dict[str, Any]) -> bool:
        self.config.update(updates)
        return self.config_manager.save(self.config)

    def build_command(self) -> List[str]:
        cmd = [sys.executable, "main.py"]
        cmd.extend(["--port", self.get_config_value("port", "8188")])
        cmd.extend(["--listen", self.get_config_value("listen", "0.0.0.0")])

        if self.get_config_value("auto_launch", True):
            cmd.append("--auto-launch")
        if self.get_config_value("cpu_mode", False):
            cmd.append("--cpu")
        if not self.get_config_value("gpu_opt", True):
            cmd.append("--disable-gpu-optimization")
        if self.get_config_value("lowvram", False):
            cmd.append("--lowvram")
        if self.get_config_value("highvram", False):
            cmd.append("--highvram")
        if self.get_config_value("normalvram", False):
            cmd.append("--normalvram")
        if self.get_config_value("novram", False):
            cmd.append("--novram")
        if self.get_config_value("fp16_vae", False):
            cmd.append("--fp16-vae")
        if self.get_config_value("fp32_vae", False):
            cmd.append("--fp32-vae")
        if self.get_config_value("bf16_unet", False):
            cmd.append("--bf16-unet")
        if self.get_config_value("fp16_unet", False):
            cmd.append("--fp16-unet")
        if self.get_config_value("fp8_e4m3fn_unet", False):
            cmd.append("--fp8_e4m3fn-unet")
        if self.get_config_value("fp8_e5m2_unet", False):
            cmd.append("--fp8_e5m2-unet")
        if self.get_config_value("disable_smart_memory", False):
            cmd.append("--disable-smart-memory")
        if self.get_config_value("deterministic", False):
            cmd.append("--deterministic")
        if self.get_config_value("dont_upcast_attention", False):
            cmd.append("--dont-upcast-attention")
        if self.get_config_value("force_upcast_attention", False):
            cmd.append("--force-upcast-attention")
        if self.get_config_value("disable_xformers", False):
            cmd.append("--disable-xformers")
        if self.get_config_value("use_pytorch_cross_attention", False):
            cmd.append("--use-pytorch-cross-attention")
        if self.get_config_value("directml", False):
            cmd.append("--directml")

        preview_method = self.get_config_value("preview_method", "auto")
        if preview_method and preview_method != "auto":
            cmd.extend(["--preview-method", preview_method])

        extra_args = self.get_config_value("extra_args", "")
        if extra_args:
            cmd.extend(extra_args.split())

        return cmd

    def log_message(self, message: str, level: str = "info"):
        entry = LogEntry(message, level)
        self.logs.append(entry)

    def start_fuxkcomfy(self) -> Dict[str, Any]:
        if self.is_running:
            return {"success": False, "message": "Process already running"}

        try:
            cmd = self.build_command()
            cmd_str = ' '.join(cmd)
            self.log_message(f"Starting: {cmd_str}", "info")

            self.history.append({
                "timestamp": datetime.now().isoformat(),
                "command": cmd_str,
                "config": self.config.copy()
            })
            self.config_manager.save_history(self.history)

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                cwd=os.getcwd()
            )

            self.is_running = True
            self.start_time = time.time()
            self.system_monitor.process_pid = self.process.pid
            self.restart_attempts = 0

            threading.Thread(target=self.read_output, daemon=True).start()
            threading.Thread(target=self.monitor_health, daemon=True).start()

            self.log_message(f"Process started successfully (PID: {self.process.pid})", "success")
            return {"success": True, "message": "Process started successfully", "pid": self.process.pid}

        except Exception as e:
            self.log_message(f"Failed to start process: {str(e)}", "error")
            return {"success": False, "message": f"Start failed: {str(e)}"}

    def stop_fuxkcomfy(self, force: bool = False) -> Dict[str, Any]:
        if not self.is_running or self.process is None:
            return {"success": False, "message": "Process not running"}

        try:
            self.log_message("Stopping process...", "warning")

            if force:
                self.process.kill()
                self.log_message("Process force killed", "warning")
            else:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                    self.log_message("Process terminated gracefully", "info")
                except subprocess.TimeoutExpired:
                    self.log_message("Graceful shutdown timeout, force killing...", "warning")
                    self.process.kill()
                    self.log_message("Process force killed", "warning")

            self.is_running = False
            self.system_monitor.process_pid = None
            self.start_time = None

            return {"success": True, "message": "Process stopped"}

        except Exception as e:
            self.log_message(f"Error stopping process: {str(e)}", "error")
            return {"success": False, "message": f"Stop failed: {str(e)}"}

    def restart_fuxkcomfy(self) -> Dict[str, Any]:
        self.log_message("Restarting process...", "info")
        stop_result = self.stop_fuxkcomfy()
        if stop_result["success"]:
            time.sleep(2)
            return self.start_fuxkcomfy()
        return stop_result

    def read_output(self):
        try:
            for line in iter(self.process.stdout.readline, ''):
                if line:
                    line = line.strip()
                    level = "info"

                    line_lower = line.lower()
                    if "error" in line_lower or "exception" in line_lower or "failed" in line_lower:
                        level = "error"
                    elif "warning" in line_lower or "warn" in line_lower:
                        level = "warning"
                    elif "success" in line_lower or "ready" in line_lower or "started" in line_lower:
                        level = "success"

                    self.log_message(line, level)

            self.process.wait()
            exit_code = self.process.returncode
            self.is_running = False
            self.system_monitor.process_pid = None

            if exit_code == 0:
                self.log_message(f"Process exited normally (code: {exit_code})", "success")
            else:
                self.log_message(f"Process exited with error code: {exit_code}", "error")
                self.last_crash_time = time.time()

        except Exception as e:
            self.log_message(f"Output reader error: {str(e)}", "error")

    def monitor_health(self):
        while self.is_running:
            time.sleep(5)
            if self.process and self.process.poll() is not None:
                if self.get_config_value("auto_restart", False):
                    max_attempts = self.get_config_value("max_restart_attempts", 3)
                    if self.restart_attempts < max_attempts:
                        self.restart_attempts += 1
                        self.log_message(f"Auto-restart attempt {self.restart_attempts}/{max_attempts}", "warning")
                        time.sleep(3)
                        self.start_fuxkcomfy()
                    else:
                        self.log_message(f"Max restart attempts ({max_attempts}) reached, giving up", "error")
                        self.is_running = False
                break

    def clear_logs(self):
        self.logs.clear()
        self.log_message("Logs cleared", "info")

    def get_logs(self, level_filter: str = "all", search: str = "", limit: int = 200) -> List[Dict[str, Any]]:
        filtered_logs = []

        for log in self.logs:
            if level_filter != "all" and log.level != level_filter:
                continue
            if search and search.lower() not in log.message.lower():
                continue
            filtered_logs.append(log.to_dict())

        return filtered_logs[-limit:]

    def get_uptime(self) -> Optional[str]:
        if not self.start_time:
            return None
        uptime_seconds = int(time.time() - self.start_time)
        hours = uptime_seconds // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

launcher = FuxkComfyLauncher()

@flask_app.route('/')
def index():
    return render_template_string(WEB_TEMPLATE)

@flask_app.route('/api/status')
def status():
    uptime = launcher.get_uptime()
    process_info = launcher.system_monitor.get_process_info()

    return jsonify({
        'running': launcher.is_running,
        'config': launcher.config,
        'uptime': uptime,
        'process_info': process_info,
        'restart_attempts': launcher.restart_attempts,
        'pid': launcher.process.pid if launcher.process else None
    })

@flask_app.route('/api/system')
def system_status():
    return jsonify({
        'cpu': launcher.system_monitor.get_cpu_usage(),
        'memory': launcher.system_monitor.get_memory_usage(),
        'gpu': launcher.system_monitor.get_gpu_usage(),
        'info': launcher.system_monitor.get_system_info()
    })

@flask_app.route('/api/logs')
def get_logs():
    level_filter = request.args.get('level', 'all')
    search = request.args.get('search', '')
    limit = int(request.args.get('limit', 200))
    logs = launcher.get_logs(level_filter, search, limit)
    return jsonify({'logs': logs})

@flask_app.route('/api/logs/clear', methods=['POST'])
def clear_logs():
    launcher.clear_logs()
    return jsonify({'success': True})

@flask_app.route('/api/config', methods=['POST'])
def update_config():
    data = request.json
    success = launcher.update_config(data)
    return jsonify({'success': success})

@flask_app.route('/api/presets')
def get_presets():
    return jsonify({'presets': launcher.presets})

@flask_app.route('/api/presets', methods=['POST'])
def save_preset():
    data = request.json
    preset_name = data.get('name')
    preset_config = data.get('config')
    if preset_name and preset_config:
        launcher.presets[preset_name] = preset_config
        success = launcher.config_manager.save_presets(launcher.presets)
        return jsonify({'success': success})
    return jsonify({'success': False, 'message': 'Invalid preset data'})

@flask_app.route('/api/presets/<name>', methods=['DELETE'])
def delete_preset(name):
    if name in launcher.presets and name != 'default':
        del launcher.presets[name]
        success = launcher.config_manager.save_presets(launcher.presets)
        return jsonify({'success': success})
    return jsonify({'success': False, 'message': 'Cannot delete default preset'})

@flask_app.route('/api/history')
def get_history():
    return jsonify({'history': launcher.history})

@flask_app.route('/api/start', methods=['POST'])
def start():
    result = launcher.start_fuxkcomfy()
    return jsonify(result)

@flask_app.route('/api/stop', methods=['POST'])
def stop():
    force = request.json.get('force', False) if request.json else False
    result = launcher.stop_fuxkcomfy(force)
    return jsonify(result)

@flask_app.route('/api/restart', methods=['POST'])
def restart():
    result = launcher.restart_fuxkcomfy()
    return jsonify(result)

WEB_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FuxkComfy Launcher Pro</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --bg-primary: #0a0e1a;
            --bg-secondary: #0f1419;
            --bg-tertiary: #1a1f2e;
            --bg-elevated: #151b28;
            --border-color: #1e3a5f;
            --border-hover: #2563eb;
            --text-primary: #e5e7eb;
            --text-secondary: #9ca3af;
            --text-muted: #6b7280;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-yellow: #f59e0b;
            --accent-purple: #8b5cf6;
            --shadow-sm: 0 2px 8px rgba(0,0,0,0.3);
            --shadow-md: 0 4px 16px rgba(0,0,0,0.4);
            --shadow-lg: 0 8px 24px rgba(0,0,0,0.5);
        }

        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.85);
            backdrop-filter: blur(8px);
            z-index: 9999;
            animation: fadeIn 0.2s ease;
        }

        .modal-overlay.active {
            display: flex;
            align-items: center;
            justify-content: center;
        }

        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        @keyframes boomIn {
            0% {
                transform: scale(0.3) rotate(-5deg);
                opacity: 0;
            }
            50% {
                transform: scale(1.05) rotate(2deg);
            }
            100% {
                transform: scale(1) rotate(0deg);
                opacity: 1;
            }
        }

        .modal {
            background: var(--bg-secondary);
            border: 2px solid var(--border-color);
            border-radius: 16px;
            padding: 0;
            min-width: 400px;
            max-width: 500px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.8);
            animation: boomIn 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            overflow: hidden;
        }

        .modal-header {
            padding: 20px 24px;
            background: linear-gradient(135deg, var(--bg-tertiary), var(--bg-elevated));
            border-bottom: 1px solid var(--border-color);
        }

        .modal-title {
            font-size: 18px;
            font-weight: 600;
            color: var(--text-primary);
        }

        .modal-body {
            padding: 24px;
        }

        .modal-message {
            font-size: 15px;
            color: var(--text-secondary);
            line-height: 1.6;
            margin-bottom: 24px;
        }

        .modal-input {
            width: 100%;
            padding: 10px 14px;
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: var(--text-primary);
            font-size: 14px;
            margin-bottom: 20px;
            transition: all 0.2s;
        }

        .modal-input:focus {
            outline: none;
            border-color: var(--accent-blue);
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }

        .modal-actions {
            display: flex;
            gap: 12px;
            justify-content: flex-end;
        }

        .modal-btn {
            padding: 10px 24px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid transparent;
        }

        .modal-btn-cancel {
            background: var(--bg-elevated);
            color: var(--text-primary);
            border-color: var(--border-color);
        }

        .modal-btn-cancel:hover {
            background: var(--bg-tertiary);
            border-color: var(--border-hover);
        }

        .modal-btn-confirm {
            background: var(--accent-blue);
            color: white;
            border-color: var(--accent-blue);
        }

        .modal-btn-confirm:hover {
            background: #2563eb;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
        }

        .modal-btn-danger {
            background: var(--accent-red);
            color: white;
            border-color: var(--accent-red);
        }

        .modal-btn-danger:hover {
            background: #dc2626;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4);
        }

        .lang-switcher {
            background: var(--bg-elevated);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 4px 12px;
            color: var(--text-secondary);
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s;
        }

        .lang-switcher:hover {
            border-color: var(--accent-blue);
            color: var(--text-primary);
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            overflow: hidden;
        }

        .app-container {
            display: grid;
            grid-template-rows: auto 1fr;
            height: 100vh;
        }

        .header {
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-color);
            padding: 16px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: var(--shadow-sm);
        }

        .header-left {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .logo {
            font-size: 20px;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: 0.5px;
        }

        .status-indicator {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 500;
            background: var(--bg-elevated);
            border: 1px solid var(--border-color);
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }

        .status-running .status-dot {
            background: var(--accent-green);
            box-shadow: 0 0 8px var(--accent-green);
        }

        .status-stopped .status-dot {
            background: var(--accent-red);
            animation: none;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .header-right {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .uptime {
            font-family: 'Courier New', monospace;
            color: var(--text-secondary);
            font-size: 13px;
        }

        .main-content {
            display: grid;
            grid-template-columns: 320px 1fr 280px;
            gap: 16px;
            padding: 16px;
            height: calc(100vh - 64px);
            overflow: hidden;
        }

        .panel {
            background: var(--bg-secondary);
            border-radius: 12px;
            border: 1px solid var(--border-color);
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }

        .panel-header {
            padding: 14px 18px;
            background: var(--bg-tertiary);
            border-bottom: 1px solid var(--border-color);
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-secondary);
        }

        .panel-content {
            flex: 1;
            overflow-y: auto;
            padding: 16px;
        }

        .form-group {
            margin-bottom: 16px;
        }

        .form-label {
            display: block;
            font-size: 13px;
            font-weight: 500;
            margin-bottom: 6px;
            color: var(--text-primary);
        }

        .form-input,
        .form-select,
        .form-textarea {
            width: 100%;
            padding: 8px 12px;
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            color: var(--text-primary);
            font-size: 14px;
            transition: all 0.2s;
        }

        .form-input:focus,
        .form-select:focus,
        .form-textarea:focus {
            outline: none;
            border-color: var(--accent-blue);
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }

        .form-textarea {
            resize: vertical;
            min-height: 60px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
        }

        .checkbox-group {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 10px;
        }

        .checkbox-input {
            width: 18px;
            height: 18px;
            cursor: pointer;
            accent-color: var(--accent-blue);
        }

        .checkbox-label {
            font-size: 14px;
            cursor: pointer;
            user-select: none;
        }

        .btn {
            padding: 10px 18px;
            background: var(--bg-elevated);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            color: var(--text-primary);
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }

        .btn:hover {
            background: var(--bg-tertiary);
            border-color: var(--border-hover);
        }

        .btn:active {
            transform: translateY(1px);
        }

        .btn-primary {
            background: var(--accent-blue);
            border-color: var(--accent-blue);
            color: white;
        }

        .btn-primary:hover {
            background: #2563eb;
            border-color: #2563eb;
        }

        .btn-success {
            background: var(--accent-green);
            border-color: var(--accent-green);
            color: white;
        }

        .btn-danger {
            background: var(--accent-red);
            border-color: var(--accent-red);
            color: white;
        }

        .btn-group {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
            margin-top: 16px;
        }

        .section-divider {
            margin: 20px 0;
            border: 0;
            border-top: 1px solid var(--border-color);
        }

        .preset-item {
            padding: 10px;
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            cursor: pointer;
            transition: all 0.2s;
        }

        .preset-item:hover {
            border-color: var(--accent-blue);
            background: var(--bg-elevated);
        }

        .preset-name {
            font-weight: 500;
            font-size: 14px;
        }

        .logs-container {
            flex: 1;
            background: var(--bg-primary);
            border-radius: 6px;
            padding: 12px;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            overflow-y: auto;
            line-height: 1.5;
        }

        .log-entry {
            margin: 2px 0;
            padding: 2px 0;
        }

        .log-timestamp {
            color: var(--text-muted);
            margin-right: 8px;
        }

        .log-info { color: var(--text-secondary); }
        .log-success { color: var(--accent-green); }
        .log-warning { color: var(--accent-yellow); }
        .log-error { color: var(--accent-red); }

        .log-controls {
            display: flex;
            gap: 8px;
            padding: 12px;
            background: var(--bg-tertiary);
            border-top: 1px solid var(--border-color);
        }

        .log-filter {
            flex: 1;
        }

        .stats-grid {
            display: grid;
            gap: 12px;
        }

        .stat-card {
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 12px;
        }

        .stat-label {
            font-size: 12px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }

        .stat-value {
            font-size: 20px;
            font-weight: 600;
            color: var(--text-primary);
        }

        .stat-bar {
            height: 4px;
            background: var(--bg-tertiary);
            border-radius: 2px;
            margin-top: 8px;
            overflow: hidden;
        }

        .stat-bar-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--accent-blue), var(--accent-purple));
            transition: width 0.3s;
        }

        .gpu-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .gpu-card {
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 10px;
        }

        .gpu-name {
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 8px;
            color: var(--text-primary);
        }

        .gpu-stat {
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            margin: 4px 0;
            color: var(--text-secondary);
        }

        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }

        ::-webkit-scrollbar-track {
            background: var(--bg-primary);
        }

        ::-webkit-scrollbar-thumb {
            background: var(--bg-tertiary);
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: var(--border-color);
        }

        .tab-container {
            display: flex;
            gap: 4px;
            padding: 0 16px;
            background: var(--bg-tertiary);
            border-bottom: 1px solid var(--border-color);
        }

        .tab {
            padding: 10px 16px;
            background: transparent;
            border: none;
            color: var(--text-secondary);
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
        }

        .tab:hover {
            color: var(--text-primary);
        }

        .tab.active {
            color: var(--accent-blue);
            border-bottom-color: var(--accent-blue);
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
        }
    </style>
</head>
<body>
    <div class="app-container">
        <div class="header">
            <div class="header-left">
                <div class="logo">FuxkComfy Launcher Pro</div>
                <div class="status-indicator" id="statusIndicator">
                    <div class="status-dot"></div>
                    <span id="statusText">Loading...</span>
                </div>
            </div>
            <div class="header-right">
                <div class="uptime" id="uptime">--:--:--</div>
                <button class="btn btn-success" onclick="startProcess()" id="startBtn">Start</button>
                <button class="btn btn-danger" onclick="stopProcess()" id="stopBtn">Stop</button>
                <button class="btn" onclick="restartProcess()" id="restartBtn">Restart</button>
            </div>
        </div>

        <div class="main-content">
            <div class="panel">
                <div class="tab-container">
                    <button class="tab active" onclick="switchTab('config')">Config</button>
                    <button class="tab" onclick="switchTab('presets')">Presets</button>
                </div>

                <div class="panel-content">
                    <div class="tab-content active" id="tab-config">
                        <div class="form-group">
                            <label class="form-label">Port</label>
                            <input type="number" class="form-input" id="port" min="1" max="65535" value="8188">
                        </div>

                        <div class="form-group">
                            <label class="form-label">Listen Address</label>
                            <input type="text" class="form-input" id="listen" value="0.0.0.0">
                        </div>

                        <hr class="section-divider">

                        <div class="checkbox-group">
                            <input type="checkbox" class="checkbox-input" id="autoLaunch" checked>
                            <label class="checkbox-label" for="autoLaunch">Auto launch browser</label>
                        </div>

                        <div class="checkbox-group">
                            <input type="checkbox" class="checkbox-input" id="gpuOpt" checked>
                            <label class="checkbox-label" for="gpuOpt">GPU optimization</label>
                        </div>

                        <div class="checkbox-group">
                            <input type="checkbox" class="checkbox-input" id="cpuMode">
                            <label class="checkbox-label" for="cpuMode">CPU mode</label>
                        </div>

                        <div class="checkbox-group">
                            <input type="checkbox" class="checkbox-input" id="lowvram">
                            <label class="checkbox-label" for="lowvram">Low VRAM</label>
                        </div>

                        <div class="checkbox-group">
                            <input type="checkbox" class="checkbox-input" id="highvram">
                            <label class="checkbox-label" for="highvram">High VRAM</label>
                        </div>

                        <div class="checkbox-group">
                            <input type="checkbox" class="checkbox-input" id="autoRestart">
                            <label class="checkbox-label" for="autoRestart">Auto restart on crash</label>
                        </div>

                        <hr class="section-divider">

                        <div class="form-group">
                            <label class="form-label">Extra Arguments</label>
                            <textarea class="form-textarea" id="extraArgs" placeholder="--preview-method auto --cache-lru 32"></textarea>
                        </div>

                        <div class="btn-group">
                            <button class="btn btn-primary" onclick="saveConfig()">Save Config</button>
                            <button class="btn" onclick="openComfy()">Open UI</button>
                        </div>
                    </div>

                    <div class="tab-content" id="tab-presets">
                        <div id="presetsList"></div>
                        <div class="btn-group">
                            <button class="btn btn-primary" onclick="saveAsPreset()">Save as Preset</button>
                        </div>
                    </div>
                </div>
            </div>

            <div class="panel">
                <div class="tab-container">
                    <button class="tab active" onclick="switchLogTab('all')">All</button>
                    <button class="tab" onclick="switchLogTab('error')">Errors</button>
                    <button class="tab" onclick="switchLogTab('warning')">Warnings</button>
                    <button class="tab" onclick="switchLogTab('success')">Success</button>
                </div>

                <div class="panel-content" style="padding: 0; overflow: hidden; display: flex; flex-direction: column;">
                    <div class="logs-container" id="logs"></div>
                    <div class="log-controls">
                        <input type="text" class="form-input log-filter" id="logSearch" placeholder="Search logs...">
                        <button class="btn" onclick="clearLogs()">Clear</button>
                    </div>
                </div>
            </div>

            <div class="panel">
                <div class="panel-header">System Monitor</div>
                <div class="panel-content">
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-label">CPU Usage</div>
                            <div class="stat-value" id="cpuValue">0%</div>
                            <div class="stat-bar">
                                <div class="stat-bar-fill" id="cpuBar" style="width: 0%"></div>
                            </div>
                        </div>

                        <div class="stat-card">
                            <div class="stat-label">Memory</div>
                            <div class="stat-value" id="memValue">0 GB</div>
                            <div class="stat-bar">
                                <div class="stat-bar-fill" id="memBar" style="width: 0%"></div>
                            </div>
                        </div>

                        <div id="gpuSection"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentLogLevel = 'all';
        let currentTab = 'config';

        function switchTab(tab) {
            currentTab = tab;
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('tab-' + tab).classList.add('active');

            if (tab === 'presets') {
                loadPresets();
            }
        }

        function switchLogTab(level) {
            currentLogLevel = level;
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            updateLogs();
        }

        function updateStatus() {
            fetch('/api/status')
                .then(res => res.json())
                .then(data => {
                    const indicator = document.getElementById('statusIndicator');
                    const statusText = document.getElementById('statusText');

                    if (data.running) {
                        indicator.className = 'status-indicator status-running';
                        statusText.textContent = 'Running';
                    } else {
                        indicator.className = 'status-indicator status-stopped';
                        statusText.textContent = 'Stopped';
                    }

                    document.getElementById('uptime').textContent = data.uptime || '--:--:--';

                    if (data.config) {
                        document.getElementById('port').value = data.config.port;
                        document.getElementById('listen').value = data.config.listen;
                        document.getElementById('autoLaunch').checked = data.config.auto_launch;
                        document.getElementById('gpuOpt').checked = data.config.gpu_opt;
                        document.getElementById('cpuMode').checked = data.config.cpu_mode;
                        document.getElementById('lowvram').checked = data.config.lowvram;
                        document.getElementById('highvram').checked = data.config.highvram || false;
                        document.getElementById('autoRestart').checked = data.config.auto_restart || false;
                        document.getElementById('extraArgs').value = data.config.extra_args || '';
                    }
                });
        }

        function updateSystemMonitor() {
            fetch('/api/system')
                .then(res => res.json())
                .then(data => {
                    document.getElementById('cpuValue').textContent = data.cpu.toFixed(1) + '%';
                    document.getElementById('cpuBar').style.width = data.cpu + '%';

                    const mem = data.memory;
                    document.getElementById('memValue').textContent = mem.used_gb + ' / ' + mem.total_gb + ' GB';
                    document.getElementById('memBar').style.width = mem.percent + '%';

                    const gpuSection = document.getElementById('gpuSection');
                    if (data.gpu && data.gpu.length > 0) {
                        gpuSection.innerHTML = '<div class="gpu-list">' + data.gpu.map(gpu => `
                            <div class="gpu-card">
                                <div class="gpu-name">${gpu.name}</div>
                                <div class="gpu-stat">
                                    <span>Load:</span>
                                    <span>${gpu.load}%</span>
                                </div>
                                <div class="gpu-stat">
                                    <span>Memory:</span>
                                    <span>${gpu.memory_used} / ${gpu.memory_total} GB</span>
                                </div>
                                <div class="gpu-stat">
                                    <span>Temp:</span>
                                    <span>${gpu.temperature}°C</span>
                                </div>
                            </div>
                        `).join('') + '</div>';
                    } else {
                        gpuSection.innerHTML = '<div class="stat-card"><div class="stat-label">No GPU detected</div></div>';
                    }
                });
        }

        function updateLogs() {
            const search = document.getElementById('logSearch').value;
            fetch(`/api/logs?level=${currentLogLevel}&search=${encodeURIComponent(search)}`)
                .then(res => res.json())
                .then(data => {
                    const logsDiv = document.getElementById('logs');
                    logsDiv.innerHTML = data.logs.map(log =>
                        `<div class="log-entry log-${log.level}"><span class="log-timestamp">[${log.timestamp}]</span>${log.message}</div>`
                    ).join('');
                    logsDiv.scrollTop = logsDiv.scrollHeight;
                });
        }

        function saveConfig() {
            const config = {
                port: document.getElementById('port').value,
                listen: document.getElementById('listen').value,
                auto_launch: document.getElementById('autoLaunch').checked,
                gpu_opt: document.getElementById('gpuOpt').checked,
                cpu_mode: document.getElementById('cpuMode').checked,
                lowvram: document.getElementById('lowvram').checked,
                highvram: document.getElementById('highvram').checked,
                auto_restart: document.getElementById('autoRestart').checked,
                extra_args: document.getElementById('extraArgs').value
            };

            fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            }).then(() => updateStatus());
        }

        function startProcess() {
            saveConfig();
            setTimeout(() => {
                fetch('/api/start', { method: 'POST' })
                    .then(res => res.json())
                    .then(() => setTimeout(updateStatus, 500));
            }, 300);
        }

        function stopProcess() {
            if (confirm('Stop FuxkComfy process?')) {
                fetch('/api/stop', { method: 'POST' })
                    .then(res => res.json())
                    .then(() => setTimeout(updateStatus, 500));
            }
        }

        function restartProcess() {
            if (confirm('Restart FuxkComfy process?')) {
                fetch('/api/restart', { method: 'POST' })
                    .then(res => res.json())
                    .then(() => setTimeout(updateStatus, 500));
            }
        }

        function clearLogs() {
            fetch('/api/logs/clear', { method: 'POST' })
                .then(() => updateLogs());
        }

        function openComfy() {
            const port = document.getElementById('port').value;
            window.open(`http://127.0.0.1:${port}`, '_blank');
        }

        function loadPresets() {
            fetch('/api/presets')
                .then(res => res.json())
                .then(data => {
                    const list = document.getElementById('presetsList');
                    list.innerHTML = Object.keys(data.presets).map(name => `
                        <div class="preset-item" onclick="applyPreset('${name}')">
                            <span class="preset-name">${name}</span>
                            ${name !== 'default' ? `<button class="btn btn-danger" onclick="event.stopPropagation(); deletePreset('${name}')" style="padding: 4px 10px; font-size: 12px;">Delete</button>` : ''}
                        </div>
                    `).join('');
                });
        }

        function applyPreset(name) {
            fetch('/api/presets')
                .then(res => res.json())
                .then(data => {
                    const preset = data.presets[name];
                    if (preset) {
                        document.getElementById('port').value = preset.port;
                        document.getElementById('listen').value = preset.listen;
                        document.getElementById('autoLaunch').checked = preset.auto_launch;
                        document.getElementById('gpuOpt').checked = preset.gpu_opt;
                        document.getElementById('cpuMode').checked = preset.cpu_mode;
                        document.getElementById('lowvram').checked = preset.lowvram;
                        document.getElementById('highvram').checked = preset.highvram || false;
                        document.getElementById('autoRestart').checked = preset.auto_restart || false;
                        document.getElementById('extraArgs').value = preset.extra_args || '';
                        saveConfig();
                        switchTab('config');
                    }
                });
        }

        function saveAsPreset() {
            const name = prompt('Enter preset name:');
            if (name) {
                const config = {
                    port: document.getElementById('port').value,
                    listen: document.getElementById('listen').value,
                    auto_launch: document.getElementById('autoLaunch').checked,
                    gpu_opt: document.getElementById('gpuOpt').checked,
                    cpu_mode: document.getElementById('cpuMode').checked,
                    lowvram: document.getElementById('lowvram').checked,
                    highvram: document.getElementById('highvram').checked,
                    auto_restart: document.getElementById('autoRestart').checked,
                    extra_args: document.getElementById('extraArgs').value
                };

                fetch('/api/presets', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, config })
                }).then(() => loadPresets());
            }
        }

        function deletePreset(name) {
            if (confirm(`Delete preset "${name}"?`)) {
                fetch(`/api/presets/${name}`, { method: 'DELETE' })
                    .then(() => loadPresets());
            }
        }

        document.getElementById('logSearch').addEventListener('input', updateLogs);

        updateStatus();
        updateSystemMonitor();
        updateLogs();

        setInterval(updateStatus, 2000);
        setInterval(updateSystemMonitor, 3000);
        setInterval(updateLogs, 2000);
    </script>
</body>
</html>
'''

def run_flask():
    flask_app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False, threaded=True)

def main():
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    time.sleep(1.5)

    launcher_url = 'http://127.0.0.1:5000'

    if HAS_WEBVIEW:
        try:
            window = webview.create_window(
                'FuxkComfy Launcher Pro',
                launcher_url,
                width=1400,
                height=900,
                resizable=True,
                min_size=(1200, 700)
            )
            webview.start()
        except Exception as e:
            print(f"pywebview error: {e}")
            print(f"Opening in browser: {launcher_url}")
            webbrowser.open(launcher_url)
    else:
        print("pywebview not installed (optional)")
        print(f"Opening launcher in browser: {launcher_url}")
        webbrowser.open(launcher_url)
        print("\nPress Ctrl+C to stop the launcher")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down launcher...")

if __name__ == "__main__":
    main()
