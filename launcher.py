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
import atexit
import signal
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request
from datetime import datetime
from collections import deque
from typing import Dict, List, Any, Optional
from launcher_tools import (
    PythonEnvironment,
    DependencyManager,
    CustomNodesManager,
    SystemDiagnostics,
    PyTorchManager
)

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
        launcher_dir = Path(__file__).parent
        self.config_file = launcher_dir / config_file
        self.presets_file = launcher_dir / "launcher_presets.json"
        self.history_file = launcher_dir / "launcher_history.json"
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
            "use_split_cross_attention": False,
            "use_quad_cross_attention": False,
            "use_sage_attention": False,
            "use_flash_attention": False,
            "directml": False,
            "gpu_only": False,
            "reserve_vram": "",
            "cpu_vae": False,
            "async_offload": False,
            "disable_mmap": False,
            "force_channels_last": False,
            "preview_method": "auto",
            "preview_size": "",
            "extra_args": "",
            "python_executable": "",
            "language": "en",
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
        python_exe = self.get_config_value("python_executable", "")
        if python_exe and os.path.isfile(python_exe):
            cmd = [python_exe, "-s", "main.py"]
            self.log_message(f"Using custom Python: {python_exe}", "info")
        else:
            cmd = [sys.executable, "-s", "main.py"]
            self.log_message(f"Using system Python: {sys.executable}", "info")

        cmd.append("--windows-standalone-build")
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
        if self.get_config_value("use_split_cross_attention", False):
            cmd.append("--use-split-cross-attention")
        if self.get_config_value("use_quad_cross_attention", False):
            cmd.append("--use-quad-cross-attention")
        if self.get_config_value("use_sage_attention", False):
            cmd.append("--use-sage-attention")
        if self.get_config_value("use_flash_attention", False):
            cmd.append("--use-flash-attention")
        if self.get_config_value("directml", False):
            cmd.append("--directml")
        if self.get_config_value("gpu_only", False):
            cmd.append("--gpu-only")
        if self.get_config_value("cpu_vae", False):
            cmd.append("--cpu-vae")
        if self.get_config_value("async_offload", False):
            cmd.append("--async-offload")
        if self.get_config_value("disable_mmap", False):
            cmd.append("--disable-mmap")
        if self.get_config_value("force_channels_last", False):
            cmd.append("--force-channels-last")

        reserve_vram = self.get_config_value("reserve_vram", "")
        if reserve_vram:
            cmd.extend(["--reserve-vram", reserve_vram])

        preview_method = self.get_config_value("preview_method", "auto")
        if preview_method and preview_method != "auto":
            cmd.extend(["--preview-method", preview_method])

        preview_size = self.get_config_value("preview_size", "")
        if preview_size:
            cmd.extend(["--preview-size", preview_size])

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
                encoding='utf-8',
                errors='replace',
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
        if self.process is None:
            if self.system_monitor.process_pid:
                self.log_message(f"Found orphaned PID {self.system_monitor.process_pid}, attempting cleanup...", "warning")
                pid = self.system_monitor.process_pid
            else:
                return {"success": False, "message": "Process not running"}
        else:
            pid = self.process.pid

        if not self.is_running and self.process:
            self.log_message("Process object exists but is_running=False, checking actual status...", "warning")
            try:
                proc = psutil.Process(pid)
                if proc.is_running():
                    self.log_message(f"Process {pid} is actually running, correcting state...", "info")
                    self.is_running = True
                else:
                    self.log_message("Process confirmed not running", "info")
                    self.is_running = False
                    self.process = None
                    self.system_monitor.process_pid = None
                    return {"success": False, "message": "Process not running"}
            except psutil.NoSuchProcess:
                self.log_message("Process confirmed not running", "info")
                self.is_running = False
                self.process = None
                self.system_monitor.process_pid = None
                return {"success": False, "message": "Process not running"}

        try:
            self.log_message("Stopping process...", "warning")
            self.log_message(f"Process PID: {pid}", "info")

            if platform.system() == 'Windows':
                self.log_message("Using Windows taskkill method...", "info")
                try:
                    if force:
                        result = subprocess.run(
                            ['taskkill', '/F', '/T', '/PID', str(pid)],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        self.log_message(f"taskkill output: {result.stdout}", "info")
                        if result.stderr:
                            self.log_message(f"taskkill stderr: {result.stderr}", "warning")
                        self.log_message("Process force killed with taskkill /F", "warning")
                    else:
                        result = subprocess.run(
                            ['taskkill', '/T', '/PID', str(pid)],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        self.log_message(f"taskkill output: {result.stdout}", "info")
                        if result.stderr:
                            self.log_message(f"taskkill stderr: {result.stderr}", "warning")

                        time.sleep(2)

                        try:
                            proc_check = psutil.Process(pid)
                            if proc_check.is_running():
                                self.log_message("Process still running, force killing...", "warning")
                                subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], timeout=10)
                                self.log_message("Process force killed", "warning")
                        except psutil.NoSuchProcess:
                            self.log_message("Process terminated successfully", "success")

                    try:
                        self.process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        pass

                except subprocess.TimeoutExpired:
                    self.log_message("taskkill timeout, trying alternative method...", "warning")
                    raise Exception("taskkill timeout")
                except FileNotFoundError:
                    self.log_message("taskkill not found, using psutil...", "warning")
                    raise Exception("taskkill not found")

            else:
                try:
                    parent = psutil.Process(pid)
                    children = parent.children(recursive=True)

                    if force:
                        self.log_message(f"Force killing process {pid} and all children...", "warning")
                        for child in children:
                            try:
                                child.kill()
                                self.log_message(f"Killed child process {child.pid}", "info")
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                pass
                        parent.kill()
                        self.log_message("Process force killed", "warning")
                    else:
                        self.log_message(f"Terminating process {pid} and all children...", "info")
                        for child in children:
                            try:
                                child.terminate()
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                pass
                        parent.terminate()

                        try:
                            parent.wait(timeout=5)
                            self.log_message("Process terminated gracefully", "success")
                        except psutil.TimeoutExpired:
                            self.log_message("Graceful shutdown timeout, force killing...", "warning")
                            for child in children:
                                try:
                                    if child.is_running():
                                        child.kill()
                                except (psutil.NoSuchProcess, psutil.AccessDenied):
                                    pass
                            parent.kill()
                            parent.wait(timeout=2)
                            self.log_message("Process force killed", "warning")
                except psutil.NoSuchProcess:
                    self.log_message("Process already terminated", "info")

            self.is_running = False
            self.system_monitor.process_pid = None
            self.start_time = None

            return {"success": True, "message": "Process stopped"}

        except Exception as e:
            self.log_message(f"Error stopping process: {str(e)}", "error")
            self.log_message("Attempting final cleanup with psutil...", "warning")

            try:
                if self.process and self.process.poll() is None:
                    self.process.kill()
                    self.process.wait(timeout=3)
                    self.log_message("Process killed via subprocess.kill()", "warning")
            except Exception as final_error:
                self.log_message(f"Final cleanup failed: {str(final_error)}", "error")

            self.is_running = False
            self.system_monitor.process_pid = None
            self.start_time = None

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

