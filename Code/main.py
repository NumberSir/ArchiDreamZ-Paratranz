"""
Paratranz格式双向转换程序
作者：彼梦Archi & DeepSeek
功能：根据文件类型提取游戏文本到JSON键值对，或将翻译后的JSON还原为游戏文件格式
使用方法：通过运行.bat调用，输入1提取，输入2还原
"""

import os
import json
import shutil
import re
from pathlib import Path
from collections import defaultdict

# ======================
# 全局配置
# ======================
BASE_DIR = Path(__file__).parent.parent  # 项目根目录
SOURCE_DIR = BASE_DIR / "1-SourceFile"
CONVERTED_DIR = BASE_DIR / "2-ConvertedParatranzFile"
TRANSLATED_DIR = BASE_DIR / "3-TranslatedParatranzFile"
OUTPUT_DIR = BASE_DIR / "4-SourceTranslatedFile"

IGNORE_FOLDERS_RESTORE = ["其他语言参考"]  # 仅还原时忽略

# ======================
# 通用工具函数
# ======================
def clean_directory(dir_path):
    """清空目标目录"""
    if dir_path.exists():
        shutil.rmtree(dir_path)
    dir_path.mkdir(parents=True)

def walk_directory(root_dir, mode="extract"):
    """遍历目录生成文件路径列表
    :param mode: extract-提取模式（包含参考文件）/ restore-还原模式（过滤参考文件）
    """
    file_list = []
    for root, dirs, files in os.walk(root_dir):
        # 还原模式时过滤文件夹
        if mode == "restore":
            dirs[:] = [d for d in dirs if d not in IGNORE_FOLDERS_RESTORE]
        
        for file in files:
            file_path = Path(root) / file
            file_list.append(file_path)
    return file_list

# ======================
# Lang文件处理模块 (.lang)
# ======================
def process_lang_file(file_path):
    """处理.lang文件提取"""
    entries = {}
    comment_counter = 1
    blank_counter = 1
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            original_line = line.rstrip('\n')
            # 处理空行
            if original_line.strip() == '':
                entries[f"blank_line.{blank_counter}"] = "\\n"
                blank_counter += 1
            # 处理注释
            elif original_line.startswith('#'):
                entries[f"comment_line.{comment_counter}"] = original_line
                comment_counter += 1
            # 处理普通键值对
            elif '=' in original_line:
                key, value = original_line.split('=', 1)
                entries[key.strip()] = value.strip()
                
    return entries

def restore_lang_file(json_data, output_path):
    """还原.lang文件"""
    output_lines = []
    
    for key, value in json_data.items():
        # 处理注释
        if key.startswith('comment_line.'):
            output_lines.append(value)
        # 处理空行
        elif key.startswith('blank_line.'):
            output_lines.append('')
        # 处理普通键值对
        else:
            output_lines.append(f"{key}={value}")
    
    # 写入文件
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))

# ======================
# 魔戒Lore文件处理模块
# ======================
def process_lore_file(file_path, root_dir):
    """处理LOTR lore文件提取"""
    relative_path = file_path.relative_to(root_dir)
    key_base = "lotr.lore." + relative_path.stem
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read().replace('\n', '\\n')
    
    return {key_base: content}

def restore_lore_file(json_data, output_path):
    """还原LOTR lore文件"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        for value in json_data.values():
            f.write(value.replace('\\n', '\n'))

# ======================
# Speech/Names文件处理模块
# ======================
def process_speech_file(file_path, root_dir):
    """处理Speech/Names文件提取"""
    entries = {}
    relative_path = file_path.relative_to(root_dir.parent)  # 获取相对于LOTR目录的路径
    key_base = "lotr." + str(relative_path).replace('\\', '.').replace('/', '.').replace('.txt', '')
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if line.strip():
                entries[f"{key_base}.{line_num}"] = line.strip()
    
    return entries

def restore_speech_file(json_data, output_path):
    """还原Speech/Names文件"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    # 按行号排序
    sorted_items = sorted(json_data.items(), key=lambda x: int(x[0].split('.')[-1]))
    for _, value in sorted_items:
        lines.append(value)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

