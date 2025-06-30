import contextlib
import os
import shutil
from pathlib import Path
from zipfile import ZipFile

import httpx

from src.config import settings
from src.log import logger


class Paratranz:
    def __init__(self, client: httpx.Client = httpx.Client()):
        logger.info("")
        logger.info("======= PARATRANZ START =======")
        self._client = client
        self._base_url = "https://paratranz.cn/api"
        self._headers = {"Authorization": settings.paratranz.token}
        self._project_id = settings.paratranz.project_id

    def get_files(self) -> list:
        url = f"{self.base_url}/projects/{self.project_id}/files"
        response = self.client.get(url, headers=self.headers)
        return response.json()

    def update_file(self, file: Path | str, fileid: int):
        """
        :param file: 文件在本地的路径
        :param fileid: 唯一标识符
        """
        file = file.__str__() if isinstance(file, Path) else file

        url = f"{self.base_url}/projects/{self.project_id}/files/{fileid}"
        headers = {**self.headers, 'Content-Type': 'multipart/form-data'}
        data = {"file": file}
        response = self.client.post(url, headers=headers, data=data)
        logger.bind(filepath=response.json()).success("Updated file successfully")

    def create_file(self, file: Path, path: Path | str):
        """
        :param file: 文件在本地的路径
        :param path: 文件在平台上的路径
        """
        path = path.__str__() if isinstance(path, Path) else path

        url = f"{self.base_url}/projects/{self.project_id}/files"
        headers = {**self.headers, 'Content-Type': 'multipart/form-data'}
        data = {"path": path}
        files = {file.name: open(file, "rb")}
        response = self.client.post(url, headers=headers, files=files, data=data)
        logger.bind(filepath=response.json()).success("Created file successfully")

    def download(self):
        logger.info("Starting to download translated files...")
        os.makedirs(settings.filepath.root / settings.filepath.tmp, exist_ok=True)
        os.makedirs(settings.filepath.root / settings.filepath.download, exist_ok=True)
        with contextlib.suppress(httpx.TimeoutException):
            self._trigger_export()
        self._download_artifacts()
        self._extract_artifacts()
        logger.success("Download completes.")

    def _trigger_export(self):
        url = f"{self.base_url}/projects/{self.project_id}/artifacts"
        self.client.post(url, headers=self.headers)

    def _download_artifacts(self):
        url = f"{self.base_url}/projects/{self.project_id}/artifacts/download"
        try:
            content = (self.client.get(url, headers=self.headers, follow_redirects=True)).content
        except httpx.ConnectError as e:
            logger.error(f"Error downloading artifacts: {e}")
            raise
        with open(settings.filepath.root / settings.filepath.tmp / "paratranz_export.zip", "wb") as fp:
            fp.write(content)

    def _extract_artifacts(self):
        with ZipFile(settings.filepath.root / settings.filepath.tmp / "paratranz_export.zip") as zfp:
            zfp.extractall(settings.filepath.root / settings.filepath.tmp)

        shutil.copytree(
            settings.filepath.root / settings.filepath.tmp / "utf8",
            settings.filepath.root / settings.filepath.download,
            dirs_exist_ok=True
        )

    @property
    def client(self) -> httpx.Client:
        return self._client

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def headers(self) -> dict:
        return self._headers

    @property
    def project_id(self) -> int:
        return self._project_id

    # @property
    # def paratranz_client(self) -> ParatranzClient:
    #     return self._paratranz_client


__all__ = [
    'Paratranz'
]
