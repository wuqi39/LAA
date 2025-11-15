"""
MCP service calling module
Contains calling functions for MCP services such as Bing search, Amap, and aggregated data
"""
import os
import json
import time
import requests
from typing import Dict, Any
from qwen_agent.tools.base import BaseTool, register_tool

# Define resource file root directory
ROOT_RESOURCE = os.path.join(os.path.dirname(__file__), 'resource')

# Ensure resource directory exists
os.makedirs(ROOT_RESOURCE, exist_ok=True)

# Create image storage directory
IMAGES_DIR = os.path.join(ROOT_RESOURCE, 'images')
os.makedirs(IMAGES_DIR, exist_ok=True)

# Get API key from environment variables
modelscope_token = os.getenv('MODELSCOPE_TOKEN', 'ms-90dcd170-3e12-4906-9a75-b9d05ef5be7f')

# Track last call time for each API to manage QPS
amap_api_last_call = {
    'maps_text_search': 0,
    'maps_search_detail': 0,
    'maps_geo': 0,
    'maps_around_search': 0
}

# Minimum delay between API calls (in seconds) to avoid QPS limits
AMAP_API_DELAY = 0.5  # 500ms delay to respect QPS limits

def download_and_save_image(image_url: str, filename: str = None) -> str:
    """
    Download and save image to local storage
    
    Args:
        image_url: Image URL
        filename: Optional filename, automatically generated if not provided
    
    Returns:
        Relative path to the local image file
    """
    try:
        import hashlib
        import requests

        # If no filename is provided, generate from URL
        if not filename:
            url_hash = hashlib.md5(image_url.encode()).hexdigest()[:8]
            # Extract file extension from URL
            ext = '.jpg'  # Default extension
            if '.' in image_url.split('/')[-1]:
                ext = '.' + image_url.split('.')[-1].split('?')[0]
            filename = f"img_{url_hash}{ext}"
        
        # Ensure filename is safe
        safe_filename = "".join(c for c in filename if c.isalnum() or c in ('.', '_', '-'))
        if not safe_filename:
            safe_filename = f"image_{hash(image_url)}.jpg"
        
        local_path = os.path.join(IMAGES_DIR, safe_filename)
        
        # If file exists, return path directly
        if os.path.exists(local_path):
            return f"/resource/images/{safe_filename}"
        
        # Download image
        response = requests.get(image_url, timeout=10)
        if response.status_code == 200:
            with open(local_path, 'wb') as f:
                f.write(response.content)
            return f"/resource/images/{safe_filename}"
        else:
            return None
    except Exception as e:
        print(f"Failed to download image: {str(e)}")
        return None