launcher = None

@flask_app.route('/')
def index():
    template_path = Path(__file__).parent / 'launcher_template.html'
    if template_path.exists():
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    return render_template_string(WEB_TEMPLATE)

@flask_app.route('/launcher_tools.js')
def launcher_tools_js():
    js_path = Path(__file__).parent / 'launcher_tools.js'
    if js_path.exists():
        with open(js_path, 'r', encoding='utf-8') as f:
            return f.read(), 200, {'Content-Type': 'application/javascript'}
    return '', 404

@flask_app.route('/pytorch_manager.js')
def pytorch_manager_js():
    js_path = Path(__file__).parent / 'pytorch_manager.js'
    if js_path.exists():
        with open(js_path, 'r', encoding='utf-8') as f:
            return f.read(), 200, {'Content-Type': 'application/javascript'}
    return '', 404

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

@flask_app.route('/api/python/info')
def python_info():
    return jsonify(PythonEnvironment.get_python_info())

@flask_app.route('/api/python/check')
def python_check():
    return jsonify(PythonEnvironment.check_python_version())

@flask_app.route('/api/python/find')
def python_find():
    executables = PythonEnvironment.find_python_executables()
    
    # Add custom configured Python if it exists and is valid
    custom_python = launcher.get_config_value("python_executable", "")
    if custom_python:
        # Convert to absolute path if relative
        if not os.path.isabs(custom_python):
            custom_python = os.path.abspath(custom_python)
        
        if os.path.isfile(custom_python):
            # Check if it's not already in the list
            if not any(exe["path"] == custom_python for exe in executables):
                try:
                    result = subprocess.run(
                        [custom_python, "--version"],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    version = result.stdout.strip().split()[-1] if result.stdout else "unknown"
                    executables.insert(0, {
                        "path": custom_python,
                        "version": version,
                        "current": False,
                        "source": "custom",
                        "configured": True
                    })
                except Exception:
                    # If custom path is invalid, still show it but mark as invalid
                    executables.insert(0, {
                        "path": custom_python,
                        "version": "invalid",
                        "current": False,
                        "source": "custom",
                        "configured": True,
                        "invalid": True
                    })
    
    return jsonify({'executables': executables})

@flask_app.route('/api/dependencies/check')
def dependencies_check():
    python_exe = launcher.get_config_value("python_executable", "")
    dep_manager = DependencyManager(python_executable=python_exe)

    launcher.log_message(f"Checking dependencies using Python: {dep_manager.python_executable}", "info")
    result = dep_manager.check_dependencies()

    if result['missing'] > 0:
        missing_names = ', '.join([p['name'] for p in result['missing_packages']])
        launcher.log_message(f"Missing {result['missing']} dependencies: {missing_names}", "warning")
    else:
        launcher.log_message("All dependencies satisfied", "success")

    launcher.log_message(f"Total: {result['total']} | Installed: {result['installed']} | Missing: {result['missing']}", "info")

    result['using_python'] = dep_manager.python_executable
    return jsonify(result)

@flask_app.route('/api/dependencies/install', methods=['POST'])
def dependencies_install():
    data = request.json
    package = data.get('package')
    python_exe = launcher.get_config_value("python_executable", "")
    dep_manager = DependencyManager(python_executable=python_exe)

    launcher.log_message(f"Installing dependencies using Python: {dep_manager.python_executable}", "info")

    if package:
        launcher.log_message(f"Installing package: {package}", "info")
        success, output = dep_manager.install_package(package)
    else:
        launcher.log_message("Installing all missing dependencies from requirements.txt", "info")
        success, output = dep_manager.install_requirements()

    for line in output.split('\n'):
        line = line.strip()
        if not line:
            continue
        if 'Successfully installed' in line or 'already satisfied' in line or '✅' in line:
            launcher.log_message(line, "success")
        elif 'ERROR' in line or 'Failed' in line or '❌' in line:
            launcher.log_message(line, "error")
        elif 'WARNING' in line or 'Skipped' in line or '⏭️' in line:
            launcher.log_message(line, "warning")
        else:
            launcher.log_message(line, "info")

    if success:
        launcher.log_message("Dependencies installation completed successfully", "success")
    else:
        launcher.log_message("Dependencies installation completed with errors", "error")

    output_with_python = f"Using Python: {dep_manager.python_executable}\n\n{output}"
    return jsonify({'success': success, 'output': output_with_python})

@flask_app.route('/api/nodes/scan')
def nodes_scan():
    nodes_manager = CustomNodesManager()
    return jsonify({'nodes': nodes_manager.scan_custom_nodes()})

@flask_app.route('/api/nodes/install', methods=['POST'])
def nodes_install():
    data = request.json
    git_url = data.get('git_url')
    target_name = data.get('target_name')
    if not git_url:
        return jsonify({'success': False, 'message': 'git_url is required'})
    nodes_manager = CustomNodesManager()
    success, message = nodes_manager.install_from_git(git_url, target_name)
    return jsonify({'success': success, 'message': message})

@flask_app.route('/api/nodes/toggle', methods=['POST'])
def nodes_toggle():
    data = request.json
    node_name = data.get('node_name')
    enable = data.get('enable', True)
    if not node_name:
        return jsonify({'success': False, 'message': 'node_name is required'})
    nodes_manager = CustomNodesManager()
    success, message = nodes_manager.toggle_node(node_name, enable)
    return jsonify({'success': success, 'message': message})

@flask_app.route('/api/nodes/delete', methods=['POST'])
def nodes_delete():
    data = request.json
    node_name = data.get('node_name')
    if not node_name:
        return jsonify({'success': False, 'message': 'node_name is required'})
    nodes_manager = CustomNodesManager()
    success, message = nodes_manager.delete_node(node_name)
    return jsonify({'success': success, 'message': message})

@flask_app.route('/api/nodes/update', methods=['POST'])
def nodes_update():
    data = request.json
    node_name = data.get('node_name')
    if not node_name:
        return jsonify({'success': False, 'message': 'node_name is required'})
    nodes_manager = CustomNodesManager()
    success, message = nodes_manager.update_node(node_name)
    return jsonify({'success': success, 'message': message})

@flask_app.route('/api/diagnostics')
def diagnostics():
    return jsonify(SystemDiagnostics.get_full_diagnostics())

@flask_app.route('/api/pytorch/info')
def pytorch_info():
    python_exe = launcher.get_config_value("python_executable", "")
    torch_manager = PyTorchManager(python_executable=python_exe)
    info = torch_manager.get_current_torch_info()
    info['using_python'] = torch_manager.python_executable
    return jsonify(info)

@flask_app.route('/api/pytorch/versions')
def pytorch_versions():
    return jsonify(PyTorchManager.get_available_versions())

@flask_app.route('/api/pytorch/install', methods=['POST'])
def pytorch_install():
    data = request.json
    version_key = data.get('version_key')
    if not version_key:
        return jsonify({'success': False, 'output': 'version_key is required'})

    python_exe = launcher.get_config_value("python_executable", "")
    torch_manager = PyTorchManager(python_executable=python_exe)

    launcher.log_message(f"Installing PyTorch version: {version_key}", "info")
    launcher.log_message(f"Using Python: {torch_manager.python_executable}", "info")

    def log_callback(line):
        line = line.strip()
        if not line:
            return
        if 'Successfully' in line or '✅' in line:
            launcher.log_message(line, "success")
        elif 'ERROR' in line or 'Failed' in line or '❌' in line:
            launcher.log_message(line, "error")
        elif 'WARNING' in line or 'Uninstalling' in line or 'Downloading' in line:
            launcher.log_message(line, "warning")
        elif 'Installing' in line or 'Collecting' in line:
            launcher.log_message(line, "info")
        else:
            launcher.log_message(line, "info")

    def install_in_background():
        success, output = torch_manager.install_pytorch(version_key, log_callback=log_callback)
        if success:
            launcher.log_message("PyTorch installation completed successfully", "success")
        else:
            launcher.log_message("PyTorch installation failed", "error")

    install_thread = threading.Thread(target=install_in_background, daemon=True)
    install_thread.start()

    return jsonify({'success': True, 'message': 'Installation started in background. Check logs for progress.'})

@flask_app.route('/api/huggingface/download', methods=['POST'])
def huggingface_download():
    data = request.json
    model_url = data.get('model_url', '').strip()
    save_path = data.get('save_path', 'models/checkpoints')

    if not model_url:
        return jsonify({'success': False, 'error': 'Model URL is required'})

    model_id = model_url
    if model_url.startswith('http'):
        parts = model_url.split('huggingface.co/')
        if len(parts) > 1:
            model_id = parts[1].rstrip('/')
        else:
            return jsonify({'success': False, 'error': 'Invalid HuggingFace URL'})

    launcher.log_message(f"Starting HuggingFace model download: {model_id}", "info")
    launcher.log_message(f"Save path: {save_path}", "info")

    def download_in_background():
        try:
            import requests
            import re
            from urllib.parse import urljoin, unquote

            api_url = f"https://huggingface.co/api/models/{model_id}"
            launcher.log_message(f"Fetching model info from {api_url}", "info")

            response = requests.get(api_url, timeout=30)
            if response.status_code != 200:
                launcher.log_message(f"Failed to fetch model info: {response.status_code}", "error")
                return

            model_info = response.json()
            siblings = model_info.get('siblings', [])

            if not siblings:
                launcher.log_message("No files found in model repository", "warning")
                return

            download_files = []
            for sibling in siblings:
                filename = sibling.get('rfilename', '')
                if filename and not filename.startswith('.'):
                    download_files.append(filename)

            launcher.log_message(f"Found {len(download_files)} files to download", "info")

            abs_save_path = os.path.abspath(save_path)
            os.makedirs(abs_save_path, exist_ok=True)

            for file_path in download_files:
                file_url = f"https://huggingface.co/{model_id}/resolve/main/{file_path}"
                local_file_path = os.path.join(abs_save_path, os.path.basename(file_path))

                launcher.log_message(f"Downloading {file_path}...", "info")

                aria2c_path = "aria2c"
                aria2c_cmd = [
                    aria2c_path,
                    "--max-connection-per-server=16",
                    "--split=16",
                    "--min-split-size=1M",
                    "--continue=true",
                    "--allow-overwrite=true",
                    "--auto-file-renaming=false",
                    "--max-tries=5",
                    "--retry-wait=3",
                    "--console-log-level=warn",
                    "--summary-interval=0",
                    f"--dir={abs_save_path}",
                    f"--out={os.path.basename(file_path)}",
                    file_url
                ]

                try:
                    process = subprocess.Popen(
                        aria2c_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        bufsize=1,
                        universal_newlines=True
                    )

                    for line in process.stdout:
                        line = line.strip()
                        if line:
                            launcher.log_message(f"[aria2c] {line}", "info")

                    process.wait()

                    if process.returncode == 0:
                        launcher.log_message(f"Successfully downloaded {file_path}", "success")
                    else:
                        launcher.log_message(f"Failed to download {file_path} (exit code: {process.returncode})", "error")

                except FileNotFoundError:
                    launcher.log_message("aria2c not found. Falling back to requests download...", "warning")

                    try:
                        file_response = requests.get(file_url, stream=True, timeout=60)
                        file_response.raise_for_status()

                        total_size = int(file_response.headers.get('content-length', 0))
                        downloaded_size = 0

                        with open(local_file_path, 'wb') as f:
                            for chunk in file_response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                                    downloaded_size += len(chunk)
                                    if total_size > 0:
                                        progress = (downloaded_size / total_size) * 100
                                        if downloaded_size % (1024 * 1024 * 10) == 0:
                                            launcher.log_message(f"Progress: {progress:.1f}% ({downloaded_size}/{total_size} bytes)", "info")

                        launcher.log_message(f"Successfully downloaded {file_path}", "success")
                    except Exception as req_error:
                        launcher.log_message(f"Failed to download {file_path}: {str(req_error)}", "error")

                except Exception as e:
                    launcher.log_message(f"Error downloading {file_path}: {str(e)}", "error")

            launcher.log_message(f"HuggingFace model download completed: {model_id}", "success")

        except Exception as e:
            launcher.log_message(f"HuggingFace download error: {str(e)}", "error")

    download_thread = threading.Thread(target=download_in_background, daemon=True)
    download_thread.start()

    return jsonify({'success': True, 'message': 'Download started in background. Check logs for progress.'})

WEB_TEMPLATE = '''Fallback template'''


def cleanup_on_exit():
    global launcher

    print("\nLauncher is closing, cleaning up...")

    if launcher and launcher.process:
        try:
            pid = launcher.process.pid
            print(f"Stopping FuxkComfy process (PID: {pid})...")

            if platform.system() == 'Windows':
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL,
                             timeout=5)
            else:
                try:
                    parent = psutil.Process(pid)
                    children = parent.children(recursive=True)
                    for child in children:
                        child.kill()
                    parent.kill()
                except:
                    pass

            print("FuxkComfy process stopped successfully")
        except Exception as e:
            print(f"Error stopping FuxkComfy: {e}")

    print("Cleanup complete, exiting...")
    os._exit(0)

def signal_handler(signum, frame):
    cleanup_on_exit()

def run_flask():
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    flask_app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False, threaded=True)

def main():
    global launcher

    atexit.register(cleanup_on_exit)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    launcher = FuxkComfyLauncher()

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
            cleanup_on_exit()
        except Exception as e:
            print(f"pywebview error: {e}")
            print(f"Opening in browser: {launcher_url}")
            webbrowser.open(launcher_url)
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                cleanup_on_exit()
    else:
        print("pywebview not installed (optional)")
        print(f"Opening launcher in browser: {launcher_url}")
        webbrowser.open(launcher_url)
        print("\nPress Ctrl+C to stop the launcher")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            cleanup_on_exit()

if __name__ == "__main__":
    main()
