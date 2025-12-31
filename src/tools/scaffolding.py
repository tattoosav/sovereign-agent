"""
Project Scaffolding Tool.

Generate complete project structures with best practices
for various project types and frameworks.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class ProjectTemplate:
    """A project template definition."""
    name: str
    description: str
    language: str
    framework: str
    files: dict[str, str]  # path -> content
    dependencies: list[str]
    dev_dependencies: list[str]
    scripts: dict[str, str]


# Project templates
TEMPLATES = {
    "python-cli": ProjectTemplate(
        name="Python CLI Application",
        description="Command-line application with click",
        language="python",
        framework="click",
        files={
            "src/__init__.py": "",
            "src/main.py": '''"""Main entry point."""
import click

@click.group()
@click.version_option()
def cli():
    """Application description."""
    pass

@cli.command()
@click.argument("name")
def hello(name: str):
    """Say hello."""
    click.echo(f"Hello, {name}!")

if __name__ == "__main__":
    cli()
''',
            "src/config.py": '''"""Configuration management."""
from dataclasses import dataclass
from pathlib import Path
import yaml

@dataclass
class Config:
    debug: bool = False
    log_level: str = "INFO"

    @classmethod
    def load(cls, path: Path) -> "Config":
        if path.exists():
            with open(path) as f:
                data = yaml.safe_load(f)
                return cls(**data)
        return cls()
''',
            "tests/__init__.py": "",
            "tests/test_main.py": '''"""Tests for main module."""
from click.testing import CliRunner
from src.main import cli

def test_hello():
    runner = CliRunner()
    result = runner.invoke(cli, ["hello", "World"])
    assert result.exit_code == 0
    assert "Hello, World!" in result.output
''',
            "pyproject.toml": '''[project]
name = "{project_name}"
version = "0.1.0"
description = "{description}"
requires-python = ">=3.11"
dependencies = [
    "click>=8.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "ruff>=0.1",
    "mypy>=1.0",
]

[project.scripts]
{project_name} = "src.main:cli"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = true
''',
            "README.md": '''# {project_name}

{description}

## Installation

```bash
pip install -e ".[dev]"
```

## Usage

```bash
{project_name} --help
```

## Development

```bash
# Run tests
pytest

# Type check
mypy src/

# Lint
ruff check src/
```
''',
            ".gitignore": '''__pycache__/
*.py[cod]
*$py.class
.venv/
dist/
*.egg-info/
.mypy_cache/
.pytest_cache/
.ruff_cache/
.coverage
''',
        },
        dependencies=["click", "pyyaml"],
        dev_dependencies=["pytest", "pytest-cov", "ruff", "mypy"],
        scripts={"test": "pytest", "lint": "ruff check src/", "typecheck": "mypy src/"},
    ),

    "python-api": ProjectTemplate(
        name="Python FastAPI Application",
        description="REST API with FastAPI",
        language="python",
        framework="fastapi",
        files={
            "src/__init__.py": "",
            "src/main.py": '''"""FastAPI application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import router
from src.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/health")
async def health():
    return {"status": "healthy"}
''',
            "src/config.py": '''"""Application configuration."""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "My API"
    debug: bool = False
    database_url: str = "sqlite:///./app.db"

    class Config:
        env_file = ".env"

