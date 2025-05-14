import io
import json
import os
import re
import shutil
from contextlib import suppress
from dataclasses import dataclass, asdict
from enum import Enum, auto
from pathlib import Path
from typing import Callable

import chardet

from src.config import settings
from src.log import logger

# from src.libs.openapi_client import ApiClient as ParatranzClient, FilesApi, Configuration

DIR_ORIGINAL = settings.filepath.root / settings.filepath.source / "original"
DIR_REFERENCE = settings.filepath.root / settings.filepath.source / "reference"
DIR_TRANSLATION = settings.filepath.root / settings.filepath.source / "translation"

FileContent = str | list[str] | list | dict


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

    LOTR_RENEWED_SPEECH = auto()


class Conversion:
    def convert(self):
        """local raw texts to paratranz jsons"""
        for root, dirs, files in os.walk(DIR_ORIGINAL):
            for file in files:
                filepath = Path(root) / file
                relative_path = filepath.relative_to(DIR_ORIGINAL)
                converted_path = relative_path.parent / f"{relative_path.name}.json"
                os.makedirs(settings.filepath.root / settings.filepath.converted / relative_path.parent, exist_ok=True)

                file_type = Project.categorize(relative_path)
                match file_type:
                    case FileType.LANG:
                        datas = self._convert_lang(relative_path, file_type)
                    case FileType.JSON_LANG:
                        datas = self._convert_json_lang(relative_path, file_type)
                    case _:
                        datas = self._convert_misc(relative_path, file_type)

                with open(settings.filepath.root / settings.filepath.converted / converted_path, "w", encoding="utf-8") as fp:
                    json.dump([asdict(_) for _ in datas], fp, ensure_ascii=False, indent=2)

    def _convert_general(self, filepath: Path, type_: FileType, process_function: Callable[..., list[Data]], **kwargs) -> list[Data]:
        filepath_original = DIR_ORIGINAL / filepath
        with open(filepath_original, "r", encoding="utf-8") as fp:
            original = Project.read(fp, type_)

        reference = None
        filename_reference: str | None = kwargs.get("filename_reference", None)
        filepath_reference = (DIR_REFERENCE / filepath.parent / filename_reference) if filename_reference else (DIR_REFERENCE / filepath)
        if reference_flag := filepath_reference.exists():
            with open(filepath_reference, "r", encoding="utf-8") as fp:
                reference = Project.read(fp, type_)

        translation = None
        filename_translation: str | None = kwargs.get("filename_translation", None)
        filepath_translation = (DIR_TRANSLATION / filepath.parent / filename_translation) if filename_translation else (DIR_TRANSLATION / filepath)
        if translation_flag := filepath_translation.exists():
            with open(filepath_translation, "r", encoding="utf-8") as fp:
                translation = Project.read(fp, type_)

        return process_function(
            filepath=filepath,
            original=original,
            reference=reference,
            reference_flag=reference_flag,
            translation=translation,
            translation_flag=translation_flag,
            **kwargs
        )

    def _convert_lang(self, filepath: Path, type_: FileType) -> list[Data]:
        """old versions"""
        def _process(**kwargs) -> list[Data]:
            original: list[str] = kwargs["original"]
            reference_flag: bool = kwargs["reference_flag"]
            reference: list[str] = kwargs["reference"]
            translation_flag: bool = kwargs["translation_flag"]
            translation: list[str] = kwargs["translation"]

            result = []
            for idx, line in enumerate(original):
                line = line.strip()
                if not line:  # blank
                    key = f"BLANK-{idx}"
                    value = line

                elif "=" not in line:  # comment / misc
                    key = f"COMMENT-{idx}" if line.startswith("#") else f"MISC-{idx}"
                    value = line

                else:  # normal
                    key, value = line.split("=", 1)

                data = Data(
                    key=key,
                    original=value,
                    translation="",
                    context=f"{idx}"
                )

                if reference_flag:
                    for line_ in reference:
                        if line_.startswith(f"{key}="):
                            data.context = f"{data.context}\n{line_.split('=', 1)[1]}"
                            break

                if translation_flag:
                    for line_ in translation:
                        if line_.startswith(f"{key}="):
                            data.translation = f"{line_.split('=', 1)[1].strip()}"
                            break

                result.append(data)

            # some keys not exist in original but do exist in translation
            if translation_flag:
                for line_ in translation:
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
                        for line_r in reference:
                            if line_r.startswith(f"{newkey}="):
                                data.context = f"{data.context}\n{line_r.split('=', 1)[1]}"
                                break

                    result.append(data)
            return result

        return self._convert_general(
            filepath=filepath,
            type_=type_,
            process_function=_process,
            filename_reference="en_US.lang",
            filename_translation="zh_CN.lang",
        )

    def _convert_json_lang(self, filepath: Path, type_: FileType) -> list[Data]:
        """late versions"""
        def _process(**kwargs) -> list[Data]:
            original: dict = kwargs["original"]
            reference_flag: bool = kwargs["reference_flag"]
            reference: dict = kwargs["reference"]
            translation_flag: bool = kwargs["translation_flag"]
            translation: dict = kwargs["translation"]

            result = []
            for key, value in original.items():
                data = Data(
                    key=key,
                    original=value,
                    translation="",
                )
                if reference_flag:
                    data.context = reference.get(key, "Not exist in reference")
                if translation_flag:
                    data.translation = translation.get(key, "")
                result.append(data)
            return result

        return self._convert_general(
            filepath=filepath,
            type_=type_,
            process_function=_process,
            filename_reference="en_us.json",
            filename_translation="zh_cn.json",
        )

    def _convert_misc(self, filepath: Path, type_: FileType) -> list[Data]:
        """plaintext, generally"""
        match type_:
            case FileType.PLAINTEXT:
                return self._convert_misc_plaintext(filepath, type_)
            case FileType.PLAINTEXT_IN_LINES:
                return self._convert_misc_plaintext_in_lines(filepath, type_)
            case FileType.CUSTOM_NPCS_DIALOGS:
                return self._convert_misc_customnpcs_dialog(filepath, type_)
            case FileType.CUSTOM_NPCS_QUESTS:
                return self._convert_misc_customnpcs_quests(filepath, type_)
            case FileType.LOTR_RENEWED_SPEECH:
                return self._convert_misc_lotr_renewed_speech(filepath, type_)
            case _:
                raise Exception(f"Unknown file type when convert: {filepath}")

    def _convert_misc_plaintext(self, filepath: Path, type_: FileType) -> list[Data]:
        """plaintext, whole file"""
        def _process(**kwargs) -> list[Data]:
            original: str = kwargs["original"]
            reference_flag: bool = kwargs["reference_flag"]
            reference: str = kwargs["reference"]
            translation_flag: bool = kwargs["translation_flag"]
            translation: str = kwargs["translation"]

            data = Data(
                key=f"{filepath.with_suffix('').name}",
                original=original,
                translation=""
            )
            if reference_flag:
                data.context = reference
            if translation_flag:
                data.translation = translation
            return [data]

        return self._convert_general(
            filepath=filepath,
            type_=type_,
            process_function=_process,
        )

    def _convert_misc_plaintext_in_lines(self, filepath: Path, type_: FileType) -> list[Data]:
        """plaintext, split in lines"""
        def _process(**kwargs) -> list[Data]:
            original: list[str] = kwargs["original"]
            reference_flag: bool = kwargs["reference_flag"]
            reference: list[str] = kwargs["reference"]
            translation_flag: bool = kwargs["translation_flag"]
            translation: list[str] = kwargs["translation"]
            
            if reference_flag and len(original) != len(reference):
                reference_flag = False
            if translation_flag and len(original) != len(translation):
                translation_flag = False

            result = []
            for idx, line in enumerate(original):
                key = f"{idx}"
                if not line.strip():
                    key = f"BLANK-{key}"

                data = Data(
                    key=key,
                    original=line,
                    translation=""
                )
                if reference_flag:
                    data.context = reference[idx]
                if translation_flag:
                    data.translation = translation[idx]
                result.append(data)
            return result

        return self._convert_general(
            filepath=filepath,
            type_=type_,
            process_function=_process,
        )

    def _convert_misc_customnpcs_dialog(self, filepath: Path, type_: FileType) -> list[Data]:
        def _process(**kwargs) -> list[Data]:
            original: str = kwargs["original"]
            translation_flag: bool = kwargs["translation_flag"]
            translation: str = kwargs["translation"]

            option_slots = re.findall(r'\"OptionSlot\": (\d+),*\n', original)
            option_titles = re.findall(r'\"Title\": \"([\s\S]*?)\",*\n', original)
            dialog_text = re.findall(r'\"DialogText\": \"([\s\S]*?)\",*\n', original)

            fetch = {
                "dialogtext": dialog_text[0] if dialog_text else "",
                **dict(zip(option_slots, option_titles)),
            }

            if translation_flag:
                option_slots_translation = re.findall(r'\"OptionSlot\": (\d+),*\n', translation)
                option_titles_translation = re.findall(r'\"Title\": \"([\s\S]*?)\",*\n', translation)
                dialog_text_translation = re.findall(r'\"DialogText\": \"([\s\S]*?)\",*\n', translation)

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

        return self._convert_general(
            filepath=filepath,
            type_=type_,
            process_function=_process,
        )

    def _convert_misc_customnpcs_quests(self, filepath: Path, type_: FileType) -> list[Data]:
        def _process(**kwargs) -> list[Data]:
            original: str = kwargs["original"]
            translation_flag: bool = kwargs["translation_flag"]
            translation: str = kwargs["translation"]

            fetch = {
                "text": re.findall(r'\"Text\": \"([\s\S]*?)\",*\n', original)[0],
                "completetext": re.findall(r'\"CompleteText\": \"([\s\S]*?)\",*\n', original)[0],
            }

            if translation_flag:
                fetch_translation = {
                    "title": re.findall(r'\"Title\": \"([\s\S]*?)\",*\n', translation)[0],
                    "text": re.findall(r'\"Text\": \"([\s\S]*?)\",*\n', translation)[0],
                    "completetext": re.findall(r'\"CompleteText\": \"([\s\S]*?)\",*\n', translation)[0],
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

        return self._convert_general(
            filepath=filepath,
            type_=type_,
            process_function=_process,
        )

    def _convert_misc_lotr_renewed_speech(self, filepath: Path, type_: FileType) -> list[Data]:
        def _process(**kwargs) -> list[Data]:
            original: list[dict] = kwargs["original"]

            result = []
            for idx, speech in enumerate(original):
                result.extend([
                    Data(
                        key=f'{idx}-{idx_}',
                        original=line,
                        translation="",
                    )
                    for idx_, line in enumerate(speech['lines'])
                ])
            return result

        return self._convert_general(
            filepath=filepath,
            type_=type_,
            process_function=_process,
        )


class Restoration:
    def restore(self):
        """paratranz jsons to local raw texts"""
        for root, dirs, files in os.walk(settings.filepath.root / settings.filepath.download):
            for file in files:
                filepath = Path(root) / file
                relative_path = filepath.relative_to(settings.filepath.root / settings.filepath.download)
                relative_path = relative_path.with_suffix("")
                converted_path = relative_path.parent / f"{relative_path.name}.json"
                os.makedirs(settings.filepath.root / settings.filepath.result / relative_path.parent, exist_ok=True)

                file_type = Project.categorize(relative_path)

                try:
                    match file_type:
                        case FileType.LANG:
                            self._restore_lang(converted_path, file_type)
                        case FileType.JSON_LANG:
                            self._restore_json_lang(converted_path, file_type)
                        case _:
                            self._restore_misc(converted_path, file_type)
                except FileNotFoundError as e:
                    logger.error(f'File not exist: {converted_path}')

    @staticmethod
    def _restore_general(filepath: Path, type_: FileType, process_function: Callable[..., "FileContent"], **kwargs):
        filepath_original = DIR_ORIGINAL / filepath.with_suffix("")
        with open(filepath_original, "r", encoding="utf-8") as fp:
            original = Project.read(fp, type_)

        filepath_download = settings.filepath.root / settings.filepath.download / filepath
        with open(filepath_download, "r", encoding="utf-8") as fp:
            download = json.load(fp)

        result = process_function(
            filepath=filepath,
            original=original,
            download=download,
            **kwargs
        )

        filename_translation: Path | None = kwargs.get("filename_translation", None)
        filepath_result = (settings.filepath.root / settings.filepath.result / filepath.parent / filename_translation) if filename_translation else (settings.filepath.root / settings.filepath.result / filepath.with_suffix(""))
        with open(filepath_result, "w", encoding="utf-8") as fp:
            Project.write(content=result, fp=fp, type_=type_)

    def _restore_lang(self, filepath: Path, type_: FileType):
        def _process(**kwargs) -> "FileContent":
            download: list[dict] = kwargs["download"]

            result = []
            for line in download:
                if line["key"].startswith("BLANK"):
                    result.append("\n")
                    continue

                if line["key"].startswith("COMMENT") or line["key"].startswith("MISC"):
                    result.append((line['translation'] or line['original']).rstrip("\n") + "\n" or line["original"])
                    continue

                result.append(
                    f"{line['key']}={line['translation'] or line['original']}".rstrip("\n") + "\n"
                )
            return result

        return self._restore_general(
            filepath=filepath,
            type_=type_,
            process_function=_process,
            filename_translation="zh_CN.lang"
        )

    def _restore_json_lang(self, filepath: Path, type_: FileType):
        def _process(**kwargs) -> "FileContent":
            filepath_: Path = kwargs["filepath"]
            original: dict = kwargs["original"]
            download: list[dict] = kwargs["download"]

            for data in download:
                if data["key"] not in original:
                    logger.warning(f"File might not be consistent: {filepath_.with_suffix('')}")
                original[data["key"]] = data['translation'] or data['original']
            return original

        return self._restore_general(
            filepath=filepath,
            type_=type_,
            process_function=_process,
            filename_translation="zh_cn.json"
        )

    def _restore_misc(self, filepath: Path, type_: FileType):
        """plaintext, generally"""
        match type_:
            case FileType.PLAINTEXT:
                return self._restore_misc_plaintext(filepath, type_)
            case FileType.PLAINTEXT_IN_LINES:
                return self._restore_misc_plaintext_in_lines(filepath, type_)
            case FileType.CUSTOM_NPCS_DIALOGS:
                return self._restore_misc_customnpcs_dialog(filepath, type_)
            case FileType.CUSTOM_NPCS_QUESTS:
                return self._restore_misc_customnpcs_quests(filepath, type_)
            case FileType.LOTR_RENEWED_SPEECH:
                return self._restore_misc_lotr_renewed_speech(filepath, type_)
            case _:
                raise Exception(f"Unknown file type when restore: {filepath}")

    def _restore_misc_plaintext(self, filepath: Path, type_: FileType):
        def _process(**kwargs) -> "FileContent":
            download: list[dict] = kwargs["download"]
            return download[0]['translation'] or download[0]['original']

        return self._restore_general(
            filepath=filepath,
            type_=type_,
            process_function=_process,
        )

    def _restore_misc_plaintext_in_lines(self, filepath: Path, type_: FileType):
        def _process(**kwargs) -> "FileContent":
            download: list[dict] = kwargs["download"]

            result = []
            for line in download:
                if line["key"].startswith("BLANK"):
                    result.append("\n")
                    continue

                result.append(
                    (line['translation'] or line['original']).rstrip('\n') + "\n"
                )
            return result

        return self._restore_general(
            filepath=filepath,
            type_=type_,
            process_function=_process,
        )

    def _restore_misc_customnpcs_dialog(self, filepath: Path, type_: FileType):
        def _process(**kwargs) -> "FileContent":
            original: str = kwargs["original"]
            download: list[dict] = kwargs["download"]

            option_slots = re.findall(r'\"OptionSlot\": (\d+),*\n', original)
            option_titles = list(re.finditer(r'\"Title\": \"([\s\S]*?)\",*\n', original))
            for slot, title in list(zip(option_slots, option_titles))[::-1]:
                processed_line = title.group().replace(
                    title.groups()[0],
                    [
                        _['translation'] or _['original']
                        for _ in download
                        if _['key'] == slot
                    ][0]
                )

                original = (
                    f"{original[:title.start()]}"
                    f"{processed_line}"
                    f"{original[title.end():]}"
                )

            for pattern, key in {re.compile(r'\"DialogText\": \"([\s\S]*?)\",*\n'): "dialogtext"}.items():
                original = self._regex_restore(pattern, download, key, original)
            return original

        return self._restore_general(
            filepath=filepath,
            type_=type_,
            process_function=_process,
        )

    def _restore_misc_customnpcs_quests(self, filepath: Path, type_: FileType):
        def _process(**kwargs) -> "FileContent":
            original: str = kwargs["original"]
            download: list[dict] = kwargs["download"]

            for pattern, key in {
                re.compile(r'\"Title\": \"([\s\S]*?)\",*\n'): "title",
                re.compile(r'\"Text\": \"([\s\S]*?)\",*\n'): "text",
                re.compile(r'\"CompleteText\": \"([\s\S]*?)\",*\n'): "completetext",
            }.items():
                original = self._regex_restore(pattern, download, key, original)
            return original

        return self._restore_general(
            filepath=filepath,
            type_=type_,
            process_function=_process,
        )

    def _restore_misc_lotr_renewed_speech(self, filepath: Path, type_: FileType):
        def _process(**kwargs) -> "FileContent":
            original: list[dict] = kwargs["original"]
            download: list[dict] = kwargs["download"]

            for idx, speech in enumerate(original):
                for idx_, line in enumerate(speech["lines"]):
                    if result := [
                        _["translation"] or _["original"]
                        for _ in download
                        if _["key"] == f"{idx}-{idx_}"
                    ]:
                        original[idx]["lines"][idx_] = result[0]
            return original

        return self._restore_general(
            filepath=filepath,
            type_=type_,
            process_function=_process,
        )

    @staticmethod
    def _regex_restore(pattern: re.Pattern, content: list[dict], key: str, original: str):
        title = re.search(pattern, original)
        replaced = [
            _["translation"] or _["original"]
            for _ in content
            if _["key"] == key
        ]
        if not replaced:
            return original

        processed_line = title.group().replace(
            title.groups()[0],
            replaced[0]
        )
        return (
            f"{original[:title.start()]}"
            f"{processed_line}"
            f"{original[title.end():]}"
        )


class Project:
    def __init__(self):
        self._convert = Conversion().convert
        self._restore = Restoration().restore

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

        if "lotr" in filepath_str.lower():
            if "speech" in filepath_str:
                if filepath.suffix == ".json":
                    return FileType.LOTR_RENEWED_SPEECH

        raise Exception(f"Unknown file type: {filepath}")

    @staticmethod
    def read(fp: io.TextIOBase, type_: FileType) -> list[str] | str | list | dict:
        match type_:
            case FileType.LANG | FileType.PLAINTEXT_IN_LINES:
                return fp.readlines()
            case FileType.JSON_LANG | FileType.LOTR_RENEWED_SPEECH:
                return json.load(fp)
            case _:
                return fp.read()

    @staticmethod
    def write(content: "FileContent", fp: io.TextIOBase, type_: FileType):
        match type_:
            case FileType.LANG | FileType.PLAINTEXT_IN_LINES:
                fp.writelines(content)
            case FileType.JSON_LANG | FileType.LOTR_RENEWED_SPEECH:
                json.dump(content, fp, ensure_ascii=False, indent=2)
            case _:
                fp.write(content)

    @staticmethod
    def wash_encoding():
        for root, dirs, files in os.walk(settings.filepath.root / settings.filepath.source):
            for file in files:
                filepath = Path(root) / file
                try:
                    with open(filepath, "r", encoding="utf-8") as fp:
                        fp.read()
                except UnicodeDecodeError as e:
                    Project.change_encoding(filepath)

    @staticmethod
    def change_encoding(filepath: Path):
        with open(filepath, "rb") as fp:
            encoding = chardet.detect(fp.read())

        encoding, confidence, language = encoding["encoding"], encoding["confidence"], encoding["language"]
        if encoding != "utf-8":
            logger.warning(f"not utf-8: {encoding}(prob: {confidence}, lang: {language}) | {filepath}")

            if confidence < 0.5:
                return

            with open(filepath, "r", encoding=encoding) as fp:
                content = fp.read()

            with open(filepath, "w", encoding="utf-8") as fp:
                fp.write(content)

    @property
    def convert(self):
        return self._convert

    @property
    def restore(self):
        return self._restore


__all__ = [
    "Project"
]
