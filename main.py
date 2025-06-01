#!/usr/bin/env python3
"""
Open Source Software Attribution Generator

A tool to generate attribution files for open source software dependencies,
with enhanced support for license expressions, "others" URLs, global project
configuration, and component modification details.
"""

import json
import yaml
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple 
from dataclasses import dataclass, field
from collections import defaultdict
import re 


@dataclass
class Component:
    """Represents a software component with license information."""
    name: str
    copyright: str
    license: str 
    version: Optional[str] = None
    others_url: Optional[str] = None
    modified: bool = False # New field
    modified_url: Optional[str] = None # New field


class LicenseManager:
    """Manages license text storage and retrieval."""

    def __init__(self, license_config_path: str = "licenses.yaml"):
        self.license_config_path = Path(license_config_path)
        self.licenses = self._load_licenses()

    def _load_licenses(self) -> Dict[str, str]:
        if not self.license_config_path.exists():
            print(f"⚠️ Warning: License configuration file '{self.license_config_path}' not found. License texts may be missing.")
            return {}
        try:
            with open(self.license_config_path, 'r', encoding='utf-8') as f:
                loaded_licenses = yaml.safe_load(f)
                if not isinstance(loaded_licenses, dict):
                    print(f"⚠️ Warning: License configuration file '{self.license_config_path}' is not a valid dictionary. Licenses may not load correctly.")
                    return {}
                return loaded_licenses
        except Exception as e:
            print(f"⚠️ Error loading license configuration file '{self.license_config_path}': {e}. No license texts will be available.")
            return {}

    def _get_individual_license_text(self, lic_id: str) -> Tuple[str, str]:
        header = f"For license: {lic_id}"
        text = ""
        if lic_id.lower() == "others":
            text = self.licenses.get(
                "OTHERS_DEFINITION",
                "[This component is subject to additional terms or conditions, often specified by the copyright holder or in accompanying notices. These 'other' terms should be detailed here, in a referenced document, or by defining 'OTHERS_DEFINITION' in your licenses.yaml. Specific URLs may be listed with components below.]"
            )
            header = f"Regarding '{lic_id}' conditions:"
        else:
            text = self.licenses.get(
                lic_id,
                f"ERROR: License text for '{lic_id}' not found in '{self.license_config_path}'. Please add the full text for this license."
            )
        return header, text

    def get_license_text(self, license_expression: str) -> str:
        if not license_expression or not license_expression.strip():
            return "License information not provided for this component."

        extracted_ids: Set[str] = set()
        is_predominantly_and = False
        is_predominantly_or = False
        is_mixed_for_intro = False
        
        temp_expr_upper = license_expression.upper()
        temp_expr_no_paren = re.sub(r'\([^)]*\)', '', temp_expr_upper)
        has_top_level_and = " AND " in temp_expr_no_paren
        has_top_level_or = " OR " in temp_expr_no_paren

        if has_top_level_and and has_top_level_or:
            is_mixed_for_intro = True
        elif has_top_level_and:
            is_predominantly_and = True
        elif has_top_level_or:
            is_predominantly_or = True

        cleaned_expression_for_ids = license_expression.replace('(', ' ').replace(')', ' ').replace(';', ' ')
        id_candidates = re.split(r'\s+(?:AND|OR)\s+|\s*[,;]\s*', cleaned_expression_for_ids, flags=re.IGNORECASE)

        for part in id_candidates:
            part = part.strip()
            if part and part.upper() not in ["AND", "OR"]:
                extracted_ids.add(part)
        
        if not extracted_ids and license_expression.strip():
             extracted_ids.add(license_expression.strip())

        intro_phrase = ""
        if len(extracted_ids) > 1: 
            if is_mixed_for_intro:
                intro_phrase = f"This component is subject to a combination of license terms ({license_expression}). You should review all applicable terms carefully:\n\n"
            elif is_predominantly_and:
                intro_phrase = f"This component is licensed under multiple terms ({license_expression}), and you should observe all of them:\n\n"
            elif is_predominantly_or:
                intro_phrase = f"This component is licensed under one of the following terms ({license_expression}), at your option (unless specified otherwise by the component's documentation):\n\n"
        
        final_text_segments = [intro_phrase]
        
        if not extracted_ids:
             lic_id_to_fetch = license_expression.strip()
             if lic_id_to_fetch:
                header, text = self._get_individual_license_text(lic_id_to_fetch)
                final_text_segments.append(f"{header}\n{'-'*len(header)}\n{text}")
             else:
                return "License information was empty or invalid."
        else:
            for i, lic_id in enumerate(sorted(list(extracted_ids))): 
                if i > 0 and intro_phrase: 
                    final_text_segments.append("\n\n--------------------\nAnd also:\n--------------------\n\n")
                elif i > 0 : 
                    final_text_segments.append("\n\n--------------------\n\n")
                header, text = self._get_individual_license_text(lic_id)
                final_text_segments.append(f"{header}\n{'-'*len(header)}\n{text}")
        return "".join(final_text_segments)


