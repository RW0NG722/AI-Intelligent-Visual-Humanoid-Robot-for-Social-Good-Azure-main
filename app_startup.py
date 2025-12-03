import sys
import logging
import traceback
import glob
import os
from app_main import app, socketio, main
from app_utils import ensure_directories, clean_old_files

def setup_logging():
    """設置日誌系統"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("app.log", encoding="utf-8"),
        ]
    )
    logging.info("日誌系統初始化完成")

def check_dependencies():
    """檢查必要的依賴項是否安裝 - 依據實際安裝修改檢查邏輯"""
    # 基本必要的依賴項
    required_packages = [
        "flask", "flask_socketio", "whisper", "sounddevice", "numpy", "scipy",
        "pygame", "webrtcvad"
    ]
    
    # Azure 相關的依賴項 - 使用實際安裝的包名稱
    azure_packages = {
        "azure.cognitiveservices.speech": "Azure Speech API",
        "azure.ai.vision.imageanalysis": "Azure Vision Imageanalysis"
    }
    
    # 檢查基本依賴項
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        logging.error(f"缺少必要的依賴項: {', '.join(missing_packages)}")
        return False
    
    # 檢查 Azure 依賴項 - 使用更靈活的導入方式
    azure_missing = []
    for package_name, package_description in azure_packages.items():
        try:
            package_parts = package_name.split('.')
            current_module = __import__(package_parts[0])
            
            for part in package_parts[1:]:
                current_module = getattr(current_module, part)
                
            logging.info(f"成功導入 {package_description}: {package_name}")
        except (ImportError, AttributeError) as e:
            azure_missing.append(f"{package_name} ({package_description})")
            logging.warning(f"無法導入 {package_description} ({package_name}): {str(e)}")
    
    if azure_missing:
        logging.warning(f"部分 Azure 依賴項可能無法正確導入: {', '.join(azure_missing)}")
        logging.warning("這些功能可能無法正常工作，但我們將嘗試繼續啟動。")
    
    logging.info("依賴項檢查完成")
    return True

def check_config():
    """檢查配置文件是否存在必要的設置，但不阻止啟動"""
    config_exists = True
    try:
        from config import (
            AZURE_SPEECH_API_KEY, AZURE_SPEECH_REGION, 
            AZURE_VISION_ENDPOINT, AZURE_VISION_KEY,
            AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT,
            AZURE_OPENAI_API_VERSION, AZURE_OPENAI_DEPLOYMENT_NAME,
            WHISPER_CONFIG
        )
        
        # 檢查 Azure Speech 設置
        if not AZURE_SPEECH_API_KEY or not AZURE_SPEECH_REGION:
            logging.warning("Azure Speech 設置不完整，TTS 功能可能無法正常工作")
        
        # 檢查 Azure Vision 設置
        if not AZURE_VISION_ENDPOINT or not AZURE_VISION_KEY:
            logging.warning("Azure Vision 設置不完整，圖像分析功能可能無法正常工作")
        
        # 檢查 Azure OpenAI 設置
        if not AZURE_OPENAI_API_KEY or not AZURE_OPENAI_ENDPOINT:
            logging.warning("Azure OpenAI 設置不完整，聊天功能可能無法正常工作")
        
        # 檢查 Whisper 設置
        if not WHISPER_CONFIG:
            logging.warning("Whisper 設置不完整，語音轉文字功能可能無法正常工作")
        
        logging.info("成功檢查配置文件")
    except ImportError:
        logging.error("缺少 config.py 文件，請根據 config_example.py 創建")
        config_exists = False
    except Exception as e:
        logging.error(f"檢查配置文件時出錯: {e}")
        config_exists = False
    
    return config_exists

def startup(force=True):
    """啟動應用程序，可以選擇強制啟動即使檢查失敗"""
    try:
        # 設置日誌系統
        setup_logging()
        logging.info("開始啟動應用程序...")
        
        # 檢查依賴項和配置
        deps_ok = check_dependencies()
        config_ok = check_config()
        
        if not (deps_ok and config_ok) and not force:
            logging.error("啟動檢查失敗，應用程序無法啟動。使用 --force 參數可強制啟動。")
            return False
        
        # 確保必要目錄存在
        ensure_directories()
        
        # 清理舊文件
        clean_old_files("uploads", 24)
        clean_old_files("static/uploads", 24)

        # 清理 static/ 下的 response*.wav
        for f in glob.glob("static/response*.wav"):
            try:
                os.remove(f)
                logging.info(f"已刪除舊 TTS 音檔：{f}")
            except Exception as e:
                logging.warning(f"無法刪除 {f}: {e}")

        # 清理 static/uploads/test/ 下的 .wav
        for f in glob.glob("static/uploads/test/*.wav"):
            try:
                os.remove(f)
                logging.info(f"已刪除測試上傳音檔：{f}")
            except Exception as e:
                logging.warning(f"無法刪除 {f}: {e}")

        # 清理 static/uploads/test/ 下的 .jpg
        for f in glob.glob("static/uploads/test/*.jpg"):
            try:
                os.remove(f)
                logging.info(f"已刪除測試圖片：{f}")
            except Exception as e:
                logging.warning(f"無法刪除 {f}: {e}")
        
        try:
            # 初始化主應用
            logging.info("正在初始化主應用...")
            main()
            logging.info("應用程序初始化完成")
        except Exception as app_init_error:
            logging.error(f"初始化主應用時出錯: {app_init_error}")
            if not force:
                raise app_init_error
            logging.warning("由於指定了強制啟動，我們將嘗試繼續啟動服務器...")
        
        logging.info("準備啟動服務器...")
        return True
    except Exception as e:
        logging.error(f"啟動應用程序時出錯: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # 檢查命令行參數
    host = "0.0.0.0"
    port = 5001
    debug = True
    force = True  # 默認強制啟動
    
    if "--help" in sys.argv or "-h" in sys.argv:
        print("用法: python app_startup.py [host] [port] [debug] [--force/--no-force]")
        print("  host: 伺服器主機地址 (預設: 0.0.0.0)")
        print("  port: 伺服器埠號 (預設: 5001)")
        print("  debug: 是否啟用除錯模式 (預設: True)")
        print("  --force/--no-force: 是否強制啟動，即使檢查失敗 (預設: --force)")
        sys.exit(0)
    
    if "--no-force" in sys.argv:
        force = False
        sys.argv.remove("--no-force")
    elif "--force" in sys.argv:
        force = True
        sys.argv.remove("--force")
    
    if len(sys.argv) > 1 and sys.argv[1][0] != "-":
        host = sys.argv[1]
    
    if len(sys.argv) > 2 and sys.argv[2][0] != "-":
        try:
            port = int(sys.argv[2])
        except ValueError:
            print(f"無效的埠號: {sys.argv[2]}，使用預設埠號 5001")
    
    if len(sys.argv) > 3 and sys.argv[3][0] != "-":
        debug = sys.argv[3].lower() == "true"
    
    # 啟動應用
    if startup(force):
        try:
            logging.info(f"開始運行 PC 服務端，地址: {host}:{port}")
            socketio.run(app, host=host, port=port, debug=debug)
        except Exception as e:
            logging.error(f"運行服務器時出錯: {e}")
            traceback.print_exc()
            sys.exit(1)
    else:
        logging.error("應用程序啟動失敗")
        sys.exit(1)