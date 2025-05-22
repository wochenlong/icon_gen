import os
import sys
import json
import uuid
import time
import random
import base64
import websocket
import requests
from datetime import datetime
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("警告: 未安装PIL库，部分图像处理功能将不可用")

# 配置文件路径
CONFIG_FILE = "comfyui_api_config.json"

# 配置参数
CONFIG = {
    "server_address": "127.0.0.1:8188",  # ComfyUI服务器地址
    "output_folder": r"E:\img",  # 输出文件夹路径
    "input_folder": r"E:\M72",  # 输入图片文件夹
    "workflow_path": "default_workflow.json",  # 工作流JSON文件路径，使用默认工作流
    "debug": False,  # 调试模式
    "default_steps": 20,  # 默认采样步数
    "default_cfg": 8.0,  # 默认CFG值
    "default_denoise": 0.75,  # 默认去噪强度
    "default_negative_prompt": "低质量, 模糊, 畸变, 扭曲, 低分辨率, 低细节",  # 默认负面提示词
    "timeout": 60,  # API请求超时时间（秒）
    "save_workflow": True,  # 是否保存修改后的工作流
    "auto_convert_format": True  # 自动转换图像格式
}

def load_config():
    """从配置文件加载配置"""
    global CONFIG
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                # 更新配置，但保留默认值作为后备
                for key, value in loaded_config.items():
                    CONFIG[key] = value
            print(f"已从 {CONFIG_FILE} 加载配置")
        else:
            # 如果配置文件不存在，保存当前配置
            save_config()
    except Exception as e:
        print(f"加载配置文件时出错: {e}")

def save_config():
    """保存配置到文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(CONFIG, f, indent=4, ensure_ascii=False)
        print(f"配置已保存到 {CONFIG_FILE}")
    except Exception as e:
        print(f"保存配置文件时出错: {e}")

# 加载配置
load_config()

def print_debug(message):
    """打印调试信息"""
    if CONFIG.get("debug", False):
        print(f"[调试] {message}")

def establish_connection():
    """建立与ComfyUI服务器的WebSocket连接"""
    server_address = CONFIG["server_address"]
    client_id = str(uuid.uuid4())
    print_debug(f"连接到服务器: {server_address}")
    print_debug(f"客户端ID: {client_id}")
    
    try:
        # 先检查服务器是否运行
        print("检查ComfyUI服务器是否运行...")
        response = requests.get(f"http://{server_address}/system_stats")
        if response.status_code != 200:
            print(f"错误: 无法连接到ComfyUI服务器 ({server_address})，请确保服务器正在运行")
            return None, server_address, client_id
            
        print("ComfyUI服务器已连接!")
        
        # 建立WebSocket连接
        ws = websocket.WebSocket()
        ws.connect(f"ws://{server_address}/ws?clientId={client_id}")
        print_debug("WebSocket连接已建立")
        return ws, server_address, client_id
        
    except requests.exceptions.ConnectionError:
        print(f"错误: 无法连接到ComfyUI服务器 ({server_address})，请确保服务器正在运行")
        return None, server_address, client_id
    except Exception as e:
        print(f"建立连接时出错: {e}")
        return None, server_address, client_id

def queue_prompt(prompt, client_id, server_address):
    """将工作流提交到队列中执行"""
    # 确保所有节点ID是字符串类型
    fixed_prompt = {}
    if isinstance(prompt, dict):
        for node_id, node_data in prompt.items():
            fixed_prompt[str(node_id)] = node_data
    else:
        fixed_prompt = prompt
    
    data = {"prompt": fixed_prompt, "client_id": client_id}
    headers = {"Content-Type": "application/json"}
    
    print_debug(f"提交工作流到队列")
    try:
        response = requests.post(f"http://{server_address}/prompt", json=data, headers=headers)
        
        if response.status_code != 200:
            print(f"错误: API返回{response.status_code} - {response.text}")
            return None
            
        return response.json()
    except Exception as e:
        print(f"提交工作流失败: {e}")
        import traceback
        print(traceback.format_exc())
        return None

def get_history(prompt_id, server_address):
    """获取已完成工作流的输出数据"""
    print_debug(f"获取历史记录: {prompt_id}")
    response = requests.get(f"http://{server_address}/history/{prompt_id}")
    
    if response.status_code != 200:
        print(f"错误: 获取历史记录失败 - {response.status_code}")
        return None
        
    return response.json()

def get_image(filename, subfolder, folder_type, server_address):
    """获取生成的图像"""
    params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    print_debug(f"获取图像: {filename}")
    
    response = requests.get(f"http://{server_address}/view", params=params)
    
    if response.status_code != 200:
        print(f"错误: 获取图像失败 - {response.status_code}")
        return None
        
    return response.content

def upload_image(input_path, server_address, folder_type="input", image_type="image", overwrite=True):
    """上传图像到ComfyUI服务器"""
    filename = os.path.basename(input_path)
    print_debug(f"上传图像: {filename}")
    
    try:
        # 如果启用了自动格式转换，确保图像是PNG格式
        temp_file = None
        if CONFIG.get("auto_convert_format", True) and PIL_AVAILABLE:
            _, ext = os.path.splitext(input_path)
            if ext.lower() not in ['.png', '.jpg', '.jpeg', '.webp']:
                try:
                    temp_filename = f"temp_{uuid.uuid4().hex}.png"
                    temp_file = os.path.join(os.path.dirname(input_path), temp_filename)
                    img = Image.open(input_path)
                    img.save(temp_file, "PNG")
                    print(f"图像已转换为PNG格式: {temp_file}")
                    input_path = temp_file
                    filename = temp_filename
                except Exception as e:
                    print(f"图像格式转换失败: {e}")
        
        with open(input_path, 'rb') as file:
            files = {
                "image": (filename, file, 'image/png')
            }
            data = {
                "type": folder_type,
                "overwrite": str(overwrite).lower()
            }
            url = f"http://{server_address}/upload/{image_type}"
            
            # 设置超时参数
            timeout = CONFIG.get("timeout", 60)
            response = requests.post(url, files=files, data=data, timeout=timeout)
            
            if response.status_code != 200:
                print(f"错误: 上传图像失败 - {response.status_code}")
                return None
                
            print_debug(f"图像上传成功: {filename}")
            
            # 如果创建了临时文件，删除它
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    print_debug(f"临时文件已删除: {temp_file}")
                except Exception as e:
                    print_debug(f"无法删除临时文件: {e}")
                    
            return filename
    except Exception as e:
        print(f"上传图像失败: {e}")
        
        # 如果创建了临时文件，删除它
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass
                
        return None

def load_workflow(path):
    """加载工作流JSON"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            workflow_data = json.load(f)
        
        # 如果是从ComfyUI保存的API格式，则需要提取prompt部分
        if isinstance(workflow_data, dict) and "prompt" in workflow_data:
            workflow_data = workflow_data["prompt"]
        
        # 确保工作流是字典格式并符合要求
        if not isinstance(workflow_data, dict):
            print(f"错误: 工作流不是有效的字典格式")
            return None
            
        # 确保所有节点ID是字符串类型
        workflow_fixed = {}
        for node_id, node_data in workflow_data.items():
            # 确保节点ID是字符串
            str_node_id = str(node_id)
            
            # 跳过非字典类型的节点数据
            if not isinstance(node_data, dict):
                print(f"警告: 节点 {node_id} 数据不是字典格式，已跳过")
                continue
                
            workflow_fixed[str_node_id] = node_data
            
        return workflow_fixed
    except Exception as e:
        print(f"加载工作流失败: {e}")
        import traceback
        print(traceback.format_exc())
        return None