class TemplateManager:
    """Manages output templates."""
    def __init__(self, template_config_path: str = "templates.yaml"):
        self.template_config_path = Path(template_config_path)
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict[str, str]:
        default_templates = {
            # Updated header to accept project_name and copyright_holder_full
            "header": "{project_name} - OPEN SOURCE SOFTWARE ATTRIBUTIONS\n" + \
                      "Copyright (C) {copyright_holder_full}. All Rights Reserved.\n" + \
                      "=" * 60, # Increased length for potentially longer lines
            "license_group_header": "Open Source Software Licensed under: {license_id}\n" + 
                                    "# Note: The software listed below may have been modified by {copyright_holder_short}.\n" + # Added short holder
                                    "--------------------------------------------------------------------",
            # Updated component_listing to include {modification_notice}
            "component_listing": "  {serial_number}. {name}\n" + \
                                 "     Copyright: {copyright}\n" + \
                                 "     Version: {version}{modification_notice}", # modification_notice will include leading newline if needed
            "license_group_footer": "\nTerms related to \"{license_id}\":\n" + 
                                    "--------------------------------------------------------------------\n" +
                                    "{license_text}", 
            "inter_license_separator": "=" * 70, 
            "footer": "=" * 60 + "\nGenerated by OSS Attribution Generator for {project_name}", # Added project name to footer
            "others_url_section_header": "\nSpecific 'Others' Notices/URLs for components in this group:",
            "others_url_item": "  {component_serial_number}. {component_name}: {others_url}"
        }
        if not self.template_config_path.exists():
            return default_templates
        try:
            with open(self.template_config_path, 'r', encoding='utf-8') as f:
                user_templates = yaml.safe_load(f)
                if isinstance(user_templates, dict):
                    return {**default_templates, **user_templates}
                else:
                    print(f"⚠️ Warning: Template config '{self.template_config_path}' is not a dict. Using defaults.")
                    return default_templates
        except Exception as e:
            print(f"⚠️ Error loading template file '{self.template_config_path}': {e}. Using defaults.")
            return default_templates

    def get_template(self, template_name: str) -> str:
        template_str = self.templates.get(template_name)
        if template_str is None:
            print(f"⚠️ Warning: Template '{template_name}' not found. Using empty string.")
            return ""
        return template_str


