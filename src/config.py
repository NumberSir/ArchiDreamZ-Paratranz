from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class ProjectSettings(BaseSettings):
    """About this project"""
    model_config = SettingsConfigDict(env_prefix="PROJECT_")

    name: str = Field(default="ArchiDreamZ-Paratranz")
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="<g>{time:HH:mm:ss}</g> | [<lvl>{level:^7}</lvl>] | {extra[project_name]}{message:<35}{extra[filepath]}")
    language: str = Field(default="zh_cn")


class FilepathSettings(BaseSettings):
    """About files / directories"""
    model_config = SettingsConfigDict(env_prefix="PATH_")

    root: Path = Field(default=Path(__file__).parent.parent)
    data: Path = Field(default=Path("data"))
    resource: Path = Field(default=Path("resource"))
    tmp: Path = Field(default=Path("resource/tmp"))
    source: Path = Field(default=Path("resource/1-SourceFile"))
    converted: Path = Field(default=Path("resource/2-ConvertedParatranzFile"))
    download: Path = Field(default=Path("resource/3-TranslatedParatranzFile"))
    result: Path = Field(default=Path("resource/4-SourceTranslatedFile"))
    repo: Path = Field(default=Path("repositories"))  # hard coded


class GitHubSettings(BaseSettings):
    """About GitHub"""
    model_config = SettingsConfigDict(env_prefix='GITHUB_')

    access_token: str = Field(default="")


class ParatranzSettings(BaseSettings):
    """About Paratranz"""
    model_config = SettingsConfigDict(env_prefix='PARATRANZ_')

    project_id: int = Field(default="")
    token: str = Field(default="")


class HuijiWikiSettings(BaseSettings):
    """About HuijiWiki"""
    model_config = SettingsConfigDict(env_prefix='HUIJI_')

    username: str = Field(default="")
    userid: str = Field(default="")
    token: str = Field(default="")


class Settings(BaseSettings):
    """Main settings"""
    github: GitHubSettings = GitHubSettings()
    project: ProjectSettings = ProjectSettings()
    filepath: FilepathSettings = FilepathSettings()

    huijiwiki: HuijiWikiSettings = HuijiWikiSettings()
    paratranz: ParatranzSettings = ParatranzSettings()


settings = Settings()

__all__ = [
    "Settings",
    "settings",
]

if __name__ == '__main__':
    from pprint import pprint

    pprint(Settings().model_dump())
