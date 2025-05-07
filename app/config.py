import os

from pydantic_settings import BaseSettings

_CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))

class Settings(BaseSettings):
    # Authentication
    SECRET_KEY: str = "rhrytuejifuhru4577838478f47ty748urujruty478uru4t58y"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 300

    # Application settings
    ECHO: bool = True
    RELOAD: bool = True
    # aws configuration
    AWS_ACCESS_KEY_ID: str = "fhefhedfuefyeudnbfhefhuefuefuygeruf"
    AWS_SECRET_ACCESS_KEY: str = "hefeyfrhiwdhefiheyfhienhyfhefy"
    AWS_DEFAULT_REGION: str = "jednjehfue"
    SENDER_EMAIL: str = "jejfehfu"

    DB_USER: str = "fn7n48dr"
    DB_PASSWORD: str = "fn7n48dr"
    RDS_ENDPOINT: str = "fn7n48dr"
    DB_PORT: int = 5432
    DB_NAME: str = "fn7n48dr"

    class Config:
        env_file = os.path.join(_CONFIG_DIR, ".env")
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
