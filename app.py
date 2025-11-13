import os
import sqlite3
import jieba
import bcrypt
import pandas as pd
import matplotlib.pyplot as plt
from snownlp import SnowNLP
from wordcloud import WordCloud
from collections import Counter
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, g
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from pyecharts import options as opts
from pyecharts.charts import Pie, Bar, Line,Map

# -------------------------- 1. 配置参数 --------------------------
import os
app = Flask(
    __name__,
    static_folder=os.path.join(os.path.dirname(__file__), './static'),  # 强制指定静态文件夹路径
    template_folder=os.path.join(os.path.dirname(__file__), './templates')  # 同时指定模板文件夹（确保安全）
)
app.config['SECRET_KEY'] = 'weibo_yuqing_2025_secret_key'  # 会话加密密钥
app.config['DATABASE'] = os.path.join('data', 'weibo_yuqing.db')  # SQLite数据库路径
app.config['STATIC_FOLDER'] = 'static'
app.config['VISUALIZATION_FOLDER'] = os.path.join(app.config['STATIC_FOLDER'], 'images')

# 确保数据目录和静态目录存在
os.makedirs('data', exist_ok=True)
os.makedirs(app.config['VISUALIZATION_FOLDER'], exist_ok=True)

# 停用词列表（过滤无意义词汇）
STOP_WORDS = {"的", "了", "是", "在", "和", "就", "都", "而", "及", "与", "也", "一个", "没有",
              "我们", "你们", "他们", "这", "那", "不", "很", "非常", "哦", "啊", "呢", "吧", "于"}



# -------------------------- 2. SQLite数据库操作 --------------------------
def get_db():
    """获取数据库连接（Flask请求上下文内复用）"""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
        db.row_factory = sqlite3.Row  # 使查询结果可通过列名访问
    return db

@app.teardown_appcontext
def close_connection(exception):
    """请求结束时关闭数据库连接"""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# 找到 app.py 中的 init_db 函数，修改 comment_data 表的创建语句
def init_db():
    """初始化数据库（创建表结构，新增 user_id 字段）"""
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        # 修改 comment_data 表，新增 user_id 字段（关联 users 表的 id）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comment_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,  -- 新增：关联用户ID（关键）
                created_at TEXT NOT NULL,
                text TEXT NOT NULL,
                source TEXT,
                screen_name TEXT NOT NULL,
                description TEXT,
                sentiment_score REAL,
                sentiment_label TEXT,
                crawl_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                -- 新增外键约束：确保 user_id 必须在 users 表中存在
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        # users 表无需修改，保持原样
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                register_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.commit()

# 重新执行初始化（会自动添加字段，不影响现有数据）
init_db()

# -------------------------- 3. 用户认证模块 --------------------------
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # 未登录时跳转的页面


class User(UserMixin):
    def __init__(self, user_id, username, email):
        self.id = user_id
        self.username = username
        self.email = email


