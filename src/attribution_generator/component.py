"""
Component module for representing open source software components.

This module provides the Component class that represents a single open source
software component with its metadata, including:
1. Name and version
2. Copyright information
3. License expression
4. Modification status
5. Additional URLs
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class Component:
    """
    Represents a single open source software component.
    
    This class holds all metadata for a component, including its name,
    copyright information, license expression, and modification status.
    It is used as a data container throughout the attribution generation process.
    
    Attributes:
        name: Component name
        copyright: Copyright notice
        license: License expression (e.g., "MIT", "Apache-2.0 OR GPL-3.0")
        version: Component version (optional)
        others_url: URL for additional notices (optional)
        modified: Whether the component is modified (default: False)
        modified_url: URL to modified code (optional)
    """
    
    name: str
    copyright: str
    license: str
    version: Optional[str] = None
    others_url: Optional[str] = None
    modified: bool = False
    modified_url: Optional[str] = None