def run_mcp(server_name: str, tool_name: str, args: dict) -> dict:
    """
    Universal function to call MCP services
    Supports direct calling of real MCP services, including amap-maps, fetch, bing-cn-mcp-server and juhe-mcp-server
    
    Args:
        server_name: MCP server name
        tool_name: Tool name
        args: Tool arguments
    
    Returns:
        Service call result
    """
    try:
        # Print call information
        print(f"Calling MCP service: {server_name}.{tool_name}")
        print(f"Parameters: {args}")
        
        # Check if MCP server is available
        available_servers = {
            "amap-maps": ["maps_geo", "maps_regeocode", "maps_weather", "maps_direction_driving", "maps_distance", "maps_text_search", "maps_search_detail", "maps_around_search"],
            "fetch": ["fetch"],
            "bing-cn-mcp-server": ["bing_search", "fetch_webpage"],
            "juhe-mcp-server": ["get_weather", "query_train_tickets", "book_train_ticket", "pay_train_ticket"]
        }
        
        if server_name not in available_servers:
            return {
                'status': 'error',
                'message': f'Unknown MCP server: {server_name}',
                'available_servers': list(available_servers.keys())
            }
            
        if tool_name not in available_servers[server_name]:
            return {
                'status': 'error',
                'message': f'Unknown tool name: {tool_name}',
                'available_tools': available_servers[server_name]
            }
        
        # For Amap service, try to get API key from environment variables
        if server_name == "amap-maps":
            amap_api_key = os.environ.get("AMAP_API_KEY", "")
            if amap_api_key:
                print("Amap API key is set, will use real service")
            else:
                print("Warning: Environment variable AMAP_API_KEY is not set, will try to simulate service")
        
        # In non-Trae AI environment, make actual service calls based on the server type
        if server_name == "bing-cn-mcp-server" and tool_name == "bing_search":
            # Make actual Bing search API call using GET method (required for this endpoint)
            query = args.get('query', '')
            num_results = args.get('num_results', 5)
            headers = {
                "Authorization": f"Bearer {modelscope_token}"
            }
            api_url = "https://mcp.api-inference.modelscope.net/48630c4386cf43/sse"
            # Use GET request with query parameters instead of POST with JSON payload
            params = {
                "query": query,
                "num_results": num_results
            }
            
            print(f"Making Bing search request: {api_url}, query: {query}")  # Debug info
            # Use GET request with timeout and better error handling
            try:
                response = requests.get(api_url, headers=headers, params=params, timeout=30)
                print(f"Bing search response status: {response.status_code}")  # Debug info
                if response.status_code == 200:
                    print(f"Bing search response text (first 200 chars): {response.text[:200] if response.text else 'No response text'}")  # Debug info
                    # Try to parse JSON response, handle different response formats
                    try:
                        json_data = response.json()
                        print(f"Parsed Bing search JSON data: {type(json_data)}")  # Debug info
                        return {
                            'status': 'success',
                            'data': json_data
                        }
                    except ValueError:
                        # If response is not JSON, try to parse as text or handle differently
                        print(f"Bing API returned non-JSON response: {response.text[:200]}...")
                        # Try to parse as SSE if it's an SSE response
                        if 'data:' in response.text:
                            # Parse SSE response
                            lines = response.text.split('\n')
                            sse_data = []
                            for line in lines:
                                if line.startswith('data:'):
                                    data_content = line[5:].strip()
                                    try:
                                        parsed_data = json.loads(data_content)
                                        sse_data.append(parsed_data)
                                    except ValueError:
                                        sse_data.append(data_content)
                            print(f"Parsed {len(sse_data)} SSE data items")  # Debug info
                            return {
                                'status': 'success',
                                'data': {'results': sse_data}
                            }
                        elif response.text.strip().startswith('{') and response.text.strip().endswith('}'):
                            # Handle single JSON object in response text
                            try:
                                json_data = json.loads(response.text.strip())
                                print(f"Parsed single JSON object from response text: {type(json_data)}")  # Debug info
                                return {
                                    'status': 'success',
                                    'data': json_data
                                }
                            except ValueError:
                                raise Exception(f'Bing search returned invalid JSON response: {response.text[:200]}...')
                        else:
                            # If not JSON or SSE format, return as plain text
                            print(f"Returning plain text response: {response.text[:200]}...")  # Debug info
                            return {
                                'status': 'success',
                                'data': {'results': [{'title': f'Search results for {query}', 'description': response.text[:500], 'url': api_url}]}
                            }
                elif response.status_code == 401:
                    raise Exception('Bing search API authentication failed - check your API token')
                elif response.status_code == 429:
                    raise Exception('Bing search API rate limit exceeded - too many requests')
                elif response.status_code == 400:
                    error_msg = response.text if response.text else f'status {response.status_code}'
                    raise Exception(f'Bing search API call failed with status {response.status_code} (Bad Request): {error_msg}')
                elif response.status_code >= 400:
                    # Try to extract error message from response
                    error_msg = response.text if response.text else f'status {response.status_code}'
                    raise Exception(f'Bing search API call failed with status {response.status_code}: {error_msg}')
                else:
                    # For status codes not explicitly handled, return the response as is
                    error_msg = response.text if response.text else f'status {response.status_code}'
                    raise Exception(f'Bing search API call failed with status {response.status_code}: {error_msg}')
            except requests.exceptions.Timeout:
                print(f"Bing search request timed out after 30 seconds")  # Debug info
                raise Exception('Bing search API call timed out after 30 seconds')
            except requests.exceptions.ConnectionError:
                print(f"Bing search connection failed - check network connectivity")  # Debug info
                raise Exception('Bing search API connection failed - check network connectivity')
            except requests.exceptions.RequestException as e:
                print(f"Bing search request failed: {str(e)}")  # Debug info
                raise Exception(f'Bing search API call failed: {str(e)}')
            except Exception as e:
                print(f"Unexpected error during Bing search: {str(e)}")  # Debug info
                raise Exception(f'Unexpected error during Bing search: {str(e)}')
        elif server_name == "amap-maps":
            # Make actual Amap API call based on tool_name
            amap_api_key = os.environ.get("AMAP_API_KEY", "")
            if not amap_api_key:
                raise Exception("AMAP_API_KEY environment variable is not set")
            
            # Implement rate limiting to avoid QPS limits
            current_time = time.time()
            time_since_last_call = current_time - amap_api_last_call.get(tool_name, 0)
            if time_since_last_call < AMAP_API_DELAY:
                time.sleep(AMAP_API_DELAY - time_since_last_call)
            
            # Update last call time
            amap_api_last_call[tool_name] = time.time()
            
            if tool_name == "maps_text_search":
                # Amap text search with retry mechanism
                keywords = args.get('keywords', '')
                city = args.get('city', '')
                api_url = "https://restapi.amap.com/v5/place/text"
                params = {
                    'key': amap_api_key,
                    'keywords': keywords,
                    'city': city
                }
                
                # Retry mechanism for handling QPS limits
                max_retries = 3
                retry_count = 0
                while retry_count < max_retries:
                    try:
                        response = requests.get(api_url, params=params, timeout=10)
                        if response.status_code == 200:
                            data = response.json()
                            if data.get('info') == 'OK':
                                return {
                                    'status': 'success',
                                    'data': {
                                        'results': data.get('pois', [])
                                    }
                                }
                            elif data.get('info') in ['INVALID_USER_KEY', 'SERVICE_NOT_AVAILABLE', 'DAILY_QUERY_OVER_LIMIT']:
                                # Don't retry for these errors as they won't resolve with retries
                                raise Exception(f'Amap API returned error: {data.get("info")}')
                            else:
                                # For other errors, increment retry count and wait before retrying
                                retry_count += 1
                                if retry_count < max_retries:
                                    time.sleep(2 ** retry_count)  # Exponential backoff
                                else:
                                    raise Exception(f'Amap API returned error: {data.get("info")}')
                        elif response.status_code == 429:  # Too Many Requests
                            retry_count += 1
                            if retry_count < max_retries:
                                time.sleep(2 ** retry_count)  # Exponential backoff
                            else:
                                raise Exception(f'Amap API call failed with status {response.status_code} - Too Many Requests')
                        else:
                            raise Exception(f'Amap API call failed with status {response.status_code}')
                    except requests.exceptions.RequestException as e:
                        retry_count += 1
                        if retry_count < max_retries:
                            time.sleep(2 ** retry_count)  # Exponential backoff
                        else:
                            raise Exception(f'Amap API call failed: {str(e)}')
            elif tool_name == "maps_search_detail":
                # Amap detail search with retry mechanism
                id_param = args.get('id', '')
                api_url = "https://restapi.amap.com/v5/place/detail"
                params = {
                    'key': amap_api_key,
                    'id': id_param
                }
                
                # Retry mechanism for handling QPS limits
                max_retries = 3
                retry_count = 0
                while retry_count < max_retries:
                    try:
                        response = requests.get(api_url, params=params, timeout=10)
                        if response.status_code == 200:
                            data = response.json()
                            if data.get('info') == 'OK':
                                return {
                                    'status': 'success',
                                    'data': data.get('poi', {})
                                }
                            elif data.get('info') in ['INVALID_USER_KEY', 'SERVICE_NOT_AVAILABLE', 'DAILY_QUERY_OVER_LIMIT']:
                                # Don't retry for these errors as they won't resolve with retries
                                raise Exception(f'Amap API returned error: {data.get("info")}')
                            else:
                                # For other errors, increment retry count and wait before retrying
                                retry_count += 1
                                if retry_count < max_retries:
                                    time.sleep(2 ** retry_count)  # Exponential backoff
                                else:
                                    raise Exception(f'Amap API returned error: {data.get("info")}')
                        elif response.status_code == 429:  # Too Many Requests
                            retry_count += 1
                            if retry_count < max_retries:
                                time.sleep(2 ** retry_count)  # Exponential backoff
                            else:
                                raise Exception(f'Amap API call failed with status {response.status_code} - Too Many Requests')
                        else:
                            raise Exception(f'Amap API call failed with status {response.status_code}')
                    except requests.exceptions.RequestException as e:
                        retry_count += 1
                        if retry_count < max_retries:
                            time.sleep(2 ** retry_count)  # Exponential backoff
                        else:
                            raise Exception(f'Amap API call failed: {str(e)}')
            elif tool_name == "maps_geo":
                # Amap geocoding with retry mechanism
                address = args.get('address', '')
                city = args.get('city', '')
                api_url = "https://restapi.amap.com/v3/geocode/geo"
                params = {
                    'key': amap_api_key,
                    'address': address,
                    'city': city
                }
                
                # Retry mechanism for handling QPS limits
                max_retries = 3
                retry_count = 0
                while retry_count < max_retries:
                    try:
                        response = requests.get(api_url, params=params, timeout=10)
                        if response.status_code == 200:
                            data = response.json()
                            if data.get('info') == 'OK' and len(data.get('geocodes', [])) > 0:
                                return {
                                    'status': 'success',
                                    'data': {
                                        'location': data['geocodes'][0].get('location', '')
                                    }
                                }
                            elif data.get('info') in ['INVALID_USER_KEY', 'SERVICE_NOT_AVAILABLE', 'DAILY_QUERY_OVER_LIMIT']:
                                # Don't retry for these errors as they won't resolve with retries
                                raise Exception(f'Amap API returned error: {data.get("info")}')
                            else:
                                # For other errors, increment retry count and wait before retrying
                                retry_count += 1
                                if retry_count < max_retries:
                                    time.sleep(2 ** retry_count)  # Exponential backoff
                                else:
                                    raise Exception(f'Amap API returned error: {data.get("info")}')
                        elif response.status_code == 429:  # Too Many Requests
                            retry_count += 1
                            if retry_count < max_retries:
                                time.sleep(2 ** retry_count)  # Exponential backoff
                            else:
                                raise Exception(f'Amap API call failed with status {response.status_code} - Too Many Requests')
                        else:
                            raise Exception(f'Amap API call failed with status {response.status_code}')
                    except requests.exceptions.RequestException as e:
                        retry_count += 1
                        if retry_count < max_retries:
                            time.sleep(2 ** retry_count)  # Exponential backoff
                        else:
                            raise Exception(f'Amap API call failed: {str(e)}')
            elif tool_name == "maps_around_search":
                # Amap around search with retry mechanism
                location = args.get('location', '')
                keywords = args.get('keywords', '')
                radius = args.get('radius', 3000)
                city = args.get('city', '')
                api_url = "https://restapi.amap.com/v5/place/around"
                params = {
                    'key': amap_api_key,
                    'location': location,
                    'keywords': keywords,
                    'radius': radius,
                    'city': city
                }
                
                # Retry mechanism for handling QPS limits
                max_retries = 3
                retry_count = 0
                while retry_count < max_retries:
                    try:
                        response = requests.get(api_url, params=params, timeout=10)
                        if response.status_code == 200:
                            data = response.json()
                            if data.get('info') == 'OK':
                                return {
                                    'status': 'success',
                                    'data': {
                                        'results': data.get('pois', [])
                                    }
                                }
                            elif data.get('info') in ['INVALID_USER_KEY', 'SERVICE_NOT_AVAILABLE', 'DAILY_QUERY_OVER_LIMIT']:
                                # Don't retry for these errors as they won't resolve with retries
                                raise Exception(f'Amap API returned error: {data.get("info")}')
                            else:
                                # For other errors, increment retry count and wait before retrying
                                retry_count += 1
                                if retry_count < max_retries:
                                    time.sleep(2 ** retry_count)  # Exponential backoff
                                else:
                                    raise Exception(f'Amap API returned error: {data.get("info")}')
                        elif response.status_code == 429:  # Too Many Requests
                            retry_count += 1
                            if retry_count < max_retries:
                                time.sleep(2 ** retry_count)  # Exponential backoff
                            else:
                                raise Exception(f'Amap API call failed with status {response.status_code} - Too Many Requests')
                        else:
                            raise Exception(f'Amap API call failed with status {response.status_code}')
                    except requests.exceptions.RequestException as e:
                        retry_count += 1
                        if retry_count < max_retries:
                            time.sleep(2 ** retry_count)  # Exponential backoff
                        else:
                            raise Exception(f'Amap API call failed: {str(e)}')
            else:
                # For other Amap services, we'll implement as needed
                raise Exception(f'Unsupported Amap service: {tool_name}')
        elif server_name == "fetch":
            # Make actual fetch API call
            url = args.get('url', '')
            headers = {
                "Authorization": f"Bearer {modelscope_token}"
            }
            api_url = "https://mcp.api-inference.modelscope.net/978f1188c2404b/sse"
            payload = {
                "url": url
            }
            response = requests.post(api_url, headers=headers, json=payload)
            if response.status_code == 200:
                return {
                    'status': 'success',
                    'data': response.json()
                }
            else:
                raise Exception(f'Fetch API call failed with status {response.status_code}')
        elif server_name == "juhe-mcp-server":
            # For juhe services, implement as needed
            raise Exception(f'Juhe services are not implemented yet: {tool_name}')
        else:
            raise Exception(f'Unsupported MCP server: {server_name}')
        
    except Exception as e:
        print(f"MCP service call failed: {str(e)}")
        return {
            'status': 'error',
            'message': str(e),
            'server_name': server_name,
            'tool_name': tool_name
        }


