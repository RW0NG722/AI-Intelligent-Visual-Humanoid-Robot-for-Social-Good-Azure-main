import requests
import config
from datetime import datetime
from langchain_openai import AzureChatOpenAI
from langchain.schema import HumanMessage
from azure.core.credentials import AzureKeyCredential

class GoogleSearch:
    def __init__(self):
        # Google Custom Search API 配置
        self.api_key = config.GOOGLE_API_KEY  # Google API Key
        self.search_engine_id = config.GOOGLE_CSE_ID  # Search Engine ID

        # Azure OpenAI API 配置
        self.openai_api_key = config.AZURE_OPENAI_API_KEY  # Azure OpenAI API Key
        self.openai_endpoint = config.AZURE_OPENAI_ENDPOINT  # Azure OpenAI API Endpoint
        
        # 初始化 langchain OpenAI 客户端
        self.client = AzureChatOpenAI(
            openai_api_key=self.openai_api_key,
            openai_endpoint=self.openai_endpoint,
            model="gpt-4"  # 选择使用 GPT-4 模型
        )

    def get_today_date(self):
        """获取当前日期，格式为 YYYY-MM-DD"""
        return datetime.now().strftime("%Y-%m-%d")

    def search(self, query):
        """使用 Google Custom Search API 进行搜索"""
        try:
            # 自动附加日期（如果查询中包含“今日”或“今天”）
            if "今日" in query or "今天" in query:
                today = self.get_today_date()
                query = f"{query} {today}"

            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": self.api_key,
                "cx": self.search_engine_id,
                "q": query,
                "num": 3,  # 限制返回最多3个结果
                "safe": "off",
            }
            response = requests.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            if "items" in data:
                results = [
                    f"{item.get('title', '无标题')} - {item.get('snippet', '无描述')} ({item.get('link', '')})"
                    for item in data["items"]
                ]
                return results
            else:
                return ["没有找到相关结果。"]
        except requests.exceptions.RequestException as e:
            return [f"查询失败，错误信息：{e}"]
        except Exception as e:
            return [f"未知错误：{e}"]

    def summarize_results(self, results):
        """对搜索结果生成简短摘要"""
        if not results or results[0].startswith("查询失败"):
            return "抱歉，我未能找到相关信息。"

        # 提取并限制返回条目数量
        summarized = "\n".join([f"{idx + 1}. {result}" for idx, result in enumerate(results[:3])])
        return summarized

    def format_results_for_gpt(self, results):
        """将搜索结果格式化为 GPT 可处理的文本"""
        if not results or results[0].startswith("查询失败"):
            return "抱歉，我未能找到相关信息。"

        formatted_results = "\n".join([f"{idx + 1}. {result}" for idx, result in enumerate(results[:3])])
        return (
            f"以下是搜索结果：\n{formatted_results}\n\n"
            "请按以下要求总结：\n"
            "1. 提取最重要和最相关的信息要点\n"
            "2. 合并重复或相似的信息\n"
            "3. 移除网站名称、广告语等无关信息\n"
            "4. 确保每个要点都包含具体且有价值的信息\n"
            "5. 不要提及信息来源或网站\\n"
            "6. 不要添加浏览建议或链接提示\n"
            "7. 用自然的句式连接所有重要信息\n\n"
            
            "输出要求：\n"
            "- 用3-4个简短的句子总结主要信息\n"
            "- 每句话应该是完整且独立的信息点\n"
            "- 使用简洁客观的语言\n"
            "- 不要添加评论、建议或客套语"
        )

    def ask_gpt_to_summarize(self, results):
        """将格式化的搜索结果传递给 Azure OpenAI 并整理答案"""
        formatted_results = self.format_results_for_gpt(results)

        try:
            # 调用 Azure OpenAI API，通过 langchain 请求 GPT
            response = self.client.generate(
                [HumanMessage(content=formatted_results)],
                temperature=0.3,  # 你可以根据需要调整温度
                max_tokens=500  # 限制生成的文本长度
            )

            # 提取生成的内容
            answer = response['choices'][0]['message']['content'].strip()
            return answer

        except Exception as e:
            return f"错误：无法请求 GPT 进行回答，错误信息：{e}"
        
    
