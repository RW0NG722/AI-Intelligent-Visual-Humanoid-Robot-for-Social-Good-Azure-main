import subprocess
import logging
import json


class RobotStatus:
    def __init__(self):
        self.last_heartbeat = None
        self.status = "disconnected"
        self.battery = 100
        self.temperature = 25


def execute_singledigit_action(action_id, repeat_count='1'):
    """執行單位數動作(0-9)"""
    try:
        logging.info(f"執行單位數動作: {action_id}, 重複 {repeat_count} 次")

        # 確保參數為字符串
        action_id_str = str(action_id)
        repeat_count_str = str(repeat_count)

        # 使用完全相同的格式和長度，與成功案例保持一致
        curl_command = [
            "curl",
            "-X", "POST", "http://192.168.137.3:9030/",
            "-H", "deviceid: your_device_id",
            "-H", "X-JSON-RPC: RunAction",
            "-H", "er: false",
            "-H", "dr: false",
            "-H", "Content-Type: text/x-markdown; charset=utf-8",
            "-H", "Content-Length: 76",  # 保留原始長度
            "-H", "Connection: Keep-Alive",
            "-H", "Accept-Encoding: gzip",
            "-H", "User-Agent: okhttp/4.9.1",
            "-d", f'{{"id":1732853986186,"jsonrpc":"2.0","method":"RunAction","params":["{action_id_str}","{repeat_count_str}"]}}'
        ]

        result = subprocess.run(curl_command, capture_output=True, text=True)

        if result.returncode == 0:
            logging.info(f"成功執行單位數動作 {action_id}, 重複 {repeat_count} 次")
        else:
            logging.error(f"執行單位數動作失敗: {result.stderr}")

        return json.dumps({
            "stdout": result.stdout,
            "stderr": result.stderr
        })
    except Exception as e:
        logging.error(f"執行單位數動作時出錯: {e}")
        return json.dumps({
            "error": str(e)
        })


def execute_doubledigit_action(action_id, repeat_count='1'):
    """執行雙位數動作(10-99)"""
    try:
        logging.info(f"執行雙位數動作: {action_id}, 重複 {repeat_count} 次")

        # 確保參數為字符串
        action_id_str = str(action_id)
        repeat_count_str = str(repeat_count)

        # 使用完全相同的格式和長度，與成功案例保持一致
        curl_command = [
            "curl",
            "-X", "POST", "http://192.168.149.1:9030/",
            "-H", "deviceid: your_device_id",
            "-H", "X-JSON-RPC: RunAction",
            "-H", "er: false",
            "-H", "dr: false",
            "-H", "Content-Type: text/x-markdown; charset=utf-8",
            "-H", "Content-Length: 77",  # 保留原始長度
            "-H", "Connection: Keep-Alive",
            "-H", "Accept-Encoding: gzip",
            "-H", "User-Agent: okhttp/4.9.1",
            "-d", f'{{"id":1732853986186,"jsonrpc":"2.0","method":"RunAction","params":["{action_id_str}","{repeat_count_str}"]}}'
        ]

        result = subprocess.run(curl_command, capture_output=True, text=True)

        if result.returncode == 0:
            logging.info(f"成功執行雙位數動作 {action_id}, 重複 {repeat_count} 次")
        else:
            logging.error(f"執行雙位數動作失敗: {result.stderr}")

        return json.dumps({
            "stdout": result.stdout,
            "stderr": result.stderr
        })
    except Exception as e:
        logging.error(f"執行雙位數動作時出錯: {e}")
        return json.dumps({
            "error": str(e)
        })


def record_action_execution(action_id, action_name):
    """記錄機器人動作執行到聊天歷史"""
    try:
        from app_main import save_chat_message
        from datetime import datetime

        action_message = {
            "type": "received",
            "text": f"🤖 已執行動作: {action_name}",
            "timestamp": datetime.now().isoformat(),
            "audioSrc": None
        }
        save_chat_message(action_message)

        logging.info(f"已記錄動作執行: {action_name}")
    except Exception as e:
        logging.error(f"記錄動作執行時出錯: {e}")


def get_robot_status(robot_id):
    """获取指定机器人的状态"""
    from app_main import connected_robots

    if robot_id in connected_robots:
        status = connected_robots[robot_id]['status']
        return {
            'robot_id': robot_id,
            'status': status.status,
            'battery': status.battery,
            'temperature': status.temperature,
            'last_heartbeat': status.last_heartbeat
        }
    else:
        return None


def get_all_robots_status():
    """获取所有连接的机器人状态"""
    from app_main import connected_robots

    result = []
    for robot_id, robot_info in connected_robots.items():
        status = robot_info['status']
        result.append({
            'robot_id': robot_id,
            'status': status.status,
            'battery': status.battery,
            'temperature': status.temperature,
            'last_heartbeat': status.last_heartbeat
        })

    return result


def execute_wave_action():
    """执行挥手动作，这是一个经常用到的快捷方式"""
    return execute_singledigit_action('9', '1')


def execute_sequence_of_actions(action_sequence):
    """
    执行一系列按顺序排列的动作
    action_sequence 格式: [('single', '9', '1'), ('double', '10', '1'), ...]
    """
    import time

    results = []
    for action_type, action_id, repeat_count in action_sequence:
        try:
            if action_type == 'single':
                result = execute_singledigit_action(action_id, repeat_count)
            else:
                result = execute_doubledigit_action(action_id, repeat_count)

            results.append({
                'action_id': action_id,
                'type': action_type,
                'repeat': repeat_count,
                'result': result
            })

            # 等待动作完成，避免动作重叠
            # 简单动作等待2秒，复杂动作等待4秒
            wait_time = 2 if action_type == 'single' else 4
            time.sleep(wait_time)

        except Exception as e:
            logging.error(f"执行动作序列时出错: {e}")
            results.append({
                'action_id': action_id,
                'type': action_type,
                'repeat': repeat_count,
                'error': str(e)
            })

    return results


def convert_cantonese_to_action(text):
    """根据广东话指令判断要执行的动作"""
    from app_main import chatbot

    action_map = {
        '揮手': ('single', '9', '1'),
        '招手': ('single', '9', '1'),
        '打招呼': ('single', '9', '1'),
        '鞠躬': ('double', '10', '1'),
        '左轉': ('single', '7', '1'),
        '右轉': ('single', '8', '1'),
        '前進': ('single', '1', '1'),
        '後退': ('single', '2', '1'),
        '跳舞': 'dance',
        '詠春': 'wing_chun'
    }

    # 简单的关键词匹配
    for keyword, action in action_map.items():
        if keyword in text:
            if action == 'dance':
                # 特殊处理：跳舞
                chatbot.custom_actions.random_dance()
                return [{'action': 'dance', 'status': 'executed'}]
            elif action == 'wing_chun':
                # 特殊处理：咏春
                chatbot.custom_actions.wing_chun()
                return [{'action': 'wing_chun', 'status': 'executed'}]
            else:
                # 正常单一动作
                action_type, action_id, repeat = action
                if action_type == 'single':
                    execute_singledigit_action(action_id, repeat)
                else:
                    execute_doubledigit_action(action_id, repeat)
                return [{'action': keyword, 'status': 'executed'}]

    return None  # 没有匹配到任何动作
