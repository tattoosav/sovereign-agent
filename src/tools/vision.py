"""
Vision Tool - Image and Screenshot Analysis.

Enables the agent to analyze images, screenshots, and game visuals
using vision-capable models (like LLaVA, Qwen-VL, etc.).
"""

import base64
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class ImageAnalysis:
    """Result of image analysis."""
    description: str
    detected_elements: list[str]
    text_content: list[str]
    suggestions: list[str]


class VisionTool(BaseTool):
    """Tool for analyzing images and screenshots using vision models."""

    name = "vision"
    description = """Analyze images, screenshots, and game visuals.

Operations:
- analyze: General image analysis and description
- describe_ui: Analyze UI elements in a screenshot
- read_text: Extract text/OCR from image
- game_analyze: Analyze game screenshot (detect elements, HUD, scene)
- compare: Compare two images

Supports: PNG, JPG, JPEG, GIF, BMP, WEBP

Models used: LLaVA, Qwen2-VL, or other vision models via Ollama.
"""
    parameters = {
        "operation": "Operation to perform",
        "image_path": "Path to image file",
        "image_path2": "Second image path (for compare)",
        "prompt": "Custom prompt/question about the image",
        "model": "Vision model to use (default: llava)",
    }

    # Supported vision models in Ollama
    VISION_MODELS = [
        "llava",
        "llava:13b",
        "llava:34b",
        "llava-llama3",
        "bakllava",
        "qwen2-vl",
        "qwen2-vl:7b",
        "moondream",
    ]

    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url.rstrip("/")
        self.default_model = "llava"

    def execute(
        self,
        operation: str,
        image_path: str = "",
        image_path2: str = "",
        prompt: str = "",
        model: str = "",
        **kwargs: Any
    ) -> ToolResult:
        """Execute vision operation."""
        try:
            model = model or self.default_model

            if operation == "analyze":
                return self._analyze(image_path, prompt, model)
            elif operation == "describe_ui":
                return self._describe_ui(image_path, model)
            elif operation == "read_text":
                return self._read_text(image_path, model)
            elif operation == "game_analyze":
                return self._game_analyze(image_path, prompt, model)
            elif operation == "compare":
                return self._compare(image_path, image_path2, model)
            elif operation == "list_models":
                return self._list_vision_models()
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Unknown operation: {operation}"
                )
        except FileNotFoundError as e:
            return ToolResult(success=False, output="", error=f"Image not found: {e}")
        except Exception as e:
            logger.exception(f"Vision tool error: {e}")
            return ToolResult(success=False, output="", error=str(e))

    def _load_image_base64(self, image_path: str) -> str:
        """Load image and convert to base64."""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(image_path)

        # Check file size (limit to 20MB)
        if path.stat().st_size > 20 * 1024 * 1024:
            raise ValueError("Image too large (max 20MB)")

        # Check extension
        valid_extensions = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
        if path.suffix.lower() not in valid_extensions:
            raise ValueError(f"Unsupported image format: {path.suffix}")

        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _call_vision_model(
        self,
        image_base64: str,
        prompt: str,
        model: str
    ) -> str:
        """Call Ollama vision model."""
        url = f"{self.ollama_url}/api/generate"

        payload = {
            "model": model,
            "prompt": prompt,
            "images": [image_base64],
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 1024,
            }
        }

        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.ollama_url}. "
                "Make sure Ollama is running with a vision model."
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(
                    f"Model '{model}' not found. "
                    f"Install with: ollama pull {model}"
                )
            raise

    def _analyze(self, image_path: str, prompt: str, model: str) -> ToolResult:
        """General image analysis."""
        if not image_path:
            return ToolResult(success=False, output="", error="image_path is required")

        image_b64 = self._load_image_base64(image_path)

        if not prompt:
            prompt = """Analyze this image in detail. Describe:
1. What is shown in the image
2. Key visual elements and their positions
3. Colors and visual style
4. Any text visible
5. The overall context or purpose of the image"""

        response = self._call_vision_model(image_b64, prompt, model)

        lines = [
            f"Image Analysis: {image_path}",
            "=" * 50,
            "",
            response
        ]

        return ToolResult(success=True, output="\n".join(lines))

    def _describe_ui(self, image_path: str, model: str) -> ToolResult:
        """Analyze UI elements in a screenshot."""
        if not image_path:
            return ToolResult(success=False, output="", error="image_path is required")

        image_b64 = self._load_image_base64(image_path)

        prompt = """Analyze this UI screenshot. Identify and describe:

1. **Layout**: Overall structure and arrangement
2. **UI Elements**: Buttons, menus, forms, text fields, icons
3. **Navigation**: How users would interact with this interface
4. **Text Content**: All visible text and labels
5. **Visual Hierarchy**: What draws attention first
6. **Color Scheme**: Main colors used
7. **Potential Issues**: Any UX problems you notice

Provide specific details about element positions (top, bottom, left, right, center)."""

        response = self._call_vision_model(image_b64, prompt, model)

        lines = [
            f"UI Analysis: {image_path}",
            "=" * 50,
            "",
            response
        ]

        return ToolResult(success=True, output="\n".join(lines))

    def _read_text(self, image_path: str, model: str) -> ToolResult:
        """Extract text from image (OCR-like)."""
        if not image_path:
            return ToolResult(success=False, output="", error="image_path is required")

        image_b64 = self._load_image_base64(image_path)

        prompt = """Extract ALL text visible in this image.
Include:
- Main headings and titles
- Body text
- Labels on buttons or UI elements
- Any numbers or codes
- Small text or captions

Format the text maintaining approximate layout where possible.
If text is unclear, indicate with [unclear].
List each distinct text element on a new line."""

        response = self._call_vision_model(image_b64, prompt, model)

        lines = [
            f"Text Extracted from: {image_path}",
            "=" * 50,
            "",
            response
        ]

        return ToolResult(success=True, output="\n".join(lines))

    def _game_analyze(self, image_path: str, prompt: str, model: str) -> ToolResult:
        """Analyze game screenshot."""
        if not image_path:
            return ToolResult(success=False, output="", error="image_path is required")

        image_b64 = self._load_image_base64(image_path)

        base_prompt = """Analyze this game screenshot in detail:

1. **Game Type**: What kind of game is this (FPS, RPG, strategy, etc.)?
2. **Scene Description**: What's happening in the game?
3. **HUD Elements**: Identify all UI elements:
   - Health/mana bars
   - Minimap
   - Inventory
   - Score/currency
   - Abilities/skills
   - Quest/objective info
4. **Characters/Entities**: Players, NPCs, enemies visible
5. **Environment**: Setting, terrain, objects
6. **Game State**: What phase of gameplay (combat, exploration, menu, etc.)?

"""
        if prompt:
            base_prompt += f"\nAdditional focus: {prompt}"

        response = self._call_vision_model(image_b64, base_prompt, model)

        lines = [
            f"Game Screenshot Analysis: {image_path}",
            "=" * 50,
            "",
            response
        ]

        return ToolResult(success=True, output="\n".join(lines))

    def _compare(self, image_path1: str, image_path2: str, model: str) -> ToolResult:
        """Compare two images."""
        if not image_path1 or not image_path2:
            return ToolResult(
                success=False,
                output="",
                error="Both image_path and image_path2 are required"
            )

        # Load both images
        image1_b64 = self._load_image_base64(image_path1)
        image2_b64 = self._load_image_base64(image_path2)

        # Analyze first image
        prompt1 = "Describe this image in detail, noting all key elements, positions, colors, and text."
        desc1 = self._call_vision_model(image1_b64, prompt1, model)

        # Analyze second image
        desc2 = self._call_vision_model(image2_b64, prompt1, model)

        # Format comparison
        lines = [
            "Image Comparison",
            "=" * 50,
            "",
            f"**Image 1:** {image_path1}",
            desc1,
            "",
            "-" * 50,
            "",
            f"**Image 2:** {image_path2}",
            desc2,
            "",
            "-" * 50,
            "",
            "**Key Differences:**",
            "Compare the descriptions above to identify changes."
        ]

        return ToolResult(success=True, output="\n".join(lines))

    def _list_vision_models(self) -> ToolResult:
        """List available vision models."""
        try:
            url = f"{self.ollama_url}/api/tags"
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url)
                response.raise_for_status()
                data = response.json()

            installed = [m["name"] for m in data.get("models", [])]

            # Filter to vision-capable models
            vision_installed = []
            for model in installed:
                model_base = model.split(":")[0]
                if model_base in ["llava", "bakllava", "llava-llama3", "moondream", "qwen2-vl"]:
                    vision_installed.append(model)

            lines = [
                "Vision Models",
                "=" * 50,
                "",
                "**Installed:**"
            ]

            if vision_installed:
                for m in vision_installed:
                    lines.append(f"  ✓ {m}")
            else:
                lines.append("  (none)")

            lines.extend([
                "",
                "**Recommended models to install:**",
                "  ollama pull llava           # 7B, good balance",
                "  ollama pull llava:13b       # Better quality",
                "  ollama pull moondream       # Fast, lightweight",
                "  ollama pull qwen2-vl        # Advanced vision",
            ])

            return ToolResult(success=True, output="\n".join(lines))

        except Exception as e:
            return ToolResult(success=False, output="", error=f"Failed to list models: {e}")


