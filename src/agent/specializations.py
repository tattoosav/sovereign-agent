"""
Language and Framework Specializations.

Provides specialized knowledge and prompts for different
programming languages and frameworks.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Specialization(Enum):
    """Available specializations."""
    GENERAL = "general"
    CPP = "cpp"
    CPP_GUI = "cpp_gui"
    DOTNET = "dotnet"
    WINFORMS = "winforms"
    WPF = "wpf"
    QT = "qt"
    UNREAL = "unreal"
    GAME_DEV = "game_dev"
    FIVEM = "fivem"
    GAME_OVERLAY = "game_overlay"


@dataclass
class SpecializationConfig:
    """Configuration for a specialization."""
    name: str
    description: str
    file_extensions: list[str]
    frameworks: list[str]
    system_prompt_additions: str
    best_practices: list[str]
    common_patterns: dict[str, str]
    debugging_tips: list[str]


# Specialization definitions
SPECIALIZATIONS: dict[Specialization, SpecializationConfig] = {
    Specialization.CPP: SpecializationConfig(
        name="C++ Development",
        description="Modern C++ (C++17/20/23) development",
        file_extensions=[".cpp", ".c", ".h", ".hpp", ".cc", ".cxx"],
        frameworks=["STL", "Boost", "fmt", "spdlog", "nlohmann/json"],
        system_prompt_additions="""
## C++ Expertise

You are an expert C++ developer with deep knowledge of:
- Modern C++ (C++17, C++20, C++23 features)
- Memory management (RAII, smart pointers, move semantics)
- Template metaprogramming and concepts
- STL containers and algorithms
- Performance optimization and profiling
- Build systems (CMake, MSBuild, Ninja)

### Best Practices
- Use RAII for resource management
- Prefer smart pointers over raw pointers
- Use `const` and `constexpr` liberally
- Leverage move semantics for performance
- Use `std::string_view` for read-only string parameters
- Prefer `std::array` over C-style arrays
- Use range-based for loops
- Apply the Rule of Zero/Five

### Code Style
- Use `nullptr` instead of `NULL`
- Use `auto` for complex types, explicit types for clarity
- Prefer `enum class` over plain `enum`
- Use `[[nodiscard]]` for functions that shouldn't ignore returns
- Use structured bindings for cleaner code
""",
        best_practices=[
            "Use smart pointers (unique_ptr, shared_ptr) instead of raw pointers",
            "Apply RAII for all resource management",
            "Prefer references over pointers when null is not valid",
            "Use const-correctness throughout",
            "Leverage move semantics for performance",
            "Use std::optional for nullable values",
            "Prefer std::variant over unions",
            "Use concepts for template constraints (C++20)",
        ],
        common_patterns={
            "singleton": '''class Singleton {
public:
    static Singleton& instance() {
        static Singleton instance;
        return instance;
    }
    Singleton(const Singleton&) = delete;
    Singleton& operator=(const Singleton&) = delete;
private:
    Singleton() = default;
};''',
            "pimpl": '''// Header
class Widget {
public:
    Widget();
    ~Widget();
    void doSomething();
private:
    struct Impl;
    std::unique_ptr<Impl> pImpl;
};

// Source
struct Widget::Impl {
    // Implementation details
};
Widget::Widget() : pImpl(std::make_unique<Impl>()) {}
Widget::~Widget() = default;''',
            "observer": '''template<typename... Args>
class Signal {
    std::vector<std::function<void(Args...)>> slots;
public:
    void connect(std::function<void(Args...)> slot) {
        slots.push_back(std::move(slot));
    }
    void emit(Args... args) {
        for (auto& slot : slots) slot(args...);
    }
};''',
        },
        debugging_tips=[
            "Use AddressSanitizer (-fsanitize=address) for memory errors",
            "Use Valgrind for memory leak detection",
            "Enable all warnings: -Wall -Wextra -Wpedantic",
            "Use static analyzers: clang-tidy, cppcheck",
            "Debug with gdb/lldb or Visual Studio debugger",
        ],
    ),

    Specialization.CPP_GUI: SpecializationConfig(
        name="C++ GUI Development",
        description="Windows GUI development with C++ (Win32, MFC)",
        file_extensions=[".cpp", ".c", ".h", ".hpp", ".rc", ".def"],
        frameworks=["Win32", "MFC", "ATL", "WTL", "DirectX"],
        system_prompt_additions="""
