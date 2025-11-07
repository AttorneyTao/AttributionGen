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
                 project_name: str, copyright_holder_full: str, copyright_holder_short: str,
                 license_serial_starts: dict = None,
                 component_spacing: int = 1,  # 空行数量
                 show_source_url: bool = False):  # 全局控制是否显示源代码链接
        """
        Initialize the attribution generator.
        
        Args:
            license_config: Path to license configuration file
            template_config: Path to template configuration file
            project_name: Name of the project
            copyright_holder_full: Full legal name of copyright holder
            copyright_holder_short: Short name for copyright notices
            license_serial_starts: Dictionary for license serial start numbers
            component_spacing: Number of blank lines between components
            show_source_url: Global setting to control whether to show source URLs
        """
        self.license_manager = LicenseManager(license_config)
        self.template_manager = TemplateManager(template_config)
        self.project_name = project_name
        self.copyright_holder_full = copyright_holder_full
        self.copyright_holder_short = copyright_holder_short
        self.license_serial_starts = license_serial_starts or {}
        self.component_spacing = component_spacing  # 空行数量
        self.show_source_url = show_source_url  # 全局源代码链接显示控制

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
            elif col_lower in ['notice_url', 'other_url', 'third_party_url'] and 'others_url' in component_fields:
                mapping['others_url'] = col_name_str
            # 可继续扩展别名
        return mapping

    def _row_to_component_kwargs(self, row, column_mapping, component_fields):
        """
        �将一行数据（dict或Series）转换为Component的参数字典。
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

    def _format_optional_field(self, value: str, prefix: str = "\n") -> str:
        """处理可选字段的格式化，空值不产生换行"""
        return f"{prefix}{value}" if value else ""

    def _clean_content(self, content: str) -> str:
        """清理内容中的多余空行"""
        # 将多个连续空行替换为单个空行
        lines = [line.rstrip() for line in content.splitlines()]
        # 去掉开头和结尾的空行
        while lines and not lines[0]:
            lines.pop(0)
        while lines and not lines[-1]:
            lines.pop()
        return '\n'.join(lines)

    def _resolve_others_url(self, others_url: str, repository: str) -> str:
        """
        解析 others_url，如果是相对路径则与 repository 拼接
        
        Args:
            others_url: 原始的 others_url（可能是相对路径）
            repository: 组件的 repository URL
            
        Returns:
            完整的 URL
        """
        if not others_url:
            return ""
            
        # 如果 others_url 已经是完整 URL，直接返回
        if others_url.startswith(('http://', 'https://')):
            return others_url
            
        # 如果没有 repository，无法拼接
        if not repository:
            return others_url
            
        # 处理 GitHub URL，截取到根目录
        base_url = self._extract_github_base_url(repository)
        if not base_url:
            return others_url
            
        # 拼接相对路径
        return f"{base_url}/{others_url.lstrip('/')}"
    
    def _extract_github_base_url(self, repository_url: str) -> str:
        """
        从 GitHub repository URL 中提取基础 URL（到 tag/branch 的根目录）
        
        例如：
        https://github.com/gabime/spdlog/blob/v1.x/LICENSE 
        -> https://github.com/gabime/spdlog/tree/v1.x
        
        Args:
            repository_url: GitHub repository URL
            
        Returns:
            基础 URL，如果不是有效的 GitHub URL 返回空字符串
        """
        if not repository_url or not repository_url.startswith('https://github.com/'):
            return ""
            
        # 移除末尾的斜杠
        url = repository_url.rstrip('/')
        
        # 分割URL路径
        parts = url.split('/')
        
        # GitHub URL 格式: https://github.com/owner/repo/blob|tree/branch/path...
        # 我们需要: https://github.com/owner/repo/tree/branch
        if len(parts) >= 6 and parts[5] in ['blob', 'tree']:
            # 有 blob/tree 路径
            if len(parts) >= 7:
                # 有分支/tag信息
                base_parts = parts[:7]  # owner/repo/blob|tree/branch
                base_parts[5] = 'tree'  # 统一使用 tree
                return '/'.join(base_parts)
            else:
                # 只有 blob/tree，没有分支信息，默认使用 main
                return f"{'/'.join(parts[:5])}/tree/main"
        elif len(parts) >= 5:
            # 没有 blob/tree 路径，直接是 repo 根目录
            return f"{'/'.join(parts[:5])}/tree/main"
        else:
            # URL 格式不符合预期
            return ""

    def _has_others_in_license(self, license_expression: str) -> bool:
        """
        检查 license expression 是否包含 'and others'
        
        Args:
            license_expression: SPDX license expression
            
        Returns:
            如果包含 'others' 返回 True
        """
        if not license_expression:
            return False
        return 'others' in license_expression.lower()

    def generate_attribution(self, components: List[Component]) -> str:
        """
        生成归属文本。
        处理模板中的多余空行。
        """
        if not components: 
            return "No components to attribute."
        
        grouped_components = self.group_by_license(components)
        global_config_values = {
            "project_name": self.project_name,
            "copyright_holder_full": self.copyright_holder_full,
            "copyright_holder_short": self.copyright_holder_short
        }

        # Generate header
        output_parts = []
        header_template_str = self.template_manager.get_template("header")
        formatted_header = self._clean_content(header_template_str.format(**global_config_values))
        output_parts.append(formatted_header)
        
        # Process components by license group
        sorted_grouped_items = sorted(grouped_components.items(), key=lambda item: item[0].lower())

        for i, (license_expr_key, component_list) in enumerate(sorted_grouped_items):
            # 添加空行
            output_parts.append("")
            output_parts.append("")
            
            # 添加 license group header
            license_header = self.template_manager.get_template("license_group_header").format(
                license_id=license_expr_key
            )
            output_parts.append(self._clean_content(license_header))
            
            # 处理每个组件
            serial_start = self.license_serial_starts.get(license_expr_key, 1)
            components_with_others_urls_in_group = []
            
            for offset, comp_obj in enumerate(component_list):
                idx = serial_start + offset
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
                if getattr(comp_obj, "repository", None) and self.show_source_url:
                    repository_statement = self.template_manager.get_template("repository_statement").format(
                        repository=comp_obj.repository
                    )

                # 新增处理 repository_statement_with_newline
                repository_statement_with_newline = ""
                if getattr(comp_obj, "repository", None) and self.show_source_url:
                    repository_statement_with_newline = self.template_manager.get_template("repository_statement_with_newline").format(
                        repository=comp_obj.repository
                    )

                # 处理 others URL（仅当许可证表达式包含 'others' 且有 others_url 时）
                others_url_statement = ""
                if self._has_others_in_license(license_expr_key) and getattr(comp_obj, "others_url", None):
                    resolved_url = self._resolve_others_url(comp_obj.others_url, getattr(comp_obj, "repository", None))
                    if resolved_url:
                        others_url_statement = self.template_manager.get_template("others_license_notice").format(
                            url=resolved_url
                        )

                version_display = ""
                if comp_obj.version and str(comp_obj.version).strip():
                    version_display = self.template_manager.get_template("version_display").format(
                        version=comp_obj.version
                    )
                
                # 组合所有可选字段
                optional_statements = []
                if modification_notice:
                    optional_statements.append(modification_notice)
                if others_url_statement:
                    optional_statements.append(others_url_statement)
                
                combined_optional = self._format_optional_field("\n".join(optional_statements))
                
                # 使用工具方法处理可选字段的换行
                component_text = self.template_manager.get_template("component_listing").format(
                    serial_number=idx,
                    name=comp_obj.name,
                    version=comp_obj.version or "",
                    version_display=version_display,
                    copyright=comp_obj.copyright or "",
                    modification_notice_with_newline=combined_optional,
                    repository_statement_with_newline=repository_statement_with_newline  # 使用新处理的字段
                )
                output_parts.append(self._clean_content(component_text))
                # 在条目之间插入空行（最后一个条目后不加）
                if offset < len(component_list) - 1:
                    output_parts.extend([""] * self.component_spacing)
        
            # 添加 license text
            # 始终不显示"For license:"标记，只保留"Terms of the {license_id}:"
            combined_license_text = self.license_manager.get_license_text(license_expr_key, include_license_headers=False)
            
            if len(sorted_grouped_items) == 1:
                # 单许可证情况使用单许可证模板
                license_footer = self.template_manager.get_template("single_license_footer").format(
                    license_id=license_expr_key,
                    license_text=combined_license_text
                )
            else:
                # 多许可证情况也使用带标题但无"For license:"的模板
                license_footer = self.template_manager.get_template("license_group_footer").format(
                    license_id=license_expr_key,
                    license_text=combined_license_text
                )
            output_parts.append(self._clean_content(license_footer))

            # 只在不是最后一组时添加固定数量的空行
            if i < len(sorted_grouped_items) - 1:
                output_parts.extend(["", "", ""])

        # Generate footer
        output_parts.append("")
        footer_template_str = self.template_manager.get_template("footer")
        formatted_footer = self._clean_content(footer_template_str.format(**global_config_values))
        output_parts.append(formatted_footer)
        
        # 最后整体清理一次
        return self._clean_content("\n".join(output_parts))

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