# ====== MCP service integration tool implementation ======
@register_tool('search_web')
class BingSearchTool(BaseTool):
    """
    Web search tool, directly uses Bing search MCP service to get information
    """
    description = 'Search for relevant information on the internet'
    parameters = [{
        'name': 'query',
        'type': 'string',
        'description': 'Search query',
        'required': True
    }]

    def call(self, params: str, **kwargs) -> str:
        import json
        try:
            # Parse parameters
            args = json.loads(params)
            query = args['query']
            
            # Call Bing MCP service for web search
            result = run_mcp(
                server_name="bing-cn-mcp-server",
                tool_name="bing_search",
                args={"query": query, "num_results": 5}
            )
            
            # Process MCP service return result
            if result.get('status') == 'success':
                # Process real search results - handle different response formats
                data = result.get('data', {})
                search_results = []
                
                # Handle different possible response formats
                if 'results' in data:
                    search_results = data['results']
                elif isinstance(data, list):
                    # If data is a list, it might be the results directly
                    search_results = data
                elif 'data' in data:
                    # Handle nested data structure
                    search_results = data['data']
                else:
                    # Try to find any list-type field that might contain results
                    for key, value in data.items():
                        if isinstance(value, list):
                            search_results = value
                            break
                
                # If no results found in the data structure, check if the whole data is a single result
                if not search_results and data:
                    if isinstance(data, dict):
                        # If data is a dict but doesn't have a results key, try to treat it as a single result
                        search_results = [data]
                    else:
                        # If data is not a dict or list, wrap it in a list
                        search_results = [data]
                
                if search_results and len(search_results) > 0:
                    formatted_result = f"Search results (about '{query}'):\n\n"
                    # Process up to 5 results
                    for i, item in enumerate(search_results[:5], 1):
                        # Handle different possible item structures
                        if isinstance(item, dict):
                            title = item.get('title', item.get('name', f'Result {i}'))
                            description = item.get('description', item.get('snippet', item.get('content', 'No description')))
                            url = item.get('url', item.get('link', item.get('href', 'No link')))
                            formatted_result += f"{i}. **{title}**\n"
                            formatted_result += f"   Description: {description}\n"
                            formatted_result += f"   Link: {url}\n\n"
                        elif isinstance(item, str):
                            # If item is a string, try to parse as JSON if it looks like JSON
                            if item.strip().startswith('{') and item.strip().endswith('}'):
                                try:
                                    parsed_item = json.loads(item)
                                    title = parsed_item.get('title', parsed_item.get('name', f'Result {i}'))
                                    description = parsed_item.get('description', parsed_item.get('snippet', parsed_item.get('content', 'No description')))
                                    url = parsed_item.get('url', parsed_item.get('link', parsed_item.get('href', 'No link')))
                                    formatted_result += f"{i}. **{title}**\n"
                                    formatted_result += f"   Description: {description}\n"
                                    formatted_result += f"   Link: {url}\n\n"
                                except ValueError:
                                    # If JSON parsing fails, treat as plain text
                                    formatted_result += f"{i}. {item}\n\n"
                            else:
                                # If not JSON-like, treat as plain text
                                formatted_result += f"{i}. {item}\n\n"
                        else:
                            # If item is not a dict or string, convert to string
                            formatted_result += f"{i}. {str(item)}\n\n"
                    return formatted_result
                else:
                    # Try to extract information from data if no results found
                    if data:
                        return f"Search results (about '{query}'):\n\n{json.dumps(data, ensure_ascii=False, indent=2)}"
                    else:
                        return f"No information found about '{query}'"
            else:
                return f"Search failed: {result.get('message', 'Unknown error')}"
                
        except json.JSONDecodeError:
            return "Error: Invalid parameter format, please provide valid JSON format parameters"
        except Exception as e:
            print(f"BingSearchTool error: {str(e)}")  # Debug info
            return f"Search failed: {str(e)}"


