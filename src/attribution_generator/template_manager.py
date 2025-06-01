"""
Template manager module for handling attribution file templates.

This module provides the TemplateManager class that handles:
1. Loading templates from configuration
2. Managing template sections
3. Providing formatted templates for attribution generation
"""

import yaml
from pathlib import Path
from typing import Dict

class TemplateManager:
    """
    Manages templates for attribution file generation.
    
    This class handles all aspects of template management:
    1. Loading templates from configuration file
    2. Providing access to template sections
    3. Handling template formatting
    4. Managing template errors
    """

    def __init__(self, template_config_path: str = "templates.yaml"):
        """
        Initialize the template manager.
        
        Args:
            template_config_path: Path to template configuration file
        """
        self.template_config_path = Path(template_config_path)
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict[str, str]:
        """
        Load templates from configuration file.
        
        Loads and validates the template configuration file containing
        all template sections for attribution file generation.
        
        Returns:
            Dictionary mapping template section names to their content
            
        Note:
            Returns empty dict if file not found or invalid
        """
        if not self.template_config_path.exists():
            print(f"⚠️ Warning: Template configuration file '{self.template_config_path}' not found. Templates may be missing.")
            return {}
        try:
            with open(self.template_config_path, 'r', encoding='utf-8') as f:
                loaded_templates = yaml.safe_load(f)
                if not isinstance(loaded_templates, dict):
                    print(f"⚠️ Warning: Template configuration file '{self.template_config_path}' is not a valid dictionary. Templates may not load correctly.")
                    return {}
                return loaded_templates
        except Exception as e:
            print(f"⚠️ Error loading template configuration file '{self.template_config_path}': {e}. No templates will be available.")
            return {}

    def get_template(self, template_name: str) -> str:
        """
        Get template content for a specific section.
        
        Retrieves the template content for a given section name.
        Returns a default template if the requested one is not found.
        
        Args:
            template_name: Name of the template section
            
        Returns:
            Template content as string
        """
        template = self.templates.get(template_name)
        if template is None:
            print(f"⚠️ Warning: Template '{template_name}' not found in '{self.template_config_path}'. Using default template.")
            # Return appropriate default template based on section
            if template_name == "header":
                return "Open Source Software Attribution\nProject: {project_name}\nCopyright (c) {copyright_holder_full}\n"
            elif template_name == "footer":
                return "\nEnd of Attribution File"
            elif template_name == "component_listing":
                return "{serial_number}. {name} (v{version})\n{copyright}{modification_notice}"
            elif template_name == "license_group_header":
                return "Components under license: {license_id}"
            elif template_name == "license_group_footer":
                return "License text for {license_id}:\n\n{license_text}"
            elif template_name == "inter_license_separator":
                return "=" * 80
            elif template_name == "others_url_section_header":
                return "\nAdditional notices for the above components:"
            elif template_name == "others_url_item":
                return "  • Component {component_serial_number} ({component_name}): {others_url}"
            else:
                return f"[Template '{template_name}' not found]"
        return template