def get_available_models(server_address):
    """获取服务器上可用的模型列表"""
    try:
        response = requests.get(f"http://{server_address}/object_info")
        if response.status_code != 200:
            print(f"错误: 获取模型信息失败 - {response.status_code}")
            return None
            
        object_info = response.json()
        
        # 提取可用的模型
        checkpoints = []
        if "CheckpointLoaderSimple" in object_info:
            for input_name, input_info in object_info["CheckpointLoaderSimple"]["input"]["required"].items():
                if input_name == "ckpt_name" and isinstance(input_info, list) and len(input_info) > 0:
                    checkpoints = input_info[0]
                    print(f"可用模型: {', '.join(checkpoints[:5])}...")
        
        return checkpoints
    except Exception as e:
        print(f"获取可用模型失败: {e}")
        return None
        
def update_workflow(workflow, input_image, positive_prompt):
    """更新工作流参数"""
    try:
        if not workflow or not isinstance(workflow, dict):
            print("错误: 无效的工作流数据")
            return workflow
            
        # 创建节点ID到类型的映射
        id_to_class_type = {}
        for node_id, node_data in workflow.items():
            if isinstance(node_data, dict) and "class_type" in node_data:
                id_to_class_type[node_id] = node_data["class_type"]
        
        print_debug(f"工作流节点类型: {id_to_class_type}")
        
        # 如果没有找到任何节点，可能是工作流格式不对
        if not id_to_class_type:
            print("警告: 工作流中未找到任何有效节点")
            return workflow
            
        # 获取可用的模型
        models = get_available_models(CONFIG["server_address"])
        
        # 检查并更新模型名称
        checkpoint_nodes = [key for key, value in id_to_class_type.items() 
                          if value in ["CheckpointLoaderSimple", "CheckpointLoader"]]
        
        if models and checkpoint_nodes:
            for checkpoint_node in checkpoint_nodes:
                if ("inputs" in workflow[checkpoint_node] and 
                    "ckpt_name" in workflow[checkpoint_node]["inputs"]):
                    current_model = workflow[checkpoint_node]["inputs"]["ckpt_name"]
                    
                    # 如果当前模型不在可用列表中，则更换为第一个可用模型
                    if current_model not in models and models:
                        print(f"注意: 模型 '{current_model}' 不可用，已切换到 '{models[0]}'")
                        workflow[checkpoint_node]["inputs"]["ckpt_name"] = models[0]
        
        # 更新随机种子
        k_sampler_nodes = [key for key, value in id_to_class_type.items() if 'KSampler' in value]
        for k_sampler in k_sampler_nodes:
            if ("inputs" in workflow[k_sampler] and 
                isinstance(workflow[k_sampler]["inputs"], dict) and 
                "seed" in workflow[k_sampler]["inputs"]):
                workflow[k_sampler]["inputs"]["seed"] = random.randint(1, 2**32 - 1)
                print_debug(f"更新种子值: {workflow[k_sampler]['inputs']['seed']}")
                
                # 更新正向提示词
                if "positive" in workflow[k_sampler]["inputs"]:
                    positive_node_id = workflow[k_sampler]["inputs"]["positive"]
                    if isinstance(positive_node_id, list) and len(positive_node_id) > 0:
                        positive_node_id = positive_node_id[0]
                    
                    if (positive_node_id in workflow and 
                        isinstance(workflow[positive_node_id], dict) and
                        "inputs" in workflow[positive_node_id] and 
                        isinstance(workflow[positive_node_id]["inputs"], dict) and
                        "text" in workflow[positive_node_id]["inputs"]):
                        workflow[positive_node_id]["inputs"]["text"] = positive_prompt
                        print_debug(f"更新正向提示词: {positive_prompt[:30]}...")
        
        # 更新输入图像
        load_image_nodes = [key for key, value in id_to_class_type.items() if value in ["LoadImage", "LoadImageMask"]]
        for load_image in load_image_nodes:
            if ("inputs" in workflow[load_image] and 
                isinstance(workflow[load_image]["inputs"], dict) and
                "image" in workflow[load_image]["inputs"]):
                workflow[load_image]["inputs"]["image"] = input_image
                print_debug(f"更新输入图像: {input_image}")
        
        return workflow
    except Exception as e:
        print(f"更新工作流失败: {e}")
        import traceback
        print(traceback.format_exc())
        return workflow

