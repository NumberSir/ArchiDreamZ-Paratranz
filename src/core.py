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
DIR_TRANSLATION = settings.file.root / settings.file.source / "translation"


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
    PLAINTEXT = auto()

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
        filepath_str = str(filepath)
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
                if "lore" in filepath_str:
                    return FileType.PLAINTEXT
                return FileType.PLAINTEXT_IN_LINES
            case _:
                pass

        """ special """
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

        if translation_flag := (DIR_TRANSLATION / filepath.parent / "zh_CN.lang").exists():
            with open(DIR_TRANSLATION / filepath.parent / "zh_CN.lang", "r", encoding="utf-8") as fp:
                lines_translation = fp.readlines()

        result = []
        for idx, line in enumerate(lines):
            line = line.strip()
            if not line:  # blank
                key = f"BLANK-{idx}"
                value = line

            elif "=" not in line:  # comment / misc
                key = f"COMMENT-{idx}" if line.startswith("#") else f"MISC-{idx}"
                value = line

            else:   #normal
                key, value = line.split("=", 1)

            data = Data(
                key=key,
                original=value,
                translation="",
                context=f"{idx}"
            )

            if reference_flag:
                for line_ in lines_reference:
                    if line_.startswith(f"{key}="):
                        data.context = f"{data.context}\n{line_.split('=', 1)[1]}"
                        break

            if translation_flag:
                for line_ in lines_translation:
                    if line_.startswith(f"{key}="):
                        data.translation = f"{line_.split('=', 1)[1].strip()}"
                        break

            result.append(data)

        # some keys not exist in original but do exist in translation
        if translation_flag:
            for line_ in lines_translation:
                if "=" not in line_:
                    continue
                newkey, newvalue = line_.split("=", 1)
                if newkey in {_.key for _ in result}:
                    continue

                data = Data(
                    key=newkey,
                    original="MISSING",
                    translation=newvalue,
                    context="Additional in translation"
                )

                if reference_flag:
                    for line_r in lines_reference:
                        if line_r.startswith(f"{newkey}="):
                            data.context = f"{data.context}\n{line_r.split('=', 1)[1]}"
                            break

                result.append(data)

        return result

    def _convert_json_lang(self, filepath: Path) -> list[Data]:
        """late versions"""
        with open(DIR_ORIGINAL / filepath, "r", encoding="utf-8") as fp:
            content = json.load(fp)

        if reference_flag := (DIR_REFERENCE / filepath.parent / "en_us.json").exists():
            with open(DIR_REFERENCE / filepath.parent / "en_us.json", "r", encoding="utf-8") as fp:
                content_reference = json.load(fp)

        if translation_flag := (DIR_TRANSLATION / filepath.parent / "zh_cn.json").exists():
            with open(DIR_TRANSLATION / filepath.parent / "zh_cn.json", "r", encoding="utf-8") as fp:
                content_translation = json.load(fp)

        result = []
        for key, value in content.items():
            data = Data(
                key=key,
                original=value,
                translation="",
            )
            if reference_flag:
                data.context = content_reference.get(key, "Not exist in reference")
            if translation_flag:
                data.translation = content_translation.get(key, "")
            result.append(data)
        return result

    def _convert_misc(self, filepath: Path, type_: FileType) -> list[Data]:
        """plaintext, generally"""
        match type_:
            case FileType.PLAINTEXT:
                return self._convert_misc_plaintext(filepath)
            case FileType.PLAINTEXT_IN_LINES:
                return self._convert_misc_plaintext_in_lines(filepath)
            case FileType.CUSTOM_NPCS_DIALOGS:
                return self._convert_misc_customnpcs_dialog(filepath)
            case FileType.CUSTOM_NPCS_QUESTS:
                return self._convert_misc_customnpcs_quests(filepath)
            case _:
                raise Exception(f"Unknown file type when convert: {filepath}")

    def _convert_misc_plaintext(self, filepath: Path) -> list[Data]:
        """plaintext, whole file"""
        with open(DIR_ORIGINAL / filepath, "r", encoding="utf-8") as fp:
            content = fp.read()

        if reference_flag := (DIR_REFERENCE / filepath).exists():
            with open(DIR_REFERENCE / filepath, "r", encoding="utf-8") as fp:
                content_reference = fp.read()

        if translation_flag := (DIR_TRANSLATION / filepath).exists():
            with open(DIR_TRANSLATION / filepath, "r", encoding="utf-8") as fp:
                content_translation = fp.read()

        data = Data(
            key=f"{filepath.with_suffix('').name}",
            original=content,
            translation=""
        )
        if reference_flag:
            data.context = content_reference
        if translation_flag:
            data.translation = content_translation
        return [data]

    def _convert_misc_plaintext_in_lines(self, filepath: Path) -> list[Data]:
        """plaintext, split in lines"""
        with open(DIR_ORIGINAL / filepath, "r", encoding="utf-8") as fp:
            lines = fp.readlines()

        if reference_flag := (DIR_REFERENCE / filepath).exists():
            with open(DIR_REFERENCE / filepath, "r", encoding="utf-8") as fp:
                lines_reference = fp.readlines()

            if len(lines) != len(lines_reference):
                # logger.warning(f"reference not compatible: {filepath}")
                reference_flag = False

        if translation_flag := (DIR_TRANSLATION / filepath).exists():
            with open(DIR_TRANSLATION / filepath, "r", encoding="utf-8") as fp:
                lines_translation = fp.readlines()

            if len(lines) != len(lines_translation):
                # logger.warning(f"translation not compatible: {filepath}")
                translation_flag = False

        result = []
        for idx, line in enumerate(lines):
            key = f"{idx}"
            if not line.strip():
                key = f"BLANK-{key}"

            data = Data(
                key=key,
                original=line,
                translation=""
            )
            if reference_flag:
                data.context = lines_reference[idx]
            if translation_flag:
                data.translation = lines_translation[idx]
            result.append(data)
        return result

    def _convert_misc_customnpcs_dialog(self, filepath: Path) -> list[Data]:
        with open(DIR_ORIGINAL / filepath, "r", encoding="utf-8") as fp:
            content = fp.read()

        option_slots = re.findall(r'\"OptionSlot\": (\d+),*\n', content)
        option_titles = re.findall(r'\"Title\": \"([\s\S]*?)\",*\n', content)
        dialog_text = re.findall(r'\"DialogText\": \"([\s\S]*?)\",*\n', content)

        fetch = {
            "dialogtext": dialog_text[0] if dialog_text else "",
            **dict(zip(option_slots, option_titles)),
        }

        if translation_flag := (DIR_TRANSLATION / filepath).exists():
            with open(DIR_TRANSLATION / filepath, "r", encoding="utf-8") as fp:
                content_translation = fp.read()

            option_slots_translation = re.findall(r'\"OptionSlot\": (\d+),*\n', content_translation)
            option_titles_translation = re.findall(r'\"Title\": \"([\s\S]*?)\",*\n', content_translation)
            dialog_text_translation = re.findall(r'\"DialogText\": \"([\s\S]*?)\",*\n', content_translation)

            fetch_translation = {
                "dialogtext": dialog_text_translation[0] if dialog_text_translation else "",
                **dict(zip(option_slots_translation, option_titles_translation)),
            }

        result = []
        for key, value in fetch.items():
            data = Data(
                key=key,
                original=value,
                translation="",
            )
            if translation_flag:
                data.translation = fetch_translation.get(key, "")
            result.append(data)
        return result

    def _convert_misc_customnpcs_quests(self, filepath: Path) -> list[Data]:
        with open(DIR_ORIGINAL / filepath, "r", encoding="utf-8") as fp:
            content = fp.read()

        fetch = {
            "text": re.findall(r'\"Text\": \"([\s\S]*?)\",*\n', content)[0],
            "completetext": re.findall(r'\"CompleteText\": \"([\s\S]*?)\",*\n', content)[0],
            "nextquesttitle": re.findall(r'\"NextQuestTitle\": \"([\s\S]*?)\",*\n', content)[0],
        }

        if translation_flag := (DIR_TRANSLATION / filepath).exists():
            with open(DIR_TRANSLATION / filepath, "r", encoding="utf-8") as fp:
                content_translation = fp.read()

            fetch_translation = {
                "title": re.findall(r'\"Title\": \"([\s\S]*?)\",*\n', content_translation)[0],
                "text": re.findall(r'\"Text\": \"([\s\S]*?)\",*\n', content_translation)[0],
                "completetext": re.findall(r'\"CompleteText\": \"([\s\S]*?)\",*\n', content_translation)[0],
                "nextquesttitle": re.findall(r'\"NextQuestTitle\": \"([\s\S]*?)\",*\n', content_translation)[0],
            }

        result = []
        for key, value in fetch.items():
            data = Data(
                key=key,
                original=value,
                translation="",
            )
            if translation_flag:
                data.translation = fetch_translation.get(key, "")
            result.append(data)
        return result

    def restore(self):
        """paratranz jsons to local raw texts"""
        for root, dirs, files in os.walk(settings.file.root / settings.file.download):
            for file in files:
                filepath = Path(root) / file
                relative_path = filepath.relative_to(settings.file.root / settings.file.download)
                relative_path = relative_path.with_suffix("")
                converted_path = relative_path.parent / f"{relative_path.name}.json"
                os.makedirs(settings.file.root / settings.file.result / relative_path.parent, exist_ok=True)

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

        result = []
        for line in content:
            if line["key"].startswith("BLANK"):
                result.append("\n")
                continue

            if line["key"].startswith("COMMENT") or line["key"].startswith("MISC"):
                result.append(line.get("translation", line["original"]).rstrip("\n") + "\n" or line["original"])
                continue

            result.append(
                f"{line['key']}={line['translation']}".rstrip("\n") + "\n"
                if line['translation'] else
                f"{line['key']}={line['original']}".rstrip("\n") + "\n"
            )

        with open(settings.file.root / settings.file.result / filepath.with_suffix(""), "w", encoding="utf-8") as fp:
            fp.writelines(result)

    def _restore_json_lang(self, filepath: Path):
        with open(settings.file.root / settings.file.download / filepath, "r", encoding="utf-8") as fp:
            content = json.load(fp)

        with open(DIR_ORIGINAL / filepath.with_suffix(""), "r", encoding="utf-8") as fp:
            original = json.load(fp)

        for data in content:
            if data["key"] not in original:
                logger.warning(f"File might not be consistent: {filepath.with_suffix('')}")
            original[data["key"]] = data.get("translation", data["original"])

        with open(settings.file.root / settings.file.result / filepath.with_suffix(""), "w", encoding="utf-8") as fp:
            json.dump(original, fp, ensure_ascii=False, indent=2)

    def _restore_misc(self, filepath: Path, type_: FileType):
        """plaintext, generally"""
        match type_:
            case FileType.PLAINTEXT:
                return self._restore_misc_plaintext(filepath)
            case FileType.PLAINTEXT_IN_LINES:
                return self._restore_misc_plaintext_in_lines(filepath)
            case FileType.CUSTOM_NPCS_DIALOGS:
                return self._restore_misc_customnpcs_dialog(filepath)
            case FileType.CUSTOM_NPCS_QUESTS:
                return self._restore_misc_customnpcs_quests(filepath)
            case _:
                raise Exception(f"Unknown file type when restore: {filepath}")

    def _restore_misc_plaintext(self, filepath: Path):
        with open(settings.file.root / settings.file.download / filepath, "r", encoding="utf-8") as fp:
            content = json.load(fp)

        with open(settings.file.root / settings.file.result / filepath.with_suffix(""), "w", encoding="utf-8") as fp:
            fp.write(content[0].get("translation", content[0]["original"]))

    def _restore_misc_plaintext_in_lines(self, filepath: Path):
        with open(settings.file.root / settings.file.download / filepath, "r", encoding="utf-8") as fp:
            content = json.load(fp)

        result = []
        for line in content:
            if line["key"].startswith("BLANK"):
                result.append("\n")
                continue

            result.append(
                line['translation'].rstrip('\n') + "\n"
                if line['translation'] else
                line["original"].rstrip('\n') + "\n"
            )

        with open(settings.file.root / settings.file.result / filepath.with_suffix(""), "w", encoding="utf-8") as fp:
            fp.writelines(result)

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
            [_.get("translation", _["original"]) for _ in content if _["key"] == key][0]
        )
        return (
            f"{original[:title.start()]}"
            f"{processed_line}"
            f"{original[title.end():]}"
        )


__all__ = [
    "Project"
]
