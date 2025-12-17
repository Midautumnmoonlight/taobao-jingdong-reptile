import time
import pyautogui
import os
import random
import datetime
import ntplib  # 必须安装: pip install ntplib
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# ================= 配置区 =================
seckill_time_str = input("请输入抢购时间 (格式 2025-01-01 19:59:59): ").strip()
if len(seckill_time_str.split()) == 2 and "." not in seckill_time_str:
    seckill_time_str += ".000000"


# =========================================

def start_browser():
    print("正在启动浏览器...")
    chrome_options = Options()
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--start-maximized")

    # ⭐ 请确认路径
    chrome_driver_path = r"C:\chromedriver.exe"

    try:
        service = Service(executable_path=chrome_driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        print(f"浏览器启动失败: {e}")
        exit()


# 1. 启动
WebBrowser = start_browser()
WebBrowser.get("https://cart.jd.com/cart_index")

print("\n" + "=" * 60)
print("1. 扫码登录京东。")
print("2. 进入【购物车】，手动【勾选】你要抢购的商品。")
print("3. 【关键】：把鼠标移动到【去结算】按钮上，不要动！")
print("4. 另一只手按回车，脚本会'记住'这个位置。")
print("=" * 60)

# 2. 坐标校准
input(">>> 鼠标指在按钮上了吗？指好了就按回车... <<<")
target_x, target_y = pyautogui.position()
print(f"✅ 已锁定坐标: ({target_x}, {target_y})")
print(">>> 现在你可以把鼠标移开了，脚本已经记住了位置。")


# ============================================================
# ⭐ 新增：NTP 时间校准模块
# ============================================================
def sync_ntp_time():
    print("正在连接阿里云时间服务器 (NTP) 进行校准...")
    try:
        client = ntplib.NTPClient()
        # 尝试连接，超时时间 2 秒
        response = client.request('ntp.aliyun.com', version=3, timeout=2)

        # 计算偏移量：网络时间 - 本地时间
        # 如果 offset 是正数，说明网络比本地快（本地慢了）
        offset = response.tx_time - time.time()
        print(f"✅ 时间校准成功！本地时间误差: {offset:.4f} 秒")
        return offset
    except Exception as e:
        print(f"❌ 校准失败，将使用本地时间: {e}")
        return 0.0


# 执行校准
time_offset = sync_ntp_time()


# 辅助函数：获取当前精确的标准时间戳
def get_current_timestamp():
    return time.time() + time_offset


# ============================================================

# 3. 准备倒计时
try:
    target_dt = datetime.datetime.strptime(seckill_time_str, "%Y-%m-%d %H:%M:%S.%f")
    target_timestamp = target_dt.timestamp()
    print(f"目标时间: {target_dt} (已校准)")
except ValueError:
    print("时间格式错误")
    exit()

print(f"等待倒计时中... (机器会自动点击坐标 {target_x}, {target_y})")

# 4. 循环等待
while True:
    # ⭐ 这里使用校准后的时间
    current_ts = get_current_timestamp()
    diff = target_timestamp - current_ts

    # 提前 0.05 秒启动，抵消代码执行延迟
    if diff <= 0.05:
        print(f"\n⏰ 时间到！启动安全点击！")

        # 1. 瞬移鼠标到记录的坐标
        pyautogui.moveTo(target_x, target_y)

        # 2. 适度点击 (模拟人类极限手速，防止页面崩溃)
        # 循环 20 次，每次间隔 0.05~0.1秒
        for i in range(20):
            pyautogui.click()

            # 【关键修改】：加入随机等待，防止被京东判定为DDoS攻击
            sleep_time = random.uniform(0.05, 0.1)
            time.sleep(sleep_time)

            print(f"点击第 {i + 1} 次...", end="\r")

        print("\n>>> 点击结束！请检查是否跳转。")
        break

    else:
        if diff > 5:
            if int(diff) % 5 == 0:
                print(f"\r还剩 {int(diff)} 秒...", end="")
            time.sleep(0.5)
        elif diff > 0.5:
            time.sleep(0.1)
        else:
            pass  # 最后 0.5 秒全速空转