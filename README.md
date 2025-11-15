# 轻量级个人AI助理 (LAA - Light-weight AI Assistant)

基于Qwen Agent框架开发的个人助理系统，具备任务管理、笔记记录、天气查询、网络搜索、景点搜索、数据统计和MCP服务集成等功能。

## 功能特性

- **任务管理**：创建、查看、更新、删除个人任务
- **笔记记录**：记录和检索个人笔记
- **天气查询**：查询指定城市的天气信息
- **网络搜索**：获取网络信息
- **图表生成**：根据数据生成柱状图、折线图、饼图、散点图等
- **景点搜索**：搜索指定地点的景点信息，并提供景点图片链接
- **数据统计**：对数据进行统计分析并生成可视化图表
- **MCP服务集成**：提供URL内容获取、火车票查询、地图服务等功能
- **本地存储**：使用SQLite数据库持久化数据

## 系统架构

LAA采用模块化设计，主要包括：

1. **核心框架**：基于Qwen Agent实现
2. **工具系统**：Function Calling机制调用不同功能
3. **数据库**：SQLite本地存储
4. **交互界面**：支持Web GUI和终端TUI两种模式
5. **MCP服务集成**：支持多种MCP服务，包括高德地图、Bing搜索、聚合数据等

## 安装依赖

```bash
pip install -r requirements.txt
```

## 环境配置

- 设置DashScope API Key：
  ```bash
  export DASHSCOPE_API_KEY=your_api_key
  ```
  
- 如需使用天气查询功能，设置高德API Key：
  ```bash
  export AMAP_API_KEY=your_amap_api_key
  ```

## MCP服务配置

LAA支持以下MCP服务：

1. **高德地图服务** (amap-maps)
   - 地址查询、路径规划、景点搜索等
   - 需要设置AMAP_API_KEY环境变量

2. **Bing搜索服务** (bing-cn-mcp-server)
   - 网络搜索功能
   - 已预配置授权密钥

3. **内容获取服务** (fetch)
   - URL内容获取
   - 已预配置授权密钥

4. **聚合数据服务** (juhe-mcp-server)
   - 天气查询、火车票查询等
   - 已预配置访问令牌

详细配置信息请参考[MCP服务配置.md](./MCP服务配置.md)文件。

## 运行方式

### Web界面模式（默认）
```bash
python laa_assistant.py
```

### 终端模式
修改`laa_assistant.py`中的主函数，将`app_gui()`改为`app_tui()`：
```bash
python laa_assistant.py
```

## 工具说明

### 1. 任务管理工具
- `create_task`：创建新任务
- `view_tasks`：查看任务列表
- `update_task`：更新任务状态
- `delete_task`：删除任务

### 2. 笔记管理工具
- `create_note`：创建笔记
- `view_notes`：查看笔记

### 3. 实用工具
- `get_weather`：天气查询
- `search_web`：网络搜索
- `generate_chart`：图表生成（支持柱状图、折线图、饼图、散点图）
- `search_attractions`：景点搜索
- `data_statistics`：数据统计分析

### 4. MCP服务工具
- `mcp_fetch`：URL内容获取
- `mcp_weather`：MCP天气查询
- `mcp_train_ticket`：火车票查询
- `mcp_maps`：地图服务
- `mcp_amap_maps`：高德地图服务

## 项目结构

```
LAA/
├── laa_assistant.py      # 主程序入口
├── requirements.txt      # 依赖包
├── resource/             # 资源目录（包含数据库）
├── test_laa.py           # 测试脚本
├── demo.py               # 功能演示
└── README.md             # 项目说明
```

## 使用示例

在交互界面中，您可以尝试以下指令：
- "帮我创建一个任务：明天开会"
- "查看我的待办任务"
- "今天北京天气怎么样？"
- "记录一个笔记：今天学习了Function Calling"
- "搜索人工智能的最新发展"
- "生成一个柱状图，数据为：项目A: 30, 项目B: 70, 项目C: 50"
- "帮我画一个饼图展示市场份额：公司A: 40%, 公司B: 35%, 公司C: 25%"
- "搜索北京的旅游景点"
- "帮我分析一下这组数据：[{"name": "产品A", "value": 120}, {"name": "产品B", "value": 80}]"
- "查询从北京到上海的火车票"
- "规划从天安门到故宫的路线"

## 依赖项

- qwen-agent
- dashscope
- requests
- sqlite3
- pandas
- sqlalchemy
- matplotlib
- numpy
- base64