import whisper
import pyttsx3
import pyaudio
import wave
import os
import webrtcvad
from pydub import AudioSegment
from pydub.playback import play

class AudioManager:
    def __init__(self):
        self.stt_model = whisper.load_model("small")  # Whisper 語音轉文字模型
        self.tts_engine = pyttsx3.init()  # 使用 pyttsx3 進行文字轉語音
        self.is_recording = False  # 初始化錄音狀態
    
    def convert_audio_to_16k_mono(self, input_path, output_path="converted_audio.wav"):
        """將音訊轉換為 16kHz 單聲道"""
        audio = AudioSegment.from_file(input_path)
        audio = audio.set_frame_rate(16000).set_channels(1)
        audio.export(output_path, format="wav")
        return output_path
    
    def speech_to_text(self, audio_path):
        """語音轉文字"""
        processed_audio_path = self.convert_audio_to_16k_mono(audio_path)
        result = self.stt_model.transcribe(processed_audio_path, language="zh")
        return result.get("text")

    def text_to_speech(self, text):
        """文字轉語音"""
        self.tts_engine.save_to_file(text, "output.wav")
        self.tts_engine.runAndWait()
        with open("output.wav", "rb") as f:
            return f.read()
    
    def play_sound(self, file_path):
        """播放提示音"""
        try:
            sound = AudioSegment.from_file(file_path)
            play(sound)
        except Exception as e:
            print(f"播放提示音失敗：{e}")
    
    def start_recording(self, output_file="hardware_recording.wav"):
        """基於音量檢測的錄音功能"""
        CHUNK = 320
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        
        p = pyaudio.PyAudio()
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
        
        vad = webrtcvad.Vad()
        vad.set_mode(3)  # 高敏感度
        
        frames = []
        silence_count = 0
        has_detected_speech = False
        max_silence_frames = int(RATE / CHUNK * 5)  # 用戶講話後的靜音時間 (5 秒)
        max_wait_frames = int(RATE / CHUNK * 30)  # 完全靜音的等待時間 (30 秒)
        total_frames = 0
        
        self.is_recording = True
        self.play_sound("start_beep.wav")  # 播放開始提示音
        print("[INFO] 開始錄音...")

        try:
            while self.is_recording:
                data = stream.read(CHUNK, exception_on_overflow=False)
                total_frames += 1

                if vad.is_speech(data, RATE):
                    print("[INFO] 檢測到語音，錄音中...")
                    frames.append(data)
                    silence_count = 0
                    has_detected_speech = True
                else:
                    silence_count += 1

                if has_detected_speech and silence_count > max_silence_frames:
                    print("[INFO] 用戶靜音超過 5 秒，結束錄音...")
                    break
                
                if not has_detected_speech and total_frames > max_wait_frames:
                    print("[INFO] 完全靜音 30 秒，結束等待...")
                    frames = []
                    break
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()
            self.is_recording = False
            self.play_sound("stop_beep.wav")  # 播放結束提示音
            print("[INFO] 錄音結束")

        if frames:
            wf = wave.open(output_file, 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))
            wf.close()
            print(f"[INFO] 錄音保存為 {output_file}")
            self.handle_audio(output_file)
        else:
            print("[INFO] 沒有錄音內容，重新進入錄音模式...")
            self.start_recording()

    def play_sound(self, file_path):
        """播放提示音"""
        try:
            sound = AudioSegment.from_wav(file_path)
            play(sound)
            print(f"[INFO] 播放提示音: {file_path}")
        except Exception as e:
            print(f"[ERROR] 播放提示音失敗：{e}")
    
    def handle_audio(self, audio_file):
        """處理錄音並回應"""
        transcribed_text = self.speech_to_text(audio_file)
        if not transcribed_text:
            print("無法識別語音內容。")
            return
        
        if os.path.exists(audio_file):
            os.remove(audio_file)
            print(f"[INFO] 已刪除用戶錄音文件: {audio_file}")
        
        response = chatbot.get_response(transcribed_text)
        print(f"[INFO] Chatbot 回應: {response}")
        self.speak_response(response)
    
    def speak_response(self, response):
        """播放機器人回應"""
        try:
            audio_file = self.text_to_speech(response)
            if not audio_file:
                print("[ERROR] 無法生成音頻文件")
                return
            
            audio = AudioSegment.from_file("output.wav", format="wav")
            play(audio)
            print("[INFO] 播放機器人回應")
            
            if os.path.exists("output.wav"):
                os.remove("output.wav")
                print("[INFO] 已刪除回應音頻文件")
        except Exception as e:
            print(f"語音播放失敗：{e}")
