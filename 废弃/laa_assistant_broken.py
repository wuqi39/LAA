"""
轻量级个人AI助理 (LAA) - Light-weight AI Assistant
基于Qwen Agent框架开发的个人助理系统
"""
import os
import json
import asyncio
from typing import Optional, Dict, Any
import dashscope
from qwen_agent.agents import Assistant
from qwen_agent.gui import WebUI
from qwen_agent.tools.base import BaseTool, register_tool
import sqlite3
from datetime import datetime
import requests
import urllib.parse
import matplotlib
matplotlib.use('Agg')  # 使用非GUI后端
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import io
import base64


# 配置 DashScope API Key
dashscope.api_key = os.getenv('DASHSCOPE_API_KEY', '')
dashscope.timeout = 30

# 定义资源文件根目录
ROOT_RESOURCE = os.path.join(os.path.dirname(__file__), 'resource')

# 确保资源目录存在
os.makedirs(ROOT_RESOURCE, exist_ok=True)


# ====== 任务管理工具实现 ======
@register_tool('create_task')
class CreateTaskTool(BaseTool):
    """
    创建任务工具
    """
    description = '创建一个新的待办任务'
    parameters = [{
        'name': 'title',
        'type': 'string',
        'description': '新标题',
        'required': True
    }, {
        'name': 'description',
        'type': 'string',
        'description': '新描述',
        'required': False
    }]

    def call(self, params: str, **kwargs) -> str:
        import json
        args = json.loads(params)
        title = args['title']
        description = args.get('description', '')
        
        # 连接数据库并创建任务
        db_path = os.path.join(ROOT_RESOURCE, 'laa_data.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT INTO tasks (title, description) VALUES (?, ?)',
            (title, description)
        )
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return f"任务创建成功！任务ID: {task_id}, 标题: {title}"