class AttributionGenerator:
    """Main attribution generator class."""

    def __init__(self, license_config: str, template_config: str, 
                 project_name: str, copyright_holder_full: str, copyright_holder_short: str):
        self.license_manager = LicenseManager(license_config)
        self.template_manager = TemplateManager(template_config)
        self.project_name = project_name
        self.copyright_holder_full = copyright_holder_full
        self.copyright_holder_short = copyright_holder_short

    def _clean_excel_string(self, text: any) -> str:
        if not isinstance(text, str): text = str(text)
        return text.replace('_x000d_', '').replace('_x000D_', '').strip()

    def _str_to_bool(self, s: any) -> bool:
        if isinstance(s, bool): return s
        s_str = str(s).lower().strip()
        return s_str in ['true', '1', 't', 'y', 'yes']

    def load_components(self, input_file: str) -> List[Component]:
        input_path = Path(input_file)
        if not input_path.exists(): raise FileNotFoundError(f"Input file {input_file} not found.")
        components = []

        if input_path.suffix.lower() in ['.xlsx', '.xls']:
            try:
                df = pd.read_excel(input_path, dtype=str)
                df.fillna('', inplace=True)
                column_mapping = {}
                for col_name_obj in df.columns:
                    col_name_str = str(col_name_obj)
                    col_lower = col_name_str.lower().strip()
                    if 'component_name' in col_lower or col_lower == 'name': column_mapping['name'] = col_name_str
                    elif 'copyright' in col_lower: column_mapping['copyright'] = col_name_str
                    elif 'license' in col_lower: column_mapping['license'] = col_name_str
                    elif 'version' in col_lower: column_mapping['version'] = col_name_str
                    elif 'others_url' in col_lower or 'notice_url' in col_lower: column_mapping['others_url'] = col_name_str
                    elif 'modified' == col_lower: column_mapping['modified'] = col_name_str # Exact match for 'modified'
                    elif 'modified_url' in col_lower : column_mapping['modified_url'] = col_name_str
                
                required_fields = ['name', 'copyright', 'license']
                missing_fields = [f for f in required_fields if f not in column_mapping]
                if missing_fields: raise ValueError(f"Missing required columns in Excel: {missing_fields}. Available: {list(df.columns)}")

                for _, row in df.iterrows():
                    name = self._clean_excel_string(row.get(column_mapping.get('name'), ''))
                    if not name: continue
                    copyright_str = self._clean_excel_string(row.get(column_mapping.get('copyright'), ''))
                    license_expr = self._clean_excel_string(row.get(column_mapping.get('license'), ''))
                    version = self._clean_excel_string(row.get(column_mapping.get('version'), '')) or None
                    
                    modified_str = self._clean_excel_string(row.get(column_mapping.get('modified'), 'false')) # Default to false
                    modified = self._str_to_bool(modified_str)
                    modified_url = self._clean_excel_string(row.get(column_mapping.get('modified_url'), '')) or None
                    
                    others_url = self._clean_excel_string(row.get(column_mapping.get('others_url'), '')) or None
                    
                    if not license_expr: print(f"⚠️ Warning: Missing license for '{name}'.")
                    components.append(Component(name, copyright_str, license_expr, version, others_url, modified, modified_url))
            except Exception as e: raise ValueError(f"Error reading Excel '{input_file}': {e}")
        
        elif input_path.suffix.lower() in ['.json', '.yaml', '.yml']:
            try:
                with open(input_path, 'r', encoding='utf-8') as f:
                    data_source = json.load(f) if input_path.suffix.lower() == '.json' else yaml.safe_load(f)
                data_list = []
                if isinstance(data_source, list): data_list = data_source
                elif isinstance(data_source, dict) and 'components' in data_source and isinstance(data_source['components'], list):
                    data_list = data_source['components']
                else: raise ValueError(f"Invalid format in {input_path.name}. Expected list or dict with 'components' key.")

                for item in data_list:
                    if not isinstance(item, dict):
                        print(f"⚠️ Skipping non-dict item in {input_path.name}: {item}"); continue
                    name = self._clean_excel_string(item.get('name', ''))
                    if not name: print(f"⚠️ Skipping component with no name: {item}"); continue
                    
                    copyright_str = self._clean_excel_string(item.get('copyright', ''))
                    license_expr = self._clean_excel_string(item.get('license', ''))
                    version = self._clean_excel_string(item.get('version', '')) or None
                    others_url = self._clean_excel_string(item.get('others_url', '')) or None
                    
                    modified_input = item.get('modified', False) # Expect bool, or string like "true"
                    modified = self._str_to_bool(modified_input)
                    modified_url = self._clean_excel_string(item.get('modified_url', '')) or None

                    if not license_expr: print(f"⚠️ Missing license for '{name}' in {input_path.name}.")
                    components.append(Component(name, copyright_str, license_expr, version, others_url, modified, modified_url))
            except Exception as e: raise ValueError(f"Error reading {input_path.name}: {e}")
        else: raise ValueError(f"Unsupported input file: {input_path.suffix}.")
        return components

    def group_by_license(self, components: List[Component]) -> Dict[str, List[Component]]:
        grouped = defaultdict(list)
        for comp in components:
            key = comp.license if comp.license and comp.license.strip() else "UNSPECIFIED_LICENSE"
            grouped[key].append(comp)
        return dict(grouped)

    def generate_attribution(self, components: List[Component]) -> str:
        if not components: return "No components to attribute."
        grouped_components = self.group_by_license(components)
        
        # Pass all global config values to header and footer formatting
        global_config_values = {
            "project_name": self.project_name,
            "copyright_holder_full": self.copyright_holder_full,
            "copyright_holder_short": self.copyright_holder_short
        }

        header_template_str = self.template_manager.get_template("header")
        formatted_header = header_template_str.format(**global_config_values)
        output_parts = [formatted_header, ""]
        
        sorted_grouped_items = sorted(grouped_components.items(), key=lambda item: item[0].lower())

        for i, (license_expr_key, component_list) in enumerate(sorted_grouped_items):
            if i > 0:
                output_parts.append("")
                output_parts.append(self.template_manager.get_template("inter_license_separator"))
                output_parts.append("")

            output_parts.append(self.template_manager.get_template("license_group_header").format(
                license_id=license_expr_key,
                copyright_holder_short=self.copyright_holder_short 
            ))
            
            components_with_others_urls_in_group = []
            for idx, comp_obj in enumerate(component_list, start=1):
                modification_notice = ""
                if comp_obj.modified:
                    notice_base = f"\n     This software is modified by {self.copyright_holder_short}"
                    if comp_obj.modified_url:
                        modification_notice = f"{notice_base}, you may find the modified code at {comp_obj.modified_url}"
                    else:
                        modification_notice = f"{notice_base}."
                
                output_parts.append(self.template_manager.get_template("component_listing").format(
                    serial_number=idx, name=comp_obj.name, 
                    copyright=comp_obj.copyright, version=comp_obj.version or "N/A",
                    modification_notice=modification_notice
                ))
                if comp_obj.others_url:
                    components_with_others_urls_in_group.append({
                        "name": comp_obj.name, "url": comp_obj.others_url, "serial_number": idx
                    })

            output_parts.append("")
            combined_license_text = self.license_manager.get_license_text(license_expr_key)
            output_parts.append(self.template_manager.get_template("license_group_footer").format(
                license_id=license_expr_key, license_text=combined_license_text
            ))

            if "others" in license_expr_key.lower() and components_with_others_urls_in_group:
                output_parts.append(self.template_manager.get_template("others_url_section_header"))
                for item_data in components_with_others_urls_in_group:
                    output_parts.append(self.template_manager.get_template("others_url_item").format(
                        component_serial_number=item_data["serial_number"],
                        component_name=item_data["name"], 
                        others_url=item_data["url"]
                    ))
                output_parts.append("")

        footer_template_str = self.template_manager.get_template("footer")
        formatted_footer = footer_template_str.format(**global_config_values)
        output_parts.extend(["", formatted_footer, ""])
        return "\n".join(output_parts)

    def generate_from_file(self, input_file: str, output_file: str = "ATTRIBUTIONS.txt"):
        loaded_components = self.load_components(input_file)
        attribution_text = self.generate_attribution(loaded_components)
        output_path = Path(output_file)
        try:
            with open(output_path, 'w', encoding='utf-8') as f: f.write(attribution_text)
        except IOError as e:
            print(f"❌ Error writing to output file '{output_path}': {e}")
            raise

