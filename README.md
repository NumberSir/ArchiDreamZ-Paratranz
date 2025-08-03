# 概述
该项目是一个半自动化的 Minecraft 模组的翻译辅助工具，使得 MC 模组语言文件可以在 [Paratranz 云翻译平台](https://paratranz.cn/) 进行翻译。该项目会将模组语言文件转换格式为 Paratranz 要求的格式，并最终实现 Github 仓库与 Paratranz 项目进行双向文件同步。

# 特点介绍
- 将模组的语言文件按要求放进程序并运行，就能转换为 Paratranz 所要求的格式。
- 支持为原文添加参照语言，例如：原文是俄文，如果模组有英文翻译，可以将英文的文件也放入程序，程序能为每个俄文词条分别添加英文参照。
- 支持添加已存在的翻译文件，程序会自动将已有的翻译提取进相应词条。
- 支持添加译者自创的额外翻译，译者可以按要求将某文件额外的魔戒姓名与对话放在指定位置，程序会自动将其提取为该文件的新的词条。
- 若译文与原文或参照语言相同，则程序不会进行提取。
- 支持的文件类型：MC 的 lang 文件、魔戒 1.7.10 所有文件、魔戒 1.16.5 所有文件、自定义 NPC 对话与任务。

## 转换机制介绍
该程序的转换机制分为提取与还原两部分：将模组原文件提取为 Paratranz 格式、将 Paratranz 翻译完的文件还原为模组文件原格式。

**MC lang 文件提取机制：**
- MC 1.13 以前，MC 的语言文件是.lang 格式的，模组的语言文件也是一样。程序会逐行提取，每行为一个词条。但文件中还有空行与注释，这些也会被分别提取为一个词条。
- MC 1.13 更新后，语言文件变为了.json 格式，同样是每行一个词条。只是文件中只有空行不再有注释了，每个空行也会被分别提取为一个词条。

**1.7.10 魔戒类模组提取机制：**
- lore 文件会将整个文件的内容提取进单个词条。
- names 与 speech 文件会逐行提取，每行为一个词条。
- 在 names 与 speech 文件中，若某文件的**译文**的行数与原文不同，则该译文文件每一行的译文都不会被提取，以防止原文译文匹配错误，需要用户在 Paratranz 手动添加译文。
- 在 names 与 speech 文件中，若某文件的**参照语言**的行数与原文不同，则该参照语言文件的所有内容都会被程序提取进每一行原文中，即每一行原文都有整个参照语言文件做参照。
- 在 names 与 speech 文件中，经常会有译者添加自创的额外内容，若添加后导致行数与原文不同的话，程序将不会提取该文件内的所有译文，需要用户手动将额外文本放置在下方后文要求的另一位置，以确保译文与原文文件逐行对应。

**1.7.10 自定义 NPC 提取机制：**
- dialogs 文件只会提取 DialogText 与 Options，也就是对话与选项，其他内容（例如 DialogTitle）因会导致游戏错误而不可翻译。
- quests 文件只会提取 Text 与 CompleteText，也就是任务介绍文本与完成文本，其他内容（例如 CompleterNpc、Title、QuestLocation）因会导致游戏错误而不可翻译。
- 目前只有对话框能够翻译，而 NPC 的气泡对话因直接储存在区块文件内而没有外置，因此无法翻译。

**1.16.5 魔戒类模组提取机制：**


# 运行流程介绍
1. 若进行提取操作，用户需在 `./resource/1-SourceFile` 文件夹下按照下方要求，放入模组原文件。
2. 运行程序后，`./resource/2-ConvertedParatranzFile` 中会生成提取后的文件，需要手动上传到 Paratranz 项目（未来实现自动），注意文件目录结构要与提取时的相同，否则无法还原且无法自动文件同步，可参考我们在 Paratranz 上已有的项目。
3. 若进行还原操作，在 `./resource/3-TranslatedParatranzFile` 中会生成自动下载好的 Paratranz 翻译后的文件（原文-汉化字典），或手动去 Paratranz 下载并放入。若开启了自动下载却没有下载文件，则说明你的 Paratranz 项目中没有汉化文件，或 Paratranz 项目结构不对。
4. 运行程序后，`./resource/4-SourceTranslatedFile` 中会生成还原后的模组文件，需要将其手动放入模组文件中。

# 项目部署
1. 你的电脑上需要有 [Python][Python] 3.10+ 环境。

2. 安装本项目必需的库：
    - 安装 [pipx](https://pipx.pypa.io/stable/installation/) ：
    ```shell
    pip install pipx
    ```
    - 安装 [poetry](https://python-poetry.org/docs/#installation) ：
    ```shell
    pipx install poetry
    ```
    - 为该项目安装 poetry 依赖，在项目当前目录下运行：
    ```shell
    poetry install
    ```
    
# 使用说明
1.文件结构：
```text
resource
┖━ 1-SourceFile
   ┣━ original 
   ┃  ┣━ CustomNPCs
   ┃  ┃  ┗━ ...
   ┃  ┣━ LOTRReworked
   ┃  ┃  ┣━ lang
   ┃  ┃  ┃  ┗━ ru_RU.lang
   ┃  ┃  ┗━ ...
   ┃  ┗━ ...
   ┣━ reference 
   ┃  ┣━ LOTRReworked
   ┃  ┃  ┣━ lang
   ┃  ┃  ┃  ┗━ en_US.lang
   ┃  ┃  ┗━ ...
   ┃  ┗━ ...
   ┣━ translation
   ┃  ┣━ CustomNPCs
   ┃  ┃  ┗━ ...
   ┃  ┣━ LOTRReworked
   ┃  ┃  ┣━ lang
   ┃  ┃  ┃  ┗━ zh_CN.lang
   ┃  ┃  ┗━ ...
   ┃  ┗━ ...
   ┗━ translation_extra
      ┣━ LOTRReworked
      ┃  ┣━ names
      ┃  ┃  ┗━ ...
      ┃  ┗━ speech
      ┃     ┗━ ...
      ┗━ ...
```
2. 手动从模组文件内拿出所有需要提取的原文、参照、译文文件，并确保所有文件编码为 UTF-8。当程序进行提取时，若检测到非 UTF-8 编码文件即会报错，用户需按照报错的提示去处理相应的文件。需特别注意：
    - 俄文模组的 lang 文件编码经常是 UTF-8-BOM，需要手动转换编码为 UTF-8，不然提取时会出现问题。
	- 俄文模组的 speech 文件编码经常是 Windows-1251 编码（可能会被误识别为 Macintosh 编码），需要手动转换编码为 UTF-8。

3. **提取**：在 `./resource/1-SourceFile` 文件夹下按照模组名称放入需要提取的文件：
    - 其中 `original` 文件夹中放原文文件；
    - 若有其他参照语言文件请按照同样相对路径放入 `reference` 文件夹中；
    - 若有已经翻译好的译文文件请按照同样相对路径放入 `translation` 文件夹中；
    - 若魔戒模组的 names 与 speech 文件中有译者自创的额外姓名或对话，请将额外内容剪切到同名的新文件内，并将新文件按照同样相对路径放入 `translation_extra` 文件夹中。

4. **还原**：将从 Paratranz 下载的文件，按照模组名称放入 `./resource/3-TranslatedParatranzFile` 文件夹中即可。若开启了自动文件下载上传功能，在程序运行后可自动从 Paratranz 下载文件。

5. 填写 `.env` 中的环境变量
```dotenv
PROJECT_NAME=<项目名，默认为 ArchiDreamZ-Paratranz>
PROJECT_LANGUAGE=<所要翻译成的语言代码，默认为 zh_cn>
PROJECT_LOG_LEVEL=<日志输出的最低等级，默认为 INFO>
GITHUB_ACCESS_TOKEN=<必填。GitHub 个人 token，暂时无用>         #若用不到Github可填0
PARATRANZ_PROJECT_ID=<必填。Paratranz 项目 ID，整数>            #若用不到Paratranz自动文件上传下载可填0
PARATRANZ_TOKEN=<必填。Paratranz 个人 token，32 位字母数字组合> #若用不到Paratranz自动文件上传下载可填0
```
6. 运行根目录下的 `main.py`
```shell
poetry run python -m main
```
