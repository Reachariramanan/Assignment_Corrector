# Modern Aesthetic Logging System

A clean, aesthetic logging system with soft, modern colors for the Yukta ecosystem.

## 🌟 Overview

The Modern Logger provides a clean, professional aesthetic for your Yukta ecosystem logs. Designed with soft colors and minimal design, it creates a pleasant visual experience without any thematic distractions.

### Visual Style
- **Color Palette**: Soft Blue, Light Blue, Deep Teal, Muted Purple, Warm Silver
- **Theme**: Clean, modern interface
- **Elements**: Clean borders, minimal icons, soft color gradients

## 🎨 Design Philosophy

### Soft State Indicators
The system visualizes activity levels with soft, aesthetic indicators:
- 🔵 **Normal** (Light Blue) - Low activity
- 💫 **Warming** (Soft Blue + Sparkle) - Active state
- ✨ **Active** (Soft Blue + Glow) - High activity
- 📊 **Processing** (Light Blue + Chart) - Critical activity

### Color Scheme
| Color | ANSI | Use Case |
|-------|------|----------|
| Soft Blue | \033[38;5;81m | Main system color (calming, modern) |
| Light Blue | \033[38;5;117m | Active state |
| Deep Teal | \033[38;5;23m | Headers, borders |
| Muted Purple | \033[38;5;98m | Information text |
| Warm Silver | \033[38;5;188m | Timestamps |
| Soft Amber | \033[38;5;214m | Warnings |
| Muted Orange | \033[38;5;202m | Errors |

## 🚀 Quick Start

### Basic Usage

```python
from cookbook.utils import setup_logging

# Initialize with default settings
setup_logging()
```

### Advanced Configuration

```python
from cookbook.utils import setup_logging

setup_logging(
    level=logging.DEBUG,      # Logging level
    use_color=True,           # Enable ANSI colors
    verbose_banners=True,     # Show decorative banners
    formatter_type="standard" # "standard", "compact", or "decorator"
)
```

## 📚 API Reference

### Core Functions

#### `setup_logging()`
Initialize the modern logging system.

```python
from wrapper import setup_logging

setup_logging(
    level=logging.INFO,
    use_color=True,
    verbose_banners=True,
    formatter_type="standard"
)
```

#### `get_logger()`
Get the global logger instance.

```python
from wrapper import get_logger

logger = get_logger()
logger.info("System initialized")
```

### Logging Methods

| Method | Description |
|--------|-------------|
| `log_start()` | Log the startup banner |
| `log_agent_activated(agent_name)` | Log agent activation with banner |
| `log_system_status(agent_name, status)` | Log system status header |
| `log_task_header(task_description)` | Log task submission header |
| `log_tool_registered(tool_name, tool_type)` | Log tool registration |
| `log_status(status)` | Log system status |
| `log_separator(width)` | Log decorative separator line |
| `debug(message)` | Debug level logging |
| `info(message)` | Info level logging |
| `warning(message)` | Warning level logging |
| `error(message)` | Error level logging |
| `critical(message)` | Critical level logging |

## 📊 Visual Examples

### Start Banner
```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  🌱 [LOGGING SYSTEM] v1.0 [MODERN] 🌱                                          │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Agent Activation
```
────────────────────────────────────────────────────────────────────────────────────
✨ Agent 'architect' ✨ [ACTIVATED]
────────────────────────────────────────────────────────────────────────────────────
```

### System Status
```
⚡ [SYSTEM INIT] Agent 'architect' | 🔵 Status: ACTIVE
```

### Full Flow Example
```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  🌱 [LOGGING SYSTEM] v1.0 [MODERN] 🌱                                          │
└──────────────────────────────────────────────────────────────────────────────────┘

────────────────────────────────────────────────────────────────────────────────────
🚀 [PIPELINE] Starting build and run agent pipeline...
System Status: CHARGING
────────────────────────────────────────────────────────────────────────────────────

🔍 [SEARCH] Locating agent 'architect'...
✅ Agent 'architect' found: Architect
[TOOL] Registered: architect (agent)
⚙️ [BOOTSTRAP] Building bootstrap prompt...
🔧 [TRANSFORM] Building yukta Agent from ecosystem data...
🔧 [TOOLS] Loading 5 tools for agent...
[TOOL] Registered: file-editor (builtin)
[TOOL] Registered: terminal (builtin)
[TOOL] Registered: git (builtin)
[TOOL] Registered: search (builtin)
[TOOL] Registered: validator (builtin)
✅ Agent 'architect' ready with 5 tools
System Status: ACTIVE
────────────────────────────────────────────────────────────────────────────────────

────────────────────────────────────────────────────────────────────────────────────
✨ Agent 'architect' ✨ [ACTIVATED]
────────────────────────────────────────────────────────────────────────────────────

14:30:25  🔵 State #01: Active  [INFO]  ⚡ [SYSTEM INIT] Agent 'architect' | 🔵 Status: ACTIVE
14:30:25  🔵 State #02: Active  [INFO]  ⚡ [TASK SUBMITTED] "Analyze the project architecture"
```

## 🎛️ Configuration

### System Configuration
Edit `ecosystem/config/main.yaml`:

```yaml
logging:
  level: INFO
  output: stdout
  enable_logging: true
  enable_memory_logging: true
```

### Environment Variables
```bash
# Disable color output (useful for CI)
export NO_COLOR=1

# Enable verbose banners
export VERBOSE_LOGGING=true
```

## 🔧 Troubleshooting

### No Colors Displayed
If you see ANSI codes instead of colors, ensure:
1. Your terminal supports ANSI colors
2. The `use_color` parameter is set to `True`
3. `NO_COLOR` environment variable is not set

### Logger Not Found
```python
# Ensure yukta-package is in your Python path
export PYTHONPATH="$PWD/yukta-package:$PYTHONPATH"

# Or install the package
pip install -e ./yukta-package/
```

### Fallback to Standard Logging
If modern logger fails to import, the system automatically falls back to standard Python logging.

## 🏗️ Architecture

### File Structure
```
wrapper/
├── modern_logger.py       # Main logger class
├── modern_formatter.py    # ANSI formatter with modern colors
├── runner.py              # Integrated logging
├── transformer.py         # Integrated logging
└── reader.py              # Integrated logging
```

### Classes
| Class | Purpose |
|-------|---------|
| `ModernLogger` | Main logger with modern styling |
| `ModernFormatter` | Custom logging formatter |
| `ModernCompactFormatter` | Compact format for high-frequency logs |
| `ModernDecoratorFormatter` | Decorative banners for special messages |
| `StateManager` | Manages system state indicators |

## 🎨 Customization

### Custom Colors
Edit `wrapper/modern_formatter.py`:

```python
class ModernColors:
    SOFT_BLUE = "\033[38;5;81m"      # Calming blue
    LIGHT_BLUE = "\033[38;5;117m"    # Active state
    DEEP_TEAL = "\033[38;5;23m"      # Headers, borders
    MUTED_PURPLE = "\033[38;5;98m"   # Information text
    WARM_SILVER = "\033[38;5;188m"   # Timestamps
    SOFT_AMBER = "\033[38;5;214m"    # Warnings
    MUTED_ORANGE = "\033[38;5;202m"  # Errors
```

### Custom Banner
```python
from wrapper.modern_logger import generate_banner

banner = generate_banner("MY CUSTOM BANNER", "Subtitle")
print(banner)
```

## 📝 License
Part of yukta-ecosystem - See root for full license.

---

*🌱 Clean, modern logging for better development experience.*
