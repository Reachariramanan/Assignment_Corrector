"""
System Prompt Module
Provides a structured way to define and manage system prompts for agents.
Handles JSON and other content with literal braces transparently.

Key Feature: Only valid Python identifiers in braces are treated as variables.
This means JSON like {"name": "value"} works naturally without any escaping.

Example:
    prompt = SystemPrompt(
        "MyAgent",
        '''Generate JSON matching this schema:
        {"name": string, "age": number}
        
        Use this context: {user_context}'''
    )
    prompt.get_prompt(user_context="example")  # JSON stays intact, variable is replaced
"""

from typing import Optional, Dict, Any
from datetime import datetime
import re


class SystemPrompt:
    """
    A class to manage system prompts for AI agents.
    
    Attributes:
        prompt_name (str): Name/identifier for the system prompt
        prompt_text (str): The actual system prompt text
        variables (Dict[str, Any]): Variables to be used in prompt templating
        created_at (datetime): Timestamp when the prompt was created
        metadata (Dict[str, Any]): Additional metadata about the prompt
    """
    
    def __init__(
        self,
        prompt_name: str,
        prompt_text: str,
        variables: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize a SystemPrompt instance.
        
        Args:
            prompt_name: Identifier for the prompt
            prompt_text: The system prompt text (can include {variable} placeholders)
            variables: Dictionary of variables for prompt templating
            metadata: Additional metadata (version, author, etc.)
        """
        self.prompt_name = prompt_name
        self.prompt_text = prompt_text
        self.variables = variables or {}
        self.metadata = metadata or {}
        self.created_at = datetime.now()
    
    def get_prompt(self, **kwargs) -> str:
        """
        Get the formatted system prompt with variables substituted.
        Only valid Python identifiers in braces are treated as variables.
        All other braces (like in JSON) are left unchanged.
        
        Args:
            **kwargs: Additional variables to override or extend instance variables
            
        Returns:
            Formatted prompt string with variables substituted
            
        Example:
            prompt = SystemPrompt("Agent", 'Schema: {"name": string}, use {variable}')
            result = prompt.get_prompt(variable="value")
            # Output: 'Schema: {"name": string}, use value'
        """
        # Merge instance variables with kwargs
        all_variables = {**self.variables, **kwargs}
        
        # Replace only valid Python identifiers in braces
        # Pattern matches {identifier} where identifier is a valid Python name
        # This leaves {"name": "value"} intact while replacing {variable}
        def replace_var(match):
            key = match.group(1)
            if key not in all_variables:
                # Return the original text if variable not found
                return match.group(0)
            return str(all_variables[key])
        
        # Pattern: { followed by valid identifier (letter/underscore + alphanumeric/underscore) followed by }
        return re.sub(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}', replace_var, self.prompt_text)
    
    def update_prompt(self, new_prompt_text: str) -> None:
        """
        Update the prompt text.
        
        Args:
            new_prompt_text: New system prompt text
        """
        self.prompt_text = new_prompt_text
    
    def add_variables(self, **kwargs) -> None:
        """
        Add or update variables for the prompt.
        
        Args:
            **kwargs: Key-value pairs to add/update in variables
            
        Example:
            prompt.add_variables(user_name="Alice", context="example")
        """
        self.variables.update(kwargs)
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get information about this system prompt.
        
        Returns:
            Dictionary containing prompt metadata and info
        """
        return {
            "prompt_name": self.prompt_name,
            "created_at": self.created_at.isoformat(),
            "variables": list(self.variables.keys()),
            "metadata": self.metadata,
            "prompt_length": len(self.prompt_text)
        }
    
    def __repr__(self) -> str:
        return f"SystemPrompt(name='{self.prompt_name}', length={len(self.prompt_text)})"
    
    def __str__(self) -> str:
        return self.get_prompt()