settings = Settings()
''',
            "src/api/__init__.py": '''"""API routes."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

@router.get("/items")
async def list_items():
    return {"items": []}

@router.post("/items")
async def create_item(data: dict):
    return {"created": data}
''',
            "src/models.py": '''"""Database models."""
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
''',
            "tests/__init__.py": "",
            "tests/test_api.py": '''"""API tests."""
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_list_items():
    response = client.get("/api/v1/items")
    assert response.status_code == 200
''',
            "pyproject.toml": '''[project]
name = "{project_name}"
version = "0.1.0"
description = "{description}"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.100",
    "uvicorn[standard]>=0.20",
    "pydantic-settings>=2.0",
    "sqlalchemy>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "httpx>=0.24",
    "ruff>=0.1",
    "mypy>=1.0",
]
''',
            ".env.example": '''APP_NAME=My API
DEBUG=false
DATABASE_URL=sqlite:///./app.db
''',
        },
        dependencies=["fastapi", "uvicorn", "pydantic-settings", "sqlalchemy"],
        dev_dependencies=["pytest", "httpx", "ruff", "mypy"],
        scripts={"dev": "uvicorn src.main:app --reload", "test": "pytest"},
    ),

    "cpp-console": ProjectTemplate(
        name="C++ Console Application",
        description="Modern C++ console application with CMake",
        language="cpp",
        framework="cmake",
        files={
            "src/main.cpp": '''#include <iostream>
#include <string>
#include <format>

int main(int argc, char* argv[]) {
    std::cout << std::format("Hello, {}!", "World") << std::endl;
    return 0;
}
''',
            "include/{project_name}/config.hpp": '''#pragma once

#include <string>
#include <optional>

namespace {project_name} {{

struct Config {{
    bool debug = false;
    std::string log_level = "INFO";

    static std::optional<Config> load(const std::string& path);
}};

}} // namespace {project_name}
''',
            "src/config.cpp": '''#include "{project_name}/config.hpp"
#include <fstream>

namespace {project_name} {{

std::optional<Config> Config::load(const std::string& path) {{
    std::ifstream file(path);
    if (!file.is_open()) {{
        return std::nullopt;
    }}
    // Parse config...
    return Config{{}};
}}

}} // namespace {project_name}
''',
            "tests/test_main.cpp": '''#include <gtest/gtest.h>

TEST(MainTest, BasicTest) {
    EXPECT_EQ(1, 1);
}

int main(int argc, char** argv) {
    testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
''',
            "CMakeLists.txt": '''cmake_minimum_required(VERSION 3.20)
project({project_name} VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Main executable
add_executable(${{PROJECT_NAME}}
    src/main.cpp
    src/config.cpp
)
target_include_directories(${{PROJECT_NAME}} PRIVATE include)

# Tests
enable_testing()
find_package(GTest QUIET)
if(GTest_FOUND)
    add_executable(tests tests/test_main.cpp)
    target_link_libraries(tests GTest::gtest GTest::gtest_main)
    add_test(NAME tests COMMAND tests)
endif()
''',
            ".clang-format": '''BasedOnStyle: Google
IndentWidth: 4
ColumnLimit: 100
BreakBeforeBraces: Attach
''',
            ".gitignore": '''build/
.cache/
compile_commands.json
*.o
*.obj
*.exe
''',
        },
        dependencies=[],
        dev_dependencies=["gtest"],
        scripts={"build": "cmake -B build && cmake --build build", "test": "ctest --test-dir build"},
    ),

    "dotnet-webapi": ProjectTemplate(
        name=".NET Web API",
        description="ASP.NET Core Web API with best practices",
        language="csharp",
        framework="aspnetcore",
        files={
            "Program.cs": '''var builder = WebApplication.CreateBuilder(args);

// Add services
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

var app = builder.Build();

// Configure pipeline
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseHttpsRedirection();
app.UseAuthorization();
app.MapControllers();

app.Run();
''',
            "Controllers/ItemsController.cs": '''using Microsoft.AspNetCore.Mvc;

namespace {project_name}.Controllers;

[ApiController]
[Route("api/[controller]")]
public class ItemsController : ControllerBase
{
    private readonly ILogger<ItemsController> _logger;

    public ItemsController(ILogger<ItemsController> logger)
    {
        _logger = logger;
    }

    [HttpGet]
    public ActionResult<IEnumerable<Item>> GetAll()
    {
        return Ok(new List<Item>());
    }

    [HttpGet("{id}")]
    public ActionResult<Item> GetById(int id)
    {
        return Ok(new Item { Id = id, Name = "Sample" });
    }

    [HttpPost]
    public ActionResult<Item> Create(Item item)
    {
        return CreatedAtAction(nameof(GetById), new { id = item.Id }, item);
    }
}

public record Item
{
    public int Id { get; init; }
    public string Name { get; init; } = "";
}
''',
            "{project_name}.csproj": '''<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>

  <ItemGroup>
    <PackageReference Include="Swashbuckle.AspNetCore" Version="6.5.0" />
  </ItemGroup>
</Project>
''',
            "appsettings.json": '''{
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "Microsoft.AspNetCore": "Warning"
    }
  },
  "AllowedHosts": "*"
}
''',
            ".gitignore": '''bin/
obj/
.vs/
*.user
appsettings.Development.json
''',
        },
        dependencies=["Swashbuckle.AspNetCore"],
        dev_dependencies=[],
        scripts={"run": "dotnet run", "build": "dotnet build", "test": "dotnet test"},
    ),

    "dotnet-winforms": ProjectTemplate(
        name=".NET WinForms Application",
        description="Windows Forms desktop application",
        language="csharp",
        framework="winforms",
        files={
            "Program.cs": '''namespace {project_name};

static class Program
{
    [STAThread]
    static void Main()
    {
        ApplicationConfiguration.Initialize();
        Application.Run(new MainForm());
    }
}
''',
            "MainForm.cs": '''namespace {project_name};

public partial class MainForm : Form
{
    public MainForm()
    {
        InitializeComponent();
        SetupUI();
    }

    private void SetupUI()
    {
        this.Text = "{project_name}";
        this.Size = new Size(800, 600);
        this.StartPosition = FormStartPosition.CenterScreen;

        var menuStrip = new MenuStrip();
        var fileMenu = new ToolStripMenuItem("File");
        fileMenu.DropDownItems.Add("Exit", null, (s, e) => Application.Exit());
        menuStrip.Items.Add(fileMenu);
        this.MainMenuStrip = menuStrip;
        this.Controls.Add(menuStrip);

        var statusStrip = new StatusStrip();
        statusStrip.Items.Add(new ToolStripStatusLabel("Ready"));
        this.Controls.Add(statusStrip);
    }
}
''',
            "MainForm.Designer.cs": '''namespace {project_name};

partial class MainForm
{
    private System.ComponentModel.IContainer components = null;

    protected override void Dispose(bool disposing)
    {
        if (disposing && (components != null))
        {
            components.Dispose();
        }
        base.Dispose(disposing);
    }

    private void InitializeComponent()
    {
        this.SuspendLayout();
        this.AutoScaleDimensions = new System.Drawing.SizeF(7F, 15F);
        this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
        this.ClientSize = new System.Drawing.Size(800, 450);
        this.Name = "MainForm";
        this.ResumeLayout(false);
    }
}
''',
            "{project_name}.csproj": '''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>WinExe</OutputType>
    <TargetFramework>net8.0-windows</TargetFramework>
    <Nullable>enable</Nullable>
    <UseWindowsForms>true</UseWindowsForms>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
</Project>
''',
        },
        dependencies=[],
        dev_dependencies=[],
        scripts={"run": "dotnet run", "build": "dotnet build", "publish": "dotnet publish -c Release"},
    ),

    "dotnet-wpf": ProjectTemplate(
        name=".NET WPF Application",
        description="WPF desktop application with MVVM",
        language="csharp",
        framework="wpf",
        files={
            "App.xaml": '''<Application x:Class="{project_name}.App"
             xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
             xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
             StartupUri="MainWindow.xaml">
    <Application.Resources>
    </Application.Resources>
</Application>
''',
            "App.xaml.cs": '''namespace {project_name};

public partial class App : Application
{
}
''',
            "MainWindow.xaml": '''<Window x:Class="{project_name}.MainWindow"
        xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        xmlns:vm="clr-namespace:{project_name}.ViewModels"
        Title="{project_name}" Height="450" Width="800">
    <Window.DataContext>
        <vm:MainViewModel />
    </Window.DataContext>
    <Grid>
        <Grid.RowDefinitions>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="*"/>
            <RowDefinition Height="Auto"/>
        </Grid.RowDefinitions>

        <Menu Grid.Row="0">
            <MenuItem Header="_File">
                <MenuItem Header="_Exit" Command="{Binding ExitCommand}"/>
            </MenuItem>
        </Menu>

        <TextBlock Grid.Row="1" Text="{Binding WelcomeMessage}"
                   HorizontalAlignment="Center" VerticalAlignment="Center"
                   FontSize="24"/>

        <StatusBar Grid.Row="2">
            <StatusBarItem Content="{Binding StatusMessage}"/>
        </StatusBar>
    </Grid>
</Window>
''',
            "MainWindow.xaml.cs": '''namespace {project_name};

public partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
    }
}
''',
            "ViewModels/ViewModelBase.cs": '''using System.ComponentModel;
using System.Runtime.CompilerServices;

namespace {project_name}.ViewModels;

public class ViewModelBase : INotifyPropertyChanged
{
    public event PropertyChangedEventHandler? PropertyChanged;

    protected void OnPropertyChanged([CallerMemberName] string? name = null)
        => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));

    protected bool SetProperty<T>(ref T field, T value, [CallerMemberName] string? name = null)
    {
        if (EqualityComparer<T>.Default.Equals(field, value)) return false;
        field = value;
        OnPropertyChanged(name);
        return true;
    }
}
''',
            "ViewModels/MainViewModel.cs": '''using System.Windows.Input;

namespace {project_name}.ViewModels;

public class MainViewModel : ViewModelBase
{
    private string _welcomeMessage = "Welcome to {project_name}!";
    private string _statusMessage = "Ready";

    public string WelcomeMessage
    {
        get => _welcomeMessage;
        set => SetProperty(ref _welcomeMessage, value);
    }

    public string StatusMessage
    {
        get => _statusMessage;
        set => SetProperty(ref _statusMessage, value);
    }

    public ICommand ExitCommand { get; }

    public MainViewModel()
    {
        ExitCommand = new RelayCommand(_ => System.Windows.Application.Current.Shutdown());
    }
}

public class RelayCommand : ICommand
{
    private readonly Action<object?> _execute;
    private readonly Predicate<object?>? _canExecute;

    public RelayCommand(Action<object?> execute, Predicate<object?>? canExecute = null)
    {
        _execute = execute;
        _canExecute = canExecute;
    }

    public event EventHandler? CanExecuteChanged
    {
        add => CommandManager.RequerySuggested += value;
        remove => CommandManager.RequerySuggested -= value;
    }

    public bool CanExecute(object? parameter) => _canExecute?.Invoke(parameter) ?? true;
    public void Execute(object? parameter) => _execute(parameter);
}
''',
            "{project_name}.csproj": '''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>WinExe</OutputType>
    <TargetFramework>net8.0-windows</TargetFramework>
    <Nullable>enable</Nullable>
    <UseWPF>true</UseWPF>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
</Project>
''',
        },
        dependencies=[],
        dev_dependencies=[],
        scripts={"run": "dotnet run", "build": "dotnet build"},
    ),
}


class ScaffoldingTool(BaseTool):
    """Tool for generating project scaffolding."""

    name = "scaffold"
    description = """Generate complete project structures.