## C++ Windows GUI Expertise

You are an expert in Windows GUI development with C++:
- Win32 API programming
- Modern Windows UI (WinUI 3)
- MFC and ATL frameworks
- DirectX/Direct2D graphics
- COM programming
- Windows message handling

### Win32 Window Creation Pattern
```cpp
LRESULT CALLBACK WndProc(HWND hWnd, UINT message, WPARAM wParam, LPARAM lParam) {
    switch (message) {
    case WM_CREATE:
        // Initialize
        break;
    case WM_PAINT: {
        PAINTSTRUCT ps;
        HDC hdc = BeginPaint(hWnd, &ps);
        // Paint
        EndPaint(hWnd, &ps);
        break;
    }
    case WM_DESTROY:
        PostQuitMessage(0);
        break;
    default:
        return DefWindowProc(hWnd, message, wParam, lParam);
    }
    return 0;
}
```

### Best Practices
- Use RAII wrappers for Windows handles
- Handle WM_DESTROY and cleanup properly
- Use Unicode (WCHAR) for text
- Validate all user input
- Handle DPI awareness for modern displays
""",
        best_practices=[
            "Use Unicode (WCHAR/wstring) for all text",
            "Create RAII wrappers for handles (HWND, HDC, etc.)",
            "Handle window messages efficiently",
            "Use double buffering for flicker-free drawing",
            "Support high DPI displays",
            "Handle WM_CLOSE vs WM_DESTROY correctly",
        ],
        common_patterns={
            "handle_wrapper": '''template<typename HandleType, typename Deleter>
class HandleWrapper {
    HandleType handle;
    Deleter deleter;
public:
    explicit HandleWrapper(HandleType h, Deleter d)
        : handle(h), deleter(d) {}
    ~HandleWrapper() { if (handle) deleter(handle); }
    operator HandleType() const { return handle; }
};''',
        },
        debugging_tips=[
            "Use Spy++ to analyze window messages",
            "Use Process Monitor for file/registry access",
            "Enable Application Verifier for runtime checks",
            "Use WinDbg for kernel-level debugging",
        ],
    ),

    Specialization.DOTNET: SpecializationConfig(
        name=".NET Development",
        description="Modern .NET (6/7/8) development with C#",
        file_extensions=[".cs", ".csproj", ".sln", ".razor", ".cshtml"],
        frameworks=[".NET 8", "ASP.NET Core", "Entity Framework", "MAUI"],
        system_prompt_additions="""
## .NET Expertise

You are an expert .NET developer with deep knowledge of:
- Modern C# (10, 11, 12 features)
- .NET 8 and latest runtime features
- ASP.NET Core for web development
- Entity Framework Core for data access
- Dependency Injection patterns
- Async/await and Task-based programming

### Best Practices
- Use nullable reference types
- Prefer `record` for immutable data types
- Use `IAsyncEnumerable` for streaming data
- Apply the Options pattern for configuration
- Use minimal APIs for simple endpoints
- Leverage source generators for performance

### Code Style
```csharp
// Modern C# patterns
public record Person(string Name, int Age);

// Nullable reference types
public string? GetValue(string key) => _dict.GetValueOrDefault(key);

// Pattern matching
var result = obj switch {
    int n when n > 0 => "positive",
    int n when n < 0 => "negative",
    _ => "zero or null"
};

// File-scoped namespaces
namespace MyApp;

public class Service { }
```
""",
        best_practices=[
            "Enable nullable reference types",
            "Use dependency injection",
            "Prefer async/await for I/O operations",
            "Use ILogger for logging",
            "Apply the repository pattern for data access",
            "Use records for DTOs",
            "Leverage LINQ efficiently",
        ],
        common_patterns={
            "repository": '''public interface IRepository<T> where T : class {
    Task<T?> GetByIdAsync(int id);
    Task<IEnumerable<T>> GetAllAsync();
    Task AddAsync(T entity);
    Task UpdateAsync(T entity);
    Task DeleteAsync(int id);
}''',
            "options": '''public class MyOptions {
    public const string SectionName = "MySection";
    public string Setting1 { get; set; } = "";
    public int Setting2 { get; set; }
}
// Registration
services.Configure<MyOptions>(config.GetSection(MyOptions.SectionName));''',
        },
        debugging_tips=[
            "Use dotnet watch for hot reload",
            "Enable detailed errors in Development",
            "Use the debugger's Exception Settings",
            "Profile with dotnet-trace and dotnet-counters",
        ],
    ),

    Specialization.WINFORMS: SpecializationConfig(
        name="WinForms Development",
        description="Windows Forms desktop application development",
        file_extensions=[".cs", ".Designer.cs", ".resx", ".csproj"],
        frameworks=["WinForms", ".NET 8", "System.Drawing"],
        system_prompt_additions="""
