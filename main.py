#!/usr/bin/env python3
"""
Open Source Software Attribution Generator

A tool to generate attribution files for open source software dependencies,
with enhanced support for license expressions, "others" URLs, global project
configuration, and component modification details.

This script serves as the main entry point for the attribution generator.
It handles:
1. Project configuration
2. Component loading from various input formats
3. Attribution file generation
4. Error handling and reporting
"""
import sys
import argparse
from pathlib import Path
import yaml
import datetime
import pandas as pd
# Add src directory to Python path to allow importing from the package
sys.path.insert(0, str(Path(__file__).parent / "src"))
from attribution_generator.generator import AttributionGenerator
from attribution_generator.component import Component

# Risk classification for common SPDX license identifiers.
# Covers canonical IDs as stored in licenses.yaml / resolved via alias table.
_RISK_HIGH = "high"
_RISK_MEDIUM = "medium"

LICENSE_RISK_TABLE = {
    # ── 高风险：强著佐权（Copyleft） ────────────────────────────────────────
    "GPL-2.0-only":      (_RISK_HIGH,   "强著佐权：分发衍生作品须以 GPL-2.0 开源"),
    "GPL-2.0-or-later":  (_RISK_HIGH,   "强著佐权：分发衍生作品须以 GPL-2.0+ 开源"),
    "GPL-3.0-only":      (_RISK_HIGH,   "强著佐权：分发衍生作品须以 GPL-3.0 开源"),
    "GPL-3.0-or-later":  (_RISK_HIGH,   "强著佐权：分发衍生作品须以 GPL-3.0+ 开源"),
    "AGPL-3.0-only":     (_RISK_HIGH,   "网络著佐权：通过网络提供服务亦须开源，风险极高"),
    "AGPL-3.0-or-later": (_RISK_HIGH,   "网络著佐权：通过网络提供服务亦须开源，风险极高"),
    "SSPL-1.0":          (_RISK_HIGH,   "服务著佐权：以此软件对外提供服务须开源整个服务栈"),
    "OSL-3.0":           (_RISK_HIGH,   "强著佐权：所有衍生作品须以 OSL-3.0 发布"),
    # ── 中等风险：弱著佐权（Weak Copyleft） ─────────────────────────────────
    "LGPL-2.0-only":     (_RISK_MEDIUM, "弱著佐权：动态链接通常允许，静态链接须注意"),
    "LGPL-2.0-or-later": (_RISK_MEDIUM, "弱著佐权：动态链接通常允许，静态链接须注意"),
    "LGPL-2.1-only":     (_RISK_MEDIUM, "弱著佐权：动态链接通常允许，静态链接须注意"),
    "LGPL-2.1-or-later": (_RISK_MEDIUM, "弱著佐权：动态链接通常允许，静态链接须注意"),
    "LGPL-3.0-only":     (_RISK_MEDIUM, "弱著佐权：动态链接通常允许，静态链接须注意"),
    "LGPL-3.0-or-later": (_RISK_MEDIUM, "弱著佐权：动态链接通常允许，静态链接须注意"),
    "MPL-2.0":           (_RISK_MEDIUM, "文件级著佐权：被修改的文件须以 MPL-2.0 开源"),
    "CDDL-1.0":          (_RISK_MEDIUM, "文件级著佐权：被修改的文件须以 CDDL-1.0 开源"),
    "EPL-1.0":           (_RISK_MEDIUM, "插件著佐权：与 EPL 代码链接的模块可能须开源"),
    "EPL-2.0":           (_RISK_MEDIUM, "插件著佐权：与 EPL 代码链接的模块可能须开源"),
    "EUPL-1.1":          (_RISK_MEDIUM, "弱著佐权：修改版须以 EUPL 或兼容许可证开源"),
    "EUPL-1.2":          (_RISK_MEDIUM, "弱著佐权：修改版须以 EUPL 或兼容许可证开源"),
    "CPAL-1.0":          (_RISK_MEDIUM, "广告条款著佐权：修改版须保留原始归属信息"),
    "CDLA-Sharing-1.0":  (_RISK_MEDIUM, "数据著佐权：共享衍生数据集须以相同条款发布"),
}


