import asyncio
import json

import paratranz_client
from selenium import webdriver

from src.config import settings
from src.huijiwiki import LoTRWiki
from src.log import logger


async def main(force: bool = False):
    with webdriver.Edge() as driver:
        wiki = LoTRWiki(driver)

        filepath = settings.filepath.root / settings.filepath.resource / wiki.project_name / "translations.json"
        if filepath.exists() and not force:
            with filepath.open("r", encoding="utf-8") as fp:
                results = json.load(fp)
        else:
            urls = wiki.get_target_urls()
            datas = wiki.get_data(urls)
            results = wiki.process_paratranz_models(datas)

    configuration = paratranz_client.Configuration(host="https://paratranz.cn/api")
    configuration.api_key["Token"] = settings.paratranz.token
    async with paratranz_client.ApiClient(configuration) as api_client:
        files_api = paratranz_client.FilesApi(api_client)
        files_response = await files_api.get_files(settings.paratranz.project_id)
        if fileid := [file for file in files_response if file.name == "translations.json"]:
            await files_api.delete_file(
                project_id=settings.paratranz.project_id,
                file_id=fileid[0].id,
            )
            logger.success("Delete file successfully")

        file_response = await files_api.create_file(
            project_id=settings.paratranz.project_id,
            file=filepath.__str__(),
        )
        fileid = [file_response.file]
        logger.success("Created file successfully")

        await files_api.update_file_translation(
            project_id=settings.paratranz.project_id,
            file_id=fileid[0].id,
            file=filepath.__str__()
        )
        logger.success("Updated translation successfully")


if __name__ == '__main__':
    asyncio.run(main())
