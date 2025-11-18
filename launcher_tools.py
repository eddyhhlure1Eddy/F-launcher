# Author: eddy

import os
import sys
import subprocess
import json
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

class PythonEnvironment:
    @staticmethod
    def get_python_info() -> Dict[str, Any]:
        return {
            "executable": sys.executable,
            "version": sys.version,
            "version_info": {
                "major": sys.version_info.major,
                "minor": sys.version_info.minor,
                "micro": sys.version_info.micro
            },
            "platform": sys.platform,
            "prefix": sys.prefix,
            "path": sys.path
        }

    @staticmethod
    def check_python_version() -> Dict[str, Any]:
        info = PythonEnvironment.get_python_info()
        version_info = info["version_info"]
        is_compatible = version_info["major"] == 3 and version_info["minor"] >= 10

        return {
            "compatible": is_compatible,
            "version": f"{version_info['major']}.{version_info['minor']}.{version_info['micro']}",
            "recommended": "3.12+",
            "executable": info["executable"]
        }

    @staticmethod
    def find_python_executables() -> List[Dict[str, str]]:
        executables = []
        project_root = Path.cwd()
        
        # Scan project directories for Python executables
        python_dirs = [
            "python_embeded",
            "python_embedded",
            "python",
            ".venv",
            "venv",
            "env"
        ]
        
        for dir_name in python_dirs:
            dir_path = project_root / dir_name
            if dir_path.exists() and dir_path.is_dir():
                # Check common Python executable locations
                python_paths = [
                    dir_path / "python.exe",
                    dir_path / "Scripts" / "python.exe",
                    dir_path / "bin" / "python",
                    dir_path / "bin" / "python3"
                ]
                
                for python_path in python_paths:
                    if python_path.exists() and python_path.is_file():
                        if not any(exe["path"] == str(python_path.absolute()) for exe in executables):
                            try:
                                result = subprocess.run(
                                    [str(python_path), "--version"],
                                    capture_output=True,
                                    text=True,
                                    timeout=2
                                )
                                version = result.stdout.strip().split()[-1] if result.stdout else "unknown"
                                
                                # Determine source type
                                source_type = "embedded" if "embed" in dir_name.lower() else "virtual_env"
                                
                                executables.append({
                                    "path": str(python_path.absolute()),
                                    "version": version,
                                    "current": str(python_path.absolute()) == sys.executable,
                                    "source": source_type,
                                    "location": dir_name
                                })
                            except Exception:
                                pass
        
        # Add current Python only if it's within the project directory
        current = sys.executable
        current_path = Path(current)
        if current_path.is_relative_to(project_root) or str(project_root) in current:
            if not any(exe["path"] == current for exe in executables):
                executables.append({
                    "path": current,
                    "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                    "current": True,
                    "source": "current",
                    "location": "current"
                })
        
        return executables