def track_progress(ws, prompt_id):
    """跟踪图像生成进度"""
    print("正在生成图像，请稍候...")
    
    try:
        while True:
            message = json.loads(ws.recv())
            
            if message["type"] == "progress":
                progress = message["data"]["value"]
                max_progress = message["data"]["max"]
                print(f"进度: {progress}/{max_progress}")
                
            elif message["type"] == "executing":
                node_name = message["data"].get("node", "未知节点")
                print_debug(f"正在执行节点: {node_name}")
                
            elif message["type"] == "execution_cached":
                print_debug(f"缓存执行: {message['data']}")
                
            # 检查完成状态
            if (message["type"] == "executed" and
                "prompt_id" in message["data"] and
                message["data"]["prompt_id"] == prompt_id):
                print("生成完成")
                return True
                
    except Exception as e:
        print(f"跟踪进度时出错: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def save_output_image(image_data, output_name):
    """保存输出图像到本地"""
    try:
        os.makedirs(CONFIG["output_folder"], exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        filename = f"{output_name}_{timestamp}.png"
        filepath = os.path.join(CONFIG["output_folder"], filename)
        
        with open(filepath, "wb") as img_file:
            img_file.write(image_data)
            
        print(f"图像已保存: {filepath}")
        return filepath
    except Exception as e:
        print(f"保存图像失败: {e}")
        return None

def generate_image(input_image_path, positive_prompt, output_name=None):
    """主函数：执行图生图过程"""
    if not os.path.exists(input_image_path):
        print(f"错误: 输入图像不存在 - {input_image_path}")
        return False
        
    # 首先确保有一个可用的工作流
    if not os.path.exists(CONFIG["workflow_path"]):
        print(f"工作流文件不存在，创建默认工作流")
        create_default_workflow()
        
    if not output_name:
        output_name = f"img2img_{os.path.basename(input_image_path).split('.')[0]}"
    
    # 建立连接
    ws, server_address, client_id = establish_connection()
    if not ws:
        return False
    
    try:
        # 加载工作流
        workflow = load_workflow(CONFIG["workflow_path"])
        if not workflow:
            print("创建并使用默认工作流")
            create_default_workflow()
            workflow = load_workflow(CONFIG["workflow_path"])
            if not workflow:
                print("无法创建工作流，程序退出")
                return False
            
        # 上传输入图像
        uploaded_filename = upload_image(input_image_path, server_address)
        if not uploaded_filename:
            return False
            
        # 更新工作流
        updated_workflow = update_workflow(workflow, uploaded_filename, positive_prompt)
        
        # 提交工作流到队列
        queue_result = queue_prompt(updated_workflow, client_id, server_address)
        if not queue_result:
            return False
            
        prompt_id = queue_result["prompt_id"]
        print(f"工作流已提交，ID: {prompt_id}")
        
        # 跟踪进度
        if not track_progress(ws, prompt_id):
            print("生成失败或中断")
            return False
            
        # 获取结果
        history = get_history(prompt_id, server_address)
        if not history:
            return False
            
        outputs = history[prompt_id]["outputs"]
        
        # 获取并保存输出图像
        saved_images = []
        for node_id in outputs:
            node_output = outputs[node_id]
            if "images" in node_output:
                for image_info in node_output["images"]:
                    image_data = get_image(
                        image_info["filename"],
                        image_info["subfolder"],
                        image_info["type"],
                        server_address
                    )
                    
                    if image_data:
                        saved_path = save_output_image(image_data, output_name)
                        if saved_path:
                            saved_images.append(saved_path)
        
        if saved_images:
            print(f"成功生成 {len(saved_images)} 张图像")
            return True
        else:
            print("没有生成任何图像")
            return False
            
    except Exception as e:
        print(f"生成图像时出错: {e}")
        import traceback
        print(traceback.format_exc())
        return False
        
    finally:
        ws.close()
        print("连接已关闭")

def list_input_images():
    """列出输入文件夹中的图像"""
    input_folder = CONFIG["input_folder"]
    if not os.path.exists(input_folder):
        print(f"错误: 输入文件夹不存在 - {input_folder}")
        return []
        
    image_files = []
    for file in os.listdir(input_folder):
        if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            image_files.append(os.path.join(input_folder, file))
            
    return image_files

def get_comfyui_info(server_address):
    """获取ComfyUI服务器详细信息"""
    print("获取ComfyUI服务器详细信息...")
    
    try:
        # 获取对象信息
        response = requests.get(f"http://{server_address}/object_info")
        if response.status_code != 200:
            print(f"错误: 获取对象信息失败 - {response.status_code}")
            return None
            
        object_info = response.json()
        
        # 获取系统信息
        response = requests.get(f"http://{server_address}/system_stats")
        if response.status_code != 200:
            print(f"错误: 获取系统信息失败 - {response.status_code}")
            return None
            
        system_stats = response.json()
        
        # 获取当前队列和历史记录
        response = requests.get(f"http://{server_address}/queue")
        queue_info = response.json() if response.status_code == 200 else {}
        
        # 提取有用信息
        info = {
            "available_nodes": list(object_info.keys()),
            "system_stats": system_stats,
            "queue_info": queue_info
        }
        
        # 提取可用模型
        checkpoints = []
        if "CheckpointLoaderSimple" in object_info:
            for input_name, input_info in object_info["CheckpointLoaderSimple"]["input"]["required"].items():
                if input_name == "ckpt_name" and isinstance(input_info, list) and len(input_info) > 0:
                    checkpoints = input_info[0]
                    print(f"可用模型: {', '.join(checkpoints[:5])}...")
                    info["checkpoints"] = checkpoints
        
        # 提取可用的CLIP模型
        clip_models = []
        for node_type, node_info in object_info.items():
            if "CLIPLoader" in node_type or "CLIPTextEncode" in node_type:
                if "input" in node_info and "required" in node_info["input"]:
                    for input_name, input_info in node_info["input"]["required"].items():
                        if input_name in ["clip_name", "clip"] and isinstance(input_info, list) and len(input_info) > 0:
                            if isinstance(input_info[0], list):
                                clip_models = input_info[0]
                                info["clip_models"] = clip_models
                                print(f"可用CLIP模型: {clip_models}")
                                break
        
        # 提取采样器信息
        samplers = []
        if "KSampler" in object_info and "input" in object_info["KSampler"] and "required" in object_info["KSampler"]["input"]:
            for input_name, input_info in object_info["KSampler"]["input"]["required"].items():
                if input_name == "sampler_name" and isinstance(input_info, list) and len(input_info) > 0:
                    samplers = input_info[0]
                    info["samplers"] = samplers
                    print(f"可用采样器: {', '.join(samplers)}")
        
        return info
    except Exception as e:
        print(f"获取ComfyUI信息失败: {e}")
        import traceback
        print(traceback.format_exc())
        return None

def create_default_workflow(server_info=None):
    """创建默认工作流并保存"""
    # 如果没有服务器信息，尝试获取
    if not server_info:
        server_info = get_comfyui_info(CONFIG["server_address"])
    
    # 确定使用的模型
    checkpoint = "sd_xl_base_1.0.safetensors"  # 默认模型
    sampler = "euler"  # 默认采样器
    
    if server_info and "checkpoints" in server_info and server_info["checkpoints"]:
        checkpoint = server_info["checkpoints"][0]  # 使用第一个可用模型
        print(f"使用模型: {checkpoint}")
        
    if server_info and "samplers" in server_info and server_info["samplers"]:
        sampler = server_info["samplers"][0]  # 使用第一个可用采样器
        print(f"使用采样器: {sampler}")
    
    # 创建一个简单的图生图工作流
    # 节点类型不同版本的ComfyUI可能不同，我们从服务器获取信息后构建工作流
    default_workflow = {}
    
    # 使用字符串作为节点ID
    default_workflow["1"] = {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
            "ckpt_name": checkpoint
        }
    }
    
    # CLIP文本编码正向提示词
    default_workflow["2"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": "精美的游戏图标",
            "clip": ["1", 1]  # 从CheckpointLoader获取CLIP
        }
    }
    
    # CLIP文本编码负向提示词
    default_workflow["3"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": CONFIG.get("default_negative_prompt", "低质量, 模糊, 畸变"),
            "clip": ["1", 1]  # 从CheckpointLoader获取CLIP
        }
    }
    
    # 加载图像
    default_workflow["4"] = {
        "class_type": "LoadImage",
        "inputs": {
            "image": "1 (38).png"  # 默认图像名称，会被替换
        }
    }
    
    # VAE编码
    default_workflow["5"] = {
        "class_type": "VAEEncode",
        "inputs": {
            "pixels": ["4", 0],
            "vae": ["1", 2]  # 从CheckpointLoader获取VAE
        }
    }
    
    # KSampler
    default_workflow["6"] = {
        "class_type": "KSampler",
        "inputs": {
            "seed": random.randint(1, 2**32 - 1),
            "steps": CONFIG.get("default_steps", 20),
            "cfg": CONFIG.get("default_cfg", 8),
            "sampler_name": sampler,
            "scheduler": "normal",
            "denoise": CONFIG.get("default_denoise", 0.75),
            "model": ["1", 0],
            "positive": ["2", 0],
            "negative": ["3", 0],
            "latent_image": ["5", 0]
        }
    }
    
    # VAE解码
    default_workflow["7"] = {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": ["6", 0],
            "vae": ["1", 2]  # 从CheckpointLoader获取VAE
        }
    }
    
    # 保存图像
    default_workflow["8"] = {
        "class_type": "SaveImage",
        "inputs": {
            "filename_prefix": "img2img_output",
            "images": ["7", 0]
        }
    }
    
    # 保存默认工作流
    with open("default_workflow.json", "w", encoding="utf-8") as f:
        json.dump(default_workflow, f, indent=2, ensure_ascii=False)
        
    CONFIG["workflow_path"] = "default_workflow.json"
    print("已创建默认工作流: default_workflow.json")
    return default_workflow

