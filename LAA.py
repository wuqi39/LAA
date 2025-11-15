"""

轻量级个人AI助理 (LAA) - Light-weight AI Assistant

基于Qwen Agent框架开发的个人助理系统，集成任务管理、笔记记录、天气查询、网络搜索、地图服务等功能

"""

import os
import json
import asyncio
import threading
from typing import Optional, Dict, Any

import dashscope
from qwen_agent.agents import Assistant
from qwen_agent.gui import WebUI
from qwen_agent.tools.base import BaseTool, register_tool

import sqlite3
from datetime import datetime
import requests
import urllib.parse

# 导入静态文件服务
try:
    from flask import Flask, send_from_directory
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False



# 导入本地Function Calling模块和MCP服务模块

# 由于模块中的工具已经使用register_tool装饰器注册，这里不再需要导入工具函数本身

import local_function_calling

import mcp_services


# 配置 DashScope API Key

dashscope.api_key = os.getenv('DASHSCOPE_API_KEY', '')

dashscope.timeout = 30



# 定义资源文件根目录

ROOT_RESOURCE = os.path.join(os.path.dirname(__file__), 'resource')



# 确保资源目录存在

os.makedirs(ROOT_RESOURCE, exist_ok=True)



# 创建图片存储目录

IMAGES_DIR = os.path.join(ROOT_RESOURCE, 'images')

os.makedirs(IMAGES_DIR, exist_ok=True)



# 导入本地Function Calling模块和MCP服务模块

# 由于模块中的工具已经使用register_tool装饰器注册，这里不再需要导入工具函数本身

import local_function_calling

import mcp_services




# ====== LAA助理主类 ======
class LAAAssistant:
    """
    轻量级个人AI助理主类
    """
    def __init__(self):
        self.db_path = os.path.join(ROOT_RESOURCE, 'laa_data.db')
        self._init_database()
        self.bot = None
    
    def _init_database(self):
        """
        初始化本地SQLite数据库
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建任务表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL
            )
        ''')
        
        # 创建笔记表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_assistant_config(self):
        """
        获取助理配置
        """
        system_prompt = """我是您的个人AI助理（LAA），零号，我可以帮助您管理任务、记录笔记、查询天气、搜索网络信息、生成图表，以及搜索景点信息和进行数据统计分析，并提供专业的地图服务功能。

以下是可用的功能：
1. 任务管理：创建、查看、更新、删除个人任务（仅当用户明确要求管理任务时使用）
2. 笔记记录：记录和检索个人笔记（仅当用户明确要求记录笔记时使用）
3. 天气查询：查询指定城市的天气信息（仅当用户询问天气时使用）
4. 网络搜索：获取网络信息（当其他专用功能无法满足需求时使用）
5. 图表生成：根据数据生成柱状图、折线图、饼图、散点图（当用户要求生成图表时使用）
6. 景点搜索：搜索指定地点的景点信息，并提供景点图片链接（当用户询问景点信息时优先使用）
7. 周边景点搜索：搜索指定位置周边的景点，支持按半径搜索并提供景点图片（当用户询问周边景点时使用）
8. 带图片的景点搜索：结合Bing搜索和高德地图获取景点详细信息和图片（当用户需要景点详情和图片时使用）
9. 数据统计：对数据进行统计分析并生成可视化图表（当用户要求分析数据时使用）
10. MCP服务集成：提供URL内容获取、天气查询、火车票查询、地图服务等功能
11. 高德地图服务：提供地点查询、路线规划、导航、周边搜索等地图相关功能（当用户询问地理位置、导航、路线规划等相关问题时优先使用）

重要使用原则：
- 当用户询问地理位置、地点查询、路线规划、导航、景点、旅游等相关问题时，优先使用高德地图服务、景点搜索等功能
- 当用户明确要求\"创建任务\"、\"记录笔记\"、\"查询天气\"等具体操作时才使用相应功能
- 不要对用户的普通查询（如\"查询XX位置\"）自动创建任务