## WinForms Expertise

You are an expert in Windows Forms development:
- Form and control design
- Custom control creation
- Data binding
- MDI applications
- Drag and drop
- Printing and reporting

### Best Practices
- Use async/await for long operations to keep UI responsive
- Implement IDisposable for forms with resources
- Use data binding for list controls
- Apply MVP or MVVM patterns
- Handle form lifecycle events properly
- Use ErrorProvider for validation feedback

### Common Patterns
```csharp
// Async button handler
private async void btnLoad_Click(object sender, EventArgs e) {
    btnLoad.Enabled = false;
    try {
        var data = await LoadDataAsync();
        dataGridView1.DataSource = data;
    } finally {
        btnLoad.Enabled = true;
    }
}

// Cross-thread UI update
if (InvokeRequired) {
    Invoke(new Action(() => UpdateUI(value)));
} else {
    UpdateUI(value);
}
```
""",
        best_practices=[
            "Use async/await for all I/O operations",
            "Never block the UI thread",
            "Use Invoke/BeginInvoke for cross-thread UI updates",
            "Implement proper disposal of resources",
            "Use BindingSource for data binding",
            "Apply consistent error handling",
        ],
        common_patterns={
            "mvp": '''public interface IMainView {
    string UserInput { get; set; }
    void ShowMessage(string message);
    event EventHandler SubmitClicked;
}

public class MainPresenter {
    private readonly IMainView _view;
    private readonly IService _service;

    public MainPresenter(IMainView view, IService service) {
        _view = view;
        _service = service;
        _view.SubmitClicked += OnSubmit;
    }

    private async void OnSubmit(object? sender, EventArgs e) {
        var result = await _service.ProcessAsync(_view.UserInput);
        _view.ShowMessage(result);
    }
}''',
        },
        debugging_tips=[
            "Use breakpoints in event handlers",
            "Check for cross-thread exceptions",
            "Use the Immediate Window for quick tests",
            "Enable first-chance exceptions for InvalidOperationException",
        ],
    ),

    Specialization.WPF: SpecializationConfig(
        name="WPF Development",
        description="Windows Presentation Foundation development",
        file_extensions=[".xaml", ".xaml.cs", ".cs", ".csproj"],
        frameworks=["WPF", ".NET 8", "MVVM Toolkit", "Prism"],
        system_prompt_additions="""
## WPF Expertise

You are an expert in WPF development:
- XAML and data binding
- MVVM architecture
- Custom controls and templates
- Styles and resources
- Animations and visual states
- Dependency properties

### MVVM Pattern
```csharp
public class MainViewModel : ObservableObject {
    private string _title = "My App";
    public string Title {
        get => _title;
        set => SetProperty(ref _title, value);
    }

    public IRelayCommand LoadCommand { get; }

    public MainViewModel() {
        LoadCommand = new AsyncRelayCommand(LoadAsync);
    }

    private async Task LoadAsync() {
        // Load data
    }
}
```

