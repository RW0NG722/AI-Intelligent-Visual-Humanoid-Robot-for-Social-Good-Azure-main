HI # Intelligent Robot Control System (Server Side)

## 🤖 Overview

> 🔗 **Robot Side Repository**: [vtcfypA05_robot](https://github.com/Ash0Lam/vtcfypA05-Robot)

This project is part of the Intelligent Robot Control System:

- **Server Side (Current Repository)**: Web interface and AI processing
- **[Robot Side](https://github.com/Ash0Lam/vtcfypA05-Robot)**: Hardware control and sensor management

This is a Python-based intelligent robot control system that integrates voice recognition, natural language processing, and multi-modal interaction capabilities. The system supports robot control through both web interface and voice commands, with real-time status monitoring.

## ✨ Key Features

- 🎮 **Multi-Modal Control**

  - Support for voice and text input
  - Web-based control interface
  - **Phone mode for continuous voice interaction**

- 🧠 **Intelligent Dialogue**

  - Azure OpenAI integration for natural language understanding
  - Knowledge base queries and web search capabilities
  - **Specialized in Cantonese responses and interactions**

- 🎤 **Voice Recognition**

  - **Flexible speech recognition with both local Whisper and Azure Speech Services**
  - Text-to-speech functionality with natural Cantonese voice
  - **Voice activity detection and automatic recording**

- 👁️ **Computer Vision**

  - **Azure Vision API integration for image analysis**
  - **Real-time camera feed analysis and description**
  - **Object and person detection capabilities**

- 🌐 **Web Interface**
  - Intuitive visual control dashboard
  - Real-time robot status monitoring
  - **Camera feed display and analysis**
  - **Testing tools for audio and vision components**

## 🛠 System Requirements

### API Requirements

- Azure OpenAI API access
- Azure Speech Services access
- **Azure Vision API access**
- Google Custom Search API (optional)

### Hardware Requirements

- **Webcam or compatible camera (for vision features)**
- Microphone and audio equipment (for voice features)
- **Robot hardware with HTTP API support (default: 192.168.149.1:9030)**

### Essential Tools

- **Microsoft Visual C++ Build Tools**
  - Download: [Microsoft Visual C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
  - Select "C++ Build Tools" during installation to support Python packages like `PyAudio` and `webrtcvad`

## 📥 Installation Guide

### 1. Install Python 3.12.6

Download and install [Python 3.12.6](https://www.python.org/downloads/release/python-3126/). Make sure to check "Add Python to PATH" during installation.

### 2. Install Microsoft Visual C++ Build Tools

Download and install [Microsoft Visual C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/). Ensure the build tools are properly configured in your system.

### 3. Set Up Virtual Environment & Dependencies

#### Create and Activate Virtual Environment

```powershell
python -m venv venv
.\venv\Scripts\Activate
```

#### Install Dependencies

```powershell
pip install -r requirements.txt
```

For manual dependency installation:

```powershell
pip install flask flask-socketio openai-whisper sounddevice scipy pyttsx3 pyaudio webrtcvad pydub azure-cognitiveservices-speech langchain langchain-core langchain-openai openai python-dotenv pygame azure-core azure-ai-vision-imageanalysis
```

## ⚙️ Environment Configuration

Create a `.env` file in the project root and add the following API keys:

```plaintext
AZURE_OPENAI_API_KEY=your_key_here
AZURE_OPENAI_ENDPOINT=your_endpoint_here
AZURE_SPEECH_API_KEY=your_key_here
AZURE_SPEECH_REGION=your_region_here
AZURE_VISION_ENDPOINT=your_endpoint_here
AZURE_VISION_KEY=your_key_here
GOOGLE_API_KEY=your_key_here  # Optional
GOOGLE_CSE_ID=your_cse_id_here  # Optional, for web search
```

## 🚀 Launch Application

### 1. Start Server

```bash
python app_startup.py
```

### 2. Access Web Interface

Open your browser and navigate to `http://localhost:5001` to access the control panel:

- Choose input mode (voice/text)
- Execute robot commands

## 📁 Project Structure

```plaintext
.
├── app_main.py            # Main application entry point
├── app_startup.py         # Application startup and initialization
├── app_socket_handlers.py # WebSocket communication handlers
├── app_audio.py           # Audio processing and TTS functionality
├── app_vision.py          # Computer vision integration
├── app_utils.py           # Utility functions
├── app_robot_control.py   # Robot action control
├── app_phone_mode.py      # Phone mode implementation
├── chatbot.py             # Chatbot core logic
├── whisper_selector.py    # Speech recognition selector (local/cloud)
├── pc_recorder.py         # PC-based voice recording
├── custom_actions.py      # Custom robot action sequences
├── google_search.py       # Google search integration
├── config.py              # Configuration and API keys
├── static/                # Static resources (CSS, JS, audio)
├── templates/             # HTML templates
└── requirements.txt       # Dependency list
```

## 📖 Usage Guide

### Web Interface Usage

1. Open browser and visit `http://localhost:5001`
2. Use the control panel to:
   - Execute robot actions
   - Monitor robot status
   - **Control camera functions**
   - **Analyze camera feed**
   - **Test audio and vision components**

### Voice Control

- Supported languages:
  - Chinese (Mandarin/Cantonese)
  - English
- Use the microphone button on the web interface to send voice commands
- **Vision-related commands (e.g., "你看到什麼" / "What do you see") will trigger camera analysis**

### **Phone Mode**

- **Click the phone icon to enter continuous conversation mode**
- **System will listen for voice input, process it, and respond automatically**
- **Ideal for hands-free operation**

### **Camera Functions**

- **Click the camera icon to open the camera feed**
- **Use the analysis button to get a description of what the robot sees**
- **Camera can detect people and automatically wave when a person is identified**

### **Testing Tools**

- **Access testing tools through the settings menu**
- **Upload audio files to test speech recognition**
- **Upload images to test vision analysis**

## ⚠️ Important Notes

1. **Microsoft Visual C++ Build Tools** installation is mandatory for proper functioning of dependencies like `PyAudio` and `webrtcvad`.

2. Ensure you're using the correct Python version (3.12.6) when installing dependencies.

3. **Camera permissions** must be granted for vision features to work properly.

4. **When using Whisper for the first time**, the system will download the selected model, which may take some time depending on your internet connection.

5. **The robot should be on the same network** as the server, and accessible via HTTP at the configured IP address (default: 192.168.149.1).
"# AI-Intelligent-Visual-Humanoid-Robot-for-Social-Good-Azure" 
