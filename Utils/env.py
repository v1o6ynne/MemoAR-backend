import os


def get_env_key(key_name: str) -> str:
    value = os.environ.get(key_name)
    if not value:
        raise EnvironmentError(f"{key_name} not found in environment")
    return value