### XAML Best Practices
```xml
<!-- Use StaticResource for performance -->
<Button Style="{StaticResource PrimaryButton}" />

<!-- Use x:Bind for compile-time checking (UWP/WinUI) -->
<TextBlock Text="{Binding Title}" />

<!-- Use TemplateBinding in control templates -->
<Border Background="{TemplateBinding Background}" />
```
""",
        best_practices=[
            "Use MVVM pattern strictly",
            "Prefer StaticResource over DynamicResource",
            "Use ICommand for button actions",
            "Apply data templates for dynamic content",
            "Use value converters for UI transformations",
            "Keep code-behind minimal",
            "Use dependency properties for custom controls",
        ],
        common_patterns={
            "viewmodel_base": '''public class ViewModelBase : INotifyPropertyChanged {
    public event PropertyChangedEventHandler? PropertyChanged;

    protected void OnPropertyChanged([CallerMemberName] string? name = null)
        => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));

    protected bool SetProperty<T>(ref T field, T value, [CallerMemberName] string? name = null) {
        if (EqualityComparer<T>.Default.Equals(field, value)) return false;
        field = value;
        OnPropertyChanged(name);
        return true;
    }
}''',
            "relay_command": '''public class RelayCommand : ICommand {
    private readonly Action<object?> _execute;
    private readonly Predicate<object?>? _canExecute;

    public RelayCommand(Action<object?> execute, Predicate<object?>? canExecute = null) {
        _execute = execute;
        _canExecute = canExecute;
    }

    public event EventHandler? CanExecuteChanged {
        add => CommandManager.RequerySuggested += value;
        remove => CommandManager.RequerySuggested -= value;
    }

    public bool CanExecute(object? parameter) => _canExecute?.Invoke(parameter) ?? true;
    public void Execute(object? parameter) => _execute(parameter);
}''',
        },
        debugging_tips=[
            "Use Snoop or WPF Inspector for visual tree debugging",
            "Check Output window for binding errors",
            "Use PresentationTraceSources for binding diagnostics",
            "Enable Live Visual Tree in Visual Studio",
        ],
    ),

    Specialization.FIVEM: SpecializationConfig(
        name="FiveM/GTA V Modding",
        description="FiveM server/client development for GTA V multiplayer",
        file_extensions=[".lua", ".js", ".cpp", ".h", ".json", ".cfg"],
        frameworks=["CFX", "CitizenFX", "FiveM", "RedM", "Lua", "NativeUI"],
        system_prompt_additions="""
## FiveM/GTA V Modding Expertise

You are an expert in FiveM and GTA V modding:
- **CFX Framework** - CitizenFX.Core for C#, citizen natives for Lua/JS
- **Resource System** - fxmanifest.lua/resource.lua structure
- **Native Functions** - GTA V native database (natives.altv.mp, nativedb.dotindustries.dev)
- **Networking** - Client/server events, state bags, OneSync
- **Entity Management** - Vehicles, peds, objects, blips
- **UI Systems** - NUI (HTML/CSS/JS), NativeUI, custom draws

### Resource Structure
```
my_resource/
├── fxmanifest.lua      # Resource manifest
├── client/
│   ├── main.lua        # Client-side logic
│   └── nui/            # HTML UI files
├── server/
│   └── main.lua        # Server-side logic
└── shared/
    └── config.lua      # Shared configuration
```

### fxmanifest.lua Template
```lua
fx_version 'cerulean'
game 'gta5'

author 'Your Name'
description 'Resource description'
version '1.0.0'

client_scripts {
    'client/*.lua'
}
server_scripts {
    'server/*.lua'
}
shared_scripts {
    'shared/*.lua'
}
ui_page 'nui/index.html'
files {
    'nui/**/*'
}
```

### Common Patterns

**Drawing on Screen (Client):**
```lua
Citizen.CreateThread(function()
    while true do
        -- Draw text, markers, etc.
        DrawText2D(0.5, 0.5, "Hello World", 0.5)
        Citizen.Wait(0)  -- Required for render loop
    end
end)
```

**Server-Client Communication:**
```lua
-- Server
RegisterNetEvent('myResource:serverEvent')
AddEventHandler('myResource:serverEvent', function(data)
    local source = source
    TriggerClientEvent('myResource:clientResponse', source, result)
end)

-- Client
TriggerServerEvent('myResource:serverEvent', data)
RegisterNetEvent('myResource:clientResponse')
AddEventHandler('myResource:clientResponse', function(result)
    -- Handle response
end)
```

