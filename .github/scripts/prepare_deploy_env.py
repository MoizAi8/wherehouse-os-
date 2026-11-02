"""Encode selected CI settings as literal Compose dotenv values, never shell code."""
import base64
import os
import re


def encode_settings(environ: dict[str, str]) -> str:
    values = {key[4:]: value for key, value in environ.items() if key.startswith("CFG_") and value}
    required = ("POSTGRES_PASSWORD", "JWT_SECRET", "WEBHOOK_SECRET", "INTEGRATION_SECRET_KEY",
                "DOMAIN", "FRONTEND_URL")
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise ValueError("Missing deployment settings: " + ", ".join(missing))
    if re.search(r"[^A-Za-z0-9._~-]", values["POSTGRES_PASSWORD"]):
        raise ValueError("POSTGRES_PASSWORD must use URL-safe characters for the Compose database URL")
    lines = []
    for key, value in values.items():
        if any(char in value for char in ("\n", "\r", "\x00", "'", "\\")):
            raise ValueError(f"Unsupported dotenv characters in {key}; provision this value securely on host")
        lines.append(f"{key}='{value}'")
    return base64.b64encode(("\n".join(lines) + "\n").encode()).decode()


if __name__ == "__main__":
    if not os.environ.get("CFG_OPENAI_API_KEY"):
        print("External AI and embeddings are unconfigured; core application only. No provider requests will be enabled.")
    encoded = encode_settings(dict(os.environ))
    print(f"::add-mask::{encoded}")
    with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as target:
        target.write(f"CONFIG_B64={encoded}\n")
