import os
import sys
import yaml

# Adjust sys.path to allow imports from the project root directory
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from scrapers.fonte2_scraper import Fonte2Scraper

def main():
    config_path = os.path.join(project_root, "config", "sources.yaml")
    print(f"Loading configuration from: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    fonte2_config = config.get("fonte2", {})
    
    # Run the scraper
    scraper = Fonte2Scraper(fonte2_config)
    scraper.run()

if __name__ == "__main__":
    main()