@register_tool('search_attractions')
class SearchAttractionsTool(BaseTool):
    """
    Attraction search tool, uses Amap MCP service to search for attractions in specified locations and provides attraction image links
    """
    description = 'Search for attraction information in specified locations'
    parameters = [{
        'name': 'location',
        'type': 'string',
        'description': 'Search location name, e.g.: Beijing, Shanghai, West Lake Hangzhou',
        'required': True
    }]

    def call(self, params: str, **kwargs) -> str:
        import json
        
        # Parse parameters
        args = json.loads(params)
        location = args.get('location', '').strip()
        
        if not location:
            return "Error: Please provide a valid location name"
        
        try:
            # Print debug information
            print(f"Starting to search for attraction information in {location}...")
            
            # Use correct parameter format to call Amap text_search interface
            result = run_mcp(
                server_name="amap-maps",
                tool_name="maps_text_search",
                args={
                    "keywords": f"{location} 景点",  # Use location-specific keywords
                    "city": location,       # Specify city
                }
            )
            
            # Print MCP service return result for debugging
            print(f"Amap API return result: {result}")
            
            # Process MCP service return result
            if result.get('status') != 'success':
                error_msg = result.get('message', 'Unknown error')
                print(f"API call failed: {error_msg}")
                return f"Search failed: {error_msg}"
            
            # Get attraction data - supports different result formats
            data = result.get('data', {})
            attractions_data = []
            
            # Check multiple possible result fields
            if 'results' in data:
                attractions_data = data['results']
            elif 'pois' in data:
                # Amap API sometimes uses pois field
                attractions_data = data['pois']
            else:
                # Try to find any list type data
                for key, value in data.items():
                    if isinstance(value, list):
                        attractions_data = value
                        print(f"Got {len(attractions_data)} attractions from field '{key}'")
                        break
            
            # If no data is found, try using backup query method
            if not attractions_data:
                print(f"First query returned no results, trying backup query method")
                alt_result = run_mcp(
                    server_name="amap-maps",
                    tool_name="maps_text_search",
                    args={"keywords": f"{location} 景点"}
                )
                
                if alt_result.get('status') == 'success':
                    alt_data = alt_result.get('data', {})
                    if 'results' in alt_data:
                        attractions_data = alt_data['results']
                    elif 'pois' in alt_data:
                        attractions_data = alt_data['pois']
            
            # Process found attraction data
            if attractions_data:
                print(f"Found {len(attractions_data)} attractions")
                formatted_result = f"Popular attractions in {location}:\n\n"
                
                # Process first 5 attractions
                for i, attraction in enumerate(attractions_data[:5], 1):
                    poi_id = attraction.get('id', '')
                    name = attraction.get('name', attraction.get('title', 'Unknown attraction'))
                    address = attraction.get('address', attraction.get('location', 'Address unknown'))
                    
                    print(f"Processing attraction #{i}: {name}")
                    
                    # Build attraction information
                    formatted_result += f"{i}. **{name}**\n"
                    formatted_result += f"   Address: {address}\n"
                    
                    # Try to get attraction details (may contain images)
                    if poi_id:
                        try:
                            detail_result = run_mcp(
                                server_name="amap-maps",
                                tool_name="maps_search_detail",
                                args={"id": poi_id}
                            )
                            
                            # Add image information
                            if detail_result and detail_result.get('status') == 'success':
                                detail_data = detail_result.get('data', {})
                                photos_found = False
                                
                                # Check multiple possible image field locations
                                if detail_data and 'photos' in detail_data:
                                    photos = detail_data['photos'][:2]  # Show at most 2 images
                                    for j, photo in enumerate(photos, 1):
                                        photo_url = photo.get('url', '')
                                        if photo_url:
                                            try:
                                                # Download image to local storage
                                                local_image_path = download_and_save_image(photo_url, name)
                                                if local_image_path:
                                                    formatted_result += f"   Image{j}: <img src='{local_image_path}' alt='{name} image{j}' style='max-width: 300px; max-height: 200px;'>\n"
                                                else:
                                                    formatted_result += f"   Image{j}: Image download failed\n"
                                            except Exception as img_e:
                                                print(f"Failed to download image: {str(img_e)}")
                                                formatted_result += f"   Image{j}: Image download failed\n"
                                            photos_found = True
                                
                                # If no images found, check if main data has images
                                if not photos_found and 'photos' in attraction:
                                    main_photos = attraction['photos'][:2]
                                    for j, photo in enumerate(main_photos, 1):
                                        photo_url = photo.get('url', '')
                                        if photo_url:
                                            try:
                                                local_image_path = download_and_save_image(photo_url, name)
                                                if local_image_path:
                                                    formatted_result += f"   Image{j}: <img src='{local_image_path}' alt='{name} image{j}' style='max-width: 300px; max-height: 200px;'>\n"
                                                else:
                                                    formatted_result += f"   Image{j}: Image download failed\n"
                                            except Exception as img_e:
                                                formatted_result += f"   Image{j}: Image download failed\n"
                                    if not photos_found:
                                        formatted_result += "   Image: No image information obtained yet\n"
                            else:
                                formatted_result += "   Image: Attraction details acquisition failed\n"
                        except Exception as detail_e:
                            print(f"Failed to get attraction details: {str(detail_e)}")
                            formatted_result += "   Image: Attraction details acquisition failed\n"
                    else:
                        # If no poi_id, try to get images from main data
                        if 'photos' in attraction:
                            main_photos = attraction['photos'][:2]
                            for j, photo in enumerate(main_photos, 1):
                                photo_url = photo.get('url', '')
                                if photo_url:
                                    try:
                                        local_image_path = download_and_save_image(photo_url, name)
                                        if local_image_path:
                                            formatted_result += f"   Image{j}: <img src='{local_image_path}' alt='{name} image{j}' style='max-width: 300px; max-height: 200px;'>\n"
                                        else:
                                            formatted_result += f"   Image{j}: Image download failed\n"
                                    except Exception as img_e:
                                        formatted_result += f"   Image{j}: Image download failed\n"
                            if not attraction['photos']:
                                formatted_result += "   Image: No image information obtained yet\n"
                        else:
                            formatted_result += "   Image: No image information obtained yet\n"
                    
                    formatted_result += "\n"
                
                return formatted_result
            else:
                print(f"No attraction information found in {location}")
                return f"No attraction information found in {location}, please try using other keywords to search"
                
        except json.JSONDecodeError:
            return "Error: Invalid parameter format, please provide valid JSON format parameters"
        except Exception as e:
            print(f"Search process exception occurred: {str(e)}")
            import traceback
            traceback.print_exc()
            return f"Search failed: {str(e)}"