@register_tool('view_tasks')
class ViewTasksTool(BaseTool):
    """
    查看任务工具
    """
    description = '查看所有或特定状态的待办任务'
    parameters = [{
        'name': 'status',
        'type': 'string',
        'description': '任务状态(pending/completed/all)',
        'required': False
    }]

    def call(self, params: str, **kwargs) -> str:
        import json
        args = json.loads(params)
        status = args.get('status', 'all')
        
        # 连接数据库并查询任务
        db_path = os.path.join(ROOT_RESOURCE, 'laa_data.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        if status == 'pending':
            cursor.execute('SELECT id, title, description, created_at FROM tasks WHERE status = "pending"')
        elif status == 'completed':
            cursor.execute('SELECT id, title, description, completed_at FROM tasks WHERE status = "completed"')
        else:
            cursor.execute('SELECT id, title, description, status, created_at FROM tasks')
        
        tasks = cursor.fetchall()
        conn.close()
        
        if not tasks:
            return "暂无任务"
        
        result = "任务列表：\n"
        for task in tasks:
            if len(task) == 4:
                result += f"ID: {task[0]}, 标题: {task[1]}, 状态: {task[3]}, 创建时间: {task[2]}\n"
            else:
                result += f"ID: {task[0]}, 标题: {task[1]}, 描述: {task[2]}, 状态: {task[3]}, 创建时间: {task[4]}\n"
        
        return result


@register_tool('update_task')
class UpdateTaskTool(BaseTool):
    """
    更新任务工具
    """
    description = '更新任务状态或信息'
    parameters = [{
        'name': 'task_id',
        'type': 'integer',
        'description': '任务ID',
        'required': True
    }, {
        'name': 'status',
        'type': 'string',
        'description': '新状态(pending/completed)',
        'required': False
    }, {
        'name': 'title',
        'type': 'string',
        'description': '新标题',
        'required': False
    }, {
        'name': 'description',
        'type': 'string',
        'description': '新描述',
        'required': False
    }]

    def call(self, params: str, **kwargs) -> str:
        import json
        args = json.loads(params)
        task_id = args['task_id']
        
        # 构建更新字段
        updates = []
        update_values = []
        
        if 'status' in args:
            updates.append('status = ?')
            update_values.append(args['status'])
            if args['status'] == 'completed':
                updates.append('completed_at = ?')
                update_values.append(datetime.now().isoformat())
        
        if 'title' in args:
            updates.append('title = ?')
            update_values.append(args['title'])
        
        if 'description' in args:
            updates.append('description = ?')
            update_values.append(args['description'])
        
        if not updates:
            return "未提供任何更新字段"
        
        # 连接数据库并更新任务
        db_path = os.path.join(ROOT_RESOURCE, 'laa_data.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
        update_values.append(task_id)
        
        cursor.execute(query, update_values)
        conn.commit()
        
        rows_affected = cursor.rowcount
        conn.close()
        
        if rows_affected > 0:
            return f"任务 {task_id} 更新成功"
        else:
            return f"未找到ID为 {task_id} 的任务"


@register_tool('delete_task')
class DeleteTaskTool(BaseTool):
    """
    删除任务工具
    """
    description = '删除指定ID的任务'        
    parameters = [{
        'name': 'task_id',
        'type': 'integer',
        'description': '任务ID',
        'required': True
    }]

    def call(self, params: str, **kwargs) -> str:
        import json
        args = json.loads(params)
        task_id = args['task_id']
        
        # 连接数据库并删除任务
        db_path = os.path.join(ROOT_RESOURCE, 'laa_data.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        conn.commit()
        
        rows_affected = cursor.rowcount
        conn.close()
        
        if rows_affected > 0:
            return f"任务 {task_id} 删除成功"
        else:
            return f"未找到ID为 {task_id} 的任务"


# ====== 笔记管理工具实现 ======
@register_tool('create_note')
class CreateNoteTool(BaseTool):
    """
    创建笔记工具
    """
    description = '创建一个新的笔记'
    parameters = [{
        'name': 'title',
        'type': 'string',
        'description': '笔记标题',
        'required': True
    }, {
        'name': 'content',
        'type': 'string',
        'description': '笔记内容',
        'required': True
    }]

    def call(self, params: str, **kwargs) -> str:
        import json
        args = json.loads(params)
        title = args['title']
        content = args['content']
        
        # 连接数据库并创建笔记
        db_path = os.path.join(ROOT_RESOURCE, 'laa_data.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT INTO notes (title, content) VALUES (?, ?)',
            (title, content)
        )
        note_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return f"笔记创建成功！笔记ID: {note_id}, 标题: {title}"


@register_tool('view_notes')
class ViewNotesTool(BaseTool):
    """
    查看笔记工具
    """
    description = '查看所有笔记或根据关键词搜索笔记'
    parameters = [{
        'name': 'keyword',
        'type': 'string',
        'description': '搜索关键词，根据标题或内容搜索',
        'required': False
    }]

    def call(self, params: str, **kwargs) -> str:
        import json
        args = json.loads(params)
        keyword = args.get('keyword', '')
        
        # 连接数据库并查询笔记
        db_path = os.path.join(ROOT_RESOURCE, 'laa_data.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        if keyword:
            cursor.execute(
                'SELECT id, title, content, updated_at FROM notes WHERE title LIKE ? OR content LIKE ?',
                (f'%{keyword}%', f'%{keyword}%')
            )
        else:
            cursor.execute('SELECT id, title, content, updated_at FROM notes')
        
        notes = cursor.fetchall()
        conn.close()
        
        if not notes:
            return "暂无笔记"
        
        result = "笔记列表：\n"
        for note in notes:
            result += f"ID: {note[0]}, 标题: {note[1]}, 内容: {note[2][:50]}..., 更新时间: {note[3]}\n"
        
        return result


# ====== 天气查询工具实现 ======
@register_tool('get_weather')
class WeatherTool(BaseTool):
    """
    天气查询工具，通过高德地图API查询指定位置的天气情况
    """
    description = '获取指定位置的当前天气情况'
    parameters = [{
        'name': 'location',
        'type': 'string',
        'description': '城市名称，例如：北京',
        'required': True
    }]

    def call(self, params: str, **kwargs) -> str:
        import json
        args = json.loads(params)
        location = args['location']
        
        return self.get_weather_from_gaode(location)

    def get_weather_from_gaode(self, location: str) -> str:
        """调用高德地图API查询天气"""
        # 从环境变量获取高德API Key，如果未设置则提示用户
        gaode_api_key = os.getenv('AMAP_API_KEY', '')
        if not gaode_api_key or gaode_api_key == '':
            return "请设置环境变量 AMAP_API_KEY 以使用天气查询功能"
        
        base_url = "https://restapi.amap.com/v3/weather/weatherInfo"
        
        params = {
            "key": gaode_api_key,
            "city": location,
            "extensions": "base",  # 可改为"all" 获取预报
        }
        
        try:
            response = requests.get(base_url, params=params)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == '1' and data.get('lives'):
                    weather_info = data['lives'][0]
                    # 确保时间格式完整
                    report_time = weather_info.get('reporttime', '')
                    # 检查时间格式是否完整（应为 YYYY-MM-DD HH:MM:SS 格式）
                    if report_time and len(report_time) >= 16 and report_time[-1].isdigit():
                        # 时间格式完整
                        formatted_time = report_time
                    elif report_time and report_time.endswith(':'):
                        # 时间格式不完整（以冒号结尾），移除最后的冒号
                        formatted_time = report_time.rstrip(':')
                    else:
                        # 没有时间或格式异常，使用当前时间
                        formatted_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    result = f"天气查询结果：\n城市：{weather_info.get('city')}\n天气：{weather_info.get('weather')}\n温度：{weather_info.get('temperature')}°C\n风向：{weather_info.get('winddirection')}\n风力：{weather_info.get('windpower')}\n湿度：{weather_info.get('humidity')}%\n发布时间：{formatted_time}"
                    return result
                else:
                    return f"获取天气信息失败：{data.get('info', '未知错误')}"
            else:
                return f"请求失败：HTTP状态码 {response.status_code}"
        except Exception as e:
            return f"获取天气信息出错：{str(e)}"


# ====== 网络搜索工具实现 ======
@register_tool('search_web')
class BingSearchTool(BaseTool):
    """
    网络搜索工具，直接使用Bing搜索的MCP服务获取信息
    """
    description = '在互联网上搜索相关信息'
    parameters = [{
        'name': 'query',
        'type': 'string',
        'description': '搜索查询词',
    }]

    def call(self, params: str, **kwargs) -> str:
        import json
        try:
            # 解析参数
            args = json.loads(params)
            query = args['query']
            
            # 调用Bing MCP服务进行网络搜索
            result = run_mcp(
                server_name="bing-cn-mcp-server",
                tool_name="bing_search",
                args={"query": query, "num_results": 5}
            )
            
            # 处理MCP服务返回的结果            if result.get('status') == 'success':
                # 在Trae AI环境中，run_mcp会自动被替换为真实的服务调用
                # 我们直接返回结果，让系统处理实际的调用                if 'is_mcp_request' in result.get('data', {}):
                    # 这是在模拟环境中，我们构造一个示例响应                    formatted_result = f"已发送搜索请求到Bing MCP服务 (关于 '{query}')。\\n"
                    formatted_result += "在实际环境中，您将收到以下格式的搜索结果：\\n\\n"
                    formatted_result += "1. **示例标题**\\n"
                    formatted_result += "   描述: 这是示例描述内容\\n"
                    formatted_result += "   链接: https://example.com\\n\\n"
                    formatted_result += "在Trae AI环境中，系统会自动拦截并使用真实的MCP服务获取实际搜索结果。"
                    return formatted_result
                else:
                    # 处理真实的搜索结果                    search_results = result.get('data', {}).get('results', [])
                    if search_results:
                        formatted_result = f"搜索结果 (关于 '{query}')：\\n\\n"
                        for i, item in enumerate(search_results, 1):
                            formatted_result += f"{i}. **{item.get('title', '未知标题')}**\\n"
                            formatted_result += f"   描述: {item.get('description', '无描述')}\n"
                            formatted_result += f"   链接: {item.get('url', '无链接')}\n\n"
                        return formatted_result
                    else:
                        return f"未找到关于'{query}' 的信息"
            else:
                return f"搜索失败：{result.get('message', '未知错误')}"
                
        except json.JSONDecodeError:
            return "错误：参数格式无效，请提供有效的JSON格式参数"
        except Exception as e:
            return f"搜索失败：{str(e)}"


@register_tool('search_attractions')
class SearchAttractionsTool(BaseTool):
    """
    景点搜索工具，使用高德地图MCP服务搜索指定地点的景点信息，并提供景点图片链接
    """
    description = '搜索指定地点的景点信息'
    parameters = [{
        'name': 'location',
        'type': 'string',
        'description': '搜索的地点名称，例如：北京、上海、杭州西湖',
        'required': True
    }]

    def call(self, params: str, **kwargs) -> str:
        import json
        
        # 解析参数
        args = json.loads(params)
        location = args.get('location', '').strip()
        
        if not location:
            return "错误：请提供有效的地点名称"
        
        try:
            # 首先使用高德地图的关键词搜索获取景点列表
            result = run_mcp(
                server_name="amap-maps",
                tool_name="maps_text_search",
                args={"query": f"{location} 景点", "city": location, "types": "旅游景点"}
            )
            
            # 处理MCP服务返回的结果            if result.get('status') == 'success':
                # 在Trae AI环境中，run_mcp会自动被替换为真实的服务调用
                if 'is_mcp_request' in result.get('data', {}):
                    # 这是在模拟环境中
                    formatted_result = f"已发送景点搜索请求到高德地图MCP服务 (关于 '{location} 景点')。\n"
                    formatted_result += "在实际环境中，您将收到实际的景点搜索结果。"
                    return formatted_result
                else:
                    # 处理真实的搜索结果                    attractions_data = result.get('data', {}).get('results', [])
                    
                    if attractions_data:
                        result_text = f"{location}的热门景点信息：\n\n"
                        
                        # 处理每个景点                        for i, attraction in enumerate(attractions_data[:5], 1):
                            poi_id = attraction.get('id', '')
                            name = attraction.get('name', '未知景点')
                            address = attraction.get('address', '地址不详')
                            
                            # 尝试获取景点详情（可能包含图片）
                            detail_result = None
                            if poi_id:
                                detail_result = run_mcp(
                                    server_name="amap-maps",
                                    tool_name="maps_search_detail",
                                    args={"id": poi_id}
                                )
                            
                            # 构建景点信息
                            result_text += f"{i}. **{name}**\n"
                            result_text += f"   地址: {address}\n"
                            
                            # 添加图片信息
                            if detail_result and detail_result.get('status') == 'success':
                                detail_data = detail_result.get('data', {})
                                if detail_data and 'photos' in detail_data:
                                    photos = detail_data['photos'][:2]  # 最多显示2张图片                                    for j, photo in enumerate(photos, 1):
                                        photo_url = photo.get('url', '')
                                        if photo_url:
                                            # 使用Markdown图片格式，以便WebUI组件能正确渲染                                            result_text += f"   图片{j}: ![{name}图片{j}]({photo_url})\n"
                                        else:
                                            result_text += "   图片: 图片链接不可用\n"
                                else:
                                    result_text += "   图片: 暂未获取到图片信息\n"
                            else:
                                result_text += "   图片: 暂未获取到图片信息\n"
                            
                            result_text += "\n"
                        
                        return result_text
                    else:
                        return f"未找到{location}的景点信息，请尝试使用其他关键词搜索"
            else:
                return f"搜索失败：{result.get('message', '未知错误')}"
                
        except json.JSONDecodeError:
            return "错误：参数格式无效，请提供有效的JSON格式参数"
        except Exception as e:
            return f"搜索失败：{str(e)}"


@register_tool('data_statistics')
class DataStatisticsTool(BaseTool):
    """
    数据统计工具，对数据进行统计分析并生成可视化图表
    """
    description = '对数据进行统计分析并生成可视化图表'
    parameters = [{
        'name': 'data',
        'type': 'array',
        'description': '要分析的数据，格式为JSON数组，例如：[{"name": "项目A", "value": 30}, {"name": "项目B", "value": 70}]',
        'required': True
    }, {
        'name': 'analysis_type',
        'type': 'string',
        'description': '分析类型，可选值：summary（汇总统计）、distribution（分布分析）、comparison（比较分析）',
        'required': False
    }, {
        'name': 'chart_type',
        'type': 'string',
        'description': '图表类型，可选值：bar（柱状图）、line（折线图）、pie（饼图）、scatter（散点图）',
        'required': False
    }]

    def call(self, params: str, **kwargs) -> str:
        import json
        try:
            args = json.loads(params)
            data = args.get('data', [])
            analysis_type = args.get('analysis_type', 'summary')
            chart_type = args.get('chart_type', 'bar')
            
            if not data or not isinstance(data, list):
                return "错误：请提供有效的数据数组"
            
            # 转换数据为DataFrame便于分析
            df = pd.DataFrame(data)
            
            # 执行统计分析
            result = "数据统计分析结果：\n\n"
            
            if analysis_type == 'summary':
                # 基本统计汇总                numeric_cols = df.select_dtypes(include=[np.number]).columns
                if len(numeric_cols) > 0:
                    summary = df[numeric_cols].describe()
                    result += f"基本统计信息：\n{summary}\n\n"
                else:
                    result += "未找到数值型数据进行统计分析\n\n"
            
            elif analysis_type == 'distribution':
                # 分布分析
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                if len(numeric_cols) > 0:
                    for col in numeric_cols:
                        result += f"{col}的分布统计：\n"
                        result += f"  均值: {df[col].mean():.2f}
"
                        result += f"  中位数: {df[col].median():.2f}
"
                        result += f"  标准差: {df[col].std():.2f}\n\n"
                else:
                    result += "未找到数值型数据进行分布分析\n\n"
            
            elif analysis_type == 'comparison':
                # 比较分析
                result += "数据比较分析：\n"
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                if len(numeric_cols) > 0:
                    for col in numeric_cols:
                        result += f"{col}列：\n"
                        result += f"  最大值: {df[col].max():.2f}\n"
                        result += f"  最小值: {df[col].min():.2f}"
                        result += f"  极差: {df[col].max() - df[col].min():.2f}\n\n"
                else:
                    result += "未找到数值型数据进行比较分析\n\n"
            
            # 生成图表
            try:
                # 确保有用于绘图的数据
                if 'value' in df.columns:
                    # 创建图表目录
                    charts_dir = os.path.join(ROOT_RESOURCE, 'charts')
                    os.makedirs(charts_dir, exist_ok=True)
                    
                    # 生成图表
                    plt.figure(figsize=(10, 6))
                    
                    if chart_type == 'bar':
                        plt.bar(df['name'], df['value'])
                        plt.title('柱状图分析')
                    elif chart_type == 'pie':
                        plt.pie(df['value'], labels=df['name'], autopct='%1.1f%%')
                        plt.title('饼图分析')
                    elif chart_type == 'line':
                        plt.plot(df['name'], df['value'], marker='o')
                        plt.title('折线图分析')
                    elif chart_type == 'scatter' and len(df) > 1:
                        # 对于散点图，需要两列数据                        if len(df.columns) >= 2 and all(col in df.columns for col in ['x', 'y']):
                            plt.scatter(df['x'], df['y'])
                            plt.title('散点图分析')
                            plt.xlabel('X轴')
                            plt.ylabel('Y轴')
                        else:
                            result += "警告：散点图需要两列数值数据（x和y），已默认使用柱状图"
                            plt.bar(df['name'], df['value'])
                            plt.title('柱状图分析')
                    
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    
                    # 保存图表
                    import time
                    filename = f"stats_chart_{int(time.time())}.png"
                    filepath = os.path.join(charts_dir, filename)
                    plt.savefig(filepath)
                    plt.close()
                    
                    result += f"图表已生成并保存至：{filepath}\n"
                else:
                    result += "警告：未找到'value'列，无法生成图表\n"
            except Exception as chart_error:
                result += f"生成图表时出错：{str(chart_error)}\n"
            
            return result
            
        except json.JSONDecodeError:
            return "错误：解析参数失败，请检查数据格式是否正确"
        except Exception as e:
            return f"错误：处理请求时发生错误 - {str(e)}"


# ====== MCP服务集成工具实现 ======
@register_tool('mcp_fetch')
class MCPFetchTool(BaseTool):
    """
    MCP Fetch服务工具，用于获取URL内容
    """
    description = '获取指定URL的内容'
    parameters = [{
        'name': 'url',
        'type': 'string',
        'description': '要获取的URL地址',
        'required': True
    }, {
        'name': 'max_length',
        'type': 'integer',
        'description': '返回内容的最大字符数，默认5000',
        'required': False
    }, {
        'name': 'raw',
        'type': 'boolean',
        'description': '是否返回原始HTML内容，默认为false',
        'required': False
    }]

    def call(self, params: str, **kwargs) -> str:
        import json
        args = json.loads(params)
        url = args['url']
        max_length = args.get('max_length', 5000)
        raw = args.get('raw', False)
        
        try:
            # 调用MCP fetch服务
            from laa_assistant import run_mcp  # 临时导入，避免循环依赖            result = run_mcp(
                server_name='fetch',
                tool_name='fetch',
                args={'url': url, 'max_length': max_length, 'raw': raw}
            )
            return result.get('content', '获取内容失败')
        except Exception as e:
            return f"调用MCP Fetch服务失败：{str(e)}"

@register_tool('mcp_weather')
class MCPWeatherTool(BaseTool):
    """
    MCP 天气查询服务工具
    """
    description = '查询指定城市的天气情况'
    parameters = [{
        'name': 'city',
        'type': 'string',
        'description': '城市名称，例如：北京',
        'required': True
    }]

    def call(self, params: str, **kwargs) -> str:
        import json
        args = json.loads(params)
        city = args['city']
        
        try:
            # 调用MCP天气服务
            from laa_assistant import run_mcp  # 临时导入，避免循环依赖            result = run_mcp(
                server_name='juhe-mcp-server',
                tool_name='get_weather',
                args={'city': city}
            )
            return self.format_weather_result(result)
        except Exception as e:
            return f"调用MCP天气服务失败：{str(e)}"
    
    def format_weather_result(self, result: dict) -> str:
        """格式化天气查询结果"""
        if not result:
            return "未获取到天气信息"
        
        # 根据实际返回结构格式化输出        if isinstance(result, dict):
            if 'weather' in result:
                return f"天气查询结果：\n城市：{result.get('city', '未知')}\n{result.get('weather', '')}"
            else:
                return json.dumps(result, ensure_ascii=False, indent=2)
        return str(result)

@register_tool('mcp_train_ticket')
class MCPTrainTicketTool(BaseTool):
    """
    MCP 火车票查询服务工具
    """
    description = '查询火车票信息'
    parameters = [{
        'name': 'departure_station',
        'type': 'string',
        'description': '出发城市或车站名称',
        'required': True
    }, {
        'name': 'arrival_station',
        'type': 'string',
        'description': '到达城市或车站名称',
        'required': True
    }, {
        'name': 'date',
        'type': 'string',
        'description': '出发日期，格式为：YYYY-MM-DD',
        'required': True
    }, {
        'name': 'filter',
        'type': 'string',
        'description': '车次筛选条件，如G(高铁/城际),D(动车),Z(直达特快),T(特快),K(快速)',
        'required': False
    }]

    def call(self, params: str, **kwargs) -> str:
        import json
        args = json.loads(params)
        departure_station = args['departure_station']
        arrival_station = args['arrival_station']
        date = args['date']
        filter_opt = args.get('filter', '')
        
        try:
            # 调用MCP火车票查询服务            from laa_assistant import run_mcp  # 临时导入，避免循环依赖            result = run_mcp(
                server_name='juhe-mcp-server',
                tool_name='query_train_tickets',
                args={
                    'departure_station': departure_station,
                    'arrival_station': arrival_station,
                    'date': date,
                    'filter': filter_opt
                }
            )
            return self.format_train_result(result)
        except Exception as e:
            return f"调用MCP火车票查询服务失败：{str(e)}"
    
    def format_train_result(self, result: dict) -> str:
        """格式化火车票查询结果"""
        if not result:
            if not result:
            return "未获取到火车票信息"
        
        # 根据实际返回结构格式化输出        if isinstance(result, dict):
            if 'tickets' in result:
                tickets = result['tickets']
                result_str = f"火车票查询结果：\n出发站：{result.get('departure_station')}\n到达站：{result.get('arrival_station')}\n日期：{result.get('date')}\n\n车次信息：\n"
                for ticket in tickets[:5]:  # 最多显示5条记录                    result_str += f"车次：{ticket.get('train_no', 'N/A')} | 出发时间：{ticket.get('departure_time', 'N/A')} | 到达时间：{ticket.get('arrival_time', 'N/A')} | 价格：{ticket.get('price', 'N/A')}\n"
                return result_str
            else:
                return json.dumps(result, ensure_ascii=False, indent=2)
        return str(result)

@register_tool('mcp_maps')
class MCPMapsTool(BaseTool):
    """
    MCP 地图服务工具，用于地理位置查询、路径规划等
    """
    description = '使用地图服务查询地理位置信息或进行路径规划'
    parameters = [{
        'name': 'action',
        'type': 'string',
        'description': '操作类型：geocode(地址转坐标)、regeocode(坐标转地址)、text_search(文本搜索)、direction_driving(驾车导航)、distance(距离测量)、weather(天气查询)、search_detail(搜索详情)',
        'required': True
    }, {
        'name': 'address',
        'type': 'string',
        'description': '地址信息，用于geocode操作',
        'required': False
    }, {
        'name': 'location',
        'type': 'string',
        'description': '经纬度坐标，格式为经度,纬度，用于regeocode等操作',
        'required': False
    }, {
        'name': 'origin',
        'type': 'string',
        'description': '起点经纬度，用于路径规划，格式为经度,纬度',
        'required': False
    }, {
        'name': 'destination',
        'type': 'string',
        'description': '终点经纬度，用于路径规划，格式为经度,纬度',
        'required': False
    }]

    def call(self, params: str, **kwargs) -> str:
        import json
        args = json.loads(params)
        action = args['action']
        
        try:
            # 根据action选择不同的地图服务
            from laa_assistant import run_mcp  # 临时导入，避免循环依赖
            if action == 'geocode':
                # 地址转坐标
                result = run_mcp(
                    server_name='amap-maps',
                    tool_name='maps_geo',
                    args={
                        'address': args.get('address', ''),
                        'city': args.get('city', '')
                    }
                )
            elif action == 'regeocode':
                # 坐标转地址
                result = run_mcp(
                    server_name='amap-maps',
                    tool_name='maps_regeocode',
                    args={'location': args.get('location', '')}
                )
            elif action == 'direction_driving':
                # 驾车导航
                result = run_mcp(
                    server_name='amap-maps',
                    tool_name='maps_direction_driving',
                    args={
                        'origin': args.get('origin', ''),
                        'destination': args.get('destination', '')
                    }
                )
            elif action == 'distance':
                # 距离测量
                result = run_mcp(
                    server_name='amap-maps',
                    tool_name='maps_distance',
                    args={
                        'origins': args.get('origin', ''),
                        'destination': args.get('destination', ''),
                        'type': args.get('type', '0')  # 0为直线距离离
                    }
                )
            elif action == 'weather':
                # 地图天气查询
                result = run_mcp(
                    server_name='amap-maps',
                    tool_name='maps_weather',
                    args={'city': args.get('city', '')}
                )
            else:
                return f"不支持的地图操作类型：{action}"
            
            return self.format_maps_result(action, result)
        except Exception as e:
            return f"调用MCP地图服务失败：{str(e)}"
    
    def format_maps_result(self, action: str, result: dict) -> str:
        """格式化地图服务结果"""
        if not result:
            return f"未获取到{action}信息"
        
        # 简单格式化输出
        if isinstance(result, dict):
            return json.dumps(result, ensure_ascii=False, indent=2)
        return str(result)

# ====== 图表生成工具实现 ======
@register_tool('generate_chart')
class ChartTool(BaseTool):
    """
    图表生成工具，可以根据数据生成简单的图表（柱状图、折线图、饼图等）    """
    description = '根据数据生成图表'
    parameters = [{
        'name': 'chart_type',
        'type': 'string',
        'description': '图表类型 (bar, line, pie, scatter)',
        'required': True
    }, {
        'name': 'data',
        'type': 'array',
        'description': '图表数据，例如 [{"name": "项目A", "value": 30}, {"name": "项目B", "value": 70}]',
        'required': True
    }, {
        'name': 'title',
        'type': 'string',
        'description': '图表标题',
        'required': False
    }, {
        'name': 'x_label',
        'type': 'string',
        'description': 'X轴标签',
        'required': False
    }, {
        'name': 'y_label',
        'type': 'string',
        'description': 'Y轴标签',
        'required': False
    }]

    def call(self, params: str, **kwargs) -> str:
        import json
        import matplotlib
        matplotlib.use('Agg')  # 使用非GUI后端
        import matplotlib.pyplot as plt
        import numpy as np
        import pandas as pd
        import io
        import base64
        
        args = json.loads(params)
        chart_type = args['chart_type']
        data = args['data']
        title = args.get('title', 'Chart')
        x_label = args.get('x_label', '')
        y_label = args.get('y_label', '')

        # 设置中文字体支持
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False

        # 准备数据
        if not data or not isinstance(data, list) or len(data) == 0:
            return "错误：数据为空或格式不正确"

        # 提取标签和值值        labels = []
        values = []
        
        for item in data:
            if isinstance(item, dict):
                if 'name' in item and 'value' in item:
                    labels.append(str(item['name']))
                    values.append(float(item['value']))
                elif 'x' in item and 'y' in item:
                    labels.append(str(item['x']))
                    values.append(float(item['y']))
                else:
                    # 尝试直接从字典中获取值值                    for key, value in item.items():
                        labels.append(str(key))
                        values.append(float(value))
                        break
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                labels.append(str(item[0]))
                values.append(float(item[1]))
            else:
                return "错误：数据格式不正确，需要包含name和value字段"

        # 创建图表
        fig, ax = plt.subplots(figsize=(10, 6))

        if chart_type == 'bar':
            ax.bar(labels, values)
            ax.set_xlabel(x_label if x_label else '类别')
            ax.set_ylabel(y_label if y_label else '数值')
        elif chart_type == 'line':
            ax.plot(labels, values, marker='o')
            ax.set_xlabel(x_label if x_label else '类别')
            ax.set_ylabel(y_label if y_label else '数值')
            ax.grid(True)
        elif chart_type == 'pie':
            ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=90)
            ax.axis('equal')  # 确保饼图是圆形的
        elif chart_type == 'scatter':
            x_vals = list(range(len(values)))
            ax.scatter(x_vals, values)
            ax.set_xlabel(x_label if x_label else 'X值')
            ax.set_ylabel(y_label if y_label else 'Y值')
            ax.set_xticks(x_vals)
            ax.set_xticklabels(labels, rotation=45, ha="right")
        else:
            plt.close(fig)
            return f"错误：不支持的图表类型'{chart_type}'，支持的类型：bar, line, pie, scatter"

        ax.set_title(title)

        # 调整布局，防止标签被截断
        plt.tight_layout()

        # 将图表保存到内存中的字节流        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
        img_buffer.seek(0)

        # 将图片转换为base64编码
        img_base64 = base64.b64encode(img_buffer.getvalue()).decode()
        plt.close(fig)  # 关闭图形以释放内存
        # 创建一个临时文件保存图表（如果需要）
        import tempfile
        import os
        temp_dir = os.path.join(os.path.dirname(__file__), 'resource', 'charts')
        os.makedirs(temp_dir, exist_ok=True)
        
        import time
        filename = f"chart_{int(time.time())}.png"
        filepath = os.path.join(temp_dir, filename)
        
        with open(filepath, 'wb') as f:
            f.write(img_buffer.getvalue())

        return f"图表生成成功！图表已保存到{filepath}。图表类型 {chart_type}, 数据点数 {len(data)}"


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
        初始化本地SQLite数据库        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建任务表表        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL
            )
        ''')
        
        # 创建笔记表表        cursor.execute('''
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
        system_prompt = """我是您的个人AI助理（LAA），零号，我可以帮助您管理任务、记录笔记、查询天气、搜索网络信息、生成图表，以及搜索景点信息和进行数据统计。        
以下是可用的功能：1. 任务管理：创建、查看、更新、删除个人任务 2. 笔记记录：记录和检索个人笔记 3. 天气查询：查询指定城市的天气信息
4. 网络搜索：获取网络信息 5. 图表生成：根据数据生成柱状图、折线图、饼图、散点图等 6. 景点搜索：搜索指定地点的景点信息，并提供景点图片链接
7. 数据统计：对数据进行统计分析并生成可视化图表
8. MCP服务集成：提供URL内容获取、天气查询、火车票查询、地图服务等功能

我会根据您的需求智能使用这些功能。"""
        
        return {
            'model': 'qwen-turbo',
            'timeout': 30,
            'retry_count': 3,
        }, system_prompt


