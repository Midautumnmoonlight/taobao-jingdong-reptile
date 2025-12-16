import threading
import logging
import time
import datetime
import ntplib
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class TaobaoSeckill:
    def __init__(self):
        self.driver = None
        self.main_thread = None
        self.confirm_thread = None
        self.running = False
        self.lock = threading.Lock()
        self.time_offset = 0.0

    def _init_browser(self):
        chrome_options = Options()
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--start-maximized")

        chrome_driver_path = r"C:\chromedriver.exe"

        try:
            service = Service(executable_path=chrome_driver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            logger.error(f"浏览器启动失败: {e}")
            raise e

        self.driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
        )
        logger.info("浏览器初始化完成")

    def _sync_time(self):
        logger.info("正在进行时间校准 (NTP)...")
        try:
            client = ntplib.NTPClient()
            response = client.request('ntp.aliyun.com', version=3)
            self.time_offset = response.tx_time - time.time()
            logger.info(f"时间校准成功！本地时间误差: {self.time_offset:.4f} 秒")
        except Exception as e:
            logger.warning(f"时间校准失败，将使用本地时间: {e}")
            self.time_offset = 0.0

    def _get_current_time(self):
        return time.time() + self.time_offset

    def _wait_for_trigger(self, target_time_str):
        now = datetime.datetime.fromtimestamp(self._get_current_time())
        try:
            if len(target_time_str) <= 8:
                target_dt = datetime.datetime.strptime(target_time_str, "%H:%M:%S")
                target_dt = now.replace(
                    hour=target_dt.hour,
                    minute=target_dt.minute,
                    second=target_dt.second,
                    microsecond=0
                )
                if target_dt < now:
                    target_dt += datetime.timedelta(days=1)
            else:
                target_dt = datetime.datetime.strptime(target_time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            logger.error("时间格式错误！请使用 '20:00:00' 或 '2023-01-01 20:00:00'")
            return False

        target_timestamp = target_dt.timestamp()
        logger.info(f"锁定抢购时间: {target_dt} (校准后)")
        logger.info("等待倒计时中...")

        while True:
            current_ts = self._get_current_time()
            diff = target_timestamp - current_ts

            if diff <= 0:
                logger.info(">>> 时间到！启动抢购！<<<")
                break

            if diff > 3:
                time.sleep(0.5)
                if int(diff) % 10 == 0:
                    print(f"\r还剩 {int(diff)} 秒...", end="")
            else:
                pass

        return True

    def _start_confirm_thread(self):
        def confirm_task():
            while self._is_running():
                try:
                    curr_url = self.driver.current_url
                    if "buy.taobao.com" not in curr_url and "confirm_order" not in curr_url:
                        time.sleep(0.5)
                        continue

                    submit_xpath = "//*[contains(text(), '提交订单')]"
                    try:
                        btn = WebDriverWait(self.driver, 0.5).until(
                            EC.presence_of_element_located((By.XPATH, submit_xpath))
                        )
                        logger.info("!!! [副线程] 发现提交按钮，执行点击 !!!")
                        self.driver.execute_script("arguments[0].click();", btn)
                        try:
                            btn.click()
                        except:
                            pass
                        time.sleep(0.2)
                    except TimeoutException:
                        pass
                except Exception:
                    pass

        with self.lock:
            if not self.confirm_thread or not self.confirm_thread.is_alive():
                self.confirm_thread = threading.Thread(target=confirm_task)
                self.confirm_thread.daemon = True
                self.confirm_thread.start()

    def _main_monitor_task(self):
        logger.info(">>> [主线程] 购物车监控已启动...")

        while self._is_running():
            try:
                if "buy.taobao.com" in self.driver.current_url:
                    logger.info(">>> 检测到页面跳转！主线程转入待机...")
                    self._start_confirm_thread()
                    time.sleep(2)
                    continue

                target_btn = None
                try:
                    target_btn = self.driver.find_element(By.CLASS_NAME, "btn--QDjHtErD")
                except:
                    pass
                if not target_btn:
                    try:
                        target_btn = self.driver.find_element(By.CSS_SELECTOR, "#J_Go .submit-btn")
                    except:
                        pass
                if not target_btn:
                    try:
                        target_btn = self.driver.find_element(
                            By.XPATH,
                            "//*[@id='J_Go']//div[contains(@class, 'btn') and contains(., '结算')]"
                        )
                    except:
                        pass

                if not target_btn:
                    time.sleep(0.2)
                    continue

                try:
                    if not target_btn.is_displayed():
                        continue
                    btn_class = target_btn.get_attribute("class") or ""
                    if "disabled" in btn_class or "submit-btn-disabled" in btn_class:
                        time.sleep(0.5)
                        continue
                except StaleElementReferenceException:
                    continue

                logger.info(">>> 锁定按钮，执行点击！")
                try:
                    self.driver.execute_script("arguments[0].click();", target_btn)
                    try:
                        target_btn.click()
                    except:
                        pass
                except Exception as e:
                    logger.error(f"点击报错: {e}")

                self._start_confirm_thread()
                logger.info(">>> 点击已发送，等待跳转 (2秒)...")
                time.sleep(2.0)

            except Exception as e:
                if "Connection pool" in str(e):
                    time.sleep(2)
                else:
                    logger.error(f"主线程异常: {e}")
                    time.sleep(1)

    def _is_running(self):
        with self.lock:
            return self.running

    def start(self):
        self._sync_time()
        self._init_browser()
        logger.info("正在打开淘宝购物车...")
        self.driver.get("https://cart.taobao.com/cart.htm")

        print("\n" + "=" * 60)
        print("【操作步骤】：")
        print("1. 扫码登录，并手动勾选商品。")
        print("2. 确保【结算】按钮变亮。")
        print("3. 回到这里输入抢购时间。")
        print("=" * 60 + "\n")

        while True:
            target_str = input(">>> 请输入抢购时间 (例如 19:59:59 或 20:00:00): ").strip()
            if target_str:
                break

        is_time = self._wait_for_trigger(target_str)

        if is_time:
            with self.lock:
                self.running = True

            self.main_thread = threading.Thread(target=self._main_monitor_task)
            self.main_thread.daemon = True
            self.main_thread.start()

            print("\n!!! 抢购程序运行中 (Ctrl+C 停止) !!!")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.stop()

    def stop(self):
        logger.info("正在停止程序...")
        with self.lock:
            self.running = False
        if self.driver:
            self.driver.quit()
        logger.info("程序已退出")


if __name__ == "__main__":
    app = TaobaoSeckill()
    app.start()
