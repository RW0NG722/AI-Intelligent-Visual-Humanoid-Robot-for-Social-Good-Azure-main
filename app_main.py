from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import logging
import os
import wave
import time
import whisper
import random
import importlib.util
import subprocess
import sounddevice as sd
import numpy as np
import io
import traceback
import json
from scipy.io import wavfile as wav
from datetime import datetime
import pygame
import threading
from app_audio import generate_tts, transcribe_audio
from app_socket_handlers import register_socket_handlers
from app_vision import analyze_current_frame, analyze_image_with_vision
from app_robot_control import RobotStatus, execute_singledigit_action, execute_doubledigit_action
from app_phone_mode import PhoneMode
from app_utils import initialize_chat_history, save_chat_message, is_history_outdated
from audio_manager import AudioManager
from azure.cognitiveservices.speech import SpeechConfig, SpeechSynthesizer, AudioConfig, ResultReason
from chatbot import ChatBot
from whisper_selector import SpeechToTextSelector
from config import AZURE_SPEECH_API_KEY, AZURE_SPEECH_REGION, AZURE_VISION_ENDPOINT, AZURE_VISION_KEY, WHISPER_CONFIG
from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential
import base64
from pc_recorder import PCRecorder


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log", encoding="utf-8"),
    ]
)

app = Flask(__name__, static_folder="static")
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")
latest_frame = None  # 儲存最新影像
last_camera_log_time = 0
camera_frame_count = 0
phone_mode_active = False
pc_recorder = PCRecorder()
pygame.mixer.init()

# 聊天歷史文件路徑
CHAT_HISTORY_FILE = "chat_history.json"
MAX_HISTORY_ENTRIES = 15

# 初始化聊天歷史
chat_history = {"messages": []}

# 初始化模块
chatbot = ChatBot()
audio_manager = AudioManager()
stt_selector = SpeechToTextSelector(WHISPER_CONFIG)

# 全局变量
connected_robots = {}  # 存储已连接的机器人信息
current_input_mode = "pc_microphone"  # 默认使用PC麦克风
current_output_mode = "pc_speaker"    # 默认使用PC喇叭

# 創建 Vision 客戶端
vision_client = ImageAnalysisClient(
    endpoint=AZURE_VISION_ENDPOINT,
    credential=AzureKeyCredential(AZURE_VISION_KEY)
)

# 錄音配置
SAMPLE_RATE = 16000  # 16kHz 采樣率
CHANNELS = 1  # 單聲道
DURATION = 5  # 錄音時間（秒）

# 机器人状态字典
robot_statuses = {}


def should_trigger_vision(text):
    """檢查文字是否包含觸發 AI Vision 的關鍵詞"""
    if not text:
        return False

    vision_keywords = ['看到什麼', '見到什麼', '看到咩野', '見到咩野',
                       '你看見什麼', '你看見了什麼', '看見什麼',
                       '看到', '看到', '見到', '看見', '見到', '睇到', '睇見', '睇到咩', '睇見咩']

    text_lower = text.lower()
    return any(keyword in text_lower for keyword in vision_keywords)


