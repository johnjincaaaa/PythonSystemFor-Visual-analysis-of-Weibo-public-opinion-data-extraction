import requests
from lxml import etree
from parsecookie import parse_cookie

def search_urls_and_cmCount(keyword,page) ->list:
    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "priority": "u=0, i",
        "referer": "https://s.weibo.com/weibo?q=%E6%88%90%E9%BE%99&Refer=index&page=2",
        "sec-ch-ua": "\"Chromium\";v=\"142\", \"Google Chrome\";v=\"142\", \"Not_A Brand\";v=\"99\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
    }
    cookies_last = parse_cookie()
    cookies = {}
    for cookie in cookies_last:
        cookies[cookie['name']] = cookie['value']

    url = "https://s.weibo.com/weibo"
    params = {
        "q": keyword,
        "Refer": "index",
        "page": page
    }
    response = requests.get(url, headers=headers, cookies=cookies, params=params)

    # print(response.text)
    # print(response)
    tree = etree.HTML(response.text)
    urls = tree.xpath('//div[@class="from"]/a[1]/@href')
    # print(urls)
    comments_counts = tree.xpath('//a[@action-type="feed_list_comment"]/text()')
    # print(comments_counts)
    a = []
    # '//weibo.com/1916193382/QdsSY36xi?refer_flag=1001030103_23 33'
    for i,j in zip(urls, comments_counts):
        try:
            param = i[23:32]
            count = int(j)
        except Exception as e:
            print(e,"评论为0")
            continue
        else:
            a.append((param, count))
    print(a)
    return a

if __name__ == '__main__':

    search_urls_and_cmCount('蔡徐坤',1)