def interactive_mode():
    """交互模式"""
    print("\n=== ComfyUI 图生图 API 客户端 ===")
    print(f"输入图片文件夹: {CONFIG['input_folder']}")
    print(f"输出文件夹: {CONFIG['output_folder']}")
    print(f"ComfyUI服务器: {CONFIG['server_address']}")
    
    # 检查服务器连接
    ws, server_address, client_id = establish_connection()
    if not ws:
        # 尝试更新服务器地址
        new_address = input("请输入ComfyUI服务器地址 (例如: 127.0.0.1:8188): ").strip()
        if new_address:
            CONFIG["server_address"] = new_address
            ws, server_address, client_id = establish_connection()
            if not ws:
                print("无法连接到ComfyUI服务器，程序退出")
                return
        else:
            print("未提供服务器地址，程序退出")
            return
    
    if ws:
        ws.close()  # 关闭测试连接
    
    # 获取ComfyUI服务器信息并创建工作流
    server_info = get_comfyui_info(CONFIG["server_address"])
    
    # 创建默认工作流
    if not os.path.exists(CONFIG["workflow_path"]) or server_info:
        print("创建默认工作流")
        create_default_workflow(server_info)
    
    while True:
        print("\n=== 主菜单 ===")
        print("1. 生成单个图像")
        print("2. 批量处理图像")
        print("3. 修改配置")
        print("4. 查看当前配置")
        print("5. 检查队列状态")
        print("6. 退出")
        
        choice = input("请选择: ").strip()
        
        if choice == "1":
            # 列出可用的输入图像
            input_images = list_input_images()
            if not input_images:
                print("没有找到输入图像，请确认输入文件夹路径")
                input_folder = input("请输入输入图片文件夹路径: ").strip()
                if input_folder:
                    CONFIG["input_folder"] = input_folder
                    save_config()
                    input_images = list_input_images()
            
            if not input_images:
                print("仍然没有找到输入图像，请先添加图像到输入文件夹")
                continue
            
            print("\n可用的输入图像:")
            for i, image_path in enumerate(input_images):
                print(f"{i+1}. {os.path.basename(image_path)}")
            
            while True:
                try:
                    print("\n请选择要处理的图像 (输入序号或'返回'回到主菜单):")
                    choice = input().strip()
                    
                    if choice.lower() in ['back', 'return', '返回', 'b']:
                        break
                        
                    try:
                        index = int(choice) - 1
                        if 0 <= index < len(input_images):
                            selected_image = input_images[index]
                            print(f"已选择: {os.path.basename(selected_image)}")
                            
                            print("请输入正向提示词:")
                            positive_prompt = input().strip()
                            
                            print("开始生成图像...")
                            start_time = time.time()
                            
                            success = generate_image(selected_image, positive_prompt)
                            
                            end_time = time.time()
                            execution_time = end_time - start_time
                            
                            print(f"处理完成，耗时: {execution_time:.2f}秒")
                        else:
                            print("无效的选择，请重试")
                    except ValueError:
                        print("请输入有效的序号")
                except KeyboardInterrupt:
                    print("\n已中断")
                    break
                except Exception as e:
                    print(f"发生错误: {e}")
                    import traceback
                    print(traceback.format_exc())
        
        elif choice == "2":  # 批量处理
            # 列出可用的输入图像
            input_images = list_input_images()
            if not input_images:
                print("没有找到输入图像，请确认输入文件夹路径")
                input_folder = input("请输入输入图片文件夹路径: ").strip()
                if input_folder:
                    CONFIG["input_folder"] = input_folder
                    save_config()
                    input_images = list_input_images()
            
            if not input_images:
                print("仍然没有找到输入图像，请先添加图像到输入文件夹")
                continue
            
            print(f"\n找到 {len(input_images)} 张图像可供处理")
            print("选择批处理模式:")
            print("1. 处理所有图像")
            print("2. 选择多个图像")
            print("3. 返回")
            
            batch_choice = input("请选择: ").strip()
            
            if batch_choice == "1":
                # 处理所有图像
                print("请输入正向提示词 (将用于所有图像):")
                positive_prompt = input().strip()
                
                if positive_prompt:
                    batch_process(input_images, positive_prompt)
                else:
                    print("未输入提示词，取消批处理")
            
            elif batch_choice == "2":
                # 选择多个图像
                print("\n可用的输入图像:")
                for i, image_path in enumerate(input_images):
                    print(f"{i+1}. {os.path.basename(image_path)}")
                
                print("\n请输入要处理的图像序号，用逗号分隔 (例如: 1,3,5):")
                selected = input().strip()
                
                try:
                    selected_indices = [int(idx.strip()) - 1 for idx in selected.split(',')]
                    valid_indices = [idx for idx in selected_indices if 0 <= idx < len(input_images)]
                    
                    if valid_indices:
                        selected_images = [input_images[idx] for idx in valid_indices]
                        
                        print(f"已选择 {len(selected_images)} 张图像")
                        print("请输入正向提示词 (将用于所有选中图像):")
                        positive_prompt = input().strip()
                        
                        if positive_prompt:
                            batch_process(selected_images, positive_prompt)
                        else:
                            print("未输入提示词，取消批处理")
                    else:
                        print("未选择有效的图像，取消批处理")
                except ValueError:
                    print("输入格式错误，请输入有效的数字序号")
            
            elif batch_choice == "3":
                continue
                
            else:
                print("无效的选择")
        
        elif choice == "3":  # 修改配置
            print("\n=== 修改配置 ===")
            print("1. 服务器地址")
            print("2. 输入文件夹")
            print("3. 输出文件夹")
            print("4. 采样参数 (步数/CFG/去噪)")
            print("5. 默认负面提示词")
            print("6. 其他设置")
            print("7. 返回")
            
            config_choice = input("请选择要修改的配置: ").strip()
            
            if config_choice == "1":
                new_address = input(f"请输入服务器地址 (当前: {CONFIG['server_address']}): ").strip()
                if new_address:
                    CONFIG["server_address"] = new_address
                    save_config()
                    print(f"服务器地址已更新为: {new_address}")
            
            elif config_choice == "2":
                new_folder = input(f"请输入输入文件夹路径 (当前: {CONFIG['input_folder']}): ").strip()
                if new_folder:
                    if os.path.exists(new_folder):
                        CONFIG["input_folder"] = new_folder
                        save_config()
                        print(f"输入文件夹已更新为: {new_folder}")
                    else:
                        create = input("文件夹不存在，是否创建? (y/n): ").strip().lower()
                        if create in ['y', 'yes', '是']:
                            try:
                                os.makedirs(new_folder, exist_ok=True)
                                CONFIG["input_folder"] = new_folder
                                save_config()
                                print(f"已创建并设置输入文件夹: {new_folder}")
                            except Exception as e:
                                print(f"创建文件夹失败: {e}")
            
            elif config_choice == "3":
                new_folder = input(f"请输入输出文件夹路径 (当前: {CONFIG['output_folder']}): ").strip()
                if new_folder:
                    if os.path.exists(new_folder):
                        CONFIG["output_folder"] = new_folder
                        save_config()
                        print(f"输出文件夹已更新为: {new_folder}")
                    else:
                        create = input("文件夹不存在，是否创建? (y/n): ").strip().lower()
                        if create in ['y', 'yes', '是']:
                            try:
                                os.makedirs(new_folder, exist_ok=True)
                                CONFIG["output_folder"] = new_folder
                                save_config()
                                print(f"已创建并设置输出文件夹: {new_folder}")
                            except Exception as e:
                                print(f"创建文件夹失败: {e}")
            
            elif config_choice == "4":
                try:
                    print(f"当前采样步数: {CONFIG.get('default_steps', 20)}")
                    steps = input("请输入新的采样步数 (10-50, 回车跳过): ").strip()
                    if steps:
                        CONFIG["default_steps"] = int(steps)
                    
                    print(f"当前CFG值: {CONFIG.get('default_cfg', 8.0)}")
                    cfg = input("请输入新的CFG值 (1-30, 回车跳过): ").strip()
                    if cfg:
                        CONFIG["default_cfg"] = float(cfg)
                    
                    print(f"当前去噪强度: {CONFIG.get('default_denoise', 0.75)}")
                    denoise = input("请输入新的去噪强度 (0.0-1.0, 回车跳过): ").strip()
                    if denoise:
                        CONFIG["default_denoise"] = float(denoise)
                    
                    save_config()
                    print("采样参数已更新")
                except ValueError:
                    print("输入无效，请输入数字")
            
            elif config_choice == "5":
                print(f"当前默认负面提示词: {CONFIG.get('default_negative_prompt', '')}")
                new_negative = input("请输入新的默认负面提示词 (回车跳过): ").strip()
                if new_negative:
                    CONFIG["default_negative_prompt"] = new_negative
                    save_config()
                    print("默认负面提示词已更新")
            
            elif config_choice == "6":
                print("\n其他设置:")
                debug = input(f"启用调试模式? (y/n, 当前: {'是' if CONFIG.get('debug', False) else '否'}): ").strip().lower()
                if debug in ['y', 'yes', '是']:
                    CONFIG["debug"] = True
                elif debug in ['n', 'no', '否']:
                    CONFIG["debug"] = False
                
                auto_convert = input(f"启用自动格式转换? (y/n, 当前: {'是' if CONFIG.get('auto_convert_format', True) else '否'}): ").strip().lower()
                if auto_convert in ['y', 'yes', '是']:
                    CONFIG["auto_convert_format"] = True
                elif auto_convert in ['n', 'no', '否']:
                    CONFIG["auto_convert_format"] = False
                
                save_workflow = input(f"保存修改后的工作流? (y/n, 当前: {'是' if CONFIG.get('save_workflow', True) else '否'}): ").strip().lower()
                if save_workflow in ['y', 'yes', '是']:
                    CONFIG["save_workflow"] = True
                elif save_workflow in ['n', 'no', '否']:
                    CONFIG["save_workflow"] = False
                
                save_config()
                print("设置已更新")
        
        elif choice == "4":  # 查看当前配置
            print("\n=== 当前配置 ===")
            for key, value in CONFIG.items():
                print(f"{key}: {value}")
            input("按回车继续...")
        
        elif choice == "5":  # 检查队列状态
            check_queue_status(CONFIG["server_address"])
        
        elif choice == "6":  # 退出
            print("退出程序")
            break
        
        else:
            print("无效的选择，请重试")

