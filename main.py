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
    INPUT_FILE = config.get("input_file", "components.xlsx")
    OUTPUT_FILE = config.get("output_file", "ATTRIBUTIONS.txt")
    LICENSE_CONFIG = config.get("license_config", "licenses.yaml")
    TEMPLATE_CONFIG = config.get("template_config", "templates.yaml")
    LICENSE_SERIAL_STARTS = config.get("license_serial_starts", {})
    COMPONENT_SPACING = config.get("component_spacing", 1)


    print("OSS Attribution Generator")
    print("=" * 40)
    return_code = 0
    try:
        # Initialize the generator with configuration
        generator = AttributionGenerator(
            LICENSE_CONFIG, TEMPLATE_CONFIG,
            PROJECT_NAME, COPYRIGHT_HOLDER_FULL, COPYRIGHT_HOLDER_SHORT,
            license_serial_starts=LICENSE_SERIAL_STARTS,
            component_spacing=COMPONENT_SPACING
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
