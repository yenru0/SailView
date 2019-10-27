"""
Project Sail Steel
The Sail View
"""


import mistune
from flask import Flask, render_template_string, redirect, render_template, url_for, abort, request, session
from flask import _app_ctx_stack
import re
import sys
import os
import subprocess as sp
import logging as log
import datetime as dt
from tempfile import TemporaryDirectory, NamedTemporaryFile
import time
import sqlite3
from hashlib import sha3_256
import secrets

__version__ = "0.0.1t"

"""
f: file
d: document 
***document in file***

name: name (usually using with f like fname)
path: dir + fname
dir: path except fname

dpath: document_path
fpath: file_path
"""

# =========
# init
# =========

# topdir = "documents/"
dummydir = "./dummy/"
md = mistune.Markdown()
latex_re = re.compile(r'<pre><code class="(lang|language)-(latex|math)">(.+?)</code></pre>', re.DOTALL)

LATEX_Cs = r"""\documentclass[dvips]{article}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{amsfonts}
\usepackage{amsthm}
\usepackage{kotex}
\usepackage{tikz}
\usepackage{tkz-euclide}
\usepackage{pgfplots}
\usepackage{tikz-3dplot}
\pgfplotsset{compat=1.16}
\thispagestyle{empty}
\setmainhangulfont{NanumGothic}
\setsanshangulfont{NanumMyeongjo}
\setmonohangulfont{D2Coding}
\begin{document}
%s
\end{document}
"""

#
# permission set
#
"""
Document Access Permission?
public: for all user but not generator
private: non public, It owes But High permission User for example 'admin' and 'moderator'
locked: 'highuser' can connect this simple locked document.
---
forbidden: for 'admin' and 'moderator' 
security: for 'admin' only

for example an example document perm is 'public/locked/admin' means 'getperm/editperm/settingperm'

Exceptionally, private set specific human to connect for example 'private:yenru0' means privately and allow to yenru0
"""

doc_permission = {"public": 0, "private": 1, "locked": 2, "forbidden": 3, "security": 4}
private_permission = 1
public_document_permissions = ["public", "private", "forbidden"]
normal_user_document_permissions = ["public", "private", "private"]

"""
user permission?
banned: It was a human.
human: It is normal user
highuser: high user is allowed to connect locked document
moderator: sub admin
admin: admin!
"""

user_permission = {"deleted": 0, "human": 1, "highuser": 2, "moderator": 3, "admin": 4}
generate_private_permission = 1
full_compile_able_permission = 2
default_user_permission = 1





#
# sqlite db init
#

conn = None
curs = None

db_name = "docs.db"

conn = sqlite3.connect(db_name)
curs = conn.cursor()

"""
""
yenru0
├─ project
│  ├── sub-project1 (project/sub-project1)
│  │   ├── sub-sub-project (project/sub-project1/sub-sub-project)
│  ├── sub-project2 (project/sub-project2)
│  └── sub-project3 (project/sub-project3)
└── temp-project

when db project/sub-project1 is
    (yenru0, project/sub-project1, project, ... )
when db project/sub-project1/sub-sub-project is
    (yenru0, project/sub-project1/sub-sub-project, project/sub-project, ... )

but project document is project/$project_document
"""

curs.execute("CREATE TABLE if not exists document (user, project, doc_name, raw, compiled, last)")
curs.execute("CREATE TABLE if not exists project (user, project, parent_project, description, access_perm)")
curs.execute("CREATE TABLE if not exists history (user, project, doc_name, number, edit_user, cause, length)")
curs.execute("CREATE TABLE if not exists user (name, id, pw, permission, date)")
curs.execute("CREATE TABLE if not exists user_setting (name, key, value)")
# make_user(":public:", ":public_system:", "admin", "admin")
curs.execute("INSERT INTO user SELECT :name, :id, :pw, :perm, :date WHERE NOT EXISTS(SELECT * FROM user WHERE name = :name AND id = :id)",
             {'name': ":public:", 'id': "☆→@public_system@←※", 'pw': sha3_256("admin".encode("utf-8")).hexdigest(), 'perm': "admin", 'date': dt.datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
              }
            )