@register_tool('around_search_attractions')
class AroundSearchAttractionsTool(BaseTool):
    """
    Surrounding attractions search tool, uses Amap surrounding search API to find attractions near specified locations and provides images
    """
    description = 'Search for attraction information near specified locations and provide images'
    parameters = [{
        'name': 'location',
        'type': 'string',
        'description': 'Search center location, can be address, place name or latitude/longitude coordinates (format: longitude,latitude)',
        'required': True
    }, {
        'name': 'radius',
        'type': 'integer',
        'description': 'Search radius, unit: meters, default 3000 meters',
        'required': False
    }, {
        'name': 'city',
        'type': 'string',
        'description': 'City name, helps improve search accuracy',
        'required': False
    }]

    def call(self, params: str, **kwargs) -> str:
        import json
        try:
            # Parse parameters
            args = json.loads(params)
            location = args.get('location', '').strip()
            radius = args.get('radius', 3000)
            city = args.get('city', '')
            
            if not location:
                return "Error: Please provide a valid search location"
            
            # First try to get location coordinates (if address is provided)
            coordinates = location
            if ',' not in location or not self._is_valid_coordinates(location):
                # If not coordinate format, first perform geocoding to get coordinates
                geo_result = run_mcp(
                    server_name='amap-maps',
                    tool_name='maps_geo',
                    args={
                        'address': location,
                        'city': city
                    }
                )
                
                if geo_result.get('status') == 'success':
                    data = geo_result.get('data', {})
                    if 'location' in data:
                        coordinates = data['location']
                    else:
                        return f"Unable to get location coordinates: {location}"
                else:
                    return f"Geocoding failed: {geo_result.get('message', 'Unknown error')}"
            
            # Use surrounding search API to find attractions
            around_result = run_mcp(
                server_name='amap-maps',
                tool_name='maps_around_search',
                args={
                    'location': coordinates,
                    'keywords': 'tourist attractions',
                    'radius': radius,
                    'city': city
                }
            )
            
            # Process search results
            if around_result.get('status') == 'success':
                data = around_result.get('data', {})
                # Process real search results
                if 'results' in data and data['results']:
                    results = data['results']
                    formatted_result = f"Found {len(results)} attractions within {radius} meters of {location}:\n\n"
                    
                    # Process first 5 attractions
                    for i, attraction in enumerate(results[:5], 1):
                        poi_id = attraction.get('id', '')
                        name = attraction.get('name', 'Unknown attraction')
                        address = attraction.get('address', 'Address unknown')
                        distance = attraction.get('distance', 'Distance unknown')
                        location_info = attraction.get('location', 'Location unknown')
                        
                        # Build attraction information
                        formatted_result += f"{i}. **{name}**\n"
                        formatted_result += f"   Address: {address}\n"
                        formatted_result += f"   Distance: {distance} meters\n"
                        formatted_result += f"   Location: {location_info}\n"
                        
                        # Try to get attraction details and images
                        if poi_id:
                            detail_result = run_mcp(
                                server_name='amap-maps',
                                tool_name='maps_search_detail',
                                args={'id': poi_id}
                            )
                            
                            if detail_result and detail_result.get('status') == 'success':
                                detail_data = detail_result.get('data', {})
                                if 'photos' in detail_data and detail_data['photos']:
                                    photos = detail_data['photos'][:2]  # Show at most 2 images
                                    for j, photo in enumerate(photos, 1):
                                        photo_url = photo.get('url', '')
                                        if photo_url:
                                            # Download image to local storage
                                            local_image_path = download_and_save_image(photo_url)
                                            if local_image_path:
                                                formatted_result += f"   Image{j}: <img src='{local_image_path}' alt='{name} image{j}' style='max-width: 300px; max-height: 200px;'>\n"
                                            else:
                                                formatted_result += f"   Image{j}: Image download failed\n"
                                        else:
                                            formatted_result += "   Image: Image link unavailable\n"
                                else:
                                    formatted_result += "   Image: No image information obtained yet\n"
                            else:
                                formatted_result += "   Image: No image information obtained yet\n"
                            
                            formatted_result += "\n"
                        
                    return formatted_result
                else:
                    return f"No attractions found within {radius} meters of {location}, please try expanding search range or using other keywords"
            else:
                return f"Around search failed: {around_result.get('message', 'Unknown error')}"
                
        except json.JSONDecodeError:
            return "Error: Invalid parameter format, please provide valid JSON format parameters"
        except Exception as e:
            return f"Search failed: {str(e)}"
    
    def _is_valid_coordinates(self, coordinates: str) -> bool:
        """Check if coordinate format is valid"""
        try:
            parts = coordinates.split(',')
            if len(parts) != 2:
                return False
            lon, lat = float(parts[0]), float(parts[1])
            # Simple latitude/longitude range check
            return -180 <= lon <= 180 and -90 <= lat <= 90
        except:
            return False


