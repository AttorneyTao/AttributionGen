"""
Core generator module for creating attribution files.

This module provides the main AttributionGenerator class that handles:
1. Loading components from various input formats (Excel, JSON, YAML)
2. Processing license expressions and component metadata
3. Generating formatted attribution files
4. Managing component modifications and "others" URLs
"""

from pathlib import Path
import pandas as pd
import json
import yaml
from collections import defaultdict
from attribution_generator.component import Component
from attribution_generator.license_manager import LicenseManager
from attribution_generator.template_manager import TemplateManager
from typing import List, Dict

class AttributionGenerator:
    """
    Main attribution generator class.
    
    This class orchestrates the entire attribution generation process:
    1. Loading and validating components
    2. Processing license expressions
    3. Generating formatted attribution text
    4. Managing component modifications
    """

    def __init__(self, license_config: str, template_config: str, 
                 project_name: str, copyright_holder_full: str, copyright_holder_short: str):
        """
        Initialize the attribution generator.
        
        Args:
            license_config: Path to license configuration file
            template_config: Path to template configuration file
            project_name: Name of the project
            copyright_holder_full: Full legal name of copyright holder
            copyright_holder_short: Short name for copyright notices
        """
        self.license_manager = LicenseManager(license_config)
        self.template_manager = TemplateManager(template_config)
        self.project_name = project_name
        self.copyright_holder_full = copyright_holder_full
        self.copyright_holder_short = copyright_holder_short

    def _clean_excel_string(self, text: any) -> str:
        """
        Clean string values from Excel input.
        
        Removes Excel-specific characters and whitespace.
        
        Args:
            text: Input text to clean
            
        Returns:
            Cleaned string
        """
        if not isinstance(text, str): text = str(text)
        return text.replace('_x000d_', '').replace('_x000D_', '').strip()

    def _str_to_bool(self, s: any) -> bool:
        """
        Convert string or other input to boolean.
        
        Handles various string representations of boolean values.
        
        Args:
            s: Input to convert
            
        Returns:
            Boolean value
        """
        if isinstance(s, bool): return s
        s_str = str(s).lower().strip()
        return s_str in ['true', '1', 't', 'y', 'yes']

    def load_components(self, input_file: str) -> List[Component]:
        """
        Load components from input file.
        
        Supports Excel (.xlsx, .xls), JSON, and YAML formats.
        Validates required fields and processes optional fields.
        
        Args:
            input_file: Path to input file
            
        Returns:
            List of Component objects
            
        Raises:
            FileNotFoundError: If input file doesn't exist
            ValueError: If file format is invalid or required fields are missing
        """
        input_path = Path(input_file)
        if not input_path.exists(): raise FileNotFoundError(f"Input file {input_file} not found.")
        components = []

        if input_path.suffix.lower() in ['.xlsx', '.xls']:
            try:
                # Read Excel file with string dtype to preserve formatting
                df = pd.read_excel(input_path, dtype=str)
                df.fillna('', inplace=True)
                
                # Map column names to standardized field names
                column_mapping = {}
                for col_name_obj in df.columns:
                    col_name_str = str(col_name_obj)
                    col_lower = col_name_str.lower().strip()
                    if 'component_name' in col_lower or col_lower == 'name': column_mapping['name'] = col_name_str
                    elif 'copyright' in col_lower: column_mapping['copyright'] = col_name_str
                    elif 'license' in col_lower: column_mapping['license'] = col_name_str
                    elif 'version' in col_lower: column_mapping['version'] = col_name_str
                    elif 'others_url' in col_lower or 'notice_url' in col_lower: column_mapping['others_url'] = col_name_str
                    elif 'modified' == col_lower: column_mapping['modified'] = col_name_str
                    elif 'modified_url' in col_lower : column_mapping['modified_url'] = col_name_str
                
                # Validate required fields
                required_fields = ['name', 'copyright', 'license']
                missing_fields = [f for f in required_fields if f not in column_mapping]
                if missing_fields: raise ValueError(f"Missing required columns in Excel: {missing_fields}. Available: {list(df.columns)}")

                # Process each row into a Component object
                for _, row in df.iterrows():
                    name = self._clean_excel_string(row.get(column_mapping.get('name'), ''))
                    if not name: continue
                    copyright_str = self._clean_excel_string(row.get(column_mapping.get('copyright'), ''))
                    license_expr = self._clean_excel_string(row.get(column_mapping.get('license'), ''))
                    version = self._clean_excel_string(row.get(column_mapping.get('version'), '')) or None
                    
                    modified_str = self._clean_excel_string(row.get(column_mapping.get('modified'), 'false'))
                    modified = self._str_to_bool(modified_str)
                    modified_url = self._clean_excel_string(row.get(column_mapping.get('modified_url'), '')) or None
                    
                    others_url = self._clean_excel_string(row.get(column_mapping.get('others_url'), '')) or None
                    
                    if not license_expr: print(f"⚠️ Warning: Missing license for '{name}'.")
                    components.append(Component(name, copyright_str, license_expr, version, others_url, modified, modified_url))
            except Exception as e: raise ValueError(f"Error reading Excel '{input_file}': {e}")
        
        elif input_path.suffix.lower() in ['.json', '.yaml', '.yml']:
            try:
                # Read JSON or YAML file
                with open(input_path, 'r', encoding='utf-8') as f:
                    data_source = json.load(f) if input_path.suffix.lower() == '.json' else yaml.safe_load(f)
                
                # Extract component list from data structure
                data_list = []
                if isinstance(data_source, list): data_list = data_source
                elif isinstance(data_source, dict) and 'components' in data_source and isinstance(data_source['components'], list):
                    data_list = data_source['components']
                else: raise ValueError(f"Invalid format in {input_path.name}. Expected list or dict with 'components' key.")

                # Process each component into a Component object
                for item in data_list:
                    if not isinstance(item, dict):
                        print(f"⚠️ Skipping non-dict item in {input_path.name}: {item}"); continue
                    name = self._clean_excel_string(item.get('name', ''))
                    if not name: print(f"⚠️ Skipping component with no name: {item}"); continue
                    
                    copyright_str = self._clean_excel_string(item.get('copyright', ''))
                    license_expr = self._clean_excel_string(item.get('license', ''))
                    version = self._clean_excel_string(item.get('version', '')) or None
                    others_url = self._clean_excel_string(item.get('others_url', '')) or None
                    
                    modified_input = item.get('modified', False)
                    modified = self._str_to_bool(modified_input)
                    modified_url = self._clean_excel_string(item.get('modified_url', '')) or None

                    if not license_expr: print(f"⚠️ Missing license for '{name}' in {input_path.name}.")
                    components.append(Component(name, copyright_str, license_expr, version, others_url, modified, modified_url))
            except Exception as e: raise ValueError(f"Error reading {input_path.name}: {e}")
        else: raise ValueError(f"Unsupported input file: {input_path.suffix}.")
        return components

    def group_by_license(self, components: List[Component]) -> Dict[str, List[Component]]:
        """
        Group components by their license expressions.
        
        Args:
            components: List of Component objects
            
        Returns:
            Dictionary mapping license expressions to lists of components
        """
        grouped = defaultdict(list)
        for comp in components:
            key = comp.license if comp.license and comp.license.strip() else "UNSPECIFIED_LICENSE"
            grouped[key].append(comp)
        return dict(grouped)

    def generate_attribution(self, components: List[Component]) -> str:
        """
        Generate attribution text for components.
        
        Creates a formatted attribution file with:
        1. Project header
        2. Components grouped by license
        3. License texts
        4. Modification notices
        5. "Others" URLs
        6. Project footer
        
        Args:
            components: List of Component objects
            
        Returns:
            Formatted attribution text
        """
        if not components: return "No components to attribute."
        grouped_components = self.group_by_license(components)
        
        # Prepare global configuration values for templates
        global_config_values = {
            "project_name": self.project_name,
            "copyright_holder_full": self.copyright_holder_full,
            "copyright_holder_short": self.copyright_holder_short
        }

        # Generate header
        header_template_str = self.template_manager.get_template("header")
        formatted_header = header_template_str.format(**global_config_values)
        output_parts = [formatted_header, ""]
        
        # Process components by license group
        sorted_grouped_items = sorted(grouped_components.items(), key=lambda item: item[0].lower())

        for i, (license_expr_key, component_list) in enumerate(sorted_grouped_items):
            # Add separator between license groups
            if i > 0:
                output_parts.append("")
                output_parts.append(self.template_manager.get_template("inter_license_separator"))
                output_parts.append("")

            # Add license group header
            output_parts.append(self.template_manager.get_template("license_group_header").format(
                license_id=license_expr_key,
                copyright_holder_short=self.copyright_holder_short 
            ))
            
            # Process components in this license group
            components_with_others_urls_in_group = []
            for idx, comp_obj in enumerate(component_list, start=1):
                # Generate modification notice if applicable
                modification_notice = ""
                if comp_obj.modified:
                    notice_base = f"\n     This software was modified by {self.copyright_holder_short}"
                    if comp_obj.modified_url:
                        modification_notice = f"{notice_base}, you may find the modified code at {comp_obj.modified_url}"
                    else:
                        modification_notice = f"{notice_base}."
                
                # Add component listing
                output_parts.append(self.template_manager.get_template("component_listing").format(
                    serial_number=idx, name=comp_obj.name, 
                    copyright=comp_obj.copyright, version=comp_obj.version or "N/A",
                    modification_notice=modification_notice
                ))
                
                # Track components with "others" URLs
                if comp_obj.others_url:
                    components_with_others_urls_in_group.append({
                        "name": comp_obj.name, "url": comp_obj.others_url, "serial_number": idx
                    })

            # Add license text
            output_parts.append("")
            combined_license_text = self.license_manager.get_license_text(license_expr_key)
            output_parts.append(self.template_manager.get_template("license_group_footer").format(
                license_id=license_expr_key, license_text=combined_license_text
            ))

            # Add "others" URLs section if applicable
            if "others" in license_expr_key.lower() and components_with_others_urls_in_group:
                output_parts.append(self.template_manager.get_template("others_url_section_header"))
                for item_data in components_with_others_urls_in_group:
                    output_parts.append(self.template_manager.get_template("others_url_item").format(
                        component_serial_number=item_data["serial_number"],
                        component_name=item_data["name"], 
                        others_url=item_data["url"]
                    ))
                output_parts.append("")

        # Generate footer
        footer_template_str = self.template_manager.get_template("footer")
        formatted_footer = footer_template_str.format(**global_config_values)
        output_parts.extend(["", formatted_footer, ""])
        return "\n".join(output_parts)

    def generate_from_file(self, input_file: str, output_file: str = "ATTRIBUTIONS.txt"):
        """
        Generate attribution file from input file.
        
        Args:
            input_file: Path to input file
            output_file: Path to output file
            
        Raises:
            IOError: If output file cannot be written
        """
        loaded_components = self.load_components(input_file)
        attribution_text = self.generate_attribution(loaded_components)
        output_path = Path(output_file)
        try:
            with open(output_path, 'w', encoding='utf-8') as f: f.write(attribution_text)
        except IOError as e:
            print(f"❌ Error writing to output file '{output_path}': {e}")
            raise