def _prompt_license_text(lm, lic_id: str) -> bool:
    """
    Interactively prompt the user to paste the full text for a license.
    The text is appended to licenses.yaml via lm.add_license_text().

    If the user enters nothing (empty input), a clearly-marked placeholder is
    stored so generation can proceed, but a warning is printed.

    Returns:
        True if real text was provided; False if only a placeholder was saved.
    """
    print(f"   请粘贴 '{lic_id}' 的完整许可证文本")
    print(f"   (在单独一行输入一个英文句点 '.' 并回车，表示输入结束):")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == '.':
            break
        lines.append(line)

    if lines:
        lm.add_license_text(lic_id, '\n'.join(lines))
        print(f"   ✅ 已将 '{lic_id}' 的许可证文本追加到 licenses.yaml")
        return True
    else:
        placeholder = f"[LICENSE TEXT FOR '{lic_id}' NOT PROVIDED — please add manually to licenses.yaml]"
        lm.add_license_text(lic_id, placeholder)
        print(f"   ⚠️  未输入文本，已写入占位符，请事后手动补充到 licenses.yaml")
        return False


def preflight_check(generator: AttributionGenerator, component_list: list) -> None:
    """
    Pre-flight check: interactively resolve all unknown license identifiers
    before generating the attribution file.

    For each unique leaf license ID across all components (including the special
    UNSPECIFIED_LICENSE key used for components with no license field):
      1. If it resolves directly (via licenses.yaml or alias table) → OK, skip.
      2. If not found → ask the user which SPDX identifier it corresponds to.
         Pressing Enter skips the alias step and uses the original identifier.
      3. If the resolved identifier still has no text in licenses.yaml → the user
         MUST paste the license text; an empty entry writes a placeholder instead
         of silently skipping.
    """
    lm = generator.license_manager

    # Collect all unique leaf IDs, including UNSPECIFIED_LICENSE for empty fields
    all_leaf_ids: set = set()
    for comp in component_list:
        if comp.license and comp.license.strip():
            for leaf in lm.get_leaf_ids(comp.license):
                all_leaf_ids.add(leaf)
        else:
            all_leaf_ids.add("UNSPECIFIED_LICENSE")

    if not all_leaf_ids:
        return

    print("\n🔍 预检所有许可证标识符...")

    processed: set = set()

    for leaf_id in sorted(all_leaf_ids):
        if leaf_id.lower() == 'others' or leaf_id in processed:
            continue
        processed.add(leaf_id)

        if lm.can_resolve(leaf_id):
            continue

        # ── Step 1: ask for SPDX identifier (Enter = keep original name) ──
        print(f"\n⚠️  未知许可证标识符: '{leaf_id}'")
        print(f"   请输入该许可证对应的SPDX标识符 (如: MIT, Apache-2.0)")
        print(f"   参考: https://spdx.org/licenses/  或  https://scancode-licensedb.aboutcode.org/")
        print(f"   直接回车则以 '{leaf_id}' 作为标识符，无需建立别名:")
        user_input = input("   > ").strip()

        if user_input:
            resolved_id = user_input
            lm.add_alias(leaf_id, resolved_id)
            print(f"   ✅ 已保存别名: '{leaf_id}' → '{resolved_id}'")
        else:
            resolved_id = leaf_id
            print(f"   (使用 '{leaf_id}' 作为许可证标识符)")

        # ── Step 2: if resolved ID still has no text → must provide text ──
        if lm.can_resolve(resolved_id):
            continue

        print(f"\n⚠️  licenses.yaml 中缺少许可证文本: '{resolved_id}'")
        _prompt_license_text(lm, resolved_id)