### Best Practices
- Use Citizen.Wait(0) in render loops, higher values elsewhere
- Namespace events to prevent conflicts
- Use state bags for synced data (OneSync)
- Cache frequently used natives
- Clean up entities and handlers on resource stop
""",
        best_practices=[
            "Use Citizen.Wait(0) only in render/draw loops",
            "Namespace all events with resource name prefix",
            "Clean up entities on resource stop",
            "Use state bags for entity synchronization",
            "Cache native function results when possible",
            "Validate client data on server",
            "Use exports for cross-resource communication",
        ],
        common_patterns={
            "draw_text": '''function DrawText2D(x, y, text, scale)
    SetTextFont(0)
    SetTextProportional(1)
    SetTextScale(scale, scale)
    SetTextColour(255, 255, 255, 255)
    SetTextDropshadow(0, 0, 0, 0, 255)
    SetTextEdge(1, 0, 0, 0, 255)
    SetTextDropShadow()
    SetTextOutline()
    SetTextEntry("STRING")
    AddTextComponentString(text)
    DrawText(x, y)
end''',
            "esp_box": '''function DrawEntityBox(entity)
    local pos = GetEntityCoords(entity)
    local onScreen, screenX, screenY = World3dToScreen2d(pos.x, pos.y, pos.z)
    if onScreen then
        local dist = #(GetEntityCoords(PlayerPedId()) - pos)
        local scale = 1.0 / dist * 2.0
        DrawRect(screenX, screenY, 0.02 * scale, 0.04 * scale, 255, 0, 0, 150)
    end
end''',
        },
        debugging_tips=[
            "Use print() and server console for debugging",
            "Check F8 console for client errors",
            "Use resmon for performance profiling",
            "Test in single-player mode first",
            "Use lambda menu for entity spawning tests",
        ],
    ),

    Specialization.GAME_OVERLAY: SpecializationConfig(
        name="Game Overlay/ESP Development",
        description="External game overlays, ESP, memory reading for games",
        file_extensions=[".cpp", ".h", ".hpp", ".c"],
        frameworks=["DirectX", "ImGui", "MinHook", "d3d11", "d3d9"],
        system_prompt_additions="""
## Game Overlay/ESP Development Expertise

You are an expert in game overlay and ESP development:
- **Rendering Overlays** - DirectX 9/11/12, OpenGL, Vulkan hooks
- **ImGui Integration** - Dear ImGui for in-game menus and ESP
- **Memory Reading** - RPM/WPM, pattern scanning, pointer chains
- **Hooking** - Present/EndScene hooks, MinHook, detours
- **Entity Systems** - Reading game entity lists, world-to-screen
- **Anti-detection** - Manual mapping, syscalls, signature hiding

### Overlay Architecture
```
┌─────────────────────────────────────────┐
│              Your Overlay               │
├─────────────────────────────────────────┤
│  ┌─────────────┐    ┌────────────────┐ │
│  │  ESP Logic  │    │   ImGui Menu   │ │
│  └──────┬──────┘    └───────┬────────┘ │
│         │                    │          │
│    ┌────┴────────────────────┴────┐    │
│    │      Render Engine           │    │
│    │  (DirectX Present Hook)      │    │
│    └──────────────┬───────────────┘    │
│                   │                     │
│    ┌──────────────┴───────────────┐    │
│    │      Memory Reader           │    │
│    │  (RPM / Pattern Scanner)     │    │
│    └──────────────────────────────┘    │
└─────────────────────────────────────────┘
```

