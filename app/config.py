from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./blog.db"

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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
