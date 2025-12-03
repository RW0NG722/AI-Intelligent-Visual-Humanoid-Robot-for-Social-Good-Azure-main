import pyaudio
import wave
import numpy as np
import os
import time
import threading
import webrtcvad
from scipy.io import wavfile

class PCRecorder:
    def __init__(self):
        self.is_recording = False
        self.output_file = "uploads/phone_mode_audio.wav"
        self.chunk = 320
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        self.frames = []
        self.recording_thread = None
        self.vad = webrtcvad.Vad(3)  # 設置VAD敏感度為3（最高）
        self.debug = True
        
    def start_recording(self):
        """開始錄音"""
        # 確保目錄存在
        os.makedirs("uploads", exist_ok=True)
        
        # 如果已經在錄音，先停止
        if self.is_recording:
            self.stop_recording()
            
        # 重置狀態
        self.is_recording = True
        self.frames = []
        
        # 開始新線程錄音
        self.recording_thread = threading.Thread(target=self._record)
        self.recording_thread.daemon = True
        self.recording_thread.start()
        
        if self.debug:
            print("[PC_RECORDER] 開始錄音")
        
        return True
        
    def stop_recording(self):
        """停止錄音"""
        if not self.is_recording:
            return None
            
        self.is_recording = False
        
        # 等待錄音線程結束
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=1)
            
        # 如果沒有錄到任何內容，返回None
        if not self.frames:
            if self.debug:
                print("[PC_RECORDER] 沒有錄到任何聲音")
            return None
            
        # 保存錄音文件
        self._save_wav()
        
        if self.debug:
            print(f"[PC_RECORDER] 錄音結束，保存至 {self.output_file}")
            
        return self.output_file
    
    def _record(self):
        """執行實際錄音過程"""
        p = pyaudio.PyAudio()
        stream = p.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk
        )
        
        silence_count = 0
        has_detected_speech = False
        max_silence_frames = int(self.rate / self.chunk * 5)  # 5秒靜音後結束
        max_wait_frames = int(self.rate / self.chunk * 10)  # 10秒完全靜音等待
        total_frames = 0
        
        try:
            while self.is_recording:
                data = stream.read(self.chunk, exception_on_overflow=False)
                total_frames += 1
                
                # 分析這個塊是否包含語音
                try:
                    is_speech = self.vad.is_speech(data, self.rate)
                except:
                    is_speech = False  # 如果VAD分析失敗，假設不是語音
                
                if is_speech:
                    if self.debug and not has_detected_speech:
                        print("[PC_RECORDER] 檢測到語音，錄音中...")
                    self.frames.append(data)
                    silence_count = 0
                    has_detected_speech = True
                else:
                    silence_count += 1
                    # 如果檢測到語音，我們仍然添加一些靜音幀以保持上下文
                    if has_detected_speech:
                        self.frames.append(data)
                
                # 如果已經檢測到語音，且之後的靜音超過閾值，則停止錄音
                if has_detected_speech and silence_count > max_silence_frames:
                    if self.debug:
                        print("[PC_RECORDER] 檢測到5秒靜音，停止錄音")
                    break
                    
                # 如果等待太久沒有檢測到語音，則停止錄音
                if not has_detected_speech and total_frames > max_wait_frames:
                    if self.debug:
                        print("[PC_RECORDER] 10秒內未檢測到語音，停止錄音")
                    break
                    
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()
            self.is_recording = False
            
    def _save_wav(self):
        """將錄音幀保存為WAV文件"""
        if not self.frames:
            return None
            
        # 保存WAV文件
        p = pyaudio.PyAudio()
        wf = wave.open(self.output_file, 'wb')
        wf.setnchannels(self.channels)
        wf.setsampwidth(p.get_sample_size(self.format))
        wf.setframerate(self.rate)
        wf.writeframes(b''.join(self.frames))
        wf.close()
        p.terminate()
        
        return self.output_file