def check_license_risks(generator: AttributionGenerator, component_list: list) -> None:
    """
    Scan all components for medium/high-risk licenses and print a CLI warning
    block.  Called after preflight_check so aliases are already resolved.
    """
    lm = generator.license_manager
    # findings: spdx_id → {risk, desc, components: [name, ...]}
    findings = {}
    for comp in component_list:
        if not comp.license or not comp.license.strip():
            continue
        for leaf_id in lm.get_leaf_ids(comp.license):
            resolved = lm.resolve_id(leaf_id)
            if resolved in LICENSE_RISK_TABLE:
                risk_level, desc = LICENSE_RISK_TABLE[resolved]
                entry = findings.setdefault(resolved, {"risk": risk_level, "desc": desc, "components": []})
                entry["components"].append(comp.name)

    if not findings:
        return

    high = {k: v for k, v in findings.items() if v["risk"] == _RISK_HIGH}
    medium = {k: v for k, v in findings.items() if v["risk"] == _RISK_MEDIUM}

    print(f"\n{'='*44}")
    print("⚠️   许可证风险预警")
    print(f"{'='*44}")

    if high:
        print("🔴 高风险（强著佐权 Copyleft）:")
        for spdx_id, info in sorted(high.items()):
            names = ", ".join(info["components"])
            count = len(info["components"])
            print(f"  • {spdx_id}")
            print(f"    风险: {info['desc']}")
            print(f"    涉及组件 ({count}): {names}")

    if medium:
        if high:
            print()
        print("🟡 中等风险（弱著佐权 Weak Copyleft）:")
        for spdx_id, info in sorted(medium.items()):
            names = ", ".join(info["components"])
            count = len(info["components"])
            print(f"  • {spdx_id}")
            print(f"    风险: {info['desc']}")
            print(f"    涉及组件 ({count}): {names}")

    print(f"{'='*44}")
    print("💡 建议: 请法务团队审查上述许可证的合规要求。")


# ── Column patterns for Tencent-style Excel input ──────────────────────────────
# Each entry maps a Component field (or '_distribute' filter) to a list of
# substrings that may appear in the actual column header (case-insensitive).
_INPUTS_COLUMN_PATTERNS: dict = {
    'name':        ['组件/模型名称', '组件名称', '名称'],
    'version':     ['组件/模型版本号', '版本号', '版本'],
    'repository':  ['组件/模型下载地址', '下载地址'],
    'modified':    ['是否修改'],
    'license':     ['开源协议名称', '协议名称', '许可证名称', '许可证'],
    'copyright':   ['版权信息', '版权'],
    'others_url':  ['third_party', 'third party', 'others_url', 'others url'],
    '_distribute': ['是否分发'],
}


def _detect_header_row(excel_path: Path, max_scan: int = 5) -> int:
    """
    Scan the first few rows to find the one that looks like a column header.
    Returns the 0-based row index suitable for passing as pandas header=.
    """
    df_raw = pd.read_excel(excel_path, header=None, dtype=str, nrows=max_scan)
    df_raw.fillna('', inplace=True)
    keywords = ['是否分发', '名称', '版本', 'third_party', 'license', 'name']
    best_row, best_score = 0, 0
    for i, row in df_raw.iterrows():
        row_text = ' '.join(str(v) for v in row).lower()
        score = sum(1 for kw in keywords if kw.lower() in row_text)
        if score > best_score:
            best_score, best_row = score, i
    return best_row


def _map_columns(headers: list) -> dict:
    """
    Match actual column headers against _INPUTS_COLUMN_PATTERNS.
    Returns {field: actual_column_name} for every pattern that matched.
    """
    mapping: dict = {}
    for field, patterns in _INPUTS_COLUMN_PATTERNS.items():
        for header in headers:
            h = str(header).strip()
            if any(p.lower() in h.lower() for p in patterns):
                mapping[field] = h
                break
    return mapping


