import json
import os
from datetime import datetime
from enum import Enum, auto
from urllib.parse import unquote

from loguru._logger import Logger
from pydantic import BaseModel, Field, field_serializer
from selenium import webdriver
from selenium.webdriver.common.by import By

from src.config import settings
from src.log import logger


class ParatranzTermPos(Enum):
    NOUN = auto()
    VERB = auto()
    ADJ = auto()
    ADV = auto()

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return self.name.lower()


class ParatranzModel(BaseModel, extra="allow"):
    """String Item"""
    key: str
    original: str
    translation: str
    context: str = Field(default="")


class ParatranzTermModel(BaseModel, extra="allow"):
    """Terms"""
    id: int | None = Field(default=None)
    createdAt: datetime | None = Field(default=None)
    updatedAt: datetime | None = Field(default=None)
    """最后修改用户的ID"""
    updatedBy: int | None = Field(default=None)
    """创建用户的ID"""
    uid: int | None = Field(default=None)
    """术语注释"""
    note: str | None = Field(default=None)
    """术语所属项目ID"""
    project: int | None = Field(default=None)

    """术语词性"""
    pos: ParatranzTermPos = Field(default=ParatranzTermPos.NOUN)
    """术语原文"""
    term: str = Field(default="")
    """术语译文"""
    translation: str = Field(default="")
    """术语原文的其他形式"""
    variants: list[str] = Field(default_factory=list)
    """术语匹配时是否大小写敏感"""
    caseSensitive: bool = Field(default=False)

    @field_serializer("pos")
    def serialize_pos(self, pos: ParatranzTermPos):
        return str(pos)


class TableModel(BaseModel, extra="allow"):
    original: str
    original_ascii: str
    translation: str
    description: str


class LoTRWiki:
    def __init__(self, driver: webdriver):
        self._project_name = "LoTRWiki"
        self._driver = driver
        self._logger = logger.bind(project_name=self.project_name)
        self.logger.info("===== LoTRWiki Start =====")

        os.makedirs(settings.filepath.root / settings.filepath.resource / self.project_name, exist_ok=True)

    def get_target_urls(self) -> dict[str, str]:
        url = "https://lotr.huijiwiki.com/wiki/模板:译名表目录"
        self.driver.get(url)
        self.driver.add_cookie({'name': 'huijiUserName', 'value': settings.huijiwiki.username})
        self.driver.add_cookie({'name': 'huijiUserID', 'value': settings.huijiwiki.userid})
        self.driver.add_cookie({'name': 'huijiToken', 'value': settings.huijiwiki.token})
        self.logger.debug("cookie set")
        self.driver.refresh()
        self.logger.debug("page refreshed")

        table_url_elements = self.driver.find_elements(By.XPATH, '//a[contains(@title, "译名表/")]')
        self.logger.success(f"{len(table_url_elements)} target urls in total.")
        return {
            element.get_attribute('title'): element.get_attribute('href')
            for element in table_url_elements
        }

    def get_data(self, urls: dict[str, str]) -> list[TableModel]:
        datas: list[TableModel] = []
        for url in urls.values():
            data = self._get_each_data(url)
            data = [
                TableModel(
                    original=original.text.strip(),
                    original_ascii=original_ascii.text.strip(),
                    translation=translation.text.strip(),
                    description=description.text.strip(),
                )
                for original, original_ascii, translation, description in data
                if original.text.strip() != "原名"  # title row, dont need
            ]
            datas.extend(data)

        self.logger.success(f"{len(datas)} elements in total.")
        return datas

    def _get_each_data(self, url: str) -> zip | None:
        self.driver.implicitly_wait(1)
        self.driver.get(url)
        original_name_elements = self.driver.find_elements(By.XPATH, '//tr/td[1]')
        original_name_ascii_elements = self.driver.find_elements(By.XPATH, '//tr/td[2]')
        translation_name_elements = self.driver.find_elements(By.XPATH, '//tr/td[3]')
        description_elements = self.driver.find_elements(By.XPATH, '//tr/td[4]')
        self.logger.success(f"{len(original_name_elements)} elements for {unquote(url.split('/wiki/')[-1])}")
        return zip(
            original_name_elements,
            original_name_ascii_elements,
            translation_name_elements,
            description_elements,
        )

    def process_paratranz_models(self, datas: list[TableModel]) -> list[ParatranzModel]:
        mappings: dict[str, TableModel] = {data.original: data for data in datas}
        result_models = self._process_generate_results(mappings)

        with open(settings.filepath.root / settings.filepath.resource / self.project_name / "translations.json", "w", encoding="utf-8") as fp:
            json.dump([_.model_dump(exclude_unset=True) for _ in result_models], fp=fp, indent=4, ensure_ascii=False)
        self.logger.success(f"Result saved, {len(result_models)} elements in total.")
        return result_models

    def _process_generate_results(self, mappings: dict[str, TableModel]) -> list[ParatranzModel]:
        result_models: list[ParatranzModel] = []
        for original, data in mappings.items():
            result_model = ParatranzModel(
                key=original.replace(" ", "_"),
                original=original,
                translation=data.translation,
                context=data.description,
            )
            alt_model = None
            if data.original_ascii != original:
                alt_model = ParatranzModel(
                    key=data.original_ascii.replace(" ", "_"),
                    original=data.original_ascii,
                    translation=data.translation,
                    context=data.description,
                )
            result_models.extend([result_model, alt_model])
        return [_ for _ in result_models if _ is not None]

    @property
    def project_name(self) -> str:
        return self._project_name

    @property
    def driver(self) -> webdriver:
        return self._driver

    @property
    def logger(self) -> Logger:
        return self._logger


__all__ = [
    "LoTRWiki",
]
