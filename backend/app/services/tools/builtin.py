"""Approved Built-in Platform Tools."""

import ast
import operator
from typing import Any


class CalculatorSecurityError(ValueError):
    pass


# Allowed safe mathematical operators
_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def safe_calculate(expression: str) -> float | int:
    """Safely evaluate an arithmetic expression using AST parsing without eval() or code execution."""
    if not expression or not isinstance(expression, str):
        raise CalculatorSecurityError("Expression must be a non-empty string.")

    if len(expression) > 100:
        raise CalculatorSecurityError("Expression exceeds maximum length of 100 characters.")

    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as err:
        raise CalculatorSecurityError(f"Invalid arithmetic expression: {err}") from err

    def _eval_node(node: ast.AST) -> float | int:
        if isinstance(node, ast.Expression):
            return _eval_node(node.body)
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise CalculatorSecurityError(f"Non-numeric constant '{node.value}' is not allowed.")
        elif isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in _SAFE_OPERATORS:
                raise CalculatorSecurityError(f"Operator '{op_type.__name__}' is forbidden.")
            left = _eval_node(node.left)
            right = _eval_node(node.right)
            # Prevent excessive exponentiation denial-of-service
            if op_type is ast.Pow and (right > 100 or left > 10000):
                raise CalculatorSecurityError("Exponentiation parameters exceed safe limits.")
            return _SAFE_OPERATORS[op_type](left, right)
        elif isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in _SAFE_OPERATORS:
                raise CalculatorSecurityError(f"Unary operator '{op_type.__name__}' is forbidden.")
            return _SAFE_OPERATORS[op_type](_eval_node(node.operand))
        else:
            raise CalculatorSecurityError(f"Unsupported AST node: '{type(node).__name__}'.")

    return _eval_node(tree)


def synthetic_weather_lookup(city: str) -> dict[str, Any]:
    """Deterministic synthetic weather lookup tool for testing without paid weather APIs."""
    c_lower = city.strip().lower()
    conditions = {
        "london": {"temperature_c": 14.5, "condition": "Cloudy with light rain", "humidity": 78},
        "tokyo": {"temperature_c": 21.0, "condition": "Sunny", "humidity": 55},
        "new york": {"temperature_c": 18.2, "condition": "Partly Cloudy", "humidity": 62},
        "san francisco": {"temperature_c": 16.0, "condition": "Breezy and foggy", "humidity": 72},
        "paris": {"temperature_c": 17.8, "condition": "Clear", "humidity": 60},
    }
    default = {"temperature_c": 20.0, "condition": "Clear skies", "humidity": 50}
    weather = conditions.get(c_lower, default)
    return {
        "city": city.title(),
        **weather,
    }


BUILTIN_TOOL_DEFINITIONS = [
    {
        "name": "calculator",
        "display_name": "Safe Calculator",
        "description": "Performs exact, safe mathematical and arithmetic operations without code execution.",
        "namespace": "builtin",
        "tool_type": "BUILTIN",
        "risk_level": "READ_ONLY",
        "requires_approval": False,
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The arithmetic expression to evaluate (e.g. '15 * (1200 / 4) + 50')",
                }
            },
            "required": ["expression"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "result": {"type": "number"},
            },
        },
    },
    {
        "name": "weather_lookup",
        "display_name": "Weather Information Lookup",
        "description": "Retrieves current weather, temperature, and atmospheric conditions for a specified city.",
        "namespace": "builtin",
        "tool_type": "BUILTIN",
        "risk_level": "READ_ONLY",
        "requires_approval": False,
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name to retrieve weather for"}
            },
            "required": ["city"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "temperature_c": {"type": "number"},
                "condition": {"type": "string"},
                "humidity": {"type": "number"},
            },
        },
    },
    {
        "name": "web_read_url",
        "display_name": "Secure Web Page Reader",
        "description": "Reads and extracts clean, structured text content from a public web page URL with SSRF protection.",
        "namespace": "builtin",
        "tool_type": "BUILTIN",
        "risk_level": "READ_ONLY",
        "requires_approval": False,
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The public HTTP/HTTPS URL of the web page to read.",
                },
                "max_length": {
                    "type": "integer",
                    "description": "Maximum characters of text to extract (default 20000).",
                },
            },
            "required": ["url"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "title": {"type": "string"},
                "text": {"type": "string"},
                "status": {"type": "string"},
            },
        },
    },
    {
        "name": "web_search",
        "display_name": "Agentic Web Search",
        "description": "Searches the public web for relevant websites, articles, and documentation with citations.",
        "namespace": "builtin",
        "tool_type": "BUILTIN",
        "risk_level": "READ_ONLY",
        "requires_approval": False,
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to look up on the web.",
                },
                "count": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 5).",
                },
            },
            "required": ["query"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "results": {"type": "array"},
            },
        },
    },
    {
        "name": "web_save_to_kb",
        "display_name": "Save Web Source to Knowledge Base",
        "description": "Persists a retrieved public web page into an authorized Knowledge Base as either a REFERENCE (bookmark) or FULL_CONTENT.",
        "namespace": "builtin",
        "tool_type": "BUILTIN",
        "risk_level": "WRITE",
        "requires_approval": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The canonical URL of the web page to save.",
                },
                "knowledge_base_id": {
                    "type": "string",
                    "description": "The UUID of the destination Knowledge Base.",
                },
                "title": {
                    "type": "string",
                    "description": "Optional custom title for the saved document.",
                },
                "storage_mode": {
                    "type": "string",
                    "enum": ["REFERENCE", "FULL_CONTENT"],
                    "description": "Storage mode: REFERENCE (bookmark/metadata) or FULL_CONTENT (extracted text). Defaults to REFERENCE.",
                },
                "notes": {
                    "type": "string",
                    "description": "Optional notes or summary to store alongside the web source.",
                },
            },
            "required": ["url", "knowledge_base_id"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "document_id": {"type": "string"},
                "title": {"type": "string"},
                "storage_mode": {"type": "string"},
                "status": {"type": "string"},
            },
        },
    },
]