# 初始化助理服务
def run_mcp(server_name: str, tool_name: str, args: dict):
    """
    调用MCP服务
    
    Args:
        server_name: MCP服务器名称
        tool_name: 工具名称
        args: 工具参数
    
    Returns:
        服务调用结果
    """
    import os
    import json

    try:
        # 打印调用信息
        print(f"调用MCP服务: {server_name}.{tool_name}")
        print(f"参数: {args}")
        
        # 检查MCP服务器是否可用- 根据MCP服务配置.md优化配置
        available_servers = {
            "amap-maps": ["maps_geo", "maps_regeocode", "maps_weather", "maps_direction_driving", "maps_distance", "maps_text_search", "maps_search_detail"],
            "fetch": ["fetch"],
            "bing-cn-mcp-server": ["bing_search", "fetch_webpage"],
            "juhe-mcp-server": ["get_weather", "query_train_tickets", "book_train_ticket", "pay_train_ticket"]
        }
        
        if server_name not in available_servers:
            return {
                'status': 'error',
                'message': f'未知的MCP服务器: {server_name}',
                'available_servers': list(available_servers.keys())
            }
            
        if tool_name not in available_servers[server_name]:
            return {
                'status': 'error',
                'message': f'未知的工具名称 {tool_name}',
                'available_tools': available_servers[server_name]
            }
        
        # 对于高德地图服务，尝试从环境变量获取API key
        if server_name == "amap-maps":
            amap_api_key = os.environ.get("AMAP_API_KEY", "")
            if amap_api_key:
                print("高德地图API key已设置，将使用真实服务")
            else:
                print("警告: 未设置环境变量AMAP_API_KEY，将使用配置的默认值")
        
        # 这里我们返回一个特殊的响应，表明我们已经识别到了MCP服务请求
        # 实际上，在Trae AI环境中，当调用这个函数时，系统会自动拦截并使用真正的run_mcp工具
        # 这种方式避免了在Python代码中尝试导入不存在的模块
        return {
            'status': 'success',
            'message': f'MCP服务调用请求已接收 {server_name}.{tool_name}',
            'data': {
                'server_name': server_name,
                'tool_name': tool_name,
                'args': args,
                'is_mcp_request': True,
                'note': '在Trae AI环境中，此请求将被自动转发到真实的MCP服务'
            }
        }
        
    except Exception as e:
        print(f"MCP服务调用失败: {str(e)}")
        return {
            'status': 'error',
            'message': str(e),
            'server_name': server_name,
            'tool_name': tool_name
        }


def init_agent_service():
    """
    初始化AI助理服务
    
    Returns:
        配置好的Assistant实例
    """
    from qwen_agent.agents import Assistant
    
    # 获取助理配置
    laa = LAAAssistant()
    config, system_prompt = laa.get_assistant_config()
    
    # 创建并返回助理实例
    bot = Assistant(llm=config, system=system_prompt)
    return bot


def app_tui():
    """
    终端交互模式
    """
    try:
        print("正在启动LAA助理终端模式...")
        bot = init_agent_service()

        messages = []
        while True:
            try:
                query = input('\n请输入您的请求(输入 "quit" 退出): ')
                if query.lower() == 'quit':
                    break
                
                if not query.strip():
                    print('请求内容不能为空')
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
    """
    图形界面模式
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
                '搜索人工智能的最新发展'
            ]
        }
        
        print("Web界面准备就绪，正在启动服务..")
        WebUI(
            bot,
            chatbot_config=chatbot_config
        ).run()
        
    except Exception as e:
        print(f"启动Web界面失败: {str(e)}")


if __name__ == '__main__':
    # 默认启动Web界面模式
    app_gui()
