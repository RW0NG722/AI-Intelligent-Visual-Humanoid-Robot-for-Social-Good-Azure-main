// 初始化 Socket.IO
const socket = io();

// DOM 元素引用
const chatMessages = document.getElementById('chat-messages');
const textInput = document.getElementById('text-input');
const sendTextButton = document.getElementById('send-text-button');
const recordButton = document.getElementById('record-button');
const cameraButton = document.getElementById('camera-button');
const phoneButton = document.getElementById('phone-button');
const systemStatus = document.getElementById('system-status');
const batteryLevel = document.getElementById('battery-level');
const temperatureValue = document.getElementById('temperature-value');
const actionResponse = document.getElementById('actionResponse');
const clearHistoryButton = document.getElementById('clear-history');
const actionToast = document.getElementById('action-toast');
const actionToastText = document.getElementById('action-toast-text');
const phoneModeContainer = document.getElementById('phone-mode-container');
const endPhoneCallButton = document.getElementById('end-phone-call');
const autoPlayAudioCheckbox = document.getElementById('autoPlayAudio');
const lastHeartbeatTime = document.getElementById('last-heartbeat-time');

// 消息歷史記錄
let messageHistory = [];
const MAX_HISTORY = 15;
// 電話模式變量
let phoneMode = false;
let phoneCallStartTime = null;
let phoneCallTimer = null;
// 測試模式變量
let testModeEnabled = false;
let audioPlayQueue = [];
let isPlayingAudio = false;

// 用於記錄已自動播放過的 TTS 文件，確保每個 TTS 只自動播放一次
const autoPlayedAudioFiles = new Set();

// 自動調整文本輸入框高度
textInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});

// 從本地存儲加載聊天記錄
function loadChatHistory() {
    const savedHistory = localStorage.getItem('chatHistory');
    if (savedHistory) {
        try {
            messageHistory = JSON.parse(savedHistory);
            
            // 檢查是否需要清理過期記錄（24小時）
            const currentTime = new Date().getTime();
            const oneDayAgo = currentTime - (24 * 60 * 60 * 1000);
            const firstMessageTime = messageHistory.length > 0 ? new Date(messageHistory[0].timestamp).getTime() : currentTime;
            
            if (firstMessageTime < oneDayAgo) {
                console.log("聊天記錄已過期，清除記錄");
                messageHistory = [];
                localStorage.removeItem('chatHistory');
                return;
            }
            
            // 顯示歷史消息
            messageHistory.forEach(message => {
                addMessageToUI(message.text, message.type, message.timestamp, message.audioSrc);
                
                // 將歷史記錄中的音頻文件標記為已播放，防止重新加載頁面時自動播放
                if (message.audioSrc) {
                    autoPlayedAudioFiles.add(message.audioSrc.split('?')[0]); // 去除時間戳參數
                }
            });
            
            // 滾動到底部
            scrollToBottom();
        } catch (e) {
            console.error('Failed to load chat history:', e);
            // 如果解析失敗，清空歷史記錄
            localStorage.removeItem('chatHistory');
        }
    }
}

// 保存聊天記錄到本地存儲
function saveChatHistory() {
    localStorage.setItem('chatHistory', JSON.stringify(messageHistory));
}

// 全局音頻標記
const audioSources = {
    CHATBOT: 'chatbot',
    NOTIFICATION: 'notification',
    PHONE: 'phone',
    CURRENT: null
};

// 音頻播放函數
function playQueuedAudio() {
    if (audioPlayQueue.length === 0 || isPlayingAudio) {
        return;
    }
    
    // 阻止在錄音過程中播放聊天機器人音頻
    if (recordButton.classList.contains('recording') && 
        audioPlayQueue[0].getAttribute('data-source') === audioSources.CHATBOT) {
        console.log("錄音中，阻止播放聊天機器人音頻");
        return;
    }
    
    isPlayingAudio = true;
    const audioElement = audioPlayQueue.shift();
    audioSources.CURRENT = audioElement.getAttribute('data-source');
    
    audioElement.onended = () => {
        isPlayingAudio = false;
        audioSources.CURRENT = null;
        setTimeout(playQueuedAudio, 50);
    };
    
    audioElement.onerror = () => {
        console.log("音頻播放失敗");
        isPlayingAudio = false;
        audioSources.CURRENT = null;
        setTimeout(playQueuedAudio, 50);
    };
    
    try {
        const playPromise = audioElement.play();
        if (playPromise) {
            playPromise.catch(e => {
                console.log("自動播放失敗:", e);
                isPlayingAudio = false;
                audioSources.CURRENT = null;
                setTimeout(playQueuedAudio, 50);
            });
        }
    } catch (e) {
        console.log("播放過程發生異常:", e);
        isPlayingAudio = false;
        audioSources.CURRENT = null;
        setTimeout(playQueuedAudio, 50);
    }
}

