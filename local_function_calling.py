"""
本地Function Calling实现模块
包含任务管理、笔记记录、天气查询、图表生成、数据统计等本地功能
"""
import os
import json
import sqlite3
from datetime import datetime
import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import io
import base64
from typing import Optional, Dict, Any
from qwen_agent.tools.base import BaseTool, register_tool

# 配置 DashScope API Key
import dashscope
dashscope.api_key = os.getenv('DASHSCOPE_API_KEY', '')
dashscope.timeout = 30

# 定义资源文件根目录
ROOT_RESOURCE = os.path.join(os.path.dirname(__file__), 'resource')

# 确保资源目录存在
os.makedirs(ROOT_RESOURCE, exist_ok=True)

# 创建图片存储目录
IMAGES_DIR = os.path.join(ROOT_RESOURCE, 'images')
os.makedirs(IMAGES_DIR, exist_ok=True)

def download_and_save_image(image_url: str, filename: str = None) -> str:
    """
    下载图片并保存到本地
    
    Args:
        image_url: 图片URL
        filename: 可选的文件名，如果不提供则自动生成
    
    Returns:
        本地图片文件的相对路径
    """
    try:
        # 如果没有提供文件名，从URL生成
        if not filename:
            import hashlib
            url_hash = hashlib.md5(image_url.encode()).hexdigest()[:8]
            # 从URL中提取文件扩展名
            ext = '.jpg'  # 默认扩展名
            if '.' in image_url.split('/')[-1]:
                ext = '.' + image_url.split('.')[-1].split('?')[0]
            filename = f"img_{url_hash}{ext}"
        
        # 确保文件名安全
        safe_filename = "".join(c for c in filename if c.isalnum() or c in ('.', '_', '-'))
        if not safe_filename:
            safe_filename = f"image_{hash(image_url)}.jpg"
        
        local_path = os.path.join(IMAGES_DIR, safe_filename)
        
        # 如果文件已存在，直接返回路径
        if os.path.exists(local_path):
            return f"/resource/images/{safe_filename}"
        
        # 下载图片
        response = requests.get(image_url, timeout=10)
        if response.status_code == 200:
            with open(local_path, 'wb') as f:
                f.write(response.content)
            return f"/resource/images/{safe_filename}"
        else:
            return None
    except Exception as e:
        print(f"下载图片失败: {str(e)}")
        return None


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
        'description': '任务标题',
        'required': True
    }, {
        'name': 'description',
        'type': 'string',
        'description': '任务描述',
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
            return f"任务 {task_id} 更新成功！"
        else:
            return f"未找到ID为{task_id} 的任务"


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
            return f"任务 {task_id} 删除成功！"
        else:
            return f"未找到ID为{task_id} 的任务"


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
        'description': '搜索关键词',
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


# ====== 数据统计工具实现 ======
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
                # 基本统计汇总
                numeric_cols = df.select_dtypes(include=[np.number]).columns
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
                        result += f"  均值: {df[col].mean():.2f}\n"
                        result += f"  中位数: {df[col].median():.2f}\n"
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
                        result += f"  最小值: {df[col].min():.2f}\n"
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
                        # 对于散点图，需要两列数据
                        if len(df.columns) >= 2 and all(col in df.columns for col in ['x', 'y']):
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
                    
                    # 生成相对文件路径用于WebUI显示
                    relative_filepath = f"/resource/charts/{filename}"
                    
                    result += f"图表已生成并保存至：{filepath}\n\n"
                    result += f"<img src=\"{relative_filepath}\" alt=\"数据统计图表\" style=\"max-width: 800px; max-height: 600px;\">\n"
                else:
                    result += "警告：未找到'value'列，无法生成图表\n"
            except Exception as chart_error:
                result += f"生成图表时出错：{str(chart_error)}\n"
            
            return result
            
        except json.JSONDecodeError:
            return "错误：解析参数失败，请检查数据格式是否正确"
        except Exception as e:
            return f"错误：处理请求时发生错误 - {str(e)}"


# ====== 图表生成工具实现 ======
@register_tool('generate_chart')
class ChartTool(BaseTool):
    """
    图表生成工具，可以根据数据生成简单的图表（柱状图、折线图、饼图等）
    """
    description = '根据数据生成图表'
    parameters = [{
        'name': 'chart_type',
        'type': 'string',
        'description': '图表类型 (bar, line, pie, scatter)',
        'required': True
    }, {
        'name': 'data',
        'type': 'array',
        'description': '图表数据，例如：[{"name": "项目A", "value": 30}, {"name": "项目B", "value": 70}]',
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

        # 提取标签和值
        labels = []
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
                    # 尝试直接从字典中获取值
                    for key, value in item.items():
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
            ax.set_xlabel(x_label if x_label else 'X轴')
            ax.set_ylabel(y_label if y_label else 'Y轴')
            ax.set_xticks(x_vals)
            ax.set_xticklabels(labels, rotation=45, ha="right")
        else:
            plt.close(fig)
            return f"错误：不支持的图表类型 '{chart_type}'，支持的类型：bar, line, pie, scatter"

        ax.set_title(title)

        # 调整布局，防止标签被截断
        plt.tight_layout()

        # 将图表保存到内存中的字节流
        img_buffer = io.BytesIO()
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

        # 生成相对文件路径用于WebUI显示
        relative_filepath = f"/resource/charts/{filename}"
        
        # 返回包含本地图片路径的HTML格式结果
        return f"图表生成成功！图表类型: {chart_type}, 数据点数: {len(data)}\n\n" \
               f"<img src=\"{relative_filepath}\" alt=\"{title}\" style=\"max-width: 800px; max-height: 600px;\">\n\n" \
               f"图表也已保存至: {filepath}"


@register_tool('search_attractions_with_images')
class SearchAttractionsWithImagesTool(BaseTool):
    """
    景点搜索与图片显示工具，结合使用Bing搜索和高德地图API获取景点信息及图片
    """
    description = '搜索指定地点的景点信息，并提供景点图片链接'
    parameters = [{
        'name': 'location',
        'type': 'string',
        'description': '搜索地点名称，例如：兰州、北京、上海',
        'required': True
    }]

    def call(self, params: str, **kwargs) -> str:
        import json
        args = json.loads(params)
        location = args.get('location', '').strip()

        if not location:
            return "错误：请提供有效的地点名称"

        try:
            # 首先使用Bing搜索获取兰州旅游景点
            print(f"正在通过Bing搜索 {location} 的旅游景点...")
            from mcp_services import run_mcp
            
            # 调用Bing搜索获取兰州景点
            bing_result = run_mcp(
                server_name="bing-cn-mcp-server",
                tool_name="bing_search",
                args={"query": f"{location} 旅游景点", "num_results": 5}
            )
            
            result_text = f"好的，我将为您推荐一些{location}的著名景点，并提供相关图片。请稍等片刻。\n\n"
            
            # 初始化景点列表
            attractions_to_search = []
            
            if bing_result.get('status') == 'success':
                search_results = bing_result.get('data', {}).get('results', [])
                if search_results:
                    # 尝试从Bing结果中识别相关景点名称
                    for result in search_results:
                        title = result.get('title', '')
                        snippet = result.get('snippet', '')
                        # 简单提取可能的景点名称
                        if '景点' in title or '旅游' in title or '好玩' in title:
                            attractions_to_search.append(title.replace(' - 知乎', '').replace(' - 今日头条', '').replace(' - 马蜂窝', '').replace(' - 携程', ''))
                    
                    # 如果从Bing结果中没能获取有用景点名，使用预定义列表
                    if not attractions_to_search:
                        if location.lower() == '兰州':
                            attractions_to_search = ["黄河母亲雕塑", "小西湖公园", "张掖路步行街", "白塔山公园", "中山桥"]
                        elif location.lower() == '北京':
                            attractions_to_search = ["故宫", "天安门广场", "颐和园", "长城", "天坛"]
                        elif location.lower() == '上海':
                            attractions_to_search = ["外滩", "东方明珠", "豫园", "南京路步行街", "上海迪士尼乐园"]
                        else:
                            # 对于其他城市，使用通用景点词搜索
                            attractions_to_search = [f"{location}热门景点", f"{location}著名景点", f"{location}必去景点", f"{location}旅游攻略", f"{location}好玩的地方"]
            
            # 使用高德地图搜索这些景点的详细信息和图片
            if not attractions_to_search:  # 如果Bing搜索失败，直接使用高德地图搜索
                amap_result = run_mcp(
                    server_name="amap-maps",
                    tool_name="maps_text_search",
                    args={"keywords": f"{location} 景点", "city": location}
                )
                
                if amap_result.get('status') == 'success':
                    pois = amap_result.get('data', {}).get('pois', [])
                    if pois and len(pois) > 0:
                        for i, poi in enumerate(pois[:5], 1):  # 最多显示5个景点
                            name = poi.get('name', '未知景点')
                            address = poi.get('address', '地址未知')
                            
                            result_text += f"{i}. **{name}**\n\n"
                            result_text += f"   地址：{address}\n\n"
                            
                            # 尝试获取景点图片
                            photos = poi.get('photos', [])
                            if photos and len(photos) > 0:
                                for j, photo in enumerate(photos[:2], 1):  # 最多显示2张图片
                                    photo_url = photo.get('url', '')
                                    if photo_url:
                                        # 下载图片并保存到本地
                                        local_image_path = download_and_save_image(photo_url, f"{name}_{j}")
                                        if local_image_path:
                                            result_text += f"   图片{j}： <img src=\"{local_image_path}\" alt=\"{name}图片{j}\" style=\"max-width: 400px; max-height: 300px;\">\n\n"
                                        else:
                                            result_text += f"   图片{j}： 图片下载失败\n\n"
                            else:
                                result_text += "   图片： 暂无图片信息\n\n"
                    else:
                        return f"未能找到 {location} 的相关景点信息，请尝试其他关键词搜索。"
                else:
                    return f"搜索 {location} 的景点信息失败：{amap_result.get('message', '未知错误')}。请检查网络连接或API配置。"
            else:  # 如果Bing搜索成功，使用提取的景点进行搜索
                for i, attraction in enumerate(attractions_to_search[:5], 1):
                    result_text += f"{i}. **{attraction}**\n\n"
                    
                    # 使用高德地图的文本搜索功能获取景点详细信息和图片
                    amap_result = run_mcp(
                        server_name="amap-maps",
                        tool_name="maps_text_search",
                        args={"keywords": attraction, "city": location}
                    )
                    
                    if amap_result.get('status') == 'success':
                        pois = amap_result.get('data', {}).get('pois', [])
                        if pois and len(pois) > 0:
                            poi = pois[0]  # 获取第一个匹配结果
                            name = poi.get('name', attraction)
                            address = poi.get('address', '地址未知')
                            
                            result_text += f"   名称：{name}\n"
                            result_text += f"   地址：{address}\n\n"
                            
                            # 尝试获取景点图片
                            photos = poi.get('photos', [])
                            if photos and len(photos) > 0:
                                for j, photo in enumerate(photos[:2], 1):  # 最多显示2张图片
                                    photo_url = photo.get('url', '')
                                    if photo_url:
                                        # 下载图片并保存到本地
                                        local_image_path = download_and_save_image(photo_url, f"{name}_{j}")
                                        if local_image_path:
                                            result_text += f"   图片{j}： <img src=\"{local_image_path}\" alt=\"{name}图片{j}\" style=\"max-width: 400px; max-height: 300px;\">\n\n"
                                        else:
                                            result_text += f"   图片{j}： 图片下载失败\n\n"
                            else:
                                result_text += "   图片： 暂无图片信息\n\n"
                        else:
                            result_text += "   详细信息：未找到相关景点信息\n\n"
                    else:
                        result_text += "   详细信息：获取失败\n\n"
            
            return result_text
            
        except json.JSONDecodeError:
            return "错误：参数格式无效，请提供有效的JSON格式参数"
        except Exception as e:
            return f"搜索失败：{str(e)}"


@register_tool('search_lanzhou_attractions')
class SearchLanzhouAttractionsTool(BaseTool):
    """
    兰州景点搜索与图片显示工具，专门用于搜索兰州的景点信息及图片
    """
    description = '搜索兰州的景点信息，并提供景点图片链接'
    parameters = []

    def call(self, params: str, **kwargs) -> str:
        # 直接调用通用景点搜索工具，搜索兰州景点
        import json
        args = {}  # 无参数
        try:
            # 使用通用景点搜索工具搜索兰州景点
            from mcp_services import run_mcp
            
            # 使用Bing搜索兰州的景点
            bing_result = run_mcp(
                server_name="bing-cn-mcp-server",
                tool_name="bing_search",
                args={"query": "兰州 旅游景点", "num_results": 5}
            )
            
            attractions_to_search = ["黄河母亲雕塑", "小西湖公园", "张掖路步行街", "白塔山公园", "中山桥"]
            result_text = "兰州的著名景点：\n\n"
            
            for i, attraction in enumerate(attractions_to_search, 1):
                result_text += f"{i}. **{attraction}**\n"
                
                # 获取景点详细信息
                amap_result = run_mcp(
                    server_name="amap-maps",
                    tool_name="maps_text_search",
                    args={"keywords": attraction, "city": "兰州"}
                )
                
                if amap_result.get('status') == 'success':
                    pois = amap_result.get('data', {}).get('pois', [])
                    if pois:
                        poi = pois[0]  # 获取第一个匹配结果
                        address = poi.get('address', '地址未知')
                        result_text += f"   地址：{address}\n"
                        
                        # 尝试获取图片
                        photos = poi.get('photos', [])
                        if photos:
                            for j, photo in enumerate(photos[:2], 1):  # 最多显示2张图片
                                photo_url = photo.get('url', '')
                                if photo_url:
                                    # 下载图片并保存到本地
                                    local_image_path = download_and_save_image(photo_url, f"{attraction}_{j}")
                                    if local_image_path:
                                        result_text += f"   图片{j}： <img src=\"{local_image_path}\" alt=\"{attraction}图片{j}\" style=\"max-width: 300px; max-height: 200px;\">\n"
                                    else:
                                        result_text += f"   图片{j}： 图片下载失败\n"
                        else:
                            result_text += "   图片： 暂无图片信息\n"
                    else:
                        result_text += "   地址： 信息未知\n   图片： 暂无图片信息\n"
                else:
                    result_text += "   详细信息获取失败\n   图片： 暂无图片信息\n"
                
                result_text += "\n"
            
            return result_text
            
        except Exception as e:
            return f"搜索兰州景点失败：{str(e)}"