# 初始化 PhoneMode 实例
phone_mode_manager = None


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/test/upload-image', methods=['POST'])
def test_upload_image():
    try:
        # 檢查是否有文件被上傳
        if 'image' not in request.files:
            return jsonify({
                'success': False,
                'message': '未找到圖片文件'
            }), 400

        image_file = request.files['image']

        # 檢查文件是否有內容
        if image_file.filename == '':
            return jsonify({
                'success': False,
                'message': '未選擇文件'
            }), 400

        # 檢查文件類型
        if not image_file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            return jsonify({
                'success': False,
                'message': '只支持JPG和PNG格式的圖片'
            }), 400

        # 確保上傳目錄存在
        upload_dir = os.path.join('static', 'uploads', 'test')
        os.makedirs(upload_dir, exist_ok=True)

        # 保存文件
        filename = f"test_image_{int(time.time())}.jpg"
        filepath = os.path.join(upload_dir, filename)
        image_file.save(filepath)

        # 使用Azure Vision分析圖片
        with open(filepath, 'rb') as f:
            image_data = f.read()

        print("[DEBUG] 開始處理測試上傳圖片")

        # 分析圖片
        result = vision_client.analyze(
            image_data=image_data,
            visual_features=[
                VisualFeatures.CAPTION,
                VisualFeatures.OBJECTS,
                VisualFeatures.TAGS
            ],
            gender_neutral_caption=True
        )

        # 提取分析結果
        caption = ""
        if hasattr(result, 'caption') and result.caption:
            caption = result.caption.text

        objects = []
        if hasattr(result, 'objects') and result.objects:
            for obj in result.objects:
                if hasattr(obj, 'name'):
                    objects.append(obj.name)

        tags = []
        if hasattr(result, 'tags') and result.tags:
            for tag in result.tags:
                if hasattr(tag, 'name'):
                    tags.append(tag.name)

        # 檢查是否識別到人物
        detected_person = False
        person_related_terms = ["person", "people", "human",
                                "man", "woman", "boy", "girl", "child", "baby", "face"]

        if any(term.lower() in caption.lower() for term in person_related_terms):
            detected_person = True

        for obj in objects:
            if any(term.lower() in obj.lower() for term in person_related_terms):
                detected_person = True
                break

        for tag in tags:
            if any(term.lower() in tag.lower() for term in person_related_terms):
                detected_person = True
                break

        # 準備廣東話描述的提示詞
        prompt = """用廣東話描述這張圖片，以「我見到」開頭，語氣要自然活潑一點。描述要詳細，但不要太長。"""

        # 使用 chatbot 獲取 GPT 回應
        print("[DEBUG] 將直接通過 chatbot 獲取回應")

        try:
            # 使用現有的 chatbot 對象而不是創建新的
            gpt_response = chatbot.get_response(
                prompt + f"\n\n圖片描述: {caption}\n可見物件: {', '.join(objects)}\n標籤: {', '.join(tags)}")

            print(f"[DEBUG] GPT回應: {gpt_response}")

            # 確保回應以「我見到」開頭 (如果不是則修正)
            if not gpt_response.startswith("我見到"):
                print("[DEBUG] 回應不以「我見到」開頭，添加前綴")
                gpt_response = "我見到" + gpt_response

            # 使用現有的 generate_tts 函數
            print(f"[DEBUG] 生成TTS，使用文本: {gpt_response}")
            tts_file = generate_tts(gpt_response)

            if tts_file:
                print(f"[DEBUG] TTS生成成功: {tts_file}")

                # 記錄AI回應到聊天歷史
                ai_message = {
                    "type": "received",
                    "text": gpt_response,
                    "timestamp": datetime.now().isoformat(),
                    "audioSrc": tts_file
                }
                save_chat_message(ai_message)

                # 如果檢測到人物，嘗試執行揮手動作 (使用全局函數)
                if detected_person:
                    print("[DEBUG] 檢測到人物，執行揮手動作")
                    try:
                        # 直接調用，不用任何導入
                        result = subprocess.run([
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
                            "-d", '{"id":1732853986186,"jsonrpc":"2.0","method":"RunAction","params":["9","1"]}'
                        ], capture_output=True, text=True)

                        print(f"[DEBUG] 揮手動作執行結果: {result.stdout}")

                        # 添加機器人動作訊息到聊天記錄
                        action_message = {
                            "type": "received",
                            "text": "🤖 執行動作: 揮手 已完成",
                            "timestamp": datetime.now().isoformat(),
                            "audioSrc": None
                        }
                        save_chat_message(action_message)

                    except Exception as action_error:
                        print(f"[ERROR] 執行動作失敗: {action_error}")

                # 返回成功結果
                return jsonify({
                    'success': True,
                    'image_url': f"/static/uploads/test/{filename}",
                    'caption': caption,
                    'tags': tags,
                    'objects': objects,
                    'analysis_text': gpt_response,
                    'tts_file': tts_file,
                    'detected_person': detected_person
                })
            else:
                # TTS生成失敗，使用備用方案
                print("[WARNING] TTS生成失敗，使用備用方案")
                raise Exception("TTS生成失敗")

        except Exception as e:
            # 詳細記錄錯誤
            print(f"[ERROR] GPT處理失敗: {str(e)}")
            import traceback
            traceback.print_exc()

            # 創建更自然的廣東話備用回應
            backup_response = f"我見到圖片中有{caption}"

            if objects and len(objects) > 0:
                # 只使用前3個物體，避免過長
                shown_objects = objects[:3]
                backup_response = f"我見到圖片中有{', '.join(shown_objects)}"

            print(f"[DEBUG] 使用備用回應: {backup_response}")

            # 生成備用TTS
            backup_tts_file = generate_tts(backup_response)

            # 記錄基本回應到聊天歷史
            basic_message = {
                "type": "received",
                "text": backup_response,
                "timestamp": datetime.now().isoformat(),
                "audioSrc": backup_tts_file
            }
            save_chat_message(basic_message)

            # 如果檢測到人物，執行揮手動作
            if detected_person:
                try:
                    # 直接執行命令，不依賴外部函數
                    result = subprocess.run([
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
                        "-d", '{"id":1732853986186,"jsonrpc":"2.0","method":"RunAction","params":["9","1"]}'
                    ], capture_output=True, text=True)

                    # 添加機器人動作訊息到聊天記錄
                    action_message = {
                        "type": "received",
                        "text": "🤖 執行動作: 揮手 已完成",
                        "timestamp": datetime.now().isoformat(),
                        "audioSrc": None
                    }
                    save_chat_message(action_message)

                except Exception as action_error:
                    print(f"[ERROR] 執行動作失敗: {action_error}")

            # 返回備用回應
            return jsonify({
                'success': True,
                'image_url': f"/static/uploads/test/{filename}",
                'caption': caption,
                'tags': tags,
                'objects': objects,
                'analysis_text': backup_response,
                'tts_file': backup_tts_file,
                'detected_person': detected_person
            })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'處理圖片時出錯: {str(e)}'
        }), 500

