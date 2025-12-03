import random
import subprocess
import threading
import time
import pygame



class CustomActions:
   def __init__(self):
       self.actions = {
           "跳舞": self.random_dance,
           "詠春": self.wing_chun,
       }
       
       # 定義每個動作所需時間(秒)
       self.action_durations = {
           # 基本動作
           "0": 2,    # 立正
           "1": 3,    # 前進
           "2": 3,    # 後退
           "3": 3,    # 左移
           "4": 3,    # 右移
           "7": 3,  # 左轉
           "8": 3,  # 右轉
           "9": 3,    # 揮手
           
           # 表演動作
           "10": 3,   # 鞠躬
           "12": 5,   # 慶祝
           "22": 5,   # 扭腰
           "24": 3,   # 踏步
           
           # 運動動作
           "13": 3,   # 左腳踢
           "14": 3,   # 右腳踢
           "15": 5,   # 詠春
           "16": 3,   # 左勾拳
           "17": 3,   # 右勾拳
       }

       # 定義舞蹈組合
       self.dance_moves = {
           "活力小跳舞": [("9", 1, 0.5), ("24", 1, 0), ("16", 1, 0.5), ("17", 1, 0.5), ("22", 1, 0)],
           "左右搖擺舞": [("3", 1, 0), ("4", 1, 0), ("13", 1, 0.5), ("14", 1, 0.5), ("9", 1, 0)],
           "歡樂節拍舞": [("9", 1, 0.5), ("7", 1, 0), ("8", 1, 0), ("22", 1, 0), ("10", 1, 1)],
       }
       
       self.dance_music = {
           "活力小跳舞": "dance1.mp3",
           "左右搖擺舞": "dance2.mp3",
           "歡樂節拍舞": "dance3.mp3",
       }

   def execute_single_digit(self, action_id, repeat=1):
       """執行單位數動作(0-9)"""
       curl_command = [
           "curl", "-X", "POST", "http://192.168.149.1:9030/",
           "-H", "deviceid: your_device_id",
           "-H", "X-JSON-RPC: RunAction",
           "-H", "er: false", "-H", "dr: false",
           "-H", "Content-Type: text/x-markdown; charset=utf-8",
           "-H", "Content-Length: 76",
           "-H", "Connection: Keep-Alive",
           "-H", "Accept-Encoding: gzip",
           "-H", "User-Agent: okhttp/4.9.1",
           "-d", f'{{"id":1732853986186,"jsonrpc":"2.0","method":"RunAction","params":["{action_id}","{repeat}"]}}'
       ]
       try:
           subprocess.run(curl_command)
           print(f"執行單位數動作: {action_id}, 重複{repeat}次")
       except Exception as e:
           print(f"執行動作失敗: {e}")

   def execute_double_digit(self, action_id, repeat=1):
       """執行雙位數動作(10-99)"""
       curl_command = [
           "curl", "-X", "POST", "http://192.168.149.1:9030/",
           "-H", "deviceid: your_device_id",
           "-H", "X-JSON-RPC: RunAction",
           "-H", "er: false", "-H", "dr: false",
           "-H", "Content-Type: text/x-markdown; charset=utf-8",
           "-H", "Content-Length: 77",
           "-H", "Connection: Keep-Alive",
           "-H", "Accept-Encoding: gzip",
           "-H", "User-Agent: okhttp/4.9.1",
           "-d", f'{{"id":1732853986186,"jsonrpc":"2.0","method":"RunAction","params":["{action_id}","{repeat}"]}}'
       ]
       try:
           subprocess.run(curl_command)
           print(f"執行雙位數動作: {action_id}, 重複{repeat}次")
       except Exception as e:
           print(f"執行動作失敗: {e}")

   def execute_action(self, action_id, repeat=1):
       """根據動作ID長度調用對應執行方法"""
       if len(action_id) == 1:
           self.execute_single_digit(action_id, repeat)
       else:
           self.execute_double_digit(action_id, repeat)

   def get_action_duration(self, action_id, repeat=1):
       """計算動作實際所需時間"""
       base_duration = self.action_durations.get(action_id, 2)  # 預設2秒
       return (base_duration * repeat) + 1  # 所有動作+2秒安全時間


   def random_dance(self):
        """隨機選擇一個舞蹈表演"""
        dance_name = random.choice(list(self.dance_moves.keys()))
        dance_sequence = self.dance_moves[dance_name]
        music_file = self.dance_music[dance_name]
        
        print(f"開始表演: {dance_name}")
        
        # 开始播放音乐
        music_thread = threading.Thread(target=self.play_music, args=(music_file,))
        music_thread.start()
        
        # 这里已经不需要单独发送"我开始跳舞了"的消息，因为在调用此方法前已经发送了
        # 在get_response中我们已经提前返回了"我开始跳舞了"的消息
        
        # 執行動作序列
        for action_id, repeat, extra_wait in dance_sequence:
            # 執行動作
            self.execute_action(action_id, repeat)
            # 等待動作完成 + 額外等待時間
            action_time = self.get_action_duration(action_id, repeat)
            total_wait = action_time + extra_wait
            time.sleep(total_wait)
   
   def wing_chun(self):
       """詠春組合技"""
       moves = [
           # [動作ID, 重複次數, 額外等待時間]
           ("15", 1, 0.5),  # 詠春基本動作
           ("16", 2, 0),    # 左勾拳
           ("17", 2, 0),    # 右勾拳
           ("13", 1, 0.5),  # 左腳踢
           ("14", 1, 0),    # 右腳踢
       ]

       for action_id, repeat, extra_wait in moves:
           self.execute_action(action_id, repeat)
           action_time = self.get_action_duration(action_id, repeat)
           total_wait = action_time + extra_wait
           time.sleep(total_wait)

   def handle_command(self, text):
       """處理命令"""
       for keyword, action in self.actions.items():
           if keyword in text:
               action()
               return True
       return False
    
   def play_music(self, music_file):
        """播放音樂"""
        try:
            pygame.mixer.init()
            pygame.mixer.music.load(f"static/music/{music_file}")
            pygame.mixer.music.play()
            print(f"播放音樂: {music_file}")
        except Exception as e:
            print(f"播放音樂失敗: {e}")