@login_manager.user_loader
def load_user(user_id):
    """加载用户（Flask-Login要求）"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, username, email FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if user:
        return User(user['id'], user['username'], user['email'])
    return None


# -------------------------- 4. 数据爬取模块（替换为你的实际爬虫） --------------------------
from comments_api import crawl_main
"""
字段：created_at, text, source, screen_name, description
"""
    # 测试数据
    # import random
    # from faker import Faker
    # fake = Faker('zh_CN')
    # data = []
    # for i in range(page_num * 20):  # 每页20条评论
    #     # 随机生成正面/负面评论
    #     sentiment = random.choice(['正面', '中性', '负面'])
    #     adj = {
    #         '正面': ['不错', '很好', '支持', '优秀', '推荐'],
    #         '中性': ['一般', '还行', '看看', '了解', '关注'],
    #         '负面': ['失望', '不好', '反对', '糟糕', '垃圾']
    #     }[sentiment]
    #     data.append({
    #         'created_at': fake.date_time_between(start_date='-30d', end_date='now').strftime('%Y-%m-%d %H:%M:%S'),
    #         'text': f'{keyword}{random.choice(adj)}！{fake.sentence()}',
    #         'source': random.choice(['iPhone客户端', 'Android客户端', '微博网页版', 'iPad客户端']),
    #         'screen_name': fake.user_name(),
    #         'description': fake.sentence()
    #     })
    # return data


# -------------------------- 5. 数据管理模块（SQLite操作） --------------------------
class DataManager:
    def __init__(self, user_id):  # 接收当前用户的 user_id
        self.db = get_db()
        self.cursor = self.db.cursor()
        self.user_id = user_id  # 保存用户ID，后续操作都用这个


    def insert_comments(self, comments):
        """插入爬取的评论数据（关联当前用户）"""
        try:
            sql = """
                  INSERT INTO comment_data
                      (user_id, created_at, text, source, screen_name, description)  -- 新增 user_id
                  VALUES (?, ?, ?, ?, ?, ?)
                  """
            # 批量插入时，添加 self.user_id 作为第一个参数
            self.cursor.executemany(sql, [
                (self.user_id, c['created_at'], c['text'], c['source'], c['screen_name'], c['description'])
                for c in comments
            ])
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            print(f"插入数据失败：{e}")
            return False

    # 修改 DataManager 类的 search_comments 方法，添加 user_id 过滤
    def search_comments(self, keyword="", start_time=""):
        """多条件搜索评论数据（仅查询当前用户的）"""
        sql = "SELECT * FROM comment_data WHERE user_id = ?"  # 强制过滤当前用户
        params = [self.user_id]  # 第一个参数是当前用户ID
        if keyword:
            sql += " AND text LIKE ?"
            params.append(f'%{keyword}%')
        if start_time:
            sql += " AND created_at >= ?"
            params.append(start_time)
        sql += " ORDER BY created_at DESC"
        self.cursor.execute(sql, params)
        columns = [desc[0] for desc in self.cursor.description]
        data = self.cursor.fetchall()
        return pd.DataFrame(data, columns=columns) if data else pd.DataFrame()

    # 修改 DataManager 类的 update_sentiment 方法
    def update_sentiment(self, df):
        """更新情感分析结果（仅更新当前用户的评论）"""
        try:
            sql = """
                  UPDATE comment_data
                  SET sentiment_score = ?,
                      sentiment_label = ?
                  WHERE user_id = ? -- 新增：仅更新当前用户的数据
                    AND created_at = ?
                    AND screen_name = ?
                    AND text = ?
                  """
            self.cursor.executemany(sql, [
                (row['sentiment_score'], row['sentiment_label'],
                 self.user_id,  # 新增：用户ID条件
                 row['created_at'], row['screen_name'], row['text'])
                for _, row in df.iterrows()
            ])
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            print(f"更新情感数据失败：{e}")
            return False



import re
from datetime import datetime

from bs4 import BeautifulSoup, NavigableString, Tag

def clean_comment_text(text):
    # 解析HTML文本
    soup = BeautifulSoup(text, 'html.parser')
    result = []

    def process_element(element):
        """递归处理HTML元素，提取有效文本"""
        if isinstance(element, NavigableString):
            # 处理文本节点，去除前后空格
            text_content = str(element).strip()
            if text_content:  # 忽略空文本
                result.append(text_content)
        elif isinstance(element, Tag):
            if element.name == 'img':
                # 提取图片的alt或title作为描述
                alt = element.get('alt', '').strip()
                title = element.get('title', '').strip()
                img_text = alt if alt else title  # 优先用alt
                if img_text:
                    result.append(img_text)
            else:
                # 处理其他标签（如<a>），递归处理子元素
                for child in element.contents:
                    process_element(child)

    # 处理整个HTML结构的所有内容
    for element in soup.contents:
        process_element(element)

    # 合并结果，用空格分隔并去除首尾空格
    return ' '.join(result).strip()



def format_time(raw_time_str):
    """将原始时间字符串（如Wed Nov 12 23:50:39 +0800 2025）转换为YYYY-MM-DD HH:MM:SS"""
    try:
        # 解析原始时间格式（注意：月份是英文缩写，需用%b）
        dt = datetime.strptime(raw_time_str, '%a %b %d %H:%M:%S %z %Y')
        # 转换为目标格式
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        print(f"时间格式转换失败：{e}，原始时间：{raw_time_str}")
        return raw_time_str  # 转换失败时保留原始值

# -------------------------- 6. 情感分析模块 --------------------------
def sentiment_analysis(df):
    """对评论内容进行情感分析（基于SnowNLP）"""

    def analyze(text):
        if not text:
            return 0.5, "中性"
        score = SnowNLP(text).sentiments  # 0-1之间的分数
        if score > 0.6:
            return score, "正面"
        elif score < 0.4:
            return score, "负面"
        else:
            return score, "中性"

    # 批量处理
    df[['sentiment_score', 'sentiment_label']] = df['text'].apply(
        lambda x: pd.Series(analyze(x))
    )
    return df

def extract_region(source):
    """提取地域并标准化（适配地图组件的行政区划名称）"""
    if not source or "来自" not in source:
        return "未知"
    region = source.replace("来自", "").strip()
    # 补充省份/城市后缀，确保与地图匹配（例如“北京”→“北京市”，“湖北”→“湖北省”）
    if region in ["北京", "上海", "天津", "重庆"]:
        return f"{region}市"  # 直辖市补“市”
    if region in ["内蒙古", "宁夏", "新疆", "西藏", "广西"]:
        return f"{region}自治区"  # 自治区补“自治区”
    # 普通省份补“省”（如“湖北”→“湖北省”）
    if len(region) <= 2 and region not in ["香港", "澳门", "台湾"]:
        return f"{region}省"
    return region


def region_distribution(comments):
    # 提取所有地域并统计
    regions = [extract_region(c['source']) for c in comments]
    region_counts = Counter(regions).most_common(20)  # 取前20个地区

    # 生成地图
    map_chart = (
        Map()
        .add("评论数", region_counts, "china")
        .set_global_opts(
            title_opts=opts.TitleOpts(title="评论地域分布"),
            visualmap_opts=opts.VisualMapOpts(max_=max([c[1] for c in region_counts]))
        )
    )
    return map_chart.render(path="static/images/region_map.html")

def region_sentiment_correlation(comments_with_sentiment):
    # comments_with_sentiment 包含现有字段+sentiment_label
    region_sentiment = {}
    for c in comments_with_sentiment:
        region = extract_region(c['source'])
        sentiment = c['sentiment_label']
        if region not in region_sentiment:
            region_sentiment[region] = {'正面':0, '中性':0, '负面':0}
        region_sentiment[region][sentiment] += 1
    # 生成各地区情感占比柱状图（略）


# -------------------------- 7. 可视化模块 --------------------------
class Visualizer:
    def __init__(self, df):
        self.df = df
        self.timestamp = datetime.now().strftime('%Y%m%d%H%M%S')  # 用于区分图表文件

    def region_distribution_map(self):
        if self.df.empty:
            return ""
        # 提取并标准化地域
        self.df['region'] = self.df['source'].apply(extract_region)
        # 统计各地区评论数（排除“未知”）
        region_counts = self.df[self.df['region'] != "未知"]['region'].value_counts().to_dict()
        region_data = [(k, v) for k, v in region_counts.items()]
        if not region_data:
            return ""

        # 计算评论数最大值（用于视觉映射范围）
        max_count = max([v for _, v in region_data])

        # 生成带热力效果的地图（核心：增加颜色渐变配置）
        map_chart = (
            Map()
            .add(
                series_name="评论数",
                data_pair=region_data,
                maptype="china",  # 指定中国地图
                label_opts=opts.LabelOpts(is_show=True)  # 显示地区名称
            )
            .set_global_opts(
                title_opts=opts.TitleOpts(title="评论地域分布（IP属地）"),
                visualmap_opts=opts.VisualMapOpts(
                    type_="color",  # 颜色映射（热力核心）
                    is_calculable=True,
                    min_=0,
                    max_=max_count,
                    # 颜色渐变：从浅蓝到深蓝（数值越高颜色越深）
                    range_color=["#e0f7fa", "#b2ebf2", "#80deea", "#4dd0e1", "#26c6da", "#00bcd4", "#00acc1"],
                    range_text=["高", "低"],  # 图例文本
                    pos_right="10%",  # 图例位置
                    pos_bottom="10%"
                )
            )
        )
        path = os.path.join(app.config['VISUALIZATION_FOLDER'], f'region_map_{self.timestamp}.html')
        map_chart.render(path)
        return os.path.basename(path)

    def region_sentiment_bar(self):
        """生成地域-情感分布柱状图（修复tolist错误）"""
        if self.df.empty:
            return ""
        # 提取地域并关联情感标签
        self.df['region'] = self.df['source'].apply(extract_region)
        # 按地域和情感分组统计
        region_sentiment = self.df.groupby(['region', 'sentiment_label']).size().unstack(fill_value=0)
        # 过滤"未知"地区，取评论数前10的地区
        region_sentiment = region_sentiment.drop(index="未知", errors='ignore')
        if len(region_sentiment) == 0:
            return ""
        top_regions = region_sentiment.sum(axis=1).nlargest(10).index  # 取评论数前10的地区
        region_sentiment = region_sentiment.loc[top_regions]

        # 安全转换函数（复用之前的逻辑，避免列表调用tolist()）
        def safe_tolist(data, key):
            val = data.get(key, [])
            return val.tolist() if isinstance(val, pd.Series) else val

        # 生成柱状图（使用安全转换）
        bar = (
            Bar()
            .add_xaxis(xaxis_data=region_sentiment.index.tolist())
            .add_yaxis("正面", y_axis=safe_tolist(region_sentiment, '正面'))  # 修复此处
            .add_yaxis("中性", y_axis=safe_tolist(region_sentiment, '中性'))  # 修复此处
            .add_yaxis("负面", y_axis=safe_tolist(region_sentiment, '负面'))  # 修复此处
            .set_global_opts(
                title_opts=opts.TitleOpts(title="各地区情感分布"),
                xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=-45)),
                yaxis_opts=opts.AxisOpts(name="评论数量")
            )
        )
        # 保存柱状图HTML
        path = os.path.join(app.config['VISUALIZATION_FOLDER'], f'region_sentiment_{self.timestamp}.html')
        bar.render(path)
        return os.path.basename(path)

    def generate_wordcloud(self):
        """生成词云图"""
        if self.df.empty:
            return ""
        all_text = " ".join(self.df['text'].dropna())
        words = jieba.cut(all_text)
        filtered_words = [
            word for word in words
            if word.strip() and word not in STOP_WORDS and len(word) > 1
        ]
        if not filtered_words:
            return ""
        # 生成词云
        wc = WordCloud(
            font_path="simhei.ttf",  # Windows系统默认有该字体
            width=1200, height=600,
            background_color="white",
            max_words=200,
            contour_width=1,
            contour_color='steelblue'
        ).generate(" ".join(filtered_words))
        # 保存图片
        path = os.path.join(app.config['VISUALIZATION_FOLDER'], f'wordcloud_{self.timestamp}.png')
        wc.to_file(path)
        return os.path.basename(path)


    def hot_words_bar(self, top_n=10):
        plt.switch_backend('Agg')  # 使用非交互式后端，避免线程问题
        """生成热词TopN柱状图"""
        if self.df.empty:
            return ""
        all_text = " ".join(self.df['text'].dropna())
        words = jieba.cut(all_text)
        filtered_words = [
            word for word in words
            if word.strip() and word not in STOP_WORDS and len(word) > 1
        ]
        if not filtered_words:
            return ""
        # 统计词频
        word_counts = Counter(filtered_words).most_common(top_n)
        words = [item[0] for item in word_counts]
        counts = [item[1] for item in word_counts]
        # 绘制柱状图（修正字体配置，只保留Windows系统存在的字体）
        plt.rcParams["font.family"] = ["SimHei"]  # 仅保留“黑体”，Windows默认自带
        plt.figure(figsize=(12, 6))
        bars = plt.bar(words, counts, color='#4CAF50')
        # 添加数据标签
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width() / 2., height + 0.5,
                     f'{height}', ha='center', va='bottom')
        plt.title(f'评论热词TOP{top_n}', fontsize=16)
        plt.xlabel('词汇', fontsize=12)
        plt.ylabel('出现次数', fontsize=12)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        # 保存图片
        path = os.path.join(app.config['VISUALIZATION_FOLDER'], f'hotwords_{self.timestamp}.png')
        plt.savefig(path, dpi=300)
        plt.close()
        return os.path.basename(path)

    def sentiment_pie(self):
        """生成情感分布饼图"""
        if self.df.empty:
            return ""
        sentiment_counts = self.df['sentiment_label'].value_counts().to_dict()
        for label in ['正面', '中性', '负面']:
            if label not in sentiment_counts:
                sentiment_counts[label] = 0
        # 构建饼图（修正颜色配置）
        pie = (
            Pie()
            .add(
                "",
                [list(item) for item in sentiment_counts.items()],
                radius=["40%", "70%"],
                label_opts=opts.LabelOpts(formatter="{b}: {c} ({d}%)"),
                color=['#4CAF50', '#FFC107', '#F44336']  # 在这里指定饼图扇区颜色
            )
            .set_global_opts(
                title_opts=opts.TitleOpts(title="评论情感分布", pos_top=10),
                legend_opts=opts.LegendOpts(pos_bottom=10)
            )
            .set_series_opts(
                itemstyle_opts=opts.ItemStyleOpts()  # 移除colors参数，如需单个样式可配置color
            )
        )
        path = os.path.join(app.config['VISUALIZATION_FOLDER'], f'sentiment_pie_{self.timestamp}.html')
        pie.render(path)
        return os.path.basename(path)

    def trend_line(self):
        """生成情感时间趋势图"""
        if self.df.empty:
            return ""
        # 提取日期（忽略时间部分）
        self.df['date'] = self.df['created_at'].str.split(' ').str[0]
        # 按日期和情感标签分组统计数量
        trend_data = self.df.groupby(['date', 'sentiment_label']).size().unstack(fill_value=0)
        if trend_data.empty:
            return ""

        # 安全获取各情感数据（判断类型后转换）
        def safe_tolist(data, key):
            val = data.get(key, [])
            return val.tolist() if isinstance(val, pd.Series) else val  # 核心修复

        # 构建折线图
        line = (
            Line()
            .add_xaxis(xaxis_data=trend_data.index.tolist())
            .add_yaxis(
                series_name="正面",
                y_axis=safe_tolist(trend_data, '正面'),  # 使用安全转换函数
                symbol="emptyCircle",
                itemstyle_opts=opts.ItemStyleOpts(color="#4CAF50")
            )
            .add_yaxis(
                series_name="中性",
                y_axis=safe_tolist(trend_data, '中性'),  # 使用安全转换函数
                symbol="emptyCircle",
                itemstyle_opts=opts.ItemStyleOpts(color="#FFC107")
            )
            .add_yaxis(
                series_name="负面",
                y_axis=safe_tolist(trend_data, '负面'),  # 使用安全转换函数
                symbol="emptyCircle",
                itemstyle_opts=opts.ItemStyleOpts(color="#F44336")
            )
            .set_global_opts(
                title_opts=opts.TitleOpts(title="情感时间趋势"),
                tooltip_opts=opts.TooltipOpts(trigger="axis"),
                xaxis_opts=opts.AxisOpts(
                    type_="category",
                    axislabel_opts=opts.LabelOpts(rotate=-45)  # 日期标签旋转45度避免重叠
                ),
                yaxis_opts=opts.AxisOpts(name="评论数量")
            )
        )
        # 保存折线图为HTML
        path = os.path.join(app.config['VISUALIZATION_FOLDER'], f'trend_line_{self.timestamp}.html')
        line.render(path)
        return os.path.basename(path)






# -------------------------- 8. Flask路由（Web界面） --------------------------
@app.route('/')
def index():
    """首页重定向到登录页"""
    return redirect(url_for('login'))




@app.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册"""
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip().encode('utf-8')
        email = request.form['email'].strip()

        # 简单验证
        if not all([username, password, email]):
            return render_template('register.html', error="请填写完整信息")

        # 密码加密
        hashed_pw = bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')

        # 插入数据库
        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, password, email) VALUES (?, ?, ?)",
                (username, hashed_pw, email)
            )
            db.commit()
            return redirect(url_for('login', msg="注册成功，请登录"))
        except sqlite3.IntegrityError:
            return render_template('register.html', error="用户名或邮箱已存在")
        except Exception as e:
            return render_template('register.html', error=f"注册失败：{str(e)}")

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录"""
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip().encode('utf-8')

        # 查询用户
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id, username, password FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()

        if user and bcrypt.checkpw(password, user['password'].encode('utf-8')):
            # 登录成功
            login_user(User(user['id'], user['username'], ""))
            next_page = request.args.get('next', 'dashboard')
            return redirect(next_page)
        else:
            return render_template('login.html', error="用户名或密码错误")

    return render_template('login.html', msg=request.args.get('msg'))


@app.route('/logout')
@login_required
def logout():
    """退出登录"""
    logout_user()
    return redirect(url_for('login', msg="已退出登录"))


# 导入math模块用于向上取整
import math


@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    """仪表盘（核心功能页）- 数据隔离版"""
    # 关键：创建 DataManager 时传入当前用户的 ID
    dm = DataManager(user_id=current_user.id)  # 新增 user_id 参数
    keyword = request.args.get('keyword', '')
    start_time = request.args.get('start_time', '')
    visualizations = {
        'wordcloud': '', 'hot_words': '', 'sentiment_pie': '', 'trend_line': '',
        'region_map': '', 'region_sentiment': ''
    }

    # 处理爬取请求（后续逻辑不变，仅 DataManager 已关联用户ID）
    if request.method == 'POST' and 'crawl' in request.form:
        crawl_keyword = request.form.get('crawl_keyword', '').strip()
        comment_num = int(request.form.get('comment_num', 20))
        if not crawl_keyword:
            return render_template('dashboard.html', error="请输入搜索关键词", data=[], **visualizations)
        if comment_num <= 0:
            return render_template('dashboard.html', error="评论数必须大于0", data=[], **visualizations)

        page_num = math.ceil(comment_num / 20)
        comments = crawl_main(crawl_keyword, page_num)[:comment_num]
        if not comments:
            return render_template('dashboard.html', error="未爬取到数据，请尝试其他关键词", data=[], **visualizations)

        # 数据清洗（不变）
        cleaned_comments = []
        for c in comments:
            cleaned = {
                'created_at': format_time(c['created_at']),
                'text': clean_comment_text(c['text']),
                'source': c.get('source', ''),
                'screen_name': c.get('screen_name', ''),
                'description': c.get('description', '')
            }
            cleaned_comments.append(cleaned)

        # 插入数据（已自动关联当前用户ID）
        if dm.insert_comments(cleaned_comments):
            df_new = pd.DataFrame(cleaned_comments)
            df_new = sentiment_analysis(df_new)
            dm.update_sentiment(df_new)

    # 搜索数据（仅查询当前用户的）
    df = dm.search_comments(keyword, start_time)
    data = df.to_dict('records') if not df.empty else []

    # 生成可视化（不变，基于当前用户数据）
    if not df.empty:
        visualizer = Visualizer(df)
        visualizations = {
            'wordcloud': visualizer.generate_wordcloud(),
            'hot_words': visualizer.hot_words_bar(),
            'sentiment_pie': visualizer.sentiment_pie(),
            'trend_line': visualizer.trend_line(),
            'region_map': visualizer.region_distribution_map(),
            'region_sentiment': visualizer.region_sentiment_bar()
        }

    return render_template('dashboard.html', data=data, **visualizations)

@app.route('/clean_old_data')
@login_required
def clean_old_data():
    """清洗当前用户的旧数据（时间格式+图片标签）"""
    dm = DataManager(user_id=current_user.id)  # 传入当前用户ID
    cursor = dm.db.cursor()
    # 仅查询当前用户的旧数据
    cursor.execute("SELECT id, created_at, text FROM comment_data WHERE user_id = ?", (current_user.id,))
    old_data = cursor.fetchall()

    for item in old_data:
        item_id, raw_time, raw_text = item['id'], item['created_at'], item['text']
        cleaned_time = format_time(raw_time)
        cleaned_text = clean_comment_text(raw_text)
        cursor.execute(
            "UPDATE comment_data SET created_at = ?, text = ? WHERE id = ? AND user_id = ?",
            (cleaned_time, cleaned_text, item_id, current_user.id)  # 加 user_id 条件
        )
    dm.db.commit()
    return "当前用户的旧数据清洗完成"




# -------------------------- 9. 主函数 --------------------------
if __name__ == '__main__':
    # 启动Flask服务（debug=True仅用于开发环境）
    app.run(debug=True, host='0.0.0.0', port=5000)