我会根据您的需求智能使用这些功能。"""
        
        return {
            'model': 'qwen-turbo',
            'timeout': 30,
            'retry_count': 3,
        }, system_prompt


# 初始化助理服务
def init_agent_service():
    """
    初始化LAA助理服务
    """
    laa = LAAAssistant()
    llm_cfg, system_prompt = laa.get_assistant_config()
    
    # 获取模型配置
    llm_cfg, system_prompt = laa.get_assistant_config()
    
    # 检查是否设置了必要的API密钥
    dashscope_key = os.getenv('DASHSCOPE_API_KEY', '')
    amap_key = os.getenv('AMAP_API_KEY', '')
    
    if not dashscope_key:
        print("警告：未设置 DASHSCOPE_API_KEY 环境变量，可能无法正常使用。")
        print("请在环境变量中设置您的 DashScope API 密钥。")
    
    if not amap_key:
        print("警告：未设置 AMAP_API_KEY 环境变量，地图功能可能受限。")
    
    # 更新模型为qwen-max以支持地图功能
    llm_cfg['model'] = 'qwen-max'

    try:
        bot = Assistant(
            llm=llm_cfg,
            name='轻量级个人AI助理',
            description='个人任务管理与信息助理',
            system_message=system_prompt,
            function_list=[
                'create_task',
                'view_tasks', 
                'update_task',
                'delete_task',
                'create_note',
                'view_notes',
                'search_web',
                'get_weather',
                'generate_chart',
                'search_attractions',  # 新增景点搜索功能
                'data_statistics',     # 新增数据统计功能
                'around_search_attractions',  # 新增周边景点搜索功能
                'search_attractions_with_images',  # 新增景点搜索与图片显示功能
                # MCP服务工具
                'mcp_fetch',
                'mcp_weather',
                'mcp_train_ticket',
                'mcp_maps',
                'mcp_amap_maps'  # 新增高德地图MCP服务工具
            ],
        )
        print("LAA助理初始化成功！")
        return bot
    except Exception as e:
        print(f"助理初始化失败: {str(e)}")
        raise


# MCP服务调用函数

def run_mcp(server_name: str, tool_name: str, args: dict) -> dict:

    """

    调用MCP服务的通用函数

    支持直接调用真实的MCP服务，包括amap-maps、fetch、bing-cn-mcp-server和juhe-mcp-server

    

    Args:

        server_name: MCP服务器名称

        tool_name: 工具名称

        args: 工具参数

    

    Returns:

        服务调用结果

    """

    # 这个函数已移至mcp_services.py模块中

    # 为了保持向后兼容性，这里保留一个简单的调用

    try:

        from mcp_services import run_mcp as mcp_run_mcp

        return mcp_run_mcp(server_name, tool_name, args)

    except Exception as e:

        print(f"MCP服务调用失败: {str(e)}")

        return {

            'status': 'error',

            'message': str(e),

            'server_name': server_name,

            'tool_name': tool_name

        }


def test(query='请帮我搜索上海的景点信息', file: Optional[str] = None):
    """测试模式
    
    用于快速测试单个查询
    
    Args:
        query: 查询语句，默认为创建任务
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
            print('LAA回复:', response)
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
        print("正在启动LAA助理终端模式...")
        bot = init_agent_service()

        # 对话历史
        messages = []
        while True:
            try:
                query = input('\n请输入您的请求(输入 "quit" 退出): ')
                if query.lower() == 'quit':
                    break
                
                if not query.strip():
                    print('请求内容不能为空！')
                    continue
                
                messages.append({'role': 'user', 'content': query})
                
                print("正在处理您的请求...")
                response = []
                for response in bot.run(messages):
                    print(f'LAA回复: {response}')
                messages.extend(response)
                
            except KeyboardInterrupt:
                print("\n程序被用户中断")
                break
            except Exception as e:
                print(f"处理请求时出错: {str(e)}")
                
    except Exception as e:
        print(f"启动终端模式失败: {str(e)}")


def app_gui():
    """图形界面模式

    提供 Web 图形界面，特点：
    - 友好的用户界面
    - 预设查询建议
    - 智能功能推荐
    """
    try:
        print("正在启动LAA助理Web界面...")
        bot = init_agent_service()
        
        chatbot_config = {

            'prompt.suggestions': [

                '帮我创建一个任务：明天开会',

                '查看我的待办任务',

                '今天北京天气怎么样？',

                '记录一个笔记：今天学习了Function Calling',

                '搜索人工智能的最新发展',

                '帮我规划从北京到上海的旅游路线',

                '分析这组数据：[{"name": "产品A", "value": 120}, {"name": "产品B", "value": 80}]',

                '搜索兰州的景点及图片',

                '查找上海的旅游景点并显示图片',

                '推荐成都的必去景点'

            ]

        }
        
        print("Web界面准备就绪，正在启动服务...")
        # 启动 Web 界面
        WebUI(
            bot,
            chatbot_config=chatbot_config
        ).run()
        
    except Exception as e:
        print(f"启动Web界面失败: {str(e)}")