# 添加測試音頻上傳和處理的路由


@app.route('/api/test/upload-audio', methods=['POST'])
def test_upload_audio():
    try:
        # 檢查是否有文件被上傳
        if 'audio' not in request.files:
            return jsonify({
                'success': False,
                'message': '未找到音頻文件'
            }), 400

        audio_file = request.files['audio']

        # 檢查文件是否有內容
        if audio_file.filename == '':
            return jsonify({
                'success': False,
                'message': '未選擇文件'
            }), 400

        # 檢查文件類型
        if not audio_file.filename.lower().endswith('.wav'):
            return jsonify({
                'success': False,
                'message': '只支持WAV格式的音頻文件'
            }), 400

        # 確保上傳目錄存在
        upload_dir = os.path.join('static', 'uploads', 'test')
        os.makedirs(upload_dir, exist_ok=True)

        # 保存文件
        filename = f"test_audio_{int(time.time())}.wav"
        filepath = os.path.join(upload_dir, filename)
        audio_file.save(filepath)

        # 轉錄音頻
        transcribed_text = transcribe_audio(filepath)

        # 獲取AI回應
        ai_response = None
        response_audio_url = None

        if transcribed_text:
            # 使用chatbot處理文本
            ai_response = chatbot.get_response(transcribed_text)

            # 生成TTS
            if ai_response:
                tts_file = generate_tts(ai_response)
                if tts_file:
                    response_audio_url = tts_file

        # 返回結果
        return jsonify({
            'success': True,
            'text': transcribed_text,
            'response': ai_response,
            'audio_url': f"/static/uploads/test/{filename}",
            'response_audio': response_audio_url
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'處理音頻時出錯: {str(e)}'
        }), 500