def check_queue_status(server_address):
    """检查ComfyUI队列状态"""
    try:
        response = requests.get(f"http://{server_address}/queue")
        
        if response.status_code != 200:
            print(f"错误: 获取队列信息失败 - {response.status_code}")
            return None
            
        queue_data = response.json()
        
        # 检查当前队列中的任务数量
        queue_running = queue_data.get("queue_running", [])
        queue_pending = queue_data.get("queue_pending", [])
        
        # 输出队列状态
        print(f"队列状态: {len(queue_running)}个任务正在执行, {len(queue_pending)}个任务等待中")
        
        # 如果有正在执行的任务，打印详细信息
        if queue_running:
            for i, task in enumerate(queue_running):
                task_id = task.get("prompt_id", "未知")
                print(f"  运行中 #{i+1}: ID {task_id}")
                
        # 如果有等待的任务，打印数量
        if queue_pending:
            print(f"  等待中: {len(queue_pending)}个任务")
            
        return {
            "running": queue_running,
            "pending": queue_pending
        }
    except Exception as e:
        print(f"检查队列状态失败: {e}")
        return None

def batch_process(input_images, positive_prompt):
    """批量处理多个图像"""
    if not input_images:
        print("没有输入图像，无法批处理")
        return False
        
    successful = 0
    failed = 0
    start_time = time.time()
    
    print(f"开始批量处理 {len(input_images)} 张图像")
    print(f"使用正向提示词: {positive_prompt}")
    
    for i, image_path in enumerate(input_images):
        print(f"\n处理图像 {i+1}/{len(input_images)}: {os.path.basename(image_path)}")
        
        try:
            # 使用图像文件名作为输出文件名前缀
            output_name = f"batch_{os.path.basename(image_path).split('.')[0]}"
            
            success = generate_image(image_path, positive_prompt, output_name)
            
            if success:
                successful += 1
            else:
                failed += 1
                
        except Exception as e:
            print(f"处理图像 {os.path.basename(image_path)} 时出错: {e}")
            failed += 1
            
    end_time = time.time()
    total_time = end_time - start_time
    avg_time = total_time / len(input_images) if input_images else 0
    
    print(f"\n批处理完成!")
    print(f"总共处理: {len(input_images)} 张图像")
    print(f"成功: {successful}，失败: {failed}")
    print(f"总耗时: {total_time:.2f}秒，平均每张: {avg_time:.2f}秒")
    
    return successful > 0

