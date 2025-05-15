# 简介
半自动化汉化 Minecraft 模组小工具

# 用法
1. 安装 Python 3.8+, 安装必需的库：
```shell
pip install -r requirements.txt
```
2. 在 `./resource/1-SourceFile` 文件夹下按照模组放入需要汉化的原文件
    - 其中 `original` 文件夹中放原文件
    - 若有其他语言参考请按照同样相对路径放入 `reference` 文件夹中
    - 若有已经翻译好的文件请按照同样相对路径放入 `translation` 文件夹中
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
   ┗━ translation
      ┣━ CustomNPCs
      ┃  ┗━ ...
      ┗━ ...
```
3. 填写 `.env` 中的环境变量
```dotenv
PROJECT_NAME=<项目名，默认为 ArchiDreamZ-Paratranz>
PROJECT_LANGUAGE=<所要翻译成的语言代码，默认为 zh_cn>
PROJECT_LOG_LEVEL=<日志输出的最低等级，默认为 INFO>
GITHUB_ACCESS_TOKEN=<必填。GitHub 个人 token，暂时无用>
PARATRANZ_PROJECT_ID=<必填。Paratranz 项目 ID，整数>
PARATRANZ_TOKEN=<必填。Paratranz 个人 token，32 位字母数字组合>
```
4. 运行根目录下的 `main.py`
```shell
python -m main
```
5. `./resource/2-ConvertedParatranzFile` 中会生成处理后的原文件，需要手动上传到 Paratranz 项目根目录下
6. `./resource/3-TranslatedParatranzFile` 中会生成自动下载好的原文-汉化字典，若没有说明你的 Paratranz 项目中没有汉化文件，或 Paratranz 项目结构不对
7. `./resource/4-SourceTranslatedFile` 中会生成替换完毕的汉化文件，需要将其手动放入模组文件中