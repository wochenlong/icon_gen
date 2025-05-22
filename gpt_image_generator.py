import os
import base64
import requests
import json
import time
from datetime import datetime

# 配置参数
CONFIG = {
    "prompt": "将这只猫变成一只吉普力风格的红色福猪，背景是红色灯笼和福字，喜庆的节日氛围",  # 生成图片的提示词
    "api_key": "e8743103d690270832dbb693bf434dfc09145fbd58d4d07c404f0c707afa6f72",  # GoAPI密钥
    "output_folder": r"E:\img",  # 输出文件夹路径
    "size": "1024x1024",  # 图片尺寸
    "use_image": True,  # 是否使用图像变体模式
    "default_image": r"E:\img\test_cat.jpg",  # 默认测试图片路径
    "debug": True,  # 调试模式
    "print_response": True  # 是否打印API响应
}

# API端点
TEXT_TO_IMAGE_URL = "https://api.goapi.ai/v1/images/generations"
IMAGE_TO_IMAGE_URL = "https://api.goapi.ai/v1/images/variations"
MODEL = "gpt-image-1"

def print_debug(message):
    """打印调试信息"""
    if CONFIG.get("debug", False):
        print(f"[DEBUG] {message}")

def generate_image_from_text():
    """纯文本到图像生成"""
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {CONFIG['api_key']}"}
    data = {"model": MODEL, "prompt": CONFIG["prompt"], "n": 1, "size": CONFIG["size"]}
    
    print(f"使用提示词生成图像: {CONFIG['prompt']}")
    
    try:
        # 发送请求
        response = requests.post(TEXT_TO_IMAGE_URL, headers=headers, json=data)
        if response.status_code != 200:
            print(f"错误: API返回{response.status_code} - {response.text}")
            return False
        
        # 解析响应
        result = response.json()
        print_debug(f"API响应结构: {list(result.keys())}")
        
        # 打印响应
        if CONFIG.get("print_response", False):
            print("\n--- API响应 ---")
            try:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            except Exception as e:
                print(f"无法格式化JSON: {e}")
            print("--- 响应结束 ---\n")
        
        # 保存图片
        if "data" in result and len(result["data"]) > 0:
            data_item = result["data"][0]
            
            # 处理base64编码的图像
            if "b64_json" in data_item:
                return save_base64_image(result)
                
            # 处理图像URL
            elif "url" in data_item:
                url = data_item["url"]
                print_debug(f"API返回图像URL: {url[:50]}...")
                return download_url(url)
            
            print("错误: API响应中的图像数据格式不符合预期")
            return False
        
        print("错误: 响应中没有图像数据")
        return False
    
    except Exception as e:
        print(f"生成图像时出错: {e}")
        return False

def generate_image_with_image(image_path):
    """图像到图像生成"""
    if not os.path.exists(image_path):
        print(f"错误: 图片不存在 - {image_path}")
        return False
    
    try:
        # 读取并编码图片
        with open(image_path, "rb") as img_file:
            img_data = base64.b64encode(img_file.read()).decode('utf-8')
        
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {CONFIG['api_key']}"}
        
        # 使用文本到图像的API端点，而不是图像变体端点
        data = {
            "model": MODEL,
            "prompt": CONFIG["prompt"],
            "n": 1,
            "size": CONFIG["size"],
            # 添加图像参考
            "reference_image": img_data
        }
        
        print(f"使用图片和提示词生成图像: {CONFIG['prompt']}")
        
        # 发送请求
        response = requests.post(TEXT_TO_IMAGE_URL, headers=headers, json=data)
        print(f"API响应状态码: {response.status_code}")
        
        if response.status_code != 200:
            print(f"错误: API返回{response.status_code} - {response.text}")
            return False
        
        # 解析响应
        result = response.json()
        print(f"API响应结构: {list(result.keys())}")
        
        # 打印完整响应
        if CONFIG.get("print_response", False):
            print("\n--- API响应 ---")
            try:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            except Exception as e:
                print(f"无法格式化JSON: {e}")
                print("原始响应内容:")
                print(response.text[:2000])  # 打印前2000个字符
            print("--- 响应结束 ---\n")
        
        # 处理响应
        if "data" in result and len(result["data"]) > 0:
            data_item = result["data"][0]
            
            # 处理base64编码的图像
            if "b64_json" in data_item:
                return save_base64_image(result)
                
            # 处理图像URL
            elif "url" in data_item:
                url = data_item["url"]
                print_debug(f"API返回图像URL: {url[:50]}...")
                return download_url(url)
            
            print("错误: API响应中的图像数据格式不符合预期")
            return False
        
        print("错误: 响应中没有图像数据")
        return False
    
    except Exception as e:
        print(f"生成图像时出错: {e}")
        import traceback
        print(traceback.format_exc())
        return False

def save_base64_image(result):
    """保存base64编码的图片"""
    try:
        os.makedirs(CONFIG["output_folder"], exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        b64_image = result["data"][0]["b64_json"]
        img_data = base64.b64decode(b64_image)
        
        filepath = os.path.join(CONFIG["output_folder"], f"{timestamp}_goapi.png")
        with open(filepath, "wb") as img_file:
            img_file.write(img_data)
        
        print(f"图片已保存: {filepath}")
        return True
    
    except Exception as e:
        print(f"保存图片失败: {e}")
        return False

def download_url(url, timestamp=None):
    """下载URL并保存为图片"""
    try:
        if not url or not url.startswith(('http://', 'https://')):
            print(f"错误: 无效的URL格式 - {url}")
            return False
            
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        os.makedirs(CONFIG["output_folder"], exist_ok=True)
        
        print(f"下载图片: {url}")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        filepath = os.path.join(CONFIG["output_folder"], f"{timestamp}_goapi.png")
        with open(filepath, "wb") as img_file:
            for chunk in response.iter_content(chunk_size=8192):
                img_file.write(chunk)
        
        print(f"图片已保存: {filepath}")
        return True
    
    except Exception as e:
        print(f"下载图片失败: {e}")
        return False

def main():
    print(f"API模型: {MODEL}")
    print(f"输出文件夹: {CONFIG['output_folder']}")
    
    start_time = time.time()  # 记录开始时间
    
    os.makedirs(CONFIG["output_folder"], exist_ok=True)
    
    if CONFIG["use_image"]:
        # 获取默认图片路径
        default_path = CONFIG.get("default_image", "")
        
        # 检查默认图片是否存在
        if default_path and os.path.exists(default_path):
            image_path = default_path
            print(f"使用默认图片: {image_path}")
        else:
            print("默认图片不存在，请输入图片路径:")
            image_path = input().strip()
            
        # 再次检查输入路径
        if not image_path or not os.path.exists(image_path):
            print(f"错误: 图片路径无效 - {image_path}")
            return
            
        print(f"使用图像变体模式，输入图片: {image_path}")
        success = generate_image_with_image(image_path)
    else:
        print("使用纯文本生成模式")
        success = generate_image_from_text()
    
    # 计算并输出总耗时
    end_time = time.time()
    execution_time = end_time - start_time
    
    print("图像生成成功！" if success else "图像生成失败。")
    print(f"总耗时: {execution_time:.2f}秒")

if __name__ == "__main__":
    main() 