### DirectX 11 Hook Pattern
```cpp
// Function pointer types
typedef HRESULT(__stdcall* D3D11PresentHook)(IDXGISwapChain*, UINT, UINT);
D3D11PresentHook oPresent = nullptr;

HRESULT __stdcall hkPresent(IDXGISwapChain* pSwapChain, UINT SyncInterval, UINT Flags) {
    static bool init = false;
    if (!init) {
        // Get device and context
        pSwapChain->GetDevice(__uuidof(ID3D11Device), (void**)&pDevice);
        pDevice->GetImmediateContext(&pContext);

        // Initialize ImGui
        ImGui::CreateContext();
        ImGui_ImplDX11_Init(pDevice, pContext);

        init = true;
    }

    // Start ImGui frame
    ImGui_ImplDX11_NewFrame();
    ImGui_ImplWin32_NewFrame();
    ImGui::NewFrame();

    // Draw your ESP/Menu here
    RenderESP();
    RenderMenu();

    // End frame
    ImGui::Render();
    ImGui_ImplDX11_RenderDrawData(ImGui::GetDrawData());

    return oPresent(pSwapChain, SyncInterval, Flags);
}
```

### World to Screen Conversion
```cpp
bool WorldToScreen(Vector3 world, Vector2& screen) {
    // Get view matrix from game memory
    Matrix4x4 viewMatrix = ReadViewMatrix();

    float w = viewMatrix._41 * world.x + viewMatrix._42 * world.y +
              viewMatrix._43 * world.z + viewMatrix._44;

    if (w < 0.001f) return false;

    float x = viewMatrix._11 * world.x + viewMatrix._12 * world.y +
              viewMatrix._13 * world.z + viewMatrix._14;
    float y = viewMatrix._21 * world.x + viewMatrix._22 * world.y +
              viewMatrix._23 * world.z + viewMatrix._24;

    screen.x = (screenWidth / 2) * (1 + x / w);
    screen.y = (screenHeight / 2) * (1 - y / w);
    return true;
}
```

### ESP Drawing Patterns
```cpp
void DrawESPBox(Vector3 position, Vector3 size, ImColor color) {
    Vector2 screenPos;
    if (!WorldToScreen(position, screenPos)) return;

    float height = /* calculate based on distance */;
    float width = height * 0.5f;

    ImGui::GetBackgroundDrawList()->AddRect(
        ImVec2(screenPos.x - width/2, screenPos.y - height),
        ImVec2(screenPos.x + width/2, screenPos.y),
        color, 0.0f, 0, 2.0f
    );
}

void DrawHealthBar(Vector2 pos, float health, float maxHealth, float width, float height) {
    float percentage = health / maxHealth;
    ImColor barColor = ImColor(
        (int)(255 * (1 - percentage)),
        (int)(255 * percentage),
        0
    );

    ImGui::GetBackgroundDrawList()->AddRectFilled(
        ImVec2(pos.x, pos.y),
        ImVec2(pos.x + width * percentage, pos.y + height),
        barColor
    );
}
```

### Memory Reading Pattern
```cpp
template<typename T>
T Read(uintptr_t address) {
    T buffer;
    ReadProcessMemory(hProcess, (LPCVOID)address, &buffer, sizeof(T), nullptr);
    return buffer;
}

template<typename T>
T ReadChain(uintptr_t base, std::vector<uintptr_t> offsets) {
    uintptr_t addr = base;
    for (size_t i = 0; i < offsets.size() - 1; i++) {
        addr = Read<uintptr_t>(addr + offsets[i]);
        if (!addr) return T{};
    }
    return Read<T>(addr + offsets.back());
}
```