def select_and_load_inputs_excel() -> list | None:
    """
    Interactive loader for Tencent-style component Excel files in ./inputs/.

    Steps:
      1. List all .xlsx / .xls files in the inputs/ directory.
      2. Let the user pick one by number.
      3. Auto-detect the real header row (skips merged description rows).
      4. Filter to rows where '是否分发' == '是'.
      5. Map columns to Component fields; third_party → others_url (optional).

    Returns a list of Component objects, or None on unrecoverable error.
    """
    inputs_dir = Path('inputs')
    if not inputs_dir.exists():
        print("❌ 未找到 'inputs' 目录。")
        return None

    excel_files = sorted(
        list(inputs_dir.glob('*.xlsx')) + list(inputs_dir.glob('*.xls'))
    )
    if not excel_files:
        print("❌ 'inputs/' 目录中未找到 Excel 文件。")
        return None

    print("\n📂 'inputs/' 目录中的 Excel 文件：")
    for i, f in enumerate(excel_files, 1):
        print(f"  {i}. {f.name}")

    while True:
        try:
            raw = input(f"\n请选择文件编号 (1-{len(excel_files)}): ").strip()
            idx = int(raw) - 1
            if 0 <= idx < len(excel_files):
                selected = excel_files[idx]
                break
            print(f"  请输入 1 到 {len(excel_files)} 之间的数字。")
        except ValueError:
            print("  请输入有效数字。")

    print(f"📖 已选择: {selected.name}")

    header_row = _detect_header_row(selected)
    df = pd.read_excel(selected, header=header_row, dtype=str)
    df.fillna('', inplace=True)

    col_map = _map_columns(list(df.columns))

    # Validate required columns
    missing = [f for f in ('name', 'license', 'copyright') if f not in col_map]
    if missing:
        print(f"❌ 无法识别以下必需列: {missing}")
        print(f"   当前识别到的列: {list(df.columns)}")
        return None

    # Filter by 是否分发 == 是
    dist_col = col_map.get('_distribute')
    if dist_col:
        before = len(df)
        df = df[df[dist_col].str.strip() == '是'].copy()
        after = len(df)
        print(f"🔍 按「是否分发=是」过滤: {before} 行 → {after} 行")
    else:
        print("⚠️  未找到「是否分发」列，将使用全部行。")

    if df.empty:
        print("ℹ️  过滤后无数据。")
        return []

    def _get(row, field):
        col = col_map.get(field)
        if col is None:
            return None
        val = str(row.get(col, '')).strip()
        return val if val else None

    components = []
    for _, row in df.iterrows():
        modified_raw = _get(row, 'modified') or ''
        modified = modified_raw.strip() in ('是', '1', 'yes', 'true', 'y', 't')
        comp = Component(
            name=_get(row, 'name') or '',
            copyright=_get(row, 'copyright') or '',
            license=_get(row, 'license') or '',
            version=_get(row, 'version'),
            repository=_get(row, 'repository'),
            modified=modified,
            others_url=_get(row, 'others_url'),
        )
        components.append(comp)

    # 与 generator.load_components() 保持一致：
    # 有 others_url 但 license 里没有 'others' 的组件，自动追加 AND others
    AttributionGenerator._patch_others_in_license(components)

    return components