curs.execute("INSERT INTO user_setting SELECT :name, :key, :value WHERE NOT EXISTS(SELECT * FROM user_setting WHERE name = :name AND key = :key)",
             {"name": ":public:", "key": "user_default_perm_set", "value": "/".join(public_document_permissions)}
             )
conn.commit()


conn.close()

conn = None
curs = None

def opendb(func):
    def wrapper(*args, **kwargs):
        global conn, curs
        conn = get_db()
        curs = conn.cursor()
        return func(*args, **kwargs)
    return wrapper


### flask init
app = Flask(__name__)
app.url_map.strict_slashes = False

def get_db():
    top = _app_ctx_stack.top
    if not hasattr(top, 'sqlite_db'):
        top.sqlite_db = sqlite3.connect(db_name)
    return top.sqlite_db


@app.teardown_appcontext
def close_connection(exception):
    top = _app_ctx_stack.top
    if hasattr(top, 'sqlite_db'):
        top.sqlite_db.close()




### define default functions
def composePath(*args:str):
    return "/".join([j for p in args
                    for i in p.split("/")
                    for j in i.split("\\")
                     if j]
                    )

def formatDatetime(datetime:dt.datetime):
    return datetime.strftime("%Y-%m-%d-%H:%M:%S")

def reformatDatetime(fdatetime:str):
    return dt.datetime.strptime(fdatetime, "%Y-%m-%d-%H:%M:%S")

def formatDatetimeNow():
    return formatDatetime(dt.datetime.now())

def hash(k:str):
    return sha3_256(k.encode("utf-8")).hexdigest()

app.jinja_env.globals.update(composePath=composePath)



# =========
# define sqlite operation functions
# ========


#
# user
#
@opendb
def check_user_overlap(name:str, id:str):
    """
    :param name:
    :param id:
    :return: True if Exists Others else False
    check if exists same name or id
    """
    curs.execute("SELECT name, id FROM user WHERE name = :name OR id = :id", {"name": name, "id": id})
    t = curs.fetchone()
    return bool(t)

@opendb
def check_user_overlap_id(id:str):
    """
    :param id:
    :return: True if Exists Others else False
    check if exists same id
    """
    curs.execute("SELECT name, id FROM user WHERE id = :id", {"id": id})
    t = curs.fetchone()
    return bool(t)

@opendb
def match_user_pw(id:str, pw:str):
    curs.execute("SELECT name, id FROM user WHERE id = :id AND pw = :pw",
                 {"id": id, "pw": hash(pw)}
                 )
    t = curs.fetchone()
    return bool(t)

@opendb
def get_user_by_name(name):
    curs.execute("SELECT * FROM user WHERE name = :name", {"name": name})
    return curs.fetchone()

@opendb
def get_user_by_id(id):
    curs.execute("SELECT * FROM user WHERE id = :id", {"id": id})
    return curs.fetchone()

@opendb
def get_user_name_by_id(id):
    curs.execute("SELECT name FROM user WHERE id = :id", {"id": id})
    return curs.fetchone()[0]

@opendb
def get_user_by_id_name(name, id):
    curs.execute("SELECT * FROM user WHERE id = :id", {"name": name, "id": id})
    return curs.fetchone()

@opendb
def get_user_perm_by_id(id:str):
    """
    :param id:
    :return: permission number
    Str -> Int
    """
    curs.execute("SELECT permission FROM user WHERE id = :id", {"id": id})
    if curs.fetchone() is None:
        return default_user_permission
    else:
        try:
            return user_permission[curs.fetchone()[0]]
        except KeyError as e:
            print(e)
            return default_user_permission





