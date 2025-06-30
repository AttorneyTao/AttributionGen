import yaml
from pathlib import Path

CONFIG_FILE = "project_config.yaml"

def reset_license_serial_starts(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if "license_serial_starts" in config and isinstance(config["license_serial_starts"], dict):
        for key in config["license_serial_starts"]:
            config["license_serial_starts"][key] = 1
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, sort_keys=False)
        print("✅ license_serial_starts 已全部重置为 1")
    else:
        print("⚠️ 未找到 license_serial_starts 字段或格式不正确")

if __name__ == "__main__":
    reset_license_serial_starts(CONFIG_FILE)