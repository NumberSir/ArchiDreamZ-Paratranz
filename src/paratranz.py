import contextlib
import os
import shutil
from pathlib import Path
from zipfile import ZipFile

import httpx

from src.config import settings
from src.log import logger


class Paratranz:
    def __init__(self, client: httpx.Client):
        logger.info("======= PARATRANZ START =======")
        self._client = client
        self._base_url = "https://paratranz.cn/api"
        self._headers = {"Authorization": settings.paratranz.token}
        self._project_id = settings.paratranz.project_id

        # self._paratranz_client = ParatranzClient(
        #     Configuration(
        #         host=self.base_url,
        #         api_key={"Token": settings.paratranz.token},
        #     )
        # )

    # def upload(self):
    #     logger.info("Starting uploading files from Paratranz...")
    #     files = self._get_files()
    # 
    #     filepaths = [Path(_["name"]) for _ in files]
    #     fileids = [_["id"] for _ in files]
    #     filepairs = dict(zip(filepaths, fileids))
    # 
    #     for root, dirs, files in os.walk(settings.filepath.root / settings.filepath.converted):
    #         for file in files:
    #             filepath = Path(root) / file
    #             relative_path = filepath.relative_to(settings.filepath.root / settings.filepath.converted)
    # 
    #             with open(filepath, "r") as fp:
    #                 file_data = fp.read()
    # 
    #             if relative_path in filepaths:  # update
    #                 logger.info(f"Updating file: {relative_path}")
    #                 self._update_file(file=file_data, fileid=filepairs[relative_path])
    #             else:                           # create
    #                 logger.info(f"Creating file: {relative_path}")
    #                 self._create_file(file=file_data, path=relative_path)
    #     logger.info("Upload completes.")

    # def _get_files(self) -> list[dict]:
    #     response = FilesApi(self.paratranz_client).get_files(self.project_id)
    #     return response

    def _update_file(self, file: str, fileid: int):
        url = f"{self.base_url}/projects/{self.project_id}/files/{fileid}"
        headers = {**self.headers, 'Content-Type': 'multipart/form-data'}
        data = {"file": bytearray(file, "utf-8")}
        response = self.client.post(url, headers=headers, data=data)
        logger.debug(response.url)
        logger.info(f"file updated: {response.json()}")

    def _create_file(self, file: str, path: Path):
        url = f"{self.base_url}/projects/{self.project_id}/files"
        headers = {**self.headers, 'Content-Type': 'multipart/form-data'}
        data = {"file": bytearray(file, "utf-8"), "path": path.__str__()}
        response = self.client.post(url, headers=headers, data=data)
        logger.info(f"file created: {response.json()}")

    def download(self):
        logger.info("Starting downloading files from Paratranz...")
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
        content = (self.client.get(url, headers=self.headers, follow_redirects=True)).content
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
