import urllib.request
import urllib.error
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import socket

def test_channel_speed(channel_name, url, timeout=5):
    """
    测试单个频道的播放速度
    """
    try:
        start_time = time.time()
        
        # 创建请求对象
        request = urllib.request.Request(
            url,
            method='HEAD',
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        
        # 发送HEAD请求测试响应速度
        response = urllib.request.urlopen(request, timeout=timeout)
        
        if response.status == 200:
            response_time = (time.time() - start_time) * 1000  # 转换为毫秒
            return channel_name, url, response_time, "成功"
        else:
            return channel_name, url, float('inf'), f"HTTP错误: {response.status}"
            
    except socket.timeout:
        return channel_name, url, float('inf'), "超时"
    except urllib.error.URLError as e:
        if isinstance(e.reason, socket.timeout):
            return channel_name, url, float('inf'), "超时"
        else:
            return channel_name, url, float('inf'), f"连接错误: {str(e.reason)}"
    except Exception as e:
        return channel_name, url, float('inf'), f"其他错误: {str(e)}"

def read_channel_list(filename):
    """
    读取直播源文件，解析频道名称和URL
    """
    channels = []
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith('#'):
                    # 支持多种分隔符：逗号、制表符、空格
                    if ',' in line:
                        parts = line.split(',', 1)
                    elif '\t' in line:
                        parts = line.split('\t', 1)
                    else:
                        parts = line.split(' ', 1)
                    
                    if len(parts) == 2:
                        channel_name = parts[0].strip()
                        url = parts[1].strip()
                        # 验证URL格式
                        if url.startswith(('http://', 'https://', 'rtmp://', 'rtsp://')):
                            channels.append((channel_name, url))
                        else:
                            print(f"警告: 跳过无效URL的频道 {channel_name}: {url}")
        
        return channels
    except FileNotFoundError:
        print(f"错误：文件 {filename} 未找到")
        return []
    except Exception as e:
        print(f"读取文件时出错: {str(e)}")
        return []

def filter_target_channels(channels, target_names):
    """
    过滤出目标频道
    """
    if not target_names:
        return channels
    
    filtered_channels = []
    for name, url in channels:
        for target in target_names:
            if target.lower() in name.lower():
                filtered_channels.append((name, url))
                break
    return filtered_channels

def main():
    input_file = "ptv_list.txt"
    output_file = "1.txt"
    
    # 目标频道关键词（可以根据需要修改）
    target_channels = ["cctv1", "cctv2", "cctv3", "河南卫视", "湖南卫视", "浙江卫视", "江苏卫视"]
    
    print("正在读取直播源文件...")
    all_channels = read_channel_list(input_file)
    
    if not all_channels:
        print("未找到有效的频道数据")
        return
    
    # 过滤出目标频道
    channels = filter_target_channels(all_channels, target_channels)
    
    if not channels:
        print("未找到目标频道，将测试所有频道")
        channels = all_channels
    else:
        print(f"找到 {len(channels)} 个目标频道")
    
    print("开始测试播放速度...")
    
    # 使用多线程测试所有频道的速度
    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_channel = {
            executor.submit(test_channel_speed, name, url): (name, url) 
            for name, url in channels
        }
        
        completed = 0
        for future in as_completed(future_to_channel):
            result = future.result()
            results.append(result)
            completed += 1
            channel_name, url, response_time, status = result
            if status == "成功":
                print(f"进度: {completed}/{len(channels)} - {channel_name}: {response_time:.2f}ms")
            else:
                print(f"进度: {completed}/{len(channels)} - {channel_name}: {status}")
    
    # 过滤出成功的测试并按响应时间排序（从小到大）
    successful_results = [r for r in results if r[3] == "成功"]
    successful_results.sort(key=lambda x: x[2])
    
    # 写入结果到文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# 频道播放速度测试结果（响应时间从小到大排序）\n")
        f.write("# 格式：频道名称,URL,响应时间(ms)\n\n")
        
        for channel_name, url, response_time, status in successful_results:
            f.write(f"{channel_name},{url},{response_time:.2f}ms\n")
        
        # 添加失败的信息
        failed_results = [r for r in results if r[3] != "成功"]
        if failed_results:
            f.write(f"\n# 以下 {len(failed_results)} 个频道测试失败:\n")
            for channel_name, url, response_time, status in failed_results:
                f.write(f"# {channel_name},{url},{status}\n")
    
    print(f"\n测试完成！")
    print(f"成功测试: {len(successful_results)} 个频道")
    print(f"测试失败: {len(failed_results)} 个频道")
    print(f"结果已保存到: {output_file}")
    
    # 显示结果
    if successful_results:
        print(f"\n播放速度由快到慢排序:")
        print("-" * 60)
        for i, (channel_name, url, response_time, status) in enumerate(successful_results, 1):
            print(f"{i:2d}. {channel_name:<15} : {response_time:>6.2f}ms")
    
    if failed_results:
        print(f"\n测试失败的频道:")
        print("-" * 60)
        for channel_name, url, response_time, status in failed_results:
            print(f"{channel_name}: {status}")

if __name__ == "__main__":
    main()
