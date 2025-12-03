import os
import logging
import time
from datetime import datetime
from azure.cognitiveservices.speech import SpeechConfig, SpeechSynthesizer, AudioConfig, ResultReason
from config import AZURE_SPEECH_API_KEY, AZURE_SPEECH_REGION

# 全局变量，从主应用共享
global current_output_mode, stt_selector
current_output_mode = "pc_speaker"    # 默认使用PC喇叭
stt_selector = None  # 将在初始化时设置

def set_stt_selector(selector):
    """设置 STT 选择器实例"""
    global stt_selector
    stt_selector = selector

def set_output_mode(mode):
    """设置输出模式"""
    global current_output_mode
    current_output_mode = mode
    logging.info(f"音頻輸出模式設置為: {mode}")

def generate_tts(text, for_web_player=True):
    """生成 TTS 音頻，每次生成不同文件名避免緩存問題
    
    Args:
        text: 要轉換為語音的文本
        for_web_player: 是否返回網頁播放器所需的文件路徑。
                       如果是robot_speaker模式且for_web_player=False，
                       則不返回網頁播放器所需的文件路徑
    """
    # 生成帶時間戳的唯一文件名
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    output_file = f"static/response_{timestamp}.wav"
    
    try:
        speech_config = SpeechConfig(
            subscription=AZURE_SPEECH_API_KEY, region=AZURE_SPEECH_REGION)
        speech_config.speech_synthesis_voice_name = "zh-HK-WanLungNeural"
        audio_config = AudioConfig(filename=output_file)
        synthesizer = SpeechSynthesizer(
            speech_config=speech_config, audio_config=audio_config)

        result = synthesizer.speak_text_async(text).get()

        if result.reason == ResultReason.SynthesizingAudioCompleted:
            logging.info(f"TTS 文件生成成功: {output_file}")
            
            # 如果是機器人喇叭模式，將音頻發送到機器人
            if current_output_mode == 'robot_speaker':
                try:
                    # 直接調用發送函數，避免循環導入
                    logging.info(f"檢測到 robot_speaker 模式，準備發送音頻到機器人: {output_file}")
                    
                    # 讀取音頻文件數據
                    with open(output_file, 'rb') as f:
                        audio_data = f.read()
                    
                    # 從主模塊獲取必要的變數和函數
                    from app_main import socketio, connected_robots
                    
                    # 確認有連接的機器人
                    if connected_robots:
                        for robot_id in connected_robots:
                            logging.info(f"發送音頻到機器人 {robot_id}, 數據大小: {len(audio_data)} 字節")
                            socketio.emit('play_audio', {
                                'audio_data': audio_data
                            }, room=robot_id)
                    else:
                        logging.warning("沒有連接的機器人，無法發送音頻")
                    
                    # 如果不需要為網頁播放器返回路徑，則返回None
                    if not for_web_player:
                        return None
                
                except Exception as e:
                    logging.error(f"發送音頻到機器人時出錯: {str(e)}")
                    import traceback
                    traceback.print_exc()
            
            return f"/{output_file}"
        else:
            logging.error(f"TTS 生成失敗: {result.reason}")
            return None
    except Exception as e:
        logging.error(f"生成 TTS 時出錯: {e}")
        return None

def transcribe_audio(audio_file):
    """將音頻轉文字，支持本地和Azure Whisper"""
    print("[INFO] 開始語音轉文字...")
    try:
        # 確保 stt_selector 已設置
        global stt_selector
        if stt_selector is None:
            from app_main import stt_selector as main_stt_selector
            stt_selector = main_stt_selector
            
        # 使用選擇器進行轉錄
        result = stt_selector.transcribe(audio_file)
        return result
    except Exception as e:
        print(f"[ERROR] 語音轉文字失敗: {e}")
        import traceback
        traceback.print_exc()
        return ""

def convert_audio_format(input_file, output_file, sample_rate=16000, channels=1):
    """转换音频格式为16kHz单声道WAV"""
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(input_file)
        audio = audio.set_frame_rate(sample_rate).set_channels(channels)
        audio.export(output_file, format="wav")
        logging.info(f"音频格式转换成功: {input_file} -> {output_file}")
        return output_file
    except Exception as e:
        logging.error(f"音频格式转换失败: {e}")
        return input_file  # 如果转换失败，返回原文件

def check_vad(audio_data, sample_rate=16000):
    """检查是否有语音活动"""
    try:
        import webrtcvad
        vad = webrtcvad.Vad(3)  # 设置敏感度为3（最高）
        
        # 确保音频长度为以10ms或30ms为单位
        frame_duration = 30  # ms
        frame_size = int(sample_rate * (frame_duration / 1000.0))
        frames = []
        
        # 将音频分割成30ms的帧
        for i in range(0, len(audio_data), frame_size):
            frames.append(audio_data[i:i+frame_size])
        
        # 检查是否有语音
        speech_frames = 0
        for frame in frames:
            if len(frame) == frame_size:
                if vad.is_speech(frame.tobytes(), sample_rate):
                    speech_frames += 1
        
        # 如果超过20%的帧包含语音，则认为有语音活动
        speech_ratio = speech_frames / max(len(frames), 1)
        return speech_ratio > 0.2
    
    except Exception as e:
        logging.error(f"VAD检测失败: {e}")
        return True  # 如果检测失败，默认认为有语音