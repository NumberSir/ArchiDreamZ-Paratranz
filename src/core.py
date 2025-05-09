import json
import os
import re
import shutil
from contextlib import suppress
from dataclasses import dataclass, asdict
from enum import Enum, auto
from pathlib import Path

from src.config import settings
from src.log import logger

# from src.libs.openapi_client import ApiClient as ParatranzClient, FilesApi, Configuration

DIR_ORIGINAL = settings.file.root / settings.file.source / "original"
DIR_REFERENCE = settings.file.root / settings.file.source / "reference"


@dataclass
class Data:
    key: str
    original: str
    translation: str
    context: str = ""


class FileType(Enum):
    LANG = auto()
    JSON_LANG = auto()
    PLAINTEXT_IN_LINES = auto()

    CUSTOM_NPCS_DIALOGS = auto()
    CUSTOM_NPCS_QUESTS = auto()


class Project:
    @staticmethod
    def clean(*filepaths: Path):
        for filepath in filepaths:
            with suppress(FileNotFoundError):
                shutil.rmtree(filepath)
            os.makedirs(filepath, exist_ok=True)

    @staticmethod
    def categorize(filepath: Path) -> FileType:
        match filepath.name:
            case "en_US.lang" | "ru_RU.lang" | "zh_CN.lang":
                return FileType.LANG
            case "en_us.json" | "ru_ru.json" | "zh_cn.json":
                return FileType.JSON_LANG
            case _:
                pass

        suffix = filepath.suffix or Path(f" {filepath.name}").suffix
        match suffix:
            case ".lang":
                return FileType.LANG
            case ".txt":
                return FileType.PLAINTEXT_IN_LINES
            case _:
                pass

        """ special """
        filepath_str = str(filepath)
        if "CustomNPCs" in filepath_str:
            if "dialogs" in filepath_str:
                return FileType.CUSTOM_NPCS_DIALOGS
            elif "quests" in filepath_str:
                return FileType.CUSTOM_NPCS_QUESTS

        raise Exception(f"Unknown file type: {filepath}")

    def convert(self):
        """local raw texts to paratranz jsons"""
        for root, dirs, files in os.walk(DIR_ORIGINAL):
            for file in files:
                filepath = Path(root) / file
                relative_path = filepath.relative_to(DIR_ORIGINAL)
                converted_path = relative_path.parent / f"{relative_path.name}.json"
                os.makedirs(settings.file.root / settings.file.converted / relative_path.parent, exist_ok=True)

                file_type = self.categorize(relative_path)
                match file_type:
                    case FileType.LANG:
                        datas = self._convert_lang(relative_path)
                    case FileType.JSON_LANG:
                        datas = self._convert_json_lang(relative_path)
                    case _:
                        datas = self._convert_misc(relative_path, file_type)

                with open(settings.file.root / settings.file.converted / converted_path, "w", encoding="utf-8") as fp:
                    json.dump([asdict(_) for _ in datas], fp, ensure_ascii=False, indent=2)

    def _convert_lang(self, filepath: Path) -> list[Data]:
        """old versions"""
        with open(DIR_ORIGINAL / filepath, "r", encoding="utf-8") as fp:
            lines = fp.readlines()

        if reference_flag := (DIR_REFERENCE / filepath.parent / "en_US.lang").exists():
            with open(DIR_REFERENCE / filepath.parent / "en_US.lang", "r", encoding="utf-8") as fp:
                lines_reference = fp.readlines()

        result = []
        for idx, line in enumerate(lines):
            line = line.strip()
            if not line:  # blank
                continue

            if line.startswith("#"):  # comment
                continue

            if "=" not in line:  # misc
                continue

            key, value = line.split("=", 1)
            data = Data(
                key=key,
                original=value,
                translation="",
                context=f"{idx}"
            )
            if reference_flag:
                for idx_, line_ in enumerate(lines_reference):
                    if not line_.startswith(f"{key}="):
                        continue
                    data.context = f"{data.context}\n{line_.split('=', 1)[1]}"
            result.append(data)

        return result

    def _convert_json_lang(self, filepath: Path) -> list[Data]:
        """late versions"""
        with open(DIR_ORIGINAL / filepath, "r", encoding="utf-8") as fp:
            content = json.load(fp)

        if reference_flag := (DIR_REFERENCE / filepath.parent / "en_us.json").exists():
            with open(DIR_REFERENCE / filepath.parent / "en_us.json", "r", encoding="utf-8") as fp:
                content_reference = json.load(fp)

        return [
            Data(
                key=k,
                original=v,
                translation="",
                context=content_reference[k]
            )
            if reference_flag and k in content_reference
            else Data(
                key=k,
                original=v,
                translation=""
            )
            for k, v in content.items()
        ]

    def _convert_misc(self, filepath: Path, type_: FileType) -> list[Data]:
        """plaintext, generally"""
        match type_:
            case FileType.PLAINTEXT_IN_LINES:
                return self._convert_misc_in_lines(filepath)
            case FileType.CUSTOM_NPCS_DIALOGS:
                return self._convert_misc_customnpcs_dialog(filepath)
            case FileType.CUSTOM_NPCS_QUESTS:
                return self._convert_misc_customnpcs_quests(filepath)
            case _:
                raise Exception(f"Unknown file type when convert: {filepath}")

    def _convert_misc_in_lines(self, filepath: Path) -> list[Data]:
        """plaintext, split in lines"""
        with open(DIR_ORIGINAL / filepath, "r", encoding="utf-8") as fp:
            lines = fp.readlines()

        if reference_flag := (DIR_REFERENCE / filepath).exists():
            with open(DIR_REFERENCE / filepath, "r", encoding="utf-8") as fp:
                lines_reference = fp.readlines()

            if len(lines) != len(lines_reference):
                # logger.warning(f"reference not compatible: {filepath}")
                reference_flag = False

        return [
            Data(
                key=f"{idx}",
                original=line,
                translation="",
                context=lines_reference[idx]
            ) if reference_flag else Data(
                key=f"{idx}",
                original=line,
                translation=""
            ) for idx, line in enumerate(lines)
            if line.strip()
        ]

    def _convert_misc_customnpcs_dialog(self, filepath: Path) -> list[Data]:
        with open(DIR_ORIGINAL / filepath, "r", encoding="utf-8") as fp:
            content = fp.read()

        option_slots = re.findall(r'\"OptionSlot\": (\d+),*\n', content)
        option_titles = re.findall(r'\"Title\": \"([\s\S]*?)\",*\n', content)

        dialog_title = re.findall(r'\"DialogTitle\": \"([\s\S]*?)\",*\n', content)
        dialog_text = re.findall(r'\"DialogText\": \"([\s\S]*?)\",*\n', content)

        data = {
            "dialogtitle": dialog_title[0] if dialog_title else "",
            "dialogtext": dialog_text[0] if dialog_text else "",
            **dict(zip(option_slots, option_titles)),
        }

        return [
            Data(
                key=k,
                original=v,
                translation="",
            ) for k, v in data.items()
        ]

    def _convert_misc_customnpcs_quests(self, filepath: Path) -> list[Data]:
        with open(DIR_ORIGINAL / filepath, "r", encoding="utf-8") as fp:
            content = fp.read()

        data = {
            "title": re.findall(r'\"Title\": \"([\s\S]*?)\",*\n', content)[0],
            "text": re.findall(r'\"Text\": \"([\s\S]*?)\",*\n', content)[0],
            "completetext": re.findall(r'\"CompleteText\": \"([\s\S]*?)\",*\n', content)[0],
            "nextquesttitle": re.findall(r'\"NextQuestTitle\": \"([\s\S]*?)\",*\n', content)[0],
        }

        return [
            Data(
                key=k,
                original=v,
                translation="",
            ) for k, v in data.items()
        ]

    def restore(self):
        """paratranz jsons to local raw texts"""
        for root, dirs, files in os.walk(DIR_ORIGINAL):
            for file in files:
                filepath = Path(root) / file
                relative_path = filepath.relative_to(DIR_ORIGINAL)
                converted_path = relative_path.parent / f"{relative_path.name}.json"
                os.makedirs(settings.file.root / settings.file.converted / relative_path.parent, exist_ok=True)

                file_type = self.categorize(relative_path)

                try:
                    match file_type:
                        case FileType.LANG:
                            self._restore_lang(converted_path)
                        case FileType.JSON_LANG:
                            self._restore_json_lang(converted_path)
                        case _:
                            self._restore_misc(converted_path, file_type)
                except FileNotFoundError as e:
                    logger.error(f'File not exist: {converted_path}')

    def _restore_lang(self, filepath: Path):
        with open(settings.file.root / settings.file.download / filepath, "r", encoding="utf-8") as fp:
            content = json.load(fp)

        with open(DIR_ORIGINAL / filepath.with_suffix(""), "r", encoding="utf-8") as fp:
            original = fp.readlines()

        for line in content:
            idx = line["context"].split("\n")[0]
            if not original[int(idx)].startswith(line["key"]):
                logger.warning(f"File might not be consistent: {filepath.with_suffix('')}")
            original[int(idx)] = f"{line['key']}={line['translation']}".rstrip("\n") + "\n"

        with open(settings.file.root / settings.file.result / filepath.with_suffix(""), "w", encoding="utf-8") as fp:
            fp.writelines(original)

    def _restore_json_lang(self, filepath: Path):
        with open(settings.file.root / settings.file.download / filepath, "r", encoding="utf-8") as fp:
            content = json.load(fp)

        with open(DIR_ORIGINAL / filepath.with_suffix(""), "r", encoding="utf-8") as fp:
            original = json.load(fp)

        for data in content:
            if data["key"] not in original:
                logger.warning(f"File might not be consistent: {filepath.with_suffix('')}")
            original[data["key"]] = data["translation"]

        with open(settings.file.root / settings.file.result / filepath.with_suffix(""), "w", encoding="utf-8") as fp:
            json.dump(original, fp, ensure_ascii=False, indent=2)

    def _restore_misc(self, filepath: Path, type_: FileType):
        """plaintext, generally"""
        match type_:
            case FileType.PLAINTEXT_IN_LINES:
                return self._restore_misc_in_lines(filepath)
            case FileType.CUSTOM_NPCS_DIALOGS:
                return self._restore_misc_customnpcs_dialog(filepath)
            case FileType.CUSTOM_NPCS_QUESTS:
                return self._restore_misc_customnpcs_quests(filepath)
            case _:
                raise Exception(f"Unknown file type when restore: {filepath}")

    def _restore_misc_in_lines(self, filepath: Path):
        with open(settings.file.root / settings.file.download / filepath, "r", encoding="utf-8") as fp:
            content = json.load(fp)

        with open(DIR_ORIGINAL / filepath.with_suffix(""), "r", encoding="utf-8") as fp:
            original = fp.readlines()

        for line in content:
            idx = line["key"]
            if original[int(idx)] != line["original"]:
                logger.warning(f"File might not be consistent: {filepath.with_suffix('')}")
            original[int(idx)] = line['translation'].rstrip('\n') + "\n"

        with open(settings.file.root / settings.file.result / filepath.with_suffix(""), "w", encoding="utf-8") as fp:
            fp.writelines(original)

    def _restore_misc_customnpcs_dialog(self, filepath: Path):
        with open(settings.file.root / settings.file.download / filepath, "r", encoding="utf-8") as fp:
            content = json.load(fp)

        with open(DIR_ORIGINAL / filepath.with_suffix(""), "r", encoding="utf-8") as fp:
            original = fp.read()

        option_titles = list(re.finditer(r'\"Title\": \"([\s\S]*?)\",*\n', content))
        for idx, title in enumerate(option_titles[::-1]):
            processed_line = title.group().replace(
                title.groups()[0],
                [_['translation'] for _ in content if int(_['key']) == len(option_titles) - idx - 1][0]
            )

            original = (
                f"{original[:title.start()]}"
                f"{processed_line}"
                f"{original[title.end():]}"
            )

        for pattern, key in {
            re.compile(r'\"DialogTitle\": \"([\s\S]*?)\",*\n'): "dialogtitle",
            re.compile(r'\"DialogText\": \"([\s\S]*?)\",*\n'): "dialogtext"
        }.items():
            original = self._regex_restore(pattern, content, key, original)

        with open(settings.file.root / settings.file.result / filepath.with_suffix(""), "w", encoding="utf-8") as fp:
            fp.write(original)

    def _restore_misc_customnpcs_quests(self, filepath: Path):
        with open(settings.file.root / settings.file.download / filepath, "r", encoding="utf-8") as fp:
            content = json.load(fp)

        with open(DIR_ORIGINAL / filepath.with_suffix(""), "r", encoding="utf-8") as fp:
            original = fp.read()

        for pattern, key in {
            re.compile(r'\"Title\": \"([\s\S]*?)\",*\n'): "title",
            re.compile(r'\"Text\": \"([\s\S]*?)\",*\n'): "text",
            re.compile(r'\"CompleteText\": \"([\s\S]*?)\",*\n'): "completetext",
            re.compile(r'\"NextQuestTitle\": \"([\s\S]*?)\",*\n'): "nextquesttitle",
        }.items():
            original = self._regex_restore(pattern, content, key, original)

        with open(settings.file.root / settings.file.result / filepath.with_suffix(""), "w", encoding="utf-8") as fp:
            fp.write(original)

    @staticmethod
    def _regex_restore(pattern: re.Pattern, content: list[dict], key: str, original: str):
        title = re.search(pattern, original)
        processed_line = title.group().replace(
            title.groups()[0],
            [_["translation"] for _ in content if _["key"] == key][0]
        )
        return (
            f"{original[:title.start()]}"
            f"{processed_line}"
            f"{original[title.end():]}"
        )


__all__ = [
    "Project"
]