@app.route('/api/settings/whisper', methods=['POST'])
def update_whisper_settings():
    try:
        data = request.json
        mode = data.get('mode')
        config = {
            'local_whisper_model': data.get('local_model'),
            'azure_whisper_model': data.get('azure_model')
        }

        # 使用選擇器切換模式
        result = stt_selector.switch_mode(mode, config)

        # 獲取當前狀態
        status = stt_selector.get_status()

        return jsonify({
            'success': True,
            'message': result,
            'current_status': status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400

# 添加獲取當前Whisper設置的API


@app.route('/api/settings/whisper', methods=['GET'])
def get_whisper_settings():
    try:
        status = stt_selector.get_status()
        return jsonify({
            'success': True,
            'current_status': status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/test/whisper-status', methods=['GET'])
def test_whisper_status():
    """測試Whisper狀態，返回詳細資訊"""
    try:
        status = stt_selector.get_status()

        # 測試Azure認證
        azure_creds_ok = False
        azure_error = None
        try:
            api_key = os.getenv("AZURE_OPENAI_API_KEY")
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            azure_creds_ok = api_key is not None and endpoint is not None
        except Exception as e:
            azure_error = str(e)

        # 嘗試初始化Azure客戶端
        azure_init_ok = False
        azure_init_error = None
        if status['mode'] == 'azure':
            try:
                stt_selector._initialize_azure_client()
                azure_init_ok = True
            except Exception as e:
                azure_init_error = str(e)

        return jsonify({
            'success': True,
            'current_status': status,
            'azure_credentials_ok': azure_creds_ok,
            'azure_init_ok': azure_init_ok,
            'azure_error': azure_error,
            'azure_init_error': azure_init_error,
            'config': {
                'AZURE_SPEECH_API_KEY': os.getenv("AZURE_SPEECH_API_KEY", "未設置")[:4] + "..." if os.getenv("AZURE_SPEECH_API_KEY") else "未設置",
                'AZURE_SPEECH_REGION': os.getenv("AZURE_SPEECH_REGION", "未設置"),
                'WHISPER_CONFIG': WHISPER_CONFIG,
            }
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# 處理單位數動作


@app.route('/execute_singledigit_action', methods=['POST'])
def execute_singledigit_action_route():
    try:
        data = request.json
        if 'params' not in data:
            return jsonify({"error": "Missing 'params' field"}), 400

        params = data['params']

        # 記錄收到的參數
        logging.info(f"收到單位數動作參數: {params}")

        # 嘗試獲取並處理參數
        try:
            if isinstance(params, list) and len(params) >= 2:
                action_id = params[0]
                repeat_count = params[1]
            elif isinstance(params, str):
                # 兼容舊格式
                import json
                try:
                    params_array = json.loads(params)
                    action_id = params_array[0]
                    repeat_count = params_array[1]
                except:
                    # 無法解析，使用原始數據
                    return execute_singledigit_action(params, "1")
            else:
                # 參數格式不是預期的
                return jsonify({"error": f"Unexpected params format: {type(params)}"}), 400

            return execute_singledigit_action(action_id, repeat_count)
        except Exception as e:
            logging.error(f"處理單位數動作參數失敗: {e}")
            # 嘗試直接使用原始參數
            return execute_singledigit_action(params, "1")

    except Exception as e:
        logging.error(f"執行單位數動作路由處理失敗: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/execute_doubledigit_action', methods=['POST'])
def execute_doubledigit_action_route():
    try:
        data = request.json
        if 'params' not in data:
            return jsonify({"error": "Missing 'params' field"}), 400

        params = data['params']

        # 記錄收到的參數
        logging.info(f"收到雙位數動作參數: {params}")

        # 嘗試獲取並處理參數
        try:
            if isinstance(params, list) and len(params) >= 2:
                action_id = params[0]
                repeat_count = params[1]
            elif isinstance(params, str):
                # 兼容舊格式
                import json
                try:
                    params_array = json.loads(params)
                    action_id = params_array[0]
                    repeat_count = params_array[1]
                except:
                    # 無法解析，使用原始數據
                    return execute_doubledigit_action(params, "1")
            else:
                # 參數格式不是預期的
                return jsonify({"error": f"Unexpected params format: {type(params)}"}), 400

            return execute_doubledigit_action(action_id, repeat_count)
        except Exception as e:
            logging.error(f"處理雙位數動作參數失敗: {e}")
            # 嘗試直接使用原始參數
            return execute_doubledigit_action(params, "1")

    except Exception as e:
        logging.error(f"執行雙位數動作路由處理失敗: {e}")
        return jsonify({"error": str(e)}), 500


def record_audio(output_file="recorded_audio.wav"):
    """使用 sounddevice 錄音"""
    print("[INFO] 開始錄音...")
    audio_data = sd.rec(int(SAMPLE_RATE * DURATION),
                        samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=np.int16)
    sd.wait()  # 等待錄音完成
    wav.write(output_file, SAMPLE_RATE, audio_data)  # 儲存音檔
    print(f"[INFO] 錄音完成，儲存至 {output_file}")

    return output_file


def send_audio_to_robot(audio_file):
    """將音頻文件發送到機器人端播放"""
    try:
        # 讀取音頻文件數據
        with open(audio_file, 'rb') as f:
            audio_data = f.read()

        # 向所有連接的機器人發送音頻數據
        for robot_id in connected_robots:
            socketio.emit('play_audio', {
                'audio_data': audio_data
            }, room=robot_id)
            logging.info(f"發送音頻到機器人 {robot_id}")
    except Exception as e:
        logging.error(f"發送音頻到機器人失敗: {e}")


def main():
    # 初始化 PhoneMode 實例
    global phone_mode_manager
    phone_mode_manager = PhoneMode(
        socketio=socketio,
        chatbot=chatbot,
        transcribe_func=transcribe_audio,
        tts_func=generate_tts,
        save_message_func=save_chat_message,
        should_trigger_vision_func=should_trigger_vision,
        analyze_frame_func=analyze_current_frame
    )

    # 初始化聊天歷史
    initialize_chat_history()

    # 注册所有套接字处理程序
    register_socket_handlers(
        socketio, stt_selector, chatbot, current_input_mode,
        current_output_mode, phone_mode_manager, phone_mode_active,
        should_trigger_vision, analyze_current_frame, save_chat_message,
        generate_tts, record_audio, pc_recorder, connected_robots
    )

    try:
        # 強制設置為 Azure 模式
        logging.info("嘗試強制設置 Whisper 為 Azure 模式...")
        stt_selector.switch_mode("azure")
        status = stt_selector.get_status()
        logging.info(f"Whisper 當前狀態: {status}")

        # 初始化 Azure 客戶端
        logging.info("強制初始化 Azure 客戶端...")
        stt_selector._initialize_azure_client()
        logging.info("Azure 客戶端初始化成功")
    except Exception as e:
        logging.error(f"強制設置 Azure 模式失敗: {e}")
        traceback.print_exc()


if __name__ == '__main__':
    main()
    logging.info("PC 服务端启动于 0.0.0.0:5001")
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)
