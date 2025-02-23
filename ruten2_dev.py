import csv
from multiprocessing import Pool
import random
import time
import urllib.parse
from datetime import datetime
import tkinter as tk
from tkinter import messagebox
from playwright.sync_api import sync_playwright

now = datetime.now()
formatted_date = now.strftime("%Y%m%d%H%M")

# 隨機延遲的秒數
delay_choices = [3, 5, 7, 9, 11]
delay = random.choice(delay_choices)


class UrlResult:
    def __init__(self):
        self.val = []

    def update_result(self, val: list):
        self.val.extend(val)


def access_page(keyword: str, store: str, page: int) -> list:
    print(f"開始爬取第{page}頁資料")
    url = get_url(keyword, store, page)
    print(url)
    item_urls = []
    with sync_playwright() as p:
        browser = p.webkit.launch(headless=False)
        page = browser.new_page()
        page.goto(url)

        time.sleep(delay)

        # get item urls
        item_urls = get_page_item_urls(page)
        browser.close()
    return item_urls


def scrape_item_data_from_page(page) -> tuple:
    # price
    price = page.locator(
        "//div[@class='item-purchase-stack'][1]/strong[@class='rt-text-xx-large rt-text-important']").inner_text(
        timeout=500)
    #price = price.replace(',', '').replace('$', '')
    price = price.replace(',', '').replace('$', '').replace(' - ','~')
    # item purchase stack
    try:
        item_purchase_stack = page.locator(
            "//div[@class='item-purchase-stack item-purchase-amount amount']//strong["
            "@class='rt-text-isolated']").inner_text()
    except:
        item_purchase_stack = '售完，缺貨中'

    # latest update date
    latest_update_date_xpath = "//div[@class='intro-section auction-data']/div[@class='intro-section-left " \
                               "product-intro']//span[@class='date']"
    latest_update_date = None
    if page.locator(latest_update_date_xpath).count() > 0:
        latest_update_date = page.locator(latest_update_date_xpath).inner_text()
    # total buy count
    total_buy_count = page.locator(
        "//div[@class='goods-page-section']//div[@class='rt-tab-item "
        "rt-tab-item-current customizable-borderless customizable-medium']//span["
        "@class='rt-text-parentesis count']").inner_text()
    # latest buy information
    buy_count = None
    buy_time = None
    if total_buy_count != '0':
        latest_buyer = page.locator("//table/tbody/tr[1]")
        buy_count_element = latest_buyer.locator("//td[2]")
        if buy_count_element.is_visible():
            buy_count = buy_count_element.inner_text()
        else:
            buy_count = None

        buy_time_element = latest_buyer.locator("//td[3]")
        if buy_time_element.is_visible():
            buy_time = buy_time_element.inner_text()
        else:
            buy_time = '近半年無銷售記錄'
    title = page.title()
    title = title.replace(' | 露天市集 | 全台最大的網路購物市集', '')
    return title, price, item_purchase_stack, latest_update_date, total_buy_count, buy_count, buy_time


def scrape_item_data(url: str) -> tuple:
    print(f"開始爬取商品資料::{url}")
    with sync_playwright() as p:
        browser = p.webkit.launch(headless=True)
        page = browser.new_page()
        page.goto(url)

        time.sleep(delay)

        result = scrape_item_data_from_page(page)
        browser.close()
        return result