def check_environment():
    """检查运行环境"""
    # 检查必要的依赖
    required_packages = {
        "websocket-client": "websocket",
        "requests": "requests",
        "pillow": "PIL"  # 如果PIL不可用，上面已经有检查
    }
    
    missing_packages = []
    for package_name, import_name in required_packages.items():
        if import_name == "PIL" and not PIL_AVAILABLE:
            missing_packages.append(package_name)
            continue
            
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(package_name)
    
    if missing_packages:
        print("警告: 缺少以下必要的依赖库:")
        for package in missing_packages:
            print(f"  - {package}")
        print("请使用以下命令安装依赖:")
        print("pip install -r requirements.txt")
    
    # 检查配置和工作目录
    print("检查工作环境...")
    
    # 检查输入文件夹
    if not os.path.exists(CONFIG.get("input_folder", "")):
        print(f"警告: 输入文件夹不存在: {CONFIG.get('input_folder')}")
        print("您可以稍后在配置中设置正确的输入文件夹")
    else:
        print(f"输入文件夹: {CONFIG.get('input_folder')} (存在)")
        
    # 检查输出文件夹
    if not os.path.exists(CONFIG.get("output_folder", "")):
        try:
            os.makedirs(CONFIG.get("output_folder", ""), exist_ok=True)
            print(f"已创建输出文件夹: {CONFIG.get('output_folder')}")
        except Exception as e:
            print(f"警告: 无法创建输出文件夹: {CONFIG.get('output_folder')}")
            print(f"错误: {e}")
    else:
        print(f"输出文件夹: {CONFIG.get('output_folder')} (存在)")
    
    # 检查工作流文件
    if not os.path.exists(CONFIG.get("workflow_path", "")):
        print(f"工作流文件不存在: {CONFIG.get('workflow_path')}")
        print("将在首次运行时创建默认工作流")
    else:
        print(f"工作流文件: {CONFIG.get('workflow_path')} (存在)")
    
    return True

