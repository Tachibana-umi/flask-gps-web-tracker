"""
主要功能：
1. 提供用户注册 / 登录接口，并使用 session 记录登录状态。
2. 使用 sqlite 数据库存储用户信息和每个用户的轨迹点。
3. 登录成功后，跳转到地图页面（前端使用百度地图 JS 追踪位置）。
4. 前端在采集到位置后，会调用后端 API，把每个点保存到数据库中。
"""

import os
import sqlite3
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    g,
)
from werkzeug.security import generate_password_hash, check_password_hash

# 创建 Flask 应用对象
# static_folder / template_folder 指定静态文件和模板文件所在的目录
app = Flask(__name__, static_folder="static", template_folder="templates")

# session 加密用的密钥（生产环境中请改成环境变量，而不是写死在代码里）
app.secret_key = "dev-secret-key-change-me"

# sqlite 数据库文件路径，放在当前项目根目录下
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "app.db")


# -------- 数据库相关的辅助函数 --------

def get_db():
    """
    在一次请求的生命周期内，获取（或创建）一个 sqlite 连接。
    使用 g 对象保存，避免重复创建连接。
    """
    if "db" not in g:
        # check_same_thread=False 允许同一个连接在不同线程中使用，
        # 对于简单的开发环境来说够用。
        g.db = sqlite3.connect(DATABASE, check_same_thread=False)
        # 让查询结果支持通过列名访问，比如 row["username"]
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    """
    每次请求结束时自动调用，关闭数据库连接。
    """
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """
    初始化数据库：
    - 创建用户表 users
    - 创建轨迹点表 locations
    如果表已经存在，则不会重复创建。
    """
    db = get_db()
    # 创建用户表：存储用户名和密码哈希
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
        """
    )

    # 创建轨迹点表：每个点与一个用户关联
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
    )
    db.commit()


# 在应用启动时，创建好数据库和表
with app.app_context():
    init_db()


# -------- 登录状态相关的辅助工具 --------

def login_required(view_func):
    """
    自定义装饰器，用于保护需要登录才能访问的路由。

    用法示例：
    @app.route("/map")
    @login_required
    def map_page():
        ...
    """

    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            # 如果没有登录，跳转回登录页面
            return redirect(url_for("index"))
        return view_func(*args, **kwargs)

    return wrapped_view


# -------- 路由定义 --------

@app.route("/", methods=["GET"])
def index():
    """
    网站首页：显示登录 / 注册页面。
    如果用户已经登录，则直接跳转到地图页面。
    """
    if "user_id" in session:
        return redirect(url_for("map_page"))  #重定向到地图页面
    # 默认 form_type 设置为 "login"，用于前端控制显示哪个 tab 高亮
    return render_template("index.html", form_type="login")  


@app.route("/register", methods=["POST"])
def register():
    """
    处理注册表单提交：
    1. 从表单中获取用户名和密码。
    2. 校验数据是否为空。
    3. 把密码加密后存入数据库（不要明文存储密码）。
    4. 如果用户名已存在，则给出错误提示。
    """
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    if not username or not password:
        # 数据校验不通过，重新渲染页面并展示错误信息
        return render_template(
            "index.html",
            error="用户名和密码不能为空。",
            form_type="register",
        )

    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, generate_password_hash(password)),
        )
        db.commit()
    except sqlite3.IntegrityError:
        # 违反唯一约束（UNIQUE），说明用户名已经被注册
        return render_template(
            "index.html",
            error="用户名已存在，请换一个。",
            form_type="register",
        )

    # 注册成功后，不自动登录，而是提示用户去登录
    return render_template(
        "index.html",
        message="注册成功，请使用该账号登录。",
        form_type="login",
    )


@app.route("/login", methods=["POST"])
def login():
    """
    处理登录表单提交：
    1. 根据用户名查找数据库中的记录。
    2. 使用 check_password_hash 校验密码是否正确。
    3. 如果正确，则把 user_id 存到 session 中，表示“已登录”。
    """
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()

    if user is None or not check_password_hash(user["password_hash"], password):
        # 用户不存在，或者密码不匹配
        return render_template(
            "index.html",
            error="用户名或密码错误。",
            form_type="login",
        )

    # 登录成功，在 session 中记录用户 ID 和用户名
    session["user_id"] = user["id"]
    session["username"] = user["username"]

    # 跳转到地图页面
    return redirect(url_for("map_page"))


@app.route("/logout")
def logout():
    """
    注销登录：清空 session 中保存的用户信息，然后回到登录页。
    """
    session.clear()
    return redirect(url_for("index"))


@app.route("/map")
@login_required
def map_page():
    """
    地图页面路由：
    - 这里只是做一个简单判断：必须登录后才能访问。
    - 实际页面由前端静态文件 static/index.html 提供。
    """
    return app.send_static_file("index.html")


@app.route("/api/location", methods=["POST"])
@login_required
def save_location():
    """
    接收前端上传的轨迹点数据，并保存到数据库的 locations 表中。

    前端提交 JSON 数据格式示例：
    {
        "latitude": 39.9,
        "longitude": 116.3
    }
    """
    data = request.get_json(silent=True) or {}
    latitude = data.get("latitude")
    longitude = data.get("longitude")

    # 做一些简单的合法性检查
    if latitude is None or longitude is None:
        return jsonify({"error": "缺少经纬度参数。"}), 400

    try:
        lat = float(latitude)
        lng = float(longitude)
    except (TypeError, ValueError):
        return jsonify({"error": "经纬度必须是数字。"}), 400

    user_id = session.get("user_id")

    db = get_db()
    db.execute(
        "INSERT INTO locations (user_id, latitude, longitude) VALUES (?, ?, ?)",
        (user_id, lat, lng),
    )
    db.commit()

    return jsonify({"status": "ok"})


if __name__ == "__main__":
    # debug=True 方便开发调试，修改代码后会自动重启服务
    app.run(debug=True)
