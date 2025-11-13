"""
视频入口：https://weibo.com/7977461661/Q9ssxas4L
https://weibo.com/3725773862/QdwtLq3Ek
id：随着视频变换而变换
加密参数：max_id
"""
from parsecookie import parse_cookie
from keyword_to_search_blogurls import search_urls_and_cmCount
import requests

def get_id(url_param_:str):
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "cache-control": "no-cache",
        "client-version": "v2.47.134",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": "https://weibo.com/7977461661/Q9ssxas4L",
        "sec-ch-ua": "\"Chromium\";v=\"142\", \"Google Chrome\";v=\"142\", \"Not_A Brand\";v=\"99\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "server-version": "v2025.11.12.1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        "x-requested-with": "XMLHttpRequest",
        "x-xsrf-token": "fTzsFd1j4dYlXIVbAePRE1UG"
    }

    cookies_last = parse_cookie()
    cookies = {}
    for cookie in cookies_last:
        cookies[cookie['name']] = cookie['value']
    url = "https://weibo.com/ajax/statuses/show"
    params = {
        "id": url_param_,
        "locale": "zh-CN",
        "isGetLongText": "true"
    }
    response = requests.get(url, headers=headers, cookies=cookies, params=params)

    return response.json().get("id")

def single_video(id_,max_id=0):
    cookies_last = parse_cookie()
    cookies = {}
    for cookie in cookies_last:
        cookies[cookie['name']] = cookie['value']
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "cache-control": "no-cache",
        "client-version": "v2.47.129",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": "https://weibo.com/7789475114/QbbcWFm6k",
        "sec-ch-ua": "\"Google Chrome\";v=\"141\", \"Not?A_Brand\";v=\"8\", \"Chromium\";v=\"141\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "server-version": "v2025.10.24.3",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
        "x-requested-with": "XMLHttpRequest",
        "x-xsrf-token": "w9tg9UCyT7SMef1D7g9-PSGp"
    }

    url = "https://weibo.com/ajax/statuses/buildComments"
    params = {
        "is_asc": "0",
        "is_reload": "1",
        "id": id_,
        "is_show_bulletin": "1",
        "is_mix": "0",
        "max_id": max_id,
        "count": "20",
        "fetch_level": "0",
        "locale": "zh-CN"
    }

    response = requests.get(url, headers=headers, cookies=cookies, params=params)
    result = response.json()
    data = []

    try:
        for i in result['data']:
            data.append({
                'created_at': i["created_at"],
                'text': i["text"],
                'source': i["source"],
                'screen_name': i["user"]["screen_name"],
                'description': i["user"]["description"],
            })
    except Exception as e:
        print(e)
    return data, result['max_id']


def get_data(url_param_:str) -> list:
    final = []
    video_id = get_id(url_param_)
    max_id = 0
    while True:
        data_, max_id = single_video(id_= video_id, max_id=max_id)
        final.extend(data_)
        if max_id:
            max_id = max_id
        else:
            break
    return final

def crawl_main(keyword_, page_num:int):
    start_count = 0
    start_page = 1
    PARAM = []
    # break_while = False  # 标志位：是否退出while循环

    while start_count < page_num:
        for url_param, count in search_urls_and_cmCount(keyword=keyword_, page=start_page):
            start_page += 1
            start_count += count
            PARAM.append(url_param)
        if not search_urls_and_cmCount(keyword=keyword_, page=start_page):
            break


    print(f'已经获取{start_count}条')
    print('PARAM:', PARAM)
    result = []
    for p in PARAM:
        data = get_data(p)
        for i in data:
            print(i)
            result.append(i)
    return result

if __name__ == '__main__':
    keyword = input('请输入搜索关键字：')
    COUNT = int(input('请输入爬取评论数：').strip())
    crawl_main(keyword, COUNT)
