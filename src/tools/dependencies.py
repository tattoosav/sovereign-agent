"""
Dependency Analysis and Management Tool.

Analyzes project dependencies, detects issues, and suggests updates.
"""

import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class Dependency:
    """A project dependency."""
    name: str
    version: str
    required_version: str = ""
    latest_version: str = ""
    is_dev: bool = False
    is_outdated: bool = False
    has_vulnerability: bool = False
    vulnerability_info: str = ""


@dataclass
class DependencyReport:
    """Dependency analysis report."""
    language: str
    dependencies: list[Dependency]
    dev_dependencies: list[Dependency]
    total_count: int
    outdated_count: int
    vulnerable_count: int


class DependencyTool(BaseTool):
    """Tool for dependency analysis and management."""

    name = "dependencies"
    description = """Analyze and manage project dependencies.

Operations:
- analyze: Analyze dependencies in a project
- check_updates: Check for available updates
- check_security: Check for security vulnerabilities
- add: Add a new dependency
- remove: Remove a dependency
- update: Update dependencies
- tree: Show dependency tree
"""
    parameters = {
        "operation": "Operation to perform",
        "path": "Project path",
        "package": "Package name (for add/remove)",
        "version": "Package version (optional)",
        "dev": "Is development dependency (true/false)",
    }

    def execute(
        self,
        operation: str,
        path: str = ".",
        package: str = "",
        version: str = "",
        dev: bool = False,
        **kwargs: Any
    ) -> ToolResult:
        """Execute dependency operation."""
        try:
            project_path = Path(path)
            language = self._detect_project_type(project_path)

            if operation == "analyze":
                return self._analyze(project_path, language)
            elif operation == "check_updates":
                return self._check_updates(project_path, language)
            elif operation == "check_security":
                return self._check_security(project_path, language)
            elif operation == "add":
                return self._add_dependency(project_path, language, package, version, dev)
            elif operation == "remove":
                return self._remove_dependency(project_path, language, package)
            elif operation == "update":
                return self._update_dependencies(project_path, language, package)
            elif operation == "tree":
                return self._dependency_tree(project_path, language)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Unknown operation: {operation}"
                )
        except Exception as e:
            logger.exception(f"Dependency tool error: {e}")
            return ToolResult(success=False, output="", error=str(e))

    def _detect_project_type(self, path: Path) -> str:
        """Detect project type from files."""
        if (path / "pyproject.toml").exists() or (path / "requirements.txt").exists():
            return "python"
        if (path / "package.json").exists():
            return "nodejs"
        if list(path.glob("*.csproj")) or list(path.glob("*.sln")):
            return "dotnet"
        if (path / "CMakeLists.txt").exists() or (path / "vcpkg.json").exists():
            return "cpp"
        if (path / "Cargo.toml").exists():
            return "rust"
        if (path / "go.mod").exists():
            return "go"
        return "unknown"

    def _analyze(self, path: Path, language: str) -> ToolResult:
        """Analyze project dependencies."""
        if language == "python":
            return self._analyze_python(path)
        elif language == "nodejs":
            return self._analyze_nodejs(path)
        elif language == "dotnet":
            return self._analyze_dotnet(path)
        elif language == "cpp":
            return self._analyze_cpp(path)
        else:
            return ToolResult(
                success=False,
                output="",
                error=f"Unsupported project type: {language}"
            )

    def _analyze_python(self, path: Path) -> ToolResult:
        """Analyze Python dependencies."""
        dependencies = []
        dev_dependencies = []

        # Check pyproject.toml
        pyproject = path / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()

            # Parse dependencies
            dep_match = re.search(r'dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
            if dep_match:
                deps = re.findall(r'"([^"]+)"', dep_match.group(1))
                for dep in deps:
                    name = re.split(r'[>=<\[]', dep)[0].strip()
                    version = dep.replace(name, "").strip()
                    dependencies.append(Dependency(name=name, version=version or "*"))

            # Parse dev dependencies
            dev_match = re.search(r'dev\s*=\s*\[(.*?)\]', content, re.DOTALL)
            if dev_match:
                deps = re.findall(r'"([^"]+)"', dev_match.group(1))
                for dep in deps:
                    name = re.split(r'[>=<\[]', dep)[0].strip()
                    version = dep.replace(name, "").strip()
                    dev_dependencies.append(Dependency(name=name, version=version or "*", is_dev=True))

        # Check requirements.txt
        req_file = path / "requirements.txt"
        if req_file.exists():
            for line in req_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    name = re.split(r'[>=<\[]', line)[0].strip()
                    version = line.replace(name, "").strip()
                    if name and name not in [d.name for d in dependencies]:
                        dependencies.append(Dependency(name=name, version=version or "*"))

        output_lines = [
            "Python Dependency Analysis",
            "=" * 40,
            f"\nDependencies ({len(dependencies)}):",
        ]
        for dep in dependencies:
            output_lines.append(f"  {dep.name}: {dep.version}")

        if dev_dependencies:
            output_lines.append(f"\nDev Dependencies ({len(dev_dependencies)}):")
            for dep in dev_dependencies:
                output_lines.append(f"  {dep.name}: {dep.version}")

        return ToolResult(success=True, output="\n".join(output_lines))

    def _analyze_nodejs(self, path: Path) -> ToolResult:
        """Analyze Node.js dependencies."""
        package_json = path / "package.json"
        if not package_json.exists():
            return ToolResult(
                success=False,
                output="",
                error="package.json not found"
            )

        data = json.loads(package_json.read_text())
        dependencies = []
        dev_dependencies = []

        for name, version in data.get("dependencies", {}).items():
            dependencies.append(Dependency(name=name, version=version))

        for name, version in data.get("devDependencies", {}).items():
            dev_dependencies.append(Dependency(name=name, version=version, is_dev=True))

        output_lines = [
            f"Node.js Dependency Analysis: {data.get('name', 'unknown')}",
            "=" * 40,
            f"\nDependencies ({len(dependencies)}):",
        ]
        for dep in dependencies:
            output_lines.append(f"  {dep.name}: {dep.version}")

        if dev_dependencies:
            output_lines.append(f"\nDev Dependencies ({len(dev_dependencies)}):")
            for dep in dev_dependencies:
                output_lines.append(f"  {dep.name}: {dep.version}")

        return ToolResult(success=True, output="\n".join(output_lines))

    def _analyze_dotnet(self, path: Path) -> ToolResult:
        """Analyze .NET dependencies."""
        csproj_files = list(path.glob("*.csproj"))
        if not csproj_files:
            csproj_files = list(path.rglob("*.csproj"))

        if not csproj_files:
            return ToolResult(
                success=False,
                output="",
                error="No .csproj files found"
            )

        all_deps = []
        for csproj in csproj_files:
            content = csproj.read_text()
            # Parse PackageReference
            refs = re.findall(
                r'<PackageReference\s+Include="([^"]+)"(?:\s+Version="([^"]+)")?',
                content
            )
            for name, version in refs:
                all_deps.append(Dependency(name=name, version=version or "*"))

        output_lines = [
            ".NET Dependency Analysis",
            "=" * 40,
            f"\nProjects analyzed: {len(csproj_files)}",
            f"Total packages: {len(all_deps)}",
            "\nPackages:",
        ]
        for dep in all_deps:
            output_lines.append(f"  {dep.name}: {dep.version}")

        return ToolResult(success=True, output="\n".join(output_lines))

    def _analyze_cpp(self, path: Path) -> ToolResult:
        """Analyze C++ dependencies."""
        output_lines = ["C++ Dependency Analysis", "=" * 40]

        # Check vcpkg.json
        vcpkg = path / "vcpkg.json"
        if vcpkg.exists():
            data = json.loads(vcpkg.read_text())
            deps = data.get("dependencies", [])
            output_lines.append(f"\nvcpkg dependencies ({len(deps)}):")
            for dep in deps:
                if isinstance(dep, str):
                    output_lines.append(f"  {dep}")
                else:
                    output_lines.append(f"  {dep.get('name', dep)}")

        # Check CMakeLists.txt for find_package
        cmake = path / "CMakeLists.txt"
        if cmake.exists():
            content = cmake.read_text()
            packages = re.findall(r'find_package\((\w+)', content)
            if packages:
                output_lines.append(f"\nCMake packages ({len(packages)}):")
                for pkg in set(packages):
                    output_lines.append(f"  {pkg}")

        # Check for Conan
        conanfile = path / "conanfile.txt"
        if conanfile.exists():
            content = conanfile.read_text()
            requires_section = re.search(r'\[requires\](.*?)(?:\[|$)', content, re.DOTALL)
            if requires_section:
                deps = [l.strip() for l in requires_section.group(1).splitlines() if l.strip()]
                output_lines.append(f"\nConan dependencies ({len(deps)}):")
                for dep in deps:
                    output_lines.append(f"  {dep}")

        if len(output_lines) == 2:
            output_lines.append("\nNo dependency files found (vcpkg.json, conanfile.txt)")

        return ToolResult(success=True, output="\n".join(output_lines))

    def _check_updates(self, path: Path, language: str) -> ToolResult:
        """Check for dependency updates."""
        if language == "python":
            try:
                result = subprocess.run(
                    ["pip", "list", "--outdated", "--format=json"],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0:
                    outdated = json.loads(result.stdout)
                    if not outdated:
                        return ToolResult(
                            success=True,
                            output="All packages are up to date!"
                        )

                    lines = ["Outdated Python Packages:", "=" * 40]
                    for pkg in outdated:
                        lines.append(
                            f"  {pkg['name']}: {pkg['version']} -> {pkg['latest_version']}"
                        )
                    return ToolResult(success=True, output="\n".join(lines))
            except Exception as e:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Failed to check updates: {e}"
                )

        elif language == "nodejs":
            try:
                result = subprocess.run(
                    ["npm", "outdated", "--json"],
                    capture_output=True,
                    text=True,
                    cwd=path,
                    timeout=60
                )
                if result.stdout:
                    outdated = json.loads(result.stdout)
                    if not outdated:
                        return ToolResult(
                            success=True,
                            output="All packages are up to date!"
                        )

                    lines = ["Outdated Node.js Packages:", "=" * 40]
                    for name, info in outdated.items():
                        lines.append(
                            f"  {name}: {info.get('current', '?')} -> {info.get('latest', '?')}"
                        )
                    return ToolResult(success=True, output="\n".join(lines))
            except Exception as e:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Failed to check updates: {e}"
                )

        elif language == "dotnet":
            try:
                result = subprocess.run(
                    ["dotnet", "list", "package", "--outdated"],
                    capture_output=True,
                    text=True,
                    cwd=path,
                    timeout=120
                )
                return ToolResult(
                    success=result.returncode == 0,
                    output=result.stdout,
                    error=result.stderr if result.returncode != 0 else None
                )
            except Exception as e:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Failed to check updates: {e}"
                )

        return ToolResult(
            success=False,
            output="",
            error=f"Update check not supported for {language}"
        )

    def _check_security(self, path: Path, language: str) -> ToolResult:
        """Check for security vulnerabilities."""
        if language == "python":
            try:
                # Try pip-audit
                result = subprocess.run(
                    ["pip-audit", "--format=json"],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                if result.returncode == 0:
                    vulns = json.loads(result.stdout)
                    if not vulns:
                        return ToolResult(
                            success=True,
                            output="No known vulnerabilities found!"
                        )

                    lines = ["Security Vulnerabilities:", "=" * 40]
                    for vuln in vulns:
                        lines.append(f"\n{vuln.get('name', 'Unknown')}:")
                        lines.append(f"  Version: {vuln.get('version', '?')}")
                        for v in vuln.get("vulns", []):
                            lines.append(f"  - {v.get('id', '?')}: {v.get('description', '')[:100]}")
                    return ToolResult(success=True, output="\n".join(lines))
            except FileNotFoundError:
                return ToolResult(
                    success=False,
                    output="",
                    error="pip-audit not installed. Install with: pip install pip-audit"
                )

        elif language == "nodejs":
            try:
                result = subprocess.run(
                    ["npm", "audit", "--json"],
                    capture_output=True,
                    text=True,
                    cwd=path,
                    timeout=120
                )
                data = json.loads(result.stdout) if result.stdout else {}
                vulns = data.get("vulnerabilities", {})

                if not vulns:
                    return ToolResult(
                        success=True,
                        output="No known vulnerabilities found!"
                    )

                lines = ["Security Vulnerabilities:", "=" * 40]
                for name, info in vulns.items():
                    lines.append(f"\n{name}:")
                    lines.append(f"  Severity: {info.get('severity', '?')}")
                    lines.append(f"  Via: {', '.join(info.get('via', [])[:3])}")
                return ToolResult(success=True, output="\n".join(lines))
            except Exception as e:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"npm audit failed: {e}"
                )

        return ToolResult(
            success=False,
            output="",
            error=f"Security check not supported for {language}"
        )

    def _add_dependency(
        self,
        path: Path,
        language: str,
        package: str,
        version: str,
        dev: bool
    ) -> ToolResult:
        """Add a new dependency."""
        if not package:
            return ToolResult(
                success=False,
                output="",
                error="Package name is required"
            )

        if language == "python":
            cmd = ["pip", "install", f"{package}{version}" if version else package]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                return ToolResult(
                    success=result.returncode == 0,
                    output=f"Installed {package}" + (f" {version}" if version else ""),
                    error=result.stderr if result.returncode != 0 else None
                )
            except Exception as e:
                return ToolResult(success=False, output="", error=str(e))

        elif language == "nodejs":
            cmd = ["npm", "install", f"{package}@{version}" if version else package]
            if dev:
                cmd.append("--save-dev")
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=path, timeout=120)
                return ToolResult(
                    success=result.returncode == 0,
                    output=f"Installed {package}",
                    error=result.stderr if result.returncode != 0 else None
                )
            except Exception as e:
                return ToolResult(success=False, output="", error=str(e))

        elif language == "dotnet":
            pkg_spec = f"{package}" + (f" -v {version}" if version else "")
            cmd = ["dotnet", "add", "package", package]
            if version:
                cmd.extend(["-v", version])
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=path, timeout=120)
                return ToolResult(
                    success=result.returncode == 0,
                    output=f"Added {package}",
                    error=result.stderr if result.returncode != 0 else None
                )
            except Exception as e:
                return ToolResult(success=False, output="", error=str(e))

        return ToolResult(
            success=False,
            output="",
            error=f"Add dependency not supported for {language}"
        )

    def _remove_dependency(self, path: Path, language: str, package: str) -> ToolResult:
        """Remove a dependency."""
        if not package:
            return ToolResult(success=False, output="", error="Package name is required")

        if language == "python":
            cmd = ["pip", "uninstall", "-y", package]
        elif language == "nodejs":
            cmd = ["npm", "uninstall", package]
        elif language == "dotnet":
            cmd = ["dotnet", "remove", "package", package]
        else:
            return ToolResult(
                success=False,
                output="",
                error=f"Remove dependency not supported for {language}"
            )

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=path, timeout=60)
            return ToolResult(
                success=result.returncode == 0,
                output=f"Removed {package}",
                error=result.stderr if result.returncode != 0 else None
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def _update_dependencies(self, path: Path, language: str, package: str) -> ToolResult:
        """Update dependencies."""
        if language == "python":
            if package:
                cmd = ["pip", "install", "--upgrade", package]
            else:
                return ToolResult(
                    success=True,
                    output="For Python, specify a package to update or use: pip install --upgrade -r requirements.txt"
                )
        elif language == "nodejs":
            cmd = ["npm", "update"] + ([package] if package else [])
        elif language == "dotnet":
            # dotnet doesn't have a direct update command
            return ToolResult(
                success=True,
                output="For .NET, use: dotnet add package <package> to update to latest version"
            )
        else:
            return ToolResult(
                success=False,
                output="",
                error=f"Update not supported for {language}"
            )

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=path, timeout=180)
            return ToolResult(
                success=result.returncode == 0,
                output=result.stdout or f"Updated {package or 'all packages'}",
                error=result.stderr if result.returncode != 0 else None
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def _dependency_tree(self, path: Path, language: str) -> ToolResult:
        """Show dependency tree."""
        if language == "python":
            try:
                result = subprocess.run(
                    ["pip", "show", "--files"],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                # pip doesn't have a built-in tree command
                return ToolResult(
                    success=True,
                    output="For Python dependency tree, install pipdeptree: pip install pipdeptree && pipdeptree"
                )
            except Exception:
                pass

        elif language == "nodejs":
            try:
                result = subprocess.run(
                    ["npm", "ls", "--depth=2"],
                    capture_output=True,
                    text=True,
                    cwd=path,
                    timeout=60
                )
                return ToolResult(
                    success=True,
                    output=result.stdout
                )
            except Exception as e:
                return ToolResult(success=False, output="", error=str(e))

        return ToolResult(
            success=False,
            output="",
            error=f"Dependency tree not supported for {language}"
        )
