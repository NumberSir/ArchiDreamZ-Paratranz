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
from src.exception import ProjectStructureException, UnknownFileTypeException
from src.log import logger

# from src.libs.openapi_client import ApiClient as ParatranzClient, FilesApi, Configuration

DIR_ORIGINAL = settings.filepath.root / settings.filepath.source / "original"
DIR_REFERENCE = settings.filepath.root / settings.filepath.source / "reference"
DIR_TRANSLATION = settings.filepath.root / settings.filepath.source / "translation"
DIR_TRANSLATION_EXTRA = settings.filepath.root / settings.filepath.source / "translation_extra"

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

    LOTR_LEGACY_SPEECH = auto()
    LOTR_LEGACY_NAMES = auto()
    LOTR_RENEWED_SPEECH = auto()


class Conversion:
    def convert(self):
        """local raw texts to paratranz jsons"""
        logger.info("")
        logger.info("======= CONVERSION START =======")
        if not DIR_ORIGINAL.exists():
            logger.bind(filepath=DIR_ORIGINAL).error("Filepath does not exist!")
            raise ProjectStructureException(DIR_ORIGINAL)

        for root, dirs, files in os.walk(DIR_ORIGINAL, topdown=False):
            for file in files:
                filepath = Path(root) / file
                relative_path = filepath.relative_to(DIR_ORIGINAL)
                converted_path = relative_path.parent / f"{relative_path.name}.json"
                os.makedirs(settings.filepath.root / settings.filepath.converted / relative_path.parent, exist_ok=True)

                logger.bind(filepath=relative_path).debug("Converting file")
                file_type = Project.categorize(relative_path)
                if not file_type:
                    continue

                match file_type:
                    case FileType.LANG:
                        datas = self._convert_lang(relative_path, file_type)
                    case FileType.JSON_LANG:
                        datas = self._convert_json_lang(relative_path, file_type)
                    case _:
                        datas = self._convert_misc(relative_path, file_type)

                if datas is None:
                    logger.bind(filepath=relative_path).error("Converting file failed")
                    continue

                with open(settings.filepath.root / settings.filepath.converted / converted_path, "w", encoding="utf-8") as fp:
                    json.dump([asdict(_) for _ in datas], fp, ensure_ascii=False, indent=2)
                logger.bind(filepath=relative_path).debug("Converting file successfully")

            if Path(root).parent.parent == DIR_ORIGINAL:
                logger.bind(filepath=Path(root).relative_to(DIR_ORIGINAL)).success("Converting mod folder successfully")
            elif Path(root).parent == DIR_ORIGINAL:
                logger.bind(filepath=Path(root).name).success("Converting mod successfully.")

    @staticmethod
    def _convert_general(filepath: Path, type_: FileType, process_function: Callable[..., list[Data]], **kwargs) -> list[Data] | None:
        filepath_original = DIR_ORIGINAL / filepath
        original = Project.safe_read(filepath_original, type_)
        if not original:
            return None

        reference = None
        filename_reference: str | None = kwargs.get("filename_reference", None)
        filepath_reference = (DIR_REFERENCE / filepath.parent / filename_reference) if filename_reference else (DIR_REFERENCE / filepath)
        if reference_flag := filepath_reference.exists():
            logger.bind(filepath=filepath_reference.relative_to(DIR_REFERENCE)).debug("Reference file exists")
            reference = Project.safe_read(filepath_reference, type_)
            if not reference:
                reference_flag = False

        translation = None
        filename_translation: str | None = kwargs.get("filename_translation", None)
        filepath_translation = (DIR_TRANSLATION / filepath.parent / filename_translation) if filename_translation else (DIR_TRANSLATION / filepath)
        if translation_flag := filepath_translation.exists():
            logger.bind(filepath=filepath_translation.relative_to(DIR_TRANSLATION)).debug("Translation file exists")
            translation = Project.safe_read(filepath_translation, type_)
            if not translation:
                translation_flag = False

        translation_extra = None
        filename_translation_extra: str | None = kwargs.get("filename_translation_extra", None)
        filepath_translation_extra = (DIR_TRANSLATION_EXTRA / filepath.parent / filename_translation_extra) if filename_translation_extra else (DIR_TRANSLATION_EXTRA / filepath)
        if translation_extra_flag := filepath_translation_extra.exists():
            logger.bind(filepath=filepath_translation_extra.relative_to(DIR_TRANSLATION_EXTRA)).debug("Translation extra file exists")
            translation_extra = Project.safe_read(filepath_translation_extra, type_)
            if not translation_extra:
                translation_extra_flag = False

        return process_function(
            filepath=filepath,
            original=original,
            reference=reference,
            reference_flag=reference_flag,
            translation=translation,
            translation_flag=translation_flag,
            translation_extra=translation_extra,
            translation_extra_flag=translation_extra_flag,
            **kwargs
        )

    """ LANG """
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
                    potential_context = [
                        f"{data.context}\n{line_.split('=', 1)[1].strip()}"
                        for line_ in reference
                        if line_.startswith(f"{key}=")
                    ]
                    data.context = potential_context[0] if potential_context else data.context

                if translation_flag:
                    potential_translation = [
                        f"{line_.split('=', 1)[1].strip()}"
                        for line_ in translation
                        if line_.startswith(f"{key}=")
                    ]
                    data.translation = potential_translation[0] if potential_translation else data.translation

                result.append(data)

            # some keys not exist in original but do exist in reference
            if reference_flag:
                for line_ in reference:
                    if "=" not in line_:
                        continue
                    newkey, newvalue = line_.split("=", 1)
                    if newkey in {_.key for _ in result}:
                        continue
                    logger.debug(f"Reference has new key-values: {newkey}={newvalue}")

                    data = Data(
                        key=newkey,
                        original=newvalue.strip(),
                        translation="",
                        context="Additional in reference"
                    )

                    if translation_flag:
                        for line_r in translation:
                            if line_r.startswith(f"{newkey}="):
                                data.translation = line_r.split("=", 1)[1].strip()
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
                    logger.debug(f"Translation has new key-values: {newkey}={newvalue}")

                    data = Data(
                        key=newkey,
                        original="MISSING",
                        translation=newvalue.strip(),
                        context="Additional in translation"
                    )

                    if reference_flag:
                        for line_r in reference:
                            if line_r.startswith(f"{newkey}="):
                                data.context = f"{data.context}\n{line_r.split('=', 1)[1].strip()}"
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

            # some keys not exist in original but do exist in reference
            if reference_flag:
                for key, value in reference.items():
                    if key in original:
                        continue
                    logger.debug(f"Reference has new key-values: {key}={value}")

                    data = Data(
                        key=key,
                        original=value,
                        translation="",
                        context="Additional in reference"
                    )

                    if translation_flag and key in translation:
                        data.translation = translation[key]
                    result.append(data)

            # some keys not exist in original but do exist in translation
            if translation_flag:
                for key, value in translation.items():
                    if key in original:
                        continue
                    logger.debug(f"Translation has new key-values: {key}={value}")

                    data = Data(
                        key=key,
                        original="MISSING",
                        translation=value,
                        context="Additional in translation"
                    )
                    if reference_flag and key in reference:
                        data.context = f"{data.context}\n{reference[key]}"
                    result.append(data)
                    
            return result

        return self._convert_general(
            filepath=filepath,
            type_=type_,
            process_function=_process,
            filename_reference="en_us.json",
            filename_translation="zh_cn.json",
        )

    """ MISC """
    def _convert_misc(self, filepath: Path, type_: FileType) -> list[Data]:
        """plaintext, generally"""
        match type_:
            case FileType.PLAINTEXT:
                return self._convert_misc_plaintext(filepath, type_)
            case FileType.PLAINTEXT_IN_LINES:
                return self._convert_misc_plaintext_in_lines(filepath, type_)
            case _:
                return self._convert_special(filepath, type_)

    def _convert_misc_plaintext(self, filepath: Path, type_: FileType) -> list[Data]:
        """plaintext, whole file"""
        def _process(**kwargs) -> list[Data]:
            original: str = kwargs["original"]
            reference_flag: bool = kwargs["reference_flag"]
            reference: str = kwargs["reference"]
            translation_flag: bool = kwargs["translation_flag"]
            translation: str = kwargs["translation"]

            data = Data(
                key=f"{'.'.join(filepath.with_suffix('').parts)}",
                original=original,
                translation=""
            )
            if reference_flag:
                data.context = reference
            if translation_flag:
                data.translation = translation if (translation != original and translation != reference) else ""
            return [data]

        return self._convert_general(
            filepath=filepath,
            type_=type_,
            process_function=_process,
        )

    def _convert_misc_plaintext_in_lines(self, filepath: Path, type_: FileType, *, replace_untranslated_with_blank: bool = False) -> list[Data]:
        """plaintext, split in lines"""
        def _process(**kwargs) -> list[Data]:
            original: list[str] = kwargs["original"]
            reference_flag: bool = kwargs["reference_flag"]
            reference: list[str] = kwargs["reference"]
            translation_flag: bool = kwargs["translation_flag"]
            translation: list[str] = kwargs["translation"]
            translation_extra_flag: bool = kwargs["translation_extra_flag"]
            translation_extra: list[str] = kwargs["translation_extra"]

            reference_length_unequal = False
            if reference_flag and len(original) != len(reference):
                reference_length_unequal = len(original) != len(reference)
                logger.bind(filepath=filepath).warning(f"Reference length inequal ({len(original)}/{len(reference)})")

            translation_length_unequal = False
            if translation_flag and len(original) != len(translation):
                translation_length_unequal = len(original) != len(translation)
                logger.bind(filepath=filepath).warning(f"Translation length inequal ({len(original)}/{len(translation)})")

            result = []
            for idx, line in enumerate(original):
                line = line.strip()
                key = f"{'.'.join(filepath.with_suffix('').parts)}.{idx}"
                if not line:
                    key = f"BLANK-{key}"

                data = Data(
                    key=key,
                    original=line,
                    translation=""
                )
                if reference_flag:
                    if reference_length_unequal:
                        data.context = "".join(reference)
                    else:
                        data.context = reference[idx].strip() if len(reference) > idx else ""
                if translation_flag and not translation_length_unequal:
                    data.translation = translation[idx].strip() if len(translation) > idx else ""
                    if replace_untranslated_with_blank and data.translation == data.original:
                        data.translation = ""
                result.append(data)

            if translation_extra_flag:
                for idx, line in enumerate(translation_extra):
                    line = line.strip()
                    key = f"{'.'.join(filepath.with_suffix('').parts)}.{idx+len(original)+1}"
                    if not line.strip():
                        key = f"BLANK-{key}"

                    result.append(
                        Data(
                            key=key,
                            original="Extra keys in translation",
                            translation=line
                        )
                    )

            return result

        return self._convert_general(
            filepath=filepath,
            type_=type_,
            process_function=_process,
        )

    """ SPECIAL """
    def _convert_special(self, filepath: Path, type_: FileType) -> list[Data]:
        match type_:
            case FileType.CUSTOM_NPCS_DIALOGS:
                return self._convert_misc_customnpcs_dialog(filepath, type_)
            case FileType.CUSTOM_NPCS_QUESTS:
                return self._convert_misc_customnpcs_quests(filepath, type_)
            case FileType.LOTR_RENEWED_SPEECH:
                return self._convert_misc_lotr_renewed_speech(filepath, type_)
            case FileType.LOTR_LEGACY_NAMES:
                return self._convert_misc_lotr_legacy_names(filepath, type_)
            case FileType.LOTR_LEGACY_SPEECH:
                return self._convert_misc_lotr_legacy_speech(filepath, type_)
            case _:
                logger.bind(filepath=filepath).error("Unknown file type when convert")
                raise UnknownFileTypeException(filepath)

    def _convert_misc_customnpcs_dialog(self, filepath: Path, type_: FileType) -> list[Data]:
        def _process(**kwargs) -> list[Data]:
            original: str = kwargs["original"]
            translation_flag: bool = kwargs["translation_flag"]
            translation: str = kwargs["translation"]

            option_slots = re.findall(r'\"OptionSlot\": (\d+),*\n', original)
            option_titles = re.findall(r'\"Title\": \"([\s\S]*?)\",*\n', original)
            dialog_text = re.findall(r'\"DialogText\": \"([\s\S]*?)(?<!\\)\",\n', original) or re.findall(r'\"DialogText\": \"([\s\S]*?)(?<!\\)\"\n', original)

            fetch = {
                "DialogText": dialog_text[0] if dialog_text else "",
                **dict(zip([f"Options.slot{idx}" for idx in option_slots], option_titles)),
            }

            if translation_flag:
                option_slots_translation = re.findall(r'\"OptionSlot\": (\d+),*\n', translation)
                option_titles_translation = re.findall(r'\"Title\": \"([\s\S]*?)\",*\n', translation)
                dialog_text_translation = re.findall(r'\"DialogText\": \"([\s\S]*?)\",*\n', translation) or re.findall(r'\"DialogText\": \"([\s\S]*?)(?<!\\)\"\n', translation)

                fetch_translation = {
                    "DialogText": dialog_text_translation[0] if dialog_text_translation else "",
                    **dict(zip([f"Options.slot{idx}" for idx in option_slots_translation], option_titles_translation)),
                }

            result = []
            for key, value in fetch.items():
                data = Data(
                    key=f"{'.'.join(filepath.with_suffix('').parts[:-1])}.file{filepath.with_suffix('').name}.{key}",
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
                "Text": re.findall(r'\"Text\": \"([\s\S]*?)\",*\n', original)[0],
                "CompleteText": re.findall(r'\"CompleteText\": \"([\s\S]*?)\",*\n', original)[0],
            }

            if translation_flag:
                fetch_translation = {
                    "Title": re.findall(r'\"Title\": \"([\s\S]*?)\",*\n', translation)[0],
                    "Text": re.findall(r'\"Text\": \"([\s\S]*?)\",*\n', translation)[0],
                    "CompleteText": re.findall(r'\"CompleteText\": \"([\s\S]*?)\",*\n', translation)[0],
                }

            result = []
            for key, value in fetch.items():
                data = Data(
                    key=f"{'.'.join(filepath.with_suffix('').parts[:-1])}.file{filepath.with_suffix('').name}.{key}",
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
            original: dict = kwargs["original"]

            result = []
            for idx, speech in enumerate(original["speech"]):
                result.extend([
                    Data(
                        key=f"{'.'.join(filepath.with_suffix('').parts)}.speech{idx}.line{idx_}",
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

    def _convert_misc_lotr_legacy_names(self, filepath: Path, type_: FileType) -> list[Data]:
        return self._convert_misc_plaintext_in_lines(filepath=filepath, type_=type_, replace_untranslated_with_blank=True)

    def _convert_misc_lotr_legacy_speech(self, filepath: Path, type_: FileType) -> list[Data]:
        return self._convert_misc_plaintext_in_lines(filepath=filepath, type_=type_, replace_untranslated_with_blank=True)


class Restoration:
    def restore(self):
        """paratranz jsons to local raw texts"""
        logger.info("")
        logger.info("======= RESTORATION START =======")
        for root, dirs, files in os.walk(settings.filepath.root / settings.filepath.download, topdown=False):
            for file in files:
                filepath = Path(root) / file
                relative_path = filepath.relative_to(settings.filepath.root / settings.filepath.download)
                relative_path = relative_path.with_suffix("")
                converted_path = relative_path.parent / f"{relative_path.name}.json"
                os.makedirs(settings.filepath.root / settings.filepath.result / relative_path.parent, exist_ok=True)

                logger.bind(filepath=converted_path).debug("Restoring file")
                file_type = Project.categorize(relative_path)
                if not file_type:
                    continue

                match file_type:
                    case FileType.LANG:
                        flag = self._restore_lang(converted_path, file_type)
                    case FileType.JSON_LANG:
                        flag = self._restore_json_lang(converted_path, file_type)
                    case _:
                        flag = self._restore_misc(converted_path, file_type)

                if flag:
                    logger.bind(filepath=converted_path).debug("Restoring file successfully")
                else:
                    logger.bind(filepath=converted_path).error("Restoring file failed")

            if Path(root).parent.parent == settings.filepath.root / settings.filepath.download:
                logger.bind(filepath=Path(root).relative_to(settings.filepath.root / settings.filepath.download)).success("Restoring mod folder successfully")
            elif Path(root).parent ==  settings.filepath.root / settings.filepath.download:
                logger.bind(filepath=Path(root).name).success("Restoring mod successfully.")

    @staticmethod
    def _restore_general(filepath: Path, type_: FileType, process_function: Callable[..., "FileContent"], **kwargs) -> bool:
        filepath_original = DIR_ORIGINAL / filepath.with_suffix("")
        original = Project.safe_read(filepath_original, type_)
        if not original:
            return False

        filepath_download = settings.filepath.root / settings.filepath.download / filepath
        with open(filepath_download, "r", encoding="utf-8") as fp:
            download = json.load(fp)

        filepath_translation_extra = DIR_TRANSLATION_EXTRA / filepath
        translation_extra_flag = filepath_translation_extra.exists()

        result = process_function(
            filepath=filepath,
            original=original,
            download=download,
            translation_extra_flag=translation_extra_flag,
            filepath_translation_extra=filepath_translation_extra,
            **kwargs
        )

        filename_translation: Path | None = kwargs.get("filename_translation", None)
        filepath_result = (settings.filepath.root / settings.filepath.result / filepath.parent / filename_translation) if filename_translation else (settings.filepath.root / settings.filepath.result / filepath.with_suffix(""))
        with open(filepath_result, "w", encoding="utf-8") as fp:
            Project.write(content=result, fp=fp, type_=type_)
        return True

    """ LANG """
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
                    logger.bind(filepath=filepath).warning("Extra keys in translation")
                original[data["key"]] = data['translation'] or data['original']
            return original

        return self._restore_general(
            filepath=filepath,
            type_=type_,
            process_function=_process,
            filename_translation="zh_cn.json"
        )

    """ MISC """
    def _restore_misc(self, filepath: Path, type_: FileType):
        """plaintext, generally"""
        match type_:
            case FileType.PLAINTEXT:
                return self._restore_misc_plaintext(filepath, type_)
            case FileType.PLAINTEXT_IN_LINES:
                return self._restore_misc_plaintext_in_lines(filepath, type_)
            case _:
                return self._restore_special(filepath, type_)

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
            original: list[str] = kwargs["original"]
            download: list[dict] = kwargs["download"]
            translation_extra_flag: bool = kwargs["translation_extra_flag"]
            filepath_translation_extra: Path = kwargs["filepath_translation_extra"]

            if translation_extra_flag:
                download = download[:len(original)]
                extra = download[len(original):]
                extra = [
                    '\n' if line['key'].startswith("BLANK") else line["translation"]
                    for line in extra
                ]
                with open(filepath_translation_extra, "w", encoding="utf-8") as fp:
                    fp.writelines(extra)
                shutil.copyfile(
                    filepath_translation_extra,
                    settings.filepath.root / settings.filepath.result / "extra" / filepath_translation_extra.relative_to(DIR_TRANSLATION_EXTRA)
                )

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

    """ SPECIAL """
    def _restore_special(self, filepath: Path, type_: FileType):
        match type_:
            case FileType.CUSTOM_NPCS_DIALOGS:
                return self._restore_misc_customnpcs_dialog(filepath, type_)
            case FileType.CUSTOM_NPCS_QUESTS:
                return self._restore_misc_customnpcs_quests(filepath, type_)
            case FileType.LOTR_RENEWED_SPEECH:
                return self._restore_misc_lotr_renewed_speech(filepath, type_)
            case FileType.LOTR_LEGACY_NAMES:
                return self._restore_misc_lotr_legacy_names(filepath, type_)
            case FileType.LOTR_LEGACY_SPEECH:
                return self._restore_misc_lotr_legacy_speech(filepath, type_)
            case _:
                raise UnknownFileTypeException(filepath)

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
            original: dict = kwargs["original"]
            download: list[dict] = kwargs["download"]

            for idx, speech in enumerate(original["speech"]):
                for idx_, line in enumerate(speech["lines"]):
                    if result := [
                        _["translation"] or _["original"]
                        for _ in download
                        if _["key"] == f"{idx}-{idx_}"
                    ]:
                        original["speech"][idx]["lines"][idx_] = result[0]
            return original

        return self._restore_general(
            filepath=filepath,
            type_=type_,
            process_function=_process,
        )

    def _restore_misc_lotr_legacy_names(self, filepath: Path, type_: FileType):
        return self._restore_misc_plaintext_in_lines(filepath=filepath, type_=type_)

    def _restore_misc_lotr_legacy_speech(self, filepath: Path, type_: FileType):
        return self._restore_misc_plaintext_in_lines(filepath=filepath, type_=type_)

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
            logger.bind(filepath=filepath).debug("Filepath cleaned")

    @staticmethod
    def categorize(filepath: Path) -> FileType | None:
        filepath_str = str(filepath)
        filepath_str_lower = filepath_str.lower()
        suffix = filepath.suffix or Path(filepath.name).suffix
        """ special """
        if "CustomNPCs" in filepath_str:
            if "dialogs" in filepath_str:
                logger.bind(filepath=filepath).debug(f"Type: {FileType.CUSTOM_NPCS_DIALOGS.name}")
                return FileType.CUSTOM_NPCS_DIALOGS
            if "quests" in filepath_str:
                logger.bind(filepath=filepath).debug(f"Type: {FileType.CUSTOM_NPCS_QUESTS.name}")
                return FileType.CUSTOM_NPCS_QUESTS

        if "lotr" in filepath_str_lower:
            if "speech" in filepath_str:
                if suffix == ".json":
                    logger.bind(filepath=filepath).debug(f"Type: {FileType.LOTR_RENEWED_SPEECH.name}")
                    return FileType.LOTR_RENEWED_SPEECH
                if suffix == ".txt":
                    logger.bind(filepath=filepath).debug(f"Type: {FileType.LOTR_LEGACY_SPEECH.name}")
                    return FileType.LOTR_LEGACY_SPEECH

            if "names" in filepath_str:
                logger.bind(filepath=filepath).debug(f"Type: {FileType.LOTR_LEGACY_NAMES.name}")
                return FileType.LOTR_LEGACY_NAMES

        match filepath.name:
            case "en_US.lang" | "ru_RU.lang" | "zh_CN.lang":
                logger.bind(filepath=filepath).debug(f"Type: {FileType.LANG.name}")
                return FileType.LANG
            case "en_us.json" | "ru_ru.json" | "zh_cn.json":
                logger.bind(filepath=filepath).debug(f"Type: {FileType.JSON_LANG.name}")
                return FileType.JSON_LANG
            case _:
                pass

        match suffix:
            case ".lang":
                logger.bind(filepath=filepath).debug(f"Type: {FileType.LANG.name}")
                return FileType.LANG
            case ".txt":
                if "lore" in filepath_str:
                    logger.bind(filepath=filepath).debug(f"Type: {FileType.PLAINTEXT.name}")
                    return FileType.PLAINTEXT
                logger.bind(filepath=filepath).debug(f"Type: {FileType.PLAINTEXT_IN_LINES.name}")
                return FileType.PLAINTEXT_IN_LINES
            case _:
                pass

        logger.bind(filepath=filepath).error("Unknown filetype when categorize")
        return None

    @staticmethod
    def safe_read(filepath: Path, type_: FileType) -> FileContent | None:
        try:
            with open(filepath, "r", encoding="utf-8") as fp:
                return Project.read(fp, type_)
        except FileNotFoundError as e:
            logger.bind(filepath=filepath).error("File not found when reading")
            return None

        except UnicodeDecodeError as e:
            logger.bind(filepath=filepath).warning("File encoding is not utf-8")
            if not Project.change_encoding(filepath):
                return None

            with open(filepath, "r", encoding="utf-8") as fp:
                return Project.read(fp, type_)

    @staticmethod
    def read(fp: io.TextIOBase, type_: FileType) -> list[str] | str | list | dict:
        match type_:
            case FileType.LANG | FileType.PLAINTEXT_IN_LINES | FileType.LOTR_LEGACY_NAMES | FileType.LOTR_LEGACY_SPEECH:
                return fp.readlines()
            case FileType.JSON_LANG | FileType.LOTR_RENEWED_SPEECH:
                return json.load(fp)
            case _:
                return fp.read()

    @staticmethod
    def write(content: "FileContent", fp: io.TextIOBase, type_: FileType):
        match type_:
            case FileType.LANG | FileType.PLAINTEXT_IN_LINES | FileType.LOTR_LEGACY_NAMES | FileType.LOTR_LEGACY_SPEECH:
                fp.writelines(content)
            case FileType.JSON_LANG | FileType.LOTR_RENEWED_SPEECH:
                json.dump(content, fp, ensure_ascii=False, indent=2)
            case _:
                fp.write(content)

    @staticmethod
    def change_encoding(filepath: Path) -> bool:
        with open(filepath, "rb") as fp:
            encoding = chardet.detect(fp.read())

        encoding, confidence, language = encoding["encoding"], encoding["confidence"], encoding["language"]
        if encoding == "utf-8":
            logger.bind(filepath=filepath).warning("Encoding detecting failed, file skipped")
            return False

        logger.bind(filepath=filepath).warning(f"Probably encoding: {encoding}({confidence*100:.2f}% {language})")
        if confidence < 0.5:
            logger.bind(filepath=filepath).warning(f"Confidence too low ({confidence*100:.2f}%<50%), file skipped")
            return False

        with open(filepath, "r", encoding=encoding) as fp:
            content = fp.read()

        with open(filepath, "w", encoding="utf-8") as fp:
            fp.write(content)
        logger.bind(filepath=filepath).success("Encoding successfully changed to utf-8")
        return True

    @property
    def convert(self):
        return self._convert

    @property
    def restore(self):
        return self._restore


__all__ = [
    "Project",
    "Conversion",
    "Restoration"
]