def scrape(keyword, store):
    print(f"開始爬取資料::{keyword}, {store}")
    url = get_url(keyword, store)
    print(url)
    url_items = UrlResult()
    with sync_playwright() as p:
        browser = p.webkit.launch(headless=False)
        page = browser.new_page()
        page.goto(url)

        time.sleep(delay)

        page_number_xpath = '//div[@class="head-pagination"]/div[@class="rt-pagination-light rt-pagination"]' \
                            '/ul[@class="page-link-list"]/li[@class="page-num-info"]'
        page_number = page.locator(page_number_xpath).inner_html()
        try:
            page_number = int(page_number.split('</span>')[1])
        except ValueError:
            browser.close()
        url_items.update_result(get_page_item_urls(page))
        with Pool(processes=5) as pool:
            for n in range(2, page_number + 1):
                pool.apply_async(
                    access_page, (keyword, store, n),
                    callback=url_items.update_result)
            pool.close()
            pool.join()
        browser.close()
    item_dataset = []
    with Pool(processes=5) as pool:
        for idx, url in enumerate(url_items.val):
            url_with_history = f"{url}#history&p=1"
            pool.apply_async(scrape_item_data, args=(url_with_history,), callback=lambda x: item_dataset.append(x))
        pool.close()
        pool.join()
    save_to_csv(item_dataset, store, keyword)


def save_to_csv(data, store, keyword):
    print("共{}筆".format(len(data)))
    print("開始儲存資料")
    with open(f'ruten_{store}_{keyword}_{formatted_date}.csv', 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['商品名稱', '價格', '可販售數量', '最後更新日期', '購買人數', '最後銷售數量', '最後銷售時間'])
        for row in data:
            writer.writerow(row)
    print("儲存資料結束")


def get_page_item_urls(page):
    print("開始取得商品網址")
    item_urls = set()
    item_css_selector = 'div.rt-product-card-detail-wrap > a'
    item_elements = page.locator(item_css_selector)
    for item in item_elements.all():
        temp = item.get_attribute("href")
        item_urls.add(temp)
    #for item_element in item_elements:
    #    item_url = item_element.get_attribute('href')
    #    print(item_url)
    #    item_urls.add(item_url)
    return list(item_urls)


def get_url(keyword, store, page=1):
    if not keyword:
        url = f'https://www.ruten.com.tw/store/{store}/list?sort=new%2Fdc&p={page}'
    else:
        keyword = urllib.parse.quote(keyword)
        url = f'https://www.ruten.com.tw/store/{store}/find?sort=new%2Fdc&q={keyword}&p={page}'
    return url


def main():
    # 創建 Tkinter 視窗
    window = tk.Tk()
    window.title("露天爬爬 2.0")
    window.geometry("300x200+300+300")

    # 輸入框
    keyword_label = tk.Label(window, text="請輸入關鍵字：")
    keyword_label.pack()

    keyword_entry = tk.Entry(window)
    keyword_entry.pack()

    # 下拉式選單選項與值的字典
    store_options = {
        "91特賣場": "m122041855",
        "萬隆達": "comic-king",
        "再生卡鋪": "senion0901",
        "逛逛賣場": "wl00177413",
        "樂遊wow": "too1212",
        "白貓貓": "peapi",
        "Xin Qi": "a717890",
        "Zoo": "bts225",
        "HAPPY夏普": "18500zz8",
        "遊戲王特賣": "as75395112367",
        "台中黑殿": "sc086500",
        "台中黑殿2": "slifer5",
        "APP STORE": "benson082012",
        "崇文": "clyde0424",
        "Lizz": "deeploveu",
        "Shin": "0988509634",
        "遊戲王單卡": "gigi931215",
        "源氏": "chrisliu510875",
        "未來廣場": "25446238",
        "Cardmaster": "cardmaster"
    }

    store_var = tk.StringVar(window)
    store_var.set("萬隆達")  # 預設選擇第一個選項

    store_label = tk.Label(window, text="請選擇店家：")
    store_label.pack()

    store_option_menu = tk.OptionMenu(window, store_var, *store_options.keys())
    store_option_menu.pack()

    # 增加空的區域，調整元件位置
    space_label = tk.Label(window, height=1)
    space_label.pack()

    # 按鈕
    scrape_button = tk.Button(
        window, text="爬取資料",
        command=lambda: scrape(keyword_entry.get(), store_options[store_var.get()]))
    scrape_button.pack()

    # 開始執行視窗循環
    window.mainloop()


if __name__ == "__main__":
    main()
