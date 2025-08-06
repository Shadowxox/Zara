import yaml
import dotenv
from pathlib import Path

# Determine config directory
config_dir = Path(__file__).parent.parent.resolve() / "config"

# Load YAML config
with open(config_dir / "config.yml", 'r') as f:
    config_yaml = yaml.safe_load(f)

# Load .env config
config_env = dotenv.dotenv_values(config_dir / "config.env")

# Bot settings
telegram_token = config_yaml["telegram_token"]
openai_api_key = config_yaml["openai_api_key"]
openai_api_base = config_yaml.get("openai_api_base", None)
enable_message_streaming = config_yaml.get("enable_message_streaming", True)
return_n_generated_images = config_yaml.get("return_n_generated_images", 1)
image_size = config_yaml.get("image_size", "512x512")
mongodb_uri = f"mongodb://mongo:{config_env['MONGODB_PORT']}"

# Load chat modes (Zara only)
with open(config_dir / "chat_modes.yml", 'r') as f:
    chat_modes = yaml.safe_load(f)

# Load models
with open(config_dir / "models.yml", 'r') as f:
    models = yaml.safe_load(f)