# ======================
# CustomNPCs文件处理模块
# ======================
def process_customnpcs_file(file_path, root_dir):
    """处理CustomNPCs文件提取"""
    entries = {}
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 构建基础键名
    relative_path = file_path.relative_to(root_dir)
    key_base = "customnpcs." + str(relative_path.parent).replace('\\', '.').replace('/', '.') 
    key_base += f".file{file_path.stem}"
    
    # 提取不同字段
    patterns = {
        "DialogText": r'"DialogText": "(.*?)",',
        "Text": r'"Text": "(.*?)",',
        "CompleteText": r'"CompleteText": "(.*?)",',
    }
    
    # 处理普通字段
    for field, regex in patterns.items():
        match = re.search(regex, content, re.DOTALL)
        if match:
            text = match.group(1).replace('\n', '\\n')
            entries[f"{key_base}.{field}"] = text
    
    # 处理Title字段
    if "OptionSlot" in content:
        titles = re.findall(r'"Title": "(.*?)",', content, re.DOTALL)
        for idx, title in enumerate(titles, 1):
            entries[f"{key_base}.Title.slot{idx}"] = title.replace('\n', '\\n')
    
    return entries

def restore_customnpcs_file(json_data, output_path, original_file):
    """还原CustomNPCs文件"""
    with open(original_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 替换普通文本字段
    for key, value in json_data.items():
        if 'DialogText' in key:
            content = re.sub(r'("DialogText": ")(.*?)(",)', 
                            fr'\g<1>{value}\g<3>', content, flags=re.DOTALL)
        elif 'Text' in key:
            content = re.sub(r'("Text": ")(.*?)(",)', 
                            fr'\g<1>{value}\g<3>', content, flags=re.DOTALL)
        elif 'CompleteText' in key:
            content = re.sub(r'("CompleteText": ")(.*?)(",)', 
                            fr'\g<1>{value}\g<3>', content, flags=re.DOTALL)

    # 替换Title文本字段
    # 步骤1：提取所有需要替换的Title
    title_slots = {}
    for key in json_data:
        if 'Title.slot' in key:
            slot_num = int(key.split('slot')[-1])
            title_slots[slot_num] = json_data[key].replace('\\n', '\n')
    
    # 步骤2：构建替换队列
    if title_slots:
        # 使用队列记录替换顺序
        replacements = []
        def record_title(match):
            text = match.group(1)
            replacements.append(text)
            return match.group(0)  # 暂时保留原文本
        content = re.sub(r'"Title": "(.*?)",', record_title, content, flags=re.DOTALL)
        
        # 步骤3：应用具体替换
        for slot_num, new_text in title_slots.items():
            if 1 <= slot_num <= len(replacements):
                replacements[slot_num-1] = new_text
        
        # 步骤4：重新注入修改后的Title
        new_content = []
        title_index = 0
        for line in content.split('\n'):
            if '"Title": "' in line:
                if title_index < len(replacements):
                    line = re.sub(r'"Title": ".*?",', 
                                f'"Title": "{replacements[title_index]}",', line)
                    title_index += 1
            new_content.append(line)
        content = '\n'.join(new_content)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

# ======================
# 主处理流程
# ======================
def source_to_json():
    """提取原文件到JSON（包含参考文件）"""
    clean_directory(CONVERTED_DIR)
    reporter = ProcessReporter("extract")
    
    for file_path in walk_directory(SOURCE_DIR, mode="extract"):
        # 跳过不需要处理的文件
        if "language/json" in str(file_path):
            continue
        
        # 开始新的统计项
        reporter.start_new_file(file_path)
        
        # 根据文件类型选择处理方式
        try:
            if file_path.suffix == '.lang':
                entries = process_lang_file(file_path)
            elif "lore" in str(file_path):
                entries = process_lore_file(file_path, SOURCE_DIR / "txt/LOTR/lore")
            elif "speech" in str(file_path) or "names" in str(file_path):
                entries = process_speech_file(file_path, SOURCE_DIR / "txt/LOTR")
            elif "CustomNPCs" in str(file_path):
                entries = process_customnpcs_file(file_path, SOURCE_DIR / "CustomNPCs")
            else:
                continue  # 跳过不支持的文件类型
        
        # 写入JSON文件&记录统计
            if entries:
                # 保留原始文件名并添加.json后缀
                relative_path = file_path.relative_to(SOURCE_DIR)
                output_path = CONVERTED_DIR / relative_path.parent / (relative_path.name + ".json")
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(entries, f, ensure_ascii=False, indent=2)
                reporter.record_success()
            else:
                reporter.record_warning(file_path)
        except Exception as e:
            print(f"处理文件{file_path}时发生错误：{str(e)}")
            
    reporter.final_report()  # 报告输出

def json_to_source():
    """还原JSON到原文件格式（排除参考文件）"""
    clean_directory(OUTPUT_DIR)
    reporter = ProcessReporter("restore")
    
    # 使用还原模式（过滤参考文件夹）
    for json_path in walk_directory(TRANSLATED_DIR, mode="restore"):
        if json_path.suffix != '.json':
            continue
        
        # 开始新统计项
        reporter.start_new_file(json_path)
        
        try:
            # 获取原文件路径与输出路径（去除.json后缀）
            relative_path = json_path.relative_to(TRANSLATED_DIR)
            source_file = SOURCE_DIR / relative_path.with_suffix('')
            output_path = OUTPUT_DIR / relative_path.with_suffix('')
        
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
        
            # 根据文件类型选择还原方式
            restored = False
            if "lang" in str(json_path):
                output_path = OUTPUT_DIR / relative_path.with_suffix('')
                restore_lang_file(json_data, output_path)
                restored = True
            elif "lore" in str(json_path):
                output_path = OUTPUT_DIR / relative_path.with_suffix('')
                restore_lore_file(json_data, output_path)
                restored = True
            elif "speech" in str(json_path) or "names" in str(json_path):
                output_path = OUTPUT_DIR / relative_path.with_suffix('')
                restore_speech_file(json_data, output_path)
                restored = True
            elif "CustomNPCs" in str(json_path):
                output_path = OUTPUT_DIR / relative_path.with_suffix('')
                restore_customnpcs_file(json_data, output_path, source_file)
                restored = True
                
            # 记录统计
            if restored:
                reporter.record_success()
            else:
                reporter.record_warning(json_path)
        except Exception as e:
            print(f"处理文件{json_path}时发生错误：{str(e)}")
    
    reporter.final_report()  # 报告输出

# ======================
# 控制台信息统计与输出模块
# ======================
class ProcessReporter:
    def __init__(self, operation_type):
        self.operation_type = operation_type  # extract/restore
        self.last_group = None                # 上一个统计单元名称
        self.current_count = 0                # 当前统计单元计数
        self.total_files = 0                  # 总计文件数
        self.operation_map = {
            "extract": ("提取", "未提取到有效内容"),
            "restore": ("还原", "未还原有效内容")
        }

    def _get_group_name(self, file_path):
        """生成三级路径统计单元名称"""
        # 处理特殊文件夹
        if "其他语言参考" in str(file_path):
            return "其他语言参考文件"
        
        # 解析路径层级
        parts = []
        try:
            relative_path = file_path.relative_to(SOURCE_DIR if self.operation_type == "extract" else TRANSLATED_DIR)
            parts = list(relative_path.parent.parts)
        except ValueError:
            parts = list(file_path.parts)
        
        # 构建三级路径名称
        name_parts = []
        for i in range(min(3, len(parts))):
            name_parts.append(parts[i])
        
        return "-".join(name_parts) + "文件" if len(name_parts) > 0 else "根目录文件"

    def _flush_group(self):
        """输出当前统计单元结果"""
        if self.last_group and self.current_count > 0:
            action = self.operation_map[self.operation_type][0]
            print(f"{self.last_group}：已{action}完成，共{action}文件{self.current_count}个")
            self.total_files += self.current_count
            self.current_count = 0

    def start_new_file(self, file_path):
        """处理新文件时的统计逻辑"""
        current_group = self._get_group_name(file_path)
        
        # 检测到统计单元变化时输出结果
        if current_group != self.last_group:
            self._flush_group()
            self.last_group = current_group

    def record_success(self):
        """记录成功处理"""
        self.current_count += 1

    def record_warning(self, file_path):
        """记录警告信息"""
        action, warning = self.operation_map[self.operation_type]
        try:
            rel_path = file_path.relative_to(SOURCE_DIR if self.operation_type == "extract" else TRANSLATED_DIR)
        except ValueError:
            rel_path = file_path
        print(f"警告：{rel_path} {warning}")

    def final_report(self):
        """输出最终统计"""
        self._flush_group()  # 输出最后一个统计单元
        print(f"\n总计处理文件：{self.total_files}个")


# ======================
# 主程序入口
# ======================
if __name__ == "__main__":
    print("请选择操作模式：")
    print("1. 提取原文件到JSON")
    print("2. 还原JSON到原文件格式")
    choice = input("请输入数字选择(1/2): ")
    
    if choice == '1':
        source_to_json()
        print("提取完成！文件已保存到2-ConvertedParatranzFile")
    elif choice == '2':
        json_to_source()
        print("还原完成！文件已保存到4-SourceTranslatedFile")
    else:
        print("输入错误，请输入1或2")