def main():
    """
    Main entry point for the Attribution Generator.

    Command line usage:
        python main.py [input_file]          # explicit file
        python main.py -i / --from-inputs    # pick from inputs/ directory

    Returns:
        int: 0 for success, 1 for failure
    """
    # --- Global Configuration ---
    CONFIG_FILE = "project_config.yaml"
    if not Path(CONFIG_FILE).exists():
        print(f"❌ Error: Config file '{CONFIG_FILE}' not found.")
        return 1
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    PROJECT_NAME = config.get("project_name", "Unknown Project")
    COPYRIGHT_HOLDER_FULL = config.get("copyright_holder_full", "")
    COPYRIGHT_HOLDER_SHORT = config.get("copyright_holder_short", "")

    # --- Argument parsing ---
    parser = argparse.ArgumentParser(
        description='OSS Attribution Generator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'input_file', nargs='?',
        help='Input file path (xlsx/yaml/json). Defaults to project_config.yaml input_file.',
    )
    parser.add_argument(
        '-i', '--from-inputs', action='store_true',
        help='Interactively select an Excel file from the ./inputs/ directory.',
    )
    args = parser.parse_args()

    use_inputs_dir = args.from_inputs
    if not use_inputs_dir:
        if args.input_file:
            INPUT_FILE = args.input_file
        else:
            INPUT_FILE = config.get("input_file", "components.xlsx")
        
    # 生成带时间戳的输出文件名
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    OUTPUT_DIR = "outputs"
    OUTPUT_FILE = f"{OUTPUT_DIR}/ATTRIBUTIONS{timestamp}.txt"
    
    # 确保输出目录存在
    Path(OUTPUT_DIR).mkdir(exist_ok=True)
    
    LICENSE_CONFIG = config.get("license_config", "licenses.yaml")
    TEMPLATE_CONFIG = config.get("template_config", "templates.yaml")
    ALIAS_CONFIG = config.get("alias_config", "license_aliases.yaml")
    LICENSE_SERIAL_STARTS = config.get("license_serial_starts", {})
    COMPONENT_SPACING = config.get("component_spacing", 1)
    SHOW_SOURCE_URL = config.get("show_source_url", False)


    print("OSS Attribution Generator")
    print("=" * 40)
    return_code = 0
    try:
        # Initialize the generator with configuration
        generator = AttributionGenerator(
            LICENSE_CONFIG, TEMPLATE_CONFIG,
            PROJECT_NAME, COPYRIGHT_HOLDER_FULL, COPYRIGHT_HOLDER_SHORT,
            license_serial_starts=LICENSE_SERIAL_STARTS,
            component_spacing=COMPONENT_SPACING,
            show_source_url=SHOW_SOURCE_URL,
            alias_config=ALIAS_CONFIG
        )

        # Load components — two paths depending on --from-inputs flag
        if use_inputs_dir:
            component_list = select_and_load_inputs_excel()
            if component_list is None:
                return 1
        else:
            if not Path(INPUT_FILE).exists():
                print(f"❌ Error: Input file '{INPUT_FILE}' not found.")
                return 1
            print(f"📖 Reading components from: {INPUT_FILE}")
            component_list = generator.load_components(INPUT_FILE)

        raw_count = len(component_list)

        if not component_list:
            print("ℹ️ No components loaded.")
            print("\n🎉 Done!")
            return 0

        print(f"✅ Loaded {raw_count} components.")

        # Deduplicate (all fields identical = duplicate)
        component_list = generator.deduplicate_components(component_list)
        dedup_count = len(component_list)

        # Pre-flight: resolve unknown licenses interactively before generating
        preflight_check(generator, component_list)

        # Risk warning: flag medium/high-risk licenses before generating
        check_license_risks(generator, component_list)

        # ── Helper: write attribution text to file ──────────────────────────
        def _write_attribution(comps):
            text = generator.generate_attribution(comps)
            Path(OUTPUT_FILE).write_text(text, encoding='utf-8')

        # Generate attribution file
        print(f"\n🔨 Generating attribution file to: {OUTPUT_FILE}")
        _write_attribution(component_list)
        print(f"✅ Attribution file generated: {Path(OUTPUT_FILE).resolve()}")

        # Safety net: licenses still missing after generation
        # (e.g. UNSPECIFIED_LICENSE or edge cases not caught by preflight)
        missing = set(generator.license_manager.missing_licenses)
        if missing:
            print(f"\n⚠️  以下 {len(missing)} 个许可证文本在生成过程中仍未找到，请逐一补充:")
            lm = generator.license_manager
            for lic_id in sorted(missing):
                print(f"\n── '{lic_id}' ──")
                _prompt_license_text(lm, lic_id)

            print(f"\n🔄 重新生成归属文件（已补充许可证文本）...")
            lm.missing_licenses.clear()
            _write_attribution(component_list)
            still_missing = set(lm.missing_licenses)
            if still_missing:
                print(f"⚠️  仍有 {len(still_missing)} 个许可证文本缺失（已写入占位符）: {sorted(still_missing)}")
            else:
                print(f"✅ 重新生成完成: {Path(OUTPUT_FILE).resolve()}")

        # ── Final summary ────────────────────────────────────────────────────
        from collections import Counter
        lm = generator.license_manager
        license_counts: Counter = Counter()
        for comp in component_list:
            raw_expr = comp.license if comp.license and comp.license.strip() else "UNSPECIFIED_LICENSE"
            display_expr = lm.normalize_expression(raw_expr)
            license_counts[display_expr] += 1

        removed_count = raw_count - dedup_count
        print(f"\n{'='*44}")
        print(f"📊 生成摘要")
        print(f"{'='*44}")
        print(f"  输入组件数:   {raw_count}")
        if removed_count:
            print(f"  去重后数量:   {dedup_count}  （移除 {removed_count} 个重复）")
        else:
            print(f"  去重后数量:   {dedup_count}  （无重复）")
        print(f"  许可证种类:   {len(license_counts)} 种")
        for lic_expr, count in sorted(license_counts.items(), key=lambda x: x[0].lower()):
            print(f"    • {lic_expr}: {count} 个组件")
        print(f"{'='*44}")

        print("\n🎉 Done!")
        
    except FileNotFoundError as e: 
        print(f"❌ File not found: {e}")
        return_code = 1
    except ValueError as e: 
        print(f"❌ Data error: {e}")
        return_code = 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return_code = 1
    return return_code

if __name__ == "__main__":
    exit(main())