// 添加消息到 UI
function addMessageToUI(text, type, timestamp = new Date(), audioSrc = null) {
    // 創建消息容器
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type === 'system' ? 'system-message' : 'message-content ' + type}`;
    
    // 系統消息特殊處理
    if (type === 'system') {
        messageDiv.textContent = text;
        chatMessages.appendChild(messageDiv);
        return;
    }
    
    // 正常消息
    const messageContent = document.createElement('div');
    messageContent.textContent = text;
    
    const timeSpan = document.createElement('div');
    timeSpan.className = 'timestamp';
    timeSpan.textContent = formatTimestamp(timestamp);
    
    messageDiv.appendChild(messageContent);
    messageDiv.appendChild(timeSpan);
    
    // 如果有音頻，添加音頻播放器
    if (audioSrc) {
        const audioDiv = document.createElement('div');
        audioDiv.className = 'message-audio';
        
        const audio = document.createElement('audio');
        audio.controls = true;
        audio.src = audioSrc;
        
        audioDiv.appendChild(audio);
        messageDiv.appendChild(audioDiv);
    }
    
    chatMessages.appendChild(messageDiv);
    
    // 滾動到底部
    scrollToBottom();
}

// 滾動到對話底部
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// 添加消息到歷史記錄
function addMessageToHistory(text, type, audioSrc = null) {
    const message = {
        text: text,
        type: type,
        timestamp: new Date(),
        audioSrc: audioSrc
    };
    
    // 添加到歷史記錄
    messageHistory.push(message);
    
    // 如果超過最大限制，移除最舊的消息
    if (messageHistory.length > MAX_HISTORY) {
        messageHistory.shift();
    }
    
    // 保存到本地存儲
    saveChatHistory();
    
    // 添加到 UI
    addMessageToUI(text, type, message.timestamp, audioSrc);
}

// 格式化時間戳
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// 格式化電話通話時間
function formatPhoneTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

// 更新電話通話計時器
function updatePhoneTimer() {
    if (!phoneCallStartTime) return;
    
    const elapsedSeconds = Math.floor((Date.now() - phoneCallStartTime) / 1000);
    document.querySelector('.phone-mode-timer').textContent = formatPhoneTime(elapsedSeconds);
}

// 清除聊天記錄
function clearChatHistory() {
    messageHistory = [];
    localStorage.removeItem('chatHistory');
    chatMessages.innerHTML = '';
    showSystemMessage('聊天記錄已清除');
}

// 顯示系統消息
function showSystemMessage(text) {
    addMessageToHistory(text, 'system');
}

// 顯示動作提示
function showActionToast(text, duration = 3000) {
    actionToastText.textContent = text;
    actionToast.classList.add('show');
    
    setTimeout(() => {
        actionToast.classList.remove('show');
    }, duration);
}

// 修改電話模式回應處理
socket.on('phone_mode_response', function(data) {
    console.log('收到電話模式回應:', data);
    addMessageToHistory(`📞 ${data.text}`, 'received', data.audio_file);
    
    if (data.audio_file) {
        console.log('準備播放音頻:', data.audio_file);
        
        // 檢查此音頻文件是否已經自動播放過
        const audioFileBase = data.audio_file.split('?')[0]; // 去除時間戳參數
        
        if (!autoPlayedAudioFiles.has(audioFileBase)) {
            // 如果沒有自動播放過，則播放並記錄
            playPhoneTts(data.audio_file);
            autoPlayedAudioFiles.add(audioFileBase);
            console.log('已將音頻標記為已自動播放:', audioFileBase);
        } else {
            console.log('跳過已自動播放過的音頻:', audioFileBase);
        }
    }
});

// 連接狀態更新
socket.on('connect', () => {
    updateSystemStatus(true);
    showSystemMessage('已連接到服務器');
});

socket.on('disconnect', () => {
    updateSystemStatus(false);
    showSystemMessage('與服務器斷開連接');
});

// 更新系統狀態
function updateSystemStatus(connected) {
    const statusIndicator = systemStatus.querySelector('.status-indicator');
    
    if (statusIndicator) {
        statusIndicator.className = `status-indicator ${connected ? 'status-connected' : 'status-disconnected'}`;
        systemStatus.innerHTML = `<span class="status-indicator ${connected ? 'status-connected' : 'status-disconnected'}"></span> 系統狀態：${connected ? '已連接' : '未連接'}`;
    } else {
        systemStatus.innerHTML = `<span class="status-indicator ${connected ? 'status-connected' : 'status-disconnected'}"></span> 系統狀態：${connected ? '已連接' : '未連接'}`;
    }
}

// 更新電池狀態
function updateBatteryStatus(level) {
    batteryLevel.style.width = `${level}%`;
    batteryLevel.style.backgroundColor = level > 20 ? '#28a745' : '#dc3545';
}

// 更新溫度狀態
function updateTemperatureStatus(temp) {
    temperatureValue.textContent = `${temp}°C`;
    temperatureValue.style.color = temp < 50 ? '#fff' : '#ffc107';
}

let lastPlayedAudioFile = null;
let isCurrentlyPlayingTTS = false;

// 修改播放音頻的函數
function playAudio(audioFile) {
    // 如果是同一個音頻文件且正在播放中，則不重複播放
    if (audioFile === lastPlayedAudioFile && isCurrentlyPlayingTTS) {
        console.log('已在播放相同的音頻，跳過重複播放');
        return;
    }
    
    const audio = new Audio(audioFile);
    lastPlayedAudioFile = audioFile;
    isCurrentlyPlayingTTS = true;
    
    audio.onended = function() {
        isCurrentlyPlayingTTS = false;
    };
    
    audio.play().catch(e => {
        console.error('音頻播放失敗:', e);
        isCurrentlyPlayingTTS = false;
    });
}

// 電話模式下TTS播放
function playPhoneTts(audioFile) {
    console.log('播放電話模式TTS:', audioFile);
    const audio = new Audio(audioFile);
    audio.play().catch(e => {
        console.error('電話模式TTS播放失敗:', e);
    });
}

// 發送文字消息
function sendTextMessage() {
    const text = textInput.value.trim();
    if (text) {
        // 添加到 UI 和歷史記錄
        addMessageToHistory(text, 'sent');
        
        // 發送到服務器
        socket.emit('text_input', { text });
        
        // 清空輸入框
        textInput.value = '';
        textInput.style.height = 'auto';
        
        // 顯示處理中狀態
        showSystemMessage('正在處理訊息...');
    }
}

// 改進錄音處理函數
function handleRecording() {
    const micIcon = recordButton.querySelector('i');
    
    if (recordButton.classList.contains('recording')) {
        // 結束錄音
        recordButton.classList.remove('recording', 'btn-danger', 'recording-animation');
        micIcon.className = 'fas fa-microphone';
        socket.emit('stop_recording');
    } else {
        // 開始錄音前暫停所有音頻
        document.querySelectorAll('audio').forEach(audio => {
            try {
                if (!audio.paused) {
                    audio.pause();
                    audio.currentTime = 0;
                }
            } catch (e) {}
        });
        
        // 清空音頻隊列
        audioPlayQueue = [];
        isPlayingAudio = false;
        
        // 開始錄音
        recordButton.classList.add('recording', 'btn-danger', 'recording-animation');
        micIcon.className = 'fas fa-stop';
        socket.emit('start_recording');
    }
}


// 切換電話模式
function togglePhoneMode() {
    if (phoneMode) {
        // 停止電話模式
        stopPhoneMode();
    } else {
        // 開始電話模式
        startPhoneMode();
    }
}

// 音頻播放函數
function playAudioFile(src) {
    return new Promise((resolve, reject) => {
        const audio = new Audio(src);
        audio.onended = resolve;
        audio.onerror = reject;
        audio.play().catch(reject);
    });
}

// 開始電話模式
// 在電話模式啟動時禁用所有音頻自動播放
function startPhoneMode() {
    phoneMode = true;
    phoneButton.classList.add('phone-mode-active');
    phoneModeContainer.classList.add('active');
    
    // 禁用音頻自動播放
    disableAutoPlay = true;
    
    // 開始計時
    phoneCallStartTime = Date.now();
    phoneCallTimer = setInterval(updatePhoneTimer, 1000);
    updatePhoneTimer();
    
    // 發送開始命令到服務器
    socket.emit('start_phone_mode');
    
    showSystemMessage('已啟動電話模式 - 機器人將自動接聽並回應');
}

// 停止電話模式時恢復自動播放
function stopPhoneMode() {
    phoneMode = false;
    phoneButton.classList.remove('phone-mode-active');
    phoneModeContainer.classList.remove('active');
    
    // 恢復音頻自動播放
    disableAutoPlay = false;
    
    // 停止計時
    clearInterval(phoneCallTimer);
    phoneCallStartTime = null;
    
    // 發送停止命令到服務器
    socket.emit('stop_phone_mode');
    
    showSystemMessage('已退出電話模式');
}



// 單位數動作執行
function executeSingleDigitAction(actionId, repeatCount) {
    const payload = {
        params: JSON.stringify([actionId, repeatCount])
    };
    
    fetch('/execute_singledigit_action', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
        handleActionResponse(data, `執行動作: ${getActionName(actionId)}`);
    })
    .catch(error => showActionError('執行失敗', error.message));
}

// 雙位數動作執行
function executeDoubleDigitAction(actionId, repeatCount) {
    const payload = {
        params: JSON.stringify([actionId, repeatCount])
    };
    
    fetch('/execute_doubledigit_action', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
        handleActionResponse(data, `執行動作: ${getActionName(actionId)}`);
    })
    .catch(error => showActionError('執行失敗', error.message));
}

// 根據動作ID獲取動作名稱
function getActionName(actionId) {
    const actionNames = {
        '0': '立正', '1': '前進', '2': '後退', '3': '左移', '4': '右移', 
        '5': '俯臥撐', '6': '仰臥起坐', '7': '左轉', '8': '右轉', '9': '揮手',
        '10': '鞠躬', '11': '下蹲', '12': '慶祝', '13': '左腳踢', '14': '右腳踢',
        '15': '詠春', '16': '左勾拳', '17': '右勾拳', '18': '左側踢', '19': '右側踢',
        '22': '扭腰', '24': '原地踏步', '35': '舉重'
    };
    return actionNames[actionId] || `動作 ${actionId}`;
}

// 處理動作響應
function handleActionResponse(data, actionText) {
    if (data.stdout) {
        try {
            const result = JSON.parse(data.stdout);
            if (result.result && result.result[0] === true) {
                showActionSuccess(actionText);
                // 添加機器人動作訊息到聊天記錄
                addMessageToHistory(`🤖 ${actionText} 已完成`, 'received');
                // 顯示提示
                showActionToast(`${actionText} 已執行`);
            } else if (result.error) {
                showActionError('錯誤', JSON.stringify(result.error));
            }
        } catch (e) {
            showActionError('解析錯誤', '響應資料格式錯誤');
        }
    }
}

// 顯示動作成功消息
function showActionSuccess(message) {
    actionResponse.innerHTML = `<div class="alert alert-success py-2">${message} 成功！</div>`;
    setTimeout(() => {
        actionResponse.innerHTML = '';
    }, 3000);
}

// 顯示動作錯誤消息
function showActionError(title, message) {
    actionResponse.innerHTML = `<div class="alert alert-danger py-2"><strong>${title}</strong><br><small>${message}</small></div>`;
    setTimeout(() => {
        actionResponse.innerHTML = '';
    }, 3000);
}

// 格式化時間函數
function formatTimeWithSeconds(date) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

// 處理測試模式開關
function toggleTestMode(enabled) {
    testModeEnabled = enabled;
    const testPanel = document.getElementById('test-panel');
    
    if (enabled) {
        // 顯示測試面板
        if (testPanel) testPanel.style.display = 'block';
        // 添加測試模式標記
        document.body.classList.add('test-mode-active');
        // 記錄到localStorage
        localStorage.setItem('testModeEnabled', 'true');
        // 顯示系統消息
        showSystemMessage('已啟用測試模式');
    } else {
        // 隱藏測試面板
        if (testPanel) testPanel.style.display = 'none';
        // 移除測試模式標記
        document.body.classList.remove('test-mode-active');
        // 記錄到localStorage
        localStorage.setItem('testModeEnabled', 'false');
        // 顯示系統消息
        showSystemMessage('已停用測試模式');
    }
}

// 處理音頻文件上傳
function handleAudioUpload() {
    const fileInput = document.getElementById('audio-file');
    const uploadResult = document.getElementById('upload-result');
    const playButton = document.getElementById('play-uploaded-audio');
    const audioPlayer = document.getElementById('audio-player');
    const playerContainer = document.getElementById('player-container');
    
    if (!fileInput || !fileInput.files || !fileInput.files[0]) {
        if (uploadResult) {
            uploadResult.innerHTML = `<div class="alert alert-warning">請先選擇音頻文件</div>`;
        }
        return;
    }
    
    const file = fileInput.files[0];
    
    // 檢查文件類型
    if (file.type !== 'audio/wav' && !file.name.toLowerCase().endsWith('.wav')) {
        if (uploadResult) {
            uploadResult.innerHTML = `<div class="alert alert-danger">請上傳 WAV 格式的音頻文件</div>`;
        }
        return;
    }
    
    // 顯示加載中
    if (uploadResult) {
        uploadResult.innerHTML = `<div class="spinner-border spinner-border-sm text-primary" role="status"></div> 上傳並處理中...`;
    }
    
    // 創建 FormData 對象
    const formData = new FormData();
    formData.append('audio', file);
    
    // 使用 Fetch API 上傳文件
    fetch('/api/test/upload-audio', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            if (uploadResult) {
                uploadResult.innerHTML = `<div class="alert alert-success">
                    <strong>上傳成功!</strong><br>
                    <small>識別結果：${data.text || '無文字'}</small>
                </div>`;
            }
            
            // 啟用播放按鈕
            if (playButton) {
                playButton.disabled = false;
            }
            
            // 設置音頻播放器
            if (audioPlayer && playerContainer) {
                audioPlayer.src = data.audio_url || '';
                playerContainer.style.display = 'block';
            }
            
            // 顯示識別文本和回復（如果有）
            if (data.text) {
                addMessageToHistory(`🔊 [測試] ${data.text}`, 'sent');
            }
            
            if (data.response) {
                addMessageToHistory(data.response, 'received', data.response_audio);
                
                // 確保回應音頻播放器自動播放
                if (data.response_audio) {
                    // 檢查此音頻文件是否已經自動播放過
                    const audioFileBase = data.response_audio.split('?')[0]; // 去除時間戳參數
                    
                    if (!autoPlayedAudioFiles.has(audioFileBase)) {
                        setTimeout(() => {
                            const allAudios = document.querySelectorAll('.message-audio audio');
                            if (allAudios.length > 0) {
                                const latestAudio = allAudios[allAudios.length - 1];
                                latestAudio.play().catch(e => console.log("測試回應播放器自動播放失敗:", e));
                                
                                // 標記為已自動播放
                                autoPlayedAudioFiles.add(audioFileBase);
                            }
                        }, 100);
                    } else {
                        console.log('跳過已自動播放過的音頻:', audioFileBase);
                    }
                }
            }
        } else {
            if (uploadResult) {
                uploadResult.innerHTML = `<div class="alert alert-danger">
                    <strong>上傳失敗</strong><br>
                    <small>${data.message || '未知錯誤'}</small>
                </div>`;
            }
        }
    })
    .catch(error => {
        console.error('上傳錯誤:', error);
        if (uploadResult) {
            uploadResult.innerHTML = `<div class="alert alert-danger">
                <strong>處理錯誤</strong><br>
                <small>${error.message || '未知錯誤'}</small>
            </div>`;
        }
    });
}

// 創建和播放不會干擾主音頻的提示音函數
let lastNotificationSound = null;

function playNotificationSound(soundUrl) {
    // 停止正在播放的提示音
    if (lastNotificationSound) {
        try {
            lastNotificationSound.pause();
            lastNotificationSound.currentTime = 0;
        } catch (e) {
            console.log("停止先前提示音失敗:", e);
        }
    }
    
    // 創建新的音頻元素，與DOM完全分離
    const notificationSound = new Audio();
    
    // 使用獨立的事件處理
    notificationSound.addEventListener('canplaythrough', () => {
        try {
            // 使用Promise來處理播放
            const playPromise = notificationSound.play();
            if (playPromise) {
                playPromise.catch(e => console.log("提示音播放失敗:", e));
            }
        } catch (e) {
            console.log("提示音播放異常:", e);
        }
    }, { once: true });
    
    // 設置音頻來源
    notificationSound.src = soundUrl;
    notificationSound.volume = 0.7; // 稍微降低音量避免干擾
    
    // 保存引用
    lastNotificationSound = notificationSound;
}

// 修改 response 事件處理中的音頻播放部分
socket.on('response', (data) => {
    // 移除處理中消息
    const processingMessages = document.querySelectorAll('.system-message');
    processingMessages.forEach(msg => {
        if (msg.textContent.includes('處理')) {
            msg.remove();
        }
    });
    
    // 添加时间戳参数以避免缓存问题
    const audioSrc = data.audio_file ? `${data.audio_file}?t=${new Date().getTime()}` : null;
    
    // 添加到歷史記錄
    addMessageToHistory(data.text, 'received', audioSrc);
    
    // 如果有音頻文件，檢查是否需要自動播放
    if (audioSrc) {
        // 檢查此音頻文件是否已經自動播放過
        const audioFileBase = data.audio_file.split('?')[0]; // 去除時間戳參數
        
        if (!autoPlayedAudioFiles.has(audioFileBase)) {
            // 等待DOM更新後找到最新的音頻元素
            setTimeout(() => {
                const allAudios = document.querySelectorAll('.message-audio audio');
                if (allAudios.length > 0) {
                    const latestAudio = allAudios[allAudios.length - 1];
                    
                    // 標記音頻來源
                    latestAudio.setAttribute('data-source', audioSources.CHATBOT);
                    
                    // 將音頻添加到播放隊列
                    audioPlayQueue.push(latestAudio);
                    playQueuedAudio();
                    
                    // 標記為已自動播放
                    autoPlayedAudioFiles.add(audioFileBase);
                    console.log('已將音頻標記為已自動播放:', audioFileBase);
                }
            }, 100); // 小延遲確保DOM已更新
        } else {
            console.log('跳過已自動播放過的音頻:', audioFileBase);
        }
    }
});

// 修改開始錄音確認事件
let beepAudio = null;

socket.on('start_recording_confirmed', () => {
    // 暫停並移除所有當前播放的音頻
    document.querySelectorAll('audio').forEach(audio => {
        try {
            if (!audio.paused) {
                audio.pause();
                audio.currentTime = 0;
            }
        } catch (e) {}
    });
    
    // 停止所有隊列中的音頻播放
    audioPlayQueue = [];
    isPlayingAudio = false;
    
    // UI 更新
    recordButton.classList.add('recording', 'btn-danger', 'recording-animation');
    recordButton.querySelector('i').className = 'fas fa-stop';
    
    // 完全獨立的音頻元素用於播放提示音
    if (beepAudio) {
        beepAudio.pause();
        beepAudio.currentTime = 0;
    }
    
    beepAudio = new Audio();
    // 直接設置事件處理
    beepAudio.oncanplaythrough = () => {
        // 立即播放，不依賴於全局音頻系統
        beepAudio.play().catch(e => console.log("提示音播放失敗:", e));
    };
    beepAudio.src = '/static/start_beep.wav';
    
    // 添加系統消息
    showSystemMessage('開始錄音...');
});

socket.on('stop_recording_confirmed', () => {
    // UI 更新
    recordButton.classList.remove('recording', 'btn-danger', 'recording-animation');
    recordButton.querySelector('i').className = 'fas fa-microphone';
    
    // 完全獨立的音頻元素用於播放提示音
    if (beepAudio) {
        beepAudio.pause();
        beepAudio.currentTime = 0;
    }
    
    beepAudio = new Audio();
    beepAudio.oncanplaythrough = () => {
        // 立即播放，不依賴於全局音頻系統
        beepAudio.play().catch(e => console.log("提示音播放失敗:", e));
    };
    beepAudio.src = '/static/stop_beep.wav';
    
    // 添加系統消息
    showSystemMessage('錄音結束，正在處理...');
});

// 為提示音和TTS添加互斥鎖
const audioLock = {
    notification: false,
    tts: false
};
// 從伺服器接收播放音頻的指令
socket.on('play_audio', (data) => {
    if (data.audio_file) {
        // 檢查此音頻文件是否已經自動播放過
        const audioFileBase = data.audio_file.split('?')[0]; // 去除時間戳參數
        
        if (!autoPlayedAudioFiles.has(audioFileBase)) {
            // 自動播放界面播放器
            setTimeout(() => {
                const allAudios = document.querySelectorAll('.message-audio audio');
                if (allAudios.length > 0) {
                    const latestAudio = allAudios[allAudios.length - 1];
                    latestAudio.play().catch(e => console.log("播放器自動播放失敗:", e));
                    
                    // 標記為已自動播放
                    autoPlayedAudioFiles.add(audioFileBase);
                }
            }, 100);
        } else {
            console.log('跳過已自動播放過的音頻:', audioFileBase);
        }
    }
});

// 心跳响应
socket.on('heartbeat_response', (data) => {
    // 更新機器人狀態
    if (data.battery !== undefined) {
        updateBatteryStatus(data.battery);
    }
    if (data.temperature !== undefined) {
        updateTemperatureStatus(data.temperature);
    }
    
    // 更新最後心跳時間
    const now = new Date();
    if (lastHeartbeatTime) {
        lastHeartbeatTime.textContent = formatTimeWithSeconds(now);
    }
});

// 動作完成響應
socket.on('action_completed', (data) => {
    if (data.status === 'completed') {
        showActionSuccess(`動作 ${data.name} 執行完成`);
        showActionToast(`動作 ${data.name} 已完成`);
    } else {
        showActionError('動作執行失敗', data.error || '未知錯誤');
    }
});

// 動作狀態響應
socket.on('action_status', (data) => {
    if (data.status === 'error') {
        showActionError('動作錯誤', data.message);
    } else {
        showActionSuccess(data.message);
    }
});

// 更新語音檢測提示
socket.on('phone_mode_speech_detected', () => {
    // 添加系統消息
    showSystemMessage('檢測到語音輸入...');
});

// 添加錯誤處理
socket.on('error', (data) => {
    showSystemMessage(`錯誤: ${data.message}`);
    console.error('Socket.IO error:', data.message);
    
    // 如果是電話模式相關錯誤，可能需要重置狀態
    if (phoneMode && data.message.includes("電話模式")) {
        phoneMode = false;
        phoneButton.classList.remove('phone-mode-active');
        phoneModeContainer.classList.remove('active');
        clearInterval(phoneCallTimer);
        phoneCallStartTime = null;
    }
});

socket.on('start_recording_confirmed', () => {
    recordButton.classList.add('recording', 'btn-danger', 'recording-animation');
    recordButton.querySelector('i').className = 'fas fa-stop';
    
    // 暫停所有正在播放的音頻
    document.querySelectorAll('audio').forEach(audio => {
        try {
            if (!audio.paused) {
                audio.pause();
                console.log("已暫停現有音頻播放");
            }
        } catch (e) {}
    });
    
    // 清空播放隊列
    audioPlayQueue = [];
    isPlayingAudio = false;
    
    // 使用新的提示音函數
    setTimeout(() => {
        playNotificationSound('/static/start_beep.wav');
    }, 50);
    
    // 添加系統消息
    showSystemMessage('開始錄音...');
});

// 結束錄音確認
socket.on('stop_recording_confirmed', () => {
    recordButton.classList.remove('recording', 'btn-danger', 'recording-animation');
    recordButton.querySelector('i').className = 'fas fa-microphone';
    
    // 播放結束提示音
    const stopBeep = new Audio('/static/stop_beep.wav');
    stopBeep.play();
    
    // 添加系統消息
    showSystemMessage('錄音結束，正在處理...');
});

// 攝像頭相關事件
socket.on('camera_start_confirmed', () => {
    showSystemMessage('攝像頭已開啟');
    // 不需要更新主攝像頭，只更新側邊欄攝像頭狀態
});

socket.on('camera_stop_confirmed', () => {
    showSystemMessage('攝像頭已關閉');
    // 更新側邊欄攝像頭狀態
    const sideRobotCamera = document.getElementById('side-robot-camera');
    const sideCameraPlaceholder = document.getElementById('side-camera-placeholder');
    
    if (sideRobotCamera) sideRobotCamera.style.display = 'none';
    if (sideCameraPlaceholder) sideCameraPlaceholder.style.display = 'flex';
});

socket.on('pc_webcam_start_confirmed', () => {
    showSystemMessage('本地網絡攝像頭已開啟');
    // 更新側邊欄使用本地攝像頭按鈕狀態
    const sideUseLocalCamera = document.getElementById('side-use-local-camera');
    if (sideUseLocalCamera) sideUseLocalCamera.classList.add('active');
});

socket.on('pc_webcam_stop_confirmed', () => {
    showSystemMessage('本地網絡攝像頭已關閉');
    // 更新側邊欄使用本地攝像頭按鈕狀態
    const sideUseLocalCamera = document.getElementById('side-use-local-camera');
    if (sideUseLocalCamera) sideUseLocalCamera.classList.remove('active');
    
    // 更新側邊欄攝像頭狀態
    const sideRobotCamera = document.getElementById('side-robot-camera');
    const sideCameraPlaceholder = document.getElementById('side-camera-placeholder');
    
    if (sideRobotCamera) sideRobotCamera.style.display = 'none';
    if (sideCameraPlaceholder) sideCameraPlaceholder.style.display = 'flex';});

socket.on('update_frame', (data) => {
    if (data.image) {
        // 只更新側邊欄攝像頭
        const sideRobotCamera = document.getElementById('side-robot-camera');
        const sideCameraPlaceholder = document.getElementById('side-camera-placeholder');
        
        if (sideRobotCamera) {
            sideRobotCamera.src = "data:image/jpeg;base64," + data.image;
            
            // 強制顯示攝像頭圖像，隱藏佔位符
            sideRobotCamera.style.display = 'block';
            if (sideCameraPlaceholder) {
                sideCameraPlaceholder.style.display = 'none';
            }
        }
        
        // 顯示來源提示
        if (data.source === 'pc_webcam') {
            robotCamera.setAttribute('data-source', 'PC 網絡攝像頭');
        } else {
            robotCamera.setAttribute('data-source', '機器人攝像頭');
        }
    }
});

socket.on('camera_error', (error) => {
    showSystemMessage(`攝像頭錯誤: ${error.message}`);
    cameraPlaceholder.style.display = 'flex';
    robotCamera.style.display = 'none';
});

socket.on('analysis_result', (data) => {
    if (data.success) {
        const { caption, objects, tags } = data.analysis;
        
        let resultText = `📷 分析結果: ${caption}`;
        
        if (objects && objects.length > 0) {
            resultText += `\n🔍 識別物件: ${objects.join(', ')}`;
        }
        
        addMessageToHistory(resultText, 'received');
        
        // 如果有TTS文件，檢查是否需要自動播放
        if (data.tts_file) {
            // 檢查此音頻文件是否已經自動播放過
            const audioFileBase = data.tts_file.split('?')[0]; // 去除時間戳參數
            
            if (!autoPlayedAudioFiles.has(audioFileBase)) {
                setTimeout(() => {
                    const allAudios = document.querySelectorAll('.message-audio audio');
                    if (allAudios.length > 0) {
                        const latestAudio = allAudios[allAudios.length - 1];
                        latestAudio.play().catch(e => {
                            console.log("攝像頭分析TTS自動播放失敗:", e);
                        });
                        
                        // 標記為已自動播放
                        autoPlayedAudioFiles.add(audioFileBase);
                    }
                }, 100);
            } else {
                console.log('跳過已自動播放過的音頻:', audioFileBase);
            }
        }
    } else {
        showSystemMessage(`分析失敗: ${data.message}`);
    }
});

// 歷史記錄同步
socket.on('chat_history_loaded', (data) => {
    if (messageHistory.length === 0 && data.messages && data.messages.length > 0) {
        showSystemMessage('已從伺服器加載聊天記錄');
        
        // 清空現有記錄
        messageHistory = [];
        chatMessages.innerHTML = '';
        
        // 加載新的記錄
        data.messages.forEach(message => {
            messageHistory.push(message);
            addMessageToUI(message.text, message.type, message.timestamp, message.audioSrc);
            
            // 將歷史記錄中的音頻文件標記為已播放
            if (message.audioSrc) {
                autoPlayedAudioFiles.add(message.audioSrc.split('?')[0]); // 去除時間戳參數
            }
        });
        
        // 保存到本地存儲
        saveChatHistory();
    }
});

socket.on('chat_history_cleared', (data) => {
    if (data.status === 'success') {
        clearChatHistory();
    } else {
        showSystemMessage(`清除聊天記錄失敗: ${data.message}`);
    }
});

// 更新電話模式的狀態顯示
socket.on('phone_mode_started', () => {
    phoneMode = true;
    phoneButton.classList.add('phone-mode-active');
    phoneModeContainer.classList.add('active');
    
    // 開始計時
    phoneCallStartTime = Date.now();
    phoneCallTimer = setInterval(updatePhoneTimer, 1000);
    updatePhoneTimer();
});

socket.on('phone_mode_stopped', () => {
    phoneMode = false;
    phoneButton.classList.remove('phone-mode-active');
    phoneModeContainer.classList.remove('active');
    
    // 停止計時
    clearInterval(phoneCallTimer);
    phoneCallStartTime = null;
});

// Whisper模式切换相关事件处理
socket.on('whisper_mode_switched', function(data) {
    const resultDiv = document.getElementById('whisper-test-result');
    
    if (data.success) {
        resultDiv.innerHTML = `<div class="alert alert-success">
            <i class="fas fa-check-circle"></i> ${data.message}<br>
            <small>當前模式: ${data.current_status.mode}, 
            模型: ${data.current_status.mode === 'local' ? data.current_status.local_model : data.current_status.azure_model}</small>
        </div>`;
    } else {
        resultDiv.innerHTML = `<div class="alert alert-danger">
            <i class="fas fa-times-circle"></i> 測試失敗: ${data.message}
        </div>`;
    }
});

// 加載Whisper設置
function loadWhisperSettings() {
    // 從localStorage讀取Whisper設置
    const mode = localStorage.getItem('WHISPER_MODE');
    const localModel = localStorage.getItem('LOCAL_WHISPER_MODEL');
    const azureModel = localStorage.getItem('AZURE_WHISPER_MODEL');
    
    if (mode) document.getElementById('whisper-mode').value = mode;
    if (localModel) document.getElementById('local-whisper-model').value = localModel;
    if (azureModel) document.getElementById('azure-whisper-model').value = azureModel;
    
    // 切換顯示設置面板
    if (mode === 'azure') {
        document.getElementById('local-whisper-settings').style.display = 'none';
        document.getElementById('azure-whisper-settings').style.display = 'block';
    } else {
        document.getElementById('local-whisper-settings').style.display = 'block';
        document.getElementById('azure-whisper-settings').style.display = 'none';
    }
    
    // 從伺服器獲取當前設置
    fetch('/api/settings/whisper')
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const status = data.current_status;
            document.getElementById('whisper-mode').value = status.mode;
            
            if (status.local_model) {
                document.getElementById('local-whisper-model').value = status.local_model;
            }
            
            if (status.azure_model) {
                document.getElementById('azure-whisper-model').value = status.azure_model;
            }
            
            // 切換顯示設置面板
            if (status.mode === 'local') {
                document.getElementById('local-whisper-settings').style.display = 'block';
                document.getElementById('azure-whisper-settings').style.display = 'none';
            } else {
                document.getElementById('local-whisper-settings').style.display = 'none';
                document.getElementById('azure-whisper-settings').style.display = 'block';
            }
        }
    })
    .catch(error => console.error('獲取Whisper設置失敗:', error));
}

// DOMContentLoaded 事件處理
document.addEventListener('DOMContentLoaded', function() {
    // 發送按鈕點擊
    if (sendTextButton) {
        sendTextButton.addEventListener('click', sendTextMessage);
    }
    
    // 輸入框回車發送
    if (textInput) {
        textInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendTextMessage();
            }
        });
    }
    
    // 錄音按鈕點擊
    if (recordButton) {
        recordButton.addEventListener('click', handleRecording);
    }
    
    // 攝像頭按鈕點擊 - 改為提示用戶使用側邊欄攝像頭
    if (cameraButton) {
        cameraButton.addEventListener('click', () => {
            showSystemMessage('請使用右側邊欄的攝像頭控制');
        });
    }
    
    // 電話按鈕點擊
    if (phoneButton) {
        phoneButton.addEventListener('click', togglePhoneMode);
    }
    
    // 結束通話按鈕點擊
    if (endPhoneCallButton) {
        endPhoneCallButton.addEventListener('click', stopPhoneMode);
    }
    
    // 隱藏主攝像頭容器
    const cameraContainer = document.getElementById('camera-container');
    if (cameraContainer) {
        cameraContainer.style.display = 'none';
    }
    
    // 清除歷史記錄按鈕點擊
    if (clearHistoryButton) {
        clearHistoryButton.addEventListener('click', () => {
            if (confirm('確定要清除所有聊天記錄嗎？')) {
                socket.emit('clear_chat_history');
            }
        });
    }
    
    // 側邊攝像頭按鈕
    const sideStartCamera = document.getElementById('side-start-camera');
    if (sideStartCamera) {
        sideStartCamera.addEventListener('click', () => {
            socket.emit('start_camera');
            console.log("側邊欄：開始攝像頭");
        });
    }
    
    // 側邊欄攝像頭開啟按鈕
    document.getElementById('side-start-camera').addEventListener('click', function() {
        socket.emit('start_camera');
        const sideRobotCamera = document.getElementById('side-robot-camera');
        const sideCameraPlaceholder = document.getElementById('side-camera-placeholder');
        
        if (sideRobotCamera) sideRobotCamera.style.display = 'block';
        if (sideCameraPlaceholder) sideCameraPlaceholder.style.display = 'none';
    });

    // 側邊欄攝像頭關閉按鈕
    document.getElementById('side-stop-camera').addEventListener('click', function() {
        socket.emit('stop_camera');
    });

    // 側邊欄使用本地攝像頭按鈕
    document.getElementById('side-use-local-camera').addEventListener('click', function() {
        if (this.classList.contains('active')) {
            socket.emit('stop_pc_webcam');
            this.classList.remove('active');
        } else {
            socket.emit('start_pc_webcam');
            this.classList.add('active');
            
            // 顯示攝像頭畫面，隱藏佔位符
            const sideRobotCamera = document.getElementById('side-robot-camera');
            const sideCameraPlaceholder = document.getElementById('side-camera-placeholder');
            
            if (sideRobotCamera) sideRobotCamera.style.display = 'block';
            if (sideCameraPlaceholder) sideCameraPlaceholder.style.display = 'none';
        }
    });
    
    const sideStopCamera = document.getElementById('side-stop-camera');
    if (sideStopCamera) {
        sideStopCamera.addEventListener('click', () => {
            socket.emit('stop_camera');
            socket.emit('stop_pc_webcam');
            const sideUseLocalCamera = document.getElementById('side-use-local-camera');
            if (sideUseLocalCamera) {
                sideUseLocalCamera.classList.remove('active');
            }
            
            // 停止時恢復佔位符顯示
            const sideRobotCamera = document.getElementById('side-robot-camera');
            const sideCameraPlaceholder = document.getElementById('side-camera-placeholder');
            
            if (sideRobotCamera) sideRobotCamera.style.display = 'none';
            if (sideCameraPlaceholder) sideCameraPlaceholder.style.display = 'flex';
            console.log("側邊欄：停止攝像頭");
        });
    }
    
    
    // 修改分析攝像頭畫面功能，以使用側邊欄攝像頭
    window.analyzeCamera = function() {
    // 修改側邊欄攝像頭分析按鈕的事件處理程序
    document.getElementById('side-analyze-camera').addEventListener('click', function() {
        // 檢查側邊欄攝像頭是否開啟
        const sideRobotCamera = document.getElementById('side-robot-camera');
        
        if (sideRobotCamera && sideRobotCamera.style.display !== 'none') {
            showSystemMessage('正在分析畫面...');
            socket.emit('analyze_camera_frame');
        } else {
            showActionToast('請先開啟攝像頭', 2000);
        }
    });
    
    
    const sideUseLocalCamera = document.getElementById('side-use-local-camera');
    if (sideUseLocalCamera) {
        sideUseLocalCamera.addEventListener('click', () => {
            if (sideUseLocalCamera.classList.contains('active')) {
                socket.emit('stop_pc_webcam');
                sideUseLocalCamera.classList.remove('active');
            } else {
                socket.emit('stop_camera');
                socket.emit('start_pc_webcam');
                sideUseLocalCamera.classList.add('active');
            }
        });
    }
    
    // 只更新側邊欄攝像頭
    socket.on('update_frame', (data) => {
        if (data.image) {
            // 只更新側邊欄攝像頭
            const sideRobotCamera = document.getElementById('side-robot-camera');
            const sideCameraPlaceholder = document.getElementById('side-camera-placeholder');
            
            if (sideRobotCamera) {
                sideRobotCamera.src = "data:image/jpeg;base64," + data.image;
                
                // 即使src被更新時已經是顯示狀態，也要確保顯示方式正確
                sideRobotCamera.style.display = 'block';
                if (sideCameraPlaceholder) {
                    sideCameraPlaceholder.style.display = 'none';
                }
                console.log("側邊欄攝像頭畫面已更新");
            } else {
                console.log("找不到側邊欄攝像頭元素");
            }
        }
    });
    
    // 修改分析攝像頭畫面功能，以使用側邊欄攝像頭
    window.analyzeCamera = function() {
        const sideRobotCamera = document.getElementById('side-robot-camera');
        
        if (sideRobotCamera && sideRobotCamera.style.display !== 'none') {
            showSystemMessage('正在分析畫面...');
            socket.emit('analyze_camera_frame');
        } else {
            showActionToast('請先開啟攝像頭', 2000);
        }
    };
}});

// 設置 IP 按鈕點擊
const setIpButton = document.getElementById('set-ip-button');
if (setIpButton) {
    setIpButton.addEventListener('click', () => {
        const ipInput = document.getElementById('robot-ip');
        if (!ipInput) return;
        
        const ipAddress = ipInput.value.trim();
        if (ipAddress) {
            localStorage.setItem('robotIpAddress', ipAddress);
            showSystemMessage(`機器人 IP 設置為: ${ipAddress}`);
        }
    });
}

// Whisper 模式切換處理
const whisperMode = document.getElementById('whisper-mode');
if (whisperMode) {
    whisperMode.addEventListener('change', function() {
        const mode = this.value;
        const localSettings = document.getElementById('local-whisper-settings');
        const azureSettings = document.getElementById('azure-whisper-settings');
        
        if (mode === 'local') {
            if (localSettings) localSettings.style.display = 'block';
            if (azureSettings) azureSettings.style.display = 'none';
        } else {
            if (localSettings) localSettings.style.display = 'none';
            if (azureSettings) azureSettings.style.display = 'block';
        }
    });
}

// 測試Whisper設置
const testWhisperButton = document.getElementById('test-whisper-button');
if (testWhisperButton) {
    testWhisperButton.addEventListener('click', function() {
        const resultDiv = document.getElementById('whisper-test-result');
        if (!resultDiv) return;
        
        resultDiv.innerHTML = '<div class="spinner-border spinner-border-sm text-primary" role="status"></div> 測試中...';
        
        const whisperMode = document.getElementById('whisper-mode');
        const localModel = document.getElementById('local-whisper-model');
        const azureModel = document.getElementById('azure-whisper-model');
        
        if (!whisperMode || !localModel || !azureModel) return;
        
        const mode = whisperMode.value;
        const localModelValue = localModel.value;
        const azureModelValue = azureModel.value;
        
        // 發送測試請求
        socket.emit('switch_whisper_mode', {
            mode: mode,
            local_model: localModelValue,
            azure_model: azureModelValue
        });
    });
}

// 儲存設置按鈕點擊
const saveSettings = document.getElementById('save-settings');
if (saveSettings) {
    saveSettings.addEventListener('click', () => {
        const inputMode = document.getElementById('input-mode');
        const outputMode = document.getElementById('output-mode');
        const enableNotifications = document.getElementById('enableNotifications');
        
        if (inputMode) localStorage.setItem('inputMode', inputMode.value);
        if (outputMode) localStorage.setItem('outputMode', outputMode.value);
        if (enableNotifications) localStorage.setItem('notificationsEnabled', enableNotifications.checked.toString());
        
        // 將輸入和輸出模式發送到服務器
        if (inputMode) socket.emit('set_input_mode', { mode: inputMode.value });
        if (outputMode) socket.emit('set_output_mode', { mode: outputMode.value });
        
        // 顯示確認信息
        showSystemMessage(`設置已保存，輸出模式: ${outputMode ? outputMode.value : '未知'}`);
        
        // Whisper設置保存
        const whisperMode = document.getElementById('whisper-mode');
        const localModel = document.getElementById('local-whisper-model');
        const azureModel = document.getElementById('azure-whisper-model');
        
        if (whisperMode) localStorage.setItem('WHISPER_MODE', whisperMode.value);
        if (localModel) localStorage.setItem('LOCAL_WHISPER_MODEL', localModel.value);
        if (azureModel) localStorage.setItem('AZURE_WHISPER_MODEL', azureModel.value);
        
        // 發送到服務器
        if (whisperMode && localModel && azureModel) {
            socket.emit('switch_whisper_mode', {
                mode: whisperMode.value,
                local_model: localModel.value,
                azure_model: azureModel.value
            });
        }
        
        // 更新伺服器設置
        if (inputMode) socket.emit('set_input_mode', { mode: inputMode.value });
        if (outputMode) socket.emit('set_output_mode', { mode: outputMode.value });
        
        showSystemMessage(`設置已保存，語音識別模式: ${whisperMode ? whisperMode.value : '未知'}`);
    });
}

// 測試模式開關
const testModeToggle = document.getElementById('testModeToggle');
if (testModeToggle) {
    // 載入保存的設置
    const savedTestMode = localStorage.getItem('testModeEnabled');
    if (savedTestMode === 'true') {
        testModeToggle.checked = true;
        toggleTestMode(true);
    }
    
    // 監聽變更
    testModeToggle.addEventListener('change', function() {
        toggleTestMode(this.checked);
    });
}

// 音頻文件上傳
const uploadButton = document.getElementById('upload-audio');
if (uploadButton) {
    uploadButton.addEventListener('click', handleAudioUpload);
}

// 播放音頻
const playButton = document.getElementById('play-uploaded-audio');
const audioPlayer = document.getElementById('audio-player');
if (playButton && audioPlayer) {
    playButton.addEventListener('click', function() {
        if (audioPlayer.src) {
            audioPlayer.play().catch(e => console.error('播放失敗:', e));
        }
    });
}

// 文件選擇變更
const fileInput = document.getElementById('audio-file');
if (fileInput) {
    fileInput.addEventListener('change', function() {
        const playButton = document.getElementById('play-uploaded-audio');
        const playerContainer = document.getElementById('player-container');
        
        if (playButton) playButton.disabled = true;
        if (playerContainer) playerContainer.style.display = 'none';
        
        const uploadResult = document.getElementById('upload-result');
        if (uploadResult) uploadResult.innerHTML = '';
        
        if (this.files && this.files[0]) {
            const file = this.files[0];
            // 顯示選擇的文件名
            uploadResult.innerHTML = `<div class="alert alert-info">
                已選擇文件: ${file.name} (${(file.size / 1024).toFixed(2)} KB)
            </div>`;
        }
    });
}

// 初始化
try {
    loadWhisperSettings();
} catch (e) {
    console.error('載入Whisper設置失敗:', e);
}

try {
    loadChatHistory();
} catch (e) {
    console.error('載入聊天記錄失敗:', e);
}

// 如果記錄為空，顯示歡迎消息
if (messageHistory.length === 0) {
    addMessageToHistory('你好！我是機械人小助手，有什麼可以幫助你的嗎？', 'received');
}

// 請求從伺服器加載聊天記錄
socket.emit('get_chat_history');

// 讀取保存的設置
const savedIp = localStorage.getItem('robotIpAddress');
const robotIp = document.getElementById('robot-ip');
if (savedIp && robotIp) {
    robotIp.value = savedIp;
}

const savedInputMode = localStorage.getItem('inputMode');
const inputMode = document.getElementById('input-mode');
if (savedInputMode && inputMode) {
    inputMode.value = savedInputMode;
}

const savedOutputMode = localStorage.getItem('outputMode');
const outputMode = document.getElementById('output-mode');
if (savedOutputMode && outputMode) {
    outputMode.value = savedOutputMode;
}

const notificationsEnabled = localStorage.getItem('notificationsEnabled');
const enableNotifications = document.getElementById('enableNotifications');
if (notificationsEnabled !== null && enableNotifications) {
    enableNotifications.checked = notificationsEnabled === 'true';
}

// 處理圖片文件上傳
function handleImageUpload() {
    const fileInput = document.getElementById('image-file');
    const uploadResult = document.getElementById('image-upload-result');
    const previewButton = document.getElementById('preview-image');
    const imagePreview = document.getElementById('image-preview');
    const previewContainer = document.getElementById('image-preview-container');
    
    if (!fileInput || !fileInput.files || !fileInput.files[0]) {
        if (uploadResult) {
            uploadResult.innerHTML = `<div class="alert alert-warning">請先選擇圖片文件</div>`;
        }
        return;
    }
    
    const file = fileInput.files[0];
    
    // 檢查文件類型
    const validTypes = ['image/jpeg', 'image/jpg', 'image/png'];
    if (!validTypes.includes(file.type)) {
        if (uploadResult) {
            uploadResult.innerHTML = `<div class="alert alert-danger">請上傳 JPG 或 PNG 格式的圖片</div>`;
        }
        return;
    }
    
    // 顯示加載中
    if (uploadResult) {
        uploadResult.innerHTML = `<div class="spinner-border spinner-border-sm text-primary" role="status"></div> 上傳並分析中...`;
    }
    
    // 創建 FormData 對象
    const formData = new FormData();
    formData.append('image', file);
    
    // 使用 Fetch API 上傳文件
    fetch('/api/test/upload-image', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            if (uploadResult) {
                // 構建分析結果HTML
                let resultHtml = `<div class="alert alert-success">
                    <strong>分析成功!</strong>
                </div>
                <div class="card mt-2">
                    <div class="card-body p-2">
                        <h6 class="card-title">視覺分析結果:</h6>`;
                
                // 添加描述
                if (data.caption) {
                    resultHtml += `<p class="mb-1"><strong>描述:</strong> ${data.caption}</p>`;
                }
                
                // 添加標籤
                if (data.tags && data.tags.length > 0) {
                    resultHtml += `<p class="mb-1"><strong>標籤:</strong> `;
                    data.tags.forEach((tag, index) => {
                        resultHtml += `<span class="badge bg-info me-1">${tag}</span>`;
                    });
                    resultHtml += `</p>`;
                }
                
                // 添加物體
                if (data.objects && data.objects.length > 0) {
                    resultHtml += `<p class="mb-1"><strong>檢測到的物體:</strong> `;
                    data.objects.forEach((obj, index) => {
                        resultHtml += `<span class="badge bg-warning text-dark me-1">${obj}</span>`;
                    });
                    resultHtml += `</p>`;
                }
                
                // 添加人物检测结果
                if (data.detected_person) {
                    resultHtml += `<p class="mb-1"><strong>人物检测:</strong> <span class="badge bg-success me-1">已检测到人物</span></p>`;
                }
                
                resultHtml += `</div></div>`;
                
                uploadResult.innerHTML = resultHtml;
            }
            
            // 啟用預覽按鈕
            if (previewButton) {
                previewButton.disabled = false;
            }
            
            // 設置圖片預覽
            if (imagePreview && previewContainer && data.image_url) {
                imagePreview.src = data.image_url;
                previewContainer.style.display = 'block';
            }
            
            // 移除處理中消息 (與攝像頭分析完全一致)
            const processingMessages = document.querySelectorAll('.system-message');
            processingMessages.forEach(msg => {
                if (msg.textContent.includes('處理')) {
                    msg.remove();
                }
            });
            
            // 在聊天區域顯示回應
            if (data.analysis_text) {
                // 先显示用户上传的图片消息
                addMessageToHistory(`🖼️ [測試] 上傳了圖片`, 'sent');
                
                // 顯示處理中狀態 (與攝像頭分析相同)
                showSystemMessage('正在處理圖片...');
                
                // 將TTS文件路徑添加到ChatBot回應中
                addMessageToHistory(data.analysis_text, 'received', data.tts_file);
                
                // 自動播放TTS音頻 (與攝像頭分析完全一致)
                if (data.tts_file) {
                    // 檢查此音頻文件是否已經自動播放過
                    const audioFileBase = data.tts_file.split('?')[0]; // 去除時間戳參數
                    
                    if (!autoPlayedAudioFiles.has(audioFileBase)) {
                        setTimeout(() => {
                            const allAudios = document.querySelectorAll('.message-audio audio');
                            if (allAudios.length > 0) {
                                const latestAudio = allAudios[allAudios.length - 1];
                                latestAudio.play().catch(e => {
                                    console.log("圖片分析TTS自動播放失敗:", e);
                                    // 如果自動播放失敗，顯示提示
                                    showSystemMessage("請點擊播放按鈕聆聽回應");
                                });
                                
                                // 標記為已自動播放
                                autoPlayedAudioFiles.add(audioFileBase);
                            }
                        }, 100);
                    } else {
                        console.log('跳過已自動播放過的音頻:', audioFileBase);
                    }
                }
                
                // 如果检测到人物，显示执行动作的消息 (与攝像頭分析一致)
                if (data.detected_person) {
                    showActionToast("檢測到人物，執行揮手動作", 3000);
                    // 添加机器人动作訊息到聊天記錄
                    addMessageToHistory(`🤖 執行動作: 揮手 已完成`, 'received');
                }
            }
        } else {
            if (uploadResult) {
                uploadResult.innerHTML = `<div class="alert alert-danger">
                    <strong>分析失敗</strong><br>
                    <small>${data.message || '未知錯誤'}</small>
                </div>`;
            }
            
            // 显示错误消息在聊天区域 (与攝像頭分析一致)
            showSystemMessage(`圖片分析失敗: ${data.message || '未知錯誤'}`);
        }
    })
    .catch(error => {
        console.error('上傳錯誤:', error);
        if (uploadResult) {
            uploadResult.innerHTML = `<div class="alert alert-danger">
                <strong>處理錯誤</strong><br>
                <small>${error.message || '未知錯誤'}</small>
            </div>`;
        }
        
        // 显示错误消息在聊天区域
        showSystemMessage(`圖片上傳或處理時出錯: ${error.message || '未知錯誤'}`);
    });
}

// 在DOMContentLoaded事件中添加事件監聽器
document.addEventListener('DOMContentLoaded', function() {
    // 圖片上傳按鈕點擊
    const uploadImageButton = document.getElementById('upload-image');
    if (uploadImageButton) {
        uploadImageButton.addEventListener('click', handleImageUpload);
    }
    
    // 圖片預覽按鈕點擊
    const previewImageButton = document.getElementById('preview-image');
    const imagePreviewContainer = document.getElementById('image-preview-container');
    if (previewImageButton && imagePreviewContainer) {
        previewImageButton.addEventListener('click', function() {
            if (imagePreviewContainer.style.display === 'none') {
                imagePreviewContainer.style.display = 'block';
                previewImageButton.innerHTML = '<i class="fas fa-eye-slash me-1"></i>隱藏';
            } else {
                imagePreviewContainer.style.display = 'none';
                previewImageButton.innerHTML = '<i class="fas fa-eye me-1"></i>預覽';
            }
        });
    }
    
    // 圖片文件選擇變更
    const imageFileInput = document.getElementById('image-file');
    if (imageFileInput) {
        imageFileInput.addEventListener('change', function() {
            const previewButton = document.getElementById('preview-image');
            const previewContainer = document.getElementById('image-preview-container');
            
            if (previewButton) previewButton.disabled = true;
            if (previewContainer) previewContainer.style.display = 'none';
            
            const uploadResult = document.getElementById('image-upload-result');
            if (uploadResult) uploadResult.innerHTML = '';
            
            if (this.files && this.files[0]) {
                const file = this.files[0];
                // 顯示選擇的文件名
                uploadResult.innerHTML = `<div class="alert alert-info">
                    已選擇文件: ${file.name} (${(file.size / 1024).toFixed(2)} KB)
                </div>`;
                
                // 預覽圖片
                const reader = new FileReader();
                reader.onload = function(e) {
                    const imagePreview = document.getElementById('image-preview');
                    if (imagePreview) {
                        imagePreview.src = e.target.result;
                        imagePreview.onload = function() {
                            if (previewButton) previewButton.disabled = false;
                        };
                    }
                };
                reader.readAsDataURL(file);
            }
        });
    }
});