Templates available:
- python-cli: Python CLI application with click
- python-api: FastAPI REST API
- cpp-console: C++ console app with CMake
- dotnet-webapi: ASP.NET Core Web API
- dotnet-winforms: Windows Forms application
- dotnet-wpf: WPF application with MVVM

Use 'list' operation to see all templates.
"""
    parameters = {
        "operation": "Operation: create, list, info",
        "template": "Template name (e.g., python-cli)",
        "path": "Output directory path",
        "project_name": "Name of the project",
        "description": "Project description",
    }

    def execute(
        self,
        operation: str,
        template: str = "",
        path: str = ".",
        project_name: str = "my_project",
        description: str = "A new project",
        **kwargs: Any
    ) -> ToolResult:
        """Execute scaffolding operation."""
        try:
            if operation == "list":
                return self._list_templates()
            elif operation == "info":
                return self._template_info(template)
            elif operation == "create":
                return self._create_project(template, path, project_name, description)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Unknown operation: {operation}"
                )
        except Exception as e:
            logger.exception(f"Scaffolding error: {e}")
            return ToolResult(success=False, output="", error=str(e))

    def _list_templates(self) -> ToolResult:
        """List all available templates."""
        lines = ["Available Project Templates:", "=" * 40]
        for key, template in TEMPLATES.items():
            lines.append(f"\n{key}")
            lines.append(f"  {template.name}")
            lines.append(f"  Language: {template.language}")
            lines.append(f"  Framework: {template.framework}")
            lines.append(f"  {template.description}")
        return ToolResult(success=True, output="\n".join(lines))

    def _template_info(self, template_name: str) -> ToolResult:
        """Get detailed info about a template."""
        template = TEMPLATES.get(template_name)
        if not template:
            return ToolResult(
                success=False,
                output="",
                error=f"Template not found: {template_name}"
            )

        lines = [
            f"Template: {template.name}",
            f"Language: {template.language}",
            f"Framework: {template.framework}",
            f"Description: {template.description}",
            "",
            "Files:",
        ]
        for file_path in template.files.keys():
            lines.append(f"  - {file_path}")

        if template.dependencies:
            lines.append("\nDependencies:")
            for dep in template.dependencies:
                lines.append(f"  - {dep}")

        if template.scripts:
            lines.append("\nScripts:")
            for name, cmd in template.scripts.items():
                lines.append(f"  {name}: {cmd}")

        return ToolResult(success=True, output="\n".join(lines))

    def _create_project(
        self,
        template_name: str,
        path: str,
        project_name: str,
        description: str
    ) -> ToolResult:
        """Create a new project from template."""
        template = TEMPLATES.get(template_name)
        if not template:
            return ToolResult(
                success=False,
                output="",
                error=f"Template not found: {template_name}"
            )

        project_dir = Path(path) / project_name
        project_dir.mkdir(parents=True, exist_ok=True)

        created_files = []
        for file_path, content in template.files.items():
            # Replace placeholders
            file_path = file_path.replace("{project_name}", project_name)
            content = content.replace("{project_name}", project_name)
            content = content.replace("{description}", description)

            full_path = project_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
            created_files.append(file_path)

        output_lines = [
            f"Created project: {project_name}",
            f"Location: {project_dir}",
            f"Template: {template.name}",
            "",
            "Files created:",
        ]
        for f in created_files:
            output_lines.append(f"  - {f}")

        if template.scripts:
            output_lines.append("\nNext steps:")
            output_lines.append(f"  cd {project_name}")
            for name, cmd in list(template.scripts.items())[:3]:
                output_lines.append(f"  {cmd}  # {name}")

        return ToolResult(success=True, output="\n".join(output_lines))
