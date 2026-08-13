import os
from pathlib import Path

from boukensha.config import Config
from boukensha.tasks.player import Player

# Override the config directory so the example works from the repo root.
# In real usage a user's ~/.boukensha is picked up automatically.
os.environ.setdefault(
    "BOUKENSHA_DIR",
    str(Path(__file__).resolve().parents[4] / ".boukensha"),
)

config = Config()
player_settings = config.tasks("player")

print("=== Boukensha Step 0: Configuration ===")
print()
print(f"Config dir:     {config.dir}")
print(f"Tasks:          {', '.join(config.tasks())}")
print()
print("-- player task --")
print(f"Provider:       {Player.provider(player_settings)}")
print(f"Model:          {Player.model(player_settings)}")
print(f"Prompt override?{Player.prompt_override(player_settings, 'system')}")
system_prompt = Player.system_prompt(
    player_settings,
    user_prompts_dir=config.user_prompts_dir(),
    default_prompts_dir=Config.PROMPTS_DIR,
)
preview = (system_prompt[:60] if system_prompt else "") + "..."
print(f"System prompt:  {preview}")
print()
print(f"MUD host:       {config.mud_host()}:{config.mud_port()}")
print(f"MUD user:       {config.mud_username()}")
print()
print(f"API key set?    {os.environ.get('ANTHROPIC_API_KEY') is not None}")
print()
print(config)
