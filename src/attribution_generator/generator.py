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
from dataclasses import fields

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

    def _build_column_mapping(self, columns, component_fields):
        """
        自动建立表头与Component字段的映射，支持常见别名。
        """
        mapping = {}
        for col_name_obj in columns:
            col_name_str = str(col_name_obj)
            col_lower = col_name_str.lower().strip()
            if col_lower in component_fields:
                mapping[component_fields[col_lower]] = col_name_str
            elif col_lower in ['repo', 'source_url'] and 'repository' in component_fields:
                mapping['repository'] = col_name_str
            elif col_lower in ['notice_url'] and 'others_url' in component_fields:
                mapping['others_url'] = col_name_str
            # 可继续扩展别名
        return mapping

    def _row_to_component_kwargs(self, row, column_mapping, component_fields):
        """
        将一行数据（dict或Series）转换为Component的参数字典。
        """
        kwargs = {}
        for field in component_fields:
            excel_col = column_mapping.get(field)
            if excel_col:
                value = self._clean_excel_string(row.get(excel_col, ''))
                if value == '':
                    value = None
                kwargs[field] = value
        # 特殊处理布尔型
        if 'modified' in kwargs and kwargs['modified'] is not None:
            kwargs['modified'] = self._str_to_bool(kwargs['modified'])
        return kwargs

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
        if not input_path.exists():
            raise FileNotFoundError(f"Input file {input_file} not found.")
        components = []
        component_fields = {f.name.lower(): f.name for f in fields(Component)}

        if input_path.suffix.lower() in ['.xlsx', '.xls']:
            try:
                df = pd.read_excel(input_path, dtype=str)
                df.fillna('', inplace=True)
                column_mapping = self._build_column_mapping(df.columns, component_fields)
                required_fields = ['name', 'copyright', 'license']
                missing_fields = [f for f in required_fields if f not in column_mapping]
                if missing_fields:
                    raise ValueError(f"Missing required columns in Excel: {missing_fields}. Available: {list(df.columns)}")
                for _, row in df.iterrows():
                    kwargs = self._row_to_component_kwargs(row, column_mapping, component_fields)
                    component = Component(**kwargs)
                    components.append(component)
            except Exception as e:
                raise ValueError(f"Error reading Excel '{input_file}': {e}")

        elif input_path.suffix.lower() in ['.json', '.yaml', '.yml']:
            try:
                with open(input_path, 'r', encoding='utf-8') as f:
                    data_source = json.load(f) if input_path.suffix.lower() == '.json' else yaml.safe_load(f)
                data_list = []
                if isinstance(data_source, list):
                    data_list = data_source
                elif isinstance(data_source, dict) and 'components' in data_source and isinstance(data_source['components'], list):
                    data_list = data_source['components']
                else:
                    raise ValueError(f"Invalid format in {input_path.name}. Expected list or dict with 'components' key.")
                # 直接用字段名做映射
                column_mapping = {k: k for k in component_fields}
                for item in data_list:
                    if not isinstance(item, dict):
                        print(f"⚠️ Skipping non-dict item in {input_path.name}: {item}")
                        continue
                    kwargs = self._row_to_component_kwargs(item, column_mapping, component_fields)
                    component = Component(**kwargs)
                    components.append(component)
            except Exception as e:
                raise ValueError(f"Error reading {input_path.name}: {e}")
        else:
            raise ValueError(f"Unsupported input file: {input_path.suffix}.")
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
                modification_notice = ""
                if comp_obj.modified:
                    mod_url_clause = ""
                    if comp_obj.modified_url:
                        mod_url_clause = self.template_manager.get_template("modification_url_clause").format(
                            modified_url=comp_obj.modified_url
                        )
                    modification_notice = self.template_manager.get_template("modification_notice").format(
                        copyright_holder_short=self.copyright_holder_short,
                        modified_url_clause=mod_url_clause
                    )

                repository_statement = ""
                if getattr(comp_obj, "repository", None):
                    repository_statement = self.template_manager.get_template("repository_statement").format(
                        repository=comp_obj.repository
                    )

                version_display = ""
                if comp_obj.version and str(comp_obj.version).strip():
                    version_display = self.template_manager.get_template("version_display").format(version=comp_obj.version)
                output_parts.append(self.template_manager.get_template("component_listing").format(
                    serial_number=idx,
                    name=comp_obj.name,
                    version=comp_obj.version or "",
                    version_display=version_display,
                    copyright=comp_obj.copyright,
                    modification_notice=modification_notice,
                    repository_statement=repository_statement
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