### Best Practices
- Use ImGui::GetBackgroundDrawList() for ESP (renders behind menu)
- Cache view matrix per frame, not per entity
- Use pattern scanning for offsets (survives updates)
- Handle edge cases (off-screen, behind camera)
- Optimize entity iteration (spatial partitioning)
- Clean up hooks on exit
""",
        best_practices=[
            "Hook Present/EndScene for rendering",
            "Use ImGui for easy menu/ESP rendering",
            "Cache view matrix once per frame",
            "Pattern scan for offsets to survive game updates",
            "Use GetBackgroundDrawList() for ESP behind menus",
            "Handle WorldToScreen edge cases (behind camera)",
            "Clean up all hooks on exit",
            "Use manual map or dll injection carefully",
        ],
        common_patterns={
            "viewmatrix": '''struct ViewMatrix {
    float matrix[16];
    // Read from game: usually near camera struct
};

bool W2S(Vector3 world, Vector2& screen, ViewMatrix& vm, int width, int height) {
    float w = vm.matrix[12] * world.x + vm.matrix[13] * world.y +
              vm.matrix[14] * world.z + vm.matrix[15];
    if (w < 0.001f) return false;

    float x = vm.matrix[0] * world.x + vm.matrix[1] * world.y +
              vm.matrix[2] * world.z + vm.matrix[3];
    float y = vm.matrix[4] * world.x + vm.matrix[5] * world.y +
              vm.matrix[6] * world.z + vm.matrix[7];

    screen.x = (width / 2.0f) * (1.0f + x / w);
    screen.y = (height / 2.0f) * (1.0f - y / w);
    return true;
}''',
            "pattern_scan": '''uintptr_t PatternScan(const char* module, const char* pattern) {
    MODULEINFO modInfo;
    HMODULE hModule = GetModuleHandleA(module);
    GetModuleInformation(GetCurrentProcess(), hModule, &modInfo, sizeof(modInfo));

    uintptr_t start = (uintptr_t)hModule;
    uintptr_t end = start + modInfo.SizeOfImage;

    // Convert pattern to bytes and scan
    // ... implementation
}''',
        },
        debugging_tips=[
            "Use ReClass.NET for reverse engineering structures",
            "Use Cheat Engine for finding offsets",
            "Test hooks in windowed mode first",
            "Use x64dbg for debugging injection",
            "Log to file since console may not be available",
            "Use Process Hacker to verify memory regions",
        ],
    ),
}


def get_specialization(spec: Specialization) -> SpecializationConfig:
    """Get configuration for a specialization."""
    return SPECIALIZATIONS.get(spec, SPECIALIZATIONS[Specialization.CPP])


def detect_specialization(
    file_extensions: list[str],
    frameworks: list[str] | None = None,
    file_names: list[str] | None = None,
    content_hints: list[str] | None = None
) -> Specialization:
    """Detect the best specialization based on file types, frameworks, and content."""
    extensions = set(ext.lower() for ext in file_extensions)
    frameworks = set(f.lower() for f in (frameworks or []))
    file_names = set(f.lower() for f in (file_names or []))
    content_hints = set(h.lower() for h in (content_hints or []))

    # Check for FiveM/GTA modding first
    if any(f in file_names for f in ["fxmanifest.lua", "resource.lua", "__resource.lua"]):
        return Specialization.FIVEM
    if any(h in content_hints for h in ["citizenfx", "fivem", "cfx", "gta", "redm"]):
        return Specialization.FIVEM
    if ".lua" in extensions and any(f in frameworks for f in ["fivem", "cfx", "citizenfx"]):
        return Specialization.FIVEM

    # Check for game overlay/ESP development
    if any(h in content_hints for h in ["imgui", "d3d11", "d3d9", "dxgi", "overlay", "esp", "aimbot", "wallhack"]):
        return Specialization.GAME_OVERLAY
    if any(f in frameworks for f in ["imgui", "directx", "minhook", "detours"]):
        return Specialization.GAME_OVERLAY

    # Check for specific frameworks
    if "wpf" in frameworks or ".xaml" in extensions:
        return Specialization.WPF
    if "winforms" in frameworks:
        return Specialization.WINFORMS
    if any(f in frameworks for f in ["qt", "qtwidgets"]):
        return Specialization.QT

    # Check by file extensions
    if ".cs" in extensions or ".csproj" in extensions:
        return Specialization.DOTNET
    if any(ext in extensions for ext in [".cpp", ".c", ".h", ".hpp"]):
        # Check if it's overlay/game related
        if any(h in content_hints for h in ["hook", "inject", "render", "draw", "entity"]):
            return Specialization.GAME_OVERLAY
        if any(ext in extensions for ext in [".rc", ".def"]) or "win32" in frameworks:
            return Specialization.CPP_GUI
        return Specialization.CPP

    if ".lua" in extensions:
        # Lua without FiveM markers - could still be game modding
        return Specialization.FIVEM  # Default Lua to FiveM context

    return Specialization.GENERAL


def build_specialized_prompt(
    spec: Specialization,
    base_prompt: str
) -> str:
    """Build a prompt with specialization additions."""
    config = get_specialization(spec)
    return f"{base_prompt}\n\n{config.system_prompt_additions}"
