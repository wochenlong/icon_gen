import os
import base64
import requests
import json
import time
from datetime import datetime
import sys

# 配置参数
CONFIG = {
    "api_key": "e8743103d690270832dbb693bf434dfc09145fbd58d4d07c404f0c707afa6f72",  # GoAPI密钥
    "output_folder": r"E:\img",  # 输出文件夹路径
    "reference_folder": r"E:\M72",  # 参考图片文件夹
    "size": "1024x1024",  # 图片尺寸
    "debug": True,  # 调试模式
    "print_response": True  # 是否打印API响应
}

# API端点
TEXT_TO_IMAGE_URL = "https://api.goapi.ai/v1/images/generations"
CHAT_COMPLETION_URL = "https://api.goapi.ai/v1/chat/completions"
IMAGE_MODEL = "gpt-image-1"
CHAT_MODEL = "gpt-4o"  # 使用GPT-4o模型进行对话

class ArtifactIconGenerator:
    def __init__(self, config=None):
        """初始化生成器"""
        self.config = config or CONFIG
        self.context = []  # 保存对话上下文
        self.print_debug(f"初始化完成，对话模型: {CHAT_MODEL}，图像模型: {IMAGE_MODEL}")
        self.print_debug(f"参考图片文件夹: {self.config['reference_folder']}")
        self.print_debug(f"输出文件夹: {self.config['output_folder']}")
        
    def print_debug(self, message):
        """打印调试信息"""
        if self.config.get("debug", False):
            print(f"[调试] {message}")

    def add_to_context(self, role, content):
        """添加消息到上下文"""
        self.context.append({"role": role, "content": content})
        self.print_debug(f"添加到上下文: {role} - {content[:30]}...")
        
    def get_reference_images(self):
        """获取参考图片列表"""
        ref_folder = self.config['reference_folder']
        if not os.path.exists(ref_folder):
            print(f"错误: 参考图片文件夹不存在 - {ref_folder}")
            return []
            
        image_files = []
        for file in os.listdir(ref_folder):
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                image_files.append(os.path.join(ref_folder, file))
                
        self.print_debug(f"找到 {len(image_files)} 个参考图片")
        return image_files
        
    def encode_image(self, image_path):
        """将图片编码为base64格式"""
        if not os.path.exists(image_path):
            print(f"错误: 图片不存在 - {image_path}")
            return None
            
        try:
            with open(image_path, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode('utf-8')
        except Exception as e:
            print(f"图片编码失败: {e}")
            return None
            
    def upload_reference_images(self):
        """上传参考图片并初始化对话"""
        # 系统提示词，定义AI角色
        system_prompt = """你是一个专门为网页端批量生成游戏异宝图标的智能体。
用户会提供异宝信息（异宝名称、品质、所属场景、异宝描述），可能附带参考画风图片。
你的任务是：学习参考图的图标风格，等待用户提供"具体的图标文案或创意方向"。"""

        self.add_to_context("system", system_prompt)
        
        # 获取参考图片
        ref_images = self.get_reference_images()
        if not ref_images:
            print("没有找到参考图片，将直接进行文本对话")
            return True
            
        # 构建带有图片的消息
        message_text = "我正在上传一些参考图片，请学习这些图片的风格，以便生成类似风格的异宝图标。"
        self.add_to_context("user", message_text)
        
        # 上传图片，将每个图片作为单独的用户消息发送
        for img_path in ref_images:
            try:
                img_data = self.encode_image(img_path)
                if not img_data:
                    continue
                    
                # 添加图片消息到上下文
                img_message = {
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": f"这是一张参考图片，文件名: {os.path.basename(img_path)}"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_data}"}}
                    ]
                }
                
                self.context.append(img_message)
                self.print_debug(f"已添加参考图片: {os.path.basename(img_path)}")
                
            except Exception as e:
                self.print_debug(f"上传图片失败: {e}")
                
        # 添加说明
        self.add_to_context("user", "请分析这些参考图片的风格特点，我稍后会提供异宝信息和创意方向。")
        
        # 获取API响应
        response = self.get_api_response()
        if response:
            self.print_debug("收到API对参考图片的分析")
            self.add_to_context("assistant", response)
            return True
        return False
            
    def get_api_response(self):
        """向API发送请求获取响应"""
        headers = {
            "Content-Type": "application/json", 
            "Authorization": f"Bearer {self.config['api_key']}"
        }
        
        data = {
            "model": CHAT_MODEL,  # 使用GPT-4o模型进行对话
            "messages": self.context
        }
        
        try:
            self.print_debug("发送API请求...")
            response = requests.post(
                CHAT_COMPLETION_URL, 
                headers=headers, 
                json=data
            )
            
            if response.status_code != 200:
                print(f"错误: API返回{response.status_code} - {response.text}")
                return None
                
            result = response.json()
            
            # 打印API响应
            if self.config.get("print_response", False):
                self.print_debug("接收到API响应")
                try:
                    self.print_debug(f"响应结构: {list(result.keys())}")
                except Exception:
                    pass
                    
            # 从结果中提取文本响应
            if "choices" in result and len(result["choices"]) > 0:
                message = result["choices"][0].get("message", {})
                content = message.get("content", "")
                return content
                
            print("错误: 无法从API响应中提取内容")
            return None
            
        except Exception as e:
            print(f"API请求失败: {e}")
            import traceback
            print(traceback.format_exc())
            return None
            
    def generate_icon(self, artifact_info, creative_direction):
        """生成异宝图标"""
        # 添加异宝信息和创意方向到上下文
        prompt = f"""
请为以下游戏异宝生成图标:

异宝名称: {artifact_info.get('name', '未知')}
品质: {artifact_info.get('quality', '未知')}
所属场景: {artifact_info.get('scene', '未知')}
异宝描述: {artifact_info.get('description', '未知')}

创意方向: {creative_direction}

请生成一个与参考图片风格一致的异宝图标。
"""
        self.add_to_context("user", prompt)
        
        # 获取API响应
        response = self.get_api_response()
        if response:
            print("\n--- API响应 ---")
            print(response)
            print("--- 响应结束 ---\n")
            self.add_to_context("assistant", response)
            
            # 现在使用文生图功能生成图标
            return self.text_to_image(creative_direction, artifact_info)
        return False
            
    def text_to_image(self, creative_direction, artifact_info):
        """使用文生图功能生成图标"""
        # 构建提示词
        prompt = f"""游戏异宝图标: {artifact_info.get('name', '未知异宝')}
品质: {artifact_info.get('quality', '普通')}
风格: 与参考图片一致的游戏图标风格，简洁明了，具有游戏感。
内容: {creative_direction}"""

        headers = {
            "Content-Type": "application/json", 
            "Authorization": f"Bearer {self.config['api_key']}"
        }
        
        data = {
            "model": IMAGE_MODEL, 
            "prompt": prompt, 
            "n": 1, 
            "size": self.config["size"]
        }
        
        print(f"生成图标中，提示词: {prompt}")
        
        try:
            # 发送请求
            response = requests.post(TEXT_TO_IMAGE_URL, headers=headers, json=data)
            
            if response.status_code != 200:
                print(f"错误: API返回{response.status_code} - {response.text}")
                return False
                
            # 解析响应
            result = response.json()
            
            # 打印响应
            if self.config.get("print_response", False):
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
                    return self.save_base64_image(result, artifact_info["name"])
                    
                # 处理图像URL
                elif "url" in data_item:
                    url = data_item["url"]
                    self.print_debug(f"API返回图像URL: {url[:50]}...")
                    return self.download_url(url, artifact_info["name"])
                
                print("错误: API响应中的图像数据格式不符合预期")
                return False
                
            print("错误: 响应中没有图像数据")
            return False
            
        except Exception as e:
            print(f"生成图像时出错: {e}")
            import traceback
            print(traceback.format_exc())
            return False
            
    def save_base64_image(self, result, name):
        """保存base64编码的图片"""
        try:
            os.makedirs(self.config["output_folder"], exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            b64_image = result["data"][0]["b64_json"]
            img_data = base64.b64decode(b64_image)
            
            filename = f"{name}_{timestamp}.png"
            filepath = os.path.join(self.config["output_folder"], filename)
            
            with open(filepath, "wb") as img_file:
                img_file.write(img_data)
                
            print(f"图标已保存: {filepath}")
            
            # 添加图像生成结果到上下文
            self.add_to_context("user", f"生成的图标已保存为 {filename}，请评价一下这个图标是否符合要求？")
            response = self.get_api_response()
            if response:
                print("\n--- API评价 ---")
                print(response)
                print("--- 评价结束 ---\n")
                self.add_to_context("assistant", response)
                
            return True
            
        except Exception as e:
            print(f"保存图片失败: {e}")
            return False
            
    def download_url(self, url, name):
        """下载URL并保存为图片"""
        try:
            if not url or not url.startswith(('http://', 'https://')):
                print(f"错误: 无效的URL格式 - {url}")
                return False
                
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            os.makedirs(self.config["output_folder"], exist_ok=True)
            
            print(f"下载图片: {url}")
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            filename = f"{name}_{timestamp}.png"
            filepath = os.path.join(self.config["output_folder"], filename)
            
            with open(filepath, "wb") as img_file:
                for chunk in response.iter_content(chunk_size=8192):
                    img_file.write(chunk)
                    
            print(f"图标已保存: {filepath}")
            
            # 添加图像生成结果到上下文
            self.add_to_context("user", f"生成的图标已保存为 {filename}，请评价一下这个图标是否符合要求？")
            response = self.get_api_response()
            if response:
                print("\n--- API评价 ---")
                print(response)
                print("--- 评价结束 ---\n")
                self.add_to_context("assistant", response)
                
            return True
            
        except Exception as e:
            print(f"下载图片失败: {e}")
            return False
            
    def interactive_session(self):
        """开始交互式会话"""
        print("\n=== 游戏异宝图标生成器 ===")
        print("正在加载参考图片，请稍候...")
        
        # 上传参考图片
        if not self.upload_reference_images():
            print("初始化失败，无法上传参考图片")
            return
            
        print("\n生成器> 我已经学习了参考图片的风格，现在可以为您生成游戏异宝图标")
        print("生成器> 请描述您想要的异宝，包括名称、品质、外观特点等")
        print("生成器> 例如：'寒冰戒指，传说品质，蓝色宝石镶嵌，有冰霜效果'")
        print("生成器> 输入'退出'结束会话")
        print("-" * 50)
            
        while True:
            # 显示提示符
            print("\n您> ", end="")
            
            # 获取用户输入
            input_text = input().strip()
            if input_text.lower() in ['exit', 'quit', '退出']:
                print("\n生成器> 会话已结束，感谢使用！")
                break
                
            # 自动生成文件名
            file_name = f"异宝图标_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # 直接使用输入文本生成图像
            success = self.text_to_image_direct(input_text, file_name)
            
            if not success:
                print("\n生成器> 请尝试修改您的描述后重试")
            
    def text_to_image_direct(self, prompt_text, file_name):
        """直接使用文本生成图像"""
        # 构建提示词
        prompt = f"""游戏异宝图标，风格类似于参考图片: {prompt_text}"""

        headers = {
            "Content-Type": "application/json", 
            "Authorization": f"Bearer {self.config['api_key']}"
        }
        
        data = {
            "model": IMAGE_MODEL, 
            "prompt": prompt, 
            "n": 1, 
            "size": self.config["size"]
        }
        
        # 开始计时
        start_time = time.time()
        
        # 不再显示完整提示词，只显示简单提示
        print(f"\n生成器> 正在生成中...")
        
        try:
            # 发送请求
            response = requests.post(TEXT_TO_IMAGE_URL, headers=headers, json=data)
            
            if response.status_code != 200:
                # 只显示简单错误信息
                print(f"\n生成器> 生成图标失败，API返回错误代码：{response.status_code}")
                self.print_debug(f"错误详情: {response.text}")
                return False
                
            # 解析响应
            result = response.json()
            
            # 打印API响应（仅在调试模式）
            if self.config.get("print_response", False):
                self.print_debug("API返回响应")
                try:
                    self.print_debug(f"响应结构: {list(result.keys())}")
                except Exception:
                    pass
                    
            # 保存图片
            if "data" in result and len(result["data"]) > 0:
                data_item = result["data"][0]
                
                saved = False
                # 处理base64编码的图像
                if "b64_json" in data_item:
                    saved = self.save_base64_image_direct(result, file_name)
                    
                # 处理图像URL
                elif "url" in data_item:
                    url = data_item["url"]
                    self.print_debug(f"API返回图像URL: {url[:50]}...")
                    saved = self.download_url_direct(url, file_name)
                
                # 计算耗时
                end_time = time.time()
                execution_time = end_time - start_time
                
                if saved:
                    print(f"\n生成器> 图标已成功生成！耗时: {execution_time:.2f}秒")
                    return True
                else:
                    print(f"\n生成器> 图标保存失败。")
                    return False
                    
            print("\n生成器> 生成图标失败，API返回数据格式不符合预期")
            self.print_debug(f"响应内容: {result}")
            return False
            
        except Exception as e:
            print(f"\n生成器> 生成图标时发生错误")
            self.print_debug(f"错误详情: {e}")
            import traceback
            self.print_debug(traceback.format_exc())
            return False
            
    def save_base64_image_direct(self, result, name):
        """保存base64编码的图片（直接方式）"""
        try:
            os.makedirs(self.config["output_folder"], exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            b64_image = result["data"][0]["b64_json"]
            img_data = base64.b64decode(b64_image)
            
            filename = f"{name}_{timestamp}.png"
            filepath = os.path.join(self.config["output_folder"], filename)
            
            with open(filepath, "wb") as img_file:
                img_file.write(img_data)
                
            print(f"\n生成器> 图标已保存: {filepath}")
            return True
            
        except Exception as e:
            self.print_debug(f"保存图片失败: {e}")
            return False
            
    def download_url_direct(self, url, name):
        """下载URL并保存为图片（直接方式）"""
        try:
            if not url or not url.startswith(('http://', 'https://')):
                self.print_debug(f"错误: 无效的URL格式 - {url}")
                return False
                
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            os.makedirs(self.config["output_folder"], exist_ok=True)
            
            self.print_debug(f"下载图片: {url}")
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            filename = f"{name}_{timestamp}.png"
            filepath = os.path.join(self.config["output_folder"], filename)
            
            with open(filepath, "wb") as img_file:
                for chunk in response.iter_content(chunk_size=8192):
                    img_file.write(chunk)
                    
            print(f"\n生成器> 图标已保存: {filepath}")
            return True
            
        except Exception as e:
            self.print_debug(f"下载图片失败: {e}")
            return False

def main():
    """主函数"""
    start_time = time.time()  # 记录开始时间
    
    # 配置调试模式
    if len(sys.argv) > 1 and sys.argv[1] == "--debug":
        print("调试模式已启用")
    else:
        # 非调试模式下关闭调试输出
        CONFIG["debug"] = False
        CONFIG["print_response"] = False
    
    generator = ArtifactIconGenerator()
    generator.interactive_session()
    
    # 计算并输出总耗时
    end_time = time.time()
    execution_time = end_time - start_time
    print(f"\n总耗时: {execution_time:.2f}秒")

if __name__ == "__main__":
    main() 