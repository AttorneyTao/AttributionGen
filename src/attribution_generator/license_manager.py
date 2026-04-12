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
from typing import Dict, List, Set, Tuple
import re

class LicenseManager:
    class ExprNode:
        def __init__(self, kind, value=None, left=None, right=None, exception=None):
            self.kind = kind  # 'LEAF', 'WITH', 'AND', 'OR'
            self.value = value  # license id for LEAF, None for AND/OR
            self.left = left
            self.right = right
            self.exception = exception  # for WITH

    def _parse_expr(self, expr: str) -> 'ExprNode':
        """
        递归解析表达式，支持括号、AND、OR、WITH。
        返回表达式树根节点。
        """
        expr = expr.strip()
        # 括号优先
        if expr.startswith('(') and expr.endswith(')'):
            # 去除最外层括号
            inner = expr[1:-1].strip()
            # 检查括号是否配对
            depth = 0
            for i, c in enumerate(expr):
                if c == '(': depth += 1
                if c == ')': depth -= 1
                if depth == 0 and i != len(expr)-1:
                    break
            else:
                # 完全包裹，递归
                return self._parse_expr(inner)
        # 先分割顶层AND/OR
        def split_top(expr, op):
            depth = 0
            i = 0
            last = 0
            res = []
            expr_len = len(expr)
            op_len = len(op)
            while i < expr_len:
                if expr[i] == '(': depth += 1
                elif expr[i] == ')': depth -= 1
                elif depth == 0 and expr[i:i+op_len].upper() == op:
                    res.append(expr[last:i].strip())
                    last = i+op_len
                    i += op_len-1
                i += 1
            if last < expr_len:
                res.append(expr[last:].strip())
            return res if len(res) > 1 else None
        # 先OR再AND（SPDX优先级一致，左结合）
        for op in [' OR ', ' AND ']:
            parts = split_top(expr, op)
            if parts:
                nodes = [self._parse_expr(p) for p in parts]
                node = nodes[0]
                for n in nodes[1:]:
                    node = self.ExprNode(op.strip(), left=node, right=n)
                return node
        # 处理WITH
        m = re.match(r'^(.*?)(?:\s+WITH\s+)(.+)$', expr, flags=re.IGNORECASE)
        if m:
            main = m.group(1).strip()
            exc = m.group(2).strip()
            return self.ExprNode('WITH', left=self._parse_expr(main), exception=exc)
        # 叶子节点
        return self.ExprNode('LEAF', value=expr)
    """
    Manages license text storage and retrieval.
    
    This class handles all aspects of license text management:
    1. Loading license texts from configuration file
    2. Processing complex license expressions
    3. Combining multiple license texts
    4. Handling special cases and error conditions
    """

    def __init__(self, license_config_path: str = "licenses.yaml",
                 alias_config_path: str = "license_aliases.yaml"):
        """
        Initialize the license manager.

        Args:
            license_config_path: Path to license configuration file (licenses.yaml)
            alias_config_path: Path to alias table file (license_aliases.yaml)
        """
        self.license_config_path = Path(license_config_path)
        self.alias_config_path = Path(alias_config_path)
        self._license_original_case: Dict[str, str] = {}  # populated by _load_licenses
        self.licenses = self._load_licenses()
        self.aliases = self._load_aliases()
        self.missing_licenses = set()

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
                # Build a lowercase → original-case mapping so we can recover
                # canonical SPDX casing (e.g. "bsd-3-clause" → "BSD-3-Clause")
                self._license_original_case: Dict[str, str] = {
                    str(k).lower(): str(k) for k in loaded_licenses
                }
                return {str(k).lower(): v for k, v in loaded_licenses.items()}
        except Exception as e:
            print(f"⚠️ Error loading license configuration file '{self.license_config_path}': {e}. No license texts will be available.")
            return {}

    @staticmethod
    def _normalize_id(lic_id: str) -> str:
        """
        Normalize a license identifier for fuzzy matching.

        Replaces every run of whitespace characters (including non-breaking spaces
        such as U+00A0, U+2009, U+202F, etc.) with a single hyphen, collapses
        consecutive hyphens, strips leading/trailing hyphens, and lowercases the
        result.

        Examples:
            'BSD  3-Clause'  -> 'bsd-3-clause'
            'Apache\\xa02.0' -> 'apache-2.0'
            'MIT'            -> 'mit'
        """
        # \s covers ASCII whitespace; the character class also catches common
        # Unicode space variants that \s may miss depending on the Python build.
        normalized = re.sub(r'[\s\xa0\u2000-\u200b\u202f\u205f\u3000]+', '-', lic_id.strip())
        normalized = re.sub(r'-{2,}', '-', normalized)
        return normalized.strip('-').lower()

    def _load_aliases(self) -> Dict[str, str]:
        """
        Load license alias table from configuration file.

        Keys are normalized via _normalize_id so that lookups are space-insensitive
        and hyphen-normalised.  Values keep their original SPDX casing.

        Returns:
            Dictionary mapping normalized alias strings to SPDX identifiers.
            Returns empty dict if file not found.
        """
        if not self.alias_config_path.exists():
            return {}
        try:
            with open(self.alias_config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                return {}
            return {self._normalize_id(str(k)): str(v) for k, v in data.items()}
        except Exception as e:
            print(f"⚠️ Warning: Could not load alias config '{self.alias_config_path}': {e}")
            return {}

    def resolve_id(self, lic_id: str) -> str:
        """
        Resolve a license identifier to its canonical SPDX identifier.

        Lookup order:
          1. Exact lowercase match in alias table.
          2. Normalized form (spaces → hyphens) match in alias table.

        Args:
            lic_id: The license identifier to resolve (may be non-SPDX).

        Returns:
            The SPDX identifier if a mapping exists, otherwise lic_id unchanged.
        """
        # Try exact lowercase first (handles IDs that are already SPDX-like)
        hit = self.aliases.get(lic_id.lower())
        if hit:
            return hit
        # Try normalized form
        return self.aliases.get(self._normalize_id(lic_id), lic_id)

    def can_resolve(self, lic_id: str) -> bool:
        """
        Return True if lic_id can be resolved to a known license text via any path:
        direct lookup, normalization, or alias table.
        """
        if lic_id.lower() in self.licenses:
            return True
        if self._normalize_id(lic_id) in self.licenses:
            return True
        resolved = self.resolve_id(lic_id)
        return resolved.lower() in self.licenses

    def _canonical_id(self, lic_id: str) -> str:
        """
        Return the canonical SPDX identifier for a single license leaf.

        Resolution order:
          1. Alias table → returns the alias value (already canonical SPDX casing).
          2. Normalized form matched in licenses → recover original YAML key casing.
          3. Direct lowercase match → recover original YAML key casing.
          4. Not found → return lic_id unchanged.

        'others' is returned as-is (it is a special structural token, not a SPDX ID).
        """
        if lic_id.lower() == 'others':
            return lic_id

        # Alias table has canonical SPDX casing as its values
        resolved = self.resolve_id(lic_id)
        if resolved != lic_id:
            return resolved

        # Try to recover original YAML casing via the original-case map
        normalized = self._normalize_id(lic_id)
        if normalized in self._license_original_case:
            return self._license_original_case[normalized]
        if lic_id.lower() in self._license_original_case:
            return self._license_original_case[lic_id.lower()]

        return lic_id  # unknown — leave as-is

    def normalize_expression(self, expression: str) -> str:
        """
        Normalize a full license expression by replacing every leaf ID with its
        canonical SPDX identifier and uppercasing the AND / OR / WITH operators.

        Examples:
            'gpl-2.0 and others'        → 'GPL-2.0-only AND others'
            'bsd  3-clause'             → 'BSD-3-Clause'
            'Apache-2.0 AND MIT'        → 'Apache-2.0 AND MIT'  (unchanged)
        """
        if not expression or not expression.strip():
            return expression

        def render(node) -> str:
            if node is None:
                return ''
            if node.kind == 'LEAF':
                return self._canonical_id(node.value)
            if node.kind == 'WITH':
                left = render(node.left)
                exc = self._canonical_id(node.exception) if node.exception else ''
                return f'{left} WITH {exc}'
            if node.kind == 'AND':
                return f'{render(node.left)} AND {render(node.right)}'
            if node.kind == 'OR':
                return f'{render(node.left)} OR {render(node.right)}'
            return expression

        return render(self._parse_expr(expression))

    def get_leaf_ids(self, expression: str) -> List[str]:
        """
        Extract all individual license identifiers (leaf nodes) from a license expression.

        Args:
            expression: SPDX-style license expression, possibly containing AND/OR/WITH.

        Returns:
            List of leaf license ID strings (excludes the special 'others' token).
        """
        def collect(node, result):
            if node is None:
                return
            if node.kind == 'LEAF':
                val = node.value.strip()
                if val.lower() != 'others':
                    result.append(val)
            elif node.kind == 'WITH':
                collect(node.left, result)
                if node.exception:
                    exc = node.exception.strip()
                    if exc.lower() != 'others':
                        result.append(exc)
            else:  # AND or OR
                collect(node.left, result)
                collect(node.right, result)

        result: List[str] = []
        if expression and expression.strip():
            tree = self._parse_expr(expression)
            collect(tree, result)
        return result

    def add_alias(self, alias: str, spdx_id: str) -> None:
        """
        Add a new alias mapping and persist it to the alias config file.

        The alias key is normalized (spaces → hyphens, lowercased) before storage
        so it is consistent with the normalization applied during lookup.

        Args:
            alias: The non-standard identifier to map.
            spdx_id: The canonical SPDX identifier it maps to.
        """
        alias_key = self._normalize_id(alias)
        self.aliases[alias_key] = spdx_id
        try:
            with open(self.alias_config_path, 'a', encoding='utf-8') as f:
                f.write(f'{alias_key}: {spdx_id}\n')
        except Exception as e:
            print(f"⚠️ Warning: Could not save alias to '{self.alias_config_path}': {e}")

    def add_license_text(self, spdx_id: str, text: str) -> None:
        """
        Add a new license text entry and append it to licenses.yaml.

        Args:
            spdx_id: The SPDX identifier for the license.
            text: The full license text.
        """
        self.licenses[spdx_id.lower()] = text
        self._license_original_case[spdx_id.lower()] = spdx_id
        try:
            with open(self.license_config_path, 'a', encoding='utf-8') as f:
                f.write(f'\n{spdx_id}: |\n')
                for line in text.splitlines():
                    f.write(f'  {line}\n')
        except Exception as e:
            print(f"⚠️ Warning: Could not save license text to '{self.license_config_path}': {e}")

    def _get_individual_license_text(self, lic_id: str, include_header: bool = True) -> Tuple[str, str]:
        """
        Get text for a single license.
        
        Retrieves the license text and appropriate header for a given license ID.
        Handles special cases like "others" licenses.
        
        Args:
            lic_id: License identifier
            include_header: Whether to include "For license:" header
            
        Returns:
            Tuple of (header, text)
        """
        if include_header:
            header = f"For license: {lic_id}"
        else:
            header = ""
        text = ""
        if lic_id.lower() == "others":
            text = self.licenses.get(
                "others_definition",  # 这里也要小写
                "[This component is subject to additional terms or conditions, often specified by the copyright holder or in accompanying notices. These 'other' terms should be detailed here, in a referenced document, or by defining 'OTHERS_DEFINITION' in your licenses.yaml. Specific URLs may be listed with components below.]"
            )
            header = f"Regarding '{lic_id}' conditions:"
        else:
            # --- Resolution order ---
            # 1. Exact lowercase match in licenses.yaml
            # 2. Normalized form (spaces → hyphens) direct match in licenses.yaml
            # 3. Alias table lookup (also uses normalization internally)
            if lic_id.lower() in self.licenses:
                text = self.licenses[lic_id.lower()]
            else:
                normalized_key = self._normalize_id(lic_id)
                if normalized_key in self.licenses:
                    # Normalized form matched a known SPDX entry directly
                    text = self.licenses[normalized_key]
                else:
                    # Try alias resolution (resolve_id also applies normalization)
                    resolved_id = self.resolve_id(lic_id)
                    if resolved_id.lower() in self.licenses:
                        text = self.licenses[resolved_id.lower()]
                        if include_header and resolved_id.lower() != lic_id.lower():
                            header = f"For license: {resolved_id}"
                    else:
                        missing_id = resolved_id if resolved_id.lower() != lic_id.lower() else lic_id
                        text = f"ERROR: License text for '{missing_id}' not found in '{self.license_config_path}'. Please add the full text for this license."
                        self.missing_licenses.add(missing_id)
        return header, text

    def get_license_text(self, license_expression: str, include_license_headers: bool = True) -> str:
        """
        Get combined license text for a license expression.
        
        Processes complex license expressions (e.g., "MIT AND Apache-2.0")
        and combines the appropriate license texts with explanatory headers.
        Special handling for "with" syntax for license exceptions.
        
        Args:
            license_expression: License expression to process
            include_license_headers: Whether to include "For license:" headers
            
        Returns:
            Combined license text with appropriate headers and formatting
        """
        if not license_expression or not license_expression.strip():
            return "License information not provided for this component."

        # Check if this is a "with" exception case
        has_with_exception = " with " in license_expression.lower()
        
        # Extract individual license IDs

        # 新实现：支持混合AND/OR/WITH表达式
        # 新实现：递归遍历表达式树生成归属文本
        def render(node, intro=True):
            if node is None:
                return ""
            if node.kind == 'LEAF':
                header, text = self._get_individual_license_text(node.value, include_license_headers)
                if not text.strip():  # Skip if the text is empty or None
                    return ""
                if header:
                    return f"{header}\n{'-'*len(header)}\n{text}"
                else:
                    return text
            elif node.kind == 'WITH':
                main_text = render(node.left, intro=False)
                exc_header, exc_text = self._get_individual_license_text(node.exception, True)
                return f"{main_text}\n\n--------------------\nWith the following exception(s):\n--------------------\n\nException: {exc_header}\n{'-'*(len(exc_header)+11)}\n{exc_text}"
            elif node.kind == 'AND' or node.kind == 'OR':
                op = node.kind
                left = render(node.left, intro=False)
                right = render(node.right, intro=False)
                op_str = "And also" if op == 'AND' else "Or"
                return f"{left}\n\n--------------------\n{op_str}:\n--------------------\n\n{right}"
            else:
                return ""

        # intro phrase
        intro_phrase = ""
        if '(' in license_expression or ')' in license_expression:
            intro_phrase = f"This component is subject to a complex license expression ({license_expression}). Please review all applicable terms carefully:\n\n"
        # else可根据需要保留原有intro逻辑
        expr_tree = self._parse_expr(license_expression)
        return intro_phrase + render(expr_tree)