class ScreenshotTool(BaseTool):
    """Tool for taking screenshots (requires pyautogui or mss)."""

    name = "screenshot"
    description = """Capture screenshots of the screen.

Operations:
- capture: Take a screenshot and save to file
- capture_region: Capture a specific region

Requires: mss or pyautogui package
"""
    parameters = {
        "operation": "Operation: capture, capture_region",
        "output_path": "Where to save the screenshot",
        "region": "Region as 'x,y,width,height' (for capture_region)",
        "monitor": "Monitor number (default: 1 for primary)",
    }

    def execute(
        self,
        operation: str,
        output_path: str = "screenshot.png",
        region: str = "",
        monitor: int = 1,
        **kwargs: Any
    ) -> ToolResult:
        """Execute screenshot operation."""
        try:
            if operation == "capture":
                return self._capture(output_path, monitor)
            elif operation == "capture_region":
                return self._capture_region(output_path, region)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Unknown operation: {operation}"
                )
        except ImportError as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Screenshot requires 'mss' package. Install with: pip install mss\n{e}"
            )
        except Exception as e:
            logger.exception(f"Screenshot error: {e}")
            return ToolResult(success=False, output="", error=str(e))

    def _capture(self, output_path: str, monitor: int) -> ToolResult:
        """Capture full screen."""
        try:
            import mss

            with mss.mss() as sct:
                # Get monitor
                if monitor > len(sct.monitors) - 1:
                    monitor = 1  # Default to primary

                screenshot = sct.grab(sct.monitors[monitor])

                # Save to file
                path = Path(output_path)
                mss.tools.to_png(screenshot.rgb, screenshot.size, output=str(path))

                return ToolResult(
                    success=True,
                    output=f"Screenshot saved to: {path.absolute()}\n"
                           f"Size: {screenshot.width}x{screenshot.height}"
                )

        except ImportError:
            # Fallback to pyautogui
            import pyautogui
            screenshot = pyautogui.screenshot()
            screenshot.save(output_path)
            return ToolResult(
                success=True,
                output=f"Screenshot saved to: {output_path}"
            )

    def _capture_region(self, output_path: str, region: str) -> ToolResult:
        """Capture a region of the screen."""
        if not region:
            return ToolResult(
                success=False,
                output="",
                error="Region required as 'x,y,width,height'"
            )

        try:
            x, y, w, h = map(int, region.split(","))
        except ValueError:
            return ToolResult(
                success=False,
                output="",
                error="Invalid region format. Use: x,y,width,height"
            )

        try:
            import mss

            with mss.mss() as sct:
                region_dict = {"left": x, "top": y, "width": w, "height": h}
                screenshot = sct.grab(region_dict)

                path = Path(output_path)
                mss.tools.to_png(screenshot.rgb, screenshot.size, output=str(path))

                return ToolResult(
                    success=True,
                    output=f"Region screenshot saved to: {path.absolute()}\n"
                           f"Region: {x},{y} - {w}x{h}"
                )

        except ImportError:
            import pyautogui
            screenshot = pyautogui.screenshot(region=(x, y, w, h))
            screenshot.save(output_path)
            return ToolResult(
                success=True,
                output=f"Region screenshot saved to: {output_path}"
            )
