"""
主要功能：
1. 提供用户注册 / 登录接口，并使用 session 记录登录状态。
2. 使用 sqlite 数据库存储用户信息和每个用户的轨迹点。
3. 网站首页直接展示地图页面，右上角弹窗完成登录 / 注册。
4. 只有在“已登录”的情况下，前端上报的轨迹点才会被保存到数据库。
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
    网站首页：直接显示地图主页面(静态文件 static/index.html)。

    登录逻辑交给前端在右上角弹窗中处理：
    - 如果用户已登录：右上角展示用户名，并可以“退出登录”。
    - 如果用户未登录：右上角按钮可以打开“登录 / 注册”弹窗。
    """
    return app.send_static_file("index.html")


@app.route("/register", methods=["POST"])
def register():
    """
    处理注册表单提交：
    1. 从表单中获取用户名和密码。
    2. 校验数据是否为空。
    3. 把密码加密后存入数据库（不要明文存储密码）。
    4. 如果用户名已存在，则给出错误提示。
    """
    # 既支持传统表单（request.form），也支持前端 fetch 发送的 JSON。
    # 优先从 JSON 里取数据，如果没有再从表单取。
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or request.form.get("username") or "").strip()
    password = data.get("password") or request.form.get("password") or ""

    if not username or not password:
        # 数据校验不通过，返回 JSON 形式的错误信息
        return jsonify({"ok": False, "error": "用户名和密码不能为空。"}), 400

    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, generate_password_hash(password)),
        )
        db.commit()
    except sqlite3.IntegrityError:
        # 违反唯一约束（UNIQUE），说明用户名已经被注册
        return jsonify({"ok": False, "error": "用户名已存在，请换一个。"}), 400

    # 注册成功后，不自动登录，而是提示用户去登录
    return jsonify(
        {
            "ok": True,
            "message": "注册成功，请使用该账号登录。",
            "username": username,
        }
    )


@app.route("/login", methods=["POST"])
def login():
    """
    处理登录表单提交：
    1. 根据用户名查找数据库中的记录。
    2. 使用 check_password_hash 校验密码是否正确。
    3. 如果正确，则把 user_id 存到 session 中，表示“已登录”。
    """
    # 同样支持 JSON / 表单两种提交方式
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or request.form.get("username") or "").strip()
    password = data.get("password") or request.form.get("password") or ""

    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()

    if user is None or not check_password_hash(user["password_hash"], password):
        # 用户不存在，或者密码不匹配
        return jsonify({"ok": False, "error": "用户名或密码错误。"}), 400

    # 登录成功，在 session 中记录用户 ID 和用户名
    session["user_id"] = user["id"]
    session["username"] = user["username"]

    # 返回 JSON，前端根据返回结果更新界面（而不是做页面跳转）
    return jsonify({"ok": True, "username": user["username"]})


@app.route("/logout", methods=["GET", "POST"])
def logout():
    """
    注销登录：清空 session 中保存的用户信息。

    - 当前端通过 fetch 以 POST 方式调用时，返回 JSON。
    - 若用户在浏览器直接访问 /logout，则重定向回首页。
    """
    session.clear()
    # 如果是前端 AJAX / fetch 调用，则返回 JSON
    if request.method == "POST" or request.is_json:
        return jsonify({"ok": True})
    # 否则重定向到首页
    return redirect(url_for("index"))


@app.route("/map")
def map_page():
    """
    地图页面路由：
    - 现在首页 "/" 就是地图页面，这个路由只是一个别名。
    - 不再强制要求登录，在地图右上角由用户决定是否登录。
    """
    return app.send_static_file("index.html")


@app.route("/api/location", methods=["POST"])
def save_location():
    """
    接收前端上传的轨迹点数据，并保存到数据库的 locations 表中。

    注意：
    - 只有当用户已登录时（session 里有 user_id），数据才会被保存。
    - 未登录时返回 401，前端可以选择只在本地画轨迹、不做持久化。
    """
    # 如果没有登录，返回 401 提示
    if "user_id" not in session:
        return jsonify({"error": "未登录，轨迹不会被保存。"}), 401
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


@app.route("/api/me", methods=["GET"])
def current_user():
    """
    一个小工具接口：让前端知道当前是否已经登录。

    返回示例：
    - 未登录: {"logged_in": false}
    - 已登录: {"logged_in": true, "username": "alice"}
    """
    if "user_id" in session:
        return jsonify(
            {
                "logged_in": True,
                "username": session.get("username"),
            }
        )
    return jsonify({"logged_in": False})


if __name__ == "__main__":
    # debug=True 方便开发调试，修改代码后会自动重启服务
    app.run(debug=True)
