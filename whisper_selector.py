import os
import logging
import whisper
from openai import AzureOpenAI

def _initialize_azure_client(self):
    """初始化Azure OpenAI客戶端"""
    try:
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
        
        if not api_key or not endpoint:
            logging.error("!!!!! Azure 配置缺失 !!!!!")
            logging.error(f"API Key: {'存在' if api_key else '缺失'}")
            logging.error(f"Endpoint: {'存在' if endpoint else '缺失'}")
            raise ValueError("缺少Azure OpenAI配置，請設置環境變量AZURE_OPENAI_API_KEY和AZURE_OPENAI_ENDPOINT")
            
        logging.info(f"初始化Azure OpenAI客戶端，端點: {endpoint}")
        
        # 強制打印API密鑰前四位，檢查是否正確
        if api_key:
            logging.info(f"API密鑰前四位: {api_key[:4]}...")
        
        self.azure_client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint
        )
        
        # 嘗試進行一個簡單測試以確認客戶端可用
        logging.info("測試Azure客戶端連接...")
        # 這裡可以添加一個非常簡單的API調用測試
        
        logging.info("Azure OpenAI客戶端初始化成功")
    except Exception as e:
        logging.error(f"初始化Azure OpenAI客戶端失敗: {e}")
        logging.error(traceback.format_exc())  # 打印完整錯誤堆疊
        raise
    
class SpeechToTextSelector:
    """語音轉文字選擇器類，支持本地Whisper和Azure Whisper"""
    
    
    def __init__(self, config):
        self.mode = config.get("stt_mode", "local")  # 默認使用本地模式
        self.local_model_size = config.get("local_whisper_model", "medium")  # 默認使用medium模型
        self.azure_model = config.get("azure_whisper_model", "whisper")  # Azure模型部署名稱
        self.azure_client = None
        self.local_model = None
        self.initialized = False
        
        logging.info(f"初始化STT選擇器，模式: {self.mode}, 本地模型: {self.local_model_size}")
        
    def initialize(self):
        """懶加載初始化模型，減少啟動時間"""
        if self.initialized:
            return
            
        if self.mode == "local":
            self._initialize_local_model()
        else:
            self._initialize_azure_client()
            
        self.initialized = True
        
    def _initialize_local_model(self):
        """初始化本地Whisper模型"""
        try:
            logging.info(f"正在加載本地Whisper模型: {self.local_model_size}")
            self.local_model = whisper.load_model(self.local_model_size)
            logging.info("本地Whisper模型加載成功")
        except Exception as e:
            logging.error(f"加載本地Whisper模型失敗: {e}")
            raise
            
    def _initialize_azure_client(self):
        """初始化Azure OpenAI客戶端"""
        try:
            api_key = os.getenv("AZURE_OPENAI_API_KEY")
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
            
            if not api_key or not endpoint:
                raise ValueError("缺少Azure OpenAI配置，請設置環境變量AZURE_OPENAI_API_KEY和AZURE_OPENAI_ENDPOINT")
                
            logging.info(f"初始化Azure OpenAI客戶端，端點: {endpoint}")
            
            self.azure_client = AzureOpenAI(
                api_key=api_key,
                api_version=api_version,
                azure_endpoint=endpoint
            )
            
            logging.info("Azure OpenAI客戶端初始化成功")
        except Exception as e:
            logging.error(f"初始化Azure OpenAI客戶端失敗: {e}")
            raise
            
    def switch_mode(self, mode, config=None):
        """切換STT模式"""
        if mode not in ["local", "azure"]:
            raise ValueError(f"不支持的STT模式: {mode}，只支持'local'或'azure'")
            
        # 如果提供了新配置，更新配置
        if config:
            if mode == "local" and "local_whisper_model" in config:
                self.local_model_size = config["local_whisper_model"]
                # 重置本地模型以便重新加載
                self.local_model = None
                
            if mode == "azure" and "azure_whisper_model" in config:
                self.azure_model = config["azure_whisper_model"]
                
        # 切換模式
        prev_mode = self.mode
        self.mode = mode
        self.initialized = False  # 重置初始化狀態，以便懶加載新模型
        
        logging.info(f"STT模式已從 {prev_mode} 切換到 {mode}")
        return f"語音轉文字模式已切換為: {mode}"
        
    def transcribe(self, audio_file):
        """轉錄音頻文件 - 已禁用回退邏輯"""
        # 確保模型已初始化
        if not self.initialized:
            logging.info("模型未初始化，開始初始化...")
            try:
                self.initialize()
                logging.info(f"初始化完成，當前模式: {self.mode}")
            except Exception as init_error:
                logging.error(f"初始化失敗，錯誤: {init_error}")
                return ""
        
        # 添加醒目的模式提示
        mode_banner = "=" * 50
        if self.mode == "local":
            logging.info(f"\n{mode_banner}\n當前使用模式: 本地 WHISPER ({self.local_model_size})\n{mode_banner}")
        else:
            logging.info(f"\n{mode_banner}\n當前使用模式: AZURE CLOUD WHISPER ({self.azure_model})\n{mode_banner}")
        
        try:
            if self.mode == "local":
                return self._transcribe_local(audio_file)
            else:
                # 嘗試使用 Azure
                logging.info(f"嘗試使用 Azure 轉錄: {audio_file}")
                if self.azure_client is None:
                    logging.error("Azure 客戶端未初始化！")
                    return ""
                return self._transcribe_azure(audio_file)
        except Exception as e:
            logging.error(f"轉錄失敗: {e}")
            logging.error("轉錄失敗，不使用備份模式。")
            return ""
            
    def _transcribe_local(self, audio_file):
        """使用本地Whisper模型轉錄"""
        logging.info(f"使用本地Whisper模型轉錄文件: {audio_file}")
        result = self.local_model.transcribe(audio_file)
        return result.get("text", "")
        
    def _transcribe_azure(self, audio_file):
        """使用Azure Whisper模型轉錄"""
        logging.info(f"使用Azure Whisper模型轉錄文件: {audio_file}")
        
        with open(audio_file, "rb") as audio:
            result = self.azure_client.audio.transcriptions.create(
                file=audio,
                model=self.azure_model
            )
            
        return result.text if hasattr(result, 'text') else str(result)
        
    def get_status(self):
        """獲取當前狀態信息"""
        return {
            "mode": self.mode,
            "local_model": self.local_model_size if self.mode == "local" else None,
            "azure_model": self.azure_model if self.mode == "azure" else None,
            "initialized": self.initialized
        }