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

    def __init__(self, license_config_path: str = "licenses.yaml"):
        """
        Initialize the license manager.
        
        Args:
            license_config_path: Path to license configuration file
        """
        self.license_config_path = Path(license_config_path)
        self.licenses = self._load_licenses()
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
                # 关键：全部转小写
                return {str(k).lower(): v for k, v in loaded_licenses.items()}
        except Exception as e:
            print(f"⚠️ Error loading license configuration file '{self.license_config_path}': {e}. No license texts will be available.")
            return {}

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
            if lic_id.lower() in self.licenses:
                text = self.licenses[lic_id.lower()]
            else:
                text = f"ERROR: License text for '{lic_id}' not found in '{self.license_config_path}'. Please add the full text for this license."
                self.missing_licenses.add(lic_id)
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