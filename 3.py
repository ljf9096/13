import urllib.request
from urllib.parse import urlparse
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import socket
import time
from datetime import datetime


# 读取文本方法
def read_txt_to_array(file_name):
    try:
        with open(file_name, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            lines = [line.strip() for line in lines]
            return lines
    except FileNotFoundError:
        print(f"File '{file_name}' not found.")
        return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []


# 准备支持 m3u 格式
def get_url_file_extension(url):
    # 解析 URL
    parsed_url = urlparse(url)
    # 获取路径部分
    path = parsed_url.path
    # 提取文件扩展名
    extension = os.path.splitext(path)[1]
    return extension


def convert_m3u_to_txt(m3u_content):
    # 分行处理
    lines = m3u_content.split('\n')
    txt_lines = []
    # 临时变量用于存储频道名称
    channel_name = ""
    for line in lines:
        # 过滤掉 #EXTM3U 开头的行
        if line.startswith("#EXTM3U"):
            continue
        # 处理 #EXTINF 开头的行
        if line.startswith("#EXTINF"):
            # 获取频道名称（假设频道名称在引号后）
            channel_name = line.split(',')[-1].strip()
        # 处理 URL 行
        elif line.startswith("http") or line.startswith("rtmp") or line.startswith("p3p"):
            txt_lines.append(f"{channel_name},{line.strip()}")
    # 将结果合并成一个字符串，以换行符分隔
    return '\n'.join(txt_lines)


# 处理带 $ 的 URL，把 $ 之后的内容都去掉（包括 $ 也去掉）
def clean_url(url):
    last_dollar_index = url.rfind('$')  # 安全起见找最后一个 $ 处理
    if last_dollar_index != -1:
        return url[:last_dollar_index]
    return url


# 处理所有 URL
def process_url(url, timeout=10):
    try:
        # 打开 URL 并读取内容
        start_time = time.time()
        with urllib.request.urlopen(url, timeout=timeout) as response:
            # 以二进制方式读取数据
            data = response.read()
            # 将二进制数据解码为字符串
            text = data.decode('utf-8')

            # 处理 m3u 和 m3u8，提取 channel_name 和 channel_address
            if get_url_file_extension(url) == ".m3u" or get_url_file_extension(url) == ".m3u8":
                text = convert_m3u_to_txt(text)

            # 逐行处理内容
            lines = text.split('\n')
            channel_count = 0  # 初始化频道计数器
            for line in lines:
                if "#genre#" not in line and "," in line and "://" in line:
                    # 拆分成频道名和 URL 部分
                    parts = line.split(',')
                    channel_name = parts[0]  # 获取频道名称
                    channel_address = parts[1]  # 获取频道地址
                    # 处理带 # 号源 = 予加速源
                    if "#" not in channel_address:
                        yield channel_name, clean_url(channel_address)  # 如果没有井号，则照常按照每行规则进行分发
                    else:
                        # 如果有 "#" 号，则根据 "#" 号分隔
                        url_list = channel_address.split('#')
                        for channel_url in url_list:
                            yield channel_name, clean_url(channel_url)
                    channel_count += 1  # 每处理一个频道，计数器加一

            print(f"正在读取URL: {url}")
            print(f"获取到频道列表: {channel_count} 条")  # 打印频道数量

    except Exception as e:
        print(f"处理 URL 时发生错误：{e}")
        return []


# 函数用于过滤和替换频道名称
def filter_and_modify_sources(corrections):
    filtered_corrections = []
    name_dict = ['购物', '理财', '导视', '指南', '测试', '芒果', 'CGTN']
    url_dict = []  # '2409:'留空不过滤ipv6频道

    for name, url in corrections:
        if any(word.lower() in name.lower() for word in name_dict) or any(word in url for word in url_dict):
            print("过滤频道:" + name + "," + url)
        else:
            # 进行频道名称的替换操作
            name = name.replace("FHD", "").replace("HD", "").replace("hd", "").replace("频道", "").replace("高清", "") \
                .replace("超清", "").replace("20M", "").replace("-", "").replace("4k", "").replace("4K", "") \
                .replace("4kR", "")
            filtered_corrections.append((name, url))
    return filtered_corrections


def check_url(url, channel_name, timeout=6):
    start_time = time.time()
    elapsed_time = None
    success = False

    try:
        if url.startswith("http"):
            response = urllib.request.urlopen(url, timeout=timeout)
            if response.status == 200:
                success = True
        elif url.startswith("p3p"):
            success = check_p3p_url(url, timeout)
        elif url.startswith("rtmp"):
            success = check_rtmp_url(url, timeout)
        elif url.startswith("rtp"):
            success = check_rtp_url(url, timeout)
        else:
            return None, False

        elapsed_time = (time.time() - start_time) * 1000  # 转换为毫秒
    except Exception as e:
        print(f"检测错误 {channel_name}: {url}: {e}")

    return elapsed_time, success


# 以下是检测不同协议URL的函数
def check_rtmp_url(url, timeout):
    try:
        result = subprocess.run(['ffprobe', '-v', 'error', '-rtmp_transport', 'tcp', '-i', url],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=timeout)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"检测超时 {url}")
    except Exception as e:
        print(f"检测错误 {url}: {e}")
    return False