@register_tool('mcp_fetch')
class MCPFetchTool(BaseTool):
    """
    MCP Fetch service tool, used to get URL content
    """
    description = 'Get content from specified URL'
    parameters = [{
        'name': 'url',
        'type': 'string',
        'description': 'URL address to get',
        'required': True
    }, {
        'name': 'max_length',
        'type': 'integer',
        'description': 'Maximum number of characters in returned content, default 5000',
        'required': False
    }, {
        'name': 'raw',
        'type': 'boolean',
        'description': 'Whether to return raw HTML content, default false',
        'required': False
    }]

    def call(self, params: str, **kwargs) -> str:
        import json
        args = json.loads(params)
        url = args['url']
        max_length = args.get('max_length', 5000)
        raw = args.get('raw', False)
        
        try:
            # Call MCP fetch service
            result = run_mcp(
                server_name='fetch',
                tool_name='fetch',
                args={'url': url, 'max_length': max_length, 'raw': raw}
            )
            return result.get('content', 'Failed to get content')
        except Exception as e:
            return f"Failed to call MCP Fetch service: {str(e)}"


@register_tool('mcp_weather')
class MCPWeatherTool(BaseTool):
    """
    MCP weather query service tool
    """
    description = 'Query weather conditions in specified cities'
    parameters = [{
        'name': 'city',
        'type': 'string',
        'description': 'City name, e.g.: Beijing',
        'required': True
    }]

    def call(self, params: str, **kwargs) -> str:
        import json
        args = json.loads(params)
        city = args['city']
        
        try:
            # Call MCP weather service
            result = run_mcp(
                server_name='juhe-mcp-server',
                tool_name='get_weather',
                args={'city': city}
            )
            return self.format_weather_result(result)
        except Exception as e:
            return f"Failed to call MCP weather service: {str(e)}"
    
    def format_weather_result(self, result: dict) -> str:
        """Format weather query result"""
        if not result:
            return "No weather information obtained"
        
        # Format output according to actual return structure
        if isinstance(result, dict):
            if 'weather' in result:
                return f"Weather query result:\nCity: {result.get('city', 'Unknown')}\n{result.get('weather', '')}"
            else:
                return json.dumps(result, ensure_ascii=False, indent=2)
        return str(result)


