
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum


class ToolType(Enum):
    """Enumeration of tool types."""
    CUSTOM = "custom"
    BUILTIN = "builtin"
    REMOTE_MCP = "remote_mcp"
    MCP = "mcp"  # Legacy MCP via SSE


@dataclass
class ToolParameter:
    """
    Represents a single tool parameter.
    
    Attributes:
        name: Parameter name
        type: Parameter type (string, integer, boolean, object, array)
        description: Parameter description
        required: Whether this parameter is required
        default: Default value if any
        enum: List of allowed values if restricted
    """
    name: str
    type: str
    description: str
    required: bool = False
    default: Any = None
    enum: Optional[List[Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert parameter to dictionary format."""
        param_dict = {
            "type": self.type,
            "description": self.description
        }
        if self.default is not None:
            param_dict["default"] = self.default
        if self.enum:
            param_dict["enum"] = self.enum
        return param_dict


@dataclass
class Tool:
    """
    Represents a tool that can be used by an agent.

    Attributes:
        name: Tool name/identifier
        description: What the tool does
        parameters: List of tool parameters
        tool_type: Type of tool (custom, builtin)
        function: Optional callable function for custom tools
        metadata: Additional metadata about the tool
        trust_level: "trusted" (default, direct execution) or "sandbox" (subprocess isolation).
            Use "sandbox" for user-provided or untrusted tool functions.
    """
    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)
    tool_type: ToolType = ToolType.CUSTOM
    function: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    trust_level: str = "trusted"
    required_permission: str = "basic"

    def get_required_params(self) -> List[str]:
        """Get list of required parameter names."""
        return [param.name for param in self.parameters if param.required]
    
    def get_optional_params(self) -> List[str]:
        """Get list of optional parameter names."""
        return [param.name for param in self.parameters if not param.required]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tool to dictionary format."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    param.name: param.to_dict() 
                    for param in self.parameters
                },
                "required": self.get_required_params()
            },
            "tool_type": self.tool_type.value,
            "metadata": self.metadata
        }
    

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate arguments against tool parameters.

        Args:
            args: Dictionary of arguments to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required parameters
        required = self.get_required_params()
        for param_name in required:
            if param_name not in args:
                return False, f"Missing required parameter: {param_name}"

        # Check for unknown parameters
        valid_params = {param.name: param for param in self.parameters}
        for arg_name in args:
            if arg_name not in valid_params:
                return False, f"Unknown parameter: {arg_name}"

        # Type validation
        _type_map: Dict[str, Any] = {
            "string": str,
            "str": str,
            "integer": int,
            "int": int,
            "number": (int, float),
            "float": float,
            "boolean": bool,
            "bool": bool,
            "array": list,
            "list": list,
            "object": dict,
            "dict": dict,
        }
        for arg_name, value in args.items():
            param = valid_params.get(arg_name)
            if param is None or value is None:
                continue
            expected = _type_map.get(param.type.lower())
            if expected is None:
                continue
            # bool is a subclass of int in Python; explicitly reject bools for numeric types
            if expected in (int, (int, float)) and isinstance(value, bool):
                return False, (
                    f"Parameter '{arg_name}' expected {param.type}, got boolean"
                )
            if not isinstance(value, expected):
                return False, (
                    f"Parameter '{arg_name}' expected {param.type}, got {type(value).__name__}"
                )

        # Enum constraint validation
        for arg_name, value in args.items():
            param = valid_params.get(arg_name)
            if param is None or value is None:
                continue
            if param.enum and value not in param.enum:
                return False, (
                    f"Parameter '{arg_name}' value {value!r} is not one of the allowed values: {param.enum}"
                )

        return True, None