class DependencyManager:
    def __init__(self, requirements_file: str = "requirements.txt", python_executable: Optional[str] = None):
        self.requirements_file = Path(requirements_file)
        python_exe = python_executable if python_executable and os.path.isfile(python_executable) else sys.executable
        self.pip_executable = [python_exe, "-m", "pip"]
        self.python_executable = python_exe

    def get_installed_packages(self) -> Dict[str, str]:
        try:
            result = subprocess.run(
                self.pip_executable + ["list", "--format=json"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                print(f"pip list failed: {result.stderr}")
                return {}
            packages = json.loads(result.stdout)
            pkg_dict = {}
            for pkg in packages:
                name_lower = pkg["name"].lower()
                name_normalized = name_lower.replace("_", "-")
                pkg_dict[name_normalized] = pkg["version"]
                if "_" in name_lower:
                    pkg_dict[name_lower] = pkg["version"]
            return pkg_dict
        except Exception as e:
            print(f"get_installed_packages error: {e}")
            return {}

    def parse_requirements(self) -> List[Dict[str, Any]]:
        if not self.requirements_file.exists():
            return []

        requirements = []
        with open(self.requirements_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                requirement = {"raw": line, "name": "", "version": "", "optional": False}

                if line.startswith('-'):
                    continue

                if '~=' in line:
                    parts = line.split('~=')
                    requirement["name"] = parts[0].strip()
                    requirement["version"] = parts[1].strip() if len(parts) > 1 else ""
                    requirement["operator"] = "~="
                elif '>=' in line:
                    parts = line.split('>=')
                    requirement["name"] = parts[0].strip()
                    requirement["version"] = parts[1].strip() if len(parts) > 1 else ""
                    requirement["operator"] = ">="
                elif '==' in line:
                    parts = line.split('==')
                    requirement["name"] = parts[0].strip()
                    requirement["version"] = parts[1].strip() if len(parts) > 1 else ""
                    requirement["operator"] = "=="
                else:
                    requirement["name"] = line.strip()
                    requirement["operator"] = ""

                requirements.append(requirement)

        return requirements

    def check_dependencies(self) -> Dict[str, Any]:
        installed = self.get_installed_packages()
        required = self.parse_requirements()

        missing = []
        outdated = []
        satisfied = []

        for req in required:
            name = req["name"].lower()
            if name not in installed:
                missing.append(req)
            else:
                req["installed_version"] = installed[name]
                satisfied.append(req)

        return {
            "total": len(required),
            "installed": len(satisfied),
            "missing": len(missing),
            "missing_packages": missing,
            "satisfied_packages": satisfied
        }

    def install_package(self, package: str) -> Tuple[bool, str]:
        try:
            result = subprocess.run(
                self.pip_executable + ["install", package],
                capture_output=True,
                text=True,
                timeout=300
            )
            success = result.returncode == 0
            return success, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)

    def install_requirements(self, skip_not_found: bool = True) -> Tuple[bool, str]:
        if not self.requirements_file.exists():
            return False, "requirements.txt not found"

        requirements = self.parse_requirements()
        if not requirements:
            return False, "No valid requirements found"

        output_lines = []
        failed_packages = []
        installed_count = 0
        skipped_count = 0

        for req in requirements:
            package_spec = req["raw"]
            package_name = req["name"]

            try:
                result = subprocess.run(
                    self.pip_executable + ["install", package_spec],
                    capture_output=True,
                    text=True,
                    timeout=300
                )

                if result.returncode == 0:
                    output_lines.append(f"✅ Installed: {package_name}")
                    installed_count += 1
                else:
                    error_msg = result.stderr.lower()
                    if "could not find a version" in error_msg or "no matching distribution" in error_msg:
                        if skip_not_found:
                            output_lines.append(f"⏭️  Skipped (not found): {package_name}")
                            skipped_count += 1
                        else:
                            output_lines.append(f"❌ Failed: {package_name}")
                            failed_packages.append(package_name)
                    else:
                        output_lines.append(f"❌ Failed: {package_name} - {result.stderr[:100]}")
                        failed_packages.append(package_name)

            except subprocess.TimeoutExpired:
                output_lines.append(f"⏱️  Timeout: {package_name}")
                failed_packages.append(package_name)
            except Exception as e:
                output_lines.append(f"❌ Error: {package_name} - {str(e)[:100]}")
                failed_packages.append(package_name)

        summary = f"\n\n📊 Summary:\n"
        summary += f"✅ Installed: {installed_count}\n"
        summary += f"⏭️  Skipped: {skipped_count}\n"
        summary += f"❌ Failed: {len(failed_packages)}\n"

        if failed_packages:
            summary += f"\nFailed packages: {', '.join(failed_packages)}"

        full_output = "\n".join(output_lines) + summary
        success = len(failed_packages) == 0 or (skip_not_found and installed_count > 0)

        return success, full_output

class CustomNodesManager:
    def __init__(self, custom_nodes_dir: str = "custom_nodes"):
        self.custom_nodes_dir = Path(custom_nodes_dir)
        self.custom_nodes_dir.mkdir(exist_ok=True)

    def scan_custom_nodes(self) -> List[Dict[str, Any]]:
        nodes = []

        if not self.custom_nodes_dir.exists():
            return nodes

        for item in self.custom_nodes_dir.iterdir():
            if item.is_dir() and not item.name.startswith('.') and item.name != '__pycache__':
                node_info = {
                    "name": item.name,
                    "path": str(item),
                    "enabled": not item.name.endswith('.disabled'),
                    "has_requirements": (item / "requirements.txt").exists(),
                    "has_install_script": (item / "install.py").exists(),
                    "is_git_repo": (item / ".git").exists(),
                    "files_count": len(list(item.glob("**/*.py")))
                }

                if node_info["is_git_repo"]:
                    try:
                        result = subprocess.run(
                            ["git", "-C", str(item), "remote", "get-url", "origin"],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result.returncode == 0:
                            node_info["git_url"] = result.stdout.strip()
                    except Exception:
                        pass

                nodes.append(node_info)

        return sorted(nodes, key=lambda x: x["name"])

    def install_from_git(self, git_url: str, target_name: Optional[str] = None) -> Tuple[bool, str]:
        if not shutil.which("git"):
            return False, "Git not found. Please install Git first."

        if target_name:
            target_path = self.custom_nodes_dir / target_name
        else:
            repo_name = git_url.rstrip('/').split('/')[-1].replace('.git', '')
            target_path = self.custom_nodes_dir / repo_name

        if target_path.exists():
            return False, f"Directory {target_path.name} already exists"

        try:
            result = subprocess.run(
                ["git", "clone", git_url, str(target_path)],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                return False, result.stderr

            requirements_file = target_path / "requirements.txt"
            install_output = ""

            if requirements_file.exists():
                dep_manager = DependencyManager(str(requirements_file))
                install_success, install_msg = dep_manager.install_requirements()
                install_output = f"\n\nDependency installation: {'Success' if install_success else 'Failed'}\n{install_msg}"

            install_script = target_path / "install.py"
            if install_script.exists():
                try:
                    subprocess.run(
                        [sys.executable, str(install_script)],
                        cwd=str(target_path),
                        timeout=300
                    )
                except Exception as e:
                    install_output += f"\n\nInstall script error: {str(e)}"

            return True, f"Successfully cloned {git_url}{install_output}"

        except Exception as e:
            return False, str(e)

    def toggle_node(self, node_name: str, enable: bool) -> Tuple[bool, str]:
        current_path = self.custom_nodes_dir / node_name

        if enable:
            if current_path.name.endswith('.disabled'):
                new_path = self.custom_nodes_dir / current_path.name[:-9]
            else:
                return True, f"{node_name} is already enabled"
        else:
            if not current_path.name.endswith('.disabled'):
                new_path = self.custom_nodes_dir / f"{current_path.name}.disabled"
            else:
                return True, f"{node_name} is already disabled"

        try:
            current_path.rename(new_path)
            return True, f"{'Enabled' if enable else 'Disabled'} {node_name}"
        except Exception as e:
            return False, str(e)

    def delete_node(self, node_name: str) -> Tuple[bool, str]:
        node_path = self.custom_nodes_dir / node_name

        if not node_path.exists():
            return False, f"Node {node_name} not found"

        try:
            shutil.rmtree(node_path)
            return True, f"Deleted {node_name}"
        except Exception as e:
            return False, str(e)

    def update_node(self, node_name: str) -> Tuple[bool, str]:
        node_path = self.custom_nodes_dir / node_name

        if not node_path.exists():
            return False, f"Node {node_name} not found"

        if not (node_path / ".git").exists():
            return False, f"{node_name} is not a git repository"

        try:
            result = subprocess.run(
                ["git", "-C", str(node_path), "pull"],
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                return False, result.stderr

            return True, result.stdout

        except Exception as e:
            return False, str(e)

class SystemDiagnostics:
    @staticmethod
    def get_disk_usage() -> Dict[str, Any]:
        try:
            usage = shutil.disk_usage(os.getcwd())
            return {
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "percent": round((usage.used / usage.total) * 100, 1)
            }
        except Exception:
            return {}

    @staticmethod
    def check_git() -> Dict[str, Any]:
        git_path = shutil.which("git")
        if not git_path:
            return {"installed": False, "version": None, "path": None}

        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            version = result.stdout.strip() if result.returncode == 0 else "unknown"
            return {"installed": True, "version": version, "path": git_path}
        except Exception:
            return {"installed": False, "version": None, "path": git_path}

    @staticmethod
    def get_full_diagnostics() -> Dict[str, Any]:
        return {
            "python": PythonEnvironment.check_python_version(),
            "disk": SystemDiagnostics.get_disk_usage(),
            "git": SystemDiagnostics.check_git(),
            "cwd": os.getcwd()
        }

class PyTorchManager:
    TORCH_VERSIONS = {
        "2.8.0+cu128": {
            "name": "PyTorch 2.8.0 + CUDA 12.8 (Nightly)",
            "index_url": "https://download.pytorch.org/whl/nightly/cu128",
            "packages": ["torch", "torchvision", "torchaudio"]
        },
        "2.8.0+cu124": {
            "name": "PyTorch 2.8.0 + CUDA 12.4 (Nightly)",
            "index_url": "https://download.pytorch.org/whl/nightly/cu124",
            "packages": ["torch", "torchvision", "torchaudio"]
        },
        "2.5.1+cu124": {
            "name": "PyTorch 2.5.1 + CUDA 12.4 (Stable)",
            "index_url": "https://download.pytorch.org/whl/cu124",
            "packages": ["torch==2.5.1", "torchvision==0.20.1", "torchaudio==2.5.1"]
        },
        "2.5.1+cu121": {
            "name": "PyTorch 2.5.1 + CUDA 12.1 (Stable)",
            "index_url": "https://download.pytorch.org/whl/cu121",
            "packages": ["torch==2.5.1", "torchvision==0.20.1", "torchaudio==2.5.1"]
        },
        "2.5.1+cu118": {
            "name": "PyTorch 2.5.1 + CUDA 11.8 (Stable)",
            "index_url": "https://download.pytorch.org/whl/cu118",
            "packages": ["torch==2.5.1", "torchvision==0.20.1", "torchaudio==2.5.1"]
        },
        "2.5.1+cpu": {
            "name": "PyTorch 2.5.1 + CPU Only",
            "index_url": "https://download.pytorch.org/whl/cpu",
            "packages": ["torch==2.5.1", "torchvision==0.20.1", "torchaudio==2.5.1"]
        },
        "2.4.1+cu124": {
            "name": "PyTorch 2.4.1 + CUDA 12.4",
            "index_url": "https://download.pytorch.org/whl/cu124",
            "packages": ["torch==2.4.1", "torchvision==0.19.1", "torchaudio==2.4.1"]
        },
        "2.4.1+cu121": {
            "name": "PyTorch 2.4.1 + CUDA 12.1",
            "index_url": "https://download.pytorch.org/whl/cu121",
            "packages": ["torch==2.4.1", "torchvision==0.19.1", "torchaudio==2.4.1"]
        }
    }

    def __init__(self, python_executable: Optional[str] = None):
        python_exe = python_executable if python_executable and os.path.isfile(python_executable) else sys.executable
        self.pip_executable = [python_exe, "-m", "pip"]
        self.python_executable = python_exe

    def get_current_torch_info(self) -> Dict[str, Any]:
        try:
            result = subprocess.run(
                [self.python_executable, "-c",
                 "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.version.cuda if hasattr(torch.version, 'cuda') else 'N/A')"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                return {
                    "installed": True,
                    "version": lines[0] if len(lines) > 0 else "unknown",
                    "cuda_available": lines[1].lower() == 'true' if len(lines) > 1 else False,
                    "cuda_version": lines[2] if len(lines) > 2 else "N/A"
                }
        except Exception as e:
            pass
        return {
            "installed": False,
            "version": None,
            "cuda_available": False,
            "cuda_version": None
        }

    def install_pytorch(self, version_key: str, log_callback=None) -> Tuple[bool, str]:
        if version_key not in self.TORCH_VERSIONS:
            return False, f"Unknown PyTorch version: {version_key}"

        config = self.TORCH_VERSIONS[version_key]
        output_lines = []

        def log(msg):
            output_lines.append(msg)
            if log_callback:
                log_callback(msg)

        log(f"Installing {config['name']}...")
        log(f"Using Python: {self.python_executable}")

        try:
            log("Uninstalling existing PyTorch packages...")
            uninstall_cmd = self.pip_executable + ["uninstall", "-y", "torch", "torchvision", "torchaudio"]

            process = subprocess.Popen(
                uninstall_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            for line in process.stdout:
                line = line.rstrip()
                if line:
                    log(line)

            process.wait()

            log(f"\nInstalling from: {config['index_url']}...")
            install_cmd = self.pip_executable + ["install"] + config["packages"] + [
                "--index-url", config["index_url"], "--progress-bar", "raw"
            ]

            process = subprocess.Popen(
                install_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            buffer = ""
            while True:
                chunk = process.stdout.read(1)
                if not chunk:
                    break
                buffer += chunk
                if chunk in ("\n", "\r"):
                    line = buffer.strip()
                    buffer = ""
                    if line:
                        log(line)

            if buffer:
                line = buffer.strip()
                if line:
                    log(line)

            return_code = process.wait()

            if return_code == 0:
                log(f"\n✅ Successfully installed {config['name']}")
                return True, "\n".join(output_lines)
            else:
                log(f"\n❌ Failed to install {config['name']}")
                return False, "\n".join(output_lines)

        except Exception as e:
            log(f"\n❌ Error: {str(e)}")
            return False, "\n".join(output_lines)

    @classmethod
    def get_available_versions(cls) -> Dict[str, str]:
        return {key: config["name"] for key, config in cls.TORCH_VERSIONS.items()}
