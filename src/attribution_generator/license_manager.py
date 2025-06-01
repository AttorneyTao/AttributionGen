import yaml
from pathlib import Path
from typing import Dict, Set, Tuple
import re

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