@opendb
def make_user(name:str, id:str, pw:str, perm:str):
    """
    :param name:
    :param id:
    :param pw:
    :param perm:
    :return: False if Can't make else True
    """

    if check_user_overlap(name, id):
        return False
    else:
        curs.execute("INSERT INTO user VALUES (:name, :id, :pw, :perm, :date)",
                     {'name': name, 'id': id, 'pw': hash(pw), 'perm': perm, 'date': formatDatetimeNow()}
                     )
        conn.commit()
        return True

@opendb
def del_user(name:str, id:str):
    curs.execute("UPDATE user SET permission = 'deleted' WHERE name = ? AND id = ?", (name, id))
    conn.commit()
    return True



#
# user setting
#

@opendb
def set_user_setting(name, key, value):
    curs.execute("SELECT name FROM user_setting WHERE name = ? AND key = ?", (name, key))
    t = curs.fetchone()
    if t is None:
        curs.execute("INSERT INTO user_setting VALUES (:name, :key, :value) WHERE name = :name AND key = :key",
                     {"name": name, "key": key, "value": value}
                     )
    else:
        curs.execute("UPDATE user_setting SET value = :value WHERE name = :name AND key = :key",
                     {"name": name, "key": key, "value": value}
                     )
    conn.commit()
    return True

def get_user_setting(name, key):
    curs.execute("SELECT value FROM user_setting WHERE name = ? AND key = ?", (name, key))
    return curs.fetchone()



#
# document
#


@opendb
def get_raw(user:str, project:str, doc_name:str):
    curs.execute("SELECT raw FROM document WHERE user = ? AND project = ? AND doc_name = ?", (user, project, doc_name))
    return curs.fetchone()


@opendb
def get_compiled(user:str, project:str, doc_name:str):
    curs.execute("SELECT compiled FROM document WHERE user = ? AND project = ? AND doc_name = ?", (user, project, doc_name))
    return curs.fetchone()

@opendb
def check_document(user:str, project:str, doc_name:str):
    if get_project(user, project):
        curs.execute("SELECT doc_name FROM document WHERE user = :user AND project = :project AND doc_name = :doc_name",
                     {"user": user, "project": project, "doc_name": doc_name}
                     )
        return not bool(curs.fetchone())
    else:
        return False


@opendb
def make_document(user:str, project:str, doc_name:str, raw:str = ""):
    if check_document(user, project, doc_name):
        curs.execute("INSERT INTO document VALUES (?, ?, ?, ?, ?, ?)",
                     (user, project, doc_name, raw, "", formatDatetimeNow())
                     )
        conn.commit()
        return True
    else:
        return False



#
# project
#

@opendb
def check_dir(user, parent_project, sub_project):
    if parent_project == "" or parent_project is None:
        parent_project = ""
        t2 = True
    else :
        curs.execute("SELECT project FROM project WHERE user = :user AND project = :parent_project",
                     {"user": user, "parent_project": parent_project}
                     )
        t2 = curs.fetchone()  # It must exist
    curs.execute("SELECT project FROM project WHERE user = :user AND project = :project AND parent_project = :parent_project",
                 {"user": user, "parent_project": parent_project , "project": composePath(parent_project, sub_project)}
                 )
    t1 = curs.fetchone()  # It must not exist
    return not(bool(t1) is False and bool(t2) is True)

@opendb
def make_project(user, parent_project, sub_project):
    if parent_project is None:
        parent_project = ""

    if check_dir(user, parent_project, sub_project):
        return False
    else:
        curs.execute("INSERT INTO project VALUES (?, ?, ?, ?, ?)", (
            user, composePath(parent_project, sub_project), parent_project, ":SailViewProject:", None)
                     )
        conn.commit()
        return True


@opendb
def get_project(user, project):
    curs.execute("SELECT * FROM project WHERE user = ? AND project = ?", (user, project))
    return curs.fetchone()

