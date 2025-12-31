"""
Visual Studio Project Tools.

Specialized tools for creating and managing Visual Studio projects,
C++, .NET, WinForms, WPF, and GUI applications.
"""

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


# Project templates
VCXPROJ_TEMPLATE = '''<?xml version="1.0" encoding="utf-8"?>
<Project DefaultTargets="Build" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <ItemGroup Label="ProjectConfigurations">
    <ProjectConfiguration Include="Debug|x64">
      <Configuration>Debug</Configuration>
      <Platform>x64</Platform>
    </ProjectConfiguration>
    <ProjectConfiguration Include="Release|x64">
      <Configuration>Release</Configuration>
      <Platform>x64</Platform>
    </ProjectConfiguration>
  </ItemGroup>
  <PropertyGroup Label="Globals">
    <VCProjectVersion>16.0</VCProjectVersion>
    <ProjectGuid>{{{project_guid}}}</ProjectGuid>
    <RootNamespace>{project_name}</RootNamespace>
    <WindowsTargetPlatformVersion>10.0</WindowsTargetPlatformVersion>
  </PropertyGroup>
  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.Default.props" />
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Debug|x64'" Label="Configuration">
    <ConfigurationType>{config_type}</ConfigurationType>
    <UseDebugLibraries>true</UseDebugLibraries>
    <PlatformToolset>v143</PlatformToolset>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'" Label="Configuration">
    <ConfigurationType>{config_type}</ConfigurationType>
    <UseDebugLibraries>false</UseDebugLibraries>
    <PlatformToolset>v143</PlatformToolset>
    <WholeProgramOptimization>true</WholeProgramOptimization>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.props" />
  <ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='Debug|x64'">
    <ClCompile>
      <WarningLevel>Level3</WarningLevel>
      <SDLCheck>true</SDLCheck>
      <PreprocessorDefinitions>_DEBUG;{preprocessor_defs}_UNICODE;UNICODE;%(PreprocessorDefinitions)</PreprocessorDefinitions>
      <ConformanceMode>true</ConformanceMode>
      <LanguageStandard>stdcpp20</LanguageStandard>
    </ClCompile>
    <Link>
      <SubSystem>{subsystem}</SubSystem>
      <GenerateDebugInformation>true</GenerateDebugInformation>
    </Link>
  </ItemDefinitionGroup>
  <ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'">
    <ClCompile>
      <WarningLevel>Level3</WarningLevel>
      <FunctionLevelLinking>true</FunctionLevelLinking>
      <IntrinsicFunctions>true</IntrinsicFunctions>
      <SDLCheck>true</SDLCheck>
      <PreprocessorDefinitions>NDEBUG;{preprocessor_defs}_UNICODE;UNICODE;%(PreprocessorDefinitions)</PreprocessorDefinitions>
      <ConformanceMode>true</ConformanceMode>
      <LanguageStandard>stdcpp20</LanguageStandard>
    </ClCompile>
    <Link>
      <SubSystem>{subsystem}</SubSystem>
      <EnableCOMDATFolding>true</EnableCOMDATFolding>
      <OptimizeReferences>true</OptimizeReferences>
      <GenerateDebugInformation>true</GenerateDebugInformation>
    </Link>
  </ItemDefinitionGroup>
  <ItemGroup>
{source_files}
  </ItemGroup>
  <ItemGroup>
{header_files}
  </ItemGroup>
  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.targets" />
</Project>
'''

CSPROJ_TEMPLATE = '''<Project Sdk="Microsoft.NET.Sdk{sdk_suffix}">
  <PropertyGroup>
    <OutputType>{output_type}</OutputType>
    <TargetFramework>{target_framework}</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
{additional_props}
  </PropertyGroup>
{item_groups}
</Project>
'''

SLN_TEMPLATE = '''Microsoft Visual Studio Solution File, Format Version 12.00
# Visual Studio Version 17
VisualStudioVersion = 17.0.31903.59
MinimumVisualStudioVersion = 10.0.40219.1
{projects}
Global
	GlobalSection(SolutionConfigurationPlatforms) = preSolution
		Debug|Any CPU = Debug|Any CPU
		Debug|x64 = Debug|x64
		Release|Any CPU = Release|Any CPU
		Release|x64 = Release|x64
	EndGlobalSection
	GlobalSection(ProjectConfigurationPlatforms) = postSolution
{project_configs}
	EndGlobalSection
EndGlobal
'''