def check_rtp_url(url, timeout):
    try:
        parsed_url = urlparse(url)
        host = parsed_url.hostname
        port = parsed_url.port

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(timeout)
            s.connect((host, port))
            s.sendto(b'', (host, port))
            s.recv(1)
        return True
    except (socket.timeout, socket.error):
        return False


def check_p3p_url(url, timeout):
    try:
        parsed_url = urlparse(url)
        host = parsed_url.hostname
        port = parsed_url.port
        path = parsed_url.path

        with socket.create_connection((host, port), timeout=timeout) as s:
            request = f"GET {path} P3P/1.0\r\nHost: {host}\r\n\r\n"
            s.sendall(request.encode())
            response = s.recv(1024)
            return b"P3P" in response
    except Exception as e:
        print(f"检测错误 {url}: {e}")
    return False


# 去掉文本'$'后面的内容
def process_line(line):
    if "://" not in line:
        return None, None
    line = line.split('$')[0]
    parts = line.split(',')
    if len(parts) == 2:
        name, url = parts
        elapsed_time, is_valid = check_url(url.strip(), name)
        if is_valid:
            return elapsed_time, f"{name},{url}"
    return None, None


def process_urls_multithreaded(lines, max_workers=200):
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_line, line): line for line in lines}
        for future in as_completed(futures):
            elapsed_time, result = future.result()
            if elapsed_time is not None:
                results.append((elapsed_time, result))

    # 按照检测后的毫秒数升序排列
    results.sort()
    return results


# 主函数 - 修改为按频道模板生成各频道速度最快前3个
def main():
    # 读取 URLs
    urls_file_path = os.path.join(os.getcwd(), 'config/urls.txt')
    urls = read_txt_to_array(urls_file_path)

    # 处理过滤和替换频道名称
    all_channels = []
    for url in urls:
        for channel_name, channel_url in process_url(url):
            all_channels.append((channel_name, channel_url))

    # 过滤和修改频道名称
    filtered_channels = filter_and_modify_sources(all_channels)

    # 去重
    unique_channels = list(set(filtered_channels))

    unique_channels_str = [f"{name},{url}" for name, url in unique_channels]

    print(f"总共采集到 {len(unique_channels_str)} 个频道，开始检测速度...")

    # 使用多线程检测URL
    results = process_urls_multithreaded(unique_channels_str)

    # 读取频道模板
    template_directory = os.path.join(os.getcwd(), '频道模板')
    if not os.path.exists(template_directory):
        os.makedirs(template_directory)
        print(f"目录 '{template_directory}' 已创建。")
        return

    template_files = [f for f in os.listdir(template_directory) if f.endswith('.txt')]
    
    if not template_files:
        print("频道模板目录中没有找到模板文件")
        return

    # 收集所有模板频道名称
    all_template_channels = []
    for template_file in template_files:
        template_channels = read_txt_to_array(os.path.join(template_directory, template_file))
        all_template_channels.extend(template_channels)
    
    # 去重模板频道
    all_template_channels = list(set(all_template_channels))
    print(f"从模板中读取到 {len(all_template_channels)} 个目标频道")

    # 按频道名称分组，每个频道取速度最快的前3个
    channel_groups = {}
    for elapsed_time, channel_info in results:
        channel_name, channel_url = channel_info.split(',', 1)
        
        # 检查这个频道是否在模板中
        if channel_name in all_template_channels:
            if channel_name not in channel_groups:
                channel_groups[channel_name] = []
            channel_groups[channel_name].append((elapsed_time, channel_url))
    
    # 对每个频道组取前3个最快的
    fastest_channels_by_group = {}
    for channel_name, channels in channel_groups.items():
        # 按响应时间排序
        channels.sort(key=lambda x: x[0])
        # 取前3个
        fastest_channels_by_group[channel_name] = channels[:3]

    # 写入4.txt文件
    output_file = "4.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        # 写入标题
        f.write("# 各频道速度最快前3个直播源\n")
        f.write(f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        total_count = 0
        # 按频道名称排序输出
        for channel_name in sorted(fastest_channels_by_group.keys()):
            channels = fastest_channels_by_group[channel_name]
            f.write(f"# {channel_name} 频道 (共{len(channels)}个源)\n")
            
            for i, (elapsed_time, channel_url) in enumerate(channels, 1):
                f.write(f"{channel_name}源{i},{channel_url}\n")
                total_count += 1
            
            f.write("\n")
    
    # 打印统计信息
    print(f"\n{'='*60}")
    print(f"各频道速度最快前3个直播源已保存到: {output_file}")
    print(f"总共处理了 {len(fastest_channels_by_group)} 个频道")
    print(f"总共生成了 {total_count} 个直播源")
    print(f"{'='*60}")
    
    # 打印每个频道的详情
    for channel_name in sorted(fastest_channels_by_group.keys()):
        channels = fastest_channels_by_group[channel_name]
        print(f"\n{channel_name}:")
        for i, (elapsed_time, channel_url) in enumerate(channels, 1):
            print(f"  源{i}: {elapsed_time:.0f}ms - {channel_url}")


if __name__ == "__main__":
    main()