def app_map():
    """地图助手模式
    
    专注于地图相关功能，特点：
    - 地点查询
    - 路线规划
    - 景点推荐
    """
    try:
        print("正在启动地图助手模式...")
        
        # 检查是否设置了必要的API密钥
        dashscope_key = os.getenv('DASHSCOPE_API_KEY', '')
        amap_key = os.getenv('AMAP_API_KEY', '')
        
        if not dashscope_key:
            print("警告：未设置 DASHSCOPE_API_KEY 环境变量，可能无法正常使用。")
            print("请在环境变量中设置您的 DashScope API 密钥。")
        
        if not amap_key:
            print("警告：未设置 AMAP_API_KEY 环境变量，地图功能可能受限。")
        
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
                        "AMAP_MAPS_API_KEY": amap_key
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
                name='地图助手',
                description='地图查询/路线规划/景点推荐',
                system_message=system,
                function_list=tools,
            )
            print("地图助手初始化成功！")
            
            # 配置聊天界面
            chatbot_config = {
                'prompt.suggestions': [
                    '将 https://k.sina.com.cn/article_7732457677_1cce3f0cd01901eeeq.html 网页转化为Markdown格式',
                    '帮我找一下静安寺附近的停车场',
                    '推荐陆家嘴附近的高档餐厅',
                    '帮我搜索一下关于AI的最新新闻',
                    '规划从北京到上海的旅游路线',
                    '查找杭州西湖附近的景点'
                ]
            }
            
            print("地图助手Web界面准备就绪，正在启动服务...")
            # 启动 Web 界面
            WebUI(
                bot,
                chatbot_config=chatbot_config
            ).run()
            
        except Exception as e:
            print(f"地图助手初始化失败: {str(e)}")
            print("\n可能的原因和解决方案：")
            print("1. 请确保已安装高德地图MCP服务器: npm install -g @amap/amap-maps-mcp-server")
            print("2. 请检查API密钥是否正确配置")
            print("3. 请确保网络连接正常")
            print("4. 可以尝试使用测试模式运行: python LAA.py test")
            
    except Exception as e:
        print(f"启动地图助手模式失败: {str(e)}")


def start_static_server():
    """启动静态文件服务"""
    if not FLASK_AVAILABLE:
        print("Flask未安装，无法启动静态文件服务。请运行 'pip install flask' 安装Flask。")
        return None
    
    try:
        # 创建Flask应用
        static_app = Flask(__name__)
        RESOURCE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resource')
        
        @static_app.route('/resource/<path:filename>')
        def resource_files(filename):
            """提供resource目录下的静态文件访问"""
            import os
            print(f"Requesting file: {filename}")  # 调试信息
            filepath = os.path.join(RESOURCE_PATH, filename)
            print(f"Full file path: {filepath}")  # 调试信息
            if os.path.exists(filepath):
                print(f"File exists: {filepath}")  # 调试信息
                return send_from_directory(RESOURCE_PATH, filename)
            else:
                print(f"File not found: {filepath}")  # 调试信息
                from flask import abort
                abort(404)
        
        # 在单独的线程中启动Flask应用
        def run_static_server():
            static_app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)
        
        static_thread = threading.Thread(target=run_static_server, daemon=True)
        static_thread.start()
        print("静态文件服务已在端口8000启动")
        return static_thread
    except Exception as e:
        print(f"启动静态文件服务失败: {str(e)}")
        return None


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
            # 启动静态文件服务
            start_static_server()
            app_gui()        # 图形界面模式
        elif mode == 'map':
            # 启动静态文件服务
            start_static_server()
            app_map()        # 地图助手模式
        else:
            print(f"未知模式: {mode}")
            print("可用模式: test, tui, gui, map")
            print("示例: python LAA.py test")
    else:
        # 默认运行图形界面模式
        app_gui()          # 图形界面模式（默认）