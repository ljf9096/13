import urllib.request
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

def test_channel_speed(channel_data):
    """测试单个频道速度"""
    name, url = channel_data
    start_time = time.time()
    
    try:
        # 只测试HTTP协议
        if url.startswith('http'):
            urllib.request.urlopen(url, timeout=3)
            speed = (time.time() - start_time) * 1000
            return speed, f"{name},{url}"
    except:
        pass
    return None, None

def main():
    # 你的频道列表 - 替换成实际的频道数据
    channels = [
        ("CCTV1", "http://example.com/cctv1"),
        ("CCTV5", "http://example.com/cctv5"),
        ("湖南卫视", "http://example.com/hunan"),
        # ... 更多频道
    ]
    
    print("测试频道速度...")
    results = []
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(test_channel_speed, channel) for channel in channels]
        
        for future in as_completed(futures):
            speed, channel_info = future.result()
            if speed:
                results.append((speed, channel_info))
                print(f"✓ {channel_info.split(',')[0]} - {speed:.0f}ms")
    
    # 取最快的3个
    if results:
        results.sort()
        fastest = results[:3]
        
        with open('1.txt', 'w', encoding='utf-8') as f:
            for speed, channel in fastest:
                f.write(channel + '\n')
                print(f"最快: {channel.split(',')[0]} - {speed:.0f}ms")
    else:
        print("没有找到可用的频道")

if __name__ == "__main__":
    main()