@register_tool('mcp_train_ticket')
class MCPTrainTicketTool(BaseTool):
    """
    MCP train ticket query service tool
    """
    description = 'Query train ticket information'
    parameters = [{
        'name': 'departure_station',
        'type': 'string',
        'description': 'Departure city or station name',
        'required': True
    }, {
        'name': 'arrival_station',
        'type': 'string',
        'description': 'Arrival city or station name',
        'required': True
    }, {
        'name': 'date',
        'type': 'string',
        'description': 'Departure date, format: YYYY-MM-DD',
        'required': True
    }, {
        'name': 'filter',
        'type': 'string',
        'description': 'Train filter conditions, such as G(high-speed/intercity), D(EMU), Z(direct express), T(express), K(fast) etc.',
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
            # Call MCP train ticket query service
            result = run_mcp(
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
            return f"Failed to call MCP train ticket query service: {str(e)}"
    
    def format_train_result(self, result: dict) -> str:
        """Format train ticket query result"""
        if not result:
            return "No train ticket information obtained"
        
        # Format output according to actual return structure
        if isinstance(result, dict):
            if 'tickets' in result:
                tickets = result['tickets']
                result_str = f"Train ticket query result:\nDeparture station: {result.get('departure_station')}\nArrival station: {result.get('arrival_station')}\nDate: {result.get('date')}\n\nTrain information:\n"
                for ticket in tickets[:5]:  # Show at most 5 records
                    result_str += f"Train number: {ticket.get('train_no', 'N/A')} | Departure time: {ticket.get('departure_time', 'N/A')} | Arrival time: {ticket.get('arrival_time', 'N/A')} | Price: {ticket.get('price', 'N/A')}\n"
                return result_str
            else:
                return json.dumps(result, ensure_ascii=False, indent=2)
        return str(result)


@register_tool('mcp_maps')
class MCPMapsTool(BaseTool):
    """
    MCP map service tool, used for geographic location query, route planning, etc.
    """
    description = 'Use map service to query geographic location information or perform route planning'
    parameters = [{
        'name': 'action',
        'type': 'string',
        'description': 'Operation type: geocode(address to coordinates), regeocode(coordinates to address), direction_driving(driving navigation), distance(distance measurement)',
        'required': True
    }, {
        'name': 'address',
        'type': 'string',
        'description': 'Address information, used for geocode operation',
        'required': False
    }, {
        'name': 'location',
        'type': 'string',
        'description': 'Latitude/longitude coordinates, format: longitude,latitude, used for regeocode and other operations',
        'required': False
    }, {
        'name': 'origin',
        'type': 'string',
        'description': 'Starting point latitude/longitude, used for route planning, format: longitude,latitude',
        'required': False
    }, {
        'name': 'destination',
        'type': 'string',
        'description': 'Destination latitude/longitude, used for route planning, format: longitude,latitude',
        'required': False
    }]

    def call(self, params: str, **kwargs) -> str:
        import json
        args = json.loads(params)
        action = args['action']
        
        try:
            # Select different map services according to action
            if action == 'geocode':
                # Address to coordinates
                result = run_mcp(
                    server_name='amap-maps',
                    tool_name='maps_geo',
                    args={
                        'address': args.get('address', ''),
                        'city': args.get('city', '')
                    }
                )
            elif action == 'regeocode':
                # Coordinates to address
                result = run_mcp(
                    server_name='amap-maps',
                    tool_name='maps_regeocode',
                    args={'location': args.get('location', '')}
                )
            elif action == 'direction_driving':
                # Driving navigation
                result = run_mcp(
                    server_name='amap-maps',
                    tool_name='maps_direction_driving',
                    args={
                        'origin': args.get('origin', ''),
                        'destination': args.get('destination', '')
                    }
                )
            elif action == 'distance':
                # Distance measurement
                result = run_mcp(
                    server_name='amap-maps',
                    tool_name='maps_distance',
                    args={
                        'origins': args.get('origin', ''),
                        'destination': args.get('destination', ''),
                        'type': args.get('type', '0')  # 0 for straight-line distance
                    }
                )
            elif action == 'weather':
                # Map weather query
                result = run_mcp(
                    server_name='amap-maps',
                    tool_name='maps_weather',
                    args={'city': args.get('city', '')}
                )
            else:
                return f"Unsupported map operation type: {action}"
            
            return self.format_maps_result(action, result)
        except Exception as e:
            return f"Failed to call MCP map service: {str(e)}"
    
    def format_maps_result(self, action: str, result: dict) -> str:
        """Format map service result"""
        if not result:
            return f"No {action} information obtained"
        
        # Simple format output
        if isinstance(result, dict):
            return json.dumps(result, ensure_ascii=False, indent=2)
        return str(result)


@register_tool('mcp_amap_maps')
class MCPAmapMapsTool(BaseTool):
    """
    Amap MCP service tool, supports address query, route planning, attraction search, etc.
    """
    description = 'Use Amap service for address query, route planning, attraction search, etc.'
    parameters = [{
        'name': 'action',
        'type': 'string',
        'description': 'Operation type: geocode(address to coordinates), regeocode(coordinates to address), text_search(text search), direction_driving(driving navigation), distance(distance measurement), weather(weather query), search_detail(search details)',
        'required': True
    }, {
        'name': 'query',
        'type': 'string',
        'description': 'Search query, used for text_search operation',
        'required': False
    }, {
        'name': 'address',
        'type': 'string',
        'description': 'Address information, used for geocode operation',
        'required': False
    }, {
        'name': 'location',
        'type': 'string',
        'description': 'Latitude/longitude coordinates, format: longitude,latitude, used for regeocode and other operations',
        'required': False
    }, {
        'name': 'origin',
        'type': 'string',
        'description': 'Starting point latitude/longitude, used for route planning, format: longitude,latitude',
        'required': False
    }, {
        'name': 'destination',
        'type': 'string',
        'description': 'Destination latitude/longitude, used for route planning, format: longitude,latitude',
        'required': False
    }, {
        'name': 'city',
        'type': 'string',
        'description': 'City name, used for text_search or weather operation',
        'required': False
    }, {
        'name': 'id',
        'type': 'string',
        'description': 'POI ID, used for search_detail operation',
        'required': False
    }]

    def call(self, params: str, **kwargs) -> str:
        import json
        args = json.loads(params)
        action = args['action']
        
        try:
            # Select different map services according to action
            if action == 'geocode':
                # Address to coordinates
                result = run_mcp(
                    server_name='amap-maps',
                    tool_name='maps_geo',
                    args={
                        'address': args.get('address', ''),
                        'city': args.get('city', '')
                    }
                )
            elif action == 'regeocode':
                # Coordinates to address
                result = run_mcp(
                    server_name='amap-maps',
                    tool_name='maps_regeocode',
                    args={'location': args.get('location', '')}
                )
            elif action == 'text_search':
                # Text search
                result = run_mcp(
                    server_name='amap-maps',
                    tool_name='maps_text_search',
                    args={
                        'query': args.get('query', ''),
                        'city': args.get('city', ''),
                        'types': args.get('types', '')
                    }
                )
            elif action == 'direction_driving':
                # Driving navigation
                result = run_mcp(
                    server_name='amap-maps',
                    tool_name='maps_direction_driving',
                    args={
                        'origin': args.get('origin', ''),
                        'destination': args.get('destination', '')
                    }
                )
            elif action == 'distance':
                # Distance measurement
                result = run_mcp(
                    server_name='amap-maps',
                    tool_name='maps_distance',
                    args={
                        'origins': args.get('origin', ''),
                        'destination': args.get('destination', ''),
                        'type': args.get('type', '0')  # 0 for straight-line distance
                    }
                )
            elif action == 'weather':
                # Map weather query
                result = run_mcp(
                    server_name='amap-maps',
                    tool_name='maps_weather',
                    args={'city': args.get('city', '')}
                )
            elif action == 'search_detail':
                # Search details
                result = run_mcp(
                    server_name='amap-maps',
                    tool_name='maps_search_detail',
                    args={'id': args.get('id', '')}
                )
            else:
                return f"Unsupported map operation type: {action}"
            
            return self.format_maps_result(action, result)
        except Exception as e:
            return f"Failed to call Amap MCP service: {str(e)}"
    
    def format_maps_result(self, action: str, result: dict) -> str:
        """Format map service result"""
        if not result:
            return f"No {action} information obtained"
        
        if isinstance(result, dict):
            if result.get('status') == 'success':
                data = result.get('data', {})
                # Process real results
                if action == 'text_search' and 'results' in data:
                    results = data['results']
                    if results:
                        formatted_result = f"Search results (total {len(results)}):\n\n"
                        for i, item in enumerate(results[:5], 1):  # Show at most first 5 results
                            name = item.get('name', 'Unknown name')
                            address = item.get('address', 'Address unknown')
                            location = item.get('location', 'Location unknown')
                            formatted_result += f"{i}. **{name}**\n"
                            formatted_result += f"   Address: {address}\n"
                            formatted_result += f"   Location: {location}\n\n"
                        return formatted_result
                    else:
                        return "No related search results found"
                elif action == 'search_detail' and data:
                    # Process POI details
                    formatted_result = "Location details:\n"
                    for key, value in data.items():
                        formatted_result += f"{key}: {value}\n"
                    return formatted_result
                else:
                    # Generic JSON format output
                    import json
                    return json.dumps(data, ensure_ascii=False, indent=2)
            else:
                return f"Map service call failed: {result.get('message', 'Unknown error')}"
        
        return str(result)