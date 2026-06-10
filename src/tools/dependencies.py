"""
Dependency Analysis and Management Tool.

Analyzes project dependencies, detects issues, and suggests updates.
"""

import json
import logging
import re
from dataclasses import dataclass
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
    description = """Analyze project dependencies (offline, read-only).

Operations:
- analyze: Analyze the dependencies declared in a project's manifest files

Note: This build is air-gapped. Operations that contact package registries
(update checks, security scans, install/remove/update) are intentionally
unavailable. Only local manifest analysis is supported.
"""
    parameters = {
        "operation": "Operation to perform (only 'analyze' is supported)",
        "path": "Project path",
    }

    def execute(
        self,
        operation: str,
        path: str = ".",
        **kwargs: Any
    ) -> ToolResult:
        """Execute dependency operation (air-gapped: analyze only)."""
        try:
            project_path = Path(path)
            language = self._detect_project_type(project_path)

            if operation == "analyze":
                return self._analyze(project_path, language)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=(
                        f"Operation '{operation}' is disabled in the air-gapped "
                        f"build (it would contact a package registry). "
                        f"Only 'analyze' is available."
                    )
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