class VisualStudioTool(BaseTool):
    """Tool for creating and managing Visual Studio projects."""

    name = "visual_studio"
    description = """Create and manage Visual Studio projects.

Operations:
- create_solution: Create a new .sln file
- create_cpp_project: Create a C++ project (.vcxproj)
- create_dotnet_project: Create a .NET project (.csproj)
- add_to_solution: Add a project to a solution
- analyze_project: Analyze an existing project structure
- build: Build a project using MSBuild
"""
    parameters = {
        "operation": "Operation to perform",
        "path": "Path for the project/solution",
        "name": "Project/solution name",
        "project_type": "Type: console, winforms, wpf, library, gui",
        "language": "Language: cpp, csharp, fsharp",
        "framework": "Target framework (for .NET)",
    }

    def __init__(self, working_dir: Path | None = None):
        self.working_dir = working_dir or Path.cwd()

    def execute(
        self,
        operation: str,
        path: str = "",
        name: str = "",
        project_type: str = "console",
        language: str = "cpp",
        framework: str = "net8.0",
        **kwargs: Any
    ) -> ToolResult:
        """Execute Visual Studio operation."""
        try:
            if operation == "create_solution":
                return self._create_solution(path, name)
            elif operation == "create_cpp_project":
                return self._create_cpp_project(path, name, project_type)
            elif operation == "create_dotnet_project":
                return self._create_dotnet_project(path, name, project_type, framework)
            elif operation == "add_to_solution":
                return self._add_to_solution(path, kwargs.get("project_path", ""))
            elif operation == "analyze_project":
                return self._analyze_project(path)
            elif operation == "build":
                return self._build_project(path, kwargs.get("configuration", "Debug"))
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Unknown operation: {operation}"
                )
        except Exception as e:
            logger.exception(f"Visual Studio tool error: {e}")
            return ToolResult(success=False, output="", error=str(e))

    def _generate_guid(self) -> str:
        """Generate a GUID for project files."""
        import uuid
        return str(uuid.uuid4()).upper()

    def _create_solution(self, path: str, name: str) -> ToolResult:
        """Create a new Visual Studio solution."""
        sln_path = Path(path) / f"{name}.sln"
        sln_path.parent.mkdir(parents=True, exist_ok=True)

        content = SLN_TEMPLATE.format(projects="", project_configs="")
        sln_path.write_text(content, encoding="utf-8")

        return ToolResult(
            success=True,
            output=f"Created solution: {sln_path}"
        )

    def _create_cpp_project(
        self,
        path: str,
        name: str,
        project_type: str
    ) -> ToolResult:
        """Create a C++ project."""
        project_dir = Path(path) / name
        project_dir.mkdir(parents=True, exist_ok=True)

        # Determine configuration
        if project_type == "console":
            config_type = "Application"
            subsystem = "Console"
            preprocessor_defs = ""
        elif project_type in ("gui", "winforms"):
            config_type = "Application"
            subsystem = "Windows"
            preprocessor_defs = "_WINDOWS;"
        elif project_type == "library":
            config_type = "StaticLibrary"
            subsystem = "Windows"
            preprocessor_defs = "_LIB;"
        elif project_type == "dll":
            config_type = "DynamicLibrary"
            subsystem = "Windows"
            preprocessor_defs = "_USRDLL;"
        else:
            config_type = "Application"
            subsystem = "Console"
            preprocessor_defs = ""

        # Create main.cpp
        if project_type == "gui":
            main_content = '''#include <windows.h>

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance,
                   LPSTR lpCmdLine, int nCmdShow)
{
    MessageBox(NULL, L"Hello, Windows!", L"{name}", MB_OK);
    return 0;
}
'''.replace("{name}", name)
        else:
            main_content = '''#include <iostream>

int main()
{
    std::cout << "Hello, World!" << std::endl;
    return 0;
}
'''

        main_path = project_dir / "main.cpp"
        main_path.write_text(main_content, encoding="utf-8")

        # Create vcxproj
        vcxproj_content = VCXPROJ_TEMPLATE.format(
            project_guid=self._generate_guid(),
            project_name=name,
            config_type=config_type,
            subsystem=subsystem,
            preprocessor_defs=preprocessor_defs,
            source_files='    <ClCompile Include="main.cpp" />',
            header_files=""
        )

        vcxproj_path = project_dir / f"{name}.vcxproj"
        vcxproj_path.write_text(vcxproj_content, encoding="utf-8")

        return ToolResult(
            success=True,
            output=f"Created C++ project: {vcxproj_path}\nMain file: {main_path}"
        )

    def _create_dotnet_project(
        self,
        path: str,
        name: str,
        project_type: str,
        framework: str
    ) -> ToolResult:
        """Create a .NET project."""
        project_dir = Path(path) / name
        project_dir.mkdir(parents=True, exist_ok=True)

        # Determine SDK and output type
        sdk_suffix = ""
        output_type = "Exe"
        additional_props = ""
        item_groups = ""

        if project_type == "winforms":
            sdk_suffix = ".WindowsDesktop"
            additional_props = "    <UseWindowsForms>true</UseWindowsForms>"
        elif project_type == "wpf":
            sdk_suffix = ".WindowsDesktop"
            additional_props = "    <UseWPF>true</UseWPF>"
        elif project_type == "library":
            output_type = "Library"
        elif project_type == "webapi":
            sdk_suffix = ".Web"
        elif project_type == "blazor":
            sdk_suffix = ".Web"
            additional_props = "    <UseBlazorWebAssembly>true</UseBlazorWebAssembly>"

        # Create csproj
        csproj_content = CSPROJ_TEMPLATE.format(
            sdk_suffix=sdk_suffix,
            output_type=output_type,
            target_framework=framework,
            additional_props=additional_props,
            item_groups=item_groups
        )

        csproj_path = project_dir / f"{name}.csproj"
        csproj_path.write_text(csproj_content, encoding="utf-8")

        # Create Program.cs
        if project_type == "winforms":
            program_content = '''namespace {name};

static class Program
{{
    [STAThread]
    static void Main()
    {{
        ApplicationConfiguration.Initialize();
        Application.Run(new MainForm());
    }}
}}
'''.replace("{name}", name)

            # Create MainForm
            form_content = '''namespace {name};

public partial class MainForm : Form
{{
    public MainForm()
    {{
        InitializeComponent();
        this.Text = "{name}";
        this.Size = new Size(800, 600);
    }}
}}
'''.replace("{name}", name)

            designer_content = '''namespace {name};

partial class MainForm
{{
    private System.ComponentModel.IContainer components = null;

    protected override void Dispose(bool disposing)
    {{
        if (disposing && (components != null))
        {{
            components.Dispose();
        }}
        base.Dispose(disposing);
    }}

    private void InitializeComponent()
    {{
        this.SuspendLayout();
        this.AutoScaleDimensions = new System.Drawing.SizeF(7F, 15F);
        this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
        this.ClientSize = new System.Drawing.Size(800, 450);
        this.Name = "MainForm";
        this.Text = "{name}";
        this.ResumeLayout(false);
    }}
}}
'''.replace("{name}", name)

            (project_dir / "Program.cs").write_text(program_content, encoding="utf-8")
            (project_dir / "MainForm.cs").write_text(form_content, encoding="utf-8")
            (project_dir / "MainForm.Designer.cs").write_text(designer_content, encoding="utf-8")

        elif project_type == "wpf":
            program_content = '''namespace {name};

public partial class App : Application
{{
}}
'''.replace("{name}", name)

            mainwindow_content = '''namespace {name};

public partial class MainWindow : Window
{{
    public MainWindow()
    {{
        InitializeComponent();
    }}
}}
'''.replace("{name}", name)

            xaml_content = '''<Window x:Class="{name}.MainWindow"
        xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="{name}" Height="450" Width="800">
    <Grid>
        <TextBlock Text="Hello, WPF!" HorizontalAlignment="Center"
                   VerticalAlignment="Center" FontSize="24"/>
    </Grid>
</Window>
'''.replace("{name}", name)

            (project_dir / "App.xaml.cs").write_text(program_content, encoding="utf-8")
            (project_dir / "MainWindow.xaml.cs").write_text(mainwindow_content, encoding="utf-8")
            (project_dir / "MainWindow.xaml").write_text(xaml_content, encoding="utf-8")

        else:
            program_content = '''Console.WriteLine("Hello, World!");
'''
            (project_dir / "Program.cs").write_text(program_content, encoding="utf-8")

        return ToolResult(
            success=True,
            output=f"Created .NET {project_type} project: {csproj_path}"
        )

    def _add_to_solution(self, sln_path: str, project_path: str) -> ToolResult:
        """Add a project to a solution."""
        sln_file = Path(sln_path)
        proj_file = Path(project_path)

        if not sln_file.exists():
            return ToolResult(success=False, output="", error="Solution not found")
        if not proj_file.exists():
            return ToolResult(success=False, output="", error="Project not found")

        # Determine project type GUID
        ext = proj_file.suffix.lower()
        if ext == ".vcxproj":
            type_guid = "8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942"  # C++
        elif ext == ".csproj":
            type_guid = "FAE04EC0-301F-11D3-BF4B-00C04F79EFBC"  # C#
        elif ext == ".fsproj":
            type_guid = "F2A71F9B-5D33-465A-A702-920D77279786"  # F#
        else:
            type_guid = "FAE04EC0-301F-11D3-BF4B-00C04F79EFBC"  # Default to C#

        project_guid = self._generate_guid()
        project_name = proj_file.stem
        rel_path = os.path.relpath(proj_file, sln_file.parent)

        # Read existing solution
        content = sln_file.read_text(encoding="utf-8")

        # Add project entry before Global section
        project_line = f'Project("{{{type_guid}}}") = "{project_name}", "{rel_path}", "{{{project_guid}}}"\nEndProject\n'

        if "Global" in content:
            content = content.replace("Global", project_line + "Global")
        else:
            content += project_line

        sln_file.write_text(content, encoding="utf-8")

        return ToolResult(
            success=True,
            output=f"Added {project_name} to solution"
        )

    def _analyze_project(self, path: str) -> ToolResult:
        """Analyze a project structure."""
        proj_path = Path(path)
        if not proj_path.exists():
            return ToolResult(success=False, output="", error="Path not found")

        analysis = []

        # Find all project files
        vcxproj_files = list(proj_path.rglob("*.vcxproj"))
        csproj_files = list(proj_path.rglob("*.csproj"))
        sln_files = list(proj_path.rglob("*.sln"))

        analysis.append(f"Project Analysis: {proj_path}")
        analysis.append("-" * 50)

        if sln_files:
            analysis.append(f"Solutions: {len(sln_files)}")
            for sln in sln_files:
                analysis.append(f"  - {sln.name}")

        if vcxproj_files:
            analysis.append(f"\nC++ Projects: {len(vcxproj_files)}")
            for proj in vcxproj_files:
                analysis.append(f"  - {proj.name}")
                # Try to parse project type
                try:
                    tree = ET.parse(proj)
                    root = tree.getroot()
                    ns = {"ms": "http://schemas.microsoft.com/developer/msbuild/2003"}
                    config_type = root.find(".//ms:ConfigurationType", ns)
                    if config_type is not None:
                        analysis.append(f"    Type: {config_type.text}")
                except Exception:
                    pass

        if csproj_files:
            analysis.append(f"\n.NET Projects: {len(csproj_files)}")
            for proj in csproj_files:
                analysis.append(f"  - {proj.name}")
                try:
                    tree = ET.parse(proj)
                    root = tree.getroot()
                    tf = root.find(".//TargetFramework")
                    if tf is not None:
                        analysis.append(f"    Framework: {tf.text}")
                    output = root.find(".//OutputType")
                    if output is not None:
                        analysis.append(f"    Output: {output.text}")
                except Exception:
                    pass

        # Count source files
        cpp_files = list(proj_path.rglob("*.cpp")) + list(proj_path.rglob("*.c"))
        h_files = list(proj_path.rglob("*.h")) + list(proj_path.rglob("*.hpp"))
        cs_files = list(proj_path.rglob("*.cs"))
        xaml_files = list(proj_path.rglob("*.xaml"))

        analysis.append(f"\nSource Files:")
        if cpp_files:
            analysis.append(f"  C/C++: {len(cpp_files)} source, {len(h_files)} headers")
        if cs_files:
            analysis.append(f"  C#: {len(cs_files)} files")
        if xaml_files:
            analysis.append(f"  XAML: {len(xaml_files)} files")

        return ToolResult(success=True, output="\n".join(analysis))

    def _build_project(self, path: str, configuration: str = "Debug") -> ToolResult:
        """Build a project using MSBuild."""
        proj_path = Path(path)
        if not proj_path.exists():
            return ToolResult(success=False, output="", error="Project not found")

        # Find MSBuild
        msbuild_paths = [
            r"C:\Program Files\Microsoft Visual Studio\2022\Enterprise\MSBuild\Current\Bin\MSBuild.exe",
            r"C:\Program Files\Microsoft Visual Studio\2022\Professional\MSBuild\Current\Bin\MSBuild.exe",
            r"C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe",
            r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Enterprise\MSBuild\Current\Bin\MSBuild.exe",
            r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\MSBuild\Current\Bin\MSBuild.exe",
        ]

        msbuild = None
        for path_candidate in msbuild_paths:
            if Path(path_candidate).exists():
                msbuild = path_candidate
                break

        if not msbuild:
            # Try dotnet build for .NET projects
            if proj_path.suffix == ".csproj":
                try:
                    result = subprocess.run(
                        ["dotnet", "build", str(proj_path), "-c", configuration],
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    return ToolResult(
                        success=result.returncode == 0,
                        output=result.stdout,
                        error=result.stderr if result.returncode != 0 else None
                    )
                except Exception as e:
                    return ToolResult(success=False, output="", error=str(e))

            return ToolResult(
                success=False,
                output="",
                error="MSBuild not found. Install Visual Studio or use 'dotnet build' for .NET projects."
            )

        try:
            result = subprocess.run(
                [msbuild, str(proj_path), f"/p:Configuration={configuration}", "/m"],
                capture_output=True,
                text=True,
                timeout=600
            )
            return ToolResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr if result.returncode != 0 else None
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error="Build timed out")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
