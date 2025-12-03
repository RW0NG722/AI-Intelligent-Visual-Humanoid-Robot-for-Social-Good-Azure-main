import os
import time
import logging
import threading
import pygame
import wave
import numpy as np
import sounddevice as sd
from datetime import datetime
from scipy.io import wavfile

class PhoneMode:
    def __init__(self, socketio, chatbot, transcribe_func, tts_func, save_message_func, 
                should_trigger_vision_func=None, analyze_frame_func=None):
        self.socketio = socketio
        self.chatbot = chatbot
        self.transcribe_func = transcribe_func
        self.tts_func = tts_func
        self.save_message_func = save_message_func
        self.should_trigger_vision = should_trigger_vision_func
        self.analyze_frame = analyze_frame_func
        self.active = False
        self.is_recording = False
        self.recording_thread = None
        self.audio_file = "uploads/phone_mode_audio.wav"
        self.start_beep = "static/start_beep.wav"
        self.stop_beep = "static/stop_beep.wav"
    
    def start(self):
        """啟動電話模式"""
        if self.active:
            return False
            
        self.active = True
        return self._start_recording_cycle()
    
    def stop(self):
        """停止電話模式"""
        self.active = False
        self._ensure_beep_files()
        self._play_beep(self.stop_beep)  # 播放結束提示音
        return True
    
    def _ensure_beep_files(self):
        """確保提示音文件存在"""
        for beep_file in [self.start_beep, self.stop_beep]:
            if not os.path.exists(beep_file):
                logging.warning(f"提示音文件不存在: {beep_file}")
                return False
        return True
        
    def _play_beep(self, beep_file):
        """播放提示音"""
        try:
            if not os.path.exists(beep_file):
                logging.warning(f"提示音文件不存在: {beep_file}")
                return
                
            # 通知前端播放音頻
            self.socketio.emit('play_audio', {'audio_file': f'/{beep_file}'})
            
            # 本地也播放提示音
            pygame.mixer.Sound(beep_file).play()
            
            logging.info(f"播放提示音: {beep_file}")
        except Exception as e:
            logging.error(f"播放提示音失敗: {e}")
    
    def _start_recording_cycle(self):
        """開始錄音循環"""
        if not self._ensure_beep_files():
            return False
            
        # 播放開始提示音
        self._play_beep(self.start_beep)
        
        # 啟動錄音線程
        self.recording_thread = threading.Thread(target=self._recording_worker)
        self.recording_thread.daemon = True
        self.recording_thread.start()
        
        return True
    
    def _recording_worker(self):
        """錄音工作線程"""
        import sounddevice as sd
        import numpy as np
        import wave
        import webrtcvad
        from scipy.io import wavfile
        
        # 創建保存目錄
        os.makedirs("uploads", exist_ok=True)
        
        # 設置錄音參數
        duration = 60  # 最長錄音時間（秒）
        fs = 16000     # 採樣率
        channels = 1   # 單聲道
        
        # 初始化VAD
        vad = webrtcvad.Vad()
        vad.set_mode(3)  # 設置為最敏感模式
        
        chunk_duration = 0.02  # 20ms chunks for VAD
        chunk_samples = int(fs * chunk_duration)
        
        # 開始錄音
        self.is_recording = True
        
        logging.info("開始電話模式錄音...")
        
        frames = []
        silent_chunks = 0
        speech_detected = False
        max_silent_chunks = int(5 / chunk_duration)   # 5秒靜音後結束 (已檢測到語音)
        max_wait_chunks = int(10 / chunk_duration)    # 10秒等待 (未檢測到語音)
        total_chunks = 0
        
        try:
            # 開始錄音
            audio_data = sd.rec(int(duration * fs), samplerate=fs, channels=channels, dtype=np.int16)
            
            # 每隔一小段時間檢查是否有語音
            for i in range(int(duration / chunk_duration)):
                if not self.active or total_chunks >= int(duration / chunk_duration):
                    break
                    
                time.sleep(chunk_duration)
                total_chunks += 1
                
                # 獲取當前錄音的這一小段
                if i * chunk_samples < len(audio_data):
                    current_chunk = audio_data[i*chunk_samples:min((i+1)*chunk_samples, len(audio_data))]
                    
                    # 轉換為bytes用於VAD
                    chunk_bytes = current_chunk.tobytes()
                    
                    # 檢測是否有語音
                    try:
                        is_speech = vad.is_speech(chunk_bytes, fs)
                    except Exception:
                        is_speech = False
                    
                    if is_speech:
                        silent_chunks = 0
                        speech_detected = True
                        frames.append(current_chunk.copy())
                    else:
                        silent_chunks += 1
                        if speech_detected:  # 如果之前檢測到過語音，也保存靜音片段
                            frames.append(current_chunk.copy())
                    
                    # 如果檢測到語音後有足夠長的靜音，結束錄音
                    if speech_detected and silent_chunks >= max_silent_chunks:
                        logging.info("檢測到5秒靜音，結束錄音")
                        break
                    
                    # 如果等待太久沒有檢測到語音，也結束錄音
                    if not speech_detected and total_chunks >= max_wait_chunks:
                        logging.info("10秒內未檢測到語音，結束錄音")
                        break
            
            # 停止錄音
            sd.stop()
            
            # 播放結束提示音
            self._play_beep(self.stop_beep)
            
            # 如果沒有檢測到語音或幀數太少，視為無效錄音
            if not speech_detected or len(frames) < 10:
                logging.info("未檢測到有效語音，重新開始錄音循環")
                self.is_recording = False
                
                # 如果電話模式仍然活躍，開始新的錄音循環
                if self.active:
                    time.sleep(1)  # 等待一秒
                    self._start_recording_cycle()
                return
            
            # 保存錄音
            if frames:
                combined_frames = np.vstack(frames) if len(frames) > 1 else frames[0]
                wavfile.write(self.audio_file, fs, combined_frames)
                logging.info(f"已保存錄音: {self.audio_file}")
                
                # 處理錄音
                self._process_recording()
            
        except Exception as e:
            logging.error(f"錄音過程中出錯: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.is_recording = False

    def _process_recording(self):
        """處理錄音文件"""
        try:
            # 檢查文件是否存在
            if not os.path.exists(self.audio_file):
                logging.error(f"錄音文件不存在: {self.audio_file}")
                return
                    
            # 通知前端檢測到語音
            self.socketio.emit('phone_mode_speech_detected')
                
            # 轉錄語音
            transcribed_text = self.transcribe_func(self.audio_file)
                
            if not transcribed_text:
                logging.warning("無法識別語音內容")
                # 如果電話模式仍然活躍，開始新的錄音循環
                if self.active:
                    self._start_recording_cycle()
                return
                        
            logging.info(f"識別到語音: {transcribed_text}")
            
            # 保存用戶消息
            user_message = {
                "type": "sent",
                "text": f"📞 {transcribed_text}",
                "timestamp": datetime.now().isoformat(),
                "audioSrc": None
            }
            self.save_message_func(user_message)
            
            # 檢查是否需要觸發 AI Vision 分析
            if self.should_trigger_vision and self.should_trigger_vision(transcribed_text):
                logging.info("觸發 AI Vision 分析")
                if self.analyze_frame:
                    # 傳遞 socketio 實例
                    self.analyze_frame(self.socketio)
                
                # 等待一段時間後再開始新的錄音循環
                time.sleep(5)  # 等待 5 秒
                if self.active:
                    self._start_recording_cycle()
                return
            
            # 獲取AI回應
            ai_response = self.chatbot.get_response(transcribed_text)
            
            # 生成語音
            tts_file = self.tts_func(ai_response)
            
            # 保存AI回應
            ai_message = {
                "type": "received",
                "text": f"📞 {ai_response}",
                "timestamp": datetime.now().isoformat(),
                "audioSrc": tts_file
            }
            self.save_message_func(ai_message)
            
            # 發送回應到前端
            self.socketio.emit('phone_mode_response', {
                "text": ai_response,
                "audio_file": tts_file
            })
            
            # 計算TTS文件長度並增加額外等待時間
            extra_wait_time = 5  # 播放完TTS後的額外等待時間（秒）
            
            if tts_file:
                # 移除开头的斜杠以避免路径重复
                file_path = tts_file.lstrip('/')
                
                if os.path.exists(file_path):
                    # 使用wave模块读取音频文件时长
                    try:
                        with wave.open(file_path, 'rb') as wf:
                            # 计算音频长度（秒）
                            tts_duration = wf.getnframes() / wf.getframerate()
                            total_wait = tts_duration + extra_wait_time
                            logging.info(f"TTS時長: {tts_duration:.2f}秒，總等待時間: {total_wait:.2f}秒")
                            time.sleep(total_wait)
                    except Exception as e:
                        # 如果读取文件时出错，记录错误并使用预设等待时间
                        logging.error(f"讀取TTS文件時出錯: {e}")
                        default_wait = 10
                        logging.info(f"使用預設等待時間: {default_wait}秒")
                        time.sleep(default_wait)
                else:
                    # 如果文件不存在，记录错误并使用预设等待时间
                    logging.warning(f"TTS文件不存在: {file_path}")
                    default_wait = 10
                    logging.info(f"使用預設等待時間: {default_wait}秒")
                    time.sleep(default_wait)
            else:
                # 如果没有TTS文件路径，使用预设等待时间
                default_wait = 10
                logging.info(f"無TTS文件路徑，使用預設等待時間: {default_wait}秒")
                time.sleep(default_wait)
            
            # 如果電話模式仍然活躍，開始新的錄音循環
            if self.active:
                self._start_recording_cycle()
                
        except Exception as e:
            logging.error(f"處理錄音時出錯: {e}")
            import traceback
            traceback.print_exc()
            
            # 如果電話模式仍然活躍，嘗試開始新的錄音循環
            if self.active:
                time.sleep(2)  # 等待2秒
                self._start_recording_cycle()