def main():
    # --- Global Configuration ---
    PROJECT_NAME = "Your Project Name" 
    COPYRIGHT_HOLDER_FULL = "Your Full Company Name L.L.C." 
    COPYRIGHT_HOLDER_SHORT = "YourCo" 
    # --- End Global Configuration ---

    INPUT_FILE = "components.xlsx" 
    OUTPUT_FILE = "ATTRIBUTIONS.txt"
    LICENSE_CONFIG = "licenses.yaml"
    TEMPLATE_CONFIG = "templates.yaml"

    print("OSS Attribution Generator")
    print("=" * 40)
    return_code = 0
    try:
        generator = AttributionGenerator(
            LICENSE_CONFIG, TEMPLATE_CONFIG,
            PROJECT_NAME, COPYRIGHT_HOLDER_FULL, COPYRIGHT_HOLDER_SHORT
        )
        if not Path(INPUT_FILE).exists():
            print(f"❌ Error: Input file '{INPUT_FILE}' not found.")
            return 1 
        print(f"📖 Reading components from: {INPUT_FILE}")
        component_list = generator.load_components(INPUT_FILE) 
        if not component_list:
            print("ℹ️ No components loaded.")
        else:
            print(f"✅ Loaded {len(component_list)} components.")
            grouped = generator.group_by_license(component_list)
            print("\n📊 Components by license expression:")
            if grouped:
                for license_expr, comps in sorted(grouped.items(), key=lambda x: x[0].lower()): 
                    print(f"  • \"{license_expr}\": {len(comps)} component(s)")
            else:
                print("  No components to summarize.")
        print(f"\n🔨 Generating attribution file to: {OUTPUT_FILE}")
        generator.generate_from_file(input_file=INPUT_FILE, output_file=OUTPUT_FILE)
        print(f"✅ Attribution file generated: {Path(OUTPUT_FILE).resolve()}")
        print("\n🎉 Done!")
    except FileNotFoundError as e: print(f"❌ File not found: {e}"); return_code = 1
    except ValueError as e: print(f"❌ Data error: {e}"); return_code = 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return_code = 1
    return return_code

if __name__ == "__main__":
    exit(main())
