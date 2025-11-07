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
from pathlib import Path
import yaml
import datetime
# Add src directory to Python path to allow importing from the package
sys.path.insert(0, str(Path(__file__).parent / "src"))
from attribution_generator.generator import AttributionGenerator

def main():
    """
    Main entry point for the Attribution Generator.
    
    This function:
    1. Sets up global project configuration
    2. Initializes the AttributionGenerator
    3. Loads components from input file
    4. Generates attribution file
    5. Handles errors and provides user feedback
    
    Command line usage:
        python main.py [input_file] [output_file]
    
    Returns:
        int: 0 for success, 1 for failure
    """
    # --- Global Configuration ---
    # These values are used in the generated attribution file
    CONFIG_FILE = "project_config.yaml"
    if not Path(CONFIG_FILE).exists():
        print(f"❌ Error: Config file '{CONFIG_FILE}' not found.")
        return 1
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    PROJECT_NAME = config.get("project_name", "Unknown Project")
    COPYRIGHT_HOLDER_FULL = config.get("copyright_holder_full", "")
    COPYRIGHT_HOLDER_SHORT = config.get("copyright_holder_short", "")
    
    # Handle command line arguments or use config defaults
    if len(sys.argv) >= 2:
        INPUT_FILE = sys.argv[1]
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
            show_source_url=SHOW_SOURCE_URL
        )
        
        # Check if input file exists
        if not Path(INPUT_FILE).exists():
            print(f"❌ Error: Input file '{INPUT_FILE}' not found.")
            return 1 
            
        # Load components from input file
        print(f"📖 Reading components from: {INPUT_FILE}")
        component_list = generator.load_components(INPUT_FILE) 
        
        # Report on loaded components
        if not component_list:
            print("ℹ️ No components loaded.")
        else:
            print(f"✅ Loaded {len(component_list)} components.")
            # Group and display components by license
            grouped = generator.group_by_license(component_list)
            print("\n📊 Components by license expression:")
            if grouped:
                for license_expr, comps in sorted(grouped.items(), key=lambda x: x[0].lower()): 
                    print(f"  • \"{license_expr}\": {len(comps)} component(s)")
            else:
                print("  No components to summarize.")
                
        # Generate attribution file
        print(f"\n🔨 Generating attribution file to: {OUTPUT_FILE}")
        generator.generate_from_file(input_file=INPUT_FILE, output_file=OUTPUT_FILE)
        print(f"✅ Attribution file generated: {Path(OUTPUT_FILE).resolve()}")
        # 输出未找到的license
        missing = set(generator.license_manager.missing_licenses)
        if missing:
            print("\n⚠️ The following license(s) were referenced but not found in licenses.yaml:")
            for lic in sorted(missing):
                print(f"  - {lic}")
            print("请补充完整这些license的文本到licenses.yaml后再生成归属文件。\n")
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