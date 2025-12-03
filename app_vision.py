import logging
import base64
import traceback
from datetime import datetime
from app_audio import generate_tts
from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from config import AZURE_VISION_ENDPOINT, AZURE_VISION_KEY
from azure.core.credentials import AzureKeyCredential

# 全局变量，会在app_main.py中设置
vision_client = None
chatbot = None
save_chat_message = None

def init_vision_module(vision_client_instance, chatbot_instance, save_chat_message_func):
    """初始化视觉模块"""
    global vision_client, chatbot, save_chat_message
    vision_client = vision_client_instance
    chatbot = chatbot_instance
    save_chat_message = save_chat_message_func
    
    logging.info("Visual模块初始化完成")

def analyze_image_with_vision(image_path):
    """使用Azure Vision分析圖片"""
    try:
        # 讀取圖片二進制數據
        with open(image_path, 'rb') as image_file:
            image_data = image_file.read()
            
        # 使用Azure Vision客戶端分析圖片
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
                    
        # 生成文本描述
        analysis_text = f"📷 圖片分析結果:\n\n"
        
        if caption:
            analysis_text += f"這張圖片顯示的是 {caption}。\n\n"
            
        if objects:
            analysis_text += f"圖中可見的物體: {', '.join(objects)}。\n\n"
            
        if tags:
            analysis_text += f"相關標籤: {', '.join(tags)}。"
            
        return {
            'caption': caption,
            'objects': objects,
            'tags': tags,
            'text': analysis_text
        }
    except Exception as e:
        logging.error(f"分析圖片時出錯: {e}")
        return {
            'caption': '分析失敗',
            'objects': [],
            'tags': [],
            'text': f"抱歉，我無法分析這張圖片。發生錯誤: {str(e)}"
        }

def is_person_detected(caption, objects, tags):
    """检查是否检测到人物"""
    person_related_terms = ["person", "people", "human", "man", "woman", "boy", "girl", "child", "baby", "face", 
                            "人", "人物", "男人", "女人", "小孩", "嬰兒", "臉", "面孔"]
    
    # 检查标题、物体和标签中是否有人物相关词
    if any(term.lower() in caption.lower() for term in person_related_terms):
        return True
    
    for obj in objects:
        if any(term.lower() in obj.lower() for term in person_related_terms):
            return True
            
    for tag in tags:
        if any(term.lower() in tag.lower() for term in person_related_terms):
            return True
            
    return False

def analyze_current_frame(socketio_instance=None):
    """分析當前攝像頭畫面"""
    # 注意：不要使用global語句，直接從主模塊獲取最新的frame數據
    try:
        # 如果没有设置socketio实例，从主模块导入
        if socketio_instance is None:
            from app_main import socketio
            socketio_instance = socketio
            
        # 直接從主模塊獲取當前最新的frame
        from app_socket_handlers import get_latest_frame
        latest_frame = get_latest_frame()
        
        if latest_frame is None or latest_frame == "":
            response = "抱歉，目前沒有可用的攝像頭畫面。請確保攝像頭已開啟。"
            socketio_instance.emit('response', {"text": response, "status": "error"})
            return

        logging.info("[VISION] 開始處理攝像頭畫面")
        logging.info(f"[VISION] 接收到圖像數據，長度: {len(latest_frame) if latest_frame else 0}")
        
        # 將 base64 圖片數據轉換為二進制
        try:
            image_data = base64.b64decode(latest_frame)
            logging.info(f"[VISION] 成功解碼圖片數據，大小: {len(image_data)} bytes")
        except Exception as e:
            logging.error(f"[VISION] 圖片解碼失敗: {e}")
            response = "抱歉，圖像數據無法解碼，請重試。"
            socketio_instance.emit('response', {"text": response, "status": "error"})
            return

        # 分析圖片
        from app_main import vision_client, chatbot, save_chat_message
        
        result = vision_client.analyze(
            image_data=image_data,
            visual_features=[
                VisualFeatures.CAPTION,
                VisualFeatures.OBJECTS,
                VisualFeatures.TAGS
            ],
            gender_neutral_caption=True
        )

        logging.info(f"[VISION] 圖片分析完成，開始處理結果")

        # 收集分析結果
        caption = ""
        confidence = 0
        if hasattr(result, 'caption') and result.caption:
            caption = result.caption.text
            confidence = result.caption.confidence

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

        # 检查是否识别到人物相关的内容
        detected_person = is_person_detected(caption, objects, tags)

        # 準備給 GPT 的提示
        prompt = f"""作為一個友善的助手，請用自然的廣東話描述以下場景：

場景描述：{caption}
可見的物件：{', '.join(objects) if objects else '無'}
場景特徵：{', '.join(tags) if tags else '無'}

請用簡單、生活化的方式描述，一定要以「我見到」開始句子。"""

        response_text = ""
        tts_file = None

        try:
            # 使用 chatbot 獲取 GPT 回應
            gpt_response = chatbot.get_response(prompt)
            logging.info(f"[VISION] GPT 生成回應: {gpt_response}")
            
            if gpt_response:
                response_text = gpt_response
            else:
                # 如果 GPT 回應為空，使用備用回應
                backup_response = f"我見到{caption}"
                if objects:
                    backup_response += f"，仲有{', '.join(objects)}"
                response_text = backup_response

        except Exception as e:
            logging.error(f"[VISION] GPT 處理失敗: {str(e)}")
            # 使用基本回應
            response_text = f"我見到{caption}"
        
        # 只在這一個地方生成 TTS
        tts_file = generate_tts(response_text)
        
        # 記錄 AI 回應到聊天歷史
        ai_message = {
            "type": "received",
            "text": response_text,
            "timestamp": datetime.now().isoformat(),
            "audioSrc": tts_file
        }
        save_chat_message(ai_message)
        
        # 發送回應
        socketio_instance.emit('response', {
            "text": response_text,
            "audio_file": tts_file,
            "status": "success"
        })
        
        # 如果检测到人物相关内容，执行一次挥手动作
        if detected_person:
            logging.info("[VISION] 检测到人物，执行挥手动作")
            # 使用单位数动作9（挥手）
            from app_robot_control import execute_singledigit_action
            execute_singledigit_action('9', '1')

    except Exception as e:
        logging.error(f"[VISION] 分析圖片時出錯: {str(e)}")
        traceback.print_exc()
        response = "抱歉，分析畫面時出現問題，請再試一次。"
        socketio_instance.emit('response', {
            "text": response,
            "status": "error"
        })