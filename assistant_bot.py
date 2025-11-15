"""基于 Assistant 实现的高德地图智能助手

这个模块提供了一个智能地图助手，可以：
1. 通过自然语言进行地图服务查询
2. 支持多种交互方式（GUI、TUI、测试模式）
3. 支持旅游规划、地点查询、路线导航等功能
"""

import os
import asyncio
from typing import Optional
import dashscope
from qwen_agent.agents import Assistant
from qwen_agent.gui import WebUI

# 定义资源文件根目录
ROOT_RESOURCE = os.path.join(os.path.dirname(__file__), 'resource')

# 配置 DashScope
dashscope.api_key = os.getenv('DASHSCOPE_API_KEY', '')  # 从环境变量获取 API Key
dashscope.timeout = 30  # 设置超时时间为 30 秒

def init_agent_service():
    """初始化高德地图助手服务
    
    配置说明：
    - 使用 qwen-max 作为底层语言模型
    - 设置系统角色为地图助手
    - 配置高德地图 MCP 工具
    
    Returns:
        Assistant: 配置好的地图助手实例
    """
    # 检查是否设置了必要的API密钥
    dashscope_key = os.getenv('DASHSCOPE_API_KEY', '')
    amap_key = os.getenv('AMAP_MAPS_API_KEY', '你的KEY')
    fetch_key = os.getenv('FETCH_API_KEY', '你的KEY')
    bing_key = os.getenv('BING_API_KEY', '你的KEY')
    
    if not dashscope_key:
        print("警告：未设置 DASHSCOPE_API_KEY 环境变量，可能无法正常使用。")
        print("请在环境变量中设置您的 DashScope API 密钥。")
    
    # 检查是否使用默认的占位符密钥
    if amap_key == '你的KEY':
        print("警告：未配置高德地图 API 密钥，需要在环境变量中设置 AMAP_MAPS_API_KEY。")
        print("或者您需要先安装高德地图MCP服务器：npm install -g @amap/amap-maps-mcp-server")
    
    # LLM 模型配置
    llm_cfg = {
        'model': 'qwen-max',
        'timeout': 30,  # 设置模型调用超时时间
        'retry_count': 3,  # 设置重试次数
    }
    # 系统角色设定
    system = ('你扮演一个地图助手，你具有查询地图、规划路线、推荐景点等能力。'
             '你可以帮助用户规划旅游行程，查找地点，导航等。'
             '你应该充分利用高德地图、Bing搜索、数据聚合等各种MCP工具来提供专业的建议。')
    # MCP 工具配置
    # 注意：需要在环境变量中设置 DASHSCOPE_API_KEY 和 AMAP_API_KEY
    amap_api_key = os.getenv('AMAP_API_KEY', '')  # 从环境变量获取高德地图 API Key
    modelscope_token = "ms-90dcd170-3e12-4906-9a75-b9d05ef5be7f"  # 从MCP服务配置中获取
    
    tools = [{
        "mcpServers": {
            "amap-maps": {
                "command": "npx",
                "args": [
                    "-y",
                    "@amap/amap-maps-mcp-server"
                ],
                "env": {
                    "AMAP_MAPS_API_KEY": amap_api_key
                }
            },
            "fetch": {
                "type": "sse",
                "url": "https://mcp.api-inference.modelscope.net/978f1188c2404b/sse",
                "headers": {
                    "Authorization": f"Bearer {modelscope_token}"
                }
            },
            "bing-cn-mcp-server": {
                "type": "sse",
                "url": "https://mcp.api-inference.modelscope.net/48630c4386cf43/sse",
                "headers": {
                    "Authorization": f"Bearer {modelscope_token}"
                }
            },
            "juhe-mcp-server": {
                "type": "sse",
                "url": "https://mcp.juhe.cn/sse?token=7xWzyz7qxtbIHYedpl01MZHOvfQXVKEmBBnDsPTbA86SxV"
            }
        }
    }]
    
    try:
        # 创建助手实例
        bot = Assistant(
            llm=llm_cfg,
            name='AI助手',
            description='地图查询/指定网页获取/Bing搜索',
            system_message=system,
            function_list=tools,
        )
        print("助手初始化成功！")
        return bot
    except Exception as e:
        print(f"助手初始化失败: {str(e)}")
        print("\n可能的原因和解决方案：")
        print("1. 请确保已安装高德地图MCP服务器: npm install -g @amap/amap-maps-mcp-server")
        print("2. 请检查API密钥是否正确配置")
        print("3. 请确保网络连接正常")
        print("4. 可以尝试使用测试模式运行: python assistant_bot.py test")
        raise


