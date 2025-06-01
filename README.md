# Open Source Software Attribution Generator

[![Built with Cursor](https://img.shields.io/badge/Built%20with-Cursor-2ea44f)](https://cursor.sh)
[![Pylint](https://github.com/yourusername/Attribution_Generator/actions/workflows/pylint.yml/badge.svg)](https://github.com/yourusername/Attribution_Generator/actions/workflows/pylint.yml)

A Python tool to generate attribution files for open source software dependencies, with enhanced support for license expressions, "others" URLs, global project configuration, and component modification details.

This project was built using [Cursor](https://cursor.sh), the world's best IDE for AI-powered development.

## Features

- Generates comprehensive attribution files for open source components
- Supports multiple input formats (Excel, JSON, YAML)
- Handles complex license expressions (AND, OR combinations)
- Supports "others" URLs for additional notices
- Tracks component modifications
- Configurable project settings
- Customizable templates

## Requirements

- Python 3.8+
- uv (Python package installer)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd Attribution_Generator
```

2. Install dependencies using uv:
```bash
uv pip install -e .
```

## Usage

1. Configure your project settings in `main.py`:
```python
PROJECT_NAME = "Your Project Name"
COPYRIGHT_HOLDER_FULL = "Your Full Company Name L.L.C."
COPYRIGHT_HOLDER_SHORT = "YourCo"
```

2. Prepare your components file:
   - Use `components.xlsx` for Excel input
   - Required columns: name, copyright, license
   - Optional columns: version, others_url, modified, modified_url

3. Run the generator:
```bash
python main.py
```

The tool will generate an `ATTRIBUTIONS.txt` file with properly formatted attributions for all components.

## Input File Format

### Excel Format
Required columns:
- name: Component name
- copyright: Copyright notice
- license: License expression

Optional columns:
- version: Component version
- others_url: URL for additional notices
- modified: Whether the component is modified (true/false)
- modified_url: URL to modified code

### JSON/YAML Format
```json
{
  "components": [
    {
      "name": "Component Name",
      "copyright": "Copyright Notice",
      "license": "License Expression",
      "version": "1.0.0",
      "others_url": "https://example.com/notice",
      "modified": false,
      "modified_url": null
    }
  ]
}
```

## Configuration Files

### licenses.yaml
Contains license texts and definitions. Example:
```yaml
MIT: |
  MIT License
  Copyright (c) [year] [fullname]
  ...

OTHERS_DEFINITION: |
  [Default text for components with "others" license]
```

### templates.yaml
Contains templates for different sections of the attribution file. Example:
```yaml
header: |
  Open Source Software Attribution
  Project: {project_name}
  Copyright (c) {copyright_holder_full}
  ...

component_listing: |
  {serial_number}. {name} (v{version})
  {copyright}{modification_notice}
```

## Development

This project uses `pyproject.toml` for dependency management and `uv` as the package installer. The main dependencies are:
- pandas (>=1.5.0)
- PyYAML (>=6.0)
- openpyxl (>=3.0.0)

### Code Quality

The project maintains high code quality standards through:
- Automated Pylint checks on every push
- Testing against Python 3.8, 3.9, and 3.10
- Comprehensive docstrings and type hints
- PEP 8 style compliance

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
