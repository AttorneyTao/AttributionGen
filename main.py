#!/usr/bin/env python3
"""
Open Source Software Attribution Generator

A tool to generate attribution files for open source software dependencies,
with enhanced support for license expressions, "others" URLs, global project
configuration, and component modification details.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))
from attribution_generator.generator import AttributionGenerator

def main():
    """
    Main entry point for the Attribution Generator.
    Handles configuration, component loading, and attribution file generation.
    Returns:
        int: 0 for success, 1 for failure
    """
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