@opendb
def exist_project(user, project):
    curs.execute("SELECT project FROM project WHERE user = ? AND project = ?", (user, project))
    return bool(curs.fetchone())


@opendb
def delete_project(user, project):
    curs.execute("DELETE FROM project WHERE user = ? AND project = ?",
                 (user, project)
                 )
    curs.execute("DELETE FROM project WHERE user = ? AND project REGEXP ?",
                 (user, r'{}/.+'.format(project))
                 )
    curs.execute("DELETE FROM project WHERE user = ? AND project = ?",
                 (user, project)
                 )
    curs.execute("DELETE FROM document WHERE user = ? AND project REGEXP ?",
                 (user, r'{}/.+'.format(project))
                 )
    conn.commit()
    return True

@opendb
def get_subproject(user, project):
    if project is None:
        project = ""
    curs.execute("SELECT * FROM project WHERE user = :user AND parent_project = :parent",
                 {"user": user, "parent": project}
                 )
    return curs.fetchall()

@opendb
def get_all_subproject(user, project):
    if project is None or project == "":
        curs.execute("SELECT project FROM project WHERE user = :user", {"user": user})
    else :
        curs.execute("SELECT project FROM project WHERE user = :user AND project LIKE :parp ",
                     {"user": user, "parp": "{}/%".format(project)}
                     )
    return curs.fetchall()

@opendb
def get_project_document(user, project):
    curs.execute("SELECT * FROM document WHERE user = ? AND project = ?",
                 (user, project)
                 )
    return curs.fetchall()

# ==========
# Define High Level Functions
# ==========

def login(id):
    session["login_state"] = 1
    session["id"] = id
    session["name"] = get_user_name_by_id(id)


def logout():
    session["login_state"] = 0





# =========
# Define Compile Functions
# ==========
def GFM_LMX(raw, extended = True):
    lastendpos = 0


    output = md(raw)


    while 1:

        n = 0
        t = latex_re.search(output, lastendpos)
        if t:

            with TemporaryDirectory(prefix="tmpdir-", dir=dummydir) as tmpdir:
                with NamedTemporaryFile("w", encoding="utf-8", prefix="tmp-", suffix=".tex", dir=tmpdir, delete= False) as tmpf:
                    with open(tmpf.name, 'w', encoding='utf-8') as f:
                        f.write(LATEX_Cs % t.group(3))
                    op = sp.call(
                        "xelatex --no-pdf --output-directory={0} -interaction=nonstopmode --halt-on-error {1}".format(tmpdir, tmpf.name),
                        stdout=NamedTemporaryFile('w', encoding='utf-8', dir=tmpdir, delete=False)
                    )

                    if op == 1:
                        print("XeLaTeX 는 이상한 것이 분명하오 요카지마.")

                    else:
                        tempdvifname = os.path.splitext(tmpf.name)[0] + ".xdv"

                        op2: str = sp.check_output(
                            "dvisvgm --clipjoin -e --stdout --no-fonts {0}".format(tempdvifname),
                        )

                        output = latex_re.sub(op2.decode("utf-8"), output, count=1)


            lastendpos = t.end()
            n += 1
        else:
            break
    return output


def compile(user, project, doc_name, perm):
    print("망내나")
    """
    try:
        t = get_raw(user, project, doc_name)
        if user_permission[perm] >= full_compile_able_permission:
            ot = GFM_LMX(t, extended = True)
        else:
            ot = GFM_LMX(t, extended = False)
        # update
    except KeyError as e:
        log.warning("perm is incorrect")
    """

def compile_project(user, project, perm):
    print("ㅇㅇ")

    return

    allsubproject = get_all_subproject(user, project)
    if not allsubproject:
        for prj in allsubproject:
            t = get_project_document(user, composePath(prj[0]))
            if not t:
                for doc in t:
                    compile(user, prj[0], doc[2])
            else:
                continue

    else:
        return

### Deprecated In USER
def compile_all():
    pass




