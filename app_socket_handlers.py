import logging
import os
import time
from datetime import datetime
from flask import request
from flask_socketio import emit
from app_audio import generate_tts

# 全局變量，用於存儲最新一幀
global latest_frame, last_camera_log_time, camera_frame_count
latest_frame = None
last_camera_log_time = 0
camera_frame_count = 0

def get_latest_frame():
    """獲取最新一幀，提供給其他模塊使用"""
    global latest_frame
    return latest_frame

def register_socket_handlers(socketio, stt_selector, chatbot, current_input_mode, 
                             current_output_mode, phone_mode_manager, phone_mode_active,
                             should_trigger_vision, analyze_current_frame, save_chat_message,
                             generate_tts, record_audio, pc_recorder, connected_robots):
    """注册所有Socket.IO事件处理程序"""
    
    @socketio.on('connect')
    def handle_connect():
        """处理新连接"""
        client_id = request.sid
        logging.info(f"新客户端连接: {client_id}")
        emit('system_info', {'message': '已连接到服务器'})

    @socketio.on('robot_connect')
    def handle_robot_connect(data):
        """处理机器人连接"""
        from app_robot_control import RobotStatus
        
        robot_id = request.sid
        connected_robots[robot_id] = {
            'id': robot_id,
            'status': RobotStatus()
        }
        logging.info(f"机器人 {robot_id} 已连接")
        broadcast_robot_status(robot_id)

    @socketio.on('heartbeat')
    def handle_heartbeat(data):
        """处理心跳包"""
        robot_id = request.sid
        if robot_id in connected_robots:
            status = connected_robots[robot_id]['status']
            status.last_heartbeat = time.time()
            status.status = "connected"
            # 更新机器人状态
            if 'battery' in data:
                status.battery = data['battery']
            if 'temperature' in data:
                status.temperature = data['temperature']

            emit('heartbeat_response', {
                'status': 'active',
                'timestamp': time.time(),
                'battery': status.battery,
                'temperature': status.temperature
            }, broadcast=True)
            broadcast_robot_status(robot_id)

    @socketio.on('switch_whisper_mode')
    def handle_switch_whisper_mode(data):
        """处理Whisper模式切换"""
        try:
            mode = data.get('mode')
            config = {
                'local_whisper_model': data.get('local_model'),
                'azure_whisper_model': data.get('azure_model')
            }
            
            result = stt_selector.switch_mode(mode, config)
            status = stt_selector.get_status()
            
            emit('whisper_mode_switched', {
                'success': True,
                'message': result,
                'current_status': status
            })
        except Exception as e:
            emit('whisper_mode_switched', {
                'success': False,
                'message': str(e)
            })

    @socketio.on('start_phone_mode')
    def handle_start_phone_mode():
        """啟動電話模式"""
        nonlocal phone_mode_active
        
        try:
            if phone_mode_active:
                emit('error', {'message': '電話模式已經啟動'})
                return
            
            # 啟動電話模式
            success = phone_mode_manager.start()
            
            if success:
                phone_mode_active = True
                emit('phone_mode_started')
                logging.info("電話模式已啟動")
            else:
                emit('error', {'message': '無法啟動電話模式'})
                
        except Exception as e:
            logging.error(f"啟動電話模式時出錯: {e}")
            emit('error', {'message': f'啟動電話模式時出錯: {str(e)}'})

    @socketio.on('stop_phone_mode')
    def handle_stop_phone_mode():
        """停止電話模式"""
        nonlocal phone_mode_active
        
        try:
            success = phone_mode_manager.stop()
            
            if success:
                phone_mode_active = False
                emit('phone_mode_stopped')
                logging.info("電話模式已停止")
            else:
                emit('error', {'message': '無法停止電話模式'})
                
        except Exception as e:
            logging.error(f"停止電話模式時出錯: {e}")
            emit('error', {'message': f'停止電話模式時出錯: {str(e)}'})

    @socketio.on('robot_vad_audio')
    def handle_robot_vad_audio(data):
        """處理機器人VAD檢測到的語音"""
        if not phone_mode_active:
            return
        
        try:
            # 從機器人接收到音頻數據
            audio_data = data.get('audio_data')
            if not audio_data:
                return
            
            # 通知前端檢測到語音
            emit('phone_mode_speech_detected', broadcast=True)
            
            # 保存音頻到臨時文件
            temp_file = "uploads/phone_mode_audio.wav"
            os.makedirs("uploads", exist_ok=True)
            
            with open(temp_file, 'wb') as f:
                f.write(audio_data)
            
            # 轉錄語音
            from app_audio import transcribe_audio
            transcribed_text = transcribe_audio(temp_file)
            
            if not transcribed_text:
                logging.warning("電話模式無法識別語音內容")
                return
            
            # 記錄用戶語音輸入到聊天歷史
            user_message = {
                "type": "sent",
                "text": f"📞 {transcribed_text}",
                "timestamp": datetime.now().isoformat(),
                "audioSrc": None
            }
            save_chat_message(user_message)
            
            # 使用 chatbot 處理語音指令
            ai_response = chatbot.get_response(transcribed_text)
            tts_file = generate_tts(ai_response)
            
            # 記錄 AI 回應到聊天歷史
            ai_message = {
                "type": "received",
                "text": f"📞 {ai_response}",
                "timestamp": datetime.now().isoformat(),
                "audioSrc": tts_file
            }
            save_chat_message(ai_message)
            
            # 發送回應到前端
            emit('phone_mode_response', {
                "text": ai_response,
                "audio_file": tts_file
            }, broadcast=True)
            
            # 將TTS發送給機器人播放
            if tts_file:
                with open(f"static{tts_file}", 'rb') as f:
                    tts_data = f.read()
                
                for robot_id in connected_robots:
                    emit('play_audio', {
                        'audio_data': tts_data
                    }, room=robot_id)
        
        except Exception as e:
            logging.error(f"處理電話模式語音時出錯: {e}")
            import traceback
            traceback.print_exc()

    @socketio.on('set_input_mode')
    def handle_set_input_mode(data):
        """设置输入模式"""
        nonlocal current_input_mode
        mode = data.get('mode')
        if mode in ['pc_microphone', 'robot_microphone']:
            current_input_mode = mode
            emit('mode_update', {'type': 'input', 'mode': mode})
            logging.info(f"输入模式已切换为: {mode}")

    @socketio.on('set_output_mode')
    def handle_set_output_mode(data):
        """設置輸出模式"""
        nonlocal current_output_mode
        mode = data.get('mode')
        if mode in ['pc_speaker', 'robot_speaker']:
            current_output_mode = mode
            # 更新app_audio.py中的輸出模式
            from app_audio import set_output_mode
            set_output_mode(mode)
            emit('mode_update', {'type': 'output', 'mode': mode})
            logging.info(f"輸出模式已切換為: {mode}")
            print(f"[INFO] 輸出模式切換為: {mode}")

    @socketio.on('get_chat_history')
    def handle_get_chat_history():
        """返回聊天歷史紀錄"""
        from app_main import chat_history
        emit('chat_history_loaded', chat_history)

    @socketio.on('clear_chat_history')
    def handle_clear_chat_history():
        """清除聊天歷史紀錄"""
        from app_main import chat_history, CHAT_HISTORY_FILE
        chat_history["messages"] = []
        
        try:
            if os.path.exists(CHAT_HISTORY_FILE):
                os.remove(CHAT_HISTORY_FILE)
            emit('chat_history_cleared', {'status': 'success'})
            logging.info("聊天歷史已清除")
        except Exception as e:
            logging.error(f"清除聊天歷史紀錄時發生錯誤: {e}")
            emit('chat_history_cleared', {'status': 'error', 'message': str(e)})

    @socketio.on('text_input')
    def handle_text_input(data):
        """處理文字輸入並生成 AI 音頻回應"""
        text = data.get("text", "")
        if not text:
            emit('response', {"text": "輸入為空，請重新輸入", "status": "error"})
            return

        try:
            # 記錄用戶輸入到聊天歷史
            user_message = {
                "type": "sent",
                "text": text,
                "timestamp": datetime.now().isoformat(),
                "audioSrc": None
            }
            save_chat_message(user_message)
            
            # 檢查是否是要求分析畫面的命令
            if should_trigger_vision(text):
                # 觸發 AI Vision 分析
                analyze_current_frame()
                return

            # 使用 chatbot 取得 AI 回應
            ai_response = chatbot.get_response(text)

            # 生成語音回應
            tts_file = generate_tts(ai_response)
            
            # 記錄 AI 回應到聊天歷史
            ai_message = {
                "type": "received",
                "text": ai_response,
                "timestamp": datetime.now().isoformat(),
                "audioSrc": tts_file
            }
            save_chat_message(ai_message)

            # 發送回應
            emit('response', {
                "text": ai_response,
                "audio_file": tts_file,
                "status": "success"
            })

            print(f"[INFO] 文字輸入: {text}")
            print(f"[INFO] AI 回應: {ai_response}")

        except Exception as e:
            print(f"[ERROR] 文字輸入處理失敗: {e}")
            emit('response', {
                "text": "處理請求時出錯，請稍後重試",
                "status": "error"
            })

    @socketio.on('start_recording')
    def handle_start_recording():
        """當前端發送錄音指令時，執行電腦錄音，轉錄並發送給 AI"""
        try:
            # 檢查提示音文件
            if not os.path.exists("static/start_beep.wav") or not os.path.exists("static/stop_beep.wav"):
                emit('error', {'message': "找不到提示音檔案"})
                return
                
            # 通知前端開始錄音
            emit('start_recording_confirmed')
            
            audio_file = record_audio()
            
            # 通知前端結束錄音
            emit('stop_recording_confirmed')
            
            from app_audio import transcribe_audio
            transcribed_text = transcribe_audio(audio_file)

            if not transcribed_text:
                emit('response', {"text": "無法識別語音內容。", "status": "error"})
                return

            # 記錄用戶語音輸入到聊天歷史
            user_message = {
                "type": "sent",
                "text": f"🎤 {transcribed_text}",
                "timestamp": datetime.now().isoformat(),
                "audioSrc": None
            }
            save_chat_message(user_message)

            print(f"[DEBUG] 語音轉錄結果: {transcribed_text}")

            # 使用 should_trigger_vision 函數檢查是否需要觸發 AI Vision 分析
            if should_trigger_vision(transcribed_text):
                print("[DEBUG] 偵測到語音詢問畫面內容，開始影像分析")
                analyze_current_frame()
                return  # 直接返回，避免 chatbot 處理這句話

            # 取得 AI 回應
            ai_response = chatbot.get_response(transcribed_text)
            tts_file = generate_tts(ai_response)
            
            # 記錄 AI 回應到聊天歷史
            ai_message = {
                "type": "received",
                "text": ai_response,
                "timestamp": datetime.now().isoformat(),
                "audioSrc": tts_file
            }
            save_chat_message(ai_message)

            emit('response', {
                "text": ai_response,
                "audio_file": tts_file,
                "status": "success"
            })

        except Exception as e:
            print(f"[ERROR] 錄音或轉錄失敗: {e}")
            emit('error', {'message': f"錄音或轉錄失敗: {str(e)}"})

    @socketio.on('audio_uploaded')
    def handle_audio_upload(data):
        """處理音頻上傳"""
        try:
            filename = "user_audio.wav"
            content = data.get('content')

            if not content:
                raise ValueError("接收到空的音頻數據")

            filepath = os.path.join("uploads", filename)
            os.makedirs("uploads", exist_ok=True)

            # 保存音頻文件
            with open(filepath, 'wb') as f:
                f.write(content)

            # 轉錄音頻
            text = audio_manager.speech_to_text(filepath)
            if not text:
                raise ValueError("音頻轉錄失敗")
                
            # 記錄用戶語音輸入到聊天歷史
            user_message = {
                "type": "sent",
                "text": f"🎤 {text}",
                "timestamp": datetime.now().isoformat(),
                "audioSrc": None
            }
            save_chat_message(user_message)

            # 獲取 ChatBot 回應
            response = chatbot.get_response(text)

            # 生成語音回應
            tts_audio = audio_manager.text_to_speech(response)
            
            # 記錄 AI 回應到聊天歷史
            ai_message = {
                "type": "received",
                "text": response,
                "timestamp": datetime.now().isoformat(),
                "audioSrc": "/output.wav"
            }
            save_chat_message(ai_message)

            # 讀取音頻文件的二進制數據
            with open("output.wav", 'rb') as f:
                audio_data = f.read()

            # 發送回應
            emit('response', {
                "text": response,
                "audio_file": "output.wav",
                "audio_data": audio_data
            })

        except Exception as e:
            logging.error(f"處理音頻時出錯: {str(e)}")
            emit('error', {'message': f"處理音頻時出錯: {str(e)}"})

    @socketio.on('control_action')
    def handle_control_action(data):
        """處理動作控制"""
        action = data.get('action')
        if not action:
            emit('error', {'message': '無效的動作指令'})
            return

        try:
            # 檢查是否有連接的機器人
            if not connected_robots:
                emit('action_status', {
                    'status': 'error',
                    'message': '沒有連接的機器人'
                })
                return

            # 向所有連接的機器人發送動作指令
            for robot_id in connected_robots:
                emit('execute_action', {'action': action}, room=robot_id)
                logging.info(f"向機器人 {robot_id} 發送動作指令: {action}")

            emit('action_status', {
                'status': 'sent',
                'action': action,
                'message': f'已發送動作指令: {action}'
            })

        except Exception as e:
            logging.error(f"發送動作指令時出錯: {e}")
            emit('action_status', {
                'status': 'error',
                'message': f'發送指令時出錯: {str(e)}'
            })

    @socketio.on('action_completed')
    def handle_action_completed(data):
        """处理动作完成响应"""
        robot_id = request.sid
        action = data.get('action')
        status = data.get('status')
        emit('action_status', {
            'status': status,
            'action': action,
            'robot_id': robot_id
        }, broadcast=True)

    @socketio.on('start_camera')
    def handle_start_camera():
        """開始攝像頭串流"""
        print("[DEBUG] 收到開始攝像頭命令")
        # 檢查是否有連接的機器人
        if not connected_robots:
            print("[ERROR] 沒有連接的機器人")
            emit('camera_error', {
                'message': '沒有連接的機器人',
                'code': 'NO_ROBOT'
            })
            return
        
        for robot_id in connected_robots:
            print(f"[DEBUG] 向機器人 {robot_id} 發送開始攝像頭命令")
            emit('start_camera', room=robot_id)
        
        emit('camera_start_confirmed')

    @socketio.on('stop_camera')
    def handle_stop_camera():
        """停止攝像頭串流"""
        print("[DEBUG] 收到停止攝像頭命令")
        # 檢查是否有連接的機器人
        if not connected_robots:
            print("[ERROR] 沒有連接的機器人")
            emit('camera_error', {
                'message': '沒有連接的機器人',
                'code': 'NO_ROBOT'
            })
            return
        
        for robot_id in connected_robots:
            print(f"[DEBUG] 向機器人 {robot_id} 發送停止攝像頭命令")
            emit('stop_camera', room=robot_id)
        
        emit('camera_stop_confirmed')

    @socketio.on('camera_stream')
    def handle_camera_stream(data):
        """接收來自機械人的影像數據並轉發到前端"""
        global latest_frame, last_camera_log_time, camera_frame_count
        
        try:
            latest_frame = data['image']
            
            # 计数并控制日志输出
            camera_frame_count += 1
            current_time = time.time()
            
            if current_time - last_camera_log_time >= 10:
                print(f"[DEBUG] 收到攝像頭影像：已接收 {camera_frame_count} 幀")
                last_camera_log_time = current_time
                camera_frame_count = 0
            
            # 發送影像給前端
            socketio.emit('update_frame', {'image': latest_frame})
        
        except Exception as e:
            print(f"[ERROR] Camera stream error: {e}")

    @socketio.on('analyze_camera_frame')
    def handle_analyze_frame():
        """分析當前攝像頭畫面"""
        try:
            global latest_frame
            
            if latest_frame is None or latest_frame == "":
                print("[ERROR] analyze_camera_frame: 沒有可用的攝像頭畫面")
                emit('analysis_result', {
                    'success': False,
                    'message': '沒有可用的攝像頭畫面'
                })
                return
                
            print(f"[DEBUG] 開始分析攝像頭畫面，數據長度: {len(latest_frame) if latest_frame else 0}")
            analyze_current_frame(socketio)

        except Exception as e:
            print(f"[ERROR] 分析圖片時出錯: {str(e)}")
            emit('analysis_result', {
                'success': False,
                'message': f'分析失敗: {str(e)}'
            })

    @socketio.on('disconnect')
    def handle_disconnect():
        """处理断开连接"""
        client_id = request.sid
        if client_id in connected_robots:
            del connected_robots[client_id]
            logging.info(f"机器人 {client_id} 断开连接")
            emit('robot_disconnected', {'robot_id': client_id}, broadcast=True)

    @socketio.on_error()
    def handle_error(e):
        """处理 WebSocket 错误"""
        logging.error(f"WebSocket error: {str(e)}")
        emit('error', {'message': '操作出错，请重试'})

    def broadcast_robot_status(robot_id):
        """广播机器人状态更新"""
        if robot_id in connected_robots:
            status = connected_robots[robot_id]['status']
            emit('robot_status_update', {
                'robot_id': robot_id,
                'status': status.status,
                'battery': status.battery,
                'temperature': status.temperature
            }, broadcast=True)