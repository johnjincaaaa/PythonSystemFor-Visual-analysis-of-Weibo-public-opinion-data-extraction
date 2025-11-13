def parse_cookie() ->list:
    r = list()
    with open('cookie.txt', 'r', encoding='utf-8') as f:
        data = f.readlines()
        # print(data)
        for i in data:
            a = i.split('.weibo.com')[0].split('\t')
            r.append({'name': a[0], 'value': a[1]})

    # print(r)
    return r