@app.route("/docs/<user>", methods=["GET"])
@app.route("/docs/<user>/<path:project_path>", methods=["GET"])
def showUser(user, project_path= None):
    if user != ":public:":
        return "없어요"
    else:

        if project_path is None:
            t = get_subproject(user, project_path)
            return render_template("docs_directory.html", projects=t)
        else:
            t = [i for i in project_path.split("/") if i]
            if t[-1][0] == "§":
                t1 = get_compiled(user, composePath(*t[0:-1]), t[-1][1:])
                if t1 is None:
                    return render_template("somethingNotFound.html", document_path = project_path)
                else:
                    return render_template("documentpage.html", document_content = t1[0])

            else:
                if exist_project(user, project_path):
                    return render_template("docs_directory.html", projects = get_subproject(user, project_path), documents = get_project_document(user, project_path))
                else:
                    return render_template("somethingNotFound.html", project_path = project_path)

@app.route("/docs/<user>", methods=["POST"])
@app.route("/docs/<user>/<path:project_path>", methods=["POST"])
def behaviorUser(user, project_path = None):
    if user != ":public:":
        return "없어요"
    else:
        behavior = request.form["behavior"]
        perm = get_user_perm_by_id(session.get("id"))
        if behavior == "compile":
            if project_path is None:
                print("제오리온")
                pass
                # compile_all
            else:
                t = [i for i in project_path.split("/") if i]

                if t[-1][0] == "§":
                    doc_name = t[-1][1:]
                    project = composePath(*t[0:-1])
                    compile(user, project, doc_name, 3)
                else :
                    compile_project(user, project_path, 4)
                return redirect(url_for("showUser", user=user, project_path=project_path))
        return "404"




@app.route("/")
def c():
    return ""

@app.route("/login", methods=["GET", "POST"])
def loginPage():
    if request.method == "GET":
        return render_template("loginpage.html")
    elif request.method == "POST":
        user_id = request.form["id"]
        user_pw = request.form["pw"]
        if match_user_pw(user_id, user_pw):
            login(user_id)
            return redirect(url_for("frontPage"))
        else :
            return redirect(url_for("loginPage"))

@app.route("/logout", methods=["GET", "POST"])
def logoutPage():
    session["login_state"] = 0
    return redirect(url_for("frontPage"))

@app.route("/register", methods=["GET", "POST"])
def registerPage():
    if request.method == "GET":
        return render_template("registerpage.html")
    elif request.method == "POST":
        user_name = request.form["name"]
        user_id = request.form["id"]
        user_pw = request.form["pw"]
        if make_user(user_name, user_id, user_pw, None):
            login(user_id)
            return redirect(url_for("frontPage"))
        else :
            return redirect(url_for("registerPage"))

@app.route("/front/")
def frontPage():
    return render_template("frontpage.html")

"""
@app.route("/compile", methods=['POST'])
def showCompile():
    path = request.form['path']
    if path == None:
        path = ''
        pass
    else:
        compile(composePath(topdir, os.path.splitext(path)[0]))
    return redirect(url_for('showDocument', document_path=path))

@app.route("/compile_dir", methods=['POST'])
def showCompile_dir():
    path = request.form['path']
    if path == None:
        path = ''
        pass
    else:
        for p, dirs, fns in os.walk(composePath(topdir, path)):
            for fn in fns:
                ext = os.path.splitext(fn)[-1]
                if ext == '.md':
                    print(composePath(p, fn))
                    compile(composePath(p, fn))

    return redirect(url_for('showDocument', document_path=path))
"""


if __name__ == '__main__':
    """
    initial setting 해야함
    """
    if not os.path.isdir(dummydir):
        os.makedirs(dummydir)
    app.secret_key = secrets.token_urlsafe(19)
    app.run(host="192.168.0.5", port="54321",)
    #print(get_raw('yenru0', '', 'teset'))
    #compile_all()
    #app.run(host="localhost", port="54321",)
    #mainWindow()