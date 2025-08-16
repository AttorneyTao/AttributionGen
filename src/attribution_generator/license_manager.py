"""
License manager module for handling license texts and expressions.

This module provides the LicenseManager class that handles:
1. Loading license texts from configuration
2. Processing license expressions
3. Combining multiple license texts
4. Handling special cases like "others" licenses
"""

import yaml
from pathlib import Path
from typing import Dict, Set, Tuple
import re

class LicenseManager:
    """
    Manages license text storage and retrieval.
    
    This class handles all aspects of license text management:
    1. Loading license texts from configuration file
    2. Processing complex license expressions
    3. Combining multiple license texts
    4. Handling special cases and error conditions
    """

    def __init__(self, license_config_path: str = "licenses.yaml"):
        """
        Initialize the license manager.
        
        Args:
            license_config_path: Path to license configuration file
        """
        self.license_config_path = Path(license_config_path)
        self.licenses = self._load_licenses()

    def _load_licenses(self) -> Dict[str, str]:
        """
        Load license texts from configuration file.
        
        Loads and validates the license configuration file containing
        license texts and special definitions.
        
        Returns:
            Dictionary mapping license IDs to their texts
            
        Note:
            Returns empty dict if file not found or invalid
        """
        if not self.license_config_path.exists():
            print(f"⚠️ Warning: License configuration file '{self.license_config_path}' not found. License texts may be missing.")
            return {}
        try:
            with open(self.license_config_path, 'r', encoding='utf-8') as f:
                loaded_licenses = yaml.safe_load(f)
                if not isinstance(loaded_licenses, dict):
                    print(f"⚠️ Warning: License configuration file '{self.license_config_path}' is not a valid dictionary. Licenses may not load correctly.")
                    return {}
                # 关键：全部转小写
                return {str(k).lower(): v for k, v in loaded_licenses.items()}
        except Exception as e:
            print(f"⚠️ Error loading license configuration file '{self.license_config_path}': {e}. No license texts will be available.")
            return {}

    def _get_individual_license_text(self, lic_id: str) -> Tuple[str, str]:
        """
        Get text for a single license.
        
        Retrieves the license text and appropriate header for a given license ID.
        Handles special cases like "others" licenses.
        
        Args:
            lic_id: License identifier
            
        Returns:
            Tuple of (header, text)
        """
        header = f"For license: {lic_id}"
        text = ""
        if lic_id.lower() == "others":
            text = self.licenses.get(
                "others_definition",  # 这里也要小写
                "[This component is subject to additional terms or conditions, often specified by the copyright holder or in accompanying notices. These 'other' terms should be detailed here, in a referenced document, or by defining 'OTHERS_DEFINITION' in your licenses.yaml. Specific URLs may be listed with components below.]"
            )
            header = f"Regarding '{lic_id}' conditions:"
        else:
            text = self.licenses.get(
                lic_id.lower(),  # 查找时小写
                f"ERROR: License text for '{lic_id}' not found in '{self.license_config_path}'. Please add the full text for this license."
            )
        return header, text

    def get_license_text(self, license_expression: str) -> str:
        """
        Get combined license text for a license expression.
        
        Processes complex license expressions (e.g., "MIT AND Apache-2.0")
        and combines the appropriate license texts with explanatory headers.
        
        Args:
            license_expression: License expression to process
            
        Returns:
            Combined license text with appropriate headers and formatting
        """
        if not license_expression or not license_expression.strip():
            return "License information not provided for this component."

        # Extract individual license IDs
        extracted_ids: Set[str] = set()
        is_predominantly_and = False
        is_predominantly_or = False
        is_mixed_for_intro = False
        
        # Analyze license expression structure
        temp_expr_upper = license_expression.upper()
        temp_expr_no_paren = re.sub(r'\([^)]*\)', '', temp_expr_upper)
        has_top_level_and = " AND " in temp_expr_no_paren
        has_top_level_or = " OR " in temp_expr_no_paren

        # Determine expression type for appropriate introduction
        if has_top_level_and and has_top_level_or:
            is_mixed_for_intro = True
        elif has_top_level_and:
            is_predominantly_and = True
        elif has_top_level_or:
            is_predominantly_or = True

        # Extract individual license IDs
        cleaned_expression_for_ids = license_expression.replace('(', ' ').replace(')', ' ').replace(';', ' ')
        id_candidates = re.split(r'\s+(?:AND|OR)\s+|\s*[,;]\s*', cleaned_expression_for_ids, flags=re.IGNORECASE)

        for part in id_candidates:
            part = part.strip()
            if part and part.upper() not in ["AND", "OR"]:
                extracted_ids.add(part)
        
        if not extracted_ids and license_expression.strip():
             extracted_ids.add(license_expression.strip())

        # Generate appropriate introduction based on expression type
        intro_phrase = ""
        if len(extracted_ids) > 1: 
            if is_mixed_for_intro:
                intro_phrase = f"This component is subject to a combination of license terms ({license_expression}). You should review all applicable terms carefully:\n\n"
            elif is_predominantly_and:
                intro_phrase = f"This component is licensed under multiple terms ({license_expression}), and you should observe all of them:\n\n"
            elif is_predominantly_or:
                intro_phrase = f"This component is licensed under one of the following terms ({license_expression}), at your option (unless specified otherwise by the component's documentation):\n\n"
        
        # Build final text
        final_text_segments = [intro_phrase]
        
        if not extracted_ids:
             lic_id_to_fetch = license_expression.strip()
             if lic_id_to_fetch:
                header, text = self._get_individual_license_text(lic_id_to_fetch)
                final_text_segments.append(f"{header}\n{'-'*len(header)}\n{text}")
             else:
                return "License information was empty or invalid."
        else:
            # Add each license text with appropriate separators
            for i, lic_id in enumerate(sorted(list(extracted_ids))): 
                if i > 0 and intro_phrase: 
                    final_text_segments.append("\n\n--------------------\nAnd also:\n--------------------\n\n")
                elif i > 0 : 
                    final_text_segments.append("\n\n--------------------\n\n")
                header, text = self._get_individual_license_text(lic_id)
                final_text_segments.append(f"{header}\n{'-'*len(header)}\n{text}")
        return "".join(final_text_segments)