def main():
    """主函数"""
    # 检查环境
    check_environment()
    
    # 解析命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "--debug":
            CONFIG["debug"] = True
            print("调试模式已启用")
            # 进入交互模式
            interactive_mode()
        elif sys.argv[1] == "--help" or sys.argv[1] == "-h":
            print("ComfyUI 图生图 API 客户端")
            print("用法:")
            print("  python comfyui_img2img_api.py                   - 进入交互模式")
            print("  python comfyui_img2img_api.py --debug           - 以调试模式进入交互模式")
            print("  python comfyui_img2img_api.py 图片路径 提示词     - 处理单个图像")
            print("  python comfyui_img2img_api.py --batch 文件夹 提示词 - 批量处理文件夹中的所有图像")
            print("  python comfyui_img2img_api.py --config          - 修改配置后进入交互模式")
            return
        elif sys.argv[1] == "--config":
            # 修改配置后进入交互模式
            print("=== 配置模式 ===")
            # 加载配置
            load_config()
            # 修改服务器地址
            new_address = input(f"ComfyUI服务器地址 (当前: {CONFIG['server_address']}): ").strip()
            if new_address:
                CONFIG["server_address"] = new_address
            # 修改输入文件夹
            new_input = input(f"输入图片文件夹 (当前: {CONFIG['input_folder']}): ").strip()
            if new_input:
                CONFIG["input_folder"] = new_input
            # 修改输出文件夹
            new_output = input(f"输出文件夹 (当前: {CONFIG['output_folder']}): ").strip()
            if new_output:
                CONFIG["output_folder"] = new_output
            # 保存配置
            save_config()
            print("配置已更新，进入交互模式")
            interactive_mode()
        elif sys.argv[1] == "--batch":
            # 批量处理模式
            if len(sys.argv) < 4:
                print("错误: 批量处理需要提供文件夹路径和提示词")
                print("用法: python comfyui_img2img_api.py --batch 文件夹 提示词")
                return
                
            batch_folder = sys.argv[2]
            batch_prompt = sys.argv[3]
            
            if not os.path.isdir(batch_folder):
                print(f"错误: {batch_folder} 不是有效的文件夹")
                return
                
            # 获取文件夹中的所有图像
            batch_images = []
            for file in os.listdir(batch_folder):
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    batch_images.append(os.path.join(batch_folder, file))
                    
            if not batch_images:
                print(f"错误: {batch_folder} 中没有找到任何图像")
                return
                
            print(f"找到 {len(batch_images)} 张图像，开始批量处理")
            batch_process(batch_images, batch_prompt)
        elif os.path.exists(sys.argv[1]):
            input_image = sys.argv[1]
            
            if len(sys.argv) > 2:
                positive_prompt = sys.argv[2]
                generate_image(input_image, positive_prompt)
            else:
                print("错误: 请提供正向提示词")
        else:
            print("ComfyUI 图生图 API 客户端")
            print("用法:")
            print("  python comfyui_img2img_api.py                   - 进入交互模式")
            print("  python comfyui_img2img_api.py --debug           - 以调试模式进入交互模式")
            print("  python comfyui_img2img_api.py 图片路径 提示词     - 处理单个图像")
            print("  python comfyui_img2img_api.py --batch 文件夹 提示词 - 批量处理文件夹中的所有图像")
            print("  python comfyui_img2img_api.py --config          - 修改配置后进入交互模式")
    else:
        # 进入交互模式
        interactive_mode()

if __name__ == "__main__":
    main() 