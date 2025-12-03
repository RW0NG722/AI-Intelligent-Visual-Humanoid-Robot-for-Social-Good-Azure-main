import os
import random
from typing import List
from langchain_openai import AzureChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferWindowMemory
from langchain.chains import ConversationChain
from langchain.schema import BaseMessage
from langchain.chains import LLMChain
from azure.cognitiveservices.speech import SpeechConfig, SpeechSynthesizer, AudioConfig, ResultReason
from datetime import datetime
from queue import Queue, Empty
from threading import Thread
from time import sleep
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed
from tenacity import wait_exponential
import config
import json
import re
import subprocess
import traceback
import time
from custom_actions import CustomActions
from google_search import GoogleSearch
import threading

class ChatBot:
    def __init__(self):
        # 設置環境變量
        os.environ["OPENAI_API_KEY"] = config.AZURE_OPENAI_API_KEY
        os.environ["OPENAI_API_BASE"] = config.AZURE_OPENAI_ENDPOINT
        os.environ["OPENAI_API_VERSION"] = config.AZURE_OPENAI_API_VERSION

        self.action_delays = {
            "single": 4.0,  # 單位數動作等待時間
            "double": 4.0   # 雙位數動作等待時間
        }

        # 初始化工具類
        self.custom_actions = CustomActions()
        self.google_search = GoogleSearch()
        self.action_queue = Queue()
        self.should_stop = False
        self.action_thread = Thread(target=self._action_worker)
        self.action_thread.daemon = True  # 設為守護線程
        self.action_thread.start()
        
        # 加載知識庫
        self.load_knowledge_base()
        
        # 初始化 LangChain 組件
        self.setup_langchain()

    def _action_worker(self):
        """處理動作隊列的工作線程"""
        while not self.should_stop:
            try:
                action = self.action_queue.get(timeout=1)
                if action is None:
                    continue
                    
                action_type, action_id, repeat_count = action
                try:
                    # 根據動作類型選擇不同的發送方式
                    if action_type == "single":
                        curl_command = [
                            "curl",
                            "-X", "POST", "http://192.168.149.1:9030/",
                            "-H", "deviceid: your_device_id",
                            "-H", "X-JSON-RPC: RunAction",
                            "-H", "er: false",
                            "-H", "dr: false",
                            "-H", "Content-Type: text/x-markdown; charset=utf-8",
                            "-H", "Content-Length: 76",
                            "-H", "Connection: Keep-Alive",
                            "-H", "Accept-Encoding: gzip",
                            "-H", "User-Agent: okhttp/4.9.1",
                            "-d", f'{{"id":1732853986186,"jsonrpc":"2.0","method":"RunAction","params":["{action_id}","{repeat_count}"]}}'
                        ]
                        wait_time = self.action_delays["single"]
                    else:
                        curl_command = [
                            "curl",
                            "-X", "POST", "http://192.168.149.1:9030/",
                            "-H", "deviceid: your_device_id",
                            "-H", "X-JSON-RPC: RunAction",
                            "-H", "er: false",
                            "-H", "dr: false",
                            "-H", "Content-Type: text/x-markdown; charset=utf-8",
                            "-H", "Content-Length: 77",
                            "-H", "Connection: Keep-Alive",
                            "-H", "Accept-Encoding: gzip",
                            "-H", "User-Agent: okhttp/4.9.1",
                            "-d", f'{{"id":1732853986186,"jsonrpc":"2.0","method":"RunAction","params":["{action_id}","{repeat_count}"]}}'
                        ]
                        wait_time = self.action_delays["double"]

                    # 執行指令
                    print(f"🖨 正在執行 curl 指令：\n{' '.join(curl_command)}")
                    result = subprocess.run(curl_command, capture_output=True, text=True)
                    
                    # 顯示執行結果
                    print(f"🔍 Curl 命令結果: {result.stdout}")
                    print(f"⚠️  錯誤輸出: {result.stderr}")
                    
                    if result.returncode == 0:
                        print(f"✅ 成功執行 {'單位數' if action_type == 'single' else '雙位數'} "
                            f"動作 {action_id}，重複 {repeat_count} 次")
                    else:
                        print("❌ curl 執行失敗")
                    
                    # 等待指定時間
                    sleep(wait_time)
                    
                except Exception as e:
                    print(f"❌ 執行動作失敗: {str(e)}")
                    
            except Empty:
                continue
            except Exception as e:
                print(f"工作線程出錯：{str(e)}")

    def stop_all_actions(self):
        """停止所有動作"""
        while not self.action_queue.empty():
            try:
                self.action_queue.get_nowait()
            except Empty:
                break
        return "已停止所有動作"
    
    def get_queue_status(self):
        """獲取當前隊列狀態"""
        return f"隊列中還有 {self.action_queue.qsize()} 個動作待執行"

    def cleanup(self):
        """清理資源"""
        self.should_stop = True
        # 清空隊列
        self.stop_all_actions()
        # 等待工作線程結束
        if hasattr(self, 'action_thread'):
            self.action_thread.join(timeout=2)
        # 清除記憶
        self.clear_memory()

    def __del__(self):
        """析構函數"""
        self.cleanup()

    def load_knowledge_base(self):
        """加載知識庫數據"""
        with open("knowledge_base.json", "r", encoding="utf-8") as file:
            self.knowledge_base = json.load(file)
            self.single_digit_actions = self.knowledge_base["actions"]["single_digit"]
            self.double_digit_actions = self.knowledge_base["actions"]["double_digit"]
            self.number_mapping = {
                **self.knowledge_base["number_mapping"]["traditional"],
                **self.knowledge_base["number_mapping"]["simplified"],
                **self.knowledge_base["number_mapping"]["cantonese"],
                **self.knowledge_base["number_mapping"]["english"]
            }

    def setup_langchain(self):
        """設置 LangChain 組件"""
        try:
            self.llm = AzureChatOpenAI(
                azure_deployment=config.AZURE_OPENAI_DEPLOYMENT_NAME,
                model_name="gpt-4",
                temperature=0.3,
                max_tokens=500,
                azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
                api_key=config.AZURE_OPENAI_API_KEY,
                api_version=config.AZURE_OPENAI_API_VERSION,
                request_timeout=15,  # 增加超時時間
                max_retries=3        # 減少重試次數
            )
            # 縮短記憶長度以減少 token 使用
            self.memory = ConversationBufferWindowMemory(
                return_messages=True,
                memory_key="chat_history",
                input_key="input",
                k=5
            )

            self.prompt = PromptTemplate(
                input_variables=["chat_history", "input"],
                template="""
                你是 Raspberry，VTC 學生開發的助手。請使用繁體中文、廣東話回應。
                不要說自己是虛擬助手或無法執行動作。
                
                過往對話：
                {chat_history}
                
                用戶輸入：{input}
                回應："""
            )

            # 設置對話鏈
            self.conversation = ConversationChain(
                llm=self.llm,
                memory=self.memory,
                prompt=self.prompt,
                verbose=False
            )

        except Exception as e:
            print(f"LLM 設置失敗：{e}")

    @retry(
        stop=stop_after_attempt(2),  # 最多重試 2 次
        wait=wait_exponential(multiplier=1, min=5, max=10),  # 最多等 10 秒
        retry=retry_if_exception_type(Exception)
    )
    def ask_gpt_direct(self, user_input):
        """直接使用 GPT 回應用戶問題"""
        try:
            # **避免過多請求，每次請求間隔 10 秒**
            time.sleep(10)  # <-- 讓每個 GPT 請求之間間隔至少 10 秒
            response = self.conversation.predict(input=user_input)
            return response
        except Exception as e:
            print(f"GPT 調用失敗：{e}")
            raise  # 讓 retry 裝飾器捕獲異常並重試

    def _predict_with_retry(self, user_input):
        return self.conversation.predict(input=user_input)
            
    def get_memory_content(self) -> List[BaseMessage]:
        """獲取當前記憶內容"""
        return self.memory.chat_memory.messages

    def clear_memory(self):
        """清除所有對話記憶"""
        self.memory.clear()

    def show_memory_status(self):
        """顯示當前記憶狀態"""
        messages = self.get_memory_content()
        print(f"當前記憶中的對話數量: {len(messages)//2}")  # 除以2是因為每輪對話包含問題和回答
        for i, msg in enumerate(messages):
            print(f"Message {i+1}: {msg.content[:50]}..." if len(msg.content) > 50 else f"Message {i+1}: {msg.content}")

    def extract_number(self, text):
        """從文字中提取次數"""
        # 先嘗試提取阿拉伯數字
        arabic_numbers = re.findall(r'\d+', text)
        if arabic_numbers:
            return int(arabic_numbers[0])
        
        # 嘗試提取中文數字
        for character, value in self.number_mapping.items():
            if character in text:
                return value
                
        return 1  # 預設為 1

    def execute_single_digit_action(self, action_id, repeat_count):
        """執行單位數動作"""
        try:
            print("[机器人动作触发]")
            print(f"➡️ 动作: {action_id}")
            print(f"➡️ 重复次数: {repeat_count}")
            
            # 確保 repeat_count 是整數
            repeat_count = int(repeat_count) if isinstance(repeat_count, str) else repeat_count
            
            # 加入隊列
            self.action_queue.put(("single", action_id, min(repeat_count, 10)))
            
            # 顯示 curl 指令
            print(f"🖨 已將動作加入隊列")
            
            return f"好的，我會向{self.get_action_name(action_id)}，重複{min(repeat_count, 10)}次"
            
        except Exception as e:
            print(f"❌ 發送指令失敗: {str(e)}")
            return "抱歉，執行動作時出現問題。"

    def execute_double_digit_action(self, action_id, repeat_count):
        """執行單位數動作"""
        try:
            print("[机器人动作触发]")
            print(f"➡️ 动作: {action_id}")
            print(f"➡️ 重复次数: {repeat_count}")
            
            # 確保 repeat_count 是整數
            repeat_count = int(repeat_count) if isinstance(repeat_count, str) else repeat_count
            
            # 加入隊列
            self.action_queue.put(("double", action_id, min(repeat_count, 10)))
            
            # 顯示 curl 指令
            print(f"🖨 已將動作加入隊列")
            
            return f"好的，我會向{self.get_action_name(action_id)}，重複{min(repeat_count, 10)}次"
            
        except Exception as e:
            print(f"❌ 發送指令失敗: {str(e)}")
            return "抱歉，執行動作時出現問題。"
            
    def get_action_name(self, action_id):
        """根據動作 ID 獲取動作名稱"""
        # 反向查找動作名稱
        for actions in [self.single_digit_actions, self.double_digit_actions]:
            for name, aid in actions.items():
                if aid == action_id:
                    return name
        return f"動作{action_id}"
            

    def handle_google_search(self, user_input):
        """處理 Google 搜索"""
        search_results = self.google_search.search(user_input)
        if not search_results or search_results[0].startswith("查詢失敗"):
            return "抱歉，我未能找到相關資訊。"

        # 使用 LangChain 總結搜索結果
        summary_prompt = f"""
        基於以下搜索結果：
        {search_results}
        
        請用3-4個簡短的句子總結主要信息。注意保持友善的語氣，並確保信息準確完整。
        """
        
        response = self.conversation.predict(
            input=summary_prompt,
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        return response

    def query_knowledge_base(self, query):
        """查詢知識庫"""
        # 檢查一般問答
        for question, answer in self.knowledge_base["general_qa"].items():
            if query in question or question in query:
                return answer
        return None
    
    def _perform_random_small_action(self):
        """在普通聊天时随机执行小动作"""
        # 控制随机动作触发概率 (60%)
        if random.random() < 0.6:
            # 小动作列表 (只选择短时间的简单动作)
            small_actions = [
                # 单位数动作
                ('0', '1'),  # 立正
                ('7', '1'),  # 左转
                ('8', '1'),  # 右转
                ('9', '1'),  # 挥手
                # 短时间的双位数动作
                ('10', '1'),  # 鞠躬
                ('16', '1'),  # 左勾拳
                ('17', '1'),  # 右勾拳
                ('24', '1')   # 踏步
            ]
            
            # 随机选择1-3个动作
            num_actions = random.randint(1, 1)
            selected_actions = random.sample(small_actions, min(num_actions, len(small_actions)))
            
            print(f"[DEBUG] 随机执行 {num_actions} 个小动作")
            
            # 执行选中的动作
            for action in selected_actions:
                action_id, repeat_count = action
                if len(action_id) == 1:
                    self.execute_single_digit_action(action_id, repeat_count)
                else:
                    self.execute_double_digit_action(action_id, repeat_count)
                # 添加短暂延迟，避免动作之间冲突
                time.sleep(1)
                
    def get_response(self, user_input):
        """生成对话回应并控制机器人动作"""
        
        try:
            # 只保留最後一輪對話作為上下文
            if len(self.memory.chat_memory.messages) > 4:  # 2輪對話 = 4條消息
                self.memory.chat_memory.messages = self.memory.chat_memory.messages[-4:]

            # 检查问候语，如果是问候类型的输入，生成回应并执行挥手动作
            greetings = ["你好", "哈囉", "hi", "hello", "早晨", "午安", "晚安", "早上好", "下午好", "晚上好", "打招呼"]
            is_greeting = any(greeting in user_input.lower() for greeting in greetings)
            
            # **1️⃣ 先檢查本地知識庫**
            response = self.query_knowledge_base(user_input)
            if response:
                # 如果是问候语，在回应后执行挥手
                if is_greeting:
                    print("[DEBUG] 检测到问候语，执行挥手动作")
                    self.execute_single_digit_action('9', '1')
                return response  # **直接返回知識庫內的回答**
                    
            # **2️⃣ 如果用戶說「跳舞」，執行 `random_dance()`**
            if "跳舞" in user_input or "dance" in user_input:
                print("[DEBUG] 檢測到 '跳舞' 指令")
                # 先发送回应，再执行动作
                ai_response = "好的，我開始跳舞了！💃🎵"
                # 异步执行舞蹈动作，这样可以先返回回应，然后机器人才开始跳舞
                threading.Thread(target=self.custom_actions.random_dance).start()
                return ai_response

            # **2️⃣ 檢查單位數動作**
            for command, action_id in self.single_digit_actions.items():
                if command in user_input:
                    repeat_count = self.extract_number(user_input)
                    print("[DEBUG] 檢測到單位數動作:", command)
                    return self.execute_single_digit_action(action_id, repeat_count)

            # **3️⃣ 檢查雙位數動作**
            for command, action_id in self.double_digit_actions.items():
                if command in user_input:
                    repeat_count = self.extract_number(user_input)
                    print("[DEBUG] 檢測到雙位數動作:", command)
                    return self.execute_double_digit_action(action_id, repeat_count)

            # **4️⃣ 檢查是否為斜槓命令**
            if user_input.startswith("/"):
                if user_input.lower() in ["/stop", "停止"]:
                    return self.stop_all_actions()
                elif user_input.lower() in ["/status", "狀態"]:
                    return self.get_queue_status()
                elif user_input.lower() in ["/clear", "清除記憶"]:
                    self.clear_memory()
                    return "已清除對話記憶"
                
                command_response = self.command_parser.parse_command(user_input)
                if command_response and "無法解析的指令" not in command_response:
                    return command_response

            # **5️⃣ 檢查 Google 搜索**
            if "天氣" in user_input or "新聞" in user_input:
                return self.handle_google_search(user_input)

            # **6️⃣ 處理日期相關問題**
            if "日期" in user_input or "今天" in user_input:
                current_date = datetime.now().strftime("%Y年%m月%d日")
                return f"今天是 {current_date}。"

            # **7️⃣ 使用 GPT 回應**
            response = self.ask_gpt_direct(user_input)
            
            # 如果是问候语，执行挥手动作
            if is_greeting:
                print("[DEBUG] 检测到问候语，执行挥手动作")
                self.execute_single_digit_action('9', '1')
            else:
                # 随机执行小动作（非问候时）
                self._perform_random_small_action()
                
            return response

        except Exception as e:
            print(f"錯誤處理用戶輸入時發生問題：{e}")
            return "抱歉，我無法處理您的請求。"

    def check_knowledge_base_actions(self, user_input):
        try:
            print(f"[DEBUG] 檢查知識庫動作，輸入: {user_input}")
            
            for category, mappings in self.knowledge_base.get('actions', {}).items():
                for trigger, details in mappings.items():
                    if trigger in user_input:
                        print(f"[DEBUG] 找到匹配: {trigger}")
                        
                        # 選擇響應
                        text_responses = details.get('text_responses', [])
                        text_response = text_responses[0] if text_responses else "你好！"
                        print(f"[DEBUG] 選擇響應: {text_response}")

                        # 優先生成 TTS
                        tts_file = self.generate_tts(text_response)
                        
                        # 然後執行動作
                        for action in details.get('actions', []):
                            try:
                                print(f"[DEBUG] 執行動作: {action}")
                                if action['type'] == 'single_digit':
                                    self.execute_single_digit_action(
                                        action['id'], 
                                        action.get('repeat', 1)
                                    )
                                elif action['type'] == 'double_digit':
                                    self.execute_double_digit_action(
                                        action['id'], 
                                        action.get('repeat', 1)
                                    )
                            except Exception as e:
                                print(f"[ERROR] 執行動作失敗: {e}")

                        return text_response

            # 如果沒有找到特殊響應，使用 LLM
            response = self.conversation.predict(input=user_input)
            print(f"[DEBUG] LLM 回應: {response}")
            return response

        except Exception as e:
            print(f"[ERROR] check_knowledge_base_actions() 出錯: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
        
    def generate_tts(self, text):
        """生成 TTS 音頻"""
        output_file = "static/response.wav"
        
        # 如果存在舊的文件就刪除
        if os.path.exists(output_file):
            try:
                os.remove(output_file)
            except Exception as e:
                print(f"[ERROR] 刪除舊 TTS 文件時出錯: {e}")

        try:
            speech_config = SpeechConfig(
                subscription=config.AZURE_SPEECH_API_KEY, 
                region=config.AZURE_SPEECH_REGION
            )
            speech_config.speech_synthesis_voice_name = "zh-HK-WanLungNeural"
            audio_config = AudioConfig(filename=output_file)
            synthesizer = SpeechSynthesizer(
                speech_config=speech_config, audio_config=audio_config)

            result = synthesizer.speak_text_async(text).get()

            if result.reason == ResultReason.SynthesizingAudioCompleted:
                print(f"[INFO] TTS 文件生成成功: {output_file}")
                return f"/{output_file}"
            else:
                print(f"[ERROR] TTS 生成失敗: {result.reason}")
                return None
        except Exception as e:
            print(f"[ERROR] 生成 TTS 時出錯: {e}")
            return None