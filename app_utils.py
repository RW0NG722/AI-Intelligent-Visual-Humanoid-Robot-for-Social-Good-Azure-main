import os
import time
import json
import logging
from datetime import datetime

# 聊天歷史文件路徑 (從主應用共享)
CHAT_HISTORY_FILE = "chat_history.json"
MAX_HISTORY_ENTRIES = 15

# 全局变量
chat_history = {"messages": []}

def initialize_chat_history():
    """初始化聊天歷史紀錄"""
    global chat_history
    
    if os.path.exists(CHAT_HISTORY_FILE):
        try:
            with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                chat_history = json.load(f)
                
            # 檢查是否需要清除過期記錄 (24小時)
            if is_history_outdated():
                chat_history = {"messages": []}
                try:
                    os.remove(CHAT_HISTORY_FILE)
                except:
                    logging.warning("無法刪除過期的聊天歷史文件")
                    
        except Exception as e:
            logging.error(f"讀取聊天歷史記錄時出錯: {e}")
            chat_history = {"messages": []}
    else:
        chat_history = {"messages": []}

def is_history_outdated():
    """檢查聊天歷史是否過期 (24小時)"""
    if not os.path.exists(CHAT_HISTORY_FILE):
        return False
    
    file_time = os.path.getmtime(CHAT_HISTORY_FILE)
    current_time = time.time()
    hours_passed = (current_time - file_time) / 3600
    
    return hours_passed > 24

def save_chat_message(message_entry):
    """添加一條消息到聊天歷史紀錄並保存"""
    global chat_history
    
    # 添加新消息
    chat_history["messages"].append(message_entry)
    
    # 如果超過最大條目數，移除最早的消息
    if len(chat_history["messages"]) > MAX_HISTORY_ENTRIES:
        chat_history["messages"] = chat_history["messages"][-MAX_HISTORY_ENTRIES:]
    
    # 保存到文件
    try:
        with open(CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(chat_history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"保存聊天歷史紀錄時發生錯誤: {e}")

def save_audio_file(filename, content):
    """保存音频文件"""
    filepath = os.path.join("uploads", filename)
    os.makedirs("uploads", exist_ok=True)
    with open(filepath, 'wb') as f:
        f.write(content)
    logging.info(f"音频文件已保存: {filepath}")
    return filepath

def format_timestamp(timestamp):
    """将时间戳格式化为可读格式"""
    try:
        dt = datetime.fromisoformat(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return timestamp

def ensure_directories():
    """确保必要的目录存在"""
    directories = ["uploads", "static/uploads", "static/uploads/test"]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
    
    logging.info("已确保必要目录存在")

def clean_old_files(directory, max_age_hours=24):
    """清理指定目录中超过指定时间的文件"""
    try:
        if not os.path.exists(directory):
            return
            
        current_time = time.time()
        count = 0
        
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath):
                file_time = os.path.getmtime(filepath)
                hours_passed = (current_time - file_time) / 3600
                
                if hours_passed > max_age_hours:
                    os.remove(filepath)
                    count += 1
        
        if count > 0:
            logging.info(f"已清理 {count} 个过期文件 (超过 {max_age_hours} 小时)")
    except Exception as e:
        logging.error(f"清理文件时出错: {e}")

def load_json_file(file_path, default=None):
    """加载 JSON 文件，如果文件不存在或加载失败则返回默认值"""
    if default is None:
        default = {}
        
    try:
        if not os.path.exists(file_path):
            return default
            
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"加载 JSON 文件 {file_path} 时出错: {e}")
        return default

def save_json_file(file_path, data):
    """保存数据到 JSON 文件"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logging.error(f"保存 JSON 文件 {file_path} 时出错: {e}")
        return False
        
def create_backup(file_path):
    """创建文件备份"""
    if not os.path.exists(file_path):
        return False
        
    try:
        backup_path = f"{file_path}.bak"
        with open(file_path, 'rb') as src:
            with open(backup_path, 'wb') as dst:
                dst.write(src.read())
        return True
    except Exception as e:
        logging.error(f"创建备份文件时出错: {e}")
        return False