def test(query='帮我查找上海东方明珠的具体位置', file: Optional[str] = None):
    """测试模式
    
    用于快速测试单个查询
    
    Args:
        query: 查询语句，默认为查询地标位置
        file: 可选的输入文件路径
    """
    try:
        # 初始化助手
        bot = init_agent_service()

        # 构建对话消息
        messages = []

        # 根据是否有文件输入构建不同的消息格式
        if not file:
            messages.append({'role': 'user', 'content': query})
        else:
            messages.append({'role': 'user', 'content': [{'text': query}, {'file': file}]})

        print("正在处理您的请求...")
        # 运行助手并打印响应
        for response in bot.run(messages):
            print('bot response:', response)
    except Exception as e:
        print(f"处理请求时出错: {str(e)}")


def app_tui():
    """终端交互模式
    
    提供命令行交互界面，支持：
    - 连续对话
    - 文件输入
    - 实时响应
    """
    try:
        # 初始化助手
        bot = init_agent_service()

        # 对话历史
        messages = []
        while True:
            try:
                # 获取用户输入
                query = input('user question: ')
                # 获取可选的文件输入
                file = input('file url (press enter if no file): ').strip()
                
                # 输入验证
                if not query:
                    print('user question cannot be empty！')
                    continue
                    
                # 构建消息
                if not file:
                    messages.append({'role': 'user', 'content': query})
                else:
                    messages.append({'role': 'user', 'content': [{'text': query}, {'file': file}]})

                print("正在处理您的请求...")
                # 运行助手并处理响应
                response = []
                for response in bot.run(messages):
                    print('bot response:', response)
                messages.extend(response)
            except Exception as e:
                print(f"处理请求时出错: {str(e)}")
                print("请重试或输入新的问题")
    except Exception as e:
        print(f"启动终端模式失败: {str(e)}")


def app_gui():
    """图形界面模式
    
    提供 Web 图形界面，特点：
    - 友好的用户界面
    - 预设查询建议
    - 智能路线规划
    """
    try:
        print("正在启动 Web 界面...")
        # 初始化助手
        bot = init_agent_service()
        # 配置聊天界面
        chatbot_config = {
            'prompt.suggestions': [
                '将 https://k.sina.com.cn/article_7732457677_1cce3f0cd01901eeeq.html 网页转化为Markdown格式',
                '帮我找一下静安寺附近的停车场',
                '推荐陆家嘴附近的高档餐厅',
                '帮我搜索一下关于AI的最新新闻'
            ]
        }
        
        print("Web 界面准备就绪，正在启动服务...")
        # 启动 Web 界面
        WebUI(
            bot,
            chatbot_config=chatbot_config
        ).run()
    except Exception as e:
        print(f"启动 Web 界面失败: {str(e)}")
        print("请检查网络连接和 API Key 配置")


if __name__ == '__main__':
    import sys
    # 运行模式选择
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        if mode == 'test':
            test()           # 测试模式
        elif mode == 'tui':
            app_tui()        # 终端交互模式
        elif mode == 'gui':
            app_gui()        # 图形界面模式
        else:
            print(f"未知模式: {mode}")
            print("可用模式: test, tui, gui")
            print("示例: python assistant_bot.py test")
    else:
        # 默认运行图形界面模式
        app_gui()          # 图形界面模式（默认）